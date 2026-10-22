"""Gen 2 (Crystal) shared basics: constants, moves, Pokemon state, stat and damage helpers."""
import math
from .data import load

D = load()
ENGINE_VERSION = "0.12.0"
SLP, PAR, BRN, PSN, FRZ = 1, 2, 3, 4, 5
PHYS = frozenset({"NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "STEEL"})
RATIO = [25, 28, 33, 40, 50, 66, 100, 150, 200, 250, 300, 350, 400]   # stage -6..+6, percent
from move_rules import BATTLE_LEVEL, battle_level
LEVEL = dict.fromkeys(("GROWTH_SLOW", "GROWTH_MEDIUM_FAST", "GROWTH_MEDIUM_SLOW", "GROWTH_FAST"), BATTLE_LEVEL)
HIGH_CRIT = frozenset({"KARATE_CHOP", "RAZOR_WIND", "RAZOR_LEAF", "CRABHAMMER", "SLASH", "AEROBLAST", "CROSS_CHOP"})
CRIT_CHANCE = (17, 32, 64, 85, 128)      # out of 256, by crit stage (pokecrystal)
PRIO = {"PROTECT": 2, "DETECT": 2, "ENDURE": 2, "PRIORITY_HIT": 1, "COUNTER": -1, "MIRROR_COAT": -1, "FORCE_SWITCH": -1}
DMG_NO_POWER = frozenset({"OHKO"})       # damaging effects whose power field is 0

class Rules:
    def __init__(self, both_faint_draw=True, turn_limit=50, statexp=11000):
        self.both_faint_draw = both_faint_draw    # any simultaneous faint is a draw
        self.badge_glitch = False                 # Gen 2 recalculates stats from scratch: no stacking
        self.turn_limit = turn_limit
        self.statexp = statexp

RULES = Rules()

class Move:
    __slots__ = ("name", "type", "power", "acc", "pp", "effect", "chance", "phys", "prio", "kind", "supported")

    def __init__(self, name, d):
        self.name = name
        self.type = d["type"]
        self.power = d["power"]
        self.acc = min(255, d["acc"] * 255 // 100)
        self.pp = d["pp"]
        self.effect = d["effect"][7:]            # drop "EFFECT_"
        self.chance = d["chance"] * 255 // 100   # threshold out of 256
        self.phys = self.type in PHYS
        self.prio = PRIO.get(self.effect, 0)
        if name == "VITAL_THROW":
            self.prio = -1
        self.kind = "dmg" if (self.power > 0 or self.effect in DMG_NO_POWER) else "status"
        self.supported = True

    def __repr__(self):
        return self.name

MV = {n: Move(n, d) for n, d in D["moves"].items()}
MOVE_ORDER = list(MV.values())                    # pokecrystal move id order (Metronome picks by id)
STRUGGLE = MV["STRUGGLE"]
NO_METRONOME = frozenset({"METRONOME", "STRUGGLE", "SKETCH", "COUNTER", "DESTINY_BOND", "DETECT", "ENDURE", "MIMIC",
                          "MIRROR_COAT", "MIRROR_MOVE", "PROTECT", "SLEEP_TALK", "THIEF"})
_TM = {}

def type_mults(mt, t1, t2, foresight=False):
    k = (mt, t1, t2, foresight)
    r = _TM.get(k)
    if r is None:
        r = tuple(m for a, d, m, fs in D["chart"] if a == mt and (d == t1 or d == t2) and not (fs and foresight))
        _TM[k] = r
    return r

class Mon:
    __slots__ = ("key", "name", "types", "lvl", "maxhp", "hp", "raw", "stage", "status", "slp", "toxic", "conf",
                 "flinch", "sub", "reflect", "lscreen", "safeguard", "mist", "seeded", "nightmare", "cursed", "perish",
                 "dbond", "protect_n", "protecting", "enduring", "encore_mv", "encore_left", "dis_idx", "dis_left",
                 "lockon", "foresight", "charge", "invuln", "recharge", "rampage_left", "rampage_mv", "rollout_left",
                 "rollout_n", "fury_n", "bide_left", "bide_acc", "trapped", "trap_left", "attract", "focus", "moves",
                 "pp", "took_dmg", "took_phys", "last_mv", "used", "badges", "future_left", "future_by", "curl",
                 "rage", "rage_n", "future_dmg", "skip", "gender", "bt", "minimized", "base_atk", "stolen", "species_key")

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
    g = s["gender"]
    gender = "F" if g == "GENDER_F100" else ("N" if g == "GENDER_UNKNOWN" else "M")
    return dict(key=key, name=s["name"], types=(s["types"][0], s["types"][1]), lvl=L, hp=hp, gender=gender,
                raw=(stat(s["atk"]), stat(s["defn"]), stat(s["spd"]), stat(s["spa"]), stat(s["sdf"])),
                base_atk=s["atk"], moves=list(move_names))

def fresh(sp, bt, badges):
    m = Mon()
    m.key, m.name, m.types, m.lvl, m.gender, m.bt = sp["key"], sp["name"], sp["types"], sp["lvl"], sp["gender"], bt
    m.maxhp = m.hp = sp["hp"]
    m.raw = tuple(sp["raw"])
    m.base_atk = sp["base_atk"]
    m.species_key = m.key
    m.stage = [0] * 7
    m.status = m.slp = m.toxic = m.conf = m.sub = 0
    m.reflect = m.lscreen = m.safeguard = m.perish = m.protect_n = 0
    m.encore_left = m.dis_left = m.rampage_left = m.rollout_left = m.rollout_n = m.fury_n = 0
    m.bide_left = m.bide_acc = m.trap_left = m.took_dmg = m.future_left = 0
    for f in ("flinch", "mist", "seeded", "nightmare", "cursed", "dbond", "protecting", "enduring", "lockon",
              "foresight", "recharge", "trapped", "attract", "focus", "curl", "rage", "rage_n", "future_dmg", "skip", "minimized", "stolen"):
        setattr(m, f, False)
    m.charge = m.invuln = m.encore_mv = m.rampage_mv = m.last_mv = m.future_by = m.took_phys = None
    m.dis_idx = -1
    m.moves = [MV[n] for n in sp["moves"]]
    m.pp = [mv.pp for mv in m.moves]
    m.used = {}
    m.rage_n = 1
    m.future_dmg = 0
    m.badges = badges
    return m

def estat(m, i):
    v = m.raw[i] * RATIO[m.stage[i] + 6] // 100
    v = 1 if v < 1 else (999 if v > 999 else v)
    if i == 2 and m.status == PAR:
        v = max(1, v // 4)
    elif i == 0 and m.status == BRN:
        v = max(1, v // 2)
    if m.badges:
        v = min(999, v + v // 8)
    return v

def spd(m):
    return estat(m, 2)

def crit_stage(m, mv):
    return min(4, (1 if m.focus else 0) + (2 if mv.name in HIGH_CRIT else 0))

def mtype_of(mv):
    return "TYPELESS" if mv.name in ("STRUGGLE", "BEAT_UP") else ("DARK" if mv.effect == "HIDDEN_POWER" else mv.type)

def calc_base(att, dfn, mv, crit=False, power=None):
    if mv.effect == "BEAT_UP":
        if att.status:
            return 0
        attack = D['mons'][att.key]['atk']
        defense = D['mons'][dfn.species_key]['defn']
        return min(997, ((2 * att.lvl // 5 + 2) * mv.power * attack // defense) // 50) + 2
    mt = mtype_of(mv)
    phys = mt in PHYS or mv.name == "STRUGGLE"
    ai, di = (0, 1) if phys else (3, 4) # But damage uses the computed type
    use_mod = (not crit) or dfn.stage[di] < att.stage[ai]
    A = estat(att, ai) if use_mod else att.raw[ai]
    Df = estat(dfn, di) if use_mod else dfn.raw[di]
    if not crit and ((phys and dfn.reflect) or (not phys and dfn.lscreen)):
        Df *= 2
    if mv.effect == "SELFDESTRUCT":
        Df = max(1, Df // 2)
    if A > 255 or Df > 255:
        A = max(1, (A // 4) & 255)
        Df = max(1, (Df // 4) & 255)
    pw = power if power is not None else mv.power
    dmg = ((2 * att.lvl // 5 + 2) * pw * A // Df) // 50
    if crit:
        dmg *= 2
    dmg = min(997, dmg) + 2
    w = att.bt.weather if att.bt is not None else None
    if w == "rain":
        dmg = dmg + dmg // 2 if mt == "WATER" else (dmg // 2 if mt == "FIRE" else dmg)
    elif w == "sun":
        dmg = dmg + dmg // 2 if mt == "FIRE" else (dmg // 2 if mt == "WATER" else dmg)
    if mv.effect == "FUTURE_SIGHT":
        return dmg  
    if mt == att.types[0] or mt == att.types[1]:
        dmg += dmg // 2
    for mult in type_mults(mt, dfn.types[0], dfn.types[1], dfn.foresight):
        dmg = dmg * mult // 10
    # Crystal applies Rage after STAB/type, before damage variation.
    if mv.effect == "RAGE":
        dmg = min(65535, dmg * att.rage_n)
    return dmg

def can_reach(mv, defender, locked=False):
    """Crystal CheckHit Fly/Dig exceptions, including the Lock-On ground bug."""
    state = defender.invuln
    if not state:
        return True
    if locked:
        return not (state == "fly" and mv.name in ("EARTHQUAKE", "FISSURE", "MAGNITUDE"))
    return ((state == "fly" and mv.name in ("GUST", "WHIRLWIND", "THUNDER", "TWISTER")) or
            (state == "dig" and mv.name in ("EARTHQUAKE", "FISSURE", "MAGNITUDE")))

def double_reach_damage(mv, defender):
    return ((defender.invuln == "fly" and mv.name in ("GUST", "TWISTER")) or
            (defender.invuln == "dig" and mv.name in ("EARTHQUAKE", "MAGNITUDE")))

ACC_RATIO = [33, 36, 43, 50, 60, 75, 100, 133, 166, 200, 233, 266, 300]

def acc_thresh(m, o, mv, accuracy=None):
    acc = mv.acc if accuracy is None else accuracy
    if accuracy is None and mv.effect == "THUNDER" and m.bt is not None and m.bt.weather == "sun":
        acc = 128  # ThunderAccuracy: 50 percent + 1, before stage modifiers.
    own, evasion = m.stage[5], o.stage[6]
    if o.foresight and evasion >= own:
        return acc
    # Crystal applies each ratio separately, rounding and flooring at one each time.
    acc = max(1, acc * ACC_RATIO[own + 6] // 100)
    acc = max(1, acc * ACC_RATIO[6 - evasion] // 100)
    return min(255, acc)

def ohko_thresh(m, o, mv):
    # BattleCommand_OHKO adds two accuracy bytes per level, then calls CheckHit.
    return acc_thresh(m, o, mv, min(255, mv.acc + 2 * (m.lvl - o.lvl)))

def multi_hits(rnd):
    r = rnd(8) & 3
    if r < 2:
        return r + 2
    return (rnd(8) & 3) + 2