"""Gen 4 (Platinum) single-battle simulation, without badge boosts; required form items are fixed."""
from .base import *
from .effects import Effects, SELF_EFFECTS

class Battle(Effects):
    def __init__(self, sa, sb, rng, brain, rules=RULES, log=None):
        self.weather, self.weather_left = None, 0
        self.a, self.b = fresh(sa, self, True), fresh(sb, self, False)
        self.rnd = rng.getrandbits
        self.brain, self.rules, self.log = brain, rules, log
        self.res, self.turn, self.actor = None, 0, None
        self.action_number=0;self.gravity=self.trick_room=0;self.last_used=None

    def pick(self, m, o):
        if m.bide_left:return (MV["BIDE"],-1,"bide")
        if m.uproar and m.last_mv is not None and m.last_mv.effect=="UPROAR":
            return (m.last_mv,-1,"uproar")
        if m.recharge:
            return (None, -1, "recharge")
        if m.charge is not None:
            return (m.charge, -1, "charge2")
        if m.rampage_left > 0:
            return (m.rampage_mv, -1, "rampage")
        if m.rollout_left > 0:
            return (m.rampage_mv, -1, "rollout")
        if m.bide_left > 0:
            return (MV["BIDE"], -1, "bide")
        if m.encore_left > 0 and m.encore_mv in m.moves:
            i = m.moves.index(m.encore_mv)
            if m.pp[i] > 0:
                return (m.encore_mv, i, "normal")
        mv, idx = self.brain(m, o)
        return (mv, idx, "normal")

    def run(self):
        a, b, rnd = self.a, self.b, self.rnd
        entry=sorted(((a,b),(b,a)),key=lambda pair:-spd(pair[0]))
        for event in ('entry_trace','entry_weather','entry_intimidate','entry_download'):
            for m,o in entry:self.trigger_ability(m,o,event)
        self.update_forms()
        for t in range(1, self.rules.turn_limit + 1):
            self.turn = t
            for m in (a, b):
                m.flinch, m.took_dmg, m.took_phys = False, 0, None
                m.acted=False
            ca, cb = self.pick(a, b), self.pick(b, a)
            a.attack_move,b.attack_move=ca[0],cb[0]
            pa = ca[0].prio if ca[0] else 0
            pb = cb[0].prio if cb[0] else 0
            if pa != pb:
                a_first = pa > pb
            elif (a.ability=='STALL') != (b.ability=='STALL'):
                a_first=b.ability=='STALL'
            else:
                sa, sb = spd(a), spd(b)
                a_first = (rnd(8) < 128) if sa == sb else (sa < sb if self.trick_room else sa > sb)
            order = ((a, b, ca), (b, a, cb)) if a_first else ((b, a, cb), (a, b, ca))
            for self.action_number, (m, o, c) in enumerate(order):
                self.actor = m
                self.act(m, o, *c)
                m.acted=True
                self.apply_immunities()
                self.update_forms()
                if self.over():
                    return self.res
            if self.between_turns(self.residual_order()):
                return self.res
        self.res = 2
        return 2

    def can_move(self, m, o, mv, idx):
        rnd = self.rnd
        if m.status==SLP and m.ability!='SOUNDPROOF' and any(x.uproar for x in (self.a,self.b)):
            m.status=m.slp=0;m.nightmare=False
        if m.status == SLP:
            m.slp -= 2 if m.ability=='EARLY_BIRD' else 1
            if m.slp <= 0:
                m.status, m.nightmare = 0, False          
            elif mv is None or mv.effect not in ("SNORE", "SLEEP_TALK"):
                return False
        if m.status == FRZ:
            if (mv is not None and mv.name in ("FLAME_WHEEL", "SACRED_FIRE", "FLARE_BLITZ")) or rnd(8) < 51:   
                m.status = 0
            else:
                return False
        if m.ability=="TRUANT" and m.loaf:
            return False
        if m.recharge:
            m.recharge=False
            return False
        if m.flinch and m.ability!="INNER_FOCUS":
            return False
        if m.conf:
            m.conf -= 1
            if m.conf > 0 and rnd(8) < 128:
                self.self_hit(m)
                return False
        if m.attract and rnd(8) < 128:
            return False
        if m.status == PAR and m.ability!="MAGIC_GUARD" and rnd(16)%4==0:
            return False
        return True

    def self_hit(self, m):
        A, Df = estat(m, 0), estat(m, 1)
        d = ((2 * m.lvl // 5 + 2) * 40 * A // Df) // 50 + 2
        if d > 1:
            d = d * self.roll() // 100
        m.hp = max(0, m.hp - d)

    def act(self, m, o, mv, idx, mode):
        if not self.can_move(m, o, mv, idx):
            m.charge, m.invuln = None, None
            m.uproar = 0
            m.rampage_left = m.rollout_left = m.rollout_n = m.bide_left = 0
            return
        if mv is None:return
        if m.taunt and mv.kind=="status": return
        if m.torment and mv is m.last_selected and mode=="normal": return
        if self.other(m).imprison and mv in self.other(m).moves: return
        if mode == "normal" and idx >= 0:
            if idx == m.dis_idx:
                return                                     
            targets_foe=mv.effect not in SELF_EFFECTS or mv.effect in ("PAIN_SPLIT","TRANSFORM","PERISH_SONG")
            m.pp[idx] = max(0,m.pp[idx]-(2 if o.ability=="PRESSURE" and targets_foe else 1))
        if mode == "normal":
            if mv.effect not in ("PROTECT", "ENDURE", "DETECT"):
                m.protect_n = 0
            if mv.effect != "RAGE":
                m.rage = False
            if mv.effect != "FURY_CUTTER":
                m.fury_n = 0
            if mv.effect not in ("ROLLOUT",):
                m.rollout_left = m.rollout_n = 0
        m.acted=True
        m.active_idx=idx
        if mode=="normal":m.last_selected=mv
        m.dbond = m.dbond and mv.effect == "DESTINY_BOND"
        m.grudge = m.grudge and mv.effect == "GRUDGE"
        m.used[mv.name] = m.used.get(mv.name, 0) + 1
        m.last_mv = mv
        if mode == "charge2":
            m.charge, m.invuln = None, None
        if self.log is not None:
            self.L(f"T{self.turn} [{'a' if m is self.a else 'b'}] {m.name} uses {mv.name} (hp {m.hp}/{m.maxhp}) vs {o.name} (hp {o.hp}/{o.maxhp})")
        if mode == "bide":
            m.bide_left -= 1
            if m.bide_left == 0:
                dmg, m.bide_acc = m.bide_acc * 2, 0
                if dmg > 0:
                    self.deal(m, o, dmg, mv, True)
            return
        if mv.kind == "dmg":
            self.dmg_move(m, o, mv, mode)
            if mode == "rampage":
                m.rampage_left -= 1
                if m.rampage_left <= 0:
                    m.rampage_left = 0
                    self.confuse(m)
        else:
            self.status_move(m, o, mv, idx)
        if mv.name in ("FLAME_WHEEL", "SACRED_FIRE", "FLARE_BLITZ") and m.status == FRZ:
            m.status = 0
        self.last_used=m.last_mv

    def residual_order(self):
        # Field-end order is recomputed from speed, independently of move priority.
        a,b=self.a,self.b
        sa,sb=spd(a),spd(b)
        first=(sa<sb if self.trick_room else sa>sb) if sa!=sb else self.rnd(8)<128
        return (a,b) if first else (b,a)

    def apply_immunities(self):
        for m in (self.a,self.b):
            if ((m.ability=='IMMUNITY' and m.status==PSN) or
                (m.ability=='WATER_VEIL' and m.status==BRN) or
                (m.ability=='LIMBER' and m.status==PAR) or
                (m.ability=='MAGMA_ARMOR' and m.status==FRZ) or
                (m.ability in ('INSOMNIA','VITAL_SPIRIT') and m.status==SLP)):
                m.status=m.toxic=m.slp=0
            if m.ability=='OWN_TEMPO':m.conf=0
            if m.ability=='OBLIVIOUS':m.attract=False

    def between_turns(self, order):
        # Platinum: side timers/Wish/weather; all effects for each battler;
        # delayed attacks in slot order; Perish Song in residual speed order.
        for m in order:
            for field in ('reflect','lscreen','safeguard'):
                setattr(m,field,max(0,getattr(m,field)-1))
            if m.mist_left:
                m.mist_left-=1
                if not m.mist_left:m.mist=False
            if m.wish:
                m.wish-=1
                if not m.wish:self.heal(m,max(1,m.maxhp//2))
        if self.weather and self.weather_left>0:
            self.weather_left-=1
            if self.weather_left==0:self.weather=None
        self.update_forms()
        # Weather abilities resolve before Ingrain, Aqua Ring and poison/burn.
        if self.weather and not weather_suppressed(self):
            for m in order:
                hidden=m.invuln in ('dig','dive')
                if self.weather=='sand' and not hidden and not ({'ROCK','GROUND','STEEL'} & set(m.types)) and m.ability!='SAND_VEIL':self.indirect(m,max(1,m.maxhp//16))
                if self.weather=='hail' and not hidden:
                    if m.ability=='ICE_BODY':self.heal(m,max(1,m.maxhp//16),blocked=False)
                    elif 'ICE' not in m.types and m.ability!='SNOW_CLOAK':self.indirect(m,max(1,m.maxhp//16))
                if self.weather=='sun' and not hidden and m.ability in ('DRY_SKIN','SOLAR_POWER'):self.indirect(m,max(1,m.maxhp//8))
                if self.weather=='rain':
                    if m.ability=='DRY_SKIN':self.heal(m,max(1,m.maxhp//8),blocked=False)
                    if m.ability=='RAIN_DISH':self.heal(m,max(1,m.maxhp//16),blocked=False)
                    if m.ability=='HYDRATION':m.status=m.toxic=m.slp=0
                if self.over():return True
        self.gravity=max(0,self.gravity-1)
        for m in order:
            o=self.other(m)
            if m.ingrain:self.heal(m,max(1,m.maxhp//16))
            if m.aqua_ring:self.heal(m,max(1,m.maxhp//16))
            if m.ability=='SHED_SKIN' and m.status and self.rnd(16)%10<3:m.status=m.toxic=m.slp=0
            if m.ability=='TRUANT':m.loaf=not m.loaf
            if m.ability=='SPEED_BOOST':self.change_stage(m,2,1,m)
            if m.seeded and m.hp>0 and o.hp>0 and m.ability!='MAGIC_GUARD':
                amount=max(1,m.maxhp//8)
                self.indirect(m,amount)
                if m.ability=='LIQUID_OOZE':self.indirect(o,amount)
                else:self.heal(o,amount)
                if self.over():return True
            if m.status==PSN and m.ability=='POISON_HEAL':
                self.heal(m,max(1,m.maxhp//8),blocked=False)
                if m.toxic:m.toxic=min(15,m.toxic+1)
            elif m.status in (BRN,PSN):
                amount=max(1,m.maxhp//16)*m.toxic if m.status==PSN and m.toxic else max(1,m.maxhp//8)
                if m.status==BRN and m.ability=='HEATPROOF':amount=max(1,amount//2)
                self.indirect(m,amount)
                if m.toxic:m.toxic=min(15,m.toxic+1)
                if self.over():return True
            if m.nightmare:
                if m.status==SLP:self.indirect(m,max(1,m.maxhp//4))
                else:m.nightmare=False
                if self.over():return True
            if m.cursed:
                self.indirect(m,max(1,m.maxhp//4))
                if self.over():return True
            if m.trap_left:
                m.trap_left-=1
                m.trapped=m.trap_left>0
                if m.trap_left:self.indirect(m,max(1,m.maxhp//16))
                if self.over():return True
            if o.ability=='BAD_DREAMS' and m.status==SLP:
                self.indirect(m,max(1,m.maxhp//8))
                if self.over():return True
            if m.uproar:
                for x in order:
                    if x.status==SLP and x.ability!='SOUNDPROOF':x.status=x.slp=0;x.nightmare=False
                m.uproar-=1
            if m.dis_left:
                m.dis_left-=1
                if not m.dis_left:m.dis_idx=-1
            if m.encore_left:
                m.encore_left-=1
                if m.encore_mv not in m.moves or m.pp[m.moves.index(m.encore_mv)]==0:m.encore_left=0
            if m.lockon_left:
                m.lockon_left-=1
                if not m.lockon_left:m.lockon=False
            m.taunt=max(0,m.taunt-1)
            m.charge_power=max(0,m.charge_power-1)
            if m.yawn:
                m.yawn-=1
                if not m.yawn:self.inflict(m,SLP)
        for m in order:
            if m.future_left:
                m.future_left-=1
                if not m.future_left and m.future_by is not None:
                    acc=acc_thresh(m.future_by,m,m.future_move)
                    if acc>=100 or self.rnd(8)<acc*256//100:
                        dealt,hit_sub,_=self.deal(m.future_by,m,max(1,m.future_dmg*self.roll()//100),m.future_move,False,passive=True)
                        if dealt and not hit_sub and m.rage and m.hp>0:self.change_stage(m,0,1,m)
                    if self.over():return True
        for m in order:
            if m.perish:
                m.perish-=1
                if not m.perish:
                    m.hp=0
                    if self.over():return True
            for timer in ('heal_block','lucky_chant','magnet_rise','tailwind','embargo','slow_start'):
                setattr(m,timer,max(0,getattr(m,timer)-1))
            if m.roost_types:m.types=m.roost_types;m.roost_types=None
            m.protecting=m.enduring=m.magic_coat=m.snatch=False
        self.trick_room=max(0,self.trick_room-1)
        return False

    def update_forms(self):
        weather=None if weather_suppressed(self) else self.weather
        for mon in (self.a,self.b):
            if mon.species_key=='shayminsky' and mon.status==FRZ and not mon.sub:
                from .pool import pool
                build=dict(mon.build,moves=pool('shaymin',mon.lvl)[:1],ability='NATURAL_CURE')
                land=make_spec('shaymin',build,level=mon.lvl)
                mon.raw=land['raw'];mon.types=tuple(land['types']);mon.ability='NATURAL_CURE';mon.species_key='shaymin';mon.name='SHAYMIN_LAND'
            if mon.species_key=='castform':
                typ={'sun':'FIRE','rain':'WATER','hail':'ICE'}.get(weather,'NORMAL') if mon.ability=='FORECAST' else 'NORMAL'
                mon.types=(typ,typ)

    def trigger_ability(self,mon,opp,event,move_type=None,mv=None):
        ab=mon.ability
        if event in ("on_entry","entry_intimidate"):
            if ab=="INTIMIDATE":self.change_stage(opp,0,-1,mon)
        if event in ("on_entry","entry_weather"):
            if ab in ("DROUGHT","DRIZZLE","SAND_STREAM","SNOW_WARNING"):
                self.weather={"DROUGHT":"sun","DRIZZLE":"rain","SAND_STREAM":"sand","SNOW_WARNING":"hail"}[ab];self.weather_left=-1
        if event in ('on_entry','entry_trace'):
            if ab=='TRACE' and opp.ability not in ('TRACE','MULTITYPE','FORECAST'):mon.ability=opp.ability
        if event in ('on_entry','entry_download') and ab=='DOWNLOAD' and not opp.sub:
            defense=opp.raw[1]*(2+max(0,opp.stage[1]))//(2+max(0,-opp.stage[1]))
            special=opp.raw[4]*(2+max(0,opp.stage[4]))//(2+max(0,-opp.stage[4]))
            self.change_stage(mon,0 if defense<special else 3,1,mon)
        if event=="defend_hit":
            if move_type=='GROUND' and mon.magnet_rise and not self.gravity and not mon.ingrain:return "immune"
            if ignored(opp,mon):return "continue"
            if ab=="LEVITATE" and move_type=="GROUND" and not self.gravity and not mon.ingrain:return "immune"
            if ab=="WONDER_GUARD" and (mv is None or mv.name!="FIRE_FANG") and move_type!="TYPELESS" and calc_effectiveness(move_type,mon)<=1:return "immune"
            if (ab,move_type) in (("VOLT_ABSORB","ELECTRIC"),("WATER_ABSORB","WATER"),("DRY_SKIN","WATER")):
                self.heal(mon,mon.maxhp//4);return "immune"
            if ab=='MOTOR_DRIVE' and move_type=='ELECTRIC':self.change_stage(mon,2,1,mon);return 'immune'
            if ab=="FLASH_FIRE" and move_type=="FIRE" and mon.status!=FRZ:mon.flash_fire=True;return "immune"
        return "continue"

    def contact_effects(self,m,o,mv,hit_sub):
        if hit_sub or m.hp<=0:return
        if o.ability=='AFTERMATH' and o.hp<=0 and mv.contact and not any(x.ability=='DAMP' for x in (m,o)):self.indirect(m,max(1,m.maxhp//4))
        if not mv.contact:return
        if o.ability=="ROUGH_SKIN":self.indirect(m,max(1,m.maxhp//8))
        if o.ability in ("STATIC","POISON_POINT","FLAME_BODY") and self.rnd(16)%3==0:
            self.inflict(m,{"STATIC":PAR,"POISON_POINT":PSN,"FLAME_BODY":BRN}[o.ability],o,ability=True)
        if o.ability=="EFFECT_SPORE" and self.rnd(16)%10<3:self.inflict(m,(SLP,PSN,PAR)[self.rnd(8)%3],o,ability=True)
        if o.ability=="CUTE_CHARM" and m.ability!="OBLIVIOUS" and self.rnd(16)%3==0 and {m.gender,o.gender}=={"M","F"}:m.attract=True


def calc_effectiveness(typ,mon):
    value=1
    for x in type_mults(typ,*mon.types,mon.foresight):value*=x/10
    return value
