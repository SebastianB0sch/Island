# 05 — Economy, inventory and decks (pass 3)

Branch: `refactor/code-review-pass`

Scope: `DAInventorySubsystem.*`, `DAShopSubsystem.*`, `DADeckLogic.*`,
`DACardRecords.*`, `DACardArtSubsystem.*`, `DACharacterPortraitSubsystem.*`,
`DAEconomyTypes.h`, `DAEconomyJson.h`, `DAEconomyTests.*`, and this report.
Pass-2 work in these files is retained. No UI, story, save-subsystem, data,
manifest, pack/card JSON or generated asset files were changed. No Unreal
process was run by this workstream.

## 1. Summary

Pass 2 made the save path transactional, but the economy providers still
accepted or silently repaired malformed save sections, and several arithmetic
and lifecycle edges remained. This pass closes those within the owned files:

- inventory save sections are validated strictly and imported transactionally;
  malformed count keys such as `"1x"` can no longer become card 1, and malformed
  ante/count entries no longer silently disappear;
- shop save sections gained a real `ValidateSaveSection`, struct saves filter
  negative restock/stock counters, and day/count arithmetic saturates instead of
  wrapping;
- deck loading now uses the same case-insensitive id rules as runtime and save
  import, save validation checks field shapes before apply, non-positive card
  ids are dropped from struct payloads, and active deck ids are canonicalised;
- `AnyCount` fusion recipes (F.G.D. = five Dragon monsters) now appear in the
  deck-editor recipe list using the same material rule as the duel engine;
- card-record scalar readers reject booleans/fractional/out-of-range numbers,
  and opponent deck registration rejects non-positive card ids;
- `-DAEconomySelfTest` now exits non-zero when a check fails.

The `purchase_limit` question is resolved for shipped data: all 48 packs use
`purchase_limit: 1` and a positive restock window, and the existing restock gate
already limits a pack to one purchase per window. `stock` is a separate lifetime
cap, not replenished by restocks. A future `purchase_limit > 1` would need
per-window counters; the limitation is documented on `FDAEPackDef`.

Two high-impact defects are outside this workstream and are specified in
section 6: `DAHUD` feeds a year-relative day into the shop restock clock, and
the story starter-deck grant never imports the chosen starter deck or grants
its cards.

## 2. Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| E1 | High | `DAInventorySubsystem.cpp` `ImportStateJson` / `ValidateSaveSection` | Counts keys were parsed with `Atoi64` prefix semantics, so `"1x"` loaded as card 1. Invalid counts/ante/max entries were silently skipped; provider validation only checked that a `counts` object existed, so a malformed save could silently empty or alter the trunk. | Fixed: strict canonical key parsing, strict positive integral counts, max/ante validation shared by `ValidateSaveSection` and `ImportStateJson`; no state is touched until validation succeeds. |
| E2 | Medium | `DAInventorySubsystem.cpp` `ApplySaveData` | `MaxOwnedCopies == 0` (unlimited mode) was not restored, and ante records with invalid ids/empty duel ids were installed. | Fixed: 0 round-trips; invalid ante records are filtered. |
| E3 | Medium | `DAInventorySubsystem.cpp` `GetCollectionSize` / `GetCollectionStats` | Totals and per-rarity/type counters accumulated in `int32`; save-loaded counts near `INT_MAX` could wrap negative. `CompletionPercent` also counted ids that no longer exist in `cards.json`, so a legacy save could exceed 100% and bypass collection unlocks. | Fixed with 64-bit saturating aggregation, known-id-only clamped completion, and a regression test. |
| E4 | Medium | `DAInventorySubsystem.cpp` `OpenPackDefinition` | A failure after earlier slots added cards rolled the trunk back but returned partial reveals and duplicate DP that was never credited. Duplicate-DP accumulation could overflow. | Fixed: failure clears `Cards`/`DPFromDuplicates`; DP accumulates with saturation. |
| E4b | Medium | `DAInventorySubsystem.cpp` `OpenPackDefinition` | An `AnyCard` slot in a non-all-cards pack had an empty candidate list even though `validate_packs.py` permits the shape (any-card slot sourced from materialised pools), so such a pack could never open. | Fixed: candidate ids are the union of the pack's rarity pools when `bAllCards` is false. |
| E5 | Low | `DAInventorySubsystem.cpp` `ResolveSeed` | A generated seed could be 0, which the public API uses to mean "pick a seed". | Fixed: generated 0 maps to 1. |
| E5b | Low | `DAInventorySubsystem.cpp` `RemoveCardForAnte` | Repeated ante calls for the same duel removed a second copy, while `ReturnAnteCard` returns only one, leaving a stranded stake or losing a card on commit. | Fixed: one ante stake per duel; regression test. |
| E6 | Medium | `DAShopSubsystem.cpp` | No `ValidateSaveSection`; `ImportStateJson` skipped malformed/negative map entries and accepted an empty `{}` section, and `ApplySaveData` accepted negative counters/days. Negative counters had previously been able to bypass stock/restock gates. | Fixed: strict provider validator, strict import, and filtered struct apply. |
| E7 | Medium | `DAShopSubsystem.cpp` `GetNextAvailableDay` / `MakeView` / `CheckPurchase` / `MarkPurchased` | Day and purchase-count arithmetic could overflow with `INT_MAX` values accepted from saves; `PurchaseCounts++` could overflow. A backwards clock (new game, legacy relative day) could also soft-lock a pack for the whole difference. | Fixed with 64-bit clamped arithmetic, a backwards-clock "treat as restocked" guard, and regression tests. |
| E8 | Low | `DAShopSubsystem.cpp` `LoadPacks` | Explicit negative `stock`/`purchase_limit` values were clamped to valid values, hiding bad data from `ValidateCatalogue`. | Fixed: raw values are retained so validation reports them. |
| E9 | Info | `Content/Data/Shop/packs.json`, `CheckPurchase` | Pass-2 F22: `purchase_limit` is per-restock. All 48 shipped rows use 1 with a positive restock window, so the restock gate enforces the limit. `stock` is lifetime (30/25/20 rows stay finite). A future value >1 is not separately counted. | Verified, documented on `FDAEPackDef`, and asserted in the self-test. No behaviour change for shipped data. |
| E10 | Medium | `DADeckLogic.cpp` `LoadPlayerDeckFile` | Duplicate player deck ids were compared case-sensitively while `FindPlayerDeck` and save import are case-insensitive. `Player_1` and `player_1` could both load, and the resulting save would be rejected by the provider validator. | Fixed: ids are trimmed and deduplicated case-insensitively; the deck limit is kept consistent with the loaded count. |
| E11 | Medium | `DADeckLogic.cpp` `ValidateSaveSection` / `ImportStateJson` | Save validation only checked deck count and duplicate ids. Non-numeric card arrays, non-string `active_deck_id` and wrong boolean types were silently coerced or dropped. | Fixed: field-shape validation before apply, including `main`/`extra` positive integer arrays. |
| E12 | Low | `DADeckLogic.cpp` `ApplySaveData` / `ImportStateJson` / `SetActiveDeckId` | Active ids retained caller casing/whitespace; non-positive card ids could be persisted through the struct API; an unknown id silently activated an unrelated deck. | Fixed: active ids are trimmed/canonicalised, non-positive ids are dropped from struct payloads, and the fallback logs a warning. |
| E13 | Low | `DADeckLogic.cpp` `CanUseCard` | A limited-list entry with limit 0 produced "limited to 0 copies" while validation treats it as forbidden. | Fixed: edit path now reports the forbidden-card message. |
| E14 | Medium | `DADeckLogic.cpp` `GetAvailableFusionRecipes` | Recipes with `AnyCount > 0` were always hidden because the loop required a non-empty `Materials` array. The shipped F.G.D. recipe ("5 Dragon monsters") could therefore never be shown, even with five Dragons owned. | Fixed: `AnyCount` recipes count owned monsters of `MaterialsType`, mirroring `FDuelEngine::FindFusionOption`; regression test covers both sides of the threshold. |
| E15 | Medium | `DACardRecords.cpp` `CardReadInt` / `CardReadString` / `CardReadStringArray` | Scalar ints accepted booleans (`true` → 1) and rounded fractional values; numeric values could be coerced into strings. | Fixed: real JSON numbers with integral int32 values and real JSON strings only. |
| E16 | Low | `DACardRecords.cpp` `RegisterDeck` | Registered opponent/starter decks could contain non-positive card ids, producing an unusable `FindDeck` result. | Fixed: `RegisterDeck` rejects invalid ids with a warning and leaves the existing registry untouched. |
| E17 | Medium | `DAInventorySubsystem.cpp` `TickSelfTest` / `DAEconomyTests` | `-DAEconomySelfTest` always requested exit code 0, even when checks failed; the integration harness treats the process return code as authoritative. | Fixed: `Run` reports the failure count and `TickSelfTest` exits 1 on failures/timeouts. |
| E18 | Info | `DAEconomyJson.h` | `ReadIntArray` used `AsNumber()` on every JSON type, so booleans/strings became bogus card ids; `ReadBool` accepted numbers. | Fixed: typed, range/integrality-checked readers used by shop, deck and inventory loaders. |
| E19 | — | `DACardArtSubsystem.*`, `DACharacterPortraitSubsystem.*` | Re-reviewed integer/path/cache/null handling. No new concrete defect found; pass-2 path traversal rejection, lowercase cache keys and null caching hold. | No change. Documented cache limitation remains (see risks). |
| E20 | High (out of scope) | `DAHUD.cpp` `WireEconomySystems` | `FDAEUnlockContext.DayNumber` is built as day-of-month plus elapsed months in the current year, not an absolute day. It resets at the school-year boundary, so restock windows follow a non-absolute clock (and previously soft-locked packs until the new guard). This contradicts the documented "absolute in-game day" contract. | Reported; exact fix in section 6. |
| E21 | High (out of scope) | `DAStorySubsystem.cpp` `ApplyDeckGrant` / `EnsureStarterDeck` | Story passes starter recipe ids (`fire`, `water`, `wind`) to `SetActiveDeckId`, which only knows player deck ids. No starter deck is imported and no starter cards are granted on a real new game; water/wind selection falls back to `player_1` (fire), and the inventory can remain empty. | Reported; exact fix in section 6. |
| E22 | Medium (out of scope) | `DASaveGame.cpp` provider apply | Only present provider sections are applied. Loading a legacy payload without `shop`/`inventory`/`decks` leaves the previous in-memory state in place instead of resetting it. | Reported as a save-subsystem follow-up. |
| E23 | Medium (out of scope) | `golden_new_game.json`, `DASaveGame::MigrateLegacyPayloadToV1` | The tracked golden save uses the schema's legacy flat `inventory` map and a root `decks` list. The providers now (and already in pass 2) expect `inventory.counts` and a `{version,decks}` deck section, so the golden fixture cannot load as a v1 payload without migration. | Reported; migration required in the save subsystem, not in the provider contract. |

## 3. Changes made

### Shared economy JSON helpers (`DAEconomyJson.h`)

- Added `TryReadInt` / `TryReadCardId`: only a real JSON number (`EJson::Number`,
  not booleans) with a finite, integral value in int32 range is accepted.
- `ReadInt` and `ReadBool` are now type-strict; `ReadIntArray` returns only
  positive integral card ids; `ReadStringArray` accepts strings only.
- All economy loaders benefit: malformed booleans/fractions/strings no longer
  become card ids, weights, limits or flags.

### Inventory (`DAInventorySubsystem.*`)

- Added shared `ValidateInventorySectionObject`, used by both
  `ValidateSaveSection` and `ImportStateJson`:
  - `counts` is required and must be an object;
  - keys must be canonical positive decimal card ids (no `+`, spaces,
    fractions, leading zeroes or `1x`);
  - values must be non-negative integral ints; an explicit zero is accepted as
    "not owned" (the schema allows it) and the writer omits it;
  - optional `max_owned_copies` must be a non-negative integral int;
  - optional `pending_ante` must be an array of objects with a positive
    `card_id`, a non-empty string `duel_id`, and a string `source` when present.
- `ImportStateJson` validates before building locals and commits only at the
  end, so a failed import cannot partially replace counts or ante.
- `ApplySaveData` now round-trips `MaxOwnedCopies == 0` (unlimited), filters
  invalid ante records, and keeps the existing all-invalid-count rejection.
- `GetCollectionSize` and `GetCollectionStats` use saturating 64-bit
  accumulation for totals and per-rarity/type/attribute counters.
  `CompletionPercent` counts only ids present in the current card database and
  is clamped to 0–100, so removed-card ids in a legacy save cannot inflate
  catalogue completion or unlock collection-gated packs.
- `OpenPackDefinition`:
  - duplicate-DP addition saturates;
  - a failed open clears partial `Cards` and `DPFromDuplicates`;
  - `ConsumePendingPackGrant` similarly returns a clean failure after rollback;
  - preview skips the full trunk copy when applying a real open;
  - `AnyCard` slots in a non-all-cards pack draw from the union of the
    materialised rarity pools (the shape the data validator allows).
- `ResolveSeed` never returns 0 for a generated seed.
- `RemoveCardForAnte` rejects a second stake for a duel that already has one,
  matching `ReturnAnteCard`'s one-card-per-duel contract.
- `TickSelfTest` uses `RequestExitWithStatus` and reports failure code 1 when
  `DAEconomyTests::Run` reports failed checks or subsystem startup times out.
- `LoadOwnershipLimit` and rarity loading use the strict int reader.

### Shop (`DAShopSubsystem.*`)

- Added `UDAShopSubsystem::ValidateSaveSection` (the interface already existed)
  and a shared `ValidateShopSectionObject`:
  - optional `cached_dp` must be a non-negative integral int;
  - optional `internal_wallet` must be a bool;
  - `last_purchase_day` / `purchase_counts` must be objects with non-empty
    keys and non-negative integral values.
- `ReadSaveSection` and `ImportStateJson` validate before applying; import
  rejects rather than silently skipping malformed entries.
- `ApplySaveData` filters empty keys, negative days and negative counts, and
  clamps `CachedDP`.
- `GetNextAvailableDay`, `MakeView`, the restock message and `MarkPurchased`
  use 64-bit clamped arithmetic. `GetRemainingStock` uses a 64-bit difference.
  A `LastPurchaseDay` greater than the current day is treated as a completed
  restock (new game or legacy relative clock) instead of soft-locking the pack.
- `LoadPacks` keeps raw negative `stock`/`purchase_limit` values so
  `ValidateCatalogue` can report them instead of silently normalising them.
- `DAEconomyTypes.h` documents the shipped `purchase_limit` per-restock
  interpretation and that `stock` is a lifetime cap.

### Decks (`DADeckLogic.*`)

- `ParseDeckObject` trims ids; player-deck loading deduplicates case-insensitively
  and raises the slot limit (with a warning) if the shipped deck file contains
  more decks than `max_player_decks`, instead of creating an unsaveable state.
- `LoadRules` uses the strict card-id readers for banned/limited arrays and
  objects.
- `ValidateSaveSection` now checks:
  - non-empty deck array within `MaxPlayerDecks`;
  - string `active_deck_id` when present;
  - `main`/`extra` arrays containing only positive integral card ids;
  - boolean types for `bStarter`, `is_starter` and `bPlayerDeck` when present.
- `ImportStateJson` runs that validation before parsing and canonicalises the
  active id; `ApplySaveData` trims ids, drops non-positive card ids, canonicalises
  the active id and keeps the duplicate/count checks.
- `SetActiveDeckId` trims input, stores the canonical deck id, and logs a warning
  when a starter recipe id cannot be resolved (this is the story hand-off issue
  in E21).
- `CanUseCard` treats limit 0 as forbidden, consistent with validation.
- `GetAvailableFusionRecipes` handles `AnyCount` recipes using
  `MaterialsType`/monster ownership, matching the duel engine's generic-material
  rule.
- Header comments corrected from 20 to 15 Extra Deck slots.

### Card records (`DACardRecords.cpp`)

- Scalar card/recipe integers require real JSON numbers with integral int32
  values; booleans and fractions are rejected.
- Card strings and fusion-type arrays require real JSON strings.
- `RegisterDeck` rejects non-positive `Cards`/`Extra` ids and keeps the previous
  registration on failure; starter-id collisions still return false.

### Self-test harness (`DAEconomyTests.*`)

- `Run` gained an optional `int32* OutFailures` (default null) so the headless
  launcher can set a non-zero exit code without changing the in-process API.
- New regression coverage:
  - inventory section write/validate/read, malformed count keys/values,
    explicit zero counts, malformed ante, duplicate ante, empty inventory,
    unlimited-cap round-trip, saturating aggregation, unknown-id completion,
    late-slot pack rollback, AnyCard pool opening, unknown pool card, unknown
    pack ids, and preview immutability;
  - shop unknown pack, sold-out stock, negative struct counters, `INT_MAX`
    next-day saturation, rewound-clock restock, malformed provider sections,
    duplicate-DP saturation, and the shipped `purchase_limit == 1` /
    positive-restock data assumption;
  - deck save round-trip, case-insensitive duplicate rejection, malformed card
    arrays/field types, unknown cards, main/extra separation, copy and limited
    edit limits, underfilled-deck activation rejection, starter import/copy
    flags, active-deck erase fallback, struct filtering of non-positive ids,
    and the `AnyCount` fusion recipe threshold.

### Art and portraits

No code change. The pass-2 hardening (id validation, lowercase cache keys,
path-traversal rejection, cache reset on initialize, null-tolerant lookups)
was re-read against the current callers and found sound. The only remaining
limitation is the intentional missing-art/null-cache policy (section 5).

## 4. Verification

| Check | Result |
|---|---|
| `git diff --check -- <all owned source files>` | **PASS** (exit 0). Only Git's LF→CRLF notices; no whitespace errors. |
| `python Tools/economy/validate_decks.py` | **PASS** — 81 checks, 0 failures, exit 0. |
| `python Tools/economy/validate_packs.py` | **PASS** — 1,342 checks, 0 failures, exit 0. |
| `python -m unittest Tools.tests.test_run_smoke -v` | **PASS** — 56 harness tests, 0 failures, exit 0 (covers the summary/exit-code handling used by the changed self-test launcher). |
| `python Tools/validate/validate_all.py` | **FAIL** (exit 1) on 4 tree-local canon-manifest errors (`canon_manifest_hash` / `canon_manifest_size` for `cards_manifest.json` and `exams.json`), with the baseline 15 warnings and 6 gaps. No data or manifest file was edited by this workstream; the failure is unrelated to these C++ changes. |
| Python audit of shipped economy data | **PASS** — 48 packs / 1,200 cards; all pack metadata integral; every row has `purchase_limit: 1`; all deck/banned card arrays are positive ints; the runtime golden inventory counts are canonical. |
| Lightweight brace/paren check of changed C++ files | **PASS** — balanced for all changed files (syntax sanity only, not a compiler). |
| Unreal build / `-DAEconomySelfTest` / automation tests | **Not run** — forbidden in this workstream. The parent owns the combined build and headless runs. |

No generated data, manifest, report, committed asset or golden save was
modified. No commit or staging action was performed.

## 5. API and serialization impact

- Serialized formats are unchanged. All additions are validation and
  arithmetic hardening.
- **Additive API:** `UDAShopSubsystem::ValidateSaveSection` overrides the
  existing `IDASavePayloadProvider` hook. `DAEconomyTests::Run` gains an
  optional trailing `int32*` parameter; existing calls remain valid.
- **Stricter input contract:** a present save section must use the canonical
  shapes written by the shipped code:
  - inventory `counts` keys are canonical positive decimal ids and values are
    non-negative integers (zero means absent); `pending_ante` entries require a
    positive card id and a non-empty duel id;
  - shop maps have non-empty keys and non-negative integer values;
  - deck `main`/`extra` arrays contain only positive integer card ids and
    boolean flags keep boolean types.
  Saves produced by this build and by the shipped pass-1/pass-2 code satisfy
  these contracts. Hand-edited or malformed legacy payloads are now rejected
  instead of silently repaired.
- `FDAEInventorySaveData::MaxOwnedCopies == 0` now round-trips through
  `ApplySaveData` (previously only the JSON path preserved it).
- `UDADeckLogic::SetActiveDeckId` stores the canonical deck id; a save may see
  its casing normalised to the deck's stored id. Deck ids are trimmed when
  loaded/imported.
- `FDAEPackDef::PurchaseLimit` and `Stock` documentation now states the
  per-restock versus lifetime semantics.

## 6. Remaining risks and cross-workstream follow-ups

1. **High — shop restock clock uses a year-relative day.**
   `DAHUD::WireEconomySystems` (`DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAHUD.cpp`,
   around lines 1020–1028) builds
   `Context.DayNumber` as `Calendar->GetDay()` plus the days in preceding months
   of the current year. It resets at the school-year boundary, so restock
   windows are evaluated against a non-absolute clock. The shop's new
   backward-clock guard prevents the worst soft-lock, but the cadence still
   resets and the `FDAEUnlockContext` contract is violated. Required change:
   ```cpp
   Context.MonthIndex = Calendar->GetMonthIndex() + 1;
   Context.DayNumber = Calendar->GetAbsoluteDay();
   ```
   `GetAbsoluteDay()` already exists and is the documented contract for
   `FDAEUnlockContext::DayNumber`. Add a regression assertion in the HUD/story
   self-test if one can observe the unlock context across a year boundary.
2. **High — starter deck selection is not imported or granted.**
   `UDAStorySubsystem::ApplyDeckGrant` (`DAStorySubsystem.cpp`, around line 2694)
   calls `SetActiveDeckId(DeckId)` with `fire`/`water`/`wind`, but
   `UDADeckLogic` only stores player deck ids. `SetActiveDeckId` therefore falls
   back to `player_1`; no starter cards are added to the inventory on a real new
   game (only `ADAHUD::PrepareGameplayUITestState` grants
   `GetDefaultStarterCards()`). Required story-side change:
   - if `Decks->FindPlayerDeck(DeckId)` is null, call
     `Decks->ImportStarterDeck(DeckId, DisplayName, OutId, Error)`;
   - grant `Decks->GetStarterDeckCards(DeckId)` through
     `UDAInventorySubsystem::GrantStarterCollection`;
   - activate `OutId` (not the starter recipe id);
   - on `StartOpeningFresh`/a real new game, also call
     `Shop->ResetPurchaseState()`, `Inventory->ResetCollection()` and
     `Decks->ResetToDefaults()` before granting the starter deck so a second
     new game in the same GameInstance does not inherit the previous economy.
3. **Medium — absent provider sections preserve stale state.**
   `UDASaveSubsystem::ApplyPayload` only applies sections that are present. A
   legacy payload without `shop`/`inventory`/`decks` therefore leaves the
   previous in-memory state intact. The save workstream should either require
   registered provider sections for new-version saves or add an
   "apply defaults for absent section" hook. The new provider validators make
   present malformed sections fail transactionally, but cannot fix absence.
   The tracked `golden_new_game.json` uses the schema's legacy flat inventory
   and a root `decks` list; `MigrateLegacyPayloadToV1` should wrap those into
   `inventory: {counts: {...}}` and
   `decks: {version: 1, active_deck_id: <default>, decks: [...]}` before
   provider validation. Otherwise the golden save cannot load even though the
   schema accepts its shapes.
4. **Low — deck-editor display for generic fusion recipes.**
   `DADeckLogic::GetAvailableFusionRecipes` now returns `AnyCount` recipes
   (F.G.D.), but `DADeckUI::DrawRecipesOverlay` builds its material line from
   `Recipe.Materials` only. The F.G.D. row therefore renders as
   `"  =  Five-Headed Dragon"`. The UI owner should render
   `"%d %s monsters"` (`Recipe.AnyCount`, `Recipe.MaterialsType`) when
   `AnyCount > 0`, or `"%d monsters"` when `MaterialsType` is empty. This is a
   display-only change in `DADeckUI.cpp`; the recipe is already correctly
   present in the data returned by the deck logic.
5. **Low — future `purchase_limit > 1` is unsupported.**
   Shipped rows all use 1, so the restock gate is equivalent. A future pack with
   a larger limit would still be restricted to one purchase per window until a
   per-window counter is added to `FDAEShopSaveData` (additive field) and
   `CheckPurchase`. This is documented on `FDAEPackDef`.
6. **Low — strict save validation rejects hand-edited/legacy malformed data.**
   This is intentional: silently repairing bad sections was the source of the
   E1/E6 defects. Current shipped saves and the A02 fuzz payloads satisfy the
   new contracts. If a migration window is needed, add an explicit
   version-specific repair step rather than loosening the validator.
7. **Low — fusion recipe hints are ownership-based.**
   `GetAvailableFusionRecipes` is a deck-editor hint, not a duel legality check.
   For `AnyCount` recipes it counts all owned monster copies of `MaterialsType`
   without knowing hand/field/graveyard/Extra zones; `FDuelEngine` performs the
   authoritative zone-aware selection. The result is conservative for the
   shipped F.G.D. recipe and matches the engine's type comparison.
8. **Low — art/portrait caches still have no invalidation API.**
   Missing art is cached as null for the session, and replacing a portrait or
   expression requires a restart. This is the pass-2 policy, retained to keep
   per-frame draw code cheap; document it in the owning UI contract if live
   replacement is ever needed.
9. **Medium — combined build and headless verification are still required.**
   The new tests and code paths are compile-ready but were not executed here.
   The parent should run the editor build, `-DAEconomySelfTest`, the story
   playthrough/self-test (save rollback and deck grants), and the save-fuzz
   suite. The expected self-test check count rises because of the new sections;
   `Tools/integration/run_smoke.py` parses the summary rather than a hard-coded
   count.
10. **Info — the full data validator is not green in this tree.**
    `Tools/validate/validate_all.py` reports canon-manifest hash/size mismatches
    for `cards_manifest.json` and `exams.json`. Those files are outside this
    workstream and were not touched; the parent should refresh the manifest only
    if the tree owner confirms the content is intended, per the validator hint.

## 7. Parent integration follow-up

The three economy hand-offs were implemented during integration:

- `ADAHUD::WireEconomySystems` now uses `Calendar->GetAbsoluteDay()` for the
  shop restock context.
- `UDADeckLogic::EnsureStarterDeck` was added; `UDAStorySubsystem::ApplyDeckGrant`
  imports the selected fire/water/wind recipe under its stable recipe id,
  grants its cards once, and activates the real player-deck id. A fresh opening
  resets inventory, shop purchase state and player decks first. `-DAStorySelfTest`
  now asserts the imported deck and granted collection.
- Inventory, shop and deck providers implement `ResetSaveSectionState()`, so a
  legacy payload without those sections no longer inherits the previous
  session's trunk/store/decks. The shop reset preserves HUD wallet handlers.
- `DADeckUI::DrawRecipesOverlay` renders `AnyCount` recipes as
  `"N <type> monsters"`.
- `settings.json` now uses the `F` duel-disk binding, and
  `golden_new_game.json` was wrapped in the current provider shape.

Final gates: `-DAEconomySelfTest` **446/446**, story self-test/playthrough and
save fuzz all pass. The canon manifest was refreshed after a concurrent
workstream restored it; `validate_all` now reports 0 errors.
