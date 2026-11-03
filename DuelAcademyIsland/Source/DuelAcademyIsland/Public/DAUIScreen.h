// Duel Academy Island - shared Canvas helpers for the gameplay screens.
//
// Plain C++ (no UObject) so the shop/deck/exam screens follow the same
// TUniquePtr-on-ADAHUD ownership pattern as the dialogue/PDA/title overlays.

#pragma once

#include "CoreMinimal.h"

class ADAHUD;
class APlayerController;
class UCanvas;
class UFont;
class UGameInstance;
class UWorld;

namespace DAUIText
{
	/**
	 * Shorten Str with a trailing ellipsis until MeasureWidth(Str) fits.
	 * MeasureWidth is a callable taking the candidate FString and returning
	 * its width in canvas pixels. Shared so the Canvas screens that do not
	 * derive from FDAUIScreen still use the same truncation contract.
	 */
	template <typename TMeasureWidth>
	FString EllipsizeMeasured(const FString& Str, float MaxWidth, TMeasureWidth&& MeasureWidth)
	{
		if (!FMath::IsFinite(MaxWidth))
		{
			return Str;
		}
		FString Out = Str;
		while (Out.Len() > 4 && MeasureWidth(Out) > MaxWidth)
		{
			Out = Out.LeftChop(4) + TEXT("...");
		}
		return Out;
	}
}

struct FDAUIHitTarget
{
	FString Action;
	FString Payload;
	int32 Index = INDEX_NONE;
	float X = 0.f;
	float Y = 0.f;
	float W = 0.f;
	float H = 0.f;

	bool Contains(const FVector2D& Point) const
	{
		return Point.X >= X && Point.X <= X + W && Point.Y >= Y && Point.Y <= Y + H;
	}
};

class FDAUIScreen
{
public:
	explicit FDAUIScreen(ADAHUD* InOwner);
	virtual ~FDAUIScreen();

	/** Each gameplay screen draws itself into the HUD canvas. */
	virtual void Draw(UCanvas* InCanvas) {}

protected:
	/** Refresh owner/canvas scale and clear last frame's hit targets. */
	void BeginFrame(UCanvas* InCanvas);

	void AddHit(const FString& Action, int32 Index, float X, float Y, float W, float H,
		const FString& Payload = FString());
	bool GetMousePosition(FVector2D& OutPosition) const;

	UWorld* GetWorld() const;
	UGameInstance* GetGameInstance() const;
	APlayerController* GetPlayerController() const;
	UFont* GetFont(bool bLarge) const;

	void DrawRect(const FLinearColor& Color, float X, float Y, float W, float H);
	void DrawText(const FString& Str, float X, float Y, const FLinearColor& Color, float InScale,
		bool bCenter = false, UFont* Font = nullptr);
	void DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent);
	void Diamond(const FVector2D& C, float R, const FLinearColor& Color);
	FVector2D Measure(const FString& Str, float InScale, UFont* Font = nullptr) const;
	TArray<FString> WrapText(const FString& Str, float MaxWidth, float InScale, UFont* Font = nullptr) const;
	/** Shorten Str with an ellipsis until it measures within MaxWidth. */
	FString Ellipsize(const FString& Str, float MaxWidth, float InScale, UFont* Font = nullptr) const;
	void PlaySfx(const TCHAR* SoundName, float Volume = 1.f) const;

	TWeakObjectPtr<ADAHUD> OwnerHUD;
	APlayerController* PlayerOwner = nullptr;
	UCanvas* Canvas = nullptr;
	float UIScale = 1.f;
	TArray<FDAUIHitTarget> HitTargets;
};
