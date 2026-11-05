# Pass 4 — WS-03 Economy & Profile

Workstream report. Baseline `77cc9c7`, branch `refactor/code-review-pass`.

## Scope & constraints

- Owned files (all edits inside this set):
  `DAProfileSubsystem.h/.cpp`, `DAProfileSelfTest.cpp`,
  `DAInventorySubsystem.h/.cpp`, `DAShopSubsystem.h/.cpp`, `DADeckLogic.{h,cpp}`
  (header unchanged), `DAEconomyJson.h`, `DAEconomyTypes.h`, `DAEconomyTests.h`
  (unchanged) `/.cpp`, this report.
- No Unreal processes were run (no UBT/editor), no git commands run.
  Read-only reads of other lanes' files (`DASaveGame.cpp`, `DADuelUI.cpp`,
  `DAExamUI.cpp`, `DAStorySubsystem.cpp`, `DATitleSystem.cpp`,
  `DAA02GateTests.cpp`, `DAStoryPlaythroughTest.cpp`, `packs.json`) were used to
  re-verify findings and cross-lane contract behavior.

## Findings table

| ID | Sev | Location (finding) | Status | Note |
|----|-----|--------------------|--------|------|
| E1 | MED | `DAProfileSubsystem.cpp:427-459` | **fixed** | claim now in-memory; apply's single autosave persists token+effects atomically |
| E2 | MED | `DAInventorySubsystem.cpp:388-405` (:37) | **fixed** | no phantom zero entries; distinct count counts positives only |
| E4 | MED | `DAShopSubsystem.cpp:1298-1309`, `:1241-1256` | **fixed** | handlers present ⇒ external wallet regardless of saved flag |
| E3 | MED | `DADeckLogic.cpp:195-216` (activation side) | **fixed** | rules-gate refuses illegal switches, keeps previous deck; engine half = WS-01 |
| E5 | LOW | `DAInventorySubsystem.cpp:1139-1198` | **fixed** | ante duel ids fold (trim+lower) at stake/return/loss/load/struct-apply |
| E6 | LOW | `DAInventorySubsystem.cpp:1356-1368` vs `:1271-1289` | **fixed** | explicit-zero-is-absent rule applied to `ApplySaveData` |
| E7 | LOW | `DADeckLogic.cpp:339` vs `:452-461` | **fixed** | member is the source; `Rules.MaxPlayerDecks` re-synced at every raise |
| E8 | LOW | `DAShopSubsystem.cpp:409-422` | **fixed** | `MaxShopPackSize = 20` clamp at load; `ValidateCatalogue` reports clamped rows |
| E9 | INFO | validators (all three lanes) | **fixed** | shared `DAEconomyJson::RequireVersion(Object, Known)`; accept <= known, reject higher; writers stay at version 1 |
| E10 | INFO | `DAEconomyTypes.h:70` | **fixed** | `EDAEPurchaseBlock::DeckInvalid` removed; grep confirmed zero producers/consumers; it was the last value, nothing renumbers |
| E11 | INFO | `DAShopSubsystem.cpp:493-497` | **fixed** | pack ids folded everywhere (index, `FindPack`, purchase maps, load/write) |
| P4-11 | LOW(P4) | `DAProfileSubsystem.cpp:906-909`, `:735-748` | **fixed** | clamp at read (365 max), grace default (7 days) when count missing, explicit zero still expires |
| C3 | — | per-lane id mixtures | **fixed** | shared `DAEconomy::NormalizeIdKey` used for deck ids, ante duel ids, shop pack keys |
| T-gaps → tests | — | `DAEconomyTests.cpp` | **partially fixed** | 5 of 6 gaps closed in-harness; 1 recorded as not exercisable (see below) |

No finding was refused. Nothing from the deferred-by-design list was attempted.

## Changes & rationale

### E1 — result-token autosave order (`DAProfileSubsystem.h/.cpp`)

- New private `MarkResultTokenAppliedInternal(Token)`: validates emptiness/duplicate,
  appends, trims to the 256-token bound. No save.
- `TryMarkResultTokenApplied` (public, unchanged signature): claim + immediate
  `RequestAutosave("result_token")` — kept because the exam lane
  (`DAExamUI.cpp:572`, not mine) calls it standalone and the slot test
  (`DAProfileSelfTest.cpp:420`) relies on claim semantics; a standalone claim
  with no guaranteed follow-up apply must persist its guard.
- New public UFUNCTION `TryMarkResultTokenAppliedDeferred(const FString&)`:
  claim in memory only, no save. For claim+apply pairs.
- `RecordDuelResultOnce`: claims in memory, then `RecordDuelResult` applies
  counters/DP/title and its existing single autosave persists
  **token + effects atomically**. A crash before that save leaves no token
  behind, so the result re-applies on retry — the reward can no longer be
  stranded behind a token-only save. Order-independent exactly-once holds:
  *applied (memory) → saved (one write)*.
- Tutorial-mode tokenized results (which early-return in `RecordDuelResult`
  without its autosave) get one catch-up `RequestAutosave("result_token")` so
  the claim still persists exactly once. The mode check is a shared
  `ProfileIsTutorialMode` helper used by both sites, so it cannot drift.
- Net effect for the normal duel path: **one synchronous save per result
  instead of two**, removing the double-save ordering hazard the finding asked
  to fix by construction. No debounce system was added (per dispatch).

**API impact:** new `UFUNCTION(BlueprintCallable) bool TryMarkResultTokenAppliedDeferred(const FString&)`
on `UDAProfileSubsystem`. `TryMarkResultTokenApplied` behavior kept (still autosaves;
doc comment now warns claim+apply pairs to use the deferred form).
**Serialized format impact:** none (token array unchanged).

**WS-04 hand-off (DAExamUI.cpp:565-586):** the exam outcome block still uses the
standalone claim, so its own two-save crash window (claim→counters/DP/title)
remains until WS-04 migrates it — exact edit:
replace `Profile->TryMarkResultTokenApplied(OutcomeToken)` with
`Profile->TryMarkResultTokenAppliedDeferred(OutcomeToken)`, and after the
`if (Profile)` outcome block add a single
`GameInstance->GetSubsystem<UDASaveSubsystem>()->RequestAutosave(TEXT("exam_outcome"))`.
Afterwards the claim+outcome are one atomic save. Until migrated, exam
idempotency is unchanged (token persists with the claim's own save) but a crash
between the two saves can lose an exam reward — same class as pre-E1 duels.

### E2 — phantom zero counts (`DAInventorySubsystem.h/.cpp`)

- `AddCard` reads `GetCount(CardId)` and only inserts/overwrites
  (`Counts.Add`) when `Added > 0`; at-cap adds no longer create `id → 0`
  entries. A same-id legacy phantom is healed on the next successful add.
- `GetDistinctCardsOwned` (interface override in the header) now counts only
  positive values instead of `Counts.Num()`, so any other zero-entry source
  cannot inflate `DATitleSystem::MinCardsOwned` gates (verified consumers:
  `DATitleSystem.cpp:583`, `DAPDAUI.cpp:443`).

### E4 — wallet detach after Continue (`DAShopSubsystem.cpp`)

- In both `ImportStateJson` and `ApplySaveData` the saved
  `internal_wallet` flag is now advisory: with all three handlers present
  `bInternalWallet = false` (handlers kept); only with handlers genuinely
  absent does the cached fallback wallet stay authoritative
  (`bInternalWallet = !(GetDPHandler && SpendDPHandler && CreditDPHandler)`).
  A legacy `internal_wallet:true` row can no longer silently detach the shop
  from the profile wallet mid-session. `DAHUD.cpp:1080` (the only wiring site,
  WS-04's file) needed no change.
- Regression test added (handlers survive + absent-handlers fallback with the
  same payload).

### E3 — activation-side legality gate (`DADeckLogic.cpp`)

- `SetActiveDeckId` (the `IDAProfileDeckInterface` hook used by story grants
  and the playthrough test): existing decks are validated with
  `ValidateDeckWithoutOwnership` (rules only — shape/copy/banlist; deliberately
  no ownership check, so story-granted starter decks remain legal by
  construction and usable before their card grant). An illegal switch is
  refused with a clear warning log and the previous activation is kept;
  no broadcast on refusal (no state change).
- Degenerate-case guard: if the card database is absent so rules cannot be
  evaluated (only error = `database_unavailable`), the pre-gate behavior is
  kept instead of refusing — the engine's own Start validation (WS-01's half)
  still refuses illegal decks once rules load.
- The "unknown id falls back to PlayerDecks[0]" path (story recipe ids) is
  unchanged; call sites verified fire-and-forget (`DAStorySubsystem.cpp:2754/:2764`,
  `DAStoryPlaythroughTest.cpp:422`).
- Blueprint `SetActiveDeck(DeckId, OutError)` (full ownership check) unchanged.

### E5 — ante id normalization (`DAInventorySubsystem.cpp`)

- `RemoveCardForAnte` folds the duel id (`DAEconomy::NormalizeIdKey`) before
  the one-stake guard and stores the folded id; `ReturnAnteCard` /
  `CommitAnteLoss` fold lookups the same way. Comparisons stay
  `Equals(IgnoreCase)` so legacy saved rows (previously written raw) still
  match. `ImportStateJson` and `ApplySaveData` also fold ids on load, and the
  shared validator rejects whitespace-only duel ids (it and the importer now
  agree: normalized-empty ⇒ "no duel id" error).

### E6 — zero-count struct contract (`DAInventorySubsystem.cpp`)

- `ApplySaveData` now mirrors the JSON importer: zero counts are dropped as
  "not owned"; the "no valid card counts" rejection that fired only on the
  struct path is gone. An all-zero payload refreshes the trunk to empty.

### E7 — single-source `MaxPlayerDecks` (`DADeckLogic.cpp`)

- `MaxPlayerDecks` (loose member) remains the writable authority;
  `Rules.MaxPlayerDecks` is re-synced at every raise site (`LoadRules`,
  `LoadPlayerDeckFile`'s data-driven raise and the defaults-exceed-limit
  raise) so `GetRules()` stays truthful. No external reader changed.

### E8 — pack_size clamp (`DAShopSubsystem.cpp`, `DAEconomyTypes.h`)

- `LoadPacks` clamps `PackSize` to `MaxShopPackSize` (20; shipped canon is
  3-7) **before** slot regeneration, so the regeneration loop is bounded; the
  new runtime-only `FDAEPackDef::bPackSizeClamped` flag records the row, and
  `ValidateCatalogue` reports `pack_size exceeded the load-time maximum and
  was clamped`.
- **Format impact:** `FDAEPackDef` gained one non-serialized diagnostic bool
  (the struct ships in save payloads only via card/count lists — no changed
  bytes on disk).

### E9 — version gate (`DAEconomyJson.h` and all three validators)

- New `DAEconomyJson::RequireVersion(Object, KnownVersion, OutError)`:
  sections with no `version` field or a version ≤ known load; higher
  (newer-build) sections, non-integer versions and negative versions are
  rejected. Wired first in each validator:
  `ValidateInventorySectionObject`, `ValidateShopSectionObject`,
  `UDADeckLogic::ValidateSaveSection`; writers now emit the matching
  file-local constants (`InventorySaveSectionVersion`, `ShopSaveSectionVersion`,
  `DeckSaveSectionVersion`) so writer and gate cannot drift.
- **Behavior impact:** a future unknown-higher section is now rejected loudly
  instead of silently imported. Existing payloads (version 1 / legacy
  no-version) are unaffected.

### E10 — dead enum value (`DAEconomyTypes.h`)

- `EDAEPurchaseBlock::DeckInvalid` removed. Repo-wide grep showed no
  producer/consumer; it was the final enumerator so no value shifted, and
  `Block` fields are runtime-only (never serialized).

### E11/C3 — one shared id normalizer

- `DAEconomy::NormalizeIdKey(FString)` (trim + lowercase) added to
  `DAEconomyTypes.h`, matching the deck lane's existing fold. Used now for:
  deck ids (`ValidateSaveSection`, `LoadPlayerDeckFile`, `ApplySaveData`,
  `ImportStateJson`), ante duel ids (E5), and shop pack keys (`LoadPacks`
  index/dedup, `FindPack` lookups, `MarkPurchased`, `GetLastPurchaseDay`,
  `GetPurchaseCount`, load-side key folding in `ReadSaveIntMap` +
  `ApplySaveData`, first-wins on case collisions for determinism).
  Remaining per-lane `ToLower` uses are enum-text parsers
  (`ParseUnlockType`/`ParseSlotType`), not id lookups.
- **Shop save-format note:** `last_purchase_day`/`purchase_counts` keys are
  now written normalized (they were already written canonical in practice;
  a mixed-case hand-edited save folds on load instead of dead-keying).

### P4-11 — temporary titles (`DAProfileSubsystem.cpp`)

- Read path: `temporary_title_days` present ⇒ clamped to
  `MaxTemporaryTitleDays = 365` (a full school year; `DAA02GateTests`
  generates 1..365, so legitimate values round-trip untouched — verified).
  Absent count with a saved title ⇒ `DefaultTemporaryTitleGraceDays = 7`
  instead of silently dropping the title. An explicit zero still expires the
  title (kept from the original code's contract).
- `NotifyDayChanged` decrement now operates on a bounded value; no change to
  the expiry logic. `SetTemporaryTitle` was deliberately not clamped to keep
  the WS-04 test fixture space semantically bytes-identical.
- Regression checks added to `TestSave` in `DAProfileSelfTest.cpp`
  (uncapped count clamps to 365; missing count keeps the title on a grace;
  explicit zero still expires). The self-test prints live totals, so the
  added checks need no separate count bookkeeping.

## Tests (`DAEconomyTests.cpp`, in-memory harness only)

Extensions (all existing assertions kept, none weakened):

1. **AddCard at-cap map hygiene / GetDistinctCardsOwned exact** — at-cap add
   reports exactly one distinct card and leaves no non-positive entry in
   `GetCollection()`; emptied trunk reports zero distinct; cap-refill keeps
   exactly one distinct (`TestInventory`).
2. **All-zero struct payload refresh** — `ApplySaveData{Counts:{1:0,2:0}}`
   returns true and empties the trunk / distinct = 0
   (`TestInventoryTransactionality`).
3. **`SetActiveDeckId` legality refusal** — a fresh empty deck (illegal by
   shape) is refused, previous activation kept; a rules-legal deck (any
   shipped deck validated without ownership) still activates; the gate deck is
   erased after (`TestDeckState`).
4. **RequireVersion** — future inventory/shop/deck sections
   (`"version":2`, int32-max, non-integer and negative cases for inventory)
   are rejected by validator and importer with live state preserved; known
   (1) and older (0) plus no-version payloads import
   (new `TestSaveVersionGates`, registered in `Run`).
5. **pack_size clamp** — canon invariant: no shipped pack carries
   `bPackSizeClamped` and `ValidateCatalogue` stays clean (`TestCatalogue`).
   See residual note below for the oversized-row fixture.
6. **E4 wallet retention** — handlers survive an `internal_wallet:true`
   payload with DP still coming from the handler; absent handlers fall back
   and the cached DP is then visible (`TestShop`).
7. **Pack-rollback-after-grant-failure** — found not exercisable end-to-end:
   the failure branch (`ConsumePendingPackGrant` returning false after cards
   are added) requires `Story->GetPendingPackGrants().Contains(id)` true while
   the story consume fails, but the story loader drops counts < 1
   (`DAStorySubsystem.cpp:3558`) and a single-threaded caller cannot win the
   race the branch guards. The replaced checks assert the observable contract
   (a zero-count row is not queued; the consume reports `no_pending_grant`
   and adds nothing) — `TestPendingPackGrants`. The
   mid-open pool-failure rollback path (same-file `OpenPackDefinition`
   rollback) was already covered (`:1277-1296`) and remains.

Self-test totals are printed from live counters (`RunProfileSelfTest`,
`DAEconomyTests::Run`), so the added checks need no hardcoded total updates.

## Verification (static)

- No compile possible (no Unreal processes permitted); verification was:
  full re-read of every edited file region after each edit; grep sweeps for
  stale symbols (`OldOwned`, removed enum, leftover `ToLower` id sites,
  removed `TryMark...` save call, orphaned handler-reset logic),
  consumer checks for every changed API (`GetDistinctCardsOwned`,
  ante/pack/purchase lookups, `SetActiveDeckId` call sites,
  `SetTemporaryTitle` day values, wallet-handler wiring order, story
  `pending_packs` loader semantics); whitespace cleanliness checked on all
  touched files (`[ \t]+$` clean — satisfies `git diff --check` without
  running git).
- Python suites are irrelevant to WS-03 files; not run.
- Two compile-risk candidates to watch at integration: the new
  `FName == FName` comparison in the E3 gate (standard UE) and inline
  `GetDistinctCardsOwned` in `DAInventorySubsystem.h` (plain member loop).

## Remaining risks

- **Exam lane** (WS-04): until the deferred-claim migration above, the exam
  outcome keeps the two-save window. It cannot be fixed from WS-03's files.
- **`SetActiveDeckId` no longer broadcasts on refusal** — correct (no state
  change), but any future UI code assuming "broadcast always follows a call"
  would need to poll `GetActiveDeckId()` instead.
- **Whitespace-only ante duel ids** now fail save validation (previously
  half-imported and then rejected by the importer); consistency was chosen
  over tolerance — a full save with such junk is rejected rather than
  silently dropping the record.
- **E8 clamp value**: raising `MaxShopPackSize` requires content review
  (it is the memory/allocation bound per pack row).
- **`Rules.MaxPlayerDecks`**: sync is manual at the three known raise points;
  a future raise site must re-sync (commented at all current sites).

## Integration hand-offs

1. **WS-04 — `DAExamUI.cpp` (outcome block, ~:561-586):** swap
   `Profile->TryMarkResultTokenApplied(OutcomeToken)` →
   `Profile->TryMarkResultTokenAppliedDeferred(OutcomeToken)`; after the
   outcome block add
   `GameInstance->GetSubsystem<UDASaveSubsystem>()->RequestAutosave(TEXT("exam_outcome"))`.
   (The public deferred API already exists from WS-03; this is the only edit
   needed to make the exam outcome a single atomic save.)
2. **WS-01 — engine Start validation** (their list item "engine Start
   validate"): unchanged ordering now that `SetActiveDeckId` refuses illegal
   activations pre-Start; no WS-03-side change required.
3. **WS-02 — informational:** `RequestAutosave("duel_result")` now writes
   one save per duel result (the token-only pre-save is gone); no change
   needed in `DASaveGame.cpp`. `Validation` of `pending_packs` counts < 1
   being dropped (`DASaveGameConsumer` note) is why WS-03's grant-failure
   rollback branch remains race-only and untestable in-harness.
4. **Parent — brief row "profile debounce / shop autosave trigger":** not
   implemented, per the dispatch's explicit "no debounce system" instruction;
   E1's fix already removes the duel-result double save. If a debounce is
   still wanted after integration, the insertion point is
   `UDAProfileSubsystem::RequestProgressionAutosave` (private,
   `DAProfileSubsystem.cpp`).
