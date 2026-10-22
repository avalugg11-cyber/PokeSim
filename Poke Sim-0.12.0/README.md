# Pokémon solo tournament simulator — build 0.12.0

Local Python application for Gen 1 (Red/Blue/Yellow), Gen 2 (Crystal), Gen 3 (Emerald + forms), and Gen 4 (Platinum + forms). It seeds builds, searches for improvements, runs a round robin, and exports rankings. Bundled Gen 1–3 data caches allow offline use. Gen 4 requires its matching cache or the original Platinum raw inputs. No Python packages or accounts are required.

## Source checkout status

This checkout was restored from supplied source attachments. Gen 1–3 caches
and the supplied `gens/gen3/raw/forms.json` are included. Gen 2/3 caches were
built from the pinned Crystal/Emerald sources and checked with every default
species/form build. Gen 4 still requires `gens/gen4/data/gen4.json`, or both
`gens/gen4/raw/platinum.json` and `gens/gen4/raw/battle_lib.c` to rebuild it.
Original reference suites and platform launchers were not supplied.
The mechanics regressions use small synthetic datasets; broader default-roster
smoke checks do not establish exhaustive cartridge correctness.

## Start

Use Python 3.10 or newer. Automated checks use Python 3.14.4 on Linux. Windows operation was confirmed by the user; macOS is outside the current verification scope.

```bash
python3 app.py
```

The dashboard opens at `http://127.0.0.1:8765`. Choose a generation and preset, then select **Start run**. The local server binds to the loopback interface. Platform launchers are available in the original distribution; they are absent from this source checkout.

Outputs are stored in `out/gen1/`, `out/gen2/`, `out/gen3/`, or `out/gen4/`. Builds persist between runs; **Fresh start** is unchecked by default and backs up the previous builds. **Skip search** always preserves saved builds, including when combined with Fresh start; it seeds defaults only when no saved file exists. When upgrading from a build with TM/HM moves, enable **Fresh start** (CLI: `--fresh`) to seed new legal sets. Continuing or battling with incompatible saved sets returns an error; files are not silently rewritten. **Stop** terminates the pipeline and its worker processes. Only one dashboard run may be active at once.

## Command line

```bash
python3 pipeline.py --gen 4 --preset quick --procs 2
python3 pipeline.py --gen 4 --skip-search --games 5 --seed 7 --procs 2
python3 search.py --gen 4 --passes 1 --sample 8 --procs 2
python3 tournament.py --gen 4 --games 5 --seed 7 --procs 2
```

For a short integration run in a separate directory:

```bash
python3 pipeline.py --gen 4 --limit 4 --out out/smoke --passes 1 --sample 2 --screen-games 1 --confirm-games 1 --games 1 --procs 2 --seed 7 --fresh
```

`--limit` restricts the field. Use a separate `--out` directory to preserve full-field builds and rankings. A full search across 522 Gen 4 entries can be expensive; runtime depends on candidate counts, hardware, and the selected preset. No speed estimate is guaranteed.

## Rules and search

- Complete generation rosters: 151 species in Gen 1, 251 in Gen 2, 386 in Gen 3 (389 entries with forms), and 493 in Gen 4 (522 entries with forms). Version exclusivity does not restrict the field.
- All Pokémon battle at level 50. Movesets may use their full initial and level-up learnsets, including moves learned above level 50 and retained pre-evolution level-up moves. There is no learn-level cutoff; evolution may be delayed. TM, HM, tutor, event and transfer moves are excluded, even when the species can learn them in the games.
- Egg moves are allowed only for baby species: Pichu, Cleffa, Igglybuff, Togepi, Tyrogue, Smoochum, Elekid and Magby in Gen 2/3, plus Azurill and Wynaut in Gen 3. Gen 4 adds Budew, Chingling, Bonsly, Mime Jr., Happiny, Munchlax, Riolu, and Mantyke. A baby without listed egg moves gains none. Spiky-eared Pichu has the ordinary Pichu level-up pool and no event or egg grants. These egg exceptions do not carry into evolved species' build pools. Gen 3/4 Pichu also has the special bred Volt Tackle move.
- Gen 1 has no tournament-specific move bans, but the acquisition rule still applies. Double Team is available to natural learners; Toxic and Mimic are absent from Gen 1 saved-build pools because no species learns them naturally in this generation. They remain implemented for in-battle called/copied moves. Automatic Mimic selection follows link-battle behavior.
- One active Pokémon per side, no bench and no freely chosen held items. Gen 4 form-required items are fixed to their entry: Griseous Orb for Giratina Origin and the matching plate for typed Arceus. Both fainting is a draw; the turn limit is 50.
- Pairings alternate sides. Win percentage is wins divided by all games; draws add no wins. Bradley–Terry ratings break win-total ties. Equal win totals share the best tier reached by that tie group.
- Gen 1/2 retain the supplied rules: perfect DVs and 11,000 stat experience. Gen 1 retains its player-side badge mechanics. Gen 2 has no accumulating badge glitch; its sleep counter is 2–7.
- Gen 3/4 use perfect IVs (31), all 25 natures, species abilities, and EVs limited to 255 per stat and 510 total. All growth groups use level 50 for stats and level-dependent battle mechanics; experience budgets no longer determine level. No Gen 3/4 badge boosts apply.
- Gen 3 pools use pinned Emerald level-up and baby egg data. Smeargle starts with Sketch; imported permanent Sketch sets are excluded by the acquisition rule. Sketch, Mimic, Metronome and other called/copied moves still work during battle. Minimum evolution/capture levels are not enforced, to keep every species in the field at the format's fixed level 50. Full breeding-parent and egg-move combination legality is not modeled.
- Gen 3/4 search moves, abilities, natures, preset EV spreads, and transfers of 4 or 32 EVs between stats. Screening and confirmation use separate deterministic samples. This is a heuristic search; a pass with no accepted changes does not establish a globally optimal build.
- Hidden Power is Dark/70 with the fixed perfect Gen 3/4 IVs. Return and Frustration each use their maximum power as a simulator convention. Gen 4 Chatter assumes a strongest recorded cry (31% confusion chance).
- Gender is fixed per species for this simulation: male where available, female for female-only species, otherwise genderless. It is not sampled per individual.

## Forms and Platinum rules

Named forms have independent saved-build keys, search candidates, tournament rows, and battle-viewer choices. Forms with no difference in stats, learnsets or typing share one competitor. Unown letters, Burmy cloaks, and east/west Shellos and Gastrodon use their original base-species keys. Gender differences, shininess and Spinda spot patterns are not named forms.

- Gen 3: four Deoxys forms and one Unown entry. Deoxys uses each form's original Ruby/FireRed/LeafGreen/Emerald level-up data under Emerald battle mechanics.
- Gen 4: those forms plus Wormadam cloaks, Rotom appliances, Giratina Altered/Origin, Shaymin Land/Sky, all 17 Arceus types, and HGSS's Spiky-eared Pichu. All use Platinum battle rules and Platinum level-up acquisition. All Rotom appliances are Electric/Ghost in Gen 4. Their appliance-interaction signature moves are excluded because they are not level-up or baby egg moves.
- Castform/Cherrim ability-driven changes stay within battle state. Shaymin Sky can revert to Land when frozen in battle. Later-generation forms such as Megas and Primals will belong to their introduction generations.
- Required items are not search dimensions. Their boosts and Embargo suppression are modeled; required items appear in exports and battle/results displays. Embargo leaves the selected form's typing intact; it can suppress Judgment's plate-derived move type.
- Gen 4 has the physical/special split, Platinum's 60%-accuracy Hypnosis, native move priorities, and dedicated effects/abilities including Trick Room, Gravity, Roost, Mold Breaker, Simple, Unaware, Download, Magic Guard and Poison Heal. Its engine has independent move objects and battle state.

Existing Gen 3/4 caches automatically collapse cosmetic duplicates without downloading data. Fresh start is unnecessary: canonical saved builds are retained, and an old variant build is recovered if its canonical build is missing. New runs omit cosmetic aliases; historical results remain historical and need a new tournament for the revised field. Existing compatible builds are not reoptimized merely by loading them.

Example Gen 3 Pichu build JSON:

```json
{"moves":["VOLT_TACKLE","DOUBLE_SLAP","THUNDER_WAVE","THUNDER_SHOCK"],"ability":"STATIC","nature":"ADAMANT","evs":{"hp":4,"atk":252,"spe":252}}
```

Actual moves and abilities must be legal for the selected species and generation; learn levels do not restrict moves. Old move-array imports are normalized to a neutral nature, first species ability, and zero EVs.

## Files

- `gens/`: independent generation engines, brains, pools, and data loaders.
- `search.py`, `tournament.py`, `pipeline.py`: search and ranking workflow.
- `app.py`, `ui.html`: local dashboard, live events, and new seeded battle simulations using current builds. The viewer is not a replay of a recorded tournament match. HP snapshots precede each logged action.
- `storage.py`, `exports.py`, `config.py`: atomic file writes, JSON/CSV exports, and input validation.
- `out/genN/movesets.json`: saved builds; `results.json`, `results.csv`, and `type_stats.csv`: exports. CSV exports include Gen 3/4 EVs and fixed form items.

Data is extracted from pinned public pret disassemblies. Gen 3 source revision: `731ad5bfd6e6f265508d0efcca0ba42f9dcf5881`. Gen 1/2 revisions are pinned in their loaders. Preserve the bundled `data/` directories for offline use. Rebuilding a missing Gen 1/2 cache requires internet; Gen 3/4 extraction sources are bundled under `raw/`.

## Verification

```bash
python3 -m unittest discover -s tests -v
node tests/check_ui.cjs
python3 tests/process_probe.py
python3 tests/benchmark.py --battles 1000
```

The included regression suite covers the repaired mechanics, all four decision
policies, missing move slots, candidate equivalence, ranking cache invalidation,
time budgets, exports and saved-build preservation. The Node check exercises the
actual dashboard script using a fake DOM and controlled responses. The process
probe checks serial/spawn equivalence for rankings and scoring across all four
generations, cache reuse and worker termination at a deadline.

The benchmark compares corrected engines with and without estimate reuse on
synthetic data, checking winner, final HP and turn count for every seed. It does
not predict full-roster runtime. The original distribution's 91-test suite,
source-damage fixtures and full-field checker were not supplied and have not
been rerun here.

## Search performance and behavior

- Damage estimates are reused within a decision only where battle state is
  unchanged. Temporary screen and type probes recalculate their estimates.
- Gen 4 snapshots damage phases once, applying each random roll with the original
  integer rounding order. Decision estimates reuse the snapshot for KO probabilities.
- Screening promotes four distinct alternatives. Exact early rejection stops a
  candidate only when its remaining possible wins cannot beat the current fourth
  finalist; stable tie ordering matches exhaustive scoring.
- Battle-equivalent candidates are scored once. Species, move order, ability,
  item, gender, typing, stats, nature modifiers and EV inputs remain in identity.
- Legal Gen 1/2 movepools are cached, and unused battle log strings are avoided.
- Screening samples opponents uniformly without replacement. Confirmation draws
  an independent sample and battle seed. Every species has equal inclusion
  probability, matching the final tournament's equal-opponent objective.
- Search no longer runs a preliminary all-pairs tournament each pass. The final
  tournament remains a complete round robin. `PairCache` is still available for
  callers explicitly repeating tournaments with unchanged pairings.
- Worker pools receive the caller's rules and restart when generation/rules change.
  The pool stays alive between species/passes. Counts report completed scoring
  battles and can omit partial work interrupted by a deadline.
- Search checkpoints `<movesets path>.search.json`: seed, next evidence pass,
  stability count, configuration/data identity and build fingerprint. Resume
  advances its evidence; changing builds/settings invalidates the checkpoint.
  `pipeline.py --fresh` resets it. `--seed` controls search and final tournament;
  with no explicit seed, search retains its checkpoint seed and the tournament
  gets a new seed. Standalone `search.py --seed` controls search too.
- Two consecutive complete passes with no accepted change report stability.
  Quick mode (one pass) can stop before this criterion. This is sampled local
  stability, not statistical proof or a global optimum. The acceptance margin
  is an improvement threshold, not a significance test.
- Time budgets are checked between battles, with parent-side worker timeouts.
  The final tournament remains outside the search budget. An active serial
  battle and worker startup/cleanup can delay stopping slightly.
- Short builds can gain missing move slots. Each species accepts at most one
  improvement per pass. Species without distinct alternatives skip scoring.
  A limited search preserves saved builds outside its selected field.

### Measure the current optimizations

```bash
python3 tests/efficiency_benchmark.py --baseline /path/to/pre-change/source --output efficiency.json
```

Use a separate pre-change source tree with its tests/fixtures.py and Gen 1 cache.
The script reports three alternating timing pairs, verifies battle outcomes and
exact screening finalists, and compares two-pass searches on a 12-species Gen 1
field against fixed opponents on independent seeds. Timings exclude imports.
This benchmark does not measure full Gen 4 convergence or establish optimal builds.

## Limits

This is a repaired simulator, not a verified cartridge emulator. The test suite does not establish exhaustive effect accuracy, turn-order fidelity in every simultaneous event, RNG parity, or stable full-roster search convergence. The supplied Gen 1/2 engines retain additional uncalibrated behavior. Search deadlines cover candidate battles, with the stopping granularity described above. The source-damage harness isolates selected C routines with format-specific stubs; it is not a full cartridge battle or RNG check. The Gen 3/4 decision policies use damage estimates and selective tactical rules; they are not optimal policies for every available move.

Moves requiring allies, switching, escape, or items fail or have no additional effect in this format (Assist, Helping Hand, Follow Me, Baton Pass, Roar, Whirlwind, Teleport, Spikes, Trick, Recycle). Damage-only item effects such as Knock Off and Thief retain their damage. Non-battle abilities and abilities requiring switches, allies, or items have no effect here. Multi-hit contact, Transform, called moves, and residual ordering have targeted source-derived regressions; exhaustive cartridge comparison remains outstanding. Nature Power/Secret Power/Camouflage assume a plain indoor battlefield. Detailed repairs are listed in `HANDOFF.md`.

### Updating an existing installation

Stop the server before extracting an update. Replace the application files
as a set, including `forms.py`, `gens/gen3/data.py`, and `gens/gen4/data.py`.
Keep your `out/` directory and any additional `gens/*/raw/` or `gens/*/data/`
assets; the update ZIP does not contain every Gen 4 input. Restart the server
after extraction. Mixing older loaders with a newer forms helper can cause
`ImportError: cannot import name 'add_unown'` or obsolete roster-count failures.
The legacy import is now supported, but the updated loaders are still needed
for cosmetic cache migration and the revised roster size.

### Level-50 format change (0.12.0)

This intentionally replaces the old 156,250-EXP format and its learn-level cutoff.
All Gen 1–4 competitors use level 50, with all natural level-up moves available.
Articuno can therefore use Blizzard (51), Agility (55), and Mist (60) at level 50.
TM/HM, tutor, event and transfer moves remain excluded, and baby egg-move rules
are unchanged. Four distinct moves remain the maximum. Level 50 also governs
level-dependent damage and accuracy, alongside stats, as required by battle rules.
Existing compatible saved builds remain valid but need further search to explore
the expanded pools. Fresh start is optional. Engine version changes reset search
evidence automatically; rerun search and tournaments for rankings in this format.
Historical results keep their original levels/rankings until replaced by a new run.
