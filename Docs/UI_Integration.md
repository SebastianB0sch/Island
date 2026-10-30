# UI Integration — Dialogue, PDA and HUD hosting (A09, pass 1)

> Scope of this pass: the first visible UI shell for the opening vertical slice.
> Code-only Canvas, same approach as the existing HUD and duel board. No UMG,
> Blueprint or binary UI assets were added.
>
> **Owned files:** `DAHUD.*`, `DADialogueUI.*`, `DAPDAUI.*`, `Content/Data/UI/**`,
> `Docs/UI_Integration.md`. `DADuelUI.*` was **not** modified.

---

## 1. What is in this pass

| Area | Status |
| --- | --- |
| Dialogue box: speaker, portrait/expression, typewriter, continue, choices, skip/auto, history log | Implemented, Canvas |
| Portrait fallback (colored monogram + silhouette) | Implemented |
| PDA shell: Map, Calendar, Deck, Mail, Save, Options, Records, Limitation | Implemented, placeholder panes marked |
| PDA Map tab | Live: reads `UDAIslandSubsystem` zones and fast-travels |
| PDA Deck tab | Live: lists the existing starter decks from `UCardDatabaseSubsystem` |
| PDA Calendar/Records | Placeholder October + profile basics; A02 replaces via view model |
| PDA Mail/Save/Limitation | Empty placeholder panes + action hooks for A03/A02/A01/A07 |
| Options tab | Text Speed and Auto-Advance are wired to the dialogue box immediately |
| HUD hosting | Dialogue/PDA draw above the world HUD; modal checks include both |
| Debug switches | `-DADialogueTest`, `-DAPDATest`, `-DAUITest` |
| Data | `Content/Data/UI/ui.json` (labels, tabs, sample dialogue) |

Existing location banner, minimap, compass, help panel, island map/fast travel
and duel deck-select/board/result flows are unchanged and still draw exactly as
before when no new UI is open.

---

## 2. Files

**New**

- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DADialogueUI.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DADialogueUI.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAPDAUI.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAPDAUI.cpp`
- `DuelAcademyIsland/Content/Data/UI/ui.json`
- `Docs/UI_Integration.md` (this file)

**Modified (minimal)**

- `Public/DAHUD.h` — includes, modal checks, dialogue/PDA hosting API, members.
- `Private/DAHUD.cpp` — creates/ticks/draws the overlays, input mode, P polling,
  debug switches, help text.
- `Private/DAStudentCharacter.cpp` — **one line** in `IsMovementBlocked()` so
  movement/interact stop while dialogue or the PDA is open (see §8).

`DADuelUI.h/.cpp` are untouched.

---

## 3. Dialogue API (A03 contract)

`DADialogueUI.h` defines the presentation payload. A03 resolves its story
commands (`PORT_MASTERPLAN` §4.3) to this struct and calls `ADAHUD::BeginDialogue`.

```cpp
struct FDADialogueLine
{
    FString SpeakerId;       // "jaden" — portrait/trace id
    FString SpeakerName;     // display name; empty -> SpeakerId
    FString Portrait;        // optional portrait override; empty -> SpeakerId
    FString Expression;      // "neutral" | "happy" | "angry" | "shocked" | "sad" | ...
    FString Text;            // resolved display text
    bool bChoice = false;
    TArray<FString> Options; // choice labels

    // Optional integration metadata
    FString TextKey;         // localization/trace key, e.g. "E01.sheppard_01"
    FString NodeId;
    FString SpeakerTitle;    // small subtitle under the name
    float AutoAdvanceDelay = 2.2f;
    FLinearColor Accent = FLinearColor(1.f, 0.78f, 0.25f);
};
```

### HUD entry points

```cpp
// Start a conversation. ConversationId is echoed by OnDialogueClosed / OnChoiceMade.
HUD->BeginDialogue(Lines, TEXT("E01"));

// Single-line convenience (interaction bark, debug).
HUD->BeginDialogueLine(Line);

// Forward the choice to A03 / story graph.
if (FDADialogueUI* D = HUD->GetDialogueUI())
{
    D->OnChoiceMade.AddLambda([](const FString& ConversationId, int32 OptionIndex)
    {
        // A03: apply the branch for ConversationId/OptionIndex
    });
    D->OnDialogueClosed.AddLambda([](const FString& ConversationId)
    {
        // A03: continue the command queue
    });
}
```

### `FDADialogueUI` public API

| Method | Purpose |
| --- | --- |
| `Begin(Lines, ConversationId)` | Start a conversation; broadcasts `OnLineShown` for line 0. |
| `BeginLine(Line, ConversationId)` | Single-line conversation. |
| `Close()` | Close and broadcast `OnDialogueClosed`. |
| `Advance()` | Reveal the current line; next line; close at the end. Returns false on a pending choice. |
| `Choose(int32)` | Commit an option, broadcast `OnChoiceMade`, advance. |
| `SkipConversation()` | Close immediately (SKIP button). |
| `SetAutoAdvance(bool)` / `ToggleAutoAdvance()` | Auto mode. |
| `ToggleHistory()` / `ScrollHistory(int32)` | Dialogue log. |
| `SetTextSpeed(float)` | 10–200 characters/sec. |
| `SetAllowEscapeClose(bool)` | Critical scenes can require a choice / prevent Escape-close. |
| `IsOpen()` / `IsTyping()` / `IsWaitingForChoice()` | State for story logic and tests. |
| `GetHistory()` / `GetLines()` / `GetLineIndex()` | QA and save/history support. |

### Events

- `OnLineShown(const FString& ConversationId, int32 LineIndex)`
- `OnChoiceMade(const FString& ConversationId, int32 OptionIndex)`
- `OnDialogueClosed(const FString& ConversationId)`

Portraits are loaded through `UCharacterPortraitSubsystem`:

1. `GetExpression(SpeakerId, Expression)` when `Expression` is set.
2. `GetPortrait(Portrait` or `SpeakerId`, face crop)`.
3. `GetPortrait(id, full bust)`.
4. Colored monogram + bust silhouette fallback with a `NO PORTRAIT` label.

No story text is compiled into C++. Sample text is loaded from
`Content/Data/UI/ui.json` and is explicitly marked `(Placeholder.)`.

---

## 4. PDA API (A02/A03/A06/A07 contract)

`DAPDAUI.h` exposes a view model rather than reading gameplay systems directly.
The UI never implements rules or progression.

```cpp
enum class EDAPDATab : uint8
{
    Map, Calendar, Deck, Mail, Save, Options, Records, Limitation, Count
};

struct FDAPDAViewModel
{
    FDAPDAProfileView Profile;                  // A02
    FDAPDACalendarView Calendar;                // A02
    FDAPDADeckView Deck;                        // A06
    TArray<FDAPDAMailView> Mail;                // A03
    TArray<FDAPDASaveSlotView> SaveSlots;       // A02
    TArray<FDAPDAOptionRow> Options;            // A02 (UI applies two of them now)
    TArray<FDAPDARecordRow> Records;            // A02/A07
    TArray<FDAPDALimitRow> Limitations;         // A01/A07
    FString FooterNote;
};
```

### Integration pattern

Bind `ViewModelBuilder` once (for example from `ADAGameMode::BeginPlay` or an
A10 integration bootstrap). It is called on every PDA open and tab change,
after the built-in placeholder data is created — overwrite only the tabs you own.

```cpp
if (FDAPDAUI* PDA = HUD->GetPDAUI())
{
    PDA->ViewModelBuilder = [](FDAPDAUI& UI)
    {
        FDAPDAViewModel& V = UI.GetViewModel();
        // A02:
        V.Profile.PlayerName = Profile->GetName();
        V.Profile.DP = Profile->GetDP();
        V.Profile.bPlaceholder = false;
        // V.Calendar = Calendar->BuildPDAView();
        // A03:
        // V.Mail = Mailbox->BuildPDAView();
        // A06:
        // V.Deck = Inventory->BuildDeckView();
    };
}
```

Activation of rows is reported through `OnAction(FName ActionId, const FString& Payload)`:

| Action id | Payload | Emitted when | Expected owner |
| --- | --- | --- | --- |
| `map.travel` | zone display name | Map row activated | A08/HUD (already travels) |
| `calendar.select` | day number | Calendar day activated | A02 |
| `deck.open` | deck id | Deck row activated | A06 (`DADeckUI`) |
| `mail.open` | mail id | Mail row activated | A03 |
| `save.slot` | slot id (`slot_1`…`slot_3`, `autosave`) | Save row activated | A02 |
| `options.changed` | `id=value` (`text_speed=Fast`) | Options row cycled | A02 + HUD applies |
| `records.row` | record label | Records row activated | A02/A07 (optional) |
| `limitation.row` | card name | Limitation row activated | A01/A07 (optional) |

`ADAHUD::HandlePDAAction` already handles `options.changed` for the dialogue box
(text speed + auto-advance) and shows a short “hook not connected” toast for
`deck.open`, `mail.open` and `save.slot` until those screens land.

### Other public API

```cpp
HUD->OpenPDA(EDAPDATab::Map);
HUD->ClosePDA();
HUD->TogglePDA();
HUD->IsPDAOpen();

FDAPDAUI* PDA = HUD->GetPDAUI();
PDA->Open(EDAPDATab::Calendar);
PDA->SetTab(EDAPDATab::Deck);
PDA->NextTab(+1);
PDA->RefreshViewModel();       // pull fresh data after a save/purchase
PDA->GetViewModel();
PDA->GetSelection();
PDA->MoveSelection(+1);
PDA->ActivateSelection();      // keyboard/automation parity
PDA->OnTabChanged / OnAction / OnClosed
```

---

## 5. Input bindings

All UI keys are **polled** with `APlayerController::WasInputKeyJustPressed`
(the same pattern as the existing island map), so they work in `GameAndUI`
mode where Enhanced Input can swallow keys. No new Enhanced Input action was
added, and `DAStudentCharacter.*` input bindings were not changed.

### HUD / global

| Key | Action |
| --- | --- |
| `P` / gamepad View (Select) | Toggle PDA |
| `M` / `Tab` / gamepad Start | Island map (existing; blocked while PDA/dialogue/duel is open) |
| `F1` / `H` | Help (blocked while PDA/dialogue/duel is open) |

### PDA

| Key / input | Action |
| --- | --- |
| `P` / gamepad View / `Esc` / gamepad B | Close PDA |
| `Q` / `E`, `Left` / `Right`, LB/RB | Previous / next tab |
| `1`–`8` | Jump to tab |
| `Up` / `Down`, `W` / `S`, D-pad | Move row selection |
| `Enter` / `Space` / gamepad A | Activate row |
| Mouse | Click a tab, row or calendar day |
| Mouse hover | Highlights the tab/row under the cursor |

### Dialogue

| Key / input | Action |
| --- | --- |
| `E` / `Space` / `Enter` / gamepad A or B / click | Reveal, then continue |
| `Up` / `Down`, `W` / `S`, D-pad, `1`–`9` | Choice selection / number choice |
| `H` / gamepad View | Toggle dialogue log |
| `A` | Toggle auto-advance |
| Hold `Ctrl` | Skip typewriter and fast-advance |
| `Esc` | Close dialogue (unless `SetAllowEscapeClose(false)`) |
| Mouse | Click an option, or click the box to advance |

### Shared-file change (documented)

`DAStudentCharacter.cpp` is a shared file. The only change is:

```cpp
bool ADAStudentCharacter::IsMovementBlocked() const
{
    const ADAHUD* HUD = GetDAHUD();
    return HUD && (HUD->IsDuelOpen() || HUD->IsMapOpen()
        || HUD->IsDialogueOpen() || HUD->IsPDAOpen());
}
```

This blocks movement, look, jump, sprint, zoom and E-interaction while the new
modal UI is open. No movement/camera/duel logic was touched. A09 did **not**
add a P or dialogue Enhanced Input action; the HUD polls those keys itself.
`J` (jacket), `F` (duel pose) and the time keys still work behind an open
dialogue/PDA; treat that as a cosmetic known gap until A10 approves a broader
modal input block.

---

## 6. Modal precedence and input ownership

From highest to lowest:

1. **Duel** (`DADuelUI`) — draws alone and owns its input mode.
2. **Island map** — draws alone (existing behaviour).
3. **Dialogue** — draws above the PDA and consumes all UI input while open.
4. **PDA** — full-screen shell; stops updating input while dialogue is open.
5. **Help** — overlay; cannot be opened while the above are open.
6. **World HUD** — compass, minimap, banner, message, prompt.

Rules enforced by `ADAHUD`:

- `IsModalOpen()` = map || help || duel || PDA || dialogue.
- `P` / gamepad View opens the PDA only when no duel/dialogue is open; opening while the map is
  open closes the map first.
- `M` and `F1` are ignored while the PDA/dialogue is open.
- A story dialogue may open **over** the PDA (for mail/phone scenes). Closing
  the dialogue returns input to the still-open PDA.
- The PDA/dialogue use `FInputModeGameAndUI` with a visible cursor; closing the
  last one restores `FInputModeGameOnly`.
- `DADuelUI` always wins; the new UI never changes duel input mode.

---

## 7. Data: `Content/Data/UI/ui.json`

```json
{
  "version": 1,
  "labels": {
    "pda.title": "DUEL ACADEMY PDA",
    "pda.tab.map": "MAP",
    "pda.tab.calendar": "CALENDAR",
    "pda.tab.deck": "DECK",
    "pda.tab.mail": "MAIL",
    "pda.tab.save": "SAVE",
    "pda.tab.options": "OPTIONS",
    "pda.tab.records": "RECORDS",
    "pda.tab.limitation": "LIMIT",
    "pda.footer.hints": "Q / E or 1-8: tabs ...",
    "pda.footer.placeholder": "PDA shell - ... await A02/A03/A06/A07."
  },
  "dialogueSamples": {
    "opening_test": [
      {
        "speakerId": "sheppard",
        "speakerName": "Chancellor Sheppard",
        "portrait": "sheppard",
        "expression": "neutral",
        "speakerTitle": "Chancellor",
        "text": "Welcome to Duel Academy. This line is a placeholder ...",
        "textKey": "PLACEHOLDER.E01.sheppard_01",
        "nodeId": "E01.sheppard_01",
        "autoAdvanceDelay": 3.0
      },
      {
        "speakerId": "sheppard",
        "speakerName": "Chancellor Sheppard",
        "text": "Choice buttons are live ...",
        "bChoice": true,
        "options": ["Fire Deck", "Water Deck", "Wind Deck"]
      }
    ]
  }
}
```

Notes:

- `labels` is the single place for screen/tab strings used by this shell. Every
  lookup has a C++ fallback so a missing file does not break the HUD.
- `dialogueSamples` is **test data only**. Real story lines belong in
  `Content/Data/Story/**` (A03). Sample `textKey`s are prefixed `PLACEHOLDER.`
  so the traceability validator can reject them in release content.
- The file is under `Content/Data`, which `Config/DefaultGame.ini` already
  stages with `+DirectoriesToAlwaysStageAsUFS=(Path="Data")`.
- The loader caches the file for the process. Restart the game/editor after
  editing it (or add a console refresh in a later pass).
- `pda.tab.limitation` is deliberately short (`LIMIT`) so eight tabs fit at
  1080p; change the JSON label if the final design uses a different short form.

---

## 8. Debug / screenshot commands

All three switches are read in `ADAHUD::BeginPlay`. Run one automated harness per
process: `-DADuelScreenshot`, `-DADuelSelfTest` and `-DAUITest` each schedule
their own screenshots/exit, so combining them produces a race.

| Switch | Effect |
| --- | --- |
| `-DADialogueTest` | Opens the `opening_test` sample dialogue after 1.2 s. Use for manual 1080p/4K checks. |
| `-DAPDATest` | Opens the PDA on the Map tab after 1.2 s. Use for manual checks. |
| `-DAUITest` | Cycles all eight PDA tabs, captures `DAPDA_<tab>.png`, opens the sample dialogue, captures `DADialogue.png` / `DADialogueChoice.png`, then exits. |

Example (replace the editor executable path with your local UE 5.8 path):

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  /Game/DuelAcademy/Maps/DuelAcademyIsland `
  -game -windowed -ResX=1920 -ResY=1080 -DAUITest
```

For 4K use `-ResX=3840 -ResY=2160`. Screenshots land in
`DuelAcademyIsland/Saved/Screenshots/Windows/` (or the platform equivalent).
Files produced by `-DAUITest`:

- `DAPDA_Map.png`, `DAPDA_Calendar.png`, `DAPDA_Deck.png`, `DAPDA_Mail.png`
- `DAPDA_Save.png`, `DAPDA_Options.png`, `DAPDA_Records.png`, `DAPDA_Limitation.png`
- `DADialogue.png`, `DADialogueChoice.png`

The existing duel harness (`-DADuelScreenshot`, `-DADuelSelfTest`) is unchanged.

### Manual smoke checklist

1. Launch normally; verify the world HUD, banner, minimap, map and help look and
   behave exactly as before.
2. Press `P`: PDA opens with the Map tab; `Q`/`E` and clicks change tabs; `Esc`
   or `P` closes; movement resumes.
3. Map tab: select a zone and press Enter/click; the PDA closes and the player
   fast-travels (only for `bFastTravel` zones).
4. Options: cycle Text Speed to Fast; close the PDA; open `-DADialogueTest`;
   typewriter speed is visibly faster. Toggle Auto-Advance and confirm lines
   advance on their own.
5. Dialogue: `H` opens the log; Up/Down scrolls; `Esc` closes the log first.
6. Choice line: Up/Down changes the highlight, `1`–`3` or a click chooses; the
   next line appears (sample data), and closing returns a clean HUD.
7. Run `-DAUITest` at 1920×1080 and 3840×2160; check for clipped tab labels,
   portrait/name collisions and option-button overlap.

---

## 9. Integration hooks for the other lanes

### A02 — Profile / Calendar / Save / Settings

- Fill `FDAPDAProfileView`, `FDAPDACalendarView`, `FDAPDASaveSlotView`,
  `FDAPDAOptionRow`, `FDAPDARecordRow` in `ViewModelBuilder`.
- Handle `OnAction` `save.slot` to call the real save/load flow.
- Replace the placeholder October grid with the real
  `UDACalendarSubsystem` month; set `bPlaceholder=false`.
- Persist the two live options (`text_speed`, `auto_advance`); feed them back
  into `ViewModelBuilder` so the PDA shows the stored values.
- Optional: add `UDASettings` text-speed/auto fields and have `ADAHUD` apply
  them when the dialogue UI is created.

### A03 — Story / Mail

- Convert `FStoryCommand` (`Dialogue`/`Choice`) to `TArray<FDADialogueLine>`
  and call `ADAHUD::BeginDialogue(Lines, ConversationId)`.
- Bind `FDADialogueUI::OnChoiceMade` before the first conversation; apply the
  branch, then feed the next command batch.
- Bind `OnDialogueClosed` to resume the command queue (fade/wait/camera/duel).
  Do not call `Begin()` synchronously from `OnDialogueClosed` or
  `OnChoiceMade`; queue the next batch for the next tick so the UI can finish
  closing cleanly.
- Fill `FDAPDAMailView`; handle `mail.open` to show a message/duel request.
- For a mail scene over the PDA, call `BeginDialogue` while the PDA is open;
  the dialogue draws on top and returns to the PDA when closed.

### A06 — Inventory / Deck / Shop

- Fill `FDAPDADeckView` with player decks, counts and validation strings.
- Handle `OnAction` `deck.open` to open `DADeckUI` with the payload deck id;
  close the PDA first or leave it as the return layer, whichever the deck UI
  prefers (document the choice in `Docs/UI_Integration.md`).
- Cards/shop screens are out of scope for this pass; add `DAShopUI.*` and a
  PDA row/action later.
- The Deck tab already lists the four existing starter decks as a stopgap.

### A07 — Exams / Records / Limitation

- Fill `FDAPDARecordRow` (wins, timed clears, exam scores, titles) and
  `FDAPDALimitRow` (banned/limited cards).
- Add exam entry points later (PDA Calendar day → exam screen) through
  `OnAction` `calendar.select` or a new `exam.open` action.
- The Limitation pane intentionally shows the empty-state explanation until
  A01/A07 data exists.

### A08 — World / fast travel

- PDA Map already consumes `UDAIslandSubsystem::GetZones()`, discovery state,
  theme colours and `bFastTravel`. Interior/portal destinations will appear
  automatically once A08 registers their zones.
- If A08 needs a different PDA map presentation, expose a map widget rather
  than changing `DAPDAUI` directly.

### Duel UI

`DADuelUI.cpp` was not touched. If the duel board needs dialogue/choice
prompts (e.g. card effect text), route them through a separate duel-local
overlay in a later pass; do not host `FDADialogueUI` inside the duel's
`GameAndUI` input mode without coordinating with A04/A10. The current modal
order guarantees the duel always owns input while open.

---

## 10. Known gaps / next pass

- Title/new-game/continue, name entry, credits, shop, deck editor, exam UI and
  save-slot UI are **not** in this pass (A09 waves 2–3).
- Mail/Save/Limitation panes are deliberately empty placeholders; actions emit
  events but the target screens are not connected.
- `J`/`F`/time keys still act behind dialogue/PDA (see §5); needs an A10-approved
  broader input-block decision.
- Options are applied to the current process only; persistence waits on A02.
- History is a flat text log (no per-speaker portraits, save/load integration or
  unlimited scrollback paging yet).
- Dialogue skip is hold-to-fast-forward plus an immediate SKIP button; there is
  no “already seen” line skip or per-scene skip policy yet.
- The dialogue box uses the engine’s medium/large fonts, matching the existing
  HUD; final font/legibility treatment is a later presentation pass.
- Mouse wheel scrolling of long PDA lists is not wired; keyboard/gamepad and
  click work.
- `ui.json` is cached for the process; hot reload requires a restart.
- The dialogue shell does not pause world time or hide NPCs; A03/A08 own scene
  staging (camera anchors, time pause, letterbox already drawn by the UI).
- No automated UI smoke test file yet (`DAUISmokeTests.cpp` is planned for the
  A10 harness). `-DAUITest` is the current screenshot/regression entry point.
- The PDA calendar/records values are sample placeholders and must not ship as
  canon; `bPlaceholder` and the footer note call this out visibly.

---

## 11. Verification notes

This pass was written against UE 5.8 C++ without running a concurrent editor
build (per the A09 brief: other lanes may be building). Changes are additive and
compile-safe by inspection:

- New classes are plain C++ (`FDADialogueUI`, `FDAPDAUI`), matching the
  existing `FDADuelUI` ownership pattern (`TUniquePtr` members on `ADAHUD`).
- No new module dependencies; only `Core`, `Engine`, `InputCore`, `RenderCore`,
  `Json`, `JsonUtilities`, all already in `DuelAcademyIsland.Build.cs`.
- No reflected types were added, so UHT surface is unchanged. `DAHUD`'s new
  members are non-`UPROPERTY` pointers, like the existing duel UI.
- All new drawing uses `Canvas`, `FCanvasTileItem`, `FCanvasTextItem`,
  `FCanvasTriangleItem` and the engine fonts already used by `DAHUD.cpp`.
- Entry points are additive: existing `ADAHUD` public methods keep their
  signatures; only `ToggleHelp()` moved from inline to a `.cpp` definition with
  the same behaviour plus modal guards.

Recommended gate review: build the editor target, run the manual smoke
checklist in §8, then run `-DAUITest` at 1080p/4K before merging.
