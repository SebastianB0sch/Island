// Duel Academy Island - settings implementation.

#include "DASettings.h"

#include "DAJson.h"
#include "DASaveGame.h"
#include "DuelAcademyIsland.h"

#include "Engine/GameInstance.h"

namespace
{
	FString AnimationSpeedToString(EDAAnimationSpeed Speed)
	{
		switch (Speed)
		{
		case EDAAnimationSpeed::Slow: return TEXT("slow");
		case EDAAnimationSpeed::Fast: return TEXT("fast");
		case EDAAnimationSpeed::Normal:
		default:                      return TEXT("normal");
		}
	}

	EDAAnimationSpeed StringToAnimationSpeed(const FString& Value, EDAAnimationSpeed Fallback)
	{
		const FString Lower = Value.TrimStartAndEnd().ToLower();
		if (Lower == TEXT("slow") || Lower == TEXT("0"))
		{
			return EDAAnimationSpeed::Slow;
		}
		if (Lower == TEXT("fast") || Lower == TEXT("2"))
		{
			return EDAAnimationSpeed::Fast;
		}
		if (Lower == TEXT("normal") || Lower == TEXT("1"))
		{
			return EDAAnimationSpeed::Normal;
		}
		return Fallback;
	}

	FString TextSpeedToString(EDATextSpeed Speed)
	{
		switch (Speed)
		{
		case EDATextSpeed::Slow:    return TEXT("slow");
		case EDATextSpeed::Fast:    return TEXT("fast");
		case EDATextSpeed::Instant: return TEXT("instant");
		case EDATextSpeed::Normal:
		default:                    return TEXT("normal");
		}
	}

	EDATextSpeed StringToTextSpeed(const FString& Value, EDATextSpeed Fallback)
	{
		const FString Lower = Value.TrimStartAndEnd().ToLower();
		if (Lower == TEXT("slow") || Lower == TEXT("0"))
		{
			return EDATextSpeed::Slow;
		}
		if (Lower == TEXT("fast") || Lower == TEXT("2"))
		{
			return EDATextSpeed::Fast;
		}
		if (Lower == TEXT("instant") || Lower == TEXT("3"))
		{
			return EDATextSpeed::Instant;
		}
		if (Lower == TEXT("normal") || Lower == TEXT("1"))
		{
			return EDATextSpeed::Normal;
		}
		return Fallback;
	}
}

void UDASettings::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	LoadDefaults();
}

void UDASettings::BuildDefaultControls()
{
	DefaultControls.Reset();
	DefaultControls.Add(TEXT("MoveForward"), TEXT("W"));
	DefaultControls.Add(TEXT("MoveBack"), TEXT("S"));
	DefaultControls.Add(TEXT("MoveLeft"), TEXT("A"));
	DefaultControls.Add(TEXT("MoveRight"), TEXT("D"));
	DefaultControls.Add(TEXT("Look"), TEXT("Mouse"));
	DefaultControls.Add(TEXT("Interact"), TEXT("E"));
	DefaultControls.Add(TEXT("Jump"), TEXT("Space"));
	DefaultControls.Add(TEXT("Sprint"), TEXT("Left Shift"));
	DefaultControls.Add(TEXT("PDA"), TEXT("Tab"));
	DefaultControls.Add(TEXT("DuelDisk"), TEXT("F"));
	DefaultControls.Add(TEXT("Pause"), TEXT("Escape"));
	DefaultControls.Add(TEXT("DuelConfirm"), TEXT("Enter"));
	DefaultControls.Add(TEXT("DuelCancel"), TEXT("Escape"));
	Controls = DefaultControls;
}

void UDASettings::ResetToDefaults()
{
	AnimationSpeed = EDAAnimationSpeed::Normal;
	bConfirmActivation = true;
	TextSpeed = EDATextSpeed::Normal;
	BgmVolume = 0.8f;
	SfxVolume = 0.8f;
	bSubtitles = true;
	LanguageKey = TEXT("en");
	BuildDefaultControls();
	OnSettingsChanged.Broadcast();
}

bool UDASettings::LoadDefaults()
{
	ResetToDefaults();

	const FString Path = DAJson::ContentDataPath(TEXT("Profile/settings.json"));
	TSharedPtr<FJsonObject> Root;
	FString LoadError;
	if (!DAJson::LoadObjectFile(Path, Root, LoadError))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Settings data unavailable (%s); using defaults."), *LoadError);
		return false;
	}

	FString Error;
	const bool bResult = ReadJson(Root, Error);
	if (bResult)
	{
		// settings.json controls are the defaults ResetControl restores.
		DefaultControls = Controls;
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Settings data at %s was invalid: %s"), *Path, *Error);
	}
	return bResult;
}

bool UDASettings::Save()
{
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UDASaveSubsystem* SaveSubsystem = GameInstance->GetSubsystem<UDASaveSubsystem>())
		{
			SaveSubsystem->RequestAutosave(TEXT("settings"));
			return true;
		}
	}
	return false;
}

// ------------------------------------------------------------------------ animation / text

void UDASettings::SetAnimationSpeed(EDAAnimationSpeed NewSpeed)
{
	if (AnimationSpeed == NewSpeed)
	{
		return;
	}
	AnimationSpeed = NewSpeed;
	OnSettingsChanged.Broadcast();
}

float UDASettings::GetAnimationSpeedScale() const
{
	switch (AnimationSpeed)
	{
	case EDAAnimationSpeed::Slow: return 0.75f;
	case EDAAnimationSpeed::Fast: return 1.5f;
	case EDAAnimationSpeed::Normal:
	default:                      return 1.0f;
	}
}

void UDASettings::SetConfirmActivation(bool bNewValue)
{
	if (bConfirmActivation == bNewValue)
	{
		return;
	}
	bConfirmActivation = bNewValue;
	OnSettingsChanged.Broadcast();
}

void UDASettings::SetTextSpeed(EDATextSpeed NewSpeed)
{
	if (TextSpeed == NewSpeed)
	{
		return;
	}
	TextSpeed = NewSpeed;
	OnSettingsChanged.Broadcast();
}

float UDASettings::GetTextSpeedCps() const
{
	switch (TextSpeed)
	{
	case EDATextSpeed::Slow:    return 20.0f;
	case EDATextSpeed::Fast:    return 80.0f;
	case EDATextSpeed::Instant: return 10000.0f;
	case EDATextSpeed::Normal:
	default:                    return 40.0f;
	}
}

void UDASettings::SetSubtitles(bool bNewValue)
{
	if (bSubtitles == bNewValue)
	{
		return;
	}
	bSubtitles = bNewValue;
	OnSettingsChanged.Broadcast();
}

// ------------------------------------------------------------------------ audio

void UDASettings::SetBgmVolume(float NewVolume)
{
	if (!FMath::IsFinite(NewVolume))
	{
		return;
	}
	const float Clamped = FMath::Clamp(NewVolume, 0.0f, 1.0f);
	if (FMath::IsNearlyEqual(BgmVolume, Clamped))
	{
		return;
	}
	BgmVolume = Clamped;
	OnSettingsChanged.Broadcast();
}

void UDASettings::SetSfxVolume(float NewVolume)
{
	if (!FMath::IsFinite(NewVolume))
	{
		return;
	}
	const float Clamped = FMath::Clamp(NewVolume, 0.0f, 1.0f);
	if (FMath::IsNearlyEqual(SfxVolume, Clamped))
	{
		return;
	}
	SfxVolume = Clamped;
	OnSettingsChanged.Broadcast();
}

// ------------------------------------------------------------------------ language / controls

void UDASettings::SetLanguageKey(const FString& NewKey)
{
	const FString Trimmed = NewKey.TrimStartAndEnd();
	if (Trimmed.IsEmpty() || LanguageKey.Equals(Trimmed, ESearchCase::IgnoreCase))
	{
		return;
	}
	LanguageKey = Trimmed;
	OnSettingsChanged.Broadcast();
}

FString UDASettings::GetControl(const FString& Action) const
{
	if (const FString* Key = Controls.Find(Action))
	{
		return *Key;
	}
	return FString();
}

void UDASettings::SetControl(const FString& Action, const FString& Key)
{
	const FString ActionKey = Action.TrimStartAndEnd();
	const FString KeyText = Key.TrimStartAndEnd();
	if (ActionKey.IsEmpty() || KeyText.IsEmpty())
	{
		return;
	}
	const FString OldKey = Controls.FindRef(ActionKey);
	if (OldKey.Equals(KeyText, ESearchCase::IgnoreCase))
	{
		return;
	}
	Controls.Add(ActionKey, KeyText);
	OnSettingsChanged.Broadcast();
}

void UDASettings::ResetControl(const FString& Action)
{
	const FString ActionKey = Action.TrimStartAndEnd();
	if (ActionKey.IsEmpty())
	{
		return;
	}
	const FString* DefaultKey = DefaultControls.Find(ActionKey);
	const FString* Existing = Controls.Find(ActionKey);
	const bool bChanged = DefaultKey
		? (!Existing || !Existing->Equals(*DefaultKey, ESearchCase::CaseSensitive))
		: Existing != nullptr;
	if (!bChanged)
	{
		return;
	}
	if (DefaultKey)
	{
		Controls.Add(ActionKey, *DefaultKey);
	}
	else
	{
		Controls.Remove(ActionKey);
	}
	OnSettingsChanged.Broadcast();
}

// ------------------------------------------------------------------------ persistence

void UDASettings::WriteJson(TSharedPtr<FJsonObject>& Root) const
{
	if (!Root.IsValid())
	{
		return;
	}
	Root->SetStringField(TEXT("animation_speed"), AnimationSpeedToString(AnimationSpeed));
	Root->SetBoolField(TEXT("confirm_activation"), bConfirmActivation);
	Root->SetStringField(TEXT("text_speed"), TextSpeedToString(TextSpeed));
	Root->SetNumberField(TEXT("bgm_volume"), BgmVolume);
	Root->SetNumberField(TEXT("sfx_volume"), SfxVolume);
	Root->SetBoolField(TEXT("subtitles"), bSubtitles);
	Root->SetStringField(TEXT("language"), LanguageKey);

	TSharedPtr<FJsonObject> ControlsObject = MakeShared<FJsonObject>();
	for (const TPair<FString, FString>& Pair : Controls)
	{
		ControlsObject->SetStringField(Pair.Key, Pair.Value);
	}
	Root->SetObjectField(TEXT("controls"), ControlsObject);
}

bool UDASettings::ReadJson(const TSharedPtr<FJsonObject>& Root, FString& OutError)
{
	if (!Root.IsValid())
	{
		OutError = TEXT("Settings save data is missing.");
		return false;
	}

	// Parse into locals and commit only after the whole object validates, so a
	// malformed save cannot leave settings half applied (the save layer calls
	// ResetToDefaults before ReadSaveData).
	EDAAnimationSpeed NewAnimationSpeed = AnimationSpeed;
	bool bNewConfirmActivation = bConfirmActivation;
	EDATextSpeed NewTextSpeed = TextSpeed;
	float NewBgmVolume = BgmVolume;
	float NewSfxVolume = SfxVolume;
	bool bNewSubtitles = bSubtitles;
	FString NewLanguageKey = LanguageKey;
	TMap<FString, FString> NewControls = Controls;

	FString AnimationText;
	if (!ReadSpeedField(Root, TEXT("animation_speed"), AnimationText, OutError))
	{
		return false;
	}
	if (!AnimationText.IsEmpty())
	{
		NewAnimationSpeed = StringToAnimationSpeed(AnimationText, NewAnimationSpeed);
	}

	if (!ReadBoolField(Root, TEXT("confirm_activation"), bNewConfirmActivation, OutError))
	{
		return false;
	}

	FString TextSpeedText;
	if (!ReadSpeedField(Root, TEXT("text_speed"), TextSpeedText, OutError))
	{
		return false;
	}
	if (!TextSpeedText.IsEmpty())
	{
		NewTextSpeed = StringToTextSpeed(TextSpeedText, NewTextSpeed);
	}

	BgmVolume = FMath::Clamp(static_cast<float>(DAJson::ReadFiniteDouble(Root, TEXT("bgm_volume"), BgmVolume)), 0.0f, 1.0f);
	SfxVolume = FMath::Clamp(static_cast<float>(DAJson::ReadFiniteDouble(Root, TEXT("sfx_volume"), SfxVolume)), 0.0f, 1.0f);
	Root->TryGetBoolField(TEXT("subtitles"), bSubtitles);

	FString Language;
	if (!ReadStringField(Root, TEXT("language"), Language, OutError))
	{
		return false;
	}
	const FString TrimmedLanguage = Language.TrimStartAndEnd();
	if (!TrimmedLanguage.IsEmpty())
	{
		NewLanguageKey = TrimmedLanguage;
	}

	if (const TSharedPtr<FJsonValue> ControlsValue = Root->TryGetField(TEXT("controls")))
	{
		if (ControlsValue->Type != EJson::Object || !ControlsValue->AsObject().IsValid())
		{
			OutError = TEXT("Settings field 'controls' must be an object.");
			return false;
		}
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : ControlsValue->AsObject()->Values)
		{
			const FString ActionKey = SettingsJsonKeyToString(Pair.Key).TrimStartAndEnd();
			if (ActionKey.IsEmpty())
			{
				const FString KeyText = Pair.Value->AsString().TrimStartAndEnd();
				if (!KeyText.IsEmpty())
				{
					Controls.Add(DAJson::KeyToString(Pair.Key), KeyText);
				}
			}
		}
	}

	AnimationSpeed = NewAnimationSpeed;
	bConfirmActivation = bNewConfirmActivation;
	TextSpeed = NewTextSpeed;
	BgmVolume = NewBgmVolume;
	SfxVolume = NewSfxVolume;
	bSubtitles = bNewSubtitles;
	LanguageKey = NewLanguageKey;
	Controls = MoveTemp(NewControls);

	OnSettingsChanged.Broadcast();
	OutError.Reset();
	return true;
}
