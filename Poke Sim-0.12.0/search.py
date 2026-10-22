"""Automatic moveset search: iterated best response against the field, scored by WINS only
(the same metric that decides rank). No manual sets.
"""
import argparse, hashlib, json, math, os, random, sys, time
from multiprocessing import Pool, TimeoutError as PoolTimeout
from simulation import SimulationTimeout, check_deadline, battle_signature, freeze
import gens
from config import validate
from storage import write_json
import tournament as T
G = E = P = brain = BRAIN_VERSION = None

def use_gen(n):
    global G, E, P, brain, BRAIN_VERSION
    T.use_gen(n)
    G = gens.get(n)
    E, P, brain, BRAIN_VERSION = G.E, G.P, G.brain, G.BRAIN_VERSION


def _init_gen(gen, rules=None):
    use_gen(gen)
    if rules is not None:
        vars(E.RULES).update(rules)

HERE = os.path.dirname(os.path.abspath(__file__))

def evaluate(spec, opps, games, seed_base, deadline=None, cutoff=None):
    w = played = 0
    total = len(opps)*games
    for oi, o in enumerate(opps):
        for g in range(games):
            check_deadline(deadline)
            rng = random.Random((seed_base * 1000003 + oi) * 1000 + g)
            if (g + oi) % 2 == 0:
                w += E.Battle(spec, o, rng, brain).run() == 0
            else:
                w += E.Battle(o, spec, rng, brain).run() == 1
            played += 1
            if cutoff is not None and w + total - played <= cutoff:
                return -1, played
    return (w, played) if cutoff is not None else w

def _eval_chunk(args):
    specs, opps, games, seed, deadline = args
    return [evaluate(spec, opps, games, seed, deadline) for spec in specs]

def _race_chunk(args):
    specs, opps, games, seed, deadline, cutoff = args
    return [evaluate(spec, opps, games, seed, deadline, cutoff) for spec in specs]


def distinct_candidates(key, current, candidates):
    seen = {battle_signature(E.make_spec(key,current), getattr(E,'NATURES',None))}
    result = []
    for candidate in candidates:
        signature = battle_signature(E.make_spec(key,candidate), getattr(E,'NATURES',None))
        if signature not in seen:
            seen.add(signature)
            result.append(candidate)
    return result


class Scorer:
    def __init__(self, procs, deadline=None):
        self.procs = max(1, procs)
        self.pool = None
        self.battles = 0
        self.deadline = deadline
        self.context = None

    def close(self):
        if self.pool is not None:
            self.pool.terminate()
            self.pool.join()
            self.pool = None

    def score(self, key, cands, opps, games, seed):
        check_deadline(self.deadline)
        if G is None: use_gen(1)
        context = (G.id, freeze(vars(E.RULES)), id(E.D), E.ENGINE_VERSION, BRAIN_VERSION)
        if context != self.context:
            self.close()
            self.context = context
        unique, positions, seen = [], [], {}
        for candidate in cands:
            spec = E.make_spec(key, candidate)
            signature = battle_signature(spec, getattr(E, 'NATURES', None))
            if signature not in seen:
                seen[signature] = len(unique)
                unique.append(spec)
            positions.append(seen[signature])
        if not unique:
            return []
        if self.procs == 1 or len(unique) < 4:
            scores = _eval_chunk((unique, opps, games, seed, self.deadline))
        else:
            if self.pool is None:
                self.pool = Pool(self.procs, initializer=_init_gen, initargs=(G.id, vars(E.RULES).copy()))
            size = max(1, math.ceil(len(unique) / (self.procs * 4)))
            jobs = [(unique[i:i + size], opps, games, seed, self.deadline)
                    for i in range(0, len(unique), size)]
            scores = []
            results = self.pool.imap(_eval_chunk, jobs)
            for _ in jobs:
                check_deadline(self.deadline)
                try:
                    part = results.next(timeout=None if self.deadline is None else max(0, self.deadline - time.monotonic()))
                except PoolTimeout:
                    raise SimulationTimeout('search time budget reached') from None
                scores.extend(part)
        self.battles += len(unique) * len(opps) * games
        return [scores[i] for i in positions]

    def finalists(self, key, current, candidates, opps, games, seed, count=4):
        """Exact top-k screening: abandon only candidates unable to beat kth.

        Stable ties favor earlier candidates, exactly as exhaustive sorted scoring.
        The incumbent is always fully evaluated and is not a finalist slot.
        """
        candidates = distinct_candidates(key, current, candidates)
        first = candidates[:count]
        scores = self.score(key, [current]+first, opps, games, seed)
        best = sorted(zip(scores[1:], range(len(first)), first), key=lambda x:(-x[0],x[1]))
        width = max(1,self.procs*4)
        for start in range(count,len(candidates),width):
            check_deadline(self.deadline)
            batch = candidates[start:start+width]
            cutoff = best[-1][0]
            specs = [E.make_spec(key,c) for c in batch]
            jobs = [([spec],opps,games,seed,self.deadline,cutoff) for spec in specs]
            if self.pool is None:
                results = map(_race_chunk,jobs)
            else:
                pending = self.pool.imap(_race_chunk,jobs)
                def collect():
                    for _ in jobs:
                        try:
                            yield pending.next(timeout=None if self.deadline is None else max(0,self.deadline-time.monotonic()))
                        except PoolTimeout:
                            raise SimulationTimeout('search time budget reached') from None
                results = collect()
            for index, result in enumerate(results,start):
                wins, played = result[0]
                self.battles += played
                if wins >= 0:
                    best.append((wins,index,candidates[index]))
            best = sorted(best,key=lambda x:(-x[0],x[1]))[:count]
        return scores[0], [(wins,candidate) for wins,_,candidate in best]


def quick_order(keys, ms, games=3, procs=1, cache=None, stats=None, deadline=None):
    specs = [E.make_spec(k, ms[k]) for k in keys]
    W, _ = T.run_round_robin(specs, games, seed=99, procs=procs, progress=False,
                           cache=cache, stats=stats, deadline=deadline)
    wins = [sum(r) for r in W]
    return sorted(range(len(keys)), key=lambda i: -wins[i])


def select_opponents(keys, key, sample, rng=None):
    """Uniform inclusion probability matches the equally weighted field objective."""
    others = [x for x in keys if x != key]
    return (rng or random.Random(0)).sample(others,min(sample,len(others)))


def _print_event(type_, **f):
    def fmt_b(b):
        """Safely format Gen 1/2 arrays OR Gen 3 dictionaries for the terminal log."""
        if isinstance(b, list): return " ".join(b)
        if isinstance(b, dict): return f"{' '.join(b.get('moves', []))} | {b.get('ability', '')} | {b.get('nature', '')}"
        return str(b)
        
    if type_ == "pass_start":
        print(f"-- pass {f['pass_no']}/{f['passes']}: evaluating the field...", flush=True)
    elif type_ == "mon_result":
        tag = "CHANGED" if f["accepted"] else "kept   "
        extra = (f"{fmt_b(f['old'])} -> {fmt_b(f['new'])}  ({f['base_wins']}->{f['best_wins']}/{f['total']})"
                 if f["accepted"] else f"({f['base_wins']}/{f['total']}, best alt {f['best_wins']})" if f["best_tried"] else "")
        print(f"[pass {f['pass_no']} {f['n']:>3}/{f['of']}] {tag} {f['key']}: {extra}", flush=True)
    elif type_ == "pass_done":
        print(f"pass {f['pass_no']}: {f['changed']} of {f['of']} sets changed", flush=True)
    elif type_ == "time_budget":
        print("time budget reached", flush=True)

def run(path, passes, sample, screen_games, confirm_games, margin_pct, minutes, only, procs=1, emit=None, field_keys=None, seed=None, fresh=False):
    if G is None: use_gen(1)
    checked=validate(dict(passes=passes,sample=sample,screen_games=screen_games,confirm_games=confirm_games,margin=margin_pct,minutes=minutes,procs=procs,seed=seed))
    passes,sample,screen_games,confirm_games,margin_pct,minutes,procs=(checked[k] for k in ('passes','sample','screen_games','confirm_games','margin','minutes','procs'))
    seed = checked.get('seed')
    if emit is None:
        def emit(type_, **f): _print_event(type_, **f)
    keys = list(E.D["mons"]) if field_keys is None else list(field_keys)
    if len(keys)<2 or any(k not in E.D["mons"] for k in keys): raise ValueError("search requires at least two valid species")
    ms = T.load_movesets(path, keys)
    # Keep builds outside a limited search field.
    try:
        with open(path,encoding='utf-8') as f: saved = json.load(f)
        ms = {**T.canonical_builds(saved, E.D["mons"]), **ms}
    except FileNotFoundError:
        pass
    state_path = path + '.search.json'
    def digest(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    context = digest([G.id,E.ENGINE_VERSION,BRAIN_VERSION,E.D,vars(E.RULES),keys,
                      sorted(only),sample,screen_games,confirm_games,margin_pct])
    try:
        with open(state_path,encoding='utf-8') as f: state=json.load(f)
    except (FileNotFoundError,ValueError):state={}
    if (fresh or state.get('context')!=context or state.get('builds')!=digest(ms)
            or seed is not None and state.get('seed')!=seed):state={}
    seed = state.get('seed',seed if seed is not None else random.SystemRandom().randrange(2**63))
    next_pass = state.get('next_pass',1)
    stable = state.get('stable',0)
    def checkpoint():
        write_json(state_path,dict(context=context,builds=digest(ms),seed=seed,
                                  next_pass=next_pass,stable=stable))
    specs = {k: E.make_spec(k, ms[k]) for k in keys}
    pools = {k: P.pool(k) for k in keys}
    names = {k: E.D["mons"][k]["name"] for k in keys}
    t0 = time.monotonic()
    deadline = t0 + minutes * 60 if minutes else None
    ranking_battles = 0
    ranking_stats = dict(reused_battles=0)
    sc = Scorer(procs, deadline)
    converged = False
    try:
        for ps in range(1, passes + 1):
            emit("pass_start", pass_no=ps, passes=passes)
            evidence_pass = next_pass
            next_pass += 1  # Reserve before work so interruption cannot replay its evidence.
            previous_stable = stable
            stable = 0
            checkpoint()
            rng = random.Random(seed * 1000003 + evidence_pass)
            todo = [k for k in keys if (G.id >= 3 or k != "ditto") and (not only or k in only)]
            rng.shuffle(todo)
            changed = 0
            for n, k in enumerate(todo, 1):
                check_deadline(deadline)
                opp_keys = select_opponents(keys, k, sample, rng)
                opps = [specs[x] for x in opp_keys]
                
                cur = ms[k]
                if isinstance(cur, list): cur = list(cur)
                elif isinstance(cur, dict): cur = json.loads(json.dumps(cur)) 
                
                if hasattr(P, "neighbours"): nb = P.neighbours(k, cur, pools[k])
                else: 
                    # Legacy fallback
                    seen, nb = {frozenset(cur)}, []
                    for s in range(len(cur) + (len(cur) < 4)):
                        for m in pools[k]:
                            if m in cur: continue
                            new = cur[:s] + [m] + cur[s + 1:]
                            f = frozenset(new)
                            if f not in seen:
                                seen.add(f); nb.append(new)
                                
                emit("mon_start", key=k, name=names[k], pass_no=ps, n=n, of=len(todo), moves=cur,
                     candidates=len(nb) + 1, opponents=len(opps))
                battle_seed = (seed * 1000003 + evidence_pass) * 1000000 + n
                nb = distinct_candidates(k,cur,nb)
                if not nb:
                    emit("mon_result",key=k,name=names[k],pass_no=ps,n=n,of=len(todo),
                         old=cur,new=cur,accepted=False,base_wins=0,best_wins=0,best_tried=False,
                         total=0,needed=0,changed_so_far=changed,battles=sc.battles,
                         ranking_battles=0,reused_ranking_battles=0,
                         elapsed=round(time.monotonic()-t0,1),confirm=[])
                    continue
                sbase, scored = sc.finalists(k,cur,nb,opps,screen_games,battle_seed)
                top = [c for _,c in scored]
                emit("screen",base_wins=sbase,total=len(opps)*screen_games,
                     top=[dict(moves=c,wins=w) for w,c in scored])
                # Independent opponent sample and random stream for confirmation.
                confirm_keys = select_opponents(keys,k,sample,rng)
                confirm_opps = [specs[x] for x in confirm_keys]
                cres = sc.score(k,[cur]+top,confirm_opps,confirm_games,-battle_seed-1)
                cbase, cw = cres[0], cres[1:]
                best, bw = None, cbase
                for cand, w in zip(top, cw):
                    if w > bw:
                        best, bw = cand, w
                total = len(opps) * confirm_games
                needed = math.ceil(margin_pct / 100 * total - 1e-9)
                accepted = bool(best and bw - cbase >= needed)
                
                if accepted:
                    ms[k] = best
                    specs[k] = E.make_spec(k, best)
                    changed += 1
                    save(path, ms)
                    checkpoint()
                    
                emit("mon_result", key=k, name=names[k], pass_no=ps, n=n, of=len(todo), old=cur, new=ms[k],
                     accepted=accepted, base_wins=cbase, best_wins=max(cw) if cw else cbase, best_tried=bool(cw),
                     total=total, needed=needed, changed_so_far=changed, battles=sc.battles + ranking_battles,
                     ranking_battles=ranking_battles, reused_ranking_battles=ranking_stats["reused_battles"],
                     elapsed=round(time.monotonic() - t0, 1), confirm=[dict(moves=c, wins=w) for c, w in zip(top, cw)])
            save(path, ms)
            emit("pass_done", pass_no=ps, changed=changed, of=len(todo))
            stable = previous_stable + 1 if changed == 0 else 0
            checkpoint()
            if stable >= 2:
                converged = True
                break
    except SimulationTimeout:
        save(path, ms)
        checkpoint()
        emit("time_budget")
        return False
    finally:
        sc.close()
    return converged

def save(path, ms):
    write_json(path, dict(ms), indent=0)
    write_json(os.path.join(os.path.dirname(path) or '.', 'movesets_meta.json'),
               dict(brain_version=BRAIN_VERSION, engine_version=E.ENGINE_VERSION, generation=G.id,
                    note='heuristic search; evaluate on independent tournament seeds'))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--gen", type=int, default=1)
    ap.add_argument("--moves", default=None)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--sample", type=int, default=32)
    ap.add_argument("--screen-games", type=int, default=3)
    ap.add_argument("--confirm-games", type=int, default=10)
    ap.add_argument("--margin", type=float, default=2.0)
    ap.add_argument("--minutes", type=float, default=0)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--only", nargs="*", default=[])
    a = ap.parse_args()
    use_gen(a.gen)
    a.moves = a.moves or os.path.join(HERE, "out", f"gen{G.id}", "movesets.json")
    run(a.moves, a.passes, a.sample, a.screen_games, a.confirm_games, a.margin, a.minutes, set(a.only), procs=a.procs, seed=a.seed)