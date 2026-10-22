"""Gen 4 Legal movepools, standard EV spreads, and multi-dimensional neighbor generation."""
import json
import copy
from .base import D, NATURES, MV

# Curated competitive EV spreads (HP, Atk, Def, SpA, SpD, Spe)
EV_SPREADS = [
    {"hp": 4, "atk": 252, "defn": 0, "spa": 0, "sdf": 0, "spe": 252},     # Fast Physical
    {"hp": 4, "atk": 0, "defn": 0, "spa": 252, "sdf": 0, "spe": 252},     # Fast Special
    {"hp": 252, "atk": 252, "defn": 4, "spa": 0, "sdf": 0, "spe": 0},     # Bulky Physical
    {"hp": 252, "atk": 0, "defn": 4, "spa": 252, "sdf": 0, "spe": 0},     # Bulky Special
    {"hp": 252, "atk": 0, "defn": 252, "spa": 0, "sdf": 4, "spe": 0},     # Physical Wall
    {"hp": 252, "atk": 0, "defn": 4, "spa": 0, "sdf": 252, "spe": 0}      # Special Wall
]

from functools import lru_cache
from .base import LEVEL, PHYS, mtype_of
from .data import norm

@lru_cache(None)
def _pool(key):
    from move_rules import level_pool
    moves = level_pool(D, key)
    return tuple(sorted(m for m in moves if m in MV and MV[m].supported and m != 'STRUGGLE'))

def pool(key, level=None):
    """Full natural learnset; level is a legacy argument and does not filter."""
    return list(_pool(key))

def default_moves(key):
    """Smart heuristic seed mapping to break local maxima."""
    m = D["mons"][key]
    abs_list = [a for a in m["abilities"] if a != "NONE"]
    ability = abs_list[0] if abs_list else "NONE"
    
    p = pool(key)
    is_special = m['spa'] > m['atk']
    def value(name):
        mv = MV[name]
        if mv.kind != 'dmg' or mv.effect in {'SELFDESTRUCT','COUNTER','MIRROR_COAT','FUTURE_SIGHT'}: return 0
        typ = mtype_of(mv)
        power = 102 if name == 'RETURN' else 70 if name == 'HIDDEN_POWER' else mv.power
        attack = m['atk'] if mv.phys else m['spa']
        score = power * attack * (1.5 if typ in m['types'] else 1) * (mv.acc or 100) / 100
        if mv.effect in {'FLY','SOLARBEAM','HYPER_BEAM','SKY_ATTACK','SKULL_BASH'}: score /= 2
        return score
    attacks = sorted((n for n in p if value(n) > 0), key=value, reverse=True)
    moves = attacks[:1]
    for name in attacks[1:]:
        if not moves or mtype_of(MV[name]) != mtype_of(MV[moves[0]]):
            moves.append(name); break
    for name in ['SPORE','SLEEP_POWDER','LOVELY_KISS','RECOVER','SOFT_BOILED','SLACK_OFF','MILK_DRINK','CALM_MIND','BULK_UP','THUNDER_WAVE','TOXIC','REST']:
        if name in p and name not in moves and len(moves)<4: moves.append(name)
    for name in attacks + p:
        if name not in moves and len(moves)<4: moves.append(name)
    return {
        "moves": moves[:4],
        "ability": ability,
        "nature": "MODEST" if is_special else "ADAMANT",
        "evs": copy.deepcopy(EV_SPREADS[1] if is_special else EV_SPREADS[0])
    }

def neighbours(key, cur_build, pl):
    out, seen = [], set()
    legal_abilities = [a for a in D["mons"][key]["abilities"] if a != "NONE"]
    if not legal_abilities: legal_abilities = ["NONE"]
    
    def state_hash(b): return json.dumps(b, sort_keys=True)
    seen.add(state_hash(cur_build))
    
    # 1. Move neighbors
    cur_moves = cur_build["moves"]
    for s in range(len(cur_moves) + (len(cur_moves) < 4)):
        for m in pl:
            if m in cur_moves: continue
            nb = dict(cur_build)
            nb["moves"] = cur_moves[:s] + [m] + cur_moves[s + 1:]
            h = state_hash(nb)
            if h not in seen:
                seen.add(h); out.append(nb)
                
    # 2. Nature neighbors
    for nat in NATURES.keys():
        if nat == cur_build["nature"]: continue
        nb = dict(cur_build)
        nb["nature"] = nat
        h = state_hash(nb)
        if h not in seen:
            seen.add(h); out.append(nb)
            
    # 3. EV neighbors
    for ev in EV_SPREADS:
        if ev == cur_build["evs"]: continue
        nb = dict(cur_build)
        nb["evs"] = ev
        h = state_hash(nb)
        if h not in seen:
            seen.add(h); out.append(nb)
            
    # Refine thresholds in 4-EV stat steps, beyond the preset seeds.
    fields = ('hp','atk','defn','spa','sdf','spe')
    current = {k: cur_build['evs'].get(k,0) for k in fields}
    for amount in (4,32):
        for dest in fields:
            if current[dest]+amount > 252: continue
            if sum(current.values())+amount <= 510:
                ev = dict(current); ev[dest] += amount
                nb = dict(cur_build, evs=ev)
                h=state_hash(nb)
                if h not in seen: seen.add(h); out.append(nb)
            for source in fields:
                if source == dest or current[source] < amount: continue
                ev = dict(current); ev[source] -= amount; ev[dest] += amount
                nb = dict(cur_build, evs=ev)
                h=state_hash(nb)
                if h not in seen: seen.add(h); out.append(nb)

    # 4. Ability neighbors
    for ab in legal_abilities:
        if ab == cur_build["ability"]: continue
        nb = dict(cur_build)
        nb["ability"] = ab
        h = state_hash(nb)
        if h not in seen:
            seen.add(h); out.append(nb)
            
    return out