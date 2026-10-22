"""Gen 2 (Crystal) data loader: pulls canonical data from the pret/pokecrystal disassembly and caches it to
data/gen2.json (offline after the first run). All 251 Pokemon, 251 moves, 17 types."""
import json, os, re, urllib.request
from storage import write_json

BASE = "https://raw.githubusercontent.com/pret/pokecrystal/97187cd21b15e9a266a786318c851848f2fac24b/"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "data", "gen2.json")

def fetch(path):
    local = os.path.join(RAW, path.replace("/", "_"))
    # Re-download if the file doesn't exist or is empty (0 bytes) from a previous interrupted run
    if not os.path.exists(local) or os.path.getsize(local) == 0:
        os.makedirs(RAW, exist_ok=True)
        with urllib.request.urlopen(BASE + path, timeout=30) as r:
            data = r.read()
        with open(local, "wb") as f:
            f.write(data)
    with open(local, encoding="utf-8") as f:
        return f.read()

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

def parse_evos(text):
    out = {}
    blocks = re.split(r"^(\w+)EvosAttacks:\s*$", text, flags=re.M)
    for i in range(1, len(blocks), 2):
        lines = [re.sub(r"\s+", " ", re.sub(r";.*", "", l)).strip() for l in blocks[i + 1].splitlines()]
        lines = [l for l in lines if l]
        k, evolutions, learn = 0, [], []
        while k < len(lines) and lines[k] != "db 0":
            m = re.match(r"db (EVOLVE_\w+), ([^,]+), (?:\w+, )?(\w+)$", lines[k])
            if m:
                kind = m.group(1)[7:].lower()
                lvl = int(m.group(2)) if kind in ("level", "stat") and m.group(2).strip().isdigit() else 0
                evolutions.append((kind, lvl, m.group(3)))
            k += 1
        k += 1
        while k < len(lines) and lines[k] != "db 0":
            m = re.match(r"db (\d+), (\w+)", lines[k])
            if m:
                learn.append((int(m.group(1)), m.group(2)))
            k += 1
        out[norm(blocks[i])] = dict(evolutions=evolutions, learn=learn)
    return out

def baby_eggs():
    from move_rules import BABIES
    text = fetch('data/pokemon/egg_moves.asm')
    result = {}
    for name, body in re.findall(r'^(\w+)EggMoves:\s*\n(.*?)(?=^\w+EggMoves:|\Z)', text, re.M | re.S):
        key = norm(name)
        if key in BABIES:
            result[key] = re.findall(r'^\s*db ([A-Z][A-Z_0-9]+)\s*(?:;.*)?$', body, re.M)
    if len(result) != 8: raise ValueError('incomplete Crystal baby egg moves')
    return result

def build():
    moves = {}
    for m in re.finditer(r"^\s*move\s+(\w+),\s*(EFFECT_\w+),\s*(\d+),\s*(\w+),\s*(\d+),\s*(\d+),\s*(\d+)",
                         fetch("data/moves/moves.asm"), re.M):
        name, eff, power, typ, acc, pp, chance = m.groups()
        moves[name] = dict(effect=eff, power=int(power), type=typ, acc=int(acc), pp=int(pp), chance=int(chance))
    chart, foresight = [], False
    for l in fetch("data/types/type_matchups.asm").splitlines():
        l = re.sub(r";.*", "", l).strip()
        if re.match(r"db\s+-2", l):
            foresight = True
            continue
        m = re.match(r"db\s+(\w+),\s+(\w+),\s+(NO_EFFECT|NOT_VERY_EFFECTIVE|SUPER_EFFECTIVE)", l)
        if m:
            a, d, e = m.groups()
            chart.append([a, d, {"NO_EFFECT": 0, "NOT_VERY_EFFECTIVE": 5, "SUPER_EFFECTIVE": 20}[e], int(foresight)])
    
    tutors = re.findall(r"add_mt (\w+)", fetch("constants/item_constants.asm"))
    evos = parse_evos(fetch("data/pokemon/evos_attacks.asm"))
    index = list(dict.fromkeys(re.findall(r'base_stats/(\w+)\.asm', fetch("data/pokemon/base_stats.asm"))))
    mons = {}
    
    for dex, fname in enumerate(index, 1):
        t = fetch(f"data/pokemon/base_stats/{fname}.asm")
        
        stat_match = re.search(r"db\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", t)
        if not stat_match:
            raise RuntimeError(f"Could not parse base stats for {fname}. File might be corrupted. Delete the 'gens/gen2/raw' folder and run again.\nPreview: {t[:100]}")
        stats = [int(x) for x in stat_match.groups()]
        
        type_match = re.search(r"\n\s*db ([A-Z_]+), ([A-Z_]+)\s*(?:;[^\n]*)?\n\s*db \d+", t)
        if not type_match:
            type_match = re.search(r"\n\s*db\s+([A-Z_]+)\s*,\s*([A-Z_]+)", t)
        types = type_match.groups() if type_match else ("NORMAL", "NORMAL")

        growth_match = re.search(r"db (GROWTH_\w+)", t)
        growth = growth_match.group(1) if growth_match else "GROWTH_MEDIUM_FAST"
        
        gender_match = re.search(r"db (GENDER_\w+)", t)
        gender = gender_match.group(1) if gender_match else "GENDER_UNKNOWN"
        
        tm_match = re.search(r"\btmhm\b(.*?)(?:\n\s*;\s*end|\n\s*[a-z]+ |\Z)", t, re.S)
        tm_raw = tm_match.group(1) if tm_match else ""
        tm = re.findall(r"[A-Z][A-Z_0-9]+", re.sub(r";[^\n]*", "", tm_raw).replace("\\", " "))
        tm = [x for x in tm if x not in tutors]
        
        key = norm(fname)
        mons[key] = dict(dex=dex, name=fname.upper().replace("__", "_"), hp=stats[0], atk=stats[1], defn=stats[2], spd=stats[3],
                         spa=stats[4], sdf=stats[5], types=list(types), growth=growth, gender=gender, tm=tm,
                         lvl=[list(x) for x in evos.get(key, {}).get("learn", [])], 
                         evolutions=evos.get(key, {}).get("evolutions", []))
                         
    return dict(moves=moves, chart=chart, mons=mons, tutor_moves=tutors, baby_eggs=baby_eggs())

def load():
    try:
        with open(OUT, encoding='utf-8') as f:
            result = json.load(f)
        if 'baby_eggs' not in result:
            result['baby_eggs'] = baby_eggs()
            write_json(OUT, result)
        return result
    except (OSError, ValueError):
        result=build()
        write_json(OUT,result)
        return result
