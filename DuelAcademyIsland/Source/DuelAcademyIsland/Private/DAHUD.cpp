// Duel Academy Island - canvas HUD.

#include "DAHUD.h"

#include "CanvasItem.h"
#include "DAInteractableInterface.h"
#include "DAIslandManager.h"
#include "DAIslandSubsystem.h"
#include "DALocationVolume.h"
#include "DAStudentCharacter.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/Texture2D.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "RenderUtils.h"
#include "TextureResource.h"

namespace
{
	const FLinearColor Gold(1.f, 0.78f, 0.25f);
	const FLinearColor Ink(0.02f, 0.03f, 0.06f);
	const FLinearColor Paper(0.95f, 0.95f, 0.97f);

	FLinearColor WithAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}
}

ADAHUD::ADAHUD()
{
}

void ADAHUD::BeginPlay()
{
	Super::BeginPlay();
	SmallFont = GEngine ? GEngine->GetMediumFont() : nullptr;
	BigFont = GEngine ? GEngine->GetLargeFont() : nullptr;
	StartTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
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
	DrawRect(WithAlpha(Ink, Alpha), X, Y, W, H);
	DrawRect(WithAlpha(Accent, 0.95f), X, Y, 5.f * S(), H);
	DrawRect(WithAlpha(Accent, 0.5f), X, Y + H - 2.f * S(), W, 2.f * S());
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
	DrawPrompt();
	DrawIntro(Time - StartTime);
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
	Text(TEXT("DUEL ACADEMY"), CX, Y, WithAlpha(Gold, A), 3.2f, true, BigFont);
	Text(TEXT("ISLAND"), CX, Y + 92.f * S(), WithAlpha(Paper, A), 1.8f, true, BigFont);
	Text(TEXT("Explore the island  -  M: map & fast travel  -  E: interact  -  F1: controls"), CX, Y + 150.f * S(), WithAlpha(Paper, A * 0.9f), 1.0f, true);
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
	DrawRect(WithAlpha(Zone->ThemeColor, 0.95f * A), CX - W * 0.5f, Y - 18.f * S(), W, 4.f * S());
	DrawRect(WithAlpha(Zone->ThemeColor, 0.95f * A), CX - W * 0.5f, Y + 118.f * S(), W, 4.f * S());
	if (Sub->WasFirstVisit())
	{
		Text(TEXT("NEW LOCATION DISCOVERED"), CX, Y - 8.f * S(), WithAlpha(Gold, A), 0.9f, true);
	}
	Text(Name, CX, Y + 14.f * S(), WithAlpha(Paper, A), 2.2f, true, BigFont);
	Text(Zone->Subtitle, CX, Y + 80.f * S(), WithAlpha(Zone->ThemeColor, A), 1.1f, true);
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
			Text(Mk.Label, CX + D * PxPerDeg, Y + 6.f * S(), bMajor ? (Mk.Yaw == -90.f ? Gold : Paper) : WithAlpha(Paper, 0.6f), bMajor ? 1.0f : 0.75f, true);
		}
	}
	for (int32 Deg = -180; Deg < 180; Deg += 15)
	{
		const float D = FMath::FindDeltaAngleDegrees(Yaw, static_cast<float>(Deg));
		if (FMath::Abs(D) < 88.f && Deg % 45 != 0)
		{
			DrawRect(WithAlpha(Paper, 0.5f), CX + D * PxPerDeg - 1.f, Y + 22.f * S(), 2.f, 8.f * S());
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
				Diamond(FVector2D(CX + D * PxPerDeg, Y + 44.f * S()), 6.f * S(), WithAlpha(Z->ThemeColor, 0.95f));
			}
		}
	}
	DrawRect(Gold, CX - 1.5f * S(), Y - 4.f * S(), 3.f * S(), 42.f * S());
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
		Diamond(FVector2D(X0 + Rel.X * Size, Y0 + Rel.Y * Size), 6.f * S(), WithAlpha(Z->ThemeColor, Sub->IsDiscovered(Z) ? 1.f : 0.45f));
	}
	Arrow(FVector2D(X0 + Size * 0.5f, Y0 + Size * 0.5f), 9.f * S(), Pawn->GetActorRotation().Yaw, Gold);
	Text(TEXT("N"), X0 + Size * 0.5f, Y0 + 4.f * S(), Gold, 0.9f, true);

	// zone + progress under the minimap
	const ADALocationVolume* Zone = Sub->GetCurrentZone();
	Text(Zone ? Zone->DisplayName : FString(TEXT("Duel Academy Island")), X0 + Size * 0.5f, Y0 + Size + 8.f * S(), Paper, 0.9f, true);
	const int32 Total = Sub->GetZones().Num();
	FString Progress = FString::Printf(TEXT("Explored %d / %d"), Sub->NumDiscovered(), Total);
	if (const ADAStudentCharacter* Student = Cast<ADAStudentCharacter>(Pawn))
	{
		Progress += FString::Printf(TEXT("    Cards %d"), Student->GetCollectionSize());
	}
	Text(Progress, X0 + Size * 0.5f, Y0 + Size + 30.f * S(), WithAlpha(Paper, 0.7f), 0.75f, true);
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
	Text(Clock, X - Sz.X, 22.f * S(), Paper, 1.0f);
	Text(M->IsNight() ? TEXT("Night") : TEXT("Day"), X - Measure(M->IsNight() ? TEXT("Night") : TEXT("Day"), 0.75f).X, 48.f * S(), WithAlpha(Gold, 0.85f), 0.75f);
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
	Panel(X, Y, Sz.X + 36.f * S(), Sz.Y + 18.f * S(), Gold, 0.6f);
	Text(Line, X + 20.f * S(), Y + 8.f * S(), Paper, 1.1f);
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
	Text(Msg->Title, X + 24.f * S(), Y + 14.f * S(), WithAlpha(Msg->Accent, A), 1.35f, false, BigFont);
	float LY = Y + 60.f * S();
	for (const FString& L : Lines)
	{
		Text(L, X + 24.f * S(), LY, WithAlpha(Paper, A), 0.95f);
		LY += LineH;
	}
	Text(TEXT("[E] close"), X + W - 110.f * S(), Y + H - 26.f * S(), WithAlpha(Paper, 0.5f * A), 0.7f);
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
		TEXT("M / Tab .................. Island map & fast travel"),
		TEXT("J ........................ Switch dorm jacket"),
		TEXT("F ........................ Raise duel disk"),
		TEXT("T ........................ Pause / resume time"),
		TEXT("[  ] ..................... Slower / faster time"),
		TEXT("N ........................ Skip 3 hours"),
		TEXT("F1 / H ................... Toggle this help"),
	};
	// CC-BY 3.0 models require visible attribution; the full list is in CREDITS.md
	static const TCHAR* Credits[] = {
		TEXT("Art credits: textures, skies and plants from Poly Haven, ambientCG, 3dtextures.me (CC0); trees made with EZ-Tree (MIT)."),
		TEXT("Palm, acacia, hydrangea and rose models by Space Mushrooms & Scopia (Sweet Home 3D library), CC BY 3.0, modified."),
		TEXT("Sketchfab models (CC BY 4.0, modified): stealth86, TampaJoey, Ashkelon, plaggy, adenotoxin, MarcHoogkamp,"),
		TEXT("TooManyDemons, Tetiana_Denysenko, Memorie, adventurer, yonimantz. Student by Quaternius, Khronos lantern (CC0)."),
		TEXT("Further CC0 / CC-BY assets and their authors: see CREDITS.md. Unofficial fan project, not affiliated with Konami."),
	};
	const float W = 1000.f * S();
	const float LineH = 30.f * S();
	const float CreditH = 22.f * S();
	const float H = 110.f * S() + UE_ARRAY_COUNT(Lines) * LineH + UE_ARRAY_COUNT(Credits) * CreditH;
	const float X = Canvas->ClipX * 0.5f - W * 0.5f;
	const float Y = Canvas->ClipY * 0.5f - H * 0.5f;
	Panel(X, Y, W, H, Gold, 0.85f);
	Text(TEXT("CONTROLS"), X + 28.f * S(), Y + 18.f * S(), Gold, 1.4f, false, BigFont);
	float LY = Y + 72.f * S();
	for (const TCHAR* L : Lines)
	{
		Text(L, X + 28.f * S(), LY, Paper, 0.95f);
		LY += LineH;
	}
	LY += 14.f * S();
	for (const TCHAR* L : Credits)
	{
		Text(L, X + 28.f * S(), LY, WithAlpha(Paper, 0.6f), 0.68f);
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
	Text(TEXT("N"), MX + Side * 0.5f, MY + 8.f * S(), Gold, 1.3f, true, BigFont);

	float MouseX = -1.f;
	float MouseY = -1.f;
	if (APlayerController* PC = GetOwningPlayerController())
	{
		PC->GetMousePosition(MouseX, MouseY);
	}

	const TArray<ADALocationVolume*> Zones = Sub->GetZones();
	HoveredZone.Reset();
	float BestHover = 22.f * S();
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
		Diamond(Pt, (bSel ? 10.f : 7.f) * S(), WithAlpha(Z->ThemeColor, bKnown ? 1.f : 0.55f));
		Text(Z->DisplayName, Pt.X, Pt.Y + 12.f * S(), bSel ? Gold : WithAlpha(Paper, bKnown ? 0.95f : 0.6f), bSel ? 0.9f : 0.72f, true);
	}
	if (const APlayerController* PC = GetOwningPlayerController())
	{
		if (const APawn* Pawn = PC->GetPawn())
		{
			const FVector2D UV = WorldToMapUV(Pawn->GetActorLocation());
			Arrow(FVector2D(MX + UV.X * Side, MY + UV.Y * Side), 12.f * S(), Pawn->GetActorRotation().Yaw, Gold);
		}
	}

	// side list
	const float LX = MX + Side + 40.f * S();
	const float LW = CW - LX - 40.f * S();
	Text(TEXT("ISLAND MAP"), LX, MY, Gold, 2.0f, false, BigFont);
	Text(TEXT("Up / Down select    Enter travel    Click a marker    M close"), LX, MY + 62.f * S(), WithAlpha(Paper, 0.7f), 0.8f);
	float LY = MY + 100.f * S();
	const float RowH = 30.f * S();
	for (int32 i = 0; i < Zones.Num(); ++i)
	{
		ADALocationVolume* Z = Zones[i];
		const bool bSel = i == MapSelection;
		if (bSel)
		{
			DrawRect(WithAlpha(Z->ThemeColor, 0.35f), LX - 8.f * S(), LY - 3.f * S(), LW, RowH);
		}
		DrawRect(WithAlpha(Z->ThemeColor, 1.f), LX - 8.f * S(), LY - 3.f * S(), 4.f * S(), RowH);
		const FString Label = Sub->IsDiscovered(Z) ? Z->DisplayName : Z->DisplayName + TEXT("  (unexplored)");
		Text(Label, LX + 6.f * S(), LY, bSel ? Paper : WithAlpha(Paper, 0.75f), 0.95f);
		LY += RowH;
	}
	if (ADALocationVolume* Sel = Zones.IsValidIndex(MapSelection) ? Zones[MapSelection] : nullptr)
	{
		LY += 16.f * S();
		Text(Sel->DisplayName, LX, LY, Sel->ThemeColor, 1.3f, false, BigFont);
		LY += 46.f * S();
		Text(Sel->Subtitle, LX, LY, WithAlpha(Paper, 0.8f), 0.9f);
		LY += 32.f * S();
		for (const FString& L : Wrap(Sel->Description, LW - 10.f * S(), 0.9f))
		{
			Text(L, LX, LY, Paper, 0.9f);
			LY += 26.f * S();
		}
	}
}
