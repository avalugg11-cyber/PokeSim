"""Pinned Emerald data, with real level-up/TM learnsets and move metadata."""
import json
import os
import re
import urllib.request
from storage import write_json
from forms import collapse_cosmetic_forms

REVISION = '731ad5bfd6e6f265508d0efcca0ba42f9dcf5881'
BASE = f'https://raw.githubusercontent.com/pret/pokeemerald/{REVISION}/'
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
OUT = os.path.join(HERE, 'data', 'gen3.json')
SCHEMA = 6

def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())

def fetch(path):
    local = os.path.join(RAW, path.replace('/', '_'))
    if not os.path.exists(local) or os.path.getsize(local) == 0:
        os.makedirs(RAW, exist_ok=True)
        with urllib.request.urlopen(BASE + path, timeout=30) as response:
            content = response.read()
        tmp = local + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(content)
        os.replace(tmp, local)
    with open(local, encoding='utf-8') as f:
        return f.read()

def entries(text, prefix):
    return re.split(r'\[' + prefix + r'_(\w+)\]\s*=', text)[1:]

def build():
    moves = {}
    chunks = entries(fetch('src/data/battle_moves.h'), 'MOVE')
    for name, chunk in zip(chunks[::2], chunks[1::2]):
        if name == 'NONE':
            continue
        def number(field, default=0):
            m = re.search(r'\.' + field + r'\s*=\s*(-?\d+)', chunk)
            return int(m[1]) if m else default
        effect = re.search(r'\.effect\s*=\s*EFFECT_(\w+)', chunk)
        typ = re.search(r'\.type\s*=\s*TYPE_(\w+)', chunk)
        if not effect or not typ:
            raise ValueError(f'incomplete move data: {name}')
        moves[name] = dict(effect=effect[1], type=typ[1], power=number('power'), acc=number('accuracy'),
                           pp=number('pp'), chance=number('secondaryEffectChance'), priority=number('priority'),
                           contact='FLAG_MAKES_CONTACT' in chunk, protect='FLAG_PROTECT_AFFECTED' in chunk,
                           snatch='FLAG_SNATCH_AFFECTED' in chunk, reflectable='FLAG_MAGIC_COAT_AFFECTED' in chunk, sound=name in {'GROWL','ROAR','SING','SUPERSONIC','SCREECH','SNORE','UPROAR','METAL_SOUND','GRASS_WHISTLE','HYPER_VOICE','PERISH_SONG','HEAL_BELL'})
    learns = {}
    for label, body in re.findall(r'(s\w+LevelUpLearnset)\[\]\s*=\s*\{(.*?)\};', fetch('src/data/pokemon/level_up_learnsets.h'), re.S):
        learns[label] = [[int(lv), move] for lv, move in re.findall(r'LEVEL_UP_MOVE\(\s*(\d+),\s*MOVE_(\w+)\)', body)]
    pointers = dict(re.findall(r'\[SPECIES_(\w+)\]\s*=\s*(s\w+LevelUpLearnset)', fetch('src/data/pokemon/level_up_learnset_pointers.h')))
    tms = {}
    chunks = entries(fetch('src/data/pokemon/tmhm_learnsets.h'), 'SPECIES')
    for name, body in zip(chunks[::2], chunks[1::2]):
        tms[name] = re.findall(r'\.(\w+)\s*=\s*TRUE', body)
    evolutions = {}
    chunks = entries(fetch('src/data/pokemon/evolution.h'), 'SPECIES')
    for name, body in zip(chunks[::2], chunks[1::2]):
        evolutions[name] = [[kind, int(value) if value.isdigit() else 0, dest]
                           for kind, value, dest in re.findall(r'\{(EVO_\w+),\s*(\w+),\s*SPECIES_(\w+)\}', body)]
    weights = {name: int(value) for name,value in re.findall(r'\[NATIONAL_DEX_(\w+)\]\s*=\s*\{.*?\.weight\s*=\s*(\d+)', fetch('src/data/pokemon/pokedex_entries.h'), re.S)}
    mons = {}
    chunks = entries(fetch('src/data/pokemon/species_info.h'), 'SPECIES')
    for name, body in zip(chunks[::2], chunks[1::2]):
        hp = re.search(r'\.baseHP\s*=\s*(\d+)', body)
        if not hp or name not in pointers:
            continue
        def field(pattern):
            m = re.search(pattern, body)
            if not m: raise ValueError(f'incomplete species data: {name}: {pattern}')
            return m[1]
        types = re.findall(r'TYPE_(\w+)', field(r'\.types\s*=\s*\{([^}]+)\}'))
        abilities = re.findall(r'ABILITY_(\w+)', field(r'\.abilities\s*=\s*\{([^}]+)\}'))
        growth = field(r'\.growthRate\s*=\s*(GROWTH_\w+)')
        gender = field(r'\.genderRatio\s*=\s*([^,\n]+)')
        mons[norm(name)] = dict(name=name, hp=int(hp[1]), atk=int(field(r'\.baseAttack\s*=\s*(\d+)')),
            defn=int(field(r'\.baseDefense\s*=\s*(\d+)')), spe=int(field(r'\.baseSpeed\s*=\s*(\d+)')),
            spa=int(field(r'\.baseSpAttack\s*=\s*(\d+)')), sdf=int(field(r'\.baseSpDefense\s*=\s*(\d+)')),
            types=types, abilities=abilities, growth=growth, gender=gender, weight=weights[name],
            lvl=learns[pointers[name]], tm=tms.get(name, []), evolutions=evolutions.get(name, []))
    if len(mons) != 386 or len(moves) != 354:
        raise ValueError(f'incomplete Emerald extraction: {len(mons)} species, {len(moves)} moves')
    text=fetch('src/battle_main.c').split('const u8 gTypeEffectiveness[336] =',1)[1].split('};',1)[0]
    factors={'NOT_EFFECTIVE':5,'SUPER_EFFECTIVE':20,'NO_EFFECT':0}
    chart=[[a,b,factors[value]] for a,b,value in re.findall(r'TYPE_(\w+), TYPE_(\w+), TYPE_MUL_(\w+)',text) if a not in ('FORESIGHT','ENDTABLE')]
    from move_rules import BABIES
    eggs = {norm(name): re.findall(r'MOVE_(\w+)', body)
            for name, body in re.findall(r'egg_moves\((\w+),(.*?)\)', fetch('src/data/pokemon/egg_moves.h'), re.S)
            if norm(name) in BABIES}
    if len(eggs) != 9: raise ValueError('incomplete Emerald baby egg moves')
    daycare = fetch('src/daycare.c')
    if 'GiveVoltTackleIfLightBall(&egg, daycare)' not in daycare: raise ValueError('missing special Pichu breeding rule')
    eggs['pichu'].append('VOLT_TACKLE')
    from forms import add_gen3
    with open(os.path.join(RAW,'forms.json'), encoding='utf-8') as f: add_gen3(mons,json.load(f))
    return dict(schema=SCHEMA, source_revision=REVISION, mons=mons, moves=moves, chart=chart, baby_eggs=eggs)

def load():
    try:
        with open(OUT, encoding='utf-8') as f:
            result = json.load(f)
        if result.get('schema') == SCHEMA and result.get('source_revision') == REVISION:
            if collapse_cosmetic_forms(result['mons']):
                write_json(OUT, result)
            return result
    except (OSError, ValueError):
        pass
    result = build()
    write_json(OUT, result)
    return result
