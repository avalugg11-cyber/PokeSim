"""Gen 2 move effects: every one of the 135 effects in Crystal is handled here."""
from .base import *

STAT_MOVES = {   
    "ATTACK_UP": (True, [(0, 1)]), "ATTACK_UP_2": (True, [(0, 2)]), "DEFENSE_UP": (True, [(1, 1)]),
    "DEFENSE_UP_2": (True, [(1, 2)]), "DEFENSE_CURL": (True, [(1, 1)]), "SP_ATK_UP": (True, [(3, 1)]),
    "SP_DEF_UP_2": (True, [(4, 2)]), "SPEED_UP_2": (True, [(2, 2)]), "EVASION_UP": (True, [(6, 1)]),
    "ACCURACY_DOWN": (False, [(5, -1)]), "ATTACK_DOWN": (False, [(0, -1)]), "ATTACK_DOWN_2": (False, [(0, -2)]),
    "DEFENSE_DOWN": (False, [(1, -1)]), "DEFENSE_DOWN_2": (False, [(1, -2)]), "EVASION_DOWN": (False, [(6, -1)]),
    "SPEED_DOWN": (False, [(2, -1)]), "SPEED_DOWN_2": (False, [(2, -2)])}
HIT_STAT = {  
    "ACCURACY_DOWN_HIT": (False, [(5, -1)]), "ATTACK_DOWN_HIT": (False, [(0, -1)]),
    "DEFENSE_DOWN_HIT": (False, [(1, -1)]), "SPEED_DOWN_HIT": (False, [(2, -1)]),
    "SP_DEF_DOWN_HIT": (False, [(4, -1)]), "ATTACK_UP_HIT": (True, [(0, 1)]), "DEFENSE_UP_HIT": (True, [(1, 1)]),
    "ALL_UP_HIT": (True, [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1)])}
STATUS_HIT = {"BURN_HIT": BRN, "FREEZE_HIT": FRZ, "PARALYZE_HIT": PAR, "POISON_HIT": PSN, "SACRED_FIRE": BRN,
              "FLAME_WHEEL": BRN, "THUNDER": PAR, "POISON_MULTI_HIT": PSN}
SELF_EFFECTS = frozenset(STAT_MOVES[k] and k for k in STAT_MOVES if STAT_MOVES[k][0]) | {
    "FOCUS_ENERGY", "HEAL", "MOONLIGHT", "MORNING_SUN", "SYNTHESIS", "LIGHT_SCREEN", "REFLECT", "SAFEGUARD", "MIST",
    "SUBSTITUTE", "RAIN_DANCE", "SUNNY_DAY", "SANDSTORM", "PROTECT", "ENDURE", "DESTINY_BOND", "PERISH_SONG",
    "BELLY_DRUM", "PSYCH_UP", "METRONOME", "MIRROR_MOVE", "SLEEP_TALK", "CONVERSION", "CONVERSION2", "BATON_PASS",
    "TELEPORT", "SPLASH", "SPIKES", "HEAL_BELL", "SKETCH", "MIMIC", "BIDE", "RAGE", "FORCE_SWITCH",
    "RESET_STATS", "PAIN_SPLIT", "TRANSFORM", "CURSE", "FORESIGHT"}
MAGNITUDE = ((13, 4, 10), (38, 5, 30), (89, 6, 50), (166, 7, 70), (217, 8, 90), (242, 9, 110), (256, 10, 150))
NO_SLEEP_TALK = frozenset({"SLEEP_TALK", "MIRROR_MOVE", "METRONOME", "BIDE", "FLY", "DIG", "SKULL_BASH", "SOLARBEAM",
                           "RAZOR_WIND", "SKY_ATTACK", "STRUGGLE", "MIMIC", "SKETCH"})
SPECIAL_PW = {"RETURN": 102, "FRUSTRATION": 1, "HIDDEN_POWER": 70}

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
        if delta < 0 and actor is not S and S.mist:
            return False
        n = max(-6, min(6, S.stage[idx] + delta))
        if n == S.stage[idx]:
            return False
        S.stage[idx] = n
        return True

    def inflict(self, o, st, by=None):
        if o.status or (by is not None and by is not o and o.safeguard > 0):
            return False
        if st == PSN and ("POISON" in o.types or "STEEL" in o.types):
            return False
        if st == BRN and "FIRE" in o.types:
            return False
        if st == FRZ and "ICE" in o.types:
            return False
        o.status = st
        o.toxic = 0
        if st == SLP:
            r = self.rnd(8) & 7
            while r == 0 or r == 7:
                r = self.rnd(8) & 7
            o.slp = r + 1                      
        return True

    def confuse(self, o, by=None):
        if o.conf or (by is not None and by is not o and o.safeguard > 0):
            return False
        o.conf = (self.rnd(8) & 3) + 2
        return True

    def heal(self, m, amount):
        if m.hp >= m.maxhp:
            return False
        m.hp = min(m.maxhp, m.hp + max(1, amount))
        return True

    def hit(self, m, o, mv):
        ef = mv.effect
        if ef in SELF_EFFECTS:
            return True
        if o.protecting:
            return False
        if o.sub and ef in ("LEECH_HIT", "DREAM_EATER"):
            return False
        if m.lockon:
            m.lockon = False
            return can_reach(mv, o, locked=True)
        if not can_reach(mv, o):
            return False
        if ef == "ALWAYS_HIT":
            return True
        acc = acc_thresh(m, o, mv)
        if ef == "THUNDER":
            if self.weather == "rain":
                return True
        return acc >= 255 or self.rnd(8) < acc

    def deal(self, m, o, dmg, mv, phys):
        o.took_dmg, o.took_phys = dmg, phys
        if o.sub > 0:
            o.sub -= dmg
            broke = o.sub <= 0
            if broke:
                o.sub = 0
            return dmg, True, broke
        if o.enduring and dmg >= o.hp:
            dmg = o.hp - 1
        d = min(dmg, o.hp)
        o.hp -= d
        if o.bide_left > 0:
            o.bide_acc += d
        if o.hp <= 0 and o.dbond:
            m.hp = 0
        return d, False, False

    def dmg_move(self, m, o, mv, mode):
        rnd, ef = self.rnd, mv.effect
        if ef == "FUTURE_SIGHT":
            if o.future_left == 0:
                o.future_left, o.future_by = 3, m
                o.future_dmg = calc_base(m, o, mv)
            return
        w = self.weather
        if mode == "normal" and (ef in ("FLY", "RAZOR_WIND", "SKULL_BASH", "SKY_ATTACK") or (ef == "SOLARBEAM" and w != "sun")):
            m.charge = mv
            if ef == "FLY":
                m.invuln = "fly" if mv.name == "FLY" else "dig"
            return
        if ef == "SELFDESTRUCT":
            m.hp = 0                                  
        if ef == "DREAM_EATER" and o.status != SLP:
            return
        if ef == "SNORE" and m.status != SLP:
            return
        if ef == "OHKO":
            diff = m.lvl - o.lvl
            if diff < 0 or o.protecting:
                return
            locked, m.lockon = m.lockon, False
            accuracy = ohko_thresh(m, o, mv)
            if not can_reach(mv, o, locked) or (not locked and accuracy < 255 and rnd(8) >= accuracy):
                self.miss(m, o, mv)
                return
        elif not self.hit(m, o, mv):
            self.miss(m, o, mv)
            return
        mt = mtype_of(mv)
        phys = mv.type in PHYS  # Crystal retaliation uses the original move type
        fs = o.foresight
        imm = 0 in type_mults(mt, o.types[0], o.types[1], fs)
        total, hit_sub, hits, dmg = 0, False, 1, 0
        if ef == "COUNTER" or ef == "MIRROR_COAT":
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
                dmg = 20 if mv.name == "SONICBOOM" else 40
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
            elif ef == "BEAT_UP":
                pw = m.base_atk // 10 + 5
            elif ef == "SOLARBEAM" and w in ("rain", "sand"):
                pw = mv.power // 2
            elif ef == "STOMP" and o.minimized:
                pw = mv.power * 2
            elif ef == "TRIPLE_KICK":
                pw = 10
            crit = rnd(8) < CRIT_CHANCE[crit_stage(m, mv)]
            base = calc_base(m, o, mv, crit, pw)
            if base == 0:
                if ef == "JUMP_KICK":
                    m.hp = max(0, m.hp - max(1, m.maxhp // 8))
                return
            dmg = base if base <= 1 else base * self.roll() // 255
            # Crystal doubles the already-varied damage, saturating 16 bits.
            if double_reach_damage(mv, o):
                dmg = min(65535, dmg * 2)
            dmg = max(1, dmg)
            if ef == "FALSE_SWIPE" and dmg >= o.hp:
                dmg = max(0, o.hp - 1)
        
        if ef == "RAGE":
            m.rage = True
        if ef == "MULTI_HIT":
            hits = multi_hits(rnd)
        elif ef in ("DOUBLE_HIT", "POISON_MULTI_HIT"):
            hits = 2
        elif ef == "TRIPLE_KICK":
            hits = 3
            
        broke = False
        for k in range(hits):
            if ef == "TRIPLE_KICK" and k > 0:
                if not self.hit(m, o, mv):
                    break
                dmg = max(1, (calc_base(m, o, mv, False, 10 * (k + 1)) * self.roll()) // 255)
            d, hs, br = self.deal(m, o, dmg, mv, phys)
            total += d
            hit_sub = hit_sub or hs
            if ef == "POISON_MULTI_HIT" and not hs and o.hp > 0 and rnd(8) < mv.chance:
                self.inflict(o, PSN, m)
            if o.hp <= 0 or br or m.hp <= 0:
                break
                
        if o.status == FRZ and mt == "FIRE" and not hit_sub and o.hp > 0:
            o.status = 0
        if o.rage and o.hp > 0 and not hit_sub and ef not in ("COUNTER", "MIRROR_COAT"):
            o.rage_n = min(256, o.rage_n + 1)

        if o.hp > 0 and not hit_sub:
            roll = rnd(8) < mv.chance
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
                if roll and ef != "TWISTER" or (ef == "TWISTER" and roll):
                    o.flinch = True
            elif ef in HIT_STAT and not HIT_STAT[ef][0]:
                if roll:
                    for i, dl in HIT_STAT[ef][1]:
                        self.change_stage(o, i, dl, m)
        if ef in HIT_STAT and HIT_STAT[ef][0] and m.hp > 0 and total > 0 and rnd(8) < mv.chance:
            for i, dl in HIT_STAT[ef][1]:
                self.change_stage(m, i, dl, m)
        if ef in ("LEECH_HIT", "DREAM_EATER") and total > 0:
            self.heal(m, total // 2)
        elif ef == "RECOIL_HIT" and total > 0:
            m.hp = max(0, m.hp - max(1, total // 4))
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
        elif ef == "RAPID_SPIN":
            m.seeded = False
            m.trap_left, m.trapped = 0, False

    def miss(self, m, o, mv):
        ef = mv.effect
        if ef in ("JUMP_KICK",):
            m.hp = max(0, m.hp - max(1, m.maxhp // 8))
        if ef == "SELFDESTRUCT":
            m.hp = 0
        if ef == "ROLLOUT":
            m.rollout_left = m.rollout_n = 0
        if ef == "FURY_CUTTER":
            m.fury_n = 0
        if ef == "RAMPAGE":
            m.rampage_left = 0

    def roll(self):
        r = self.rnd(8)
        while r < 217:
            r = self.rnd(8)
        return r

    def status_move(self, m, o, mv, idx=-1):
        ef, rnd = mv.effect, self.rnd
        w = self.weather
        if ef not in SELF_EFFECTS:
            if not self.hit(m, o, mv):
                return
            if o.sub > 0 and ef not in ("FORESIGHT", "MEAN_LOOK", "SPITE", "ENCORE", "DISABLE", "NIGHTMARE"):
                return
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
            if not o.attract and {m.gender, o.gender} == {"M", "F"}:
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
                if m.hp < m.maxhp and m.status != SLP:
                    m.hp, m.status, m.slp, m.toxic = m.maxhp, SLP, 3, 0
            elif ef == "HEAL":
                self.heal(m, m.maxhp // 2)
            else:
                self.heal(m, m.maxhp // 2 if w is None else (m.maxhp if w == "sun" else m.maxhp // 4))
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
        elif ef == "SUBSTITUTE":
            cost = m.maxhp // 4
            if m.sub == 0 and m.hp > cost:
                m.hp -= cost
                m.sub = cost + 1
        elif ef in ("RAIN_DANCE", "SUNNY_DAY", "SANDSTORM"):
            new = {"RAIN_DANCE": "rain", "SUNNY_DAY": "sun", "SANDSTORM": "sand"}[ef]
            if self.weather != new:
                self.weather, self.weather_left = new, 5
        elif ef in ("PROTECT", "ENDURE"):
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
                if not x.perish:
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
        elif ef == "HEAL_BELL":
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
                    o.dis_idx, o.dis_left = i, (rnd(8) % 7) + 2
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
            m.bide_left, m.bide_acc = (rnd(8) & 1) + 2, 0
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
                                   "WATER", "GRASS", "ELECTRIC", "PSYCHIC_TYPE", "ICE", "DRAGON", "DARK")
                       if 0 in type_mults(lm.type, t, t) or 5 in type_mults(lm.type, t, t)]
                if tgt:
                    m.types = (tgt[rnd(8) % len(tgt)],) * 2
        elif ef == "TRANSFORM":
            m.species_key = o.species_key
            m.types, m.raw, m.stage = o.types, o.raw, list(o.stage)
            m.moves = list(o.moves)
            m.pp = [5] * len(m.moves)
            m.dis_idx, m.base_atk = -1, o.base_atk
        elif ef == "METRONOME":
            r = rnd(8)
            while r == 0 or r > 251 or MOVE_ORDER[r - 1].name in NO_METRONOME:
                r = rnd(8)
            self.run_called(m, o, MOVE_ORDER[r - 1])
        elif ef == "MIRROR_MOVE":
            lm = o.last_mv
            if lm is not None and lm.effect != "MIRROR_MOVE":
                self.run_called(m, o, lm)
        elif ef == "SLEEP_TALK":
            if m.status == SLP:
                opts = [x for x in m.moves if x.name not in NO_SLEEP_TALK]
                if opts:
                    self.run_called(m, o, opts[rnd(8) % len(opts)])
        elif ef == "SKETCH":
            lm = o.last_mv
            if lm is not None and lm.name not in ("STRUGGLE", "SKETCH") and idx >= 0:
                m.moves[idx], m.pp[idx] = lm, lm.pp
        elif ef == "MIMIC":
            lm = o.last_mv
            if lm is not None and lm.name not in ("STRUGGLE", "MIMIC", "SKETCH", "METRONOME", "TRANSFORM") and idx >= 0:
                m.moves[idx], m.pp[idx] = lm, 5

    def run_called(self, m, o, mv2):
        m.last_mv = mv2
        if self.log is not None:
            self.L(f"   -> {mv2.name}")
        if mv2.kind == "dmg":
            self.dmg_move(m, o, mv2, "normal")
        else:
            self.status_move(m, o, mv2)
