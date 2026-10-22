"""Level-up movepools, plus egg moves for baby species only."""
from .engine import D, MV, LEVEL, type_mults

# Supported by the engine but not yet used by the brain's rules (kept out of pools until it is).
BRAIN_UNUSED = set()   # every move has a brain rule or falls through to the Highest Damage fallback
TYPES = ["NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "FIRE", "WATER", "GRASS",
         "ELECTRIC", "PSYCHIC_TYPE", "ICE", "DRAGON"]


def _preevos(key):
    return [(k, e[1]) for k, m in D["mons"].items() for e in m["evolutions"]
            if e[2].replace("_", "").lower() == key]


from functools import lru_cache

@lru_cache(None)
def _pool(key):
    from move_rules import level_pool
    return tuple(n for n in sorted(level_pool(D, key))
            if n in MV and MV[n].supported and n != 'STRUGGLE')

def pool(key, level=None):
    """Full natural learnset; level is a legacy argument and does not filter."""
    return list(_pool(key))


def _coverage(attack_types, defender_types_list):
    n = 0
    for d in defender_types_list:
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
    atk, spc = m["atk"], m["spc"]

    def score(n):
        mv = MV[n]
        if mv.kind != "dmg" or mv.effect == "EXPLODE_EFFECT" or n == "COUNTER":
            return 0.0
        pw = mv.power
        if mv.effect == "SPECIAL_DAMAGE_EFFECT":
            pw = 50
        elif mv.effect in ("OHKO_EFFECT",):
            pw = 40
        elif mv.effect == "SUPER_FANG_EFFECT":
            pw = 45
        elif mv.effect == "TWO_TO_FIVE_ATTACKS_EFFECT":
            pw *= 3
        elif mv.effect in ("ATTACK_TWICE_EFFECT", "TWINEEDLE_EFFECT"):
            pw *= 2
        elif mv.effect in ("CHARGE_EFFECT", "FLY_EFFECT", "HYPER_BEAM_EFFECT"):
            pw *= 0.55
        elif mv.effect == "DREAM_EATER_EFFECT":
            pw *= 0.2
        s = pw * (mv.acc / 255.0)
        if mv.type in types:
            s *= 1.5
        s *= (atk if mv.phys else spc) / 100.0
        if mv.hicrit:
            s *= 1.4
        return s

    atks = sorted([n for n in P if score(n) > 0], key=score, reverse=True)
    chosen = []
    if atks:
        chosen.append(atks[0])
        rest = [n for n in atks[1:] if MV[n].type != MV[atks[0]].type]
        defs = [t for t in TYPES]
        best = max(rest, key=lambda n: (_coverage({MV[atks[0]].type, MV[n].type}, defs), score(n)), default=None)
        if best:
            chosen.append(best)
    util = []
    for n in P:
        mv = MV[n]
        ef = mv.effect
        if ef == "SLEEP_EFFECT":
            util.append((100 + mv.acc / 10, n))
        elif n in ("RECOVER", "SOFTBOILED"):
            util.append((90, n))
        elif n == "THUNDER_WAVE" or ef == "PARALYZE_EFFECT":
            util.append((60 + mv.acc / 10, n))
        elif n == "SWORDS_DANCE" and atk >= 90:
            util.append((70, n))
        elif n == "AMNESIA" and spc >= 70:
            util.append((75, n))
        elif n == "REST":
            util.append((50, n))
        elif n == "SUBSTITUTE":
            util.append((40, n))
        elif n == "REFLECT":
            util.append((30, n))
        elif n == "COUNTER" and m["hp"] >= 100:
            util.append((35, n))
    for _, n in sorted(util, reverse=True):
        if len(chosen) >= 4:
            break
        chosen.append(n)
    for n in atks:
        if len(chosen) >= 4:
            break
        if n not in chosen:
            chosen.append(n)
    for n in P:  # status-only mons (Ditto, Magikarp): fill from whatever is legal
        if len(chosen) >= 4:
            break
        if n not in chosen:
            chosen.append(n)
    return chosen[:4]


if __name__ == "__main__":
    for k in ("mewtwo", "jynx", "ditto", "magikarp", "onix", "snorlax"):
        print(k, len(pool(k)), default_moves(k))
