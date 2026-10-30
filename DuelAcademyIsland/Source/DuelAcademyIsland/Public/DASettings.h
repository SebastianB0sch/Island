// Duel Academy Island - player options.
//
// Settings are part of the profile save payload. UDASettings loads defaults
// from Content/Data/Profile/settings.json and exposes typed setters so A09
// never parses JSON or writes files directly.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Map.h"
#include "Dom/JsonObject.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DASettings.generated.h"

UENUM(BlueprintType)
enum class EDAAnimationSpeed : uint8
{
	Slow,
	Normal,
	Fast
};

UENUM(BlueprintType)
enum class EDATextSpeed : uint8
{
	Slow,
	Normal,
	Fast,
	Instant
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FDAOnSettingsChanged);

UCLASS()
class DUELACADEMYISLAND_API UDASettings : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void ResetToDefaults();

	/** Loads Content/Data/Profile/settings.json. Returns false and keeps defaults if missing. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	bool LoadDefaults();

	/** Requests an autosave through UDASaveSubsystem. Safe to call when no game instance exists. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	bool Save();

	// ---------------------------------------------------------------- animation / text
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	EDAAnimationSpeed GetAnimationSpeed() const { return AnimationSpeed; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetAnimationSpeed(EDAAnimationSpeed NewSpeed);

	/** Multiplier A09 can apply to animation playback (0.75 / 1.0 / 1.5). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	float GetAnimationSpeedScale() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	bool GetConfirmActivation() const { return bConfirmActivation; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetConfirmActivation(bool bNewValue);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	EDATextSpeed GetTextSpeed() const { return TextSpeed; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetTextSpeed(EDATextSpeed NewSpeed);

	/** Characters per second for the dialogue typewriter. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	float GetTextSpeedCps() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	bool GetSubtitles() const { return bSubtitles; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetSubtitles(bool bNewValue);

	// ---------------------------------------------------------------- audio
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	float GetBgmVolume() const { return BgmVolume; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetBgmVolume(float NewVolume);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	float GetSfxVolume() const { return SfxVolume; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetSfxVolume(float NewVolume);

	// ---------------------------------------------------------------- language / controls
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	FString GetLanguageKey() const { return LanguageKey; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetLanguageKey(const FString& NewKey);

	/** Action -> key display string. Defaults cover the current keyboard layout. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Settings")
	FString GetControl(const FString& Action) const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void SetControl(const FString& Action, const FString& Key);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Settings")
	void ResetControl(const FString& Action);

	const TMap<FString, FString>& GetControls() const { return Controls; }

	// ---------------------------------------------------------------- persistence
	void WriteJson(TSharedPtr<FJsonObject>& Root) const;
	bool ReadJson(const TSharedPtr<FJsonObject>& Root, FString& OutError);
	void WriteSaveData(TSharedPtr<FJsonObject>& Root) const { WriteJson(Root); }
	bool ReadSaveData(const TSharedPtr<FJsonObject>& Root, FString& OutError) { return ReadJson(Root, OutError); }

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Settings")
	FDAOnSettingsChanged OnSettingsChanged;

private:
	void BuildDefaultControls();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Settings", meta = (AllowPrivateAccess = "true"))
	EDAAnimationSpeed AnimationSpeed = EDAAnimationSpeed::Normal;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Settings", meta = (AllowPrivateAccess = "true"))
	bool bConfirmActivation = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Settings", meta = (AllowPrivateAccess = "true"))
	EDATextSpeed TextSpeed = EDATextSpeed::Normal;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Settings", meta = (AllowPrivateAccess = "true"))
	float BgmVolume = 0.8f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Settings", meta = (AllowPrivateAccess = "true"))
	float SfxVolume = 0.8f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Settings", meta = (AllowPrivateAccess = "true"))
	bool bSubtitles = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Settings", meta = (AllowPrivateAccess = "true"))
	FString LanguageKey = TEXT("en");

	UPROPERTY()
	TMap<FString, FString> Controls;

	/** Defaults used by ResetControl, preserved across loads. */
	TMap<FString, FString> DefaultControls;
};
