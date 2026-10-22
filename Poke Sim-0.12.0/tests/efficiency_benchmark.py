"""Reproducible controlled speed and bounded search-quality measurements.

python3 tests/efficiency_benchmark.py --baseline /path/to/pre-change/source --output report.json
All timings are local, serial, and exclude process startup/imports.
"""
import argparse
import hashlib
import itertools
import json
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


def worker(root,kind):
    sys.path[:0]=[str(root),str(root/'tests')]
    from fixtures import generation,build
    if kind=='battles':
        result=[]
        for gen in range(1,5):
            g=generation(gen);a=g.E.make_spec('a',build(gen));b=g.E.make_spec('b',build(gen))
            start=time.perf_counter();out=[]
            for seed in range(1000):
                bt=g.E.Battle(a,b,random.Random(seed),g.brain)
                out.append((bt.run(),bt.a.hp,bt.b.hp,bt.turn))
            result.append(dict(generation=gen,seconds=time.perf_counter()-start,
                               outcome_sha256=hashlib.sha256(repr(out).encode()).hexdigest()))
        return result
    if kind=='quality':
        import gens
        import search as S
        S.use_gen(1);g=gens.get(1)
        keys=['venusaur','charizard','blastoise','pikachu','alakazam','machamp','gengar','golem','lapras','snorlax','dragonite','mewtwo']
        initial={k:g.P.default_moves(k) for k in keys}
        runs=[]
        for seed in (7,19,31):
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'movesets.json';path.write_text(json.dumps(initial));events=[]
                options=dict(procs=1,emit=lambda kind,**f:events.append((kind,f)),field_keys=keys)
                if 'seed' in __import__('inspect').signature(S.run).parameters:options['seed']=seed
                start=time.perf_counter()
                converged=S.run(str(path),2,8,2,6,1.5,0,set(),**options)
                elapsed=time.perf_counter()-start
                final=json.loads(path.read_text())
                results=[f for kind,f in events if kind=='mon_result']
                runs.append(dict(seed=seed,seconds=elapsed,converged=converged,builds=final,
                                 battles=results[-1]['battles'],changed=sum(final[k]!=initial[k] for k in keys)))
        return dict(keys=keys,initial=initial,runs=runs)
    raise ValueError(kind)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--worker',choices=['battles','quality']);parser.add_argument('--root',type=Path)
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.root,args.worker)));return
    root=Path(__file__).resolve().parents[1]
    def run(where,kind):
        result=subprocess.run([sys.executable,__file__,'--worker',kind,'--root',str(where)],capture_output=True,text=True,check=True)
        return json.loads(result.stdout)
    timing={'before':[],'after':[]}
    for repetition in range(3):
        for label in (('before','after') if repetition%2==0 else ('after','before')):
            timing[label].append(run(args.baseline if label=='before' else root,'battles'))
        print('Completed battle timing pair',repetition+1,flush=True)
    battle_summary=[]
    for gen in range(1,5):
        old=[x[gen-1] for x in timing['before']];new=[x[gen-1] for x in timing['after']]
        assert len({x['outcome_sha256'] for x in old+new})==1,gen
        before=statistics.median(x['seconds'] for x in old);after=statistics.median(x['seconds'] for x in new)
        battle_summary.append(dict(generation=gen,battles=1000,outcomes_equal=True,before_seconds=before,after_seconds=after,
                                   speedup=before/after,runtime_reduction_percent=100*(1-after/before)))
    sys.path[:0]=[str(root),str(root/'tests')]
    from fixtures import generation,build
    import search as S
    race_summary=[]
    with patch('gens.get',side_effect=generation):
        for gen in range(1,5):
            S.use_gen(gen);g=generation(gen);cur=build(gen)
            cands=[build(gen,[a,b]) for a,b in itertools.permutations(['TACKLE','BODY_SLAM','THUNDERBOLT','RECOVER','SPLASH','SELFDESTRUCT'],2)]
            cands=S.distinct_candidates('a',cur,cands)
            opps=[g.E.make_spec(k,build(gen)) for k in ('b','c','d')]
            times={False:[],True:[]};counts={}
            for rep in range(3):
                for race in ((False,True) if rep%2==0 else (True,False)):
                    sc=S.Scorer(1);start=time.perf_counter()
                    if race:base,top=sc.finalists('a',cur,cands,opps,10,7)
                    else:
                        values=sc.score('a',[cur]+cands,opps,10,7)
                        expected=(values[0],sorted(zip(values[1:],cands),key=lambda p:-p[0])[:4])
                    times[race].append(time.perf_counter()-start);counts[race]=sc.battles
                assert (base,top)==expected
            before=statistics.median(times[False]);after=statistics.median(times[True])
            race_summary.append(dict(generation=gen,candidates=len(cands),opponents=len(opps),games=10,identical_finalists=True,
                                     exhaustive_seconds=before,race_seconds=after,speedup=before/after,
                                     exhaustive_battles=counts[False],race_battles=counts[True]))
            print('Completed exact screening benchmark',gen,flush=True)
    # Both versions are scored by the current corrected engine on independent seeds.
    quality={'before':run(args.baseline,'quality'),'after':run(root,'quality')}
    S.use_gen(1);g=S.G;keys=quality['after']['keys'];initial=quality['after']['initial']
    scores=[]
    for label,runs in [('defaults',[dict(builds=initial,seed=None)]),('before',quality['before']['runs']),('after',quality['after']['runs'])]:
        for result in runs:
            wins=total=0;per_species={}
            for key in keys:
                spec=g.E.make_spec(key,result['builds'][key])
                opps=[g.E.make_spec(k,initial[k]) for k in keys if k!=key]
                w=sum(S.evaluate(spec,opps,30,seed) for seed in (901,902,903))
                n=len(opps)*30*3;wins+=w;total+=n;per_species[key]=w/n
            scores.append(dict(version=label,search_seed=result['seed'],wins=wins,battles=total,win_rate=wins/total,per_species=per_species))
    report=dict(scope='Synthetic battle/screening timings; real Gen 1 bounded 12-species search. Single process. No real Gen 4 convergence forecast.',
                baseline=str(args.baseline),battle_raw=timing,battle_summary=battle_summary,race_summary=race_summary,
                quality=quality,independent_validation=scores,
                limitations=['Old search ignores caller seed and repeats the same trajectory.',
                             'Two search passes; not a global optimum or convergence proof.',
                             'Holdout opponents are fixed default builds, not an independent full metagame.'])
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(battles=battle_summary,racing=race_summary,quality=[{k:v for k,v in x.items() if k!='per_species'} for x in scores]),indent=2))


if __name__=='__main__':main()
