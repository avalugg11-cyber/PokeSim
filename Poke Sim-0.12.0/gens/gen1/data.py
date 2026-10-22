"""Gen 1 data loader. Pulls canonical data from the pret/pokered (Red/Blue) and pret/pokeyellow (Yellow)
disassemblies, merges them (Red/Blue/Yellow all count, as in the source video), and caches the result to
data/gen1.json (offline after the first run)."""
import json, os, re, urllib.request
from storage import write_json

BASE = "https://raw.githubusercontent.com/pret/pokered/af519899719f0754965776faac0e836a3b906e6d/"
YBASE = "https://raw.githubusercontent.com/pret/pokeyellow/8ea8bcaee5e2e0fec1ba5c2e3a46d9fba6cb02ad/"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW, RAW_Y = os.path.join(HERE, "raw"), os.path.join(HERE, "raw_y")
OUT = os.path.join(HERE, "data", "gen1.json")


def fetch(path, yellow=False):
    cache = RAW_Y if yellow else RAW
    local = os.path.join(cache, path.replace("/", "_"))
    if not os.path.exists(local) or os.path.getsize(local) == 0:
        os.makedirs(cache, exist_ok=True)
        with urllib.request.urlopen((YBASE if yellow else BASE) + path, timeout=30) as r:
            open(local, "wb").write(r.read())
    return open(local, encoding="utf-8").read()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_evos(text):
    """label -> dict(evolutions, learn). Works for both disassemblies (evolutions end at 'db 0', then the learnset)."""
    out = {}
    blocks = re.split(r"^(\w+)EvosMoves:\s*$", text, flags=re.M)
    for i in range(1, len(blocks), 2):
        lines = [re.sub(r";.*", "", l).strip() for l in blocks[i + 1].splitlines()]
        lines = [re.sub(r"\s+", " ", l) for l in lines if l.strip()]
        k, evolutions, learn = 0, [], []
        while k < len(lines) and lines[k] != "db 0":
            m = re.match(r"db EVOLVE_LEVEL, (\d+), (\w+)", lines[k])
            if m:
                evolutions.append(("level", int(m.group(1)), m.group(2)))
            m = re.match(r"db EVOLVE_ITEM, \w+, \d+, (\w+)", lines[k])
            if m:
                evolutions.append(("item", 0, m.group(1)))
            m = re.match(r"db EVOLVE_TRADE, \d+, (\w+)", lines[k])
            if m:
                evolutions.append(("trade", 0, m.group(1)))
            k += 1
        k += 1
        while k < len(lines) and lines[k] != "db 0":
            m = re.match(r"db (\d+), (\w+)", lines[k])
            if m:
                learn.append((int(m.group(1)), m.group(2)))
            k += 1
        out[norm(blocks[i])] = dict(evolutions=evolutions, learn=learn)
    return out


def parse_base(t):
    stats = [int(x) for x in re.search(r"db\s+(\d+),\s+(\d+),\s+(\d+),\s+(\d+),\s+(\d+)\n\s*;\s*hp", t).groups()]
    types = re.search(r"db (\w+), (\w+) ; type", t).groups()
    start = [x for x in re.search(r"db (\w+), (\w+), (\w+), (\w+) ; level 1 learnset", t).groups() if x != "NO_MOVE"]
    growth = re.search(r"db (GROWTH_\w+)", t).group(1)
    tm = re.search(r"\btmhm\b(.*?);\s*end", t, re.S).group(1)
    return dict(stats=stats, types=list(types), start=start, growth=growth,
                tm=re.findall(r"[A-Z_0-9]+", tm.replace("\\", " ")))


def index_of(yellow):
    idx = re.findall(r"base_stats/(\w+)\.asm", fetch("data/pokemon/base_stats.asm", yellow))
    if "mew" not in idx:
        idx.append("mew")   # Mew is not in the base_stats.asm index
    return idx


def build():
    moves = {}
    for m in re.finditer(r"^\s*move\s+(\w+),\s*(\w+),\s*(\d+),\s*(\w+),\s*(\d+),\s*(\d+)",
                         fetch("data/moves/moves.asm"), re.M):
        name, eff, power, typ, acc, pp = m.groups()
        moves[name] = dict(effect=eff, power=int(power), type=typ, acc=int(acc), pp=int(pp))
    chart = []
    for m in re.finditer(r"^\s*db\s+(\w+),\s+(\w+),\s+(NO_EFFECT|NOT_VERY_EFFECTIVE|SUPER_EFFECTIVE)",
                         fetch("data/types/type_matchups.asm"), re.M):
        a, d, e = m.groups()
        chart.append([a, d, {"NO_EFFECT": 0, "NOT_VERY_EFFECTIVE": 5, "SUPER_EFFECTIVE": 20}[e]])

    evos, yevos = parse_evos(fetch("data/pokemon/evos_moves.asm")), parse_evos(fetch("data/pokemon/evos_moves.asm", True))
    mons, stat_diffs = {}, []
    for dex, fname in enumerate(index_of(False), 1):
        key = norm(fname)
        b = parse_base(fetch(f"data/pokemon/base_stats/{fname}.asm"))
        yb = parse_base(fetch(f"data/pokemon/base_stats/{fname}.asm", True))
        if yb["stats"] != b["stats"] or yb["types"] != b["types"]:
            stat_diffs.append(key)
        lvl = {tuple(x) for x in evos[key]["learn"]}
        ylvl = {tuple(x) for x in yevos[key]["learn"]}
        start = list(dict.fromkeys(b["start"] + [m for m in yb["start"] if m not in b["start"]]))
        tm = list(dict.fromkeys(b["tm"] + [m for m in yb["tm"] if m not in b["tm"]]))
        yellow_only = sorted({m for _, m in ylvl - lvl} | {m for m in yb["start"] if m not in b["start"]}
                             | {m for m in yb["tm"] if m not in b["tm"]})
        mons[key] = dict(dex=dex, name=fname.upper(), hp=b["stats"][0], atk=b["stats"][1], defn=b["stats"][2],
                         spd=b["stats"][3], spc=b["stats"][4], types=b["types"], start=start, growth=b["growth"],
                         tm=tm, lvl=[list(x) for x in sorted(lvl | ylvl)], evolutions=evos[key]["evolutions"],
                         yellow_only=yellow_only)
    return dict(moves=moves, chart=chart, mons=mons, yellow_stat_diffs=stat_diffs)


def load():
    try:
        with open(OUT, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        result=build()
        write_json(OUT,result)
        return result


if __name__ == "__main__":
    d = load()
    print(len(d["moves"]), "moves", len(d["mons"]), "mons", len(d["chart"]), "type rules")
    print("mons with Yellow-only moves:", sum(1 for m in d["mons"].values() if m["yellow_only"]),
          "| Yellow base stat/type differences:", d["yellow_stat_diffs"])
