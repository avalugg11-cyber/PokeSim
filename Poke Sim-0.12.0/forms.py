"""Finite named form entries; ability-only transformations remain battle state."""
import copy
import string

UNOWN = list(string.ascii_uppercase) + ['EXCLAMATION','QUESTION']

# Only cosmetic variants of these species are aliases. Battle forms (including
# Rotom appliances, whose signature moves differ in-game) keep independent keys.
COSMETIC_ALIASES = {
    **{'unown' + form.lower(): 'unown' for form in UNOWN[1:]},
    'unowna': 'unown',
    'burmysandy': 'burmy', 'burmytrash': 'burmy',
    'shelloseast': 'shellos', 'gastrodoneast': 'gastrodon',
}
COSMETIC_SPECIES = frozenset(COSMETIC_ALIASES.values())

def collapse_cosmetic_forms(mons):
    """Normalize both fresh rosters and old caches, without rebuilding data.

    Keep the original base-species record and key. Do not deduplicate unrelated
    species with coincidentally identical stats, or discard battle forms.
    """
    before = copy.deepcopy(mons)
    # All Wormadam cloaks must still inherit Burmy's level-up moves after its
    # duplicate cloak records disappear. Mothim's existing branch is unchanged.
    if 'burmy' in mons:
        evos = mons['burmy'].get('evolutions', [])
        for kind, level, dest in list(evos):
            if ''.join(c for c in dest.lower() if c.isalnum()) == 'wormadam':
                for form in ('sandy', 'trash'):
                    branch = [kind, level, 'WORMADAM_' + form.upper()]
                    if 'wormadam' + form in mons and branch not in evos:
                        evos.append(branch)
    for alias, base in COSMETIC_ALIASES.items():
        if alias in mons and base in mons:
            del mons[alias]
    for key in COSMETIC_SPECIES & mons.keys():
        mons[key]['name'] = key.upper()
        mons[key].pop('form', None)
    # Cosmetic evolutionary branches still lead to the same retained competitor.
    for mon in mons.values():
        for evo in mon.get('evolutions', []):
            dest = ''.join(c for c in evo[2].lower() if c.isalnum())
            if dest in COSMETIC_ALIASES:
                evo[2] = COSMETIC_ALIASES[dest].upper()
    return mons != before

def add_unown(mons):
    """Legacy import compatibility; Unown remains one canonical competitor.

    Upgrade generation loaders together with this module: older rebuild paths
    can still enforce the obsolete expanded-roster count.
    """
    collapse_cosmetic_forms(mons)

def add_gen3(mons, source):
    for form, data in source['deoxys'].items():
        key='deoxys' if form=='normal' else 'deoxys'+form
        mon=copy.deepcopy(mons['deoxys'])
        mon.update(zip(('hp','atk','defn','spe','spa','sdf'),data['stats']))
        mon.update(lvl=data['lvl'],name='DEOXYS_'+form.upper(),form=form,base_species='deoxys')
        mons[key]=mon
    collapse_cosmetic_forms(mons)

def canonical_builds(saved, roster):
    """Retain the canonical build; recover an alias only when it is missing."""
    aliases = {a: b for a, b in COSMETIC_ALIASES.items() if b in roster}
    result = {k: v for k, v in saved.items() if k not in aliases}
    for alias, base in aliases.items():
        if alias in saved:
            result.setdefault(base, saved[alias])
    return result
