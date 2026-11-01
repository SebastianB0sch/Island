# Pass 4 — WS-04 UI & pawn input report

Workstream: UI & pawn input (`DAHUD`, `DAStudentCharacter`, `DADialogueUI`,
`DATitleScreen`, `DATitleSystem`, `DAPDAUI`, `DADeckUI`, `DADuelUI`,
`DAShopUI`, `DAExamUI`, `DAUIScreen`, `DAAvatarComponent`,
`DAAvatarAnimInstance`, `DAA02GateTests.cpp`).
Branch `refactor/code-review-pass`, baseline checkpoint `77cc9c7`.

## Scope & constraints

- Static-only verification: no Unreal process was run (per brief). All
  line numbers below were re-verified against the current tree before
  editing; findings were followed by symbol, not by stale offset.
- Both pinned contracts are declared **and** implemented on the WS-04 side.
- Files read but not edited because they belong to other workstreams:
  `DAStorySubsystem.*` (WS-02, contract-#1 consumer side), `DAInteriorPortal.*`
  (WS-05, contract-#2 consumer side), `DAInteractable.cpp`,
  `DAStudentNPC.cpp`, `DADuelEngine.h` (types).
- `DATitleScreen.*`, `DATitleSystem.*`, `DAUIScreen.*` had no accepted
  findings in my list and were left untouched (only read).
- No git commands were run (parent instruction, stricter than the brief);
  instead a trailing-whitespace/brace-balance scan was run locally over every
  touched file — clean (`git diff --check` will be run by the parent).
- C++ could not be compiled. Brace/paren balance was verified with a
  comment/string-stripping scanner; every new public symbol was grep-matched
  to its definition and every removed symbol was grep-checked for orphaned
  callers first.

## Findings table

| Id | Sev | Location (as reported → re-verified) | Status | Notes |
|----|-----|----------------------------------------|--------|-------|
| Contract #1 | pinned | `DADuelUI.h/.cpp` | **fixed** | `WasDeckSelectClosedWithoutResult()` declared public with the pinned comment; tracked via a story-ownership marker captured at `OpenDeckSelect` and folded in `CloseDuel`; never misfires on a recorded result |
| Contract #2 | pinned | `DAStudentCharacter.h/.cpp` | **fixed** | `NotifyTeleportArrived()` implemented (focus clear + focus-poll timer reset only, no mode/movement changes) |
| U1 | MED | `DAStudentCharacter.cpp` handlers (~:328-560 in current tree) | **fixed** | `IsWorldInputAllowed()` = exact HUD modal set (duel/map/dialogue/PDA/title/gameplay screens/help); routed through F/J/T/N/[/]/E interact handlers; movement/camera keep `IsMovementBlocked()` |
| U2 | MED | `DAHUD.cpp` P/B poll (now :1418-1419) + help-Escape block (:1395-1411) | **fixed** | Poll excludes `!bMapOpen && !bHelpOpen`; help owns Escape and closes a pinned passive PDA first (owner decision documented in code) |
| U4 | MED | `DADuelUI.cpp` `DrawDuelDeckSelect` (now :2718-2900), keys (now :1250-1285) | **fixed** | Dynamic single-row layout: 4 decks render (page size 4, hard cap 6 static-asserted); >4 paginate with PREV/NEXT/page indicator mirroring `DrawDuelChoice`; number keys 1..N driven by the visible page |
| U5 | LOW-MED | `DAExamUI.cpp` written panel (now :895-945) | **fixed** | Shared `ComputeWrittenOptionLayout` budget (`ClipY − 200S` seam above the pinned SUBMIT/ANSWERED row); keyboard/click selection uses the same budget via `GetOptionCount()` |
| U6 | LOW | `DADeckUI.cpp` collection grid (now :1096-1100) | **fixed** | `Visible = floor((H − 154S)/RowH)` reserves the ADD/SWAP button row (was 132S → last row slid under it) |
| U7 | LOW | `DADialogueUI.h/.cpp` `GoToLine` (now :170-186) | **fixed** | Sticky `bRequestedNoEscapeClose` carries `SetAllowEscapeClose(false)` across lines; text-entry lines still force escape-close off for their duration |
| U8 | LOW | `DAShopUI.cpp` browse input (now :366-377), `DADeckUI.cpp` list + recipes input (now :697-714, :664-672) | **fixed** | `MouseScrollUp/Down` routed into `MoveSelection` / `RecipeScroll` exactly like the PDA pattern; the shop's `^/v` glyphs become live indicators |
| U9 | LOW | `DAPDAUI.cpp` `Open` same-tab early-out (now :256-280) | **fixed** | Same-tab reopen refreshes the view model + rows and resets selection/scroll to match a fresh open (stale-mail fix) |
| U10 | INFO | `DAStudentCharacter.h/.cpp` deleted `OnMenuUp/Down/Select/OnClick` | **fixed** | Handlers + their dead Enhanced Input actions removed; cross-reference comment points at the map polling owner (`ADAHUD.cpp:1449`) to stop re-binding |
| U11 | LOW | `DAExamUI.cpp` live timed-duel input (now :642-653) | **fixed** | FDAExamUI no longer polls Escape/P/Pad-B while the scenario board is live; the board owns those keys (decision documented; abandon = Timed panel skip or puzzle timeout) |
| W5 | MED | `DAStudentCharacter.cpp` `PawnClientRestart` (now :86-100) | **fixed** | `bDuelPose`/`bManualDuelPose` reset with the existing sprint/focus resets |
| W11 | INFO | `DAAvatarAnimInstance.h` fields, `.cpp` `SetLocomotion`; `DAAvatarComponent.cpp` feed | **fixed** | Never-read `VerticalSpeed`/`bInAir` fields removed and `SetLocomotion` shrank to `(speed, swim, duel)`; component's own air/jump/land selection logic (live) untouched; W4/W10 not attempted (deferred per brief) |
| W4 / W10 | INFO | avatar crossfade pop / pose pooling | **deferred** | Per the brief's deferred list (needs renderer/animator validation the parent cannot do) |

Nothing was refuted; nothing from my list was left unattempted except the two
brief-mandated deferrals.

## Changes & rationale

### Pinned contract #1 — `FDADuelUI::WasDeckSelectClosedWithoutResult()`

- Declared in `DADuelUI.h` with the pinned comment verbatim; implemented in
  `DADuelUI.cpp` as a getter over new private state.
- State machine (chosen carefully never to misfire on normal completion):
  - `bDuelOpenedForStory` is captured **once at `OpenDeckSelect`**: true iff
    `UDAStorySubsystem::Get(OwnerHUD)->HasPendingDuel()` *and* no result is
    already pending for this session. The second condition matters: the
    rematch picker grown from a story result screen (`Result` → Enter →
    `OpenDeckSelect`) runs while the story command is still waiting, but that
    session's result was already recorded (`bStoryResultPending` was still
    true at open), so backing out of it must not re-open the story duel — the
    pre-open snapshot guards that.
  - `NotifyDuelFinished` (a result was recorded → profile/story hooks ran)
    clears the flag immediately.
  - `CloseDuel` folds the outcome in **before** tearing the mode down, using a
    pure static decision `ComputeStoryDuelClosedWithoutResult(owned, recorded,
    wasOpen)`; the flag is only touched when the board was actually open, so
    an idle second `CloseDuel` cannot clobber a flag the story has not read
    yet. It also covers Escape-on-the-live-board of a story duel (no result
    recorded → story sees "re-present", not a phantom loss).
  - `OpenDeckSelect` clears the flag first: a fresh picker supersedes the
    "most recently opened" semantics.
- The comment in the pinned contract names the deck-select case; the
  implementation is worded in the header so the mid-board no-result close is
  count-inclusive (same investor: story must not infer a loss).

### Pinned contract #2 — `ADAStudentCharacter::NotifyTeleportArrived()`

- Implemented exactly as scoped: `FocusedInteractable.Reset()` +
  `FocusTimer = 0.f` (so the next tick's focus poll re-acquires from the
  arrival point instead of at a stale cadence). No teleporting, no movement
  or input-mode changes — WS-05 can call it inside `ApplyArrival` blindly.

### U1 / U10 / W5 — pawn input

- New private instance gate `IsWorldInputAllowed()` delegating to the new
  public pure static `WorldInputAllowedFor(duel, map, dialogue, pda, title,
  gameplayUI, help)`. It mirrors ADAHUD's modal-ownership set exactly — the
  brief's recommended `(!IsMovementBlocked() && !IsHelpOpen())` is equivalent
  except for the missing-HUD case (kept playable, matching
  `IsMovementBlocked`'s null-HUD behaviour).
- Routed through the gate: `OnInteract`, `OnJacket`, `OnDuelDisk`,
  `OnTimePause`, `OnTimeFaster`, `OnTimeSlower`, `OnTimeSkip` (the F/J/T/N/[/]
  and interact leaks from the finding).
- Two handlers deliberately deviate, documented at the code:
  - `OnMap` mirrors `HUD::ToggleMap`'s own refusal list (duel/help/dialogue/
    PDA/title/gameplay screens) so M/Tab keeps toggling the map **closed**
    while the map is open — routing it through the raw gate would have frozen
    the map open.
  - `OnHelp` keeps `IsMovementBlocked()`: the gate would have blocked
    closing help with F1/H (HUD's help-Escape only handles Escape/Pad-B),
    regressing the overlay's own dismissal.
- `OnZoom`, `OnLook`, `OnLookStick`, `OnJump` etc. keep `IsMovementBlocked()`
  (movement/camera per the brief).
- U10: `OnMenuUp/OnMenuDown/OnMenuSelect/OnClick` implementations and
  declarations deleted (previously never bound — the HUD already owns map nav
  polling, see `ADAHUD.cpp:1449`); the orphaned `MenuUp/MenuDown/MenuSelect/
  Click` Enhanced Input actions and their key mappings were removed from
  `CreateInput` too, with a comment warning against re-binding. HUD helpers
  (`MoveMapSelection`, `GetSelectedZone`, `PickZoneUnderCursor`) remain used
  by the HUD itself, so no dead HUD API results.
- W5: `PawnClientRestart` now also clears `bDuelPose`/`bManualDuelPose`.
- Removed the now-unused private `ADAStudentCharacter::IsDuelOpen()` (its
  last callers were the deleted/re-gated handlers; grep-verified no external
  consumer).

### U2 — HUD P/B poll and help pinning

- P (`Gamepad_Special_Left`) / B poll now requires `!bMapOpen && !bHelpOpen`,
  so neither the map nor help can spawn a hidden PDA/shop underneath.
- Help-Escape ownership (documented in `DAHUD::Tick`): help stays the owner;
  if a passive PDA is somehow pinned beneath it, that PDA is a hidden, never-
  inputted layer, so the same Escape closes the PDA first and then help.
  Dialogue/duel/title/gameplay screens still suppress the branch entirely.
  Note the PDA's own `Update` runs *before* this block in the same frame, so
  no Escape double-consume is introduced.

### U4 — starter deck picker

- `DrawDuelDeckSelect` now renders up to `DeckSelectPageSize = 4` panels in a
  single row: 1–3 decks keep the shipped pixel-exact geometry (460-wide
  panels, 40-gap stride); a 4-wide row shrinks panels to
  `(1600 − 140 − 3·20)/4 = 350` board units (gap 20). Inner content scales:
  the 4 card scans shrink with the panel (art slot ≤ 98), and KEY CARDS
  trailing trim length derives from panel width. All geometry is on the
  1600×900 board and mapped through `DX/DY/DS`, so it letterboxes safely at
  any resolution (HD/HD2 included).
- More than 4 decks paginate: `< PREV` / `NEXT >` buttons + "PAGE x / y" in
  the footer mirroring `DrawDuelChoice` (hit actions `deckprev`/`decknext`,
  handled in `HandleDuelHit`); the page clamps in both the key path and the
  draw path.
- Number keys `1..N` are driven by the visible page's deck count via a
  6-slot key table; the layout constant is static-asserted `<= 6` (the
  documented hard cap for any future page-size raise) in `DADuelUI.cpp`.
- Header/subtitle hint text now derive from the data (`…Choose one of 4
  starter decks.` / `press 1-4`), replacing the hardcoded "one of three".
- `DeckSelectPage` resets on `OpenDeckSelect`, as `DuelChoicePage` already
  did.

### U5 / U6 / U7 / U8 / U9 / U11 — screens

- U5: `ComputeWrittenOptionLayout()` (new private method,
  `DAExamUI.cpp:220-263`) computes `OptionsTop` from the wrapped question
  text and clamps the number of option rows to the `ClipY − 200S` seam above
  the pinned `SUBMIT ANSWER`/`ANSWERED` row (same footer-reserve convention
  the other panels use). `DrawWritten` uses it to draw, and `GetOptionCount()`
  — used by Up/Down, number keys, Enter and the `answer` hit filter — returns
  the same count, so no reachable option is invisible. Headingless canvas
  (first frame) falls back to the full list. Note this drops overflow *rows*
  rather than scrolling; with 4-option questions and the shipped text lengths
  the budget is not reached, it is a degenerate-case guard.
- U6: `DrawCollectionPanel` reserves 154S (was 132S) above the panel bottom
  for the ADD/SWAP row, so the last grid row no longer renders under it.
- U7: `SetAllowEscapeClose` is now a real method setting a sticky
  `bRequestedNoEscapeClose` member; `GoToLine` re-applies it on every non-text
  line (text-entry lines still force `bEscapeClose = false` themselves, and
  `Begin` resets the request). `DAStorySubsystem.cpp:1624` keeps working with
  an identical signature.
- U8: shop `Update` (browse panel) and deck `Update` (list focus + recipes
  overlay) gained `MouseScrollUp/Down` routing into `MoveSelection` /
  `RecipeScroll`, matching `FDAPDAUI::Update`'s non-wrapping pattern. The
  shop's `^`/`v` glyphs were already data-consistent indicators of
  `ListScroll`; with wheel input they now do what they claim.
- U9: `FDAPDAUI::Open` on an already-open, same-tab reopen now resets
  selection/scroll/hover/hit state and calls `RefreshViewModel()` +
  `RefreshRows()` — previously `SetTab` early-returned on the unchanged tab
  and the stale view model (mail) stayed up.
- U11: `FDAExamUI::Update` while `bTimedDuelActive` now only calls
  `PollTimedDuel()`. The exam-side Escape/P/Pad-B poll was removed: those
  presses were consumed by both the exam (→ `CancelTimedDuel` → puzzle
  failed) and the board (→ choice cancel / pile close / result continue) in
  the same frame. Ownership documented in code. Consequence (intentional,
  matches the finding's direction): a live puzzle can no longer be abandoned
  by keyboard; it ends via the board's own flow (solve / turn-or-time
  timeout → result screen) and the Timed panel still offers
  "CONTINUE WITHOUT CLEARING" for a skip, and `FDAExamUI::Close()` still
  cancels via `CancelTimedDuel` for non-keyboard closes. The
  `-DAExamTimedDuelTest` harness path is unaffected (its terminal result is
  consumed by `PollTimedDuel` without key input).

### W11 — avatar dead fields

- `UDAAvatarAnimInstance`: private fields `VerticalSpeed`/`bInAir` deleted;
  `SetLocomotion` shrunk to `(InGroundSpeed, InSwimAlpha, InDuelAlpha)` —
  documented in the header; `NativeInitializeAnimation` reset updated.
  Only the swam/duel/speed fields remain live (per the "do not remove live
  fields" constraint).
- `UDAAvatarComponent`: the `SetLocomotion` feed drops `bInAir/VerticalSpeed`.
  The component's own air state, Fall/Jump choice, landing-take heuristic and
  `LastAirVerticalSpeed`/`bWasInAir` are all *read* by the live action
  selection and single-node playback, so they stay. Grep-verified
  `SetLocomotion` has exactly one caller.

## API impact (new / changed public symbols — integration notes)

| Symbol | Kind | Who may call it |
|---|---|---|
| `FDADuelUI::WasDeckSelectClosedWithoutResult() const` | new public getter | **WS-02 only** (story consumer), through the new `ADAHUD::GetDuelUI()`. No other caller may use it. |
| `ADAStudentCharacter::NotifyTeleportArrived()` | new public UFUNCTION | **WS-05 only** (from `DAInteriorPortal::ApplyArrival`). |
| `ADAHUD::GetDuelUI()` | new public accessor (dense in `DAHUD.h`) | WS-02, only to reach contract #1. Everything else should keep using the HUD-level duel API. |
| `ADAHUD::IsHelpOpen()` | new public accessor | Any reader (used by WS-04 paw + gate test). |
| `ADAStudentCharacter::WorldInputAllowedFor(...)` | new public **static** pure helper | DAA02GateTests + the pawn's own gate. Not UFUNCTION; no engine surface. |
| `FDADuelUI::DeckSelectPageSize` (constexpr 4), `DeckSelectPageCount(int32)`, `DeckSelectPageFirstDeck(int32)`, `ComputeStoryDuelClosedWithoutResult(...)` | new public statics | DAA02GateTests + FDADuelUI's own flow. |
| `FDADuelUI::DebugSetStoryOwnedDuel(bool)` | new public test-only seam | DAA02GateTests only; production flow must not call it (documented in header). |
| `UDAAvatarAnimInstance::SetLocomotion(float,float,float)` | **signature change** (was 5 params) | One caller, `UDAAvatarComponent::TickNative`, updated. Grep-verified; nothing else in the repo calls it. |
| `FDAExamUI::ComputeWrittenOptionLayout(float&,int32&)` | new private method | FDADuelUI-family internal only (not public). |
| `FDAExamUI::SetAllowEscapeClose`-style: `FDADialogueUI::SetAllowEscapeClose` | now out-of-line; signature unchanged | Same callers (story). |
| `ADAStudentCharacter::IsDuelOpen()` | **removed** private | No external caller existed (grep-verified). |
| `ADAStudentCharacter::OnMenuUp/OnMenuDown/OnMenuSelect/OnClick` | **removed** private | Never bound; grep-verified. |

Tests: `DAA02GateTests` gained suite `-DAPawnUIGateTest` (see below), runnable
standalone or alongside `-DASaveFuzz`/`-DATwelveMonthTest`. Existing suite
bootstrap and their printed summary formats are untouched; the new suite
prints its own `=== DAPawnUIGateTest summary: … ===` line.

## Remaining risks

- **No compile / no UHT verification** (process-level constraint): the run
  surface added one UFUNCTION (`NotifyTeleportArrived`); if cross-workstream
  discovery had pinned a *different* declaration shape, the build would flag
  it immediately — the pinned text is reproduced verbatim in both headers.
- **Behaviour notes worth eyeballing in-editor**: (a) exam live-puzzles no
  longer accept Esc/P/Pad-B as an explicit abandon (U11 direction; the skip
  path on the Timed panel and the timeout path remain); (b) the 3-deck
  starter picker is pixel-identical, but the 4-deck row changes panel width
  and card-art size (U4 pre-release requirement); (c) help over a pinned PDA
  now closes both on one Escape (U2's owner decision).
- The two avatar deferrals (W4 crossfade pop, W10 pose pooling) remain
  untouched as mandated.

## Verification (static only — no engine runs claimed)

- All edits made in the owned files only; seven sibling workstreams' files
  were read but never written.
- Brace/paren balance re-verified per touched file with a comment-and-string
  stripping scanner (all deltas 0).
- Trailing-whitespace scan over each touched file: 0 matches.
- Symbol greps: every new/renamed/removed symbol cross-checked both ways
  (definitions vs call sites), including the consumers WS-05 named
  (`NotifyTeleportArrived`) and WS-02 will consume
  (`WasDeckSelectClosedWithoutResult` via `GetDuelUI`).
- Layout math for U4/U5/U6 was recomputed by hand against the board/panel
  constants (1600×900 board; deck-select row panels at 70/440/810/1180 with
  width 350 for a 4-wide row; exam seam 200S; deck editor 154S), not just
  moved.
- Nothing was compiled: the generated/UHT side remains unverified until the
  parent's build. The UCLASS-facing surface changes are limited to
  `NotifyTeleportArrived` (UFUNCTION added) and `IsHelpOpen`/`GetDuelUI`
  (plain accessors), so UHT risk is minimal but nonzero.

## Tests added (DAA02GateTests.cpp, suite `-DAPawnUIGateTest`)

1. **Input-gating truth table** — all 128 modal combinations fed to
   `ADAStudentCharacter::WorldInputAllowedFor` and cross-checked against the
   HUD modal-ownership policy expression written independently in the test,
   plus nine named spot checks for the exact leaks from the findings (duel,
   map, help, map-under-help, PDA-under-map, gameplay screens, dialogue,
   title, empty).
2. **Contract #1** — pure `ComputeStoryDuelClosedWithoutResult` truth table
   (8 masks), plus the headless state machine on an owner-less `FDADuelUI`:
   construct closed → open picker → seed story ownership via the documented
   test-only seam → close → flag true → repeated close must not clobber →
   fresh open clears → non-story close stays clear → a seeded marker is
   superseded by the fresh open's capture.
3. **U4 pagination bounds** — `DeckSelectPageCount`/`PageFirstDeck` for 1..6
   fake decks (page count, per-page first index and page width bounds),
   negative-page clamp, zero-deck page count, page size = 4 and `<= 6`.

Nightly-relevant existing suites (`-DASaveFuzz`, `-DATwelveMonthTest`) were
not restructured; their printed formats are unchanged.

## Test gaps (headless limits)

- **HUD-flag-driven instance gate**: `IsWorldInputAllowed()`'s instance path
  (reaching a live `ADAHUD`) needs a world; only its pure predicate is
  testable headless. The predicate is the whole decision, so the truth table
  is still concrete — but a pet integration run should confirm F/J/T/N/[/]
  are dead under both map and help in-editor.
- **"Recorded result clears the flag" end-to-end** (`NotifyDuelFinished`
  clearing `bDeckSelectClosedWithoutResult` in a real duel) needs a card
  database + engine; covered headlessly only via the pure bitmask. The
  `-DAExamTimedDuelTest` harness can be extended to open a story picker
  first if extra coverage is wanted (WS-02 side).
- **Escape double-consume during an exam scenario duel** (U11) is
  input-timing behaviour; static reasoning + the existing
  `-DAExamTimedDuelTest` pass path (which needs no key input) is the
  available coverage. In-editor regression: Cancel choice ≠ exam failure any
  longer.
- Same for U2 (map+P, help+P), U9 (reopen PDA with fresh mail), U7
  (`SetAllowEscapeClose` across an advance) — all key-press flows on live
  canvases; logic kept as simple as possible and the pure bits were pinned.
- **U4's drawn layout** (panel width at 4 decks, page buttons) is renderer
  work; only the paging bounds are headless-testable. `-DADuelScreenshot`,
  `-DAGameplayUITest` and `-DAUITest` cover the visual regression when the
  parent runs them.

## Integration hand-offs

1. **WS-02 (story)**: consume contract #1 through
   `ADAHUD::GetDuelUI()->WasDeckSelectClosedWithoutResult()`; the
   re-present/read window is stable until the *next* open, recorded result or
   story-owned close with a result (see the `CloseDuel` guard against idle
   second closes). No story-side edit was made; the dropped story result on
   Result-screen confirm → rematch-picker back-out still resolves through the
   profile counter inference as before (pre-existing behaviour, unchanged).
2. **WS-05 (portals)**: call `ADAStudentCharacter::NotifyTeleportArrived()`
   inside `DAInteriorPortal::ApplyArrival` after the actor is placed; it is
   strictly focus-clearing.
3. **WS-01 (duel engine)**: none required; `SetLocomotion`'s signature change
   has exactly one caller (this workstream).
4. **Parent**: run `-DAPawnUIGateTest` (with/without the existing suites) in
   the integration gate; `git diff --check` over the WS-04 file set
   (whitespace scan already clean locally).
