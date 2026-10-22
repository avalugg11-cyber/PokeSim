"""Move acquisition rules shared by all generation pools."""

BATTLE_LEVEL = 50


def battle_level(level=None):
    """The format fixes level for stats and level-dependent battle mechanics."""
    if level is not None and (type(level) is not int or level != BATTLE_LEVEL):
        raise ValueError('this format requires level 50')
    return BATTLE_LEVEL


BABIES = frozenset({'pichu','cleffa','igglybuff','togepi','tyrogue','smoochum','elekid','magby','azurill','wynaut','budew','chingling','bonsly','mimejr','happiny','munchlax','riolu','mantyke'})

def level_pool(data, key, level=None):
    """All initial/level-up moves, including retained pre-evolution moves.

    Learn levels do not restrict acquisition in the fixed-level-50 format.
    The legacy level argument is accepted for callers but does not filter moves.
    Egg moves apply only to an actual baby species, never to evolved species.
    """
    parents = {}
    for parent, mon in data['mons'].items():
        for _, _, dest in mon['evolutions']:
            child = ''.join(c for c in dest.lower() if c.isalnum())
            parents.setdefault(child, []).append(parent)
    seen, stack, moves = set(), [key], set()
    while stack:
        current = stack.pop()
        if current in seen: continue
        seen.add(current)
        mon = data['mons'][current]
        moves.update(mon.get('start', []))
        moves.update(move for _, move in mon['lvl'])
        stack.extend(parents.get(current, []))
    if key in BABIES:
        moves.update(data.get('baby_eggs', {}).get(key, []))
    return moves

def validate_moves(key, moves, allowed):
    if (not isinstance(moves, list) or not 1 <= len(moves) <= 4
        or any(not isinstance(m, str) for m in moves) or len(set(moves)) != len(moves)):
        raise ValueError('build needs 1..4 distinct moves')
    illegal = [m for m in moves if m not in allowed]
    if illegal:
        raise ValueError(f'illegal moves for {key}: {illegal}; use level-up moves or baby egg moves. '
                         'Use Fresh start to replace older saved builds.')
