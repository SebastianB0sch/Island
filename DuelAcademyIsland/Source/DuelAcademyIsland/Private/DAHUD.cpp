// Duel Academy Island - canvas HUD.

#include "DAHUD.h"

#include "CanvasItem.h"
#include "DAInteractableInterface.h"
#include "DAIslandManager.h"
#include "DAIslandSubsystem.h"
#include "DALocationVolume.h"
#include "DAStudentCharacter.h"
#include "DACardRecords.h"
#include "DADuelEngine.h"
#include "DuelAcademyIsland.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "RenderUtils.h"
#include "TextureResource.h"
#include "TimerManager.h"
#include "UnrealClient.h"

namespace
{
	const FLinearColor HudGold(1.f, 0.78f, 0.25f);
	const FLinearColor HudInk(0.02f, 0.03f, 0.06f);
	const FLinearColor HudPaper(0.95f, 0.95f, 0.97f);

	FLinearColor HudAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}

	/** Sample payload from Content/Data/UI/ui.json, with a diagnostic fallback. */
	void LoadDialogueTestLines(TArray<FDADialogueLine>& OutLines)
	{
		if (!DAUIData::LoadDialogueSample(TEXT("opening_test"), OutLines) || OutLines.Num() == 0)
		{
			FDADialogueLine Line;
			Line.SpeakerId = TEXT("sheppard");
			Line.SpeakerName = TEXT("Chancellor Sheppard");
			Line.Portrait = TEXT("sheppard");
			Line.Text = TEXT("Sample dialogue unavailable: Content/Data/UI/ui.json was not found. (Placeholder.)");
			Line.TextKey = TEXT("PLACEHOLDER.UI.missing_data");
			OutLines.Add(Line);
		}
	}
}

ADAHUD::ADAHUD()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;
}

void ADAHUD::BeginPlay()
{
	Super::BeginPlay();
	SmallFont = GEngine ? GEngine->GetMediumFont() : nullptr;
	BigFont = GEngine ? GEngine->GetLargeFont() : nullptr;
	StartTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
	DuelUI = MakeUnique<FDADuelUI>(this);
	DialogueUI = MakeUnique<FDADialogueUI>(this);
	PDAUI = MakeUnique<FDAPDAUI>(this);
	PDAUI->OnAction.AddUObject(this, &ADAHUD::HandlePDAAction);
	PDAUI->OnClosed.AddUObject(this, &ADAHUD::HandlePDAClosed);
	DialogueUI->OnDialogueClosed.AddUObject(this, &ADAHUD::HandleDialogueClosed);

	// Debug harnesses (only active with the matching command-line switch):
	//   -DADuelSelfTest   run the AI-vs-AI rules self-test after the world settles
	//   -DADuelScreenshot capture the deck picker and an active duel board
	if (FParse::Param(FCommandLine::Get(), TEXT("DADuelSelfTest")))
	{
		FTimerHandle Timer;
		GetWorldTimerManager().SetTimer(Timer, FTimerDelegate::CreateWeakLambda(this, [this]()
		{
			UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
			const FString Summary = FDuelEngine::RunSelfTest(Cards, 24);
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Summary);
			FTimerHandle ExitTimer;
			GetWorldTimerManager().SetTimer(ExitTimer, FTimerDelegate::CreateWeakLambda(this, []()
			{
				FPlatformMisc::RequestExit(false);
			}), 1.0f, false);
		}), 2.0f, false);
	}

	if (FParse::Param(FCommandLine::Get(), TEXT("DADuelScreenshot")))
	{
		TWeakObjectPtr<ADAHUD> WeakThis(this);
		auto After = [WeakThis](float Delay, TFunction<void(ADAHUD*)> Fn)
		{
			if (!WeakThis.IsValid())
			{
				return;
			}
			FTimerHandle Timer;
			WeakThis->GetWorldTimerManager().SetTimer(Timer, FTimerDelegate::CreateWeakLambda(WeakThis.Get(),
				[WeakThis, Fn]()
				{
					if (ADAHUD* HUD = WeakThis.Get())
					{
						Fn(HUD);
					}
				}), Delay, false);
		};
		After(1.0f, [](ADAHUD* HUD) { HUD->OpenDuelDeckSelect(TEXT("jaden"), TEXT("Jaden Yuki"), TEXT("jaden")); });
		After(2.2f, [](ADAHUD* HUD) { FScreenshotRequest::RequestScreenshot(TEXT("DADuelDeck.png"), false, false); });
		After(3.0f, [](ADAHUD* HUD) { HUD->StartDuelWithDeck(TEXT("fire")); });
		After(5.6f, [](ADAHUD* HUD) { HUD->DebugAutoPlayOpening(); });
		After(6.3f, [](ADAHUD* HUD) { FScreenshotRequest::RequestScreenshot(TEXT("DADuelBoard.png"), false, false); });
		After(7.1f, [](ADAHUD* HUD) { HUD->DebugSelectFirstHandCard(); });
		After(7.9f, [](ADAHUD* HUD) { FScreenshotRequest::RequestScreenshot(TEXT("DADuelSelect.png"), false, false); });
		After(8.6f, [](ADAHUD* HUD) { HUD->DebugFinishDuelWin(); });
		After(13.0f, [](ADAHUD* HUD) { FScreenshotRequest::RequestScreenshot(TEXT("DADuelResult.png"), false, false); });
		After(14.2f, [](ADAHUD* HUD) { FPlatformMisc::RequestExit(false); });
	}

	// UI debug harnesses:
	//   -DADialogueTest  open the sample dialogue from Content/Data/UI/ui.json
	//   -DAPDATest       open the PDA on the Map tab on launch
	//   -DAUITest        cycle every PDA tab + dialogue, capture screenshots, exit
	if (FParse::Param(FCommandLine::Get(), TEXT("DADialogueTest")))
	{
		FTimerHandle Timer;
		GetWorldTimerManager().SetTimer(Timer, FTimerDelegate::CreateWeakLambda(this, [this]()
		{
			TArray<FDADialogueLine> Lines;
			LoadDialogueTestLines(Lines);
			BeginDialogue(Lines, TEXT("ui_test"));
		}), 1.2f, false);
	}

	if (FParse::Param(FCommandLine::Get(), TEXT("DAPDATest")))
	{
		FTimerHandle Timer;
		GetWorldTimerManager().SetTimer(Timer, FTimerDelegate::CreateWeakLambda(this, [this]()
		{
			OpenPDA(EDAPDATab::Map);
		}), 1.2f, false);
	}

	if (FParse::Param(FCommandLine::Get(), TEXT("DAUITest")))
	{
		TWeakObjectPtr<ADAHUD> WeakThis(this);
		auto After = [WeakThis](float Delay, TFunction<void(ADAHUD*)> Fn)
		{
			if (!WeakThis.IsValid())
			{
				return;
			}
			FTimerHandle Timer;
			WeakThis->GetWorldTimerManager().SetTimer(Timer, FTimerDelegate::CreateWeakLambda(WeakThis.Get(),
				[WeakThis, Fn]()
				{
					if (ADAHUD* HUD = WeakThis.Get())
					{
						Fn(HUD);
					}
				}), Delay, false);
		};

		float T = 1.0f;
		for (int32 Index = 0; Index < DAPDATabCount; ++Index)
		{
			const EDAPDATab Tab = static_cast<EDAPDATab>(Index);
			const FString FileName = FString::Printf(TEXT("DAPDA_%s.png"), FDAPDAUI::TabSlug(Tab));
			After(T, [Tab](ADAHUD* HUD) { HUD->OpenPDA(Tab); });
			After(T + 0.6f, [FileName](ADAHUD* HUD) { FScreenshotRequest::RequestScreenshot(FileName, false, false); });
			T += 1.0f;
		}

		After(T, [](ADAHUD* HUD)
		{
			HUD->ClosePDA();
			TArray<FDADialogueLine> Lines;
			LoadDialogueTestLines(Lines);
			HUD->BeginDialogue(Lines, TEXT("ui_test"));
		});
		After(T + 0.6f, [](ADAHUD* HUD)
		{
			if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
			{
				Dialogue->Advance(); // reveal line 1
			}
		});
		After(T + 0.9f, [](ADAHUD* HUD) { FScreenshotRequest::RequestScreenshot(TEXT("DADialogue.png"), false, false); });
		After(T + 1.1f, [](ADAHUD* HUD)
		{
			if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
			{
				Dialogue->Advance(); // line 2
				Dialogue->Advance(); // reveal line 2
				Dialogue->Advance(); // line 3 (choice)
				Dialogue->Advance(); // reveal choice text
			}
		});
		After(T + 1.6f, [](ADAHUD* HUD) { FScreenshotRequest::RequestScreenshot(TEXT("DADialogueChoice.png"), false, false); });
		After(T + 2.4f, [](ADAHUD* HUD) { HUD->CloseDialogue(); });
		After(T + 3.0f, [](ADAHUD* HUD) { FPlatformMisc::RequestExit(false); });
	}
}

void ADAHUD::OpenDuelDeckSelect(const FString& OpponentId, const FString& OpponentName, const FString& OpponentDeckId)
{
	if (!DuelUI.IsValid())
	{
		DuelUI = MakeUnique<FDADuelUI>(this);
	}
	DuelUI->OpenDeckSelect(OpponentId, OpponentName, OpponentDeckId);
}

void ADAHUD::CloseDuel()
{
	if (DuelUI.IsValid())
	{
		DuelUI->CloseDuel();
	}
}

void ADAHUD::StartDuelWithDeck(const FString& DeckId)
{
	if (DuelUI.IsValid())
	{
		DuelUI->StartDuelWithDeck(DeckId);
	}
}

void ADAHUD::DebugAutoPlayOpening()
{
	if (DuelUI.IsValid())
	{
		DuelUI->DebugAutoPlayOpening();
	}
}

void ADAHUD::DebugSelectFirstHandCard()
{
	if (DuelUI.IsValid())
	{
		DuelUI->DebugSelectFirstHandCard();
	}
}

void ADAHUD::DebugFinishDuelWin()
{
	if (DuelUI.IsValid())
	{
		DuelUI->DebugFinishDuelWin();
	}
}

// ------------------------------------------------------------------------ dialogue / PDA hosting

void ADAHUD::BeginDialogue(const TArray<FDADialogueLine>& Lines, const FString& ConversationId)
{
	if (IsDuelOpen())
	{
		return;
	}
	if (!DialogueUI.IsValid())
	{
		DialogueUI = MakeUnique<FDADialogueUI>(this);
		DialogueUI->OnDialogueClosed.AddUObject(this, &ADAHUD::HandleDialogueClosed);
	}
	if (bMapOpen)
	{
		ToggleMap();
	}
	bHelpOpen = false;
	DialogueUI->Begin(Lines, ConversationId);
	UpdateInputMode();
}

void ADAHUD::BeginDialogueLine(const FDADialogueLine& Line)
{
	TArray<FDADialogueLine> Lines;
	Lines.Add(Line);
	BeginDialogue(Lines, TEXT("single"));
}

void ADAHUD::CloseDialogue()
{
	if (DialogueUI.IsValid())
	{
		DialogueUI->Close();
	}
	UpdateInputMode();
}

void ADAHUD::OpenPDA(EDAPDATab Tab)
{
	if (IsDuelOpen() || IsDialogueOpen())
	{
		return;
	}
	if (!PDAUI.IsValid())
	{
		PDAUI = MakeUnique<FDAPDAUI>(this);
		PDAUI->OnAction.AddUObject(this, &ADAHUD::HandlePDAAction);
		PDAUI->OnClosed.AddUObject(this, &ADAHUD::HandlePDAClosed);
	}
	if (bMapOpen)
	{
		ToggleMap();
	}
	bHelpOpen = false;
	PDAUI->Open(Tab);
	UpdateInputMode();
}

void ADAHUD::ClosePDA()
{
	if (PDAUI.IsValid())
	{
		PDAUI->Close();
	}
	UpdateInputMode();
}

void ADAHUD::TogglePDA(EDAPDATab Tab)
{
	if (IsDialogueOpen() || IsDuelOpen())
	{
		return;
	}
	if (IsPDAOpen())
	{
		ClosePDA();
	}
	else
	{
		OpenPDA(Tab);
	}
}

void ADAHUD::UpdateInputMode()
{
	APlayerController* PC = GetOwningPlayerController();
	if (!PC)
	{
		return;
	}
	// The duel UI owns its input mode (deck select/board/result); never fight it.
	if (IsDuelOpen())
	{
		return;
	}
	const bool bWantCursor = bMapOpen || IsPDAOpen() || IsDialogueOpen();
	PC->bShowMouseCursor = bWantCursor;
	if (bWantCursor)
	{
		FInputModeGameAndUI Mode;
		Mode.SetHideCursorDuringCapture(false);
		PC->SetInputMode(Mode);
	}
	else
	{
		PC->SetInputMode(FInputModeGameOnly());
	}
}

void ADAHUD::HandlePDAClosed()
{
	UpdateInputMode();
}

void ADAHUD::HandleDialogueClosed(const FString& ConversationId)
{
	UpdateInputMode();
}

void ADAHUD::HandlePDAAction(FName ActionId, const FString& Payload)
{
	const FString Action = ActionId.ToString();

	if (Action == TEXT("options.changed"))
	{
		FString OptionId;
		FString Value;
		if (Payload.Split(TEXT("="), &OptionId, &Value) && DialogueUI.IsValid())
		{
			if (OptionId == TEXT("text_speed"))
			{
				DialogueUI->SetTextSpeed(Value == TEXT("Slow") ? 28.f : (Value == TEXT("Fast") ? 90.f : 48.f));
			}
			else if (OptionId == TEXT("auto_advance"))
			{
				DialogueUI->SetAutoAdvance(Value == TEXT("On"));
			}
		}
		return;
	}

	FString Body;
	if (Action == TEXT("deck.open"))
	{
		Body = TEXT("Deck editor hook: A06's DADeckUI is not connected yet.");
	}
	else if (Action == TEXT("mail.open"))
	{
		Body = TEXT("Mail reader hook: A03's mailbox is not connected yet.");
	}
	else if (Action == TEXT("save.slot"))
	{
		Body = TEXT("Save/load hook: A02's SaveSubsystem is not connected yet.");
	}
	if (!Body.IsEmpty())
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
		{
			FDAMessage Msg;
			Msg.Title = TEXT("PDA");
			Msg.Body = Body;
			Msg.Accent = HudGold;
			Msg.Duration = 3.5f;
			Sub->PushMessage(Msg);
		}
	}
}

void ADAHUD::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (DuelUI.IsValid())
	{
		DuelUI->Update(DeltaSeconds);
	}

	// Exactly one modal UI consumes input at a time: dialogue sits above the PDA.
	if (IsDialogueOpen())
	{
		DialogueUI->Update(DeltaSeconds);
	}
	else if (IsPDAOpen())
	{
		PDAUI->Update(DeltaSeconds);
	}

	// P is polled here (like the map keys) so it works in GameAndUI mode and
	// does not need a new Enhanced Input action in the shared student pawn.
	if (!IsDuelOpen() && !IsDialogueOpen())
	{
		if (APlayerController* PC = GetOwningPlayerController())
		{
			if (PC->WasInputKeyJustPressed(EKeys::P)
				|| PC->WasInputKeyJustPressed(EKeys::Gamepad_Special_Left))
			{
				TogglePDA();
			}
		}
	}

	// The island map is drawn with the mouse cursor visible (GameAndUI input mode). In that mode the
	// Enhanced Input bindings for Enter and the mouse click can be swallowed, so poll the map keys here,
	// exactly like the duel UI does.
	if (bMapOpen && !IsDuelOpen() && !IsPDAOpen() && !IsDialogueOpen())
	{
		if (APlayerController* PC = GetOwningPlayerController())
		{
			if (PC->WasInputKeyJustPressed(EKeys::Up) || PC->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Up))
			{
				MoveMapSelection(-1);
			}
			if (PC->WasInputKeyJustPressed(EKeys::Down) || PC->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down))
			{
				MoveMapSelection(1);
			}
			if (PC->WasInputKeyJustPressed(EKeys::Enter) || PC->WasInputKeyJustPressed(EKeys::SpaceBar)
				|| PC->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
			{
				TravelToZone();
			}
			else if (PC->WasInputKeyJustPressed(EKeys::Escape))
			{
				ToggleMap();
			}
			else if (PC->WasInputKeyJustPressed(EKeys::LeftMouseButton))
			{
				ADALocationVolume* Clicked = PickZoneUnderCursor();
				ADALocationVolume* Row = Clicked ? nullptr : PickZoneRowUnderCursor();
				if (Clicked)
				{
					TravelToZone(Clicked);
				}
				else if (Row)
				{
					TravelToZone(Row);
				}
			}
		}
	}
}

// ------------------------------------------------------------------------ helpers

void ADAHUD::Text(const FString& Str, float X, float Y, const FLinearColor& Color, float Scale, bool bCenter, UFont* Font)
{
	if (!Canvas || Str.IsEmpty())
	{
		return;
	}
	UFont* F = Font ? Font : SmallFont.Get();
	FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(Str), F, Color);
	Item.Scale = FVector2D(Scale * S(), Scale * S());
	Item.bCentreX = bCenter;
	Item.EnableShadow(FLinearColor(0.f, 0.f, 0.f, 0.75f * Color.A), FVector2D(1.5f * S(), 1.5f * S()));
	Canvas->DrawItem(Item);
}

FVector2D ADAHUD::Measure(const FString& Str, float Scale, UFont* Font) const
{
	const UFont* F = Font ? Font : SmallFont.Get();
	if (!F || Str.IsEmpty())
	{
		return FVector2D::ZeroVector;
	}
	const float K = Scale * UIScale;
	return FVector2D(F->GetStringSize(*Str) * K, F->GetStringHeightSize(*Str) * K);
}

TArray<FString> ADAHUD::Wrap(const FString& Str, float MaxWidth, float Scale, UFont* Font) const
{
	TArray<FString> Out;
	TArray<FString> Paragraphs;
	Str.ParseIntoArray(Paragraphs, TEXT("\n"), false);
	for (const FString& Para : Paragraphs)
	{
		TArray<FString> Words;
		Para.ParseIntoArray(Words, TEXT(" "), true);
		FString Line;
		for (const FString& W : Words)
		{
			const FString Candidate = Line.IsEmpty() ? W : Line + TEXT(" ") + W;
			if (!Line.IsEmpty() && Measure(Candidate, Scale, Font).X > MaxWidth)
			{
				Out.Add(Line);
				Line = W;
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

void ADAHUD::Panel(float X, float Y, float W, float H, const FLinearColor& Accent, float Alpha)
{
	DrawRect(HudAlpha(HudInk, Alpha), X, Y, W, H);
	DrawRect(HudAlpha(Accent, 0.95f), X, Y, 5.f * S(), H);
	DrawRect(HudAlpha(Accent, 0.5f), X, Y + H - 2.f * S(), W, 2.f * S());
}

void ADAHUD::Diamond(const FVector2D& C, float R, const FLinearColor& Color)
{
	if (!Canvas)
	{
		return;
	}
	const FVector2D T(C.X, C.Y - R), B(C.X, C.Y + R), L(C.X - R, C.Y), Rt(C.X + R, C.Y);
	FCanvasTriangleItem Tri1(T, Rt, B, GWhiteTexture);
	Tri1.SetColor(Color);
	Tri1.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tri1);
	FCanvasTriangleItem Tri2(T, B, L, GWhiteTexture);
	Tri2.SetColor(Color);
	Tri2.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tri2);
}

void ADAHUD::Arrow(const FVector2D& C, float R, float YawDeg, const FLinearColor& Color)
{
	if (!Canvas)
	{
		return;
	}
	// Screen space: +X right (east), +Y down (south). UE yaw 0 = east, 90 = south (map is north-up).
	const float A = FMath::DegreesToRadians(YawDeg);
	const FVector2D Fwd(FMath::Cos(A), FMath::Sin(A));
	const FVector2D Side(-Fwd.Y, Fwd.X);
	FCanvasTriangleItem Tri(C + Fwd * R * 1.3f, C - Fwd * R * 0.8f + Side * R * 0.8f, C - Fwd * R * 0.8f - Side * R * 0.8f, GWhiteTexture);
	Tri.SetColor(Color);
	Tri.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tri);
}

FVector2D ADAHUD::WorldToMapUV(const FVector& World) const
{
	const double U = (World.X - MapMin.X) / FMath::Max(MapMax.X - MapMin.X, 1.0);
	const double V = (World.Y - MapMin.Y) / FMath::Max(MapMax.Y - MapMin.Y, 1.0);
	return FVector2D(U, V);
}

// ------------------------------------------------------------------------ map / selection

void ADAHUD::ToggleMap()
{
	if (IsDuelOpen() || IsDialogueOpen() || IsPDAOpen())
	{
		return;
	}
	bMapOpen = !bMapOpen;
	if (APlayerController* PC = GetOwningPlayerController())
	{
		PC->bShowMouseCursor = bMapOpen;
		if (bMapOpen)
		{
			FInputModeGameAndUI Mode;
			Mode.SetHideCursorDuringCapture(false);
			PC->SetInputMode(Mode);
			// Pre-select the zone we are standing in.
			if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
			{
				const TArray<ADALocationVolume*> Zones = Sub->GetZones();
				const int32 Current = Zones.IndexOfByKey(Sub->GetCurrentZone());
				if (Current != INDEX_NONE)
				{
					MapSelection = Current;
				}
				Sub->PlayUISound(TEXT("A_UIClick"), 0.5f);
			}
		}
		else
		{
			PC->SetInputMode(FInputModeGameOnly());
		}
	}
}

void ADAHUD::ToggleHelp()
{
	if (IsDuelOpen() || IsPDAOpen() || IsDialogueOpen())
	{
		return;
	}
	bHelpOpen = !bHelpOpen;
}

void ADAHUD::MoveMapSelection(int32 Delta)
{
	if (!bMapOpen)
	{
		return;
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		const int32 Num = Sub->GetZones().Num();
		if (Num > 0)
		{
			MapSelection = (MapSelection + Delta + Num) % Num;
			Sub->PlayUISound(TEXT("A_UIClick"), 0.35f);
		}
	}
}

ADALocationVolume* ADAHUD::GetSelectedZone() const
{
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		const TArray<ADALocationVolume*> Zones = Sub->GetZones();
		if (Zones.IsValidIndex(MapSelection))
		{
			return Zones[MapSelection];
		}
	}
	return nullptr;
}

void ADAHUD::TravelToZone(ADALocationVolume* Zone)
{
	ADALocationVolume* Target = Zone ? Zone : GetSelectedZone();
	if (!Target || !Target->bFastTravel)
	{
		return;
	}
	// Close the map first so the camera/input mode is back to gameplay before the teleport.
	ToggleMap();
	if (APlayerController* PC = GetOwningPlayerController())
	{
		if (ADAStudentCharacter* Character = Cast<ADAStudentCharacter>(PC->GetPawn()))
		{
			Character->FastTravelTo(Target);
		}
	}
}

ADALocationVolume* ADAHUD::PickZoneRowUnderCursor() const
{
	APlayerController* PC = GetOwningPlayerController();
	const UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	if (!PC || !Sub)
	{
		return nullptr;
	}
	int32 ViewW = 0;
	int32 ViewH = 0;
	PC->GetViewportSize(ViewW, ViewH);
	const TArray<ADALocationVolume*> Zones = Sub->GetZones();
	if (ViewW <= 0 || ViewH <= 0 || Zones.Num() == 0)
	{
		return nullptr;
	}
	// Mirror the side-list layout from DrawMap, using the live viewport rather than the last canvas.
	const float CW = static_cast<float>(ViewW);
	const float CH = static_cast<float>(ViewH);
	const float S = FMath::Clamp(CH / 1080.f, 0.6f, 2.5f);
	const float Side = FMath::Min(CH * 0.86f, CW * 0.58f);
	const float MX = CW * 0.04f;
	const float MY = (CH - Side) * 0.5f;
	const float LX = MX + Side + 40.f * S;
	const float RowH = 30.f * S;
	const float LW = CW - LX - 40.f * S;
	float MouseX = -1.f;
	float MouseY = -1.f;
	PC->GetMousePosition(MouseX, MouseY);
	if (MouseX < LX - 8.f * S || MouseX > LX - 8.f * S + LW)
	{
		return nullptr;
	}
	const int32 Index = FMath::FloorToInt((MouseY - (MY + 97.f * S)) / FMath::Max(RowH, 1.f));
	return Zones.IsValidIndex(Index) ? Zones[Index] : nullptr;
}

// ------------------------------------------------------------------------ main draw

void ADAHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas)
	{
		return;
	}
	UIScale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.6f, 2.5f);
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	ADAIslandManager* M = Sub ? Sub->GetManager() : nullptr;
	if (M)
	{
		MapTexture = M->MapTexture;
		MapMin = M->MapMin;
		MapMax = M->MapMax;
	}
	const float Time = GetWorld()->GetTimeSeconds();

	if (DuelUI.IsValid() && DuelUI->IsOpen())
	{
		DuelUI->Draw(Canvas);
		return;
	}

	if (bMapOpen && Sub)
	{
		DrawMap(Sub);
		return;
	}

	if (Sub)
	{
		DrawCompass(Sub);
		DrawMinimap(Sub);
		DrawBanner(Sub, Time);
		DrawMessage(Sub);
	}
	DrawClock(M);
	if (!IsPDAOpen() && !IsDialogueOpen())
	{
		DrawPrompt();
		DrawIntro(Time - StartTime);
	}

	if (PDAUI.IsValid() && PDAUI->IsOpen())
	{
		PDAUI->Draw(Canvas);
	}
	if (DialogueUI.IsValid() && DialogueUI->IsOpen())
	{
		DialogueUI->Draw(Canvas);
	}
	if (bHelpOpen)
	{
		DrawHelp();
	}
}

void ADAHUD::DrawIntro(float T)
{
	if (T > 9.f)
	{
		return;
	}
	const float A = FMath::Clamp(T / 0.8f, 0.f, 1.f) * FMath::Clamp((9.f - T) / 1.5f, 0.f, 1.f);
	const float CX = Canvas->ClipX * 0.5f;
	const float Y = Canvas->ClipY * 0.2f;
	Text(TEXT("DUEL ACADEMY"), CX, Y, HudAlpha(HudGold, A), 3.2f, true, BigFont);
	Text(TEXT("ISLAND"), CX, Y + 92.f * S(), HudAlpha(HudPaper, A), 1.8f, true, BigFont);
	Text(TEXT("Explore the island  -  M: map  -  P: PDA  -  E: interact  -  F1: controls"), CX, Y + 150.f * S(), HudAlpha(HudPaper, A * 0.9f), 1.0f, true);
}

void ADAHUD::DrawBanner(UDAIslandSubsystem* Sub, float Time)
{
	ADALocationVolume* Zone = Sub->GetCurrentZone();
	const float Age = Time - Sub->GetZoneChangeTime();
	if (!Zone || Age > 5.5f || Time - StartTime < 4.f)
	{
		return;
	}
	const float A = FMath::Clamp(Age / 0.5f, 0.f, 1.f) * FMath::Clamp((5.5f - Age) / 1.0f, 0.f, 1.f);
	const float CX = Canvas->ClipX * 0.5f;
	const float Y = Canvas->ClipY * 0.24f;
	const FString Name = Zone->DisplayName.ToUpper();
	const FVector2D Size = Measure(Name, 2.2f, BigFont);
	const float W = FMath::Max(Size.X + 120.f * S(), 420.f * S());
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.45f * A), CX - W * 0.5f, Y - 18.f * S(), W, 140.f * S());
	DrawRect(HudAlpha(Zone->ThemeColor, 0.95f * A), CX - W * 0.5f, Y - 18.f * S(), W, 4.f * S());
	DrawRect(HudAlpha(Zone->ThemeColor, 0.95f * A), CX - W * 0.5f, Y + 118.f * S(), W, 4.f * S());
	if (Sub->WasFirstVisit())
	{
		Text(TEXT("NEW LOCATION DISCOVERED"), CX, Y - 8.f * S(), HudAlpha(HudGold, A), 0.9f, true);
	}
	Text(Name, CX, Y + 14.f * S(), HudAlpha(HudPaper, A), 2.2f, true, BigFont);
	Text(Zone->Subtitle, CX, Y + 80.f * S(), HudAlpha(Zone->ThemeColor, A), 1.1f, true);
}

void ADAHUD::DrawCompass(UDAIslandSubsystem* Sub)
{
	APlayerController* PC = GetOwningPlayerController();
	if (!PC)
	{
		return;
	}
	const float Yaw = PC->GetControlRotation().Yaw;
	const float CX = Canvas->ClipX * 0.5f;
	const float Y = 18.f * S();
	const float W = 620.f * S();
	const float PxPerDeg = W / 180.f;
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.35f), CX - W * 0.5f, Y, W, 34.f * S());

	struct FMark { float Yaw; const TCHAR* Label; };
	// The island's north is UE -Y (yaw -90); east is +X (yaw 0).
	static const FMark Marks[] = {
		{ -90.f, TEXT("N") }, { -45.f, TEXT("NE") }, { 0.f, TEXT("E") }, { 45.f, TEXT("SE") },
		{ 90.f, TEXT("S") }, { 135.f, TEXT("SW") }, { 180.f, TEXT("W") }, { -135.f, TEXT("NW") } };
	for (const FMark& Mk : Marks)
	{
		const float D = FMath::FindDeltaAngleDegrees(Yaw, Mk.Yaw);
		if (FMath::Abs(D) < 88.f)
		{
			const bool bMajor = FCString::Strlen(Mk.Label) == 1;
			Text(Mk.Label, CX + D * PxPerDeg, Y + 6.f * S(), bMajor ? (Mk.Yaw == -90.f ? HudGold : HudPaper) : HudAlpha(HudPaper, 0.6f), bMajor ? 1.0f : 0.75f, true);
		}
	}
	for (int32 Deg = -180; Deg < 180; Deg += 15)
	{
		const float D = FMath::FindDeltaAngleDegrees(Yaw, static_cast<float>(Deg));
		if (FMath::Abs(D) < 88.f && Deg % 45 != 0)
		{
			DrawRect(HudAlpha(HudPaper, 0.5f), CX + D * PxPerDeg - 1.f, Y + 22.f * S(), 2.f, 8.f * S());
		}
	}
	// Location markers within 1 km
	if (const APawn* Pawn = PC->GetPawn())
	{
		const FVector P = Pawn->GetActorLocation();
		for (ADALocationVolume* Z : Sub->GetZones())
		{
			const FVector To = Z->GetActorLocation() - P;
			const double Dist = FVector(To.X, To.Y, 0.0).Size();
			if (Dist < 2000.0 || Dist > 100000.0 || Z == Sub->GetCurrentZone())
			{
				continue;
			}
			const float ZYaw = FMath::RadiansToDegrees(FMath::Atan2(To.Y, To.X));
			const float D = FMath::FindDeltaAngleDegrees(Yaw, ZYaw);
			if (FMath::Abs(D) < 85.f)
			{
				Diamond(FVector2D(CX + D * PxPerDeg, Y + 44.f * S()), 6.f * S(), HudAlpha(Z->ThemeColor, 0.95f));
			}
		}
	}
	DrawRect(HudGold, CX - 1.5f * S(), Y - 4.f * S(), 3.f * S(), 42.f * S());
}

void ADAHUD::DrawMinimap(UDAIslandSubsystem* Sub)
{
	APlayerController* PC = GetOwningPlayerController();
	const APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return;
	}
	const float Size = 250.f * S();
	const float X0 = Canvas->ClipX - Size - 28.f * S();
	const float Y0 = Canvas->ClipY - Size - 64.f * S();
	const FVector P = Pawn->GetActorLocation();
	const double ViewRadius = 32000.0; // 320 m shown in each direction
	const FVector2D C = WorldToMapUV(P);
	const double MapSpan = FMath::Max(MapMax.X - MapMin.X, 1.0);
	const double HalfUV = ViewRadius / MapSpan;

	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), X0 - 4.f * S(), Y0 - 4.f * S(), Size + 8.f * S(), Size + 8.f * S());
	if (MapTexture && MapTexture->GetResource())
	{
		FCanvasTileItem Tile(FVector2D(X0, Y0), MapTexture->GetResource(), FVector2D(Size, Size),
			FVector2D(C.X - HalfUV, C.Y - HalfUV), FVector2D(C.X + HalfUV, C.Y + HalfUV), FLinearColor::White);
		Tile.BlendMode = SE_BLEND_Opaque;
		Canvas->DrawItem(Tile);
	}
	else
	{
		DrawRect(FLinearColor(0.1f, 0.3f, 0.45f, 0.9f), X0, Y0, Size, Size);
	}
	// zone markers
	for (ADALocationVolume* Z : Sub->GetZones())
	{
		if (!Z->bShowOnMap)
		{
			continue;
		}
		const FVector2D UV = WorldToMapUV(Z->GetActorLocation());
		const FVector2D Rel((UV.X - C.X) / (2.0 * HalfUV) + 0.5, (UV.Y - C.Y) / (2.0 * HalfUV) + 0.5);
		if (Rel.X < 0.03 || Rel.X > 0.97 || Rel.Y < 0.03 || Rel.Y > 0.97)
		{
			continue;
		}
		Diamond(FVector2D(X0 + Rel.X * Size, Y0 + Rel.Y * Size), 6.f * S(), HudAlpha(Z->ThemeColor, Sub->IsDiscovered(Z) ? 1.f : 0.45f));
	}
	Arrow(FVector2D(X0 + Size * 0.5f, Y0 + Size * 0.5f), 9.f * S(), Pawn->GetActorRotation().Yaw, HudGold);
	Text(TEXT("N"), X0 + Size * 0.5f, Y0 + 4.f * S(), HudGold, 0.9f, true);

	// zone + progress under the minimap
	const ADALocationVolume* Zone = Sub->GetCurrentZone();
	Text(Zone ? Zone->DisplayName : FString(TEXT("Duel Academy Island")), X0 + Size * 0.5f, Y0 + Size + 8.f * S(), HudPaper, 0.9f, true);
	const int32 Total = Sub->GetZones().Num();
	FString Progress = FString::Printf(TEXT("Explored %d / %d"), Sub->NumDiscovered(), Total);
	if (const ADAStudentCharacter* Student = Cast<ADAStudentCharacter>(Pawn))
	{
		Progress += FString::Printf(TEXT("    Cards %d"), Student->GetCollectionSize());
	}
	Text(Progress, X0 + Size * 0.5f, Y0 + Size + 30.f * S(), HudAlpha(HudPaper, 0.7f), 0.75f, true);
}

void ADAHUD::DrawClock(ADAIslandManager* M)
{
	if (!M)
	{
		return;
	}
	const float X = Canvas->ClipX - 28.f * S();
	FString Clock = M->GetClockText();
	if (M->bTimePaused)
	{
		Clock += TEXT("  (paused)");
	}
	else if (M->TimeSpeed > 1.01f)
	{
		Clock += FString::Printf(TEXT("  x%.0f"), M->TimeSpeed);
	}
	const FVector2D Sz = Measure(Clock, 1.0f);
	Text(Clock, X - Sz.X, 22.f * S(), HudPaper, 1.0f);
	Text(M->IsNight() ? TEXT("Night") : TEXT("Day"), X - Measure(M->IsNight() ? TEXT("Night") : TEXT("Day"), 0.75f).X, 48.f * S(), HudAlpha(HudGold, 0.85f), 0.75f);
}

void ADAHUD::DrawPrompt()
{
	const APlayerController* PC = GetOwningPlayerController();
	const ADAStudentCharacter* Student = PC ? Cast<ADAStudentCharacter>(PC->GetPawn()) : nullptr;
	AActor* Target = Student ? Student->GetFocusedInteractable() : nullptr;
	const IDAInteractableInterface* I = Target ? Cast<IDAInteractableInterface>(Target) : nullptr;
	if (!I)
	{
		return;
	}
	const FString Line = FString::Printf(TEXT("[E]  %s  -  %s"), *I->GetInteractPrompt(), *I->GetInteractName());
	const FVector2D Sz = Measure(Line, 1.1f);
	const float X = Canvas->ClipX * 0.5f - Sz.X * 0.5f - 18.f * S();
	const float Y = Canvas->ClipY * 0.72f;
	Panel(X, Y, Sz.X + 36.f * S(), Sz.Y + 18.f * S(), HudGold, 0.6f);
	Text(Line, X + 20.f * S(), Y + 8.f * S(), HudPaper, 1.1f);
}

void ADAHUD::DrawMessage(UDAIslandSubsystem* Sub)
{
	const FDAMessage* Msg = Sub->GetActiveMessage();
	if (!Msg)
	{
		return;
	}
	const float Age = Sub->GetActiveMessageAge();
	const float A = FMath::Clamp(Age / 0.25f, 0.f, 1.f) * (Msg->Duration > 0.f ? FMath::Clamp((Msg->Duration - Age) / 0.5f, 0.f, 1.f) : 1.f);
	const float W = FMath::Min(760.f * S(), Canvas->ClipX * 0.6f);
	const TArray<FString> Lines = Wrap(Msg->Body, W - 48.f * S(), 0.95f);
	const float LineH = Measure(TEXT("Ag"), 0.95f).Y + 3.f * S();
	const float H = 64.f * S() + Lines.Num() * LineH + 26.f * S();
	const float X = 40.f * S();
	const float Y = Canvas->ClipY - H - 60.f * S();
	Panel(X, Y, W, H, Msg->Accent, 0.78f * A);
	Text(Msg->Title, X + 24.f * S(), Y + 14.f * S(), HudAlpha(Msg->Accent, A), 1.35f, false, BigFont);
	float LY = Y + 60.f * S();
	for (const FString& L : Lines)
	{
		Text(L, X + 24.f * S(), LY, HudAlpha(HudPaper, A), 0.95f);
		LY += LineH;
	}
	Text(TEXT("[E] close"), X + W - 110.f * S(), Y + H - 26.f * S(), HudAlpha(HudPaper, 0.5f * A), 0.7f);
}

void ADAHUD::DrawHelp()
{
	static const TCHAR* Lines[] = {
		TEXT("WASD / Left stick ........ Move"),
		TEXT("Mouse / Right stick ...... Look"),
		TEXT("Mouse wheel .............. Camera zoom"),
		TEXT("Shift / L3 ............... Sprint"),
		TEXT("Space / A ................ Jump"),
		TEXT("E / X .................... Interact (signs, card shop, duel fields, students)"),
		TEXT("M / Tab ................. Island map & fast travel"),
		TEXT("P ....................... PDA (map, calendar, deck, mail, save, options, records)"),
		TEXT("J ........................ Switch dorm jacket"),
		TEXT("F ........................ Raise duel disk"),
		TEXT("T ........................ Pause / resume time"),
		TEXT("[  ] ..................... Slower / faster time"),
		TEXT("N ........................ Skip 3 hours"),
		TEXT("Dialogue: E/SPACE advance   H log   A auto   Ctrl skip"),
		TEXT("F1 / H ................... Toggle this help"),
	};
	// CC-BY 3.0 models require visible attribution; the full list is in CREDITS.md
	static const TCHAR* Credits[] = {
		TEXT("Art credits: textures, skies and plants from Poly Haven, ambientCG, 3dtextures.me (CC0); trees made with EZ-Tree (MIT)."),
		TEXT("Palm, acacia, hydrangea and rose models by Space Mushrooms & Scopia (Sweet Home 3D library), CC BY 3.0, modified."),
		TEXT("Sketchfab models (CC BY 4.0, modified): stealth86, TampaJoey, Ashkelon, plaggy, MarcHoogkamp,"),
		TEXT("TooManyDemons, Tetiana_Denysenko, Memorie, adventurer, yonimantz. Fishing boat by Poly by Google, CC BY 3.0."),
		TEXT("Further CC0 / CC-BY assets and their authors: see CREDITS.md. Unofficial fan project, not affiliated with Konami."),
	};
	const float W = 1000.f * S();
	const float LineH = 30.f * S();
	const float CreditH = 22.f * S();
	const float H = 110.f * S() + UE_ARRAY_COUNT(Lines) * LineH + UE_ARRAY_COUNT(Credits) * CreditH;
	const float X = Canvas->ClipX * 0.5f - W * 0.5f;
	const float Y = Canvas->ClipY * 0.5f - H * 0.5f;
	Panel(X, Y, W, H, HudGold, 0.85f);
	Text(TEXT("CONTROLS"), X + 28.f * S(), Y + 18.f * S(), HudGold, 1.4f, false, BigFont);
	float LY = Y + 72.f * S();
	for (const TCHAR* L : Lines)
	{
		Text(L, X + 28.f * S(), LY, HudPaper, 0.95f);
		LY += LineH;
	}
	LY += 14.f * S();
	for (const TCHAR* L : Credits)
	{
		Text(L, X + 28.f * S(), LY, HudAlpha(HudPaper, 0.6f), 0.68f);
		LY += CreditH;
	}
}

void ADAHUD::DrawMap(UDAIslandSubsystem* Sub)
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	DrawRect(FLinearColor(0.f, 0.02f, 0.05f, 0.88f), 0.f, 0.f, CW, CH);

	const float Side = FMath::Min(CH * 0.86f, CW * 0.58f);
	const float MX = CW * 0.04f;
	const float MY = (CH - Side) * 0.5f;
	if (MapTexture && MapTexture->GetResource())
	{
		FCanvasTileItem Tile(FVector2D(MX, MY), MapTexture->GetResource(), FVector2D(Side, Side), FVector2D(0.0, 0.0), FVector2D(1.0, 1.0), FLinearColor::White);
		Tile.BlendMode = SE_BLEND_Opaque;
		Canvas->DrawItem(Tile);
	}
	else
	{
		DrawRect(FLinearColor(0.1f, 0.3f, 0.45f, 1.f), MX, MY, Side, Side);
	}
	Text(TEXT("N"), MX + Side * 0.5f, MY + 8.f * S(), HudGold, 1.3f, true, BigFont);

	float MouseX = -1.f;
	float MouseY = -1.f;
	if (APlayerController* PC = GetOwningPlayerController())
	{
		PC->GetMousePosition(MouseX, MouseY);
	}

	const TArray<ADALocationVolume*> Zones = Sub->GetZones();
	HoveredZone.Reset();
	float BestHover = 30.f * S();
	for (int32 i = 0; i < Zones.Num(); ++i)
	{
		const FVector2D UV = WorldToMapUV(Zones[i]->GetActorLocation());
		const FVector2D Pt(MX + UV.X * Side, MY + UV.Y * Side);
		const float D = FVector2D::Distance(Pt, FVector2D(MouseX, MouseY));
		if (D < BestHover)
		{
			BestHover = D;
			HoveredZone = Zones[i];
		}
	}
	for (int32 i = 0; i < Zones.Num(); ++i)
	{
		ADALocationVolume* Z = Zones[i];
		const FVector2D UV = WorldToMapUV(Z->GetActorLocation());
		const FVector2D Pt(MX + UV.X * Side, MY + UV.Y * Side);
		const bool bSel = i == MapSelection || Z == HoveredZone.Get();
		const bool bKnown = Sub->IsDiscovered(Z);
		Diamond(Pt, (bSel ? 13.f : 9.f) * S(), FLinearColor(0.f, 0.f, 0.f, 0.8f));
		Diamond(Pt, (bSel ? 10.f : 7.f) * S(), HudAlpha(Z->ThemeColor, bKnown ? 1.f : 0.55f));
		Text(Z->DisplayName, Pt.X, Pt.Y + 12.f * S(), bSel ? HudGold : HudAlpha(HudPaper, bKnown ? 0.95f : 0.6f), bSel ? 0.9f : 0.72f, true);
	}
	if (const APlayerController* PC = GetOwningPlayerController())
	{
		if (const APawn* Pawn = PC->GetPawn())
		{
			const FVector2D UV = WorldToMapUV(Pawn->GetActorLocation());
			Arrow(FVector2D(MX + UV.X * Side, MY + UV.Y * Side), 12.f * S(), Pawn->GetActorRotation().Yaw, HudGold);
		}
	}

	// side list
	const float LX = MX + Side + 40.f * S();
	const float LW = CW - LX - 40.f * S();
	Text(TEXT("ISLAND MAP"), LX, MY, HudGold, 2.0f, false, BigFont);
	Text(TEXT("Up / Down select    Enter travel    Click a marker    M close"), LX, MY + 62.f * S(), HudAlpha(HudPaper, 0.7f), 0.8f);
	float LY = MY + 100.f * S();
	const float RowH = 30.f * S();
	for (int32 i = 0; i < Zones.Num(); ++i)
	{
		ADALocationVolume* Z = Zones[i];
		const bool bSel = i == MapSelection;
		if (bSel)
		{
			DrawRect(HudAlpha(Z->ThemeColor, 0.35f), LX - 8.f * S(), LY - 3.f * S(), LW, RowH);
		}
		DrawRect(HudAlpha(Z->ThemeColor, 1.f), LX - 8.f * S(), LY - 3.f * S(), 4.f * S(), RowH);
		const FString Label = Sub->IsDiscovered(Z) ? Z->DisplayName : Z->DisplayName + TEXT("  (unexplored)");
		Text(Label, LX + 6.f * S(), LY, bSel ? HudPaper : HudAlpha(HudPaper, 0.75f), 0.95f);
		LY += RowH;
	}
	if (ADALocationVolume* Sel = Zones.IsValidIndex(MapSelection) ? Zones[MapSelection] : nullptr)
	{
		LY += 16.f * S();
		Text(Sel->DisplayName, LX, LY, Sel->ThemeColor, 1.3f, false, BigFont);
		LY += 46.f * S();
		Text(Sel->Subtitle, LX, LY, HudAlpha(HudPaper, 0.8f), 0.9f);
		LY += 32.f * S();
		for (const FString& L : Wrap(Sel->Description, LW - 10.f * S(), 0.9f))
		{
			Text(L, LX, LY, HudPaper, 0.9f);
			LY += 26.f * S();
		}
	}
}
