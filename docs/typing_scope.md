# Static typing: scope and mistyping inventory

Branch `typing-update`, cut from `DoorDevUnstable` (local tip `aae44661`, upstream `6f390947`).
This is a scoping document only. No code was changed; the only addition besides this file
is `pyrightconfig.json`, which reproduces the baseline below.

## 1. Baseline

Source tree excluding `test/`, `resources/`, `_vendor/`, `bundle/`, `local-files/`.

| Measure | Value |
|---|---|
| Python files | 98 |
| Lines | ~56,800 |
| Functions | 1,760 |
| Functions with any annotation | 57 (3.2%) |
| Functions with a return annotation | 6 |
| Annotated parameters | 70 of 3,771 (1.9%) |
| Annotated assignments | 5 |
| Files importing `typing` | 4 |
| Classes | 130, of which 22 are `Enum`/`FastEnum`/`Flag` |
| Settings compared against string literals | 42 `world.*` attributes, 815 comparison sites |
| Settings assigned onto `World` in `Main.py` | 55 attributes, plus 65 set in `World.__init__` |

Checker baselines, run from the repo root with the venv in
`scratchpad/tcvenv` (mypy 2.4.0, pyright 1.1.414):

```
mypy --python-version 3.12 --ignore-missing-imports --check-untyped-defs \
     --exclude '(test|resources|local-files|_vendor|bundle|build|dist|\.venv)/' .
# 954 errors: 482 attr-defined, 182 var-annotated, 69 index, 62 union-attr,
#             52 assignment, 41 operator, 25 arg-type, 17 call-arg, ...

pyright   # uses pyrightconfig.json, basic mode
# 1167 errors: 799 reportAttributeAccessIssue, 134 reportOptionalMemberAccess,
#              71 reportOptionalSubscript, 59 reportArgumentType, 29 reportGeneralTypeIssues,
#              27 reportOperatorIssue, 22 reportCallIssue, ...
```

`--check-untyped-defs` is mandatory: with 3% annotation coverage, default mypy skips
almost every function body.

### Where the noise comes from

- 328 pyright errors are tkinter `Frame`/`Tk` objects given ad-hoc attributes
  (`.widgets`, `.frames`, `.pages`, `.notebook`) in `Gui.py` and `source/gui/`. Fix is a
  handful of `Frame` subclasses; not logic bugs.
- ~260 errors are `Optional` attributes initialised to `None` in `__init__` and filled
  later (`DataTables.ow_enemy_table`, `KeyCounter` fields, `Main.state_cache = [None]`).
  Mechanical annotation work, not bugs.
- 13 "Argument to class must be a base class" are `FastEnum` false positives; the
  library ships no type stubs. Replace with `enum.Enum` or add a stub.
- 32 pyright errors on `World` are attributes set in `Main.py` instead of `__init__`
  (`settings`, `customizer`, `player_names`, `difficulty_requirements`, `_region_cache`).
- Heterogeneous literal tables (`door_addresses`, `key_drop_data`, BPS action tuples)
  make mypy infer `object`; fixed with `TypedDict`/`tuple[...]` annotations.

Of 1,167 pyright errors, 604 are outside GUI/client code and 116 of those are in rules
other than attribute access and Optional narrowing. Every one of those 116 was read for
this document; the real findings are below.

## 2. Mistypings found

### A. Live code, wrong at runtime

1. **`Rom.py:1488` – `colorize_pots` is a 2-tuple, not a bool.**
   ```python
   colorize_pots = (world.pottery[player] != 'vanilla', 'lottery'
                    and (world.colorizepots[player] or world.pottery[player] in ['reduced', 'clustered']))
   ```
   The comma makes this `(bool, <expr>)`, which is always truthy. It is passed to
   `DataTables.write_to_rom(rom, colorize_pots, ...)` (`source/rom/DataTables.py:60`) and tested
   as `if colorize:` at `PotShuffle.py:1062`, so pots are recoloured whenever `data_tables` exists,
   regardless of the `colorizepots`/`pottery` setting. The intended expression was presumably
   `world.pottery[player] not in ['none', 'lottery'] and (...)`. Also compares against `'vanilla'`,
   which is not a `pottery` choice (`none, keys, dungeon, cave, cavekeys, reduced, clustered, nonempty, lottery`).
   Introduced `4aae6034` (2023-03-10). A `colorize_pots: bool` annotation, or a `bool` parameter
   annotation on `write_to_rom`, catches this.

2. **`Fill.py:61` – leaked loop variable selects the wrong player.**
   ```python
   if world.logic[player] == 'hybridglitches' and world.keyshuffle[i.player] in ['none', 'nearby'] \
   ```
   `i` is the last element of `world.itempool` left over from the loop at `Fill.py:52`; the
   condition should read `world.keyshuffle[player]`. Correct by accident in single-player.
   `'nearby'` is not a `keyshuffle` choice (`none, wild, universal`). Typing alone does not catch the
   `i` leak (both are `int`), but a `Literal` type on `keyshuffle` catches `'nearby'`.

3. **`Fill.py:89` – inner `fill` called with four arguments, defined with three.**
   ```python
   def fill(base_state, items, key_pool):                       # Fill.py:56
   fill(hybrid_state_base, hybrid_smalls, hybrid_locations, unplaced_smalls)   # Fill.py:89
   ```
   Raises `TypeError` whenever reached: `logic == 'hybridglitches'`, in-dungeon keys, and
   `pottery` not in `none`/`cave`. Not confirmed by generation (see note at end); pyright
   reports it as `reportCallIssue`. Relevant to the HMG work in this fork.

4. **`source/tools/Bias.py:162,164` – `random.choice` on a generator.**
   `random.choice(b for b in boss_list if ...)` raises `TypeError` (`object of type 'generator'
   has no len()`). Only reachable from the Bias tool's `__main__`.

5. **`source/classes/BabelFish.py:58,81` – mixed tabs and spaces; `:72,92,109,110` – `specials`
   dict holds `bool` then `str`.** Runs today, but `specials["multiRoom"] not in display_text` is
   `True not in str` when the key was never reassigned, which Python rejects at runtime only on
   that branch.

### B. Dead or stale code that a type checker exposes

6. **`DoorShuffle.py:1498, 2242–2244` – calls with the pre-2022 signatures.**
   ```python
   find_small_key_door_candidates(builder, start_regions, world, player)   # def takes (builder, start_regions, used, world, player)  :2720
   find_valid_combination(builder, start_regions, world, player)           # def takes (builder, target, start_regions, world, player, drop_keys)  :2753
   reassign_key_doors(builder, world, player)                              # def takes (small_map, used_doors, world, player)  :3123
   ```
   Call sites date from `35c3a07d` (2019); definitions changed in `d9f0e2a7` (2022). They sit in
   `assign_cross_keys` (`:1472`) and `shuffle_key_doors` (`:2220`), both reached only from
   `cross_dungeon` (`:1338`), which has no callers. Roughly 300 lines of unreachable code that
   would crash if revived.

7. **`Plando.py:27, 77, 173, 176, 179`** – stale `World(...)` constructor (missing `spoiler_mode`
   and later params) and three-positional `fill_*` calls. No module imports `Plando`.

8. **`source/enemizer/EnemizerTestHarness.py:19, 20, 92, 94`** – constructor and function calls
   missing `custom_enemies`, `data_tables`, `custom_uw`, `custom_ow`. Dev harness, not shipped.

9. **`test-options.py:34, 36, 41, 49, 56`** – returns `int` where `Toggle` is declared;
   iterates `Choice` class incorrectly. Tooling script.

### C. Comparisons against values the setting can never hold

Found by cross-referencing every `world.<setting>[player] == '...'` against
`resources/app/cli/args.json` choices:

| Site | Literal | Declared choices |
|---|---|---|
| `Fill.py:282`, `Fill.py:431` | `'equitable'` (algorithm) | `balanced, vanilla_fill, major_only, dungeon_only, district` |
| `Fill.py:61` | `'nearby'` (keyshuffle) | `none, wild, universal` |
| `Rom.py:1488` | `'vanilla'` (pottery) | `none, keys, dungeon, cave, cavekeys, reduced, clustered, nonempty, lottery` |

Harmless today (`'equitable'` was a removed algorithm), but each is a branch that can never
fire and a sign the literal set drifted from the CLI. `Literal[...]` types on the 42 compared
settings eliminate this class.

### D. Already-fixed bugs of this class (why this matters)

These were found by hand in the last year and would have been compile-time errors under typing:

- `3eb237f6` – `Rom.py` compared the boolean `bigkeyshuffle`/`mapshuffle`/`compassshuffle`
  settings against the string `'none'`; the branch never matched, so unshuffled dungeon items
  kept keysanity item codes. Root cause of the HMG big-key complaint.
- `b711c635` – same bool-vs-`'none'` pattern forced the dungeon item HUD counter on in every seed.
- `14349117`, `f4c465f5` – mystery/customizer YAML booleans arriving as strings.
- `c64d499b` – maps/compasses treated as advancement because a `'none'` string was truthy.

All four are `bool` settings compared to `str`, or `str` settings used as `bool`. A per-setting
type on `World` (`Dict[int, bool]` vs `Dict[int, Literal['none', 'wild', 'universal']]`) makes
each one a reported error.

### E. Possible, not confirmed

- `KeyDoorShuffle.py:150–201` – `min(rule_threshold, threshold)`, `len(check_locations)`,
  `for loc in check_locations` where the fields default to `None`. Guarded by control flow
  pyright cannot follow; would need annotations to decide.
- `source/dungeon/DungeonStitcher.py:197` – `type_map[hook_from_door(attempt)]` where
  `hook_from_door` can return `None`.
- `source/overworld/EntranceShuffle2.py:855, 979`, `source/tools/MysteryUtils.py:207`,
  `Main.py:313` – Optional values passed to `remove`/`pop`/subscript.

## 3. Size of the change

Phased, each phase independently mergeable and CI-enforceable:

| Phase | Work | Rough size |
|---|---|---|
| 0. Baseline gate | Commit `pyrightconfig.json` (basic), add a CI step that fails only on *new* errors (baseline file). | 1 day |
| 1. Settings | Annotate the 55 `Main.py` settings + 65 `World.__init__` attributes as class-level declarations on `World`; `Literal` aliases generated from `args.json`; fix the 5 findings in §C/§A1–A2. | 2–3 days, ~150 lines |
| 2. Core data model | `BaseClasses.py` (3,324 lines): `Region`, `Location`, `Item`, `Entrance`, `Door`, `Dungeon`, `CollectionState`, `KeyCounter`. Optional fields and heterogeneous tables. Replace `FastEnum` with `enum.Enum` or write a stub. | 1 week |
| 3. Generation and fill | `DoorShuffle.py`, `DungeonGenerator.py`, `KeyDoorShuffle.py`, `Fill.py`, `FillUtil.py`, `EntranceShuffle2.py`, `Rom.py`, `DataTables.py`: signatures only (no body rewrites). Delete `cross_dungeon`/`assign_cross_keys`/`shuffle_key_doors` dead code, `Plando.py`. | 1–2 weeks |
| 4. GUI | `Frame`/`Tk` subclasses carrying `widgets`/`frames`/`pages`; mostly mechanical. | 3–4 days |
| 5. Strict | `--check-untyped-defs` → `disallow-untyped-defs` per module as each finishes. | ongoing |

Estimated total to reach "pyright basic clean, mypy clean with `check-untyped-defs`" over
the non-GUI code: 3–4 weeks of focused work. Annotation footprint on the order of 2,000 signature
edits (1,760 functions, 3,771 parameters) plus ~250 attribute declarations.

## 4. Expected bug yield

From the full read of the 116 high-signal non-GUI errors:

| Class | Count |
|---|---|
| Live runtime bugs (§A) | 3 in shipped code (`Rom.py:1488`, `Fill.py:61`, `Fill.py:89`), 2 in tools |
| Dead code that crashes if called (§B) | 4 clusters, ~15 call sites |
| Impossible comparisons (§C) | 4 sites, 3 distinct literals |
| Previously fixed by hand (§D) | 4 commits |
| Needs annotation to decide (§E) | ~8 sites |

The remaining ~1,000 errors across both checkers are annotation debt, not defects.
Phase 1 alone (settings types) retroactively covers every §C and §D item and is the
highest value-to-effort step.

## 5. Reproducing

```
python -m venv tcvenv && tcvenv/bin/pip install mypy pyright aenum fast-enum pyyaml websockets aioconsole colorama distro types-PyYAML
tcvenv/bin/pyright --outputjson > pyright_out.json
tcvenv/bin/mypy --python-version 3.12 --ignore-missing-imports --check-untyped-defs \
    --exclude '(test|resources|local-files|_vendor|bundle|build|dist|\.venv)/' .
```

Note: §A3 was identified statically and was not exercised by rolling a seed, per the
instruction to keep this to a documentation exercise.
