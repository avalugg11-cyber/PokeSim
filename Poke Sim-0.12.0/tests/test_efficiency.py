import copy
import itertools
import json
import random
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import generation, build
from damage_estimates import _sum_hits
from reference_damage import calc_base as old_damage
import search as S


class EfficiencyTests(unittest.TestCase):
    def battle(self, gen):
        g=generation(gen)
        return g,g.E.Battle(g.E.make_spec('a',build(gen)),g.E.make_spec('b',build(gen)),random.Random(7),g.brain)

    def move(self,g,effect,name='TEST',power=25,chance=20,**extra):
        return g.base.Move(name,dict(type='BUG',effect=effect,power=power,chance=chance,acc=100,pp=20,category='PHYSICAL',**extra))

    def test_multi_hit_ko_and_shared_independent_rolls(self):
        for gen in range(1,5):
            g,bt=self.battle(gen)
            effect='ATTACK_TWICE_EFFECT' if gen==1 else 'EFFECT_DOUBLE_HIT' if gen==2 else 'DOUBLE_HIT'
            mv=self.move(g,effect,power=30)
            single=g.brainmod._single_est(bt.a,bt.b,mv)
            target=single[2]+1
            estimate=g.brainmod.est(bt.a,bt.b,mv)
            self.assertGreaterEqual(estimate[0],target)
            self.assertAlmostEqual(g.brainmod.ko_prob(bt.a,bt.b,mv,target),g.brainmod.hit_p(bt.a,bt.b,mv))
            bt.b.hp=target;bt.rnd=lambda n:255;bt.hit=lambda *args:True
            bt.dmg_move(bt.a,bt.b,mv,False if gen==1 else 'normal')
            self.assertEqual(bt.b.hp,0)
        rolls=((1,2),)
        self.assertEqual(dict(_sum_hits(rolls,((2,1.),),True)),{2:.5,4:.5})
        self.assertEqual(dict(_sum_hits(rolls,((2,1.),),False)),{2:.25,3:.5,4:.25})

    def test_multi_distribution_matches_brute_force(self):
        from collections import Counter
        rolls=((1,2),(2,3),(3,4))
        weights=((1,.1),(2,.09),(3,.81))
        want=Counter()
        for hits,weight in weights:
            for combo in itertools.product(*rolls[:hits]):want[sum(combo)]+=weight/2**hits
        got=dict(_sum_hits(rolls,weights,False))
        self.assertEqual(set(want),set(got))
        for damage in want:self.assertAlmostEqual(want[damage],got[damage])

    def test_secondary_abilities_and_frozen_flash_fire(self):
        for gen in (3,4):
            for effect,chance,rng in [('POISON_FANG',30,100),('POISON_MULTI_HIT',20,80)]:
                for ability,expected in [('KEEN_EYE',0),('SERENE_GRACE',generation(gen).E.PSN)]:
                    g,bt=self.battle(gen);bt.a.ability=ability;bt.b.hp=10000;bt.rnd=lambda n:rng
                    bt.dmg_move(bt.a,bt.b,self.move(g,effect,chance=chance),'normal')
                    self.assertEqual(bt.b.status,expected)
            for attacker,poisoned in [('KEEN_EYE',False),('MOLD_BREAKER',gen==4)]:
                g,bt=self.battle(gen);bt.a.ability=attacker;bt.b.ability='SHIELD_DUST';bt.b.hp=10000;bt.rnd=lambda n:0
                bt.dmg_move(bt.a,bt.b,self.move(g,'POISON_MULTI_HIT'),'normal')
                self.assertEqual(bt.b.status==g.E.PSN,poisoned)
            for frozen in (False,True):
                g,bt=self.battle(gen);bt.b.ability='FLASH_FIRE';bt.b.status=g.E.FRZ if frozen else 0
                mv=g.base.Move('FLAMETHROWER',dict(type='FIRE',power=95,acc=100,pp=15,effect='BURN_HIT',chance=10,category='SPECIAL'))
                self.assertEqual(g.brainmod.est(bt.a,bt.b,mv)[2]>0,frozen)

    def test_skill_link_substitute_and_endure(self):
        g,bt=self.battle(4);bt.a.ability='SKILL_LINK';bt.b.hp=10000;bt.rnd=lambda n:128
        mv=self.move(g,'MULTI_HIT');bt.hit=lambda *args:True
        with patch.object(bt,'deal',wraps=bt.deal) as deal:bt.dmg_move(bt.a,bt.b,mv,'normal')
        self.assertEqual(deal.call_count,5)
        estimate=g.brainmod.est(bt.a,bt.b,mv)
        single=g.brainmod._single_est(bt.a,bt.b,mv)
        self.assertEqual(estimate[0],5*single[0]);self.assertEqual(estimate[2],5*single[2])
        bt.b.enduring=True;bt.b.hp=10
        self.assertEqual(g.brainmod.ko_prob(bt.a,bt.b,mv,10),0)
        for gen in (1,2):
            g,bt=self.battle(gen);bt.b.sub=1
            mv=self.move(g,'ATTACK_TWICE_EFFECT' if gen==1 else 'EFFECT_DOUBLE_HIT')
            self.assertEqual(g.brainmod.est(bt.a,bt.b,mv)[2],1)

    def test_gen4_prepared_damage_matches_original_all_rolls(self):
        g,bt=self.battle(4)
        reference=types.FunctionType(old_damage.__code__,g.base.__dict__)
        rng=random.Random(813)
        effects=['NORMAL_HIT','BEAT_UP','FUTURE_SIGHT','SELFDESTRUCT','BRICK_BREAK','SOLARBEAM']
        abilities=['KEEN_EYE','ADAPTABILITY','TINTED_LENS','FILTER','SOLID_ROCK','UNAWARE','MOLD_BREAKER','GUTS','SNIPER','SCRAPPY']
        chart={'BUG':{'NORMAL':20,'FIRE':5,'GHOST':0},'FIRE':{'NORMAL':5,'FIRE':20,'GHOST':0}}
        with patch.dict(g.base.CHART,chart,clear=True):
            for i in range(600):
                for mon in (bt.a,bt.b):
                    mon.ability=rng.choice(abilities);mon.types=(rng.choice(['NORMAL','FIRE','GHOST']),rng.choice(['NORMAL','FIRE','GHOST']))
                    mon.stage=[rng.randrange(-6,7) for _ in mon.stage]
                    mon.status=rng.choice([0,g.E.BRN]);mon.lvl=rng.randrange(1,101)
                    mon.reflect=rng.randrange(2);mon.lscreen=rng.randrange(2)
                bt.weather=rng.choice([None,'sun','rain','sand','hail']);bt.a.flash_fire=bool(rng.randrange(2));bt.a.me_first=bool(rng.randrange(2))
                mv=self.move(g,rng.choice(effects),power=rng.randrange(1,201));mv.type=rng.choice(['FIRE','BUG'])
                crit=bool(rng.randrange(2));power=rng.choice([None,10,30,100])
                want=tuple(reference(bt.a,bt.b,mv,crit,power,r) for r in range(85,101))
                self.assertEqual(g.base.damage_rolls(bt.a,bt.b,mv,crit,power),want,(i,mv.effect))
                self.assertEqual(tuple(g.base.calc_base(bt.a,bt.b,mv,crit,power,r) for r in range(85,101)),want)

    def test_exact_race_matches_exhaustive_with_ties_all_gens(self):
        with patch('gens.get',side_effect=generation):
            for gen in range(1,5):
                S.use_gen(gen);g=generation(gen);cur=build(gen)
                cands=[build(gen,[a,b]) for a,b in itertools.permutations(['TACKLE','BODY_SLAM','THUNDERBOLT','RECOVER','SPLASH'],2)]
                if gen>=3:cands += [build(gen,nature=n) for n in ['HARDY','DOCILE','QUIRKY','ADAMANT']]
                cands=S.distinct_candidates('a',cur,cands)
                opps=[g.E.make_spec(k,build(gen)) for k in ('b','c','d')]
                for seed in (7,18):
                    full=S.Scorer(1);race=S.Scorer(1)
                    scores=full.score('a',[cur]+cands,opps,3,seed)
                    want=sorted(zip(scores[1:],cands),key=lambda p:-p[0])[:4]
                    base,got=race.finalists('a',cur,cands,opps,3,seed)
                    self.assertEqual(base,scores[0]);self.assertEqual(got,want)
                    self.assertLessEqual(race.battles,full.battles)

    def test_checkpoint_no_alternatives_and_two_pass_stability(self):
        with patch('gens.get',side_effect=generation),tempfile.TemporaryDirectory() as tmp:
            S.use_gen(4);g=generation(4);path=Path(tmp)/'movesets.json'
            path.write_text(json.dumps({k:build(4) for k in ('a','b','c')}))
            args=(str(path),1,1,1,1,1.5,0,set())
            kwargs=dict(procs=1,field_keys=['a','b'],emit=lambda *a,**kw:None,seed=17)
            with patch.object(g.P,'neighbours',return_value=[]),patch.object(S.Scorer,'score',side_effect=AssertionError('no work')):
                self.assertFalse(S.run(*args,**kwargs))
                first=json.loads(Path(str(path)+'.search.json').read_text())
                self.assertTrue(S.run(*args,**kwargs))
                second=json.loads(Path(str(path)+'.search.json').read_text())
                self.assertEqual(second['next_pass'],first['next_pass']+1)
                self.assertEqual(second['stable'],2)
                self.assertIn('c',json.loads(path.read_text()))
                self.assertFalse(S.run(*args,**kwargs,fresh=True))
                third=json.loads(Path(str(path)+'.search.json').read_text())
                self.assertEqual(third['next_pass'],2)

    def test_cli_help_does_not_load_any_generation(self):
        for module in ('tournament','search','pipeline'):
            command=f"import gens,runpy,sys; gens.get=lambda n: (_ for _ in ()).throw(AssertionError('eager data load')); sys.argv=['{module}','--gen','4','--help']; runpy.run_module('{module}',run_name='__main__')"
            result=subprocess.run([sys.executable,'-c',command],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_rough_skin_can_stop_multi_hits_before_five(self):
        for gen in (3,4):
            g,bt=self.battle(gen);bt.b.ability='ROUGH_SKIN'
            bt.a.hp=2*max(1,bt.a.maxhp//(16 if gen==3 else 8))
            mv=self.move(g,'MULTI_HIT',contact=True)
            maximum=g.brainmod._single_est(bt.a,bt.b,mv)[2]
            self.assertEqual(g.brainmod.est(bt.a,bt.b,mv)[2],2*maximum)

    def test_resume_uses_new_scoring_streams(self):
        with patch('gens.get',side_effect=generation),tempfile.TemporaryDirectory() as tmp:
            S.use_gen(4);g=generation(4);path=Path(tmp)/'movesets.json'
            path.write_text(json.dumps({k:build(4) for k in ('a','b','c','d')}))
            streams=[]
            class Spy(S.Scorer):
                def finalists(self,key,current,cands,opps,games,seed,count=4):
                    streams.append(('screen',seed,[o['key'] for o in opps]))
                    return 0,[(0,cands[0])]
                def score(self,key,cands,opps,games,seed):
                    streams.append(('confirm',seed,[o['key'] for o in opps]))
                    return [0]*len(cands)
            with patch.object(S,'Scorer',Spy):
                for _ in range(2):
                    S.run(str(path),1,2,1,1,1.5,0,{'a'},procs=1,emit=lambda *a,**kw:None,
                          field_keys=['a','b','c','d'],seed=7)
            self.assertEqual(len(streams),4)
            self.assertEqual(len({seed for _,seed,_ in streams}),4)

    def test_api_data_errors_are_json_and_gen1_loads_offline(self):
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer
        import app
        for failing in (True,False):
            context=patch.object(app,'_load_engine',side_effect=ValueError('data unavailable')) if failing else patch('gens.gen1.data.fetch',side_effect=AssertionError('network'))
            with context:
                server=ThreadingHTTPServer(('127.0.0.1',0),app.H)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    try:response=urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/pokemon?gen=1',timeout=5)
                    except urllib.error.HTTPError as error:response=error
                    with response:
                        body=json.load(response)
                        self.assertEqual(response.status,500 if failing else 200)
                        if failing:self.assertIn('data unavailable',body['error'])
                        else:self.assertEqual(len(body['mons']),151)
                finally:
                    server.shutdown();server.server_close();thread.join(5)
                    self.assertFalse(thread.is_alive())
