"""Full local pipeline: seed movesets -> converge (search) -> tournament battles -> results."""
import argparse, csv, json, os, shutil, sys, time
import gens
import uuid
from config import validate
from storage import write_json
from move_rules import BATTLE_LEVEL
import search as S
import tournament as T

E = P = BRAIN_VERSION = None

def use_gen(n):
    global E, P, BRAIN_VERSION
    S.use_gen(n)
    E, P, BRAIN_VERSION = S.E, S.P, S.BRAIN_VERSION


HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = {
    "quick":    dict(passes=1, sample=8,  screen_games=2, confirm_games=6,  games=5),
    "standard": dict(passes=3, sample=32, screen_games=3, confirm_games=16, games=15),
    "thorough": dict(passes=5, sample=48, screen_games=4, confirm_games=20, games=25),
}

_t0 = time.time()

def emit(type_, **fields):
    rec = dict(type=type_, t=round(time.time() - _t0, 2), **fields)
    os.makedirs(RUN, exist_ok=True)
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    S._print_event(type_, **fields)
    if type_ in ("stage", "run_start", "done", "converged"):
        print(f"== {type_}: " + ", ".join(f"{k}={v}" for k, v in fields.items()
                                           if k in ("name", "label", "converged", "seconds", "preset")), flush=True)

from exports import write_results

def main():
    global OUT, RUN, EVENTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", type=int, default=1, help="generation")
    ap.add_argument("--out", default=None, help="output directory (default: out/genN)")
    ap.add_argument("--preset", choices=list(PRESETS), default="standard")
    for k in ("passes", "sample", "screen_games", "confirm_games", "games"):
        ap.add_argument("--" + k.replace("_", "-"), type=int, default=None)
    # Lowered default margin to 1.5% to allow EV/Nature optimizations to be accepted!
    ap.add_argument("--margin", type=float, default=1.5)
    ap.add_argument("--minutes", type=float, default=0, help="search time budget, 0 = none")
    ap.add_argument("--seed", type=int, default=None, help="search and tournament seed (default: resume search seed, random tournament seed)")
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--fresh", action="store_true", help="discard movesets, restart from heuristic seeds")
    ap.add_argument("--skip-search", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="restrict to first N species for a quick check")
    ap.add_argument("--run-id", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    try: validate(vars(a))
    except ValueError as ex: ap.error(str(ex))
    
    if a.skip_search:
        a.fresh = False
    use_gen(a.gen)
    OUT = a.out or os.path.join(HERE, "out", f"gen{a.gen}")
    RUN = os.path.join(OUT, "run")
    EVENTS = os.path.join(RUN, "events.jsonl")
    
    cfg = dict(PRESETS[a.preset])
    for k in cfg:
        if getattr(a, k) is not None:
            cfg[k] = getattr(a, k)
    seed = a.seed if a.seed is not None else int(time.time()) % 100000

    os.makedirs(RUN,exist_ok=True)
    write_json(os.path.join(RUN,"identity.json"),dict(run_id=a.run_id or uuid.uuid4().hex))
    if os.path.exists(EVENTS):
        os.remove(EVENTS)
    path = os.path.join(OUT, "movesets.json")
    keys = list(E.D["mons"])
    if a.limit:
        if a.limit<2: ap.error("limit must be at least two")
        keys=keys[:a.limit]
    emit("run_start", gen=a.gen, preset=a.preset, config=cfg, margin=a.margin, minutes=a.minutes, seed=seed, procs=a.procs,
         fresh=a.fresh, skip_search=a.skip_search, brain_version=BRAIN_VERSION, engine_version=E.ENGINE_VERSION, mons=len(keys))

    emit("stage", name="seed", label="Seed movesets")
    if a.fresh or not os.path.exists(path):
        if os.path.exists(path):
            shutil.copy(path, os.path.join(OUT, "movesets.prev.json"))
        ms = {k: P.default_moves(k) for k in keys}
        S.save(path, ms)
    else:
        ms = T.load_movesets(path, keys, a.gen)
    names = {k: E.D["mons"][k]["name"] for k in keys}
    emit("seed", movesets=ms, names=names, types={k: E.D["mons"][k]["types"] for k in keys},
         pool_sizes={k: len(P.pool(k)) for k in keys})

    converged = None
    if not a.skip_search:
        emit("stage", name="converge", label="Moveset convergence")
        converged = S.run(path, cfg["passes"], cfg["sample"], cfg["screen_games"], cfg["confirm_games"], a.margin,
                          a.minutes, set(), procs=a.procs, emit=emit, field_keys=keys, seed=a.seed, fresh=a.fresh)
        emit("converged", converged=bool(converged))
        final = T.load_movesets(path, keys, a.gen)
        emit("final_sets", movesets=final, seed_movesets=ms)
    else:
        final = ms

    emit("stage", name="tournament", label="Round-robin battles")
    specs = [E.make_spec(k, final[k]) for k in keys]
    n = len(keys)
    total_battles = n * (n - 1) // 2 * cfg["games"]
    tt = time.time()
    last = [0.0]

    def on_row(done, rows, pairs_done, pairs_total):
        now = time.time()
        if now - last[0] > 0.4 or done == rows:
            last[0] = now
            emit("battle_progress", rows_done=done, rows=rows, battles_done=pairs_done * cfg["games"],
                 battles=total_battles, elapsed=round(now - tt, 1))

    W, Dr = T.run_round_robin(specs, cfg["games"], seed, a.procs, progress=False, on_row=on_row)

    emit("stage", name="results", label="Ratings and ranks")
    cards = T.build_cards(keys, specs, W, Dr, cfg["games"])
    secs = round(time.time() - tt, 1)
    meta = dict(generation=a.gen, brain_version=BRAIN_VERSION, engine_version=E.ENGINE_VERSION, games_per_pair=cfg["games"], seed=seed,
                rules=dict(both_faint_draw=E.RULES.both_faint_draw, badge_glitch=E.RULES.badge_glitch,
                           turn_limit=E.RULES.turn_limit, statexp=E.RULES.statexp,
                           battle_level=BATTLE_LEVEL, learn_level_cap=None), seconds=secs)
    write_results(cards, meta, OUT)
    emit("results", meta=meta, cards=cards, type_stats=T.type_stats(cards))
    emit("done", seconds=round(time.time() - _t0, 1))

if __name__ == "__main__":
    main()