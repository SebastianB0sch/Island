# 03 — UI layer

Branch: `refactor/code-review-pass`

Scope: `DADuelUI.*`, `DAHUD.*`, `DAPDAUI.*`, `DATitleScreen.*`, `DADialogueUI.*`,
`DADeckUI.*`, `DAShopUI.*`, `DAExamUI.*`, `DAUIScreen.*`, and this report. No
game data, Python, story/engine logic, or out-of-scope C++ was changed.

## Summary

The UI layer is roughly 14k lines of Canvas code. The main structural pressure
is `DADuelUI.cpp`: `DrawDuelActive` (502 lines), `DrawDuelFx` (433),
`HandleDuelHit` (315) and `SpawnDuelFx` (314). The shared `FDAUIScreen` base
already owns Canvas primitives for deck/shop/exam, but the duel, dialogue, PDA,
title and HUD screens still carry private copies of the same drawing, text
measurement, wrapping, sound and hit-test code.

This pass split three of the largest duel functions into cohesive same-file
helpers (`DrawDuelLog`, `DrawDuelHand`, `DrawDuelCommandPanel`,
`ResolveDuelFxPath`, `SpawnDuelFxReaction`, `HandleDuelChoiceHit`) without
changing draw order, coordinates, timing or public APIs. It also fixed the
highest-confidence stale-index/modal-message defects found in the review and
consolidated the three identical status-string ellipsis loops onto
`FDAUIScreen::Ellipsize`.

`DrawDuelFx` remains large and is listed as the next split candidate rather than
being mechanically reshaped in this pass.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| F1 | Medium | `DADeckUI.cpp:796,805` | `HandleHit` copied raw hit indices into `CollectionSelection` / `DeckCardSelection`. Hit targets are from the previous Draw, so a filter change, deck switch or erase in the same frame can deliver an index that is out of range for the new list. Downstream lookups are guarded, so this is wrong-focus/OOB-cursor state rather than a crash. | Fixed: clamp to the current list size. |
| F2 | Medium | `DAShopUI.cpp:399,404` | Same stale-hit issue for pack and category hits. `Selection` could point past `Filtered`, and `CategoryIndex` was not validated. | Fixed: clamp to `Filtered` / `Categories`. |
| F3 | Medium | `DAExamUI.cpp:457,557` | `AnswerSelection` survived question changes. If the next question had fewer options, Enter submitted an invalid index and the question appeared unresponsive. | Fixed: clamp on update and on answer hit. |
| F4 | Medium | `DADuelUI.cpp:2137-2150` | The `pile` action decoded `Value % 10` straight into `EDuelPileType` with no range check. An unexpected hit target could set an invalid enum (drawing then silently ignored it). | Fixed: accept only Deck..Banished. |
| F5 | Medium | `DADuelUI.cpp:1774-1780` | `DuelShowMessage` accepted a colour but never stored or used it; every hint rendered gold, including the explicit blue "hand limit met" message. | Fixed: store `DuelMessageColor`, use it in the board and choice hint strips. Default argument now matches the old rendered gold so unchanged callers look the same. |
| F6 | Medium | `DADuelUI.cpp:882-897` | `UpdateDuel` returns from the winner branch before the shared Space/right-click skip block. The final damage/win beat still shows the "SPACE / RIGHT-CLICK ... SKIP" hint, but those keys do nothing until the result card appears. | Not fixed — timing/input product decision; follow-up. |
| F7 | Medium | `DAHUD.cpp:472-484` (compare `OpenShop` 1046-1080, `OpenDeckEditor` 1091-1125, `OpenExam` 1136-1170) | `OpenDuelDeckSelect` refuses title/gameplay UI but does not close or refuse map, PDA or dialogue. A caller can stack a duel over an existing modal; `Tick` updates the duel first and `DrawHUD` returns after drawing it, hiding the older screen while it remains open. | Not fixed — the story caller (`DAStorySubsystem.cpp:1785`) may rely on current ordering; needs a deliberate modal policy. |
| F8 | Low | `DAHUD.cpp:1476-1483`, `DrawHUD` 1670-1674 | `ToggleHelp` does not check `bMapOpen`. Help can open while the map is up but is not drawn because the map path returns first; it appears only after closing the map. | Not fixed. |
| F9 | Low | `DADialogueUI.cpp:800-834` | Dialogue panel height grows with choice count without clamping its top; completed text beyond the 3/4 wrapped-line cap is silently clipped (the ellipsis is only drawn while typing). | Not fixed. |
| F10 | Low | `DATitleScreen.cpp:1031-1057` | Continue cards use a 92 px minimum height and no scroll, so a save list larger than ~5 slots overflows the panel. Current data is four slots; latent. | Not fixed. |
| F11 | Low | `DADeckUI.cpp:1222-1237` | Fusion recipe lines are drawn unwrapped and untrimmed; long card names can run past the overlay edge. | Not fixed. |
| F12 | Info | `DAShopUI.cpp:127` | `Selection = Filtered.Num() > 0 ? 0 : 0;` was a redundant expression. | Fixed: `Selection = 0;`. |
| F13 | Info | `DADuelUI.cpp:2605` | `DrawDuelFx` (433 lines) is now the largest function in the file. Its per-event branches are independent and safe to extract next. | Deferred. |

### Duplication inventory

Documented rather than force-consolidated, because the implementations differ in
scale policy (duel text boost, dialogue/PDA per-call scale, title screen-space
layout, HUD base scale):

- Canvas primitives `DrawRect`, `DrawText`, `DrawPanel`, `Diamond`, `Measure`,
  `WrapText`, `PlaySfx`: `DADuelUI.cpp:213-280`, `DADialogueUI.cpp:662-769`,
  `DAPDAUI.cpp:1394-1490`, `DATitleScreen.cpp:783-881`,
  `DAHUD.cpp:1340-1415`, duplicated against `DAUIScreen.cpp:83-179`.
- Hit-target structs and reverse hit-test loops: `FDuelHitTarget`
  (`DADuelUI.h:34`), `FDADialogueHitTarget` (`DADialogueUI.h:82`),
  `FDAPDAHitTarget` (`DAPDAUI.h:168`), `FDATitleHitTarget`
  (`DATitleScreen.h:51`) versus `FDAUIHitTarget` (`DAUIScreen.h:17`). The duel
  uses `Value` where the base has `Index`; pointer/INDEX_NONE semantics also
  differ, so this needs an adapter, not a rename.
- Modal open/close guards: `ADAHUD::OpenShop`, `OpenDeckEditor`, `OpenExam`,
  `OpenTitle`, `OpenPDA`, `BeginDialogue` repeat the same "close the other
  overlays, restore input mode" sequence.
- Status ellipsis: deck/shop/exam were identical loops and are now
  `FDAUIScreen::Ellipsize`; `DAPDAUI.cpp:1844-1849` and
  `DATitleScreen.cpp:1356-1360` still carry private copies because those
  classes do not derive from `FDAUIScreen`.

## Changes

### `DADuelUI.cpp` / `.h`

- `DrawDuelActive`: 502 → 236 lines. Extracted:
  - `DrawDuelLog` (30 lines) — left log panel, entry tones and turn/phase footer.
  - `DrawDuelHand` (32 lines) — player hand layout, selection lift, hover/choice
    targets and discard/select hit actions.
  - `DrawDuelCommandPanel` (225 lines) — right detail panel, discard/tribute/card
    detail, action list, battle targets and primary phase buttons.
- `SpawnDuelFx`: 314 → 23 lines. Extracted:
  - `ResolveDuelFxPath` (220 lines) — the first event switch computing source,
    target, duration and banners.
  - `SpawnDuelFxReaction` (81 lines) — the portrait cut-in reaction switch.
- `HandleDuelHit`: 315 → 255 lines. Extracted `HandleDuelChoiceHit` (74 lines)
  for the pending-choice action set.
- Added `IsDuelHoverRect` so the extracted hand helper and the remaining board
  lambdas use the same hit rectangle.
- Added `DuelMessageColor` and used it in both hint strips; default colour kept
  visually identical.
- Added the pile-type range check.

### Stale-index fixes

- `DADeckUI::HandleHit`: clamp collection and main/extra deck selections to the
  current array.
- `DAShopUI::HandleHit`: clamp pack and category selections; removed the
  redundant ternary in `RefreshCatalogue`.
- `FDAExamUI`: clamp `AnswerSelection` whenever the written question changes and
  when an answer row is clicked.

### Shared base

- Added `FDAUIScreen::Ellipsize(Str, MaxWidth, Scale, Font)` and replaced the
  identical truncation loops in `DADeckUI::DrawStatus`, `DAShopUI::DrawStatus`
  and `FDAExamUI::DrawStatus`. Output is byte-for-byte the same for the same
  inputs (same chop-by-4 plus `"..."` behaviour).

## Verification

**Integration:** the combined editor build passed and the duel/puzzle/exam and
story playthrough suites pass. See [00-overview.md](00-overview.md).

- `git diff --check` over every file in scope: exit 0 (only Git's
  LF/CRLF advisories).
- Brace balance checked for each changed `.cpp`; all balanced.
- Diff inspected hunk-by-hunk: draw order, coordinates, colours, hit actions and
  timing constants in the moved duel code are unchanged.
- Public APIs unchanged. The only header changes are private helper
  declarations, one private member, and a private default argument value.
- No build or editor run was performed, per the parent session's instruction.
- No files outside this report's scope were edited. Other in-flight changes that
  `git status` currently shows (`.github/workflows/ci.yml`, `DADuelEngine.cpp`,
  `DAStorySubsystem.*`, `Tools/*`) were left untouched.

## Follow-ups

1. Split `DrawDuelFx` (433 lines) by event family: card flight (Draw/Summon/
   Spell/Trap/Attack), impact (Damage/Destroy/Position), transfer
   (Discard/Banish/Search/Mill/Return), and fusion/counter/effect.
2. Decide the final-beat skip policy and make the hint truthful (move the
   Space/right-click skip above the `HasWinner` return, or process
   `skipfx` hit targets there).
3. Define one modal policy for `ADAHUD::OpenDuelDeckSelect` (close map/PDA/
   dialogue like `OpenShop`, or refuse) after checking the story duel caller's
   ordering assumptions.
4. Migrate the remaining screens onto `FDAUIScreen` text/hit helpers, or add a
   shared free-function header if inheritance is undesirable. The duel text
   boost and per-screen scale policy must be parameters, not copied constants.
5. Unify hit-target structs/adapter and share the reverse-order hit-test loop.
6. Add screenshot/automation coverage for: stale hit after filter/deck switch,
   exam question-size change, invalid pile payload, colored duel messages, and
   the winner-state skip hint.
7. Low-priority UI polish: help-over-map precedence, dialogue overflow
   indicator, continue-slot overflow, recipe line trimming.
