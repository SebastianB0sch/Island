# A06 — Quartermaster

> **Read first:** `Docs/PORT_MASTERPLAN.md` (data contracts, economy).
> **Role:** economy, shop, inventory, card trunk and deck builder logic.
> **Baseline branch:** `port/baseline` → work branch `port/a06-quartermaster`.

## Mission

Make DP, packs, the card trunk and deck construction work like the GBA game — 48 packs, 1,200 cards, 3-copy limits, legal decks and the full shop experience (logic side; A09 draws the screens).

## Inputs

- A01: `packs.json`, `decks.json`, `banned_list.json`, `dp_rules.json`.
- A02: profile/DP/save APIs.
- A04: deck validation/banned list; A05: effect support manifest.
- Current: `Content/Data/cards.json`, `decks.json`, `fusions.json`, `DACardDatabase.*`, `DACardRecords.*`.

## Owned files

- `.../DAInventorySubsystem.*`, `DAShopSubsystem.*`, `DADeckLogic.*`
- `.../DACardDatabase.*`, `DACardRecords.*` (data loaders)
- `Content/Data/Shop/**`, `Content/Data/Decks/**`
- `Tools/economy/**`
- Tests: `DAInventoryTests.cpp`, `DAShopTests.cpp`, `DADeckTests.cpp`

Do not edit UI, duel rules, story, world or save schema.

## Deliverables

1. **`UDAInventorySubsystem`**
   - Card ownership counts (1,200), 3-copy limit (verify), add/remove, collection stats, rarity/type/attribute filters.
   - Pack opening: seeded RNG, rarity slots, guaranteed rules, duplicate handling, reveal data for UI.
   - Ante removal/return; deck ownership validation.
   - `AddCard`, `RemoveCard`, `GetCount`, `HasCard`, `OpenPack`, `GetCollection`, `ValidateDeck`.

2. **`UDAShopSubsystem`**
   - 48 packs: id/name/price/unlock (month/event/title)/pool/odds/pack size.
   - Purchase flow: DP check, deduct, open, add cards, save/autosave, result payload.
   - Unlock reasons for UI; Dorothy's Gift event pack; sold-out/one-time rules if canon.
   - Pack odds simulation test within canonical tolerance.

3. **`DADeckLogic`**
   - Main deck 40–60, Extra/Fusion deck ≤20, 3 copies, banned/limited; exact GBA-style errors.
   - Add/remove/swap, copy/erase, rename, sort/filter, recipes, starter decks, player deck slots.
   - Deck validation shared with A04; no engine mutation from UI.
   - Save/load integration with A02; no duplication exploits.

4. **Data loaders**
   - Extend `DACardDatabase`/`DACardRecords` to load packs/decks/rules/effect manifest; keep 1,200 cards and current 4 decks working.
   - Replace `DACardDatabase.h`'s 32 fan cards with the canon shop path; keep a clearly marked fallback only if needed.

5. **Tests**
   - Pack odds/pools; every card obtainable; no pack references missing cards.
   - DP purchase/refund/insufficient funds; no negative DP.
   - Deck legality (size, copies, banned, extra); copy/erase; save/load.
   - Duplication/ante edge cases.

## Work plan

1. Define inventory/deck/shop APIs; review with A02/A09.
2. Implement inventory + pack opening with stub packs.
3. Implement shop/unlocks/purchase + Dorothy's Gift.
4. Implement deck logic + validation; migrate the 4 existing decks.
5. Load A01's 48 packs/decks; run obtainability simulation.
6. Add tests; freeze API for A09.
7. Support A03 event rewards (cards/packs/DP) and A07 ante.

## Acceptance criteria

- [ ] 1,200 cards in inventory; 3-copy limit (or canon) enforced.
- [ ] 48/48 packs with price/unlock/pool/odds; all cards obtainable.
- [ ] Pack odds simulation within tolerance; no missing card references.
- [ ] Deck editor logic: 40–60 main, ≤20 extra, banned/limited, copy/erase, rename, sort/filter.
- [ ] DP cannot go negative; purchases atomic; save/autosave.
- [ ] Existing 4 decks still load/play; new decks save/load.
- [ ] No UI/rules/story edits; APIs stable for A09/A03/A07.

## Non-goals

- Drawing shop/deck UI (A09), card effects (A05), opponent decks/AI (A07), story rewards scripting (A03).

## Handoff report

Report: pack/deck counts, obtainability simulation, API signatures, known canon ambiguities, blockers.
