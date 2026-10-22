"""Platinum stats and damage; perfect IVs and locked form-required items."""
import copy
from .data import load
D = load()
ENGINE_VERSION = "0.12.0"
SLP, PAR, BRN, PSN, FRZ = 1, 2, 3, 4, 5
PHYS = frozenset({"NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "STEEL"})
RATIO = [25,28,33,40,50,66,100,150,200,250,300,350,400]
HIGH_CRIT = frozenset({"KARATE_CHOP","RAZOR_WIND","RAZOR_LEAF","CRABHAMMER","SLASH","AEROBLAST","CROSS_CHOP","BLAZE_KICK","POISON_TAIL","AIR_CUTTER","LEAF_BLADE"})
HIGH_CRIT = HIGH_CRIT | {'ATTACK_ORDER','NIGHT_SLASH','PSYCHO_CUT','SHADOW_CLAW','SPACIAL_REND','STONE_EDGE','CROSS_POISON'}
CRIT_CHANCE = (16,32,64,85,128)
# Preserve cartridge table order: per-type integer rounding depends on it.
CHART={}
for attack,defense,factor in D['chart']:CHART.setdefault(attack,{})[defense]=factor

NATURES = {
    "HARDY": (1.0, 1.0, 1.0, 1.0, 1.0), "LONELY": (1.1, 0.9, 1.0, 1.0, 1.0), "BRAVE": (1.1, 1.0, 1.0, 1.0, 0.9), "ADAMANT": (1.1, 1.0, 0.9, 1.0, 1.0), "NAUGHTY": (1.1, 1.0, 1.0, 0.9, 1.0),
    "DOCILE": (1.0, 1.0, 1.0, 1.0, 1.0), "BOLD": (0.9, 1.1, 1.0, 1.0, 1.0), "RELAXED": (1.0, 1.1, 1.0, 1.0, 0.9), "IMPISH": (1.0, 1.1, 0.9, 1.0, 1.0), "LAX": (1.0, 1.1, 1.0, 0.9, 1.0),
    "TIMID": (0.9, 1.0, 1.0, 1.0, 1.1), "HASTY": (1.0, 0.9, 1.0, 1.0, 1.1), "SERIOUS": (1.0, 1.0, 1.0, 1.0, 1.0), "JOLLY": (1.0, 1.0, 0.9, 1.0, 1.1), "NAIVE": (1.0, 1.0, 1.0, 0.9, 1.1),
    "MODEST": (0.9, 1.0, 1.1, 1.0, 1.0), "MILD": (1.0, 0.9, 1.1, 1.0, 1.0), "QUIET": (1.0, 1.0, 1.1, 1.0, 0.9), "BASHFUL": (1.0, 1.0, 1.0, 1.0, 1.0), "RASH": (1.0, 1.0, 1.1, 0.9, 1.0),
    "CALM": (0.9, 1.0, 1.0, 1.1, 1.0), "GENTLE": (1.0, 0.9, 1.0, 1.1, 1.0), "SASSY": (1.0, 1.0, 1.0, 1.1, 0.9), "CAREFUL": (1.0, 1.0, 0.9, 1.1, 1.0), "QUIRKY": (1.0, 1.0, 1.0, 1.0, 1.0)
}


class Rules:
    def __init__(self, both_faint_draw=True, turn_limit=50):
        self.both_faint_draw = both_faint_draw
        self.turn_limit = turn_limit
        self.ivs = 31
        self.badge_glitch = False
        self.statexp = 0
RULES = Rules()

# Normalize effect names to the shared battle vocabulary, preserving native metadata.
ALIASES = {"HIT":"NORMAL_HIT","POISON_HIT":"POISON_HIT","ABSORB":"LEECH_HIT","EXPLOSION":"SELFDESTRUCT",
    "SPECIAL_ATTACK_UP":"SP_ATK_UP","SPECIAL_DEFENSE_UP":"SP_DEF_UP","SPECIAL_ATTACK_UP_2":"SP_ATK_UP_2",
    "SPECIAL_DEFENSE_UP_2":"SP_DEF_UP_2","SPECIAL_DEFENSE_DOWN":"SP_DEF_DOWN","SPECIAL_DEFENSE_DOWN_2":"SP_DEF_DOWN_2",
    "SPECIAL_ATTACK_DOWN":"SP_ATK_DOWN","SPECIAL_ATTACK_DOWN_2":"SP_ATK_DOWN_2",
    "SPECIAL_ATTACK_DOWN_HIT":"SP_ATK_DOWN_HIT","SPECIAL_DEFENSE_DOWN_HIT":"SP_DEF_DOWN_HIT",
    "HAZE":"RESET_STATS","ROAR":"FORCE_SWITCH","REST":"HEAL","SOFTBOILED":"HEAL","RESTORE_HP":"HEAL",
    "DRAGON_RAGE":"STATIC_DAMAGE","SONICBOOM":"STATIC_DAMAGE","TRAP":"TRAP_TARGET","HIGH_CRITICAL":"NORMAL_HIT",
    "RECOIL_IF_MISS":"JUMP_KICK","RECOIL":"RECOIL_HIT","TWINEEDLE":"POISON_MULTI_HIT",
    "VITAL_THROW":"ALWAYS_HIT","RECHARGE":"HYPER_BEAM","CONVERSION_2":"CONVERSION2","FLAIL":"REVERSAL",
    "QUICK_ATTACK":"PRIORITY_HIT","MINIMIZE":"EVASION_UP","THAW_HIT":"FLAME_WHEEL","ALL_STATS_UP_HIT":"ALL_UP_HIT",
    "SEMI_INVULNERABLE":"FLY","FLINCH_MINIMIZE_HIT":"STOMP","SOLAR_BEAM":"SOLARBEAM","TELEPORT":"TELEPORT"}
ALIASES.update({
    'DEF_SPD_UP':'COSMIC_POWER','RAISE_SP_ATK_HIT':'SP_ATK_UP_HIT',
    'HIGH_CRITICAL_POISON_HIT':'POISON_HIT','LOWER_SP_DEF_2_HIT':'SP_DEF_DOWN_2_HIT',
    'RECOIL_BURN_HIT':'DOUBLE_EDGE','RECOIL_HALF':'HEAD_SMASH',
    'EAT_BERRY':'NORMAL_HIT','SWITCH_HIT':'NORMAL_HIT',
    'DOUBLE_POWER_IF_HIT':'REVENGE','SHADOW_FORCE':'FLY'})
class Move:
    def __init__(self, name, d):
        self.name=name; self.type=d['type']; self.power=d['power']; self.acc=d['acc']; self.pp=d['pp']
        self.native=d['effect']; self.effect=ALIASES.get(self.native,self.native)
        self.phys=d.get('category','PHYSICAL')=='PHYSICAL'; self.prio=d.get('priority',0); self.chance=d.get('chance',0)*256//100
        self.contact=d.get('contact',False); self.protect=d.get('protect',True); self.sound=d.get('sound',False)
        self.kind='status' if d.get('category')=='STATUS' else 'dmg' if self.power>0 or self.effect in {'OHKO','COUNTER','MIRROR_COAT','METAL_BURST','LEVEL_DAMAGE','ENDEAVOR','SUPER_FANG','PSYWAVE'} else 'status'
        self.snatch=d.get('snatch',False); self.reflectable=d.get('reflectable',False)
        self.supported=True; self.category=d.get('category','PHYSICAL' if self.phys else 'SPECIAL'); self.source_effect=d.get('source_effect','')
    def __repr__(self): return self.name
MV={name:Move(name,d) for name,d in D['moves'].items()}
STRUGGLE=MV['STRUGGLE']; MOVE_ORDER=list(MV.values())
# Cmd_metronome's source table ends at METRONOME_FORBIDDEN_END.
NO_MIMIC=frozenset({'METRONOME','STRUGGLE','SKETCH','MIMIC','CHATTER'})
NO_METRONOME=NO_MIMIC | frozenset({'COUNTER','MIRROR_COAT','PROTECT','DETECT','ENDURE','DESTINY_BOND','SLEEP_TALK','THIEF','FOLLOW_ME','SNATCH','HELPING_HAND','COVET','TRICK','FOCUS_PUNCH','FEINT','COPYCAT','ME_FIRST','SWITCHEROO','ASSIST','MIRROR_MOVE'})

def exp_for_level(growth, n):
    cube=n**3
    if growth=='GROWTH_SLOW': return 5*cube//4
    if growth=='GROWTH_FAST': return 4*cube//5
    if growth=='GROWTH_MEDIUM_SLOW': return max(0,6*cube//5-15*n*n+100*n-140)
    if growth=='GROWTH_ERRATIC':
        if n<=50:return cube*(100-n)//50
        if n<=68:return cube*(150-n)//100
        if n<=98:return cube*((1911-10*n)//3)//500
        return cube*(160-n)//100
    if growth=='GROWTH_FLUCTUATING':
        return cube*((n+1)//3+24)//50 if n<=15 else cube*(n+14)//50 if n<=36 else cube*(n//2+32)//50
    return cube
from move_rules import BATTLE_LEVEL, battle_level
LEVEL = dict.fromkeys({m['growth'] for m in D['mons'].values()}, BATTLE_LEVEL)

def make_spec(key, build, level=None, **unused):
    from .pool import pool
    s=D['mons'][key]; level=battle_level(level)
    if isinstance(build,list):
        build=dict(moves=build,ability=s['abilities'][0],nature='HARDY',evs={})
    build=copy.deepcopy(build)
    if not isinstance(build,dict): raise ValueError('build must be an object')
    moves=build.get('moves',[]); ability=build.get('ability'); nature=build.get('nature'); evs=build.get('evs',{})
    if not isinstance(moves,list) or not 1<=len(moves)<=4 or any(not isinstance(m,str) for m in moves) or len(set(moves))!=len(moves): raise ValueError('build needs 1..4 distinct moves')
    from move_rules import validate_moves
    validate_moves(key, moves, pool(key, level))
    if ability not in s['abilities'] or ability=='NONE': raise ValueError(f'illegal ability for {key}')
    if not isinstance(nature,str) or nature not in NATURES: raise ValueError('unknown nature')
    if not isinstance(evs,dict) or set(evs)-{'hp','atk','defn','spa','sdf','spe'}: raise ValueError('invalid EV stat names')
    if any(type(v) is not int or not 0<=v<=255 for v in evs.values()) or sum(evs.values())>510: raise ValueError('EVs must be 0..255 per stat, total at most 510')
    if set(build)-{'moves','ability','nature','evs'}:raise ValueError('unknown build fields; form-required items are fixed by the species entry')
    build["evs"]=dict(evs)
    nat=NATURES[nature]
    def stat(base,ev,mult):
        value=(2*base+RULES.ivs+ev//4)*level//100+5
        return value*round(mult*10)//10
    hp=1 if key=='shedinja' else (2*s['hp']+RULES.ivs+evs.get('hp',0)//4)*level//100+level+10
    gender='N' if s['gender']=='MON_GENDERLESS' else 'F' if '100' in s['gender'] or s['gender']=='MON_FEMALE' else 'M'
    return dict(key=key,name=s['name'],types=tuple(s['types']),lvl=level,hp=hp,gender=gender,ability=ability,nature=nature,base_atk=s['atk'],weight=s['weight'],item=s.get('required_item'),base_species=s.get('base_species',key),
        raw=(stat(s['atk'],evs.get('atk',0),nat[0]),stat(s['defn'],evs.get('defn',0),nat[1]),stat(s['spe'],evs.get('spe',0),nat[4]),stat(s['spa'],evs.get('spa',0),nat[2]),stat(s['sdf'],evs.get('sdf',0),nat[3])),moves=list(moves),build=build)

class Mon: pass

def fresh(sp,bt,badges=False):
    m=Mon();m.__dict__.update(sp);m.bt=bt;m.native_types=m.types;m.maxhp=m.hp;m.raw=tuple(sp['raw']);m.stage=[0]*7;m.badges=False
    for field in ('status','slp','toxic','conf','sub','reflect','lscreen','safeguard','perish','protect_n','encore_left','dis_left','rampage_left','rollout_left','rollout_n','fury_n','bide_left','bide_acc','trap_left','took_dmg','future_left','future_dmg','stockpile','taunt','torment','yawn','wish','charge_power','uproar','rage_n','mist_left','lockon_left'):
        setattr(m,field,0)
    m.rage_n=1
    for field in ('flinch','mist','seeded','nightmare','cursed','dbond','protecting','enduring','lockon','foresight','recharge','trapped','attract','focus','curl','rage','skip','minimized','stolen','flash_fire','ingrain','magic_coat','snatch','grudge','imprison','mud_sport','water_sport','loaf','transformed'):
        setattr(m,field,False)
    for field in ('charge','invuln','encore_mv','rampage_mv','last_mv','future_by','took_phys','last_received','last_selected','called_from'):
        setattr(m,field,None)
    m.call_depth=0;m.active_idx=-1;m.species_key=m.key;m.acted=False;
    m.dis_idx=-1;m.moves=[MV[n] for n in sp['moves']];m.pp=[mv.pp for mv in m.moves];m.used={}
    m.aqua_ring=m.heal_block=m.lucky_chant=m.magnet_rise=m.tailwind=m.embargo=0
    m.slow_start=5;m.suppressed_ability=None;m.roost_types=None;m.last_damage=0;m.stock_def=m.stock_sdf=0;m.attack_move=None;m.miracle_eye=False
    return m

def ignored(att,dfn):return att.ability=='MOLD_BREAKER' and dfn.ability not in ('MULTITYPE',)

def stage_of(m,i,ignore=False,ignore_ability=False):
    return 0 if ignore else max(-6,min(6,m.stage[i]*(2 if m.ability=='SIMPLE' and not ignore_ability else 1)))

def estat(m,i,ignore_stage=False,burn=True,raw=None,divisor=1,ignore_ability=False):
    value=m.raw[i] if raw is None else raw
    if i==0:
        if m.ability in ('HUGE_POWER','PURE_POWER'):value*=2
        if m.ability=='SLOW_START' and m.slow_start:value//=2
        if m.ability=='HUSTLE':value=value*3//2
        if m.status and m.ability=='GUTS':value=value*3//2
        if m.ability=='FLOWER_GIFT' and m.bt.weather=='sun' and not weather_suppressed(m.bt):value=value*3//2
    if i==1 and m.status and m.ability=='MARVEL_SCALE' and not ignore_ability:value=value*3//2
    if i==3 and m.ability=='SOLAR_POWER' and m.bt.weather=='sun' and not weather_suppressed(m.bt):value=value*3//2
    if i==4 and not weather_suppressed(m.bt):
        if m.bt.weather=='sand' and 'ROCK' in m.types:value=value*3//2
        if m.bt.weather=='sun' and m.ability=='FLOWER_GIFT' and not ignore_ability:value=value*3//2
    value//=divisor
    st=stage_of(m,i,ignore_stage,ignore_ability);value=value*(2+max(0,st))//(2+max(0,-st))
    if i==0 and burn and m.status==BRN and m.ability!='GUTS':value//=2
    if i==2:
        if m.ability=='SLOW_START' and m.slow_start:value//=2
        if m.status==PAR and m.ability!='QUICK_FEET':value//=4
        if m.status and m.ability=='QUICK_FEET':value=value*3//2
    return max(1,value)

def spd(m):
    v=estat(m,2)
    if not weather_suppressed(m.bt) and ((m.ability=='SWIFT_SWIM' and m.bt.weather=='rain') or (m.ability=='CHLOROPHYLL' and m.bt.weather=='sun')):v*=2
    if m.ability=='UNBURDEN' and getattr(m,'unburden',False):v*=2
    if m.tailwind:v*=2
    return v

def weather_suppressed(bt):return any(m.ability in ('CLOUD_NINE','AIR_LOCK') for m in (bt.a,bt.b)) if bt else False

def mtype_of(mv,att=None):
    if mv.name in ('STRUGGLE','FUTURE_SIGHT','DOOM_DESIRE','BEAT_UP'):return 'TYPELESS'
    if att and att.ability=='NORMALIZE':return 'NORMAL'
    if mv.name=='HIDDEN_POWER':return 'DARK'
    if mv.name=='JUDGMENT' and att and att.item and att.item.endswith('_PLATE') and not att.embargo:return D['mons'][att.key]['types'][0]
    if mv.name=='WEATHER_BALL' and att and not weather_suppressed(att.bt):return {'rain':'WATER','sun':'FIRE','sand':'ROCK','hail':'ICE'}.get(att.bt.weather,'NORMAL')
    return mv.type

def physical(mv,att=None):return mv.phys  # Platinum class belongs to the move, never its type.

def defensive_types(m,mt):
    if mt=='GROUND' and (getattr(m.bt,'gravity',0) or m.ingrain):
        ts=[t for t in m.types if t!='FLYING'];return (ts[0],ts[-1]) if ts else ('NORMAL','NORMAL')
    return m.types

def type_mults(mt,t1,t2,foresight=False):
    return [factor for target,factor in CHART.get(mt,{}).items() if target in (t1,t2)
        and not (foresight and ((mt in ('NORMAL','FIGHTING') and target=='GHOST') or (mt=='PSYCHIC' and target=='DARK')))] or [10]

def crit_stage(m,mv):return min(4,(2 if m.focus else 0)+(1 if mv.name in HIGH_CRIT else 0)+(1 if m.ability=='SUPER_LUCK' else 0))

PUNCHES=frozenset({'BULLET_PUNCH','COMET_PUNCH','DIZZY_PUNCH','DRAIN_PUNCH','DYNAMIC_PUNCH','FIRE_PUNCH','FOCUS_PUNCH','HAMMER_ARM','ICE_PUNCH','MACH_PUNCH','MEGA_PUNCH','METEOR_MASH','SHADOW_PUNCH','SKY_UPPERCUT','THUNDER_PUNCH'})
RECOILS=frozenset({'TAKE_DOWN','DOUBLE_EDGE','SUBMISSION','VOLT_TACKLE','FLARE_BLITZ','BRAVE_BIRD','WOOD_HAMMER','HEAD_SMASH','JUMP_KICK','HI_JUMP_KICK'})

def move_power(att,dfn,mv,power=None):
    pw=mv.power if power is None else power;name=mv.name
    if name in ('RETURN','FRUSTRATION'):pw=102
    if name=='HIDDEN_POWER':pw=70
    if name in ('ERUPTION','WATER_SPOUT'):pw=max(1,150*att.hp//att.maxhp)
    if name in ('LOW_KICK','GRASS_KNOT'):pw=next(p for limit,p in ((100,20),(250,40),(500,60),(1000,80),(2000,100),(10**9,120)) if dfn.weight<limit)
    if name=='GYRO_BALL':pw=min(150,25*spd(dfn)//max(1,spd(att))+1)
    if name in ('CRUSH_GRIP','WRING_OUT'):pw=1+120*dfn.hp//dfn.maxhp
    if name=='PUNISHMENT':pw=min(200,60+20*sum(max(0,x) for x in dfn.stage))
    if name=='TRUMP_CARD':
        pp=att.pp[att.active_idx] if 0<=att.active_idx<len(att.pp) else 0
        pw=(200,80,60,50,40)[min(4,pp)]
    if name=='SPIT_UP':pw=100*att.stockpile
    if ((name=='FACADE' and att.status in (BRN,PSN,PAR)) or (name=='WEATHER_BALL' and att.bt.weather and not weather_suppressed(att.bt)) or
        (name in ('REVENGE','AVALANCHE') and att.took_dmg) or (name=='ASSURANCE' and dfn.took_dmg) or
        (name=='PAYBACK' and dfn.acted) or (name=='BRINE' and dfn.hp*2<=dfn.maxhp) or
        (name=='WAKE_UP_SLAP' and dfn.status==SLP and not dfn.sub) or
        (name=='SMELLING_SALT' and dfn.status==PAR and not dfn.sub)):
        pw*=2
    mt=mtype_of(mv,att)
    if mt=='ELECTRIC' and att.charge_power:pw*=2
    if att.ability=='RECKLESS' and name in RECOILS:pw=pw*12//10
    if att.ability=='TECHNICIAN' and name!='STRUGGLE' and pw<=60:pw=pw*3//2
    if att.item and not att.embargo:
        if att.item.endswith('_PLATE') and mt==D['mons'][att.key]['types'][0]:pw=pw*12//10
        if att.item=='GRISEOUS_ORB' and not att.transformed and mt in ('GHOST','DRAGON'):pw=pw*12//10
    if not ignored(att,dfn) and ((dfn.ability=='THICK_FAT' and mt in ('FIRE','ICE')) or (dfn.ability=='HEATPROOF' and mt=='FIRE')):pw//=2
    if mt=='ELECTRIC' and (att.mud_sport or dfn.mud_sport):pw//=2
    if mt=='FIRE' and (att.water_sport or dfn.water_sport):pw//=2
    if att.hp<=att.maxhp//3 and (att.ability,mt) in {('OVERGROW','GRASS'),('BLAZE','FIRE'),('TORRENT','WATER'),('SWARM','BUG')}:pw=pw*3//2
    if not ignored(att,dfn) and dfn.ability=='DRY_SKIN' and mt=='FIRE':pw=pw*5//4
    if att.ability=='RIVALRY' and att.gender!='N' and dfn.gender!='N':pw=pw*(5 if att.gender==dfn.gender else 3)//4
    if att.ability=='IRON_FIST' and name in PUNCHES:pw=pw*12//10
    return max(1,pw)

def prepare_damage(att,dfn,mv,crit=False,power=None):
    """Snapshot roll-independent damage phases; preserve cartridge rounding order."""
    if mv.effect=='BEAT_UP':
        if att.status:return (0, 0, (), 1, 1)
        A=D['mons'][att.key]['atk'];Df=D['mons'][dfn.species_key]['defn']
        return ((((2*att.lvl//5+2)*mv.power*A//Df)//50+2)*(2 if crit else 1), 0, (), 1, 1)
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
    if mv.effect=='FUTURE_SIGHT':return (dmg, 2, (), 1, 1)
    if dfn.invuln and ((dfn.invuln=='fly' and mv.name in ('GUST','TWISTER')) or (dfn.invuln=='dig' and mv.name in ('EARTHQUAKE','MAGNITUDE')) or (dfn.invuln=='dive' and mv.name in ('SURF','WHIRLPOOL'))):dmg*=2
    stab = (4 if att.ability=='ADAPTABILITY' else 3) if mt in att.types else 2
    factors = tuple(type_mults(mt,*defensive_types(dfn,mt),dfn.foresight and mt in ('NORMAL','FIGHTING') or dfn.miracle_eye and mt=='PSYCHIC' or att.ability=='SCRAPPY' and mt in ('NORMAL','FIGHTING')))
    eff = 1
    for factor in factors:eff *= factor/10
    numerator, denominator = 1, 1
    if not ignore and dfn.ability in ('FILTER','SOLID_ROCK') and eff>1:numerator,denominator=3,4
    if att.ability=='TINTED_LENS' and eff<1:numerator*=2
    return dmg, stab, factors, numerator, denominator


def damage_at(prepared, roll):
    dmg, stab, factors, numerator, denominator = prepared
    if stab == 0:return dmg*roll//100  # Beat Up has no minimum-damage clamp.
    dmg = max(1,dmg*roll//100)*stab//2
    for factor in factors:
        if factor==0:return 0
        dmg=max(1,dmg*factor//10)
    return max(1,dmg*numerator//denominator)


def damage_rolls(att,dfn,mv,crit=False,power=None):
    prepared=prepare_damage(att,dfn,mv,crit,power)
    return tuple(damage_at(prepared,r) for r in range(85,101))


def calc_base(att,dfn,mv,crit=False,power=None,roll=100):
    return damage_at(prepare_damage(att,dfn,mv,crit,power),roll)


def acc_thresh(m,o,mv):
    st=stage_of(m,5)-stage_of(o,6,o.foresight or o.miracle_eye or m.ability=='UNAWARE',ignored(m,o))
    if o.ability=='UNAWARE' and not ignored(m,o):st=-stage_of(o,6,o.foresight or o.miracle_eye)
    st=max(-6,min(6,st));value=mv.acc*(3+max(0,st))//(3+max(0,-st))
    if m.ability=='COMPOUND_EYES':value=value*13//10
    if not ignored(m,o) and ((o.ability=='SAND_VEIL' and o.bt.weather=='sand') or (o.ability=='SNOW_CLOAK' and o.bt.weather=='hail')) and not weather_suppressed(o.bt):value=value*4//5
    if not ignored(m,o) and o.ability=='TANGLED_FEET' and o.conf:value//=2
    if m.ability=='HUSTLE' and mv.phys:value=value*4//5
    if getattr(m.bt,'gravity',0):value=value*5//3
    return max(1,min(100,value))

def multi_hits(rnd):
    r=rnd(8)&3
    return r+2 if r<2 else (rnd(8)&3)+2
