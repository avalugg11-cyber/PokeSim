"""Pre-optimization formula; used only to detect rounding/order regressions."""
def calc_base(att,dfn,mv,crit=False,power=None,roll=100):
    if mv.effect=='BEAT_UP':
        if att.status:return 0
        A=D['mons'][att.key]['atk'];Df=D['mons'][dfn.species_key]['defn']
        return (((2*att.lvl//5+2)*mv.power*A//Df)//50+2)*(2 if crit else 1)*roll//100
    mt=mtype_of(mv,att);phys=physical(mv,att);ai,di=(0,1) if phys else (3,4)
    ignore=ignored(att,dfn)
    ignore_attack=crit and att.stage[ai]<0 or (dfn.ability=='UNAWARE' and not ignore)
    ignore_defense=crit and dfn.stage[di]>0 or att.ability=='UNAWARE'
    A=estat(att,ai,ignore_attack,burn=False)
    Df=estat(dfn,di,ignore_defense,burn=False,divisor=2 if mv.effect=='SELFDESTRUCT' else 1,ignore_ability=ignore)
    pw=move_power(att,dfn,mv,power)
    dmg=((2*att.lvl//5+2)*pw*A//max(1,Df))//50
    if phys and att.status==BRN and att.ability!='GUTS':dmg//=2
    if not crit and mv.effect!='BRICK_BREAK' and ((phys and dfn.reflect) or (not phys and dfn.lscreen)):dmg//=2
    weather=None if weather_suppressed(att.bt) else att.bt.weather
    if weather=='rain':dmg=dmg*3//2 if mt=='WATER' else dmg//2 if mt=='FIRE' else dmg
    if weather=='sun':dmg=dmg*3//2 if mt=='FIRE' else dmg//2 if mt=='WATER' else dmg
    if mv.effect=='SOLARBEAM' and weather in ('rain','sand','hail'):dmg//=2
    if att.flash_fire and mt=='FIRE':dmg=dmg*3//2
    dmg+=2
    if crit:dmg*=3 if att.ability=='SNIPER' else 2
    if getattr(att,'me_first',False):dmg=dmg*3//2
    if mv.effect=='FUTURE_SIGHT':return max(1,dmg*roll//100)
    if dfn.invuln and ((dfn.invuln=='fly' and mv.name in ('GUST','TWISTER')) or (dfn.invuln=='dig' and mv.name in ('EARTHQUAKE','MAGNITUDE')) or (dfn.invuln=='dive' and mv.name in ('SURF','WHIRLPOOL'))):dmg*=2
    dmg=max(1,dmg*roll//100)
    if mt in att.types:dmg=dmg*2 if att.ability=='ADAPTABILITY' else dmg*3//2
    eff=1
    for factor in type_mults(mt,*defensive_types(dfn,mt),dfn.foresight and mt in ('NORMAL','FIGHTING') or dfn.miracle_eye and mt=='PSYCHIC' or att.ability=='SCRAPPY' and mt in ('NORMAL','FIGHTING')):
        if factor==0:return 0
        eff*=factor/10;dmg=max(1,dmg*factor//10)
    if not ignore and dfn.ability in ('FILTER','SOLID_ROCK') and eff>1:dmg=dmg*3//4
    if att.ability=='TINTED_LENS' and eff<1:dmg*=2
    return max(1,dmg)
