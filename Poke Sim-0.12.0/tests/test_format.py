"""Independent checks of the authorized level50/full-natural-learnset format."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fixtures import generation, build
import search as S

GROWTHS = ('SLOW', 'MEDIUM_FAST', 'MEDIUM_SLOW', 'FAST', 'ERRATIC', 'FLUCTUATING')

class FormatTests(unittest.TestCase):
    def test_all_growth_groups_use_level50_and_level50_stats(self):
        for gen in range(1,5):
            g=generation(gen)
            for growth in GROWTHS:
                with self.subTest(gen=gen,growth=growth):
                    record=copy.deepcopy(g.E.D['mons']['a'])
                    record['growth']='GROWTH_'+growth
                    with patch.dict(g.E.D['mons'],{'formatstat':record}):
                        g.P._pool.cache_clear()
                        spec=g.E.make_spec('formatstat',build(gen,['TACKLE'],nature='HARDY',evs={}))
                        self.assertEqual(spec['lvl'],50)
                        # Fixture species: all base stats80, DVs15/stat-exp11000
                        # in Gen1/2; IV31/noEVs/neutral nature in Gen3/4.
                        self.assertEqual(spec['hp'],168 if gen<3 else 155)
                        stats=spec['st'] if gen==1 else spec['raw']
                        self.assertEqual(stats,(113,)*(4 if gen==1 else 5) if gen<3 else (100,)*5)
            g.P._pool.cache_clear()

    def test_high_level_moves_available_without_changing_stats(self):
        for gen in range(1,5):
            g=generation(gen);record=copy.deepcopy(g.E.D['mons']['a'])
            record.update(start=['TACKLE'],lvl=[[80,'RECOVER'],[100,'BODY_SLAM']],tm=['THUNDERBOLT'])
            with patch.dict(g.E.D['mons'],{'formathigh':record}):
                g.P._pool.cache_clear()
                self.assertEqual(g.P.pool('formathigh'),['BODY_SLAM','RECOVER','TACKLE'])
                for level in (1,50,80,100):
                    self.assertEqual(g.P.pool('formathigh',level),g.P.pool('formathigh'))
                low=g.E.make_spec('formathigh',build(gen,['TACKLE']))
                high=g.E.make_spec('formathigh',build(gen,['RECOVER','BODY_SLAM']))
                self.assertEqual(high['lvl'],50)
                self.assertEqual(high['hp'],low['hp'])
                self.assertEqual(high.get('raw',high.get('st')),low.get('raw',low.get('st')))
                with self.assertRaises(ValueError):g.E.make_spec('formathigh',build(gen,['THUNDERBOLT']))
            g.P._pool.cache_clear()

    def test_full_preevolution_learnsets_and_baby_only_eggs(self):
        for gen in range(1,5):
            g=generation(gen)
            parent=copy.deepcopy(g.E.D['mons']['a']);parent.update(lvl=[[80,'RECOVER']],evolutions=[['LEVEL',80,'FORMATCHILD']])
            child=copy.deepcopy(parent);child.update(lvl=[[1,'TACKLE']],evolutions=[])
            baby=copy.deepcopy(child);baby['evolutions']=[['HAPPINESS',0,'FORMATCHILD']]
            with patch.dict(g.E.D['mons'],{'formatparent':parent,'formatchild':child,'pichu':baby}),patch.dict(g.E.D,{'baby_eggs':{'pichu':['THUNDERBOLT']}}):
                g.P._pool.cache_clear()
                self.assertIn('RECOVER',g.P.pool('formatchild'))
                self.assertNotIn('THUNDERBOLT',g.P.pool('formatchild'))
                self.assertIn('THUNDERBOLT',g.P.pool('pichu'))
            g.P._pool.cache_clear()

    def test_spec_cannot_override_level_or_exceed_four_moves(self):
        for gen in range(1,5):
            g=generation(gen)
            self.assertEqual(g.E.make_spec('a',build(gen),level=50)['lvl'],50)
            for level in (1,49,51,100,True,50.0,'50'):
                with self.assertRaisesRegex(ValueError,'level 50'):
                    g.E.make_spec('a',build(gen),level=level)
            with self.assertRaises(ValueError):
                g.E.make_spec('a',build(gen,['TACKLE','BODY_SLAM','THUNDERBOLT','RECOVER','SPLASH']))

    def test_resume_keeps_builds_but_resets_old_engine_evidence(self):
        with patch('gens.get',side_effect=generation):
            for gen in range(1,5):
                with self.subTest(gen=gen),tempfile.TemporaryDirectory() as tmp:
                    S.use_gen(gen);g=generation(gen);path=Path(tmp)/'movesets.json'
                    saved={k:build(gen,['TACKLE']) for k in ('a','b')}
                    path.write_text(json.dumps(saved))
                    args=(str(path),2,1,1,1,1.5,0,set())
                    kw=dict(procs=1,field_keys=['a','b'],emit=lambda *a,**kw:None,seed=17)
                    with patch.object(S,'distinct_candidates',return_value=[]):
                        with patch.object(g.E,'ENGINE_VERSION','0.10.2'):
                            self.assertTrue(S.run(*args,**kw))
                        old=json.loads(Path(str(path)+'.search.json').read_text())
                        self.assertEqual(old['stable'],2)
                        self.assertFalse(S.run(str(path),1,*args[2:],**kw))
                    new=json.loads(Path(str(path)+'.search.json').read_text())
                    self.assertNotEqual(new['context'],old['context'])
                    self.assertEqual((new['stable'],new['next_pass']),(1,2))
                    resumed=json.loads(path.read_text())
                    self.assertEqual(resumed,saved)
