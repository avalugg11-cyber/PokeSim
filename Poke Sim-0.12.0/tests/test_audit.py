"""Regressions from the follow-up Gen 1–4 source audit.

References are pinned game-source routines listed in the diagnostic report.
Fixtures instantiate production engines with synthetic species; no downloads.
"""
import random
import unittest
from unittest.mock import patch

from fixtures import generation, build


class AuditTests(unittest.TestCase):
    def battle(self, gen):
        g=generation(gen)
        bt=g.E.Battle(g.E.make_spec('a',build(gen)),g.E.make_spec('b',build(gen)),random.Random(7),g.brain)
        return g,bt

    def move(self,g,name,effect,power=0,typ='NORMAL',**extra):
        if g.id==2:effect='EFFECT_'+effect
        data=dict(type=typ,effect=effect,power=power,chance=0,acc=100,pp=20,category='PHYSICAL' if power else 'STATUS')
        data.update(extra)
        return g.base.Move(name,data)

    def test_lock_on_fails_against_substitute(self):
        for gen in (2,3,4):
            with self.subTest(gen=gen):
                g,bt=self.battle(gen);bt.b.sub=10
                bt.status_move(bt.a,bt.b,g.E.MV['LOCK_ON'])
                self.assertFalse(bt.a.lockon)

    def test_gen2_draining_attacks_fail_against_substitute(self):
        for effect,name in [('LEECH_HIT','ABSORB'),('DREAM_EATER','DREAM_EATER')]:
            with self.subTest(move=name):
                g,bt=self.battle(2);bt.a.hp-=20;bt.b.sub=50;bt.b.status=g.E.SLP
                mv=self.move(g,name,effect,40,typ='GRASS' if name=='ABSORB' else 'PSYCHIC_TYPE')
                state=(bt.a.hp,bt.b.hp,bt.b.sub)
                bt.dmg_move(bt.a,bt.b,mv,'normal')
                self.assertEqual((bt.a.hp,bt.b.hp,bt.b.sub),state)
                self.assertEqual(g.brainmod.est(bt.a,bt.b,mv)[2],0)

    def test_always_hit_policy_respects_fly_and_dig(self):
        for gen in (2,3,4):
            for invuln in ('fly','dig'):
                with self.subTest(gen=gen,invuln=invuln):
                    g,bt=self.battle(gen);bt.b.invuln=invuln
                    mv=self.move(g,'SWIFT','ALWAYS_HIT',60)
                    self.assertFalse(bt.hit(bt.a,bt.b,mv))
                    self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),0)

    def test_soundproof_policy_matches_execution(self):
        for gen in (3,4):
            with self.subTest(gen=gen):
                g,bt=self.battle(gen);bt.b.ability='SOUNDPROOF'
                mv=self.move(g,'UPROAR','UPROAR',50,sound=True)
                self.assertFalse(bt.hit(bt.a,bt.b,mv))
                self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),0)
                bt.a.ability='MOLD_BREAKER'
                self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),1 if gen==4 else 0)

    def test_gen2_thunder_can_hit_fly_and_fissure_can_hit_dig(self):
        g,bt=self.battle(2);bt.b.invuln='fly';bt.weather='rain'
        thunder=self.move(g,'THUNDER','THUNDER',120,typ='ELECTRIC',acc=70)
        self.assertTrue(bt.hit(bt.a,bt.b,thunder))
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,thunder),1)
        g,bt=self.battle(2);bt.b.invuln='dig';bt.rnd=lambda n:0
        bt.dmg_move(bt.a,bt.b,g.E.MV['FISSURE'],'normal')
        self.assertEqual(bt.b.hp,0)

    def test_gen2_rage_multiplies_damage_after_stab_and_resets(self):
        g,bt=self.battle(2);mv=self.move(g,'RAGE','RAGE',20)
        first=g.base.calc_base(bt.a,bt.b,mv)
        bt.a.rage_n=3
        self.assertEqual(g.base.calc_base(bt.a,bt.b,mv),min(65535,3*first))
        bt.act(bt.a,bt.b,g.E.MV['RECOVER'],0,'normal')
        self.assertEqual(bt.a.rage_n,1)
        bt.a.rage=True;bt.a.rage_n=256;bt.b.hp=10000
        bt.rnd=lambda n:255;bt.hit=lambda *a:True
        bt.dmg_move(bt.b,bt.a,g.E.MV['TACKLE'],'normal')
        self.assertLessEqual(bt.a.rage_n,256)

    def test_gen3_bide_always_releases_on_third_turn(self):
        g,bt=self.battle(3);mv=self.move(g,'BIDE','BIDE')
        for value in (0,1,254,255):
            with self.subTest(rng=value):
                bt.rnd=lambda n:value
                bt.status_move(bt.a,bt.b,mv)
                self.assertEqual(bt.a.bide_left,2)

    def test_mold_breaker_does_not_bypass_mist(self):
        g,bt=self.battle(4);bt.a.ability='MOLD_BREAKER';bt.b.mist=True
        self.assertFalse(bt.change_stage(bt.b,0,-1,bt.a))
        self.assertEqual(bt.b.stage[0],0)
        bt.b.mist=False;bt.b.ability='CLEAR_BODY'
        self.assertTrue(bt.change_stage(bt.b,0,-1,bt.a))

    def test_priority_finisher_does_not_choose_an_impossible_hit(self):
        for gen in (1,2,3,4):
            with self.subTest(gen=gen):
                g,bt=self.battle(gen)
                first=self.move(g,'QUICK_ATTACK','NO_ADDITIONAL_EFFECT' if gen==1 else 'PRIORITY_HIT',40,priority=1)
                alternative=self.move(g,'SWIFT','SWIFT_EFFECT',60) if gen==1 else self.move(g,'EARTHQUAKE','NORMAL_HIT',100,typ='GROUND')
                bt.a.moves=[first,alternative];bt.a.pp=[20,20]
                if gen==1:
                    bt.a.st[2]=1;bt.b.st[2]=999;bt.b.invuln=True
                else:
                    bt.a.raw=bt.a.raw[:2]+(1,)+bt.a.raw[3:]
                    bt.b.raw=bt.b.raw[:2]+(999,)+bt.b.raw[3:]
                    bt.b.invuln='dig'
                bt.b.hp=1
                chosen,_=g.brain(bt.a,bt.b)
                self.assertIs(chosen,alternative)

    def test_gen3_gen4_dream_eater_policy_respects_substitute(self):
        for gen in (3,4):
            with self.subTest(gen=gen):
                g,bt=self.battle(gen);bt.b.status=g.E.SLP;bt.b.sub=10
                mv=self.move(g,'DREAM_EATER','DREAM_EATER',100,typ='PSYCHIC')
                state=(bt.a.hp,bt.b.hp,bt.b.sub)
                bt.dmg_move(bt.a,bt.b,mv,'normal')
                self.assertEqual((bt.a.hp,bt.b.hp,bt.b.sub),state)
                self.assertEqual(g.brainmod.est(bt.a,bt.b,mv)[2],0)

    def test_lock_on_targets_and_accuracy_checks(self):
        for gen in (2,3,4):
            for state in ('normal','fly','substitute','protect'):
                with self.subTest(gen=gen,state=state):
                    g,bt=self.battle(gen);bt.rnd=lambda n:0
                    if state=='fly':bt.b.invuln='fly'
                    if state=='substitute':bt.b.sub=10
                    if state=='protect':bt.b.protecting=True
                    bt.status_move(bt.a,bt.b,g.E.MV['LOCK_ON'])
                    self.assertEqual(bt.a.lockon,state=='normal')

    def test_accuracy_bypass_preserves_lock_on_and_no_guard(self):
        for gen in (2,3,4):
            g,bt=self.battle(gen);bt.b.invuln='dig';bt.a.lockon=True
            mv=self.move(g,'SWIFT','ALWAYS_HIT',60)
            self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),1)
            self.assertTrue(bt.hit(bt.a,bt.b,mv))
            if gen==4:
                bt.a.lockon=False;bt.a.ability='NO_GUARD'
                self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),1)
                self.assertTrue(bt.hit(bt.a,bt.b,mv))

    def test_gen2_lock_on_preserves_ground_against_fly_bug(self):
        for name in ('EARTHQUAKE','FISSURE','MAGNITUDE'):
            for locked in (False,True):
                with self.subTest(move=name,locked=locked):
                    g,bt=self.battle(2);bt.b.invuln='fly';bt.a.lockon=locked
                    mv=self.move(g,name,'OHKO' if name=='FISSURE' else 'NORMAL_HIT',0 if name=='FISSURE' else 100,typ='GROUND')
                    self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),0)
                    bt.rnd=lambda n:0
                    if name=='FISSURE':
                        bt.dmg_move(bt.a,bt.b,mv,'normal');self.assertEqual(bt.b.hp,bt.b.maxhp)
                    else:self.assertFalse(bt.hit(bt.a,bt.b,mv))
                    self.assertFalse(bt.a.lockon)

    def test_gen2_rage_damage_rounding_and_saturation(self):
        g,bt=self.battle(2);mv=self.move(g,'RAGE','RAGE',20)
        for crit in (False,True):
            for types in (('NORMAL','NORMAL'),('ROCK','ROCK')):
                for multiplier in (1,2,3,256):
                    with self.subTest(crit=crit,types=types,multiplier=multiplier):
                        bt.b.types=types;bt.a.rage_n=1
                        base=g.base.calc_base(bt.a,bt.b,mv,crit)
                        bt.a.rage_n=multiplier
                        self.assertEqual(g.base.calc_base(bt.a,bt.b,mv,crit),min(65535,base*multiplier))

    def test_gen2_rage_resets_before_faster_opponent_acts(self):
        g,bt=self.battle(2);bt.rules=g.E.Rules(turn_limit=1)
        bt.a.rage=True;bt.a.rage_n=5
        bt.a.raw=bt.a.raw[:2]+(1,)+bt.a.raw[3:]
        bt.b.raw=bt.b.raw[:2]+(999,)+bt.b.raw[3:]
        bt.brain=lambda m,o:(g.E.MV['RECOVER'],2)
        states=[]
        original=bt.act
        def observe(*args):
            states.append((bt.a.rage,bt.a.rage_n))
            return original(*args)
        bt.act=observe;bt.run()
        self.assertTrue(states)
        self.assertEqual(states[0],(False,1))
        bt.a.rage=True;bt.a.rage_n=5;bt.a.flinch=True
        bt.act(bt.a,bt.b,g.E.MV['RECOVER'],2,'normal')
        self.assertEqual((bt.a.rage,bt.a.rage_n),(False,1))

    def test_gen3_bide_release_damage_and_pp(self):
        g,bt=self.battle(3);mv=self.move(g,'BIDE','BIDE')
        bt.a.moves=[mv];bt.a.pp=[10]
        bt.act(bt.a,bt.b,mv,0,'normal')
        self.assertEqual(bt.a.pp,[9])
        bt.deal(bt.b,bt.a,7,g.E.MV['TACKLE'],True)
        bt.act(bt.a,bt.b,mv,-1,'bide')
        self.assertEqual(bt.b.hp,bt.b.maxhp)
        bt.deal(bt.b,bt.a,11,g.E.MV['TACKLE'],True)
        bt.act(bt.a,bt.b,mv,-1,'bide')
        self.assertEqual(bt.b.hp,bt.b.maxhp-36)
        self.assertEqual((bt.a.bide_left,bt.a.bide_acc,bt.a.pp),(0,0,[9]))

    def test_gen1_guaranteed_ko_cannot_hit_fly(self):
        g,bt=self.battle(1)
        impossible=self.move(g,'TACKLE','NO_ADDITIONAL_EFFECT',100)
        swift=self.move(g,'SWIFT','SWIFT_EFFECT',60)
        bt.a.moves=[impossible,swift];bt.a.pp=[10,10]
        bt.a.st[2]=999;bt.b.st[2]=1;bt.b.invuln=True;bt.b.hp=1
        self.assertIs(g.brain(bt.a,bt.b)[0],swift)
        self.assertTrue(bt.hit(bt.a,bt.b,swift))
        self.assertFalse(bt.hit(bt.a,bt.b,impossible))

    def test_gen2_reach_bonus_damage_and_policy_rounding(self):
        for name,state in (('EARTHQUAKE','dig'),('GUST','fly'),('TWISTER','fly'),('MAGNITUDE','dig')):
            with self.subTest(move=name):
                g,bt=self.battle(2)
                mv=self.move(g,name,'NORMAL_HIT',40,typ='GROUND' if state=='dig' else 'FLYING')
                base=g.base.calc_base(bt.a,bt.b,mv,False)
                bt.b.invuln=state
                rolls=tuple(min(65535,2*(base*r//255)) for r in range(217,256))
                estimate=g.brainmod.est(bt.a,bt.b,mv)
                self.assertEqual((estimate[0],estimate[2]),(min(rolls),max(rolls)))
                bt.rnd=lambda n:255;bt.roll=lambda:217;bt.hit=lambda *args:True
                bt.dmg_move(bt.a,bt.b,mv,'normal')
                self.assertEqual(bt.b.maxhp-bt.b.hp,rolls[0])
                threshold=rolls[0]+1
                expected=sum(x>=threshold for x in rolls)/len(rolls)
                self.assertAlmostEqual(g.brainmod.ko_prob(bt.a,bt.b,mv,threshold),expected*g.brainmod.hit_p(bt.a,bt.b,mv))

    def test_gen4_ohko_policy_respects_level_and_semi_invulnerability(self):
        g,bt=self.battle(4);mv=g.E.MV['FISSURE']
        bt.b.invuln='dig'
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),0)
        bt.a.ability='NO_GUARD'
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),1)
        bt.a.lvl=bt.b.lvl-1
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),0)

    def test_drain_moves_still_work_when_allowed(self):
        for gen in (2,3,4):
            for sub in (0,50):
                with self.subTest(gen=gen,sub=sub):
                    g,bt=self.battle(gen);bt.a.hp-=40;bt.b.sub=sub
                    mv=self.move(g,'ABSORB','LEECH_HIT',40,typ='GRASS')
                    bt.rnd=lambda n:255
                    before=(bt.a.hp,bt.b.hp,bt.b.sub)
                    bt.dmg_move(bt.a,bt.b,mv,'normal')
                    if gen==2 and sub:self.assertEqual((bt.a.hp,bt.b.hp,bt.b.sub),before)
                    else:
                        self.assertGreater(bt.a.hp,before[0])
                        self.assertLess(bt.b.hp+bt.b.sub,before[1]+before[2])

    def test_mist_still_allows_self_drops(self):
        g,bt=self.battle(4);bt.a.mist=True;bt.a.ability='MOLD_BREAKER'
        self.assertTrue(bt.change_stage(bt.a,0,-1,bt.a))
        self.assertEqual(bt.a.stage[0],-1)

    def test_gen2_separate_accuracy_evasion_rounding(self):
        # Crystal CheckHit.StatModifiers with accuracy_multipliers.asm.
        g,bt=self.battle(2);mv=self.move(g,'TEST','NORMAL_HIT',40,acc=70)
        cases=((1,0,236),(1,1,177),(2,1,221),(6,6,176),(-6,-6,174),(6,-6,255),(-6,6,19))
        for acc,eva,expected in cases:
            with self.subTest(accuracy_stage=acc,evasion_stage=eva):
                bt.a.stage[5]=acc;bt.b.stage[6]=eva
                self.assertEqual(g.base.acc_thresh(bt.a,bt.b,mv),expected)
        bt.b.foresight=True;bt.a.stage[5]=-1;bt.b.stage[6]=1
        self.assertEqual(g.base.acc_thresh(bt.a,bt.b,mv),178)

    def test_gen2_thunder_sun_changes_base_accuracy_before_stages(self):
        g,bt=self.battle(2);bt.weather='sun'
        mv=self.move(g,'THUNDER','THUNDER',120,typ='ELECTRIC',acc=70)
        for stage,expected in ((0,128),(1,170),(-1,96)):
            with self.subTest(stage=stage):
                bt.a.stage[5]=stage
                self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),expected/256)
                for roll in (expected-1,expected):
                    bt.rnd=lambda n,r=roll:r
                    self.assertEqual(bt.hit(bt.a,bt.b,mv),roll<expected)

    def test_gen2_ohko_byte_accuracy_level_bonus_and_stages(self):
        g,bt=self.battle(2);mv=self.move(g,'FISSURE','OHKO',typ='GROUND',acc=30)
        bt.a.lvl=60;bt.b.lvl=50
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),96/256)
        landed=0
        for roll in range(256):
            bt.b.hp=bt.b.maxhp;bt.rnd=lambda n,r=roll:r
            bt.dmg_move(bt.a,bt.b,mv,'normal')
            landed+=bt.b.hp==0
        self.assertEqual(landed,96)
        bt.a.stage[5]=1
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),127/256)
        bt.a.stage[5]=0;bt.b.stage[6]=1
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),72/256)
        bt.a.lvl=49
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),0)
        bt.a.lvl=100;bt.b.lvl=10;bt.b.stage[6]=0
        self.assertEqual(g.brainmod.hit_p(bt.a,bt.b,mv),1)
        bt.b.hp=bt.b.maxhp;bt.rnd=lambda n:255
        bt.dmg_move(bt.a,bt.b,mv,'normal')
        self.assertEqual(bt.b.hp,0)
