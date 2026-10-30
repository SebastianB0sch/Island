// Duel Academy Island - Canvas dialogue box implementation.

#include "DADialogueUI.h"

#include "CanvasItem.h"
#include "DACharacterPortraitSubsystem.h"
#include "DAHUD.h"
#include "DAIslandSubsystem.h"
#include "DuelAcademyIsland.h"
#include "Dom/JsonObject.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "RenderUtils.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "TextureResource.h"

namespace
{
	const FLinearColor DlgGold(1.f, 0.78f, 0.25f);
	const FLinearColor DlgInk(0.012f, 0.022f, 0.04f);
	const FLinearColor DlgPaper(0.95f, 0.95f, 0.97f);
	const FLinearColor DlgMuted(0.62f, 0.66f, 0.72f);

	FLinearColor DialogueAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}
}

FDADialogueUI::FDADialogueUI(ADAHUD* InOwner)
	: OwnerHUD(InOwner)
{
	PlayerOwner = InOwner ? InOwner->GetOwningPlayerController() : nullptr;
}

FDADialogueUI::~FDADialogueUI() = default;

UWorld* FDADialogueUI::GetWorld() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetWorld() : nullptr;
}

UGameInstance* FDADialogueUI::GetGameInstance() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetGameInstance() : nullptr;
}

UCharacterPortraitSubsystem* FDADialogueUI::GetPortraitArt() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UCharacterPortraitSubsystem>() : nullptr;
}

UFont* FDADialogueUI::GetFont(bool bLarge) const
{
	if (OwnerHUD.IsValid())
	{
		return bLarge ? OwnerHUD->GetBigFont() : OwnerHUD->GetSmallFont();
	}
	return bLarge ? (GEngine ? GEngine->GetLargeFont() : nullptr) : (GEngine ? GEngine->GetMediumFont() : nullptr);
}

void FDADialogueUI::PlaySfx(const TCHAR* SoundName, float Volume) const
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

void FDADialogueUI::Begin(const TArray<FDADialogueLine>& InLines, const FString& InConversationId)
{
	if (InLines.Num() == 0)
	{
		Close();
		return;
	}
	if (bOpen)
	{
		Close();
	}

	Lines = InLines;
	ConversationId = InConversationId;
	LineIndex = -1;
	LastShownLine = INDEX_NONE;
	Revealed = 0.f;
	AutoTimer = 0.f;
	SkipTimer = 0.f;
	Elapsed = 0.f;
	ChoiceSelection = 0;
	bHistoryOpen = false;
	bEscapeClose = true;
	bOpen = true;

	GoToLine(0);
	PlaySfx(TEXT("A_UIClick"), 0.35f);
}

void FDADialogueUI::BeginLine(const FDADialogueLine& InLine, const FString& InConversationId)
{
	TArray<FDADialogueLine> Single;
	Single.Add(InLine);
	Begin(Single, InConversationId);
}

void FDADialogueUI::Close()
{
	if (!bOpen)
	{
		return;
	}
	const FString ClosedId = ConversationId;
	bOpen = false;
	bTyping = false;
	bHistoryOpen = false;
	Lines.Reset();
	LineIndex = 0;
	LastShownLine = INDEX_NONE;
	HitTargets.Reset();
	ConversationId.Reset();
	OnDialogueClosed.Broadcast(ClosedId);
}

bool FDADialogueUI::IsWaitingForChoice() const
{
	return bOpen && !bTyping && Lines.IsValidIndex(LineIndex) && Lines[LineIndex].bChoice;
}

void FDADialogueUI::GoToLine(int32 NewIndex)
{
	if (!Lines.IsValidIndex(NewIndex))
	{
		Close();
		return;
	}
	LineIndex = NewIndex;
	Revealed = 0.f;
	AutoTimer = 0.f;
	SkipTimer = 0.f;
	ChoiceSelection = 0;
	bTyping = !Lines[NewIndex].GetDisplayText().IsEmpty();

	if (LastShownLine != LineIndex)
	{
		PushLineToHistory();
		LastShownLine = LineIndex;
		OnLineShown.Broadcast(ConversationId, LineIndex);
	}
}

void FDADialogueUI::PushLineToHistory()
{
	if (!Lines.IsValidIndex(LineIndex))
	{
		return;
	}
	const FDADialogueLine& Line = Lines[LineIndex];
	History.Add(FString::Printf(TEXT("%s: %s"), *Line.GetDisplayName(), *Line.GetDisplayText()));
	if (History.Num() > 200)
	{
		History.RemoveAt(0, 50);
	}
}

// ------------------------------------------------------------------------ story API

bool FDADialogueUI::Advance()
{
	if (!bOpen)
	{
		return false;
	}
	if (bHistoryOpen)
	{
		bHistoryOpen = false;
		return true;
	}
	if (!Lines.IsValidIndex(LineIndex))
	{
		Close();
		return true;
	}

	const FDADialogueLine& Line = Lines[LineIndex];
	if (bTyping)
	{
		Revealed = static_cast<float>(Line.GetDisplayText().Len());
		bTyping = false;
		AutoTimer = 0.f;
		PlaySfx(TEXT("A_UIClick"), 0.45f);
		return true;
	}
	if (Line.bChoice)
	{
		return false;
	}
	if (Lines.IsValidIndex(LineIndex + 1))
	{
		GoToLine(LineIndex + 1);
		PlaySfx(TEXT("A_UIClick"), 0.5f);
		return true;
	}

	Close();
	return true;
}

bool FDADialogueUI::Choose(int32 OptionIndex)
{
	if (!bOpen || bTyping || !Lines.IsValidIndex(LineIndex))
	{
		return false;
	}
	const FDADialogueLine& Line = Lines[LineIndex];
	if (!Line.bChoice || !Line.Options.IsValidIndex(OptionIndex))
	{
		return false;
	}

	History.Add(FString::Printf(TEXT("%s: > %s"), *Line.GetDisplayName(), *Line.Options[OptionIndex]));
	const FString ChoiceConversation = ConversationId;
	OnChoiceMade.Broadcast(ChoiceConversation, OptionIndex);
	PlaySfx(TEXT("A_UIClick"), 0.7f);

	// A listener may have closed this conversation or started another one.
	if (!bOpen || ConversationId != ChoiceConversation)
	{
		return true;
	}
	if (Lines.IsValidIndex(LineIndex + 1))
	{
		GoToLine(LineIndex + 1);
	}
	else
	{
		Close();
	}
	return true;
}

void FDADialogueUI::SkipConversation()
{
	Close();
}

void FDADialogueUI::SetAutoAdvance(bool bEnabled, bool bPlaySound)
{
	bAuto = bEnabled;
	AutoTimer = 0.f;
	if (bAuto && bPlaySound)
	{
		PlaySfx(TEXT("A_UIClick"), 0.35f);
	}
}

void FDADialogueUI::ToggleAutoAdvance()
{
	SetAutoAdvance(!bAuto);
}

void FDADialogueUI::ToggleHistory()
{
	bHistoryOpen = !bHistoryOpen;
	HistoryScroll = 0;
	PlaySfx(TEXT("A_UIClick"), 0.4f);
}

void FDADialogueUI::ScrollHistory(int32 Delta)
{
	const int32 MaxScroll = FMath::Max(0, History.Num() - 1);
	HistoryScroll = FMath::Clamp(HistoryScroll + Delta, 0, MaxScroll);
}

void FDADialogueUI::SetTextSpeed(float InCharsPerSecond)
{
	CharsPerSecond = FMath::Clamp(InCharsPerSecond, 10.f, 10000.f);
}

// ------------------------------------------------------------------------ update

void FDADialogueUI::Update(float DeltaSeconds)
{
	if (!bOpen)
	{
		return;
	}

	PlayerOwner = OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr;
	Elapsed += DeltaSeconds;

	if (!Lines.IsValidIndex(LineIndex))
	{
		Close();
		return;
	}

	const FDADialogueLine& Line = Lines[LineIndex];
	const FString FullText = Line.GetDisplayText();
	const int32 TextLength = FullText.Len();

	if (bTyping)
	{
		Revealed += DeltaSeconds * CharsPerSecond;
		if (Revealed >= static_cast<float>(TextLength))
		{
			Revealed = static_cast<float>(TextLength);
			bTyping = false;
			AutoTimer = 0.f;
		}
	}

	if (bAuto && !bTyping && !Line.bChoice && !bHistoryOpen)
	{
		AutoTimer += DeltaSeconds;
		if (AutoTimer >= FMath::Max(0.4f, Line.AutoAdvanceDelay))
		{
			AutoTimer = 0.f;
			Advance();
			if (!bOpen)
			{
				return;
			}
		}
	}

	// Advance() may have changed the current line; always re-read it for input.
	if (!Lines.IsValidIndex(LineIndex))
	{
		Close();
		return;
	}
	const FDADialogueLine& InputLine = Lines[LineIndex];
	const int32 InputTextLength = InputLine.GetDisplayText().Len();

	if (!PlayerOwner)
	{
		return;
	}

	// History is modal inside the dialogue: navigation and close only.
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::H) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_Special_Left))
	{
		ToggleHistory();
	}
	if (bHistoryOpen)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Up) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Up)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::W))
		{
			ScrollHistory(1);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Down) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::S))
		{
			ScrollHistory(-1);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape))
		{
			bHistoryOpen = false;
			return;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::A))
	{
		ToggleAutoAdvance();
	}

	if (IsWaitingForChoice())
	{
		const int32 NumOptions = InputLine.Options.Num();
		if (NumOptions > 0
			&& (PlayerOwner->WasInputKeyJustPressed(EKeys::Up) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Up)
				|| PlayerOwner->WasInputKeyJustPressed(EKeys::W)))
		{
			ChoiceSelection = (ChoiceSelection - 1 + NumOptions) % NumOptions;
			PlaySfx(TEXT("A_UIClick"), 0.3f);
		}
		if (NumOptions > 0
			&& (PlayerOwner->WasInputKeyJustPressed(EKeys::Down) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down)
				|| PlayerOwner->WasInputKeyJustPressed(EKeys::S)))
		{
			ChoiceSelection = (ChoiceSelection + 1) % NumOptions;
			PlaySfx(TEXT("A_UIClick"), 0.3f);
		}

		static const FKey NumberKeys[] = {
			EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five,
			EKeys::Six, EKeys::Seven, EKeys::Eight, EKeys::Nine
		};
		for (int32 Index = 0; Index < UE_ARRAY_COUNT(NumberKeys) && Index < NumOptions; ++Index)
		{
			if (PlayerOwner->WasInputKeyJustPressed(NumberKeys[Index]))
			{
				Choose(Index);
				return;
			}
		}
	}

	const bool bSkipHeld = PlayerOwner->IsInputKeyDown(EKeys::LeftControl)
		|| PlayerOwner->IsInputKeyDown(EKeys::RightControl);
	if (bSkipHeld)
	{
		if (bTyping)
		{
			Revealed = static_cast<float>(InputTextLength);
			bTyping = false;
		}
		SkipTimer += DeltaSeconds;
		if (SkipTimer >= 0.06f)
		{
			SkipTimer = 0.f;
			Advance();
			if (!bOpen)
			{
				return;
			}
		}
	}
	else
	{
		SkipTimer = 0.f;
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
	{
		HandleClickAtMouse();
		return;
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape))
	{
		if (bEscapeClose)
		{
			Close();
		}
		return;
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::E)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Enter)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
	{
		if (IsWaitingForChoice())
		{
			Choose(ChoiceSelection);
		}
		else
		{
			Advance();
		}
	}
}

void FDADialogueUI::AddHit(const FString& Action, int32 Index, float X, float Y, float W, float H)
{
	FDADialogueHitTarget Hit;
	Hit.Action = Action;
	Hit.Index = Index;
	Hit.X = X;
	Hit.Y = Y;
	Hit.W = W;
	Hit.H = H;
	HitTargets.Add(Hit);
}

void FDADialogueUI::HandleClickAtMouse()
{
	if (!PlayerOwner)
	{
		return;
	}
	float MouseX = 0.f;
	float MouseY = 0.f;
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
	if (IsWaitingForChoice())
	{
		Choose(ChoiceSelection);
	}
	else
	{
		Advance();
	}
}

void FDADialogueUI::HandleHit(const FDADialogueHitTarget& Hit)
{
	if (Hit.Action == TEXT("choice"))
	{
		Choose(Hit.Index);
	}
	else if (Hit.Action == TEXT("history"))
	{
		ToggleHistory();
	}
	else if (Hit.Action == TEXT("history.close"))
	{
		bHistoryOpen = false;
	}
	else if (Hit.Action == TEXT("auto"))
	{
		ToggleAutoAdvance();
	}
	else if (Hit.Action == TEXT("skip"))
	{
		SkipConversation();
	}
	else if (Hit.Action == TEXT("close"))
	{
		Close();
	}
	else
	{
		if (IsWaitingForChoice())
		{
			Choose(ChoiceSelection);
		}
		else
		{
			Advance();
		}
	}
}

// ------------------------------------------------------------------------ drawing helpers

void FDADialogueUI::DrawRect(const FLinearColor& Color, float X, float Y, float W, float H)
{
	if (!Canvas || W <= 0.f || H <= 0.f)
	{
		return;
	}
	FCanvasTileItem Tile(FVector2D(X, Y), GWhiteTexture, FVector2D(W, H), Color);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void FDADialogueUI::DrawText(const FString& Str, float X, float Y, const FLinearColor& Color, float InScale,
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

void FDADialogueUI::DrawTexture(UTexture2D* Texture, float X, float Y, float W, float H, const FLinearColor& Tint)
{
	if (!Canvas || !Texture || !Texture->GetResource() || W <= 0.f || H <= 0.f)
	{
		return;
	}
	FCanvasTileItem Tile(FVector2D(X, Y), Texture->GetResource(), FVector2D(W, H), Tint);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void FDADialogueUI::DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent)
{
	DrawRect(Fill, X, Y, W, H);
	DrawRect(DialogueAlpha(Accent, 0.95f), X, Y, 5.f * UIScale, H);
	DrawRect(DialogueAlpha(Accent, 0.45f), X, Y + H - 2.f * UIScale, W, 2.f * UIScale);
}

void FDADialogueUI::Diamond(const FVector2D& C, float R, const FLinearColor& Color)
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

FVector2D FDADialogueUI::Measure(const FString& Str, float InScale, UFont* Font) const
{
	const UFont* F = Font ? Font : GetFont(false);
	if (!F || Str.IsEmpty())
	{
		return FVector2D::ZeroVector;
	}
	const float K = InScale * UIScale;
	return FVector2D(F->GetStringSize(*Str) * K, F->GetStringHeightSize(*Str) * K);
}

TArray<FString> FDADialogueUI::WrapText(const FString& Str, float MaxWidth, float InScale, UFont* Font) const
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

void FDADialogueUI::Draw(UCanvas* InCanvas)
{
	if (!bOpen || !InCanvas || !Lines.IsValidIndex(LineIndex))
	{
		return;
	}
	Canvas = InCanvas;
	UIScale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.6f, 2.5f);
	HitTargets.Reset();

	const FDADialogueLine& Line = Lines[LineIndex];
	const FString FullText = Line.GetDisplayText();
	const FString Visible = bTyping
		? FullText.Left(FMath::Clamp(FMath::FloorToInt(Revealed), 0, FullText.Len()))
		: FullText;
	const FLinearColor Accent = Line.Accent;
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;

	// Cinematic letterbox.
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.55f), 0.f, 0.f, CW, CH * 0.055f);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.55f), 0.f, CH - CH * 0.055f, CW, CH * 0.055f);

	const int32 NumOptions = Line.bChoice ? Line.Options.Num() : 0;
	const float W = FMath::Min(CW - 120.f * S, 1180.f * S);
	const float BaseH = 248.f * S;
	const float H = BaseH + NumOptions * 46.f * S;
	const float X = (CW - W) * 0.5f;
	const float Y = CH - H - 46.f * S;

	DrawPanel(X, Y, W, H, DialogueAlpha(DlgInk, 0.96f), Accent);
	AddHit(TEXT("advance"), INDEX_NONE, X, Y, W, H);

	// Portrait / fallback silhouette.
	const float PortraitSize = 164.f * S;
	DrawPortrait(X + 24.f * S, Y + 24.f * S, PortraitSize, Line, 1.f);

	// Name plate.
	const float TX = X + 24.f * S + PortraitSize + 26.f * S;
	const float TextW = W - (TX - X) - 28.f * S;
	DrawText(Line.GetDisplayName(), TX, Y + 18.f * S, Accent, 1.35f, false, GetFont(true));
	if (!Line.SpeakerTitle.IsEmpty())
	{
		DrawText(Line.SpeakerTitle, TX, Y + 52.f * S, DlgMuted, 0.8f);
	}
	DrawRect(DialogueAlpha(Accent, 0.55f), TX, Y + 80.f * S, TextW, 2.f * S);

	// Text body.
	float TextY = Y + 96.f * S;
	const float LineH = Measure(TEXT("Ag"), 1.0f).Y + 3.f * S;
	const int32 MaxTextLines = NumOptions > 0 ? 3 : 4;
	const TArray<FString> Wrapped = WrapText(Visible, TextW, 1.0f);
	for (int32 Index = 0; Index < Wrapped.Num() && Index < MaxTextLines; ++Index)
	{
		DrawText(Wrapped[Index], TX, TextY, DlgPaper, 1.0f);
		TextY += LineH;
	}
	if (bTyping && Wrapped.Num() > MaxTextLines)
	{
		DrawText(TEXT("..."), TX, Y + 96.f * S + MaxTextLines * LineH, DialogueAlpha(DlgPaper, 0.6f), 1.0f);
	}

	// Choice buttons.
	if (NumOptions > 0)
	{
		const float OptionX = TX;
		const float OptionW = TextW;
		const float OptionH = 38.f * S;
		const float OptionY0 = Y + BaseH - 16.f * S;
		float MouseX = -1.f;
		float MouseY = -1.f;
		const bool bHasMouse = PlayerOwner && PlayerOwner->GetMousePosition(MouseX, MouseY);
		const FVector2D Mouse(MouseX, MouseY);

		for (int32 Index = 0; Index < NumOptions; ++Index)
		{
			const float OY = OptionY0 + Index * 46.f * S;
			const bool bSelected = Index == ChoiceSelection;
			const bool bHovered = bHasMouse
				&& Mouse.X >= OptionX && Mouse.X <= OptionX + OptionW
				&& Mouse.Y >= OY && Mouse.Y <= OY + OptionH;
			if (bSelected || bHovered)
			{
				DrawRect(DialogueAlpha(Accent, bSelected ? 0.28f : 0.16f), OptionX, OY, OptionW, OptionH);
				DrawRect(DialogueAlpha(Accent, 1.f), OptionX, OY, 4.f * S, OptionH);
			}
			const FString Label = FString::Printf(TEXT("%d.  %s"), Index + 1, *Line.Options[Index]);
			DrawText(Label, OptionX + 14.f * S, OY + 7.f * S,
				bSelected ? DlgPaper : DialogueAlpha(DlgPaper, 0.82f), 0.95f);
			AddHit(TEXT("choice"), Index, OptionX, OY, OptionW, OptionH);
		}
	}

	// Skip / auto / log controls above the box.
	const float ButtonH = 26.f * S;
	const float ButtonY = Y - 34.f * S;
	float ButtonX = X + W;
	auto DrawDialogueButton = [&](const FString& Label, const FString& Action, float ButtonW, bool bActive)
	{
		ButtonX -= ButtonW;
		DrawRect(DialogueAlpha(bActive ? Accent : FLinearColor(0.f, 0.f, 0.f), bActive ? 0.35f : 0.42f),
			ButtonX, ButtonY, ButtonW, ButtonH);
		DrawText(Label, ButtonX + 10.f * S, ButtonY + 4.f * S,
			bActive ? Accent : DialogueAlpha(DlgPaper, 0.7f), 0.68f);
		AddHit(Action, INDEX_NONE, ButtonX, ButtonY, ButtonW, ButtonH);
		ButtonX -= 8.f * S;
	};
	DrawDialogueButton(DAUIData::Label(TEXT("dialogue.button.skip"), TEXT("SKIP")), TEXT("skip"), 74.f * S, false);
	DrawDialogueButton(DAUIData::Label(TEXT("dialogue.button.auto"), TEXT("AUTO")), TEXT("auto"), 78.f * S, bAuto);
	DrawDialogueButton(DAUIData::Label(TEXT("dialogue.button.log"), TEXT("LOG (H)")), TEXT("history"), 104.f * S, false);

	// Continue / choice prompt.
	FString Hint;
	if (NumOptions > 0)
	{
		Hint = DAUIData::Label(TEXT("dialogue.hint.choice"), TEXT("Choose an option  -  1-9 / click"));
	}
	else if (bTyping)
	{
		Hint = DAUIData::Label(TEXT("dialogue.hint.reveal"), TEXT("E / SPACE  REVEAL"));
	}
	else if (LineIndex + 1 < Lines.Num())
	{
		Hint = DAUIData::Label(TEXT("dialogue.hint.continue"), TEXT("E / SPACE  CONTINUE"));
	}
	else
	{
		Hint = DAUIData::Label(TEXT("dialogue.hint.finish"), TEXT("E / SPACE  FINISH"));
	}
	const FVector2D HintSize = Measure(Hint, 0.72f);
	const float HintAlpha = 0.55f + 0.35f * FMath::Abs(FMath::Sin(Elapsed * 3.f));
	const float HintX = NumOptions > 0 ? X : X + W - HintSize.X - 24.f * S;
	const float HintY = NumOptions > 0 ? Y - 28.f * S : Y + H - 28.f * S;
	DrawText(Hint, HintX, HintY, DialogueAlpha(Accent, HintAlpha), 0.72f);

	if (bHistoryOpen)
	{
		DrawHistoryOverlay();
	}
}

void FDADialogueUI::DrawPortrait(float X, float Y, float Size, const FDADialogueLine& Line, float Alpha)
{
	const float S = UIScale;
	const FLinearColor Accent = Line.Accent;

	DrawRect(DialogueAlpha(FLinearColor(0.025f, 0.04f, 0.065f), Alpha), X, Y, Size, Size);

	UTexture2D* Portrait = nullptr;
	if (UCharacterPortraitSubsystem* Art = GetPortraitArt())
	{
		if (!Line.Expression.IsEmpty())
		{
			Portrait = Art->GetExpression(Line.SpeakerId, Line.Expression);
		}
		if (!Portrait)
		{
			const FString PortraitId = Line.Portrait.IsEmpty() ? Line.SpeakerId : Line.Portrait;
			Portrait = Art->GetPortrait(PortraitId, true);
			if (!Portrait)
			{
				Portrait = Art->GetPortrait(PortraitId, false);
			}
		}
	}

	if (Portrait && Portrait->GetResource())
	{
		DrawTexture(Portrait, X + 2.f * S, Y + 2.f * S, Size - 4.f * S, Size - 4.f * S,
			FLinearColor(1.f, 1.f, 1.f, Alpha));
	}
	else
	{
		// Colored monogram + simple bust silhouette fallback.
		DrawRect(DialogueAlpha(Accent, 0.09f * Alpha), X, Y, Size, Size);
		Diamond(FVector2D(X + Size * 0.5f, Y + Size * 0.40f), Size * 0.20f, DialogueAlpha(Accent, 0.30f * Alpha));
		DrawRect(DialogueAlpha(Accent, 0.22f * Alpha), X + Size * 0.18f, Y + Size * 0.58f,
			Size * 0.64f, Size * 0.34f);

		FString Initial = Line.GetDisplayName().Left(1).ToUpper();
		if (Initial.IsEmpty())
		{
			Initial = TEXT("?");
		}
		DrawText(Initial, X + Size * 0.5f, Y + Size * 0.22f, DialogueAlpha(Accent, 0.92f * Alpha),
			2.4f, true, GetFont(true));
		DrawText(TEXT("NO PORTRAIT"), X + Size * 0.5f, Y + Size - 24.f * S,
			DialogueAlpha(DlgMuted, 0.75f * Alpha), 0.55f, true);
	}

	// Accent corner brackets.
	DrawRect(DialogueAlpha(Accent, 0.95f * Alpha), X, Y, Size, 2.f * S);
	DrawRect(DialogueAlpha(Accent, 0.95f * Alpha), X, Y + Size - 2.f * S, Size, 2.f * S);
	DrawRect(DialogueAlpha(Accent, 0.95f * Alpha), X, Y, 2.f * S, Size);
	DrawRect(DialogueAlpha(Accent, 0.95f * Alpha), X + Size - 2.f * S, Y, 2.f * S, Size);

	if (!Line.Expression.IsEmpty())
	{
		DrawText(Line.Expression.ToUpper(), X + 8.f * S, Y + Size - 22.f * S,
			DialogueAlpha(Accent, 0.85f * Alpha), 0.6f);
	}
}

void FDADialogueUI::DrawHistoryOverlay()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;

	HitTargets.Reset();
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.72f), 0.f, 0.f, CW, CH);
	AddHit(TEXT("history.close"), INDEX_NONE, 0.f, 0.f, CW, CH);

	const float W = FMath::Min(CW - 160.f * S, 900.f * S);
	const float H = FMath::Min(CH - 140.f * S, 640.f * S);
	const float X = (CW - W) * 0.5f;
	const float Y = (CH - H) * 0.5f;
	DrawPanel(X, Y, W, H, DialogueAlpha(DlgInk, 0.98f), DlgGold);

	DrawText(DAUIData::Label(TEXT("dialogue.history.title"), TEXT("DIALOGUE LOG")),
		X + 28.f * S, Y + 20.f * S, DlgGold, 1.4f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%d entries"), History.Num()), X + W - 130.f * S, Y + 26.f * S,
		DlgMuted, 0.72f);
	DrawRect(DialogueAlpha(DlgGold, 0.4f), X + 28.f * S, Y + 60.f * S, W - 56.f * S, 1.f * S);

	const float LineH = Measure(TEXT("Ag"), 0.82f).Y + 3.f * S;
	float DrawY = Y + 74.f * S;
	const float Bottom = Y + H - 54.f * S;
	if (History.Num() == 0)
	{
		DrawText(TEXT("No dialogue yet."), X + 28.f * S, DrawY, DlgMuted, 0.9f);
	}
	else
	{
		TArray<FString> Page;
		const int32 SafeScroll = FMath::Clamp(HistoryScroll, 0, FMath::Max(0, History.Num() - 1));
		const int32 Start = History.Num() - 1 - SafeScroll;
		for (int32 Index = Start; Index >= 0 && Page.Num() < 40; --Index)
		{
			Page.Insert(History[Index], 0);
		}
		for (const FString& Entry : Page)
		{
			const TArray<FString> Wrapped = WrapText(Entry, W - 62.f * S, 0.82f);
			for (const FString& WrappedLine : Wrapped)
			{
				if (DrawY + LineH > Bottom)
				{
					break;
				}
				DrawText(WrappedLine, X + 28.f * S, DrawY, DlgPaper, 0.82f);
				DrawY += LineH;
			}
			if (DrawY + LineH > Bottom)
			{
				break;
			}
		}
	}

	DrawText(TEXT("H / ESC close    Up / Down scroll"), X + 28.f * S, Y + H - 32.f * S,
		DialogueAlpha(DlgMuted, 0.9f), 0.72f);
	DrawText(TEXT("CLOSE"), X + W - 96.f * S, Y + H - 34.f * S, DialogueAlpha(DlgGold, 0.9f), 0.75f);
}

// ------------------------------------------------------------------------ ui.json

namespace
{
	struct FDAUIDataCache
	{
		bool bAttempted = false;
		TMap<FString, FString> Labels;
		TMap<FString, TArray<FDADialogueLine>> Samples;
		TArray<FString> Credits;
	};

	FDAUIDataCache& GetUIDataCache()
	{
		static FDAUIDataCache Cache;
		if (Cache.bAttempted)
		{
			return Cache;
		}
		Cache.bAttempted = true;

		const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/UI/ui.json"));
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("UI data not found at %s; using built-in UI-label fallbacks."), *Path);
			return Cache;
		}

		TSharedPtr<FJsonObject> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("UI data JSON could not be parsed: %s"), *Path);
			return Cache;
		}

		const TSharedPtr<FJsonObject>* LabelsObject = nullptr;
		if (Root->TryGetObjectField(TEXT("labels"), LabelsObject) && LabelsObject && LabelsObject->IsValid())
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*LabelsObject)->Values)
			{
				FString Value;
				if (Pair.Value.IsValid() && Pair.Value->TryGetString(Value))
				{
					Cache.Labels.Add(Pair.Key, Value);
				}
			}
		}

		const TSharedPtr<FJsonObject>* SamplesObject = nullptr;
		if (Root->TryGetObjectField(TEXT("dialogueSamples"), SamplesObject) && SamplesObject && SamplesObject->IsValid())
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*SamplesObject)->Values)
			{
				const TArray<TSharedPtr<FJsonValue>>* SampleArray = nullptr;
				if (!Pair.Value.IsValid() || !Pair.Value->TryGetArray(SampleArray) || !SampleArray)
				{
					continue;
				}
				TArray<FDADialogueLine>& Lines = Cache.Samples.Add(Pair.Key);
				for (const TSharedPtr<FJsonValue>& Entry : *SampleArray)
				{
					const TSharedPtr<FJsonObject>* Object = nullptr;
					if (!Entry.IsValid() || !Entry->TryGetObject(Object) || !Object || !Object->IsValid())
					{
						continue;
					}
					FDADialogueLine Line;
					(*Object)->TryGetStringField(TEXT("speakerId"), Line.SpeakerId);
					(*Object)->TryGetStringField(TEXT("speakerName"), Line.SpeakerName);
					(*Object)->TryGetStringField(TEXT("portrait"), Line.Portrait);
					(*Object)->TryGetStringField(TEXT("expression"), Line.Expression);
					(*Object)->TryGetStringField(TEXT("text"), Line.Text);
					(*Object)->TryGetStringField(TEXT("textKey"), Line.TextKey);
					(*Object)->TryGetStringField(TEXT("nodeId"), Line.NodeId);
					(*Object)->TryGetStringField(TEXT("speakerTitle"), Line.SpeakerTitle);
					(*Object)->TryGetBoolField(TEXT("bChoice"), Line.bChoice);

					double Delay = Line.AutoAdvanceDelay;
					if ((*Object)->TryGetNumberField(TEXT("autoAdvanceDelay"), Delay))
					{
						Line.AutoAdvanceDelay = static_cast<float>(Delay);
					}

					const TArray<TSharedPtr<FJsonValue>>* Options = nullptr;
					if ((*Object)->TryGetArrayField(TEXT("options"), Options) && Options)
					{
						for (const TSharedPtr<FJsonValue>& OptionValue : *Options)
						{
							FString OptionLabel;
							if (OptionValue.IsValid() && OptionValue->TryGetString(OptionLabel))
							{
								Line.Options.Add(OptionLabel);
							}
						}
					}

					FString AccentHex;
					if ((*Object)->TryGetStringField(TEXT("accent"), AccentHex) && !AccentHex.IsEmpty())
					{
						FLinearColor Parsed = FLinearColor::FromSRGBColor(
							FColor::FromHex(AccentHex.Replace(TEXT("#"), TEXT(""))));
						Parsed.A = 1.f;
						Line.Accent = Parsed;
					}
					Lines.Add(MoveTemp(Line));
				}
			}
		}

		const TArray<TSharedPtr<FJsonValue>>* CreditsArray = nullptr;
		if (Root->TryGetArrayField(TEXT("credits"), CreditsArray) && CreditsArray)
		{
			for (const TSharedPtr<FJsonValue>& CreditValue : *CreditsArray)
			{
				FString CreditLine;
				if (CreditValue.IsValid() && CreditValue->TryGetString(CreditLine))
				{
					Cache.Credits.Add(CreditLine);
				}
			}
		}

		return Cache;
	}
}

FString DAUIData::Label(const FString& Key, const FString& Fallback)
{
	if (const FString* Found = GetUIDataCache().Labels.Find(Key))
	{
		return *Found;
	}
	return Fallback;
}

bool DAUIData::LoadDialogueSample(const FString& SampleId, TArray<FDADialogueLine>& OutLines)
{
	const TArray<FDADialogueLine>* Found = GetUIDataCache().Samples.Find(SampleId);
	if (!Found || Found->Num() == 0)
	{
		return false;
	}
	OutLines = *Found;
	return true;
}

bool DAUIData::LoadCredits(TArray<FString>& OutLines)
{
	const TArray<FString>& Credits = GetUIDataCache().Credits;
	if (Credits.Num() == 0)
	{
		return false;
	}
	OutLines = Credits;
	return true;
}
