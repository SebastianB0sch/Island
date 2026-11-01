# WS-02 — Persistence & story (Pass 4 implementation report)

Branch `refactor/code-review-pass`, checkpoint `77cc9c7`. Run as a concurrent
workstream; only the files in the brief's WS-02 ownership list were edited.

## Scope & constraints

- Owned (and therefore the only files touched):
  `DASaveGame.{h,cpp}` (header unchanged, .cpp changed), `DAStorySubsystem.{h,cpp}`,
  `DAStoryPlaythroughTest.cpp`(+ `.h` unchanged), `DAEventGraph.cpp` (+ `.h`
  unchanged), `DAOpponentSubsystem.cpp` (+ `.h` unchanged),
  `DAOpponentTests.cpp`, `DACalendarSubsystem.{h,cpp}`, `DASettings.{h,cpp}`
  (header unchanged, .cpp changed), `DAIslandManager.{h,cpp}` (unchanged — see
  below).
- No Unreal processes used (no UBT/Editor/commandlets). Verification below is
  static, plus the brief-permitted `git diff --check` and read-only running of
  the data audits.
- Read everything, touched nothing outside the list: `DAHUD.cpp` refusal path,
  `DADuelUI.h` contract, `DAStudentCharacter.h` contract, `DAProfileSubsystem`,
  `DADeckLogic`, `DAIslandSubsystem` (API only), `DAStorySelfTest.cpp`,
  `DAA02GateTests.cpp`, `DAProfileSelfTest.cpp` were read to verify pinned
  contracts and caller expectations.
- Goldens, schema, manifests and committed assets untouched.

## Pinned contracts consumed

- `FDADuelUI::WasDeckSelectClosedWithoutResult() const` — declared in
  `DADuelUI.h:112` (WS-04) as pinned. JSON value semantics taken from the DADuelUI
  comments: true iff the most recent story deck-select ended without a duel
  result; cleared on the next recorded result / close-with-result; survives
  `StartDuelWithDeck`. WS-02 does not edit the type.
- `ADAStudentCharacter::NotifyTeleportArrived()` — confirmed present (WS-04→WS-05),
  not consumed by this workstream's files.

## Findings table

| ID | Sev | File:line (as reported / verified) | Status |
|----|-----|-------------------------------------|--------|
| P4-01 | P1 | `save.v1.schema.json:111` + `golden_*.json:152/46` vs `DASettings.cpp:87-98,430-437` | **fixed** |
| P4-02 | P2 | `DAStorySubsystem.cpp:1367-1373` inference → `ResolvePendingDuel(false,false)` at 3046-3075 | **fixed** |
| P4-03 | P2 | `DAHUD.cpp:529-540` refusal + `DAStorySubsystem.cpp:1374-1392` loss fallback | **fixed** (story-side only) |
| P4-04 | P2 | `DASaveGame.h:226-228` trigger set | **partial fixed + hand-offs** (event completion & day change wired; shop purchase & exam result are other lanes' files, listed below) |
| P4-05 | P3 | `DAStorySubsystem.cpp:3400-3422` ReadStringSet, 3600-3625 Validate | **fixed** |
| P4-06 | P3 | `DASaveGame.cpp:856-871` vs file-path migration 1453-1462 | **fixed** |
| P4-07 | P3 | `DAEventGraph.cpp:578-614` EvaluateTrigger | **fixed** |
| P4-09 | P3 | `DAOpponentSubsystem.cpp:949-1012` (realign 1001-1004) | **fixed** |
| P4-15 | P4 | `DAEventGraph.cpp:128-191` + story loaders | **fixed** |
| U3 | MED | `DAStorySubsystem.cpp:2838-2879` CompleteEvent never counted `story_events_cleared` (`DATitleSystem.cpp:579`, thresholds 20/33 at 183/193; migration key `DASaveGame.cpp:533`) | **fixed** |
| W9 | LOW | `DACalendarSubsystem.cpp:640` writes hour, ReadSaveData never reads | **fixed** |
| W13 | LOW | `DACalendarSubsystem.cpp:266-288` SkipToDate day-by-day | **fixed** |
| P4-13 | P4 | `DACalendarSubsystem.cpp:501-524` GetNextExamDate boundary | **deferred (conservative read), documented** |
| V2 residual | P4 | starter flags at `DAStorySubsystem.cpp:2776-2777`/reward ledger at 2551 | **fixed** |
| P4-08 | P2-def | modal-blocked infinite wait | **deferred per brief**, policy documented |
| P4-12 | P2-def | choice ledger key scheme | **deferred per brief**, unchanged |
| P4-11 | — | economy/profile | **not mine** (WS-03); not touched |

## Changes, rationale, API/serialization impact

### P4-01 — golden saves could not load (P1)

`save.v1.schema.json:111` declares `settings.animation_speed` as an
`integer 0..3` and both goldens ship `"animation_speed": 2`, while
`ReadStringField` rejected any non-string — a golden load died wholesale in
`Settings->ReadSaveData`, failing the whole `ApplyPayload` (and after rollback,
the whole load).

- `DASettings.cpp`: new `ReadSpeedField` helper — strings pass through
  unchanged; an integral number `0..3` is coerced to its decimal string
  (`2` → `"2"` → `StringToAnimationSpeed` → canonical `fast`), anything else
  (non-integral, out of range) is rejected with the standard shape error so a
  corrupt settings block cannot half-apply. Applied to `animation_speed`
  **and** `text_speed` — the schema declares text_speed the same way
  (`integer 0..3`), it is the same defect class and one call site each; no
  simpler/coarser policy was invented.
- Schema and goldens deliberately left untouched.
- New runtime fixture (see below) loads both goldens through the real
  `LoadPayloadJsonWithContext` path and asserts: load success + empty error,
  name Alex/DP 3000/Slifer, Oct 7 Year 1 AM Saturday, flags
  (`registered`, `met_jaden`, `first_free_roam`, `event_01_cleared` — the full
  set only for `golden_new_game.json`, the runtime golden carries the first
  two), inventory counts cover every `decks.player_1` card (per-card occurrence
  counts), active deck `player_1` with 40 main + 1 extra, email `jaden`
  unlocked with `jaden_01` read, opponents runtime reset (absent section),
  world section byte-identical before/after (untouched lane), saved hour
  honored, and `animation_speed` coerced to `Fast`.
- `golden_runtime_v1.json` additionally round-trips through a real `.sav` slot:
  save via `SaveNamedSlotWithContext`, reload via `LoadNamedSlotWithContext`,
  identity checks, then `DeleteNamedSlot` cleanup. (P4-01 first message lists
  DP/name/dorm etc.; the "round-trip" wording is realized as the
  load→save→reload cycle for the runtime golden.)

### P4-02 — deck-select close-without-result was a phantom loss

`FDADuelUI::WasDeckSelectClosedWithoutResult()` is now consulted by the story
tick before the counter-inference branch. The pending-duel tick decision was
extracted into a pure policy function (`DecidePendingDuelTick` in
`DAStorySubsystem.h`, enum `EDAStoryDuelTickDecision`) that the real tick
executes and the harness asserts. Ordering: open→None/`bOpened`, resume→Reopen
(`Elapsed>0.5 && !modal`, unchanged), close-without-result→**Reopen** (never a
loss), opened→ResolveInferred, `Elapsed>10`→ResolveLoss (genuine), throttled
retry→RetryRequest. Reopen resets `Elapsed`/`bOpened` and re-issues the ask;
the same selector is re-presented indefinitely while the player keeps backing
out (stay-pending semantics from the finding).

Regression assertions (playthrough persistence block): re-present outranks the
inferred loss for both the fresh and saved/resumed states; an open selector
only marks the duel opened; a restored duel re-opens when the screen frees up;
a properly closed duel still resolves by inference.

### P4-03 — silently-refused initial open burned a 10s loss

Story-side only, per the constraint (HUD untouched): `ExecuteCommand('duel')`
and every re-present now share a `OpenPendingDuelDeckSelect(ADAHUD&)` helper;
a new `DuelOpenRetryTimer` (0.5s interval) re-issues `OpenDuelDeckSelect` while
the selector has not opened and `Elapsed<=10`, so transient refusals
(title open, another duel — `DAHUD.cpp:536-539`) recover automatically and the
loss timer remains the last resort. A genuinely absent HUD keeps the existing
no-HUD fallbacks (>1s and the restored-duel >10s loss). Reset on: open, reopen,
resolve, `ResetRuntimeState`, `LoadState`.

Regression assertions: refused ask retried before the loss timer; 12s without
an open selector is still a real loss.

### P4-04 — autosave triggers

- **event completion**: `UDAStorySubsystem::CompleteEvent` now ends with
  `Profile->RequestProgressionAutosave(TEXT("event_complete"))` (the same
  lowercase reason style as the profile's `duel_result`/`result_token`).
- **day change**: `UDACalendarSubsystem::NotifyProfileDayChanged` (the existing
  cross to `Profile->NotifyDayChanged`) now also calls
  `Profile->RequestProgressionAutosave(TEXT("day_change"))`. Intentionally
  reached only through real day changes (`SetDate` day change / `AdvanceDay`);
  `Calendar::ReadSaveData` never crosses to the profile, so loading a save
  cannot trigger a save loop.
- **duel trigger**: already wired by A02 (`RecordDuelResult` →
  `RequestProgressionAutosave("duel_result")`).
- shop purchase + exam result triggers live in files I do not own → see
  *Integration hand-offs*.
- Cost note: the playthrough harness's natural 365-day loop and this fixture
  now produce ~400 autosave writes per run (small `.sav`, atomic verify each).
  Measured as acceptable for a headless harness; the game's autosave slot
  absorbs them.

### U3 — `story_events_cleared` was never incremented

`CompleteEvent` counts exactly one increment per **new** completion
(`!CompletedEvents.Contains(EventId)` guard, matching the set-add idempotency
the migration uses via `MoveCounter(...,"events"→"story_events_cleared")`).
The counter is title-system-ranked (`DATitleSystem.cpp:579`, Duel King 20 /
King of Games 33) and is NOT in the story `IsA02OwnedCounter` exclusion set, so
the profile counter API (`IncrementCounter`) receives it. Playthrough
regression: after all 35 events complete,
`GetCounter("story_events_cleared") == CompletedEvents.Num()` (35 canon + E01b).

### P4-05 — story ledgers silently reset on ill-typed arrays

- `ValidateSaveSection` now parses the `state` payload and rejects
  `applied_outcomes`, `completed`, `applied_rewards`, `unlocked_duels` when
  present but not an array (including null). The two-phase loader rejects such
  a save before any mutation and rolls back nothing (nothing happened).
- `LoadState` (direct path, e.g. restored snapshots) logs a `Warning` when a
  ledger field is present-but-not-an-array and was therefore reset — the
  read-time clearing can no longer pass silently.
- Regression: spoofed payloads with `applied_outcomes: null` / number,
  `completed: {}` are rejected with the new "not an array" error and the story
  ledger bytes stay identical after the failed loads.

### P4-06 — in-memory loads bypassed migration

`LoadPayloadJsonWithContext` now runs `MigrateJson(Payload, -1, OutError)`
before parsing/applying (same policy as `ReadPayloadFromSlotName`). A v0
payload with flat `name`/`dorm` no longer dies with "Save payload has no
profile object", and a payload claiming a newer-than-supported version is
rejected instead of silently loading un-migrated. Regression: the flat v0
probe (name LEGACY / Ra / 1234 DP / month 11 / day 5) loads, migrates, and the
identity/day assertions pass.

### P4-07 — EvaluateTrigger ignored the condition vocabulary

`EvaluateTrigger` kept a hand-rolled whitelist and answered
`"unsupported trigger type"` for `counter`, `card`, `date_at_least`,
`after_ending`, `random_chance`, composites (`all`/`any`), etc., making such
events permanently unreachable. Now: empty trigger (and `talk`/`always`
caller-driven kinds) pass as before; **everything else delegates to the shared
`new_game`-aware `EvaluateCondition`** (which covers `new_game`, `date`,
`date_at_least`, `flag`, `event`, `counter`, `card`, `dorm`, `title`,
`random_chance`, `after_ending`, `written_correct_percent`,
`wins_against_each`, `all`/`any` composites and pass-through kinds). Data
audit confirms the shipped events.json only uses `new_game/talk/event/date/
weekday/flag` — so no shipped-data semantics change; the fix unblocks
vocabulary-complete future data. Unknown trigger kinds now surface the
condition evaluator's "unknown condition type" warning-and-pass (logged),
instead of a silent, non-logged block.

### P4-09 — opponent cooldown wedged on backwards day jumps

- `CanRequestDuel` no longer errors forever on `ElapsedDays<0` (stale future
  entry): it logs (verbose) and evaluates as expired; `ConsumeDuelRequest`
  realigns on the next attempt.
- `ResetDailyRequests(DayIndex)` — on any request-day change, purges
  `LastRequestDay` entries **greater** than the new day (cooldown state from a
  later timeline can never become reachable again) and keeps per-day
  counter-reset behavior.
- `ValidateSaveSection` rejects a `request_day` that is not an integral
  int32-representable number, and rejects `last_request_day` entries later
  than the tracked `request_day` (only possible in tampered/corrupted saves;
  they would block every request forever).
- New automation test `FDAOpponentCooldownRealignTest`
  (`DuelAcademy.Opponents.CooldownRealign`): backwards jump does not block, the
  consume realigns/purges, forward cooldown still blocks mid-window and expires
  on schedule, inconsistent `last_request_day > request_day` is rejected,
  consistent bookkeeping validates.

### P4-15 — duplicate scene/line keys overwrite silently

`ParseScenes` and `ParseDialogue` now emit
`Story: duplicate scene id %s overwritten.` /
`Story: duplicate dialogue key %s overwritten.` (same channel/shape as
`MergeFromJson`'s duplicate-event-id warning) when a bundle overwrites a
previously loaded id. Overwrite behavior retained (opening→full_campaign
merge order stays the authority mechanism); only the silence is removed.

### V2 residual corner — starter flags before a successful import

- `ApplyDeckGrant` now returns `bool`: true only when the deck really landed
  (`UDADeckLogic::EnsureStarterDeck` succeeded, or an alternate
  `IDAProfileDeckInterface` provider activated it). `starter_deck_<deck>` and
  `starter_deck_chosen` are set **after** that success; `SelectedStarterDeck`
  still records the attempt.
- `ApplyRewardById` returns `bool` and, for `deck_grant` rewards, only adds
  `RewardId` to `AppliedRewardIds` after a successful grant — a failed import
  stays retryable instead of being swallowed as "already applied"
  (`opening_starter_deck_fire/water/wind` are the affected ids).
- `EnsureStarterDeck` now honestly returns the outcome of the reward/grant
  instead of a constant `true`. Call sites (`StartOpening` continuation path)
  ignore the bool as before; no behavioral dependency on the old constant.

### W9 — saved calendar hour write-only

`ReadSaveData` now reads `hour` (clamped 0..23 via the existing
`CalendarReadClampedInt`) **after** `ApplyDateInternal` so a save restores the
player's visual clock instead of resetting it to the period's start hour.
Absent/ill-typed `hour` falls back to the derived period hour (identical to the
old behavior, saving payloads that predate the field). Regression: both goldens
assert `GetHour()==8` after load.

### W13 — SkipToDate day-by-day broadcast storm

`SkipToDate` now: computes the target absolute day; applies the delta by
rolling month/year forward with the same rollover arithmetic as
`AdvanceDay` (including the `MaxSupportedYear` bound); moves `Period`/`Hour`
directly for a same-day jump; then fires **one** `BroadcastDateChanged`
(day changed = delta>0), i.e. one period broadcast, one `OnCalendarChanged`,
one `OnVisualHourChanged`, one exam broadcast, and one profile
`NotifyDayChanged` (+ the new day-change autosave). The 60-second
`DAProfileSelfTest` expectations (`SkipToDate(2,0,7)` → Year 2, Oct 7, abs 371,
Sunday weekday; past rejection) verified compatible by walk-through.

### P4-13 — GetNextExamDate boundary (deferred, conservative read)

All three callers were read: DAA02GateTests (expects month day-1 → this
month's exam), DAProfileSelfTest (Oct 7 → a Friday), and the playthrough
(max-year invariant). No non-test caller expresses "the exam *after* this
one"; changing the boundary on exam-day-itself would alter semantics for no
consumer, so the conservative read stands ("first exam day on or after the
current date", including today's exam regardless of period). The boundary is
now documented in the header comment and at the implementation. A future
caller that needs "next month's exam" should advance a day first (documented).

### DAIslandManager (in scope, unchanged, why)

`ADAIslandManager` only consumes the calendar's `OnVisualHourChanged` (and the
hour value) — W9/W13 make the hour honored and broadcasts coalesced on the
producer side; the manager needs no edit. No WS-02 finding targets it.

## Static verification (what was checked, without building)

- Data-side cross-checks (read-only): both goldens re-read end-to-end against
  the fixture assertions; `opening.json` / `events.json` trigger tables match
  the P4-07 whitelist before/after (all shipped kinds stay supported);
  `opening.json` starter-deck reward ids verified for the V2 ledger change.
- `Tools/audit_story_reachability.py` run (CHECK/no-write): output unchanged
  relative to its pre-existing data-level findings (talk-trigger events lack
  world callers — that is data/world-lane work, not C++); no new blocked ids.
- Caller-by-caller walkthroughs: every `GetNextExamDate`, `SkipToDate`,
  `OpenDuelDeckSelect`, `WasDeckSelectClosedWithoutResult`, `RequestAutosave`
  and counter call site inspected for expectation compatibility (see per-item
  notes).
- Harness structure: the new checks live inside the existing
  `RunStoryPlaythroughTest` persistence block; the summary line is computed
  dynamically (passed/failed counts), so no printed totals needed manual
  renumbering. `FDAOpponentCooldownRealignTest` is a new standalone test —
  the existing Roster test's counts are untouched.
- `git diff --check` clean for every touched file (only the repo-wide
  autocrlf line-ending normalization warnings, shared by all concurrently
  modified files in this pass).
- Compile correctness was pursued by static review only (no build allowed):
  duplicate declarations hunted and removed (e.g. the `ApplyRewardById`
  header declaration), enum/switch case match verified, lambda capture
  lifetimes (`StaleOpponents` declared before capture; fixture restores every
  lane it touched: profile/calendar/settings/story/opponents/decks/inventory),
  includes added (`DADuelUI.h`, `DAIslandSubsystem.h`, `DADeckLogic.h`,
  `Misc/Paths.h`, `Dom/JsonObject.h|JsonValue.h` in DAOpponentTests).

## Test gaps closed

- Null/ill-typed story ledger arrays are rejected before mutation (P4-05) —
  playthrough checks + ValidateSaveSection.
- Un-migrated v0 payload through `LoadPayloadJsonWithContext` migrates instead
  of failing with "no profile object" (P4-06) — playthrough probe.
- P4-02/P4-03 policy asserted in-harness (pure `DecidePendingDuelTick`
  table) — no HUD needed.
- Golden loads + runtime golden .sav round trip (P4-01) — playthrough fixtures.
- Opponent backwards-day realignment + request_day consistency (P4-09) —
  new automation test.
- `story_events_cleared` counted per completion (U3) — playthrough check.

## Deferred / refused

- **P4-08** (modal-blocked infinite wait) — deferred by the brief. Policy now:
  the deck-select retry (P4-03) and the reopen path keep asking every 0.5s
  while a story duel is pending; if `HUD::IsModalOpen()` blocks a *restored*
  duel the story stays pending indefinitely (deliberately not timed into a
  phantom loss — restated in `DecidePendingDuelTick`). A hard timeout for the
  "modal never closes" case needs product input (what should the player see?)
  and was not invented here.
- **P4-12** (choice ledger key scheme) — deferred by the brief; the existing
  `choice:<event>:<scene>:<index>:<line>:<id>` keys are untouched; P4-05's
  new validation deliberately accepts exactly the current scheme.
- **P4-13** — conservative read; see section above (documented boundary, no
  behavior change; header + cpp comments added).
- **P4-01 partial scope** — nothing distinguishes golden-new-game's
  `slot_name`-based `LoadNamedSlotWithContext` path from the payload path in a
  way that is harnessable without writing a `.sav` fixture file into the
  shipped integration directories; the payload path plus the runtime-golden
  `.sav` round-trip covers both the parse/apply path and the slot writer/reader.

## Remaining risks

1. **Autosave volume**: day-change autosave fires for every real day change;
   the playthrough harness accumulates a few hundred small `.sav` writes per
   run. If the parent cares about harness wall-time, a save-side rate
   limiter (out of my files) is the place; otherwise harmless.
2. **EvaluateTrigger delegation**: unknown trigger kinds now go through
   `EvaluateCondition`, whose unknown-type policy is warn-and-pass. A typo'd
   future trigger thus logs one warning instead of hard-blocking. If hard
   blocking is preferred, restore the explicit kind list in the trigger path
   only (the full-owned kinds are listed in the report above).
3. **P4-02 re-present loop**: a player who repeatedly Escapes the story deck
   select re-presents forever instead of ever recording a loss. That is the
   requested semantics ("stay pending / reopen"); a manual "skip duel" escape
   hatch would need new story data, which is out of scope.
4. **Harness deck/inventory restore**: the golden fixtures reset and restore
   decks via the provider section and inventory via `ImportStateJson`; if a
   future WS-03 change alters those APIs' semantics, the fixture restore line
   is the only coupling point.
5. **`story_events_cleared` equality check** assumes no legacy-completion replay
   inside one harness run (true today); a future repeatable event completing
   again in the same run would still hold because both sides measure the same
   `CompletedEvents` set.

## Integration hand-offs

1. **Shop purchase autosave trigger** (WS-03 owns `DAShopSubsystem.*`):
   in `DAShopSubsystem.cpp`, `UDAShopSubsystem::PurchasePack(...)` (the same
   place it calls `MarkPurchased(PackId)` after `SpendDP(...)` and the card
   grant succeed, around line ~986-1010), using the same reason style as the
   other progression autosaves:
   ```cpp
   // DASaveGame.h documents "purchases" as an autosave trigger.
   if (UDAProfileSubsystem* Profile /* via SpendDPHandler context or subsystem lookup */)
   {
       Profile->RequestProgressionAutosave(TEXT("shop_purchase"));
   }
   ```
   Only on success (blocked/refunded purchases must not autosave).
2. **Exam result autosave trigger** (no workstream owns `DAExamSubsystem.*`;
   the profile-side application lives in DATitleSystem/A10 terrain, WS-04 owns
   `DATitleSystem.*`): at the single place an accepted `FDAExamResult` is
   applied to the profile — `DATitleSystem::ApplyExamOutcome` (where
   `exam_passed`/`dropout_boy` flags and title changes land) or, if the parent
   prefers the A07 site, right after `UDAExamSubsystem::FinishExam` commits
   (`Phase = EDAExamPhase::Finished`) — call
   `Profile->RequestProgressionAutosave(TEXT("exam_result"))`; same
   success-only rule.
3. **P4-01 fixture data**: if WS-07 regenerates the goldens and adds more
   settings fields, `ReadSpeedField`'s 0..3 coercion bound should be revisited
   with the schema (currently matches `save.v1.schema.json:111/113`).

— end of WS-02 report.
