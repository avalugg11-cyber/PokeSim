"""Exercise production worker paths under spawn with synthetic generation data."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multiprocessing
import random
import time
from unittest.mock import patch
from fixtures import generation, build

registry = patch('gens.get',side_effect=generation)
registry.start()
import tournament as T
import search as S
from simulation import SimulationTimeout


def slow_row(args):
    time.sleep(2)
    return 0, {}


def main():
    context=multiprocessing.get_context('spawn')
    with patch.object(T,'Pool',context.Pool),patch.object(S,'Pool',context.Pool):
        for gen in range(1,5):
            S.use_gen(gen);g=generation(gen)
            specs=[g.E.make_spec(k,build(gen)) for k in ['a','b','c','d']]
            serial=T.run_round_robin(specs,3,7,1,False)
            cache=T.PairCache();stats={}
            assert serial==T.run_round_robin(specs,3,7,2,False,cache=cache,stats=stats)
            assert stats['battles']==18
            assert serial==T.run_round_robin(specs,3,7,2,False,cache=cache,stats=stats)
            assert stats['battles']==0
            cands=[build(gen,moves) for moves in [['TACKLE'],['BODY_SLAM'],['THUNDERBOLT'],['RECOVER','BODY_SLAM']]]
            one=S.Scorer(1);many=S.Scorer(2)
            try:assert one.score('a',cands,specs[1:],3,7)==many.score('a',cands,specs[1:],3,7)
            finally:one.close();many.close()
            one=S.Scorer(1);many=S.Scorer(2)
            try:
                # Exercise reuse after a caller changes rules on an already warm pool.
                many.score('a',cands,specs[1:],3,7)
                with patch.object(g.E.RULES,'turn_limit',1):
                    assert T.run_round_robin(specs,3,7,1,False)==T.run_round_robin(specs,3,7,2,False)
                    assert one.score('a',cands,specs[1:],3,7)==many.score('a',cands,specs[1:],3,7)
                current=build(gen)
                choices=[build(gen,[a,b]) for a in ('TACKLE','BODY_SLAM','THUNDERBOLT') for b in ('RECOVER','SPLASH')]
                assert one.finalists('a',current,choices,specs[1:],3,7)==many.finalists('a',current,choices,specs[1:],3,7)
            finally:one.close();many.close()
            print('PASS spawn ranking/cache/scorer generation',gen,flush=True)
        deadline=time.monotonic()+0.5
        with patch.object(T,'_row',slow_row):
            try:T.run_round_robin(specs,3,7,2,False,deadline=deadline)
            except SimulationTimeout:pass
            else:raise AssertionError('parallel deadline not enforced')
        assert time.monotonic()-deadline<1.0
        print('PASS parallel ranking deadline terminates workers promptly',flush=True)
    assert not multiprocessing.active_children()


if __name__=='__main__':main()
