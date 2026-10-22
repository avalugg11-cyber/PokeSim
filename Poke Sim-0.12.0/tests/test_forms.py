"""Roster and cache compatibility for cosmetic form consolidation."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from forms import add_gen3, canonical_builds, collapse_cosmetic_forms, UNOWN

ROOT = Path(__file__).resolve().parents[1]

def mon(name, **extra):
    return dict(name=name, form='west', hp=80, atk=80, defn=80, spe=80,
                spa=80, sdf=80, types=['NORMAL'], lvl=[[1,'TACKLE']],
                evolutions=[], **extra)

def old_roster():
    mons = {k:mon(k.upper()) for k in ('unown','burmy','shellos','gastrodon','pichu')}
    for form in UNOWN[1:]:
        mons['unown'+form.lower()] = copy.deepcopy(mons['unown'])
    for base, forms in [('burmy', ['sandy','trash']),('shellos',['east']),('gastrodon',['east'])]:
        for form in forms:
            mons[base+form] = copy.deepcopy(mons[base])
    mons['burmy']['evolutions']=[['LEVEL',20,'WORMADAM'],['MALE_LEVEL',20,'MOTHIM']]
    mons['shellos']['evolutions']=[['LEVEL',30,'GASTRODON']]
    mons['shelloseast']['evolutions']=[['LEVEL',30,'GASTRODON_EAST']]
    for key in ('deoxysattack','deoxysdefense','deoxysspeed','wormadamsandy','wormadamtrash',
                'rotomheat','rotomwash','rotomfrost','rotomfan','rotommow',
                'giratinaorigin','shayminsky','arceusfire','pichuspikyeared'):
        mons[key]=mon(key.upper())
    return mons

class CosmeticFormsTests(unittest.TestCase):
    def test_collapse_is_idempotent_and_retains_battle_forms(self):
        mons=old_roster(); old=copy.deepcopy(mons)
        self.assertTrue(collapse_cosmetic_forms(mons))
        self.assertEqual(len(old)-len(mons),31)
        self.assertFalse(collapse_cosmetic_forms(mons))
        for key in ('unown','burmy','shellos','gastrodon'):
            self.assertEqual(mons[key]['name'],key.upper())
            self.assertNotIn('form',mons[key])
        for key in old:
            if key.startswith(('deoxys','wormadam','rotom','giratina','shaymin','arceus','pichu')):
                self.assertEqual(mons[key],old[key])

    def test_burmy_moves_still_reach_every_wormadam_cloak(self):
        from move_rules import level_pool
        mons=old_roster()
        mons['burmy']['lvl']=[[1,'PROTECT']]
        collapse_cosmetic_forms(mons)
        for key in ('wormadamsandy','wormadamtrash'):
            self.assertIn('PROTECT',level_pool({'mons':mons},key,50))
        self.assertIn(['MALE_LEVEL',20,'MOTHIM'],mons['burmy']['evolutions'])

    def test_legacy_add_unown_import_keeps_one_entry(self):
        # Reproduce the import statement from the reported older Gen4 loader.
        namespace = {}
        exec('from forms import add_unown', namespace)
        mons = old_roster()
        namespace['add_unown'](mons)
        self.assertEqual([k for k in mons if k.startswith('unown')], ['unown'])
        self.assertEqual(mons['unown']['name'], 'UNOWN')
        before = copy.deepcopy(mons)
        namespace['add_unown'](mons)
        self.assertEqual(mons, before)

    def test_gen3_build_adds_only_distinct_deoxys_forms(self):
        mons={'unown':mon('UNOWN'),'deoxys':mon('DEOXYS')}
        source=json.loads((ROOT/'gens/gen3/raw/forms.json').read_text())
        add_gen3(mons,source)
        self.assertEqual(set(mons),{'unown','deoxys','deoxysattack','deoxysdefense','deoxysspeed'})
        self.assertEqual(mons['deoxysattack']['atk'],180)

    def test_valid_old_caches_migrate_without_build_or_network(self):
        for gen in (3,4):
            with self.subTest(gen=gen), tempfile.TemporaryDirectory() as tmp:
                spec=importlib.util.spec_from_file_location(f'cache_loader_{gen}',ROOT/f'gens/gen{gen}/data.py')
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                path=Path(tmp)/'cache.json'
                old=dict(schema=module.SCHEMA,source_revision=module.REVISION,mons=old_roster(),moves={})
                path.write_text(json.dumps(old))
                with patch.object(module,'OUT',path), patch.object(module,'build',side_effect=AssertionError('must not rebuild')):
                    result=module.load()
                    self.assertEqual(len(result['mons']),len(old['mons'])-31)
                    self.assertEqual(json.loads(path.read_text()),result)
                    with patch.object(module,'write_json',side_effect=AssertionError('must be idempotent')):
                        self.assertEqual(module.load(),result)

    def test_saved_builds_prefer_canonical_and_preserve_unrelated(self):
        saved={'unown':['HIDDEN_POWER'],'unownb':['TACKLE'],
               'gastrodoneast':['WATER_GUN'],'pikachu':['THUNDER_SHOCK']}
        result=canonical_builds(saved,{'unown':{},'gastrodon':{}})
        self.assertEqual(result,{'unown':['HIDDEN_POWER'],'gastrodon':['WATER_GUN'],'pikachu':['THUNDER_SHOCK']})
        self.assertEqual(canonical_builds(result,{'unown':{},'gastrodon':{}}),result)
        self.assertIn('unownb',saved)

    def test_bundled_gen3_has_one_unown_and_four_deoxys(self):
        data=json.loads((ROOT/'gens/gen3/data/gen3.json').read_text())
        self.assertEqual(len(data['mons']),389)
        self.assertEqual([k for k in data['mons'] if k.startswith('unown')],['unown'])
        self.assertEqual(len([k for k in data['mons'] if k.startswith('deoxys')]),4)
