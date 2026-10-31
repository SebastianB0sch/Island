# UI Integration — Title, Dialogue, PDA and Gameplay Screens (A09, pass 3)

> Scope: Gate 1 title/dialogue/PDA plus the Gate 2 gameplay screens: Dorothy's
> shop, deck editor, monthly exam, and the live PDA Deck/Mail/Save tabs.
> Code-only Canvas, same approach as the existing HUD and duel board. No UMG,
> Blueprint or binary UI assets were added.
>
> **Owned files:** `DAHUD.*`, `DATitleScreen.*`, `DADialogueUI.*`, `DAPDAUI.*`,
> `DAUIScreen.*`, `DAShopUI.*`, `DADeckUI.*`, `DAExamUI.*`,
> `Content/Data/UI/**`, `Docs/UI_Integration.md`. A02/A03/A06/A07 C++ and data,
> `DADuelUI.*` and world C++ were **not** modified.

---

## 1. What is in this pass

| Area | Status |
| --- | --- |
| Title screen: NEW GAME, CONTINUE, OPTIONS, CREDITS, version/build | Implemented, Canvas |
| Continue: live A02 slots with name/date/DP/title/dorm/playtime; empty + corrupt states | Implemented |
| New Game: overwrite confirmation when saves exist; starts A03 opening + autosaves | Implemented |
| Shop: categories, price, unlock reason, stock/restock, DP, purchase confirm, pack reveal | Implemented against A06 |
| Deck editor: player decks, collection filters/sort, add/remove/swap, validation, rename/copy/erase, recipes | Implemented against A06 |
| Exam: written questions + timer, written summary, timed entry, practical progress, result breakdown | Implemented against A07 |
| PDA Deck tab | Live A06 player decks, counts, active deck, validation, EDIT action |
| PDA Mail tab | A03 emails.json + A02 unlock/read state; open marks read |
| PDA Save tab | Live A02 slots; empty=save, occupied=load after confirm |
| PDA Calendar/Records | Live A02 date/exam days/profile counters |
| PDA Map/Options/Limitation | Map live; options via UDASettings; limitation still data-pending |
| Dialogue box: speaker, portrait/expression, typewriter, continue, choices, skip/auto, history log | Implemented, Canvas |
| HUD hosting | Title top modal; dialogue/PDA and gameplay screens layered |
| Debug switches | `-DATitleTest`, `-DANewGameTest`, `-DAGameplayUITest`, `-DADialogueTest`, `-DAPDATest`, `-DAUITest` |
| Data | `Content/Data/UI/ui.json` (labels, tabs, credits, sample dialogue) |

Existing location banner, minimap, compass, help panel, island map/fast travel
and duel deck-select/board/result flows are unchanged and still draw exactly as
before when no new UI is open.

---

## 2. Files

**New**

- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DATitleScreen.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DATitleScreen.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DADialogueUI.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DADialogueUI.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAPDAUI.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAPDAUI.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAUIScreen.h` — shared Canvas helper base for the gameplay screens.
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAUIScreen.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAShopUI.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAShopUI.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DADeckUI.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DADeckUI.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAExamUI.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAExamUI.cpp`
- `DuelAcademyIsland/Content/Data/UI/ui.json`
- `Docs/UI_Integration.md` (this file)

**Modified (minimal)**

- `Public/DAHUD.h` — title/gameplay screen hosting, modal checks, dialogue/PDA
  API, shop/deck/exam accessors, members.
- `Private/DAHUD.cpp` — creates/ticks/draws title/dialogue/PDA and the
  shop/deck/exam screens, game-flow callbacks, input mode, P/B polling, economy
  wiring, `-DAGameplayUITest`, help text.
- `Private/DAStudentCharacter.cpp` — **one line** in `IsMovementBlocked()` so
  movement/interact stop while title/dialogue/PDA/gameplay screens are open
  (see §5).

`DADuelUI.h/.cpp` are untouched.

---

## 2A. Title / new game / continue flow

### Normal launch

Unless a story or UI harness is starting, `ADAHUD::BeginPlay` opens
`FDATitleScreen` over the world:

- `DUEL ACADEMY / ISLAND`, tagline, version/build text.
- `NEW GAME`, `CONTINUE`, `OPTIONS`, `CREDITS`.
- Latest-save summary panel, mouse hover/selection, gamepad/keyboard navigation.
- Title is the top modal layer: movement, interact, map, help, PDA and dialogue
  are blocked while it is open. The world still renders behind the dim overlay.

The title is **suppressed** for: `-DAOpeningTest`, `-DAStorySelfTest`,
`-DANewGameTest`, `-DAGameplayUITest`, `-DADuelScreenshot`, `-DADuelSelfTest`,
`-DADialogueTest`, `-DAPDATest`, `-DAUITest`. `-DATitleTest` forces it on
regardless.

### NEW GAME

1. If any save file exists (manual or autosave), the title opens a confirmation
   panel. `START NEW GAME` proceeds; `CANCEL` returns to the menu.
2. On confirm, `ADAHUD::HandleTitleNewGame` closes the title **first**, then
   calls `UDAStorySubsystem::StartOpeningFresh()`. Closing first matters: A03
   can open a dialogue immediately, and title/dialogue are mutually exclusive
   modal layers.
3. The HUD then writes A02's autosave slot directly
   (`UDASaveSubsystem::SaveSlot(AutosaveSlotIndex, Error)`), so the new opening
   has a checkpoint and `CONTINUE` works on the next launch. This is the one
   place Gate 1 forces an autosave even if ambient autosave is disabled.
4. Existing manual slots are **not deleted**. The confirmation text explicitly
   says the autosave will be replaced as the new game saves.

### CONTINUE

`FDATitleScreen::RefreshSlots()` calls
`UDASaveSubsystem::EnumerateSlots()` and shows all four slots (0 = autosave,
1–3 = manual). Each row shows:

- slot label (`AUTOSAVE`, `SLOT 1`…), player name, dorm and title;
- date/period from A02 metadata, DP and playtime;
- `EMPTY SLOT`, `CORRUPT`, or `BACKUP USED` badges where applicable.

Selecting a usable slot calls `ADAHUD::HandleTitleContinue`:

1. `UDASaveSubsystem::LoadSlot(SlotIndex, Error)` — **never**
   `UGameplayStatics::LoadGameFromSlot` directly.
   A02 restores profile, calendar, settings and registered providers (including
   A03 story state).
2. `ApplySettingsToUI()` pushes the restored text speed/auto-advance into the
   dialogue box.
3. The title closes.
4. If `UDAStorySubsystem::IsRunning()` is false, `StartOpening()` is called:
   free-roam saves restore free roam, an opening save at the E01/E01b boundary
   resumes there. A save **mid-scene** restores `bRunning` and the pending
   command; A03's ticker resumes it, so `StartOpening()` is intentionally not
   called in that case.

Load failures keep the title open and show a red status line with A02's error.

### OPTIONS

The title options panel has four rows:

| Row | Source / effect |
| --- | --- |
| Text Speed | `UDASettings::Get/SetTextSpeed` (Slow/Normal/Fast/Instant) |
| Auto-Advance | Stored as `UDASettings::SetControl("AutoAdvance", "On"/"Off")` |
| BGM Volume | `UDASettings::Get/SetBgmVolume` (0–100%, step 10) |
| SFX Volume | `UDASettings::Get/SetSfxVolume` (0–100%, step 10) |

`OnOptionsChanged` triggers `ADAHUD::ApplySettingsToUI`, which sets
`FDADialogueUI::SetTextSpeed(Settings->GetTextSpeedCps())` and auto-advance.
Leaving the panel calls `UDASettings::Save()` (A02 autosave). Before a profile
exists there is nothing to write; the values remain in memory and are included
in the first new-game autosave.

> **A02 blocker:** `UDASettings` has no typed auto-advance field. The controls
> map is used as a persisted bridge (`"AutoAdvance"` key) so the choice survives
> save/load. Replace it with a typed property when A02 adds one.
>
> **Audio blocker:** BGM/SFX values are stored correctly but no audio mixer
> consumes them yet. That is an A10/audio integration hook, not a UI failure.

### CREDITS

The credits panel is scrollable (Up/Down, PageUp/PageDown) with Escape/gamepad B
to go back. Lines come from the `credits` array in `Content/Data/UI/ui.json`;
there is a small built-in fallback if the file is missing. No ripped assets or
story text are embedded in C++.

### Title API

```cpp
HUD->OpenTitle();
HUD->CloseTitle();
HUD->IsTitleOpen();

FDATitleScreen* Title = HUD->GetTitleScreen();
Title->ShowPanel(EDATitlePanel::Continue);
Title->RefreshSlots();
Title->GetSlots();
Title->SetStatusMessage(TEXT("..."), true);
Title->OnNewGame / OnContinue / OnOptionsChanged / OnClosed
```

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

`DAPDAUI.h` exposes a view model. The built-in refresh fills it from live A02
profile/calendar/save data, A03 `emails.json` plus A02 mail state, and A06
player-deck state; `ViewModelBuilder` can still override individual tabs. The UI
never implements rules, economy or progression.

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
| `deck.open` | deck id | Deck row activated | HUD closes the PDA and opens `DADeckUI` |
| `exam.open` | empty | Exam-day calendar cell activated | HUD closes the PDA and opens `FDAExamUI` |
| `mail.open` | mail id | Mail row activated | A02 read state (`MarkEmailRead`); body is shown in the detail pane |
| `save.slot` | `save:<slot>` / `load:<slot>` | Empty save row activated / occupied row confirmed | HUD calls A02 `SaveSlot` / `LoadSlot` |
| `options.changed` | `id=value` (`text_speed=Fast`) | Options row cycled | A02 + HUD applies |
| `records.row` | record label | Records row activated | A02/A07 (optional) |
| `limitation.row` | card name | Limitation row activated | A01/A07 (optional) |

`ADAHUD::HandlePDAAction` handles `options.changed` through `UDASettings` and
applies text speed/auto-advance to the dialogue box immediately. `deck.open`
and `exam.open` close the PDA and open the corresponding gameplay screen.
`mail.open` is a no-op in the HUD because `FDAPDAUI` has already marked the
message read through `UDAProfileSubsystem::MarkEmailRead`; the body is visible
in the selected row's detail pane. `save.slot` performs the real A02 operation:
empty slots save immediately, occupied slots require a second Enter on the same
row (`PendingLoadSelection`), corrupt slots are rejected, and a successful load
refreshes settings and resumes A03 only when the restored story is not already
running. The Save tab is rebuilt from `UDASaveSubsystem::EnumerateSlots()` with
occupied/empty/corrupt/backup state.

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

## 4A. Gameplay screens (Gate 2)

`FDAShopUI`, `FDADeckUI` and `FDAExamUI` are plain C++ Canvas screens built on
`FDAUIScreen` (shared font/draw/wrap/hit-test/audio helpers). `ADAHUD` owns one
instance of each in a `TUniquePtr` and only one of them can be open at a time.
They draw over the world and consume input; their `OnClosed` delegates restore
the HUD input mode.

### Dorothy's card shop (`FDAShopUI`)

Open/close through the HUD:

```cpp
HUD->OpenShop();          // B while facing the card-shop interactable, or debug
HUD->CloseShop();
HUD->IsShopOpen();
FDAShopUI* ShopUI = HUD->GetShopUI();
```

The old `E` card-shop path in `ADAInteractable.cpp` is intentionally untouched;
`B` is the Gate 2 entry point.

The screen is presentation-only. Every rule comes from A06:

| UI action | A06 call |
| --- | --- |
| Build category tabs and rows | `UDAShopSubsystem::GetCatalogue()` |
| Wallet display | `UDAShopSubsystem::GetDP()` (wired to A02 in `ADAHUD::WireEconomySystems`) |
| Re-evaluate event/month/title unlocks | `UDAShopSubsystem::RefreshUnlocks()` |
| Buy pack | `UDAShopSubsystem::PurchasePack(PackId, Seed, OutResult)` |
| Read unlock reason, stock/restock, price, block | `FDAEPackView` fields |
| Reveal cards, duplicate DP, DP before/after | `FDAEPurchaseResult` / `FDAEPackOpenResult` / `FDAEPackCardReveal` |

`ADAHUD::WireEconomySystems()` installs `SetWalletHandlers` (get DP / spend DP /
credit DP against `UDAProfileSubsystem`) and `SetUnlockContextProvider` (title,
counters, flags, month, absolute day). A03 exposes no completed-event list, so
event-gated packs can only be evaluated from flags/counters/title/calendar
until A03 provides one. The shop UI never mutates DP or inventory directly.

Flow: category browse → pack detail (unlock reason, stock/restock, status) →
purchase confirmation → pack reveal with card art/rarity/owned counts and
duplicate-DP feedback. `RefreshCatalogue(true)` keeps the selected pack after a
purchase.

### Deck editor (`FDADeckUI`)

```cpp
HUD->OpenDeckEditor(DeckId);   // PDA Deck row / detail-pane EDIT button, or debug
HUD->CloseDeckEditor();
HUD->IsDeckEditorOpen();
FDADeckUI* DeckUI = HUD->GetDeckUI();
```

All deck state and rules stay in A06:

| UI action | A06 call |
| --- | --- |
| Deck slot list, active deck | `GetPlayerDecks()` / `GetActiveDeckId()` |
| Main/extra counts, 40–60 / 20 / 3-copy / banlist messages | `GetDeckValidationMessage()` / `IsDeckLegal()` |
| Collection list, filter/sort | `GetCollectionView(FDAECardFilter, EDAECardSortKey, bDescending)` |
| Add / remove / swap | `AddCardToDeck` / `RemoveCardFromDeck` / `SwapCardInDeck` |
| Rename / copy / erase / create | `RenameDeck` / `CopyDeck` / `EraseDeck` / `CreateDeck` |
| Set active deck | `SetActiveDeck` |
| Fusion recipe overlay | `GetAvailableFusionRecipes()` |
| Name length / limits | `GetRules()` |

Sections: deck slots, owned-card collection with ALL/MON/SPELL/TRAP filter and
ID/NAME/ATK/LEVEL sort, current deck main/extra tabs, validation line, deck
actions, rename text entry, erase confirmation and recipe availability overlay.
Adding a fusion card or pressing `X` targets the extra deck; `G` starts a swap
from the selected deck card and completes with a collection selection.

### Monthly exam (`FDAExamUI`)

```cpp
HUD->OpenExam(MonthIndex);    // 0 = current calendar month
HUD->CloseExam();
HUD->IsExamOpen();
FDAExamUI* ExamUI = HUD->GetExamUI();
```

The exam is opened by activating an exam-day cell in the PDA Calendar
(`exam.open`), or by debug/test code. A07 owns the lifecycle and scoring; the UI
only forwards input and renders payloads:

| UI phase | A07 call |
| --- | --- |
| Start / resume | `StartExam(MonthIndex, Seed, Error)` |
| Written question | `GetCurrentQuestion()`, `SubmitWrittenAnswer(QuestionId, AnswerIndex, Error)` |
| Written summary | `FinishWritten(Error)`, `GetCorrectAnswerCount()`, `GetWrittenPoints()` |
| Timed entry | `PickTimedPuzzle(MonthIndex)`, `BeginTimed(PuzzleId, Error)` |
| Timed result | `SubmitTimedResult(bSolved, TurnsUsed, SecondsUsed, Error)` |
| Practical start | `BeginPractical(Error)` |
| Practical progress | `GetPracticalObjectives()`, `GetPracticalProgress()` |
| Practical finish / result | `FinishPractical(Error)`, `FinishExam(OutResult, Error)` |
| Score breakdown | `FDAExamResult` (written/timed/practical/total/grade/title/dorm/objectives) |

The written section shows the question, topic, difficulty, option list, answer
cursor, answered count and a timer. The written summary shows correct/points.
The timed panel shows the selected puzzle id; A04/A07 have not wired a timed
puzzle duel yet, so the normal UI records “continue without clearing (0)” and
debug helpers (`DebugAnswerAllWritten`, `DebugResolveTimed`,
`DebugFinishPractical`, `DebugCompleteExam`) drive the other phases for
screenshots. The practical panel shows opponent/deck/LP, turn/time limits,
objective progress and points; the result panel shows the full breakdown.

### Gameplay screen input

**Shop**

| Key / input | Action |
| --- | --- |
| `Up` / `Down`, `W` / `S`, D-pad | Move pack selection |
| `Left` / `Right`, `Q` / `E`, LB/RB | Previous / next category |
| `Enter` / `Space` / gamepad A | Buy selected pack (opens confirmation) |
| `Up` / `Down` in confirmation | Switch BUY / CANCEL |
| `Enter` / `Space` / gamepad A in confirmation | Confirm choice |
| `Esc` / `P` / gamepad B | Cancel / close |
| Mouse | Click category, pack, buy, confirm/cancel, reveal/close |

**Deck editor**

| Key / input | Action |
| --- | --- |
| `Tab` / LB | Cycle focus: decks → collection → deck cards |
| `Up` / `Down`, `W` / `S`, D-pad | Move selection in the focused panel |
| `Enter` / `Space` / gamepad A | Decks: set active; collection: add/complete swap; deck: remove |
| `Left` / `Right` in deck cards | Switch main / extra tab |
| `N` / `C` / `R` / `Delete` | New / copy / rename / erase deck |
| `F` / `T` | Cycle collection filter / sort |
| `X` | Toggle add target: main ↔ extra |
| `G` | Start swap from the selected deck card |
| `Q` | Fusion recipe overlay |
| `V` | Set current deck active |
| `Esc` / gamepad B | Cancel swap/name/erase, otherwise close |
| Mouse | Click deck, collection card, deck card, filter/sort chips and buttons |

**Exam**

| Key / input | Action |
| --- | --- |
| `Up` / `Down`, `W` / `S`, D-pad | Move answer selection |
| `1`–`4` | Jump to answer option |
| `Enter` / `Space` / gamepad A | Submit answer / advance phase / close result |
| `Esc` / `P` / gamepad B | Close exam |
| Mouse | Click option or on-screen button |

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
| `B` | Open Dorothy's shop when facing the card-shop interactable (old `E` path untouched) |
| `M` / `Tab` / gamepad Start | Island map (existing; blocked while title/duel/dialogue/PDA/gameplay screens are open) |
| `F1` / `H` | Help (blocked while title/duel/dialogue/PDA/gameplay screens are open) |

### Title

| Key / input | Action |
| --- | --- |
| `Up` / `Down`, `W` / `S`, D-pad | Move menu/slot/option selection |
| `Enter` / `Space` / gamepad A | Confirm / load / cycle option |
| `Left` / `Right`, D-pad left/right | Adjust options; switch confirm buttons |
| `Esc` / gamepad B | Back one panel (Main: shows a hint, does not quit) |
| Mouse | Hover highlights; click buttons, slots, options and back |
| `PageUp` / `PageDown` | Credits fast scroll |

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
        || HUD->IsDialogueOpen() || HUD->IsPDAOpen() || HUD->IsTitleOpen()
        || HUD->IsGameplayUIOpen());
}
```

This blocks movement, look, jump, sprint, zoom and E-interaction while a new
modal UI is open. No movement/camera/duel logic was touched. A09 did **not**
add P/B/dialogue Enhanced Input actions; the HUD polls those keys itself.
`J` (jacket), `F` (duel pose) and the time keys still work behind an open
dialogue/PDA/gameplay screen; treat that as a cosmetic known gap until A10
approves a broader modal input block.

---

## 6. Modal precedence and input ownership

From highest to lowest:

1. **Title** (`FDATitleScreen`) - normal-launch entry point; draws alone over
   the world and owns all input.
2. **Duel** (`DADuelUI`) - draws alone and owns its input mode.
3. **Gameplay screens** (`FDAShopUI`, `FDADeckUI`, `FDAExamUI`) - draw alone
   over the world, one at a time, and own all input while open.
4. **Island map** - draws alone (existing behaviour).
5. **PDA** - full-screen shell; stops updating input while dialogue is open.
6. **Dialogue** - draws above the PDA and consumes all UI input while open.
7. **Help** - overlay; cannot be opened while the above are open.
8. **World HUD** - compass, minimap, banner, message, prompt.

Rules enforced by `ADAHUD`:

- `IsModalOpen()` = title || map || help || duel || PDA || dialogue ||
  shop || deck editor || exam.
- `P` / gamepad View opens the PDA only when no title/duel/dialogue/gameplay
  screen is open; opening while the map is open closes the map first.
- Opening shop/deck/exam closes the PDA, dialogue, map and help first. The PDA
  Deck row and Calendar exam day close the PDA and hand over to the screen.
- `M` and `F1` are ignored while the title/PDA/dialogue/gameplay screens are open.
- A story dialogue may open **over** the PDA (for mail/phone scenes). Closing
  the dialogue returns input to the still-open PDA. Dialogue cannot open while a
  gameplay screen is open.
- New Game/Continue close the title **before** A03 starts its opening; this
  avoids A03's immediate dialogue being rejected by the title modal guard.
- The PDA/dialogue/gameplay screens use `FInputModeGameAndUI` with a visible
  cursor; closing the last one restores `FInputModeGameOnly`.
- `DADuelUI` always wins; the new UI never changes duel input mode.
- A `P` press that closes a gameplay screen is consumed for that frame and does
  not immediately re-open the PDA.

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

All switches are read in `ADAHUD::BeginPlay`. Run one automated harness per
process: `-DADuelScreenshot`, `-DADuelSelfTest` and `-DAUITest` each schedule
their own screenshots/exit, so combining them produces a race.

| Switch | Effect |
| --- | --- |
| `-DATitleTest` | Forces the title screen on launch and captures `DATitle.png` after 1.6 s. Stays open for manual navigation. |
| `-DANewGameTest` | Suppresses the title, starts `UDAStorySubsystem::StartOpeningFresh()` at 1.5 s (unless `-DAOpeningTest` is also present), captures `DANewGameOpening.png` at 4 s and keeps running. |
| `-DAOpeningTest` | Existing A03 harness: starts the fresh opening after ~2 s; the title is suppressed. |
| `-DADialogueTest` | Opens the `opening_test` sample dialogue after 1.2 s. |
| `-DAPDATest` | Opens the PDA on the Map tab after 1.2 s. |
| `-DAGameplayUITest` | Seeds a test profile (`Test Student`), starter decks/collection and unlocked contacts, then captures the shop, deck editor, exam written/written-done/timed/result and the PDA Deck/Mail/Save tabs before exiting. Run at 1920×1080. |
| `-DAUITest` | Cycles all eight PDA tabs, captures `DAPDA_<tab>.png`, opens the sample dialogue, captures `DADialogue.png` / `DADialogueChoice.png`, then exits. |

Example (replace the editor executable path with your local UE 5.8 path):

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  /Game/DuelAcademy/Maps/DuelAcademyIsland `
  -game -windowed -ResX=1920 -ResY=1080 -DATitleTest
```

For 4K use `-ResX=3840 -ResY=2160`. Screenshots land in
`DuelAcademyIsland/Saved/Screenshots/Windows/` (or the platform equivalent).
Expected files:

- Title: `DATitle.png`
- New game: `DANewGameOpening.png`
- `-DAGameplayUITest`: `DAShop.png`, `DADeckEditor.png`, `DAExamWritten.png`,
  `DAExamWrittenDone.png`, `DAExamTimed.png`, `DAExamResult.png`,
  `DAPDA_DeckGameplay.png`, `DAPDA_Mail.png`, `DAPDA_Save.png`
- `-DAUITest`: `DAPDA_Map.png`, `DAPDA_Calendar.png`, `DAPDA_Deck.png`,
  `DAPDA_Mail.png`, `DAPDA_Save.png`, `DAPDA_Options.png`,
  `DAPDA_Records.png`, `DAPDA_Limitation.png`, `DADialogue.png`,
  `DADialogueChoice.png`

### Gate 1 manual smoke checklist

1. Launch normally with no switches: the title screen appears over the world;
   movement/map/help/PDA are blocked.
2. `CONTINUE` on a clean install: the slot list opens with four clearly empty
   slots; Enter on an empty slot shows a status message.
3. `NEW GAME` with no saves: starts A03's opening immediately, closes the title,
   and creates/updates the autosave.
4. Quit and relaunch: `CONTINUE` is selected by default, the autosave row shows
   name/date/DP/title/dorm/playtime, and loading resumes the opening (mid-scene
   or free roam).
5. `NEW GAME` with an existing save: confirmation panel appears; `CANCEL`
   returns safely; `START NEW GAME` replaces the autosave.
6. `OPTIONS`: change text speed and auto-advance, back out, start a dialogue and
   confirm both take effect. BGM/SFX values are stored but have no mixer yet.
7. `CREDITS`: Up/Down and PageUp/PageDown scroll; Esc/B returns.
8. Launch with `-DAOpeningTest`: no title, opening starts as before (regression).
9. Run `-DATitleTest` and `-DAUITest` at 1920×1080 and 3840×2160; check title
   legibility, slot cards, options rows and credits scrolling.

### Gate 2 manual smoke checklist

1. Launch normally and choose `CONTINUE` on the autosave written by a new game:
   confirm the loaded profile/date/DP/deck are present and the game resumes the
   saved state rather than restarting the opening from scratch.
2. `NEW GAME` still starts the fresh opening and writes the autosave.
3. Face the card-shop counter and press `B`: category tabs, pack prices, unlock
   reasons, stock/restock line and DP balance are visible. Buy a pack, confirm,
   check the reveal cards and duplicate-DP feedback, then close with `Esc`.
4. PDA → Deck: rows show A06 player decks, main/extra counts, the active deck and
   validation errors. `Enter` opens the deck editor; add/remove/swap cards,
   change filter/sort, rename/copy/erase a deck, set it active and open recipes.
   `Esc` closes the editor and returns to gameplay.
5. PDA → Calendar: activate an exam-day cell and confirm the exam opens. Answer
   the ten written questions, review the written summary, record the timed
   placeholder, finish the practical panel and inspect the result breakdown.
6. PDA → Mail: only contacts unlocked in A02 are listed; `Enter` marks the
   selected message read and the body appears in the detail pane. PDA → Save:
   empty slot saves immediately; an occupied slot requires a second `Enter` and
   loads through A02 without `UGameplayStatics`.
7. Run `-DAGameplayUITest` at 1920×1080 and inspect all nine captures above for
   overlap, clipping, missing art fallbacks and readable text.

The existing duel harness (`-DADuelScreenshot`, `-DADuelSelfTest`) is unchanged.

---

## 9. Integration hooks for the other lanes

### A02 — Profile / Calendar / Save / Settings

- `FDAPDAUI::BuildPlaceholderViewModel` fills profile, calendar, deck, mail,
  save slots, options and records from A02/A03/A06 APIs. `ViewModelBuilder` can
  still override individual tabs after that.
- `OnAction` `save.slot` is wired: the HUD calls A02 `SaveSlot`/`LoadSlot`,
  confirms occupied slots twice, rejects corrupt slots, and reloads settings
  after a successful load. There is no direct `UGameplayStatics` call.
- The HUD installs A06's shop wallet handlers and unlock-context provider
  against `UDAProfileSubsystem` and `UDACalendarSubsystem`
  (`ADAHUD::WireEconomySystems`).
- The PDA calendar is live (`UDACalendarSubsystem` month, exam days, today);
  event markers await A03 data.
- Typed settings: add an auto-advance field to `UDASettings` and replace the
  temporary `SetControl("AutoAdvance", ...)` bridge. Add an audio mixer hook for
  the stored BGM/SFX volumes.
- Save/load metadata used by the title and PDA: `EnumerateSlots()` only. No
  UI code calls `UGameplayStatics::LoadGameFromSlot`.

### A03 — Story / Mail

- `ADAHUD::HandleTitleNewGame` closes the title, calls
  `UDAStorySubsystem::StartOpeningFresh()` and force-writes the autosave.
  `HandleTitleContinue` calls `UDASaveSubsystem::LoadSlot()` and then
  `StartOpening()` only when the restored story is not already running.
- Convert `FStoryCommand` (`Dialogue`/`Choice`) to `TArray<FDADialogueLine>`
  and call `ADAHUD::BeginDialogue(Lines, ConversationId)`.
- Bind `FDADialogueUI::OnChoiceMade` before the first conversation; apply the
  branch, then feed the next command batch.
- Bind `OnDialogueClosed` to resume the command queue (fade/wait/camera/duel).
  Do not call `Begin()` synchronously from `OnDialogueClosed` or
  `OnChoiceMade`; queue the next batch for the next tick so the UI can finish
  closing cleanly.
- `FDAPDAUI` reads `Content/Data/Story/emails.json` for contact/message bodies
  and filters them through A02 `IsEmailUnlocked` / `IsEmailRead`; a pending A02
  duel request is appended as a synthetic row. Activating a mail row calls
  `UDAProfileSubsystem::MarkEmailRead` and shows the body in the detail pane.
- A03 exposes no public completed-event list, so event-gated shop unlocks and
  Calendar event markers cannot be populated yet. Expose that state (or add it
  to `FDAEUnlockContext::CompletedEvents`) when available.
- For a mail scene over the PDA, call `BeginDialogue` while the PDA is open;
  the dialogue draws on top and returns to the PDA when closed.

### A06 — Inventory / Deck / Shop

- `FDAPDAUI` now fills `FDAPDADeckView` from `UDADeckLogic::GetPlayerDecksRef()`
  (not the four starter catalogue decks) with main/extra counts, active deck and
  `GetDeckValidationMessage()`.
- `OnAction` `deck.open` is wired: the HUD closes the PDA and calls
  `ADAHUD::OpenDeckEditor(Payload)`. The editor uses only `UDADeckLogic` /
  `UDAInventorySubsystem` APIs (collection view, add/remove/swap, rename/copy/
  erase, set active, recipes).
- `FDAShopUI` is wired to `UDAShopSubsystem::GetCatalogue` / `PurchasePack` /
  `GetDP`; A09 contains no price, stock, unlock or duplicate-DP logic.
- Remaining A06 gap: no changes were made to A06 source or data; the UI depends
  on the public headers listed in §4A.

### A07 — Exams / Records / Limitation

- `FDAExamUI` is wired to `UDAExamSubsystem::StartExam`, `SubmitWrittenAnswer`,
  `FinishWritten`, `BeginTimed`, `SubmitTimedResult`, `BeginPractical`,
  `FinishPractical` and `FinishExam`. All scoring/grade/title/dorm outcomes come
  from `FDAExamResult`; the UI performs no evaluation.
- Exam entry: activating an exam-day calendar cell emits `exam.open`; the HUD
  closes the PDA and calls `ADAHUD::OpenExam(0)` (current month).
- Remaining A07 gap: A04/A07 have not wired a timed puzzle duel. The timed panel
  records a failed timed section via `SubmitTimedResult(false, 0, 0, Error)` and
  exposes debug helpers for screenshots. Replace that button with the real duel
  launch once A04/A07 provide it.
- `FDAPDARecordRow` (wins, timed clears, exam scores, titles) and
  `FDAPDALimitRow` (banned/limited cards) still need A02/A07 data feeds.
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

- **Name entry and delete-slot confirmation** are still later-pass screens. New
  Game uses A03's default player name; A02's rename API is ready for a name-entry
  screen. The PDA save tab can save/load but cannot delete a slot.
- The title has no Quit item (not requested for Gate 1); closing the process is
  still platform/console level.
- Mail, Records and Limitation are not full readers/feeds: mail bodies come from
  `emails.json` with unlock/read state, records still use A02 profile counters,
  and the limitation list remains data-pending. Save/load **is** wired through
  A02 now.
- A03 exposes no completed-event list, so event-gated shop unlocks and calendar
  event markers remain incomplete (see §9).
- A04/A07 have no timed-puzzle duel launch yet; the exam timed section records a
  failed result with a “continue without clearing” action until that integration
  lands.
- No UE build or PIE run was performed for this pass (concurrent A-lane builds
  were prohibited). The compile audit is static only; see §11.
- `J`/`F`/time keys still act behind title/dialogue/PDA/gameplay screens (see
  §5); needs an A10-approved broader input-block decision.
- Auto-advance is persisted through the `UDASettings` controls map because A02
  has no typed field yet; replace the bridge when the field lands.
- BGM/SFX values are stored but no audio mixer consumes them yet.
- Settings changed before a profile exists stay in memory and ride along with
  the first new-game autosave; there is no separate title-only settings file.
- History is a flat text log (no per-speaker portraits, save/load integration or
  unlimited scrollback paging yet).
- Dialogue skip is hold-to-fast-forward plus an immediate SKIP button; there is
  no “already seen” line skip or per-scene skip policy yet.
- The dialogue box uses the engine’s medium/large fonts, matching the existing
  HUD; final font/legibility treatment is a later presentation pass.
- Mouse wheel scrolling of long PDA/credits lists is not wired; keyboard/gamepad
  and click work.
- `ui.json` is cached for the process; hot reload requires a restart.
- The dialogue shell does not pause world time or hide NPCs; A03/A08 own scene
  staging (camera anchors, time pause, letterbox already drawn by the UI).
- No automated UI smoke test file yet (`DAUISmokeTests.cpp` is planned for the
  A10 harness). `-DAUITest`, `-DATitleTest` and `-DANewGameTest` are the current
  screenshot/regression entry points.

---

## 11. Verification notes

This pass was written against UE 5.8 C++ without running a concurrent editor
build (per the A09 brief: other lanes may be building). Changes are additive and
compile-safe by inspection:

- New classes are plain C++ (`FDATitleScreen`, `FDADialogueUI`, `FDAPDAUI`,
  `FDAUIScreen`, `FDAShopUI`, `FDADeckUI`, `FDAExamUI`), matching the existing
  `FDADuelUI` ownership pattern (`TUniquePtr` members on `ADAHUD`).
- Title/save/options calls go through `UDAStorySubsystem`, `UDASaveSubsystem`
  and `UDASettings`; no direct `UGameplayStatics::LoadGameFromSlot` and no
  edits to A02/A03 source.
- Shop/deck/exam calls go through `UDAShopSubsystem`, `UDAInventorySubsystem`,
  `UDADeckLogic` and `UDAExamSubsystem`. Prices, stock, unlock evaluation,
  deck rules, pack rolls, exam scoring and title/dorm outcomes remain in those
  systems; the UI only renders payloads.
- No new module dependencies; only `Core`, `Engine`, `InputCore`, `RenderCore`,
  `Json`, `JsonUtilities`, all already in `DuelAcademyIsland.Build.cs`.
- No reflected types were added, so UHT surface is unchanged. `DAHUD`'s new
  members are non-`UPROPERTY` pointers, like the existing duel UI.
- All new drawing uses `Canvas`, `FCanvasTileItem`, `FCanvasTextItem`,
  `FCanvasTriangleItem` and the engine fonts already used by `DAHUD.cpp`.
- Entry points are additive: existing `ADAHUD` public methods keep their
  signatures; only `ToggleHelp()` moved from inline to a `.cpp` definition with
  the same behaviour plus modal guards.
- Static checks completed after the final edits: brace/paren balance on all
  modified/new C++ files, `ui.json` parse validation, and API signature checks
  against the A02/A06/A07 headers. **No compile or PIE run was performed**, so
  the first build may still surface include/order issues.

Recommended gate review: build the editor target, fix any compile diagnostics,
run the Gate 1 and Gate 2 manual smoke checklists in §8, then run `-DAUITest`
and `-DAGameplayUITest` at 1080p/4K before merging.
