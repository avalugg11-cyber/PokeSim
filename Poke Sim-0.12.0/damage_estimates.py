"""Decision-local damage distributions. Estimates ignore critical hits."""
from collections import Counter
from functools import lru_cache

MULTI = frozenset({'TWO_TO_FIVE_ATTACKS_EFFECT', 'ATTACK_TWICE_EFFECT',
                   'TWINEEDLE_EFFECT', 'MULTI_HIT', 'DOUBLE_HIT',
                   'POISON_MULTI_HIT', 'TRIPLE_KICK'})


class Estimate(tuple):
    def __new__(cls, low, average, high, distribution):
        result = super().__new__(cls, (low, average, high))
        result.distribution = distribution
        return result

    def ko(self, hp):
        if callable(self.distribution):
            self.distribution = self.distribution()
        return sum(p for damage, p in self.distribution if damage >= hp)


def roll_distribution(rolls):
    counts = Counter(rolls)
    return tuple((damage, count / len(rolls)) for damage, count in sorted(counts.items()))


@lru_cache(2048)
def _sum_hits(roll_sets, weights, shared):
    result = Counter()
    if shared:
        for hits, weight in weights:
            for damage, probability in roll_distribution(roll_sets[0]):
                result[damage * hits] += weight * probability
    else:
        current = {0: 1.0}
        wanted = dict(weights)
        for hit in range(1, max(wanted) + 1):
            following = Counter()
            for previous, pp in current.items():
                for damage, probability in roll_distribution(roll_sets[min(hit-1, len(roll_sets)-1)]):
                    following[previous + damage] += pp * probability
            current = following
            for damage, probability in current.items():
                result[damage] += wanted.get(hit, 0) * probability
    return tuple(sorted((d, p) for d, p in result.items() if p > 0))


def multi_estimate(att, dfn, mv, single, gen, rolls_for, hit_chance):
    """Aggregate noncritical hits, using each generation's roll correlation.

    Contact-triggered interruption is conservatively limited to the first hit.
    Substitute KO reasoning remains conservative in the policy.
    """
    if mv.effect not in MULTI or single[2] == 0:
        return single
    contact = gen >= 3 and getattr(mv,'contact',False)
    if gen >= 3 and (dfn.ability == 'COLOR_CHANGE' or contact and
                    dfn.ability in ('EFFECT_SPORE','STATIC','POISON_POINT','FLAME_BODY','CUTE_CHARM')):
        # Later hits may have different typing/stats or be interrupted by sleep.
        rolls = rolls_for(10 if mv.effect=='TRIPLE_KICK' else None)
        distribution = roll_distribution(rolls)
        return Estimate(min(rolls),sum(rolls)/len(rolls),max(rolls),distribution)
    if mv.effect == 'TRIPLE_KICK':
        chance = hit_chance(att, dfn, mv)
        weights = ((1, 1-chance), (2, chance*(1-chance)), (3, chance*chance))
        rolls = tuple(rolls_for(power) for power in (10, 20, 30))
        shared = False
    else:
        variable = mv.effect in ('MULTI_HIT', 'TWO_TO_FIVE_ATTACKS_EFFECT')
        weights = ((5, 1.0),) if gen == 4 and att.ability == 'SKILL_LINK' and variable else (
            ((2, .375), (3, .375), (4, .125), (5, .125)) if variable else ((2, 1.0),))
        rolls = (rolls_for(None),)
        shared = gen <= 2
    if contact and dfn.ability=='ROUGH_SKIN' and not (gen==4 and att.ability=='MAGIC_GUARD'):
        recoil = max(1,att.maxhp//(16 if gen==3 else 8))
        maximum = max(1,(att.hp+recoil-1)//recoil)
        capped = Counter()
        for hits,probability in weights:capped[min(hits,maximum)]+=probability
        weights = tuple(sorted(capped.items()))
    distribution = _sum_hits(rolls, weights, shared)
    if gen <= 2 and dfn.sub:
        capped = Counter()
        for damage, probability in distribution:
            capped[min(damage, dfn.sub)] += probability
        distribution = tuple(sorted(capped.items()))
    if getattr(dfn, 'enduring', False):
        capped = Counter()
        for damage, probability in distribution:
            capped[min(damage, max(0, dfn.hp-1))] += probability
        distribution = tuple(sorted(capped.items()))
    return Estimate(distribution[0][0], sum(d*p for d,p in distribution), distribution[-1][0], distribution)
