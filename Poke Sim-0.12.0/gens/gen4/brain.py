from damage_estimates import Estimate, MULTI, multi_estimate, roll_distribution
"""Gen 4 brain: inherited first-match policy with Platinum move classes and field control:
Priority finisher, Guaranteed KO, Secure the KO, Counter (+ Mirror Coat, Bide), Brace (Protect, Substitute, Reflect),
Explosion, Damage Race, Sleep, Trapping (+ Leech Seed), Damage Reduce (screens, Mist, weather), Speed Control,
Recover/Rest, Setup/Disrupt, Substitute, Highest Damage. The brain sees full battle state, like the original."""
from .base import (STRUGGLE, SLP, PAR, FRZ, BRN, PSN, spd, calc_base, prepare_damage, damage_at, damage_rolls, acc_thresh, type_mults, mtype_of, Move, MV, weather_suppressed, physical, ignored, defensive_types)
from .effects import STAT_MOVES, SPECIAL_PW

BRAIN_VERSION = "0.10.2"
ZERO = (0, 0, 0)
PROXY = Move("PROXY", {"type": "NORMAL", "power": 70, "acc": 100, "pp": 1, "effect": "EFFECT_NORMAL_HIT", "chance": 0})
TWO_TURN = ("FLY", "RAZOR_WIND", "SKULL_BASH", "SKY_ATTACK")
HEALS = ("HEAL", "MOONLIGHT", "MORNING_SUN", "SYNTHESIS", "HEAL_HALF_REMOVE_FLYING_TYPE")

def power_of(att, mv):
    ef = mv.effect
    if ef == "ROLLOUT":
        return mv.power * (2 ** att.rollout_n) * (2 if att.curl else 1)
    if ef == "FURY_CUTTER":
        return min(160, mv.power * (2 ** att.fury_n))
    if ef == "MAGNITUDE":
        return 70
    if ef in SPECIAL_PW:
        return SPECIAL_PW[ef]
    if ef == "REVERSAL":
        p = 48 * att.hp // att.maxhp
        return 200 if p < 2 else 150 if p < 5 else 100 if p < 10 else 80 if p < 17 else 40 if p < 33 else 20
    if ef == "PRESENT":
        return 50
    if ef == "BEAT_UP":
        return att.base_atk // 10 + 5
    if ef == "TRIPLE_KICK":
        return 20
    return None

def _single_est(att, dfn, mv):
    """(min, avg, max) damage of one use, ignoring crits."""
    ef = mv.effect
    if mv.sound and dfn.ability == "SOUNDPROOF" and not ignored(att,dfn):
        return ZERO
    if mv.kind != "dmg" or ef in ("COUNTER", "MIRROR_COAT", "METAL_BURST", "FUTURE_SIGHT"):
        return ZERO
    if mv.name in ('FLING','NATURAL_GIFT'):return ZERO
    if mv.name=='LAST_RESORT' and (len(att.moves)<2 or any(x.name not in att.used for x in att.moves if x.name!='LAST_RESORT')):return ZERO
    if mv.name=='FEINT' and not dfn.protecting:return ZERO
    if att.bt.gravity and mv.name in ('FLY','BOUNCE','JUMP_KICK','HI_JUMP_KICK'):return ZERO
    if (ef == "DREAM_EATER" and (dfn.status != SLP or dfn.sub)) or (ef == "SNORE" and att.status != SLP) or (ef=="FAKE_OUT" and att.bt.turn>1) or (ef=="SPIT_UP" and not att.stockpile):
        return ZERO
    if not ignored(att,dfn) and dfn.ability=='LEVITATE' and mtype_of(mv,att)=='GROUND' and not att.bt.gravity and not dfn.ingrain:return ZERO
    if not ignored(att,dfn) and (dfn.ability,mtype_of(mv,att)) in (("VOLT_ABSORB","ELECTRIC"),("WATER_ABSORB","WATER"),("DRY_SKIN","WATER"),("MOTOR_DRIVE","ELECTRIC")):return ZERO
    if dfn.ability=="FLASH_FIRE" and dfn.status!=FRZ and mtype_of(mv,att)=="FIRE" and not ignored(att,dfn):return ZERO
    if not ignored(att,dfn) and mv.name!="FIRE_FANG" and dfn.ability=="WONDER_GUARD" and mtype_of(mv,att)!="TYPELESS" and math_effectiveness(mtype_of(mv,att),dfn)<=1:return ZERO
    if 0 in type_mults(mtype_of(mv,att), *defensive_types(dfn,mtype_of(mv,att)), dfn.foresight and mtype_of(mv,att) in ('NORMAL','FIGHTING') or dfn.miracle_eye and mtype_of(mv,att)=='PSYCHIC' or att.ability=='SCRAPPY' and mtype_of(mv,att) in ('NORMAL','FIGHTING')):
        return ZERO
    if mtype_of(mv,att)=='GROUND' and dfn.magnet_rise and not att.bt.gravity and not dfn.ingrain:return ZERO
    if ef=='ENDEAVOR':return (max(0,dfn.hp-att.hp),)*3
    if ef == "LEVEL_DAMAGE":
        return (att.lvl,) * 3
    if ef == "STATIC_DAMAGE":
        return ((20 if mv.name == "SONIC_BOOM" else 40),) * 3
    if ef == "SUPER_FANG":
        return (max(1, dfn.hp // 2),) * 3
    if ef == "PSYWAVE":
        return (att.lvl * 3 // 4,) * 3
    if ef == "OHKO":
        return ZERO if (dfn.ability=="STURDY" and not ignored(att,dfn)) or att.lvl < dfn.lvl else (dfn.hp,) * 3
    prepared = prepare_damage(att, dfn, mv, False, power_of(att, mv))
    base = damage_at(prepared, 100)
    if base <= 1:
        return (base, base, base)
    low = damage_at(prepared, 85)
    return Estimate(low, (low+base)/2, base,
                    lambda: roll_distribution(tuple(damage_at(prepared,r) for r in range(85,101))))

def est(att, dfn, mv):
    single = _single_est(att, dfn, mv)
    if mv.effect not in MULTI:
        return single
    def rolls_for(power):
        return damage_rolls(att, dfn, mv, False, power_of(att,mv) if power is None else power)
    return multi_estimate(att, dfn, mv, single, 4, rolls_for, hit_p)


def hit_p(att, dfn, mv):
    ef = mv.effect
    if mv.sound and dfn.ability == "SOUNDPROOF" and not ignored(att,dfn):
        return 0.0
    if dfn.protecting and mv.protect:
        return 0.0
    if ef == "OHKO":
        if att.lvl < dfn.lvl:return 0.0
        if att.lockon or att.ability=="NO_GUARD" or dfn.ability=="NO_GUARD":return 1.0
        if dfn.invuln:return 0.0
        return min(1.0, (30 + att.lvl - dfn.lvl) / 100.0)
    if att.lockon or att.ability=="NO_GUARD" or (dfn.ability=="NO_GUARD" and not ignored(att,dfn)):
        return 1.0
    if dfn.invuln and not ((dfn.invuln == "fly" and mv.name in ("GUST", "TWISTER", "THUNDER", "SKY_UPPERCUT")) or
                           (dfn.invuln == "dig" and mv.name in ("EARTHQUAKE", "MAGNITUDE")) or (dfn.invuln=="dive" and mv.name in ("SURF","WHIRLPOOL"))):
        return 0.0
    if ef == "ALWAYS_HIT":
        return 1.0
    a = acc_thresh(att, dfn, mv)
    if ef == "THUNDER":
        if att.bt.weather == "rain" and not weather_suppressed(att.bt):
            return 1.0
        if att.bt.weather == "sun" and not weather_suppressed(att.bt):
            a = 50
    return 1.0 if a>=100 or mv.acc==0 else a/100.0

def exp_dmg(att, dfn, mv, hp, estimate=None):
    mn, av, mx = est(att, dfn, mv) if estimate is None else estimate
    if mx == 0:
        return 0.0
    e = av * hit_p(att, dfn, mv)
    ef = mv.effect
    if (ef in TWO_TURN or ef == "HYPER_BEAM" or (ef == "SOLARBEAM" and att.bt.weather != "sun")) and mn < hp:
        e *= 0.5
    elif ef in ("RAMPAGE", "ROLLOUT"):
        e *= 0.8
    return e

def ko_prob(att, dfn, mv, hp, estimate=None):
    estimate = est(att, dfn, mv) if estimate is None else estimate
    mn, av, mx = estimate
    if mx < hp:
        return 0.0
    if isinstance(estimate, Estimate):
        return estimate.ko(hp) * hit_p(att, dfn, mv)
    p = 1.0 if mn >= hp else sum(1 for r in range(85, 101) if calc_base(att,dfn,mv,False,power_of(att,mv),roll=r) >= hp) / 16.0
    return p * hit_p(att, dfn, mv)

def ttk(hp, dpt):
    return 99 if dpt <= 0 else -(-hp // max(1, int(dpt)))

def brain(me, opp):
    mv_ = me.moves
    use = [i for i in range(len(mv_)) if me.pp[i] > 0 and i != me.dis_idx
           and not (me.taunt and mv_[i].kind=="status")
           and not (me.torment and mv_[i] is me.last_selected)
           and not (opp.imprison and mv_[i] in opp.moves)
           and not (me.heal_block and mv_[i].effect in HEALS)]
    if not use:
        return STRUGGLE, -1

    def ret(i):
        return mv_[i], i

    def find(*effects, names=()):
        return [i for i in use if mv_[i].effect in effects or mv_[i].name in names]

    # asleep: only Sleep Talk and Snore can act
    if me.status == SLP and me.slp > (2 if me.ability=="EARLY_BIRD" else 1):
        for i in find("SLEEP_TALK"):
            return ret(i)
        for i in find("SNORE"):
            return ret(i)

    faster = spd(me) < spd(opp) if me.bt.trick_room else spd(me) > spd(opp)
    s_me, s_op = spd(me), spd(opp)
    incap = opp.status in (SLP, FRZ) or opp.recharge
    me_ehp = me.hp + me.sub
    op_hp = opp.hp if opp.sub == 0 else 10 ** 9
    op_ehp = opp.hp + opp.sub
    mine = {i: est(me, opp, mv_[i]) for i in use if mv_[i].kind == "dmg"}
    ouse = [j for j in range(len(opp.moves)) if opp.pp[j] > 0]
    theirs = {j: est(opp, me, opp.moves[j]) for j in ouse if opp.moves[j].kind == "dmg"}
    expl_op = [j for j in theirs if opp.moves[j].effect == "SELFDESTRUCT"]
    op_max = max([theirs[j][2] for j in theirs if j not in expl_op] or [0])
    op_best, op_best_phys = 0.0, True
    for j in theirs:
        if j in expl_op:
            continue
        e = exp_dmg(opp, me, opp.moves[j], me.hp, theirs[j])
        if e > op_best:
            op_best, op_best_phys = e, opp.moves[j].phys
    blocked_focus = {i for i in mine if mv_[i].effect=='FOCUS_PUNCH' and op_best>0 and not incap and me.sub==0}
    for i in blocked_focus:mine[i]=ZERO
    my_best, my_best_i = 0.0, None
    for i in use:
        mv = mv_[i]
        if mv.effect == "SELFDESTRUCT" or i in blocked_focus:
            continue
        if mv.kind == "dmg":
            e = exp_dmg(me, opp, mv, opp.hp, mine[i])
        elif mv.effect == "METRONOME":
            e = 0.5 * exp_dmg(me, opp, PROXY, opp.hp)
        elif mv.effect == "MIRROR_MOVE" and me.last_received is not None and me.last_received.kind == "dmg" \
                and me.last_received.effect != "MIRROR_MOVE":
            e = exp_dmg(me, opp, me.last_received, opp.hp)
        else:
            continue
        if e > my_best:
            my_best, my_best_i = e, i
    my_best_phys = mv_[my_best_i].phys \
        if my_best_i is not None else True
    my_ttk, op_ttk = ttk(op_ehp, my_best), ttk(me_ehp, op_best)
    safe = op_ttk >= 3 and op_max < me_ehp and not any(theirs[j][2] >= me_ehp for j in expl_op)

    # 1. Priority finisher
    for i in mine:
        if mv_[i].prio > 0 and mine[i][0] >= op_hp and not faster and hit_p(me, opp, mv_[i]) > 0:
            return ret(i)
    # 2. Guaranteed KO
    best = None
    for i, (mn, av, mx) in mine.items():
        mv = mv_[i]
        if mv.effect in ("SELFDESTRUCT", "FUTURE_SIGHT") or mv.effect in TWO_TURN or mn < op_hp:
            continue
        if hit_p(me, opp, mv) < 1.0 or not (faster or mv.prio > 0 or incap):
            continue
        if best is None or mn > mine[best][0]:
            best = i
    if best is not None:
        return ret(best)
    # 3. Secure the KO
    best, bp = None, 0.0
    for i in mine:
        if i in blocked_focus:continue
        mv = mv_[i]
        if mv.effect in ("SELFDESTRUCT", "FUTURE_SIGHT") or mv.effect in TWO_TURN:
            continue
        p = ko_prob(me, opp, mv, op_hp, mine[i])
        if p >= 0.5 and p > bp and (faster or mv.prio > 0 or incap or (op_max < me_ehp and not expl_op)):
            best, bp = i, p
    if best is not None:
        return ret(best)
    # 4. Counter / Mirror Coat / Bide
    for name, phys in (("COUNTER", True), ("MIRROR_COAT", False)):
        for i in find(name):
            if 0 in type_mults(mv_[i].type, opp.types[0], opp.types[1], opp.foresight):
                continue
            cand = [theirs[j][1] for j in theirs if j not in expl_op and
                    opp.moves[j].phys == phys]
            mx = max([theirs[j][2] for j in theirs if opp.moves[j].phys == phys] or [0])
            if cand and mx < me_ehp and max(cand) >= 0.9 * max(op_best, 1) and (
                    2 * max(cand) >= op_ehp or 2 * max(cand) >= 0.45 * opp.maxhp):
                return ret(i)
    for i in find("BIDE"):
        if op_best > 0 and 3 * op_max < me_ehp and 2 * op_best * 2.5 >= op_ehp * 0.9:
            return ret(i)
    # 5. Brace against an incoming Explosion
    if expl_op and max(theirs[j][2] for j in expl_op) >= me_ehp:
        for i in find("PROTECT") + find("DETECT"):
            if me.protect_n == 0:
                return ret(i)
        for i in find("SUBSTITUTE"):
            if me.sub == 0 and me.hp > me.maxhp // 4:
                return ret(i)
        for i in find("REFLECT"):
            if not me.reflect:
                me.reflect = 5
                ok = all(est(opp, me, opp.moves[j])[2] < me_ehp for j in expl_op)
                me.reflect = 0
                if ok:
                    return ret(i)
    # 6. Explosion (a draw beats a loss)
    for i in find("SELFDESTRUCT"):
        if mine[i][2] >= op_hp and mine[i][0] > 0:
            if (op_max >= me_ehp and not faster) or my_ttk > op_ttk or (my_ttk == op_ttk and not faster):
                return ret(i)
    # 7. Damage race
    if my_best > 0 and (incap or my_ttk < op_ttk or (my_ttk == op_ttk and faster)):
        return ret(my_best_i)
    # 8. Sleep
    if opp.status == 0 and opp.sub == 0 and not incap and opp.safeguard == 0 and me.bt.can_sleep(opp):
        si = find("SLEEP")
        if si:
            return ret(max(si, key=lambda i: mv_[i].acc))
    # 9. Trapping (and Leech Seed)
    if opp.trap_left == 0 and opp.sub == 0:
        ti = [i for i in find("TRAP_TARGET") if mine[i][1] > 0]
        if ti:
            return ret(max(ti, key=lambda i: exp_dmg(me, opp, mv_[i], opp.hp, mine[i])))
    for i in find("LEECH_SEED"):
        if not opp.seeded and "GRASS" not in opp.types and opp.sub == 0 and my_ttk >= 3:
            return ret(i)
    # 10. Damage reduce
    if op_ttk >= 2:
        if op_best_phys and not me.reflect:
            for i in find("REFLECT"):
                return ret(i)
        if not op_best_phys and not me.lscreen:
            for i in find("LIGHT_SCREEN"):
                return ret(i)
    for i in find("MIST"):
        if not me.mist and any(opp.moves[j].effect in ("ATTACK_DOWN", "DEFENSE_DOWN", "SPEED_DOWN", "ACCURACY_DOWN",
                                                       "ATTACK_DOWN_2", "DEFENSE_DOWN_2", "SPEED_DOWN_2") for j in ouse):
            return ret(i)
    w = me.bt.weather
    for i in find("RAIN_DANCE", "SUNNY_DAY"):
        want = "rain" if mv_[i].effect == "RAIN_DANCE" else "sun"
        helps = any(mv_[k].type == ("WATER" if want == "rain" else "FIRE") or mv_[k].effect in ("THUNDER", "SOLARBEAM") and want == ("rain" if mv_[k].effect == "THUNDER" else "sun")
                    for k in mine)
        hurts = any(opp.moves[j].type == ("FIRE" if want == "rain" else "WATER") for j in theirs)
        if w != want and helps and not hurts and safe:
            return ret(i)
    # 11. Speed control
    if not faster:
        if opp.status == 0 and opp.sub == 0 and opp.safeguard == 0 and opp.ability!="LIMBER":
            for i in find("PARALYZE"):
                if mv_[i].name != "THUNDER_WAVE" or 0 not in type_mults(mv_[i].type, opp.types[0], opp.types[1], opp.foresight):
                    return ret(i)
        for i in find("SPEED_UP_2"):
            if me.stage[2] < 2 and s_me * 2 > s_op:
                return ret(i)
        for i in find("SPEED_DOWN", "SPEED_DOWN_2"):
            if opp.sub == 0 and opp.stage[2] > -2:
                return ret(i)
    # 12. Recover / Rest
    diff = me.maxhp - me.hp
    if diff:
        for i in find(*HEALS):
            if mv_[i].name == "REST":
                if me.hp <= 0.45 * me.maxhp and op_max * 2 < me.maxhp and not expl_op and me.status != SLP and me.bt.can_sleep(me):
                    return ret(i)
            elif me.hp <= 0.5 * me.maxhp and op_best < me.maxhp // 2 * 0.9:
                return ret(i)
    # Platinum tactical field control; the shared policy still uses estimates.
    if safe or incap:
        for i in use:
            name=mv_[i].name
            if name=='TRICK_ROOM' and not me.bt.trick_room and spd(me)<spd(opp):return ret(i)
            if name=='TAILWIND' and not me.tailwind and spd(me)<spd(opp)<spd(me)*2:return ret(i)
            if name=='AQUA_RING' and not me.aqua_ring and not me.heal_block:return ret(i)
            if name=='ACUPRESSURE' and sum(me.stage)<6:return ret(i)
            if name=='WORRY_SEED' and opp.ability not in ('INSOMNIA','MULTITYPE','TRUANT'):return ret(i)
            if name=='GASTRO_ACID' and opp.ability not in ('NONE','MULTITYPE','TRUANT','SLOW_START'):return ret(i)
            if name=='HEAL_BLOCK' and not opp.heal_block and any(x.effect in HEALS for x in opp.moves):return ret(i)
            if name=='PSYCHO_SHIFT' and me.status and not opp.status:return ret(i)
    # 13. Setup / Disrupt
    if safe or incap:
        for i in use:
            mv, ef = mv_[i], mv_[i].effect
            if ef in STAT_MOVES:
                user, chg = STAT_MOVES[ef]
                k = chg[0][0]
                if user:
                    if (k == 0 and my_best_phys and me.stage[0] < 2) or (k == 3 and not my_best_phys and me.stage[3] < 2) or \
                            (k == 1 and op_best_phys and me.stage[1] < 2) or (k == 4 and not op_best_phys and me.stage[4] < 2) or \
                            (k == 6 and me.stage[6] < 3):
                        return ret(i)
                elif opp.sub == 0 and not opp.mist and ((k == 0 and op_best_phys and opp.stage[0] > -2) or
                                                          (k == 1 and my_best_phys and opp.stage[1] > -2) or
                                                          (k == 5 and opp.stage[5] > -2)):
                    return ret(i)
            elif ef == "BELLY_DRUM" and my_best_phys and me.hp > 0.55 * me.maxhp and me.stage[0] <= 0:
                return ret(i)
            elif ef == "CURSE":
                if "GHOST" in me.types:
                    if not opp.cursed and me.hp > 0.6 * me.maxhp:
                        return ret(i)
                elif my_best_phys and me.stage[0] < 2:
                    return ret(i)
            elif ef == "SWAGGER" and opp.conf == 0 and opp.sub == 0 and not op_best_phys and not incap:
                return ret(i)
            elif ef == "CONFUSE" and opp.conf == 0 and opp.sub == 0 and not incap and opp.safeguard == 0:
                return ret(i)
            elif ef in ("POISON", "TOXIC") and opp.status == 0 and opp.sub == 0 and opp.safeguard == 0 \
                    and "POISON" not in opp.types and "STEEL" not in opp.types and opp.ability!="IMMUNITY":
                return ret(i)
            elif ef == "ATTRACT" and not opp.attract and opp.sub == 0 and {me.gender, opp.gender} == {"M", "F"}:
                return ret(i)
            elif ef == "DISABLE" and opp.dis_idx < 0 and not incap:
                return ret(i)
            elif ef == "ENCORE" and opp.encore_left == 0 and opp.last_mv is not None and opp.last_mv.kind != "dmg":
                return ret(i)
            elif ef == "RESET_STATS" and (sum(max(0, x) for x in opp.stage) >= 2 or -sum(min(0, x) for x in me.stage) >= 2):
                return ret(i)
            elif ef == "PSYCH_UP" and sum(opp.stage) - sum(me.stage) >= 2:
                return ret(i)
            elif ef == "FORESIGHT" and "GHOST" in opp.types and not opp.foresight and \
                    any(mv_[k].type in ("NORMAL", "FIGHTING") for k in mine):
                return ret(i)
            elif ef == "PAIN_SPLIT" and opp.hp > me.hp * 1.5:
                return ret(i)
            elif ef == "HEAL_BELL" and me.status:
                return ret(i)
            elif ef == "DESTINY_BOND" and not faster and op_max >= me.hp and not me.dbond:
                return ret(i)
            elif ef == "PROTECT" and opp.charge is not None and me.protect_n == 0:
                return ret(i)
    # 14. Substitute
    if me.sub == 0 and me.hp >= 0.55 * me.maxhp:
        for i in find("SUBSTITUTE"):
            return ret(i)
    # 15. Highest damage (fallbacks keep the battle moving)
    if my_best_i is not None:
        return ret(my_best_i)
    for i in mine:
        if mine[i][2] > 0:
            return ret(i)
    for i in find("FUTURE_SIGHT"):
        return ret(i)
    for i in find("TRANSFORM", "SKETCH"):
        return ret(i)
    return ret(use[0])

def math_effectiveness(typ,mon):
    value=1
    for x in type_mults(typ,*mon.types,mon.foresight):value*=x/10
    return value
