"""Lazy generation registry. Engines never share mutable battle state."""
from functools import lru_cache
from importlib import import_module
from types import SimpleNamespace

_NAMES = {1: 'Gen 1 (Red/Blue/Yellow)', 2: 'Gen 2 (Crystal)', 3: 'Gen 3 (Emerald + forms)', 4: 'Gen 4 (Platinum + forms)'}

def available():
    return [dict(id=n, name=name) for n, name in _NAMES.items()]

@lru_cache(None)
def get(n):
    if type(n) is not int or n not in _NAMES:
        raise ValueError(f'generation {n!r} is not available')
    root = f'gens.gen{n}'
    engine = import_module(root + '.engine')
    pool = import_module(root + '.pool')
    brain = import_module(root + '.brain')
    return SimpleNamespace(id=n, E=engine, P=pool, brain=brain.brain, BRAIN_VERSION=brain.BRAIN_VERSION)
