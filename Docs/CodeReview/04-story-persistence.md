# 04 — Story, progression & persistence

Branch: `refactor/code-review-pass`

Scope: `DAStorySubsystem.*`, `DAStoryPlaythroughTest.*`,
`DAStorySelfTest.cpp` (new), `DASaveGame.*`, `DAProfileSubsystem.*`,
`DACalendarSubsystem.*`, `DAExamSubsystem.*`, `DAEventGraph.*`,
`DAOpponentSubsystem.*`, `DAInventorySubsystem.*`, `DAShopSubsystem.*`,
`DADeckLogic.*`, and this report. No content/data, Python or out-of-scope C++
was changed.

## Summary

The runtime story unit was the largest structural problem: `DAStorySubsystem.cpp`
was 4,340 lines, with `RunFullStorySelfTest` (663 lines) and its condition-state
collectors compiled into the gameplay subsystem. This pass moved that test-only
code into `Private/DAStorySelfTest.cpp`; the moved body was diffed against the
original after helper renaming and is byte-for-byte identical in content.

The review also fixed high-confidence persistence defects:

- story state serialized `TSet` values in nondeterministic order;
- `LoadState` kept stale runtime fields when JSON fields were absent and
  accepted non-string/non-number array elements;
- save providers could silently overwrite each other's root sections;
- `MigrateJson` let a stale caller version outrank an explicit JSON version;
- shop save import accepted negative counts (which could bypass stock/restock
  checks) and could report an external wallet while still using the cached one;
- inventory addition/import and exam scoring had unchecked integer growth.

The save-file trailer checksum path was audited in detail and is correct: the
CRC is computed over the same archive bytes on write and read, and the payload
hash is computed over `JsonPayload` on both paths. No checksum change was made.

`ApplyOutcomes` (217 lines) and `ExecuteCommand` (364 lines) were reviewed but
not mechanically split. Only the duplicated card-grant, pack-grant and
title-grant blocks were extracted from the outcome/reward paths; the command
switch remains a single readable dispatch and is left as a follow-up.
`DAStoryPlaythroughTest.*` was reviewed and needed no change; profile and
calendar logic were reviewed with only low-risk follow-ups recorded (F24/F25).

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| F1 | High | `DAStorySubsystem.cpp:3164` | `SaveState` iterated `CompletedEvents`, `AppliedRewardIds` and `UnlockedDuels` (`TSet`) directly, so the nested state string could differ between two saves of identical state. | Fixed for the set-derived arrays: copy and sort before writing. The nested `pending_packs`/`objectives` object key order still comes from `TMap`; see follow-up 7. |
| F2 | High | `DAStorySubsystem.cpp:3229` | `LoadState` used `TryGet*Field` without resetting the members first. A partial or legacy payload therefore inherited `CurrentEventId`, `CurrentSceneId`, `CommandIndex`, `bRunning`, `bFreeRoam`, etc. from the live run. Array entries were also accepted from any JSON type via `AsString`. | Fixed: reset to safe defaults first, clamp the command index, require string entries, and validate pack counts as finite positive numbers. Partial payloads still load (the economy self-test queues grants with `{"pending_packs":...}`). |
| F3 | Medium | `DAStorySubsystem.cpp:3477` | `RunFullStorySelfTest` plus `CollectConditionState`/`CollectEventState` lived in the runtime translation unit. | Fixed: moved to `DAStorySelfTest.cpp`; declarations stay on `UDAStorySubsystem`. |
| F4 | Medium | `DAStorySubsystem.cpp:2350` | `double_dp`/`dp_multiplier` computed `CurrentDP * (Multiplier - 1)` in `int32`; a large balance or multiplier overflowed before `AwardDP` could clamp. | Fixed: 64-bit multiply, clamped to `int32`. |
| F5 | Medium | `DASaveGame.cpp:1083` | Provider sections share one root object namespace. Two providers with the same (or case-different) section name silently overwrote the earlier section on write and both read the surviving object on load. | Fixed: reject duplicate provider section names during `BuildPayload`. |
| F6 | Medium | `DASaveGame.cpp:53` | `IsSafeSlotName` only rejected `/`, `\`, `:` and `..`. Windows-invalid characters, control characters, leading/trailing dots and trailing spaces were accepted as file names. | Fixed: tightened the allow/deny check. Existing `DASave_*` and self-test names are unaffected. |
| F7 | Medium | `DASaveGame.cpp:1392` | `MigrateJson` started from `FMath::Max(FromVersion, JsonVersion)`. A caller passing a stale/too-new `FromVersion` could skip a migration even when the payload itself declared an older version. | Fixed: an explicit JSON `version` is authoritative; otherwise the caller argument is used. |
| F8 | Medium | `DAShopSubsystem.cpp:1064` | `ImportStateJson` cast any JSON value to `int32` with `AsNumber`, including negative values. Negative purchase counts increased `GetRemainingStock` above the real stock and negative last-purchase days bypassed restock; `internal_wallet=false` without handlers still used `CachedDP`. | Fixed: require numeric, finite, non-negative values; clamp; force the fallback wallet when any handler is missing. |
| F9 | Medium | `DAShopSubsystem.cpp:415` | `SetWalletHandlers` accepted a missing credit handler. If a purchase charged DP and then failed to open, the refund was silently dropped. | Fixed: all three handlers are required; otherwise the internal wallet stays active. |
| F10 | Medium | `DAInventorySubsystem.cpp:212` | `AddCard` computed `Owned + Added` and `MaxOwnedCopies - Owned` in `int32`; a save-driven large count could overflow. `CanAddCard` had the same addition issue. | Fixed: 64-bit space/limit math, clamped result, return the actual added count. |
| F11 | Medium | `DAInventorySubsystem.cpp:1029` | `ImportStateJson` parsed card keys with `Atoi` and counts with an unchecked `AsNumber` cast. | Fixed: `Atoi64` range check, numeric type check, finite/positive clamp. |
| F12 | Medium | `DAExamSubsystem.cpp:628` | `RecordPracticalEvent` added `Amount` to progress in `int32`; `ScoreWritten`/`ScorePractical` and `FinishExam` summed in `int32`. | Fixed: 64-bit intermediate values, clamped totals. Negative practical objective points/targets are normalized on load. |
| F13 | Medium | `DAExamSubsystem.cpp:464` | `StartExam` accepted a cycle with an empty question list when a legacy `ExamSets` entry existed, then started with zero questions. | Fixed: fall back to the set only when the cycle list is empty, and reject an empty selection. |
| F14 | Medium | `DAEventGraph.cpp:341` | An `event` condition with any `state` other than `"complete"` (including `"incomplete"`) evaluated as true. | Fixed: `"incomplete"` now means not complete; unknown states still pass as before. |
| F15 | Low | `DAEventGraph.cpp:204` | `EventCompletionFlag` stripped any leading `e`, so an id such as `exam_01` became `event_xam_01_cleared`. | Fixed: only strip `e` when followed by a digit (`E01`, `E01b`). |
| F16 | Low | `DAOpponentSubsystem.cpp:62` | `ReadIntArray` accepted strings/bools as numbers and did not clamp non-finite/out-of-range values. | Fixed: accept numeric JSON only, clamp to `int32`. |
| F17 | Low | `DADeckLogic.cpp:1091,1153` | Deck save/import duplicate detection was case-sensitive while runtime lookup is case-insensitive, so `Player_1` and `player_1` could both load. | Fixed: compare ids case-insensitively. |
| F18 | Info | `DASaveGame.cpp:258-308` | Trailer CRC, archive-size check, `PayloadHash`, and the temp/primary/backup ordering were reviewed. The checksum inputs match exactly and the backup is only replaced after the staged file verifies. | No change. |
| F19 | Info | `DASaveGame.cpp:1122` | `ApplyPayload` mutates calendar, settings and profile before provider sections are read. A provider read failure therefore leaves a partially applied load. | Follow-up: providers need a two-phase validate/apply API. |
| F20 | Info | `DAStorySubsystem.cpp:3164` | Story state does not persist `PendingDuel`/waiting flags. Loading a save made while a duel is pending replays the duel command; if the duel UI already recorded the result, counters can be counted again. | Follow-up: add pending-duel fields to the state schema (additive). |
| F21 | Info | `DAStorySubsystem.cpp:2225` | Event outcomes are guarded per event completion, but non-reward outcomes (grant_card/grant_pack/grant_dp/item) have no per-outcome idempotency key. Re-running an event that never completed can grant again. | Follow-up: authored outcome ids or an event/outcome-index ledger. |
| F22 | Info | `DAShopSubsystem.cpp:232` | `purchase_limit` is parsed and validated but never enforced. Restock days and stock are enforced. | Follow-up: needs a product decision on per-visit vs lifetime limit. |
| F23 | Info | `DAOpponentSubsystem.cpp:373,816` | `DuelRequest.CooldownDays` is parsed but unused, and `CanRequestDuel` does not consult `DuelRequest.UnlockFlag` (it has no flags argument). | Follow-up: extend the request API or let the caller gate it. |
| F24 | Low | `DACalendarSubsystem.cpp:323,579` | At `MaxSupportedYear`, `AdvanceDay` wraps to October of the same year (moving backwards), and `GetCalendarYearForMonth` can return `MaxSupportedYear + 1` for Jan–Sep. | Follow-up; unreachable in the 12-month campaign. |
| F25 | Low | `DAProfileSubsystem.cpp:729,894` | `WriteSaveData` writes `initialized` but `ReadSaveData` ignores it and always sets `bInitialized = true`. | Follow-up; the field is redundant today. |
| F26 | Medium | `DAStorySubsystem.cpp:3372` | `ReadSaveSection` treated a present section with no `state` string as success, silently keeping whatever story state happened to be in memory. | Fixed: a present story section now requires a non-empty `state` payload. |

## Changes

### Story runtime

- Created `Private/DAStorySelfTest.cpp` (817 lines) containing
  `RunFullStorySelfTest`, `CollectConditionState` and `CollectEventState`. Local
  read helpers are namespaced `SelfTestRead*` so they cannot collide with the
  anonymous-namespace helpers in `DAStorySubsystem.cpp` under unity builds.
- `SaveState` sorts its three set-derived arrays.
- `LoadState` resets runtime fields before reading, validates array element
  types, clamps `CommandIndex` and pack counts, and clears stale choice/text
  input and pending-duel state.
- Extracted `GrantCardReward`, `AddPendingPackGrant` and `ApplyTitleReward` and
  reused them from `ApplyOutcomes`, `ApplyRewardById` and
  `ApplyRewardCommand`. Pack-grant addition is clamped.
- `double_dp` uses a 64-bit intermediate.

### Save subsystem

- `IsSafeSlotName`: reject control and Windows-invalid characters, leading/
  trailing dots and trailing/leading spaces.
- `BuildPayload`: reject duplicate provider section names (case-insensitive)
  in addition to reserved names.
- `MigrateJson`: an explicit JSON `version` now wins over `FromVersion`.

### Economy / progression

- `DAShopSubsystem`: validated save import, clamped cached-DP credit, required
  all wallet handlers, and rejected non-positive pack prices in `CheckPurchase`.
- `DAInventorySubsystem`: overflow-safe `AddCard`/`CanAddCard`, validated
  import counts.
- `DAExamSubsystem`: overflow-safe practical progress and scoring, safe empty
  cycle fallback, non-negative objective target/points.
- `DAEventGraph`: correct `state:"incomplete"` handling and narrower `E`
  prefix stripping.
- `DAOpponentSubsystem`: numeric/clamped integer arrays.
- `DADeckLogic`: case-insensitive duplicate deck ids on save load.

## Verification

**Integration:** the combined editor build passed; profile, story, full-story,
story-playthrough, save-fuzz (300 states), and twelve-month tests all pass. See
[00-overview.md](00-overview.md).

- `git diff --check` over every tracked in-scope file: clean (exit 0); the two
  new files were checked separately for trailing whitespace.
- Reviewed the full diff of every changed in-scope file.
- Moved self-test body compared line-by-line against
  `HEAD:DAStorySubsystem.cpp` after the expected helper renames:
  `identical: True`.
- `DAStorySubsystem.cpp` reduced from 4,340 to 3,629 lines; the new
  `DAStorySelfTest.cpp` is 817 lines.
- No UnrealBuildTool or UnrealEditor run was performed by this workstream; the
  parent session owns the build and headless test runs. No data files were
  edited.

## Follow-ups

1. Make save load two-phase. `ApplyPayload` currently applies calendar,
   settings and profile before provider sections; a provider error leaves a
   partially loaded game even though the call returns false. F19.
2. Persist pending-duel state (opponent, branch scenes, command index) instead
   of replaying the duel command after load. F20.
3. Add stable outcome ids (or an event/outcome-index ledger) so non-reward
   outcomes are idempotent across an interrupted event. F21.
4. Decide and implement `purchase_limit` semantics; wire opponent
   `CooldownDays`/`UnlockFlag` into the request gate. F22/F23.
5. Consider rejecting a story save section whose version is newer than the
   build; the outer provider version is currently informational only.
6. Calendar `MaxSupportedYear` wrap behavior and profile `initialized` are
   low-risk edge cases; leave until the calendar/profile schemas next change.
7. If save files must be byte-identical for identical state, canonicalize the
   nested `state` string too. `SaveState` now sorts its arrays, but the
   `pending_packs`/`objectives` object keys still use `TMap` iteration order.
   Reusing the save subsystem's canonical serializer would close this.
