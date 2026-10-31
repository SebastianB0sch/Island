# A06 Economy Notes - Gate 3

Owner: A06 Quartermaster
Scope: shop catalogue, inventory pack opening, deck logic, A06 tests.
No UI, duel-rule, exam/opponent or canon-source files were edited.

## Dorothy's Gift resolution

**Resolution: canon full pool, not a fallback.**

`Content/Data/Canon/packs.json` marks Dorothy's Gift as:

- `full_pool: true`
- `pool_size_declared: 1200`
- `pool: []` (the guide says "all cards" rather than listing them)
- price `1000 DP`, `7` cards, weekly restock, `Get 90% Collection Rate`
- `stock: null` (unlimited)

A06 now materialises that full pool in `Content/Data/Shop/packs.json`:

- all `1,200` card ids (`1..1200`), grouped into the five rarity buckets from
  `Rules/card_rarity.json`;
- exactly one entry per card, i.e. copy weight `1` (uniform);
- `pool_card_count: 1200`, `pool_copy_weight: 1`,
  `pool_status: "canon_full_pool"`;
- `all_cards: true` and `prefer_unowned: true` remain set, so the runtime
  `any` slots still draw uniformly from the database and prefer cards the
  player does not own.

There is no non-canon fallback pool. Canon does not publish per-card pull
weights, so the uniform copy weight `1` is the only deterministic interpretation
of "all cards".

`Tools/economy/sync_canon.py` now re-materialises the Dorothy pool on every
canon sync instead of writing `pools: []`, so the fix is reproducible.

## Gate 3 follow-up: Extra Deck, Jaden and pending grants

- **Extra Deck cap is 15.** `Tools/economy/sync_canon.py` now writes
  `max_extra: 15`, `DADeckLogic.h` falls back to 15, and the self-test asserts
  15 is legal and 16 is rejected. `Rules/banned_limited.json` (already 15,
  owned by A07) was not modified by this follow-up.
- **Jaden player deck normalised.** `Content/Data/decks.json` `jaden` had four
  cards whose printed name is `Luster Dragon` (2 x 663 + 2 x 780). One 663 is
  replaced by Elemental HERO Sparkman (1109), matching A07's runtime Jaden
  deck. The deck now has 663 x1, 780 x2, 1109 x3, and records
  `runtime_adjustments: ["663->1109:Luster Dragon name cap -> Sparkman"]`.
  All five starter/default player decks pass the Year 1 banlist, 15-card Extra
  and 3-copy id/name checks.
- **Pending story pack grants.** `UDAInventorySubsystem::ConsumePendingPackGrant`
  consumes one A03 story grant, opens the catalogue pack, and adds its cards.
  The grant is consumed only after a successful open; a duplicate consume
  returns `no_pending_grant` and adds nothing. If the grant is lost between
  open and consume, the added copies are rolled back and the call returns
  `grant_consume_failed`. No DP is spent or credited by the free-grant path.

## Pack validation

`Tools/economy/validate_packs.py` is the A06 catalogue validator. It checks:

- 48 packs, unique ids, names, categories from the canon set families, sources;
- positive price, pack size, restock days, purchase limit, non-negative stock;
- unlock description and at least one known unlock condition;
- non-empty materialised pool, no duplicate pool ids, every id exists in the
  1,200-card database;
- fixed slots have a matching non-empty rarity pool;
- rare-plus slots have positive weights that point at a usable pool;
- normal pack pools match the canon `unique_card_ids`;
- Dorothy's Gift: 1,200 entries, full `1..1200` coverage, one copy weight,
  five materialised rarity pools, `all_cards`/`prefer_unowned`, price/size/
  restock/unlock and unlimited stock.

Commands:

```text
python Tools/economy/validate_packs.py
python Tools/economy/validate_decks.py
python Tools/economy/sync_canon.py
python Tools/validate/validate_all.py
```

Before the fix: A06 validator `FAIL - 6 issues` (empty Dorothy pool plus five
missing Dorothy pool metadata checks), and `validate_all` reported
`pack_pool: pack dorothys_gift has an empty pool [A06]`.

After the fix: A06 validator `PASS - 1342 checks, 0 failures`; `validate_all`
reports `PASS packs: 48 packs; pool union 1200 cards [A06]` and no A06
`pack_pool` finding. The separate A01 `canon_pack_empty` gap remains because
`Canon/packs.json` still represents the pool as `full_pool: true` with an empty
list; A06 must not edit canon source data.

`Tools/economy/validate_decks.py` audits all five starter/default player decks
against the Year 1 banlist, 15-card Extra Deck and 3-copy printed-name limit.
Before the Jaden fix it failed with 4 issues across 81 checks; after the
normalisation it reports `PASS - 81 checks, 0 failures`.

## Self-test coverage

Switch: launch with `-DAEconomySelfTest`; for an in-process run call
`UDAInventorySubsystem::RunSelfTest()`.

Expected result: **213 passed, 0 failed** (the existing 119 checks plus 94 new
A06 checks).

New coverage:

- `TestCatalogue` (+9): every pack has a materialised non-empty pool, valid
  card ids, no duplicate pool ids, matching fixed-rarity pools, sane rare-plus
  weights (default tables sum to 100), price/stock/restock/purchase-limit
  metadata, unlock text/conditions, and a known set/category plus source.
- `TestDorothysGift` (+41): definition/price/size/restock/stock, five
  materialised pools covering `1..1200` at weight 1, 90% collection lock and
  unlock boundary, successful purchase, 7-card reveal, DP deduction
  `5000 -> 4000`, inventory `0 -> 7` unique cards, new-card flags, purchase
  count increment, unlimited-stock semantics, weekly restock boundary
  (day +6 blocked, day +7 allowed), duplicate-heavy purchase converting all
  seven copies to `7 x 25 DP`, inventory staying at the 3-copy cap, and
  non-negative DP.
- `TestShop` (+2): a finite-stock purchase increments the purchase counter and
  decrements remaining stock (Dorothy itself is canon-unlimited).
- `TestPendingPackGrants` (+17): queue an A03 grant, consume it into inventory,
  verify exactly-once duplicate rejection, unknown-pack failure leaves the
  grant queued, no DP is spent, and story state is restored.
- `TestDeckCatalogue` (+10): Year 1 rules load with `max_extra == 15` and
  `max_copies == 3`; every starter and player deck is legal, fits the 15-card
  Extra Deck and respects the 3-copy printed-name limit.
- `TestBulkEconomy` (+15): every pack previewed 10 times with fixed seeds
  (480 preview pairs / 960 preview opens) and purchased 10 times (480
  purchases), checking valid card ids, pack-size counts, printed-pool
  membership, no in-pack duplicates, deterministic same-seed reveals,
  non-negative DP and stock, finite-stock decrement, unlimited stock staying
  `-1`, and a balanced DP ledger.

Existing checks remain unchanged, including the original 119 pack odds,
inventory, deck legality, purchase/restock and JSON round-trip cases.

## Remaining gaps / risks

1. `Canon/packs.json` still has an empty `pool` array for Dorothy even though
   `full_pool` is true. That is A01 data; the A06 runtime catalogue is fixed.
2. Exact Dorothy pull weights are unknown. A06 uses uniform copy weight `1`;
   only the "all cards" fact is canonical.
3. Pack slot layouts and rare-plus `70/22/6/2` odds remain provisional because
   A01 marks pack odds unresolved.
4. A06 treats positive canon `stock` as a lifetime purchase cap. Dorothy has
   `stock: null`, so A06 models it as unlimited with the weekly restock clock.
5. No Unreal build was run for this gate (compile-safe review only). The C++
   changes are limited to `DAShopSubsystem`, `DAInventorySubsystem`,
   `DADeckLogic` defaults and `DAEconomyTests`; run `-DAEconomySelfTest` on the
   next editor build to confirm the expected `213 passed, 0 failed`.
6. `DADeckUI.cpp` still contains a local fallback literal of `20` when
   `GetDeckLogic()` is unavailable. That is A09-owned UI code; with DeckLogic
   present the runtime always uses the rules file value of 15. A09 can align the
   fallback when it next touches the deck UI.
7. A06 consumes pending grants from A03's `UDAStorySubsystem` queue because that
   is where `GetPendingPackGrants()` / `ConsumePendingPackGrant()` currently
   live. No profile or story file was edited.
