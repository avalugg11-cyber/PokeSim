from damage_estimates import Estimate, MULTI, multi_estimate, roll_distribution
"""The brain: a first-match-wins priority checklist (BRAIN_VERSION is saved with every run).

Order (as specified): Priority finisher, Guaranteed KO, Secure the KO, Counter, Brace, Explosion,
Damage Race, Sleep, Trapping, Damage Reduce, Speed Control, Recover/Rest, Setup/Disrupt,
Substitute, Highest Damage. The brain sees full battle state (moves, PP, stages), like the original.
"""
from .engine import (STRUGGLE, SLP, PAR, FRZ, spd, calc_base, acc_thresh, type_mults, STAT_UP, STAT_DOWN, Move)

BRAIN_VERSION = "0.10.2"
PROXY = Move("PROXY", {"type": "NORMAL", "power": 70, "acc": 100, "pp": 1, "effect": "NO_ADDITIONAL_EFFECT"})
ZERO = (0, 0, 0)


def _single_est(att, dfn, mv):
    """(min, avg, max) damage of one use, ignoring crits."""
    if mv.kind != "dmg" or mv.name == "COUNTER":
        return ZERO
    ef = mv.effect
    if ef == "DREAM_EATER_EFFECT" and dfn.status != SLP:
        return ZERO
    if 0 in type_mults(mv.type, dfn.types[0], dfn.types[1]):
        return ZERO
    if ef == "SPECIAL_DAMAGE_EFFECT":
        n = mv.name
        d = att.lvl if n in ("SEISMIC_TOSS", "NIGHT_SHADE") else 20 if n == "SONICBOOM" else 40 if n == "DRAGON_RAGE" else att.lvl * 3 // 4
        return (d, d, d)
    if ef == "SUPER_FANG_EFFECT":
        d = max(1, dfn.hp // 2)
        return (d, d, d)
    if ef == "OHKO_EFFECT":
        return ZERO if spd(att) < spd(dfn) else (65535, 65535, 65535)
    base = calc_base(att, dfn, mv)
    if base <= 1:
        return (base, base, base)
    return (base * 217 // 255, base * 236 // 255, base)


def est(att, dfn, mv):
    single = _single_est(att, dfn, mv)
    if mv.effect not in MULTI:
        return single
    def rolls_for(power):
        base = calc_base(att, dfn, mv)
        return tuple(max(1, base*r//255) for r in range(217,256))
    return multi_estimate(att, dfn, mv, single, 1, rolls_for, hit_p)


def hit_p(att, dfn, mv):
    if mv.effect == "SWIFT_EFFECT":
        return 1.0
    if dfn.invuln:
        return 0.0
    return acc_thresh(att, dfn, mv) / 256.0


def exp_dmg(att, dfn, mv, hp, estimate=None):
    mn, av, mx = est(att, dfn, mv) if estimate is None else estimate
    if mx == 0:
        return 0.0
    e = av * hit_p(att, dfn, mv)
    ef = mv.effect
    if ef in ("CHARGE_EFFECT", "FLY_EFFECT", "HYPER_BEAM_EFFECT") and mn < hp:
        e *= 0.5
    elif ef == "THRASH_PETAL_DANCE_EFFECT":
        e *= 0.8      # locked in for 3-4 turns, then confused
    elif ef == "RAGE_EFFECT":
        e *= 0.85     # locked in until the battle ends
    return e


def ko_prob(att, dfn, mv, hp, estimate=None):
    estimate = est(att, dfn, mv) if estimate is None else estimate
    mn, av, mx = estimate
    if mx < hp:
        return 0.0
    if isinstance(estimate, Estimate):
        return estimate.ko(hp) * hit_p(att, dfn, mv)
    if mn >= hp:
        p = 1.0
    else:
        base = mx
        p = sum(1 for r in range(217, 256) if base * r // 255 >= hp) / 39.0
    return p * hit_p(att, dfn, mv)


def ttk(hp, dpt):
    return 99 if dpt <= 0 else -(-hp // max(1, int(dpt)))


def brain(me, opp):
    mv_ = me.moves
    use = [i for i in range(len(mv_)) if me.pp[i] > 0 and i != me.dis_idx]
    if not use:
        return STRUGGLE, -1

    def ret(i):
        return mv_[i], i

    def find(*effects, names=()):
        return [i for i in use if mv_[i].effect in effects or mv_[i].name in names]

    s_me, s_op = spd(me), spd(opp)
    faster = s_me > s_op
    incap = opp.status in (SLP, FRZ) or opp.recharge or opp.trapped
    me_ehp = me.hp + me.sub
    op_hp = opp.hp if opp.sub == 0 else 10 ** 9   # one hit cannot KO through a Substitute
    op_ehp = opp.hp + opp.sub

    mine = {i: est(me, opp, mv_[i]) for i in use if mv_[i].kind == "dmg"}
    ouse = [j for j in range(len(opp.moves)) if opp.pp[j] > 0]
    theirs = {j: est(opp, me, opp.moves[j]) for j in ouse if opp.moves[j].kind == "dmg"}
    expl_op = [j for j in theirs if opp.moves[j].effect == "EXPLODE_EFFECT"]
    op_max = max([theirs[j][2] for j in theirs if j not in expl_op] or [0])
    op_best = 0.0
    op_best_phys = True
    for j in theirs:
        if j in expl_op:
            continue
        e = exp_dmg(opp, me, opp.moves[j], me.hp, theirs[j])
        if e > op_best:
            op_best, op_best_phys = e, opp.moves[j].phys
    my_best, my_best_i = 0.0, None
    for i in use:
        mv = mv_[i]
        if mv.effect == "EXPLODE_EFFECT":
            continue
        if mv.kind == "dmg":
            e = exp_dmg(me, opp, mv, opp.hp, mine[i])
        elif mv.effect == "METRONOME_EFFECT":            # random move: priced as a middling attack
            e = 0.5 * exp_dmg(me, opp, PROXY, opp.hp)
        elif mv.effect == "MIRROR_MOVE_EFFECT" and opp.last_mv is not None and opp.last_mv.kind == "dmg" \
                and opp.last_mv.effect != "MIRROR_MOVE_EFFECT":
            e = exp_dmg(me, opp, opp.last_mv, opp.hp)
        else:
            continue
        if e > my_best:
            my_best, my_best_i = e, i
    my_best_phys = mv_[my_best_i].phys if my_best_i is not None else True
    my_ttk, op_ttk = ttk(op_ehp, my_best), ttk(me_ehp, op_best)
    safe = op_ttk >= 3 and op_max < me_ehp and not any(theirs[j][2] >= me_ehp for j in expl_op)

    # 1. Priority finisher
    for i in find(names=("QUICK_ATTACK",)):
        if mine[i][0] >= op_hp and not faster and hit_p(me, opp, mv_[i]) > 0:
            return ret(i)
    # 2. Guaranteed KO (damage-guaranteed, 100% accuracy, we act first or they cannot act)
    best = None
    for i, (mn, av, mx) in mine.items():
        mv = mv_[i]
        if mv.effect in ("EXPLODE_EFFECT", "CHARGE_EFFECT", "FLY_EFFECT") or mn < op_hp:
            continue
        if hit_p(me, opp, mv) <= 0 or acc_thresh(me, opp, mv) < 255 or not (faster or mv.prio > 0 or incap):
            continue
        if best is None or mn > mine[best][0]:
            best = i
    if best is not None:
        return ret(best)
    # 3. Secure the KO (best KO probability, only if we survive to move)
    best, bp = None, 0.0
    for i in mine:
        mv = mv_[i]
        if mv.effect in ("EXPLODE_EFFECT", "CHARGE_EFFECT", "FLY_EFFECT"):
            continue
        p = ko_prob(me, opp, mv, op_hp, mine[i])
        if p >= 0.5 and p > bp and (faster or mv.prio > 0 or incap or (op_max < me_ehp and not expl_op)):
            best, bp = i, p
    if best is not None:
        return ret(best)
    # 4. Counter
    ci = find(names=("COUNTER",))
    if ci:
        nf = [theirs[j][1] for j in theirs if opp.moves[j].type in ("NORMAL", "FIGHTING") and j not in expl_op
              and opp.moves[j].name != "COUNTER"]
        nfmax = max([theirs[j][2] for j in theirs if opp.moves[j].type in ("NORMAL", "FIGHTING")
                     and opp.moves[j].name != "COUNTER"] or [0])
        if nf and nfmax < me_ehp and max(nf) >= 0.9 * max(op_best, 1) and (
                2 * max(nf) >= op_ehp or 2 * max(nf) >= 0.45 * opp.maxhp):
            return ret(ci[0])
    # 4b. Bide (a counter-style move): only when we cannot be killed while storing and the payoff can KO
    for i in find("BIDE_EFFECT"):
        if op_best > 0 and 3 * op_max < me_ehp and 2 * op_best * 2.5 >= op_ehp * 0.9:
            return ret(i)
    # 5. Brace against an incoming Explosion
    if expl_op and max(theirs[j][2] for j in expl_op) >= me_ehp:
        si = find("SUBSTITUTE_EFFECT")
        if si and me.sub == 0 and me.hp > me.maxhp // 4:
            return ret(si[0])
        for i in find("REFLECT_EFFECT"):
            if not me.reflect:
                me.reflect = True
                ok = all(theirs_j < me_ehp for theirs_j in
                         (est(opp, me, opp.moves[j])[2] for j in expl_op))
                me.reflect = False
                if ok:
                    return ret(i)
    # 6. Explosion (draw beats a loss: only when losing the race and it can take the foe down)
    for i in find("EXPLODE_EFFECT"):
        if mine[i][2] >= op_hp and mine[i][0] > 0:
            losing = (op_max >= me_ehp and not faster) or my_ttk > op_ttk or (my_ttk == op_ttk and not faster)
            if losing:
                return ret(i)
    # 7. Damage race
    if my_best > 0 and (incap or my_ttk < op_ttk or (my_ttk == op_ttk and faster)):
        return ret(my_best_i)
    # 8. Sleep
    if opp.status == 0 and opp.sub == 0 and not incap:
        si = find("SLEEP_EFFECT")
        if si:
            return ret(max(si, key=lambda i: mv_[i].acc))
    # 9. Trapping
    if not opp.trapped and opp.sub == 0:
        ti = [i for i in find("TRAPPING_EFFECT") if mine[i][1] > 0]
        if ti:
            return ret(max(ti, key=lambda i: exp_dmg(me, opp, mv_[i], opp.hp, mine[i])))
        for i in find("LEECH_SEED_EFFECT"):      # Leech Seed is a trap: a drain that keeps working
            if not opp.seeded and "GRASS" not in opp.types and my_ttk >= 3:
                return ret(i)
    # 10. Damage reduce
    if op_ttk >= 2:
        if op_best_phys and not me.reflect:
            for i in find("REFLECT_EFFECT"):
                return ret(i)
        if not op_best_phys and not me.lscreen:
            for i in find("LIGHT_SCREEN_EFFECT"):
                return ret(i)
    for i in find("MIST_EFFECT"):
        if not me.mist and any(opp.moves[j].effect in STAT_DOWN for j in ouse):
            return ret(i)
    for i in find("CONVERSION_EFFECT"):          # take the foe's typing when it blunts their best attack
        if me.types != opp.types and op_ttk >= 2:
            old = me.types
            me.types = opp.types
            nb = max([exp_dmg(opp, me, opp.moves[j], me.hp) for j in theirs if j not in expl_op] or [0])
            me.types = old
            if nb < 0.6 * op_best:
                return ret(i)
    # 11. Speed control
    if not faster:
        if opp.status == 0 and opp.sub == 0:
            for i in find("PARALYZE_EFFECT"):
                if mv_[i].name != "THUNDER_WAVE" or 0 not in type_mults(mv_[i].type, opp.types[0], opp.types[1]):
                    return ret(i)
        for i in find("SPEED_UP2_EFFECT", "SPEED_UP1_EFFECT"):
            if me.stage[2] < 2 and spd(me) * 2 > s_op:
                return ret(i)
        for i in find("SPEED_DOWN1_EFFECT", "SPEED_DOWN2_EFFECT"):
            if opp.sub == 0 and opp.stage[2] > -2:
                return ret(i)
    # 12. Recover / Rest
    diff = me.maxhp - me.hp
    if diff and diff % 256 != 255:
        for i in find("HEAL_EFFECT"):
            if mv_[i].name == "REST":
                if me.hp <= 0.45 * me.maxhp and op_max * 2 < me.maxhp and not expl_op:
                    return ret(i)
            elif me.hp <= 0.5 * me.maxhp and op_best < me.maxhp // 2 * 0.9:
                return ret(i)
    # 13. Setup / Disrupt (only when it is safe to spend a turn)
    if safe or incap:
        for i in use:
            mv, ef = mv_[i], mv_[i].effect
            if ef in STAT_UP:
                k, n = STAT_UP[ef]
                if k == 0 and my_best_phys and me.stage[0] < 2:
                    return ret(i)
                if k == 3 and not my_best_phys and me.stage[3] < 2:
                    return ret(i)
                if k == 3 and op_best_phys is False and me.stage[3] < 2:
                    return ret(i)
                if k == 1 and op_best_phys and me.stage[1] < 2:
                    return ret(i)
                if k == 5 and me.stage[5] < 3:
                    return ret(i)
            elif ef in STAT_DOWN and opp.sub == 0:
                k, n = STAT_DOWN[ef]
                if (k == 0 and op_best_phys and opp.stage[0] > -2) or (k == 1 and my_best_phys and opp.stage[1] > -2) \
                        or (k == 4 and opp.stage[4] > -2) or (k == 3 and not my_best_phys and opp.stage[3] > -2):
                    return ret(i)
            elif ef == "CONFUSION_EFFECT" and opp.conf == 0 and opp.sub == 0 and not incap:
                return ret(i)
            elif ef == "POISON_EFFECT" and opp.status == 0 and opp.sub == 0 and "POISON" not in opp.types:
                return ret(i)
            elif ef == "DISABLE_EFFECT" and opp.dis_idx < 0 and not incap:
                return ret(i)
            elif ef == "HAZE_EFFECT" and opp.status not in (SLP, FRZ):
                boost = sum(max(0, x) for x in opp.stage[:4]) + max(0, opp.stage[5])
                if boost >= 2 or -sum(min(0, x) for x in me.stage[:4]) >= 2:
                    return ret(i)
    # 14. Substitute
    if me.sub == 0 and me.hp >= 0.55 * me.maxhp:
        for i in find("SUBSTITUTE_EFFECT"):
            return ret(i)
    # 15. Highest damage (fallbacks keep the battle moving)
    if my_best_i is not None:
        return ret(my_best_i)
    for i in mine:
        if mine[i][2] > 0:
            return ret(i)
    for i in use:
        if mv_[i].effect == "TRANSFORM_EFFECT":
            return ret(i)
    return ret(use[0])
