"""Round-robin tournament + rating + ranks + tiers + card data.

Rules implemented from the spec:
- every Pokemon plays every other Pokemon `games` times, alternating sides; 50-turn draws
- rank is ordered by win % where win % = wins / all games (draws and losses add nothing)
- Pokemon with exactly equal win totals share a tier (the better one, "move up")
- tiers are rank bands (Gen 1 bands below, scaled by field size for other generations)
- ELO is a Bradley-Terry rating (draws = half a win, small prior so sweeps stay finite); display only
"""
import argparse, csv, json, math, os, random, sys, time
from multiprocessing import Pool, TimeoutError as PoolTimeout
from simulation import SimulationTimeout, check_deadline, freeze

import gens
from config import validate
from storage import write_json
from move_rules import BATTLE_LEVEL
from forms import canonical_builds
G = E = P = brain = BRAIN_VERSION = None

def use_gen(n):
    """Select the generation whose engine, pools and brain this module uses."""
    global G, E, P, brain, BRAIN_VERSION
    G = gens.get(n)
    E, P, brain, BRAIN_VERSION = G.E, G.P, G.brain, G.BRAIN_VERSION



HERE = os.path.dirname(os.path.abspath(__file__))
TIER_STARTS_G1 = [("S", 1), ("A+", 2), ("A", 4), ("A-", 14), ("B+", 20), ("B", 39), ("B-", 61),
                  ("C", 75), ("C-", 87), ("D+", 100), ("D", 121), ("F", 138), ("Z", 147)]
_SPECS = None


def tier_starts(n):
    """Gen 1 bands expressed as fractions of the field, so other generations reuse them."""
    starts = []
    seen = set()
    for tier, start in TIER_STARTS_G1:
        scaled = 1 if start == 1 else round((start - 1) * n / 151) + 1
        if scaled <= n and scaled not in seen:
            starts.append((tier, scaled))
            seen.add(scaled)
    return starts


def tier_for_rank(rank, n):
    tier = "S"
    for t, s in tier_starts(n):
        if rank >= s:
            tier = t
    return tier


def _init(specs, gen=1, rules=None):
    global _SPECS
    use_gen(gen)
    if rules is not None:
        vars(E.RULES).update(rules)
    _SPECS = specs


def _row(args):
    i, seed, games, opponents, deadline = args
    n = len(_SPECS)
    out = {}
    for j in opponents:
        w = d = 0  # i's wins / draws vs j (j's wins = games - w - d)
        for g in range(games):
            check_deadline(deadline)
            rng = random.Random(seed * 10 ** 12 + (i * n + j) * 10 ** 3 + g)   # unique for up to 999 games
            if (g + i + j) % 2 == 0:       # who is the player (side A) alternates; the extra game alternates by pair
                r = E.Battle(_SPECS[i], _SPECS[j], rng, brain).run()
                w += r == 0
            else:
                r = E.Battle(_SPECS[j], _SPECS[i], rng, brain).run()
                w += r == 1
            d += r == 2
        out[j] = (w, d)
    return i, out


class PairCache:
    """In-memory results for one field/configuration; never persisted across runs."""
    def __init__(self):
        self.context = None
        self.entries = {}


def run_round_robin(specs, games=15, seed=0, procs=1, progress=True, on_row=None,
                    cache=None, stats=None, deadline=None):
    """Run exact seeded pairings, reusing unchanged pairs when a cache is supplied."""
    if G is None: use_gen(1)
    checked = validate(dict(games=games, procs=procs, seed=seed))
    games, procs, seed = (checked[k] for k in ('games', 'procs', 'seed'))
    check_deadline(deadline)
    n = len(specs)
    pairs_total = n * (n - 1) // 2
    W, Dr = [[0] * n for _ in range(n)], [[0] * n for _ in range(n)]
    identities = [freeze(sp) for sp in specs] if cache is not None else None
    if cache is not None:
        context = (G.id, E.ENGINE_VERSION, BRAIN_VERSION, id(E.Battle), id(brain),
                   freeze(vars(E.RULES)), id(E.D), n, games, seed)
        if cache.context != context:
            cache.context, cache.entries = context, {}
    if stats is not None:
        stats.update(battles=0, reused_battles=0)
    jobs, pairs_done, done = [], 0, 0
    for i in range(n - 1):
        pending, reused = [], {}
        for j in range(i + 1, n):
            old = cache.entries.get((i, j)) if cache is not None else None
            if old is not None and old[:2] == (identities[i], identities[j]):
                reused[j] = old[2]
            else:
                pending.append(j)
        _store(W, Dr, i, reused, games)
        pairs_done += len(reused)
        if stats is not None:
            stats['reused_battles'] += len(reused) * games
        if pending:
            jobs.append((i, seed, games, pending, deadline))
        else:
            done += 1
    t0 = time.monotonic()

    def store_result(result):
        nonlocal pairs_done, done
        i, out = result
        _store(W, Dr, i, out, games)
        if cache is not None:
            for j, result in out.items():
                cache.entries[i, j] = (identities[i], identities[j], result)
        if stats is not None:
            stats['battles'] += len(out) * games
        pairs_done += len(out)
        done += 1
        if on_row:
            on_row(done, n - 1, pairs_done, pairs_total)
        if progress and done % 10 == 0:
            print(f"  {done}/{n - 1} rows, {time.monotonic() - t0:.0f}s", file=sys.stderr)

    if jobs and procs > 1:
        with Pool(procs, initializer=_init, initargs=(specs, G.id, vars(E.RULES).copy())) as pl:
            results = pl.imap_unordered(_row, jobs)
            for _ in jobs:
                check_deadline(deadline)
                try:
                    result = results.next(timeout=None if deadline is None else max(0, deadline - time.monotonic()))
                except PoolTimeout:
                    raise SimulationTimeout('search time budget reached') from None
                store_result(result)
    elif jobs:
        _init(specs, G.id)
        for job in jobs:
            store_result(_row(job))
    elif on_row:
        on_row(done, n - 1, pairs_done, pairs_total)
    return W, Dr


def _store(W, Dr, i, out, games):
    for j, (w, d) in out.items():
        W[i][j], W[j][i] = w, games - w - d
        Dr[i][j] = Dr[j][i] = d


def bradley_terry(W, Dr, games, prior=1.0, iters=300):
    """MM algorithm. Draws count half a win to each side; `prior` virtual games per pair (half-win each)."""
    n = len(W)
    if n < 2: return [1500] * n # Safety catch
    p = [1.0] * n
    wi = [sum(W[i][j] + 0.5 * Dr[i][j] + prior / 2 for j in range(n) if j != i) for i in range(n)]
    ng = games + prior
    for _ in range(iters):
        new = []
        for i in range(n):
            # Added max(1e-9) to absolutely prevent ZeroDivisionError during underflows
            den = sum(ng / max(1e-9, p[i] + p[j]) for j in range(n) if j != i)
            new.append(wi[i] / den)
        g = math.exp(sum(math.log(max(1e-9, x)) for x in new) / n)
        p = [x / g for x in new]
    return [1500 + 400 * math.log10(max(1e-9, x)) for x in p]

def build_cards(keys, specs, W, Dr, games):
    n = len(keys)
    elo = bradley_terry(W, Dr, games)
    wins = [sum(W[i]) for i in range(n)]
    losses = [sum(W[j][i] for j in range(n)) for i in range(n)]
    draws = [sum(Dr[i]) for i in range(n)]
    order = sorted(range(n), key=lambda i: (-wins[i], -elo[i]))   # win % decides; ELO breaks exact ties
    rank = {i: r + 1 for r, i in enumerate(order)}
    best_in_tie = {}
    for i in order:
        best_in_tie.setdefault(wins[i], rank[i])                  
    top10 = order[:10]
    cards = []
    for i in order:
        opp = [j for j in top10 if j != i]
        t10 = sum(W[i][j] for j in opp) / (games * len(opp)) if opp else 0.0
        tot = wins[i] + losses[i] + draws[i]
        cards.append(dict(
            rank=rank[i], tier=tier_for_rank(best_in_tie[wins[i]], n), name=specs[i]["name"], key=keys[i],
            moves=specs[i].get("build", specs[i]["moves"]), # Pass the complete build to the UI
            required_item=specs[i].get("item"), form=E.D["mons"][keys[i]].get("form"),
            types=sorted(set(specs[i]["types"]), key=specs[i]["types"].index),
            elo=round(elo[i]), wins=wins[i], losses=losses[i], draws=draws[i],
            win_pct=round(100 * wins[i] / max(1, tot), 1), top10_win_pct=round(100 * t10, 1), level=specs[i]["lvl"]))
    return cards


def type_stats(cards, top_n=20):
    """Per type: how many of the top-N Pokemon carry it, and the average win % of all Pokemon with it.
    Dual-typed Pokemon count once for each of their types."""
    top, wins = {}, {}
    for c in cards:
        for t in c["types"]:
            t = t.replace("_TYPE", "")
            wins.setdefault(t, []).append(c["win_pct"])
            if c["rank"] <= top_n:
                top[t] = top.get(t, 0) + 1
    rows = [dict(type=t, pokemon=len(v), top_n=top.get(t, 0), avg_win_pct=round(sum(v) / len(v), 1))
            for t, v in wins.items()]
    rows.sort(key=lambda r: (-r["top_n"], -r["avg_win_pct"]))
    return rows


def load_movesets(path, keys, gen=None):
    if G is None: use_gen(1 if gen is None else gen)
    P = gens.get(gen).P if gen else globals()["P"]
    ms = {}
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f: ms=json.load(f)
        if not isinstance(ms,dict): raise ValueError('movesets JSON must be an object')
    generation = gen if gen is not None else G.id
    engine = gens.get(generation).E
    ms = canonical_builds(ms, engine.D["mons"])
    result={k:ms.get(k) or P.default_moves(k) for k in keys}
    for key, build in result.items():
        spec = engine.make_spec(key, build)
        if generation >= 3: result[key] = spec['build']
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--gen", type=int, default=1, help="generation (1, 2, 3 or 4)")
    ap.add_argument("--moves", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0, help="only the first N Pokemon (quick tests)")
    
    a = ap.parse_args()
    use_gen(a.gen)
    a.out = a.out or os.path.join(HERE, "out", f"gen{G.id}")
    a.moves = a.moves or os.path.join(a.out, "movesets.json")
    
    keys = list(E.D["mons"])
    if a.limit:
        keys = keys[:a.limit]
    try: validate(vars(a))
    except ValueError as ex: ap.error(str(ex))
    ms = load_movesets(a.moves, keys)
    specs = [E.make_spec(k, ms[k]) for k in keys]
    t = time.time()
    W, Dr = run_round_robin(specs, a.games, a.seed, a.procs)
    cards = build_cards(keys, specs, W, Dr, a.games)
    os.makedirs(a.out, exist_ok=True)
    meta = dict(generation=G.id, brain_version=BRAIN_VERSION, engine_version=E.ENGINE_VERSION, games_per_pair=a.games, seed=a.seed,
                rules=dict(both_faint_draw=E.RULES.both_faint_draw, badge_glitch=E.RULES.badge_glitch,
                           turn_limit=E.RULES.turn_limit, statexp=E.RULES.statexp,
                           battle_level=BATTLE_LEVEL, learn_level_cap=None), seconds=round(time.time() - t, 1))
    from exports import write_results
    write_results(cards,meta,a.out)
    print(f"done in {meta['seconds']}s")
    for c in cards[:12] + cards[-6:]:
        print(f'{c["rank"]:>3} {c["tier"]:<2} {c["name"]:<11} elo {c["elo"]:>5} {c["wins"]}-{c["losses"]}-{c["draws"]} ({c["win_pct"]}%) {c["moves"]}')


if __name__ == "__main__":
    main()