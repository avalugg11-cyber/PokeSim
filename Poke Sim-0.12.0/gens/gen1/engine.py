"""Gen 1 1v1 battle engine (v0.3).

Data comes from the pokered disassembly (see data.py). Full natural learnsets
are available at fixed battle level 50; TM/HM acquisition remains excluded.
Mechanics were checked against the disassembly where noted in README.
"""
import math
from .data import load

D = load()
ENGINE_VERSION = "0.12.0"
SLP, PAR, BRN, PSN, FRZ = 1, 2, 3, 4, 5
PHYS = frozenset({"NORMAL", "FIGHTING", "FLYING", "GROUND", "ROCK", "BUG", "GHOST", "POISON"})
RATIO = [25, 28, 33, 40, 50, 66, 100, 150, 200, 250, 300, 350, 400]  # stage -6..+6, percent
from move_rules import BATTLE_LEVEL, battle_level
LEVEL = dict.fromkeys(("GROWTH_SLOW", "GROWTH_MEDIUM_FAST", "GROWTH_MEDIUM_SLOW", "GROWTH_FAST"), BATTLE_LEVEL)
HICRIT = frozenset({"KARATE_CHOP", "RAZOR_LEAF", "CRABHAMMER", "SLASH"})
BANNED_TM = frozenset()  # No tournament-specific move bans.


class Rules:
    def __init__(self, badge_glitch=True, both_faint_draw=True, turn_limit=50, statexp=11000):
        self.badge_glitch = badge_glitch
        self.both_faint_draw = both_faint_draw   # simultaneous faint (e.g. Explosion KO) = draw
        self.turn_limit = turn_limit
        self.statexp = statexp


RULES = Rules()

# ---------------------------------------------------------------- moves
STAT_UP = {"ATTACK_UP1_EFFECT": (0, 1), "DEFENSE_UP1_EFFECT": (1, 1), "SPEED_UP1_EFFECT": (2, 1),
           "SPECIAL_UP1_EFFECT": (3, 1), "ACCURACY_UP1_EFFECT": (4, 1), "EVASION_UP1_EFFECT": (5, 1),
           "ATTACK_UP2_EFFECT": (0, 2), "DEFENSE_UP2_EFFECT": (1, 2), "SPEED_UP2_EFFECT": (2, 2),
           "SPECIAL_UP2_EFFECT": (3, 2), "ACCURACY_UP2_EFFECT": (4, 2), "EVASION_UP2_EFFECT": (5, 2)}
STAT_DOWN = {"ATTACK_DOWN1_EFFECT": (0, 1), "DEFENSE_DOWN1_EFFECT": (1, 1), "SPEED_DOWN1_EFFECT": (2, 1),
             "SPECIAL_DOWN1_EFFECT": (3, 1), "ACCURACY_DOWN1_EFFECT": (4, 1), "EVASION_DOWN1_EFFECT": (5, 1),
             "ATTACK_DOWN2_EFFECT": (0, 2), "DEFENSE_DOWN2_EFFECT": (1, 2), "SPEED_DOWN2_EFFECT": (2, 2),
             "SPECIAL_DOWN2_EFFECT": (3, 2), "ACCURACY_DOWN2_EFFECT": (4, 2), "EVASION_DOWN2_EFFECT": (5, 2)}


def _pct(p):  # "cp N percent + 1" thresholds out of 256
    return p * 255 // 100 + 1


SIDE = {"POISON_SIDE_EFFECT1": (PSN, _pct(20)), "POISON_SIDE_EFFECT2": (PSN, _pct(40)),
        "BURN_SIDE_EFFECT1": (BRN, _pct(10)), "BURN_SIDE_EFFECT2": (BRN, _pct(30)),
        "FREEZE_SIDE_EFFECT1": (FRZ, _pct(10)),
        "PARALYZE_SIDE_EFFECT1": (PAR, _pct(10)), "PARALYZE_SIDE_EFFECT2": (PAR, _pct(30)),
        "FLINCH_SIDE_EFFECT1": ("flinch", _pct(10)), "FLINCH_SIDE_EFFECT2": ("flinch", _pct(30)),
        "CONFUSION_SIDE_EFFECT": ("conf", _pct(10)),
        "ATTACK_DOWN_SIDE_EFFECT": (0, _pct(33)), "DEFENSE_DOWN_SIDE_EFFECT": (1, _pct(33)),
        "SPEED_DOWN_SIDE_EFFECT": (2, _pct(33)), "SPECIAL_DOWN_SIDE_EFFECT": (3, _pct(33))}

DMG_EFFECTS = frozenset(SIDE) | {
    "NO_ADDITIONAL_EFFECT", "PAY_DAY_EFFECT", "DRAIN_HP_EFFECT", "DREAM_EATER_EFFECT", "EXPLODE_EFFECT",
    "SWIFT_EFFECT", "RECOIL_EFFECT", "TWO_TO_FIVE_ATTACKS_EFFECT", "ATTACK_TWICE_EFFECT", "TWINEEDLE_EFFECT",
    "JUMP_KICK_EFFECT", "HYPER_BEAM_EFFECT", "CHARGE_EFFECT", "FLY_EFFECT", "TRAPPING_EFFECT",
    "SUPER_FANG_EFFECT", "SPECIAL_DAMAGE_EFFECT", "OHKO_EFFECT", "THRASH_PETAL_DANCE_EFFECT", "RAGE_EFFECT"}
STATUS_EFFECTS = frozenset(STAT_UP) | frozenset(STAT_DOWN) | {
    "SLEEP_EFFECT", "POISON_EFFECT", "PARALYZE_EFFECT", "CONFUSION_EFFECT", "LEECH_SEED_EFFECT",
    "LIGHT_SCREEN_EFFECT", "REFLECT_EFFECT", "HEAL_EFFECT", "SUBSTITUTE_EFFECT", "TRANSFORM_EFFECT",
    "SPLASH_EFFECT", "SWITCH_AND_TELEPORT_EFFECT", "CONVERSION_EFFECT", "HAZE_EFFECT", "MIST_EFFECT",
    "FOCUS_ENERGY_EFFECT", "DISABLE_EFFECT", "BIDE_EFFECT", "METRONOME_EFFECT", "MIRROR_MOVE_EFFECT",
    "MIMIC_EFFECT"}


class Move:
    __slots__ = ("name", "type", "power", "acc", "pp", "effect", "phys", "hicrit", "prio", "kind", "supported")

    def __init__(self, name, d):
        self.name = name
        self.type = d["type"]
        self.power = d["power"]
        self.acc = min(255, d["acc"] * 255 // 100)
        self.pp = d["pp"]
        self.effect = d["effect"]
        self.phys = self.type in PHYS
        self.hicrit = name in HICRIT
        self.prio = 1 if name == "QUICK_ATTACK" else (-1 if name == "COUNTER" else 0)
        self.kind = "dmg" if (self.effect in DMG_EFFECTS) else "status"
        self.supported = self.effect in DMG_EFFECTS or self.effect in STATUS_EFFECTS

    def __repr__(self):
        return self.name


MV = {n: Move(n, d) for n, d in D["moves"].items()}
MOVE_ORDER = list(MV.values())  # pokered move id order (Metronome picks by id)
assert MOVE_ORDER[117].name == "METRONOME" and MOVE_ORDER[164].name == "STRUGGLE"
STRUGGLE = MV["STRUGGLE"]
RAGE_MV = MV["RAGE"]

_TM = {}


def type_mults(mt, t1, t2):
    k = (mt, t1, t2)
    r = _TM.get(k)
    if r is None:
        r = tuple(m for a, d, m in D["chart"] if a == mt and (d == t1 or d == t2))
        _TM[k] = r
    return r


# ---------------------------------------------------------------- mons
class Mon:
    __slots__ = ("key", "name", "types", "lvl", "maxhp", "hp", "st", "st0", "raw", "stage", "status", "slp",
                 "conf", "flinch", "sub", "reflect", "lscreen", "seeded", "recharge", "trapped", "trap_left",
                 "trap_mv", "trap_dmg", "charge", "invuln", "moves", "pp", "crit", "took_dmg", "took_type",
                 "used", "spd_div", "atk_div", "pumped", "mist", "dis_idx", "dis_left", "bide_left", "bide_acc",
                 "thrash_left", "thrash_mv", "rage", "last_mv", "skip", "toxic", "toxic_ticks")


def make_spec(key, move_names, statexp=None, level=None):
    s = D["mons"][key]
    L = battle_level(level)
    from .pool import pool
    from move_rules import validate_moves
    validate_moves(key, move_names, pool(key, L))
    statexp = RULES.statexp if statexp is None else statexp
    bonus = min(255, math.ceil(math.sqrt(statexp))) // 4

    def stat(base):
        return ((base + 15) * 2 + bonus) * L // 100 + 5

    hp = ((s["hp"] + 15) * 2 + bonus) * L // 100 + L + 10
    return dict(key=key, name=s["name"], types=(s["types"][0], s["types"][1]), lvl=L, hp=hp,
                st=(stat(s["atk"]), stat(s["defn"]), stat(s["spd"]), stat(s["spc"])),
                crit=s["spd"], moves=list(move_names))


def fresh(sp, rules=RULES, badges=False):
    m = Mon()
    m.key, m.name, m.types, m.lvl = sp["key"], sp["name"], sp["types"], sp["lvl"]
    m.maxhp = m.hp = sp["hp"]
    m.raw = tuple(sp["st"])                                   # unmodified stats (crits use these)
    m.st0 = tuple(min(999, v + v // 8) for v in m.raw) if badges else m.raw   # all eight badges: player only
    m.st = list(m.st0)
    m.stage = [0] * 6
    m.status = m.slp = m.conf = m.sub = m.trap_left = m.took_dmg = m.trap_dmg = 0
    m.bide_left = m.bide_acc = m.thrash_left = m.dis_left = 0
    m.flinch = m.reflect = m.lscreen = m.seeded = m.recharge = m.trapped = m.invuln = False
    m.pumped = m.mist = m.rage = m.skip = False
    m.trap_mv = m.charge = m.took_type = m.thrash_mv = m.last_mv = None
    m.dis_idx = -1
    m.spd_div = m.atk_div = 1
    m.moves = [MV[n] for n in sp["moves"]]
    m.pp = [mv.pp for mv in m.moves]
    m.crit = sp["crit"]
    m.toxic, m.toxic_ticks = False, 0
    m.used = {}
    return m


def estat(m, i):
    v = m.st[i] * RATIO[m.stage[i] + 6] // 100
    if i == 0 and m.atk_div > 1:
        v //= m.atk_div
    return 1 if v < 1 else (999 if v > 999 else v)


def spd(m):
    v = m.st[2] * RATIO[m.stage[2] + 6] // 100
    if m.spd_div > 1:
        v //= m.spd_div
    return 1 if v < 1 else (999 if v > 999 else v)


def calc_base(att, dfn, mv, crit=False, power=None):
    """Pre-roll damage after STAB and type effectiveness (0 if immune)."""
    L = att.lvl * 2 if crit else att.lvl
    ai, di = (0, 1) if mv.phys else (3, 3)
    if crit:
        A, Df = att.raw[ai], dfn.raw[di]      # crits ignore stages, screens, badge boosts and status penalties
    else:
        A, Df = estat(att, ai), estat(dfn, di)
        if mv.phys:
            if dfn.reflect:
                Df *= 2
        elif dfn.lscreen:
            Df *= 2
    if mv.effect == "EXPLODE_EFFECT":
        Df = max(1, Df // 2)
    if A > 255 or Df > 255:
        A = max(1, (A // 4) & 255)
        Df = max(1, (Df // 4) & 255)
    dmg = ((2 * L // 5 + 2) * (power or mv.power) * A // Df) // 50
    dmg = min(997, dmg) + 2
    if mv.type == att.types[0] or mv.type == att.types[1]:
        dmg += dmg // 2
    for mult in type_mults(mv.type, dfn.types[0], dfn.types[1]):
        dmg = dmg * mult // 10
    return dmg


def acc_thresh(m, o, mv):
    acc = mv.acc
    if m.stage[4] or o.stage[5]:
        acc = acc * RATIO[m.stage[4] + 6] // 100
        acc = acc * RATIO[6 - o.stage[5]] // 100
        acc = max(1, min(255, acc))
    return acc


def crit_thresh(m, mv):
    """CriticalHitTest from the disassembly, including the Focus Energy bug (it divides by 4)."""
    b = m.crit // 2
    if m.pumped:
        b >>= 1
    else:
        b = min(255, b * 2)
    if mv.hicrit:
        b = min(255, b * 2)
        b = min(255, b * 2)
    else:
        b >>= 1
    return b


def multi_hits(rnd):
    r = rnd(8) & 3
    if r < 2:
        return r + 2
    return (rnd(8) & 3) + 2


# ---------------------------------------------------------------- battle
class Battle:
    def __init__(self, sa, sb, rng, brain, rules=RULES, log=None):
        self.a, self.b = fresh(sa, rules, True), fresh(sb, rules, False)   # a = player, b = enemy
        self.wdamage = 0   # the game's "last damage" value (Bide reads it)
        self.rnd = rng.getrandbits
        self.brain = brain
        self.rules = rules
        self.log = log
        self.res = None   # 0 = A wins, 1 = B wins, 2 = draw
        self.turn = 0
        self.actor = None
        self.explosion = None

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

    def change_stage(self, S, idx, delta, actor):
        """Apply a stage change to S. Models the Gen 1 badge boost glitch: the changed stat is recalculated from
        its unmodified value and boosted once, the other stats are boosted again; paralysis/burn penalties are
        reapplied to the side that did not act (and removed from the actor's own recalculated speed/attack)."""
        s = S.stage[idx]
        n = max(-6, min(6, s + delta))
        if n == s:
            return False
        S.stage[idx] = n
        if self.rules.badge_glitch:
            if S is self.a:          # only the player has badges: its own stat-ups, or enemy stat drops on it
                if idx < 4:
                    S.st[idx] = S.st0[idx]
                for i in range(4):
                    if i != idx:
                        S.st[i] = min(999, S.st[i] + S.st[i] // 8)
            N = self.b if actor is self.a else self.a
            if N.status == PAR:
                N.spd_div = 4 if (S is N and idx == 2) else N.spd_div * 4
            if N.status == BRN:
                N.atk_div = 2 if (S is N and idx == 0) else N.atk_div * 2
            if S is actor:
                if idx == 2 and actor.status == PAR:
                    actor.spd_div = 1
                if idx == 0 and actor.status == BRN:
                    actor.atk_div = 1
        return True

    def inflict(self, o, st):
        if o.status:
            return False
        if st == PSN and "POISON" in o.types:
            return False
        if st == BRN and "FIRE" in o.types:
            return False
        if st == FRZ and "ICE" in o.types:
            return False
        o.status = st
        if st == SLP:
            r = self.rnd(8) & 7
            while r == 0:
                r = self.rnd(8) & 7
            o.slp = r
        elif st == PAR:
            o.spd_div = 4
        elif st == BRN:
            o.atk_div = 2
        return True

    def hit(self, m, o, mv):
        if mv.effect == "SWIFT_EFFECT":
            return True
        if o.invuln:
            return False
        return self.rnd(8) < acc_thresh(m, o, mv)

    # -- turn structure
    def pick(self, m, o):
        if m.recharge:
            return (None, -1, "recharge")
        if m.charge is not None:
            return (m.charge, -1, "charge2")
        if m.trap_left > 0:
            return (m.trap_mv, -1, "trapcont")
        if m.bide_left > 0:
            return (MV["BIDE"], -1, "bide")
        if m.thrash_left > 0:
            return (m.thrash_mv, -1, "thrash")
        if m.rage:
            return (RAGE_MV, -1, "rage")
        mv, idx = self.brain(m, o)
        return (mv, idx, "normal")

    def run(self):
        a, b, rnd = self.a, self.b, self.rnd
        for t in range(1, self.rules.turn_limit + 1):
            self.turn = t
            for m in (a, b):
                m.flinch = False
                m.took_dmg = 0
                m.took_type = None
            ca, cb = self.pick(a, b), self.pick(b, a)
            pa = ca[0].prio if ca[0] else 0
            pb = cb[0].prio if cb[0] else 0
            if pa != pb:
                a_first = pa > pb
            else:
                sa, sb = spd(a), spd(b)
                a_first = (rnd(8) < 128) if sa == sb else sa > sb
            order = ((a, b, ca), (b, a, cb)) if a_first else ((b, a, cb), (a, b, ca))
            for m, o, c in order:
                self.actor = m
                self.act(m, o, *c)
                if self.over():
                    return self.res
                self.residual(m, o)
                if self.over():
                    return self.res
        self.res = 2
        return 2

    def residual(self, m, o):
        def tick():
            damage=max(1,m.maxhp//16)
            if m.toxic:
                m.toxic_ticks=(m.toxic_ticks+1)&255
                damage*=m.toxic_ticks or 256
            return damage
        if m.status in (PSN,BRN):
            m.hp=max(0,m.hp-tick())
        if m.seeded:
            # Gen 1 reuses and increments Toxic's counter for Leech Seed too.
            damage=tick()
            m.hp=max(0,m.hp-damage)
            if o.hp>0:o.hp=min(o.maxhp,o.hp+damage)

    def can_move(self, m, o):
        rnd = self.rnd
        if m.skip:
            m.skip = False
            return False
        if m.recharge:
            m.recharge = False
            return False
        if m.status == FRZ:
            return False
        if m.status == SLP:
            m.slp -= 1
            if m.slp <= 0:
                m.status = 0
            return False
        if m.flinch:
            return False
        if m.trapped:
            return False
        if m.dis_left > 0:
            m.dis_left -= 1
            if m.dis_left == 0:
                m.dis_idx = -1
        if m.conf:
            m.conf -= 1
            if m.conf > 0 and rnd(8) < 128:
                self.self_hit(m)
                return False
        if m.status == PAR and rnd(8) < 63:
            return False
        return True

    def self_hit(self, m):
        A, Df = estat(m, 0), estat(m, 1)
        if A > 255 or Df > 255:
            A, Df = max(1, (A // 4) & 255), max(1, (Df // 4) & 255)
        d = ((2 * m.lvl // 5 + 2) * 40 * A // Df) // 50
        d = min(997, d) + 2
        if d > 1:
            d = d * self.roll() // 255
        m.hp = max(0, m.hp - d)

    def roll(self):
        r = self.rnd(8)
        while r < 217:
            r = self.rnd(8)
        return r

    def act(self, m, o, mv, idx, mode):
        if mv is None:  # recharge turn
            m.recharge = False
            return
        if not self.can_move(m, o):
            if m.trap_left > 0:
                m.trap_left = 0
                o.trapped = False
            m.charge = None
            m.bide_left = 0
            m.thrash_left = 0
            return
        if mode == "normal" and idx >= 0:
            if idx == m.dis_idx:          # disabled move: the turn is wasted
                return
            m.pp[idx] -= 1
        m.used[mv.name] = m.used.get(mv.name, 0) + 1
        m.last_mv = mv
        if mode == "charge2":
            m.charge = None
            m.invuln = False
        if self.log is not None:
            self.L(f"T{self.turn} [{'a' if m is self.a else 'b'}] {m.name} uses {mv.name} (hp {m.hp}/{m.maxhp}) vs {o.name} (hp {o.hp}/{o.maxhp})")
        if mode == "bide":                            # accumulates the game's last-damage value, not "damage taken"
            m.bide_acc += self.wdamage
            m.bide_left -= 1
            if m.bide_left == 0:
                dmg, m.bide_acc = min(65535, m.bide_acc * 2), 0
                self.wdamage = dmg
                if dmg > 0:
                    self.deal(o, dmg, "NORMAL")
            return
        if mode == "thrash":
            m.thrash_left -= 1
            if m.thrash_left <= 0:
                m.thrash_left = 0
                m.conf = (self.rnd(8) & 3) + 2
        if mv.kind == "dmg":
            self.dmg_move(m, o, mv, mode)
        else:
            self.status_move(m, o, mv, idx)

    def run_called(self, m, o, mv2):
        m.last_mv = mv2
        if self.log is not None:
            self.L(f"   -> {mv2.name}")
        if mv2.kind == "dmg":
            self.dmg_move(m, o, mv2, "normal")
        else:
            self.status_move(m, o, mv2)

    def deal(self, o, dmg, mt):
        """Apply damage to substitute or HP. Returns (dealt, hit_sub, sub_broke)."""
        o.took_dmg = dmg
        o.took_type = mt
        if o.sub > 0:
            o.sub -= dmg
            broke = o.sub <= 0
            if broke:
                o.sub = 0
            return dmg, True, broke
        d = min(dmg, o.hp)
        o.hp -= d
        return d, False, False

    def dmg_move(self, m, o, mv, mode):
        rnd, ef = self.rnd, mv.effect
        if mode == "trapcont":                      # repeats the stored damage, no accuracy check
            self.wdamage = m.trap_dmg
            self.deal(o, m.trap_dmg, mv.type)
            m.trap_left -= 1
            if m.trap_left <= 0 or o.hp <= 0:
                m.trap_left = 0
                o.trapped = False
            return
        if ef == "EXPLODE_EFFECT":
            self.explosion = m is self.a
            m.hp = 0  # self-faint even when the target is immune
        if ef == "DREAM_EATER_EFFECT" and o.status != SLP:
            return
        if mode == "normal" and ef in ("CHARGE_EFFECT", "FLY_EFFECT"):
            m.charge = mv
            if ef == "FLY_EFFECT":
                m.invuln = True
            return
        if not self.hit(m, o, mv):
            self.miss(m, o, mv)
            return
        name = mv.name
        total, hit_sub, broke, hits = 0, False, False, 1
        self.wdamage = 0
        if name == "COUNTER":
            if m.took_dmg > 0 and m.took_type in ("NORMAL", "FIGHTING"):
                self.wdamage = m.took_dmg * 2
                self.deal(o, m.took_dmg * 2, mv.type)
            return
        imm = 0 in type_mults(mv.type, o.types[0], o.types[1])
        if ef == "OHKO_EFFECT":
            if imm or spd(m) < spd(o):
                return
            dmg = 65535
        elif ef == "SPECIAL_DAMAGE_EFFECT":
            if imm:
                return
            if name in ("SEISMIC_TOSS", "NIGHT_SHADE"):
                dmg = m.lvl
            elif name == "SONICBOOM":
                dmg = 20
            elif name == "DRAGON_RAGE":
                dmg = 40
            else:
                lim = m.lvl * 3 // 2
                r = rnd(8)
                while r >= lim:
                    r = rnd(8)
                dmg = max(1, r)
        elif ef == "SUPER_FANG_EFFECT":
            if imm:
                return
            dmg = max(1, o.hp // 2)
        else:
            crit = rnd(8) < crit_thresh(m, mv)
            base = calc_base(m, o, mv, crit)
            if base == 0:
                if ef == "JUMP_KICK_EFFECT":
                    m.hp = max(0, m.hp - 1)
                return
            dmg = base if base <= 1 else base * self.roll() // 255
            if dmg == 0:
                dmg = 1
        self.wdamage = dmg
        if ef == "TWO_TO_FIVE_ATTACKS_EFFECT":
            hits = multi_hits(rnd)
        elif ef in ("ATTACK_TWICE_EFFECT", "TWINEEDLE_EFFECT"):
            hits = 2
        for _ in range(hits):
            d, hs, br = self.deal(o, dmg, mv.type)
            total += d
            hit_sub = hit_sub or hs
            if ef == "TWINEEDLE_EFFECT" and not hs and o.hp > 0 and rnd(8) < _pct(20):
                self.inflict(o, PSN)
            if o.hp <= 0 or br:
                broke = broke or br
                break
        if o.rage and o.hp > 0 and not hit_sub:     # Rage builds when the raging Pokemon is hit
            self.change_stage(o, 0, 1, o)
        # ---- side effects
        if o.hp > 0 and not hit_sub:
            se = SIDE.get(ef)
            if se:
                kind = se[0]
                if ef.endswith("DOWN_SIDE_EFFECT"):
                    if rnd(8) < se[1] and not (m is self.b and rnd(8) < 64):   # enemy stat drops fail 25%
                        self.change_stage(o, kind, -1, m)
                elif kind in (PAR, BRN, FRZ):
                    if o.status:
                        if o.status == FRZ and kind == BRN and mv.type == "FIRE":
                            o.status = 0                       # a Fire move with a burn effect thaws a frozen target
                    elif mv.type not in o.types and rnd(8) < se[1]:   # a target sharing the move's type is immune
                        if self.inflict(o, kind) and kind == FRZ:
                            o.recharge = False
                elif rnd(8) < se[1]:
                    if kind == "flinch":
                        o.flinch = True
                    elif kind == "conf":
                        if not o.conf:
                            o.conf = (rnd(8) & 3) + 2
                    else:
                        self.inflict(o, kind)
        if ef == "DRAIN_HP_EFFECT" or ef == "DREAM_EATER_EFFECT":
            if total > 0:
                m.hp = min(m.maxhp, m.hp + max(1, total // 2))
        elif ef == "RECOIL_EFFECT":
            if total > 0:
                m.hp = max(0, m.hp - max(1, total // (2 if mv.name == "STRUGGLE" else 4)))
        elif ef == "HYPER_BEAM_EFFECT":
            if o.hp > 0 and not broke:
                m.recharge = True
        elif ef == "TRAPPING_EFFECT":
            if o.hp > 0 and not hit_sub:
                m.trap_left = multi_hits(rnd) - 1
                m.trap_mv = mv
                m.trap_dmg = dmg
                o.trapped = True
        elif ef == "THRASH_PETAL_DANCE_EFFECT":
            if mode == "normal":                     # lock in for 2-3 more turns, then confusion
                m.thrash_left = (rnd(8) & 1) + 2
                m.thrash_mv = mv
        elif ef == "RAGE_EFFECT":
            if mode == "normal":
                m.rage = True
        if ef == "EXPLODE_EFFECT":
            m.hp = 0

    def miss(self, m, o, mv):
        self.wdamage = 0
        ef = mv.effect
        if ef == "JUMP_KICK_EFFECT":
            m.hp = max(0, m.hp - 1)
        elif ef == "EXPLODE_EFFECT":
            m.hp = 0
        if m.trap_left > 0:
            m.trap_left = 0
            o.trapped = False

    def haze(self, m, o):
        for x in (m, o):
            x.stage = [0] * 6
            x.st = list(x.raw)                       # stats reset to unmodified: badge boosts are gone
            x.spd_div = x.atk_div = 1
            x.conf = 0
            x.toxic,x.toxic_ticks=False,0
            x.mist = x.pumped = x.seeded = x.reflect = x.lscreen = False
            x.dis_idx, x.dis_left = -1, 0
        if o.status:                                  # only the target's status is cured
            if o.status in (FRZ, SLP):
                o.skip = True                         # it loses its move this turn
            o.status = 0

    def status_move(self, m, o, mv, idx=-1):
        ef, rnd = mv.effect, self.rnd
        if ef in STAT_UP:
            i, n = STAT_UP[ef]
            self.change_stage(m, i, n, m)
            return
        if ef == "REFLECT_EFFECT":
            m.reflect = True
            return
        if ef == "LIGHT_SCREEN_EFFECT":
            m.lscreen = True
            return
        if ef == "HEAL_EFFECT":
            diff = m.maxhp - m.hp
            if diff == 0 or diff % 256 == 255:
                return
            if mv.name == "REST":
                m.hp = m.maxhp
                m.status = SLP
                m.slp = 2
                m.spd_div = m.atk_div = 1
            else:
                m.hp += min(diff, m.maxhp // 2)
            return
        if ef == "SUBSTITUTE_EFFECT":
            cost = m.maxhp // 4
            if m.sub > 0 or m.hp < cost:       # fails only below the cost; paying it can leave 0 HP
                return
            m.hp -= cost
            m.sub = cost
            return
        if ef == "TRANSFORM_EFFECT":
            m.types = o.types
            m.st, m.st0, m.raw = list(o.st), o.st0, o.raw
            m.stage = list(o.stage)
            m.crit = o.crit
            m.moves = list(o.moves)
            m.pp = [5] * len(m.moves)
            m.dis_idx, m.dis_left = -1, 0
            return
        if ef == "MIMIC_EFFECT":
            if not self.hit(m,o,mv):return
            if idx<0:
                idx=next((i for i,x in enumerate(m.moves) if x.name=="MIMIC"),-1)
            if idx>=0 and o.moves:
                # Automatic battles use link-battle random selection; retain slot PP.
                m.moves[idx]=o.moves[rnd(8)%len(o.moves)]
            return
        if ef in ("SPLASH_EFFECT", "SWITCH_AND_TELEPORT_EFFECT"):
            return                                    # nothing happens in a trainer-style 1v1
        if ef == "MIST_EFFECT":
            m.mist = True
            return
        if ef == "FOCUS_ENERGY_EFFECT":
            m.pumped = True
            return
        if ef == "BIDE_EFFECT":
            m.bide_left = (rnd(8) & 1) + 2
            m.bide_acc = 0
            return
        if ef == "CONVERSION_EFFECT":
            if not o.invuln:
                m.types = o.types
            return
        if ef == "HAZE_EFFECT":
            self.haze(m, o)
            return
        if ef == "METRONOME_EFFECT":
            r = rnd(8)
            while r == 0 or r >= 165 or r == 118:
                r = rnd(8)
            self.run_called(m, o, MOVE_ORDER[r - 1])
            return
        if ef == "MIRROR_MOVE_EFFECT":
            mv2 = o.last_mv
            if mv2 is not None and mv2.effect != "MIRROR_MOVE_EFFECT":
                self.run_called(m, o, mv2)
            return
        # ---- moves that target the opponent
        if not self.hit(m, o, mv):
            self.wdamage = 0
            return
        if ef == "DISABLE_EFFECT":
            if o.dis_idx >= 0 or not any(p > 0 for p in o.pp):
                return
            n = len(o.moves)
            while True:
                r = rnd(8) & 3
                if r < n and o.pp[r] > 0:
                    break
            o.dis_idx, o.dis_left = r, (rnd(8) & 7) + 1
            return
        if o.sub > 0:
            return
        if ef in STAT_DOWN:
            if o.mist:                                # Mist blocks stat-lowering moves (not side effects)
                return
            if m is self.b and rnd(8) < 64:           # the enemy side's stat-lowering moves fail 25% of the time
                return
            i, n = STAT_DOWN[ef]
            self.change_stage(o, i, -n, m)
        elif ef == "SLEEP_EFFECT":
            self.inflict(o, SLP)
        elif ef == "POISON_EFFECT":
            if self.inflict(o, PSN) and mv.name=="TOXIC":
                o.toxic,o.toxic_ticks=True,0
        elif ef == "PARALYZE_EFFECT":
            if mv.name == "THUNDER_WAVE" and 0 in type_mults(mv.type, o.types[0], o.types[1]):
                return
            self.inflict(o, PAR)
        elif ef == "CONFUSION_EFFECT":
            if not o.conf:
                o.conf = (rnd(8) & 3) + 2
        elif ef == "LEECH_SEED_EFFECT":
            if not o.seeded and "GRASS" not in o.types:
                o.seeded = True
