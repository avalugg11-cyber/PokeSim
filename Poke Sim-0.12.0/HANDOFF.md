## Fixed level-50 format (0.12.0, current)

- User-authorized contract change: all species/forms across Gens 1–4 battle at
  level 50; full natural learnsets are available regardless of learn level.
  Supersedes the prior EXP budget and move-level cutoff in historical notes.
- TM/HM/tutor/event/transfer exclusions and baby-only egg rules are preserved.
- All engines are 0.12.0 to invalidate old search evidence. Brain policies remain
  0.10.2. Existing legal builds can resume; rerun search/tournaments. Fresh start
  is optional. Old results are historical, not converted to the new format.
- Explicit non-50 make_spec level overrides now fail rather than silently running
  a different format. Pool level arguments remain accepted but do not filter.

## Legacy loader import repair

Restored forms.add_unown as a compatibility wrapper that keeps one Unown.
Older generation loaders must still be replaced with the matching current
loaders: their rebuild counts/cache behavior predate cosmetic consolidation.
Stop/restart the server around an update; preserve out/ and extra raw/data assets.

## Cosmetic roster consolidation (current)

- Gen 3 now has 389 competitors; Gen 4 has 522. Unown, Burmy, Shellos and
  Gastrodon cosmetic variants share their base key. Earlier counts below describe
  historical validations before this roster change.
- Existing valid caches migrate locally, retaining schema/source provenance.
  Canonical saved builds win over aliases; limited searches preserve unrelated
  builds while removing obsolete cosmetic keys. Old results need a new tournament.
- Deoxys, Wormadam, Rotom, Giratina, Shaymin and typed Arceus remain distinct.
  Spiky-eared Pichu remains distinct because its acquisition pool excludes baby
  egg moves. Rotom signature moves remain excluded by the existing format rules.

# Follow-up confirmed mechanics audit — build 0.10.2

- All generations: priority finishers must be able to connect. Gen 1's separate
  guaranteed-KO rule also checks semi-invulnerability.
- Gen 2–4: Lock-On targets the opponent and respects Substitute/accuracy checks;
  always-hit policy estimates respect Fly/Dig, retaining Lock-On/No Guard bypasses.
- Gen 2: drain moves fail against Substitute. Thunder reaches Fly and Fissure
  reaches Dig; Crystal's locked ground-move/Fly bug remains. Rage multiplies
  post-STAB/type damage, resets on selecting another move, and caps its multiplier.
  Gust/Twister/Earthquake/Magnitude double after damage variation; policy estimates
  and KO rolls include this bonus.
  Accuracy/evasion ratios now apply separately with Crystal rounding/Foresight
  behavior; OHKO byte accuracy adds two per level and applies stages. Thunder
  in sun changes base accuracy to 128 before stage modifiers.
- Gen 3–4: Soundproof and Dream Eater/Substitute are reflected in damage policy.
- Gen 3: Bide stores for two turns and releases on the third, consuming PP once.
- Gen 4: Mold Breaker cannot bypass Mist; OHKO policy respects semi-invulnerability
  and the attacker's level, preserving No Guard/Lock-On exceptions.
- Focused regressions reference pinned Crystal/Emerald/Platinum routines. Gen 1
  Swift and drain/Substitute cartridge quirks are preserved. See tests/test_audit.py.
- These changes invalidate old scoring evidence through engine/brain versions.
  Existing saved builds can resume and be reevaluated under the repaired mechanics.
- Bundled supplied Gen 1 cache and forms.json; newly generated Gen 2/3 caches
  match pinned source metadata. All 251 Gen 2 and 416 Gen 3 default builds load;
  two-opponent smoke coverage completes 502/832 actual-source battles.
- All 60 Python regressions and all-generation spawn checks pass. The 990-battle
  Gen 1 native-move smoke also passes. These checks do not establish exhaustive
  cartridge fidelity, full-field convergence, or globally optimal builds.
- Gen 4's full real-roster validation needs its missing Platinum dataset.
  Native Windows/Python 3.15 verification remains outstanding. Earlier timing
  results are historical, not fresh measurements of this mechanics update.

# Accuracy and efficiency update — build 0.10.1

- Gen 1–4 multi-hit KO estimates aggregate damage, respecting shared rolls in
  Gen 1/2, independent rolls in Gen 3/4, Triple Kick accuracy, Endure and Gen 1/2
  Substitute boundaries. Contact/Color Change estimates are conservative; crits
  and a complete branching battle-state forecast remain outside this heuristic.
- Gen 3/4 Twineedle respects Shield Dust; Gen 4 respects Mold Breaker and doubles
  Poison Fang/Twineedle secondary chances with Serene Grace. Gen 4 Skill Link
  now forces five ordinary multi-hits. Frozen Flash Fire no longer causes the
  Gen 3/4 decision policy to discard damaging Fire moves.
- Gen 4 damage preparation is reused across rolls and engine damage calls,
  retaining operation order. A 600-state, all-16-roll comparison matches the
  pre-optimization formula; this is arithmetic regression coverage, not a new
  independent cartridge calibration.
- Search removes preliminary round robins, uses uniform independent screening/
  confirmation samples, distinct finalists and exact early candidate rejection.
  Checkpoints advance resumed seeds; two unchanged passes establish sampled
  stability. Pools receive caller rules under spawn and refresh after changes.
- Generation imports are lazy. Missing-data errors now return JSON to the
  dashboard instead of terminating an HTTP request without an explanation.
- Added reproducible `tests/efficiency_benchmark.py`. Local synthetic Gen 4
  battles were 14.7% faster; exact screening 22–30% faster across Gen 1–4.
  Gen 1–3 basic battle timings were roughly unchanged. The 12-species Gen 1
  holdout result improved from 51.1% to 52.7–53.8% wins across three new seeds.
  These are bounded measurements, not a full-roster runtime forecast.
- Gen 1 cache is included. Real Gen 2–4 data/reference suites and native Windows
  verification remain outstanding. Earlier source-oracle/full-roster claims
  below are inherited documentation and were not reproduced in this workspace.

## Previous supplied notes and prior fixes

## Fixes and optimization — 2026-10-21

Source restored from supplied attachments; Gen 1 cache has since been supplied. Original reference tests and Gen 2–4 datasets remain absent.

- Repaired Gen 3/4 Uproar duration/interruption, Gen 4 Wake-Up Slap status and
  Substitute handling, Gen 3 Serene Grace self-boost/poison branches, Gen 2 Beat Up
  base-stat/status/type handling and transformed target identity, and Gen 2/3
  Lock-On with OHKO moves (including decision-policy probabilities).
- Added missing move slots to neighbor search in all generations; repaired small
  field tiers, saved-set preservation for Skip search, dashboard stale responses
  and reset of time-budget state. Fresh start is unchecked by default.
- Reuse decision-local estimates, immutable legal pools and exact unchanged
  preliminary pairs; deduplicate scoring while retaining form-recalculation
  inputs, move order and all combat identity. Avoid unused log formatting.
- Cap actual opponents at sample; this changes small-sample search trajectories.
  No-change remains a sampled result; one change per species/pass still applies.
- Search counts include completed preliminary battles, pools no longer coexist,
  and cooperative/parent-side deadlines interrupt ranking and scoring.
- New synthetic regressions and spawn probe require no datasets/network. See
  README for commands and validation limits. Original reference suites and
  real-roster performance remain unverified.

# Repair handoff — build 0.9.0

This standalone project was assembled from the supplied attachments. Original attachments were preserved.

## Build 0.9 changes

- Added independent Platinum Gen 4 engine/data/pool/brain with all 493 species and 60 additional named forms (553 entries). Gen 3 adds 30 named forms (416 entries). All entries participate separately in save/load, search, rankings, exports and battle selection.
- Preserved initial/level-up/pre-evolution acquisition and baby-only eggs. No appliance-interaction grants, TM/HM/tutor/event imports or permanent imported Sketch sets.
- Added the physical/special split, original Platinum damage phases, new move/status/field effects, abilities, fixed form items and form changes. Required items cannot be imported or optimized as arbitrary build fields.
- Added a compiled original-Platinum arithmetic oracle and 3,456 stored cases retaining secondary-simulator disagreements. Broadened all shared process/API/CLI regression checks to Gen 4; 91 Python tests plus dashboard JavaScript harness.
- Form-required items are visible in JSON/CSV results and the dashboard's results/viewer. EV displays continue to use complete Gen 3/4 builds.
- Defaults/neighbors are validated for every Gen 3/4 entry. Full-field verification and browser evidence are recorded separately in the release validation report.

Existing v0.8 stability diagnostics remain valid for that release. They do not establish stable search convergence on this expanded field. General held-item optimization, doubles, bench/switch play, cartridge RNG parity and exhaustive full-battle calibration remain outside the implemented format/verified coverage.

## Build 0.8 changes

- Applied the user's acquisition rule across all generation pools and saved-import/spec validation: initial/level-up and retained pre-evolution level-up moves, plus egg moves only for baby species. Removed TM/HM pools. Gen 2/3 baby data and special Gen 3 Pichu Volt Tackle use pinned sources. No tutor imports were added.
- Gen 1/2 inherited level-up moves now allow delayed evolution up to the selected level. Every species retains a valid default build. No permanent imported Sketch sets; battle copying/calling still works.
- Corrected damage modifier phases for Facade, Weather Ball, Revenge, Smellingsalt, Stomp, Charge, and Spit Up; Facade excludes sleep/freeze. Explosion halves defense before stat stages; Thick Fat modifies raw special attack before stages. Added Plus/Minus (including opposite sides), proper Beat Up base-stat damage and per-type minimum rounding.
- Early Bird subtracts sleep turns when acting; Rest respects sleep-preventing abilities/Uproar, Soundproof can sleep through Uproar and blocks its own Heal Bell. Fixed failed/minimum-cost Substitute, False Swipe against Substitute, Skull Bash's charge defense boost, last-action Protect and Spit Up consumption.
- Corrected Mirror Move estimation and exposed Focus Punch selection; avoid several status moves against immune targets.
- Roster API stays usable with incompatible saved builds, so Fresh start can replace them. Invalid battle/search imports are rejected; saved files remain intact.
- Added an optional compiled-C fixture generator using original Emerald routines and a 1,800-case matrix retaining reference-simulator disagreements. Runtime app and ordinary tests still need only Python stdlib.

Older repair history below describes earlier milestones; acquisition rules above supersede earlier TM/HM availability.

## Repairs

### Gen 3

- Build 0.7 repairs per-hit contact/Rage, independent hit damage/crit rolls, Substitute spillover, Transform state, Mimic/Sketch restrictions, caller PP and exclusions, Mirror Move targeting, Pressure self-move PP, and acquired immunity cleanup.
- Reworked residual speed/order, Wish/weather expiry, healing before poison, Toxic rounding, Yawn/timers, and delayed attacks against Substitute/Endure without Destiny Bond/Grudge. Truant now advances at end of turn.
- Moved burn/screens/weather/Flash Fire/Thick Fat/Solar Beam modifiers to source formula phases and preserved ordered type-effectiveness rounding using cache schema 4.

- Replaced fabricated move pools with pinned Emerald level-up, TM/HM, and pre-evolution data for 386 species and 354 moves; preserved native move metadata, priorities, contact flags, weights, growth rates, and abilities.
- Rebuilt the prototype battle state machine using the supplied Gen 2 structure as a starting point, then isolated the Gen 3 modules and adapted typing, stats, weather, abilities, move effects, accuracy, and damage rolls.
- Fixed Grass against Water, Hidden Power typing/screens, exact stat-stage fractions, growth-based levels, missing Docile nature, and illegal imported builds.
- Fixed successful Hi Jump Kick recoil and negative HP, added crash dispatch, proper recoil variants, priority/Protect behavior, attack logging with explicit side identity, delayed attack snapshots, and new setup/status effects.
- Added ability handling including Truant, weather setters/suppression, Levitate, Wonder Guard, absorb abilities, Flash Fire, contact effects, Intimidate, Guts, Huge/Pure Power, Thick Fat, Compound Eyes, Marvel Scale, Forecast, and Color Change.
- Expanded build refinement beyond six EV presets; normalize legacy move arrays before search. Default EV dictionaries no longer share mutable preset state.

### Gen 1/2

- Gen 1 unbans Toxic, Mimic, and Double Team. Toxic escalates and shares its counter with Leech Seed; Mimic copies a move while preserving its slot PP; Haze clears Toxic state.
- Gen 1 Explosion/Selfdestruct faints the user against immune targets.
- Gen 2 Counter/Mirror Coat honor immunity; Hidden Power uses computed typing for damage/screens and its original category for retaliation; Struggle is typeless.
- Gen 2 Rage activates, Disable targets the last move, and Future Sight stores damage and checks accuracy at impact.
- Data source revisions pinned; cache reads close descriptors and recover malformed JSON.

### Shared/dashboard

- Added generation registry, numeric validation, and atomic JSON/CSV saves. Bare-filename saves work; invalid counts/budgets are rejected before starting work.
- Exporting results no longer imports pipeline generation-selection side effects. Small CLI fields and alternate output directories support reproducible smoke checks.
- Event streams have persistent run identities; old cursors reset when logs are replaced. Start/stop locking, child process-group shutdown, and log descriptor handling repaired.
- Live tables refresh after 600 decisions; EV-only changes appear in diffs and exports. Generation/request epochs reject stale responses. Busy runs disable Start, network failures recover the Start button, and text rendering is escaped.
- Mirror battles log explicit `a`/`b` actor identity. The battle viewer runs a fresh simulation with current builds rather than claiming to replay a tournament match.

## Verification and remaining work

See README for commands and rules and MECHANICS.md for pinned sources and reference comparisons. Build 0.8's suite has 70 Python tests, including 600 random legal-move battles, independent reference fixtures, HTTP API, worker processes, and short CLI pipelines, plus the Node dashboard harness. Original attachment claims about 12,000 battles are not reused as evidence.

The browser checks cover generation rosters, battle rendering, mirror identity, and run controls. The optional full-field checker validates one-game pairing matrices and card totals for all 151/251/386 species, with bounded selected-species search against rankings of the full field. Build 0.8 completed all 117,005 pairings. Its bounded Gen 3 search hit the two-minute budget after five decisions; the selected Gen 1/2 searches converged within that budget. Search opponents are sampled, so this is not complete search convergence or a fully optimized tournament.

No ROM/emulator or exhaustive cartridge calibration has been performed. Remaining work includes broader damage/RNG/volatile-effect comparisons across all generations, complete simultaneous-event coverage, full-field search stability, fuller tactical use of effects, and broader full-battle comparisons. Windows operation is confirmed by the user; macOS is out of scope. Gen 3 uses Emerald mechanics rather than a Ruby/Sapphire/Emerald selector. Pool constraints and intentional format exclusions are documented in README.

Upgrade using Fresh start / `--fresh` for a new complete field and when previous sets include removed TM/HM moves. Gen 3 schema 6 and Gen 4 schema 2 include the expanded form data; the bundled caches/sources support offline normal startup. See MECHANICS.md for source-oracle bounds and reference differences.
