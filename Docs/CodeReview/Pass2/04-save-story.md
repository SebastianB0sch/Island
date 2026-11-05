# 04 — Story, progression & persistence (pass 2)

Branch: `refactor/code-review-pass`

Scope: `DAStorySubsystem.*`, `DAStorySelfTest.cpp`,
`DAStoryPlaythroughTest.*`, `DASaveGame.*`, `DAProfileSubsystem.*`,
`DACalendarSubsystem.*`, `DAEventGraph.*`, `DAOpponentSubsystem.*`,
`DAInventorySubsystem.*`, `DAShopSubsystem.*`, `DADeckLogic.*`, and this
report. The first review pass is the baseline. No UI, duel-engine, effect
runtime, generated data, or out-of-scope report was changed.

## Summary

This pass makes save loading transactional and closes the story/progression
follow-ups left by pass 1:

- provider sections are validated before any live state is touched, and the
  complete current state is snapshotted so a late provider failure rolls the
  whole load back;
- pending-duel state (opponent, deck, branch scenes, command index, tutorial /
  DP flags and pre-duel counters) is persisted and re-presented instead of
  replaying the duel command;
- event and choice outcomes use an event/outcome-index ledger, so an
  interrupted event cannot grant the same card, pack or DP twice;
- the nested story `state` string uses the save subsystem's canonical
  serializer, removing `TMap` order from the bytes;
- the calendar no longer wraps backwards at `MaxSupportedYear`, profile
  `initialized` round-trips, opponent `CooldownDays` is enforced, and the
  remaining low-risk items are either fixed or documented with a contract.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| F19 | Medium | `DASaveGame.cpp` `ApplyPayload` | Calendar, settings and profile were mutated before provider sections were read. A provider read failure left a partially loaded game. | Fixed: `ValidatePayload` pre-validates every present provider section, then `ApplyPayload` snapshots the live payload and applies through `ApplyPayloadInPlace`; a failure restores the snapshot. Added `IDASavePayloadProvider::ValidateSaveSection` (default accepts) and `UDASaveSubsystem::LoadPayloadJsonWithContext` for in-memory tests. |
| F20 | Medium | `DAStorySubsystem.cpp` `SaveState`/`LoadState` | Pending duels were not serialized, so a save made while awaiting a duel replayed the duel command after load. | Fixed: additive `waiting_for_duel` + `pending_duel` object (opponent, name, deck, mode, on-win/lose/draw, tutorial, award-DP, opened/elapsed, pre-duel win/loss/draw counters). `LoadState` restores the awaiting-result state and sets a transient resume flag; `Tick` re-opens the same duel selector. If the loaded profile already contains the duel result, `LoadState` resolves the saved branch immediately instead of re-presenting the duel. Old saves without the fields keep the historical replay fallback. |
| F21 | Medium | `DAStorySubsystem.cpp` `ApplyEventOutcomes`/`ApplyOutcomes` | Non-reward event/choice outcomes had no per-outcome idempotency key; replaying an interrupted event could grant again. | Fixed: sorted `applied_outcomes` ledger keyed by `event:<id>:<index>` or `choice:<event>:<scene>:<command>:<line>:<choice-id>:<index>`. Condition-gated outcomes are marked only when they run. Old saves load with an empty ledger. |
| — | Medium | `DAStorySubsystem.cpp` `SaveState` | Nested `pending_packs`/`objectives` object keys followed `TMap` iteration order. | Fixed: `SaveState` returns `UDASaveSubsystem::SerializeCanonicalJson(Root)`, reusing the existing canonical serializer. Outer format is unchanged; only the embedded state string is now key-sorted. |
| F22 | Low | `DAShopSubsystem.cpp` `CheckPurchase` | `purchase_limit` is parsed but not checked. | No code change. All shipped rows use `purchase_limit: 1` with a restock window, and the existing restock gate already enforces one purchase per window. Enforcing it as a lifetime count would make `stock` values of 20–30 meaningless, so the per-restock interpretation is documented here rather than guessed. |
| F23 | Low | `DAOpponentSubsystem.cpp` `CanRequestDuel` | `DuelRequest.CooldownDays` was parsed but unused. | Fixed: `FDAOpponentRuntimeState::LastRequestDay` records the last consumed day; `CanRequestDuel` rejects a request before the cooldown expires (0 means no cooldown). `UnlockFlag` remains caller-gated: `CanRequestDuel` has no profile/flags input, and callers are expected to use `IsDuelistUnlocked` first. |
| F24 | Low | `DACalendarSubsystem.cpp` `AdvanceDay`/`GetCalendarYearForMonth`/`GetNextExamDate` | At `MaxSupportedYear`, `AdvanceDay` wrapped to October of the same year and moved the absolute day backwards; the calendar-year helper could return `MaxSupportedYear + 1`; the next-exam scan could return a month in the past at the bound. | Fixed: the last supported day (Sep 30, `MaxSupportedYear`) is terminal, so the date never moves backwards; the calendar-year conversion clamps at the supported bound; the exam scan stops instead of wrapping. |
| F25 | Low | `DAProfileSubsystem.cpp` `ReadSaveData` | `initialized` was written but ignored on load. | Fixed: reads the field, defaulting to `true` when absent so older saves still load as initialized. |
| F26 | — | `DAStorySubsystem.cpp` `ReadSaveSection` | Present story section with no state payload was accepted. | Re-reviewed; pass 1 fix retained. The new validator also rejects non-string/empty `state` and malformed state JSON before apply. |

## Changes

### Save subsystem

- `IDASavePayloadProvider` gained a non-mutating `ValidateSaveSection`
  override point (default accepts the object) and the save subsystem gained a
  public static `SerializeCanonicalJson`.
- `UDASaveSubsystem::ValidatePayload` checks the profile object and every
  present provider section. `ApplyPayload` then snapshots the current payload
  through `BuildPayload`, applies through `ApplyPayloadInPlace`, and restores
  the snapshot if anything fails.
- `LoadPayloadJsonWithContext` parses/applies an in-memory payload through the
  same two-phase path for tests. `LoadNamedSlotWithContext` is unchanged from
  the caller's point of view and now inherits transactional behavior.
- `DAStorySubsystem`, `DAInventorySubsystem` and `DADeckLogic` implement
  provider validation. Story validates the embedded state JSON, inventory
  requires the `counts` object, and decks validate count/entries/duplicates
  without mutating the deck list.

### Story runtime

- `FDAStoryPendingDuel` gained `bAwardDP` / `PreLosses` and the save schema
  gained `waiting_for_duel` / `pending_duel`. `CapturePendingDuel` records the
  award-DP flag and all pre-duel counters; `ResolvePendingDuel` clears the
  resume state.
- `LoadState` restores the pending duel only when the saved command index still
  points at a `Duel` command in the restored scene; otherwise it clears the
  pending state instead of soft-locking. If the loaded profile counters show
  that the duel result was already recorded, it resolves the saved branch
  immediately. Otherwise `Tick` re-opens `ADAHUD::OpenDuelDeckSelect` once and
  waits for the real result. It never replays the duel command for new saves.
- `ApplyOutcomes` takes a stable context key and skips already-ledgered
  outcome indices. Event outcomes use `event:<id>`; choice outcomes use
  `choice:<event>:<scene>:<command>:<line>:<choice-id>`; the outcome index is
  appended to each.
- `ResetRuntimeState` and `LoadState` clear the ledger; `SaveState` sorts and
  persists it.
- `SaveState` uses `UDASaveSubsystem::SerializeCanonicalJson`, so nested
  `pending_packs` and `objectives` keys are deterministic.

### Progression / economy

- `DACalendarSubsystem::AdvanceDay` treats the last supported day as terminal
  and does not wrap; `GetCalendarYearForMonth` clamps to the supported year,
  and `GetNextExamDate` stops instead of scanning into a wrapped year.
- `DAProfileSubsystem::ReadSaveData` honors `initialized`, defaulting to `true`
  for payloads that predate the field.
- `DAOpponentSubsystem` records `LastRequestDay` and enforces
  `DuelRequest.CooldownDays`; the existing `MaxPerDay` path is unchanged.
- `DAShopSubsystem` is unchanged for `purchase_limit`; see F22.

### Tests

- `DAStoryPlaythroughTest` gained a persistence-regression section:
  - malformed story provider section is rejected and leaves profile, calendar
    and story state untouched;
  - pending-duel save/load restores opponent, deck, branch scenes, command
    index and awaiting-result state without queuing a replay, and a pending
    duel whose result is already recorded resolves the branch instead of
    re-opening the selector;
  - replayed outcomes grant DP/packs once, including after a save/load;
  - nested story state is byte-identical under reversed map insertion order;
  - calendar `MaxSupportedYear` does not wrap, max-year February stays in
    range, and the next-exam scan never moves backwards;
  - profile `initialized=false` round-trips;
  - an opponent with a multi-day roster cooldown is blocked early and allowed
    after the cooldown.
- `DAStorySelfTest` (`RunFullStorySelfTest`) gained the same failing-provider
  check, so a full-campaign audit also covers the F19 transaction.

## Verification

- `git diff --check` over every changed in-scope file: clean (exit 0). No
  whitespace errors; only the repository's pre-existing CRLF notices.
- Reviewed each changed hunk, including the new save apply/validate path and
  the pending-duel state machine.
- No UnrealBuildTool or UnrealEditor run was performed by this workstream, per
  the brief. The parent session owns the combined build and headless runs.
- `DAA02GateTests.cpp` (save-fuzz) is outside this workstream's edit scope, so
  the failing-provider case was added to the story self-test and playthrough
  instead of duplicating the save-fuzz harness. The parent can call
  `-DAFullStorySelfTest` / `-DAStoryPlaythroughTest` to exercise it.

## Remaining risks / follow-ups

1. The rollback path is defensive: current providers can all be rejected by
   validation, so no shipped provider is known to fail only during
   `ReadSaveSection`. A test-only provider would be needed to force that exact
   branch.
2. The outcome ledger protects saves written by this build. A save created
   before the ledger existed can still duplicate an event's effects once if it
   was interrupted between outcome application and completion.
3. `LastRequestDay` is part of the transient opponent runtime state. If A02
   starts persisting `FDAOpponentRuntimeState`, it should include this map, or
   cooldowns reset across save/load.
4. `DuelRequest.UnlockFlag` is still not enforced by `CanRequestDuel` because
   the API has no flags input. UI callers should continue to gate with
   `IsDuelistUnlocked` / the profile `met_*` flags. Adding a flags-aware
   overload is the clean follow-up if the PDA needs it.
5. `purchase_limit` semantics remain per-restock, inferred from the shipped
   data (`purchase_limit: 1` + `restock_days`). If future data needs a
   per-visit or lifetime cap, add explicit state before changing behavior.
6. Whole-file bytes still differ between saves because `saved_at` is
   intentionally regenerated. Identical state now produces identical nested
   story bytes; the outer metadata timestamp is unchanged.
7. A payload that explicitly sets `profile.initialized=false` leaves the
   profile uninitialized and therefore rejects `SaveSlot` until a new game or
   a corrected load. This only affects malformed/legacy-hand-edited payloads;
   old payloads omit the field and default to initialized.
8. UI contract for pending-duel resume: after a load with a restored pending
   duel, the story tick calls `ADAHUD::OpenDuelDeckSelect` with the persisted
   opponent/deck/mode/award-DP values. The UI must tolerate being asked to open
   the selector after loading; no UI file was changed.
