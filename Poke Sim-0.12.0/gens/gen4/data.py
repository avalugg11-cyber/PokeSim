"""Offline Platinum extraction from pinned pret JSON; no later-gen stat updates."""
import copy
import json
import os
from pathlib import Path
from storage import write_json
from forms import collapse_cosmetic_forms
from move_rules import BABIES

REVISION='e038244ff792439e9200604736dc30eb38940bb3'
HERE=Path(__file__).resolve().parent
RAW=HERE/'raw'/'platinum.json'
OUT=HERE/'data'/'gen4.json'
SCHEMA=2

def norm(s):return ''.join(c for c in s.lower() if c.isalnum())

def build():
    raw=json.loads(RAW.read_text());mons={};moves={};eggs={}
    assert raw['revision']==REVISION
    def species(name,d,ndex,base=None):
        stats=d['base_stats'];growth=d['exp_rate'].removeprefix('EXP_RATE_')
        growth={'MEDIUM_FAST':'MEDIUM_FAST'}.get(growth,growth)
        gender=d['gender_ratio'];gender='MON_GENDERLESS' if 'NO_GENDER' in gender else 'MON_FEMALE' if gender.endswith('FEMALE_ONLY') else gender
        if gender=='GENDER_RATIO_FEMALE_100':gender='MON_FEMALE'
        evos=[]
        for e in d.get('evolutions',[]):
            dest=e[-1].removeprefix('SPECIES_');value=e[1] if len(e)>2 and isinstance(e[1],int) else 0
            evos.append([e[0],value,dest])
        source=d.get('pokedex_data',{});base_data=raw['pokemon'].get((base or name.lower())+'/data.json',{})
        weight=source.get('weight_pounds',base_data.get('pokedex_data',{}).get('weight_pounds',1))
        result=dict(name=name,national_dex=ndex,base_species=base or norm(name),
            hp=stats['hp'],atk=stats['attack'],defn=stats['defense'],spe=stats['speed'],spa=stats['special_attack'],sdf=stats['special_defense'],
            types=[t.removeprefix('TYPE_') for t in d['types']],abilities=[a.removeprefix('ABILITY_') for a in d['abilities'] if a!='ABILITY_NONE'],
            growth='GROWTH_'+growth,gender=gender,weight=round(weight*4.5359237),
            lvl=[[lv,m.removeprefix('MOVE_')] for lv,m in d.get('learnset',{}).get('by_level',[])],evolutions=evos)
        return result
    for ndex,s in enumerate(raw['species_order'],1):
        name=s.removeprefix('SPECIES_');slug=name.lower();d=raw['pokemon'][slug+'/data.json'];key=norm(name)
        mons[key]=species(name,d,ndex)
        if key in BABIES:
            eggs[key]=[m.removeprefix('MOVE_') for m in d.get('learnset',{}).get('egg_moves',[])]
        for path,fd in raw['pokemon'].items():
            if path.startswith(slug+'/forms/') and path.endswith('/data.json'):
                form=path.split('/')[2]
                if slug in ('castform','cherrim'):continue
                fkey=norm(name+form);mon=species(name+'_'+form.upper(),fd,ndex,key)
                mon['form']=form;mons[fkey]=mon
    eggs['pichu'].append('VOLT_TACKLE')
    mons['giratina']['name']='GIRATINA_ALTERED';mons['shaymin']['name']='SHAYMIN_LAND';mons['deoxys']['name']='DEOXYS_NORMAL';mons['wormadam']['name']='WORMADAM_PLANT'
    mons['giratinaorigin']['required_item']='GRISEOUS_ORB'
    for t,item in [('FIGHTING','FIST'),('FLYING','SKY'),('POISON','TOXIC'),('GROUND','EARTH'),('ROCK','STONE'),('BUG','INSECT'),('GHOST','SPOOKY'),('STEEL','IRON'),('FIRE','FLAME'),('WATER','SPLASH'),('GRASS','MEADOW'),('ELECTRIC','ZAP'),('PSYCHIC','MIND'),('ICE','ICICLE'),('DRAGON','DRACO'),('DARK','DREAD')]:
        m=copy.deepcopy(mons['arceus']);m.update(name='ARCEUS_'+t,types=[t,t],form=t.lower(),base_species='arceus',required_item=item+'_PLATE')
        mons['arceus'+t.lower()]=m
    mons['arceus']['name']='ARCEUS_NORMAL'
    spiky=copy.deepcopy(mons['pichu']);spiky.update(name='PICHU_SPIKY_EARED',base_species='pichu',form='spiky_eared',gender='MON_FEMALE',evolutions=[])
    mons['pichuspikyeared']=spiky
    collapse_cosmetic_forms(mons)
    # Names/power/accuracy/class/effects are original Platinum metadata.
    for name,d in raw['moves'].items():
        native=d['effect']['type'];effect=raw['effect_map'].get(native,native.removeprefix('BATTLE_EFFECT_'))
        flags=d['flags']
        moves[name]=dict(effect=effect,source_effect=native,type=d['type'].removeprefix('TYPE_'),category=d['class'].removeprefix('CLASS_'),
            power=d['power'],acc=d['accuracy'],pp=d['pp'],chance=d['effect']['chance'],priority=d['priority'],
            contact='MOVE_FLAG_MAKES_CONTACT' in flags,protect='MOVE_FLAG_CAN_PROTECT' in flags,
            snatch='MOVE_FLAG_CAN_SNATCH' in flags,reflectable='MOVE_FLAG_CAN_MAGIC_COAT' in flags,
            sound=name in {'GROWL','ROAR','SING','SUPERSONIC','SCREECH','SNORE','UPROAR','METAL_SOUND','GRASS_WHISTLE','HYPER_VOICE','PERISH_SONG','HEAL_BELL','BUG_BUZZ','CHATTER'})
    if len(mons)!=522 or len(moves)!=467:raise ValueError(f'incomplete Platinum data: {len(mons)} entries/{len(moves)} moves')
    import re
    text=(HERE/'raw'/'battle_lib.c').read_text().split('static const u8 sTypeMatchupMultipliers[][3] = {',1)[1].split('};',1)[0]
    factors={'NOT_VERY_EFF':5,'SUPER_EFF':20,'IMMUNE':0}
    chart=[[a,b,factors[f]] for a,b,f in re.findall(r'\{ TYPE_(\w+), TYPE_(\w+), TYPE_MULTI_(\w+) \}',text)]
    if len(chart)!=len(raw['chart']):raise ValueError('incomplete type chart')
    return dict(schema=SCHEMA,source_revision=REVISION,mons=mons,moves=moves,baby_eggs=eggs,chart=chart)

def load():
    try:
        result=json.loads(OUT.read_text())
        if result.get('schema')==SCHEMA and result.get('source_revision')==REVISION:
            if collapse_cosmetic_forms(result['mons']):
                write_json(OUT,result)
            return result
    except (OSError,ValueError):pass
    result=build();write_json(OUT,result);return result
