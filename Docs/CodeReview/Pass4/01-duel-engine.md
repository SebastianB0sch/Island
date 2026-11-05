# Pass 4 — WS-01 Duel engine — Implementation report

Workstream: 01 "Duel engine" · branch `refactor/code-review-pass` · baseline checkpoint `77cc9c7`

## Scope and constraints

- **Files edited (all inside the WS-01 ownership list):**
  `DADuelEngine.{h,cpp}`, `DADuelEngineDiagnostics.cpp`, `DAEffectRuntime.{h,cpp}`
  (`DAEffectRuntime.h` carries no change besides none being required),
  `DAEffectRuntimeSelfTest.cpp`, `DADuelRulesSelfTest.cpp`,
  plus this report. `DADuelistAI.{h,cpp}` did not need changes.
- No Unreal processes were run (no UBT/editor/Blender). No git commands. No
  generated data, manifests, reports, committed assets or golden saves touched.
- Python was used only for read-only DATA audits (deck legality, script scans)
  and static source checks (brace/whitespace balance); no validator writes.
- Read-only discovery of out-of-scope files (e.g. `DADuelUI.cpp`,
  `DAOpponentSubsystem.cpp`, `Content/Data/**`) was used to verify D-START and
  D2 safety; nothing outside the scope was edited, so no integration hand-offs
  are required.

## Findings table

| ID | Severity | Location (old line refs) | Status | Summary |
|----|----------|--------------------------|--------|---------|
| D1 | MED | `DADuelEngine.cpp` RunOpponentTurn (was 629-643) | **fixed** | AI battle turn now calls `EffectRuntime->OnBattleEnd()` before the End-Phase block, matching the player's `EndBattlePhase` pattern; guarded with `!bWinnerSet`. |
| D2 | MED | `DADuelEngine.cpp` FinishPlayerTurn (was 523-547) + hand-limit discard path (was 576-587) | **fixed** | After the End-Phase callbacks, a pending player prompt defers the AI handoff (`bPlayerEndHandoffDeferred`); `AnswerChoice`/`CancelChoice` resume it via `ContinueDeferredPlayerHandoff()`. Turn state machine not restructured. |
| D3 | LOW-MED | `DADuelEngine.cpp` AiActivateSpellCard tail (was 6666-6670) | **fixed** | AI spell cleanup now routes through `CleanupResolvedChainCard(Uid)`: defers behind pending prompts and uses the shared `"resolve"` reason like `ActivateTrapInternal`. `bStays` local removed (the helper owns the persistence check). |
| D4 | LOW | `DADuelEngine.cpp` Winged Kuriboh LV10 (was 2851-2860) | **fixed** | Burn sum now uses `GetAtk(Monster)` (field spells/buffs included) instead of raw `Monster.Data.Atk`. |
| D5 | LOW | `DADuelEngine.cpp` Card Destruction (was 4926-4932) | **fixed** | Both hands are discarded before either draw (mirroring the both-short branch), so a one-sided deck-out can no longer end the duel with the other hand unprocessed. |
| D6 | LOW | `DADuelEngine.cpp` attack event (was 2790-2803), `EmitVisual` (was 1441-1444) | **fixed** | Attack event routed through `EmitVisual` (180-entry retention cap now applies); `EmitVisual` gained an optional `const FDuelVisualEventTargetInfo*` carrying `TargetUid/TargetCardId/TargetZone/Zone/bDirect`. All existing call sites unchanged (defaulted parameter). |
| D7 | LOW | `DAEffectRuntime.cpp` `ExecuteDiscard`/`ExecuteBanish`/`ExecuteSendToGrave` (was 3051-3199) | **fixed** | `bWinnerSet` breaks added per iteration (engine batch pattern) and the `"both"` discard branch stopped once a trigger ends the duel. |
| D8 | LOW | `DADuelEngine.cpp` `ExecuteChainLinkCard` (was 7508-7528) | **fixed** | Re-fetch now uses field-only `FindSpellTrap`, so a chain card destroyed earlier in the chain is neither re-resolved from the Graveyard nor face-up-flipped there. |
| D9 | LOW | `DAEffectRuntime.cpp` `ReadInt` (was 30-38) + `DADuelEngine.cpp` `GainLp` (was 4250-4257) | **fixed** | Script-read ints are clamped to ±1e9 with non-finite rejection (finite/NaN guard), and `GainLp` clamps the LP accumulator to the new `MaxLifePoints = 1e9` constant so malformed scripts can inflate but never overflow int32. |
| D-START | engine legality | `DADuelEngine.cpp` `Start` (was 243-282) | **fixed** | `Start` now fails closed on `!ValidateDeck(...).bValid` via new private `ValidateSideDeck` (resolves the deck id through `FindDeck`, validates Main+Extra), logging every error ("Deck validation failed: …" tone `error` + `UE_LOG` warning) and ending the duel before turn 1. See deck audit below. |
| C2 | refactor | `DADuelEngine.cpp` `GetAtk`/`GetDef` (was 1612-1758) | **fixed** | Extracted `void ApplyFieldStats(int32&, const FDuelCard&, bool bAtkStyle)` (exact requested signature); both stat getters delegate the field-spell ladder to it. No numeric behavior change. |
| C5 | refactor | `DADuelEngine.cpp` `MoveToHand/MoveToBanished/MoveToDeckTop/MoveToDeckBottom` (was 971-1050) | **fixed** | Extracted `NormalizeOutbound(FDuelCard&, bool bFaceUp)` (owner repatriation, face state used by the caller, position reset, equip/tie/counter clears). `MoveToHand` still clears `bSpecialSummoned` afterwards; deck moves keep their `bExtra`/Extra-Deck handling. |

Deferred-by-design per brief (not attempted): C1 name→descriptor table, C3
defensive-trap helper, C4 effect-state registry.

## Tests added (T-gaps)

All totals in both self-tests are derived from `Report.Check` counts, so the
printed summaries stay coherent automatically; no hardcoded totals existed.

- **T2** — `DADuelRulesSelfTest.cpp` (existing 137-card regression smoke):
  now also asserts the gate summary contains `"invariant failures 0"` and
  `"RESULT PASS"`, in addition to the old no-`"missing"` / `" 0 stalls,"`
  greps. Result-level failure can no longer pass this check.
- **T4** — `DAEffectRuntimeSelfTest.cpp` (next to the player-side
  `defense_at_end` test): AI-side scenario (Blue-Eyes with a
  `battle_position_lock mode=defense_at_end` continuous script; probe asserts
  Attack before, Defense after) drives `EndTurn()` + `RunOpponentTurn()`
  through the public handoff only, asserting the flip happened during the AI
  battle turn (requires D1) and the duel is not over.
- **T1** — `DAEffectRuntimeSelfTest.cpp`: 200-card scenario deck of identical
  card id 7 with an `on_sent_to_graveyard` `gain_lp` probe plus an
  `on_end` script that mills 200 in one operation. Asserts the one-time
  pending-queue warning appears exactly once, the cascade-limit message never
  appears, exactly 64 queued events dispatch (`ExecutedScriptCount == 65`
  including the mill script, LP delta `+64` pins the drop policy: newest
  events beyond the 64-entry cap are refused), and the duel stays live with
  no pending choice.
- **T3** — `DAEffectRuntimeSelfTest.cpp`: optional `on_end` script queues a
  player prompt in the player's End Phase; `EndTurn()` defers instead of
  queuing the AI turn (asserted), auto-answering still executes the optional
  effect (LP +100 asserted), the answer resumes the handoff
  (`IsAwaitingAi()` asserted), and `RunOpponentTurn()` completes the duel
  without a win/loss.
- **Batch honesty** — `DADuelEngineDiagnostics.cpp`: the AI-vs-AI gate drives
  the player battle phase through `EnterBattlePhase()` / `EndBattlePhase()` /
  `EndTurn()` (public actions) instead of writing `Duel.Phase` and
  `Duel.bAwaitingDiscard` directly; the unconditional `bAiTurnPending = true`
  handoff is kept for stall-safety. With `SetAutoAnswerAllChoices(true)` the
  D2 defer cannot trigger in the batch, and `ObservePhase` legality is
  preserved (Main1→Battle, Battle→Main2, turn-start Main1).

## D-START deck audit (read-only, support evidence)

Audited against the shipped ruleset bounds in
`Content/Data/Rules/banned_limited.json` (`min_main 40 / max_main 60 /
max_extra 15 / max_copies 3`, 61 per-card entries, 14 banned):

- `Content/Data/decks.json` starters (fire, water, wind, jaden): **all pass**
  (size, copy limits, per-card limits, database existence, Fusion placement).
- `Content/Data/Decks/player_decks.json`: 1 deck, **passes**.
- `Content/Data/Opponents/deks/*.json`: **32/32 pass** (registered by
  `UDAOpponentSubsystem::Reload` into the same `FindDeck` table `Start` uses).

No shipped deck would newly fail; nothing was forced. The gate's own
pre-`Start` audit (`DADuelEngineDiagnostics.cpp`, lines ~763-777) validates the
same two gate decks (`fire`/`jaden`), so the new `Start` enforcement and the
audit agree by construction. Production `Start` callers pass only registered
starter ids (deck-select lists `GetDecks()`), and scenario duels go through
`StartScenario`, which is intentionally not gated (puzzle boards are not legal
decks by design).

## Changes, rationale, API impact

- **New public API surface:** none. All new members are private:
  `FDuelVisualEventTargetInfo` (public struct, additive, but only consumed via
  a defaulted `EmitVisual` parameter — no caller needs it),
  `NormalizeOutbound`, `ApplyFieldStats`, `ValidateSideDeck`,
  `FinalizePlayerEndPhaseHandoff`, `ContinueDeferredPlayerHandoff`, member
  `bPlayerEndHandoffDeferred`. `FDuelEngine::Start` and `EmitVisual`
  signatures gain no required parameters.
- **D2 rationale:** `RequestOptionalTrigger` hardcodes the Player side
  (`DAEffectRuntime.cpp` ~2260-2281), so End-Phase optional triggers could
  leave the AI handoff "pending" while a player question was queued; the
  opponent then played through a possibly interactive prompt. The deferred
  handoff keeps phase Main2, holds `bAiTurnPending` false until the prompt is
  answered (or cancelled), and preserves the exact END PHASE presentation
  (`FinalizePlayerEndPhaseHandoff` shared by both handoff sites and the
  resume). Where the old hand-limit path never emitted the END PHASE
  PhaseChange visual, it now does — unifying both paths was required to share
  the resume tail.
- **D-START rationale:** decks failing legality were previously started
  silently (only the empty-deck case was caught). Failing closed keeps the
  legal-card invariants honest and matches the diagnostics gate that already
  audits all published decks; a rejection logs both engine Log (tone `error`,
  consumed by the in-duel log) and a `UE_LOG` warning with all validation
  errors joined (`"; "`), then ends the duel before turn 1, awarding the
  remaining-legal side (legacy unloaded-deck convention if both are illegal —
  no phantom player win into story/stats).
- **D5 ordering note:** the normal (non-short) case also now discards both
  hands before drawing, which is the real card's simultaneous resolution and
  the requested mirror; Graveyard leave-triggers therefore run before either
  side's draw refills (AI-vs-AI batch outcome mix may shift accordingly, the
  gate asserts only RESULT PASS).
- **D3 rationale note:** the reason string for AI-activated one-shot Spells
  changes from the card's own name to `"resolve"`. No shipped script or
  condition keys off a reason that equals an activating spell's name
  (`"reason"` conditions/costs: 0 occurrences in all 253 script files;
  op-level reasons are labels only), and it matches `ActivateTrapInternal` /
  the deferred-cleanup path.

## Static verification performed

(Compilation and execution are parent-owned; the items below are what this
session verified without build tooling.)

- Brace/paren/bracket balance checked on all five edited sources plus the
  header (0 for all).
- Trailing whitespace 0 and LF-only line endings preserved on every edited
  file (project convention) — `git diff --check` should be clean.
- Header decl/def symmetry: `NormalizeOutbound`, `ApplyFieldStats`,
  `ValidateSideDeck`, `FinalizePlayerEndPhaseHandoff`,
  `ContinueDeferredPlayerHandoff`, `bPlayerEndHandoffDeferred`,
  `FDuelVisualEventTargetInfo`, and the `EmitVisual` default parameter are
  declared exactly where defined; `FDuelDeckValidationResult` is available via
  the existing `DADuelRules.h` include.
- All new test code uses public API only (`EndTurn`, `IsAwaitingAi`,
  `RunOpponentTurn`, `GetSide`, `FindMonster`, `GetPendingChoice`,
  `AutoAnswerPendingChoice`, `GetLog`, `GetExecutedScriptCount`,
  `LoadScriptJsonText` via the existing `LoadTestScript` helper); no private
  member access from the self-tests (unlike the diagnostics TU, which defines
  engine member functions legitimately).
- Trigger mapping and field-scan tables re-read to confirm the T1/T3 scripts
  (`on_end`, `on_sent_to_graveyard` self-probe) actually route through the
  intended paths (`TriggerFromString`, `IsSelfOnlyTrigger`, `bScanField`).
- Read-only data audit of deck legality (above) and of the shipped effect
  scripts (253 files) for reason-condition usage.

## Remaining risks

1. **Not executed:** every self-test and the gate batch remain parent-run. T2
   explicitly asserts `"RESULT PASS"`, so the D5 ordering change and the
   honesty rewrite of the AI-vs-AI batch are covered at integration time; if
   that gate fails, the first suspects are the batch rewrite
   (`EnterBattlePhase`/`EndBattlePhase`/`EndTurn`) and D5, not D1/D2 engine
   semantics (AI seeds are unchanged, but end-phase triggers now really run in
   the batch).
2. **AI End-Phase prompts** (pre-existing, out of D2 scope by its "minimal
   change" instruction): an optional trigger whose owner is the opponent can
   still queue a player prompt during the opponent's End Phase, and
   `RunOpponentTurn` only drains Opponent-side choices; the prompt then sits
   pending into the player's next turn (answerable, not dropped). Fixing that
   properly means restructuring the dominance/priority window and was
   explicitly not attempted. T3 documents this behavior in a comment.
3. **`OnBattleEnd` is side-agnostic** (`EndBattleDefenseUids` holds uids of
   both sides): with D1 it now fires for every Battle Phase end rather than
   only the player's. That matches the effect's printed rules and removes the
   one-turn-late flip, but side-scoped expiry (per controller) would be a
   data/semantics change outside this pass.
4. **`PendingEvents.Reset()` on cascade overflow** (pre-existing): when the
   128-dispatch cascade cap trips, the whole queued backlog is dropped at
   once. T1 only exercises the pending-queue cap in isolation; a deliberate
   cascade-cap scenario was not scripted because both caps share the one
   `bEventBudgetWarned` flag and would suppress each other inside one
   `FireEvent` chain.
5. **D2 + HUD:** `FDADuelUI` polls `IsAwaitingAi()` and answers prompts
   through `AnswerChoice`/`CancelChoice`, so the resume path is sufficient as
   written; if a future consumer answers pending choices through a path that
   bypasses `AnswerChoice`/`CancelChoice`/`AutoAnswerPendingChoice`, it must
   call `ContinueDeferredPlayerHandoff()` itself (private; reuse
   `AutoAnswerPendingChoice`).
6. **D9 clamp bounds (±1e9)** are far above any legal script value (card ids
   ≤ ~12000, LP effects ≤ ~1e6) but are policy, not rules law: if a future
   shipped effect legitimately needs larger intermediate integers, the bound
   must move with it (single constant in each file).
