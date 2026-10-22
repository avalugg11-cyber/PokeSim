"""Bounded synthetic benchmark of estimate reuse; no real-roster forecast.

Run: python3 tests/benchmark.py --battles 1000
"""
import argparse
import json
import random
import statistics
import sys
import time
import types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fixtures import generation, build


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--battles',type=int,default=1000)
    args=parser.parse_args()
    if args.battles<1:parser.error('battles must be positive')
    report=[]
    for gen in range(1,5):
        g=generation(gen);brain=g.brainmod;scope=dict(brain.__dict__)
        scope['exp_dmg']=lambda *args,_fn=brain.exp_dmg,**kw:_fn(*args[:4])
        scope['ko_prob']=lambda *args,_fn=brain.ko_prob,**kw:_fn(*args[:4])
        reference=types.FunctionType(brain.brain.__code__,scope)
        a=g.E.make_spec('a',build(gen));b=g.E.make_spec('b',build(gen))
        def run(policy):
            start=time.perf_counter();out=[]
            for seed in range(args.battles):
                bt=g.E.Battle(a,b,random.Random(seed),policy)
                out.append((bt.run(),bt.a.hp,bt.b.hp,bt.turn))
            return time.perf_counter()-start,out
        raw=[];optimized=[]
        for repetition in range(3):
            if repetition%2:
                new,new_results=run(g.brain);old,old_results=run(reference)
            else:old,old_results=run(reference);new,new_results=run(g.brain)
            assert old_results==new_results,(gen,repetition)
            raw.append(old);optimized.append(new)
        report.append(dict(generation=gen,battles=args.battles,repetitions=3,outcomes_equal=True,
                           without_estimate_reuse_seconds=raw,with_estimate_reuse_seconds=optimized,
                           median_runtime_reduction_percent=round(100*(1-statistics.median(optimized)/statistics.median(raw)),1)))
    print(json.dumps(dict(scope='synthetic fixtures; isolates estimate reuse on the corrected engines',results=report),indent=2))


if __name__=='__main__':main()
