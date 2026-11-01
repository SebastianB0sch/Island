# Code Review & Refactor Pass — Overview

> A second pass, stacked on this work, is documented in
> [Pass2/00-overview.md](Pass2/00-overview.md).

Branch: `refactor/code-review-pass` (from `port/baseline`)
Scope: the full repository — Unreal Engine 5.8 C++ gameplay module, the Python
asset/data pipeline, validators, and the CI/smoke harness.

## Method

The review was split into six disjoint workstreams so each could be reviewed
and changed independently, then integrated and verified together:

| # | Workstream | Main files | Report |
|---|---|---|---|
| 01 | Duel engine & rules | `DADuelEngine.*`, `DADuelistAI.*`, `DADuelRules.h` | [01-duel-engine.md](01-duel-engine.md) |
| 02 | Effect runtime & effect tools | `DAEffectRuntime.*`, `Tools/effects/` | [02-effect-runtime.md](02-effect-runtime.md) |
| 03 | UI layer | `DADuelUI.*`, `DAHUD.*`, PDA/title/dialogue/deck/shop/exam UI | [03-ui-layer.md](03-ui-layer.md) |
| 04 | Story, progression & persistence | `DAStorySubsystem.*`, `DASaveGame.*`, profile/calendar/exam/opponent/inventory/shop/deck logic | [04-story-persistence.md](04-story-persistence.md) |
| 05 | Python pipeline & validators | `Tools/dai`, `Tools/validate`, canon/economy/opponents/puzzles/story/world, editor Python | [05-python-pipeline.md](05-python-pipeline.md) |
| 06 | CI & integration harness | `.github/workflows/ci.yml`, `Tools/integration/` | [06-ci-harness.md](06-ci-harness.md) |

Each workstream was constrained to its own files. The integration step then:

1. reviewed every diff for scope and behavior changes;
2. built `DuelAcademyIslandEditor Win64 Development` with UE 5.8;
3. re-ran the headless self-tests and the data validators;
4. recorded remaining risks as follow-ups rather than hiding them.

## Baseline (before this pass)

| Check | Result |
|---|---|
| Editor target build (UE 5.8, Win64 Development) | PASS |
| `-DADuelSelfTest=24` | PASS — 24 iterations, 0 stalls, 0 invariant failures |
| `-DAProfileSelfTest` | PASS |
| `-DADuelRulesSelfTest` | PASS — 58/58 |
| `-DAEconomySelfTest` | PASS — 213/213 |
| `python Tools/validate/validate_all.py` | PASS — 0 errors, 15 warnings, 6 gaps |
| `python Tools/puzzles/validate.py` | PASS — 145 checks, 0 failures |
| `python Tools/effects/validate_effects.py` | PASS — 0 warnings |
| `python Tools/opponents/import_canon_decks.py --check` | **FAIL** — roster/story referenced `sheppard_year1` but `DECK_MAP` did not (the deck file itself existed) |

The opponent-deck failure was a pre-existing mapping gap, not missing content.
It was fixed during integration by adding the existing `sheppard_year1` runtime
deck to `DECK_MAP`; the check is now green (32/32 runtime, 37/37 constructed).

## Verification (after integration)

| Check | Result |
|---|---|
| `DuelAcademyIslandEditor Win64 Development` | **PASS** — 26 build actions, no compiler warnings |
| `-DADuelSelfTest=24` | **PASS** — 24 iterations, 12/12 wins, 0 stalls, 0 invariant failures, 37/37 decks, 100/100 puzzles |
| `-DAProfileSelfTest` | **PASS** |
| `-DADuelRulesSelfTest` | **PASS** — 58/58 |
| `-DAEconomySelfTest` | **PASS** — 213/213 |
| `-DAStorySelfTest` | **PASS** |
| `-DAFullStorySelfTest` | **PASS** |
| `-DAEffectRuntimeSelfTest` | **PASS** — 147/147 |
| `-DAPuzzleExamSelfTest` | **PASS** — puzzles 102/102, exams 104/104 |
| `-DAPortalTest` | **PASS** — 188/188 |
| `-DANpcScheduleTest` | **PASS** — 514/514 |
| `-DAStoryPlaythroughTest` | **PASS** — 35-event campaign |
| `-DASaveFuzz=300 -DATwelveMonthTest` | **PASS** — 67,496 save-fuzz checks + 10,947 calendar/save checks, 0 failures |
| `python -m unittest discover -s Tools/tests` | **PASS** — 38 tests |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 gaps |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures |
| `python Tools/effects/validate_effects.py` | **PASS** — 0 warnings |
| `python Tools/opponents/import_canon_decks.py --check` | **PASS** — 32/32 runtime, 37/37 constructed, 32/32 references |
| `python Tools/economy/validate_decks.py` / `validate_packs.py` | **PASS** — 81 checks / 1,342 checks |
| `python Tools/audit_story_fidelity.py` | **PASS** — 39/39 duels, 44 scenes |
| `python Tools/world/validate_layout.py` | **PASS** |
| `git diff --check` | **PASS** — no whitespace errors |

The two open-ended story audits (`-DAStorySelfTest`, `-DAFullStorySelfTest`)
log their result but intentionally leave the editor running; the integration
run watched for the final summary and then terminated those processes. All
other suites request their own exit.

## Outcome

- **Runtime units are smaller and more focused:** the duel diagnostics block
  moved to `DADuelEngineDiagnostics.cpp` (−993 lines in the runtime unit), and
  the full-campaign audit moved to `DAStorySelfTest.cpp` (−711 lines).
- **The worst UI functions were split:** `DrawDuelActive` 502 → 236 lines,
  `SpawnDuelFx` 314 → 23, `HandleDuelHit` 315 → 255, with draw order and
  coordinates preserved.
- **Correctness fixes landed across the stack:** prevented-destruction battle
  follow-ups, F.G.D. protection, stale flip/graveyard references, duplicate
  effect triggers, equip/state leaks, turn-scoped attack locks, save/load
  determinism, overflow-safe economy paths, and stale UI selection indices.
- **The gates are stronger:** CI runs the real validators, 38 Python unit tests
  cover the harness/pipeline, and the opponent-deck mapping check is green.
- **No generated data was intentionally changed.** `test_effects.py` and
  `audit.py` rebuild `card_effect_manifest.json`; that generated diff was
  reverted after verification.

## Remaining risks (not fixed in this pass)

1. **Effect event queue (high):** `FireEvent` drops nested events while an
   effect is executing, so effect-driven summon/destroy triggers do not fire.
   See [02-effect-runtime.md](02-effect-runtime.md) U1.
2. **Double-KO semantics (medium):** `Winner` says opponent while
   `ResultStats.bDraw` says draw. Needs a first-class draw result and UI policy.
   See [01-duel-engine.md](01-duel-engine.md).
3. **Save load is not two-phase (medium):** a provider failure can leave
   calendar/profile/settings partially applied. See
   [04-story-persistence.md](04-story-persistence.md) F19.
4. **Modal policy (medium):** the duel deck picker does not close/refuse
   PDA/dialogue/map overlays, and the final-beat skip hint is not yet truthful.
   See [03-ui-layer.md](03-ui-layer.md) F6/F7.
5. **Content gaps remain:** 493 pending Tier-2 effects and 15 validator
   warnings/6 gaps are tracked by the existing gates, not hidden by this pass.

## Size and shape

| Area | Files | Lines |
|---|---:|---:|
| C++ / C# (game module + targets) | 118 | 69,055 |
| Python pipeline (`Tools/`, excluding vendored Blender site-packages) | 102 | 44,723 |
| Python editor scripts (`Content/Python`) | 12 | 2,187 |
| Runtime data JSON | 472 | 239,805 |
| Contract schemas | 20 | 1,863 |

The main structural pressure is concentrated in a few translation units and
functions:

- `DADuelEngine.cpp`: 9,250 lines, including a 530-line self-test and a
  452-line invariant checker in the runtime unit. Now 8,257 lines, with the
  1,013-line diagnostics/self-test block in `DADuelEngineDiagnostics.cpp`.
- `DAEffectRuntime.cpp`: 5,182 lines / 130 functions. Deduplication added five
  helpers; the unit is 5,261 lines after validation/cleanup fixes.
- `DADuelUI.cpp`: 4,233 lines, with `DrawDuelActive` (502), `DrawDuelFx` (433),
  `HandleDuelHit` (315) and `SpawnDuelFx` (314). `DrawDuelActive` is now 236
  lines, `SpawnDuelFx` 23, and `HandleDuelHit` 255; `DrawDuelFx` remains the
  next split candidate.
- `DAStorySubsystem.cpp`: 4,340 lines, including `RunFullStorySelfTest` (663)
  and `ExecuteCommand` (364) in the runtime unit. Now 3,629 lines, with the
  817-line full-campaign audit in `DAStorySelfTest.cpp`.

The refactor targets those boundaries first: move test/diagnostic code out of
runtime units, split the worst drawing/dispatch functions into cohesive
helpers, and reduce duplicated JSON/drawing/input plumbing without changing
public APIs or generated data.
