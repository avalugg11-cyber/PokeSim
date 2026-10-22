import copy
import importlib
import json
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import generation, build
from simulation import SimulationTimeout, battle_signature

# Production registry remains untouched; fixtures replace only its dataset boundary.
with patch('gens.get', side_effect=generation):
    import tournament as T
    import search as S
    import pipeline as pipeline


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.registry=patch('gens.get',side_effect=generation);self.registry.start()
        self.addCleanup(self.registry.stop)
        S.use_gen(4)
        self.g=generation(4)
        self.keys=['a','b','c','d']
        self.builds={k:build(4) for k in self.keys}
        self.specs=[self.g.E.make_spec(k,self.builds[k]) for k in self.keys]

    def test_cached_rankings_match_full_results_and_only_replay_changed_pairs(self):
        cache=T.PairCache();stats={}
        first=T.run_round_robin(self.specs,3,99,progress=False,cache=cache,stats=stats)
        self.assertEqual(stats,dict(battles=18,reused_battles=0))
        second=T.run_round_robin(self.specs,3,99,progress=False,cache=cache,stats=stats)
        self.assertEqual(first,second);self.assertEqual(stats,dict(battles=0,reused_battles=18))
        self.specs[0]=self.g.E.make_spec('a',build(4,['TACKLE']))
        changed=T.run_round_robin(self.specs,3,99,progress=False,cache=cache,stats=stats)
        self.assertEqual(stats,dict(battles=9,reused_battles=9))
        self.assertEqual(changed,T.run_round_robin(self.specs,3,99,progress=False))

    def test_cache_seed_games_rules_and_order_boundaries(self):
        cache=T.PairCache();stats={}
        T.run_round_robin(self.specs,3,99,progress=False,cache=cache)
        for games,seed in [(3,100),(2,100)]:
            got=T.run_round_robin(self.specs,games,seed,progress=False,cache=cache,stats=stats)
            self.assertEqual(stats['reused_battles'],0)
            self.assertEqual(got,T.run_round_robin(self.specs,games,seed,progress=False))
        with patch.object(self.g.E.RULES,'turn_limit',1):
            T.run_round_robin(self.specs,2,100,progress=False,cache=cache,stats=stats)
            self.assertEqual(stats['reused_battles'],0)
        self.specs.reverse()
        got=T.run_round_robin(self.specs,2,100,progress=False,cache=cache,stats=stats)
        self.assertEqual(got,T.run_round_robin(self.specs,2,100,progress=False))

    def test_candidate_dedup_returns_aligned_exact_scores(self):
        cands=[build(4,nature='HARDY'),build(4,nature='DOCILE'),build(4,nature='ADAMANT')]
        scorer=S.Scorer(1)
        scores=scorer.score('a',cands,self.specs[1:],3,7)
        expected=[S.evaluate(self.g.E.make_spec('a',c),self.specs[1:],3,7) for c in cands]
        self.assertEqual(scores,expected)
        self.assertEqual(scorer.battles,2*3*3)

    def test_signature_keeps_every_combat_dimension_and_move_order(self):
        spec=self.specs[0];original=battle_signature(spec)
        metadata=copy.deepcopy(spec);metadata['build']['unused_label']='metadata'
        self.assertEqual(original,battle_signature(metadata))
        changes={'hp':spec['hp']+1,'raw':(1,)*5,'ability':'PRESSURE','gender':'F',
                 'key':'b','types':('GHOST','GHOST'),'moves':list(reversed(spec['moves'])),'item':'PLATE'}
        for field,value in changes.items():
            self.assertNotEqual(original,battle_signature(dict(spec,**{field:value})),field)

    def test_dedup_retains_build_inputs_for_form_recalculation(self):
        # Modest's Attack penalty hides one EV-derived stat point here, but a
        # different form's base Attack can expose it when stats are recomputed.
        first=build(4,evs={'atk':0})
        second=build(4,evs={'atk':4})
        a=self.g.E.make_spec('a',first);b=self.g.E.make_spec('a',second)
        self.assertEqual(a['raw'],b['raw'])
        self.assertNotEqual(battle_signature(a,self.g.E.NATURES),battle_signature(b,self.g.E.NATURES))
        hardy=self.g.E.make_spec('a',build(4,nature='HARDY'))
        docile=self.g.E.make_spec('a',build(4,nature='DOCILE'))
        self.assertEqual(battle_signature(hardy,self.g.E.NATURES),battle_signature(docile,self.g.E.NATURES))
        mons=self.g.E.D['mons']
        land=dict(mons['a'],name='SHAYMIN',atk=103,abilities=['NATURAL_CURE'])
        with patch.dict(mons,{'shaymin':land}):
            battles=[]
            for spec in (a,b):
                bt=self.g.E.Battle(spec,self.specs[1],random.Random(7),self.g.brain)
                bt.a.species_key='shayminsky';bt.a.status=self.g.E.FRZ
                bt.update_forms();battles.append(bt.a.raw)
            self.assertNotEqual(*battles)

    def test_opponent_sample_is_bounded_and_spans_field(self):
        keys=list(range(100))
        for sample in (1,8,10,11,32,48,999):
            got=S.select_opponents(keys,0,sample)
            self.assertEqual(len(got),min(sample,99));self.assertEqual(len(got),len(set(got)))
            self.assertNotIn(0,got)
            self.assertEqual(got,S.select_opponents(keys,0,sample,random.Random(0)))
        self.assertNotEqual(S.select_opponents(keys,0,32,random.Random(0)),S.select_opponents(keys,0,32,random.Random(1)))

    def test_rank_one_remains_s_and_gen1_bands_unchanged(self):
        for size in (2,4,10,151,251,416,553):
            self.assertEqual(T.tier_for_rank(1,size),'S')
        self.assertEqual(T.tier_starts(151),T.TIER_STARTS_G1)

    def test_deadlines_interrupt_ranking_and_candidate_work(self):
        deadline=time.monotonic()-1
        with self.assertRaises(SimulationTimeout):T.run_round_robin(self.specs,3,deadline=deadline)
        scorer=S.Scorer(1,deadline)
        with self.assertRaises(SimulationTimeout):scorer.score('a',[build(4)],self.specs,3,7)
        with self.assertRaises(SimulationTimeout):S.evaluate(self.specs[0],self.specs[1:],3,7,deadline)

    def test_search_deadline_saves_last_accepted_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'movesets.json';path.write_text(json.dumps(self.builds))
            events=[]
            converged=S.run(str(path),2,2,1,1,1.5,1e-12,set(),procs=1,
                            emit=lambda kind,**fields:events.append(kind),field_keys=self.keys)
            self.assertFalse(converged);self.assertIn('time_budget',events)
            self.assertEqual(json.loads(path.read_text()),self.builds)

    def test_short_legacy_builds_generate_additions_and_report_ranking_battles(self):
        for gen in (1,2):
            S.use_gen(gen);g=generation(gen);captured=[];events=[]
            class Scorer(S.Scorer):
                battles=0
                def __init__(self,*args):super().__init__(1)
                def close(self):pass
                def finalists(self,key,current,cands,opps,games,seed):
                    captured.extend(cands)
                    return 0,[(0,c) for c in cands[:4]]
                def score(self,key,cands,opps,games,seed):
                    captured.extend(cands);return [0]*len(cands)
            with tempfile.TemporaryDirectory() as tmp,patch.object(S,'Scorer',Scorer):
                path=Path(tmp)/'movesets.json';path.write_text(json.dumps({'a':['TACKLE'],'b':['TACKLE']}))
                self.assertFalse(S.run(str(path),1,1,1,1,1.5,0,{'a'},procs=1,
                      emit=lambda kind,**fields:events.append((kind,fields)),field_keys=['a','b']))
                self.assertTrue(any(len(c)==2 for c in captured))
                result=next(fields for kind,fields in events if kind=='mon_result')
                self.assertEqual(result['ranking_battles'],0)

    def test_complete_small_pipeline_all_generations(self):
        for gen in range(1,5):
            with self.subTest(gen=gen),tempfile.TemporaryDirectory() as tmp:
                g=generation(gen)
                argv=['pipeline.py','--gen',str(gen),'--out',tmp,'--limit','2',
                      '--passes','1','--sample','1','--screen-games','1','--confirm-games','1',
                      '--games','1','--procs','1','--seed','7','--fresh']
                # Keep the integration fixture small while exercising the real scorer.
                with patch.object(g.P,'pool',return_value=['TACKLE','THUNDERBOLT','RECOVER','BODY_SLAM']),patch.object(sys,'argv',argv),patch.object(pipeline,'emit'):
                    pipeline.main()
                result=json.loads((Path(tmp)/'results.json').read_text())
                self.assertEqual(result['meta']['generation'],gen)
                self.assertEqual(len(result['cards']),2)
                self.assertEqual({c['level'] for c in result['cards']},{50})
                self.assertEqual(result['meta']['rules']['battle_level'],50)
                self.assertIsNone(result['meta']['rules']['learn_level_cap'])
                for name in ('movesets.json','results.csv','type_stats.csv'):
                    self.assertTrue((Path(tmp)/name).is_file(),(gen,name))

    def test_pipeline_skip_search_preserves_saved_builds_even_with_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'movesets.json';path.write_text(json.dumps(self.builds))
            argv=['pipeline.py','--gen','4','--out',tmp,'--fresh','--skip-search','--games','1','--procs','1','--seed','7']
            with patch.object(sys,'argv',argv),patch.object(S,'save',side_effect=AssertionError('saved builds replaced')),patch.object(pipeline,'emit'):
                pipeline.main()
            self.assertEqual(json.loads(path.read_text()),self.builds)
            self.assertFalse((Path(tmp)/'movesets.prev.json').exists())
            self.assertTrue((Path(tmp)/'results.json').is_file())
