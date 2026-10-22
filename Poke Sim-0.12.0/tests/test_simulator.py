import copy
import random
import types
import unittest
from unittest.mock import patch

from fixtures import generation, build


class MechanicsTests(unittest.TestCase):
    def battle(self, gen, moves=None):
        g = generation(gen)
        return g, g.E.Battle(g.E.make_spec('a', build(gen,moves)),
                            g.E.make_spec('b',build(gen)), random.Random(3),g.brain)

    def test_uproar_ends_and_spends_pp_for_next_use(self):
        for gen in (3,4):
            with self.subTest(gen=gen):
                g, bt = self.battle(gen,['UPROAR'])
                bt.a.hp=bt.b.hp=bt.a.maxhp=bt.b.maxhp=1000000
                modes=[]
                for turn in range(1,7):
                    bt.turn=turn
                    action=bt.pick(bt.a,bt.b);modes.append(action[2])
                    bt.act(bt.a,bt.b,*action)
                    bt.between_turns((bt.a,bt.b))
                self.assertIn('normal',modes[1:])
                self.assertLess(bt.a.pp[0],29)

    def test_uproar_interruption_releases_lock(self):
        for gen in (3,4):
            g,bt=self.battle(gen,['UPROAR']);bt.a.uproar=3;bt.a.flinch=True
            bt.act(bt.a,bt.b,g.E.MV['UPROAR'],-1,'uproar')
            self.assertEqual(bt.a.uproar,0)

    def test_wake_up_slap_only_cures_unprotected_sleep(self):
        for status in (0,1,2,3,4,5):
            for substitute in (0,1,10000):
                with self.subTest(status=status,substitute=substitute):
                    g,bt=self.battle(4);bt.b.status=status;bt.b.slp=3;bt.b.sub=substitute
                    bt.dmg_move(bt.a,bt.b,g.E.MV['WAKE_UP_SLAP'],'normal')
                    self.assertEqual(bt.b.status,0 if status==g.E.SLP and not substitute else status)

    def test_serene_grace_doubles_ancient_power(self):
        for ability,expected in [('KEEN_EYE',0),('SERENE_GRACE',1)]:
            g,bt=self.battle(3);bt.a.ability=ability;bt.rnd=lambda n:40
            bt.dmg_move(bt.a,bt.b,g.E.MV['ANCIENT_POWER'],'normal')
            self.assertEqual(bt.a.stage[:5],[expected]*5)

    def test_serene_grace_poison_secondary_branches(self):
        g=generation(3)
        for name,effect,power,chance in [('POISON_FANG','POISON_FANG',50,30),
                                         ('TWINEEDLE','POISON_MULTI_HIT',25,20)]:
            move=g.base.Move(name,dict(type='BUG',power=power,acc=100,pp=20,effect=effect,chance=chance))
            for ability,expected in [('KEEN_EYE',0),('SERENE_GRACE',g.E.PSN)]:
                _,bt=self.battle(3);bt.a.ability=ability;bt.rnd=lambda n:100 if effect=='POISON_FANG' else 80
                bt.dmg_move(bt.a,bt.b,move,'normal')
                self.assertEqual(bt.b.status,expected,(name,ability))

    def test_lock_on_ohko_and_restrictions(self):
        for gen in (2,3):
            for locked,protected,higher,expected in [(False,False,False,False),
                    (True,False,False,True),(True,True,False,False),(True,False,True,False)]:
                with self.subTest(gen=gen,locked=locked,protected=protected,higher=higher):
                    g,bt=self.battle(gen);bt.rnd=lambda n:255
                    if locked:bt.status_move(bt.a,bt.b,g.E.MV['LOCK_ON'])
                    bt.b.protecting=protected
                    if higher:bt.b.lvl+=1
                    if locked:self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,g.E.MV['FISSURE']),1.0 if expected else 0.0)
                    before=bt.b.hp;bt.dmg_move(bt.a,bt.b,g.E.MV['FISSURE'],'normal')
                    self.assertEqual(bt.b.hp==0,expected)
                    if not expected:self.assertEqual(bt.b.hp,before)

    def test_gen2_beat_up_uses_base_stats_and_status_eligibility(self):
        g,bt=self.battle(2)
        mv=g.E.MV['BEAT_UP'];expected=((22*10*80//80)//50)+2
        self.assertEqual(g.base.calc_base(bt.a,bt.b,mv),expected)
        bt.a.stage[3]=6;bt.b.lscreen=5;bt.a.raw=(999,)*5;bt.b.raw=(999,)*5
        self.assertEqual(g.base.calc_base(bt.a,bt.b,mv),expected)
        bt.a.status=g.E.PAR
        self.assertEqual(g.base.calc_base(bt.a,bt.b,mv),0)
        bt.b.hp=1000;bt.dmg_move(bt.a,bt.b,mv,'normal')
        self.assertEqual(bt.b.hp,1000)
        bt.a.status=0
        bt.b.types=('GHOST','GHOST')
        self.assertEqual(g.base.mtype_of(mv),'TYPELESS')

    def test_gen2_transform_tracks_target_species_for_beat_up(self):
        g,bt=self.battle(2)
        bt.status_move(bt.a,bt.b,g.E.MV['TRANSFORM'])
        self.assertEqual(bt.a.species_key,'b')
        self.assertEqual(bt.a.key,'a')

    def test_pool_cache_returns_independent_lists(self):
        for gen in (1,2,3,4):
            g=generation(gen);before=g.P.pool('a');changed=g.P.pool('a');changed.clear()
            self.assertEqual(g.P.pool('a'),before)
            with patch('move_rules.level_pool',side_effect=AssertionError('pool rebuilt')):
                self.assertEqual(g.P.pool('a'),before)

    def test_neighbors_can_add_second_and_fourth_move(self):
        for gen in (3,4):
            g=generation(gen)
            for moves in [['TACKLE'],['TACKLE','BODY_SLAM','RECOVER']]:
                current=build(gen,moves)
                neighbors=g.P.neighbours('a',current,g.P.pool('a'))
                self.assertTrue(any(len(c['moves'])==len(moves)+1 for c in neighbors))
                for candidate in neighbors:g.E.make_spec('a',candidate)

    def test_estimate_reuse_preserves_outcomes(self):
        for gen in range(1,5):
            g=generation(gen);brain=g.brainmod
            scope=dict(brain.__dict__)
            scope['exp_dmg']=lambda *args,_fn=brain.exp_dmg,**kw:_fn(*args[:4])
            scope['ko_prob']=lambda *args,_fn=brain.ko_prob,**kw:_fn(*args[:4])
            reference=types.FunctionType(brain.brain.__code__,scope)
            for moves in [None,['TACKLE','REFLECT','RECOVER','SELFDESTRUCT']]:
                a=g.E.make_spec('a',build(gen,moves));b=g.E.make_spec('b',build(gen))
                for seed in range(40):
                    old=g.E.Battle(a,b,random.Random(seed),reference);new=g.E.Battle(a,b,random.Random(seed),g.brain)
                    self.assertEqual((old.run(),old.a.hp,old.b.hp,old.turn),
                                     (new.run(),new.a.hp,new.b.hp,new.turn),(gen,moves,seed))

    def test_estimate_call_count(self):
        for gen in range(1,5):
            g,bt=self.battle(gen)
            with patch.object(g.brainmod,'est',wraps=g.brainmod.est) as counted:
                g.brain(bt.a,bt.b)
            self.assertEqual(counted.call_count,6)

    def test_logging_only_formats_when_enabled(self):
        class Name:
            def __format__(self,s):raise AssertionError('unused log formatted')
        for gen in range(1,5):
            g,bt=self.battle(gen);bt.a.name=Name()
            bt.act(bt.a,bt.b,g.E.MV['TACKLE'],0,'normal')
            g,bt=self.battle(gen);bt.log=[]
            bt.act(bt.a,bt.b,g.E.MV['TACKLE'],0,'normal')
            self.assertTrue(bt.log)
