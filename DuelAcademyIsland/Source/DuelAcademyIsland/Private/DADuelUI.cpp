// Duel Academy Island - interactive duel board presentation.

#include "DADuelUI.h"

#include "DAHUD.h"
#include "DAIslandSubsystem.h"
#include "DAStudentCharacter.h"
#include "DACardArtSubsystem.h"
#include "DACharacterPortraitSubsystem.h"
#include "DACardRecords.h"
#include "DuelAcademyIsland.h"

#include "CanvasItem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "RenderUtils.h"
#include "TextureResource.h"

namespace
{
	enum class EDASfx
	{
		UiOpen, UiClose, UiClick, UiHover, CardFlip, CardPlace, Deny, DuelStart, LowLp,
		TurnStart, PhaseChange, CardDraw, Summon, SetCard, Spell, Trap, Attack, Impact, Damage,
		Heal, Destroy, Effect, Win, Lose, CardDiscard, CardBanish, CardSearch, CardMill,
		CardReturn, Position, Fusion, Ritual, Cost, Counter
	};

	/** Fire-and-forget UI cue: reuse the island's generated sound set. */
	void PlayCue(const UObject* WorldContextObject, EDASfx Cue, float Volume = 1.0f, float Pitch = 1.0f)
	{
		const TCHAR* Sound = TEXT("A_UIClick");
		switch (Cue)
		{
		case EDASfx::DuelStart: Sound = TEXT("A_DuelStart"); break;
		case EDASfx::Win:
		case EDASfx::Heal: Sound = TEXT("A_Discover"); break;
		case EDASfx::CardDraw:
		case EDASfx::CardFlip:
		case EDASfx::CardPlace:
		case EDASfx::Summon:
		case EDASfx::SetCard:
		case EDASfx::Spell:
		case EDASfx::Trap:
		case EDASfx::Attack:
		case EDASfx::Damage:
		case EDASfx::Destroy:
		case EDASfx::Effect:
		case EDASfx::CardDiscard:
		case EDASfx::CardBanish:
		case EDASfx::CardSearch:
		case EDASfx::CardMill:
		case EDASfx::CardReturn:
		case EDASfx::Position:
		case EDASfx::Fusion:
		case EDASfx::Ritual:
		case EDASfx::Cost:
		case EDASfx::Counter: Sound = TEXT("A_CardDraw"); break;
		default: break;
		}
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(WorldContextObject))
		{
			Sub->PlayUISound(Sound, Volume);
		}
	}

	void PlayDuelEventCue(const UObject* WorldContextObject, const FDuelVisualEvent& Event)
	{
		switch (Event.Type)
		{
		case EDuelVisualEventType::TurnStart: PlayCue(WorldContextObject, EDASfx::TurnStart, 0.95f); break;
		case EDuelVisualEventType::PhaseChange: PlayCue(WorldContextObject, EDASfx::PhaseChange, 0.8f); break;
		case EDuelVisualEventType::Draw: PlayCue(WorldContextObject, EDASfx::CardDraw, 0.9f); break;
		case EDuelVisualEventType::Summon: PlayCue(WorldContextObject, EDASfx::Summon, 1.0f); break;
		case EDuelVisualEventType::SetCard: PlayCue(WorldContextObject, EDASfx::SetCard, 0.95f); break;
		case EDuelVisualEventType::Spell: PlayCue(WorldContextObject, EDASfx::Spell, 1.0f); break;
		case EDuelVisualEventType::Trap: PlayCue(WorldContextObject, EDASfx::Trap, 1.0f); break;
		case EDuelVisualEventType::Attack: PlayCue(WorldContextObject, EDASfx::Attack, 1.0f); break;
		case EDuelVisualEventType::Damage:
			PlayCue(WorldContextObject, EDASfx::Impact, FMath::Clamp(0.45f + Event.Amount / 3200.0f, 0.45f, 1.0f));
			break;
		case EDuelVisualEventType::Heal: PlayCue(WorldContextObject, EDASfx::Heal, 0.9f); break;
		case EDuelVisualEventType::Destroy: PlayCue(WorldContextObject, EDASfx::Destroy, 1.0f); break;
		case EDuelVisualEventType::Effect: PlayCue(WorldContextObject, EDASfx::Effect, 0.85f); break;
		case EDuelVisualEventType::Win:
			PlayCue(WorldContextObject, Event.Side == EDuelOwner::Player ? EDASfx::Win : EDASfx::Lose, 1.0f);
			break;
		case EDuelVisualEventType::Discard: PlayCue(WorldContextObject, EDASfx::CardDiscard, 0.9f); break;
		case EDuelVisualEventType::Banish: PlayCue(WorldContextObject, EDASfx::CardBanish, 0.95f); break;
		case EDuelVisualEventType::Search: PlayCue(WorldContextObject, EDASfx::CardSearch, 0.95f); break;
		case EDuelVisualEventType::Mill: PlayCue(WorldContextObject, EDASfx::CardMill, 0.9f); break;
		case EDuelVisualEventType::Return: PlayCue(WorldContextObject, EDASfx::CardReturn, 0.9f); break;
		case EDuelVisualEventType::Position: PlayCue(WorldContextObject, EDASfx::Position, 0.9f); break;
		case EDuelVisualEventType::Fusion: PlayCue(WorldContextObject, EDASfx::Fusion, 1.0f); break;
		case EDuelVisualEventType::Ritual: PlayCue(WorldContextObject, EDASfx::Ritual, 1.0f); break;
		case EDuelVisualEventType::Cost: PlayCue(WorldContextObject, EDASfx::Cost, 0.9f); break;
		case EDuelVisualEventType::Counter: PlayCue(WorldContextObject, EDASfx::Counter, 1.0f); break;
		default: break;
		}
	}

	const FLinearColor Gold(0.86f, 0.67f, 0.28f, 1.0f);
	const FLinearColor GoldSoft(0.74f, 0.61f, 0.34f, 1.0f);
	const FLinearColor Ink(0.027f, 0.043f, 0.067f, 0.88f);
	const FLinearColor InkSoft(0.04f, 0.065f, 0.09f, 0.78f);
	const FLinearColor Line(0.58f, 0.45f, 0.20f, 0.55f);
	const FLinearColor Paper(0.94f, 0.92f, 0.85f, 1.0f);
	const FLinearColor Muted(0.55f, 0.66f, 0.70f, 1.0f);
	const FLinearColor AccentCyan(0.38f, 0.82f, 0.94f, 1.0f);

	constexpr float DuelTextBoost = 1.55f;

	FString CleanDuelText(const FString& Text)
	{
		FString Clean;
		Clean.Reserve(Text.Len());
		for (TCHAR Char : Text)
		{
			if (Char == 0xF0 || Char == 0x80 || Char == 0xFFFD || Char == 0x7F
				|| (Char < 32 && Char != '\n' && Char != '\r'))
			{
				Clean.AppendChar(' ');
			}
			else
			{
				Clean.AppendChar(Char);
			}
		}
		return Clean;
	}

	FString CutInQuote(const FString& CharacterId, const FString& Expression)
	{
		const bool bJaden = CharacterId.Equals(TEXT("jaden"), ESearchCase::IgnoreCase);
		if (Expression == TEXT("happy"))
		{
			return bJaden ? TEXT("Now that's what I call a duel!") : TEXT("Nice! That's the play.");
		}
		if (Expression == TEXT("angry") || Expression == TEXT("determined"))
		{
			return bJaden ? TEXT("No way I'm letting that slide!") : TEXT("I'm not out of this yet!");
		}
		if (Expression == TEXT("shocked"))
		{
			return bJaden ? TEXT("Whoa! I did not see that coming!") : TEXT("No way!");
		}
		if (Expression == TEXT("sad"))
		{
			return bJaden ? TEXT("Man... that one really hurt.") : TEXT("That's going to leave a mark...");
		}
		if (Expression == TEXT("laugh"))
		{
			return bJaden ? TEXT("Ha! This is getting good!") : TEXT("Gotcha! Read the card.");
		}
		return bJaden ? TEXT("Get your game on!") : TEXT("All right. Let's duel.");
	}
}

// ---------------------------------------------------------------------------
// Lifetime / helpers
// ---------------------------------------------------------------------------

FDADuelUI::FDADuelUI(ADAHUD* InOwner)
	: OwnerHUD(InOwner)
{
	PlayerOwner = InOwner ? InOwner->GetOwningPlayerController() : nullptr;
}

FDADuelUI::~FDADuelUI() = default;

UWorld* FDADuelUI::GetWorld() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetWorld() : nullptr;
}

UGameInstance* FDADuelUI::GetGameInstance() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetGameInstance() : nullptr;
}

UCardArtSubsystem* FDADuelUI::GetCardArt() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UCardArtSubsystem>() : nullptr;
}

UCharacterPortraitSubsystem* FDADuelUI::GetPortraitArt() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UCharacterPortraitSubsystem>() : nullptr;
}

UFont* FDADuelUI::GetFont(bool bLarge) const
{
	if (OwnerHUD.IsValid())
	{
		return bLarge ? OwnerHUD->GetBigFont() : OwnerHUD->GetSmallFont();
	}
	return bLarge ? (GEngine ? GEngine->GetLargeFont() : nullptr) : (GEngine ? GEngine->GetMediumFont() : nullptr);
}

void FDADuelUI::DrawRect(const FLinearColor& Color, float X, float Y, float W, float H)
{
	if (!Canvas || W <= 0.0f || H <= 0.0f)
	{
		return;
	}
	FCanvasTileItem Tile(FVector2D(X, Y), GWhiteTexture, FVector2D(W, H), Color);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void FDADuelUI::DrawText(const FString& Text, const FLinearColor& Color, float X, float Y, UFont* Font, float Scale)
{
	if (!Canvas || !Font || Text.IsEmpty())
	{
		return;
	}
	FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(Text), Font, Color);
	Item.Scale = FVector2D(Scale, Scale);
	Item.EnableShadow(FLinearColor(0.0f, 0.0f, 0.0f, 0.0f));
	Canvas->DrawItem(Item);
}

void FDADuelUI::GetTextSize(const FString& Text, float& OutW, float& OutH, UFont* Font, float Scale) const
{
	if (!Font || Text.IsEmpty())
	{
		OutW = OutH = 0.0f;
		return;
	}
	OutW = Font->GetStringSize(*Text) * Scale;
	OutH = Font->GetStringHeightSize(*Text) * Scale;
}

void FDADuelUI::DrawTexture(UTexture* Texture, float X, float Y, float W, float H, float U, float V, float UW, float VH,
	const FLinearColor& Tint)
{
	if (!Canvas || !Texture || !Texture->GetResource() || W <= 0.0f || H <= 0.0f)
	{
		return;
	}
	FCanvasTileItem Tile(FVector2D(X, Y), Texture->GetResource(), FVector2D(W, H),
		FVector2D(U, V), FVector2D(U + UW, V + VH), Tint);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void FDADuelUI::DrawLine(float X1, float Y1, float X2, float Y2, const FLinearColor& Color, float Thickness)
{
	if (!Canvas)
	{
		return;
	}
	FCanvasLineItem LineItem(FVector2D(X1, Y1), FVector2D(X2, Y2));
	LineItem.SetColor(Color);
	LineItem.LineThickness = Thickness;
	Canvas->DrawItem(LineItem);
}

void FDADuelUI::PlaySfx(const TCHAR* SoundName, float Volume) const
{
	if (OwnerHUD.IsValid())
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(OwnerHUD.Get()))
		{
			Sub->PlayUISound(SoundName, Volume);
		}
	}
}

void FDADuelUI::ShowToast(const FString& Text, FLinearColor Color)
{
	if (!OwnerHUD.IsValid())
	{
		return;
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(OwnerHUD.Get()))
	{
		FDAMessage Msg;
		Msg.Title = TEXT("Duel");
		Msg.Body = Text;
		Msg.Accent = Color;
		Msg.Duration = 4.0f;
		Sub->PushMessage(Msg);
	}
}

void FDADuelUI::ShowBanner(const FString& Title, const FString& Subtitle)
{
	if (!OwnerHUD.IsValid())
	{
		return;
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(OwnerHUD.Get()))
	{
		FDAMessage Msg;
		Msg.Title = Title;
		Msg.Body = Subtitle;
		Msg.Accent = Gold;
		Msg.Duration = 4.0f;
		Sub->PushMessage(Msg);
	}
}

void FDADuelUI::NotifyDuelFinished(bool bPlayerWon)
{
	FString RewardLine;
	if (bPlayerWon)
	{
		if (ADAStudentCharacter* Student = PlayerOwner ? Cast<ADAStudentCharacter>(PlayerOwner->GetPawn()) : nullptr)
		{
			UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
			if (Cards && Cards->GetCardCount() > 0)
			{
				TArray<int32> CardIds;
				Cards->GetCards().GenerateKeyArray(CardIds);
				const int32 CardId = CardIds[FMath::RandRange(0, CardIds.Num() - 1)];
				if (const FCardRecord* Card = Cards->FindCard(CardId))
				{
					Student->AddCardToCollection(Card->Name);
					RewardLine = FString::Printf(TEXT(" You also received %s for your collection."), *Card->Name);
				}
			}
		}
	}
	DuelResultTitle = bPlayerWon ? TEXT("DUEL WON") : TEXT("DUEL LOST");
	DuelResultMessage = bPlayerWon
		? FString::Printf(TEXT("You defeated %s. The whole island will hear about it.%s"), *DuelOpponentName, *RewardLine)
		: FString::Printf(TEXT("%s wins this one. Challenge them again any time."), *DuelOpponentName);
	DuelResultColor = bPlayerWon ? Gold : FLinearColor(0.85f, 0.3f, 0.25f);
	if (ADAStudentCharacter* Student = PlayerOwner ? Cast<ADAStudentCharacter>(PlayerOwner->GetPawn()) : nullptr)
	{
		Student->SetDuelPose(false);
	}
}

void FDADuelUI::OpenDeckSelect(const FString& OpponentId, const FString& OpponentName, const FString& OpponentDeckId)
{
	if (DuelMode == EDuelUiMode::Duel || DuelMode == EDuelUiMode::DeckSelect)
	{
		return;
	}
	DuelOpponentId = OpponentId.IsEmpty() ? TEXT("jaden") : OpponentId;
	DuelOpponentName = OpponentName.IsEmpty() ? TEXT("Jaden Yuki") : OpponentName;
	DuelOpponentDeckId = OpponentDeckId.IsEmpty() ? TEXT("jaden") : OpponentDeckId;

	DuelMode = EDuelUiMode::DeckSelect;
	DuelEngine.Reset();
	DuelSelectedUid = 0;
	DuelTributeHandUid = 0;
	bDuelTributeSet = false;
	DuelTributeUids.Reset();
	DuelPileType = EDuelPileType::None;
	DuelMessage.Empty();
	DuelMessageTimer = 0.0f;
	bDuelResultWon = false;
	bDuelResultNotified = false;
	DuelResultTitle.Empty();
	DuelResultMessage.Empty();
	PlaySfx(TEXT("A_UIClick"), 0.9f);

	PlayerOwner = OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr;
	if (PlayerOwner)
	{
		PlayerOwner->bShowMouseCursor = true;
		PlayerOwner->SetInputMode(FInputModeGameAndUI());
	}
	if (ADAStudentCharacter* Student = PlayerOwner ? Cast<ADAStudentCharacter>(PlayerOwner->GetPawn()) : nullptr)
	{
		Student->SetDuelPose(true);
	}
	UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Duel deck select opened against %s."), *DuelOpponentName);
}

void FDADuelUI::StartDuelWithDeck(const FString& DeckId)
{
	UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	if (!Cards || !Cards->IsLoaded())
	{
		DuelShowMessage(TEXT("Card database is not loaded."));
		return;
	}

	DuelEngine = MakeUnique<FDuelEngine>(Cards, static_cast<int32>(FPlatformTime::Cycles()));
	DuelEngine->Start(DeckId, DuelOpponentDeckId, DuelOpponentName, DuelOpponentId);
	DuelMode = EDuelUiMode::Duel;
	DuelSelectedUid = 0;
	DuelTributeHandUid = 0;
	bDuelTributeSet = false;
	DuelTributeUids.Reset();
	DuelPileType = EDuelPileType::None;
	DuelMessage.Empty();
	DuelMessageTimer = 0.0f;
	DuelAiTimer = 0.0f;
	bDuelResultWon = false;
	bDuelResultNotified = false;
	DuelIncomingEvents.Reset();
	DuelFx.Reset();
	DuelEventPumpTimer = 0.0f;
	DuelPlayerLpDisplay = 8000.0f;
	DuelOpponentLpDisplay = 8000.0f;
	DuelPlayerLpHit = 0.0f;
	DuelOpponentLpHit = 0.0f;
	DuelShakeTime = 0.0f;
	DuelShakeStrength = 0.0f;
	DuelFlashTime = 0.0f;
	DuelEventBannerTime = 0.0f;
	DuelEventBannerTitle.Empty();
	DuelEventBannerSubtitle.Empty();
	DuelIntroTime = 0.0f;
	DuelOpponentPortraitPulse = 0.0f;
	DuelPlayerPortraitPulse = 0.0f;
	DuelCutInCharacter.Empty();
	DuelCutInExpression.Empty();
	DuelCutInTitle.Empty();
	DuelCutInSubtitle.Empty();
	DuelCutInTime = 0.0f;
	DuelCutInAge = 0.0f;
	DuelCutInPriority = 0;
	DuelResultDelay = 0.0f;
	bDuelResultPending = false;
	bDuelPlayerLowLpWarned = false;
	bDuelOpponentLowLpWarned = false;
	DuelEventGap = 0.22f;
	bDuelEventsPrimed = true;
	bDuelAutoEndTurnDone = false;

	if (PlayerOwner)
	{
		PlayerOwner->bShowMouseCursor = true;
		PlayerOwner->SetInputMode(FInputModeGameAndUI());
	}
	ShowBanner(DuelOpponentName.ToUpper(), TEXT("DUEL START"));
	ShowToast(TEXT("Duel start. Select a card in your hand or press B for the Battle Phase."),
		FLinearColor(0.55f, 0.82f, 0.95f));
	PlaySfx(TEXT("A_DuelStart"), 0.8f);
}

void FDADuelUI::CloseDuel()
{
	if (DuelMode != EDuelUiMode::None)
	{
		PlaySfx(TEXT("A_UIClick"), 0.85f);
	}
	if (!DuelResultMessage.IsEmpty())
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(OwnerHUD.Get()))
		{
			FDAMessage Msg;
			Msg.Title = DuelResultTitle;
			Msg.Body = DuelResultMessage;
			Msg.Accent = DuelResultColor;
			Msg.Duration = 8.0f;
			Sub->PushMessage(Msg);
		}
		DuelResultTitle.Empty();
		DuelResultMessage.Empty();
	}
	DuelMode = EDuelUiMode::None;
	DuelEngine.Reset();
	DuelHitTargets.Reset();
	DuelPileType = EDuelPileType::None;
	DuelSelectedUid = 0;
	bDuelTributeSet = false;
	DuelTributeUids.Reset();
	DuelMessage.Empty();
	DuelIncomingEvents.Reset();
	DuelFx.Reset();
	DuelEventBannerTime = 0.0f;
	DuelFlashTime = 0.0f;
	DuelShakeTime = 0.0f;
	DuelCutInTime = 0.0f;
	DuelCutInPriority = 0;
	DuelResultDelay = 0.0f;
	bDuelResultPending = false;
	bDuelEventsPrimed = false;
	bDuelAutoEndTurnDone = false;
	if (ADAStudentCharacter* Student = PlayerOwner ? Cast<ADAStudentCharacter>(PlayerOwner->GetPawn()) : nullptr)
	{
		Student->SetDuelPose(false);
	}
	if (PlayerOwner)
	{
		PlayerOwner->SetInputMode(FInputModeGameOnly());
		PlayerOwner->bShowMouseCursor = false;
	}
}

void FDADuelUI::Update(float DeltaSeconds)
{
	UpdateDuel(DeltaSeconds);
}

void FDADuelUI::DebugAutoPlayOpening()
{
	if (!DuelEngine || DuelMode != EDuelUiMode::Duel)
	{
		return;
	}
	for (const FDuelCard& Card : DuelEngine->GetSide(EDuelOwner::Player).Hand)
	{
		if (Card.IsMonster() && DuelEngine->GetEffectiveLevel(Card) <= 4 && DuelEngine->GetRequiredTributes(Card.Uid) == 0)
		{
			HandleDuelHit(TEXT("summon"), Card.Uid);
			break;
		}
	}
}

void FDADuelUI::DebugSelectFirstHandCard()
{
	if (!DuelEngine || DuelMode != EDuelUiMode::Duel)
	{
		return;
	}
	const FDuelSide& Player = DuelEngine->GetSide(EDuelOwner::Player);
	if (Player.Hand.Num() > 0)
	{
		HandleDuelHit(TEXT("select"), Player.Hand[0].Uid);
	}
}

void FDADuelUI::DebugFinishDuelWin()
{
	if (DuelEngine && DuelMode == EDuelUiMode::Duel)
	{
		DuelEngine->DebugFinishDuel(true);
	}
}

void FDADuelUI::Draw(UCanvas* InCanvas)
{
	if (!InCanvas || DuelMode == EDuelUiMode::None)
	{
		return;
	}
	Canvas = InCanvas;
	DuelScale = FMath::Min(Canvas->ClipX / 1600.0f, Canvas->ClipY / 900.0f);
	DuelOffsetX = (Canvas->ClipX - 1600.0f * DuelScale) * 0.5f;
	DuelOffsetY = (Canvas->ClipY - 900.0f * DuelScale) * 0.5f;
	DuelHitTargets.Reset();
	DrawDuel();
}

// ---------------------------------------------------------------------------
// Ported duel presentation
// ---------------------------------------------------------------------------

void FDADuelUI::DrawPanel(float X, float Y, float Width, float Height, const FLinearColor& Fill, const FLinearColor& Border)
{
	DrawRect(Border, X, Y, Width, Height);
	DrawRect(Fill, X + 1.0f, Y + 1.0f, Width - 2.0f, Height - 2.0f);
}

float FDADuelUI::DuelTextScale(float Scale) const
{
	return DuelMode == EDuelUiMode::None ? Scale : Scale * DuelTextBoost;
}

void FDADuelUI::DrawShadowText(const FString& Text, float X, float Y, UFont* Font, float Scale,
	const FLinearColor& Color, bool bCenter, bool bApplyDuelBoost)
{
	UFont* UseFont = Font ? Font : GetFont(false);
	if (!UseFont)
	{
		return;
	}
	if (bApplyDuelBoost)
	{
		Scale = DuelTextScale(Scale);
	}
	float TextW = 0.0f;
	float TextH = 0.0f;
	GetTextSize(Text, TextW, TextH, UseFont, Scale);
	const float DrawX = bCenter ? X - TextW * 0.5f : X;
	const bool bDuel = DuelMode != EDuelUiMode::None;
	if (bDuel)
	{
		// A four-way dark outline keeps small rules text legible on top of
		// card scans and coloured panels, where a single drop shadow is not
		// enough at this type size.
		const float Outline = FMath::Max(1.0f, Scale * 0.06f);
		const FLinearColor Edge(0.0f, 0.0f, 0.0f, Color.A * 0.9f);
		DrawText(Text, Edge, DrawX - Outline, Y, UseFont, Scale);
		DrawText(Text, Edge, DrawX + Outline, Y, UseFont, Scale);
		DrawText(Text, Edge, DrawX, Y - Outline, UseFont, Scale);
		DrawText(Text, Edge, DrawX, Y + Outline, UseFont, Scale);
	}
	DrawText(Text, FLinearColor(0.0f, 0.0f, 0.0f, Color.A * 0.78f), DrawX + 1.5f, Y + 2.5f, UseFont, Scale);
	DrawText(Text, Color, DrawX, Y, UseFont, Scale);
}

void FDADuelUI::DrawShadowText(const FString& Text, const FLinearColor& Color, float X, float Y,
	UFont* Font, float Scale, bool bCenter, bool bApplyDuelBoost)
{
	DrawShadowText(Text, X, Y, Font, Scale, Color, bCenter, bApplyDuelBoost);
}

float FDADuelUI::DrawWrappedText(const FString& Text, float X, float Y, float MaxWidth, UFont* Font,
	float Scale, const FLinearColor& Color, float LineSpacing)
{
	UFont* UseFont = Font ? Font : GetFont(false);
	if (!UseFont)
	{
		return Y;
	}
	const float EffectiveScale = DuelTextScale(Scale);
	TArray<FString> Words;
	Text.ParseIntoArrayWS(Words);
	FString CurrentLine;
	float LineHeight = 18.0f;
	GetTextSize(TEXT("Ag"), LineHeight, LineHeight, UseFont, EffectiveScale);
	for (const FString& Word : Words)
	{
		const FString Candidate = CurrentLine.IsEmpty() ? Word : CurrentLine + TEXT(" ") + Word;
		float Width = 0.0f;
		float Height = 0.0f;
		GetTextSize(Candidate, Width, Height, UseFont, EffectiveScale);
		if (!CurrentLine.IsEmpty() && Width > MaxWidth)
		{
			DrawShadowText(CurrentLine, X, Y, UseFont, EffectiveScale, Color, false, false);
			Y += LineHeight + LineSpacing;
			CurrentLine = Word;
		}
		else
		{
			CurrentLine = Candidate;
		}
	}
	if (!CurrentLine.IsEmpty())
	{
		DrawShadowText(CurrentLine, X, Y, UseFont, EffectiveScale, Color, false, false);
		Y += LineHeight + LineSpacing;
	}
	return Y;
}

// ---------------------------------------------------------------------------
// Duel flow
// ---------------------------------------------------------------------------

void FDADuelUI::UpdateDuel(float DeltaSeconds)
{
	if (DuelMode == EDuelUiMode::None)
	{
		return;
	}

	if (PlayerOwner)
	{
		float MouseX = 0.0f;
		float MouseY = 0.0f;
		if (PlayerOwner->GetMousePosition(MouseX, MouseY))
		{
			DuelMousePosition = FVector2D(MouseX, MouseY);
		}
	}

	if (DuelMessageTimer > 0.0f)
	{
		DuelMessageTimer = FMath::Max(0.0f, DuelMessageTimer - DeltaSeconds);
	}

	// Soft hover tick when the pointer moves onto a different duel control.
	// Hit targets are built by DrawHUD, so this reads the previous frame's list.
	{
		FString HoverAction;
		int32 HoverValue = 0;
		for (int32 Index = DuelHitTargets.Num() - 1; Index >= 0; --Index)
		{
			const FDuelHitTarget& Hit = DuelHitTargets[Index];
			if (Hit.Contains(DuelMousePosition))
			{
				HoverAction = Hit.Action;
				HoverValue = Hit.Value;
				break;
			}
		}
		DuelHoverCooldown = FMath::Max(0.0f, DuelHoverCooldown - DeltaSeconds);
		const bool bChanged = HoverAction != DuelHoverAction || HoverValue != DuelHoverValue;
		if (bChanged && DuelHoverCooldown <= 0.0f && !HoverAction.IsEmpty())
		{
			PlayCue(OwnerHUD.Get(), EDASfx::UiHover, 0.7f, 1.0f + 0.06f * FMath::FRand());
			DuelHoverCooldown = 0.07f;
		}
		DuelHoverAction = HoverAction;
		DuelHoverValue = HoverValue;
	}

	UpdateDuelVisuals(DeltaSeconds);

	if (DuelMode == EDuelUiMode::Duel && DuelEngine)
	{
		if (DuelEngine->HasWinner())
		{
			// Let the final attack, damage number, and win cut-in finish before
			// covering the board with the result card.
			if (!bDuelResultPending)
			{
				bDuelResultPending = true;
				DuelResultDelay = 3.2f;
			}
			DuelResultDelay = FMath::Max(0.0f, DuelResultDelay - DeltaSeconds);
			const bool bReelIdle = DuelIncomingEvents.Num() == 0 && DuelFx.Num() == 0;
			if (DuelResultDelay <= 0.0f || (bReelIdle && DuelResultDelay < 1.0f))
			{
				DuelMode = EDuelUiMode::Result;
				bDuelResultWon = DuelEngine->GetWinner() == EDuelOwner::Player;
				bDuelResultNotified = false;
				DuelResultEnterTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
				DuelSelectedUid = 0;
				bDuelTributeSet = false;
			}
			return;
		}

		// Debug aid for clean animation screenshots: let the opening hand settle,
		// then end the first turn so the AI event reel is on screen at capture time.
		if (!bDuelAutoEndTurnDone && DuelIntroTime > 1.35f
			&& FParse::Param(FCommandLine::Get(), TEXT("DADuelAutoEndTurn"))
			&& DuelEngine->IsPlayerTurn())
		{
			bDuelAutoEndTurnDone = true;
			DuelEngine->EndTurn();
		}

		if (DuelEngine->IsAwaitingAi())
		{
			if (DuelAiTimer <= 0.0f)
			{
				DuelAiTimer = 0.9f;
			}
			DuelAiTimer -= DeltaSeconds;
			if (DuelAiTimer <= 0.0f)
			{
				DuelAiTimer = 0.0f;
				DuelEngine->RunOpponentTurn();
				UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("DUELAI %s"), *DuelEngine->GetLastAiMessage());
			}
		}
		else
		{
			DuelAiTimer = 0.0f;
		}
	}

	if (DuelMode == EDuelUiMode::Result && !bDuelResultNotified)
	{
		NotifyDuelFinished(bDuelResultWon);
		bDuelResultNotified = true;
	}

	if (PlayerOwner && PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
	{
		float MouseX = 0.0f;
		float MouseY = 0.0f;
		const bool bHasMouse = PlayerOwner->GetMousePosition(MouseX, MouseY);
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("DUELMBDOWN hasMouse=%d mouse=%.0f,%.0f hits=%d"), bHasMouse ? 1 : 0, MouseX, MouseY, DuelHitTargets.Num());
		if (bHasMouse)
		{
			for (int32 I = DuelHitTargets.Num() - 1; I >= 0; --I)
			{
				const FDuelHitTarget& Hit = DuelHitTargets[I];
				if (Hit.Contains(FVector2D(MouseX, MouseY)))
				{
					HandleDuelHit(Hit.Action, Hit.Value, Hit.Payload);
					break;
				}
			}
		}
	}

	if (DuelMode == EDuelUiMode::DeckSelect)
	{
		if (PlayerOwner)
		{
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::One) || PlayerOwner->WasInputKeyJustPressed(EKeys::Two)
				|| PlayerOwner->WasInputKeyJustPressed(EKeys::Three))
			{
				UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
				if (Cards && Cards->GetDecks().Num() > 0)
				{
					int32 Index = PlayerOwner->WasInputKeyJustPressed(EKeys::One) ? 0
						: (PlayerOwner->WasInputKeyJustPressed(EKeys::Two) ? 1 : 2);
					const TArray<FStarterDeckDef>& Decks = Cards->GetDecks();
					if (Decks.IsValidIndex(Index))
					{
						StartDuelWithDeck(Decks[Index].Id);
					}
				}
			}
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape))
			{
				CloseDuel();
			}
		}
	}
	else if (DuelMode == EDuelUiMode::Duel && PlayerOwner)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape))
		{
			if (DuelPileType != EDuelPileType::None) DuelPileType = EDuelPileType::None;
			else if (bDuelTributeSet) DuelCancelTribute();
			else DuelSelectedUid = 0;
		}
		if (DuelEngine && DuelEngine->IsPlayerTurn() && !DuelEngine->IsAwaitingAi())
		{
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::B))
			{
				DuelEngine->EnterBattlePhase();
			}
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::N) || PlayerOwner->WasInputKeyJustPressed(EKeys::End))
			{
				UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("DUELKEY end-turn"));
				DuelEngine->EndTurn();
				if (DuelEngine->IsAwaitingDiscard())
				{
					DuelShowMessage(TEXT("Discard down to six cards before ending the turn."), FLinearColor(0.95f, 0.8f, 0.4f));
				}
			}
		}
	}
	else if (DuelMode == EDuelUiMode::Result && PlayerOwner)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar))
		{
			OpenDeckSelect(DuelOpponentId, DuelOpponentName, DuelOpponentDeckId);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape))
		{
			CloseDuel();
		}
	}
}

// ---------------------------------------------------------------------------
// Duel animation feed
// ---------------------------------------------------------------------------

void FDADuelUI::PumpDuelVisualEvents(float DeltaSeconds)
{
	if (!DuelEngine)
	{
		return;
	}

	TArray<FDuelVisualEvent> NewEvents;
	DuelEngine->ConsumeVisualEvents(NewEvents);
	if (NewEvents.Num() > 0)
	{
		DuelIncomingEvents.Append(NewEvents);
	}

	DuelEventPumpTimer -= DeltaSeconds;
	if (DuelEventPumpTimer > 0.0f || DuelIncomingEvents.Num() == 0)
	{
		return;
	}

	SpawnDuelFx(DuelIncomingEvents[0]);
	DuelIncomingEvents.RemoveAt(0);
	DuelEventPumpTimer = DuelEventGap;
}

void FDADuelUI::UpdateDuelVisuals(float DeltaSeconds)
{
	if (DuelMode == EDuelUiMode::None || !DuelEngine)
	{
		return;
	}

	PumpDuelVisualEvents(DeltaSeconds);
	DuelIntroTime += DeltaSeconds;

	for (int32 I = DuelFx.Num() - 1; I >= 0; --I)
	{
		DuelFx[I].Elapsed += DeltaSeconds;
		if (!DuelFx[I].IsAlive())
		{
			DuelFx.RemoveAt(I);
		}
	}

	const float CurrentPlayerLp = static_cast<float>(DuelEngine->GetSide(EDuelOwner::Player).LP);
	const float CurrentOppLp = static_cast<float>(DuelEngine->GetSide(EDuelOwner::Opponent).LP);
	DuelPlayerLpDisplay = FMath::FInterpTo(DuelPlayerLpDisplay, CurrentPlayerLp, DeltaSeconds, 8.0f);
	DuelOpponentLpDisplay = FMath::FInterpTo(DuelOpponentLpDisplay, CurrentOppLp, DeltaSeconds, 8.0f);
	if (FMath::Abs(DuelPlayerLpDisplay - CurrentPlayerLp) < 1.0f) DuelPlayerLpDisplay = CurrentPlayerLp;
	if (FMath::Abs(DuelOpponentLpDisplay - CurrentOppLp) < 1.0f) DuelOpponentLpDisplay = CurrentOppLp;

	DuelPlayerLpHit = FMath::Max(0.0f, DuelPlayerLpHit - DeltaSeconds * 2.5f);
	DuelOpponentLpHit = FMath::Max(0.0f, DuelOpponentLpHit - DeltaSeconds * 2.5f);
	DuelPlayerPortraitPulse = FMath::Max(0.0f, DuelPlayerPortraitPulse - DeltaSeconds * 2.2f);
	DuelOpponentPortraitPulse = FMath::Max(0.0f, DuelOpponentPortraitPulse - DeltaSeconds * 2.2f);

	if (DuelShakeTime > 0.0f)
	{
		DuelShakeTime = FMath::Max(0.0f, DuelShakeTime - DeltaSeconds);
		const float Strength = DuelShakeStrength * (DuelShakeTime / 0.34f);
		DuelShakeX = FMath::Sin(GetWorld() ? GetWorld()->GetTimeSeconds() * 94.0f : 0.0f) * Strength;
		DuelShakeY = FMath::Cos(GetWorld() ? GetWorld()->GetTimeSeconds() * 72.0f : 0.0f) * Strength * 0.55f;
	}
	else
	{
		DuelShakeX = 0.0f;
		DuelShakeY = 0.0f;
	}

	DuelFlashTime = FMath::Max(0.0f, DuelFlashTime - DeltaSeconds);
	DuelEventBannerTime = FMath::Max(0.0f, DuelEventBannerTime - DeltaSeconds);

	if (DuelCutInTime > 0.0f)
	{
		DuelCutInTime = FMath::Max(0.0f, DuelCutInTime - DeltaSeconds);
		DuelCutInAge += DeltaSeconds;
		if (DuelCutInTime <= 0.0f)
		{
			DuelCutInPriority = 0;
		}
	}

	// A low-LP warning is one of the strongest dramatic beats in the duel.
	// Trigger it once per side, on the actual rules value rather than the
	// interpolated display so a fast burn sequence cannot skip it.
	if (DuelMode == EDuelUiMode::Duel && !DuelEngine->HasWinner())
	{
		const int32 RulesPlayerLp = DuelEngine->GetSide(EDuelOwner::Player).LP;
		const int32 RulesOpponentLp = DuelEngine->GetSide(EDuelOwner::Opponent).LP;
		if (!bDuelPlayerLowLpWarned && RulesPlayerLp > 0 && RulesPlayerLp <= 2000)
		{
			bDuelPlayerLowLpWarned = true;
			PlayCue(OwnerHUD.Get(), EDASfx::LowLp, 0.8f);
			TriggerDuelCutIn(EDuelOwner::Player, TEXT("shocked"), TEXT("LOW LIFE POINTS"),
				TEXT("UNDER 2000 LP"), 86, 2.5f);
			DuelFlashColor = FLinearColor(0.72f, 0.04f, 0.03f, 0.18f);
			DuelFlashTime = 0.4f;
		}
		if (!bDuelOpponentLowLpWarned && RulesOpponentLp > 0 && RulesOpponentLp <= 2000)
		{
			bDuelOpponentLowLpWarned = true;
			PlayCue(OwnerHUD.Get(), EDASfx::LowLp, 0.65f, 0.94f);
			TriggerDuelCutIn(EDuelOwner::Opponent, TEXT("shocked"), TEXT("LOW LIFE POINTS"),
				TEXT("UNDER 2000 LP"), 86, 2.5f);
			DuelFlashColor = FLinearColor(0.72f, 0.04f, 0.03f, 0.18f);
			DuelFlashTime = 0.4f;
		}
	}
}

void FDADuelUI::BuildDuelFxDemo()
{
	// A deterministic presentation reel for screenshots and manual inspection.
	// It is only used with -DADuelFxDemo and never changes the rules state.
	auto Add = [this](EDuelVisualEventType Type, EDuelOwner Side, int32 CardId, int32 Amount,
		const FString& Text, int32 Zone = INDEX_NONE, int32 TargetCardId = 0,
		int32 TargetZone = INDEX_NONE, bool bFaceDown = false)
	{
		FDuelVisualEvent Event;
		Event.Type = Type;
		Event.Side = Side;
		Event.CardId = CardId;
		Event.TargetCardId = TargetCardId;
		Event.Amount = Amount;
		Event.Text = Text;
		Event.Zone = Zone;
		Event.TargetZone = TargetZone;
		Event.bFaceDown = bFaceDown;
		DuelIncomingEvents.Add(Event);
	};

	Add(EDuelVisualEventType::TurnStart, EDuelOwner::Player, 0, 3, TEXT("YOUR TURN"));
	Add(EDuelVisualEventType::Summon, EDuelOwner::Player, 1108, 0, TEXT("ELEMENTAL HERO CLAYMAN"), 0);
	Add(EDuelVisualEventType::Spell, EDuelOwner::Player, 387, 0, TEXT("POT OF GREED"), 0);
	Add(EDuelVisualEventType::Trap, EDuelOwner::Opponent, 421, 0, TEXT("MIRROR FORCE"), 1);
	Add(EDuelVisualEventType::Attack, EDuelOwner::Player, 1106, 0, TEXT("ELEMENTAL HERO AVIAN"), 0, 1107, 0);
	Add(EDuelVisualEventType::Damage, EDuelOwner::Opponent, 0, 1300, TEXT("BATTLE"));
	Add(EDuelVisualEventType::Destroy, EDuelOwner::Opponent, 1107, 0, TEXT("MIRROR FORCE"), 0);
	Add(EDuelVisualEventType::Fusion, EDuelOwner::Player, 1129, 0, TEXT("AVIAN + BURSTINATRIX"));
	Add(EDuelVisualEventType::Ritual, EDuelOwner::Player, 841, 0, TEXT("INCANDESCENT ORDEAL"));
	Add(EDuelVisualEventType::Counter, EDuelOwner::Player, 841, 3, TEXT("SPELL COUNTER"), 2);
	Add(EDuelVisualEventType::Draw, EDuelOwner::Player, 1106, 0, TEXT("DRAW"));
	Add(EDuelVisualEventType::Search, EDuelOwner::Player, 117, 0, TEXT("BLACK PENDANT"));
	Add(EDuelVisualEventType::Discard, EDuelOwner::Player, 148, 0, TEXT("SPARKS"));
	Add(EDuelVisualEventType::Banish, EDuelOwner::Opponent, 1161, 0, TEXT("WINGED KURIBOH LV10"));
	Add(EDuelVisualEventType::Mill, EDuelOwner::Opponent, 1107, 0, TEXT("BURSTINATRIX"), INDEX_NONE, 0, INDEX_NONE, true);
	Add(EDuelVisualEventType::Return, EDuelOwner::Player, 1108, 0, TEXT("CLAYMAN"));
	Add(EDuelVisualEventType::Position, EDuelOwner::Player, 1108, 0, TEXT("DEFENSE"), 0);
	Add(EDuelVisualEventType::Heal, EDuelOwner::Player, 0, 800, TEXT("SPIRIT OF THE BREEZE"));
	Add(EDuelVisualEventType::Cost, EDuelOwner::Player, 0, 800, TEXT("PREMATURE BURIAL"));
	Add(EDuelVisualEventType::Effect, EDuelOwner::Player, 0, 0, TEXT("ELEMENTAL HERO"));
}

void FDADuelUI::SpawnDuelFx(const FDuelVisualEvent& Event)
{
	PlayDuelEventCue(OwnerHUD.Get(), Event);

	FDuelFx Fx;
	Fx.Type = Event.Type;
	Fx.Side = Event.Side;
	Fx.CardUid = Event.CardUid;
	Fx.CardId = Event.CardId;
	Fx.TargetUid = Event.TargetUid;
	Fx.TargetCardId = Event.TargetCardId;
	Fx.Amount = Event.Amount;
	Fx.Zone = Event.Zone;
	Fx.TargetZone = Event.TargetZone;
	Fx.bFaceDown = Event.bFaceDown;
	Fx.bDirect = Event.bDirect;
	Fx.Text = Event.Text;

	const bool bPlayer = Event.Side == EDuelOwner::Player;
	DuelEventBannerDuration = 1.0f;
	const FVector2D PlayerHand(800.0f, 810.0f);
	const FVector2D OpponentHand(800.0f, 130.0f);
	const FVector2D PlayerLp(1290.0f, 60.0f);
	const FVector2D OpponentLp(330.0f, 60.0f);
	// Life-point changes are shown over the affected side of the field rather
	// than on top of the scoreboard, where the big number hid the LP value.
	const FVector2D PlayerDamage(800.0f, 690.0f);
	const FVector2D OpponentDamage(800.0f, 230.0f);
	const FVector2D PlayerDeck(1103.0f, 647.0f);
	const FVector2D OpponentDeck(1103.0f, 201.0f);
	const FVector2D PlayerGrave(1103.0f, 730.0f);
	const FVector2D OpponentGrave(1103.0f, 284.0f);
	const FVector2D PlayerBanish(1103.0f, 772.0f);
	const FVector2D OpponentBanish(1103.0f, 326.0f);
	const FVector2D Center(800.0f, 450.0f);

	auto IsMonsterCard = [this](int32 CardId)
	{
		UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
		const FCardRecord* Record = Cards ? Cards->FindCard(CardId) : nullptr;
		return !Record || Record->IsMonster();
	};

	switch (Event.Type)
	{
	case EDuelVisualEventType::Draw:
		Fx.Source = bPlayer ? PlayerDeck : OpponentDeck;
		Fx.Target = bPlayer ? PlayerHand : OpponentHand;
		Fx.Duration = 0.55f;
		break;
	case EDuelVisualEventType::Summon:
	case EDuelVisualEventType::SetCard:
		Fx.Source = bPlayer ? PlayerHand : OpponentHand;
		Fx.Target = Event.Zone != INDEX_NONE
			? DuelZoneCenter(Event.Side, Event.Zone, true)
			: DuelCardCenter(Event.CardUid, Event.Side, true);
		Fx.Duration = 0.68f;
		break;
	case EDuelVisualEventType::Spell:
	case EDuelVisualEventType::Trap:
		Fx.Source = bPlayer ? PlayerHand : OpponentHand;
		Fx.Target = Event.Zone != INDEX_NONE
			? DuelZoneCenter(Event.Side, Event.Zone, false)
			: DuelCardCenter(Event.CardUid, Event.Side, false);
		Fx.Duration = 0.62f;
		break;
	case EDuelVisualEventType::Attack:
		Fx.Source = Event.Zone != INDEX_NONE
			? DuelZoneCenter(Event.Side, Event.Zone, true)
			: DuelCardCenter(Event.CardUid, Event.Side, true);
		Fx.Target = Event.TargetUid != 0
			? (Event.TargetZone != INDEX_NONE
				? DuelZoneCenter(Event.Side == EDuelOwner::Player ? EDuelOwner::Opponent : EDuelOwner::Player,
					Event.TargetZone, true)
				: DuelCardCenter(Event.TargetUid, Event.Side == EDuelOwner::Player ? EDuelOwner::Opponent : EDuelOwner::Player, true))
			: (Event.Side == EDuelOwner::Player ? OpponentLp : PlayerLp);
		Fx.Duration = 0.52f;
		DuelPlayerPortraitPulse = FMath::Max(DuelPlayerPortraitPulse, bPlayer ? 1.0f : 0.0f);
		DuelOpponentPortraitPulse = FMath::Max(DuelOpponentPortraitPulse, bPlayer ? 0.0f : 1.0f);
		break;
	case EDuelVisualEventType::Damage:
		Fx.Source = bPlayer ? PlayerDamage : OpponentDamage;
		Fx.Target = Fx.Source;
		Fx.Duration = 1.05f;
		if (bPlayer)
		{
			DuelPlayerLpHit = 1.0f;
			DuelPlayerPortraitPulse = 1.0f;
		}
		else
		{
			DuelOpponentLpHit = 1.0f;
			DuelOpponentPortraitPulse = 1.0f;
		}
		DuelShakeTime = 0.34f;
		DuelShakeStrength = FMath::Clamp(3.0f + Event.Amount * 0.006f, 3.0f, 16.0f);
		DuelFlashColor = FLinearColor(0.58f, 0.04f, 0.03f, 0.20f);
		DuelFlashTime = 0.30f;
		break;
	case EDuelVisualEventType::Heal:
		Fx.Source = bPlayer ? PlayerDamage : OpponentDamage;
		Fx.Target = Fx.Source;
		Fx.Duration = 1.0f;
		if (bPlayer) DuelPlayerPortraitPulse = 0.8f; else DuelOpponentPortraitPulse = 0.8f;
		DuelFlashColor = FLinearColor(0.18f, 0.54f, 0.28f, 0.14f);
		DuelFlashTime = 0.32f;
		break;
	case EDuelVisualEventType::Destroy:
	{
		const bool bMonster = IsMonsterCard(Event.CardId);
		Fx.Source = Event.Zone != INDEX_NONE
			? DuelZoneCenter(Event.Side, Event.Zone, bMonster)
			: DuelCardCenter(Event.CardUid, Event.Side, bMonster);
		Fx.Target = Fx.Source;
		Fx.Duration = 0.72f;
		break;
	}
	case EDuelVisualEventType::Discard:
		Fx.Source = bPlayer ? PlayerHand : OpponentHand;
		Fx.Target = bPlayer ? PlayerGrave : OpponentGrave;
		Fx.Duration = 0.58f;
		break;
	case EDuelVisualEventType::Banish:
		Fx.Source = bPlayer ? PlayerGrave : OpponentGrave;
		Fx.Target = bPlayer ? PlayerBanish : OpponentBanish;
		Fx.Duration = 0.62f;
		break;
	case EDuelVisualEventType::Search:
		Fx.Source = bPlayer ? PlayerDeck : OpponentDeck;
		Fx.Target = bPlayer ? PlayerHand : OpponentHand;
		Fx.Duration = 0.62f;
		break;
	case EDuelVisualEventType::Mill:
		Fx.Source = bPlayer ? PlayerDeck : OpponentDeck;
		Fx.Target = bPlayer ? PlayerGrave : OpponentGrave;
		Fx.Duration = 0.58f;
		break;
	case EDuelVisualEventType::Return:
		Fx.Source = Center;
		Fx.Target = bPlayer ? PlayerHand : OpponentHand;
		Fx.Duration = 0.62f;
		break;
	case EDuelVisualEventType::Position:
		Fx.Source = Event.Zone != INDEX_NONE
			? DuelZoneCenter(Event.Side, Event.Zone, true)
			: DuelCardCenter(Event.CardUid, Event.Side, true);
		Fx.Target = Fx.Source;
		Fx.Duration = 0.7f;
		break;
	case EDuelVisualEventType::Fusion:
		Fx.Source = FVector2D(800.0f, 560.0f);
		Fx.Target = Fx.Source;
		Fx.Duration = 1.15f;
		DuelEventBannerTitle = TEXT("FUSION SUMMON");
		DuelEventBannerSubtitle = Event.Text.IsEmpty() ? TEXT("POLYMERIZATION") : Event.Text.ToUpper();
		DuelEventBannerColor = FLinearColor(0.86f, 0.68f, 0.28f);
		DuelEventBannerTime = 1.25f;
		DuelEventBannerDuration = 1.25f;
		break;
	case EDuelVisualEventType::Ritual:
		Fx.Source = FVector2D(800.0f, 560.0f);
		Fx.Target = Fx.Source;
		Fx.Duration = 1.15f;
		DuelEventBannerTitle = TEXT("RITUAL SUMMON");
		DuelEventBannerSubtitle = Event.Text.IsEmpty() ? TEXT("INCANDESCENT ORDEAL") : Event.Text.ToUpper();
		DuelEventBannerColor = FLinearColor(0.92f, 0.46f, 0.26f);
		DuelEventBannerTime = 1.25f;
		DuelEventBannerDuration = 1.25f;
		break;
	case EDuelVisualEventType::Cost:
		Fx.Source = bPlayer ? PlayerDamage : OpponentDamage;
		Fx.Target = Fx.Source;
		Fx.Duration = 0.9f;
		break;
	case EDuelVisualEventType::Counter:
		Fx.Source = Event.Zone != INDEX_NONE
			? DuelZoneCenter(Event.Side, Event.Zone, true)
			: DuelCardCenter(Event.CardUid, Event.Side, true);
		Fx.Target = Fx.Source;
		Fx.Duration = 0.9f;
		break;
	case EDuelVisualEventType::TurnStart:
		Fx.Duration = 0.4f;
		// Do not stack a full-width turn banner on top of a character cut-in
		// from the previous beat; the persistent phase strip still names the turn.
		if (DuelCutInTime <= 0.0f)
		{
			Fx.Duration = 1.15f;
			DuelEventBannerTitle = bPlayer ? TEXT("YOUR TURN") : FString::Printf(TEXT("%s'S TURN"), *DuelOpponentName.ToUpper());
			DuelEventBannerSubtitle = FString::Printf(TEXT("TURN %d"), Event.Amount);
			DuelEventBannerColor = bPlayer ? FLinearColor(0.38f, 0.70f, 0.92f) : FLinearColor(0.86f, 0.64f, 0.28f);
			DuelEventBannerTime = 1.55f;
			DuelEventBannerDuration = 1.55f;
		}
		if (bPlayer) DuelPlayerPortraitPulse = 1.0f; else DuelOpponentPortraitPulse = 1.0f;
		break;
	case EDuelVisualEventType::PhaseChange:
		Fx.Duration = 1.0f;
		if (DuelCutInTime <= 0.0f)
		{
			DuelEventBannerTitle = Event.Text.IsEmpty() ? TEXT("PHASE") : Event.Text;
			DuelEventBannerSubtitle = bPlayer ? TEXT("YOUR MOVE") : FString::Printf(TEXT("%s'S MOVE"), *DuelOpponentName.ToUpper());
			DuelEventBannerColor = Event.Text.Contains(TEXT("BATTLE"))
				? FLinearColor(0.94f, 0.52f, 0.28f) : FLinearColor(0.44f, 0.72f, 0.88f);
			DuelEventBannerTime = 1.15f;
			DuelEventBannerDuration = 1.15f;
		}
		break;
	case EDuelVisualEventType::Effect:
		Fx.Source = Center;
		Fx.Target = Fx.Source;
		Fx.Duration = 0.9f;
		break;
	case EDuelVisualEventType::Win:
		Fx.Duration = 1.3f;
		DuelEventBannerTitle = bPlayer ? TEXT("DUEL WON") : TEXT("DUEL LOST");
		DuelEventBannerSubtitle = TEXT("THE DUEL IS OVER");
		DuelEventBannerColor = bPlayer ? Gold : FLinearColor(0.86f, 0.38f, 0.32f);
		DuelEventBannerTime = 1.8f;
		DuelEventBannerDuration = 1.8f;
		if (bPlayer) DuelPlayerPortraitPulse = 1.0f; else DuelOpponentPortraitPulse = 1.0f;
		DuelFlashColor = bPlayer ? FLinearColor(0.16f, 0.12f, 0.04f, 0.18f) : FLinearColor(0.18f, 0.02f, 0.02f, 0.2f);
		DuelFlashTime = 0.5f;
		break;
	default:
		Fx.Duration = 0.5f;
		break;
	}

	// Pick the dramatic reaction beats.  These are presentation-only; they
	// never change the rules state or block the player's input.
	UCardDatabaseSubsystem* CardDb = GetGameInstance()
		? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const FCardRecord* EventCard = CardDb ? CardDb->FindCard(Event.CardId) : nullptr;
	const FString EventCardName = EventCard ? EventCard->Name
		: (Event.Text.IsEmpty() ? FString() : Event.Text);
	const auto CutIn = [this, &Event](const TCHAR* Expression, const TCHAR* Title,
		const FString& Subtitle, int32 Priority, float Duration)
	{
		TriggerDuelCutIn(Event.Side, Expression, Title, Subtitle, Priority, Duration);
	};

	switch (Event.Type)
	{
	case EDuelVisualEventType::TurnStart:
		// Turn changes already get a banner and a scoreboard pulse; reserve the
		// large portrait cut-in for the action beats that need a reaction.
		break;
	case EDuelVisualEventType::Summon:
		if (EventCard && !EventCard->IsSpell() && !EventCard->IsTrap()
			&& (EventCard->Atk >= 2000 || EventCard->Level >= 5
				|| EventCard->CardType.Contains(TEXT("Fusion"))))
		{
			CutIn(TEXT("determined"), TEXT("SUMMON"), EventCardName, 55, 1.9f);
		}
		break;
	case EDuelVisualEventType::Fusion:
		CutIn(TEXT("determined"), TEXT("FUSION SUMMON"),
			Event.Text.IsEmpty() ? TEXT("POLYMERIZATION") : Event.Text, 90, 2.5f);
		break;
	case EDuelVisualEventType::Ritual:
		CutIn(TEXT("determined"), TEXT("RITUAL SUMMON"),
			Event.Text.IsEmpty() ? TEXT("INCANDESCENT ORDEAL") : Event.Text, 90, 2.5f);
		break;
	case EDuelVisualEventType::Trap:
		CutIn(TEXT("determined"), TEXT("TRAP CARD"),
			Event.Text.IsEmpty() ? TEXT("FACE-DOWN CARD") : Event.Text, 42, 1.7f);
		break;
	case EDuelVisualEventType::Attack:
		CutIn(TEXT("determined"), TEXT("ATTACK"),
			Event.Text.IsEmpty() ? TEXT("DIRECT ATTACK") : Event.Text, 60, 1.75f);
		break;
	case EDuelVisualEventType::Damage:
		CutIn(Event.Amount >= 1500 ? TEXT("shocked") : TEXT("sad"), TEXT("DAMAGE"),
			FString::Printf(TEXT("-%d LP"), Event.Amount), Event.Amount >= 1500 ? 74 : 52, 1.9f);
		break;
	case EDuelVisualEventType::Destroy:
		if (EventCard && EventCard->IsMonster())
		{
			CutIn(TEXT("sad"), TEXT("MONSTER DESTROYED"), EventCardName, 64, 1.85f);
		}
		break;
	case EDuelVisualEventType::Heal:
		if (Event.Amount >= 500)
		{
			CutIn(TEXT("happy"), TEXT("LIFE POINT RECOVERY"),
				FString::Printf(TEXT("+%d LP"), Event.Amount), 44, 1.7f);
		}
		break;
	case EDuelVisualEventType::Cost:
		if (Event.Amount >= 800)
		{
			CutIn(TEXT("angry"), TEXT("LIFE POINT COST"),
				FString::Printf(TEXT("-%d LP"), Event.Amount), 38, 1.7f);
		}
		break;
	case EDuelVisualEventType::Win:
		CutIn(bPlayer ? TEXT("laugh") : TEXT("sad"),
			bPlayer ? TEXT("DUEL WON") : TEXT("DUEL LOST"),
			bPlayer ? FString::Printf(TEXT("%s DEFEATED"), *DuelOpponentName.ToUpper()) : FString::Printf(TEXT("%s WINS"), *DuelOpponentName.ToUpper()), 100, 3.0f);
		break;
	default:
		break;
	}

	DuelFx.Add(Fx);
}

FVector2D FDADuelUI::DuelCardCenter(int32 Uid, EDuelOwner FallbackSide, bool bMonsterFallback) const
{
	if (DuelEngine && Uid != 0)
	{
		for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			const FDuelSide& State = DuelEngine->GetSide(Side);
			const float MonsterY = Side == EDuelOwner::Player ? 558.0f : 384.0f;
			const float SpellY = Side == EDuelOwner::Player ? 694.0f : 248.0f;
			for (int32 I = 0; I < State.Monsters.Num(); ++I)
			{
				if (State.Monsters[I].IsValid() && State.Monsters[I].Uid == Uid)
				{
					return FVector2D(584.0f + I * 98.0f, MonsterY);
				}
			}
			for (int32 I = 0; I < State.Spells.Num(); ++I)
			{
				if (State.Spells[I].IsValid() && State.Spells[I].Uid == Uid)
				{
					return FVector2D(584.0f + I * 98.0f, SpellY);
				}
			}
			if (State.Field.IsValid() && State.Field.Uid == Uid)
			{
				return FVector2D(474.0f, SpellY);
			}
			for (int32 I = 0; I < State.Hand.Num(); ++I)
			{
				if (State.Hand[I].Uid == Uid)
				{
					const int32 Count = State.Hand.Num();
					const float Spacing = FMath::Min(80.0f, 650.0f / FMath::Max(1, Count));
					const float TotalWidth = (Count - 1) * Spacing + 72.0f;
					return FVector2D(800.0f - TotalWidth * 0.5f + I * Spacing + 36.0f,
						Side == EDuelOwner::Player ? 818.0f : 130.0f);
				}
			}
		}
	}

	const float Y = bMonsterFallback
		? (FallbackSide == EDuelOwner::Player ? 558.0f : 384.0f)
		: (FallbackSide == EDuelOwner::Player ? 694.0f : 248.0f);
	return FVector2D(780.0f, Y);
}

FVector2D FDADuelUI::DuelZoneCenter(EDuelOwner Side, int32 Zone, bool bMonster) const
{
	if (Zone == INDEX_NONE)
	{
		return DuelCardCenter(0, Side, bMonster);
	}
	if (bMonster)
	{
		const float Y = Side == EDuelOwner::Player ? 558.0f : 384.0f;
		return FVector2D(584.0f + Zone * 98.0f, Y);
	}
	const float Y = Side == EDuelOwner::Player ? 694.0f : 248.0f;
	return FVector2D(584.0f + Zone * 98.0f, Y);
}

const FDuelFx* FDADuelUI::FindDuelFx(EDuelVisualEventType Type, int32 Uid) const
{
	for (int32 I = DuelFx.Num() - 1; I >= 0; --I)
	{
		if (DuelFx[I].Type == Type && (Uid == 0 || DuelFx[I].CardUid == Uid))
		{
			return &DuelFx[I];
		}
	}
	return nullptr;
}

bool FDADuelUI::GetDuelCardFx(int32 Uid, float& OutOffsetX, float& OutOffsetY, float& OutScale, float& OutAlpha) const
{
	OutOffsetX = 0.0f;
	OutOffsetY = 0.0f;
	OutScale = 1.0f;
	OutAlpha = 1.0f;
	if (Uid == 0)
	{
		return false;
	}

	bool bHasFx = false;
	for (const FDuelFx& Fx : DuelFx)
	{
		const float Local = Fx.Elapsed - Fx.Delay;
		if (Local < 0.0f || Local > Fx.Duration)
		{
			continue;
		}
		const float T = FMath::Clamp(Local / Fx.Duration, 0.0f, 1.0f);
		const float Ease = 1.0f - FMath::Pow(1.0f - T, 3.0f);

		if (Fx.Type == EDuelVisualEventType::Summon || Fx.Type == EDuelVisualEventType::SetCard)
		{
			if (Fx.CardUid == Uid)
			{
				OutScale *= 0.58f + 0.42f * Ease;
				OutOffsetY += (1.0f - Ease) * 42.0f;
				OutAlpha *= FMath::Clamp(T * 4.0f, 0.0f, 1.0f);
				bHasFx = true;
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Attack)
		{
			if (Fx.CardUid == Uid)
			{
				// The attack effects draw a full card flight; hide the board
				// copy while it is airborne so the card does not appear twice.
				const float Lunge = FMath::Sin(T * PI);
				OutOffsetY += (Fx.Side == EDuelOwner::Player ? -44.0f : 44.0f) * Lunge;
				OutScale *= 1.0f + 0.045f * Lunge;
				OutAlpha *= FMath::Clamp(1.0f - Lunge * 1.4f, 0.0f, 1.0f);
				bHasFx = true;
			}
			else if (Fx.TargetUid == Uid)
			{
				OutOffsetX += FMath::Sin(Local * 90.0f) * 5.0f * (1.0f - T);
				OutScale *= 1.0f + 0.03f * (1.0f - T);
				bHasFx = true;
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Spell || Fx.Type == EDuelVisualEventType::Trap)
		{
			if (Fx.CardUid == Uid)
			{
				OutScale *= 1.0f + 0.035f * FMath::Sin(T * PI);
				bHasFx = true;
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Position || Fx.Type == EDuelVisualEventType::Counter)
		{
			if (Fx.CardUid == Uid)
			{
				OutScale *= 1.0f + 0.06f * FMath::Sin(T * PI);
				OutOffsetY += FMath::Sin(T * PI * 2.0f) * 3.0f;
				bHasFx = true;
			}
		}
	}
	return bHasFx;
}

void FDADuelUI::DuelBeginTribute(int32 HandUid, bool bSet)
{
	if (!DuelEngine)
	{
		return;
	}
	DuelTributeHandUid = HandUid;
	bDuelTributeSet = bSet;
	DuelTributeUids.Reset();
	DuelSelectedUid = 0;
	DuelShowMessage(FString::Printf(TEXT("Select %d tribute(s), then confirm."), DuelEngine->GetRequiredTributes(HandUid)),
		FLinearColor(0.95f, 0.82f, 0.42f));
}

void FDADuelUI::DuelConfirmTribute()
{
	if (!DuelEngine || !bDuelTributeSet)
	{
		return;
	}
	const int32 Required = DuelEngine->GetRequiredTributes(DuelTributeHandUid);
	if (DuelTributeUids.Num() != Required)
	{
		DuelShowMessage(FString::Printf(TEXT("Select exactly %d tribute(s)."), Required));
		return;
	}
	TArray<int32> Tributes = DuelTributeUids.Array();
	FString Error;
	const bool bOk = DuelEngine->NormalSummon(DuelTributeHandUid, Tributes, bDuelTributeSet, Error);
	if (!bOk)
	{
		DuelShowMessage(Error);
		return;
	}
	DuelCancelTribute();
	DuelSelectedUid = 0;
}

void FDADuelUI::DuelCancelTribute()
{
	bDuelTributeSet = false;
	DuelTributeHandUid = 0;
	DuelTributeUids.Reset();
	DuelMessage.Empty();
	DuelMessageTimer = 0.0f;
}

void FDADuelUI::DuelShowMessage(const FString& Message, const FLinearColor& Color)
{
	PlayCue(OwnerHUD.Get(), EDASfx::Deny, 0.5f);
	DuelMessage = Message;
	DuelMessageTimer = 4.0f;
}

FDuelCard* FDADuelUI::GetDuelSelectedCard()
{
	if (!DuelEngine || DuelSelectedUid == 0)
	{
		return nullptr;
	}
	return DuelEngine->FindCard(DuelSelectedUid);
}

FString FDADuelUI::DuelTrim(const FString& Text, int32 MaxLength) const
{
	const FString Clean = CleanDuelText(Text);
	if (Clean.Len() <= MaxLength)
	{
		return Clean;
	}
	return Clean.Left(FMath::Max(0, MaxLength - 3)) + TEXT("...");
}

void FDADuelUI::AddDuelHit(const FString& Action, int32 Value, float X, float Y, float W, float H, const FString& Payload)
{
	FDuelHitTarget Hit;
	Hit.Action = Action;
	Hit.Payload = Payload;
	Hit.Value = Value;
	Hit.X = X;
	Hit.Y = Y;
	Hit.W = W;
	Hit.H = H;
	DuelHitTargets.Add(Hit);
}

void FDADuelUI::HandleDuelHit(const FString& Action, int32 Value, const FString& Payload)
{
	UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("DUELHIT action=%s value=%d payload=%s"), *Action, Value, *Payload);

	// Card handling gets a paper tick instead of the generic UI click so
	// selecting, opening a pile, and closing it feel physical.
	EDASfx ClickCue = EDASfx::UiClick;
	float ClickVolume = 0.5f;
	if (Action == TEXT("select") || Action == TEXT("tribute"))
	{
		ClickCue = EDASfx::CardFlip;
		ClickVolume = 0.55f;
	}
	else if (Action == TEXT("pile"))
	{
		ClickCue = EDASfx::CardFlip;
		ClickVolume = 0.75f;
	}
	else if (Action == TEXT("closepile"))
	{
		ClickCue = EDASfx::CardPlace;
		ClickVolume = 0.45f;
	}
	PlayCue(OwnerHUD.Get(), ClickCue, ClickVolume, 1.0f + 0.05f * FMath::FRand());

	if (DuelMode == EDuelUiMode::DeckSelect)
	{
		if (Action == TEXT("deck"))
		{
			StartDuelWithDeck(Payload);
		}
		else if (Action == TEXT("back"))
		{
			CloseDuel();
		}
		return;
	}
	if (DuelMode == EDuelUiMode::Result)
	{
		if (Action == TEXT("rematch"))
		{
			OpenDeckSelect(DuelOpponentId, DuelOpponentName, DuelOpponentDeckId);
		}
		else if (Action == TEXT("return"))
		{
			CloseDuel();
		}
		return;
	}
	if (DuelMode != EDuelUiMode::Duel || !DuelEngine)
	{
		return;
	}
	if (Action == TEXT("closepile"))
	{
		DuelPileType = EDuelPileType::None;
		return;
	}
	if (Action == TEXT("pile"))
	{
		DuelPileOwner = (Value / 10) == 0 ? EDuelOwner::Player : EDuelOwner::Opponent;
		DuelPileType = static_cast<EDuelPileType>(Value % 10);
		return;
	}
	if (Action == TEXT("select"))
	{
		if (bDuelTributeSet)
		{
			return;
		}
		DuelSelectedUid = (DuelSelectedUid == Value) ? 0 : Value;
		return;
	}
	if (Action == TEXT("tribute"))
	{
		if (DuelTributeUids.Contains(Value))
		{
			DuelTributeUids.Remove(Value);
		}
		else
		{
			const int32 Required = DuelEngine->GetRequiredTributes(DuelTributeHandUid);
			if (DuelTributeUids.Num() < Required)
			{
				DuelTributeUids.Add(Value);
			}
		}
		return;
	}
	if (Action == TEXT("confirmtribute"))
	{
		DuelConfirmTribute();
		return;
	}
	if (Action == TEXT("canceltribute"))
	{
		DuelCancelTribute();
		return;
	}
	if (Action == TEXT("discard"))
	{
		FString Error;
		if (!DuelEngine->DiscardFromHand(Value, Error))
		{
			DuelShowMessage(Error);
		}
		else if (!DuelEngine->IsAwaitingDiscard())
		{
			DuelShowMessage(FString::Printf(TEXT("Hand limit met. %s is taking their turn."), *DuelOpponentName), FLinearColor(0.55f, 0.82f, 0.95f));
		}
		return;
	}

	FString Error;
	bool bOk = false;
	if (Action == TEXT("summon"))
	{
		const int32 Required = DuelEngine->GetRequiredTributes(Value);
		if (Required > 0)
		{
			DuelBeginTribute(Value, false);
			return;
		}
		bOk = DuelEngine->NormalSummon(Value, {}, false, Error);
	}
	else if (Action == TEXT("setmonster"))
	{
		const int32 Required = DuelEngine->GetRequiredTributes(Value);
		if (Required > 0)
		{
			DuelBeginTribute(Value, true);
			return;
		}
		bOk = DuelEngine->NormalSummon(Value, {}, true, Error);
	}
	else if (Action == TEXT("special"))
	{
		bOk = DuelEngine->SpecialSummon(Value, Error);
	}
	else if (Action == TEXT("activatespell"))
	{
		bOk = DuelEngine->ActivateSpell(Value, Error);
	}
	else if (Action == TEXT("settrap"))
	{
		bOk = DuelEngine->SetSpellTrap(Value, Error);
	}
	else if (Action == TEXT("activatetrap"))
	{
		bOk = DuelEngine->ActivateSetTrap(Value, Error);
	}
	else if (Action == TEXT("flip"))
	{
		bOk = DuelEngine->FlipSummon(Value, Error);
	}
	else if (Action == TEXT("position"))
	{
		bOk = DuelEngine->ChangePosition(Value, Error);
	}
	else if (Action == TEXT("effect"))
	{
		bOk = DuelEngine->ActivateMonsterEffect(Value, Error);
	}
	else if (Action == TEXT("attack"))
	{
		if (DuelSelectedUid == 0)
		{
			DuelShowMessage(TEXT("Select an attacking monster first."));
			return;
		}
		bOk = DuelEngine->Attack(DuelSelectedUid, Value, Error);
	}
	else if (Action == TEXT("battle"))
	{
		DuelEngine->EnterBattlePhase();
		return;
	}
	else if (Action == TEXT("endbattle"))
	{
		DuelEngine->EndBattlePhase();
		return;
	}
	else if (Action == TEXT("endturn"))
	{
		DuelEngine->EndTurn();
		if (DuelEngine->IsAwaitingDiscard())
		{
			DuelShowMessage(TEXT("Discard down to six cards before ending the turn."), FLinearColor(0.95f, 0.8f, 0.4f));
		}
		return;
	}

	if (!bOk)
	{
		if (!Error.IsEmpty())
		{
			DuelShowMessage(Error);
		}
		return;
	}
	DuelSelectedUid = 0;
}

// ---------------------------------------------------------------------------
// Duel presentation
// ---------------------------------------------------------------------------

void FDADuelUI::DrawDuel()
{
	if (!Canvas)
	{
		return;
	}

	DuelScale = FMath::Min(Canvas->ClipX / 1600.0f, Canvas->ClipY / 900.0f);
	DuelOffsetX = (Canvas->ClipX - 1600.0f * DuelScale) * 0.5f;
	DuelOffsetY = (Canvas->ClipY - 900.0f * DuelScale) * 0.5f;
	DuelHitTargets.Reset();

	DrawRect(FLinearColor(0.005f, 0.010f, 0.020f, 0.99f), 0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);
	// Subtle vertical bands keep the board readable without a flat backdrop.
	for (int32 I = 0; I < 5; ++I)
	{
		const float BandAlpha = 0.015f + I * 0.008f;
		DrawRect(FLinearColor(0.08f, 0.18f, 0.26f, BandAlpha), DX(350.0f + I * 200.0f), 0.0f,
			DS(200.0f), Canvas->ClipY);
	}

	if (DuelMode == EDuelUiMode::DeckSelect)
	{
		DrawDuelDeckSelect();
	}
	else if (DuelMode == EDuelUiMode::Duel)
	{
		DrawDuelActive();
	}
	else if (DuelMode == EDuelUiMode::Result)
	{
		DrawDuelResult();
	}

	if (DuelMode == EDuelUiMode::Duel)
	{
		if (DuelIntroTime < 2.2f)
		{
			const float Ease = 1.0f - FMath::Pow(1.0f - FMath::Clamp(DuelIntroTime / 0.65f, 0.0f, 1.0f), 3.0f);
			const float Fade = FMath::Clamp((2.2f - DuelIntroTime) / 0.55f, 0.0f, 1.0f);
			DrawDuelPortrait(DuelOpponentId, DX(-260.0f + 290.0f * Ease), DY(300.0f), DS(180.0f), DS(230.0f),
				Gold, Fade, true);
			DrawDuelPortrait(TEXT("player"), DX(1680.0f - 290.0f * Ease), DY(300.0f), DS(180.0f), DS(230.0f),
				AccentCyan, Fade, true);
			DrawShadowText(DuelOpponentName.ToUpper(), Gold, DX(800.0f), DY(548.0f), GetFont(false), 0.82f * DuelScale, true);
			DrawShadowText(TEXT("VS  YOU"), AccentCyan, DX(800.0f), DY(572.0f), GetFont(false), 0.62f * DuelScale, true);
		}
		DrawDuelFx();
		DrawDuelEventBanner();
		DrawDuelCutIn();
	}

	if (DuelMode == EDuelUiMode::Duel && DuelPileType != EDuelPileType::None)
	{
		DrawDuelPile();
	}

	if (DuelFlashTime > 0.0f)
	{
		const float FlashAlpha = DuelFlashColor.A * FMath::Clamp(DuelFlashTime / 0.30f, 0.0f, 1.0f);
		DrawRect(FLinearColor(DuelFlashColor.R, DuelFlashColor.G, DuelFlashColor.B, FlashAlpha),
			0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);
	}
}

void FDADuelUI::DrawDuelDeckSelect()
{
	UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	UCardArtSubsystem* Art = GetCardArt();

	DrawDuelPortrait(TEXT("player"), DX(70.0f), DY(26.0f), DS(72.0f), DS(72.0f), AccentCyan, 1.0f, true);
	DrawShadowText(TEXT("DUEL ACADEMY ISLAND"), Gold, DX(158.0f), DY(34.0f), GetFont(false), 0.82f * DuelScale, false);
	DrawShadowText(TEXT("CHOOSE YOUR STARTER DECK"), Paper, DX(158.0f), DY(60.0f), GetFont(true), 1.32f * DuelScale, false);
	DrawShadowText(FString::Printf(TEXT("%s is waiting for a duel. Choose one of three starter decks."), *DuelOpponentName),
		Muted, DX(158.0f), DY(104.0f), GetFont(false), 0.8f * DuelScale, false);

	DrawPanel(DX(1130.0f), DY(26.0f), DS(430.0f), DS(98.0f),
		FLinearColor(0.035f, 0.055f, 0.075f, 0.95f), Line);
	DrawDuelPortrait(DuelOpponentId, DX(1142.0f), DY(35.0f), DS(80.0f), DS(80.0f),
		FLinearColor(0.88f, 0.58f, 0.26f), 1.0f, true);
	DrawShadowText(DuelOpponentName.ToUpper(), Gold, DX(1238.0f), DY(38.0f), GetFont(false), 0.95f * DuelScale, false);
	DrawShadowText(FString::Printf(TEXT("%s DECK  /  8000 LP"), *DuelOpponentDeckId.ToUpper()), Paper, DX(1238.0f), DY(64.0f), GetFont(false), 0.68f * DuelScale, false);
	DrawShadowText(TEXT("Click a deck or press 1, 2, 3. Esc returns."), Muted, DX(1238.0f), DY(88.0f),
		GetFont(false), 0.58f * DuelScale, false);
	DrawDuelButton(TEXT("BACK"), TEXT("back"), 0, 70.0f, 120.0f, 120.0f, 34.0f,
		true, FLinearColor(0.42f, 0.68f, 0.86f));

	if (!Cards || !Cards->IsLoaded())
	{
		DrawShadowText(TEXT("Card database not loaded (Content/Data/cards.json is missing or invalid)."),
			FLinearColor(0.95f, 0.5f, 0.4f), DX(70.0f), DY(160.0f), GetFont(false), 0.9f * DuelScale, false);
		return;
	}

	const TArray<FStarterDeckDef>& Decks = Cards->GetDecks();
	for (int32 I = 0; I < 3 && I < Decks.Num(); ++I)
	{
		const FStarterDeckDef& Deck = Decks[I];
		const float PX = 70.0f + I * 500.0f;
		const float PY = 160.0f;
		const float PW = 460.0f;
		const float PH = 650.0f;
		const float AX = DX(PX);
		const float AY = DY(PY);
		const float AW = DS(PW);
		const float AH = DS(PH);
		const bool bHover = DuelMousePosition.X >= AX && DuelMousePosition.X <= AX + AW
			&& DuelMousePosition.Y >= AY && DuelMousePosition.Y <= AY + AH;

		FLinearColor Accent = FLinearColor::FromSRGBColor(FColor::FromHex(Deck.Accent.Replace(TEXT("#"), TEXT(""))));
		Accent.A = 1.0f;
		FLinearColor PanelFill = bHover ? FLinearColor(0.055f, 0.09f, 0.125f, 0.98f) : FLinearColor(0.028f, 0.05f, 0.072f, 0.96f);
		DrawPanel(AX, AY, AW, AH, PanelFill, bHover ? Accent : Line);
		if (bHover)
		{
			DrawRect(Accent, AX, AY, AW, 4.0f);
		}

		DrawShadowText(Deck.Name.ToUpper(), Accent, DX(PX + 22.0f), DY(PY + 20.0f), GetFont(true), 1.05f * DuelScale, false);
		DrawShadowText(Deck.Subtitle.ToUpper(), Muted, DX(PX + 22.0f), DY(PY + 52.0f), GetFont(false), 0.7f * DuelScale, false);
		DrawShadowText(FString::Printf(TEXT("%d MAIN  /  %d EXTRA"), Deck.Cards.Num(), Deck.Extra.Num()),
			Paper, DX(PX + 22.0f), DY(PY + 76.0f), GetFont(false), 0.62f * DuelScale, false);

		// A row of actual card scans makes the choice readable at a glance.
		TArray<const FCardRecord*> PreviewCards;
		TSet<int32> Shown;
		for (int32 CardId : Deck.Cards)
		{
			if (Shown.Contains(CardId)) continue;
			const FCardRecord* Record = Cards->FindCard(CardId);
			if (!Record || !Record->IsMonster()) continue;
			Shown.Add(CardId);
			PreviewCards.Add(Record);
		}
		PreviewCards.Sort([](const FCardRecord& A, const FCardRecord& B) { return A.Atk > B.Atk; });
		for (int32 ArtIndex = 0; ArtIndex < PreviewCards.Num() && ArtIndex < 4; ++ArtIndex)
		{
			FDuelCard Preview;
			Preview.Data = *PreviewCards[ArtIndex];
			DrawDuelCard(Preview, DX(PX + 20.0f + ArtIndex * 106.0f), DY(PY + 106.0f), DS(98.0f), DS(142.0f), false);
		}

		DrawWrappedText(Deck.Description, DX(PX + 22.0f), DY(PY + 258.0f), DS(PW - 44.0f),
			GetFont(false), 0.68f * DuelScale, Paper, 3.0f);

		DrawPanel(DX(PX + 20.0f), DY(PY + 382.0f), DS(PW - 40.0f), DS(1.0f), FLinearColor(0.0f, 0.0f, 0.0f, 0.0f), Line);
		DrawShadowText(TEXT("KEY CARDS"), Muted, DX(PX + 22.0f), DY(PY + 400.0f), GetFont(false), 0.62f * DuelScale, false);
		float NameY = PY + 426.0f;
		for (int32 NameIndex = 0; NameIndex < PreviewCards.Num() && NameIndex < 5; ++NameIndex)
		{
			const FCardRecord* Record = PreviewCards[NameIndex];
			FString CardLine = Record->Name;
			if (Record->IsMonster())
			{
				CardLine += FString::Printf(TEXT("   %d/%d"), Record->Atk, Record->Def);
			}
			DrawShadowText(DuelTrim(CardLine, 37), Record->IsMonster() ? Paper : AccentCyan,
				DX(PX + 22.0f), DY(NameY), GetFont(false), 0.63f * DuelScale, false);
			NameY += 23.0f;
		}

		const float ButtonY = PY + PH - 64.0f;
		const bool bHoverButton = DuelMousePosition.X >= DX(PX + 20.0f) && DuelMousePosition.X <= DX(PX + PW - 20.0f)
			&& DuelMousePosition.Y >= DY(ButtonY) && DuelMousePosition.Y <= DY(ButtonY + 44.0f);
		DrawPanel(DX(PX + 20.0f), DY(ButtonY), DS(PW - 40.0f), DS(44.0f),
			bHoverButton ? Accent * 0.9f : FLinearColor(0.03f, 0.06f, 0.09f, 0.98f), Accent);
		DrawShadowText(FString::Printf(TEXT("DUEL %s   [%d]"), *DuelOpponentName.ToUpper(), I + 1), Accent,
			DX(PX + PW * 0.5f), DY(ButtonY + 12.0f), GetFont(false), 0.88f * DuelScale, true);
		AddDuelHit(TEXT("deck"), I, DX(PX), DY(PY), DS(PW), DS(PH), Deck.Id);
	}

	if (Art)
	{
		DrawShadowText(TEXT("Card scans: YGOPRODeck  /  Fan project - not affiliated with Konami"),
			FLinearColor(0.35f, 0.45f, 0.52f, 1.0f), DX(70.0f), DY(842.0f), GetFont(false), 0.55f * DuelScale, false);
	}
}

void FDADuelUI::DrawDuelPortrait(const FString& CharacterId, float X, float Y, float W, float H,
	const FLinearColor& Accent, float Alpha, bool bFaceCrop, const FString& Expression)
{
	const float A = FMath::Clamp(Alpha, 0.0f, 1.0f);
	// The portraits are flattened onto this exact panel colour so their square
	// texture edges disappear into the frame after sRGB import.
	DrawPanel(X, Y, W, H, FLinearColor::FromSRGBColor(FColor(38, 53, 65)) * FLinearColor(1.0f, 1.0f, 1.0f, A),
		FLinearColor(Accent.R, Accent.G, Accent.B, 0.85f * A));
	UTexture2D* Portrait = nullptr;
	if (!Expression.IsEmpty() && !bFaceCrop && GetPortraitArt())
	{
		Portrait = GetPortraitArt()->GetExpression(CharacterId, Expression);
	}
	if (!Portrait && GetPortraitArt())
	{
		Portrait = GetPortraitArt()->GetPortrait(CharacterId, bFaceCrop);
	}
	if (Portrait)
	{
		DrawTexture(Portrait, X + 2.0f, Y + 2.0f, W - 4.0f, H - 4.0f, 0.0f, 0.0f, 1.0f, 1.0f,
			FLinearColor(1.0f, 1.0f, 1.0f, A));
	}
	else
	{
		DrawShadowText(CharacterId.Left(1).ToUpper(), Accent, X + W * 0.5f, Y + H * 0.5f - 14.0f,
			GetFont(true), 1.4f, true);
	}
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.9f * A), X, Y, W, 2.0f);
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.55f * A), X, Y + H - 2.0f, W, 2.0f);
}

void FDADuelUI::DrawDuelCardFace(int32 CardId, bool bFaceDown, float X, float Y, float W, float H, float Alpha)
{
	const float A = FMath::Clamp(Alpha, 0.0f, 1.0f);
	FLinearColor Border = FLinearColor(0.30f, 0.38f, 0.44f, 0.75f * A);
	FLinearColor Fill = FLinearColor(0.02f, 0.035f, 0.05f, A);
	UCardDatabaseSubsystem* Cards = GetGameInstance() ? GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const FCardRecord* Record = Cards ? Cards->FindCard(CardId) : nullptr;
	if (Record && !bFaceDown)
	{
		if (Record->IsSpell()) Border = FLinearColor(0.22f, 0.62f, 0.52f, 0.9f * A);
		else if (Record->IsTrap()) Border = FLinearColor(0.52f, 0.34f, 0.74f, 0.9f * A);
		else if (Record->CardType.Contains(TEXT("Fusion"))) Border = FLinearColor(0.84f, 0.62f, 0.26f, 0.95f * A);
	}
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.5f * A), X + 3.0f, Y + 4.0f, W, H);
	DrawRect(Border, X, Y, W, H);
	DrawRect(Fill, X + 1.0f, Y + 1.0f, W - 2.0f, H - 2.0f);
	UCardArtSubsystem* Art = GetCardArt();
	UTexture2D* Texture = bFaceDown ? (Art ? Art->GetCardBack() : nullptr) : (Art ? Art->GetCardArt(CardId) : nullptr);
	if (Texture)
	{
		DrawTexture(Texture, X + 1.5f, Y + 1.5f, W - 3.0f, H - 3.0f, 0.0f, 0.0f, 1.0f, 1.0f,
			FLinearColor(1.0f, 1.0f, 1.0f, A));
	}
	else if (Record && !bFaceDown)
	{
		DrawWrappedText(Record->Name, X + 4.0f, Y + 8.0f, W - 8.0f, GetFont(false),
			FMath::Max(0.36f, 0.44f * DuelScale), FLinearColor(Paper.R, Paper.G, Paper.B, A), 1.0f);
	}
}

void FDADuelUI::DrawDuelHudBar(const FDuelSide& Side, const FString& CharacterId, float X, float Y,
	const FLinearColor& Accent, bool bRight, float LpDisplay)
{
	const float W = 420.0f;
	const float H = 88.0f;
	DrawPanel(DX(X), DY(Y), DS(W), DS(H), FLinearColor(0.022f, 0.042f, 0.062f, 0.96f), Accent);
	DrawRect(Accent, DX(X), DY(Y), DS(W), 3.0f);
	const float PortraitX = bRight ? X + W - 78.0f : X + 12.0f;
	const float Pulse = Side.Owner == EDuelOwner::Player ? DuelPlayerPortraitPulse : DuelOpponentPortraitPulse;
	const float PortraitSize = 64.0f + Pulse * 6.0f;
	DrawDuelPortrait(CharacterId, DX(PortraitX - (PortraitSize - 64.0f) * 0.5f),
		DY(Y + 12.0f - (PortraitSize - 64.0f) * 0.5f), DS(PortraitSize), DS(PortraitSize), Accent, 1.0f, true);

	const float TextX = bRight ? X + 18.0f : X + 88.0f;
	DrawShadowText(Side.Name.ToUpper(), Accent, DX(TextX), DY(Y + 9.0f), GetFont(false), 0.86f * DuelScale, false);
	const bool bLow = LpDisplay <= 2000.0f;
	DrawShadowText(FString::Printf(TEXT("%d LP"), FMath::RoundToInt(LpDisplay)),
		bLow ? FLinearColor(0.98f, 0.38f, 0.32f) : Paper, DX(TextX), DY(Y + 31.0f),
		GetFont(true), 1.18f * DuelScale, false);
	DrawShadowText(FString::Printf(TEXT("HAND %d    DECK %d    GRAVE %d"),
		Side.Hand.Num(), Side.Deck.Num(), Side.Graveyard.Num()), Muted, DX(TextX), DY(Y + 70.0f),
		GetFont(false), 0.58f * DuelScale, false);

	const float BarX = bRight ? X + 156.0f : X + 150.0f;
	const float BarW = 150.0f;
	const float BarY = Y + 57.0f;
	DrawRect(FLinearColor(0.02f, 0.03f, 0.04f, 0.9f), DX(BarX), DY(BarY), DS(BarW), DS(7.0f));
	const float Ratio = FMath::Clamp(LpDisplay / 8000.0f, 0.0f, 1.0f);
	DrawRect(bLow ? FLinearColor(0.9f, 0.28f, 0.24f) : Accent, DX(BarX), DY(BarY), DS(BarW * Ratio), DS(7.0f));

	const float Hit = Side.Owner == EDuelOwner::Player ? DuelPlayerLpHit : DuelOpponentLpHit;
	if (Hit > 0.0f)
	{
		DrawRect(FLinearColor(1.0f, 0.15f, 0.08f, 0.18f * Hit), DX(X), DY(Y), DS(W), DS(H));
	}

	const float PulseGlow = Side.Owner == EDuelOwner::Player ? DuelPlayerPortraitPulse : DuelOpponentPortraitPulse;
	if (PulseGlow > 0.0f)
	{
		DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.12f * PulseGlow), DX(PortraitX) - 3.0f,
			DY(Y + 12.0f) - 3.0f, DS(70.0f), DS(70.0f));
	}
}

void FDADuelUI::DrawDuelFx()
{
	auto DrawFrame = [this](const FLinearColor& Color, float X, float Y, float W, float H, float Thickness)
	{
		DrawRect(Color, X, Y, W, Thickness);
		DrawRect(Color, X, Y + H - Thickness, W, Thickness);
		DrawRect(Color, X, Y, Thickness, H);
		DrawRect(Color, X + W - Thickness, Y, Thickness, H);
	};

	for (const FDuelFx& Fx : DuelFx)
	{
		const float Local = Fx.Elapsed - Fx.Delay;
		if (Local < 0.0f || Local > Fx.Duration + 0.001f)
		{
			continue;
		}
		const float T = FMath::Clamp(Local / Fx.Duration, 0.0f, 1.0f);
		const float Ease = 1.0f - FMath::Pow(1.0f - T, 3.0f);
		const float Alpha = Fx.Alpha();
		const FLinearColor SideColor = Fx.Side == EDuelOwner::Player
			? FLinearColor(0.38f, 0.70f, 0.92f) : FLinearColor(0.94f, 0.68f, 0.30f);

		if (Fx.Type == EDuelVisualEventType::Draw)
		{
			const float Arc = FMath::Sin(T * PI) * (Fx.Side == EDuelOwner::Player ? -42.0f : 42.0f);
			const float CX = FMath::Lerp(Fx.Source.X, Fx.Target.X, Ease);
			const float CY = FMath::Lerp(Fx.Source.Y, Fx.Target.Y, Ease) + Arc;
			const float W = FMath::Lerp(44.0f, 72.0f, Ease);
			const float H = W * 1.45f;
			for (int32 Ghost = 2; Ghost >= 1; --Ghost)
			{
				const float GhostEase = FMath::Clamp(Ease - Ghost * 0.07f, 0.0f, 1.0f);
				const float GX = FMath::Lerp(Fx.Source.X, Fx.Target.X, GhostEase);
				const float GY = FMath::Lerp(Fx.Source.Y, Fx.Target.Y, GhostEase) + Arc;
				DrawDuelCardFace(Fx.CardId, Fx.bFaceDown, DX(GX) - DS(W * 0.5f),
					DY(GY) - DS(H * 0.5f) - DS(Ghost * 5.0f), DS(W), DS(H),
					0.16f * (1.0f - T) / Ghost);
			}
			DrawDuelCardFace(Fx.CardId, Fx.bFaceDown, DX(CX) - DS(W) * 0.5f, DY(CY) - DS(H) * 0.5f,
				DS(W), DS(H), FMath::Clamp(T * 4.0f, 0.0f, 1.0f) * (1.0f - FMath::Pow(T, 8.0f)));
			DrawRect(FLinearColor(SideColor.R, SideColor.G, SideColor.B, 0.16f * (1.0f - T)),
				DX(CX) - DS(W) * 0.7f, DY(CY) - DS(H) * 0.7f, DS(W) * 1.4f, DS(H) * 1.4f);
			// A small glint at the card's destination.
			const float Glint = FMath::Clamp((T - 0.7f) / 0.3f, 0.0f, 1.0f);
			if (Glint > 0.0f)
			{
				DrawLine(DX(Fx.Target.X - 20.0f), DY(Fx.Target.Y), DX(Fx.Target.X + 20.0f),
					DY(Fx.Target.Y), FLinearColor(1.0f, 0.94f, 0.72f, 0.55f * (1.0f - Glint)), 2.0f);
				DrawLine(DX(Fx.Target.X), DY(Fx.Target.Y - 24.0f), DX(Fx.Target.X),
					DY(Fx.Target.Y + 24.0f), FLinearColor(1.0f, 0.94f, 0.72f, 0.55f * (1.0f - Glint)), 2.0f);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Summon || Fx.Type == EDuelVisualEventType::SetCard)
		{
			const bool bSummon = Fx.Type == EDuelVisualEventType::Summon;
			const FLinearColor RingColor = bSummon
				? FLinearColor(0.94f, 0.78f, 0.34f) : FLinearColor(0.38f, 0.62f, 0.88f);
			const float Ring = 1.0f + T * 1.5f;
			const float RingAlpha = (1.0f - T) * 0.5f;

			// A soft column of light sells the card arriving on the field.
			for (int32 I = 0; I < 4; ++I)
			{
				const float Spread = 42.0f + I * 18.0f;
				const float ColumnAlpha = (1.0f - T) * (0.10f - I * 0.018f);
				DrawRect(FLinearColor(RingColor.R, RingColor.G, RingColor.B, FMath::Max(0.0f, ColumnAlpha)),
					DX(Fx.Target.X - Spread), DY(Fx.Target.Y - 130.0f - I * 8.0f),
					DS(Spread * 2.0f), DS(210.0f + I * 12.0f));
			}

			DrawFrame(FLinearColor(RingColor.R, RingColor.G, RingColor.B, RingAlpha),
				DX(Fx.Target.X) - DS(58.0f * Ring), DY(Fx.Target.Y) - DS(78.0f * Ring),
				DS(116.0f * Ring), DS(156.0f * Ring), FMath::Max(1.0f, DS(2.0f)));

			// The card itself drops from the hand and settles into the zone.
			const float CardT = FMath::Clamp(T / 0.62f, 0.0f, 1.0f);
			if (CardT < 1.0f)
			{
				const float CardEase = FMath::InterpEaseOut(0.0f, 1.0f, CardT, 2.0f);
				const float CX = FMath::Lerp(Fx.Source.X, Fx.Target.X, CardEase);
				const float CY = FMath::Lerp(Fx.Source.Y, Fx.Target.Y, CardEase)
					+ FMath::Sin(CardT * PI) * -20.0f;
				const float CardW = FMath::Lerp(62.0f, 86.0f, CardEase);
				const float CardH = CardW * 1.45f;
				DrawDuelCardFace(Fx.CardId, Fx.bFaceDown || !bSummon, DX(CX) - DS(CardW) * 0.5f,
					DY(CY) - DS(CardH) * 0.5f, DS(CardW), DS(CardH),
					FMath::Clamp(CardT * 4.0f, 0.0f, 1.0f) * (1.0f - FMath::Pow(CardT, 5.0f)));
			}

			if (!Fx.Text.IsEmpty())
			{
				DrawShadowText(Fx.Text.ToUpper(), RingColor, DX(Fx.Target.X), DY(Fx.Target.Y - 108.0f),
					GetFont(false), 0.62f * DuelScale, true);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Spell || Fx.Type == EDuelVisualEventType::Trap)
		{
			const bool bSpell = Fx.Type == EDuelVisualEventType::Spell;
			const FLinearColor Color = bSpell
				? FLinearColor(0.26f, 0.86f, 0.64f) : FLinearColor(0.76f, 0.48f, 0.98f);
			const float Pulse = 1.0f + FMath::Sin(T * PI) * 0.7f;
			const float Aura = (1.0f - T);

			// Rotating rune ring at the card's destination.
			DrawFrame(FLinearColor(Color.R, Color.G, Color.B, 0.36f * Aura),
				DX(Fx.Target.X) - DS(58.0f * Pulse), DY(Fx.Target.Y) - DS(80.0f * Pulse),
				DS(116.0f * Pulse), DS(160.0f * Pulse), FMath::Max(1.0f, DS(2.0f)));
			for (int32 Rune = 0; Rune < 8; ++Rune)
			{
				const float Angle = Rune * PI * 0.25f + T * 1.6f;
				const float Inner = 68.0f;
				const float Outer = 84.0f;
				DrawLine(DX(Fx.Target.X + FMath::Cos(Angle) * Inner),
					DY(Fx.Target.Y + FMath::Sin(Angle) * Inner * 1.32f),
					DX(Fx.Target.X + FMath::Cos(Angle) * Outer),
					DY(Fx.Target.Y + FMath::Sin(Angle) * Outer * 1.32f),
					FLinearColor(Color.R, Color.G, Color.B, 0.42f * Aura), 2.0f);
			}

			// Casting flash at the hand.
			const float Cast = FMath::Clamp(T / 0.22f, 0.0f, 1.0f);
			DrawRect(FLinearColor(Color.R, Color.G, Color.B, 0.22f * (1.0f - Cast)),
				DX(Fx.Source.X) - DS(40.0f + Cast * 28.0f), DY(Fx.Source.Y) - DS(54.0f + Cast * 38.0f),
				DS(80.0f + Cast * 56.0f), DS(108.0f + Cast * 76.0f));

			DrawLine(DX(Fx.Source.X), DY(Fx.Source.Y), DX(Fx.Target.X), DY(Fx.Target.Y),
				FLinearColor(Color.R, Color.G, Color.B, 0.52f * Aura), 3.0f);
			const float CardT = FMath::Clamp(T / 0.55f, 0.0f, 1.0f);
			if (CardT < 1.0f)
			{
				const float CX = FMath::Lerp(Fx.Source.X, Fx.Target.X, FMath::InterpEaseOut(0.0f, 1.0f, CardT, 2.0f));
				const float CY = FMath::Lerp(Fx.Source.Y, Fx.Target.Y, FMath::InterpEaseOut(0.0f, 1.0f, CardT, 2.0f));
				const float Spin = FMath::Sin(CardT * PI) * 10.0f;
				DrawDuelCardFace(Fx.CardId, false, DX(CX) - DS(36.0f), DY(CY) - DS(52.0f) - DS(Spin),
					DS(72.0f), DS(104.0f), (1.0f - CardT * 0.5f));
			}
			DrawShadowText(Fx.Text.ToUpper(), Color, DX(Fx.Target.X), DY(Fx.Target.Y - 112.0f),
				GetFont(false), 0.62f * DuelScale, true);
		}
		else if (Fx.Type == EDuelVisualEventType::Attack)
		{
			const float Charge = FMath::Clamp(T / 0.24f, 0.0f, 1.0f);
			const float StrikeT = FMath::Clamp((T - 0.20f) / 0.40f, 0.0f, 1.0f);
			const float ReturnT = FMath::Clamp((T - 0.66f) / 0.34f, 0.0f, 1.0f);
			const float Travel = StrikeT < 1.0f
				? FMath::InterpEaseOut(0.0f, 1.0f, StrikeT, 2.0f)
				: 1.0f - FMath::InterpEaseIn(0.0f, 1.0f, ReturnT, 2.0f);
			const float Arc = FMath::Sin(T * PI) * -14.0f;
			const FVector2D CardPos = FVector2D(
				FMath::Lerp(Fx.Source.X, Fx.Target.X, Travel * 0.76f),
				FMath::Lerp(Fx.Source.Y, Fx.Target.Y, Travel * 0.76f) + Arc * Travel);
			const float CardW = 80.0f;
			const float CardH = 116.0f;

			// Anticipation: a tightening ring at the attacker's zone.
			if (T < 0.28f)
			{
				const float R = 44.0f + Charge * 26.0f;
				const float A = (1.0f - Charge) * 0.55f;
				DrawFrame(FLinearColor(1.0f, 0.82f, 0.38f, A), DX(Fx.Source.X) - DS(R),
					DY(Fx.Source.Y) - DS(R * 1.35f), DS(R * 2.0f), DS(R * 2.7f),
					FMath::Max(1.0f, DS(2.0f)));
			}

			// Motion ghosts behind the attacking card.
			for (int32 Ghost = 3; Ghost >= 1; --Ghost)
			{
				const float GhostTravel = FMath::Clamp(Travel - Ghost * 0.055f, 0.0f, 1.0f);
				const float GhostX = FMath::Lerp(Fx.Source.X, Fx.Target.X, GhostTravel * 0.76f);
				const float GhostY = FMath::Lerp(Fx.Source.Y, Fx.Target.Y, GhostTravel * 0.76f)
					+ Arc * GhostTravel;
				DrawDuelCardFace(Fx.CardId, false, DX(GhostX) - DS(CardW) * 0.5f,
					DY(GhostY) - DS(CardH) * 0.5f, DS(CardW), DS(CardH),
					0.10f * (1.0f - T) * (4 - Ghost) * 0.33f);
			}

			// Speed lines between the card and the target.
			const float SpeedAlpha = FMath::Sin(T * PI) * 0.75f;
			for (int32 LineOffset = -1; LineOffset <= 1; ++LineOffset)
			{
				const float Offset = LineOffset * 11.0f;
				DrawLine(DX(CardPos.X + Offset), DY(CardPos.Y + Offset * 0.35f),
					DX(Fx.Target.X + Offset * 0.6f), DY(Fx.Target.Y + Offset * 0.35f),
					FLinearColor(1.0f, 0.82f, 0.40f, 0.55f * SpeedAlpha), 2.0f);
			}

			DrawDuelCardFace(Fx.CardId, false, DX(CardPos.X) - DS(CardW) * 0.5f,
				DY(CardPos.Y) - DS(CardH) * 0.5f, DS(CardW), DS(CardH),
				FMath::Clamp(0.35f + Travel * 0.9f, 0.0f, 1.0f));

			// Impact starburst and a short white flash at contact.
			const float Impact = FMath::Clamp((T - 0.55f) / 0.18f, 0.0f, 1.0f);
			if (Impact > 0.0f)
			{
				const float R = 24.0f + Impact * 46.0f;
				const float A = 1.0f - Impact;
				DrawFrame(FLinearColor(1.0f, 0.88f, 0.55f, 0.55f * A),
					DX(Fx.Target.X) - DS(R), DY(Fx.Target.Y) - DS(R), DS(R * 2.0f), DS(R * 2.0f),
					FMath::Max(1.0f, DS(2.0f)));
				for (int32 Ray = 0; Ray < 8; ++Ray)
				{
					const float Angle = Ray * PI * 0.25f + 0.2f;
					DrawLine(DX(Fx.Target.X + FMath::Cos(Angle) * R * 0.45f),
						DY(Fx.Target.Y + FMath::Sin(Angle) * R * 0.45f),
						DX(Fx.Target.X + FMath::Cos(Angle) * R * 1.35f),
						DY(Fx.Target.Y + FMath::Sin(Angle) * R * 1.35f),
						FLinearColor(1.0f, 0.76f, 0.34f, 0.55f * A), 2.0f);
				}
				DrawRect(FLinearColor(1.0f, 0.96f, 0.86f, 0.22f * A), DX(Fx.Target.X) - DS(R * 0.7f),
					DY(Fx.Target.Y) - DS(R * 0.7f), DS(R * 1.4f), DS(R * 1.4f));
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Damage || Fx.Type == EDuelVisualEventType::Heal)
		{
			const bool bDamage = Fx.Type == EDuelVisualEventType::Damage;
			const FLinearColor Color = bDamage ? FLinearColor(1.0f, 0.40f, 0.32f) : FLinearColor(0.50f, 0.94f, 0.60f);
			const float Rise = T * 58.0f;
			const FString Number = FString::Printf(TEXT("%s%d"), bDamage ? TEXT("-") : TEXT("+"), Fx.Amount);
			const float Pop = 1.0f + (1.0f - T) * 0.55f;

			// Impact/support burst behind the floating number.
			const float Burst = FMath::Clamp(T / 0.4f, 0.0f, 1.0f);
			const float Radius = 28.0f + Burst * 58.0f;
			DrawFrame(FLinearColor(Color.R, Color.G, Color.B, 0.34f * (1.0f - Burst)),
				DX(Fx.Source.X) - DS(Radius), DY(Fx.Source.Y) - DS(Radius),
				DS(Radius * 2.0f), DS(Radius * 2.0f), FMath::Max(1.0f, DS(2.0f)));
			for (int32 Ray = 0; Ray < 8; ++Ray)
			{
				const float Angle = Ray * PI * 0.25f + (bDamage ? 0.15f : 0.35f);
				DrawLine(DX(Fx.Source.X + FMath::Cos(Angle) * Radius * 0.55f),
					DY(Fx.Source.Y + FMath::Sin(Angle) * Radius * 0.55f),
					DX(Fx.Source.X + FMath::Cos(Angle) * Radius * 1.2f),
					DY(Fx.Source.Y + FMath::Sin(Angle) * Radius * 1.2f),
					FLinearColor(Color.R, Color.G, Color.B, 0.42f * (1.0f - Burst)), 2.0f);
			}

			if (bDamage)
			{
				DrawRect(FLinearColor(1.0f, 0.20f, 0.14f, 0.10f * (1.0f - T)), 0.0f, 0.0f,
					Canvas->ClipX, Canvas->ClipY);
			}
			else
			{
				for (int32 Spark = 0; Spark < 6; ++Spark)
				{
					const float Angle = Spark * PI / 3.0f + Fx.Elapsed * 1.2f;
					const float SparkR = 26.0f + Spark * 13.0f;
					const float SparkY = FMath::Sin(T * PI + Spark) * 10.0f - T * 40.0f;
					DrawRect(FLinearColor(0.55f, 1.0f, 0.62f, 0.6f * (1.0f - T)),
						DX(Fx.Source.X + FMath::Cos(Angle) * SparkR),
						DY(Fx.Source.Y + SparkY + FMath::Sin(Angle) * 10.0f),
						DS(5.0f), DS(9.0f));
				}
			}

			DrawShadowText(Number, Color, DX(Fx.Source.X), DY(Fx.Source.Y + 18.0f - Rise),
				GetFont(true), (1.2f * Pop) * DuelScale, true);
			if (bDamage && Fx.Amount >= 2000)
			{
				DrawShadowText(TEXT("CRITICAL"), FLinearColor(1.0f, 0.78f, 0.38f), DX(Fx.Source.X),
					DY(Fx.Source.Y - 14.0f - Rise * 0.35f), GetFont(false), 0.62f * DuelScale, true);
			}
			if (!Fx.Text.IsEmpty())
			{
				DrawShadowText(Fx.Text, Color, DX(Fx.Source.X), DY(Fx.Source.Y + 42.0f - Rise * 0.65f),
					GetFont(false), 0.5f * DuelScale, true);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Destroy)
		{
			const float GhostAlpha = (1.0f - T) * 0.9f;
			const float W = FMath::Lerp(88.0f, 22.0f, Ease);
			const float H = W * 1.45f;
			DrawDuelCardFace(Fx.CardId, false, DX(Fx.Source.X) - DS(W) * 0.5f,
				DY(Fx.Source.Y) - DS(H) * 0.5f, DS(W), DS(H), GhostAlpha);

			// Implosion ring, then card shards flying outward.
			const float Ring = 34.0f + T * 74.0f;
			DrawFrame(FLinearColor(1.0f, 0.72f, 0.32f, 0.45f * (1.0f - T)),
				DX(Fx.Source.X) - DS(Ring), DY(Fx.Source.Y) - DS(Ring * 1.35f),
				DS(Ring * 2.0f), DS(Ring * 2.7f), FMath::Max(1.0f, DS(2.0f)));
			for (int32 Shard = 0; Shard < 10; ++Shard)
			{
				const float Angle = Shard * PI * 0.2f + 0.3f;
				const float Distance = 16.0f + T * (48.0f + (Shard % 3) * 18.0f);
				const float SX = Fx.Source.X + FMath::Cos(Angle) * Distance;
				const float SY = Fx.Source.Y + FMath::Sin(Angle) * Distance * 1.25f - T * 16.0f;
				const float Size = 7.0f - T * 4.0f;
				DrawRect(FLinearColor(1.0f, 0.78f, 0.42f, 0.55f * (1.0f - T)),
					DX(SX), DY(SY), DS(Size), DS(Size * 1.8f));
			}
			for (int32 Slash = 0; Slash < 4; ++Slash)
			{
				const float Offset = (Slash - 1.5f) * 22.0f;
				DrawLine(DX(Fx.Source.X - 42.0f + Offset), DY(Fx.Source.Y - 60.0f),
					DX(Fx.Source.X + 42.0f + Offset), DY(Fx.Source.Y + 60.0f),
					FLinearColor(1.0f, 0.80f, 0.44f, 0.55f * (1.0f - T)), 2.0f);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Discard ||
			Fx.Type == EDuelVisualEventType::Banish ||
			Fx.Type == EDuelVisualEventType::Search ||
			Fx.Type == EDuelVisualEventType::Mill ||
			Fx.Type == EDuelVisualEventType::Return)
		{
			FLinearColor Color = SideColor;
			if (Fx.Type == EDuelVisualEventType::Discard) Color = FLinearColor(0.88f, 0.48f, 0.38f);
			else if (Fx.Type == EDuelVisualEventType::Banish) Color = FLinearColor(0.72f, 0.46f, 0.96f);
			else if (Fx.Type == EDuelVisualEventType::Search) Color = FLinearColor(0.42f, 0.88f, 0.78f);
			else if (Fx.Type == EDuelVisualEventType::Mill) Color = FLinearColor(0.62f, 0.58f, 0.48f);
			else if (Fx.Type == EDuelVisualEventType::Return) Color = FLinearColor(0.46f, 0.82f, 0.52f);

			const float Arc = FMath::Sin(T * PI) * (Fx.Type == EDuelVisualEventType::Search ? -26.0f : 26.0f);
			const float CX = FMath::Lerp(Fx.Source.X, Fx.Target.X, Ease);
			const float CY = FMath::Lerp(Fx.Source.Y, Fx.Target.Y, Ease) + Arc;
			const float W = FMath::Lerp(52.0f, 40.0f, Ease);
			const float H = W * 1.45f;
			DrawDuelCardFace(Fx.CardId, Fx.bFaceDown, DX(CX) - DS(W) * 0.5f, DY(CY) - DS(H) * 0.5f,
				DS(W), DS(H), FMath::Clamp(T * 5.0f, 0.0f, 1.0f) * (1.0f - FMath::Pow(T, 6.0f)));
			DrawRect(FLinearColor(Color.R, Color.G, Color.B, 0.14f * (1.0f - T)),
				DX(CX) - DS(W) * 0.75f, DY(CY) - DS(H) * 0.75f, DS(W) * 1.5f, DS(H) * 1.5f);
			if (!Fx.Text.IsEmpty())
			{
				DrawShadowText(Fx.Text.ToUpper(), Color, DX(CX), DY(CY - 78.0f),
					GetFont(false), 0.52f * DuelScale, true);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Position)
		{
			const float Ring = 1.0f + T * 1.2f;
			const float RingAlpha = (1.0f - T) * 0.7f;
			const FLinearColor Color(0.54f, 0.78f, 0.98f, RingAlpha);
			DrawFrame(Color, DX(Fx.Target.X) - DS(50.0f * Ring), DY(Fx.Target.Y) - DS(68.0f * Ring),
				DS(100.0f * Ring), DS(136.0f * Ring), FMath::Max(1.0f, DS(2.0f)));
			DrawRect(FLinearColor(0.08f, 0.16f, 0.24f, 0.06f * (1.0f - T)),
				DX(Fx.Target.X) - DS(45.0f * Ring), DY(Fx.Target.Y) - DS(63.0f * Ring),
				DS(90.0f * Ring), DS(126.0f * Ring));
			if (!Fx.Text.IsEmpty())
			{
				DrawShadowText(Fx.Text.ToUpper(), Color, DX(Fx.Target.X), DY(Fx.Target.Y - 84.0f),
					GetFont(false), 0.55f * DuelScale, true);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Fusion || Fx.Type == EDuelVisualEventType::Ritual)
		{
			const bool bFusion = Fx.Type == EDuelVisualEventType::Fusion;
			const FLinearColor Color = bFusion ? FLinearColor(0.94f, 0.72f, 0.28f) : FLinearColor(0.94f, 0.48f, 0.28f);
			DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.30f * (1.0f - T)), 0.0f, 0.0f,
				Canvas->ClipX, Canvas->ClipY);
			const float Inflate = FMath::Clamp(T / 0.28f, 0.0f, 1.0f);
			const float CardW = FMath::Lerp(40.0f, 132.0f, FMath::InterpEaseOut(0.0f, 1.0f, Inflate, 2.0f));
			const float CardH = CardW * 1.45f;
			const float Spin = T * 260.0f;
			for (int32 I = 0; I < 2; ++I)
			{
				const float R = 80.0f + I * 28.0f + FMath::Sin(T * PI * 2.0f + I) * 8.0f;
				DrawFrame(FLinearColor(Color.R, Color.G, Color.B, 0.22f * (1.0f - T)),
					DX(Fx.Target.X) - DS(R), DY(Fx.Target.Y) - DS(R), DS(R * 2.0f), DS(R * 2.0f),
					FMath::Max(1.0f, DS(2.0f)));
			}
			DrawRect(FLinearColor(Color.R, Color.G, Color.B, 0.06f * (1.0f - T)),
				DX(Fx.Target.X) - DS(86.0f), DY(Fx.Target.Y) - DS(86.0f), DS(172.0f), DS(172.0f));
			DrawDuelCardFace(Fx.CardId, false, DX(Fx.Target.X) - DS(CardW) * 0.5f,
				DY(Fx.Target.Y) - DS(CardH) * 0.5f, DS(CardW), DS(CardH), Inflate);
			const float RayLength = 170.0f + 12.0f * FMath::Sin(Spin);
			for (int32 Ray = 0; Ray < 12; ++Ray)
			{
				const float Angle = Spin * PI / 180.0f + Ray * PI / 6.0f;
				const float Inner = 92.0f;
				DrawLine(DX(Fx.Target.X + FMath::Cos(Angle) * Inner),
					DY(Fx.Target.Y + FMath::Sin(Angle) * Inner),
					DX(Fx.Target.X + FMath::Cos(Angle) * RayLength),
					DY(Fx.Target.Y + FMath::Sin(Angle) * RayLength),
					FLinearColor(Color.R, Color.G, Color.B, 0.26f * (1.0f - T)), 2.0f);
			}
			const float Seal = 118.0f;
			for (int32 Tick = 0; Tick < 16; ++Tick)
			{
				const float Angle = -Spin * PI / 220.0f + Tick * PI / 8.0f;
				DrawLine(DX(Fx.Target.X + FMath::Cos(Angle) * Seal),
					DY(Fx.Target.Y + FMath::Sin(Angle) * Seal * 1.16f),
					DX(Fx.Target.X + FMath::Cos(Angle) * (Seal + 14.0f)),
					DY(Fx.Target.Y + FMath::Sin(Angle) * (Seal + 14.0f) * 1.16f),
					FLinearColor(Color.R, Color.G, Color.B, 0.36f * (1.0f - T)), 2.0f);
			}
			if (!Fx.Text.IsEmpty())
			{
				DrawShadowText(Fx.Text.ToUpper(), Paper, DX(Fx.Target.X), DY(Fx.Target.Y + 118.0f),
					GetFont(false), 0.52f * DuelScale, true);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Cost)
		{
			const FLinearColor Color(0.98f, 0.78f, 0.34f, Alpha);
			const float Rise = T * 48.0f;
			DrawShadowText(FString::Printf(TEXT("-%d LP"), Fx.Amount), Color,
				DX(Fx.Source.X), DY(Fx.Source.Y + 12.0f - Rise), GetFont(false),
				(0.88f + (1.0f - T) * 0.25f) * DuelScale, true);
			if (!Fx.Text.IsEmpty())
			{
				DrawShadowText(Fx.Text.ToUpper(), Color, DX(Fx.Source.X), DY(Fx.Source.Y + 36.0f - Rise * 0.6f),
					GetFont(false), 0.44f * DuelScale, true);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Counter)
		{
			const float Ring = 1.0f + T * 0.9f;
			const FLinearColor Color(0.98f, 0.80f, 0.30f, (1.0f - T) * 0.85f);
			DrawFrame(Color, DX(Fx.Target.X) - DS(42.0f * Ring), DY(Fx.Target.Y) - DS(58.0f * Ring),
				DS(84.0f * Ring), DS(116.0f * Ring), FMath::Max(1.0f, DS(2.0f)));
			for (int32 I = 0; I < 6; ++I)
			{
				const float Angle = I * PI / 3.0f + T * 2.0f;
				DrawRect(Color, DX(Fx.Target.X + FMath::Cos(Angle) * 54.0f * Ring),
					DY(Fx.Target.Y + FMath::Sin(Angle) * 70.0f * Ring), DS(5.0f), DS(5.0f));
			}
			DrawShadowText(FString::Printf(TEXT("%s +1"), *Fx.Text.ToUpper()), Color,
				DX(Fx.Target.X), DY(Fx.Target.Y - 88.0f), GetFont(false), 0.52f * DuelScale, true);
			if (Fx.Amount > 1)
			{
				DrawShadowText(FString::Printf(TEXT("x%d"), Fx.Amount), Color,
					DX(Fx.Target.X), DY(Fx.Target.Y - 66.0f), GetFont(false), 0.46f * DuelScale, true);
			}
		}
		else if (Fx.Type == EDuelVisualEventType::Effect && !Fx.Text.IsEmpty())
		{
			DrawShadowText(Fx.Text.ToUpper(), FLinearColor(0.80f, 0.90f, 1.0f, Alpha),
				DX(Fx.Target.X), DY(Fx.Target.Y - 20.0f * T), GetFont(false), 0.58f * DuelScale, true);
		}
	}
}

void FDADuelUI::DrawDuelEventBanner()
{
	if (DuelEventBannerTime <= 0.0f || DuelEventBannerTitle.IsEmpty())
	{
		return;
	}
	const float T = 1.0f - DuelEventBannerTime / FMath::Max(0.01f, DuelEventBannerDuration);
	const float Ease = 1.0f - FMath::Pow(1.0f - FMath::Clamp(T / 0.18f, 0.0f, 1.0f), 3.0f);
	const float Fade = FMath::Min(
		FMath::Clamp(T / 0.12f, 0.0f, 1.0f),
		FMath::Clamp(DuelEventBannerTime / 0.26f, 0.0f, 1.0f));
	const float Slide = (1.0f - Ease) * 30.0f;
	const float X = 520.0f;
	const float Y = 388.0f + Slide;
	const float W = 560.0f;
	const float H = 72.0f;
	const FLinearColor Accent = FLinearColor(DuelEventBannerColor.R, DuelEventBannerColor.G,
		DuelEventBannerColor.B, Fade);
	DrawPanel(DX(X), DY(Y), DS(W), DS(H), FLinearColor(0.012f, 0.026f, 0.040f, 0.94f * Fade), Accent);
	DrawRect(Accent, DX(X), DY(Y), DS(W), 3.0f);
	DrawRect(Accent, DX(X), DY(Y + H - 2.0f), DS(W), 2.0f);
	DrawShadowText(DuelEventBannerTitle, FLinearColor(Paper.R, Paper.G, Paper.B, Fade),
		DX(X + W * 0.5f), DY(Y + 12.0f), GetFont(true), 1.08f * DuelScale, true);
	DrawShadowText(DuelEventBannerSubtitle, Accent, DX(X + W * 0.5f), DY(Y + 42.0f),
		GetFont(false), 0.59f * DuelScale, true);
}

void FDADuelUI::TriggerDuelCutIn(EDuelOwner Side, const FString& Expression, const FString& Title,
	const FString& Subtitle, int32 Priority, float Duration)
{
	if (DuelMode != EDuelUiMode::Duel || Expression.IsEmpty())
	{
		return;
	}

	if (DuelCutInTime > 0.0f)
	{
		const bool bOtherSide = Side != DuelCutInSide;
		const bool bFresh = DuelCutInAge < 0.38f;
		const bool bHigher = Priority > DuelCutInPriority;
		const bool bCounterBeat = bOtherSide && Priority >= 50 && DuelCutInAge > 0.32f;
		const bool bSameBeat = Priority == DuelCutInPriority && DuelCutInAge > 0.45f;
		if (!bHigher && !bCounterBeat && !bSameBeat && !bFresh)
		{
			return;
		}
		if (!bHigher && !bCounterBeat && !bSameBeat && bFresh)
		{
			return;
		}
	}

	DuelCutInSide = Side;
	DuelCutInCharacter = Side == EDuelOwner::Player ? TEXT("player") : DuelOpponentId;
	DuelCutInExpression = Expression;
	DuelCutInTitle = Title;
	DuelCutInSubtitle = Subtitle;
	DuelCutInAccent = Side == EDuelOwner::Player
		? FLinearColor(0.38f, 0.72f, 0.96f)
		: FLinearColor(0.94f, 0.66f, 0.28f);
	DuelCutInTime = Duration;
	DuelCutInDuration = FMath::Max(0.5f, Duration);
	DuelCutInAge = 0.0f;
	DuelCutInPriority = Priority;
}

void FDADuelUI::DrawDuelCutIn()
{
	if (DuelCutInTime <= 0.0f || DuelCutInCharacter.IsEmpty())
	{
		return;
	}

	const float T = 1.0f - DuelCutInTime / FMath::Max(0.01f, DuelCutInDuration);
	const float In = FMath::Clamp(T / 0.2f, 0.0f, 1.0f);
	const float Out = FMath::Clamp(DuelCutInTime / 0.28f, 0.0f, 1.0f);
	const float A = FMath::Min(In, Out);
	const float Ease = 1.0f - FMath::Pow(1.0f - In, 3.0f);
	const float Slide = (1.0f - Ease) * 460.0f;
	const float W = 400.0f;
	const float H = 400.0f;
	const float TopH = 86.0f;
	const float BaseX = DuelCutInSide == EDuelOwner::Player ? 16.0f : 1184.0f;
	const float X = DuelCutInSide == EDuelOwner::Player ? BaseX - Slide : BaseX + Slide;
	const float Y = 258.0f + (1.0f - Ease) * 26.0f;
	const FLinearColor Accent = FLinearColor(DuelCutInAccent.R, DuelCutInAccent.G,
		DuelCutInAccent.B, A);
	const FLinearColor PaperA(Paper.R, Paper.G, Paper.B, A);
	const FLinearColor MutedA(Muted.R, Muted.G, Muted.B, A);
	const FLinearColor Dark(0.008f, 0.016f, 0.026f, 0.94f * A);
	const FLinearColor PanelBg = FLinearColor::FromSRGBColor(FColor(38, 53, 65));

	// Speed lines and a dark wedge make the cut-in feel like a camera insert,
	// not another static panel.
	for (int32 I = 0; I < 6; ++I)
	{
		const float LineY = Y - 12.0f + I * 94.0f;
		const float Width = W + 24.0f + FMath::Sin(DuelCutInAge * 8.0f + I) * 22.0f;
		DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, (0.08f + I * 0.014f) * (1.0f - Ease * 0.55f) * A),
			DX(X - 18.0f - (1.0f - Ease) * 80.0f), DY(LineY), DS(Width), DS(2.0f));
	}

	DrawPanel(DX(X - 10.0f), DY(Y - 10.0f), DS(W + 20.0f), DS(TopH + H + 20.0f), Dark, Accent);
	DrawRect(Accent, DX(X - 10.0f), DY(Y - 10.0f), DS(W + 20.0f), DS(4.0f));
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.55f * A),
		DX(X - 10.0f), DY(Y + TopH + H + 6.0f), DS(W + 20.0f), DS(2.0f));

	// Corner brackets.
	const float Bracket = 22.0f;
	const float Thick = 3.0f;
	DrawRect(Accent, DX(X - 4.0f), DY(Y - 4.0f), DS(Bracket), DS(Thick));
	DrawRect(Accent, DX(X - 4.0f), DY(Y - 4.0f), DS(Thick), DS(Bracket));
	DrawRect(Accent, DX(X + W + 4.0f - Bracket), DY(Y - 4.0f), DS(Bracket), DS(Thick));
	DrawRect(Accent, DX(X + W + 4.0f - Thick), DY(Y - 4.0f), DS(Thick), DS(Bracket));
	DrawRect(Accent, DX(X - 4.0f), DY(Y + TopH + H + 4.0f - Thick), DS(Bracket), DS(Thick));
	DrawRect(Accent, DX(X - 4.0f), DY(Y + TopH + H + 4.0f - Bracket), DS(Thick), DS(Bracket));
	DrawRect(Accent, DX(X + W + 4.0f - Bracket), DY(Y + TopH + H + 4.0f - Thick), DS(Bracket), DS(Thick));
	DrawRect(Accent, DX(X + W + 4.0f - Thick), DY(Y + TopH + H + 4.0f - Bracket), DS(Thick), DS(Bracket));

	// Header: name, event, detail.
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.10f * A),
		DX(X + 6.0f), DY(Y + 6.0f), DS(W - 12.0f), DS(TopH - 12.0f));
	DrawShadowText(DuelCutInCharacter == TEXT("player") ? TEXT("YOU") : DuelOpponentName.ToUpper(), Accent,
		DX(X + 20.0f), DY(Y + 8.0f), GetFont(true), 1.25f * DuelScale, false);
	DrawShadowText(DuelCutInTitle.ToUpper(), PaperA, DX(X + 20.0f), DY(Y + 42.0f),
		GetFont(false), 0.82f * DuelScale, false);
	if (!DuelCutInSubtitle.IsEmpty())
	{
		DrawShadowText(DuelTrim(DuelCutInSubtitle.ToUpper(), 42), MutedA, DX(X + 20.0f),
			DY(Y + 64.0f), GetFont(false), 0.58f * DuelScale, false);
	}

	// Portrait.
	DrawRect(PanelBg, DX(X + 4.0f), DY(Y + TopH + 4.0f), DS(W - 8.0f), DS(H - 8.0f));
	UTexture2D* Portrait = GetPortraitArt()
		? GetPortraitArt()->GetExpression(DuelCutInCharacter, DuelCutInExpression) : nullptr;
	if (Portrait)
	{
		DrawTexture(Portrait, DX(X + 6.0f), DY(Y + TopH + 6.0f), DS(W - 12.0f), DS(H - 12.0f),
			0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(1.0f, 1.0f, 1.0f, A));
	}
	else
	{
		DrawShadowText(DuelCutInExpression.Left(1).ToUpper(), Accent,
			DX(X + W * 0.5f), DY(Y + TopH + H * 0.4f), GetFont(true), 2.2f * DuelScale, true);
	}

	// Expression line across the lower chest.
	const float QuoteH = 68.0f;
	DrawRect(FLinearColor(0.006f, 0.012f, 0.020f, 0.78f * A), DX(X + 6.0f),
		DY(Y + TopH + H - QuoteH - 6.0f), DS(W - 12.0f), DS(QuoteH));
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.85f * A), DX(X + 6.0f),
		DY(Y + TopH + H - QuoteH - 6.0f), DS(W - 12.0f), DS(2.0f));
	DrawWrappedText(CutInQuote(DuelCutInCharacter, DuelCutInExpression), DX(X + 24.0f),
		DY(Y + TopH + H - QuoteH + 20.0f), DS(W - 48.0f), GetFont(false), 0.84f * DuelScale, PaperA, 2.0f);

	// A hot rim is reserved for the low-LP warning; high-priority story beats
	// keep the character accent so Fusion/Ritual/Win do not look like danger.
	if (DuelCutInTitle == TEXT("LOW LIFE POINTS"))
	{
		const float Glow = 0.25f + 0.25f * FMath::Sin(DuelCutInAge * 14.0f);
		DrawRect(FLinearColor(1.0f, 0.22f, 0.16f, Glow * A), DX(X + 4.0f), DY(Y + TopH + 4.0f),
			DS(W - 8.0f), DS(3.0f));
		DrawRect(FLinearColor(1.0f, 0.22f, 0.16f, Glow * A), DX(X + 4.0f), DY(Y + TopH + H - 7.0f),
			DS(W - 8.0f), DS(3.0f));
	}
	else if (DuelCutInPriority >= 100)
	{
		const float Glow = 0.30f + 0.18f * FMath::Sin(DuelCutInAge * 9.0f);
		DrawRect(FLinearColor(0.98f, 0.78f, 0.30f, Glow * A), DX(X + 4.0f), DY(Y + TopH + 4.0f),
			DS(W - 8.0f), DS(3.0f));
		DrawRect(FLinearColor(0.98f, 0.78f, 0.30f, Glow * A), DX(X + 4.0f), DY(Y + TopH + H - 7.0f),
			DS(W - 8.0f), DS(3.0f));
	}
}

void FDADuelUI::DrawDuelActive()
{
	if (!DuelEngine)
	{
		return;
	}

	const FDuelSide& PlayerSide = DuelEngine->GetSide(EDuelOwner::Player);
	const FDuelSide& OpponentSide = DuelEngine->GetSide(EDuelOwner::Opponent);
	const bool bPlayerTurn = DuelEngine->IsPlayerTurn();
	const bool bAiTurn = DuelEngine->IsAwaitingAi() || !bPlayerTurn;
	const bool bMain = DuelEngine->GetPhase() == EDuelPhase::Main1 || DuelEngine->GetPhase() == EDuelPhase::Main2;
	FDuelCard* Selected = DuelEngine->FindCard(DuelSelectedUid);

	// Top scoreboards.
	const FLinearColor JadenAccent(0.88f, 0.58f, 0.26f);
	const FLinearColor PlayerAccent(0.38f, 0.70f, 0.92f);
	DrawDuelHudBar(OpponentSide, DuelOpponentId, 24.0f, 14.0f, JadenAccent, false, DuelOpponentLpDisplay);
	DrawDuelHudBar(PlayerSide, TEXT("player"), 1156.0f, 14.0f, PlayerAccent, true, DuelPlayerLpDisplay);

	// Central playmat.  It gives the board a clear silhouette and separates
	// the field from the very dark page background.
	DrawPanel(DX(414.0f), DY(168.0f), DS(760.0f), DS(598.0f),
		FLinearColor(0.010f, 0.020f, 0.034f, 0.94f), FLinearColor(0.16f, 0.28f, 0.36f, 0.75f));
	DrawRect(FLinearColor(0.22f, 0.42f, 0.52f, 0.55f), DX(414.0f), DY(168.0f), DS(760.0f), DS(2.0f));
	DrawRect(FLinearColor(0.22f, 0.42f, 0.52f, 0.35f), DX(414.0f), DY(764.0f), DS(760.0f), DS(1.0f));
	DrawRect(FLinearColor(0.22f, 0.42f, 0.52f, 0.22f), DX(414.0f), DY(168.0f), DS(2.0f), DS(596.0f));
	DrawRect(FLinearColor(0.22f, 0.42f, 0.52f, 0.22f), DX(1172.0f), DY(168.0f), DS(2.0f), DS(596.0f));
	// Lane separators behind the cards.
	for (float LaneY : { 312.0f, 448.0f, 494.0f, 622.0f, 758.0f })
	{
		DrawRect(FLinearColor(0.30f, 0.44f, 0.52f, 0.12f), DX(430.0f), DY(LaneY), DS(730.0f), DS(1.0f));
	}

	// Left duel log.
	DrawPanel(DX(24.0f), DY(110.0f), DS(340.0f), DS(760.0f), FLinearColor(0.018f, 0.032f, 0.05f, 0.94f), Line);
	DrawShadowText(TEXT("DUEL LOG"), Gold, DX(42.0f), DY(126.0f), GetFont(false), 0.78f * DuelScale, false);
	DrawRect(Line, DX(42.0f), DY(150.0f), DS(304.0f), 1.0f);
	const TArray<FDuelLogEntry>& Entries = DuelEngine->GetLog();
	const int32 FirstEntry = FMath::Max(0, Entries.Num() - 17);
	float LogY = 162.0f;
	for (int32 I = Entries.Num() - 1; I >= FirstEntry; --I)
	{
		const FDuelLogEntry& Entry = Entries[I];
		FLinearColor LogColor = Paper;
		if (Entry.Tone == TEXT("turn")) LogColor = Gold;
		else if (Entry.Tone == TEXT("phase")) LogColor = Muted;
		else if (Entry.Tone == TEXT("battle")) LogColor = FLinearColor(0.96f, 0.58f, 0.36f);
		else if (Entry.Tone == TEXT("damage") || Entry.Tone == TEXT("destroy")) LogColor = FLinearColor(0.95f, 0.42f, 0.38f);
		else if (Entry.Tone == TEXT("heal")) LogColor = FLinearColor(0.55f, 0.9f, 0.62f);
		else if (Entry.Tone == TEXT("spell")) LogColor = AccentCyan;
		else if (Entry.Tone == TEXT("trap")) LogColor = FLinearColor(0.80f, 0.62f, 0.96f);
		else if (Entry.Tone == TEXT("summon")) LogColor = FLinearColor(0.62f, 0.9f, 0.66f);
		else if (Entry.Tone == TEXT("effect")) LogColor = FLinearColor(0.72f, 0.82f, 0.96f);
		else if (Entry.Tone == TEXT("draw")) LogColor = FLinearColor(0.82f, 0.82f, 0.74f);
		DrawShadowText(DuelTrim(Entry.Message, 50), LogColor, DX(42.0f), DY(LogY), GetFont(false), 0.58f * DuelScale, false);
		LogY += 38.0f;
	}
	DrawShadowText(FString::Printf(TEXT("TURN %d   %s"), DuelEngine->GetTurnNumber(), *DuelEngine->GetPhaseLabel()),
		Muted, DX(42.0f), DY(842.0f), GetFont(false), 0.6f * DuelScale, false);

	// Board helper lambdas.
	auto IsHoverRect = [this](float X, float Y, float W, float H)
	{
		return DuelMousePosition.X >= DX(X) && DuelMousePosition.X <= DX(X + W)
			&& DuelMousePosition.Y >= DY(Y) && DuelMousePosition.Y <= DY(Y + H);
	};
	auto DrawEmptyZone = [this](float X, float Y, float W, float H, const FString& Label)
	{
		DrawPanel(DX(X), DY(Y), DS(W), DS(H), FLinearColor(0.015f, 0.03f, 0.048f, 0.7f),
			FLinearColor(0.2f, 0.3f, 0.38f, 0.45f));
		DrawShadowText(Label, FLinearColor(0.26f, 0.38f, 0.46f, 0.85f), DX(X + W * 0.5f), DY(Y + H * 0.5f - 8.0f),
			GetFont(false), 0.62f * DuelScale, true);
	};
	auto DrawFieldSlot = [this, &DrawEmptyZone](EDuelOwner SlotOwner, float X, float Y)
	{
		const FDuelSide& Side = DuelEngine->GetSide(SlotOwner);
		if (Side.Field.IsValid())
		{
			DrawDuelCard(Side.Field, DX(X), DY(Y), DS(88.0f), DS(128.0f), !Side.Field.bFaceUp,
				DuelSelectedUid == Side.Field.Uid, false, false);
			AddDuelHit(TEXT("select"), Side.Field.Uid, DX(X), DY(Y), DS(88.0f), DS(128.0f));
		}
		else
		{
			DrawEmptyZone(X, Y, 88.0f, 128.0f, TEXT("FIELD"));
		}
	};
	auto DrawPile = [this](const FString& Label, int32 Count, int32 Type, EDuelOwner PileOwner, float X, float Y)
	{
		const float W = 126.0f;
		const float H = 34.0f;
		const bool bHover = DuelMousePosition.X >= DX(X) && DuelMousePosition.X <= DX(X + W)
			&& DuelMousePosition.Y >= DY(Y) && DuelMousePosition.Y <= DY(Y + H);
		DrawPanel(DX(X), DY(Y), DS(W), DS(H), bHover ? FLinearColor(0.06f, 0.1f, 0.14f, 0.98f)
			: FLinearColor(0.02f, 0.04f, 0.06f, 0.92f), bHover ? GoldSoft : Line);
		DrawShadowText(FString::Printf(TEXT("%s %d"), *Label, Count), Paper, DX(X + 10.0f), DY(Y + 9.0f),
			GetFont(false), 0.6f * DuelScale, false);
		AddDuelHit(TEXT("pile"), (PileOwner == EDuelOwner::Player ? 0 : 10) + Type, DX(X), DY(Y), DS(W), DS(H));
	};

	// Opponent hand.
	const int32 OppHandCount = OpponentSide.Hand.Num();
	if (OppHandCount > 0)
	{
		const float CardW = 52.0f;
		const float CardH = 76.0f;
		const float Spacing = FMath::Min(58.0f, 360.0f / OppHandCount);
		const float StartX = 800.0f - (OppHandCount - 1) * Spacing * 0.5f;
		for (int32 I = 0; I < OppHandCount; ++I)
		{
			DrawDuelCard(OpponentSide.Hand[I], DX(StartX + I * Spacing - CardW * 0.5f), DY(92.0f),
				DS(CardW), DS(CardH), true);
		}
		DrawShadowText(FString::Printf(TEXT("%s'S HAND  %d"), *DuelOpponentName.ToUpper(), OppHandCount), Muted, DX(800.0f), DY(172.0f),
			GetFont(false), 0.52f * DuelScale, true);
	}

	// Opponent field.
	DrawFieldSlot(EDuelOwner::Opponent, 430.0f, 184.0f);
	for (int32 I = 0; I < OpponentSide.Spells.Num(); ++I)
	{
		const float X = 540.0f + I * 98.0f;
		const FDuelCard& Card = OpponentSide.Spells[I];
		if (Card.IsValid())
		{
			DrawDuelCard(Card, DX(X), DY(184.0f), DS(88.0f), DS(128.0f), !Card.bFaceUp,
				DuelSelectedUid == Card.Uid, IsHoverRect(X, 184.0f, 88.0f, 128.0f));
			AddDuelHit(TEXT("select"), Card.Uid, DX(X), DY(184.0f), DS(88.0f), DS(128.0f));
		}
		else
		{
			DrawEmptyZone(X, 184.0f, 88.0f, 128.0f, TEXT("S/T"));
		}
	}
	for (int32 I = 0; I < OpponentSide.Monsters.Num(); ++I)
	{
		const float X = 540.0f + I * 98.0f;
		const FDuelCard& Card = OpponentSide.Monsters[I];
		if (Card.IsValid())
		{
			DrawDuelCard(Card, DX(X), DY(320.0f), DS(88.0f), DS(128.0f), !Card.bFaceUp,
				DuelSelectedUid == Card.Uid, IsHoverRect(X, 320.0f, 88.0f, 128.0f),
				Card.Position == EDuelPosition::Defense);
			AddDuelHit(TEXT("select"), Card.Uid, DX(X), DY(320.0f), DS(88.0f), DS(128.0f));
		}
		else
		{
			DrawEmptyZone(X, 320.0f, 88.0f, 128.0f, TEXT("MONSTER"));
		}
	}

	// Phase banner.
	{
		const float BX = 540.0f;
		const float BY = 456.0f;
		FLinearColor BannerColor = bPlayerTurn ? FLinearColor(0.38f, 0.70f, 0.92f) : FLinearColor(0.82f, 0.57f, 0.31f);
		DrawPanel(DX(BX), DY(BY), DS(480.0f), DS(32.0f), FLinearColor(0.018f, 0.035f, 0.052f, 0.96f), BannerColor);
		FString BannerText = bAiTurn
			? (DuelEngine->IsAwaitingAi() ? FString::Printf(TEXT("%s'S TURN  -  THINKING"), *DuelOpponentName.ToUpper()) : FString::Printf(TEXT("%s'S TURN"), *DuelOpponentName.ToUpper()))
			: FString::Printf(TEXT("YOUR TURN  -  %s"), *DuelEngine->GetPhaseLabel());
		DrawShadowText(BannerText, BannerColor, DX(BX + 240.0f), DY(BY + 8.0f), GetFont(false), 0.7f * DuelScale, true);
	}

	// Player field.
	for (int32 I = 0; I < PlayerSide.Monsters.Num(); ++I)
	{
		const float X = 540.0f + I * 98.0f;
		const FDuelCard& Card = PlayerSide.Monsters[I];
		if (Card.IsValid())
		{
			const bool bTributeSelected = DuelTributeUids.Contains(Card.Uid);
			DrawDuelCard(Card, DX(X), DY(494.0f), DS(88.0f), DS(128.0f), !Card.bFaceUp,
				bTributeSelected || DuelSelectedUid == Card.Uid, IsHoverRect(X, 494.0f, 88.0f, 128.0f),
				Card.Position == EDuelPosition::Defense);
			AddDuelHit(bDuelTributeSet ? TEXT("tribute") : TEXT("select"), Card.Uid,
				DX(X), DY(494.0f), DS(88.0f), DS(128.0f));
		}
		else
		{
			DrawEmptyZone(X, 494.0f, 88.0f, 128.0f, TEXT("MONSTER"));
		}
	}
	for (int32 I = 0; I < PlayerSide.Spells.Num(); ++I)
	{
		const float X = 540.0f + I * 98.0f;
		const FDuelCard& Card = PlayerSide.Spells[I];
		if (Card.IsValid())
		{
			DrawDuelCard(Card, DX(X), DY(630.0f), DS(88.0f), DS(128.0f), !Card.bFaceUp,
				DuelSelectedUid == Card.Uid, IsHoverRect(X, 630.0f, 88.0f, 128.0f));
			AddDuelHit(TEXT("select"), Card.Uid, DX(X), DY(630.0f), DS(88.0f), DS(128.0f));
		}
		else
		{
			DrawEmptyZone(X, 630.0f, 88.0f, 128.0f, TEXT("S/T"));
		}
	}
	DrawFieldSlot(EDuelOwner::Player, 430.0f, 630.0f);

	// Piles.
	DrawPile(TEXT("DECK"), OpponentSide.Deck.Num(), 1, EDuelOwner::Opponent, 1040.0f, 184.0f);
	DrawPile(TEXT("EXTRA"), OpponentSide.Extra.Num(), 2, EDuelOwner::Opponent, 1040.0f, 226.0f);
	DrawPile(TEXT("GRAVE"), OpponentSide.Graveyard.Num(), 3, EDuelOwner::Opponent, 1040.0f, 268.0f);
	DrawPile(TEXT("BANISH"), OpponentSide.Banished.Num(), 4, EDuelOwner::Opponent, 1040.0f, 310.0f);
	DrawPile(TEXT("DECK"), PlayerSide.Deck.Num(), 1, EDuelOwner::Player, 1040.0f, 630.0f);
	DrawPile(TEXT("EXTRA"), PlayerSide.Extra.Num(), 2, EDuelOwner::Player, 1040.0f, 672.0f);
	DrawPile(TEXT("GRAVE"), PlayerSide.Graveyard.Num(), 3, EDuelOwner::Player, 1040.0f, 714.0f);
	DrawPile(TEXT("BANISH"), PlayerSide.Banished.Num(), 4, EDuelOwner::Player, 1040.0f, 756.0f);

	// Player hand.
	const int32 HandCount = PlayerSide.Hand.Num();
	if (HandCount > 0)
	{
		const float CardW = 72.0f;
		const float CardH = 104.0f;
		// Keep the hand inside the playmat and clear of the right-hand pile
		// column, even at the 7-8 card hand limit.
		const float Spacing = FMath::Min(80.0f,
			(480.0f - CardW) / FMath::Max(1, HandCount - 1));
		const float TotalWidth = (HandCount - 1) * Spacing + CardW;
		const float StartX = 800.0f - TotalWidth * 0.5f;
		for (int32 I = 0; I < HandCount; ++I)
		{
			const FDuelCard& Card = PlayerSide.Hand[I];
			const bool bSelectedCard = DuelSelectedUid == Card.Uid;
			const float CardY = 766.0f - (bSelectedCard ? 8.0f : 0.0f);
			DrawDuelCard(Card, DX(StartX + I * Spacing), DY(CardY), DS(CardW), DS(CardH), !Card.bFaceUp,
				bSelectedCard, IsHoverRect(StartX + I * Spacing, CardY, CardW, CardH));
			AddDuelHit(DuelEngine->IsAwaitingDiscard() ? TEXT("discard") : TEXT("select"), Card.Uid,
				DX(StartX + I * Spacing), DY(CardY), DS(CardW), DS(CardH));
		}
	}

	// Right detail/action panel.
	const float RX = 1216.0f;
	const float RY = 110.0f;
	const float RW = 360.0f;
	const float RH = 760.0f;
	DrawPanel(DX(RX), DY(RY), DS(RW), DS(RH), FLinearColor(0.022f, 0.04f, 0.058f, 0.96f), Line);

	DrawShadowText(Selected ? TEXT("CARD DETAIL") : TEXT("DUEL COMMAND"), Gold,
		DX(RX + 20.0f), DY(RY + 14.0f), GetFont(false), 0.68f * DuelScale, false);

	if (!Selected && !DuelEngine->IsAwaitingDiscard() && !bDuelTributeSet)
	{
		int32 PlayerMonsterCount = 0;
		int32 OppMonsterCount = 0;
		for (const FDuelCard& Monster : PlayerSide.Monsters) if (Monster.IsValid()) ++PlayerMonsterCount;
		for (const FDuelCard& Monster : OpponentSide.Monsters) if (Monster.IsValid()) ++OppMonsterCount;
		DrawShadowText(TEXT("HOW TO PLAY"), Muted, DX(RX + 20.0f), DY(RY + 48.0f), GetFont(false), 0.62f * DuelScale, false);
		DrawWrappedText(
			TEXT("Click a hand card to inspect it. Summon or Set it from the action list. Select a monster in the Battle Phase to see its attack targets."),
			DX(RX + 20.0f), DY(RY + 72.0f), DS(RW - 40.0f), GetFont(false), 0.64f * DuelScale, Paper, 3.0f);
		DrawRect(Line, DX(RX + 20.0f), DY(RY + 206.0f), DS(RW - 40.0f), 1.0f);
		DrawShadowText(TEXT("SHORTCUTS"), Muted, DX(RX + 20.0f), DY(RY + 222.0f), GetFont(false), 0.62f * DuelScale, false);
		DrawShadowText(TEXT("B   Battle Phase"), Paper, DX(RX + 20.0f), DY(RY + 248.0f), GetFont(false), 0.64f * DuelScale, false);
		DrawShadowText(TEXT("N   End Turn"), Paper, DX(RX + 20.0f), DY(RY + 274.0f), GetFont(false), 0.64f * DuelScale, false);
		DrawShadowText(TEXT("Esc  Deselect / close pile"), Paper, DX(RX + 20.0f), DY(RY + 300.0f), GetFont(false), 0.64f * DuelScale, false);
		DrawRect(Line, DX(RX + 20.0f), DY(RY + 338.0f), DS(RW - 40.0f), 1.0f);
		DrawShadowText(TEXT("FIELD STATUS"), Muted, DX(RX + 20.0f), DY(RY + 354.0f), GetFont(false), 0.62f * DuelScale, false);
		DrawShadowText(FString::Printf(TEXT("Your monsters: %d / 5"), PlayerMonsterCount), Paper,
			DX(RX + 20.0f), DY(RY + 380.0f), GetFont(false), 0.62f * DuelScale, false);
		DrawShadowText(FString::Printf(TEXT("%s's monsters: %d / 5"), *DuelOpponentName, OppMonsterCount), Paper,
			DX(RX + 20.0f), DY(RY + 404.0f), GetFont(false), 0.62f * DuelScale, false);
		DrawShadowText(FString::Printf(TEXT("Your hand: %d / 6"), PlayerSide.Hand.Num()),
			PlayerSide.Hand.Num() > 6 ? FLinearColor(0.98f, 0.46f, 0.34f) : Paper,
			DX(RX + 20.0f), DY(RY + 428.0f), GetFont(false), 0.62f * DuelScale, false);
		DrawShadowText(TEXT("Click Deck / Extra / Grave / Banish to inspect."), Muted,
			DX(RX + 20.0f), DY(RY + 456.0f), GetFont(false), 0.56f * DuelScale, false);
	}

	if (DuelEngine->IsAwaitingDiscard())
	{
		DrawShadowText(TEXT("HAND LIMIT"), FLinearColor(0.95f, 0.78f, 0.38f), DX(RX + 20.0f), DY(RY + 46.0f),
			GetFont(false), 0.8f * DuelScale, false);
		DrawWrappedText(FString::Printf(TEXT("Discard %d card(s) from your hand. Click a card below."),
			DuelEngine->GetDiscardCount()), DX(RX + 20.0f), DY(RY + 70.0f), DS(RW - 40.0f),
			GetFont(false), 0.72f * DuelScale, Paper, 3.0f);
	}
	else if (bDuelTributeSet)
	{
		const int32 Required = DuelEngine->GetRequiredTributes(DuelTributeHandUid);
		DrawShadowText(TEXT("TRIBUTE SUMMON"), FLinearColor(0.55f, 0.9f, 0.64f), DX(RX + 20.0f), DY(RY + 46.0f),
			GetFont(false), 0.8f * DuelScale, false);
		DrawWrappedText(FString::Printf(TEXT("Select %d tribute(s) on your field. Selected: %d / %d"),
			Required, DuelTributeUids.Num(), Required), DX(RX + 20.0f), DY(RY + 70.0f), DS(RW - 40.0f),
			GetFont(false), 0.72f * DuelScale, Paper, 3.0f);
		DrawDuelButton(TEXT("CONFIRM TRIBUTE"), TEXT("confirmtribute"), 0, RX + 20.0f, RY + 690.0f, 150.0f, 38.0f,
			DuelTributeUids.Num() == Required, FLinearColor(0.44f, 0.78f, 0.54f));
		DrawDuelButton(TEXT("CANCEL"), TEXT("canceltribute"), 0, RX + 182.0f, RY + 690.0f, 150.0f, 38.0f);
	}
	else if (Selected)
	{
		const bool bCardHidden = !Selected->bFaceUp && Selected->Owner != EDuelOwner::Player;
		if (!bCardHidden)
		{
			DrawDuelCard(*Selected, DX(RX + (RW - 170.0f) * 0.5f), DY(RY + 42.0f), DS(170.0f), DS(246.0f),
				!Selected->bFaceUp, false, false, Selected->Position == EDuelPosition::Defense);
			DrawShadowText(DuelTrim(Selected->Data.Name, 38), Paper, DX(RX + 20.0f), DY(RY + 300.0f),
				GetFont(false), 0.78f * DuelScale, false);
			FString TypeLine = Selected->Data.CardType;
			if (!Selected->Data.MonsterType.IsEmpty() && Selected->Data.MonsterType != TEXT("Spell") && Selected->Data.MonsterType != TEXT("Trap"))
			{
				TypeLine += FString::Printf(TEXT(" / %s"), *Selected->Data.MonsterType);
			}
			DrawShadowText(TypeLine, AccentCyan, DX(RX + 20.0f), DY(RY + 326.0f), GetFont(false), 0.6f * DuelScale, false);
			if (Selected->IsMonster())
			{
				DrawShadowText(FString::Printf(TEXT("ATK %d   DEF %d   LV %d"), DuelEngine->GetAtk(*Selected),
					DuelEngine->GetDef(*Selected), Selected->Data.Level), Paper, DX(RX + 20.0f), DY(RY + 348.0f),
					GetFont(false), 0.66f * DuelScale, false);
				if (Selected->Counters > 0)
				{
					DrawShadowText(FString::Printf(TEXT("SPELL COUNTERS %d"), Selected->Counters), Gold,
						DX(RX + 200.0f), DY(RY + 348.0f), GetFont(false), 0.58f * DuelScale, false);
				}
			}
			DrawWrappedText(Selected->Data.Description.Replace(TEXT("ð"), TEXT(" ")), DX(RX + 20.0f), DY(RY + 380.0f),
				DS(RW - 40.0f), GetFont(false), 0.56f * DuelScale,
				FLinearColor(0.72f, 0.78f, 0.8f), 2.0f);
		}
		else
		{
			DrawShadowText(TEXT("SET CARD"), Muted, DX(RX + 20.0f), DY(RY + 60.0f), GetFont(false), 1.0f * DuelScale, false);
			DrawWrappedText(FString::Printf(TEXT("%s's face-down card. Its identity stays hidden until it is activated or flipped."), *DuelOpponentName),
				DX(RX + 20.0f), DY(RY + 92.0f), DS(RW - 40.0f), GetFont(false), 0.66f * DuelScale, Muted, 3.0f);
		}

		if (Selected->Controller == EDuelOwner::Player && bPlayerTurn && !bAiTurn && bMain)
		{
			float ActionY = RY + 560.0f;
			auto DrawAction = [this, &ActionY, RX](const FString& Label, const FString& Action, int32 Value)
			{
				DrawDuelButton(Label, Action, Value, RX + 20.0f, ActionY, 320.0f, 34.0f);
				ActionY += 42.0f;
			};

			if (Selected->Controller == EDuelOwner::Player && PlayerSide.Hand.ContainsByPredicate(
				[this](const FDuelCard& C) { return C.Uid == DuelSelectedUid; }))
			{
				for (const FDuelActionInfo& Action : DuelEngine->GetHandActions(DuelSelectedUid))
				{
					FString Hit = TEXT("select");
					if (Action.Action == EDuelAction::NormalSummon || Action.Action == EDuelAction::TributeSummon) Hit = TEXT("summon");
					else if (Action.Action == EDuelAction::SetMonster) Hit = TEXT("setmonster");
					else if (Action.Action == EDuelAction::SpecialSummon) Hit = TEXT("special");
					else if (Action.Action == EDuelAction::ActivateSpell) Hit = TEXT("activatespell");
					else if (Action.Action == EDuelAction::SetSpellTrap) Hit = TEXT("settrap");
					DrawAction(Action.Label, Hit, DuelSelectedUid);
				}
			}
			else if (Selected->IsMonster() && Selected->Owner == EDuelOwner::Player)
			{
				for (const FDuelActionInfo& Action : DuelEngine->GetMonsterActions(DuelSelectedUid))
				{
					if (Action.Action == EDuelAction::FlipSummon) DrawAction(Action.Label, TEXT("flip"), DuelSelectedUid);
					else if (Action.Action == EDuelAction::ChangePosition) DrawAction(Action.Label, TEXT("position"), DuelSelectedUid);
					else if (Action.Action == EDuelAction::ActivateEffect) DrawAction(Action.Label, TEXT("effect"), DuelSelectedUid);
				}
			}
			else if (Selected->IsTrap() && Selected->Owner == EDuelOwner::Player)
			{
				for (const FDuelActionInfo& Action : DuelEngine->GetSpellTrapActions(DuelSelectedUid))
				{
					DrawAction(Action.Label, TEXT("activatetrap"), DuelSelectedUid);
				}
			}
		}

		// Battle targets replace the generic action list while a monster is selected.
		if (Selected->Owner == EDuelOwner::Player && Selected->IsMonster()
			&& DuelEngine->GetPhase() == EDuelPhase::Battle && bPlayerTurn && !bAiTurn)
		{
			const TArray<FDuelAttackTarget> Targets = DuelEngine->GetAttackTargets(DuelSelectedUid);
			if (Targets.Num() > 0)
			{
				DrawShadowText(TEXT("ATTACK TARGETS"), FLinearColor(0.96f, 0.62f, 0.38f),
					DX(RX + 20.0f), DY(RY + 512.0f), GetFont(false), 0.66f * DuelScale, false);
				float TargetY = RY + 532.0f;
				for (const FDuelAttackTarget& Target : Targets)
				{
					DrawDuelButton(DuelTrim(Target.Label, 40), TEXT("attack"), Target.Uid,
						RX + 20.0f, TargetY, 320.0f, 30.0f, true, FLinearColor(0.72f, 0.34f, 0.24f));
					TargetY += 34.0f;
					if (TargetY > RY + 690.0f) break;
				}
			}
		}
	}

	// Primary command buttons.
	if (bPlayerTurn && !bAiTurn && !DuelEngine->IsAwaitingDiscard() && !bDuelTributeSet)
	{
		if (DuelEngine->GetPhase() == EDuelPhase::Battle)
		{
			DrawDuelButton(TEXT("END BATTLE PHASE"), TEXT("endbattle"), 0, RX + 20.0f, RY + 704.0f, 150.0f, 36.0f,
				true, FLinearColor(0.82f, 0.48f, 0.28f));
		}
		else
		{
			const bool bCanBattle = DuelEngine->GetPhase() == EDuelPhase::Main1;
			DrawDuelButton(TEXT("BATTLE PHASE"), TEXT("battle"), 0, RX + 20.0f, RY + 704.0f, 150.0f, 36.0f,
				bCanBattle, FLinearColor(0.82f, 0.48f, 0.28f));
		}
		DrawDuelButton(TEXT("END TURN"), TEXT("endturn"), 0, RX + 182.0f, RY + 704.0f, 150.0f, 36.0f,
			true, FLinearColor(0.42f, 0.68f, 0.86f));
	}
	else if (bAiTurn)
	{
		DrawWrappedText(FString::Printf(TEXT("%s is dueling...\n%s"), *DuelOpponentName, *DuelEngine->GetLastAiMessage()),
			DX(RX + 20.0f), DY(RY + 560.0f), DS(RW - 40.0f), GetFont(false), 0.7f * DuelScale, GoldSoft, 3.0f);
	}

	// Message / hint strip.
	FString Hint = TEXT("Click a card to inspect it. B enters Battle. N ends the turn. Esc deselects.");
	if (DuelEngine->IsAwaitingDiscard())
	{
		Hint = FString::Printf(TEXT("DISCARD %d CARD(S) TO THE 6-CARD HAND LIMIT"), DuelEngine->GetDiscardCount());
	}
	if (DuelMessageTimer > 0.0f && !DuelMessage.IsEmpty())
	{
		Hint = DuelMessage;
	}
	DrawPanel(DX(540.0f), DY(872.0f), DS(480.0f), DS(22.0f), FLinearColor(0.018f, 0.035f, 0.05f, 0.95f), Line);
	DrawShadowText(DuelTrim(Hint, 62), DuelMessageTimer > 0.0f ? FLinearColor(0.95f, 0.74f, 0.38f) : Muted,
		DX(780.0f), DY(876.0f), GetFont(false), 0.52f * DuelScale, true);

	// Low-LP heartbeat vignette.  It is deliberately subtle so it never
	// competes with the board text.
	const bool bPlayerLow = DuelPlayerLpDisplay <= 2000.0f;
	const bool bOpponentLow = DuelOpponentLpDisplay <= 2000.0f;
	if (bPlayerLow || bOpponentLow)
	{
		const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
		const float Pulse = 0.5f + 0.5f * FMath::Sin(Now * 4.6f);
		const FLinearColor LowColor(0.86f, 0.10f, 0.08f, (0.08f + Pulse * 0.06f));
		const float Edge = FMath::Max(3.0f, DS(7.0f));
		DrawRect(LowColor, 0.0f, 0.0f, Canvas->ClipX, Edge);
		DrawRect(LowColor, 0.0f, Canvas->ClipY - Edge, Canvas->ClipX, Edge);
		DrawRect(LowColor, 0.0f, 0.0f, Edge, Canvas->ClipY);
		DrawRect(LowColor, Canvas->ClipX - Edge, 0.0f, Edge, Canvas->ClipY);
	}
}

void FDADuelUI::DrawDuelResult()
{
	if (!DuelEngine)
	{
		return;
	}
	const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	const float Elapsed = FMath::Max(0.0f, Now - DuelResultEnterTime);
	const float Ease = 1.0f - FMath::Pow(1.0f - FMath::Clamp(Elapsed / 0.52f, 0.0f, 1.0f), 3.0f);
	const float ResultFade = FMath::Clamp(Elapsed / 0.34f, 0.0f, 1.0f);
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.68f), 0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);
	for (int32 Band = 0; Band < 7; ++Band)
	{
		DrawRect(FLinearColor(0.16f, 0.30f, 0.40f, 0.018f + Band * 0.004f),
			DX(0.0f), DY(120.0f + Band * 96.0f), Canvas->ClipX, DS(38.0f));
	}
	if (!bDuelResultWon)
	{
		DrawRect(FLinearColor(0.22f, 0.01f, 0.01f, 0.12f), 0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);
	}

	const float X = 340.0f;
	const float Y = 160.0f;
	const float W = 920.0f;
	const float H = 560.0f;
	const FLinearColor Accent = bDuelResultWon ? FLinearColor(0.90f, 0.70f, 0.28f) : FLinearColor(0.80f, 0.42f, 0.34f);
	DrawPanel(DX(X), DY(Y), DS(W), DS(H), FLinearColor(0.018f, 0.034f, 0.052f, 0.99f), Accent);
	DrawRect(Accent, DX(X), DY(Y), DS(W), DS(4.0f));
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.28f), DX(X), DY(Y + 4.0f), DS(W), DS(1.0f));

	if (bDuelResultWon)
	{
		for (int32 I = 0; I < 26; ++I)
		{
			const float Seed = I * 37.71f;
			const float Fall = FMath::Fmod(Elapsed * (42.0f + FMath::Fmod(Seed, 55.0f)) + Seed * 3.0f, 620.0f);
			const float ConfettiX = X + 30.0f + FMath::Fmod(Seed * 23.7f, W - 60.0f)
				+ FMath::Sin(Elapsed * 1.4f + I) * 18.0f;
			const float ConfettiY = Y + Fall;
			const FLinearColor Color = (I % 3 == 0) ? Accent : ((I % 3 == 1)
				? FLinearColor(0.38f, 0.70f, 0.92f) : FLinearColor(0.92f, 0.42f, 0.32f));
			DrawRect(FLinearColor(Color.R, Color.G, Color.B, 0.58f * ResultFade), DX(ConfettiX), DY(ConfettiY),
				DS(3.0f + (I % 2) * 2.0f), DS(9.0f));
		}
	}

	DrawShadowText(TEXT("DUEL RESULT"), Muted, DX(X + W * 0.5f), DY(Y - 30.0f),
		GetFont(false), 0.72f * DuelScale, true);
	DrawShadowText(bDuelResultWon ? TEXT("DUEL WON") : TEXT("DUEL LOST"), Accent,
		DX(X + W * 0.5f), DY(Y + 24.0f), GetFont(true), 1.9f * DuelScale, true);
	DrawShadowText(bDuelResultWon ? FString::Printf(TEXT("%s DEFEATED"), *DuelOpponentName.ToUpper()) : FString::Printf(TEXT("%s WINS THE DUEL"), *DuelOpponentName.ToUpper()), Paper,
		DX(X + W * 0.5f), DY(Y + 82.0f), GetFont(false), 0.84f * DuelScale, true);

	const float PortraitW = 228.0f;
	const float PortraitH = 248.0f;
	const float PortraitY = Y + 118.0f;
	const float LeftSlide = (1.0f - Ease) * -260.0f;
	const float RightSlide = (1.0f - Ease) * 260.0f;
	const float JadenAlpha = bDuelResultWon ? 0.56f : 1.0f;
	const float PlayerAlpha = bDuelResultWon ? 1.0f : 0.56f;
	DrawDuelPortrait(DuelOpponentId, DX(X + 44.0f + LeftSlide), DY(PortraitY), DS(PortraitW), DS(PortraitH),
		bDuelResultWon ? FLinearColor(0.52f, 0.38f, 0.22f) : Accent, JadenAlpha, false,
		bDuelResultWon ? TEXT("sad") : TEXT("laugh"));
	DrawDuelPortrait(TEXT("player"), DX(X + W - 44.0f - PortraitW + RightSlide), DY(PortraitY),
		DS(PortraitW), DS(PortraitH), bDuelResultWon ? Accent : FLinearColor(0.52f, 0.34f, 0.30f),
		PlayerAlpha, false, bDuelResultWon ? TEXT("laugh") : TEXT("sad"));

	DrawShadowText(DuelOpponentName.ToUpper(), Gold, DX(X + 44.0f + PortraitW * 0.5f), DY(PortraitY + PortraitH + 8.0f),
		GetFont(false), 0.68f * DuelScale, true);
	DrawShadowText(TEXT("YOU"), AccentCyan, DX(X + W - 44.0f - PortraitW * 0.5f),
		DY(PortraitY + PortraitH + 8.0f), GetFont(false), 0.68f * DuelScale, true);
	DrawShadowText(TEXT("VS"), Muted, DX(X + W * 0.5f), DY(PortraitY + 104.0f),
		GetFont(true), 1.25f * DuelScale, true);

	DrawShadowText(FString::Printf(TEXT("YOU  %d LP        %s  %d LP        TURN %d"),
		DuelEngine->GetSide(EDuelOwner::Player).LP, *DuelOpponentName.ToUpper(),
		DuelEngine->GetSide(EDuelOwner::Opponent).LP, DuelEngine->GetTurnNumber()),
		FLinearColor(0.7f, 0.78f, 0.8f), DX(X + W * 0.5f), DY(Y + 418.0f), GetFont(false), 0.68f * DuelScale, true);
	DrawWrappedText(
		bDuelResultWon
			? TEXT("\"Good duel. You read the field better than I did - come back for a rematch whenever you want.\"")
			: TEXT("\"That was a solid attempt. Shuffle up, rethink your plays, and challenge me again.\""),
		DX(X + 110.0f), DY(Y + 444.0f), DS(W - 220.0f), GetFont(false), 0.70f * DuelScale, Paper, 3.0f);

	DrawDuelButton(TEXT("REMATCH"), TEXT("rematch"), 0, X + 226.0f, Y + 492.0f, 220.0f, 44.0f,
		true, Accent);
	DrawDuelButton(TEXT("RETURN TO ISLAND"), TEXT("return"), 0, X + 474.0f, Y + 492.0f, 220.0f, 44.0f,
		true, FLinearColor(0.42f, 0.68f, 0.86f));
	DrawShadowText(TEXT("Enter: rematch     Esc: return to the island"), Muted,
		DX(X + W * 0.5f), DY(Y + 544.0f), GetFont(false), 0.55f * DuelScale, true);
}

void FDADuelUI::DrawDuelPile()
{
	if (!DuelEngine)
	{
		return;
	}
	DuelHitTargets.Reset();
	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.66f), 0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);

	const FDuelSide& Side = DuelEngine->GetSide(DuelPileOwner);
	const TArray<FDuelCard>* Cards = nullptr;
	FString Title;
	bool bContentsHidden = false;
	switch (DuelPileType)
	{
	case EDuelPileType::Deck:
		Cards = &Side.Deck;
		Title = TEXT("DECK");
		bContentsHidden = true;
		break;
	case EDuelPileType::Extra:
		Cards = &Side.Extra;
		Title = TEXT("EXTRA DECK");
		bContentsHidden = DuelPileOwner == EDuelOwner::Opponent;
		break;
	case EDuelPileType::Graveyard:
		Cards = &Side.Graveyard;
		Title = TEXT("GRAVEYARD");
		break;
	case EDuelPileType::Banished:
		Cards = &Side.Banished;
		Title = TEXT("BANISHED");
		break;
	default:
		return;
	}

	const float X = 260.0f;
	const float Y = 90.0f;
	const float W = 1080.0f;
	const float H = 720.0f;
	DrawPanel(DX(X), DY(Y), DS(W), DS(H), FLinearColor(0.02f, 0.038f, 0.058f, 0.99f), Line);
	DrawShadowText(FString::Printf(TEXT("%s  -  %s  (%d)"),
		*Side.Name.ToUpper(), *Title, Cards->Num()), Gold, DX(X + 26.0f), DY(Y + 20.0f), GetFont(false), 0.9f * DuelScale, false);
	DrawShadowText(bContentsHidden ? TEXT("Contents are face-down.") : TEXT("Click close to return to the duel."),
		Muted, DX(X + 26.0f), DY(Y + 48.0f), GetFont(false), 0.62f * DuelScale, false);
	DrawDuelButton(TEXT("CLOSE"), TEXT("closepile"), 0, X + W - 140.0f, Y + 16.0f, 110.0f, 34.0f);

	const int32 Columns = 9;
	const int32 MaxRows = 4;
	const int32 MaxCards = Columns * MaxRows;
	const float CardW = 100.0f;
	const float CardH = 145.0f;
	const float Gap = 14.0f;
	const float GridW = Columns * CardW + (Columns - 1) * Gap;
	const float StartX = X + (W - GridW) * 0.5f;
	const float StartY = Y + 88.0f;
	for (int32 I = 0; I < Cards->Num() && I < MaxCards; ++I)
	{
		const int32 Col = I % Columns;
		const int32 Row = I / Columns;
		const float CX = StartX + Col * (CardW + Gap);
		const float CY = StartY + Row * (CardH + 18.0f);
		DrawDuelCard((*Cards)[I], DX(CX), DY(CY), DS(CardW), DS(CardH), bContentsHidden);
		if (!bContentsHidden)
		{
			DrawShadowText(DuelTrim((*Cards)[I].Data.Name, 18), Paper, DX(CX + CardW * 0.5f), DY(CY + CardH + 2.0f),
				GetFont(false), 0.44f * DuelScale, true);
		}
	}
	if (Cards->Num() > MaxCards)
	{
		DrawShadowText(FString::Printf(TEXT("Showing first %d of %d cards."), MaxCards, Cards->Num()), Muted,
			DX(X + W * 0.5f), DY(Y + H - 26.0f), GetFont(false), 0.58f * DuelScale, true);
	}
}

void FDADuelUI::DrawDuelCard(const FDuelCard& Card, float X, float Y, float W, float H,
	bool bFaceDown, bool bSelected, bool bHovered, bool bDefense)
{
	if (!Canvas)
	{
		return;
	}
	float FxOffsetX = 0.0f;
	float FxOffsetY = 0.0f;
	float FxScale = 1.0f;
	float FxAlpha = 1.0f;
	GetDuelCardFx(Card.Uid, FxOffsetX, FxOffsetY, FxScale, FxAlpha);
	X += DS(FxOffsetX);
	Y += DS(FxOffsetY);
	W *= FxScale;
	H *= FxScale;
	UCardArtSubsystem* Art = GetCardArt();
	float BorderWidth = 1.0f;
	FLinearColor Border = FLinearColor(0.30f, 0.38f, 0.44f, 0.7f);
	if (bDefense) Border = FLinearColor(0.32f, 0.62f, 0.86f, 0.9f);
	if (bHovered || bSelected)
	{
		Border = bSelected ? Gold : Paper;
		BorderWidth = bSelected ? 3.0f : 2.0f;
	}

	DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), X + DS(3.0f), Y + DS(4.0f), W, H);
	DrawRect(Border, X, Y, W, H);
	DrawRect(FLinearColor(0.01f, 0.02f, 0.03f, 1.0f), X + BorderWidth, Y + BorderWidth,
		W - BorderWidth * 2.0f, H - BorderWidth * 2.0f);

	if (bFaceDown)
	{
		UTexture2D* Back = Art ? Art->GetCardBack() : nullptr;
		if (Back)
		{
			DrawTexture(Back, X + BorderWidth, Y + BorderWidth, W - BorderWidth * 2.0f, H - BorderWidth * 2.0f,
				0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(0.72f, 0.8f, 0.92f, FxAlpha));
		}
		else
		{
			DrawRect(FLinearColor(0.08f, 0.18f, 0.36f, 1.0f), X + BorderWidth, Y + BorderWidth,
				W - BorderWidth * 2.0f, H - BorderWidth * 2.0f);
			DrawPanel(X + W * 0.18f, Y + H * 0.18f, W * 0.64f, H * 0.64f,
				FLinearColor(0.03f, 0.08f, 0.18f, 1.0f), FLinearColor(0.3f, 0.5f, 0.8f, 0.8f));
		}
		if (bDefense)
		{
			DrawRect(FLinearColor(0.1f, 0.35f, 0.6f, 0.75f), X + W - DS(28.0f), Y + DS(4.0f), DS(24.0f), DS(14.0f));
			DrawShadowText(TEXT("DEF"), Paper, X + W - DS(16.0f), Y + DS(5.0f), GetFont(false), 0.38f * DuelScale, true);
		}
		return;
	}

	UTexture2D* Texture = Art ? Art->GetCardArt(Card.Data.Id) : nullptr;
	if (Texture)
	{
		DrawTexture(Texture, X + BorderWidth, Y + BorderWidth, W - BorderWidth * 2.0f, H - BorderWidth * 2.0f,
			0.0f, 0.0f, 1.0f, 1.0f, FLinearColor(1.0f, 1.0f, 1.0f, FxAlpha));
	}
	else
	{
		FLinearColor Fill = FLinearColor(0.19f, 0.16f, 0.1f, 1.0f);
		if (Card.IsSpell()) Fill = FLinearColor(0.07f, 0.22f, 0.24f, 1.0f);
		else if (Card.IsTrap()) Fill = FLinearColor(0.22f, 0.09f, 0.24f, 1.0f);
		else if (Card.IsFusion()) Fill = FLinearColor(0.26f, 0.16f, 0.06f, 1.0f);
		DrawRect(Fill, X + BorderWidth, Y + BorderWidth, W - BorderWidth * 2.0f, H - BorderWidth * 2.0f);
		DrawWrappedText(Card.Data.Name, X + DS(6.0f), Y + DS(10.0f), W - DS(12.0f),
			GetFont(false), 0.44f * DuelScale, Paper, 1.0f);
		if (Card.IsMonster())
		{
			DrawShadowText(FString::Printf(TEXT("%d/%d"), Card.Data.Atk, Card.Data.Def), Paper,
				X + W * 0.5f, Y + H - DS(20.0f), GetFont(false), 0.4f * DuelScale, true);
		}
	}

	if (bDefense)
	{
		DrawRect(FLinearColor(0.1f, 0.35f, 0.6f, 0.8f), X + W - DS(30.0f), Y + DS(6.0f), DS(25.0f), DS(14.0f));
		DrawShadowText(TEXT("DEF"), Paper, X + W - DS(17.5f), Y + DS(6.0f), GetFont(false), 0.4f * DuelScale, true);
	}

	if (Card.Counters > 0)
	{
		const float Badge = DS(22.0f);
		DrawRect(FLinearColor(0.06f, 0.04f, 0.01f, 0.92f), X + DS(3.0f), Y + DS(3.0f), Badge, Badge);
		DrawRect(Gold, X + DS(3.0f), Y + DS(3.0f), Badge, 1.0f);
		DrawShadowText(FString::Printf(TEXT("%d"), Card.Counters), Gold, X + DS(3.0f) + Badge * 0.5f,
			Y + DS(6.0f), GetFont(false), 0.46f * DuelScale, true);
	}
}

void FDADuelUI::DrawDuelButton(const FString& Label, const FString& Action, int32 Value,
	float X, float Y, float W, float H, bool bEnabled, FLinearColor Accent)
{
	const bool bHover = bEnabled && DuelMousePosition.X >= DX(X) && DuelMousePosition.X <= DX(X + W)
		&& DuelMousePosition.Y >= DY(Y) && DuelMousePosition.Y <= DY(Y + H);
	FLinearColor Border = bEnabled ? Accent : FLinearColor(0.25f, 0.3f, 0.34f, 0.6f);
	if (bHover) Border = Paper;
	DrawPanel(DX(X), DY(Y), DS(W), DS(H),
		bHover ? FLinearColor(0.06f, 0.11f, 0.16f, 0.98f) : FLinearColor(0.025f, 0.045f, 0.065f, 0.96f), Border);
	DrawShadowText(Label, bEnabled ? Paper : FLinearColor(0.42f, 0.48f, 0.52f),
		DX(X + W * 0.5f), DY(Y + H * 0.5f - 8.0f), GetFont(false), 0.62f * DuelScale, true);
	if (bEnabled)
	{
		AddDuelHit(Action, Value, DX(X), DY(Y), DS(W), DS(H));
	}
}

