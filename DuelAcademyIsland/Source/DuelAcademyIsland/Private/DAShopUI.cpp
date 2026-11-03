// Duel Academy Island - Dorothy's card shop implementation.

#include "DAShopUI.h"

#include "CanvasItem.h"
#include "DACardArtSubsystem.h"
#include "DAShopSubsystem.h"
#include "DAUIStyle.h"
#include "DuelAcademyIsland.h"
#include "Engine/Canvas.h"
#include "Engine/Texture2D.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "TextureResource.h"

FDAShopUI::FDAShopUI(ADAHUD* InOwner)
	: FDAUIScreen(InOwner)
{
}

FDAShopUI::~FDAShopUI() = default;

UDAShopSubsystem* FDAShopUI::GetShop() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UDAShopSubsystem>() : nullptr;
}

UCardArtSubsystem* FDAShopUI::GetCardArt() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UCardArtSubsystem>() : nullptr;
}

void FDAShopUI::Open()
{
	bOpen = true;
	Elapsed = 0.f;
	Panel = EPanel::Browse;
	CategoryIndex = 0;
	Selection = 0;
	ListScroll = 0;
	ConfirmSelection = 0;
	HoveredIndex = INDEX_NONE;
	ClearStatus();

	if (UDAShopSubsystem* Shop = GetShop())
	{
		Shop->RefreshUnlocks();
	}
	RefreshCatalogue(false);
	PlaySfx(TEXT("A_UIClick"), 0.45f);
	OpenPendingGrants();
}

void FDAShopUI::OpenPendingGrants()
{
	UDAShopSubsystem* Shop = GetShop();
	if (!Shop)
	{
		return;
	}
	const int32 DPBefore = Shop->GetDP();
	TArray<FDAEPackOpenResult> Grants;
	const int32 Opened = Shop->OpenPendingPackGrants(Grants);
	if (Opened <= 0 || Grants.Num() == 0)
	{
		return;
	}

	// Show every granted card on one reveal panel.
	LastPurchase = FDAEPurchaseResult();
	LastPurchase.bPurchased = true;
	LastPurchase.PackId = Grants[0].PackId;
	LastPurchase.DPBefore = DPBefore;
	LastPurchase.Open = Grants[0];
	LastPurchase.Open.Cards.Reset();
	LastPurchase.Open.DPFromDuplicates = 0;
	for (const FDAEPackOpenResult& Grant : Grants)
	{
		LastPurchase.Open.Cards.Append(Grant.Cards);
		LastPurchase.Open.DPFromDuplicates += Grant.DPFromDuplicates;
	}
	LastPurchase.DPAfter = Shop->GetDP();
	LastPurchase.Open.DPBefore = LastPurchase.DPBefore;
	LastPurchase.Open.DPAfter = LastPurchase.DPAfter;

	Elapsed = 0.f;
	Panel = EPanel::Reveal;
	SetStatus(FString::Printf(TEXT("Opened %d gift pack%s."), Opened, Opened == 1 ? TEXT("") : TEXT("s")), false);
	PlaySfx(TEXT("A_CardDraw"), 0.9f);
	RefreshCatalogue(true);
}

void FDAShopUI::Close()
{
	if (!bOpen)
	{
		return;
	}
	bOpen = false;
	Panel = EPanel::Browse;
	ConfirmSelection = 0;
	HoveredIndex = INDEX_NONE;
	HitTargets.Reset();
	OnClosed.Broadcast();
}

void FDAShopUI::RefreshCatalogue(bool bKeepSelection)
{
	FString PreviousPackId;
	if (bKeepSelection && Filtered.IsValidIndex(Selection) && Catalogue.IsValidIndex(Filtered[Selection]))
	{
		PreviousPackId = Catalogue[Filtered[Selection]].PackId;
	}

	Catalogue.Reset();
	if (UDAShopSubsystem* Shop = GetShop())
	{
		Catalogue = Shop->GetCatalogue();
	}
	HitTargets.Reset();

	Categories.Reset();
	Categories.Add(TEXT("ALL"));
	for (const FDAEPackView& Pack : Catalogue)
	{
		const FString Category = Pack.Category.IsEmpty() ? FString(TEXT("OTHER")) : Pack.Category;
		if (!Categories.Contains(Category))
		{
			Categories.Add(Category);
		}
	}
	if (Categories.Num() > 2)
	{
		Categories.Sort([](const FString& A, const FString& B) { return A.Compare(B) < 0; });
		Categories.Remove(TEXT("ALL"));
		Categories.Insert(TEXT("ALL"), 0);
	}

	CategoryIndex = FMath::Clamp(CategoryIndex, 0, FMath::Max(0, Categories.Num() - 1));
	RebuildFiltered();

	if (!PreviousPackId.IsEmpty())
	{
		for (int32 Index = 0; Index < Filtered.Num(); ++Index)
		{
			if (Catalogue.IsValidIndex(Filtered[Index]) && Catalogue[Filtered[Index]].PackId == PreviousPackId)
			{
				Selection = Index;
				return;
			}
		}
	}
	Selection = 0;
	ListScroll = 0;
}

void FDAShopUI::RebuildFiltered()
{
	Filtered.Reset();
	const FString Category = Categories.IsValidIndex(CategoryIndex) ? Categories[CategoryIndex] : FString();
	for (int32 Index = 0; Index < Catalogue.Num(); ++Index)
	{
		if (CategoryIndex == 0 || Category.IsEmpty() || Catalogue[Index].Category.Equals(Category, ESearchCase::IgnoreCase))
		{
			Filtered.Add(Index);
		}
	}
	Selection = FMath::Clamp(Selection, 0, FMath::Max(0, Filtered.Num() - 1));
	ListScroll = FMath::Clamp(ListScroll, 0, FMath::Max(0, Filtered.Num() - 1));
}

const FDAEPackView* FDAShopUI::GetSelectedPack() const
{
	if (Filtered.IsValidIndex(Selection) && Catalogue.IsValidIndex(Filtered[Selection]))
	{
		return &Catalogue[Filtered[Selection]];
	}
	return nullptr;
}

FString FDAShopUI::GetPackStatusLine(const FDAEPackView& Pack) const
{
	FString Line = Pack.StatusText.IsEmpty() ? (Pack.bCanPurchase ? TEXT("AVAILABLE") : FString(TEXT("UNAVAILABLE"))) : Pack.StatusText;
	if (Pack.NextAvailableDay >= 0 && !Pack.bCanPurchase)
	{
		Line += FString::Printf(TEXT("   NEXT DAY %d"), Pack.NextAvailableDay);
	}
	return Line;
}

FString FDAShopUI::GetCategoryLine() const
{
	return Categories.IsValidIndex(CategoryIndex) ? Categories[CategoryIndex] : FString(TEXT("ALL"));
}

void FDAShopUI::MoveSelection(int32 Delta)
{
	const int32 Count = Filtered.Num();
	if (Count <= 0)
	{
		Selection = 0;
		return;
	}
	const int32 NewSelection = FMath::Clamp(Selection + Delta, 0, Count - 1);
	if (NewSelection != Selection)
	{
		Selection = NewSelection;
		PlaySfx(TEXT("A_UIClick"), 0.25f);
	}
}

void FDAShopUI::ChangeCategory(int32 Delta)
{
	const int32 Count = Categories.Num();
	if (Count <= 0)
	{
		return;
	}
	CategoryIndex = ((CategoryIndex + Delta) % Count + Count) % Count;
	Selection = 0;
	ListScroll = 0;
	RebuildFiltered();
	HitTargets.Reset();
	PlaySfx(TEXT("A_UIClick"), 0.3f);
}

void FDAShopUI::OpenConfirm()
{
	const FDAEPackView* Pack = GetSelectedPack();
	if (!Pack)
	{
		return;
	}
	if (!Pack->bCanPurchase)
	{
		SetStatus(Pack->StatusText.IsEmpty() ? Pack->UnlockReason : Pack->StatusText, true);
		return;
	}
	ConfirmSelection = 0;
	Panel = EPanel::Confirm;
	HitTargets.Reset();
	PlaySfx(TEXT("A_UIClick"), 0.4f);
}

void FDAShopUI::DoPurchase()
{
	UDAShopSubsystem* Shop = GetShop();
	const FDAEPackView* Pack = GetSelectedPack();
	if (!Shop || !Pack)
	{
		SetStatus(TEXT("The card shop is unavailable."), true);
		Panel = EPanel::Browse;
		return;
	}

	const FString PackId = Pack->PackId;
	LastPurchase = FDAEPurchaseResult();
	// Seed 0 lets UDAInventorySubsystem::ResolveSeed pick a 64-bit cycle-counter
	// seed; FMath::Rand() is only 15 bits on MSVC (32,768 possible reveals per pack).
	const bool bPurchased = Shop->PurchasePack(PackId, 0, LastPurchase);
	if (bPurchased)
	{
		Elapsed = 0.f;
		Panel = EPanel::Reveal;
		SetStatus(FString::Printf(TEXT("Opened %s."), *PackId), false);
		PlaySfx(TEXT("A_CardDraw"), 0.9f);
		RefreshCatalogue(true);
	}
	else
	{
		Panel = EPanel::Browse;
		SetStatus(LastPurchase.ErrorMessage.IsEmpty() ? TEXT("Purchase failed.") : LastPurchase.ErrorMessage, true);
		PlaySfx(TEXT("A_UIClick"), 0.35f);
	}
}

void FDAShopUI::Update(float DeltaSeconds)
{
	if (!bOpen)
	{
		return;
	}
	PlayerOwner = GetPlayerController();
	Elapsed += DeltaSeconds;
	TickStatus(DeltaSeconds);

	HoveredIndex = INDEX_NONE;
	FVector2D Mouse;
	if (GetMousePosition(Mouse))
	{
		for (const FDAUIHitTarget& Hit : HitTargets)
		{
			if (Hit.Action == TEXT("pack") && Hit.Contains(Mouse))
			{
				HoveredIndex = Hit.Index;
			}
		}
	}

	if (!PlayerOwner)
	{
		return;
	}

	if (Panel == EPanel::Reveal)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Enter)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			Panel = EPanel::Browse;
			PlaySfx(TEXT("A_UIClick"), 0.35f);
		}
		return;
	}

	if (Panel == EPanel::Confirm)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Up) || PlayerOwner->WasInputKeyJustPressed(EKeys::Down)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Left) || PlayerOwner->WasInputKeyJustPressed(EKeys::Right)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::W) || PlayerOwner->WasInputKeyJustPressed(EKeys::S))
		{
			ConfirmSelection = ConfirmSelection == 0 ? 1 : 0;
			PlaySfx(TEXT("A_UIClick"), 0.25f);
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
		{
			Panel = EPanel::Browse;
			return;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
		{
			if (ConfirmSelection == 0)
			{
				DoPurchase();
			}
			else
			{
				Panel = EPanel::Browse;
			}
			return;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}

	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::P)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
	{
		Close();
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
	// U8: wheel scrolls the pack list exactly like the PDA's list, so the
	// ^/v row indicators above the list stop being decoration.
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::MouseScrollUp))
	{
		MoveSelection(-1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::MouseScrollDown))
	{
		MoveSelection(1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Left) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_LeftShoulder)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Q))
	{
		ChangeCategory(-1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Right) || PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_RightShoulder)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::E))
	{
		ChangeCategory(1);
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
	{
		OpenConfirm();
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
	{
		HandleClickAtMouse();
	}
}

void FDAShopUI::HandleClickAtMouse()
{
	FDAUIHitTarget Hit;
	if (FindHitAtMouse(Hit))
	{
		HandleHit(Hit);
	}
}

void FDAShopUI::HandleHit(const FDAUIHitTarget& Hit)
{
	if (Hit.Action == TEXT("pack"))
	{
		Selection = Filtered.Num() > 0 ? FMath::Clamp(Hit.Index, 0, Filtered.Num() - 1) : 0;
		PlaySfx(TEXT("A_UIClick"), 0.25f);
	}
	else if (Hit.Action == TEXT("category"))
	{
		CategoryIndex = Categories.Num() > 0
			? FMath::Clamp(Hit.Index, 0, Categories.Num() - 1) : 0;
		Selection = 0;
		ListScroll = 0;
		RebuildFiltered();
		PlaySfx(TEXT("A_UIClick"), 0.3f);
	}
	else if (Hit.Action == TEXT("buy"))
	{
		OpenConfirm();
	}
	else if (Hit.Action == TEXT("confirm"))
	{
		if (Hit.Index == 0)
		{
			DoPurchase();
		}
		else
		{
			Panel = EPanel::Browse;
		}
	}
	else if (Hit.Action == TEXT("cancel") || Hit.Action == TEXT("reveal_close"))
	{
		Panel = EPanel::Browse;
	}
	else if (Hit.Action == TEXT("close"))
	{
		Close();
	}
}

void FDAShopUI::Draw(UCanvas* InCanvas)
{
	if (!bOpen || !InCanvas)
	{
		return;
	}
	BeginFrame(InCanvas);
	DrawHeader();
	if (Panel == EPanel::Reveal)
	{
		DrawReveal();
	}
	else
	{
		DrawBrowse();
		if (Panel == EPanel::Confirm)
		{
			HitTargets.Reset();
			DrawConfirm();
		}
	}
	DrawFooter();
	DrawStatus();
}

void FDAShopUI::DrawHeader()
{
	const float CW = Canvas->ClipX;
	const float S = UIScale;
	const float H = 84.f * S;
	DrawRect(FLinearColor(DAUIStyle::Ink.R, DAUIStyle::Ink.G, DAUIStyle::Ink.B, 0.96f), 0.f, 0.f, CW, H);
	DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Gold, 0.6f), 0.f, H - 2.f * S, CW, 2.f * S);
	DrawText(TEXT("DOROTHY'S CARD SHOP"), 32.f * S, 12.f * S, DAUIStyle::Gold, 1.65f, false, GetFont(true));
	DrawText(TEXT("BOOSTER PACKS  -  A06 INVENTORY + DP"), 34.f * S, 52.f * S, DAUIStyle::Muted, 0.72f);

	UDAShopSubsystem* Shop = GetShop();
	const FString DP = FString::Printf(TEXT("DP %d"), Shop ? Shop->GetDP() : 0);
	const FVector2D Size = Measure(DP, 1.15f, GetFont(true));
	DrawText(DP, CW - 32.f * S - Size.X, 18.f * S, DAUIStyle::Gold, 1.15f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("CATEGORY  %s"), *GetCategoryLine()),
		CW - 300.f * S, 54.f * S, DAUIStyle::Muted, 0.7f);
}

void FDAShopUI::DrawBrowse()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float Top = 104.f * S;
	const float Margin = 32.f * S;
	const float TabH = 34.f * S;
	const float TabW = FMath::Min(160.f * S, (CW - Margin * 2.f) / FMath::Max(1, Categories.Num()));
	for (int32 Index = 0; Index < Categories.Num(); ++Index)
	{
		const float X = Margin + Index * TabW;
		const bool bSelected = Index == CategoryIndex;
		if (bSelected)
		{
			DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Gold, 0.22f), X, Top, TabW - 6.f * S, TabH);
			DrawRect(DAUIStyle::Gold, X, Top + TabH - 3.f * S, TabW - 6.f * S, 3.f * S);
		}
		DrawText(Categories[Index], X + TabW * 0.5f, Top + 8.f * S,
			bSelected ? DAUIStyle::Gold : DAUIStyle::Muted, 0.72f, true);
		AddHit(TEXT("category"), Index, X, Top, TabW - 6.f * S, TabH);
	}

	const float ContentY = Top + TabH + 16.f * S;
	const float ContentH = CH - ContentY - 58.f * S;
	const float ListW = (CW - Margin * 2.f) * 0.43f;
	const float ListX = Margin;
	const float DetailX = ListX + ListW + 18.f * S;
	const float DetailW = CW - DetailX - Margin;

	DrawPanel(ListX, ContentY, ListW, ContentH, DAUIStyle::WithAlpha(DAUIStyle::Ink, 0.9f), DAUIStyle::WithAlpha(DAUIStyle::Gold, 0.7f));
	DrawText(TEXT("PACKS"), ListX + 18.f * S, ContentY + 12.f * S, DAUIStyle::Gold, 0.95f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%d in %s"), Filtered.Num(), *GetCategoryLine()),
		ListX + 18.f * S, ContentY + 36.f * S, DAUIStyle::Muted, 0.7f);

	const float RowH = 56.f * S;
	const float RowsTop = ContentY + 58.f * S;
	const int32 VisibleRows = FMath::Max(1, FMath::FloorToInt((ContentH - 66.f * S) / RowH));
	KeepRowVisible(Selection, Filtered.Num(), VisibleRows, ListScroll);

	for (int32 Index = ListScroll; Index < Filtered.Num() && Index < ListScroll + VisibleRows; ++Index)
	{
		if (!Catalogue.IsValidIndex(Filtered[Index]))
		{
			continue;
		}
		DrawPackRow(Catalogue[Filtered[Index]], Index, ListX + 10.f * S,
			RowsTop + (Index - ListScroll) * RowH, ListW - 20.f * S, RowH - 4.f * S, Index == Selection);
	}

	if (ListScroll > 0)
	{
		DrawText(TEXT("^"), ListX + ListW * 0.5f, ContentY + 48.f * S, DAUIStyle::Muted, 0.7f, true);
	}
	if (ListScroll + VisibleRows < Filtered.Num())
	{
		DrawText(TEXT("v"), ListX + ListW * 0.5f, ContentY + ContentH - 24.f * S, DAUIStyle::Muted, 0.7f, true);
	}

	DrawPanel(DetailX, ContentY, DetailW, ContentH, DAUIStyle::WithAlpha(DAUIStyle::Ink, 0.85f), DAUIStyle::WithAlpha(DAUIStyle::Muted, 0.4f));
	const FDAEPackView* Pack = GetSelectedPack();
	if (!Pack)
	{
		DrawText(TEXT("No booster packs in this category."), DetailX + 24.f * S, ContentY + 28.f * S, DAUIStyle::Muted, 0.9f);
		return;
	}

	DrawText(Pack->Name, DetailX + 24.f * S, ContentY + 22.f * S, DAUIStyle::Gold, 1.35f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%s  -  %d CARDS  -  %d DP"), *Pack->Category, Pack->PackSize, Pack->Price),
		DetailX + 24.f * S, ContentY + 62.f * S, DAUIStyle::Muted, 0.78f);
	DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Gold, 0.35f), DetailX + 24.f * S, ContentY + 92.f * S, DetailW - 48.f * S, 1.f * S);

	float Y = ContentY + 108.f * S;
	for (const FString& Line : WrapText(Pack->UnlockReason.IsEmpty() ? TEXT("Available.") : Pack->UnlockReason,
		DetailW - 48.f * S, 0.82f))
	{
		DrawText(Line, DetailX + 24.f * S, Y, DAUIStyle::Paper, 0.82f);
		Y += Measure(TEXT("Ag"), 0.82f).Y + 3.f * S;
	}
	Y += 10.f * S;
	DrawText(GetPackStatusLine(*Pack), DetailX + 24.f * S, Y,
		Pack->bCanPurchase ? DAUIStyle::Green : DAUIStyle::Red, 0.82f);
	Y += 28.f * S;
	DrawText(FString::Printf(TEXT("RESTOCK %d DAYS   LAST PURCHASE DAY %d   NEXT DAY %d"),
		Pack->RestockDays, Pack->LastPurchaseDay, Pack->NextAvailableDay),
		DetailX + 24.f * S, Y, DAUIStyle::Muted, 0.72f);

	const float ButtonW = FMath::Min(260.f * S, DetailW - 48.f * S);
	const float ButtonH = 48.f * S;
	const float ButtonX = DetailX + 24.f * S;
	const float ButtonY = ContentY + ContentH - ButtonH - 18.f * S;
	DrawRect(DAUIStyle::WithAlpha(Pack->bCanPurchase ? DAUIStyle::Gold : DAUIStyle::Muted, 0.2f), ButtonX, ButtonY, ButtonW, ButtonH);
	DrawRect(Pack->bCanPurchase ? DAUIStyle::Gold : DAUIStyle::Muted, ButtonX, ButtonY, 4.f * S, ButtonH);
	DrawText(Pack->bCanPurchase ? TEXT("[ENTER] BUY PACK") : TEXT("LOCKED"),
		ButtonX + 16.f * S, ButtonY + 12.f * S, Pack->bCanPurchase ? DAUIStyle::Paper : DAUIStyle::Muted, 0.9f);
	AddHit(TEXT("buy"), INDEX_NONE, ButtonX, ButtonY, ButtonW, ButtonH);

	const float CloseW = 110.f * S;
	DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Muted, 0.16f), DetailX + DetailW - CloseW - 24.f * S, ButtonY, CloseW, ButtonH);
	DrawText(TEXT("CLOSE"), DetailX + DetailW - CloseW, ButtonY + 12.f * S, DAUIStyle::Muted, 0.82f);
	AddHit(TEXT("close"), INDEX_NONE, DetailX + DetailW - CloseW - 24.f * S, ButtonY, CloseW, ButtonH);
}

void FDAShopUI::DrawPackRow(const FDAEPackView& Pack, int32 FilteredIndex, float X, float Y, float W, float H, bool bSelected)
{
	const float S = UIScale;
	const bool bHovered = FilteredIndex == HoveredIndex;
	const FLinearColor Accent = Pack.bCanPurchase ? DAUIStyle::Gold : DAUIStyle::Muted;
	if (bSelected || bHovered)
	{
		DrawRect(DAUIStyle::WithAlpha(Accent, bSelected ? 0.2f : 0.08f), X, Y, W, H);
		DrawRect(Accent, X, Y, 4.f * S, H);
	}
	DrawText(Pack.Name, X + 16.f * S, Y + 6.f * S,
		Pack.bCanPurchase ? DAUIStyle::Paper : DAUIStyle::Muted, 0.85f);
	const FString Price = FString::Printf(TEXT("%d DP"), Pack.Price);
	const FVector2D PriceSize = Measure(Price, 0.8f);
	DrawText(Ellipsize(Pack.Name, W - PriceSize.X - 40.f * S, 0.85f), X + 16.f * S, Y + 6.f * S,
		Pack.bCanPurchase ? ShopPaper : ShopMuted, 0.85f);
	DrawText(Price, X + W - PriceSize.X - 12.f * S, Y + 6.f * S,
		Pack.bCanPurchase ? DAUIStyle::Gold : DAUIStyle::Muted, 0.8f);
	DrawText(GetPackStatusLine(Pack), X + 16.f * S, Y + 28.f * S,
		Pack.bCanPurchase ? DAUIStyle::Green : DAUIStyle::Muted, 0.66f);
	AddHit(TEXT("pack"), FilteredIndex, X, Y, W, H);
}

void FDAShopUI::DrawConfirm()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.6f), 0.f, 0.f, CW, CH);

	const FDAEPackView* Pack = GetSelectedPack();
	const float W = FMath::Min(CW * 0.48f, 820.f * S);
	const float H = 320.f * S;
	const float X = (CW - W) * 0.5f;
	const float Y = (CH - H) * 0.5f;
	DrawPanel(X, Y, W, H, DAUIStyle::WithAlpha(DAUIStyle::Ink, 0.97f), DAUIStyle::Gold);
	DrawText(TEXT("CONFIRM PURCHASE"), X + 28.f * S, Y + 20.f * S, DAUIStyle::Gold, 1.35f, false, GetFont(true));
	DrawText(Pack ? Pack->Name : TEXT("Pack"), X + 30.f * S, Y + 68.f * S, DAUIStyle::Paper, 1.05f);
	UDAShopSubsystem* Shop = GetShop();
	const int32 DP = Shop ? Shop->GetDP() : 0;
	const int32 Price = Pack ? Pack->Price : 0;
	DrawText(FString::Printf(TEXT("PRICE %d DP      BALANCE %d DP      AFTER %d DP"), Price, DP, DP - Price),
		X + 30.f * S, Y + 104.f * S, DP >= Price ? DAUIStyle::Muted : DAUIStyle::Red, 0.82f);
	DrawText(TEXT("The pack will be opened immediately and cards added to your trunk."),
		X + 30.f * S, Y + 138.f * S, DAUIStyle::Muted, 0.76f);

	AddHit(TEXT("cancel"), INDEX_NONE, X, Y, W, H);
	const float ButtonW = W - 60.f * S;
	const float ButtonH = 48.f * S;
	for (int32 Index = 0; Index < 2; ++Index)
	{
		const bool bSelected = Index == ConfirmSelection;
		const float BY = Y + H - 120.f * S + Index * (ButtonH + 8.f * S);
		const FLinearColor Accent = Index == 0 ? DAUIStyle::Gold : DAUIStyle::Muted;
		if (bSelected)
		{
			DrawRect(DAUIStyle::WithAlpha(Accent, 0.2f), X + 30.f * S, BY, ButtonW, ButtonH);
			DrawRect(Accent, X + 30.f * S, BY, 4.f * S, ButtonH);
		}
		DrawText(Index == 0 ? TEXT("BUY PACK") : TEXT("CANCEL"), X + 48.f * S, BY + 12.f * S,
			bSelected ? DAUIStyle::Paper : DAUIStyle::Muted, 0.95f);
		AddHit(TEXT("confirm"), Index, X + 30.f * S, BY, ButtonW, ButtonH);
	}
}

void FDAShopUI::DrawReveal()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const int32 Count = LastPurchase.Open.Cards.Num();
	DrawText(TEXT("PACK OPENED"), CW * 0.5f, 112.f * S, DAUIStyle::Gold, 1.8f, true, GetFont(true));
	DrawText(FString::Printf(TEXT("DUPLICATE DP +%d      DP %d -> %d"),
		LastPurchase.Open.DPFromDuplicates, LastPurchase.Open.DPBefore, LastPurchase.Open.DPAfter),
		CW * 0.5f, 158.f * S, DAUIStyle::Muted, 0.85f, true);

	const float Margin = 32.f * S;
	const float CardW = FMath::Max(0.f, FMath::Min((CW - Margin * 2.f - 4.f * 12.f * S) / FMath::Max(1, Count), 240.f * S));
	const float CardH = FMath::Min(CH * 0.56f, 430.f * S);
	const float TotalW = Count * CardW + FMath::Max(0, Count - 1) * 12.f * S;
	float X = (CW - TotalW) * 0.5f;
	const float Y = 210.f * S;
	if (Count == 0)
	{
		DrawText(TEXT("No cards were added to the trunk."), CW * 0.5f, Y + 40.f * S,
			ShopMuted, 0.9f, true);
	}
	else if (CardW > 0.f && CardH > 0.f)
	{
		for (int32 Index = 0; Index < Count; ++Index)
		{
			DrawRevealCard(LastPurchase.Open.Cards[Index], Index, X, Y, CardW, CardH);
			X += CardW + 12.f * S;
		}
	}

	const float ButtonW = 240.f * S;
	const float ButtonH = 46.f * S;
	const float ButtonX = (CW - ButtonW) * 0.5f;
	const float ButtonY = CH - 92.f * S;
	DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Gold, 0.2f), ButtonX, ButtonY, ButtonW, ButtonH);
	DrawRect(DAUIStyle::Gold, ButtonX, ButtonY, 4.f * S, ButtonH);
	DrawText(TEXT("[ENTER] CONTINUE"), ButtonX + 40.f * S, ButtonY + 11.f * S, DAUIStyle::Paper, 0.92f);
	AddHit(TEXT("reveal_close"), INDEX_NONE, 0.f, 0.f, CW, CH);
}

void FDAShopUI::DrawRevealCard(const FDAEPackCardReveal& Card, int32 Index, float X, float Y, float W, float H)
{
	const float S = UIScale;
	if (W <= 0.f || H <= 0.f)
	{
		return;
	}
	const float Delay = Index * 0.08f;
	const float Alpha = FMath::Clamp((Elapsed - Delay) / 0.22f, 0.f, 1.f);
	const FLinearColor Rarity = RarityColor(Card.Rarity);

	DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Ink, 0.92f * Alpha), X, Y, W, H);
	DrawRect(DAUIStyle::WithAlpha(Rarity, 0.9f * Alpha), X, Y, W, 3.f * S);
	DrawRect(DAUIStyle::WithAlpha(Rarity, 0.9f * Alpha), X, Y + H - 3.f * S, W, 3.f * S);

	const float ArtH = H * 0.48f;
	if (UCardArtSubsystem* Art = GetCardArt())
	{
		if (UTexture2D* Texture = Art->GetCardArt(Card.CardId); Texture && Texture->GetResource())
		{
			FCanvasTileItem Tile(FVector2D(X + 10.f * S, Y + 12.f * S), Texture->GetResource(),
				FVector2D(W - 20.f * S, ArtH), FLinearColor(1.f, 1.f, 1.f, Alpha));
			Tile.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Tile);
		}
		else
		{
			DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Muted, 0.12f * Alpha), X + 10.f * S, Y + 12.f * S, W - 20.f * S, ArtH);
			DrawText(TEXT("NO ART"), X + W * 0.5f, Y + 12.f * S + ArtH * 0.42f, DAUIStyle::Muted, 0.7f, true);
		}
	}

	float TextY = Y + ArtH + 22.f * S;
	DrawText(Card.Name, X + 12.f * S, TextY, DAUIStyle::WithAlpha(DAUIStyle::Paper, Alpha), 0.8f);
	TextY += 24.f * S;
	DrawText(DAEconomy::RarityToString(Card.Rarity), X + 12.f * S, TextY, DAUIStyle::WithAlpha(Rarity, Alpha), 0.68f);
	TextY += 22.f * S;
	const FString State = Card.bDuplicate ? FString(TEXT("DUPLICATE")) : FString(TEXT("NEW"));
	DrawText(State, X + 12.f * S, TextY, DAUIStyle::WithAlpha(Card.bDuplicate ? DAUIStyle::Muted : DAUIStyle::Green, Alpha), 0.7f);
	TextY += 22.f * S;
	DrawText(FString::Printf(TEXT("OWNED %d -> %d"), Card.OwnedBefore, Card.OwnedAfter),
		X + 12.f * S, TextY, DAUIStyle::WithAlpha(DAUIStyle::Muted, Alpha), 0.66f);
	if (Card.DuplicateDP > 0)
	{
		TextY += 20.f * S;
		DrawText(FString::Printf(TEXT("+%d DP"), Card.DuplicateDP), X + 12.f * S, TextY,
			DAUIStyle::WithAlpha(DAUIStyle::Gold, Alpha), 0.72f);
	}
}

FLinearColor FDAShopUI::RarityColor(EDAECardRarity Rarity) const
{
	switch (Rarity)
	{
	case EDAECardRarity::Rare:       return DAUIStyle::Cyan;
	case EDAECardRarity::SuperRare:  return DAUIStyle::Purple;
	case EDAECardRarity::UltraRare:  return DAUIStyle::Gold;
	case EDAECardRarity::SecretRare: return DAUIStyle::Red;
	case EDAECardRarity::Common:
	default:                         return DAUIStyle::Muted;
	}
}

void FDAShopUI::DrawFooter()
{
	const float CW = Canvas->ClipX;
	const float CH = Canvas->ClipY;
	const float S = UIScale;
	const float H = 32.f * S;
	DrawRect(FLinearColor(0.004f, 0.008f, 0.018f, 0.94f), 0.f, CH - H, CW, H);
	DrawText(TEXT("UP / DOWN browse      LEFT / RIGHT category      ENTER buy      ESC close"),
		24.f * S, CH - H + 8.f * S, DAUIStyle::Muted, 0.7f);
}

void FDAShopUI::DrawStatus()
{
	if (StatusText.IsEmpty() || !Canvas)
	{
		return;
	}
	const float S = UIScale;
	const float W = FMath::Min(Canvas->ClipX * 0.6f, 900.f * S);
	const float H = 42.f * S;
	const float X = 24.f * S;
	const float Y = Canvas->ClipY - 94.f * S;
	const FLinearColor Accent = bStatusIsError ? DAUIStyle::Red : DAUIStyle::Gold;
	DrawRect(DAUIStyle::WithAlpha(DAUIStyle::Ink, 0.94f), X, Y, W, H);
	DrawRect(Accent, X, Y, 4.f * S, H);
	DrawText(TruncateToWidth(StatusText, W - 32.f * S, 0.8f), X + 16.f * S, Y + 9.f * S,
		bStatusIsError ? DAUIStyle::Red : DAUIStyle::Paper, 0.8f);
}
