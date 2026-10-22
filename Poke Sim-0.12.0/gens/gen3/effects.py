"""Emerald move effects and ability-aware damage hooks."""
from .base import *

STAT_MOVES = {   
    "CALM_MIND": (True, [(3,1),(4,1)]), "BULK_UP": (True, [(0,1),(1,1)]), "DRAGON_DANCE": (True, [(0,1),(2,1)]), "COSMIC_POWER": (True, [(1,1),(4,1)]), "TICKLE": (False, [(0,-1),(1,-1)]), "SP_ATK_UP_2": (True, [(3,2)]), "SP_DEF_UP": (True, [(4,1)]), "SPEED_UP": (True, [(2,1)]), "ACCURACY_UP": (True, [(5,1)]), "ACCURACY_UP_2": (True, [(5,2)]), "SP_ATK_DOWN": (False, [(3,-1)]), "SP_ATK_DOWN_2": (False, [(3,-2)]), "SP_DEF_DOWN": (False, [(4,-1)]), "SP_DEF_DOWN_2": (False, [(4,-2)]), "EVASION_UP_2": (True, [(6,2)]), "ACCURACY_DOWN_2": (False, [(5,-2)]), "EVASION_DOWN_2": (False, [(6,-2)]), "ATTACK_UP": (True, [(0, 1)]), "ATTACK_UP_2": (True, [(0, 2)]), "DEFENSE_UP": (True, [(1, 1)]),
    "DEFENSE_UP_2": (True, [(1, 2)]), "DEFENSE_CURL": (True, [(1, 1)]), "SP_ATK_UP": (True, [(3, 1)]),
    "SP_DEF_UP_2": (True, [(4, 2)]), "SPEED_UP_2": (True, [(2, 2)]), "EVASION_UP": (True, [(6, 1)]),
    "ACCURACY_DOWN": (False, [(5, -1)]), "ATTACK_DOWN": (False, [(0, -1)]), "ATTACK_DOWN_2": (False, [(0, -2)]),
    "DEFENSE_DOWN": (False, [(1, -1)]), "DEFENSE_DOWN_2": (False, [(1, -2)]), "EVASION_DOWN": (False, [(6, -1)]),
    "SPEED_DOWN": (False, [(2, -1)]), "SPEED_DOWN_2": (False, [(2, -2)])}
HIT_STAT = {  
    "SP_ATK_DOWN_HIT": (False, [(3,-1)]), "EVASION_DOWN_HIT": (False, [(6,-1)]), "ACCURACY_DOWN_HIT": (False, [(5, -1)]), "ATTACK_DOWN_HIT": (False, [(0, -1)]),
    "DEFENSE_DOWN_HIT": (False, [(1, -1)]), "SPEED_DOWN_HIT": (False, [(2, -1)]),
    "SP_DEF_DOWN_HIT": (False, [(4, -1)]), "ATTACK_UP_HIT": (True, [(0, 1)]), "DEFENSE_UP_HIT": (True, [(1, 1)]),
    "ALL_UP_HIT": (True, [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1)])}
STATUS_HIT = {"BURN_HIT": BRN, "FREEZE_HIT": FRZ, "PARALYZE_HIT": PAR, "POISON_HIT": PSN, "SACRED_FIRE": BRN,
              "FLAME_WHEEL": BRN, "THUNDER": PAR, "BLAZE_KICK": BRN, "POISON_TAIL": PSN, "SECRET_POWER": PAR, "POISON_MULTI_HIT": PSN}
SELF_EFFECTS = frozenset(STAT_MOVES[k] and k for k in STAT_MOVES if STAT_MOVES[k][0]) | {
    "FOCUS_ENERGY", "HEAL", "MOONLIGHT", "MORNING_SUN", "SYNTHESIS", "LIGHT_SCREEN", "REFLECT", "SAFEGUARD", "MIST",
    "SUBSTITUTE", "RAIN_DANCE", "SUNNY_DAY", "SANDSTORM", "PROTECT", "ENDURE", "DESTINY_BOND", "PERISH_SONG",
    "BELLY_DRUM", "PSYCH_UP", "METRONOME", "MIRROR_MOVE", "SLEEP_TALK", "CONVERSION", "CONVERSION2", "BATON_PASS",
    "TELEPORT", "SPLASH", "SPIKES", "HEAL_BELL", "SKETCH", "MIMIC", "BIDE", "RAGE", "FORCE_SWITCH", "HAIL", "STOCKPILE", "SWALLOW", "WISH", "INGRAIN", "CHARGE", "REFRESH", "MAGIC_COAT", "SNATCH", "GRUDGE", "MUD_SPORT", "WATER_SPORT", "CAMOUFLAGE",
    "RESET_STATS", "PAIN_SPLIT", "TRANSFORM", "CURSE", "FORESIGHT"}
MAGNITUDE = ((13, 4, 10), (38, 5, 30), (89, 6, 50), (166, 7, 70), (217, 8, 90), (242, 9, 110), (256, 10, 150))
NO_SLEEP_TALK = frozenset({'SLEEP_TALK','ASSIST','MIRROR_MOVE','METRONOME','BIDE','FLY','DIG','DIVE','BOUNCE','SKULL_BASH','SOLAR_BEAM','RAZOR_WIND','SKY_ATTACK','FOCUS_PUNCH','UPROAR'})
SPECIAL_PW = {"RETURN": 102, "FRUSTRATION": 102, "HIDDEN_POWER": 70}

class Effects:
    def L(self, s):
        if self.log is not None:
            self.log.append(s)

    def over(self):
        a, b = self.a, self.b
        if a.hp <= 0 and b.hp <= 0:
            if self.rules.both_faint_draw:
                self.res = 2
            else:
                self.res = 0 if self.actor is a else 1
            return True
        if a.hp <= 0:
            self.res = 1
            return True
        if b.hp <= 0:
            self.res = 0
            return True
        return False

    def other(self, m):
        return self.b if m is self.a else self.a

    def change_stage(self, S, idx, delta, actor):
        if delta < 0 and actor is not S and (S.mist or S.ability in ("CLEAR_BODY","WHITE_SMOKE") or (idx==0 and S.ability=="HYPER_CUTTER") or (idx==5 and S.ability=="KEEN_EYE")):
            return False
        n = max(-6, min(6, S.stage[idx] + delta))
        if n == S.stage[idx]:
            return False
        S.stage[idx] = n
        return True

    def can_sleep(self, mon):
        return (mon.ability not in ('INSOMNIA','VITAL_SPIRIT') and
                (mon.ability=='SOUNDPROOF' or not any(x.uproar for x in (self.a,self.b))))

    def inflict(self, o, st, by=None, ability=False):
        if o.status or (by is not None and by is not o and not ability and o.safeguard > 0):
            return False
        if st == PSN and ("POISON" in o.types or "STEEL" in o.types or o.ability=="IMMUNITY"):
            return False
        if st == BRN and ("FIRE" in o.types or o.ability=="WATER_VEIL"):
            return False
        if st == FRZ and ("ICE" in o.types or o.ability=="MAGMA_ARMOR" or (self.weather=="sun" and not weather_suppressed(self))):
            return False
        if st==PAR and o.ability=="LIMBER": return False
        if st==SLP and not self.can_sleep(o): return False
        if by is not None and by is not o and not ability and o.sub: return False
        o.status = st
        o.toxic = 0
        if st == SLP:
            o.slp = (self.rnd(8) % 4) + 2
        if o.ability=="SYNCHRONIZE" and by is not None and by is not o and st in (BRN,PSN,PAR):
            self.inflict(by,st,ability=True)
        return True

    def confuse(self, o, by=None):
        if o.ability=="OWN_TEMPO" or o.conf or (by is not None and by is not o and o.safeguard > 0):
            return False
        o.conf = (self.rnd(8) & 3) + 2
        return True

    def heal(self, m, amount):
        if m.hp <= 0 or m.hp >= m.maxhp:
            return False
        m.hp = min(m.maxhp, m.hp + max(1, amount))
        return True

    def hit(self, m, o, mv):
        ef = mv.effect
        if ef in SELF_EFFECTS:
            return True
        if mv.sound and o.ability=="SOUNDPROOF": return False
        if o.protecting and mv.protect:
            return False
        if m.lockon:
            return True
        if o.invuln:
            ok = (o.invuln == "fly" and mv.name in ("GUST", "TWISTER", "THUNDER", "SKY_UPPERCUT")) or \
                 (o.invuln == "dig" and mv.name in ("EARTHQUAKE", "MAGNITUDE")) or (o.invuln=="dive" and mv.name in ("SURF","WHIRLPOOL"))
            if not ok:
                return False
        if ef == "ALWAYS_HIT":
            return True
        acc = acc_thresh(m, o, mv)
        if ef == "THUNDER":
            if self.weather == "rain" and not weather_suppressed(self):
                return True
            if self.weather == "sun" and not weather_suppressed(self):
                acc = 50
        return mv.acc==0 or acc >= 100 or self.rnd(8) < acc*256//100

    def deal(self, m, o, dmg, mv, phys, passive=False):
        if o.hp<=0:return 0,False,False
        dmg=max(0,dmg)
        if o.sub>0:
            dealt=min(dmg,o.sub)
            o.sub-=dealt
            return dealt,True,o.sub==0
        if o.enduring and dmg>=o.hp:dmg=max(0,o.hp-1)
        d=min(dmg,o.hp)
        o.took_dmg,o.took_phys=d,phys
        o.hp-=d
        if o.bide_left>0:o.bide_acc+=d
        if not passive and o.hp<=0 and o.grudge and mv in m.moves:m.pp[m.moves.index(mv)]=0
        if not passive and o.hp<=0 and o.dbond:m.hp=0
        return d,False,False

    def dmg_move(self, m, o, mv, mode):
        try:
            return self._dmg_move(m,o,mv,mode)
        finally:
            if mv.effect=='SPIT_UP':m.stockpile=0

    def _dmg_move(self, m, o, mv, mode):
        rnd, ef = self.rnd, mv.effect
        if ef == "FUTURE_SIGHT":
            if o.future_left == 0:
                o.future_left, o.future_by = 3, m
                o.future_dmg = calc_base(m, o, mv)
                o.future_move = mv
            return
        w = None if weather_suppressed(self) else self.weather
        if mode == "normal" and (ef in ("FLY", "RAZOR_WIND", "SKULL_BASH", "SKY_ATTACK") or (ef == "SOLARBEAM" and w != "sun")):
            m.charge = mv
            if ef=="SKULL_BASH":self.change_stage(m,1,1,m)
            if ef == "FLY":
                m.invuln = "fly" if mv.name in ("FLY","BOUNCE") else "dive" if mv.name=="DIVE" else "dig"
            return
        if ef == "SELFDESTRUCT":
            if any(x.ability=="DAMP" for x in (m,o)):return
            m.hp = 0                                  
        if ef == "DREAM_EATER" and o.status != SLP:
            return
        if ef == "SNORE" and m.status != SLP:
            return
        if ef == "OHKO":
            if o.ability=="STURDY":return
            diff = m.lvl - o.lvl
            if diff < 0 or o.protecting:
                return
            if not m.lockon and not (o.invuln is None and (rnd(8) < (30 + diff) * 256 // 100)):
                self.miss(m, o, mv)
                return
        elif not self.hit(m, o, mv):
            self.miss(m, o, mv)
            return
        mt = mtype_of(mv,m)
        phys = mv.type in PHYS if mv.name=="HIDDEN_POWER" else mt in PHYS or mv.name=="STRUGGLE"
        fs = o.foresight
        imm = 0 in type_mults(mt, o.types[0], o.types[1], fs)
        if self.trigger_ability(o,m,"defend_hit",move_type=mt,mv=mv)=="immune": return
        if ef=="BRICK_BREAK": o.reflect=o.lscreen=0
        if ef=="FAKE_OUT" and self.turn>1: return
        if ef=="FOCUS_PUNCH" and m.took_dmg: return
        if ef=="SPIT_UP" and not m.stockpile: return
        if ef=="DREAM_EATER" and o.sub: return
        total, hit_sub, hits, dmg = 0, False, 1, 0
        if ef=="ENDEAVOR":
            if m.hp>=o.hp or imm: return
            dmg=o.hp-m.hp
        elif ef == "COUNTER" or ef == "MIRROR_COAT":
            if imm:
                return
            if m.took_dmg <= 0 or m.took_phys != (ef == "COUNTER"):
                return
            dmg = m.took_dmg * 2
        elif ef == "OHKO":
            if imm:
                return
            dmg = o.hp
        elif ef in ("LEVEL_DAMAGE", "STATIC_DAMAGE", "PSYWAVE", "SUPER_FANG"):
            if imm:
                return
            if ef == "LEVEL_DAMAGE":
                dmg = m.lvl
            elif ef == "STATIC_DAMAGE":
                dmg = 20 if mv.name == "SONIC_BOOM" else 40
            elif ef == "SUPER_FANG":
                dmg = max(1, o.hp // 2)
            else:
                lim = m.lvl * 3 // 2
                r = rnd(8)
                while r >= lim:
                    r = rnd(8)
                dmg = max(1, r)
        else:
            pw = mv.power
            if ef == "ROLLOUT":
                pw = mv.power * (2 ** m.rollout_n) * (2 if m.curl else 1)
            elif ef == "FURY_CUTTER":
                pw = min(160, mv.power * (2 ** m.fury_n))
            elif ef == "MAGNITUDE":
                r = rnd(8)
                pw = next(p for lim, _, p in MAGNITUDE if r < lim)
            elif ef in ("RETURN", "FRUSTRATION", "HIDDEN_POWER"):
                pw = SPECIAL_PW[ef]
            elif ef == "REVERSAL":
                p = 48 * m.hp // m.maxhp
                pw = 200 if p < 2 else 150 if p < 5 else 100 if p < 10 else 80 if p < 17 else 40 if p < 33 else 20
            elif ef == "PRESENT":
                r = rnd(8)
                if r >= 204:
                    self.heal(o, o.maxhp // 4)
                    return
                pw = 40 if r < 102 else 80 if r < 178 else 120
            elif ef == "UPROAR":
                if not m.uproar:
                    m.uproar = 2 + (rnd(8) & 3)
            elif ef == "TRIPLE_KICK":
                pw = 10
            crit = ef!="SPIT_UP" and o.ability not in ("BATTLE_ARMOR","SHELL_ARMOR") and rnd(8) < CRIT_CHANCE[crit_stage(m, mv)]
            base = calc_base(m, o, mv, crit, pw)
            if base == 0:
                if ef == "JUMP_KICK":
                    m.hp = max(0, m.hp - max(1, min(o.maxhp//2,calc_base(m,o,mv)//2)))
                return
            dmg = base if base <= 1 or ef=="SPIT_UP" else base * self.roll() // 100
            dmg = max(1, dmg)
            if ef == "FALSE_SWIPE" and not o.sub and dmg >= o.hp:
                dmg = max(0, o.hp - 1)
        
        if ef == "RAGE":
            m.rage = True
        if ef == "DOUBLE_HIT":
            hits=2
        elif ef == "MULTI_HIT":
            hits = multi_hits(rnd)
        elif ef in ("DOUBLE_HIT", "POISON_MULTI_HIT"):
            hits = 2
        elif ef == "TRIPLE_KICK":
            hits = 3
            
        o.last_received=mv
        for k in range(hits):
            if k>0:
                if m.hp<=0 or o.hp<=0 or (m.status==SLP and m.called_from!='SLEEP_TALK'):break
                if ef=='TRIPLE_KICK' and not self.hit(m,o,mv):break
                crit=o.ability not in ('BATTLE_ARMOR','SHELL_ARMOR') and rnd(8)<CRIT_CHANCE[crit_stage(m,mv)]
                base=calc_base(m,o,mv,crit,10*(k+1) if ef=='TRIPLE_KICK' else pw)
                if base==0:break
                dmg=max(1,base*self.roll()//100)
            d,hs,br=self.deal(m,o,dmg,mv,phys)
            total+=d
            hit_sub=hit_sub or hs
            if d>0 and not hs:
                if o.rage and o.hp>0 and mv.power>0:self.change_stage(o,0,1,o)
                if o.status==FRZ and mt=='FIRE' and o.hp>0:o.status=0
                self.contact_effects(m,o,mv,False)
                if o.ability=='COLOR_CHANGE' and o.hp>0 and mt!='TYPELESS' and mv.power>0:
                    o.types=(mt,mt)
            if ef=='POISON_MULTI_HIT' and not hs and o.hp>0 and o.ability!='SHIELD_DUST' and rnd(8)<min(256,mv.chance*(2 if m.ability=='SERENE_GRACE' else 1)):
                self.inflict(o,PSN,m)
            # Multi-hits continue after breaking a substitute, but Endure stops them.
            if o.hp<=0 or m.hp<=0 or (o.enduring and not hs and o.hp==1):break

        if ef=="POISON_FANG" and o.hp>0 and not hit_sub and o.ability!="SHIELD_DUST" and rnd(8)<min(256,mv.chance*(2 if m.ability=='SERENE_GRACE' else 1)):
            if self.inflict(o,PSN,m):o.toxic=1
        if ef=="FAKE_OUT" and not hit_sub and o.ability!="INNER_FOCUS":o.flinch=True
        if o.hp > 0 and not hit_sub:
            roll = rnd(8) < min(256,mv.chance*(2 if m.ability=="SERENE_GRACE" else 1)) and o.ability!="SHIELD_DUST"
            if ef in STATUS_HIT and ef != "POISON_MULTI_HIT":
                if roll:
                    self.inflict(o, STATUS_HIT[ef], m)
            elif ef == "TRI_ATTACK":
                if roll:
                    self.inflict(o, (BRN, FRZ, PAR)[rnd(8) % 3], m)
            elif ef == "CONFUSE_HIT":
                if roll:
                    self.confuse(o, m)
            elif ef in ("FLINCH_HIT", "STOMP", "TWISTER", "SNORE"):
                if roll and o.ability!="INNER_FOCUS":
                    o.flinch = True
            elif ef in HIT_STAT and not HIT_STAT[ef][0]:
                if roll:
                    for i, dl in HIT_STAT[ef][1]:
                        self.change_stage(o, i, dl, m)
        if ef in HIT_STAT and HIT_STAT[ef][0] and m.hp > 0 and total > 0 and rnd(8) < min(256, mv.chance * (2 if m.ability == "SERENE_GRACE" else 1)):
            for i, dl in HIT_STAT[ef][1]:
                self.change_stage(m, i, dl, m)
        if ef in ("LEECH_HIT", "DREAM_EATER") and total > 0 and m.hp>0:
            if o.ability=="LIQUID_OOZE": m.hp=max(0,m.hp-max(1,total//2))
            else: self.heal(m, max(1,total//2))
        elif ef in ("RECOIL_HIT","DOUBLE_EDGE") and total > 0 and (m.ability!="ROCK_HEAD" or mv.name=="STRUGGLE"):
            m.hp = max(0, m.hp - max(1, total // (3 if ef=="DOUBLE_EDGE" else 4)))
        elif ef == "HYPER_BEAM":
                m.recharge = True
        elif ef == "TRAP_TARGET":
            if o.hp > 0 and not hit_sub and o.trap_left == 0:
                o.trap_left, o.trapped = multi_hits(rnd) , True
        elif ef == "RAMPAGE":
            if mode == "normal":
                m.rampage_left, m.rampage_mv = (rnd(8) & 1) + 1, mv
        elif ef == "ROLLOUT":
            if mode == "normal":
                m.rollout_left, m.rollout_n, m.rampage_mv = 5, 0, mv
            m.rollout_n += 1
            m.rollout_left -= 1
            if m.rollout_left <= 0:
                m.rollout_left = m.rollout_n = 0
        elif ef == "FURY_CUTTER":
            m.fury_n = min(4, m.fury_n + 1)
        elif ef == "SUPERPOWER":
            self.change_stage(m,0,-1,m); self.change_stage(m,1,-1,m)
        elif ef == "OVERHEAT": self.change_stage(m,3,-2,m)
        elif ef == "SMELLINGSALT" and o.status==PAR and not hit_sub: o.status=0
        elif ef == "SPIT_UP": m.stockpile=0
        elif ef == "RAPID_SPIN":
            m.seeded = False
            m.trap_left, m.trapped = 0, False

    def miss(self, m, o, mv):
        ef = mv.effect
        if ef in ("JUMP_KICK",):
            m.hp = max(0, m.hp - max(1, min(o.maxhp//2,calc_base(m,o,mv)//2)))
        if ef == "SELFDESTRUCT":
            if any(x.ability=="DAMP" for x in (m,o)):return
            m.hp = 0
        if ef == "ROLLOUT":
            m.rollout_left = m.rollout_n = 0
        if ef == "FURY_CUTTER":
            m.fury_n = 0
        if ef == "RAMPAGE":
            m.rampage_left = 0

    def roll(self):
        return 85 + (self.rnd(8) & 15)

    def status_move(self, m, o, mv, idx=-1):
        ef, rnd = mv.effect, self.rnd
        if mv.snatch and o.snatch:
            o.snatch=False
            return self.status_move(o,m,mv)
        if mv.reflectable and o.magic_coat:
            o.magic_coat=False
            return self.status_move(o,m,mv)
        w = None if weather_suppressed(self) else self.weather
        if ef=="CURSE" and "GHOST" not in m.types:
            self.change_stage(m,2,-1,m);self.change_stage(m,0,1,m);self.change_stage(m,1,1,m);return
        if ef=="PAIN_SPLIT" and o.sub:return
        if ef not in SELF_EFFECTS:
            if not self.hit(m, o, mv):
                return
            if o.sub > 0 and ef not in ("FORESIGHT", "MEAN_LOOK", "SPITE", "ENCORE", "DISABLE", "NIGHTMARE"):
                return
        if ef not in SELF_EFFECTS:o.last_received=mv
        if ef in STAT_MOVES:
            to_user, chg = STAT_MOVES[ef]
            tgt = m if to_user else o
            for i, dl in chg:
                self.change_stage(tgt, i, dl, m)
            if ef == "DEFENSE_CURL":
                m.curl = True
            if ef == "EVASION_UP" and mv.name == "MINIMIZE":
                m.minimized = True
            return
        if ef == "SLEEP":
            self.inflict(o, SLP, m)
        elif ef == "POISON":
            self.inflict(o, PSN, m)
        elif ef == "TOXIC":
            if self.inflict(o, PSN, m):
                o.toxic = 1
        elif ef == "PARALYZE":
            if mv.name == "THUNDER_WAVE" and 0 in type_mults(mv.type, o.types[0], o.types[1], o.foresight):
                return
            self.inflict(o, PAR, m)
        elif ef == "CONFUSE":
            self.confuse(o, m)
        elif ef == "SWAGGER":
            self.change_stage(o, 0, 2, m)
            self.confuse(o, m)
        elif ef == "ATTRACT":
            if o.ability!="OBLIVIOUS" and not o.attract and {m.gender, o.gender} == {"M", "F"}:
                o.attract = True
        elif ef == "LEECH_SEED":
            if not o.seeded and "GRASS" not in o.types:
                o.seeded = True
        elif ef == "NIGHTMARE":
            if o.status == SLP and not o.nightmare:
                o.nightmare = True
        elif ef == "CURSE":
            if "GHOST" in m.types:
                if not o.cursed:
                    m.hp = max(0, m.hp - m.maxhp // 2)
                    o.cursed = True
            else:
                self.change_stage(m, 2, -1, m)
                self.change_stage(m, 0, 1, m)
                self.change_stage(m, 1, 1, m)
        elif ef == "FOCUS_ENERGY":
            m.focus = True
        elif ef in ("HEAL", "MOONLIGHT", "MORNING_SUN", "SYNTHESIS"):
            if mv.name == "REST":
                if m.hp < m.maxhp and m.status != SLP and self.can_sleep(m):
                    m.hp, m.status, m.slp, m.toxic = m.maxhp, SLP, 3, 0
            elif ef == "HEAL":
                self.heal(m, m.maxhp // 2)
            else:
                self.heal(m, m.maxhp // 2 if w is None else (m.maxhp * 2 // 3 if w == "sun" else m.maxhp // 4))
        elif ef == "LIGHT_SCREEN":
            if not m.lscreen:
                m.lscreen = 5
        elif ef == "REFLECT":
            if not m.reflect:
                m.reflect = 5
        elif ef == "SAFEGUARD":
            if not m.safeguard:
                m.safeguard = 5
        elif ef == "MIST":
            m.mist = True
            m.mist_left=5
        elif ef == "SUBSTITUTE":
            cost = max(1,m.maxhp // 4)
            if m.sub == 0 and m.hp > cost:
                m.hp -= cost
                m.sub = cost
                m.trap_left,m.trapped=0,False
        elif ef in ("RAIN_DANCE", "SUNNY_DAY", "SANDSTORM", "HAIL"):
            new = {"RAIN_DANCE": "rain", "SUNNY_DAY": "sun", "SANDSTORM": "sand", "HAIL":"hail"}[ef]
            if self.weather != new:
                self.weather, self.weather_left = new, 5
        elif ef in ("PROTECT", "ENDURE"):
            if self.action_number==1:
                m.protect_n=0
                return
            if rnd(8) < (255 >> min(m.protect_n, 7)) or m.protect_n == 0:
                if ef == "PROTECT":
                    m.protecting = True
                else:
                    m.enduring = True
                m.protect_n += 1
            else:
                m.protect_n = 0
        elif ef == "DESTINY_BOND":
            m.dbond = True
        elif ef == "PERISH_SONG":
            for x in (m, o):
                if not x.perish and x.ability!="SOUNDPROOF":
                    x.perish = 4
        elif ef == "BELLY_DRUM":
            if m.hp > m.maxhp // 2 and m.stage[0] < 6:
                m.hp -= m.maxhp // 2
                m.stage[0] = 6
        elif ef == "PSYCH_UP":
            m.stage = list(o.stage)
        elif ef == "FORESIGHT":
            o.foresight = True
        elif ef == "LOCK_ON":
            m.lockon = True
            m.lockon_left=2
        elif ef == "HEAL_BELL":
            if mv.sound and m.ability=='SOUNDPROOF':return
            m.status = 0
            m.toxic = 0
        elif ef == "PAIN_SPLIT":
            avg = (m.hp + o.hp) // 2
            m.hp, o.hp = min(m.maxhp, avg), min(o.maxhp, avg)
        elif ef == "RESET_STATS":
            m.stage, o.stage = [0] * 7, [0] * 7
        elif ef == "DISABLE":
            lm = o.last_mv
            if o.dis_idx < 0 and lm is not None and lm.name != "STRUGGLE" and lm in o.moves:
                i = o.moves.index(lm)
                if o.pp[i] > 0:
                    o.dis_idx, o.dis_left = i, (rnd(8) & 3) + 2
        elif ef == "ENCORE":
            lm = o.last_mv
            if o.encore_left == 0 and lm is not None and lm.name not in ("ENCORE", "MIRROR_MOVE", "TRANSFORM", "STRUGGLE"):
                if lm in o.moves and o.pp[o.moves.index(lm)] > 0:
                    o.encore_mv, o.encore_left = lm, (rnd(8) & 3) + 3
        elif ef == "SPITE":
            lm = o.last_mv
            if lm in o.moves:
                i = o.moves.index(lm)
                o.pp[i] = max(0, o.pp[i] - (rnd(8) % 4 + 2))
        elif ef == "BIDE":
            m.bide_left, m.bide_acc = 2, 0
        elif ef == "RAGE":
            m.rage = True
        elif ef == "CONVERSION":
            ts = [x.type for x in m.moves if x.type not in m.types and x.type != "CURSE_TYPE"]
            if ts:
                m.types = (ts[0], ts[0])
        elif ef == "CONVERSION2":
            lm = o.last_mv
            if lm is not None:
                tgt = [t for t in ("NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "STEEL", "FIRE",
                                   "WATER", "GRASS", "ELECTRIC", "PSYCHIC", "ICE", "DRAGON", "DARK")
                       if 0 in type_mults(lm.type, t, t) or 5 in type_mults(lm.type, t, t)]
                if tgt:
                    m.types = (tgt[rnd(8) % len(tgt)],) * 2
        elif ef == "TRANSFORM":
            if o.transformed or o.invuln:return
            m.transformed=True
            m.types,m.raw,m.stage=o.types,tuple(o.raw),list(o.stage)
            m.ability,m.species_key,m.weight,m.base_atk=o.ability,o.species_key,o.weight,o.base_atk
            m.moves=list(o.moves)
            m.pp=[min(5,x.pp) for x in m.moves]
            m.dis_idx,m.dis_left=-1,0
            # Gen 3 keeps the user's HP, level, gender, IVs and non-stage volatiles.
        elif ef=="WILL_O_WISP":
            if not (o.ability=="FLASH_FIRE" and o.status!=FRZ):self.inflict(o,BRN,m)
            else:o.flash_fire=True
        elif ef=="YAWN":
            if not o.status and not o.yawn: o.yawn=2
        elif ef=="TAUNT": o.taunt=2
        elif ef=="TORMENT": o.torment=1
        elif ef=="FLATTER": self.change_stage(o,3,1,m);self.confuse(o,m)
        elif ef=="MEMENTO":
            self.change_stage(o,0,-2,m);self.change_stage(o,3,-2,m);m.hp=0
        elif ef=="STOCKPILE": m.stockpile=min(3,m.stockpile+1)
        elif ef=="SWALLOW":
            if m.stockpile: self.heal(m,m.maxhp//(4 if m.stockpile==1 else 2 if m.stockpile==2 else 1));m.stockpile=0
        elif ef=="WISH":
            if not m.wish: m.wish=2
        elif ef=="INGRAIN": m.ingrain=True
        elif ef=="CHARGE": m.charge_power=2
        elif ef=="REFRESH":
            if m.status in (PSN,BRN,PAR): m.status=m.toxic=0
        elif ef=="ROLE_PLAY":
            if o.ability not in ("WONDER_GUARD",): m.ability=o.ability
        elif ef=="SKILL_SWAP":
            if "WONDER_GUARD" not in (m.ability,o.ability): m.ability,o.ability=o.ability,m.ability
        elif ef=="IMPRISON": m.imprison=True
        elif ef=="MAGIC_COAT": m.magic_coat=True
        elif ef=="SNATCH": m.snatch=True
        elif ef=="GRUDGE": m.grudge=True
        elif ef=="MUD_SPORT": m.mud_sport=True
        elif ef=="WATER_SPORT": m.water_sport=True
        elif ef=="CAMOUFLAGE": m.types=("NORMAL","NORMAL")
        elif ef=="TEETER_DANCE": self.confuse(o,m)
        elif ef=="NATURE_POWER": self.run_called(m,o,MV["SWIFT"])
        elif ef in ("ASSIST","FOLLOW_ME","HELPING_HAND","TRICK","RECYCLE","BATON_PASS","TELEPORT","FORCE_SWITCH","SPIKES","SPLASH"):
            return  # No allies, bench, escape or held items in this format.
        elif ef == "METRONOME":
            r = rnd(16) % (len(MOVE_ORDER)+1)
            while r == 0 or r > len(MOVE_ORDER) or MOVE_ORDER[r - 1].name in NO_METRONOME:
                r = rnd(16) % (len(MOVE_ORDER)+1)
            self.run_called(m, o, MOVE_ORDER[r - 1])
        elif ef == "MIRROR_MOVE":
            lm = o.last_mv
            lm=m.last_received
            if lm is not None and lm.effect != "MIRROR_MOVE":
                self.run_called(m, o, lm)
        elif ef == "SLEEP_TALK":
            if m.status == SLP:
                opts = [i for i,x in enumerate(m.moves) if x.name not in NO_SLEEP_TALK and i!=m.dis_idx
                        and not (m.taunt and x.kind=="status") and not (m.torment and x is m.last_selected)
                        and not (o.imprison and x in o.moves)]
                if opts:
                    slot=opts[rnd(8)%len(opts)]
                    self.run_called(m,o,m.moves[slot],idx=slot,caller="SLEEP_TALK")
        elif ef == "SKETCH":
            lm = o.last_mv
            if not m.transformed and lm is not None and lm.name not in ("STRUGGLE", "SKETCH") and lm not in m.moves and idx >= 0:
                m.moves[idx], m.pp[idx] = lm, lm.pp
        elif ef == "MIMIC":
            lm = o.last_mv
            if not m.transformed and lm is not None and lm.name not in NO_MIMIC and lm not in m.moves and idx >= 0:
                m.moves[idx], m.pp[idx] = lm, min(5,lm.pp)

    def run_called(self,m,o,mv2,idx=-1,caller=None):
        # Keep a call frame: called moves spend only the selecting move's PP.
        if m.call_depth>=8:return
        previous=m.called_from
        m.call_depth+=1
        m.called_from=caller or previous or (m.last_mv.name if m.last_mv else None)
        m.last_mv=mv2
        if self.log is not None:
            self.L(f"   -> {mv2.name}")
        try:
            if mv2.kind=='dmg':self.dmg_move(m,o,mv2,'normal')
            else:self.status_move(m,o,mv2,idx)
        finally:
            m.call_depth-=1
            m.called_from=previous
