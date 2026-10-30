// Duel Academy Island - title / new game / continue overlay implementation.

#include "DATitleScreen.h"

#include "CanvasItem.h"
#include "DACalendarSubsystem.h"
#include "DADialogueUI.h"
#include "DAHUD.h"
#include "DAIslandSubsystem.h"
#include "DASaveGame.h"
#include "DASettings.h"
#include "DuelAcademyIsland.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/App.h"
#include "Misc/EngineVersion.h"
#include "RenderUtils.h"

namespace
{
	const FLinearColor TitleGold(1.f, 0.78f, 0.25f);
	const FLinearColor TitleInk(0.006f, 0.012f, 0.028f);
	const FLinearColor TitlePaper(0.95f, 0.95f, 0.97f);
	const FLinearColor TitleMuted(0.58f, 0.63f, 0.72f);
	const FLinearColor TitleCyan(0.35f, 0.82f, 0.92f);
	const FLinearColor TitleRed(0.90f, 0.28f, 0.24f);
	const FLinearColor TitleGreen(0.42f, 0.82f, 0.48f);

	FLinearColor TitleAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}

	int32 TitleWrapIndex(int32 Index, int32 Count)
	{
		if (Count <= 0)
		{
			return 0;
		}
		return ((Index % Count) + Count) % Count;
	}
}

FDATitleScreen::FDATitleScreen(ADAHUD* InOwner)
	: OwnerHUD(InOwner)
{
	PlayerOwner = InOwner ? InOwner->GetOwningPlayerController() : nullptr;
	LoadOptionsFromSettings();
}

FDATitleScreen::~FDATitleScreen() = default;

UWorld* FDATitleScreen::GetWorld() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetWorld() : nullptr;
}

UGameInstance* FDATitleScreen::GetGameInstance() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetGameInstance() : nullptr;
}

APlayerController* FDATitleScreen::GetPlayerController() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr;
}

UDASaveSubsystem* FDATitleScreen::GetSaveSubsystem() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UDASaveSubsystem>() : nullptr;
}

UDASettings* FDATitleScreen::GetSettings() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UDASettings>() : nullptr;
}

UDACalendarSubsystem* FDATitleScreen::GetCalendar() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UDACalendarSubsystem>() : nullptr;
}

UFont* FDATitleScreen::GetFont(bool bLarge) const
{
	if (OwnerHUD.IsValid())
	{
		return bLarge ? OwnerHUD->GetBigFont() : OwnerHUD->GetSmallFont();
	}
	return bLarge ? (GEngine ? GEngine->GetLargeFont() : nullptr) : (GEngine ? GEngine->GetMediumFont() : nullptr);
}

void FDATitleScreen::PlaySfx(const TCHAR* SoundName, float Volume) const
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

void FDATitleScreen::Open()
{
	if (bOpen)
	{
		RefreshSlots();
		ShowPanel(EDATitlePanel::Main);
		return;
	}
	bOpen = true;
	Elapsed = 0.f;
	HoveredIndex = INDEX_NONE;
	StatusMessage.Reset();
	StatusTime = 0.f;
	bStatusError = false;
	CreditsScroll = 0;

	LoadOptionsFromSettings();
	RefreshSlots();

	Panel = EDATitlePanel::Main;
	Selection = HasUsableSave() ? 1 : 0;
	PlaySfx(TEXT("A_UIClick"), 0.45f);
}

void FDATitleScreen::Close()
{
	if (!bOpen)
	{
		return;
	}
	bOpen = false;
	HitTargets.Reset();
	HoveredIndex = INDEX_NONE;
	OnClosed.Broadcast();
}

void FDATitleScreen::ShowPanel(EDATitlePanel InPanel)
{
	Panel = InPanel;
	HoveredIndex = INDEX_NONE;
	Selection = 0;

	switch (Panel)
	{
	case EDATitlePanel::Main:
		Selection = HasUsableSave() ? 1 : 0;
		break;
	case EDATitlePanel::Continue:
		RefreshSlots();
		for (int32 Index = 0; Index < Slots.Num(); ++Index)
		{
			if (Slots[Index].bExists && !Slots[Index].bCorrupt)
			{
				Selection = Index;
				break;
			}
		}
		break;
	case EDATitlePanel::Options:
		LoadOptionsFromSettings();
		break;
	case EDATitlePanel::Credits:
		if (CreditsLines.Num() == 0)
		{
			LoadCredits();
		}
		CreditsScroll = 0;
		break;
	case EDATitlePanel::ConfirmNewGame:
		Selection = 1; // Safer default: cancel.
		break;
	default:
		break;
	}
}

// ------------------------------------------------------------------------ data

void FDATitleScreen::RefreshSlots()
{
	Slots.Reset();

	const UDASaveSubsystem* Save = GetSaveSubsystem();
	TArray<FDASaveSlotInfo> Infos;
	if (Save)
	{
		Infos = Save->EnumerateSlots();
	}

	if (Infos.Num() == 0)
	{
		for (int32 Index = 0; Index < 4; ++Index)
		{
			FDATitleSlotView View;
			View.SlotIndex = Index;
			View.SlotName = Index == 0 ? FString(TEXT("autosave")) : FString::Printf(TEXT("slot_%d"), Index);
			View.bAutosave = Index == 0;
			View.Label = Index == 0 ? FString(TEXT("AUTOSAVE")) : FString::Printf(TEXT("SLOT %d"), Index);
			View.DateLine = TEXT("EMPTY SLOT");
			Slots.Add(View);
		}
		UpdateSelectionClamp();
		return;
	}

	for (const FDASaveSlotInfo& Info : Infos)
	{
		FDATitleSlotView View;
		View.SlotIndex = Info.SlotIndex;
		View.SlotName = Info.SlotName;
		View.bAutosave = Info.bIsAutosave;
		View.bExists = Info.bExists;
		View.bCorrupt = Info.bCorrupt;
		View.bUsingBackup = Info.bUsingBackup;
		View.Label = Info.bIsAutosave ? FString(TEXT("AUTOSAVE")) : FString::Printf(TEXT("SLOT %d"), Info.SlotIndex);
		View.PlayerName = Info.PlayerName.IsEmpty() ? FString(TEXT("New Student")) : Info.PlayerName;
		View.Title = Info.Title.IsEmpty() ? FString(TEXT("No title")) : Info.Title;
		View.Dorm = DuelAcademy::DormName(Info.Dorm);
		View.DP = Info.DP;
		View.Playtime = FormatPlaytime(Info.PlaytimeSeconds);

		if (!Info.bExists)
		{
			View.DateLine = TEXT("EMPTY SLOT");
		}
		else if (Info.bCorrupt)
		{
			View.DateLine = TEXT("CORRUPT SAVE");
		}
		else
		{
			View.DateLine = FormatSlotDate(Info.SavedAtUtc, Info.Year, Info.MonthIndex, Info.Day,
				static_cast<int32>(Info.Period));
		}
		Slots.Add(View);
	}

	UpdateSelectionClamp();
}

bool FDATitleScreen::HasAnySave() const
{
	for (const FDATitleSlotView& Slot : Slots)
	{
		if (Slot.bExists)
		{
			return true;
		}
	}
	return false;
}

bool FDATitleScreen::HasUsableSave() const
{
	for (const FDATitleSlotView& Slot : Slots)
	{
		if (Slot.bExists && !Slot.bCorrupt)
		{
			return true;
		}
	}
	return false;
}

int32 FDATitleScreen::GetLatestSlotIndex() const
{
	for (int32 Index = 0; Index < Slots.Num(); ++Index)
	{
		if (Slots[Index].bExists && !Slots[Index].bCorrupt)
		{
			return Index;
		}
	}
	return INDEX_NONE;
}

void FDATitleScreen::SetStatusMessage(const FString& InMessage, bool bError)
{
	StatusMessage = InMessage;
	StatusTime = 5.0f;
	bStatusError = bError;
}

FString FDATitleScreen::FormatSlotDate(const FString& SavedAtUtc, int32 Year, int32 MonthIndex, int32 Day, int32 Period) const
{
	if (Year <= 0 || Day <= 0)
	{
		return SavedAtUtc.IsEmpty() ? FString(TEXT("Saved")) : SavedAtUtc.Left(10);
	}
	const UDACalendarSubsystem* Calendar = GetCalendar();
	const FString Month = Calendar
		? Calendar->GetMonthShortName(FMath::Clamp(MonthIndex, 0, 11))
		: FString::Printf(TEXT("%d"), MonthIndex + 1);
	const FString PeriodText = Calendar
		? Calendar->GetPeriodName(static_cast<EDADayPeriod>(FMath::Clamp(Period, 0, 2)))
		: FString(Period == 0 ? TEXT("AM") : (Period == 1 ? TEXT("PM") : TEXT("NIGHT")));
	return FString::Printf(TEXT("%s %d, Year %d  -  %s"), *Month, Day, Year, *PeriodText);
}

FString FDATitleScreen::FormatPlaytime(double Seconds)
{
	const int32 Total = FMath::Max(0, static_cast<int32>(FMath::FloorToInt(Seconds)));
	const int32 Hours = Total / 3600;
	const int32 Minutes = (Total % 3600) / 60;
	return FString::Printf(TEXT("%d:%02d"), Hours, Minutes);
}

FString FDATitleScreen::GetVersionText() const
{
	FString Build = FApp::GetBuildVersion();
	if (Build.IsEmpty())
	{
		Build = TEXT("dev");
	}
	if (Build.Len() > 48)
	{
		Build = Build.Left(45) + TEXT("...");
	}
	return FString::Printf(TEXT("BUILD %s   -   UE %s"),
		*Build, *FEngineVersion::Current().ToString(EVersionComponent::Patch));
}

bool FDATitleScreen::LoadCredits()
{
	CreditsLines.Reset();
	if (DAUIData::LoadCredits(CreditsLines) && CreditsLines.Num() > 0)
	{
		return true;
	}
	CreditsLines.Add(TEXT("DUEL ACADEMY ISLAND"));
	CreditsLines.Add(TEXT("A fan-made Unreal Engine 5.8 port of the GBA campaign."));
	CreditsLines.Add(TEXT(""));
	CreditsLines.Add(TEXT("This build is a work in progress."));
	CreditsLines.Add(TEXT("Credits data was not found in Content/Data/UI/ui.json."));
	CreditsLines.Add(TEXT(""));
	CreditsLines.Add(TEXT("Yu-Gi-Oh! GX and related names belong to their respective owners."));
	CreditsLines.Add(TEXT("Non-commercial fan project. Not affiliated with Konami."));
	return false;
}

int32 FDATitleScreen::GetVisibleCreditLines() const
{
	const float S = UIScale;
	const float CH = Canvas ? Canvas->ClipY : 1080.f;
	const float PanelH = FMath::Min(CH * 0.80f, 800.f * S);
	const float LineH = FMath::Max(18.f * S, Measure(TEXT("Ag"), 0.85f).Y + 6.f * S);
	return FMath::Clamp(FMath::FloorToInt((PanelH - 150.f * S) / FMath::Max(LineH, 1.f)), 4, 40);
}

// ------------------------------------------------------------------------ options

void FDATitleScreen::LoadOptionsFromSettings()
{
	UDASettings* Settings = GetSettings();
	if (!Settings)
	{
		return;
	}
	TextSpeedIndex = FMath::Clamp(static_cast<int32>(Settings->GetTextSpeed()), 0, 3);
	bAutoAdvance = Settings->GetControl(TEXT("AutoAdvance")).Equals(TEXT("On"), ESearchCase::IgnoreCase);
	BgmPercent = FMath::Clamp(FMath::RoundToInt(Settings->GetBgmVolume() * 100.f), 0, 100);
	SfxPercent = FMath::Clamp(FMath::RoundToInt(Settings->GetSfxVolume() * 100.f), 0, 100);
}

void FDATitleScreen::ApplyOptionsToSettings(bool bPersist)
{
	UDASettings* Settings = GetSettings();
	if (!Settings)
	{
		return;
	}
	Settings->SetTextSpeed(static_cast<EDATextSpeed>(FMath::Clamp(TextSpeedIndex, 0, 3)));
	Settings->SetBgmVolume(static_cast<float>(BgmPercent) / 100.f);
	Settings->SetSfxVolume(static_cast<float>(SfxPercent) / 100.f);
	// A02 has no typed auto-advance field yet. Use the persisted controls map as
	// a bridge so the choice still survives save/load; see Docs/UI_Integration.md.
	Settings->SetControl(TEXT("AutoAdvance"), bAutoAdvance ? TEXT("On") : TEXT("Off"));
	OnOptionsChanged.Broadcast();
	if (bPersist)
	{
		Settings->Save();
	}
}

void FDATitleScreen::AdjustSelectedOption(int32 Direction)
{
	switch (Selection)
	{
	case 0:
		TextSpeedIndex = TitleWrapIndex(TextSpeedIndex + (Direction >= 0 ? 1 : -1), 4);
		break;
	case 1:
		if (Direction == 0)
		{
			bAutoAdvance = !bAutoAdvance;
		}
		else
		{
			bAutoAdvance = Direction > 0;
		}
		break;
	case 2:
		BgmPercent = FMath::Clamp(BgmPercent + (Direction >= 0 ? 10 : -10), 0, 100);
		if (Direction > 0 && BgmPercent >= 100)
		{
			BgmPercent = 100;
		}
		break;
	case 3:
		SfxPercent = FMath::Clamp(SfxPercent + (Direction >= 0 ? 10 : -10), 0, 100);
		if (Direction > 0 && SfxPercent >= 100)
		{
			SfxPercent = 100;
		}
		break;
	default:
		break;
	}

	ApplyOptionsToSettings(false);
	PlaySfx(TEXT("A_UIClick"), 0.4f);
}

// ------------------------------------------------------------------------ navigation

void FDATitleScreen::UpdateSelectionClamp()
{
	const int32 Count = Panel == EDATitlePanel::Continue
		? Slots.Num()
		: (Panel == EDATitlePanel::ConfirmNewGame ? 2 : (Panel == EDATitlePanel::Main ? 4 : 4));
	Selection = Count > 0 ? FMath::Clamp(Selection, 0, Count - 1) : 0;
}

void FDATitleScreen::MoveSelection(int32 Delta)
{
	if (Panel == EDATitlePanel::Credits)
	{
		const int32 MaxScroll = FMath::Max(0, CreditsLines.Num() - GetVisibleCreditLines());
		const int32 NewScroll = FMath::Clamp(CreditsScroll + Delta, 0, MaxScroll);
		if (NewScroll != CreditsScroll)
		{
			CreditsScroll = NewScroll;
			PlaySfx(TEXT("A_UIClick"), 0.25f);
		}
		return;
	}

	const int32 Count = Panel == EDATitlePanel::Continue
		? Slots.Num()
		: (Panel == EDATitlePanel::ConfirmNewGame ? 2 : 4);
	if (Count <= 0)
	{
		return;
	}
	const int32 NewSelection = TitleWrapIndex(Selection + Delta, Count);
	if (NewSelection != Selection)
	{
		Selection = NewSelection;
		PlaySfx(TEXT("A_UIClick"), 0.25f);
	}
}

void FDATitleScreen::ActivateMainItem()
{
	switch (Selection)
	{
	case 0:
		if (HasAnySave())
		{
			ShowPanel(EDATitlePanel::ConfirmNewGame);
		}
		else
		{
			PlaySfx(TEXT("A_UIClick"), 0.6f);
			OnNewGame.Broadcast();
		}
		break;
	case 1:
		ShowPanel(EDATitlePanel::Continue);
		break;
	case 2:
		ShowPanel(EDATitlePanel::Options);
		break;
	case 3:
		ShowPanel(EDATitlePanel::Credits);
		break;
	default:
		break;
	}
}

void FDATitleScreen::ActivateContinueSlot()
{
	if (!Slots.IsValidIndex(Selection))
	{
		return;
	}
	const FDATitleSlotView& Slot = Slots[Selection];
	if (!Slot.bExists)
	{
		SetStatusMessage(TEXT("This slot is empty. Start a new game to create a save."), false);
		return;
	}
	if (Slot.bCorrupt)
	{
		SetStatusMessage(TEXT("This save is corrupt and cannot be loaded."), true);
		return;
	}
	PlaySfx(TEXT("A_UIClick"), 0.6f);
	OnContinue.Broadcast(Slot.SlotIndex);
}

void FDATitleScreen::ActivateOptionRow()
{
	AdjustSelectedOption(Selection == 1 ? 0 : 1);
}

bool FDATitleScreen::ConfirmSelection()
{
	switch (Panel)
	{
	case EDATitlePanel::Main:
		ActivateMainItem();
		return true;
	case EDATitlePanel::Continue:
		ActivateContinueSlot();
		return true;
	case EDATitlePanel::Options:
		ActivateOptionRow();
		return true;
	case EDATitlePanel::Credits:
		BackToMain();
		return true;
	case EDATitlePanel::ConfirmNewGame:
		if (Selection == 0)
		{
			PlaySfx(TEXT("A_UIClick"), 0.7f);
			OnNewGame.Broadcast();
		}
		else
		{
			BackToMain();
		}
		return true;
	default:
		return false;
	}
}

void FDATitleScreen::BackToMain()
{
	if (Panel == EDATitlePanel::Options)
	{
		ApplyOptionsToSettings(true);
	}
	Panel = EDATitlePanel::Main;
	Selection = HasUsableSave() ? 1 : 0;
	HoveredIndex = INDEX_NONE;
	CreditsScroll = 0;
	PlaySfx(TEXT("A_UIClick"), 0.35f);
}

// ------------------------------------------------------------------------ update

void FDATitleScreen::Update(float DeltaSeconds)
{
	if (!bOpen)
	{
		return;
	}
	PlayerOwner = GetPlayerController();
	Elapsed += DeltaSeconds;

	if (StatusTime > 0.f)
	{
		StatusTime -= DeltaSeconds;
		if (StatusTime <= 0.f)
		{
			StatusTime = 0.f;
			StatusMessage.Reset();
		}
	}

	HoveredIndex = INDEX_NONE;
	float MouseX = -1.f;
	float MouseY = -1.f;
	if (PlayerOwner && PlayerOwner->GetMousePosition(MouseX, MouseY))
	{
		const FVector2D Mouse(MouseX, MouseY);
		for (const FDATitleHitTarget& Hit : HitTargets)
		{
			if (Hit.Contains(Mouse) && (Hit.Action == TEXT("main") || Hit.Action == TEXT("slot")
				|| Hit.Action == TEXT("option") || Hit.Action == TEXT("confirm")))
			{
				HoveredIndex = Hit.Index;
			}
		}
	}

	if (!PlayerOwner)
	{
		return;
	}

	const bool bBack = PlayerOwner->WasInputKeyJustPressed(EKeys::Escape)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right);

	if (Panel == EDATitlePanel::Credits)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Up) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Up)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::W))
		{
			const int32 MaxScroll = FMath::Max(0, CreditsLines.Num() - GetVisibleCreditLines());
			CreditsScroll = FMath::Clamp(CreditsScroll - 1, 0, MaxScroll);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Down) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::S))
		{
			const int32 MaxScroll = FMath::Max(0, CreditsLines.Num() - GetVisibleCreditLines());
			CreditsScroll = FMath::Clamp(CreditsScroll + 1, 0, MaxScroll);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::PageUp))
		{
			const int32 MaxScroll = FMath::Max(0, CreditsLines.Num() - GetVisibleCreditLines());
			CreditsScroll = FMath::Clamp(CreditsScroll - GetVisibleCreditLines(), 0, MaxScroll);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::PageDown))
		{
			const int32 MaxScroll = FMath::Max(0, CreditsLines.Num() - GetVisibleCreditLines());
			CreditsScroll = FMath::Clamp(CreditsScroll + GetVisibleCreditLines(), 0, MaxScroll);
		}
		if (bBack || PlayerOwner->WasInputKeyJustPressed(EKeys::Enter)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
		{
			BackToMain();
			return;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}

	if (bBack)
	{
		if (Panel == EDATitlePanel::Main)
		{
			SetStatusMessage(TEXT("Choose NEW GAME or CONTINUE."), false);
		}
		else
		{
			BackToMain();
		}
		return;
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

	if (Panel == EDATitlePanel::Options)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Left) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Left))
		{
			AdjustSelectedOption(-1);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Right) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Right))
		{
			AdjustSelectedOption(1);
		}
	}
	if (Panel == EDATitlePanel::ConfirmNewGame)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Left) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Left))
		{
			Selection = 1;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Right) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Right))
		{
			Selection = 0;
		}
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
	{
		ConfirmSelection();
		return;
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
	{
		HandleClickAtMouse();
	}
}

void FDATitleScreen::HandleClickAtMouse()
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

void FDATitleScreen::HandleHit(const FDATitleHitTarget& Hit)
{
	if (Hit.Action == TEXT("main"))
	{
		Selection = Hit.Index;
		ActivateMainItem();
	}
	else if (Hit.Action == TEXT("slot"))
	{
		Selection = Hit.Index;
		ActivateContinueSlot();
	}
	else if (Hit.Action == TEXT("option"))
	{
		Selection = Hit.Index;
		ActivateOptionRow();
	}
	else if (Hit.Action == TEXT("confirm"))
	{
		Selection = Hit.Index;
		ConfirmSelection();
	}
	else if (Hit.Action == TEXT("back"))
	{
		BackToMain();
	}
}

void FDATitleScreen::AddHit(const FString& Action, int32 Index, float X, float Y, float W, float H)
{
	FDATitleHitTarget Hit;
	Hit.Action = Action;
	Hit.Index = Index;
	Hit.X = X;
	Hit.Y = Y;
	Hit.W = W;
	Hit.H = H;
	HitTargets.Add(MoveTemp(Hit));
}

// ------------------------------------------------------------------------ drawing helpers

void FDATitleScreen::DrawRect(const FLinearColor& Color, float X, float Y, float W, float H)
{
	if (!Canvas || W <= 0.f || H <= 0.f)
	{
		return;
	}
	FCanvasTileItem Tile(FVector2D(X, Y), GWhiteTexture, FVector2D(W, H), Color);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void FDATitleScreen::DrawText(const FString& Str, float X, float Y, const FLinearColor& Color, float InScale,
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

void FDATitleScreen::DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent)
{
	DrawRect(Fill, X, Y, W, H);
	DrawRect(TitleAlpha(Accent, 0.95f), X, Y, 4.f * UIScale, H);
	DrawRect(TitleAlpha(Accent, 0.45f), X, Y + H - 2.f * UIScale, W, 2.f * UIScale);
}

void FDATitleScreen::Diamond(const FVector2D& C, float R, const FLinearColor& Color)
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

FVector2D FDATitleScreen::Measure(const FString& Str, float InScale, UFont* Font) const
{
	const UFont* F = Font ? Font : GetFont(false);
	if (!F || Str.IsEmpty())
	{
		return FVector2D::ZeroVector;
	}
	const float K = InScale * UIScale;
	return FVector2D(F->GetStringSize(*Str) * K, F->GetStringHeightSize(*Str) * K);
}

TArray<FString> FDATitleScreen::WrapText(const FString& Str, float MaxWidth, float InScale, UFont* Font) const
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

// ------------------------------------------------------------------------ draw

void FDATitleScreen::Draw(UCanvas* InCanvas)
{
	if (!bOpen || !InCanvas)
	{
		return;
	}
	Canvas = InCanvas;
	UIScale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.6f, 2.5f);
	HitTargets.Reset();

	DrawBackground();
	switch (Panel)
	{
	case EDATitlePanel::Main:           DrawMain(); break;
	case EDATitlePanel::Continue:       DrawContinue(); break;
	case EDATitlePanel::Options:        DrawOptions(); break;
	case EDATitlePanel::Credits:        DrawCredits(); break;
	case EDATitlePanel::ConfirmNewGame: DrawConfirmNewGame(); break;
	default:                            DrawMain(); break;
	}
	DrawFooter();
	DrawStatus();
}

void FDATitleScreen::DrawBackground()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;

	DrawRect(FLinearColor(TitleInk.R, TitleInk.G, TitleInk.B, 0.88f), 0.f, 0.f, CW, CH);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.20f), 0.f, 0.f, CW, CH * 0.28f);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.22f), 0.f, CH * 0.72f, CW, CH * 0.28f);
	DrawRect(TitleAlpha(TitleGold, 0.24f), CW * 0.035f, CH * 0.08f, 2.f * S, CH * 0.84f);
	DrawRect(TitleAlpha(TitleGold, 0.18f), CW * 0.035f, CH * 0.82f, CW * 0.30f, 2.f * S);

	// Low-contrast duel-disk emblem behind the main layout.
	const FVector2D Emblem(CW * 0.78f, CH * 0.26f);
	Diamond(Emblem, 156.f * S, TitleAlpha(TitleGold, 0.035f));
	Diamond(Emblem, 128.f * S, TitleAlpha(TitleInk, 0.45f));
	Diamond(Emblem, 100.f * S, TitleAlpha(TitleGold, 0.06f));
}

void FDATitleScreen::DrawMain()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float Fade = FMath::Clamp(Elapsed / 0.45f, 0.f, 1.f);

	const float LeftX = CW * 0.075f;
	const float KickerY = CH * 0.10f;
	DrawText(DAUIData::Label(TEXT("title.kicker"), TEXT("A FAN-MADE GBA STORY PORT")),
		LeftX, KickerY, TitleAlpha(TitleGold, 0.95f * Fade), 0.72f, false, nullptr);
	DrawText(DAUIData::Label(TEXT("title.game_title"), TEXT("DUEL ACADEMY")),
		LeftX, CH * 0.135f, TitleAlpha(TitleGold, Fade), 3.15f, false, GetFont(true));
	DrawText(DAUIData::Label(TEXT("title.game_subtitle"), TEXT("ISLAND")),
		LeftX, CH * 0.255f, TitleAlpha(TitlePaper, Fade), 2.1f, false, GetFont(true));
	DrawText(DAUIData::Label(TEXT("title.tagline"), TEXT("THE OPENING SLICE  -  GATE 1")),
		LeftX, CH * 0.335f, TitleAlpha(TitleMuted, 0.95f * Fade), 0.82f);

	const float MenuY = CH * 0.435f;
	const float MenuW = FMath::Min(CW * 0.32f, 540.f * S);
	const float MenuH = 58.f * S;
	const float Gap = 12.f * S;
	static const TCHAR* MenuKeys[] = {
		TEXT("title.menu.new_game"), TEXT("title.menu.continue"),
		TEXT("title.menu.options"), TEXT("title.menu.credits")
	};
	static const TCHAR* MenuFallbacks[] = { TEXT("NEW GAME"), TEXT("CONTINUE"), TEXT("OPTIONS"), TEXT("CREDITS") };
	for (int32 Index = 0; Index < 4; ++Index)
	{
		DrawMenuButton(DAUIData::Label(MenuKeys[Index], MenuFallbacks[Index]), Index,
			LeftX, MenuY + Index * (MenuH + Gap), MenuW, MenuH, Index == Selection);
	}

	// Emblem monogram.
	const FVector2D Emblem(CW * 0.78f, CH * 0.26f);
	Diamond(Emblem, 86.f * S, TitleAlpha(TitleGold, 0.18f * Fade));
	DrawText(TEXT("DA"), Emblem.X, Emblem.Y - 38.f * S, TitleAlpha(TitlePaper, Fade),
		2.4f, true, GetFont(true));
	DrawText(DAUIData::Label(TEXT("title.emblem"), TEXT("GATE 1")), Emblem.X, Emblem.Y + 72.f * S,
		TitleAlpha(TitleMuted, 0.8f * Fade), 0.7f, true);

	// Latest save summary.
	const float PanelX = CW * 0.60f;
	const float PanelY = CH * 0.48f;
	const float PanelW = CW * 0.33f;
	const float PanelH = CH * 0.31f;
	DrawPanel(PanelX, PanelY, PanelW, PanelH, TitleAlpha(TitleInk, 0.78f), TitleAlpha(TitleGold, 0.5f));
	DrawText(DAUIData::Label(TEXT("title.save_data"), TEXT("SAVE DATA")),
		PanelX + 22.f * S, PanelY + 16.f * S, TitleGold, 1.0f, false, GetFont(true));
	DrawRect(TitleAlpha(TitleGold, 0.3f), PanelX + 22.f * S, PanelY + 48.f * S, PanelW - 44.f * S, 1.f * S);

	const int32 Latest = GetLatestSlotIndex();
	if (Slots.IsValidIndex(Latest))
	{
		const FDATitleSlotView& Slot = Slots[Latest];
		float LineY = PanelY + 64.f * S;
		const float LineH = 25.f * S;
		DrawText(FString::Printf(TEXT("%s  -  %s"), *Slot.Label, *Slot.PlayerName),
			PanelX + 22.f * S, LineY, TitlePaper, 0.95f);
		LineY += LineH;
		DrawText(FString::Printf(TEXT("%s  -  %s"), *Slot.Dorm, *Slot.Title),
			PanelX + 22.f * S, LineY, TitleMuted, 0.78f);
		LineY += LineH;
		DrawText(Slot.DateLine, PanelX + 22.f * S, LineY, TitleMuted, 0.75f);
		LineY += LineH;
		DrawText(FString::Printf(TEXT("DP %d      PLAY %s"), Slot.DP, *Slot.Playtime),
			PanelX + 22.f * S, LineY, TitleGold, 0.78f);
	}
	else
	{
		DrawText(DAUIData::Label(TEXT("title.no_save"), TEXT("NO SAVE DATA")),
			PanelX + 22.f * S, PanelY + 72.f * S, TitleMuted, 1.05f, false, GetFont(true));
		DrawText(DAUIData::Label(TEXT("title.no_save_hint"), TEXT("Start a new game to begin your first year.")),
			PanelX + 22.f * S, PanelY + 108.f * S, TitleMuted, 0.76f);
	}

	// Prompt under the menu.
	DrawText(DAUIData::Label(TEXT("title.main_hint"), TEXT("UP / DOWN SELECT      ENTER CONFIRM")),
		LeftX, MenuY + 4.f * (MenuH + Gap) + 8.f * S, TitleMuted, 0.72f);
}

void FDATitleScreen::DrawMenuButton(const FString& Label, int32 Index, float X, float Y, float W, float H, bool bSelected)
{
	const bool bHovered = Index == HoveredIndex;
	const bool bHighlight = bSelected || bHovered;
	const bool bAvailable = Index != 1 || HasUsableSave();
	const FLinearColor Accent = bAvailable ? TitleGold : TitleMuted;

	if (bHighlight)
	{
		DrawRect(TitleAlpha(Accent, bSelected ? 0.22f : 0.10f), X, Y, W, H);
		DrawRect(TitleAlpha(Accent, 0.95f), X, Y, 5.f * UIScale, H);
		DrawRect(TitleAlpha(Accent, 0.35f), X, Y + H - 1.f * UIScale, W, 1.f * UIScale);
	}
	DrawText(Label, X + 24.f * UIScale, Y + 12.f * UIScale,
		bHighlight ? TitlePaper : TitleAlpha(bAvailable ? TitlePaper : TitleMuted, 0.72f), 1.15f,
		false, GetFont(true));

	if (bSelected)
	{
		DrawText(TEXT(">"), X + W - 34.f * UIScale, Y + 12.f * UIScale, Accent, 1.1f, false, GetFont(true));
	}
	AddHit(TEXT("main"), Index, X, Y, W, H);
}

void FDATitleScreen::DrawContinue()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float PanelW = FMath::Min(CW * 0.72f, 1200.f * S);
	const float PanelH = FMath::Min(CH * 0.82f, 820.f * S);
	const float PanelX = (CW - PanelW) * 0.5f;
	const float PanelY = (CH - PanelH) * 0.5f;

	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.35f), 0.f, 0.f, CW, CH);
	DrawPanel(PanelX, PanelY, PanelW, PanelH, TitleAlpha(TitleInk, 0.94f), TitleGold);
	DrawText(DAUIData::Label(TEXT("title.continue.title"), TEXT("CONTINUE")),
		PanelX + 34.f * S, PanelY + 24.f * S, TitleGold, 1.7f, false, GetFont(true));
	DrawText(DAUIData::Label(TEXT("title.continue.hint"),
		TEXT("Choose a save slot. Empty slots are kept visible.")),
		PanelX + 36.f * S, PanelY + 74.f * S, TitleMuted, 0.78f);
	DrawRect(TitleAlpha(TitleGold, 0.3f), PanelX + 34.f * S, PanelY + 104.f * S, PanelW - 68.f * S, 1.f * S);

	const float CardsTop = PanelY + 124.f * S;
	const float CardH = FMath::Max(92.f * S, (PanelH - 210.f * S) / FMath::Max(1, Slots.Num()));
	const float CardGap = 8.f * S;
	for (int32 Index = 0; Index < Slots.Num(); ++Index)
	{
		DrawSlotCard(Slots[Index], Index, PanelX + 34.f * S,
			CardsTop + Index * (CardH + CardGap), PanelW - 68.f * S, CardH, Index == Selection);
	}

	DrawBackButton(PanelX, PanelY, PanelW, PanelH);
}

void FDATitleScreen::DrawSlotCard(const FDATitleSlotView& Slot, int32 Index, float X, float Y, float W, float H, bool bSelected)
{
	const float S = UIScale;
	const bool bHovered = Index == HoveredIndex;
	const bool bOccupied = Slot.bExists && !Slot.bCorrupt;
	const FLinearColor Accent = Slot.bCorrupt ? TitleRed
		: (Slot.bAutosave ? TitleCyan : (bOccupied ? TitleGold : TitleMuted));

	if (bSelected || bHovered || bOccupied)
	{
		DrawRect(TitleAlpha(Accent, bSelected ? 0.20f : (bHovered ? 0.10f : 0.045f)), X, Y, W, H);
	}
	DrawRect(TitleAlpha(Accent, bOccupied || Slot.bCorrupt ? 0.95f : 0.35f), X, Y, 4.f * S, H);
	DrawText(Slot.Label, X + 18.f * S, Y + 10.f * S, bOccupied || Slot.bCorrupt ? Accent : TitleMuted,
		0.86f, false, GetFont(true));

	FString Badge;
	if (Slot.bCorrupt)
	{
		Badge = DAUIData::Label(TEXT("title.corrupt_slot"), TEXT("CORRUPT"));
	}
	else if (!Slot.bExists)
	{
		Badge = DAUIData::Label(TEXT("title.empty_slot"), TEXT("EMPTY SLOT"));
	}
	else if (Slot.bUsingBackup)
	{
		Badge = DAUIData::Label(TEXT("title.backup_slot"), TEXT("BACKUP USED"));
	}
	if (!Badge.IsEmpty())
	{
		const FVector2D BadgeSize = Measure(Badge, 0.68f);
		DrawText(Badge, X + W - BadgeSize.X - 18.f * S, Y + 14.f * S,
			Slot.bCorrupt ? TitleRed : TitleMuted, 0.68f);
	}

	if (bOccupied)
	{
		DrawText(Slot.PlayerName, X + 18.f * S, Y + 36.f * S, TitlePaper, 1.0f);
		const FString Middle = FString::Printf(TEXT("%s  -  %s"), *Slot.Dorm, *Slot.Title);
		DrawText(Middle, X + 18.f * S, Y + 60.f * S, TitleMuted, 0.75f);
		const FString Right = FString::Printf(TEXT("%s      DP %d      PLAY %s"),
			*Slot.DateLine, Slot.DP, *Slot.Playtime);
		DrawText(Right, X + 18.f * S, Y + H - 28.f * S, TitleGold, 0.72f);
	}
	else if (Slot.bCorrupt)
	{
		DrawText(DAUIData::Label(TEXT("title.corrupt_hint"), TEXT("This save cannot be read.")),
			X + 18.f * S, Y + 40.f * S, TitleRed, 0.82f);
	}
	else
	{
		DrawText(DAUIData::Label(TEXT("title.empty_hint"), TEXT("No save data. Start a new game.")),
			X + 18.f * S, Y + 40.f * S, TitleMuted, 0.82f);
	}

	AddHit(TEXT("slot"), Index, X, Y, W, H);
}

void FDATitleScreen::DrawOptions()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float PanelW = FMath::Min(CW * 0.56f, 900.f * S);
	const float PanelH = FMath::Min(CH * 0.68f, 620.f * S);
	const float PanelX = (CW - PanelW) * 0.5f;
	const float PanelY = (CH - PanelH) * 0.5f;

	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.35f), 0.f, 0.f, CW, CH);
	DrawPanel(PanelX, PanelY, PanelW, PanelH, TitleAlpha(TitleInk, 0.94f), TitleGold);
	DrawText(DAUIData::Label(TEXT("title.options.title"), TEXT("OPTIONS")),
		PanelX + 34.f * S, PanelY + 24.f * S, TitleGold, 1.7f, false, GetFont(true));
	DrawText(DAUIData::Label(TEXT("title.options.hint"),
		TEXT("UP / DOWN select      LEFT / RIGHT adjust      ESC back")),
		PanelX + 36.f * S, PanelY + 74.f * S, TitleMuted, 0.76f);
	DrawRect(TitleAlpha(TitleGold, 0.3f), PanelX + 34.f * S, PanelY + 104.f * S, PanelW - 68.f * S, 1.f * S);

	static const TCHAR* TextSpeedValues[] = { TEXT("SLOW"), TEXT("NORMAL"), TEXT("FAST"), TEXT("INSTANT") };
	FString Values[4];
	Values[0] = TextSpeedValues[FMath::Clamp(TextSpeedIndex, 0, 3)];
	Values[1] = bAutoAdvance ? TEXT("ON") : TEXT("OFF");
	Values[2] = FString::Printf(TEXT("%d%%"), BgmPercent);
	Values[3] = FString::Printf(TEXT("%d%%"), SfxPercent);
	const FString Labels[4] = {
		DAUIData::Label(TEXT("title.options.text_speed"), TEXT("TEXT SPEED")),
		DAUIData::Label(TEXT("title.options.auto_advance"), TEXT("AUTO-ADVANCE")),
		DAUIData::Label(TEXT("title.options.bgm"), TEXT("BGM VOLUME")),
		DAUIData::Label(TEXT("title.options.sfx"), TEXT("SFX VOLUME"))
	};

	const float RowTop = PanelY + 132.f * S;
	const float RowH = 66.f * S;
	for (int32 Index = 0; Index < 4; ++Index)
	{
		DrawOptionRow(Labels[Index], Values[Index], Index, PanelX + 34.f * S,
			RowTop + Index * RowH, PanelW - 68.f * S, RowH - 8.f * S, Index == Selection);
	}

	DrawBackButton(PanelX, PanelY, PanelW, PanelH);
}

void FDATitleScreen::DrawOptionRow(const FString& Label, const FString& Value, int32 Index, float X, float Y,
	float W, float H, bool bSelected)
{
	const float S = UIScale;
	const bool bHovered = Index == HoveredIndex;
	if (bSelected || bHovered)
	{
		DrawRect(TitleAlpha(TitleGold, bSelected ? 0.20f : 0.09f), X, Y, W, H);
		DrawRect(TitleAlpha(TitleGold, 0.95f), X, Y, 4.f * S, H);
	}
	DrawText(Label, X + 18.f * S, Y + 12.f * S, bSelected ? TitlePaper : TitleAlpha(TitlePaper, 0.82f), 0.95f);
	const FString ValueText = FString::Printf(TEXT("<  %s  >"), *Value);
	const FVector2D Size = Measure(ValueText, 0.92f);
	DrawText(ValueText, X + W - Size.X - 18.f * S, Y + 12.f * S, bSelected ? TitleGold : TitleMuted, 0.92f);
	AddHit(TEXT("option"), Index, X, Y, W, H);
}

void FDATitleScreen::DrawCredits()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float PanelW = FMath::Min(CW * 0.62f, 980.f * S);
	const float PanelH = FMath::Min(CH * 0.80f, 800.f * S);
	const float PanelX = (CW - PanelW) * 0.5f;
	const float PanelY = (CH - PanelH) * 0.5f;

	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.35f), 0.f, 0.f, CW, CH);
	DrawPanel(PanelX, PanelY, PanelW, PanelH, TitleAlpha(TitleInk, 0.95f), TitleGold);
	DrawText(DAUIData::Label(TEXT("title.credits.title"), TEXT("CREDITS")),
		PanelX + 34.f * S, PanelY + 22.f * S, TitleGold, 1.7f, false, GetFont(true));
	DrawText(DAUIData::Label(TEXT("title.credits.hint"), TEXT("UP / DOWN scroll      ESC back")),
		PanelX + 36.f * S, PanelY + 68.f * S, TitleMuted, 0.76f);
	DrawRect(TitleAlpha(TitleGold, 0.3f), PanelX + 34.f * S, PanelY + 96.f * S, PanelW - 68.f * S, 1.f * S);

	const float TextX = PanelX + 34.f * S;
	const float TextW = PanelW - 84.f * S;
	float Y = PanelY + 112.f * S;
	const float Bottom = PanelY + PanelH - 76.f * S;
	const float LineH = FMath::Max(18.f * S, Measure(TEXT("Ag"), 0.85f).Y + 6.f * S);
	const int32 Visible = GetVisibleCreditLines();
	const int32 MaxScroll = FMath::Max(0, CreditsLines.Num() - Visible);
	const int32 Start = FMath::Clamp(CreditsScroll, 0, MaxScroll);

	for (int32 Index = Start; Index < CreditsLines.Num(); ++Index)
	{
		const FString& Line = CreditsLines[Index];
		if (Line.IsEmpty())
		{
			Y += LineH * 0.65f;
			continue;
		}
		for (const FString& Wrapped : WrapText(Line, TextW, 0.85f))
		{
			if (Y + LineH > Bottom)
			{
				break;
			}
			DrawText(Wrapped, TextX, Y, TitleAlpha(TitlePaper, 0.9f), 0.85f);
			Y += LineH;
		}
		if (Y + LineH > Bottom)
		{
			break;
		}
	}

	if (MaxScroll > 0)
	{
		const float TrackY = PanelY + 112.f * S;
		const float TrackH = Bottom - TrackY;
		const float ThumbH = FMath::Max(28.f * S, TrackH * static_cast<float>(Visible) / static_cast<float>(CreditsLines.Num()));
		const float ThumbY = TrackY + (TrackH - ThumbH) * static_cast<float>(Start) / static_cast<float>(MaxScroll);
		DrawRect(TitleAlpha(TitleMuted, 0.18f), PanelX + PanelW - 24.f * S, TrackY, 3.f * S, TrackH);
		DrawRect(TitleAlpha(TitleGold, 0.8f), PanelX + PanelW - 24.f * S, ThumbY, 3.f * S, ThumbH);
	}

	DrawBackButton(PanelX, PanelY, PanelW, PanelH);
}

void FDATitleScreen::DrawConfirmNewGame()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float PanelW = FMath::Min(CW * 0.46f, 800.f * S);
	const float PanelH = FMath::Min(CH * 0.44f, 400.f * S);
	const float PanelX = (CW - PanelW) * 0.5f;
	const float PanelY = (CH - PanelH) * 0.5f;

	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.55f), 0.f, 0.f, CW, CH);
	DrawPanel(PanelX, PanelY, PanelW, PanelH, TitleAlpha(TitleInk, 0.97f), TitleRed);
	DrawText(DAUIData::Label(TEXT("title.confirm.title"), TEXT("START A NEW GAME?")),
		PanelX + 30.f * S, PanelY + 24.f * S, TitleRed, 1.45f, false, GetFont(true));
	const FString Body = DAUIData::Label(TEXT("title.confirm.body"),
		TEXT("Existing autosave progress will be replaced as the new game saves. Manual slots are kept."));
	float BodyY = PanelY + 70.f * S;
	for (const FString& Line : WrapText(Body, PanelW - 64.f * S, 0.86f))
	{
		DrawText(Line, PanelX + 32.f * S, BodyY, TitlePaper, 0.86f);
		BodyY += Measure(TEXT("Ag"), 0.86f).Y + 4.f * S;
	}
	DrawRect(TitleAlpha(TitleRed, 0.3f), PanelX + 30.f * S, PanelY + 122.f * S, PanelW - 60.f * S, 1.f * S);

	const float ButtonW = PanelW - 60.f * S;
	const float ButtonH = 54.f * S;
	const float ButtonY = PanelY + PanelH - 138.f * S;
	for (int32 Index = 0; Index < 2; ++Index)
	{
		const bool bSelected = Index == Selection;
		const float Y = ButtonY + Index * (ButtonH + 10.f * S);
		const FLinearColor Accent = Index == 0 ? TitleRed : TitleMuted;
		if (bSelected)
		{
			DrawRect(TitleAlpha(Accent, 0.20f), PanelX + 30.f * S, Y, ButtonW, ButtonH);
			DrawRect(TitleAlpha(Accent, 0.95f), PanelX + 30.f * S, Y, 4.f * S, ButtonH);
		}
		const FString Label = Index == 0
			? DAUIData::Label(TEXT("title.confirm.start"), TEXT("START NEW GAME"))
			: DAUIData::Label(TEXT("title.confirm.cancel"), TEXT("CANCEL"));
		DrawText(Label, PanelX + 50.f * S, Y + 12.f * S, bSelected ? TitlePaper : TitleMuted, 1.0f);
		AddHit(TEXT("confirm"), Index, PanelX + 30.f * S, Y, ButtonW, ButtonH);
	}
}

void FDATitleScreen::DrawBackButton(float PanelX, float PanelY, float PanelW, float PanelH)
{
	const float S = UIScale;
	const float W = 116.f * S;
	const float H = 34.f * S;
	const float X = PanelX + PanelW - W - 26.f * S;
	const float Y = PanelY + PanelH - H - 18.f * S;
	DrawRect(TitleAlpha(TitleMuted, 0.18f), X, Y, W, H);
	DrawRect(TitleAlpha(TitleMuted, 0.75f), X, Y, 3.f * S, H);
	DrawText(DAUIData::Label(TEXT("title.back"), TEXT("BACK")), X + 16.f * S, Y + 6.f * S, TitlePaper, 0.82f);
	AddHit(TEXT("back"), INDEX_NONE, X, Y, W, H);
}

void FDATitleScreen::DrawFooter()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float H = 30.f * S;
	DrawRect(FLinearColor(0.004f, 0.008f, 0.018f, 0.92f), 0.f, CH - H, CW, H);
	DrawRect(TitleAlpha(TitleMuted, 0.22f), 0.f, CH - H, CW, 1.f * S);
	DrawText(GetVersionText(), 24.f * S, CH - H + 7.f * S, TitleAlpha(TitleMuted, 0.7f), 0.62f);

	FString Hint;
	switch (Panel)
	{
	case EDATitlePanel::Main:
		Hint = DAUIData::Label(TEXT("title.footer.main"), TEXT("UP / DOWN SELECT      ENTER CONFIRM"));
		break;
	case EDATitlePanel::Continue:
		Hint = DAUIData::Label(TEXT("title.footer.continue"), TEXT("ENTER LOAD      ESC BACK"));
		break;
	case EDATitlePanel::Options:
		Hint = DAUIData::Label(TEXT("title.footer.options"), TEXT("LEFT / RIGHT ADJUST      ESC BACK"));
		break;
	case EDATitlePanel::Credits:
		Hint = DAUIData::Label(TEXT("title.footer.credits"), TEXT("UP / DOWN SCROLL      ESC BACK"));
		break;
	case EDATitlePanel::ConfirmNewGame:
		Hint = DAUIData::Label(TEXT("title.footer.confirm"), TEXT("UP / DOWN SELECT      ENTER CONFIRM      ESC CANCEL"));
		break;
	default:
		break;
	}
	if (!Hint.IsEmpty())
	{
		const FVector2D Size = Measure(Hint, 0.66f);
		DrawText(Hint, CW - 24.f * S - Size.X, CH - H + 8.f * S, TitleAlpha(TitleMuted, 0.72f), 0.66f);
	}
}

void FDATitleScreen::DrawStatus()
{
	if (StatusMessage.IsEmpty() || !Canvas)
	{
		return;
	}
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float W = FMath::Min(CW * 0.52f, 760.f * S);
	const float H = 44.f * S;
	const float X = 24.f * S;
	const float Y = CH - 132.f * S;
	const FLinearColor Accent = bStatusError ? TitleRed : TitleGold;
	DrawRect(TitleAlpha(TitleInk, 0.92f), X, Y, W, H);
	DrawRect(TitleAlpha(Accent, 0.95f), X, Y, 4.f * S, H);
	FString Message = StatusMessage;
	while (Message.Len() > 4 && Measure(Message, 0.8f).X > W - 32.f * S)
	{
		Message = Message.LeftChop(4) + TEXT("...");
	}
	DrawText(Message, X + 16.f * S, Y + 8.f * S, bStatusError ? TitleRed : TitlePaper, 0.8f);
}
