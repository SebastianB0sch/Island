// Duel Academy Island - shared Canvas helpers for gameplay screens.

#include "DAUIScreen.h"

#include "CanvasItem.h"
#include "DAHUD.h"
#include "DAIslandSubsystem.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "RenderUtils.h"

FDAUIScreen::FDAUIScreen(ADAHUD* InOwner)
	: OwnerHUD(InOwner)
{
	PlayerOwner = InOwner ? InOwner->GetOwningPlayerController() : nullptr;
}

FDAUIScreen::~FDAUIScreen() = default;

void FDAUIScreen::BeginFrame(UCanvas* InCanvas)
{
	Canvas = InCanvas;
	PlayerOwner = OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr;
	UIScale = Canvas ? FMath::Clamp(Canvas->ClipY / 1080.f, 0.6f, 2.5f) : 1.f;
	HitTargets.Reset();
}

UWorld* FDAUIScreen::GetWorld() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetWorld() : nullptr;
}

UGameInstance* FDAUIScreen::GetGameInstance() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetGameInstance() : nullptr;
}

APlayerController* FDAUIScreen::GetPlayerController() const
{
	return OwnerHUD.IsValid() ? OwnerHUD->GetOwningPlayerController() : nullptr;
}

UFont* FDAUIScreen::GetFont(bool bLarge) const
{
	if (OwnerHUD.IsValid())
	{
		return bLarge ? OwnerHUD->GetBigFont() : OwnerHUD->GetSmallFont();
	}
	return bLarge ? (GEngine ? GEngine->GetLargeFont() : nullptr) : (GEngine ? GEngine->GetMediumFont() : nullptr);
}

bool FDAUIScreen::GetMousePosition(FVector2D& OutPosition) const
{
	APlayerController* PC = GetPlayerController();
	float X = -1.f;
	float Y = -1.f;
	if (!PC || !PC->GetMousePosition(X, Y))
	{
		return false;
	}
	OutPosition = FVector2D(X, Y);
	return true;
}

void FDAUIScreen::AddHit(const FString& Action, int32 Index, float X, float Y, float W, float H,
	const FString& Payload)
{
	FDAUIHitTarget Hit;
	Hit.Action = Action;
	Hit.Index = Index;
	Hit.X = X;
	Hit.Y = Y;
	Hit.W = W;
	Hit.H = H;
	Hit.Payload = Payload;
	HitTargets.Add(MoveTemp(Hit));
}

void FDAUIScreen::DrawRect(const FLinearColor& Color, float X, float Y, float W, float H)
{
	if (!Canvas || W <= 0.f || H <= 0.f)
	{
		return;
	}
	FCanvasTileItem Tile(FVector2D(X, Y), GWhiteTexture, FVector2D(W, H), Color);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void FDAUIScreen::DrawText(const FString& Str, float X, float Y, const FLinearColor& Color, float InScale,
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

void FDAUIScreen::DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent)
{
	DrawRect(Fill, X, Y, W, H);
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.95f), X, Y, 4.f * UIScale, H);
	DrawRect(FLinearColor(Accent.R, Accent.G, Accent.B, 0.45f), X, Y + H - 2.f * UIScale, W, 2.f * UIScale);
}

void FDAUIScreen::Diamond(const FVector2D& C, float R, const FLinearColor& Color)
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

FVector2D FDAUIScreen::Measure(const FString& Str, float InScale, UFont* Font) const
{
	const UFont* F = Font ? Font : GetFont(false);
	if (!F || Str.IsEmpty())
	{
		return FVector2D::ZeroVector;
	}
	const float K = InScale * UIScale;
	return FVector2D(F->GetStringSize(*Str) * K, F->GetStringHeightSize(*Str) * K);
}

TArray<FString> FDAUIScreen::WrapText(const FString& Str, float MaxWidth, float InScale, UFont* Font) const
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

void FDAUIScreen::PlaySfx(const TCHAR* SoundName, float Volume) const
{
	if (OwnerHUD.IsValid())
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(OwnerHUD.Get()))
		{
			Sub->PlayUISound(SoundName, Volume);
		}
	}
}
