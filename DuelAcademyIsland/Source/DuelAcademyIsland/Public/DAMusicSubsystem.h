// Duel Academy Island - music director.
//
// Owns the looping area themes and the scripted/duel/title cues. The mapping
// lives in Content/Data/Audio/music.json so a designer can retune the island
// without touching C++: zone and room ids point at track ids, and story
// `music` commands point at cue names such as BGM_Slifer_Dorm.
//
// Two UAudioComponents crossfade so walking through a door never cuts a phrase.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "DAMusicSubsystem.generated.h"

class ADALocationVolume;
class UAudioComponent;
class UDASettings;
class USoundBase;

UCLASS()
class DUELACADEMYISLAND_API UDAMusicSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	static UDAMusicSubsystem* Get(const UObject* WorldContext);

	/**
	 * Plays a story cue (BGM_Academy_Arrival, BGM_Free_Roam, ...) or a direct
	 * M_* track id. Returns false when the name is unknown. A cue is a manual
	 * override: zone changes keep the cue until SetAutoMode or another cue.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Music")
	bool PlayCue(const FString& Cue, float FadeSeconds = -1.f);

	/** Plays a track directly. Manual tracks survive zone changes. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Music")
	void PlayTrack(const FString& TrackId, float FadeSeconds = -1.f, bool bManual = true);

	/** Hands the music back to the current zone/interior. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Music")
	void SetAutoMode(float FadeSeconds = -1.f);

	/** Stops both decks and keeps automatic updates from restarting them. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Music")
	void StopMusic(float FadeSeconds = 0.4f);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Music")
	bool IsManual() const { return Mode == EMode::Manual; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Music")
	FString GetCurrentTrack() const { return CurrentTrack; }

	/** Called by the island subsystem when the smallest containing zone changes. */
	void NotifyZoneChanged(ADALocationVolume* Zone);

	/** Called by an interior portal on arrival (non-empty) and on exit (empty). */
	void SetInteriorContext(const FString& InInteriorId);
	void ClearInteriorContext() { SetInteriorContext(FString()); }

private:
	enum class EMode : uint8
	{
		Auto,
		Manual
	};

	struct FMusicTrack
	{
		float Volume = 1.f;
	};

	struct FMusicConfig
	{
		FString DefaultTrack;
		FString TitleTrack;
		FString DuelTrack;
		float FadeSeconds = 1.75f;
		TMap<FString, FMusicTrack> Tracks;
		TMap<FString, FString> Zones;
		TMap<FString, FString> Sublocations;
		TMap<FString, FString> Interiors;
		TMap<FString, FString> Cues;
	};

	void LoadConfig();
	void TryBindZoneEvents();
	void TryBindSettings();
	void UnbindEvents();

	UFUNCTION()
	void HandleZoneChanged(ADALocationVolume* NewZone, bool bFirstVisit);

	UFUNCTION()
	void HandleSettingsChanged();

	FString ResolveAutoTrack() const;
	FString ResolveZoneTrack(const FString& InZoneId) const;
	const FString* FindTrackId(const TMap<FString, FString>& Map, const FString& Key) const;
	float TrackVolume(const FString& TrackId) const;

	void PlayTrackInternal(const FString& TrackId, float FadeSeconds);
	void TickFade(float DeltaTime);
	void UpdateVolumes();
	void StopPreviousDeck();
	void StopAllDecks();

	UAudioComponent* CreateDeck();
	USoundBase* LoadTrack(const FString& TrackId);
	float BgmVolume() const;

	FMusicConfig Config;

	EMode Mode = EMode::Auto;
	FString ZoneId;
	FString InteriorId;
	FString CurrentTrack;
	float CurrentTrackVolume = 1.f;

	FString PreviousTrack;
	float PreviousTrackVolume = 1.f;
	/** Multiplier at which the outgoing deck started its fade. */
	float PreviousGain = 1.f;

	float FadeDuration = 0.f;
	float FadeElapsed = 0.f;
	bool bFading = false;

	UPROPERTY(Transient)
	TObjectPtr<UAudioComponent> CurrentDeck;

	UPROPERTY(Transient)
	TObjectPtr<UAudioComponent> PreviousDeck;

	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<USoundBase>> MusicCache;

	TWeakObjectPtr<UDASettings> Settings;
	bool bZoneEventsBound = false;
	bool bSettingsBound = false;
};
