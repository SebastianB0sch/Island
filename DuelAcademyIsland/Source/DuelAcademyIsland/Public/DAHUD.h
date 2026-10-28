// Duel Academy Island - canvas HUD: location banners, compass, minimap, island map + fast travel.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "DAHUD.generated.h"

class ADALocationVolume;
class ADAIslandManager;
class UDAIslandSubsystem;
class UFont;
class UTexture2D;

UCLASS()
class DUELACADEMYISLAND_API ADAHUD : public AHUD
{
	GENERATED_BODY()

public:
	ADAHUD();

	virtual void BeginPlay() override;
	virtual void DrawHUD() override;

	bool IsMapOpen() const { return bMapOpen; }
	void ToggleMap();
	void ToggleHelp() { bHelpOpen = !bHelpOpen; }
	void MoveMapSelection(int32 Delta);
	ADALocationVolume* GetSelectedZone() const;
	ADALocationVolume* PickZoneUnderCursor() const { return HoveredZone.Get(); }

private:
	// drawing helpers
	float S() const { return UIScale; }
	void Text(const FString& Str, float X, float Y, const FLinearColor& Color, float Scale, bool bCenter = false, UFont* Font = nullptr);
	FVector2D Measure(const FString& Str, float Scale, UFont* Font = nullptr) const;
	TArray<FString> Wrap(const FString& Str, float MaxWidth, float Scale, UFont* Font = nullptr) const;
	void Panel(float X, float Y, float W, float H, const FLinearColor& Accent, float Alpha = 0.72f);
	void Diamond(const FVector2D& C, float R, const FLinearColor& Color);
	void Arrow(const FVector2D& C, float R, float YawDeg, const FLinearColor& Color);
	FVector2D WorldToMapUV(const FVector& World) const;

	void DrawIntro(float Time);
	void DrawBanner(UDAIslandSubsystem* Sub, float Time);
	void DrawCompass(UDAIslandSubsystem* Sub);
	void DrawMinimap(UDAIslandSubsystem* Sub);
	void DrawClock(ADAIslandManager* M);
	void DrawPrompt();
	void DrawMessage(UDAIslandSubsystem* Sub);
	void DrawHelp();
	void DrawMap(UDAIslandSubsystem* Sub);

	UPROPERTY(Transient)
	TObjectPtr<UFont> SmallFont;

	UPROPERTY(Transient)
	TObjectPtr<UFont> BigFont;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> MapTexture;

	FVector2D MapMin = FVector2D(-153600.0, -153600.0);
	FVector2D MapMax = FVector2D(153600.0, 153600.0);

	bool bMapOpen = false;
	bool bHelpOpen = false;
	int32 MapSelection = 0;
	float UIScale = 1.f;
	float StartTime = 0.f;
	TWeakObjectPtr<ADALocationVolume> HoveredZone;
};
