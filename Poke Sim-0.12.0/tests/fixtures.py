"""Small synthetic datasets; no downloaded data or external services required."""
import copy
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def generation(gen):
    package = f'testgen{gen}'
    if package + '.engine' in sys.modules:
        return sys.modules[package + '.fixture']
    pkg = types.ModuleType(package)
    pkg.__path__ = []
    sys.modules[package] = pkg
    def move(power=50, effect='NORMAL_HIT', typ='NORMAL', chance=0, **extra):
        return dict(type=typ, power=power, acc=100, pp=30, effect=effect, chance=chance, category='PHYSICAL', **extra)
    moves = {'STRUGGLE': move(50, 'RECOIL_HIT'), 'TACKLE': move(35),
             'THUNDERBOLT': move(95, typ='ELECTRIC'), 'BODY_SLAM': move(85),
             'RECOVER': move(0, 'HEAL'), 'SPLASH': move(0, 'SPLASH'),
             'UPROAR': move(50, 'UPROAR'), 'WAKE_UP_SLAP': move(60, typ='FIGHTING'),
             'ANCIENT_POWER': move(60, 'ALL_STATS_UP_HIT', 'ROCK', 10),
             'LOCK_ON': move(0, 'LOCK_ON'), 'FISSURE': move(0, 'OHKO', 'GROUND'),
             'BEAT_UP': move(10, 'BEAT_UP', 'DARK'), 'TRANSFORM': move(0, 'TRANSFORM'),
             'REFLECT': move(0, 'REFLECT'), 'LIGHT_SCREEN': move(0, 'LIGHT_SCREEN'),
             'SELFDESTRUCT': move(200, 'SELFDESTRUCT')}
    moves['FISSURE']['acc'] = 30
    if gen == 1:
        records = {}
        names = list(moves) + [f'FILLER_{i}' for i in range(165-len(moves))]
        names.remove('STRUGGLE'); names.insert(164, 'STRUGGLE')
        names.remove('FILLER_0'); names.insert(117, 'METRONOME')
        alias = {'RECOVER':'HEAL_EFFECT', 'SPLASH':'SPLASH_EFFECT', 'METRONOME':'METRONOME_EFFECT',
                 'STRUGGLE':'RECOIL_EFFECT', 'REFLECT':'REFLECT_EFFECT', 'LIGHT_SCREEN':'LIGHT_SCREEN_EFFECT',
                 'SELFDESTRUCT':'EXPLODE_EFFECT'}
        names[16] = 'RAGE'
        for name in names:
            record = moves.get(name, move())
            record['effect'] = alias.get(name, 'RAGE_EFFECT' if name=='RAGE' else 'NO_ADDITIONAL_EFFECT')
            records[name] = record
        moves = records
    elif gen == 2:
        for mv in moves.values():
            mv['effect'] = 'EFFECT_' + mv['effect']
    def mon(k):
        return dict(name=k.upper(), hp=80, atk=80, defn=80, spe=80, spd=80, spc=80, spa=80, sdf=80,
                    types=['NORMAL','NORMAL'], abilities=['KEEN_EYE','SERENE_GRACE','PRESSURE'],
                    gender='GENDER_MALE' if gen==2 else 'MON_MALE', weight=100,
                    growth='GROWTH_SLOW', base_species=k, lvl=[[1,n] for n in moves if n!='STRUGGLE'], evolutions=[])
    dataset = dict(moves=moves, chart=[], mons={k:mon(k) for k in ('a','b','c','d')})
    data = types.ModuleType(package + '.data')
    data.load = lambda: dataset
    data.norm = lambda s: ''.join(c for c in s.lower() if c.isalnum())
    sys.modules[data.__name__] = data
    mods = {}
    for name in (['engine','pool','brain'] if gen==1 else ['base','pool','effects','brain','engine']):
        mods[name] = load_module(package+'.'+name, ROOT/f'gens/gen{gen}/{name}.py')
    engine = mods['engine']
    fixture = types.SimpleNamespace(id=gen, E=engine, P=mods['pool'], brain=mods['brain'].brain,
                                    BRAIN_VERSION=mods['brain'].BRAIN_VERSION, brainmod=mods['brain'],
                                    base=mods.get('base', engine), data=dataset)
    sys.modules[package+'.fixture'] = fixture
    return fixture


def build(gen, moves=None, **kw):
    moves = moves or ['TACKLE','THUNDERBOLT','RECOVER','BODY_SLAM']
    if gen < 3:
        return moves
    return dict(moves=moves, ability=kw.get('ability','KEEN_EYE'),
                nature=kw.get('nature','MODEST'), evs=copy.deepcopy(kw.get('evs',
                {'hp':4, 'spa':252, 'spe':252})))
