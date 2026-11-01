# 04 — UI interaction, modal input and label/state robustness (pass 3)

Branch: `refactor/code-review-pass`

## Scope and constraints

Scope: `DADialogueUI.*`, `DATitleScreen.*`, `DAPDAUI.*`, `DADeckUI.*`,
`DAShopUI.*`, `DAUIScreen.*`, and this report. `DADuelUI`, `DAHUD`,
`DAExamUI`, `DAExamSubsystem` and `DAPuzzleRuntime` were read but not edited
(workstream 03 owns them). No game data, manifests, saves, story, duel or
effect files were changed. The uncommitted pass-1/pass-2 tree is the baseline;
this pass only adds the interaction and presentation changes below.

No UnrealBuildTool, UnrealEditor, Blender or Unreal process was run. Nothing
was staged or committed.

## Findings

| ID | Severity | Location (current tree) | Finding | Status |
|---|---|---|---|---|
| P3-UI-01 | Medium | `DADialogueUI.cpp` update/draw choice block | Pass 2 windowed hidden choices but only keyboard/Enter could reach them; no wheel, and the `^`/`v` marks were decorative. | Fixed: mouse wheel scrolls the selection; `^`/`v` are registered hit targets (`choice.up` / `choice.down`) and move the selection by one without wrapping. Number keys, Enter, Up/Down and typewriter completion are unchanged. |
| P3-UI-02 | Medium | `DADialogueUI.cpp:147`, `:233` | A `bChoice` line with an empty `Options` array was treated as waiting for a choice, but `Choose()` always failed; Enter/click could not advance, leaving a soft-lock. | Fixed: `IsWaitingForChoice()` requires at least one option and `Advance()` only blocks on a non-empty choice. |
| P3-UI-03 | Medium | `DAHUD.cpp` `Tick` help/map input (out of scope) | Help draws over the map but the map block still handles Up/Down/Enter/Escape/click, so a player can fast-travel or close the map under the help panel. The map toggle (`M`/Tab) also still acts while help is open. | Documented: exact required HUD change in “Cross-workstream follow-ups”. Not edited because HUD is owned by workstream 03. |
| P3-UI-04 | Medium | `DAPDAUI.cpp:326` (`SetTab`) | Hit targets from the previous tab survived the tab switch until the next Draw; a click in the same frame could activate a row of the new tab by old coordinates. | Fixed: `SetTab`, `Open`, `Close` and `RefreshViewModel` clear hit targets; `RefreshViewModel` also re-clamps the row selection. |
| P3-UI-05 | Low | `DATitleScreen.cpp:484`, `:800`, `:1160` | Pass 2 made the save list scrollable but only with Up/Down; `^`/`v` were not clickable and wheel did nothing. | Fixed: Continue wheel scroll (clamped at both ends) and clickable `continue.scroll` hit targets. Credits also scroll with the wheel. |
| P3-UI-06 | Low | `DAPDAUI.cpp:1833-1876` | On the Deck tab the detail body was capped at `H - 34S`, underneath the `EDIT` button (`H - 44S..H - 14S`) and the footer hint. Long deck descriptions/validation lines overlapped the action row. | Fixed: the body cap reserves the EDIT row (`H - 58S`); the hint width also reserves the button column. |
| P3-UI-07 | Low | `DAPDAUI.cpp` list/detail/header | PDA row titles/subtitles, detail titles, tab labels, empty-state note and footer hints could still run past their panels. | Fixed with the shared measured ellipsis and wrapped empty state; fallbacks for missing deck/mail/save/option/record/limit names. |
| P3-UI-08 | Low | `DADeckUI.cpp` | No empty state for zero player decks or an empty/filtered collection; header deck name, validation message, active id, status/swap lines and the filter/sort line could overflow. Save/rename/erase/recipes transitions also left stale hit targets. | Fixed: subsystem/no-deck/empty-trunk messages; measured clipping; hit targets cleared on list refreshes and submodal transitions. |
| P3-UI-09 | Low | `DAShopUI.cpp` | Category tabs/count/status/detail lines were untruncated; a zero-card reveal still drew the normal header and could calculate a zero/negative card width; transition to Confirm left the browse hits live for the same frame. | Fixed: measured clipping, `DrawRevealCard` non-positive-size guard, explicit “No cards were added” state, hit-target resets on catalogue/category/confirm changes. |
| P3-UI-10 | Low | `DADialogueUI.cpp` draw helpers | Speaker name/title, hint, action buttons, choice labels and portrait expression tags could overflow the panel/portrait. | Fixed with the shared measured ellipsis; history title clipped; history entries already wrapped. |
| P3-UI-11 | Low | `DAPDAUI.cpp:452`, footer composition | A live `UDACalendarSubsystem` was still marked `bPlaceholder` whenever the profile was not initialized, so a live month was labelled “Sample month”. The footer also claimed deck/save/mail were live whenever the profile was live, even if a subsystem was missing. | Fixed: calendar placeholder flag is false when the calendar subsystem exists; footer is composed from the subsystems actually present. Mail/deck/save empty states now distinguish “no data yet” from “subsystem unavailable”. |
| P3-UI-12 | Info | UI harness | There is no renderer-free UI test harness in this repository. Existing automation tests cover duel/exam/puzzle/profile/story, not Canvas screens. | Documented visual checks below; source-level assertions were run one-off and recorded, but no fake test file was added. |

## Changes made

### `DAUIScreen.h/.cpp` (shared helper)

- Added `DAUIText::EllipsizeMeasured(Str, MaxWidth, MeasureWidth)`, a
  source-level template that implements one truncation contract for all Canvas
  screens. It keeps the existing “shorten by four characters and append `...`”
  behavior, ignores non-finite widths, and is now used by
  `FDAUIScreen::Ellipsize`.
- `DADialogueUI`, `DATitleScreen` and `DAPDAUI` (which do not derive from
  `FDAUIScreen`) each gained a private `Ellipsize` wrapper that delegates to the
  same helper and their own `Measure`. This removes the three copied status
  ellipsis loops in `DADeckUI`/`DAShopUI`/`DATitleScreen` in favor of the common
  rule.

### `DADialogueUI`

- Added `MoveChoiceSelection(Delta, bWrap)`. Keyboard Up/Down keep their
  existing wrapping behavior; wheel/arrow clicks clamp so a single notch cannot
  jump from the first option to the last.
- Added `EKeys::MouseScrollUp`/`MouseScrollDown` handling for the choice window
  and for the history overlay (history Up = older, Down = newer, matching the
  existing keys).
- The `^`/`v` marks are now drawn as small hover-aware buttons and registered
  as `choice.up`/`choice.down` hit targets after the option rows, so they win
  the hit test in their corner region. `HandleHit` only moves the choice while
  the line is actually accepting input.
- Choice labels, speaker name/title, hint, action buttons, portrait expression
  and history title use measured clipping. The completed-text `...` condition
  remains `Wrapped.Num() > MaxTextLines` (pass 2 behavior).
- State/hit resets: `Begin` resets history scroll, `GoToLine` clears hit targets,
  `Close` clears transient timers/window state, and `ToggleHistory` clears the
  underlying hits when the overlay opens. `HandleClickAtMouse` refuses the
  advance fallback while history is open, so a same-frame click cannot advance
  the dialogue before the overlay's full-screen close target is registered.
- Empty-option choice lines are no longer soft-locks (P3-UI-02).

### `DATitleScreen`

- Added `MoveContinueSelection(Delta)` (clamped) and wheel handling on the
  Continue panel. The `^`/`v` marks now register `continue.scroll` hits; clicks
  move the selection one slot and the existing Draw logic keeps it in view.
- Credits scroll also accepts the wheel.
- Added an explicit `Slots.IsValidIndex` guard in the Continue draw loop.
- Hit targets are cleared on `Open`, `ShowPanel`, `RefreshSlots`, `BackToMain`
  and `Close`, so panel/list changes cannot leave a stale card hit.
- Latest-save summary, menu labels, save-card labels/player name/middle/right
  lines, option labels, confirm title/buttons and footer hints use measured
  clipping. Status now uses the shared ellipsis.
- `ContinueScroll` is reset on open/close; `ShowPanel(Continue)` still resets it
  before selecting the first usable slot.

### `DAPDAUI`

- `RefreshViewModel` now clears hit targets and calls `RefreshRows` after
  normalizing, so direct refreshes from the HUD (for example after a save) also
  re-clamp selection. `Open`, `Close` and `SetTab` clear hit targets explicitly.
- PDA lists accept the wheel and clamp at the ends (`MoveSelection` already
  clamps, so `ListScroll` follows selection in Draw).
- Header title/subtitle/profile lines, tabs, list title/rows/subtitles, detail
  title/footer hint and empty text are clipped or wrapped to their panels.
- List row fallbacks for empty zone/deck/mail/save/option/record/limit fields;
  detail titles use the same fallbacks. Mail subtitles fall back to
  “Unknown sender”, and the live-mail empty note no longer says mail is waiting
  for A03.
- Empty-state text is tab-specific and wrapped: no locations, no player decks,
  no messages yet, no save slots, no limitation data. A missing save subsystem
  is stated explicitly in the save detail.
- Deck tab body now stops above the EDIT row; footer hint reserves the button
  column.
- The calendar is no longer marked as a sample month when the live calendar
  subsystem supplied the month. The footer lists only the live domains
  (profile/calendar/deck/save/mail) instead of claiming every tab.

### `DADeckUI`

- Open resets focus selections (`CollectionSelection`, `DeckCardSelection`,
  extra-deck selection, extra mode), hover and hit targets. Close clears the
  recipe/name/erase overlays and pending swap state.
- Empty states: no decks (“Press N…”, or subsystem unavailable) and empty/
  filtered collection.
- Header deck name, validation, active id, key hint, collection filter/sort
  line, add/swap button, deck-panel title, validation/swap line, name editor,
  erase confirm and footer use measured clipping.
- `RefreshDeckCards` and `RefreshCollection` clear hit targets; rename/erase/
  recipe transitions also clear them. `RefreshAll` clears recipes when the deck
  subsystem is unavailable.

### `DAShopUI`

- Open resets category/selection/scroll and hit targets; Close resets the panel
  and confirm selection.
- `RefreshCatalogue`, `ChangeCategory` and `OpenConfirm` clear hit targets so a
  category/panel change cannot be followed by a stale browse click.
- Category tabs, category line, pack names/status, detail category/status/
  restock lines, row status, confirm text and footer are measured-clipped.
- `DrawRevealCard` returns for non-positive sizes; `DrawReveal` shows an
  explicit no-cards message for a zero-card result and skips the card layout
  when it cannot allocate positive card sizes.
- The empty detail panel distinguishes “no packs in this category” from a
  missing shop subsystem.

### `DAUIScreen`

- `Ellipsize` now delegates to `DAUIText::EllipsizeMeasured`; no public class
  API change. The helper is header-only and additive.

## Input-ownership policy

The policy implemented/verified for the screens in this workstream:

1. **One modal layer consumes input at a time.** The HUD already ticks exactly
   one of shop/deck/exam/dialogue/PDA and returns early for the title; map keys
   exclude those layers, and the title is drawn/ticked before everything else.
2. **Within a screen, the topmost submodal owns Escape and click input.**
   - Dialogue history: Escape/H/close owns; underlying choices are not live.
   - Deck recipes/name editor/erase confirm: each consumes Escape/Enter and
     drops the underlying hit targets.
   - Shop reveal/confirm: each consumes Escape/Enter and drops browse hits.
   - Title panels: `ShowPanel` drops all prior panel hits.
   - PDA: no submodal; a tab switch drops prior tab/row hits.
3. **Opening/closing/tab-switching clears transient selection, scroll and
   mouse state** in the owned screens. Clicks that arrive in the same frame as
   a layout change cannot target a row that was not drawn in that layout.
4. **Help is the exception, and needs a HUD change.** Help currently draws over
   the map while map input remains live. The exact required change is below.

## Verification

Commands were run from `C:\dev\GX`. No Unreal process was run.

1. Whitespace check over every changed source/report file:

   ```powershell
   git diff --check -- <all 12 owned .cpp/.h files>
   ```

   Result: exit 0. Git printed only the existing LF/CRLF advisory for these
   files, no whitespace errors.

2. String/comment-aware brace and parenthesis balance check over all 12 changed
   C++ files (one-off script in the session temp directory, not added to the
   repository):

   ```powershell
   python C:\Users\Sebas\AppData\Local\Temp\opencode\gx_brace_check.py
   ```

   Result: 12/12 files `braces/parens balanced`, exit 0.

3. One-off source assertions over the changed files:

   ```powershell
   python C:\Users\Sebas\AppData\Local\Temp\opencode\gx_ui_source_checks.py
   ```

   Result: `22/22 source assertions passed`, exit 0. They checked wheel/arrow
   handlers, empty-choice guards, hit resets on line/tab/panel/list changes,
   empty-state messages, live-calendar/footer honesty, the EDIT-row reserve and
   the shared ellipsis helper.

4. Geometry math was checked by hand for 720p (1280×720, `UIScale = 2/3`) and
   1080p (1920×1080, `UIScale = 1`):
   - Dialogue: panel width `min(CW - 120S, 1180S)` = 786.7 px / 1180 px,
     clamped top at 58.4 px / 87.6 px and bottom at 689.3 px / 1034 px. The
     overflow window shows 15 rows at both resolutions; arrows remain inside
     the panel and the panel is not wider/taller than the viewport.
   - Title Continue: with seven save slots, both resolutions choose a scrolling
     window of six cards (92 px minimum card height at 1080p; scaled minimum at
     720p), leaving the back button clear and placing the arrows in the reserved
     header/footer gaps.
   - PDA: at both resolutions the list/detail split is positive; the detail body
     reserve for the Deck EDIT row leaves no overlap with body text or hint.
5. No `UnrealBuildTool`, `UnrealEditor`, Blender, automation run or screenshot
   capture was performed. No Python/game-data validators were affected because
   no data files changed.

### Visual checks still requiring a renderer

1. **Dialogue overflow at 720p and 1080p.** Start a choice line with at least
   17 options (or temporarily add options in a debug payload). Confirm the
   panel stays on screen, the selected row scrolls into view, wheel and the
   `^`/`v` buttons both move the hidden window, number keys 1–9 still choose the
   visible numbered index, Enter chooses the highlighted row, Up/Down wrap as
   before, typewriter completion still works and H history still opens/closes
   with wheel scrolling.
2. **Dialogue empty choice.** Feed a `bChoice` line with no options. Enter/click
   should advance or close rather than soft-lock, and no phantom choice panel
   should appear.
3. **Title save list.** Seed seven or more saves, open Continue at 720p and
   1080p. Wheel and the `^`/`v` buttons must move the selection, cards must stay
   above the back button, and a click must never activate a card that is no
   longer in the visible window.
4. **PDA tab/list state.** Open the PDA, hover/click a row, switch tabs with the
   number keys/Q/E in the same frame as a click, and confirm no row from the old
   tab activates. On Save with many slots, wheel scrolls and the selection stays
   visible. On Deck, long details stop above the EDIT button and hint line.
5. **PDA live/placeholder copy.** With A02 initialized, the calendar must not
   say “Sample month”; the footer should list only live domains. With A03
   initialized and an empty mailbox, the empty state should say “No messages
   yet”, not that A03 is still unconnected.
6. **Deck/shop empty and long-data states.** Empty trunk, zero player decks,
   filtered collection with no matches, an empty shop category, a zero-card
   reveal and long pack/card/status names. No label should cross a panel edge;
   the zero-card reveal should show the explicit message.
7. **Help over map (expected to fail until the HUD patch is integrated).** Open
   the map, press F1, then press Enter, click a map zone and press M/Tab. None
   should travel/close the map while help is visible. Escape should close help
   first; a second Escape should close the map. F1 should still toggle help.
8. **Wheel side effects.** While dialogue/PDA is open in GameAndUI mode, check
   whether the mouse wheel also zooms the pawn camera through the existing
   `MouseWheelAxis` action. The UI scrolling itself is independent, but camera
   zoom during a modal would be undesirable; if observed, the pawn/HUD input
   mode needs a follow-up (outside this workstream).

## Remaining risks and cross-workstream follow-ups

### Required `ADAHUD` change (workstream 03; do not apply here)

Help currently draws above the map but the map input block remains live. The
required policy is: while help is open, help owns Escape/close and map hotkeys
are suspended.

1. In `ADAHUD::Tick`, after the title early-return and before the modal updates,
   consume Escape/Gamepad Back while help is the top layer:

   ```cpp
   if (bHelpOpen && !IsDuelOpen() && !IsPDAOpen() && !IsDialogueOpen()
       && !IsTitleOpen() && !IsGameplayUIOpen())
   {
       if (APlayerController* PC = GetOwningPlayerController())
       {
           if (PC->WasInputKeyJustPressed(EKeys::Escape)
               || PC->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
           {
               bHelpOpen = false;
               return;
           }
       }
   }
   ```

2. Gate the map key block on help:

   ```cpp
   if (bMapOpen && !bHelpOpen && !IsDuelOpen() && !IsPDAOpen()
       && !IsDialogueOpen() && !IsGameplayUIOpen())
   ```

   This covers Up/Down, Enter/Space, Escape, left-click and `TravelToZone()`.

3. Stop the map toggle from acting under help. Add `bHelpOpen` to the refusal
   condition in `ADAHUD::ToggleMap()`:

   ```cpp
   if (bHelpOpen || IsDuelOpen() || IsDialogueOpen() || IsPDAOpen()
       || IsTitleOpen() || IsGameplayUIOpen())
   {
       return;
   }
   ```

   Internal modal openers currently call `ToggleMap()` to close the map before
   clearing help. Because `ToggleMap()` would now refuse while help is open,
   move `bHelpOpen = false;` **before** the `if (bMapOpen) ToggleMap();` call in:
   `OpenDuelDeckSelect`, `BeginDialogue`, `OpenPDA`, `OpenTitle`, `OpenShop`,
   `OpenDeckEditor` and `OpenExam` (current tree has the clear immediately after
   the map close in each). `TravelToZone()` remains reachable only through the
   now-gated map input.

Without step 3, the pawn's `M`/Tab action can still close the map under the
help overlay even though the HUD map keys are frozen.

### Other follow-ups / risks

- **No compile run.** All edits were structurally checked but not compiled here;
  the parent session owns the combined editor build. The shared header template
  and the lambda-based `Ellipsize` wrappers are the main new compile surface.
- **Wheel event source.** The implementation polls `EKeys::MouseScrollUp/Down`,
  matching the existing `WasInputKeyJustPressed` pattern used for map/dialogue
  keys. If the project's input stack does not synthesize those keys in
  GameAndUI mode, a future fallback would need an explicit Enhanced Input
  action; that would be a cross-workstream change.
- **GameAndUI camera zoom.** `DAStudentCharacter` maps `MouseWheelAxis` to
  camera zoom. The HUD polling does not consume the axis. Visual check 8 above
  decides whether the pawn needs to ignore zoom while a modal is open.
- **PDA live data builder.** `FDAPDAUI::ViewModelBuilder` is still unassigned in
  the current tree; live tabs are populated directly from A02/A03/A06
  subsystems in `BuildPlaceholderViewModel`. The Limitation tab remains
  intentionally empty until A01/A07 supplies rows. The footer and empty-state
  copy now state that honestly.
- **No automated UI harness.** Because Canvas drawing is renderer-bound, no
  fake source-text test was added. The one-off source assertions are recorded
  above for reproducibility but are not repository tests.

## Parent integration follow-up

The required HUD change was implemented in pass-3 integration: help consumes
Escape/Back, the map input block is gated on `!bHelpOpen`, `ToggleMap()` refuses
under help, and all modal openers clear help before closing the map. The
combined editor build and headless gates pass. Renderer-dependent checks
(dialogue overflow, title scrolling, wheel/pawn camera interaction) still
require a visual run.
