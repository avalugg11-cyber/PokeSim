"""Level-up movepools, plus egg moves for baby species only."""
from .base import D, MV, LEVEL, type_mults, PHYS
from .data import norm

TYPES = ["NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "STEEL", "FIRE", "WATER", "GRASS",
         "ELECTRIC", "PSYCHIC_TYPE", "ICE", "DRAGON", "DARK"]
_PRE = {}

def _preevos(key):
    if not _PRE:
        for k, m in D["mons"].items():
            for kind, lv, sp in m["evolutions"]:
                _PRE.setdefault(norm(sp), []).append((k, lv))
    return _PRE.get(key, [])

from functools import lru_cache

@lru_cache(None)
def _pool(key):
    from move_rules import level_pool
    return tuple(n for n in sorted(level_pool(D, key))
            if n in MV and MV[n].supported and n != 'STRUGGLE')

def pool(key, level=None):
    """Full natural learnset; level is a legacy argument and does not filter."""
    return list(_pool(key))


def _coverage(attack_types):
    n = 0
    for d in TYPES:
        for t in attack_types:
            mult = 10
            for x in type_mults(t, d, d):
                mult = mult * x // 10
            if mult > 10:
                n += 1
                break
    return n

def default_moves(key):
    """Heuristic seed set: best STAB attack, a coverage attack, then sleep / recovery / utility."""
    m = D["mons"][key]
    P = pool(key)
    if not P:
        return ["STRUGGLE"]
    types = set(m["types"])

    def score(n):
        mv = MV[n]
        if mv.kind != "dmg" or mv.effect in ("SELFDESTRUCT", "COUNTER", "MIRROR_COAT", "FUTURE_SIGHT", "BEAT_UP"):
            return 0.0
        pw = mv.power
        if mv.effect in ("LEVEL_DAMAGE", "STATIC_DAMAGE", "PSYWAVE", "SUPER_FANG"):
            pw = 50
        elif mv.effect == "OHKO":
            pw = 40
        elif mv.effect in ("MULTI_HIT", "TRIPLE_KICK"):
            pw *= 3
        elif mv.effect in ("DOUBLE_HIT", "POISON_MULTI_HIT"):
            pw *= 2
        elif mv.effect in ("FLY", "RAZOR_WIND", "SKULL_BASH", "SKY_ATTACK", "SOLARBEAM", "HYPER_BEAM"):
            pw *= 0.55
        elif mv.effect in ("DREAM_EATER", "SNORE"):
            pw *= 0.2
        elif mv.effect in ("RETURN",):
            pw = 102
        elif mv.effect == "HIDDEN_POWER":
            pw = 70
        elif mv.power <= 1:
            pw = 40
        s = pw * (mv.acc / 255.0)
        mt = "DARK" if mv.effect == "HIDDEN_POWER" else mv.type
        if mt in types:
            s *= 1.5
        s *= (m["atk"] if mt in PHYS else m["spa"]) / 100.0
        return s

    atks = sorted([n for n in P if score(n) > 0], key=score, reverse=True)
    chosen = []
    if atks:
        chosen.append(atks[0])
        rest = [n for n in atks[1:] if MV[n].type != MV[atks[0]].type]
        best = max(rest, key=lambda n: (_coverage({MV[atks[0]].type, MV[n].type}), score(n)), default=None)
        if best:
            chosen.append(best)
    util = []
    for n in P:
        mv = MV[n]
        ef = mv.effect
        if ef == "SLEEP":
            util.append((100 + mv.acc / 10, n))
        elif n in ("RECOVER", "SOFTBOILED", "MILK_DRINK", "MOONLIGHT", "MORNING_SUN", "SYNTHESIS"):
            util.append((90, n))
        elif ef == "PARALYZE":
            util.append((60 + mv.acc / 10, n))
        elif n == "SWORDS_DANCE" and m["atk"] >= 90:
            util.append((70, n))
        elif n in ("CURSE", "BELLY_DRUM") and m["atk"] >= 90:
            util.append((72, n))
        elif n == "AMNESIA" and m["spa"] >= 70:
            util.append((75, n))
        elif n == "REST":
            util.append((50, n))
        elif n == "SUBSTITUTE":
            util.append((40, n))
        elif n == "PROTECT":
            util.append((20, n))
    for _, n in sorted(util, reverse=True):
        if len(chosen) >= 4:
            break
        chosen.append(n)
    for n in atks:
        if len(chosen) >= 4:
            break
        if n not in chosen:
            chosen.append(n)
    for n in P:
        if len(chosen) >= 4:
            break
        if n not in chosen:
            chosen.append(n)
    return chosen[:4]