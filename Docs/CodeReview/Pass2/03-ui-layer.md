# 03 — UI layer (pass 2)

Branch: `refactor/code-review-pass`

## Scope and constraints

Scope: `DADuelUI.*`, `DAHUD.*`, `DAPDAUI.*`, `DATitleScreen.*`,
`DADialogueUI.*`, `DADeckUI.*`, `DAShopUI.*`, `DAExamUI.*`, `DAUIScreen.*`,
and this report. No game data, Python, story/save, engine, effect-runtime or
other workstream files were changed.

The uncommitted pass-1 work is the baseline. This pass only adds the remaining
UI follow-ups and high-confidence UI fixes; public APIs are unchanged apart
from private helper declarations/members and the already-additive result state.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P2-UI-01 | Medium | `DADuelUI.cpp:2605` (old) | `FDADuelUI::DrawDuelFx` was still a 433-line event switch after pass 1. It mixed every animation family in one function, making ordering and hit-target reviews expensive. | Fixed: split into 12 event-family helpers plus a shared frame helper; dispatcher preserves the old branch order. |
| P2-UI-02 | Medium | `DADuelUI.cpp:882-903` | The `HasWinner` branch returned before the shared Space/right-click skip block. The final beat still showed the skip hint, but only launched the result after the timer. A click on a cut-in was also ignored while the branch was returning. | Fixed: the winner branch now handles Space/right-click and `skipfx` hit targets while presentation is active. The hint is computed from the same helper. |
| P2-UI-03 | Medium | `DADuelUI.cpp:896`, `ResolveDuelFxPath`/`SpawnDuelFxReaction` Win cases, `DrawDuelResult` | `ResultStats.bDraw` was recorded by `NotifyDuelFinished`, but the result screen used only `bDuelResultWon`, so a simultaneous-LP draw rendered as "DUEL LOST" (and the final beat banner/cut-in said the same). | Fixed: first-class draw presentation in the final beat and result screen (`DUEL DRAW`, neutral accent, no confetti/red vignette, both portraits lit, draw quote). No engine change. |
| P2-UI-04 | Medium | `DAHUD.cpp:472-484` | `OpenDuelDeckSelect` refused title/gameplay UI but left the map, PDA and dialogue open under the duel, unlike `OpenShop`/`OpenDeckEditor`/`OpenExam`. | Fixed: one policy for all four openers — refuse title/duel, close shop, deck, exam, map, PDA, dialogue and help first. Story ordering checked: duel commands run only after dialogue closes. |
| P2-UI-05 | Low | `DAHUD.cpp:1476-1483`, `DrawHUD` 1670-1674 | Help could be toggled while the map was open but was not drawn because the map path returned first. | Fixed: help is now drawn over the map, so the F1 toggle is never invisible. |
| P2-UI-06 | Low | `DADialogueUI.cpp:797-905` | The choice panel grew upward without a top clamp, and completed text beyond the 3/4 wrapped-line cap lost its ellipsis (it was only drawn while typing). | Fixed: panel/top clamp with a selection-following option window and scroll marks; ellipsis now shows for completed overflow text. |
| P2-UI-07 | Low | `DATitleScreen.cpp:1031-1057` | Continue cards had a 92 px minimum and no scrolling, so large save lists ran under the back button. | Fixed: overflow switches to a fixed-height scrolling list around the selection; small lists keep the original stretched layout. |
| P2-UI-08 | Low | `DADeckUI.cpp:1222-1237` | Fusion recipe lines were drawn unwrapped and untrimmed, so long names ran past the overlay edge. | Fixed: line is ellipsized to the overlay width. |
| P2-UI-09 | Low | `DADeckUI.cpp`, `DAShopUI.cpp`, `DAExamUI.cpp` | Only status bars used `FDAUIScreen::Ellipsize`; deck names, card rows, pack names, exam topics/answers/buttons could still spill. | Fixed: applied the shared `Ellipsize` to these derived-screen labels. |
| P2-UI-10 | Info | `DAPDAUI.*`, `DAUIScreen.*` | No pass-2 defect found. The PDA/title status ellipsis copies remain because those classes do not derive from `FDAUIScreen`. | Audited; no change. |
| P2-UI-11 | Info | UI harness | Draw/skip/modal/overflow checks need Canvas output; there is no renderer-free UI harness. | Documented visual checks below; no fake source-text tests added. |

## Changes

### `DADuelUI.cpp` / `.h`

- `DrawDuelFx` (433 → 71 lines) now only walks `DuelFx`, computes
  `Local/T/Ease/Alpha/SideColor` exactly as before, and dispatches in the
  original order:
  - `DrawDuelFxDraw` — card draw flight, ghosts, destination glint.
  - `DrawDuelFxSummon` — Summon/Set column, ring, drop, label.
  - `DrawDuelFxSpellTrap` — rune ring, cast flash, card flight.
  - `DrawDuelFxAttack` — charge ring, ghosts, speed lines, impact burst.
  - `DrawDuelFxDamage` — Damage/Heal burst, sparks, number, CRITICAL label.
  - `DrawDuelFxDestroy` — implosion ring, shards, slashes.
  - `DrawDuelFxTransfer` — Discard/Banish/Search/Mill/Return card flight.
  - `DrawDuelFxPosition` — position-change ring.
  - `DrawDuelFxFusion` — Fusion/Ritual backdrop, rings, rays, seal.
  - `DrawDuelFxCost` — LP cost rise.
  - `DrawDuelFxCounter` — counter ring and count.
  - `DrawDuelFxEffect` — generic effect text.
  - `DrawDuelFxFrame` replaces the local frame lambda; its four `DrawRect`
    calls are unchanged.
  All coordinates, colours, timings, text and draw order are copied verbatim;
  the split only moves each branch body into a member helper.
- Added `IsDuelPresentationActive()` and used it in three places (winner skip,
  shared skip, hint strip) so the hint cannot claim a skip that input does not
  implement.
- The `HasWinner` branch now accepts Space, right-click and `skipfx` clicks
  before returning. `SkipDuelPresentation` still caps the pending result delay
  at 0.6 s, so normal (non-skip) result timing is unchanged.
- During the winner beat the hint is either the skip hint (presentation active)
  or "THE DUEL IS OVER." instead of the normal board controls.
- Result transition now reads `GetResultStats().bDraw`, then sets
  `bDuelResultWon` only for a genuine win. `bDuelResultDraw` is reset on deck
  select and duel start. `NotifyDuelFinished` keeps its existing contract: it
  reads `bDraw` from the engine stats and forwards it to the profile/opponent.
- `DrawDuelResult` renders draw as a first-class third state: neutral accent,
  no loss vignette, no win confetti, `DUEL DRAW`, `<opponent> - DRAW`,
  neutral portraits and a draw quote.
- The final `Win` visual event also checks `ResultStats.bDraw` so the banner and
  cut-in say `DUEL DRAW` / `BOTH DUELISTS AT 0 LP` instead of a loss beat.

### `DAHUD.cpp`

- `OpenDuelDeckSelect` now follows the shop/deck/exam modal policy: refuse
  while the title or a duel is open; otherwise close shop, deck editor, exam,
  map, PDA, dialogue, clear help, then open the duel picker.
  The story caller reaches a duel command only after `bWaitingForDialogue`
  clears, so closing a leftover dialogue here is safe.
- `DrawHUD` draws help above the map before returning from the map path.

### `DADialogueUI.cpp`

- Choice panels are clamped to a safe top. When rows do not fit, a window of
  rows follows `ChoiceSelection` and `^`/`v` marks show hidden rows; Up/Down
  plus Enter still reach every option (number keys cover the first nine).
- The wrapped-line overflow ellipsis is drawn whenever the text exceeds the
  cap, not only while typing.

### `DATitleScreen.cpp` / `.h`

- Added private `ContinueScroll`. Small save lists retain the original
  `Max(92, available / slot count)` card height. Overflowing lists use the
  minimum height, show as many rows as fit, auto-scroll to the selection and
  draw `^`/`v` scroll marks. `ShowPanel(Continue)` resets the scroll.

### `DADeckUI.cpp`

- Fusion recipe lines are ellipsized to `W - 52*S`.
- Deck-list names and collection/deck card names are ellipsized to their
  available column width.

### `DAShopUI.cpp`

- Detail, row, confirm and pack-reveal pack/card names use `Ellipsize` with
  the actual right-hand price reservation.

### `DAExamUI.cpp`

- Exam topic line, answer labels and generic buttons use `Ellipsize`.

### `DAPDAUI.*`, `DAUIScreen.*`

- Audited only; no pass-2 changes. `FDAUIScreen::Ellipsize` is unchanged.

## Verification

- `git diff --check` over every file in scope: exit 0 (Git only prints its
  LF/CRLF advisory for these files).
- Structural check (string/comment-aware brace and parenthesis balance) over
  every changed `.cpp`/`.h`: all balanced.
- One-off source assertions confirmed the `DrawDuelFx` helper order, winner
  skip before its return, draw result branch, duel modal close set,
  help-over-map draw, dialogue/title overflow code and `Ellipsize` adoption.
- Reviewed the `DrawDuelFx` split hunk-by-hunk: event branch order, helper
  arguments, coordinates, colours, timing constants and text match the old
  bodies. `DrawFrame` call sites (10) all map to `DrawDuelFxFrame`.
- Confirmed all `bDuelResultWon` presentation branches now treat draw
  explicitly; no remaining draw path renders as a loss.
- No UnrealBuildTool or UnrealEditor run was performed, per the brief.
- No files outside this report's scope were edited by this workstream.

### Visual checks still required

These need a renderer, so they are documented rather than automated:

1. **Draw result**: start a duel and arrange both LP to reach 0 on the same
   resolution (e.g. a reflected burn effect). Expect the final banner/cut-in to
   say `DUEL DRAW`, then `DUEL DRAW` on the result card with neutral accent, no
   confetti/red vignette, both portraits at full alpha and the draw quote.
   `-DADuelScreenshot` covers the win path (`DADuelResult.png`); a draw capture
   needs a draw-specific harness/debug finish.
2. **Final-beat skip**: use `-DADuelScreenshot`/`DebugFinishDuelWin`, then
   press Space or right-click while the last damage/win cut-in is visible.
   Expect the result within the skip window and no skip hint after the
   presentation ends. Clicking the cut-in should do the same.
3. **Modal policy**: open the map, PDA, dialogue and each gameplay screen, then
   call `OpenDuelDeckSelect` from a debug/Blueprint path. Expect the old
   overlay to close and the deck picker to be the only visible modal. Calling
   it while the title is open must still be refused.
4. **Help over map**: open the map, press F1; the help panel must be visible
   above it and close with F1.
5. **Dialogue overflow**: use a choice line with more options than fit (or
   temporarily add options) at 720p and 1080p. The panel must stay on screen,
   arrows must reveal hidden rows, and completed long text must show `...`.
6. **Title save list**: seed seven or more save slots and open Continue.
   Cards must stay above the back button, the selection must scroll into view,
   and `^`/`v` must appear only when rows are hidden.
7. **Long labels**: long deck names, fusion recipe names, shop pack names and
   exam answers must end in `...` instead of crossing panel edges.

## Remaining risks / follow-ups

- **No build run**: the split and all edits are structurally checked but not
  compiled here. The parent session owns the combined editor build.
- **Dialogue windowing**: hidden choices are reachable by Up/Down and Enter,
  but not by mouse until they scroll into the window. Mouse-wheel paging or
  clickable `^`/`v` hotspots would be a small future improvement.
- **Help over map**: help is now visible, but map keys remain live underneath
  it. Making help own Escape while the map is open would need a separate input
  policy decision.
- **Engine draw contract**: `bDraw` is currently set only when both LP reach 0
  together. If future rules end a duel in a draw for another reason (turn
  limit, mutual effect), the engine must set `ResultStats.bDraw` before
  `HasWinner()`; the UI now trusts that field for presentation/notification.
- **Modal close side effects**: closing a shop/confirm or dialogue from a
  non-story caller can discard transient UI state. This matches the existing
  shop/deck/exam policy; the story path was verified to have no open dialogue
  when its duel command runs.
- **Duplication inventory from pass 1** remains (Canvas primitive copies,
  hit-target structs, modal open/close sequences). This pass did not force
  those migrations because the scale/layout policies still differ.
