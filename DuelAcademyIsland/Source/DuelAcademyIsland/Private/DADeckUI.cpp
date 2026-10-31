// Duel Academy Island - deck editor implementation.

#include "DADeckUI.h"

#include "DAInventorySubsystem.h"
#include "DADuelEngine.h"
#include "DACardRecords.h"
#include "DuelAcademyIsland.h"
#include "Engine/Canvas.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

namespace
{
	const FLinearColor DeckGold(1.f, 0.78f, 0.25f);
	const FLinearColor DeckInk(0.008f, 0.014f, 0.028f);
	const FLinearColor DeckPaper(0.95f, 0.95f, 0.97f);
	const FLinearColor DeckMuted(0.58f, 0.63f, 0.72f);
	const FLinearColor DeckCyan(0.35f, 0.82f, 0.92f);
	const FLinearColor DeckGreen(0.42f, 0.82f, 0.48f);
	const FLinearColor DeckRed(0.90f, 0.28f, 0.24f);
	const FLinearColor DeckPurple(0.72f, 0.44f, 0.95f);

	FLinearColor DeckAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}
}

FDADeckUI::FDADeckUI(ADAHUD* InOwner)
	: FDAUIScreen(InOwner)
{
}

FDADeckUI::~FDADeckUI() = default;

UDADeckLogic* FDADeckUI::GetDeckLogic() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UDADeckLogic>() : nullptr;
}

UDAInventorySubsystem* FDADeckUI::GetInventory() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UDAInventorySubsystem>() : nullptr;
}

UCardDatabaseSubsystem* FDADeckUI::GetCardDatabase() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
}

void FDADeckUI::Open(const FString& DeckId)
{
	bOpen = true;
	Elapsed = 0.f;
	Focus = EDAFocus::Decks;
	PendingSwapCardId = 0;
	bPendingSwapExtra = false;
	bShowRecipes = false;
	bEditingName = false;
	bRenameMode = false;
	bConfirmErase = false;
	StatusMessage.Reset();
	StatusTime = 0.f;
	bStatusError = false;
	CurrentDeckId = DeckId;
	DeckIndex = 0;
	DeckScroll = 0;
	DeckCardScroll = 0;
	CollectionScroll = 0;
	RecipeScroll = 0;
	RefreshAll(!DeckId.IsEmpty());
	PlaySfx(TEXT("A_UIClick"), 0.45f);
}

void FDADeckUI::Close()
{
	if (!bOpen)
	{
		return;
	}
	bOpen = false;
	HitTargets.Reset();
	OnClosed.Broadcast();
}

void FDADeckUI::RefreshAll(bool bSelectDeckId)
{
	UDADeckLogic* Logic = GetDeckLogic();
	if (!Logic)
	{
		Decks.Reset();
		DeckMain.Reset();
		DeckExtra.Reset();
		Collection.Reset();
		CurrentDeckId.Reset();
		return;
	}

	Decks = Logic->GetPlayerDecks();
	if (Decks.Num() == 0)
	{
		DeckIndex = 0;
		CurrentDeckId.Reset();
		DeckMain.Reset();
		DeckExtra.Reset();
		RefreshCollection();
		Recipes = Logic->GetAvailableFusionRecipes();
		return;
	}

	if (bSelectDeckId && !CurrentDeckId.IsEmpty())
	{
		const int32 Found = Decks.IndexOfByPredicate([this](const FDAEDeck& Deck)
		{
			return Deck.Id == CurrentDeckId;
		});
		if (Found != INDEX_NONE)
		{
			DeckIndex = Found;
		}
	}
	if (!Decks.IsValidIndex(DeckIndex))
	{
		const FString ActiveId = Logic->GetActiveDeckId();
		DeckIndex = Decks.IndexOfByPredicate([&ActiveId](const FDAEDeck& Deck)
		{
			return Deck.Id == ActiveId;
		});
		if (DeckIndex == INDEX_NONE)
		{
			DeckIndex = 0;
		}
	}
	DeckIndex = FMath::Clamp(DeckIndex, 0, Decks.Num() - 1);
	CurrentDeckId = Decks[DeckIndex].Id;
	RefreshDeckCards();
	RefreshCollection();
	Recipes = Logic->GetAvailableFusionRecipes();
}

void FDADeckUI::RefreshDeckCards()
{
	DeckMain.Reset();
	DeckExtra.Reset();
	const FDAEDeck* Deck = nullptr;
	if (UDADeckLogic* Logic = GetDeckLogic())
	{
		Deck = Logic->FindPlayerDeck(CurrentDeckId);
	}
	if (!Deck)
	{
		Deck = GetCurrentDeck();
	}
	if (Deck)
	{
		DeckMain = Deck->Main;
		DeckExtra = Deck->Extra;
	}
	if (bDeckExtraSelection && DeckExtra.Num() == 0)
	{
		bDeckExtraSelection = false;
	}
	const int32 Count = bDeckExtraSelection ? DeckExtra.Num() : DeckMain.Num();
	DeckCardSelection = Count > 0 ? FMath::Clamp(DeckCardSelection, 0, Count - 1) : 0;
	DeckCardScroll = FMath::Clamp(DeckCardScroll, 0, FMath::Max(0, Count - 1));
	PendingSwapCardId = 0;
	bPendingSwapExtra = false;
}

void FDADeckUI::RefreshCollection()
{
	Collection.Reset();
	if (UDADeckLogic* Logic = GetDeckLogic())
	{
		FDAECardFilter Filter;
		Filter.bOwnedOnly = true;
		Filter.bMonstersOnly = FilterMode == 1;
		Filter.bSpellsOnly = FilterMode == 2;
		Filter.bTrapsOnly = FilterMode == 3;
		static const EDAECardSortKey SortKeys[] = {
			EDAECardSortKey::CardId, EDAECardSortKey::Name, EDAECardSortKey::Attack, EDAECardSortKey::Level
		};
		const EDAECardSortKey SortKey = SortKeys[FMath::Clamp(SortMode, 0, static_cast<int32>(UE_ARRAY_COUNT(SortKeys)) - 1)];
		Collection = Logic->GetCollectionView(Filter, SortKey, false);
	}
	CollectionSelection = Collection.Num() > 0
		? FMath::Clamp(CollectionSelection, 0, Collection.Num() - 1) : 0;
	CollectionScroll = FMath::Clamp(CollectionScroll, 0, FMath::Max(0, Collection.Num() - 1));
}

const FDAEDeck* FDADeckUI::GetCurrentDeck() const
{
	return Decks.IsValidIndex(DeckIndex) ? &Decks[DeckIndex] : nullptr;
}

FString FDADeckUI::GetCurrentDeckId() const
{
	const FDAEDeck* Deck = GetCurrentDeck();
	return Deck ? Deck->Id : FString();
}

const FCardRecord* FDADeckUI::FindCard(int32 CardId) const
{
	UCardDatabaseSubsystem* Cards = GetCardDatabase();
	return Cards ? Cards->FindCard(CardId) : nullptr;
}

FString FDADeckUI::GetCardName(int32 CardId) const
{
	const FCardRecord* Card = FindCard(CardId);
	return Card ? Card->Name : FString::Printf(TEXT("Card %d"), CardId);
}

bool FDADeckUI::IsExtraDeckCard(int32 CardId) const
{
	const FCardRecord* Card = FindCard(CardId);
	return Card && (Card->CardType.Contains(TEXT("Fusion"), ESearchCase::IgnoreCase)
		|| Card->Subtype.Contains(TEXT("Fusion"), ESearchCase::IgnoreCase));
}

FString FDADeckUI::GetFilterLabel() const
{
	static const TCHAR* Labels[] = { TEXT("ALL"), TEXT("MONSTERS"), TEXT("SPELLS"), TEXT("TRAPS") };
	return Labels[FMath::Clamp(FilterMode, 0, 3)];
}

FString FDADeckUI::GetSortLabel() const
{
	static const TCHAR* Labels[] = { TEXT("ID"), TEXT("NAME"), TEXT("ATK"), TEXT("LEVEL") };
	return Labels[FMath::Clamp(SortMode, 0, 3)];
}

void FDADeckUI::SetStatus(const FString& Message, bool bError)
{
	StatusMessage = Message;
	StatusTime = 5.f;
	bStatusError = bError;
}

void FDADeckUI::MoveSelection(int32 Delta)
{
	if (Focus == EDAFocus::Decks)
	{
		if (Decks.Num() == 0)
		{
			return;
		}
		const int32 NewIndex = FMath::Clamp(DeckIndex + Delta, 0, Decks.Num() - 1);
		if (NewIndex != DeckIndex)
		{
			DeckIndex = NewIndex;
			CurrentDeckId = Decks[DeckIndex].Id;
			RefreshDeckCards();
			PlaySfx(TEXT("A_UIClick"), 0.25f);
		}
		return;
	}
	if (Focus == EDAFocus::Collection)
	{
		if (Collection.Num() == 0)
		{
			return;
		}
		const int32 NewIndex = FMath::Clamp(CollectionSelection + Delta, 0, Collection.Num() - 1);
		if (NewIndex != CollectionSelection)
		{
			CollectionSelection = NewIndex;
			PlaySfx(TEXT("A_UIClick"), 0.22f);
		}
		return;
	}

	const TArray<int32>& List = bDeckExtraSelection ? DeckExtra : DeckMain;
	if (List.Num() == 0)
	{
		return;
	}
	const int32 NewIndex = FMath::Clamp(DeckCardSelection + Delta, 0, List.Num() - 1);
	if (NewIndex != DeckCardSelection)
	{
		DeckCardSelection = NewIndex;
		PlaySfx(TEXT("A_UIClick"), 0.22f);
	}
}

void FDADeckUI::MoveFocus(int32 Delta)
{
	const int32 Index = (static_cast<int32>(Focus) + Delta + 3) % 3;
	Focus = static_cast<EDAFocus>(Index);
	PlaySfx(TEXT("A_UIClick"), 0.25f);
}

void FDADeckUI::AddOrSwapSelectedCard()
{
	UDADeckLogic* Logic = GetDeckLogic();
	if (!Logic || !Collection.IsValidIndex(CollectionSelection) || CurrentDeckId.IsEmpty())
	{
		return;
	}
	const int32 CardId = Collection[CollectionSelection];
	FString Error;
	bool bSuccess = false;
	if (PendingSwapCardId != 0)
	{
		bSuccess = Logic->SwapCardInDeck(CurrentDeckId, PendingSwapCardId, CardId, bPendingSwapExtra, Error);
		PendingSwapCardId = 0;
		bPendingSwapExtra = false;
	}
	else
	{
		const bool bExtra = bExtraMode || IsExtraDeckCard(CardId);
		bSuccess = Logic->AddCardToDeck(CurrentDeckId, CardId, bExtra, Error);
	}
	if (bSuccess)
	{
		RefreshAll(true);
		SetStatus(TEXT("Deck updated."), false);
		PlaySfx(TEXT("A_CardDraw"), 0.6f);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not add that card.") : Error, true);
	}
}

void FDADeckUI::RemoveSelectedDeckCard()
{
	UDADeckLogic* Logic = GetDeckLogic();
	const TArray<int32>& List = bDeckExtraSelection ? DeckExtra : DeckMain;
	if (!Logic || !List.IsValidIndex(DeckCardSelection) || CurrentDeckId.IsEmpty())
	{
		return;
	}
	const int32 CardId = List[DeckCardSelection];
	FString Error;
	if (Logic->RemoveCardFromDeck(CurrentDeckId, CardId, bDeckExtraSelection, Error))
	{
		RefreshAll(true);
		SetStatus(TEXT("Card removed."), false);
		PlaySfx(TEXT("A_UIClick"), 0.45f);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not remove that card.") : Error, true);
	}
}

void FDADeckUI::BeginSwap()
{
	const TArray<int32>& List = bDeckExtraSelection ? DeckExtra : DeckMain;
	if (!List.IsValidIndex(DeckCardSelection))
	{
		SetStatus(TEXT("Select a deck card to swap out."), true);
		return;
	}
	PendingSwapCardId = List[DeckCardSelection];
	bPendingSwapExtra = bDeckExtraSelection;
	Focus = EDAFocus::Collection;
	SetStatus(TEXT("Select a collection card to swap in. Esc cancels."), false);
	PlaySfx(TEXT("A_UIClick"), 0.4f);
}

void FDADeckUI::BeginRename()
{
	const FDAEDeck* Deck = GetCurrentDeck();
	if (!Deck)
	{
		return;
	}
	EditDeckId = Deck->Id;
	NameBuffer = Deck->Name;
	bRenameMode = true;
	bEditingName = true;
	Focus = EDAFocus::Decks;
	PlaySfx(TEXT("A_UIClick"), 0.4f);
}

void FDADeckUI::CommitNameEdit()
{
	UDADeckLogic* Logic = GetDeckLogic();
	if (!Logic || EditDeckId.IsEmpty())
	{
		bEditingName = false;
		return;
	}
	FString Error;
	const FString NewName = NameBuffer.TrimStartAndEnd();
	if (Logic->RenameDeck(EditDeckId, NewName, Error))
	{
		CurrentDeckId = EditDeckId;
		RefreshAll(true);
		SetStatus(TEXT("Deck renamed."), false);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not rename the deck.") : Error, true);
	}
	bEditingName = false;
	bRenameMode = false;
}

void FDADeckUI::CreateNewDeck()
{
	UDADeckLogic* Logic = GetDeckLogic();
	if (!Logic)
	{
		return;
	}
	FString Error;
	const FString NewId = Logic->CreateDeck(TEXT("New Deck"), Error);
	if (!NewId.IsEmpty())
	{
		CurrentDeckId = NewId;
		RefreshAll(true);
		SetStatus(TEXT("Deck created."), false);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not create a deck.") : Error, true);
	}
}

void FDADeckUI::CopyCurrentDeck()
{
	UDADeckLogic* Logic = GetDeckLogic();
	const FDAEDeck* Deck = GetCurrentDeck();
	if (!Logic || !Deck)
	{
		return;
	}
	FString NewId;
	FString Error;
	if (Logic->CopyDeck(Deck->Id, Deck->Name + TEXT(" Copy"), NewId, Error))
	{
		CurrentDeckId = NewId;
		RefreshAll(true);
		SetStatus(TEXT("Deck copied."), false);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not copy the deck.") : Error, true);
	}
}

void FDADeckUI::EraseCurrentDeck()
{
	const FDAEDeck* Deck = GetCurrentDeck();
	if (!Deck)
	{
		return;
	}
	EraseDeckId = Deck->Id;
	bConfirmErase = true;
	PlaySfx(TEXT("A_UIClick"), 0.35f);
}

void FDADeckUI::SetCurrentDeckActive()
{
	UDADeckLogic* Logic = GetDeckLogic();
	if (!Logic || CurrentDeckId.IsEmpty())
	{
		return;
	}
	FString Error;
	if (Logic->SetActiveDeck(CurrentDeckId, Error))
	{
		RefreshAll(true);
		SetStatus(TEXT("Active deck changed."), false);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not set the active deck.") : Error, true);
	}
}

void FDADeckUI::CycleFilter()
{
	FilterMode = (FilterMode + 1) % 4;
	CollectionSelection = 0;
	CollectionScroll = 0;
	RefreshCollection();
	PlaySfx(TEXT("A_UIClick"), 0.25f);
}

void FDADeckUI::CycleSort()
{
	SortMode = (SortMode + 1) % 4;
	CollectionSelection = 0;
	CollectionScroll = 0;
	RefreshCollection();
	PlaySfx(TEXT("A_UIClick"), 0.25f);
}

void FDADeckUI::ToggleExtraMode()
{
	bExtraMode = !bExtraMode;
	SetStatus(bExtraMode ? TEXT("Add mode: EXTRA DECK.") : TEXT("Add mode: MAIN DECK."), false);
}

void FDADeckUI::UpdateNameEditor()
{
	PlayerOwner = GetPlayerController();
	if (!PlayerOwner)
	{
		return;
	}
	const int32 MaxLength = GetDeckLogic() ? GetDeckLogic()->GetRules().DeckNameMaxLength : 24;
	static const FKey LetterKeys[] = {
		EKeys::A, EKeys::B, EKeys::C, EKeys::D, EKeys::E, EKeys::F, EKeys::G,
		EKeys::H, EKeys::I, EKeys::J, EKeys::K, EKeys::L, EKeys::M, EKeys::N,
		EKeys::O, EKeys::P, EKeys::Q, EKeys::R, EKeys::S, EKeys::T, EKeys::U,
		EKeys::V, EKeys::W, EKeys::X, EKeys::Y, EKeys::Z
	};
	static const FKey NumberKeys[] = {
		EKeys::Zero, EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four,
		EKeys::Five, EKeys::Six, EKeys::Seven, EKeys::Eight, EKeys::Nine
	};
	for (int32 Index = 0; Index < UE_ARRAY_COUNT(LetterKeys); ++Index)
	{
		if (PlayerOwner->WasInputKeyJustPressed(LetterKeys[Index]) && NameBuffer.Len() < MaxLength)
		{
			NameBuffer.AppendChar(static_cast<TCHAR>('A' + Index));
		}
	}
	for (int32 Index = 0; Index < UE_ARRAY_COUNT(NumberKeys); ++Index)
	{
		if (PlayerOwner->WasInputKeyJustPressed(NumberKeys[Index]) && NameBuffer.Len() < MaxLength)
		{
			NameBuffer.AppendChar(static_cast<TCHAR>('0' + Index));
		}
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar) && NameBuffer.Len() < MaxLength)
	{
		NameBuffer.AppendChar(static_cast<TCHAR>(' '));
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::BackSpace) && !NameBuffer.IsEmpty())
	{
		NameBuffer = NameBuffer.LeftChop(1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
	{
		CommitNameEdit();
		return;
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
	{
		bEditingName = false;
		bRenameMode = false;
	}
}

void FDADeckUI::Update(float DeltaSeconds)
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
	FVector2D Mouse;
	if (GetMousePosition(Mouse))
	{
		for (const FDAUIHitTarget& Hit : HitTargets)
		{
			if ((Hit.Action == TEXT("deck") || Hit.Action == TEXT("collection")
				|| Hit.Action == TEXT("deckmain") || Hit.Action == TEXT("deckextra")) && Hit.Contains(Mouse))
			{
				HoveredIndex = Hit.Index;
			}
		}
	}

	if (!PlayerOwner)
	{
		return;
	}

	if (bEditingName)
	{
		UpdateNameEditor();
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}

	if (bConfirmErase)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
		{
			bConfirmErase = false;
			return;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
		{
			UDADeckLogic* Logic = GetDeckLogic();
			FString Error;
			if (Logic && !EraseDeckId.IsEmpty() && Logic->EraseDeck(EraseDeckId, Error))
			{
				CurrentDeckId.Reset();
				DeckIndex = 0;
				RefreshAll(false);
				SetStatus(TEXT("Deck erased."), false);
			}
			else if (!Error.IsEmpty())
			{
				SetStatus(Error, true);
			}
			bConfirmErase = false;
			return;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}

	if (bShowRecipes)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Up) || PlayerOwner->WasInputKeyJustPressed(EKeys::W))
		{
			RecipeScroll = FMath::Max(0, RecipeScroll - 1);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Down) || PlayerOwner->WasInputKeyJustPressed(EKeys::S))
		{
			RecipeScroll = FMath::Min(FMath::Max(0, Recipes.Num() - 1), RecipeScroll + 1);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Q) || PlayerOwner->WasInputKeyJustPressed(EKeys::F))
		{
			bShowRecipes = false;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
	{
		if (PendingSwapCardId != 0)
		{
			PendingSwapCardId = 0;
			bPendingSwapExtra = false;
			SetStatus(TEXT("Swap cancelled."), false);
		}
		else
		{
			Close();
		}
		return;
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Tab) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_LeftShoulder))
	{
		MoveFocus(1);
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
	if (Focus == EDAFocus::DeckCards)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Left) || PlayerOwner->WasInputKeyJustPressed(EKeys::Right)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Left) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_DPad_Right))
		{
			bDeckExtraSelection = !bDeckExtraSelection;
			DeckCardSelection = 0;
			DeckCardScroll = 0;
			PlaySfx(TEXT("A_UIClick"), 0.25f);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::G))
		{
			BeginSwap();
		}
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::N))
	{
		CreateNewDeck();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::C))
	{
		CopyCurrentDeck();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::R))
	{
		BeginRename();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Delete))
	{
		EraseCurrentDeck();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::F))
	{
		CycleFilter();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::T))
	{
		CycleSort();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::X))
	{
		ToggleExtraMode();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Q))
	{
		bShowRecipes = true;
		RecipeScroll = 0;
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::V))
	{
		SetCurrentDeckActive();
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
	{
		if (Focus == EDAFocus::Decks)
		{
			SetCurrentDeckActive();
		}
		else if (Focus == EDAFocus::Collection)
		{
			AddOrSwapSelectedCard();
		}
		else
		{
			RemoveSelectedDeckCard();
		}
		return;
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
	{
		HandleClickAtMouse();
	}
}

void FDADeckUI::HandleClickAtMouse()
{
	FVector2D Mouse;
	if (!GetMousePosition(Mouse))
	{
		return;
	}
	for (int32 Index = HitTargets.Num() - 1; Index >= 0; --Index)
	{
		if (HitTargets[Index].Contains(Mouse))
		{
			HandleHit(HitTargets[Index]);
			return;
		}
	}
}

void FDADeckUI::HandleHit(const FDAUIHitTarget& Hit)
{
	if (Hit.Action == TEXT("deck"))
	{
		DeckIndex = FMath::Clamp(Hit.Index, 0, FMath::Max(0, Decks.Num() - 1));
		if (Decks.IsValidIndex(DeckIndex))
		{
			CurrentDeckId = Decks[DeckIndex].Id;
			RefreshDeckCards();
		}
		Focus = EDAFocus::Decks;
		PlaySfx(TEXT("A_UIClick"), 0.25f);
	}
	else if (Hit.Action == TEXT("collection"))
	{
		CollectionSelection = Hit.Index;
		Focus = EDAFocus::Collection;
		PlaySfx(TEXT("A_UIClick"), 0.22f);
	}
	else if (Hit.Action == TEXT("deckmain") || Hit.Action == TEXT("deckextra"))
	{
		bDeckExtraSelection = Hit.Action == TEXT("deckextra");
		DeckCardSelection = Hit.Index;
		Focus = EDAFocus::DeckCards;
		PlaySfx(TEXT("A_UIClick"), 0.22f);
	}
	else if (Hit.Action == TEXT("filter"))
	{
		FilterMode = Hit.Index;
		CollectionSelection = 0;
		CollectionScroll = 0;
		RefreshCollection();
	}
	else if (Hit.Action == TEXT("sort"))
	{
		SortMode = Hit.Index;
		CollectionSelection = 0;
		CollectionScroll = 0;
		RefreshCollection();
	}
	else if (Hit.Action == TEXT("add"))
	{
		AddOrSwapSelectedCard();
	}
	else if (Hit.Action == TEXT("remove"))
	{
		RemoveSelectedDeckCard();
	}
	else if (Hit.Action == TEXT("swap"))
	{
		BeginSwap();
	}
	else if (Hit.Action == TEXT("set_active"))
	{
		SetCurrentDeckActive();
	}
	else if (Hit.Action == TEXT("new"))
	{
		CreateNewDeck();
	}
	else if (Hit.Action == TEXT("copy"))
	{
		CopyCurrentDeck();
	}
	else if (Hit.Action == TEXT("rename"))
	{
		BeginRename();
	}
	else if (Hit.Action == TEXT("erase"))
	{
		EraseCurrentDeck();
	}
	else if (Hit.Action == TEXT("recipes"))
	{
		bShowRecipes = true;
		RecipeScroll = 0;
	}
	else if (Hit.Action == TEXT("recipes_close"))
	{
		bShowRecipes = false;
	}
	else if (Hit.Action == TEXT("tab_main"))
	{
		bDeckExtraSelection = false;
		DeckCardSelection = 0;
	}
	else if (Hit.Action == TEXT("tab_extra"))
	{
		bDeckExtraSelection = true;
		DeckCardSelection = 0;
	}
	else if (Hit.Action == TEXT("extra"))
	{
		ToggleExtraMode();
	}
	else if (Hit.Action == TEXT("name_ok"))
	{
		CommitNameEdit();
	}
	else if (Hit.Action == TEXT("name_cancel"))
	{
		bEditingName = false;
		bRenameMode = false;
	}
	else if (Hit.Action == TEXT("erase_ok"))
	{
		UDADeckLogic* Logic = GetDeckLogic();
		FString Error;
		if (Logic && !EraseDeckId.IsEmpty() && Logic->EraseDeck(EraseDeckId, Error))
		{
			CurrentDeckId.Reset();
			DeckIndex = 0;
			RefreshAll(false);
			SetStatus(TEXT("Deck erased."), false);
		}
		else if (!Error.IsEmpty())
		{
			SetStatus(Error, true);
		}
		bConfirmErase = false;
	}
	else if (Hit.Action == TEXT("erase_cancel"))
	{
		bConfirmErase = false;
	}
	else if (Hit.Action == TEXT("close"))
	{
		Close();
	}
}

void FDADeckUI::Draw(UCanvas* InCanvas)
{
	if (!bOpen || !InCanvas)
	{
		return;
	}
	BeginFrame(InCanvas);
	DrawRect(FLinearColor(DeckInk.R, DeckInk.G, DeckInk.B, 0.96f), 0.f, 0.f, Canvas->ClipX, Canvas->ClipY);
	DrawHeader();
	DrawDeckSlots();
	DrawCollectionPanel();
	DrawDeckPanel();
	if (bShowRecipes)
	{
		DrawRecipesOverlay();
	}
	if (bEditingName)
	{
		DrawNameEditor();
	}
	if (bConfirmErase)
	{
		DrawEraseConfirm();
	}
	DrawFooter();
	DrawStatus();
}

void FDADeckUI::DrawHeader()
{
	const float CW = Canvas->ClipX;
	const float S = UIScale;
	const float H = 76.f * S;
	DrawRect(FLinearColor(0.004f, 0.009f, 0.02f, 0.96f), 0.f, 0.f, CW, H);
	DrawRect(DeckAlpha(DeckGold, 0.55f), 0.f, H - 2.f * S, CW, 2.f * S);
	DrawText(TEXT("DECK CONSTRUCTION"), 28.f * S, 10.f * S, DeckGold, 1.55f, false, GetFont(true));
	const FDAEDeck* Deck = GetCurrentDeck();
	if (Deck)
	{
		DrawText(Deck->Name, 28.f * S, 44.f * S, DeckPaper, 0.9f);
		DrawText(FString::Printf(TEXT("MAIN %d/%d   EXTRA %d/%d"), Deck->Main.Num(),
			GetDeckLogic() ? GetDeckLogic()->GetRules().MaxMain : 60, Deck->Extra.Num(),
			GetDeckLogic() ? GetDeckLogic()->GetRules().MaxExtra : 20),
			CW * 0.42f, 16.f * S, DeckMuted, 0.78f);
		const FString Validation = GetDeckLogic() ? GetDeckLogic()->GetDeckValidationMessage(*Deck) : FString();
		DrawText(Validation.IsEmpty() ? TEXT("LEGAL") : Validation,
			CW * 0.42f, 44.f * S, Validation.IsEmpty() ? DeckGreen : DeckRed, 0.72f);
		const FString ActiveId = GetDeckLogic() ? GetDeckLogic()->GetActiveDeckId() : FString();
		DrawText(FString::Printf(TEXT("ACTIVE: %s"), *ActiveId),
			CW - 280.f * S, 16.f * S, DeckMuted, 0.72f);
	}
	DrawText(TEXT("TAB focus   ENTER activate   N new   C copy   R rename   DEL erase   Q recipes"),
		CW - 760.f * S, 44.f * S, DeckMuted, 0.66f);
}

void FDADeckUI::DrawDeckSlots()
{
	const float S = UIScale;
	const float X = 20.f * S;
	const float Y = 90.f * S;
	const float W = Canvas->ClipX * 0.235f;
	const float H = Canvas->ClipY - Y - 50.f * S;
	DrawPanel(X, Y, W, H, DeckAlpha(DeckInk, 0.9f), DeckAlpha(DeckGold, 0.7f));
	DrawText(TEXT("DECKS"), X + 16.f * S, Y + 12.f * S, DeckGold, 0.95f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%d / %d"), Decks.Num(), GetDeckLogic() ? GetDeckLogic()->GetMaxPlayerDecks() : 24),
		X + W - 68.f * S, Y + 16.f * S, DeckMuted, 0.7f);

	const float RowH = 48.f * S;
	const float Top = Y + 46.f * S;
	const int32 Visible = FMath::Max(1, FMath::FloorToInt((H - 210.f * S) / RowH));
	if (DeckIndex < DeckScroll)
	{
		DeckScroll = DeckIndex;
	}
	else if (DeckIndex >= DeckScroll + Visible)
	{
		DeckScroll = DeckIndex - Visible + 1;
	}
	DeckScroll = FMath::Clamp(DeckScroll, 0, FMath::Max(0, Decks.Num() - Visible));

	const FString ActiveId = GetDeckLogic() ? GetDeckLogic()->GetActiveDeckId() : FString();
	for (int32 Index = DeckScroll; Index < Decks.Num() && Index < DeckScroll + Visible; ++Index)
	{
		const float RY = Top + (Index - DeckScroll) * RowH;
		const bool bSelected = Index == DeckIndex;
		const bool bActive = Decks[Index].Id == ActiveId;
		if (bSelected)
		{
			DrawRect(DeckAlpha(DeckGold, 0.2f), X + 8.f * S, RY, W - 16.f * S, RowH - 4.f * S);
			DrawRect(DeckGold, X + 8.f * S, RY, 4.f * S, RowH - 4.f * S);
		}
		DrawText(Decks[Index].Name, X + 20.f * S, RY + 5.f * S, bSelected ? DeckPaper : DeckMuted, 0.82f);
		DrawText(FString::Printf(TEXT("%d/%d%s"), Decks[Index].Main.Num(), Decks[Index].Extra.Num(),
			bActive ? TEXT("  ACTIVE") : TEXT("")), X + 20.f * S, RY + 25.f * S,
			bActive ? DeckGreen : DeckMuted, 0.64f);
		AddHit(TEXT("deck"), Index, X + 8.f * S, RY, W - 16.f * S, RowH - 4.f * S);
	}

	const float ButtonH = 30.f * S;
	const float ButtonY = Y + H - 140.f * S;
	static const TCHAR* Labels[] = { TEXT("NEW"), TEXT("COPY"), TEXT("RENAME"), TEXT("ERASE"), TEXT("SET ACTIVE"), TEXT("RECIPES") };
	static const TCHAR* Actions[] = { TEXT("new"), TEXT("copy"), TEXT("rename"), TEXT("erase"), TEXT("set_active"), TEXT("recipes") };
	for (int32 Index = 0; Index < UE_ARRAY_COUNT(Labels); ++Index)
	{
		const float BX = X + 12.f * S + (Index % 2) * (W - 24.f * S) * 0.5f;
		const float BY = ButtonY + (Index / 2) * (ButtonH + 6.f * S);
		const float BW = (W - 24.f * S) * 0.5f - 4.f * S;
		DrawRect(DeckAlpha(DeckMuted, 0.16f), BX, BY, BW, ButtonH);
		DrawText(Labels[Index], BX + 10.f * S, BY + 6.f * S, DeckPaper, 0.64f);
		AddHit(Actions[Index], INDEX_NONE, BX, BY, BW, ButtonH);
	}
	DrawText(TEXT("Q RECIPES / V ACTIVE"), X + 16.f * S, Y + H - 24.f * S, DeckMuted, 0.62f);
}

void FDADeckUI::DrawCollectionPanel()
{
	const float S = UIScale;
	const float X = 20.f * S + Canvas->ClipX * 0.235f + 14.f * S;
	const float Y = 90.f * S;
	const float W = Canvas->ClipX * 0.365f;
	const float H = Canvas->ClipY - Y - 50.f * S;
	DrawPanel(X, Y, W, H, DeckAlpha(DeckInk, 0.86f), DeckAlpha(DeckMuted, 0.4f));
	DrawText(TEXT("COLLECTION"), X + 16.f * S, Y + 12.f * S, DeckGold, 0.95f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%d cards"), Collection.Num()), X + W - 88.f * S, Y + 16.f * S, DeckMuted, 0.7f);

	const float ChipY = Y + 42.f * S;
	static const TCHAR* FilterLabels[] = { TEXT("ALL"), TEXT("MON"), TEXT("SPELL"), TEXT("TRAP") };
	static const TCHAR* SortLabels[] = { TEXT("ID"), TEXT("NAME"), TEXT("ATK"), TEXT("LVL") };
	const float ChipW = 62.f * S;
	for (int32 Index = 0; Index < 4; ++Index)
	{
		const float FX = X + 12.f * S + Index * ChipW;
		const bool bSel = Index == FilterMode;
		DrawRect(DeckAlpha(bSel ? DeckGold : DeckMuted, bSel ? 0.22f : 0.1f), FX, ChipY, ChipW - 3.f * S, 24.f * S);
		DrawText(FilterLabels[Index], FX + (ChipW - 3.f * S) * 0.5f, ChipY + 4.f * S,
			bSel ? DeckGold : DeckMuted, 0.6f, true);
		AddHit(TEXT("filter"), Index, FX, ChipY, ChipW - 3.f * S, 24.f * S);
	}
	DrawText(TEXT("SORT"), X + 12.f * S, ChipY + 32.f * S, DeckMuted, 0.6f);
	for (int32 Index = 0; Index < 4; ++Index)
	{
		const float SX = X + 58.f * S + Index * ChipW;
		const bool bSel = Index == SortMode;
		DrawRect(DeckAlpha(bSel ? DeckCyan : DeckMuted, bSel ? 0.22f : 0.1f), SX, ChipY + 28.f * S, ChipW - 3.f * S, 22.f * S);
		DrawText(SortLabels[Index], SX + (ChipW - 3.f * S) * 0.5f, ChipY + 31.f * S,
			bSel ? DeckCyan : DeckMuted, 0.58f, true);
		AddHit(TEXT("sort"), Index, SX, ChipY + 28.f * S, ChipW - 3.f * S, 22.f * S);
	}
	DrawText(TEXT("X EXTRA MODE"), X + W - 132.f * S, ChipY + 32.f * S,
		bExtraMode ? DeckGold : DeckMuted, 0.6f);
	AddHit(TEXT("extra"), INDEX_NONE, X + W - 138.f * S, ChipY + 24.f * S, 126.f * S, 30.f * S);

	const float RowH = 42.f * S;
	const float Top = ChipY + 64.f * S;
	const int32 Visible = FMath::Max(1, FMath::FloorToInt((H - 132.f * S) / RowH));
	if (CollectionSelection < CollectionScroll)
	{
		CollectionScroll = CollectionSelection;
	}
	else if (CollectionSelection >= CollectionScroll + Visible)
	{
		CollectionScroll = CollectionSelection - Visible + 1;
	}
	CollectionScroll = FMath::Clamp(CollectionScroll, 0, FMath::Max(0, Collection.Num() - Visible));

	for (int32 Index = CollectionScroll; Index < Collection.Num() && Index < CollectionScroll + Visible; ++Index)
	{
		DrawCardRow(Collection[Index], Index, X + 8.f * S, Top + (Index - CollectionScroll) * RowH,
			W - 16.f * S, RowH - 3.f * S, Index == CollectionSelection, false);
	}

	const float AddW = 190.f * S;
	const float AddH = 36.f * S;
	const float AddX = X + 12.f * S;
	const float AddY = Y + H - AddH - 12.f * S;
	DrawRect(DeckAlpha(DeckGold, 0.22f), AddX, AddY, AddW, AddH);
	DrawRect(DeckGold, AddX, AddY, 4.f * S, AddH);
	DrawText(PendingSwapCardId != 0 ? TEXT("[ENTER] COMPLETE SWAP") : TEXT("[ENTER] ADD / SWAP"),
		AddX + 14.f * S, AddY + 7.f * S, DeckPaper, 0.72f);
	AddHit(TEXT("add"), INDEX_NONE, AddX, AddY, AddW, AddH);
	DrawText(FString::Printf(TEXT("FILTER %s   SORT %s   OWNED ONLY"), *GetFilterLabel(), *GetSortLabel()),
		X + 220.f * S, AddY + 9.f * S, DeckMuted, 0.66f);
}

void FDADeckUI::DrawCardRow(int32 CardId, int32 Index, float X, float Y, float W, float H, bool bSelected, bool bDeckRow)
{
	const float S = UIScale;
	const FCardRecord* Card = FindCard(CardId);
	const FLinearColor Accent = bDeckRow ? DeckGold : (Card && Card->IsSpell() ? DeckCyan :
		(Card && Card->IsTrap() ? DeckPurple : DeckMuted));
	if (bSelected)
	{
		DrawRect(DeckAlpha(Accent, 0.2f), X, Y, W, H);
		DrawRect(Accent, X, Y, 4.f * S, H);
	}
	DrawText(Card ? Card->Name : FString::Printf(TEXT("Card %d"), CardId),
		X + 14.f * S, Y + 4.f * S, bSelected ? DeckPaper : DeckMuted, 0.76f);
	FString Right;
	if (bDeckRow)
	{
		Right = Card ? Card->CardType : FString();
	}
	else
	{
		const int32 Owned = GetInventory() ? GetInventory()->GetCount(CardId) : 0;
		Right = Card ? FString::Printf(TEXT("%s  x%d"), *Card->CardType, Owned) : FString::Printf(TEXT("x%d"), Owned);
	}
	const FVector2D Size = Measure(Right, 0.62f);
	DrawText(Right, X + W - Size.X - 12.f * S, Y + 12.f * S, DeckMuted, 0.62f);

	if (bDeckRow)
	{
		AddHit(bDeckExtraSelection ? TEXT("deckextra") : TEXT("deckmain"), Index, X, Y, W, H);
	}
	else
	{
		AddHit(TEXT("collection"), Index, X, Y, W, H);
	}
}

void FDADeckUI::DrawDeckPanel()
{
	const float S = UIScale;
	const float X = 20.f * S + Canvas->ClipX * 0.235f + 14.f * S + Canvas->ClipX * 0.365f + 14.f * S;
	const float Y = 90.f * S;
	const float W = Canvas->ClipX - X - 20.f * S;
	const float H = Canvas->ClipY - Y - 50.f * S;
	DrawPanel(X, Y, W, H, DeckAlpha(DeckInk, 0.9f), DeckAlpha(DeckGold, 0.7f));
	const FDAEDeck* Deck = GetCurrentDeck();
	DrawText(TEXT("CURRENT DECK"), X + 16.f * S, Y + 12.f * S, DeckGold, 0.95f, false, GetFont(true));
	DrawText(Deck ? Deck->Name : TEXT("No deck"), X + 16.f * S, Y + 40.f * S, DeckPaper, 0.85f);

	const float TabY = Y + 70.f * S;
	const float TabW = (W - 32.f * S) * 0.5f;
	const bool bMain = !bDeckExtraSelection;
	DrawRect(DeckAlpha(bMain ? DeckGold : DeckMuted, bMain ? 0.2f : 0.08f), X + 16.f * S, TabY, TabW - 4.f * S, 30.f * S);
	DrawRect(DeckAlpha(!bMain ? DeckCyan : DeckMuted, !bMain ? 0.2f : 0.08f), X + 16.f * S + TabW, TabY, TabW - 4.f * S, 30.f * S);
	DrawText(FString::Printf(TEXT("MAIN %d"), DeckMain.Num()), X + 16.f * S + TabW * 0.5f, TabY + 7.f * S,
		bMain ? DeckGold : DeckMuted, 0.72f, true);
	DrawText(FString::Printf(TEXT("EXTRA %d"), DeckExtra.Num()), X + 16.f * S + TabW * 1.5f, TabY + 7.f * S,
		!bMain ? DeckCyan : DeckMuted, 0.72f, true);
	AddHit(TEXT("tab_main"), INDEX_NONE, X + 16.f * S, TabY, TabW - 4.f * S, 30.f * S);
	AddHit(TEXT("tab_extra"), INDEX_NONE, X + 16.f * S + TabW, TabY, TabW - 4.f * S, 30.f * S);

	const TArray<int32>& List = bDeckExtraSelection ? DeckExtra : DeckMain;
	const float RowH = 40.f * S;
	const float Top = TabY + 44.f * S;
	const int32 Visible = FMath::Max(1, FMath::FloorToInt((H - 210.f * S) / RowH));
	if (DeckCardSelection < DeckCardScroll)
	{
		DeckCardScroll = DeckCardSelection;
	}
	else if (DeckCardSelection >= DeckCardScroll + Visible)
	{
		DeckCardScroll = DeckCardSelection - Visible + 1;
	}
	DeckCardScroll = FMath::Clamp(DeckCardScroll, 0, FMath::Max(0, List.Num() - Visible));

	for (int32 Index = DeckCardScroll; Index < List.Num() && Index < DeckCardScroll + Visible; ++Index)
	{
		DrawCardRow(List[Index], Index, X + 8.f * S, Top + (Index - DeckCardScroll) * RowH,
			W - 16.f * S, RowH - 3.f * S, Index == DeckCardSelection, true);
	}
	if (List.Num() == 0)
	{
		DrawText(bDeckExtraSelection ? TEXT("Extra deck is empty.") : TEXT("Main deck is empty."),
			X + 16.f * S, Top + 8.f * S, DeckMuted, 0.8f);
	}

	const float ButtonH = 34.f * S;
	const float ButtonY = Y + H - 92.f * S;
	const float ButtonW = (W - 44.f * S) * 0.5f;
	DrawRect(DeckAlpha(DeckMuted, 0.16f), X + 16.f * S, ButtonY, ButtonW, ButtonH);
	DrawText(TEXT("[ENTER] REMOVE"), X + 26.f * S, ButtonY + 8.f * S, DeckPaper, 0.7f);
	AddHit(TEXT("remove"), INDEX_NONE, X + 16.f * S, ButtonY, ButtonW, ButtonH);
	DrawRect(DeckAlpha(DeckCyan, 0.16f), X + 28.f * S + ButtonW, ButtonY, ButtonW, ButtonH);
	DrawText(TEXT("G / CLICK SWAP"), X + 38.f * S + ButtonW, ButtonY + 8.f * S, DeckCyan, 0.7f);
	AddHit(TEXT("swap"), INDEX_NONE, X + 28.f * S + ButtonW, ButtonY, ButtonW, ButtonH);

	const FString Validation = Deck && GetDeckLogic() ? GetDeckLogic()->GetDeckValidationMessage(*Deck) : FString();
	DrawText(Validation.IsEmpty() ? TEXT("DECK LEGAL") : Validation, X + 16.f * S, Y + H - 48.f * S,
		Validation.IsEmpty() ? DeckGreen : DeckRed, 0.72f);
	if (PendingSwapCardId != 0)
	{
		DrawText(FString::Printf(TEXT("SWAPPING OUT: %s"), *GetCardName(PendingSwapCardId)),
			X + 16.f * S, Y + H - 24.f * S, DeckGold, 0.68f);
	}
}

void FDADeckUI::DrawRecipesOverlay()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	HitTargets.Reset();
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), 0.f, 0.f, CW, CH);
	const float W = FMath::Min(CW * 0.6f, 980.f * S);
	const float H = FMath::Min(CH * 0.76f, 760.f * S);
	const float X = (CW - W) * 0.5f;
	const float Y = (CH - H) * 0.5f;
	DrawPanel(X, Y, W, H, DeckAlpha(DeckInk, 0.98f), DeckCyan);
	DrawText(TEXT("AVAILABLE FUSION RECIPES"), X + 26.f * S, Y + 18.f * S, DeckCyan, 1.25f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%d recipes from your current trunk"), Recipes.Num()),
		X + 26.f * S, Y + 52.f * S, DeckMuted, 0.72f);
	DrawRect(DeckAlpha(DeckCyan, 0.3f), X + 26.f * S, Y + 76.f * S, W - 52.f * S, 1.f * S);

	const float LineH = 24.f * S;
	const int32 Visible = FMath::Max(1, FMath::FloorToInt((H - 150.f * S) / LineH));
	RecipeScroll = FMath::Clamp(RecipeScroll, 0, FMath::Max(0, Recipes.Num() - Visible));
	float LY = Y + 90.f * S;
	for (int32 Index = RecipeScroll; Index < Recipes.Num() && Index < RecipeScroll + Visible; ++Index)
	{
		const FFusionRecipeDef& Recipe = Recipes[Index];
		FString Materials;
		for (int32 MaterialIndex = 0; MaterialIndex < Recipe.Materials.Num(); ++MaterialIndex)
		{
			if (MaterialIndex > 0)
			{
				Materials += TEXT(" + ");
			}
			Materials += GetCardName(Recipe.Materials[MaterialIndex]);
		}
		DrawText(FString::Printf(TEXT("%s  =  %s"), *Materials, *GetCardName(Recipe.Result)),
			X + 26.f * S, LY, DeckPaper, 0.72f);
		LY += LineH;
	}
	if (Recipes.Num() == 0)
	{
		DrawText(TEXT("No fusion recipe materials are owned yet."), X + 26.f * S, LY, DeckMuted, 0.8f);
	}
	DrawText(TEXT("UP / DOWN scroll      Q / F / ESC close"), X + 26.f * S, Y + H - 30.f * S, DeckMuted, 0.68f);
	AddHit(TEXT("recipes_close"), INDEX_NONE, 0.f, 0.f, CW, CH);
}

void FDADeckUI::DrawNameEditor()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	HitTargets.Reset();
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), 0.f, 0.f, CW, CH);
	const float W = 560.f * S;
	const float H = 220.f * S;
	const float X = (CW - W) * 0.5f;
	const float Y = (CH - H) * 0.5f;
	DrawPanel(X, Y, W, H, DeckAlpha(DeckInk, 0.98f), DeckGold);
	DrawText(bRenameMode ? TEXT("RENAME DECK") : TEXT("DECK NAME"), X + 24.f * S, Y + 18.f * S, DeckGold, 1.2f, false, GetFont(true));
	DrawText(NameBuffer.IsEmpty() ? TEXT("_") : NameBuffer, X + 24.f * S, Y + 72.f * S, DeckPaper, 1.1f);
	DrawRect(DeckAlpha(DeckGold, 0.5f), X + 24.f * S, Y + 108.f * S, W - 48.f * S, 1.f * S);
	DrawText(TEXT("Type letters/numbers/space. BACKSPACE edits. ENTER saves. ESC cancels."),
		X + 24.f * S, Y + 122.f * S, DeckMuted, 0.66f);
	const float BtnW = 150.f * S;
	const float BtnH = 34.f * S;
	DrawRect(DeckAlpha(DeckGold, 0.2f), X + 24.f * S, Y + H - 48.f * S, BtnW, BtnH);
	DrawText(TEXT("SAVE"), X + 62.f * S, Y + H - 40.f * S, DeckPaper, 0.75f);
	AddHit(TEXT("name_ok"), INDEX_NONE, X + 24.f * S, Y + H - 48.f * S, BtnW, BtnH);
	DrawRect(DeckAlpha(DeckMuted, 0.16f), X + 190.f * S, Y + H - 48.f * S, BtnW, BtnH);
	DrawText(TEXT("CANCEL"), X + 224.f * S, Y + H - 40.f * S, DeckMuted, 0.75f);
	AddHit(TEXT("name_cancel"), INDEX_NONE, X + 190.f * S, Y + H - 48.f * S, BtnW, BtnH);
}

void FDADeckUI::DrawEraseConfirm()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	HitTargets.Reset();
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), 0.f, 0.f, CW, CH);
	const float W = 560.f * S;
	const float H = 220.f * S;
	const float X = (CW - W) * 0.5f;
	const float Y = (CH - H) * 0.5f;
	DrawPanel(X, Y, W, H, DeckAlpha(DeckInk, 0.98f), DeckRed);
	DrawText(TEXT("ERASE DECK?"), X + 24.f * S, Y + 18.f * S, DeckRed, 1.2f, false, GetFont(true));
	const FDAEDeck* EraseDeck = Decks.FindByPredicate([this](const FDAEDeck& Deck)
	{
		return Deck.Id == EraseDeckId;
	});
	DrawText(FString::Printf(TEXT("%s will be removed."), EraseDeck ? *EraseDeck->Name : TEXT("This deck")),
		X + 24.f * S, Y + 64.f * S, DeckMuted, 0.8f);
	DrawText(TEXT("This cannot be undone."), X + 24.f * S, Y + 96.f * S, DeckMuted, 0.76f);
	const float BtnW = 150.f * S;
	const float BtnH = 34.f * S;
	DrawRect(DeckAlpha(DeckRed, 0.2f), X + 24.f * S, Y + H - 48.f * S, BtnW, BtnH);
	DrawText(TEXT("ERASE"), X + 60.f * S, Y + H - 40.f * S, DeckPaper, 0.75f);
	AddHit(TEXT("erase_ok"), INDEX_NONE, X + 24.f * S, Y + H - 48.f * S, BtnW, BtnH);
	DrawRect(DeckAlpha(DeckMuted, 0.16f), X + 190.f * S, Y + H - 48.f * S, BtnW, BtnH);
	DrawText(TEXT("CANCEL"), X + 224.f * S, Y + H - 40.f * S, DeckMuted, 0.75f);
	AddHit(TEXT("erase_cancel"), INDEX_NONE, X + 190.f * S, Y + H - 48.f * S, BtnW, BtnH);
}

void FDADeckUI::DrawFooter()
{
	const float S = UIScale;
	const float CH = Canvas->ClipY;
	const float H = 30.f * S;
	DrawRect(FLinearColor(0.004f, 0.008f, 0.018f, 0.94f), 0.f, CH - H, Canvas->ClipX, H);
	FString Hint;
	switch (Focus)
	{
	case EDAFocus::Decks:    Hint = TEXT("DECKS: UP/DOWN select   ENTER set active   N/C/R/DEL manage"); break;
	case EDAFocus::Collection: Hint = TEXT("COLLECTION: UP/DOWN select   ENTER add/swap   F filter   T sort   X extra"); break;
	case EDAFocus::DeckCards: Hint = TEXT("DECK: UP/DOWN select   LEFT/RIGHT main/extra   ENTER remove   G swap"); break;
	default: break;
	}
	DrawText(Hint, 20.f * S, CH - H + 7.f * S, DeckMuted, 0.66f);
	DrawText(TEXT("TAB focus   Q recipes   ESC close"), Canvas->ClipX - 300.f * S, CH - H + 7.f * S, DeckMuted, 0.66f);
}

void FDADeckUI::DrawStatus()
{
	if (StatusMessage.IsEmpty() || !Canvas)
	{
		return;
	}
	const float S = UIScale;
	const float W = FMath::Min(Canvas->ClipX * 0.62f, 900.f * S);
	const float H = 40.f * S;
	const float X = 20.f * S;
	const float Y = Canvas->ClipY - 84.f * S;
	DrawRect(DeckAlpha(DeckInk, 0.94f), X, Y, W, H);
	DrawRect(bStatusError ? DeckRed : DeckGold, X, Y, 4.f * S, H);
	FString Message = StatusMessage;
	while (Message.Len() > 4 && Measure(Message, 0.76f).X > W - 30.f * S)
	{
		Message = Message.LeftChop(4) + TEXT("...");
	}
	DrawText(Message, X + 14.f * S, Y + 8.f * S, bStatusError ? DeckRed : DeckPaper, 0.76f);
}
