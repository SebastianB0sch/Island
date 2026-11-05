# Code Review & Refactor Pass 4 — Workstream Brief

Baseline: the pass 1–3 tree, committed as `77cc9c7` ("Checkpoint: code review
passes 1-3"). Seven read-only discovery workstreams produced a verified findings
set (session reports held by the parent). This pass implements the accepted
findings with strict disjoint file ownership. Workstreams run concurrently:
**you may read anything, but edit only the files in your scope** plus your own
report `Docs/CodeReview/Pass4/NN-name.md`.

## Rules

- Do not run UnrealBuildTool, UnrealEditor, Blender, or any Unreal process. All
  builds and headless suites are run by the parent session after integration.
- Python tests: you may run `python -m unittest discover -s Tools/tests` and any
  validator in a CHECK/NO-WRITE mode (pass `--no-report`, never `--write`).
- Do not edit generated runtime data, manifests, reports, committed assets or
  golden saves unless your scope explicitly lists the file.
- No whitespace-only or formatting-only rewrites. No speculative rewrites.
- Do not run `git commit`/`git add`. The parent owns all git operations.
- `git diff --check` must be clean for the files you touched.
- If a fix needs a file outside your scope, do NOT edit it: end your report with
  an "Integration hand-offs" section with the exact edit (file, symbol, lines).
- Keep every existing test/validator expectation coherent. If a self-test
  prints totals and your change adds checks, update the printed numbers.

## Pinned cross-workstream contracts (implement EXACTLY these signatures)

1. `FDADuelUI` (WS-04 declares+implements, WS-02 consumes):
   ```cpp
   // True iff the most recently opened story deck-select ended without a duel
   // result being recorded (player backed out). Story treats this as
   // re-present, not as a phantom loss.
   bool WasDeckSelectClosedWithoutResult() const;
   ```
2. `ADAStudentCharacter` (WS-04 declares+implements, WS-05 consumes from portal
   code): ```cpp
   void NotifyTeleportArrived(); // clears FocusedInteractable and focus state
   ```

## Workstreams

| # | Name | Owns (edit) | Primary findings |
|---|------|-------------|------------------|
| 01 | Duel engine | `DADuelEngine.{h,cpp}`, `DADuelEngineDiagnostics.cpp`, `DADuelistAI.*`, `DAEffectRuntime.{h,cpp}`, self-tests `DAEffectRuntimeSelfTest.cpp`, `DADuelRulesSelfTest.{h,cpp}` | D1–D9, T-gaps, C2, C5, engine Start validate |
| 02 | Persistence & story | `DASaveGame.{h,cpp}`, `DAStorySubsystem.{h,cpp}` + `DAStoryPlaythroughTest.cpp`, `DAEventGraph.*`, `DAOpponentSubsystem.*`, `DAOpponentTests.*`, `DACalendarSubsystem.*`, `DASettings.*`, `DAIslandManager.*` | P4-01…04-09, P4-11, P4-13, P4-15, U3, W9, W13, starter-flag corner |
| 03 | Economy & profile | `DAProfileSubsystem.*`, `DAProfileSelfTest.cpp`, `DAInventorySubsystem.*`, `DAShopSubsystem.*`, `DADeckLogic.*`, `DAEconomyJson.h`, `DAEconomyTypes.h`, `DAEconomyTests.*` | E1–E11, P4-11, C3/C4 minimal, profile debounce, shop autosave trigger |
| 04 | UI & pawn input | `DAHUD.*`, `DAStudentCharacter.*`, `DADialogueUI.*`, `DATitleScreen.*`, `DATitleSystem.*`, `DAPDAUI.*`, `DADeckUI.*`, `DADuelUI.*`, `DAShopUI.*`, `DAExamUI.*`, `DAUIScreen.*`, `DAAvatarComponent.*`, `DAAvatarAnimInstance.*`, `DAA02GateTests.cpp` | U1, U2, U4–U11, pinned contract #1, W5, avatar dead fields W11 |
| 05 | World & NPC | `DAIslandSubsystem.*`, `DAInteriorPortal.*`, `DAInteractable.cpp`, `DALocationVolume.*`, `DANpcDirector.*`, `DANpcSpawnPoint.*`, `DAStudentNPC.*`, `DAWorldActors.cpp`, `DAPortalTest.*`, `DANpcScheduleTest.*` | W1, W2, W3, W6, W7, W12(+#2), P4-10 |
| 06 | Python asset pipeline | `Tools/dai/**`, `Tools/build_island.py`, `Tools/build_island_blender.py`, `DuelAcademyIsland/Content/Python/**`, `Tools/tests/test_python_pipeline.py` | T1–T8, T10–T14, G-tests |
| 07 | Data tooling & CI | `Tools/canon/**`, `Tools/effects/**`, `Tools/economy/**`, `Tools/validate/**`, `Tools/puzzles/**`, `Tools/story/**`, `Tools/opponents/**`, `Tools/tests/` (other), `Tools/integration/**`, `Tools/world/**`, `Tools/audit_story_*.py`, `.github/workflows/ci.yml`, `.gitignore`, `Docs/Integration/*`, `Docs/Canon/VALIDATION.md` | V1–V14, 9a/9b/9c |

## Deferred by design (document in reports, do not implement)

- Duel: C1 name→descriptor table, C3 defensive-trap helper, C4 effect-state
  registry (large refactors; keep for a dedicated pass).
- Avatar: W4 third-slot crossfade pop and W10 pose-context pooling (need the
  renderer/animator thread to validate; parent cannot verify visually).
- Story: P4-08 modal-blocked infinite wait (documented policy), P4-12 choice
  ledger key scheme (breaks replay idempotency for existing saves; needs a
  dual-key migration plan first).
- Inventory: T9 importer category purge opt-out (engine-only verifiable).
- Tooling: C4 archaeology of one-shot `Tools/story` migrations (they are
  historical; V2/V13 portable fixes suffice).
