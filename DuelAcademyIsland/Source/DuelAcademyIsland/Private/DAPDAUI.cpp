// Duel Academy Island - PDA shell implementation.

#include "DAPDAUI.h"

#include "CanvasItem.h"
#include "DACardRecords.h"
#include "DADialogueUI.h"
#include "DAHUD.h"
#include "DAIslandSubsystem.h"
#include "DALocationVolume.h"
#include "DAStudentCharacter.h"
#include "DuelAcademyIsland.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "RenderUtils.h"

namespace
{
	static_assert(static_cast<int32>(EDAPDATab::Count) == DAPDATabCount, "PDA tab count mismatch");

	const FLinearColor PdaGold(1.f, 0.78f, 0.25f);
	const FLinearColor PdaInk(0.01f, 0.018f, 0.034f);
	const FLinearColor PdaPaper(0.95f, 0.95f, 0.97f);
	const FLinearColor PdaMuted(0.60f, 0.65f, 0.72f);
	const FLinearColor PdaCyan(0.35f, 0.82f, 0.92f);
	const FLinearColor PdaRed(0.88f, 0.28f, 0.24f);
	const FLinearColor PdaGreen(0.42f, 0.82f, 0.48f);

	const TCHAR* WeekdayShort(int32 Weekday)
	{
		static const TCHAR* Names[] = {
			TEXT("SUN"), TEXT("MON"), TEXT("TUE"), TEXT("WED"), TEXT("THU"), TEXT("FRI"), TEXT("SAT")
		};
		return Names[((Weekday % 7) + 7) % 7];
	}

	FLinearColor WithAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}

	EDAPDATab ClampTab(EDAPDATab Tab)
	{
		const int32 Index = FMath::Clamp(static_cast<int32>(Tab), 0, DAPDATabCount - 1);
		return static_cast<EDAPDATab>(Index);
	}
}

FDAPDAUI::FDAPDAUI(ADAHUD* InOwner)
	: OwnerHUD(InOwner)
{
	PlayerOwner = InOwner ? InOwner->GetOwningPlayerController() : nullptr;
	RefreshViewModel();
}

FDAPDAUI::~FDAPDAUI() = default;

UWorld* FDAPDAUI::GetWorld() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetWorld() : nullptr;
}

UGameInstance* FDAPDAUI::GetGameInstance() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetGameInstance() : nullptr;
}

UFont* FDAPDAUI::GetFont(bool bLarge) const
{
	if (OwnerHUD.IsValid())
	{
		return bLarge ? OwnerHUD->GetBigFont() : OwnerHUD->GetSmallFont();
	}
	return bLarge ? (GEngine ? GEngine->GetLargeFont() : nullptr) : (GEngine ? GEngine->GetMediumFont() : nullptr);
}

void FDAPDAUI::PlaySfx(const TCHAR* SoundName, float Volume) const
{
	if (OwnerHUD.IsValid())
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(OwnerHUD.Get()))
		{
			Sub->PlayUISound(SoundName, Volume);
		}
	}
}

// ------------------------------------------------------------------------ lifecycle

void FDAPDAUI::Open(EDAPDATab Tab)
{
	if (bOpen)
	{
		SetTab(Tab);
		return;
	}
	bOpen = true;
	Elapsed = 0.f;
	HoveredTab = INDEX_NONE;
	HoveredRow = INDEX_NONE;
	ActiveTab = ClampTab(Tab);
	Selection = 0;
	ListScroll = 0;
	RefreshViewModel();
	if (ActiveTab == EDAPDATab::Calendar)
	{
		for (int32 Index = 0; Index < ViewModel.Calendar.Days.Num(); ++Index)
		{
			if (ViewModel.Calendar.Days[Index].bToday)
			{
				Selection = Index;
				break;
			}
		}
	}
	RefreshRows();
	PlaySfx(TEXT("A_UIClick"), 0.55f);
}

void FDAPDAUI::Close()
{
	if (!bOpen)
	{
		return;
	}
	bOpen = false;
	HitTargets.Reset();
	HoveredTab = INDEX_NONE;
	HoveredRow = INDEX_NONE;
	OnClosed.Broadcast();
}

void FDAPDAUI::Toggle(EDAPDATab Tab)
{
	if (bOpen)
	{
		Close();
	}
	else
	{
		Open(Tab);
	}
}

void FDAPDAUI::SetTab(EDAPDATab Tab)
{
	const EDAPDATab NewTab = ClampTab(Tab);
	if (NewTab == ActiveTab && bOpen)
	{
		return;
	}
	ActiveTab = NewTab;
	Selection = 0;
	ListScroll = 0;
	HoveredRow = INDEX_NONE;
	RefreshViewModel();
	if (ActiveTab == EDAPDATab::Calendar)
	{
		for (int32 Index = 0; Index < ViewModel.Calendar.Days.Num(); ++Index)
		{
			if (ViewModel.Calendar.Days[Index].bToday)
			{
				Selection = Index;
				break;
			}
		}
	}
	RefreshRows();
	PlaySfx(TEXT("A_UIClick"), 0.4f);
	OnTabChanged.Broadcast(ActiveTab);
}

void FDAPDAUI::NextTab(int32 Delta)
{
	int32 Index = static_cast<int32>(ActiveTab) + Delta;
	Index %= DAPDATabCount;
	if (Index < 0)
	{
		Index += DAPDATabCount;
	}
	SetTab(static_cast<EDAPDATab>(Index));
}

const TCHAR* FDAPDAUI::TabFallback(EDAPDATab Tab)
{
	switch (Tab)
	{
	case EDAPDATab::Map:        return TEXT("MAP");
	case EDAPDATab::Calendar:   return TEXT("CALENDAR");
	case EDAPDATab::Deck:       return TEXT("DECK");
	case EDAPDATab::Mail:       return TEXT("MAIL");
	case EDAPDATab::Save:       return TEXT("SAVE");
	case EDAPDATab::Options:    return TEXT("OPTIONS");
	case EDAPDATab::Records:    return TEXT("RECORDS");
	case EDAPDATab::Limitation: return TEXT("LIMIT");
	default:                    return TEXT("?");
	}
}

const TCHAR* FDAPDAUI::TabSlug(EDAPDATab Tab)
{
	switch (Tab)
	{
	case EDAPDATab::Map:        return TEXT("map");
	case EDAPDATab::Calendar:   return TEXT("calendar");
	case EDAPDATab::Deck:       return TEXT("deck");
	case EDAPDATab::Mail:       return TEXT("mail");
	case EDAPDATab::Save:       return TEXT("save");
	case EDAPDATab::Options:    return TEXT("options");
	case EDAPDATab::Records:    return TEXT("records");
	case EDAPDATab::Limitation: return TEXT("limitation");
	default:                    return TEXT("unknown");
	}
}

FString FDAPDAUI::TabLabel(EDAPDATab Tab)
{
	return DAUIData::Label(FString::Printf(TEXT("pda.tab.%s"), TabSlug(Tab)), TabFallback(Tab));
}

// ------------------------------------------------------------------------ placeholder / live data

void FDAPDAUI::RefreshViewModel()
{
	BuildPlaceholderViewModel();
	if (ViewModelBuilder)
	{
		ViewModelBuilder(*this);
	}
	NormalizeViewModel();
}

void FDAPDAUI::BuildPlaceholderViewModel()
{
	APlayerController* PC = OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr;
	ADAStudentCharacter* Student = PC ? Cast<ADAStudentCharacter>(PC->GetPawn()) : nullptr;

	ViewModel = FDAPDAViewModel();
	ViewModel.Profile.bPlaceholder = true;
	ViewModel.Profile.Cards = Student ? Student->GetCollectionSize() : 0;
	if (Student)
	{
		ViewModel.Profile.DormName = DuelAcademy::DormName(Student->GetDorm());
	}

	// Calendar placeholder: October, Year 1, first day Sunday (GBA week order).
	ViewModel.Calendar = FDAPDACalendarView();
	ViewModel.Calendar.MonthName = DAUIData::Label(TEXT("pda.calendar.month"), TEXT("October"));
	ViewModel.Calendar.Year = 1;
	ViewModel.Calendar.FirstWeekday = 0;
	ViewModel.Calendar.bPlaceholder = true;
	for (int32 Day = 1; Day <= 31; ++Day)
	{
		FDAPDACalendarCell Cell;
		Cell.Day = Day;
		Cell.bExam = ((Day - 6) % 7 == 0); // Sample Fridays; A02 supplies the real exam days.
		Cell.bEvent = (Day == 7);
		Cell.bToday = (Day == 7);
		if (Cell.bExam)
		{
			Cell.Note = DAUIData::Label(TEXT("pda.calendar.exam"), TEXT("Sample exam day (placeholder)"));
		}
		else if (Cell.bEvent)
		{
			Cell.Note = DAUIData::Label(TEXT("pda.calendar.event"), TEXT("Sample event marker (placeholder)"));
		}
		ViewModel.Calendar.Days.Add(Cell);
	}

	// Deck tab: read the existing starter decks; A06 replaces this with player decks.
	UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	if (Cards)
	{
		for (const FStarterDeckDef& Def : Cards->GetDecks())
		{
			FDAPDADeckSummary Summary;
			Summary.Id = Def.Id;
			Summary.Name = Def.Name;
			Summary.Subtitle = Def.Subtitle;
			Summary.MainCount = Def.Cards.Num();
			Summary.ExtraCount = 0;
			Summary.bValid = true;
			Summary.Validation = TEXT("Starter deck - A06 validation pending");
			ViewModel.Deck.Decks.Add(Summary);
		}
	}
	ViewModel.Deck.Note = TEXT("Open the deck editor once A06's DADeckUI is connected.");

	// Save slots: three manual + autosave.
	for (int32 Slot = 1; Slot <= 3; ++Slot)
	{
		FDAPDASaveSlotView View;
		View.Id = FString::Printf(TEXT("slot_%d"), Slot);
		View.Label = FString::Printf(TEXT("SLOT %d"), Slot);
		View.Date = TEXT("Empty");
		View.bOccupied = false;
		ViewModel.SaveSlots.Add(View);
	}
	{
		FDAPDASaveSlotView View;
		View.Id = TEXT("autosave");
		View.Label = TEXT("AUTOSAVE");
		View.Date = TEXT("Empty");
		View.bOccupied = false;
		View.bAutosave = true;
		ViewModel.SaveSlots.Add(View);
	}

	// Options: only the two that the dialogue box can honour today.
	FDAPDAOptionRow TextSpeed;
	TextSpeed.Id = TEXT("text_speed");
	TextSpeed.Label = TEXT("Text Speed");
	TextSpeed.Values.Add(TEXT("Slow"));
	TextSpeed.Values.Add(TEXT("Normal"));
	TextSpeed.Values.Add(TEXT("Fast"));
	TextSpeed.ValueIndex = 1;
	TextSpeed.Help = TEXT("Applied to the dialogue box immediately. A02 owns persistence.");
	if (OwnerHUD.IsValid())
	{
		if (FDADialogueUI* Dialogue = OwnerHUD->GetDialogueUI())
		{
			const float Speed = Dialogue->GetTextSpeed();
			TextSpeed.ValueIndex = Speed < 35.f ? 0 : (Speed > 65.f ? 2 : 1);
		}
	}
	ViewModel.Options.Add(TextSpeed);

	FDAPDAOptionRow Auto;
	Auto.Id = TEXT("auto_advance");
	Auto.Label = TEXT("Auto-Advance");
	Auto.Values.Add(TEXT("Off"));
	Auto.Values.Add(TEXT("On"));
	Auto.ValueIndex = 0;
	Auto.Help = TEXT("Advances fully revealed dialogue lines automatically.");
	if (OwnerHUD.IsValid())
	{
		if (FDADialogueUI* Dialogue = OwnerHUD->GetDialogueUI())
		{
			Auto.ValueIndex = Dialogue->IsAutoAdvance() ? 1 : 0;
		}
	}
	ViewModel.Options.Add(Auto);

	// Records: live profile basics, placeholders for A02 counters.
	ViewModel.Records.Reset();
	auto AddRecord = [this](const TCHAR* Label, const FString& Value, bool bHighlight)
	{
		FDAPDARecordRow Row;
		Row.Label = Label;
		Row.Value = Value;
		Row.bHighlight = bHighlight;
		ViewModel.Records.Add(Row);
	};
	AddRecord(TEXT("Title"), ViewModel.Profile.TitleName, true);
	AddRecord(TEXT("Dorm"), ViewModel.Profile.DormName, false);
	AddRecord(TEXT("DP"), FString::Printf(TEXT("%d"), ViewModel.Profile.DP), true);
	AddRecord(TEXT("Cards Collected"), FString::Printf(TEXT("%d"), ViewModel.Profile.Cards), false);
	AddRecord(TEXT("Duels Won"), TEXT("0  (placeholder)"), false);
	AddRecord(TEXT("Timed Clears"), TEXT("0  (placeholder)"), false);

	ViewModel.FooterNote = DAUIData::Label(TEXT("pda.footer.placeholder"),
		TEXT("PDA shell - panes marked placeholder await A02/A03/A06/A07."));
}

void FDAPDAUI::NormalizeViewModel()
{
	if (ViewModel.Profile.PlayerName.IsEmpty())
	{
		ViewModel.Profile.PlayerName = TEXT("New Student");
	}
	if (ViewModel.Profile.DormName.IsEmpty())
	{
		ViewModel.Profile.DormName = TEXT("Slifer Red");
	}
	if (ViewModel.Profile.TitleName.IsEmpty())
	{
		ViewModel.Profile.TitleName = TEXT("Apprentice Duelist");
	}
	if (ViewModel.Calendar.Days.Num() == 0)
	{
		ViewModel.Calendar.MonthName = DAUIData::Label(TEXT("pda.calendar.month"), TEXT("October"));
		ViewModel.Calendar.Year = 1;
		ViewModel.Calendar.FirstWeekday = 0;
		for (int32 Day = 1; Day <= 31; ++Day)
		{
			FDAPDACalendarCell Cell;
			Cell.Day = Day;
			Cell.bExam = ((Day - 6) % 7 == 0);
			Cell.bEvent = (Day == 7);
			Cell.bToday = (Day == 7);
			ViewModel.Calendar.Days.Add(Cell);
		}
	}
	ViewModel.Calendar.FirstWeekday = FMath::Clamp(ViewModel.Calendar.FirstWeekday, 0, 6);
	if (ViewModel.Options.Num() == 0)
	{
		FDAPDAOptionRow TextSpeed;
		TextSpeed.Id = TEXT("text_speed");
		TextSpeed.Label = TEXT("Text Speed");
		TextSpeed.Values.Add(TEXT("Slow"));
		TextSpeed.Values.Add(TEXT("Normal"));
		TextSpeed.Values.Add(TEXT("Fast"));
		TextSpeed.ValueIndex = 1;
		ViewModel.Options.Add(TextSpeed);
	}
	if (ViewModel.SaveSlots.Num() == 0)
	{
		for (int32 Slot = 1; Slot <= 3; ++Slot)
		{
			FDAPDASaveSlotView View;
			View.Id = FString::Printf(TEXT("slot_%d"), Slot);
			View.Label = FString::Printf(TEXT("SLOT %d"), Slot);
			View.Date = TEXT("Empty");
			ViewModel.SaveSlots.Add(View);
		}
	}
}

void FDAPDAUI::RefreshRows()
{
	const int32 Count = RowCountForTab(ActiveTab);
	Selection = Count > 0 ? FMath::Clamp(Selection, 0, Count - 1) : 0;
	ListScroll = FMath::Clamp(ListScroll, 0, FMath::Max(0, Count - 1));
}

int32 FDAPDAUI::RowCountForTab(EDAPDATab Tab) const
{
	switch (Tab)
	{
	case EDAPDATab::Map:
	{
		const UDAIslandSubsystem* Sub = OwnerHUD.IsValid() ? UDAIslandSubsystem::Get(OwnerHUD.Get()) : nullptr;
		return Sub ? Sub->GetZones().Num() : 0;
	}
	case EDAPDATab::Calendar:   return ViewModel.Calendar.Days.Num();
	case EDAPDATab::Deck:       return ViewModel.Deck.Decks.Num();
	case EDAPDATab::Mail:       return ViewModel.Mail.Num();
	case EDAPDATab::Save:       return ViewModel.SaveSlots.Num();
	case EDAPDATab::Options:    return ViewModel.Options.Num();
	case EDAPDATab::Records:    return ViewModel.Records.Num();
	case EDAPDATab::Limitation: return ViewModel.Limitations.Num();
	default:                    return 0;
	}
}

FString FDAPDAUI::RowLabel(int32 Index, FString& OutSubtitle, FLinearColor& OutAccent, bool& bOutDisabled) const
{
	OutSubtitle.Reset();
	OutAccent = PdaGold;
	bOutDisabled = false;

	switch (ActiveTab)
	{
	case EDAPDATab::Map:
	{
		const UDAIslandSubsystem* Sub = OwnerHUD.IsValid() ? UDAIslandSubsystem::Get(OwnerHUD.Get()) : nullptr;
		const TArray<ADALocationVolume*> Zones = Sub ? Sub->GetZones() : TArray<ADALocationVolume*>();
		if (Zones.IsValidIndex(Index) && Zones[Index])
		{
			ADALocationVolume* Zone = Zones[Index];
			OutAccent = Zone->ThemeColor;
			const bool bDiscovered = Sub->IsDiscovered(Zone);
			OutSubtitle = bDiscovered ? Zone->Subtitle : FString(TEXT("Unexplored"));
			bOutDisabled = !Zone->bFastTravel;
			return Zone->DisplayName;
		}
		break;
	}
	case EDAPDATab::Calendar:
	{
		if (ViewModel.Calendar.Days.IsValidIndex(Index))
		{
			const FDAPDACalendarCell& Cell = ViewModel.Calendar.Days[Index];
			const int32 Weekday = (ViewModel.Calendar.FirstWeekday + Cell.Day - 1) % 7;
			OutSubtitle = Cell.Note.IsEmpty() ? FString(WeekdayShort(Weekday)) : Cell.Note;
			OutAccent = Cell.bExam ? PdaRed : (Cell.bEvent ? PdaGold : (Cell.bToday ? PdaCyan : PdaMuted));
			return FString::Printf(TEXT("%s %d"), WeekdayShort(Weekday), Cell.Day);
		}
		break;
	}
	case EDAPDATab::Deck:
	{
		if (ViewModel.Deck.Decks.IsValidIndex(Index))
		{
			const FDAPDADeckSummary& Deck = ViewModel.Deck.Decks[Index];
			OutSubtitle = FString::Printf(TEXT("%d cards  -  %s"), Deck.MainCount, *Deck.Validation);
			OutAccent = Deck.bValid ? PdaGreen : PdaRed;
			return Deck.Name;
		}
		break;
	}
	case EDAPDATab::Mail:
	{
		if (ViewModel.Mail.IsValidIndex(Index))
		{
			const FDAPDAMailView& Mail = ViewModel.Mail[Index];
			OutSubtitle = Mail.bRead ? Mail.From : FString::Printf(TEXT("%s  (unread)"), *Mail.From);
			OutAccent = Mail.bDuelRequest ? PdaRed : PdaCyan;
			return Mail.Subject.IsEmpty() ? FString(TEXT("(no subject)")) : Mail.Subject;
		}
		break;
	}
	case EDAPDATab::Save:
	{
		if (ViewModel.SaveSlots.IsValidIndex(Index))
		{
			const FDAPDASaveSlotView& Slot = ViewModel.SaveSlots[Index];
			OutSubtitle = Slot.bOccupied ? Slot.Date : FString(TEXT("Empty"));
			OutAccent = Slot.bAutosave ? PdaCyan : PdaGold;
			return Slot.Label;
		}
		break;
	}
	case EDAPDATab::Options:
	{
		if (ViewModel.Options.IsValidIndex(Index))
		{
			const FDAPDAOptionRow& Option = ViewModel.Options[Index];
			OutSubtitle = Option.Values.IsValidIndex(Option.ValueIndex) ? Option.Values[Option.ValueIndex] : FString();
			OutAccent = PdaCyan;
			return Option.Label;
		}
		break;
	}
	case EDAPDATab::Records:
	{
		if (ViewModel.Records.IsValidIndex(Index))
		{
			const FDAPDARecordRow& Record = ViewModel.Records[Index];
			OutSubtitle = Record.Value;
			OutAccent = Record.bHighlight ? PdaGold : PdaMuted;
			return Record.Label;
		}
		break;
	}
	case EDAPDATab::Limitation:
	{
		if (ViewModel.Limitations.IsValidIndex(Index))
		{
			const FDAPDALimitRow& Limit = ViewModel.Limitations[Index];
			OutSubtitle = Limit.Status;
			OutAccent = Limit.bBanned ? PdaRed : PdaGold;
			return Limit.CardName;
		}
		break;
	}
	default:
		break;
	}
	return FString();
}

FString FDAPDAUI::RowDetailTitle(int32 Index) const
{
	switch (ActiveTab)
	{
	case EDAPDATab::Map:
	{
		const UDAIslandSubsystem* Sub = OwnerHUD.IsValid() ? UDAIslandSubsystem::Get(OwnerHUD.Get()) : nullptr;
		const TArray<ADALocationVolume*> Zones = Sub ? Sub->GetZones() : TArray<ADALocationVolume*>();
		return Zones.IsValidIndex(Index) && Zones[Index] ? Zones[Index]->DisplayName : FString();
	}
	case EDAPDATab::Calendar:
		if (ViewModel.Calendar.Days.IsValidIndex(Index))
		{
			return FString::Printf(TEXT("%s %d"), *ViewModel.Calendar.MonthName, ViewModel.Calendar.Days[Index].Day);
		}
		break;
	case EDAPDATab::Deck:
		return ViewModel.Deck.Decks.IsValidIndex(Index) ? ViewModel.Deck.Decks[Index].Name : FString();
	case EDAPDATab::Mail:
		return ViewModel.Mail.IsValidIndex(Index) ? ViewModel.Mail[Index].Subject : FString();
	case EDAPDATab::Save:
		return ViewModel.SaveSlots.IsValidIndex(Index) ? ViewModel.SaveSlots[Index].Label : FString();
	case EDAPDATab::Options:
		return ViewModel.Options.IsValidIndex(Index) ? ViewModel.Options[Index].Label : FString();
	case EDAPDATab::Records:
		return ViewModel.Records.IsValidIndex(Index) ? ViewModel.Records[Index].Label : FString();
	case EDAPDATab::Limitation:
		return ViewModel.Limitations.IsValidIndex(Index) ? ViewModel.Limitations[Index].CardName : FString();
	default:
		break;
	}
	return FString();
}

FString FDAPDAUI::RowDetailBody(int32 Index) const
{
	switch (ActiveTab)
	{
	case EDAPDATab::Map:
	{
		const UDAIslandSubsystem* Sub = OwnerHUD.IsValid() ? UDAIslandSubsystem::Get(OwnerHUD.Get()) : nullptr;
		const TArray<ADALocationVolume*> Zones = Sub ? Sub->GetZones() : TArray<ADALocationVolume*>();
		if (Zones.IsValidIndex(Index) && Zones[Index])
		{
			ADALocationVolume* Zone = Zones[Index];
			FString Body = Zone->Subtitle;
			if (!Zone->Description.IsEmpty())
			{
				Body += TEXT("\n\n") + Zone->Description;
			}
			if (Zone->bFastTravel)
			{
				Body += TEXT("\n\nEnter: fast travel to this location.");
			}
			else
			{
				Body += TEXT("\n\nThis location cannot be fast-travelled to.");
			}
			return Body;
		}
		break;
	}
	case EDAPDATab::Calendar:
	{
		if (ViewModel.Calendar.Days.IsValidIndex(Index))
		{
			const FDAPDACalendarCell& Cell = ViewModel.Calendar.Days[Index];
			const int32 Weekday = (ViewModel.Calendar.FirstWeekday + Cell.Day - 1) % 7;
			FString Body = FString::Printf(TEXT("%s, %s %d, Year %d"),
				WeekdayShort(Weekday), *ViewModel.Calendar.MonthName, Cell.Day, ViewModel.Calendar.Year);
			if (!Cell.Note.IsEmpty())
			{
				Body += TEXT("\n\n") + Cell.Note;
			}
			if (Cell.bExam)
			{
				Body += TEXT("\nExam days are Fridays in the GBA calendar.");
			}
			if (ViewModel.Calendar.bPlaceholder)
			{
				Body += TEXT("\n\nCalendar data is a placeholder until A02's CalendarSubsystem is connected.");
			}
			return Body;
		}
		break;
	}
	case EDAPDATab::Deck:
	{
		if (ViewModel.Deck.Decks.IsValidIndex(Index))
		{
			const FDAPDADeckSummary& Deck = ViewModel.Deck.Decks[Index];
			FString Body = Deck.Subtitle;
			Body += FString::Printf(TEXT("\n\nMain Deck: %d\nExtra Deck: %d\nStatus: %s"),
				Deck.MainCount, Deck.ExtraCount, *Deck.Validation);
			Body += TEXT("\n\nEnter: open the deck editor hook (A06).");
			return Body;
		}
		break;
	}
	case EDAPDATab::Mail:
	{
		if (ViewModel.Mail.IsValidIndex(Index))
		{
			const FDAPDAMailView& Mail = ViewModel.Mail[Index];
			FString Body;
			if (!Mail.From.IsEmpty())
			{
				Body += FString::Printf(TEXT("From: %s"), *Mail.From);
			}
			if (!Mail.Date.IsEmpty())
			{
				Body += FString::Printf(TEXT("\nDate: %s"), *Mail.Date);
			}
			Body += TEXT("\n\n");
			Body += Mail.Body.IsEmpty() ? Mail.Preview : Mail.Body;
			if (Mail.bDuelRequest)
			{
				Body += TEXT("\n\nDuel request - accept via A03's mailbox.");
			}
			return Body;
		}
		break;
	}
	case EDAPDATab::Save:
	{
		if (ViewModel.SaveSlots.IsValidIndex(Index))
		{
			const FDAPDASaveSlotView& Slot = ViewModel.SaveSlots[Index];
			FString Body;
			if (Slot.bOccupied)
			{
				Body = FString::Printf(TEXT("%s\n%s\n%s\nDP %d"), *Slot.Date, *Slot.Dorm, *Slot.Title, Slot.DP);
			}
			else
			{
				Body = TEXT("Empty slot.");
			}
			Body += TEXT("\n\nSave/load is handled by A02's SaveSubsystem; this shell emits save.slot.");
			return Body;
		}
		break;
	}
	case EDAPDATab::Options:
	{
		if (ViewModel.Options.IsValidIndex(Index))
		{
			const FDAPDAOptionRow& Option = ViewModel.Options[Index];
			const FString Value = Option.Values.IsValidIndex(Option.ValueIndex) ? Option.Values[Option.ValueIndex] : FString();
			return FString::Printf(TEXT("Current: %s\n\n%s\n\nEnter / click: cycle value."), *Value, *Option.Help);
		}
		break;
	}
	case EDAPDATab::Records:
	{
		if (ViewModel.Records.IsValidIndex(Index))
		{
			return ViewModel.Records[Index].Value;
		}
		break;
	}
	case EDAPDATab::Limitation:
	{
		if (ViewModel.Limitations.IsValidIndex(Index))
		{
			return ViewModel.Limitations[Index].Status;
		}
		break;
	}
	default:
		break;
	}
	return FString();
}

// ------------------------------------------------------------------------ update

void FDAPDAUI::Update(float DeltaSeconds)
{
	if (!bOpen)
	{
		return;
	}
	PlayerOwner = OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr;
	Elapsed += DeltaSeconds;
	if (!PlayerOwner)
	{
		return;
	}

	// Hovered tab/row from last frame's hit targets.
	HoveredTab = INDEX_NONE;
	HoveredRow = INDEX_NONE;
	float MouseX = -1.f;
	float MouseY = -1.f;
	if (PlayerOwner->GetMousePosition(MouseX, MouseY))
	{
		const FVector2D Mouse(MouseX, MouseY);
		for (const FDAPDAHitTarget& Hit : HitTargets)
		{
			if (!Hit.Contains(Mouse))
			{
				continue;
			}
			if (Hit.Action == TEXT("tab"))
			{
				HoveredTab = Hit.Index;
			}
			else if (Hit.Action == TEXT("row"))
			{
				HoveredRow = Hit.Index;
			}
		}
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
	{
		Close();
		return;
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Q)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Left)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_LeftShoulder))
	{
		NextTab(-1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::E)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Right)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_RightShoulder))
	{
		NextTab(1);
	}

	static const FKey TabKeys[] = {
		EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four,
		EKeys::Five, EKeys::Six, EKeys::Seven, EKeys::Eight
	};
	for (int32 Index = 0; Index < UE_ARRAY_COUNT(TabKeys); ++Index)
	{
		if (PlayerOwner->WasInputKeyJustPressed(TabKeys[Index]))
		{
			SetTab(static_cast<EDAPDATab>(Index));
		}
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Up) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Up)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::W))
	{
		MoveSelection(-1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Down) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::S))
	{
		MoveSelection(1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
	{
		ActivateSelection();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
	{
		HandleClickAtMouse();
	}
}

void FDAPDAUI::MoveSelection(int32 Delta)
{
	const int32 Count = RowCountForTab(ActiveTab);
	if (Count <= 0)
	{
		Selection = 0;
		return;
	}
	const int32 NewSelection = FMath::Clamp(Selection + Delta, 0, Count - 1);
	if (NewSelection != Selection)
	{
		Selection = NewSelection;
		PlaySfx(TEXT("A_UIClick"), 0.3f);
	}
}

bool FDAPDAUI::ActivateSelection()
{
	const int32 Count = RowCountForTab(ActiveTab);
	if (!bOpen || Count <= 0 || Selection < 0 || Selection >= Count)
	{
		return false;
	}
	ActivateRow(Selection);
	return true;
}

void FDAPDAUI::SetSelection(int32 InSelection)
{
	const int32 Count = RowCountForTab(ActiveTab);
	Selection = Count > 0 ? FMath::Clamp(InSelection, 0, Count - 1) : 0;
}

void FDAPDAUI::ActivateRow(int32 Index)
{
	if (!IsOpen())
	{
		return;
	}
	PlaySfx(TEXT("A_UIClick"), 0.55f);

	switch (ActiveTab)
	{
	case EDAPDATab::Map:
	{
		const UDAIslandSubsystem* Sub = OwnerHUD.IsValid() ? UDAIslandSubsystem::Get(OwnerHUD.Get()) : nullptr;
		const TArray<ADALocationVolume*> Zones = Sub ? Sub->GetZones() : TArray<ADALocationVolume*>();
		if (!Zones.IsValidIndex(Index) || !Zones[Index])
		{
			return;
		}
		ADALocationVolume* Zone = Zones[Index];
		OnAction.Broadcast(FName(TEXT("map.travel")), Zone->DisplayName);
		if (!Zone->bFastTravel)
		{
			ViewModel.FooterNote = TEXT("This location cannot be fast-travelled to.");
			return;
		}
		if (ADAHUD* HUD = OwnerHUD.Get())
		{
			HUD->ClosePDA();
		}
		APlayerController* PC = PlayerOwner ? PlayerOwner : (OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr);
		if (ADAStudentCharacter* Student = PC ? Cast<ADAStudentCharacter>(PC->GetPawn()) : nullptr)
		{
			Student->FastTravelTo(Zone);
		}
		return;
	}
	case EDAPDATab::Calendar:
	{
		if (!ViewModel.Calendar.Days.IsValidIndex(Index))
		{
			return;
		}
		OnAction.Broadcast(FName(TEXT("calendar.select")),
			FString::FromInt(ViewModel.Calendar.Days[Index].Day));
		return;
	}
	case EDAPDATab::Deck:
	{
		if (!ViewModel.Deck.Decks.IsValidIndex(Index))
		{
			return;
		}
		OnAction.Broadcast(FName(TEXT("deck.open")), ViewModel.Deck.Decks[Index].Id);
		return;
	}
	case EDAPDATab::Mail:
	{
		if (!ViewModel.Mail.IsValidIndex(Index))
		{
			return;
		}
		FDAPDAMailView& Mail = ViewModel.Mail[Index];
		Mail.bRead = true;
		OnAction.Broadcast(FName(TEXT("mail.open")), Mail.Id);
		return;
	}
	case EDAPDATab::Save:
	{
		if (!ViewModel.SaveSlots.IsValidIndex(Index))
		{
			return;
		}
		OnAction.Broadcast(FName(TEXT("save.slot")), ViewModel.SaveSlots[Index].Id);
		return;
	}
	case EDAPDATab::Options:
	{
		if (!ViewModel.Options.IsValidIndex(Index))
		{
			return;
		}
		FDAPDAOptionRow& Option = ViewModel.Options[Index];
		if (Option.Values.Num() > 0)
		{
			Option.ValueIndex = (Option.ValueIndex + 1) % Option.Values.Num();
			const FString Value = Option.Values[Option.ValueIndex];
			OnAction.Broadcast(FName(TEXT("options.changed")),
				FString::Printf(TEXT("%s=%s"), *Option.Id, *Value));
		}
		return;
	}
	case EDAPDATab::Records:
	{
		if (ViewModel.Records.IsValidIndex(Index))
		{
			OnAction.Broadcast(FName(TEXT("records.row")), ViewModel.Records[Index].Label);
		}
		return;
	}
	case EDAPDATab::Limitation:
	{
		if (ViewModel.Limitations.IsValidIndex(Index))
		{
			OnAction.Broadcast(FName(TEXT("limitation.row")), ViewModel.Limitations[Index].CardName);
		}
		return;
	}
	default:
		return;
	}
}

void FDAPDAUI::HandleClickAtMouse()
{
	if (!PlayerOwner)
	{
		return;
	}
	float MouseX = -1.f;
	float MouseY = -1.f;
	if (!PlayerOwner->GetMousePosition(MouseX, MouseY))
	{
		return;
	}
	const FVector2D Mouse(MouseX, MouseY);
	for (int32 Index = HitTargets.Num() - 1; Index >= 0; --Index)
	{
		if (HitTargets[Index].Contains(Mouse))
		{
			HandleHit(HitTargets[Index]);
			return;
		}
	}
}

void FDAPDAUI::HandleHit(const FDAPDAHitTarget& Hit)
{
	if (Hit.Action == TEXT("tab"))
	{
		SetTab(static_cast<EDAPDATab>(Hit.Index));
	}
	else if (Hit.Action == TEXT("row"))
	{
		SetSelection(Hit.Index);
		ActivateRow(Hit.Index);
	}
	else if (Hit.Action == TEXT("calendar.day"))
	{
		SetSelection(Hit.Index);
		if (ViewModel.Calendar.Days.IsValidIndex(Hit.Index))
		{
			OnAction.Broadcast(FName(TEXT("calendar.select")),
				FString::FromInt(ViewModel.Calendar.Days[Hit.Index].Day));
		}
	}
	else if (Hit.Action == TEXT("close"))
	{
		Close();
	}
}

// ------------------------------------------------------------------------ drawing helpers

void FDAPDAUI::AddHit(const FString& Action, int32 Index, float X, float Y, float W, float H, const FString& Payload)
{
	FDAPDAHitTarget Hit;
	Hit.Action = Action;
	Hit.Index = Index;
	Hit.X = X;
	Hit.Y = Y;
	Hit.W = W;
	Hit.H = H;
	Hit.Payload = Payload;
	HitTargets.Add(MoveTemp(Hit));
}

void FDAPDAUI::DrawRect(const FLinearColor& Color, float X, float Y, float W, float H)
{
	if (!Canvas || W <= 0.f || H <= 0.f)
	{
		return;
	}
	FCanvasTileItem Tile(FVector2D(X, Y), GWhiteTexture, FVector2D(W, H), Color);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void FDAPDAUI::DrawText(const FString& Str, float X, float Y, const FLinearColor& Color, float InScale,
	bool bCenter, UFont* Font)
{
	if (!Canvas || Str.IsEmpty())
	{
		return;
	}
	UFont* F = Font ? Font : GetFont(false);
	if (!F)
	{
		return;
	}
	FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(Str), F, Color);
	Item.Scale = FVector2D(InScale * UIScale, InScale * UIScale);
	Item.bCentreX = bCenter;
	Item.EnableShadow(FLinearColor(0.f, 0.f, 0.f, 0.8f * Color.A), FVector2D(1.2f * UIScale, 1.2f * UIScale));
	Canvas->DrawItem(Item);
}

void FDAPDAUI::DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent)
{
	DrawRect(Fill, X, Y, W, H);
	DrawRect(WithAlpha(Accent, 0.95f), X, Y, 3.f * UIScale, H);
	DrawRect(WithAlpha(Accent, 0.35f), X, Y, W, 1.f * UIScale);
}

void FDAPDAUI::Diamond(const FVector2D& C, float R, const FLinearColor& Color)
{
	if (!Canvas)
	{
		return;
	}
	const FVector2D T(C.X, C.Y - R);
	const FVector2D B(C.X, C.Y + R);
	const FVector2D L(C.X - R, C.Y);
	const FVector2D Rt(C.X + R, C.Y);

	FCanvasTriangleItem Tri1(T, Rt, B, GWhiteTexture);
	Tri1.SetColor(Color);
	Tri1.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tri1);

	FCanvasTriangleItem Tri2(T, B, L, GWhiteTexture);
	Tri2.SetColor(Color);
	Tri2.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tri2);
}

FVector2D FDAPDAUI::Measure(const FString& Str, float InScale, UFont* Font) const
{
	const UFont* F = Font ? Font : GetFont(false);
	if (!F || Str.IsEmpty())
	{
		return FVector2D::ZeroVector;
	}
	const float K = InScale * UIScale;
	return FVector2D(F->GetStringSize(*Str) * K, F->GetStringHeightSize(*Str) * K);
}

TArray<FString> FDAPDAUI::WrapText(const FString& Str, float MaxWidth, float InScale, UFont* Font) const
{
	TArray<FString> Out;
	TArray<FString> Paragraphs;
	Str.ParseIntoArray(Paragraphs, TEXT("\n"), false);
	for (const FString& Para : Paragraphs)
	{
		TArray<FString> Words;
		Para.ParseIntoArray(Words, TEXT(" "), true);
		FString Line;
		for (const FString& Word : Words)
		{
			const FString Candidate = Line.IsEmpty() ? Word : Line + TEXT(" ") + Word;
			if (!Line.IsEmpty() && Measure(Candidate, InScale, Font).X > MaxWidth)
			{
				Out.Add(Line);
				Line = Word;
			}
			else
			{
				Line = Candidate;
			}
		}
		Out.Add(Line);
	}
	return Out;
}

void FDAPDAUI::EnsureSelectionVisible(int32 VisibleRows)
{
	if (VisibleRows <= 0)
	{
		return;
	}
	if (Selection < ListScroll)
	{
		ListScroll = Selection;
	}
	else if (Selection >= ListScroll + VisibleRows)
	{
		ListScroll = Selection - VisibleRows + 1;
	}
	const int32 Count = RowCountForTab(ActiveTab);
	ListScroll = FMath::Clamp(ListScroll, 0, FMath::Max(0, Count - VisibleRows));
}

// ------------------------------------------------------------------------ draw

void FDAPDAUI::Draw(UCanvas* InCanvas)
{
	if (!bOpen || !InCanvas)
	{
		return;
	}
	Canvas = InCanvas;
	UIScale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.6f, 2.5f);
	HitTargets.Reset();

	DrawRect(FLinearColor(0.004f, 0.01f, 0.022f, 0.94f), 0.f, 0.f, Canvas->ClipX, Canvas->ClipY);
	DrawHeader();
	DrawTabBar();
	DrawContent();
	DrawFooter();
}

void FDAPDAUI::DrawHeader()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float H = 86.f * S;
	DrawRect(FLinearColor(0.012f, 0.022f, 0.04f, 0.96f), 0.f, 0.f, CW, H);
	DrawRect(WithAlpha(PdaGold, 0.55f), 0.f, H - 2.f * S, CW, 2.f * S);

	const FString Title = DAUIData::Label(TEXT("pda.title"), TEXT("DUEL ACADEMY PDA"));
	DrawText(Title, 32.f * S, 12.f * S, PdaGold, 1.6f, false, GetFont(true));
	DrawText(DAUIData::Label(TEXT("pda.subtitle"), TEXT("STUDENT TERMINAL")), 34.f * S, 52.f * S,
		WithAlpha(PdaMuted, 0.9f), 0.72f);

	const FDAPDAProfileView& Profile = ViewModel.Profile;
	const FString Line1 = FString::Printf(TEXT("%s  -  %s"), *Profile.PlayerName, *Profile.DormName);
	const FString Line2 = Profile.TitleName;
	const FString Line3 = FString::Printf(TEXT("DP %d    %s    %s"), Profile.DP, *Profile.DateLine, *Profile.Period);

	const float RightX = CW - 32.f * S;
	auto RightText = [&](const FString& Str, float Y, const FLinearColor& Color, float Scale, UFont* Font)
	{
		const FVector2D Size = Measure(Str, Scale, Font);
		DrawText(Str, RightX - Size.X, Y, Color, Scale, false, Font);
	};
	RightText(Line1, 10.f * S, PdaPaper, 1.0f, GetFont(true));
	RightText(Line2, 36.f * S, PdaGold, 0.82f, nullptr);
	RightText(Line3, 58.f * S, WithAlpha(PdaMuted, 0.95f), 0.72f, nullptr);
}

void FDAPDAUI::DrawTabBar()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float Y = 86.f * S;
	const float H = 48.f * S;
	const float Margin = 32.f * S;
	const float TabW = (CW - Margin * 2.f) / static_cast<float>(DAPDATabCount);

	DrawRect(FLinearColor(0.008f, 0.016f, 0.03f, 0.9f), 0.f, Y, CW, H);
	for (int32 Index = 0; Index < DAPDATabCount; ++Index)
	{
		const EDAPDATab Tab = static_cast<EDAPDATab>(Index);
		const bool bSelected = Tab == ActiveTab;
		const bool bHovered = Index == HoveredTab;
		const float X = Margin + Index * TabW;
		if (bSelected)
		{
			DrawRect(WithAlpha(PdaGold, 0.20f), X + 2.f * S, Y + 4.f * S, TabW - 4.f * S, H - 8.f * S);
			DrawRect(WithAlpha(PdaGold, 0.95f), X + 2.f * S, Y + H - 3.f * S, TabW - 4.f * S, 3.f * S);
		}
		else if (bHovered)
		{
			DrawRect(WithAlpha(PdaGold, 0.08f), X + 2.f * S, Y + 4.f * S, TabW - 4.f * S, H - 8.f * S);
		}
		DrawText(TabLabel(Tab), X + TabW * 0.5f, Y + 14.f * S,
			bSelected ? PdaGold : WithAlpha(PdaPaper, 0.72f), 0.78f, true);
		AddHit(TEXT("tab"), Index, X, Y, TabW, H);
	}
	DrawRect(WithAlpha(PdaMuted, 0.25f), 0.f, Y + H, CW, 1.f * S);
}

void FDAPDAUI::DrawContent()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float ContentY = 144.f * S;
	const float ContentH = CH - ContentY - 44.f * S;
	const float Margin = 32.f * S;
	const float Gap = 18.f * S;
	const float LeftW = (CW - Margin * 2.f - Gap) * 0.38f;
	const float LeftX = Margin;
	const float RightX = LeftX + LeftW + Gap;
	const float RightW = CW - RightX - Margin;

	DrawListPanel(LeftX, ContentY, LeftW, ContentH);
	DrawDetailPanel(RightX, ContentY, RightW, ContentH);
}

void FDAPDAUI::DrawListPanel(float X, float Y, float W, float H)
{
	const float S = UIScale;
	DrawPanel(X, Y, W, H, WithAlpha(PdaInk, 0.9f), WithAlpha(PdaGold, 0.7f));

	const int32 Count = RowCountForTab(ActiveTab);
	const FString Title = TabLabel(ActiveTab);
	DrawText(Title, X + 20.f * S, Y + 14.f * S, PdaGold, 1.05f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%d"), Count), X + W - 46.f * S, Y + 18.f * S,
		WithAlpha(PdaMuted, 0.9f), 0.8f);
	DrawRect(WithAlpha(PdaMuted, 0.3f), X + 20.f * S, Y + 44.f * S, W - 40.f * S, 1.f * S);

	const float RowH = 46.f * S;
	const float Top = Y + 54.f * S;
	const int32 VisibleRows = FMath::Max(1, FMath::FloorToInt((H - 64.f * S) / RowH));
	EnsureSelectionVisible(VisibleRows);

	if (Count == 0)
	{
		const FString Empty = DAUIData::Label(TEXT("pda.empty"), TEXT("No entries yet."));
		DrawText(Empty, X + 20.f * S, Top + 8.f * S, WithAlpha(PdaMuted, 0.9f), 0.9f);
		const FString Note = ActiveTab == EDAPDATab::Mail
			? FString(TEXT("Contacts and messages arrive with A03's mailbox."))
			: (ActiveTab == EDAPDATab::Limitation
				? FString(TEXT("The banned/limited list arrives with A01/A07 data."))
				: ViewModel.FooterNote);
		float NoteY = Top + 42.f * S;
		for (const FString& Line : WrapText(Note, W - 40.f * S, 0.75f))
		{
			DrawText(Line, X + 20.f * S, NoteY, WithAlpha(PdaMuted, 0.7f), 0.75f);
			NoteY += Measure(TEXT("Ag"), 0.75f).Y + 4.f * S;
		}
		return;
	}

	for (int32 Index = ListScroll; Index < Count && Index < ListScroll + VisibleRows; ++Index)
	{
		FString Subtitle;
		FLinearColor Accent = PdaGold;
		bool bDisabled = false;
		const FString Label = RowLabel(Index, Subtitle, Accent, bDisabled);
		const float RY = Top + (Index - ListScroll) * RowH;
		const bool bSelected = Index == Selection;
		const bool bHovered = Index == HoveredRow;

		if (bSelected)
		{
			DrawRect(WithAlpha(Accent, 0.26f), X + 10.f * S, RY, W - 20.f * S, RowH - 4.f * S);
		}
		else if (bHovered)
		{
			DrawRect(WithAlpha(Accent, 0.12f), X + 10.f * S, RY, W - 20.f * S, RowH - 4.f * S);
		}
		DrawRect(WithAlpha(Accent, bDisabled ? 0.4f : 1.f), X + 10.f * S, RY, 4.f * S, RowH - 4.f * S);
		DrawText(Label, X + 24.f * S, RY + 5.f * S,
			bDisabled ? WithAlpha(PdaMuted, 0.8f) : (bSelected ? PdaPaper : WithAlpha(PdaPaper, 0.88f)), 0.92f);
		if (!Subtitle.IsEmpty())
		{
			DrawText(Subtitle, X + 24.f * S, RY + 25.f * S, WithAlpha(PdaMuted, 0.9f), 0.68f);
		}
		AddHit(TEXT("row"), Index, X + 10.f * S, RY, W - 20.f * S, RowH - 4.f * S);
	}

	if (Count > VisibleRows)
	{
		const float TrackY = Top;
		const float TrackH = VisibleRows * RowH - 8.f * S;
		const float ThumbH = FMath::Max(24.f * S, TrackH * static_cast<float>(VisibleRows) / static_cast<float>(Count));
		const int32 MaxScroll = FMath::Max(1, Count - VisibleRows);
		const float ThumbY = TrackY + (TrackH - ThumbH) * static_cast<float>(ListScroll) / static_cast<float>(MaxScroll);
		DrawRect(WithAlpha(PdaMuted, 0.18f), X + W - 10.f * S, TrackY, 3.f * S, TrackH);
		DrawRect(WithAlpha(PdaGold, 0.8f), X + W - 10.f * S, ThumbY, 3.f * S, ThumbH);
	}
}

void FDAPDAUI::DrawDetailPanel(float X, float Y, float W, float H)
{
	const float S = UIScale;
	DrawPanel(X, Y, W, H, WithAlpha(PdaInk, 0.82f), WithAlpha(PdaMuted, 0.4f));

	const int32 Count = RowCountForTab(ActiveTab);
	const FString Title = (Count > 0) ? RowDetailTitle(Selection) : TabLabel(ActiveTab);
	DrawText(Title, X + 24.f * S, Y + 18.f * S, PdaGold, 1.35f, false, GetFont(true));
	DrawRect(WithAlpha(PdaGold, 0.35f), X + 24.f * S, Y + 56.f * S, W - 48.f * S, 1.f * S);

	if (ActiveTab == EDAPDATab::Calendar)
	{
		DrawCalendarGrid(X + 24.f * S, Y + 72.f * S, W - 48.f * S, H - 100.f * S);
		return;
	}

	if (Count == 0 || Selection < 0 || Selection >= Count)
	{
		FString Empty = ActiveTab == EDAPDATab::Deck ? ViewModel.Deck.Note : FString();
		if (Empty.IsEmpty())
		{
			Empty = DAUIData::Label(TEXT("pda.detail.empty"), TEXT("No data connected yet."));
		}
		DrawText(Empty, X + 24.f * S, Y + 78.f * S, WithAlpha(PdaMuted, 0.9f), 0.9f);
		return;
	}

	const FString Body = RowDetailBody(Selection);
	float TextY = Y + 74.f * S;
	const float LineH = Measure(TEXT("Ag"), 0.92f).Y + 4.f * S;
	const float MaxY = Y + H - 34.f * S;
	for (const FString& Line : WrapText(Body, W - 48.f * S, 0.92f))
	{
		if (TextY + LineH > MaxY)
		{
			DrawText(TEXT("..."), X + 24.f * S, TextY, WithAlpha(PdaMuted, 0.8f), 0.92f);
			break;
		}
		DrawText(Line, X + 24.f * S, TextY, PdaPaper, 0.92f);
		TextY += LineH;
	}

	// Footer action hint per tab.
	FString Hint;
	switch (ActiveTab)
	{
	case EDAPDATab::Map:       Hint = TEXT("Enter / click: fast travel"); break;
	case EDAPDATab::Deck:      Hint = TEXT("Enter / click: open deck editor hook (A06)"); break;
	case EDAPDATab::Mail:      Hint = TEXT("Enter / click: read message (A03 hook)"); break;
	case EDAPDATab::Save:      Hint = TEXT("Enter / click: save/load slot (A02 hook)"); break;
	case EDAPDATab::Options:   Hint = TEXT("Enter / click: cycle value"); break;
	case EDAPDATab::Records:   Hint = TEXT("A02/A07 counters will replace the placeholders"); break;
	case EDAPDATab::Limitation: Hint = TEXT("A01/A07 limitation data will populate this list"); break;
	default:                   Hint = FString(); break;
	}
	if (!Hint.IsEmpty())
	{
		DrawText(Hint, X + 24.f * S, Y + H - 28.f * S, WithAlpha(PdaMuted, 0.75f), 0.72f);
	}
}

void FDAPDAUI::DrawCalendarGrid(float X, float Y, float W, float H)
{
	const float S = UIScale;
	const float HeaderH = 22.f * S;

	for (int32 Column = 0; Column < 7; ++Column)
	{
		DrawText(WeekdayShort(Column), X + (Column + 0.5f) * (W / 7.f), Y,
			WithAlpha(PdaMuted, 0.9f), 0.68f, true);
	}

	const float GridY = Y + HeaderH + 6.f * S;
	const float CellW = W / 7.f;
	const float CellH = FMath::Clamp((H - HeaderH - 90.f * S) / 6.f, 44.f * S, 90.f * S);
	const float Gap = 2.f * S;

	for (int32 GridIndex = 0; GridIndex < 42; ++GridIndex)
	{
		const int32 DayIndex = GridIndex - ViewModel.Calendar.FirstWeekday;
		if (!ViewModel.Calendar.Days.IsValidIndex(DayIndex))
		{
			continue;
		}
		const FDAPDACalendarCell& Cell = ViewModel.Calendar.Days[DayIndex];
		const int32 Row = GridIndex / 7;
		const int32 Column = GridIndex % 7;
		const float CX = X + Column * CellW;
		const float CY = GridY + Row * CellH;
		const bool bSelected = DayIndex == Selection;

		FLinearColor Accent = PdaMuted;
		if (Cell.bExam)
		{
			Accent = PdaRed;
		}
		else if (Cell.bEvent)
		{
			Accent = PdaGold;
		}
		else if (Cell.bToday)
		{
			Accent = PdaCyan;
		}

		DrawRect(WithAlpha(Accent, bSelected ? 0.35f : 0.10f), CX + Gap, CY + Gap,
			CellW - Gap * 2.f, CellH - Gap * 2.f);
		if (Cell.bToday)
		{
			DrawRect(WithAlpha(PdaCyan, 0.9f), CX + Gap, CY + Gap, CellW - Gap * 2.f, 2.f * S);
		}
		DrawText(FString::FromInt(Cell.Day), CX + 10.f * S, CY + 8.f * S,
			bSelected ? PdaPaper : WithAlpha(PdaPaper, 0.85f), 0.9f, false, GetFont(true));
		if (Cell.bExam || Cell.bEvent)
		{
			DrawRect(WithAlpha(Accent, 0.95f), CX + CellW - 16.f * S, CY + CellH - 14.f * S, 6.f * S, 6.f * S);
		}
		AddHit(TEXT("calendar.day"), DayIndex, CX + Gap, CY + Gap, CellW - Gap * 2.f, CellH - Gap * 2.f);
	}

	// Legend + placeholder note.
	const float LegendY = GridY + 6.f * CellH + 10.f * S;
	DrawRect(WithAlpha(PdaRed, 0.95f), X, LegendY + 2.f * S, 8.f * S, 8.f * S);
	DrawText(TEXT("EXAM"), X + 14.f * S, LegendY, WithAlpha(PdaPaper, 0.8f), 0.68f);
	DrawRect(WithAlpha(PdaGold, 0.95f), X + 92.f * S, LegendY + 2.f * S, 8.f * S, 8.f * S);
	DrawText(TEXT("EVENT"), X + 106.f * S, LegendY, WithAlpha(PdaPaper, 0.8f), 0.68f);
	DrawRect(WithAlpha(PdaCyan, 0.95f), X + 190.f * S, LegendY + 2.f * S, 8.f * S, 8.f * S);
	DrawText(TEXT("TODAY"), X + 204.f * S, LegendY, WithAlpha(PdaPaper, 0.8f), 0.68f);

	if (ViewModel.Calendar.bPlaceholder)
	{
		DrawText(TEXT("Sample month - A02 replaces this with the live calendar."),
			X, LegendY + 26.f * S, WithAlpha(PdaMuted, 0.8f), 0.72f);
	}
}

void FDAPDAUI::DrawFooter()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float H = 34.f * S;
	DrawRect(FLinearColor(0.006f, 0.012f, 0.024f, 0.92f), 0.f, CH - H, CW, H);
	DrawRect(WithAlpha(PdaMuted, 0.25f), 0.f, CH - H, CW, 1.f * S);

	const FString Hints = DAUIData::Label(TEXT("pda.footer.hints"),
		TEXT("Q / E or 1-8: tabs    Up / Down: select    Enter: activate    P / Esc: close"));
	DrawText(Hints, 32.f * S, CH - H + 9.f * S, WithAlpha(PdaPaper, 0.78f), 0.72f);

	FString Note = ViewModel.FooterNote;
	const float MaxW = CW * 0.34f;
	while (Note.Len() > 4 && Measure(Note, 0.62f).X > MaxW)
	{
		Note = Note.LeftChop(4) + TEXT("...");
	}
	if (!Note.IsEmpty())
	{
		const FVector2D Size = Measure(Note, 0.62f);
		DrawText(Note, CW - 32.f * S - Size.X, CH - H + 11.f * S, WithAlpha(PdaMuted, 0.65f), 0.62f);
	}
}
