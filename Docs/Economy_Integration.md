# Economy, Shop & Deck Integration (A06)

Status: **provisional content, stable C++ contracts**.
Owner: A06 Quartermaster. Runtime code lives in `DuelAcademyIsland/Source/DuelAcademyIsland/**`.

This document covers the card trunk, the 48-pack shop, deterministic pack
opening, ante hooks and deck construction. It deliberately does **not** cover
UI drawing, duel rules or the profile/save schema; those are A09, A04 and A02.

## 1. Files and data

| Path | Purpose |
| --- | --- |
| `Public/DAEconomyTypes.h` | Shared USTRUCTs/enums: rarity, pack definitions, reveal payload, collection stats, filters, save payloads. |
| `Public/DAInventorySubsystem.h` / `Private/DAInventorySubsystem.cpp` | `UDAInventorySubsystem`: collection counts, ownership copy cap, stats/filters, pack opening, ante, save JSON. |
| `Public/DAShopSubsystem.h` / `Private/DAShopSubsystem.cpp` | `UDAShopSubsystem`: 48-pack catalogue, unlock evaluation, atomic DP purchase, restock clock, save JSON. |
| `Public/DADeckLogic.h` / `Private/DADeckLogic.cpp` | `UDADeckLogic`: deck slots, 40–60/20/3 validation, banned/limited, edit/copy/erase/rename, sorting/filtering, starter decks, save JSON. |
| `Private/DAEconomyTests.*` | `-DAEconomySelfTest` suite (inventory, pack odds, deck legality, DP atomicity, round-trip payloads). |
| `Content/Data/Shop/packs.json` | 48 packs: ids, categories, prices, pack sizes, restock periods, unlock conditions, rarity pools, slots. |
| `Content/Data/Decks/player_decks.json` | Default player deck slot(s) and the starter collection list. |
| `Content/Data/Rules/banned_limited.json` | Rule limits + banned/limited/semi-limited schema. Empty list pending canon. |
| `Content/Data/Rules/card_rarity.json` | Global rarity hint for trunk filters/stats; derived from pack pools, provisional. |
| `Tools/economy/sync_canon.py` | Re-syncs `Shop/packs.json`, `Rules/card_rarity.json` and the year 1 banned list from A01's read-only `Canon/` data. Never edits `Canon/`. |

The existing `cards.json`, `decks.json` and `fusions.json` are unchanged.
`DACardDatabase.h`'s 32-card list remains only as the legacy `DAInteractable`
fallback; the real 1,200-card catalogue is the inventory + `Shop/packs.json`.

## 2. `UDAInventorySubsystem`

### Collection

```cpp
int32 AddCard(int32 CardId, int32 Count = 1);       // returns copies actually added
int32 RemoveCard(int32 CardId, int32 Count = 1);    // returns copies actually removed
int32 GetCount(int32 CardId) const;
bool  HasCard(int32 CardId, int32 MinCount = 1) const;
bool  CanAddCard(int32 CardId, int32 Count = 1) const;
const TMap<int32, int32>& GetCollection() const;    // C++ fast path
TMap<int32, int32> GetCollectionCopy() const;       // Blueprint
TArray<int32> GetCollectionCards() const;           // sorted ids
```

`MaxOwnedCopies` defaults to **3** and is loaded from
`Rules/banned_limited.json` (`max_owned_copies`). `SetMaxOwnedCopies(0)` means
unlimited. This is the **ownership** cap; deck copies are independently capped
by `UDADeckLogic`.

When a pack produces a card already at the ownership cap the copy is not added;
the reveal reports `bDuplicate=true` and `DuplicateDP` (default 25 DP from
`packs.json`). The shop credits that compensation to the wallet in the same
transaction. `duplicate_policy` is reserved for a future canon revision; the
current implementation always converts copies beyond the ownership cap to DP.

### Stats, filters, sorting

```cpp
FDAECollectionStats GetCollectionStats() const;
TArray<int32> FilterCollection(const FDAECardFilter& Filter) const;
TArray<int32> SortCards(const TArray<int32>&, EDAECardSortKey, bool bDescending) const;
EDAECardRarity GetCardRarity(int32 CardId) const;
```

`FDAECollectionStats` contains unique count, total copies, catalog size,
completion percentage, per-rarity counts, and type/attribute/monster-type maps.
`FDAECardFilter` supports name substring, card type/subtype, attribute,
monster type, rarity, ATK/LEVEL ranges and owned-only. Sort keys: id, name, ATK,
DEF, level, card type, attribute, monster type, rarity.

### Pack opening

```cpp
FDAEPackOpenResult OpenPack(const FString& PackId, int32 Seed);
FDAEPackOpenResult PreviewPack(const FString& PackId, int32 Seed);
FDAEPackOpenResult OpenPackDefinition(const FDAEPackDef&, int32 Seed, bool bAddToCollection = true);
```

* A non-zero seed is fully deterministic: same pack definition + same seed =
  same card ids and rarities. Seed `0` is generated from the platform clock.
* Slots are data-driven. `fixed` slots draw from one rarity pool; `rare_plus`
  draws from a weighted rare-or-better table (default 70/22/6/2); `any` draws
  from every card (Dorothy's Gift, which also prefers unowned cards).
* Within one pack duplicates are avoided when the pool has enough cards.
* Adding cards is atomic: if a later slot has an invalid/empty pool, every card
  added earlier in that call is rolled back before the error is returned.
* `FDAEPackOpenResult::Cards` is the complete reveal payload for A09:
  `CardId`, `Name`, `Rarity`, `bNew`, `bDuplicate`, `OwnedBefore`, `OwnedAfter`,
  `DuplicateDP`.

### Ante

```cpp
bool RemoveCardForAnte(int32 CardId, const FString& DuelId, const FString& Source);
bool ReturnAnteCard(const FString& DuelId);   // win/draw
bool CommitAnteLoss(const FString& DuelId);   // loss
int32 ReturnAllAnte();
TArray<FDAEAnteRecord> GetPendingAnte() const;
```

The card leaves the trunk when the ante starts and is only returned through
`ReturnAnteCard`; a loss path must call `CommitAnteLoss`. This prevents the
duplication exploit where the same copy is both staked and still in the trunk.

### Save payload

`ExportStateJson()` / `ImportStateJson()` and `GetSaveData()` /
`ApplySaveData()` persist:

```json
{
  "version": 1,
  "max_owned_copies": 3,
  "counts": { "1": 3, "40": 2 },
  "pending_ante": [ { "card_id": 1, "duel_id": "duel_01", "source": "free" } ]
}
```

A02 should store the JSON string (or map fields) inside the profile save. The
inventory never writes to disk itself. The subsystem also implements A02's
`IDASavePayloadProvider` (`section = "inventory"`) and registers itself in
`Initialize`; A02's `UDASaveSubsystem` can therefore write/read the section
without bespoke glue.

## 3. `UDAShopSubsystem`

### Catalogue and unlocks

```cpp
int32 GetPackCount() const;
TArray<FDAEPackView> GetCatalogue() const;       // all 48, locked or not
TArray<FDAEPackView> GetVisiblePacks() const;    // unlocked only
bool GetPackView(const FString& PackId, FDAEPackView& OutView) const;
bool GetPackDef(const FString& PackId, FDAEPackDef& OutPack) const;
FString GetUnlockReason(const FString& PackId) const;
float GetPackCompletionPercent(const FString& PackId) const;
float GetCollectionPercent() const;
```

`FDAEPackView` is the shop row payload: `PackId`, `Name`, `Category`, `Price`,
`PackSize`, `bUnlocked`, `bCanPurchase`, `Block`, `UnlockReason`, `StatusText`,
`RestockDays`, `LastPurchaseDay`, `NextAvailableDay`.

### Purchase

```cpp
bool CanPurchase(const FString& PackId, FString& OutReason) const;
bool PurchasePack(const FString& PackId, int32 Seed, FDAEPurchaseResult& OutResult);
```

Purchase flow is atomic:

1. `CheckPurchase` validates the pack, unlock conditions, wallet balance and
   restock clock.
2. DP is deducted through the A02 wallet delegate (or the standalone fallback).
3. The inventory opens the pack and adds cards. If opening fails, the DP is
   refunded.
4. Duplicate compensation, if any, is credited in the same transaction.
5. The restock day and purchase count are recorded and `OnPackPurchased` /
   `OnShopChanged` fire.

There is no path that deducts DP and then leaves the trunk unchanged, and the
shop never allows a negative balance.

### Unlock context (A02/A03 integration)

```cpp
void SetWalletHandlers(
    TFunction<int32()> GetDP,
    TFunction<bool(int32)> SpendDP,
    TFunction<void(int32, const FString&)> CreditDP);
void ClearWalletHandlers();

void SetUnlockContextProvider(TFunction<FDAEUnlockContext()> Provider);
void SetUnlockContext(const FDAEUnlockContext& Snapshot);
void RefreshUnlocks();
```

`FDAEUnlockContext` fields: `Title`, `MonthIndex` (1 = October), `DayNumber`
(absolute in-game day; `-1` disables restock), `DormChanges`, `Titles`,
`CompletedEvents`, `CompletedTutorials`, `DormsVisited`, `Flags`, `Counters`,
`LocationDuelCounts`, `PackCompletion`, `CollectionPercent`.

Structured condition types used by `packs.json`:

| Type | Meaning |
| --- | --- |
| `start` | Always available. |
| `tutorial` | `CompletedTutorials` contains `key`. |
| `event` | `CompletedEvents` contains `key`. |
| `counter` | `Counters[key] >= value`. |
| `title` | `Title` or `Titles` contains `key`. |
| `dorm_changes` | `DormChanges >= value`. |
| `visited_all_dorms` | Slifer + Ra + Obelisk in `DormsVisited`. |
| `pack_completion` | `GetPackCompletionPercent(key) >= value`. |
| `collection_percent` | `GetCollectionPercent() >= value`. |
| `location_duels` | `LocationDuelCounts[key] >= value`. |
| `month_at_least` | `MonthIndex >= value` (calendar packs; exact last-week windows await A02). |
| `flag` | `Flags` contains `key`. |

The `description` in each unlock node is the human-readable canon text; A09
should display it directly. Pack completion and collection percentage are
computed from the inventory when available, so A02 only needs to push the
event/title/calendar/counter snapshot.

### Restock clock

`packs.json` uses the GBA's "once a week / once each two/three/four weeks"
cadence. The shop stores `LastPurchaseDay` per pack and blocks a repeat until
`DayNumber - LastPurchaseDay >= restock_days`. A02 must update `DayNumber` in
the unlock snapshot when the calendar advances. Packs with a positive `stock`
from A01 canon also have a lifetime purchase cap; once `PurchaseCounts` reaches
`stock`, the row reports `SoldOut`.

### Shop save payload

```json
{
  "version": 1,
  "cached_dp": 900,
  "internal_wallet": true,
  "last_purchase_day": { "basic_1a": 12 },
  "purchase_counts": { "basic_1a": 2 }
}
```

When A02's wallet is registered, `cached_dp` is only a fallback; the profile
remains the source of truth. `UDAShopSubsystem` implements
`IDASavePayloadProvider` (`section = "shop"`) and registers automatically.

## 4. `UDADeckLogic`

### Rules

Loaded from `Rules/banned_limited.json`:

```json
{
  "max_owned_copies": 3,
  "rules": {
    "min_main": 40, "max_main": 60, "max_extra": 20,
    "max_copies": 3, "max_side": 0, "max_player_decks": 24,
    "deck_name_min_length": 1, "deck_name_max_length": 24
  },
  "banned": [],
  "limited": [],
  "semi_limited": []
}
```

`banned` accepts raw ids or `{card_id}` objects. `limited` accepts raw ids
(limit 1) or `{card_id, limit, reason}`. `semi_limited` defaults to limit 2.

### Validation API

```cpp
bool ValidateDeck(const FDAEDeck&, TArray<FDAEDeckError>& OutErrors) const;
TArray<FDAEDeckError> GetDeckErrors(const FDAEDeck&) const;
bool IsDeckLegal(const FDAEDeck&) const;
FString GetDeckValidationMessage(const FDAEDeck&) const;
static bool ValidateDeckAgainstRules(
    const FDAEDeck&, const FDAEDeckRules&, const UCardDatabaseSubsystem*,
    const UDAInventorySubsystem*, bool bCheckOwnership, TArray<FDAEDeckError>&);
bool ValidateDeckWithoutOwnership(const FDAEDeck&, TArray<FDAEDeckError>&) const;
```

`FDAEDeckError` has a stable `Code` (`FName`) and a GBA-style `Message`:

| Code | Message |
| --- | --- |
| `main_too_small` | `Your Main Deck must contain at least 40 cards.` |
| `main_too_large` | `Your Main Deck cannot contain more than 60 cards.` |
| `extra_too_large` | `Your Fusion Deck cannot contain more than 20 cards.` |
| `copy_limit` | `You cannot have more than 3 copies of the same card in your Deck.` |
| `banned_card` | `This card is forbidden and cannot be used in your Deck.` |
| `limited_card` | `This card is limited to 1 copy.` / `... 2 copies.` |
| `not_owned` | `You do not own this card.` / `You do not own enough copies of this card.` |
| `invalid_extra_card` | `Only Fusion Monsters can be placed in the Fusion Deck.` |
| `fusion_in_main` | `Fusion Monsters cannot be placed in the Main Deck.` |
| `unknown_card` | `This card is not in the card database.` |

These strings are **provisional GBA-style wording** until A01 supplies the exact
US ROM strings. The codes are stable; A09 should key layout/localisation on
`Code`, not on the message text.

### Editing API

```cpp
bool AddCardToDeck(DeckId, CardId, bool bExtra, FString& OutError);
bool RemoveCardFromDeck(DeckId, CardId, bool bExtra, FString& OutError);
bool SwapCardInDeck(DeckId, OldCardId, NewCardId, bool bExtra, FString& OutError);
bool RenameDeck(DeckId, NewName, FString& OutError);
FString CreateDeck(Name, FString& OutError);
bool CopyDeck(SourceDeckId, NewName, FString& OutNewDeckId, FString& OutError);
bool EraseDeck(DeckId, FString& OutError);
bool SetActiveDeck(DeckId, FString& OutError);
```

`AddCardToDeck` allows an incomplete deck while editing (so the UI can build up
to 40), but enforces zone type, ownership, copy limit, banned/limited and the
60/20 hard caps. `SetActiveDeck` requires a fully legal deck because it is the
deck a duel will use.

Starter decks from `decks.json` are exposed through `GetStarterDecks()` and
`GetStarterDeckCards()`. `ImportStarterDeck` copies one into a new player slot.
`GetAvailableFusionRecipes()` returns recipes whose listed materials are owned.

### Collection views

`SortCardIds`, `FilterCardIds` and `GetCollectionView` provide the trunk's
sort/filter data without touching UI state. `GetCollectionView` uses the
inventory's owned cards by default.

### Deck save payload

```json
{
  "version": 1,
  "active_deck_id": "player_1",
  "decks": [
    {
      "id": "player_1", "name": "My Deck",
      "main": [40, 117, 148],
      "extra": [319],
      "bStarter": false, "bPlayerDeck": true
    }
  ]
}
```

A02 embeds this payload; deck ownership is not duplicated in the save. On load,
inventory counts are restored first, then decks, then the shop restock state.
`UDADeckLogic` implements `IDASavePayloadProvider` (`section = "decks"`) and
also implements A02's `IDAProfileDeckInterface` (`GetDeckIds`,
`GetActiveDeckId`, `SetActiveDeckId`). `UDAInventorySubsystem` implements
`IDAProfileInventoryInterface` (`GetOwnedCardCount`, `GetDistinctCardsOwned`).
All three providers register themselves in `Initialize`.

## 5. A02 / A04 / A09 integration points

### A02 — Registrar (profile, calendar, save)

* On new game: `Inventory->ResetCollection()`, then
  `Inventory->GrantStarterCollection(DeckLogic->GetDefaultStarterCards())`.
  The starter list intentionally keeps duplicate copies (the default Fire deck
  has two copies each of cards 483 and 892), so the granted collection supports
  every copy in the default 40-card deck.
* Register the wallet once the profile exists:

  ```cpp
  Shop->SetWalletHandlers(
      [Profile]() { return Profile->GetDP(); },
      [Profile](int32 Amount) { return Profile->TrySpendDP(Amount); },
      [Profile](int32 Amount, const FString& Reason) { Profile->AwardDP(Amount, Reason); });
  ```

* Push a fresh `FDAEUnlockContext` after any calendar/title/event/counter
  change. `DayNumber` drives the restock clock; `MonthIndex` is 1-based from
  October.
* Save the three JSON payloads under the profile's `inventory`, `shop` and
  `decks` fields. Import order: inventory, decks, shop.
* Autosave after a successful `PurchasePack` (listen to `OnPackPurchased`).

### A03 — Director (story rewards)

* Card reward: `Inventory->AddCard(CardId, Count)` (respects the cap; use
  `GrantStarterCollection` for a bundle).
* Pack reward: `Shop->PurchasePack` is a *paid* path; story grants should call
  `Inventory->OpenPack(PackId, Seed)` directly and skip the wallet.
* Event completion: add the event key to `FDAEUnlockContext::CompletedEvents`;
  the shop will unlock the matching pack.
* Ante event: `RemoveCardForAnte` before the duel; `ReturnAnteCard` on a win or
  draw; `CommitAnteLoss` on a loss.

### A04 — Rules Architect (duel rules)

* Use `UDADeckLogic::ValidateDeckAgainstRules` for the shared legality contract.
  It is a pure static function; pass `bCheckOwnership=false` for opponent decks.
* `Rules.GetCopyLimit(CardId)` is the single source of truth for the 3-copy /
  banned / limited limits.
* Ante is already handled by the inventory hooks; A04 only needs to report the
  win/loss and call the right hook.
* The `FDAEDeck` arrays are the input to the duel's deck loader; no engine
  mutation is performed by this subsystem.

### A09 — Interface (shop/deck UI)

* Shop browse: `GetCatalogue()` / `GetVisiblePacks()`, read `FDAEPackView`.
* Pack reveal: call `PurchasePack(PackId, 0, Result)` on confirm, then animate
  `Result.Open.Cards` (each has `bNew`, `bDuplicate`, `DuplicateDP`). The
  purchase is already applied; there is no separate confirmation step that can
  duplicate cards.
* DP HUD: `Shop->GetDP()` and `Shop->OnPackPurchased`.
* Trunk: `Inventory->GetCollectionStats()`, `GetCollectionCards()`,
  `FilterCollection()`, `SortCards()`.
* Deck editor: `GetPlayerDecks()`, `ValidateDeck()`, `GetDeckErrors()`, editing
  calls; show `FDAEDeckError::Message` and key layout on `Code`.
* Locked pack row: `GetUnlockReason()` / `FDAEPackView::StatusText`.
* Do not call `AddCard`/`OpenPack` from UI except through `PurchasePack`; the UI
  must not implement purchase or copy-limit rules.

### A07 — Challenger (opponents/decks)

* `ValidateDeckWithoutOwnership` validates canonical opponent decks.
* `GetStarterDecks()` exposes the existing Fire/Water/Wind/Jaden lists for
  starter selection without duplicating the data.
* `ImportStarterDeck` can create a player-owned copy when a story grants one.

## 6. Self-test

Run the editor/game with:

```text
-DAEconomySelfTest
```

The suite loads after the game instance settles and exits the process. It
checks:

* 1,200-card add/remove and 100% collection stats.
* Ownership copy cap (3 by default), refill and unlimited mode.
* Ante remove/return/loss.
* 48-pack catalogue, prices, slot counts and all-1,200 obtainability.
* Seeded pack determinism (same seed = identical reveal), variation across
  seeds, no card outside the printed pool.
* 20,000-open rarity distribution for `basic_1a` (70/22/6/2 within tolerance).
* Every pack opens 50 times with the correct card count.
* Dorothy's Gift all-cards / prefer-unowned behaviour.
* Default deck legality, 40/60/39/61 main-deck boundaries, 20/21 extra,
  3/4 copies, banned/limited/semi-limited, unowned card rejection.
* Add/remove/swap/rename/copy/erase and deck JSON round-trip.
* DP purchase success, insufficient DP, restock, wallet rejection, locked-pack
  unlock, duplicate compensation arithmetic, no negative DP.
* Inventory/shop/deck JSON round-trips.

Use `UDAInventorySubsystem::RunSelfTest()` for an in-process run that returns
the report string without requesting exit.

## 7. Canon gaps / provisional decisions

1. **Pack ids/names/categories/prices/pack sizes/pools** are synced from
   A01's `Content/Data/Canon/packs.json` (Yugipedia/ROM extraction). The local
   `Shop/packs.json` marks them provisional only because **odds are unresolved**
   in A01's data (`odds_status: "unresolved"`).
2. **Rarity odds** (70/22/6/2 for the rare-or-better slot) are a starter
   approximation, not extracted canon. The self-test proves the implementation
   matches the data, not that the data matches the GBA.
3. **Pack slots** are generated from pack size and available rarity pools. The
   canon data gives pools, not the exact in-pack slot composition. A01 should
   supply exact slot tables if the ROM exposes them.
4. **Ownership cap**: the brief specifies a data-driven default of 3. The GBA
   may allow more than three owned copies; `max_owned_copies` is isolated so
   A01 can change it without touching code. Duplicate compensation (25 DP) is a
   placeholder policy.
5. **Banned/limited list** is populated with A01's year 1 canon list
   (14 Forbidden, 40 Limited, 7 Semi-Limited). Years 2 and 3 remain available
   in `Canon/banned_list.json` for later story phases; A02/A04 must switch the
   active year list when the calendar advances if the port models that change.
6. **Deck error messages** are GBA-style but not verified against the US ROM.
   Stable codes are safe for UI keys.
7. **Player default deck** reuses the existing Fire Starter list so it is legal
   with existing cards and the year 1 banned list. A01 should replace it with
   the canonical player starter deck and `starter_cards` bundle.
8. **Unlock keys** (`tutorial`, `event`, `counter`, `location_duels`, ...) use
   slugs chosen for this port. A03's event/counter names must match the keys in
   `packs.json`; a mismatch simply leaves the pack locked until the data is
   reconciled.
9. **Calendar packs** use `month_at_least` for now. Canon descriptions such as
   "last week of October" and "January 23rd of the second year" need A02 to
   expose exact date windows; until then these packs unlock at the start of the
   month rather than the exact week/day.
10. **Dorothy's Gift** is implemented as all 1,200 cards, preferring unowned
    cards. Canon says it contains all cards; exact pull weights are not known.
11. **Restock cadence** uses the canon/A01 text. The GBA's exact in-game day
    reset semantics need verification.
12. **Stock** from A01 canon is treated as a lifetime purchase cap. This is an
    interpretation; verify whether the GBA's stock resets with the restock.
