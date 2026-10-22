> Verification scope for build 0.12.0: the source-oracle files and large case
> counts described below are inherited documentation; those assets were not
> supplied and have not been rerun here. Current checks are in `tests/`, using
> synthetic Gen 1–4 mechanics fixtures, a pre-optimization Gen 4 arithmetic
> reference, the supplied Gen 1 cache and newly built Gen 2/3 caches. Default
> Gen 2/3 roster smoke checks supplement the synthetic regressions. See
> `HANDOFF.md` for fixes and remaining calibration limits.

# Mechanics sources and verification

## Ruleset and rosters

The fields contain all 151, 251, 386 and 493 National Pokédex species available through each generation, including legendaries and version exclusives. Gen 3 uses Emerald battle rules; Gen 4 uses Platinum. Named forms expand Gen 3/4 to 389/522 independent entries. Including Ruby/Sapphire exclusives does not require using their earlier battle bugs. For example, Emerald clears Nightmare when Shed Skin cures sleep; Ruby/Sapphire can leave it set. There is no game-version mechanics selector.

All competitors use level 50 regardless of growth group. All build pools use full initial/level-up learnsets and retained pre-evolution level-up moves without a learn-level cutoff. A move learned at level 80 is legal at battle level 50. The previous 156,250-EXP level selection is superseded; level-dependent damage and accuracy use level 50 too. Only baby species receive egg moves; they do not propagate to evolved build pools. TM/HM/tutor/event/transfer acquisition is excluded. Gen 1 Toxic, Mimic, and Double Team have no tournament ban, but only naturally learned moves qualify for build pools. Therefore Gen 1 Toxic and Mimic have no build-pool learners; Double Team does. Mimic automatically selects a random opposing move as in link battles; the cartridge's local player-choice interface is not modeled.

## Pinned public sources

- [Red](https://github.com/pret/pokered/tree/af519899719f0754965776faac0e836a3b906e6d): `engine/battle/effects.asm` (`MimicEffect`, Toxic/Haze), battle core residual handling.
- [Yellow](https://github.com/pret/pokeyellow/tree/8ea8bcaee5e2e0fec1ba5c2e3a46d9fba6cb02ad): Gen 1 data extraction.
- [Crystal](https://github.com/pret/pokecrystal/tree/97187cd21b15e9a266a786318c851848f2fac24b): Gen 2 data and effects.
- [Emerald](https://github.com/pret/pokeemerald/tree/731ad5bfd6e6f265508d0efcca0ba42f9dcf5881): primary Gen 3 mechanics and data source.
- [Ruby/Sapphire](https://github.com/pret/pokeruby/tree/5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f): normal Deoxys learnset and comparison source for version differences.

- [FireRed/LeafGreen](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982): Attack/Defense Deoxys stats and level-up moves.
- [Platinum](https://github.com/pret/pokeplatinum/tree/e038244ff792439e9200604736dc30eb38940bb3): all Gen 4 species/form stats, 467 moves, level-up/baby-egg data, damage/turn routines and move scripts.
- [HeartGold/SoulSilver](https://github.com/pret/pokeheartgold/tree/6988158691eb6178cff697cda0428045ddcba5fb): Spiky-eared Pichu identity/no-evolution evidence; Platinum Pichu stats and level-up moves remain the configured rules.

Emerald source locations used in this repair:

| Source | Relevant behavior |
| --- | --- |
| `src/battle_main.c` | Ordered type-effectiveness table and battle ordering |
| `src/pokemon.c`, `CalculateBaseDamage` | Burn, screens, weather, Thick Fat, Flash Fire, Solar Beam and integer rounding |
| `src/battle_script_commands.c` | Transform, Mimic/Sketch, called-move restrictions, Substitute HP, normal damage adjustment |
| `src/battle_util.c`, `HandleTurnCounters`, `TurnBasedEffects`, `HandleWishPerishSongOnTurnEnd`, `AbilityBattleEffects` | Wish/weather, per-battler residual sequence, delayed attacks, Perish Song, contact abilities and Truant |
| `data/battle_scripts_1.s`, `BattleScript_MonTookFutureAttack` | Impact accuracy, Substitute/Endure damage adjustment, passive delayed KOs and Rage |

Gen 3 extraction inputs are bundled under `gens/gen3/raw/`. Cache schema 6 includes the ordered type table and baby egg moves; `src/daycare.c` supplies Pichu's special Volt Tackle breeding rule. Gen 2 baby egg data is bundled from Crystal's `data/pokemon/egg_moves.asm`. Run `build()` from `gens.gen3.data` to reproduce its JSON cache from those inputs.

## Independent simulator comparisons

`tests/reference-gen3.json` stores comparisons generated with `@pkmn/sim@0.10.11`, the extracted Pokémon Showdown simulator. Ten level-50, 31-IV, zero-EV, Hardy damage cases use maximum noncritical damage. They cover burn, Guts/Facade, screens, weather, Thick Fat, dual-type rounding, and Solar Beam in hail. Nine damage values match directly. Facade retains the independent value 165 and an explicit source-expected value 166; the original source doubles damage after +2, while this reference doubles base power. Additional fixtures compare per-hit Rough Skin, breaking Substitute during Double Kick, and Transform through Substitute.

The generator sets combat state explicitly without entry-ability activation. The Python fixtures match that state. Boundary fixtures exercise selected effect routines directly; they do not claim identical complete battles or RNG streams.

To regenerate outside application dependencies:

```bash
npm install --prefix /tmp/pokemon-reference --no-audit --no-fund --ignore-scripts @pkmn/sim@0.10.11
PKMN_SIM=/tmp/pokemon-reference/node_modules/@pkmn/sim node tests/generate_reference.cjs > /tmp/reference-gen3.json
```

Compare generated JSON to the stored fixture. The ordinary Python suite reads the stored fixture and needs no Node package.

## Original C damage matrix

`tests/damage-matrix-gen3.json` contains 1,800 maximum-roll damage cases across nine species/ability pairs, 20 moves, and ten status/weather/stage/critical configurations. `tests/generate_source_damage.py` extracts and compiles the original pinned Emerald functions `CalculateBaseDamage`, `Cmd_damagecalc`, `ModulateDmgByType`, and `Cmd_typecalc` unchanged. Stubs select single battles, no held items or badge boosts. The harness supplies explicit stats, effective move types, dynamic powers and script damage multipliers, and honors immunity result flags.

All 1,800 simulator damage values match these source outputs. The independent simulator agrees on 1,717 and differs on 83; both values remain stored. Differences include base-power versus damage multipliers, ordered dual-type rounding, and ability/defense stage rounding. Original source governs these cases. No divergent cases are discarded.

Optional regeneration from the project directory (requires Node plus the external pinned reference package and a C compiler supporting GNU C11):

```bash
PKMN_SIM=/tmp/pokemon-reference/node_modules/@pkmn/sim node tests/generate_damage_matrix.cjs > /tmp/matrix-inputs.json
python3 tests/generate_source_damage.py /tmp/matrix-inputs.json > /tmp/damage-matrix-gen3.json
```

This isolates damage routines; it does not execute full original battles, called-move scripts, item/doubles behavior, RNG streams, entry abilities, or all possible stat states. Ordinary regression tests read the stored fixture and require neither Node nor a compiler.

## Platinum damage and turn checks

`tests/damage-matrix-gen4.json` contains 3,456 cases: 12 species/ability pairs, 16 moves, nine configurations, and rolls 85/100. Both secondary-reference and original-C results are retained. All 3,456 Python results match the compiled original routines. The secondary simulator differs in 61 cases involving Explosion's pre-stage Defense halving, ordered mixed-type rounding, Sniper's critical multiplier phase, or Dry Skin's base-power phase. These cases remain in the suite.

`tests/generate_source_damage_gen4.py` compiles unedited Platinum `BattleSystem_CalcMoveDamage`, `BattleSystem_Divide`, `ApplyTypeMultiplier`, and `BattleSystem_ApplyTypeChart` with original stat/type/punch/item tables. Service stubs specify singles, ordinary health, fixed form items, no allies and explicit test stats. The harness supplies each case's variable power/type and critical/variance inputs; it does not independently validate every variable-power move or ability trigger. It is an arithmetic oracle, not a complete battle emulator.

```bash
PKMN_SIM=/tmp/pokemon-reference/node_modules/@pkmn/sim node tests/generate_reference_gen4.cjs > /tmp/gen4-inputs.json
python3 tests/generate_source_damage_gen4.py /tmp/gen4-inputs.json > /tmp/damage-matrix-gen4.json
```

`gens/gen4/raw/platinum.json` retains original source records. Cache schema 2 rebuilds offline, using the original ordered chart from bundled `battle_lib.c`. `daycare.c` supplies the special Pichu breeding grant. New boundary tests cover categories/screens, form/item identity, Multitype protections, Mold Breaker, Download/Trace, Gravity/No Guard, field timers, Sky Shaymin freeze reversion, Stockpile, Me First, Sucker Punch, Metal Burst, Gen 4 Struggle, Magic Guard, weather/Poison Heal, secondary effects, Pressure and complete entry/neighbor validity.

Residual weather abilities resolve before per-battler Ingrain/Aqua Ring and status damage. Bad Dreams follows binding damage; delayed attacks and Perish Song follow individual residuals. Source routines/scripts govern these targeted behaviors. No complete claim is made for all simultaneous events. The battle policy remains heuristic; cosmetic Unown, Burmy, Shellos and Gastrodon variants share one competitor each; mechanically distinct forms retain independent entries.

## Coverage boundaries

Source-derived regressions cover acquisition/import policy, baby exceptions, Toxic/Leech Seed, multi-hit, contact sleep/fainting, called-move PP, Transform state, delayed damage, timers, Truant, residual ordering, sleep abilities, Substitute, Beat Up, Spit Up, Skull Bash and selected AI decisions. The full-field checker exercises every unordered pairing once using default builds, then bounded selected-species search with sampled opponents from the full ranking. It does not establish full convergence, optimal decisions, exhaustive breeding combinations, or cartridge accuracy.

No ROM, cartridge emulator, or RNG parity check has been used. Gen 1/2 retain uncalibrated behavior beyond the repaired regressions. Egg moves for non-baby species and TM/HM/tutor/event/transfer moves are deliberately excluded by the user's format, not missing acquisition features. Minimum evolution/capture levels and breeding-parent/egg-move combination constraints remain unmodeled. See README for other format conventions. Windows operation was user-confirmed; macOS is outside current scope.
