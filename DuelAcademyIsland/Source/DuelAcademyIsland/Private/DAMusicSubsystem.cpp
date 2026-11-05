// Duel Academy Island - music director implementation.

#include "DAMusicSubsystem.h"

#include "DAIslandSubsystem.h"
#include "DALocationVolume.h"
#include "DASettings.h"
#include "DATypes.h"
#include "DuelAcademyIsland.h"
#include "Components/AudioComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Sound/SoundBase.h"

namespace
{
	const TCHAR* const MusicConfigFile = TEXT("Data/Audio/music.json");

	FString ReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Fallback = FString())
	{
		FString Value;
		return Object.IsValid() && Object->TryGetStringField(Field, Value) ? Value : Fallback;
	}

	void ReadStringMap(const TSharedPtr<FJsonObject>& Root, const TCHAR* Field, TMap<FString, FString>& Out)
	{
		const TSharedPtr<FJsonObject>* Object = nullptr;
		if (!Root.IsValid() || !Root->TryGetObjectField(Field, Object) || !Object || !Object->IsValid())
		{
			return;
		}
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*Object)->Values)
		{
			if (Pair.Value.IsValid())
			{
				Out.Add(Pair.Key, Pair.Value->AsString());
			}
		}
	}

}

void UDAMusicSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	LoadConfig();
	TryBindSettings();
	TryBindZoneEvents();
}

void UDAMusicSubsystem::Deinitialize()
{
	UnbindEvents();
	StopAllDecks();
	MusicCache.Reset();
	Super::Deinitialize();
}

TStatId UDAMusicSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UDAMusicSubsystem, STATGROUP_Tickables);
}

UDAMusicSubsystem* UDAMusicSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	const UWorld* World = WorldContext->GetWorld();
	return World ? World->GetSubsystem<UDAMusicSubsystem>() : nullptr;
}

void UDAMusicSubsystem::Tick(float DeltaTime)
{
	const UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld())
	{
		return;
	}

	TryBindZoneEvents();
	TryBindSettings();
	TickFade(DeltaTime);
	UpdateVolumes();
}

// ------------------------------------------------------------------------ config

void UDAMusicSubsystem::LoadConfig()
{
	Config = FMusicConfig();
	Config.DefaultTrack = TEXT("M_AcademyGrounds");
	Config.TitleTrack = TEXT("M_Title");
	Config.DuelTrack = TEXT("M_DuelArena");
	Config.FadeSeconds = 1.75f;

	const FString Path = FPaths::ProjectContentDir() / MusicConfigFile;
	FString Json;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Music: %s is missing; using the academy theme only."), *Path);
		return;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Music: %s could not be parsed; using the academy theme only."), *Path);
		return;
	}

	Config.DefaultTrack = ReadString(Root, TEXT("default_track"), Config.DefaultTrack);
	Config.TitleTrack = ReadString(Root, TEXT("title_track"), Config.TitleTrack);
	Config.DuelTrack = ReadString(Root, TEXT("duel_track"), Config.DuelTrack);
	double Fade = Config.FadeSeconds;
	if (Root->TryGetNumberField(TEXT("fade_seconds"), Fade) && FMath::IsFinite(Fade))
	{
		Config.FadeSeconds = FMath::Clamp(static_cast<float>(Fade), 0.f, 10.f);
	}

	ReadStringMap(Root, TEXT("zones"), Config.Zones);
	ReadStringMap(Root, TEXT("sublocations"), Config.Sublocations);
	ReadStringMap(Root, TEXT("interiors"), Config.Interiors);
	ReadStringMap(Root, TEXT("cues"), Config.Cues);

	const TSharedPtr<FJsonObject>* Tracks = nullptr;
	if (Root->TryGetObjectField(TEXT("tracks"), Tracks) && Tracks && Tracks->IsValid())
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*Tracks)->Values)
		{
			FMusicTrack Track;
			if (Pair.Value.IsValid())
			{
				const TSharedPtr<FJsonObject> TrackObject = Pair.Value->AsObject();
				double Volume = 1.0;
				if (TrackObject.IsValid() && TrackObject->TryGetNumberField(TEXT("volume"), Volume) && FMath::IsFinite(Volume))
				{
					Track.Volume = FMath::Clamp(static_cast<float>(Volume), 0.f, 2.f);
				}
			}
			Config.Tracks.Add(Pair.Key, Track);
		}
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Music: %d tracks, %d zones, %d rooms, %d cues."),
		Config.Tracks.Num(), Config.Zones.Num(), Config.Interiors.Num(), Config.Cues.Num());
}

// ------------------------------------------------------------------------ binding

void UDAMusicSubsystem::TryBindZoneEvents()
{
	if (bZoneEventsBound)
	{
		return;
	}
	if (UDAIslandSubsystem* Island = UDAIslandSubsystem::Get(this))
	{
		Island->OnZoneChanged.AddDynamic(this, &UDAMusicSubsystem::HandleZoneChanged);
		bZoneEventsBound = true;
		NotifyZoneChanged(Island->GetCurrentZone());
	}
}

void UDAMusicSubsystem::TryBindSettings()
{
	if (Settings.IsValid())
	{
		return;
	}
	UWorld* World = GetWorld();
	UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	UDASettings* NewSettings = GameInstance ? GameInstance->GetSubsystem<UDASettings>() : nullptr;
	if (NewSettings)
	{
		Settings = NewSettings;
		if (!bSettingsBound && !NewSettings->OnSettingsChanged.IsAlreadyBound(this, &UDAMusicSubsystem::HandleSettingsChanged))
		{
			NewSettings->OnSettingsChanged.AddDynamic(this, &UDAMusicSubsystem::HandleSettingsChanged);
			bSettingsBound = true;
		}
	}
}

void UDAMusicSubsystem::UnbindEvents()
{
	if (bZoneEventsBound)
	{
		if (UDAIslandSubsystem* Island = UDAIslandSubsystem::Get(this))
		{
			Island->OnZoneChanged.RemoveDynamic(this, &UDAMusicSubsystem::HandleZoneChanged);
		}
		bZoneEventsBound = false;
	}
	if (bSettingsBound && Settings.IsValid())
	{
		Settings->OnSettingsChanged.RemoveDynamic(this, &UDAMusicSubsystem::HandleSettingsChanged);
		bSettingsBound = false;
	}
	Settings.Reset();
}

void UDAMusicSubsystem::HandleZoneChanged(ADALocationVolume* NewZone, bool /*bFirstVisit*/)
{
	NotifyZoneChanged(NewZone);
}

void UDAMusicSubsystem::HandleSettingsChanged()
{
	UpdateVolumes();
}

void UDAMusicSubsystem::NotifyZoneChanged(ADALocationVolume* Zone)
{
	const FString NewZoneId = Zone ? Zone->LocationId : FString();
	// A real zone means the player is back outside the portal cells. Interiors
	// set their context through the portal after the teleport.
	if (Zone)
	{
		InteriorId.Reset();
	}
	ZoneId = NewZoneId;

	if (Mode == EMode::Auto)
	{
		const FString Track = ResolveAutoTrack();
		if (!Track.IsEmpty())
		{
			PlayTrackInternal(Track, -1.f);
		}
	}
}

// ------------------------------------------------------------------------ map

const FString* UDAMusicSubsystem::FindTrackId(const TMap<FString, FString>& Map, const FString& Key) const
{
	if (const FString* Exact = Map.Find(Key))
	{
		return Exact;
	}
	for (const TPair<FString, FString>& Pair : Map)
	{
		if (Pair.Key.Equals(Key, ESearchCase::IgnoreCase))
		{
			return &Pair.Value;
		}
	}
	return nullptr;
}

float UDAMusicSubsystem::TrackVolume(const FString& TrackId) const
{
	if (const FMusicTrack* Track = Config.Tracks.Find(TrackId))
	{
		return Track->Volume;
	}
	return 1.f;
}

FString UDAMusicSubsystem::ResolveZoneTrack(const FString& InZoneId) const
{
	FString Current = InZoneId;
	for (int32 Depth = 0; Depth < 4 && !Current.IsEmpty(); ++Depth)
	{
		if (const FString* Direct = FindTrackId(Config.Zones, Current))
		{
			return *Direct;
		}
		if (const FString* Sub = FindTrackId(Config.Sublocations, Current))
		{
			return *Sub;
		}

		FString Parent;
		if (const UDAIslandSubsystem* Island = UDAIslandSubsystem::Get(this))
		{
			for (const ADALocationVolume* Zone : Island->GetZones())
			{
				if (Zone && Zone->LocationId.Equals(Current, ESearchCase::IgnoreCase))
				{
					Parent = Zone->ParentId;
					break;
				}
			}
		}
		Current = Parent;
	}
	return Config.DefaultTrack;
}

FString UDAMusicSubsystem::ResolveAutoTrack() const
{
	if (!InteriorId.IsEmpty())
	{
		if (const FString* InteriorTrack = FindTrackId(Config.Interiors, InteriorId))
		{
			return *InteriorTrack;
		}
	}
	if (!ZoneId.IsEmpty())
	{
		return ResolveZoneTrack(ZoneId);
	}
	// No context yet (or the player is between zones): stay silent rather than
	// starting the academy theme over the title screen.
	return FString();
}

// ------------------------------------------------------------------------ transport

bool UDAMusicSubsystem::PlayCue(const FString& Cue, float FadeSeconds)
{
	const FString Name = Cue.TrimStartAndEnd();
	if (Name.IsEmpty())
	{
		return false;
	}

	if (const FString* Mapped = FindTrackId(Config.Cues, Name))
	{
		if (*Mapped == TEXT("@auto"))
		{
			SetAutoMode(FadeSeconds);
			return true;
		}
		PlayTrack(*Mapped, FadeSeconds, true);
		return true;
	}

	// The title/duel shortcuts still work if a config only supplies the top-level
	// track ids and no cue table.
	if (Name.Equals(TEXT("BGM_Title"), ESearchCase::IgnoreCase) && !Config.TitleTrack.IsEmpty())
	{
		PlayTrack(Config.TitleTrack, FadeSeconds, true);
		return true;
	}
	if (Name.Equals(TEXT("BGM_Duel"), ESearchCase::IgnoreCase) && !Config.DuelTrack.IsEmpty())
	{
		PlayTrack(Config.DuelTrack, FadeSeconds, true);
		return true;
	}

	for (const TPair<FString, FMusicTrack>& Pair : Config.Tracks)
	{
		if (Pair.Key.Equals(Name, ESearchCase::IgnoreCase))
		{
			PlayTrack(Pair.Key, FadeSeconds, true);
			return true;
		}
	}

	if (Name.StartsWith(TEXT("M_"), ESearchCase::IgnoreCase))
	{
		PlayTrack(Name, FadeSeconds, true);
		return true;
	}

	UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Music: unknown cue '%s'."), *Name);
	return false;
}

void UDAMusicSubsystem::PlayTrack(const FString& TrackId, float FadeSeconds, bool bManual)
{
	if (bManual)
	{
		Mode = EMode::Manual;
	}
	PlayTrackInternal(TrackId, FadeSeconds);
}

void UDAMusicSubsystem::SetAutoMode(float FadeSeconds)
{
	Mode = EMode::Auto;
	const FString Track = ResolveAutoTrack();
	if (!Track.IsEmpty())
	{
		PlayTrackInternal(Track, FadeSeconds);
	}
}

void UDAMusicSubsystem::PlayTrackInternal(const FString& TrackId, float FadeSeconds)
{
	if (TrackId.IsEmpty())
	{
		return;
	}
	if (TrackId.Equals(CurrentTrack, ESearchCase::IgnoreCase) && CurrentDeck && CurrentDeck->IsPlaying())
	{
		return;
	}

	USoundBase* Sound = LoadTrack(TrackId);
	if (!Sound)
	{
		return;
	}

	// Retire the current outgoing deck, then let the deck that is playing now
	// become the outgoing one. A new cue during a fade starts from wherever the
	// old fade had reached instead of jumping back to full level.
	StopPreviousDeck();
	PreviousDeck = CurrentDeck;
	PreviousTrack = CurrentTrack;
	PreviousTrackVolume = CurrentTrackVolume;
	PreviousGain = bFading && FadeDuration > KINDA_SMALL_NUMBER
		? FMath::Clamp(FadeElapsed / FadeDuration, 0.f, 1.f)
		: 1.f;

	CurrentDeck = CreateDeck();
	CurrentTrack = TrackId;
	CurrentTrackVolume = TrackVolume(TrackId);
	FadeDuration = FadeSeconds < 0.f ? Config.FadeSeconds : FMath::Max(0.f, FadeSeconds);
	FadeElapsed = 0.f;
	bFading = FadeDuration > 0.01f;

	if (!CurrentDeck)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Music: could not create an audio deck for '%s'."), *TrackId);
		CurrentTrack.Reset();
		return;
	}

	CurrentDeck->SetSound(Sound);
	CurrentDeck->Play(0.f);
	CurrentDeck->SetVolumeMultiplier(0.f);
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Music: %s -> %s (%.2fs fade, playing=%s)."),
		Mode == EMode::Auto ? TEXT("area") : TEXT("cue"), *TrackId, FadeDuration,
		CurrentDeck->IsPlaying() ? TEXT("yes") : TEXT("no"));

	if (!bFading)
	{
		StopPreviousDeck();
	}
	UpdateVolumes();
}

void UDAMusicSubsystem::StopMusic(float FadeSeconds)
{
	Mode = EMode::Manual;
	if (!CurrentDeck)
	{
		StopPreviousDeck();
		return;
	}

	StopPreviousDeck();
	PreviousDeck = CurrentDeck;
	PreviousTrack = CurrentTrack;
	PreviousTrackVolume = CurrentTrackVolume;
	PreviousGain = bFading && FadeDuration > KINDA_SMALL_NUMBER
		? FMath::Clamp(FadeElapsed / FadeDuration, 0.f, 1.f)
		: 1.f;
	CurrentDeck = nullptr;
	CurrentTrack.Reset();
	CurrentTrackVolume = 1.f;

	FadeDuration = FMath::Max(0.f, FadeSeconds);
	FadeElapsed = 0.f;
	bFading = FadeDuration > 0.01f;
	if (!bFading)
	{
		StopPreviousDeck();
	}
	UpdateVolumes();
}

void UDAMusicSubsystem::SetInteriorContext(const FString& InInteriorId)
{
	InteriorId = InInteriorId;
	if (Mode == EMode::Auto)
	{
		const FString Track = ResolveAutoTrack();
		if (!Track.IsEmpty())
		{
			PlayTrackInternal(Track, -1.f);
		}
	}
}

// ------------------------------------------------------------------------ volume / crossfade

void UDAMusicSubsystem::TickFade(float DeltaTime)
{
	if (!bFading)
	{
		return;
	}
	FadeElapsed += FMath::Max(0.f, DeltaTime);
	if (FadeElapsed >= FadeDuration)
	{
		FadeElapsed = FadeDuration;
		bFading = false;
		StopPreviousDeck();
	}
}

void UDAMusicSubsystem::UpdateVolumes()
{
	const float Bgm = FMath::Clamp(BgmVolume(), 0.f, 1.f);
	const float Alpha = bFading && FadeDuration > KINDA_SMALL_NUMBER
		? FMath::Clamp(FadeElapsed / FadeDuration, 0.f, 1.f)
		: 1.f;

	if (CurrentDeck)
	{
		CurrentDeck->SetVolumeMultiplier(FMath::Max(0.f, CurrentTrackVolume * Bgm * Alpha));
	}
	if (PreviousDeck)
	{
		PreviousDeck->SetVolumeMultiplier(FMath::Max(0.f, PreviousTrackVolume * Bgm * PreviousGain * (1.f - Alpha)));
	}
}

float UDAMusicSubsystem::BgmVolume() const
{
	return Settings.IsValid() ? Settings->GetBgmVolume() : 0.8f;
}

// ------------------------------------------------------------------------ decks

UAudioComponent* UDAMusicSubsystem::CreateDeck()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return nullptr;
	}
	UAudioComponent* Deck = NewObject<UAudioComponent>(this, UAudioComponent::StaticClass(), NAME_None, RF_Transient);
	if (!Deck)
	{
		return nullptr;
	}
	Deck->bAutoActivate = false;
	Deck->bAllowSpatialization = false;
	Deck->bIsUISound = true;
	Deck->bOverrideAttenuation = false;
	Deck->SetVolumeMultiplier(0.f);
	Deck->RegisterComponentWithWorld(World);
	return Deck;
}

void UDAMusicSubsystem::StopPreviousDeck()
{
	if (PreviousDeck)
	{
		PreviousDeck->Stop();
		PreviousDeck->DestroyComponent();
		PreviousDeck = nullptr;
	}
	PreviousTrack.Reset();
	PreviousTrackVolume = 1.f;
	PreviousGain = 1.f;
}

void UDAMusicSubsystem::StopAllDecks()
{
	StopPreviousDeck();
	if (CurrentDeck)
	{
		CurrentDeck->Stop();
		CurrentDeck->DestroyComponent();
		CurrentDeck = nullptr;
	}
	CurrentTrack.Reset();
	CurrentTrackVolume = 1.f;
	FadeDuration = 0.f;
	FadeElapsed = 0.f;
	bFading = false;
}

USoundBase* UDAMusicSubsystem::LoadTrack(const FString& TrackId)
{
	if (TrackId.IsEmpty())
	{
		return nullptr;
	}
	if (const TObjectPtr<USoundBase>* Cached = MusicCache.Find(TrackId))
	{
		return Cached->Get();
	}

	const FString Path = FString::Printf(TEXT("%s%s.%s"), DuelAcademy::SoundFolder, *TrackId, *TrackId);
	USoundBase* Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!Sound)
	{
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("Music: track '%s' is not imported (expected %s). Run the audio build/import step."), *TrackId, *Path);
		return nullptr;
	}
	MusicCache.Add(TrackId, Sound);
	return Sound;
}
