// Duel Academy Island - save game implementation.
//
// The payload is canonical JSON (sorted object keys) so saving the same state
// twice produces byte-identical text. Writes are staged through a temporary
// slot, verified, and swapped in with IFileManager::Move; the previous file
// is kept in a "<slot>_backup" slot. Save files append a 16-byte CRC trailer
// to the USaveGame archive so corrupt input can be rejected before load.

#include "DASaveGame.h"

#include "DAProfileSubsystem.h"
#include "DASettings.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "HAL/UnrealMemory.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/Crc.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
	const TCHAR* const BackupSuffix = TEXT("_backup");
	const TCHAR* const TempSuffix = TEXT("_tmp");

	bool IsReservedSaveSection(const FString& Name)
	{
		static const TCHAR* const Reserved[] = {
			TEXT("version"), TEXT("slot"), TEXT("slot_name"), TEXT("saved_at"),
			TEXT("meta"), TEXT("profile"), TEXT("calendar"), TEXT("settings"),
			TEXT("flags"), TEXT("counters"), TEXT("emails"), TEXT("sections")
		};
		for (const TCHAR* Entry : Reserved)
		{
			if (Name.Equals(Entry, ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
		return false;
	}

	bool IsSafeSlotName(const FString& Name)
	{
		return !Name.IsEmpty()
			&& Name.Len() <= 64
			&& !Name.Contains(TEXT("/"))
			&& !Name.Contains(TEXT("\\"))
			&& !Name.Contains(TEXT(":"))
			&& !Name.Contains(TEXT(".."));
	}

	FString PeriodToKey(EDADayPeriod Period)
	{
		switch (Period)
		{
		case EDADayPeriod::PM:    return TEXT("PM");
		case EDADayPeriod::Night: return TEXT("Night");
		case EDADayPeriod::AM:
		default:                  return TEXT("AM");
		}
	}

	EDADayPeriod KeyToPeriod(const FString& Key)
	{
		if (Key.Equals(TEXT("PM"), ESearchCase::IgnoreCase))
		{
			return EDADayPeriod::PM;
		}
		if (Key.Equals(TEXT("Night"), ESearchCase::IgnoreCase)
			|| Key.Equals(TEXT("NIGHT"), ESearchCase::IgnoreCase))
		{
			return EDADayPeriod::Night;
		}
		return EDADayPeriod::AM;
	}

	void AppendJsonString(const FString& In, FString& Out)
	{
		Out.AppendChar(TCHAR('"'));
		for (const TCHAR C : In)
		{
			switch (C)
			{
			case TCHAR('"'):  Out += TEXT("\\\""); break;
			case TCHAR('\\'): Out += TEXT("\\\\"); break;
			case TCHAR('\b'): Out += TEXT("\\b"); break;
			case TCHAR('\f'): Out += TEXT("\\f"); break;
			case TCHAR('\n'): Out += TEXT("\\n"); break;
			case TCHAR('\r'): Out += TEXT("\\r"); break;
			case TCHAR('\t'): Out += TEXT("\\t"); break;
			default:
				if (C < 0x20)
				{
					Out += FString::Printf(TEXT("\\u%04x"), static_cast<int32>(C));
				}
				else
				{
					Out.AppendChar(C);
				}
				break;
			}
		}
		Out.AppendChar(TCHAR('"'));
	}

	void AppendCanonicalValue(const TSharedPtr<FJsonValue>& Value, FString& Out)
	{
		if (!Value.IsValid())
		{
			Out += TEXT("null");
			return;
		}

		switch (Value->Type)
		{
		case EJson::Object:
		{
			const TSharedPtr<FJsonObject>& Object = Value->AsObject();
			if (!Object.IsValid())
			{
				Out += TEXT("{}");
				return;
			}
			TArray<FJsonObject::FStringType> Keys;
			Object->Values.GetKeys(Keys);
			Keys.Sort([](const FJsonObject::FStringType& A, const FJsonObject::FStringType& B)
			{
				return FString(*A).Compare(FString(*B), ESearchCase::CaseSensitive) < 0;
			});
			Out.AppendChar(TCHAR('{'));
			for (int32 Index = 0; Index < Keys.Num(); ++Index)
			{
				if (Index > 0)
				{
					Out.AppendChar(TCHAR(','));
				}
				AppendJsonString(FString(*Keys[Index]), Out);
				Out.AppendChar(TCHAR(':'));
				AppendCanonicalValue(Object->Values.FindRef(Keys[Index]), Out);
			}
			Out.AppendChar(TCHAR('}'));
			break;
		}
		case EJson::Array:
		{
			const TArray<TSharedPtr<FJsonValue>>& Array = Value->AsArray();
			Out.AppendChar(TCHAR('['));
			for (int32 Index = 0; Index < Array.Num(); ++Index)
			{
				if (Index > 0)
				{
					Out.AppendChar(TCHAR(','));
				}
				AppendCanonicalValue(Array[Index], Out);
			}
			Out.AppendChar(TCHAR(']'));
			break;
		}
		case EJson::String:
			AppendJsonString(Value->AsString(), Out);
			break;
		case EJson::Number:
		{
			const double Number = Value->AsNumber();
			if (FMath::IsFinite(Number)
				&& FMath::FloorToDouble(Number) == Number
				&& FMath::Abs(Number) < 9.0e15)
			{
				Out += FString::Printf(TEXT("%lld"), static_cast<int64>(Number));
			}
			else
			{
				Out += FString::Printf(TEXT("%.17g"), Number);
			}
			break;
		}
		case EJson::Boolean:
			Out += Value->AsBool() ? TEXT("true") : TEXT("false");
			break;
		case EJson::Null:
		default:
			Out += TEXT("null");
			break;
		}
	}

	FString SerializeCanonical(const TSharedPtr<FJsonObject>& Root)
	{
		FString Out;
		if (Root.IsValid())
		{
			AppendCanonicalValue(MakeShared<FJsonValueObject>(Root), Out);
		}
		else
		{
			Out = TEXT("{}");
		}
		return Out;
	}

	bool ParseJsonObject(const FString& Json, TSharedPtr<FJsonObject>& OutRoot)
	{
		OutRoot.Reset();
		if (Json.IsEmpty())
		{
			return false;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		return FJsonSerializer::Deserialize(Reader, OutRoot) && OutRoot.IsValid();
	}

	FString ReadStringField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const TCHAR* Default = TEXT(""))
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Default;
	}

	/** Trailer appended to the serialized USaveGame archive. */
	constexpr uint32 SaveFileMagic = 0x53415044; // "DAPS"
	constexpr uint32 SaveFileFormatVersion = 1;

	struct FDASaveFileTrailer
	{
		uint32 Magic = 0;
		uint32 FormatVersion = 0;
		uint32 ArchiveSize = 0;
		uint32 ArchiveCrc = 0;
	};

	static_assert(sizeof(FDASaveFileTrailer) == 16, "Save trailer must stay 16 bytes");

	bool BuildSaveFileBytes(const TArray<uint8>& Archive, TArray<uint8>& OutFileBytes, FString& OutError)
	{
		if (Archive.Num() == 0)
		{
			OutError = TEXT("Cannot build a save file from an empty archive.");
			return false;
		}

		OutFileBytes = Archive;
		FDASaveFileTrailer Trailer;
		Trailer.Magic = SaveFileMagic;
		Trailer.FormatVersion = SaveFileFormatVersion;
		Trailer.ArchiveSize = static_cast<uint32>(Archive.Num());
		Trailer.ArchiveCrc = FCrc::MemCrc32(Archive.GetData(), Archive.Num());
		const int32 Offset = OutFileBytes.Num();
		OutFileBytes.AddUninitialized(static_cast<int32>(sizeof(FDASaveFileTrailer)));
		FMemory::Memcpy(OutFileBytes.GetData() + Offset, &Trailer, sizeof(FDASaveFileTrailer));
		return true;
	}

	bool ExtractSaveArchive(const TArray<uint8>& FileBytes, TArray<uint8>& OutArchive, FString& OutError)
	{
		if (FileBytes.Num() <= static_cast<int32>(sizeof(FDASaveFileTrailer)))
		{
			OutError = TEXT("Save file is too small.");
			return false;
		}

		FDASaveFileTrailer Trailer;
		FMemory::Memcpy(&Trailer, FileBytes.GetData() + FileBytes.Num() - sizeof(FDASaveFileTrailer), sizeof(FDASaveFileTrailer));
		if (Trailer.Magic != SaveFileMagic || Trailer.FormatVersion != SaveFileFormatVersion)
		{
			OutError = TEXT("Save file header is missing or from an unsupported format.");
			return false;
		}

		const int32 ArchiveSize = FileBytes.Num() - static_cast<int32>(sizeof(FDASaveFileTrailer));
		if (Trailer.ArchiveSize != static_cast<uint32>(ArchiveSize))
		{
			OutError = TEXT("Save file length does not match its trailer.");
			return false;
		}
		if (FCrc::MemCrc32(FileBytes.GetData(), ArchiveSize) != Trailer.ArchiveCrc)
		{
			OutError = TEXT("Save file failed its checksum.");
			return false;
		}

		OutArchive.Append(FileBytes.GetData(), ArchiveSize);
		return true;
	}

	bool LoadSaveObjectFromFile(const FString& Path, UDASaveGame*& OutSave, FString& OutError)
	{
		OutSave = nullptr;
		TArray<uint8> FileBytes;
		if (!FFileHelper::LoadFileToArray(FileBytes, *Path))
		{
			OutError = FString::Printf(TEXT("Could not read save file %s."), *Path);
			return false;
		}

		TArray<uint8> Archive;
		if (!ExtractSaveArchive(FileBytes, Archive, OutError))
		{
			return false;
		}

		USaveGame* Loaded = UGameplayStatics::LoadGameFromMemory(Archive);
		UDASaveGame* Save = Cast<UDASaveGame>(Loaded);
		if (!Save)
		{
			OutError = FString::Printf(TEXT("Save file %s does not contain a UDASaveGame object."), *Path);
			return false;
		}
		OutSave = Save;
		return true;
	}

	TSharedPtr<FJsonObject> MakeDefaultSettingsJson()
	{
		TSharedPtr<FJsonObject> Settings = MakeShared<FJsonObject>();
		Settings->SetStringField(TEXT("animation_speed"), TEXT("normal"));
		Settings->SetBoolField(TEXT("confirm_activation"), true);
		Settings->SetStringField(TEXT("text_speed"), TEXT("normal"));
		Settings->SetNumberField(TEXT("bgm_volume"), 0.8);
		Settings->SetNumberField(TEXT("sfx_volume"), 0.8);
		Settings->SetBoolField(TEXT("subtitles"), true);
		Settings->SetStringField(TEXT("language"), TEXT("en"));
		Settings->SetObjectField(TEXT("controls"), MakeShared<FJsonObject>());
		return Settings;
	}

	void EnsureObjectField(const TSharedPtr<FJsonObject>& Root, const TCHAR* Field, TSharedPtr<FJsonObject>& OutObject)
	{
		const TSharedPtr<FJsonObject>* Existing = nullptr;
		if (Root->TryGetObjectField(Field, Existing) && Existing && Existing->IsValid())
		{
			OutObject = *Existing;
		}
		else
		{
			OutObject = MakeShared<FJsonObject>();
			Root->SetObjectField(Field, OutObject);
		}
	}

	void MoveStringField(const TSharedPtr<FJsonObject>& From, const TSharedPtr<FJsonObject>& To, const TCHAR* Field, const TCHAR* NewField = nullptr)
	{
		FString Value;
		if (From->TryGetStringField(Field, Value))
		{
			const TCHAR* Target = NewField ? NewField : Field;
			if (!To->HasField(Target))
			{
				To->SetStringField(Target, Value);
			}
			From->RemoveField(Field);
		}
	}

	void MoveNumberField(const TSharedPtr<FJsonObject>& From, const TSharedPtr<FJsonObject>& To, const TCHAR* Field, const TCHAR* NewField = nullptr)
	{
		int32 Value = 0;
		if (From->TryGetNumberField(Field, Value))
		{
			const TCHAR* Target = NewField ? NewField : Field;
			if (!To->HasField(Target))
			{
				To->SetNumberField(Target, Value);
			}
			From->RemoveField(Field);
		}
	}

	/** Double-preserving variant used by fields such as playtime_seconds. */
	void MoveDoubleField(const TSharedPtr<FJsonObject>& From, const TSharedPtr<FJsonObject>& To, const TCHAR* Field, const TCHAR* NewField = nullptr)
	{
		double Value = 0.0;
		if (From->TryGetNumberField(Field, Value))
		{
			const TCHAR* Target = NewField ? NewField : Field;
			if (FMath::IsFinite(Value) && !To->HasField(Target))
			{
				To->SetNumberField(Target, Value);
			}
			From->RemoveField(Field);
		}
	}

	void MoveCounter(const TSharedPtr<FJsonObject>& Counters, const TCHAR* OldName, const TCHAR* NewName)
	{
		int32 Value = 0;
		if (Counters->TryGetNumberField(OldName, Value))
		{
			if (!Counters->HasField(NewName))
			{
				Counters->SetNumberField(NewName, Value);
			}
			Counters->RemoveField(OldName);
		}
	}

	bool MigrateLegacyPayloadToV1(const TSharedPtr<FJsonObject>& Root, FString& OutError)
	{
		// v0 was a loose, partly flat payload used during early prototyping.
		// Move known top-level identity fields into "profile" and keep unknown
		// top-level sections intact.
		TSharedPtr<FJsonObject> Profile;
		EnsureObjectField(Root, TEXT("profile"), Profile);

		MoveStringField(Root, Profile, TEXT("name"));
		MoveStringField(Root, Profile, TEXT("dorm"));
		MoveStringField(Root, Profile, TEXT("title"));
		MoveNumberField(Root, Profile, TEXT("dp"));
		MoveStringField(Root, Profile, TEXT("gender"));
		MoveDoubleField(Root, Profile, TEXT("playtime_seconds"));

		if (!Profile->HasField(TEXT("name")))
		{
			Profile->SetStringField(TEXT("name"), TEXT("New Student"));
		}
		if (!Profile->HasField(TEXT("dorm")))
		{
			Profile->SetStringField(TEXT("dorm"), TEXT("Slifer"));
		}
		if (!Profile->HasField(TEXT("title")))
		{
			Profile->SetStringField(TEXT("title"), TEXT("Apprentice Duelist"));
		}

		FString ProfileName;
		FString ProfileDorm;
		FString ProfileTitle;
		Profile->TryGetStringField(TEXT("name"), ProfileName);
		Profile->TryGetStringField(TEXT("dorm"), ProfileDorm);
		Profile->TryGetStringField(TEXT("title"), ProfileTitle);
		if (ProfileName.IsEmpty())
		{
			Profile->SetStringField(TEXT("name"), TEXT("New Student"));
		}
		if (ProfileDorm.IsEmpty())
		{
			Profile->SetStringField(TEXT("dorm"), TEXT("Slifer"));
		}
		if (ProfileTitle.IsEmpty())
		{
			Profile->SetStringField(TEXT("title"), TEXT("Apprentice Duelist"));
		}
		if (!Profile->HasField(TEXT("dp")))
		{
			Profile->SetNumberField(TEXT("dp"), 3000);
		}
		if (!Profile->HasField(TEXT("gender")))
		{
			Profile->SetStringField(TEXT("gender"), TEXT("unspecified"));
		}
		if (!Profile->HasField(TEXT("playtime_seconds")))
		{
			Profile->SetNumberField(TEXT("playtime_seconds"), 0);
		}

		TSharedPtr<FJsonObject> Calendar;
		EnsureObjectField(Root, TEXT("calendar"), Calendar);
		MoveNumberField(Root, Calendar, TEXT("year"));
		MoveNumberField(Root, Calendar, TEXT("day"));
		MoveStringField(Root, Calendar, TEXT("period"));

		int32 MonthNumber = 0;
		if (Root->TryGetNumberField(TEXT("month"), MonthNumber))
		{
			Root->RemoveField(TEXT("month"));
		}
		else if (Calendar->TryGetNumberField(TEXT("month"), MonthNumber))
		{
			Calendar->RemoveField(TEXT("month"));
		}
		if (MonthNumber != 0 && !Calendar->HasField(TEXT("month_index")))
		{
			const int32 Converted = ((MonthNumber - 10) % 12 + 12) % 12;
			Calendar->SetNumberField(TEXT("month_index"), Converted);
		}
		Calendar->RemoveField(TEXT("month"));

		if (!Calendar->HasField(TEXT("year")))
		{
			Calendar->SetNumberField(TEXT("year"), 1);
		}
		if (!Calendar->HasField(TEXT("month_index")))
		{
			Calendar->SetNumberField(TEXT("month_index"), 0);
		}
		if (!Calendar->HasField(TEXT("day")))
		{
			Calendar->SetNumberField(TEXT("day"), 7);
		}
		if (!Calendar->HasField(TEXT("period")))
		{
			Calendar->SetStringField(TEXT("period"), TEXT("AM"));
		}

		if (!Root->HasField(TEXT("settings")))
		{
			Root->SetObjectField(TEXT("settings"), MakeDefaultSettingsJson());
		}

		TSharedPtr<FJsonObject> Flags;
		EnsureObjectField(Root, TEXT("flags"), Flags);

		TSharedPtr<FJsonObject> Counters;
		EnsureObjectField(Root, TEXT("counters"), Counters);
		MoveCounter(Counters, TEXT("wins"), TEXT("wins_total"));
		MoveCounter(Counters, TEXT("duels"), TEXT("duels_total"));
		MoveCounter(Counters, TEXT("timed"), TEXT("timed_clears"));
		MoveCounter(Counters, TEXT("written"), TEXT("written_correct"));
		MoveCounter(Counters, TEXT("events"), TEXT("story_events_cleared"));
		MoveCounter(Counters, TEXT("cards"), TEXT("cards_owned"));

		TSharedPtr<FJsonObject> Emails;
		EnsureObjectField(Root, TEXT("emails"), Emails);

		TSharedPtr<FJsonObject> Meta;
		EnsureObjectField(Root, TEXT("meta"), Meta);
		if (!Meta->HasField(TEXT("name")))
		{
			Meta->SetStringField(TEXT("name"), ReadStringField(Profile, TEXT("name"), TEXT("New Student")));
		}
		if (!Meta->HasField(TEXT("title")))
		{
			Meta->SetStringField(TEXT("title"), ReadStringField(Profile, TEXT("title"), TEXT("Apprentice Duelist")));
		}
		if (!Meta->HasField(TEXT("dorm")))
		{
			Meta->SetStringField(TEXT("dorm"), ReadStringField(Profile, TEXT("dorm"), TEXT("Slifer")));
		}
		if (!Meta->HasField(TEXT("dp")))
		{
			int32 DP = 0;
			Profile->TryGetNumberField(TEXT("dp"), DP);
			Meta->SetNumberField(TEXT("dp"), FMath::Max(0, DP));
		}
		if (!Meta->HasField(TEXT("playtime_seconds")))
		{
			double Playtime = 0.0;
			if (Profile->TryGetNumberField(TEXT("playtime_seconds"), Playtime) && FMath::IsFinite(Playtime))
			{
				Meta->SetNumberField(TEXT("playtime_seconds"), FMath::Max(0.0, Playtime));
			}
			else
			{
				Meta->SetNumberField(TEXT("playtime_seconds"), 0.0);
			}
		}
		if (!Meta->HasField(TEXT("year")))
		{
			int32 Year = 1;
			Calendar->TryGetNumberField(TEXT("year"), Year);
			Meta->SetNumberField(TEXT("year"), Year);
		}
		if (!Meta->HasField(TEXT("month_index")))
		{
			int32 MonthIndex = 0;
			Calendar->TryGetNumberField(TEXT("month_index"), MonthIndex);
			Meta->SetNumberField(TEXT("month_index"), MonthIndex);
		}
		if (!Meta->HasField(TEXT("day")))
		{
			int32 Day = 7;
			Calendar->TryGetNumberField(TEXT("day"), Day);
			Meta->SetNumberField(TEXT("day"), Day);
		}
		if (!Meta->HasField(TEXT("period")))
		{
			FString Period;
			Calendar->TryGetStringField(TEXT("period"), Period);
			Meta->SetStringField(TEXT("period"), Period.IsEmpty() ? TEXT("AM") : Period);
		}

		Root->SetNumberField(TEXT("version"), 1);
		OutError.Reset();
		return true;
	}
}

UDASaveGame::UDASaveGame()
{
	Version = 1;
}

// ------------------------------------------------------------------------ subsystem

void UDASaveSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	LastError.Reset();
}

void UDASaveSubsystem::Deinitialize()
{
	PayloadProviders.Reset();
	Super::Deinitialize();
}

UDASaveSubsystem* UDASaveSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	if (const UWorld* World = WorldContext->GetWorld())
	{
		if (UGameInstance* GameInstance = World->GetGameInstance())
		{
			return GameInstance->GetSubsystem<UDASaveSubsystem>();
		}
	}
	return nullptr;
}

bool UDASaveSubsystem::IsValidSlotIndex(int32 SlotIndex)
{
	return SlotIndex >= 0 && SlotIndex < NumSlots;
}

FString UDASaveSubsystem::GetSlotName(int32 SlotIndex)
{
	switch (SlotIndex)
	{
	case 0: return TEXT("DASave_Auto");
	case 1: return TEXT("DASave_Slot1");
	case 2: return TEXT("DASave_Slot2");
	case 3: return TEXT("DASave_Slot3");
	default: return FString();
	}
}

FString UDASaveSubsystem::GetSaveFilePath(const FString& SlotName)
{
	if (SlotName.IsEmpty())
	{
		return FString();
	}
	return FPaths::ConvertRelativePathToFull(
		FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("SaveGames"), SlotName + TEXT(".sav")));
}

UDAProfileSubsystem* UDASaveSubsystem::ResolveProfile() const
{
	if (const UGameInstance* GameInstance = GetGameInstance())
	{
		return GameInstance->GetSubsystem<UDAProfileSubsystem>();
	}
	return nullptr;
}

UDACalendarSubsystem* UDASaveSubsystem::ResolveCalendar() const
{
	if (const UGameInstance* GameInstance = GetGameInstance())
	{
		return GameInstance->GetSubsystem<UDACalendarSubsystem>();
	}
	return nullptr;
}

UDASettings* UDASaveSubsystem::ResolveSettings() const
{
	if (const UGameInstance* GameInstance = GetGameInstance())
	{
		return GameInstance->GetSubsystem<UDASettings>();
	}
	return nullptr;
}

// ------------------------------------------------------------------------ slots

bool UDASaveSubsystem::SaveSlot(int32 SlotIndex, FString& OutError)
{
	if (!IsValidSlotIndex(SlotIndex))
	{
		SetError(FString::Printf(TEXT("Invalid save slot %d."), SlotIndex));
		OutError = LastError;
		return false;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	UDASettings* Settings = ResolveSettings();
	if (!Profile || !Calendar || !Settings)
	{
		SetError(TEXT("Save failed: one or more progression subsystems are unavailable."));
		OutError = LastError;
		return false;
	}
	return SaveSlotWithContext(SlotIndex, Profile, Calendar, Settings, OutError);
}

bool UDASaveSubsystem::SaveSlotWithContext(int32 SlotIndex, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError)
{
	if (!IsValidSlotIndex(SlotIndex))
	{
		SetError(FString::Printf(TEXT("Invalid save slot %d."), SlotIndex));
		OutError = LastError;
		return false;
	}
	return SaveNamedSlotWithContext(GetSlotName(SlotIndex), SlotIndex, Profile, Calendar, Settings, OutError);
}

bool UDASaveSubsystem::SaveNamedSlotWithContext(const FString& SlotName, int32 LogicalSlotIndex, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError)
{
	if (!IsSafeSlotName(SlotName))
	{
		SetError(FString::Printf(TEXT("Invalid save slot name '%s'."), *SlotName));
		OutError = LastError;
		OnSaveError.Broadcast(LastError);
		return false;
	}
	if (!Profile || !Calendar || !Settings)
	{
		SetError(TEXT("Save failed: missing progression context."));
		OutError = LastError;
		OnSaveError.Broadcast(LastError);
		return false;
	}
	if (!Profile->IsInitialized())
	{
		SetError(TEXT("Save failed: the profile has not been initialized."));
		OutError = LastError;
		OnSaveError.Broadcast(LastError);
		return false;
	}

	FString Json;
	if (!BuildPayload(LogicalSlotIndex, SlotName, Profile, Calendar, Settings, Json, OutError))
	{
		SetError(OutError);
		OnSaveError.Broadcast(LastError);
		return false;
	}
	if (!WriteAtomic(SlotName, Json, OutError))
	{
		SetError(OutError);
		OnSaveError.Broadcast(LastError);
		return false;
	}

	LastError.Reset();
	OutError.Reset();
	OnSaveCompleted.Broadcast(LogicalSlotIndex, true);
	return true;
}

bool UDASaveSubsystem::LoadSlot(int32 SlotIndex, FString& OutError)
{
	if (!IsValidSlotIndex(SlotIndex))
	{
		SetError(FString::Printf(TEXT("Invalid save slot %d."), SlotIndex));
		OutError = LastError;
		return false;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	UDASettings* Settings = ResolveSettings();
	if (!Profile || !Calendar || !Settings)
	{
		SetError(TEXT("Load failed: one or more progression subsystems are unavailable."));
		OutError = LastError;
		return false;
	}
	return LoadSlotWithContext(SlotIndex, Profile, Calendar, Settings, OutError);
}

bool UDASaveSubsystem::LoadSlotWithContext(int32 SlotIndex, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError, bool* bOutRecoveredFromBackup)
{
	if (!IsValidSlotIndex(SlotIndex))
	{
		SetError(FString::Printf(TEXT("Invalid save slot %d."), SlotIndex));
		OutError = LastError;
		return false;
	}
	return LoadNamedSlotWithContext(GetSlotName(SlotIndex), Profile, Calendar, Settings, OutError, bOutRecoveredFromBackup);
}

bool UDASaveSubsystem::LoadNamedSlotWithContext(const FString& SlotName, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError, bool* bOutRecoveredFromBackup)
{
	if (bOutRecoveredFromBackup)
	{
		*bOutRecoveredFromBackup = false;
	}
	if (!Profile || !Calendar || !Settings)
	{
		SetError(TEXT("Load failed: missing progression context."));
		OutError = LastError;
		OnLoadCompleted.Broadcast(-1, false);
		return false;
	}
	if (!IsSafeSlotName(SlotName))
	{
		SetError(FString::Printf(TEXT("Invalid save slot name '%s'."), *SlotName));
		OutError = LastError;
		OnLoadCompleted.Broadcast(-1, false);
		return false;
	}

	FString Json;
	bool bUsedBackup = false;
	if (!ReadPayloadFile(SlotName, Json, bUsedBackup, OutError))
	{
		SetError(OutError);
		OnLoadCompleted.Broadcast(-1, false);
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	if (!ParseJsonObject(Json, Root))
	{
		SetError(FString::Printf(TEXT("Save slot '%s' contains invalid JSON."), *SlotName));
		OutError = LastError;
		OnLoadCompleted.Broadcast(-1, false);
		return false;
	}
	if (!ApplyPayload(Root, Profile, Calendar, Settings, OutError))
	{
		SetError(OutError);
		OnLoadCompleted.Broadcast(-1, false);
		return false;
	}

	if (bOutRecoveredFromBackup)
	{
		*bOutRecoveredFromBackup = bUsedBackup;
	}
	LastError.Reset();
	OutError.Reset();
	OnLoadCompleted.Broadcast(-1, true);
	return true;
}

bool UDASaveSubsystem::DeleteSlot(int32 SlotIndex, FString& OutError)
{
	if (!IsValidSlotIndex(SlotIndex))
	{
		SetError(FString::Printf(TEXT("Invalid save slot %d."), SlotIndex));
		OutError = LastError;
		return false;
	}
	return DeleteNamedSlot(GetSlotName(SlotIndex), OutError);
}

bool UDASaveSubsystem::DeleteNamedSlot(const FString& SlotName, FString& OutError)
{
	if (!IsSafeSlotName(SlotName))
	{
		SetError(FString::Printf(TEXT("Invalid save slot name '%s'."), *SlotName));
		OutError = LastError;
		return false;
	}

	UGameplayStatics::DeleteGameInSlot(SlotName, 0);
	UGameplayStatics::DeleteGameInSlot(SlotName + BackupSuffix, 0);
	UGameplayStatics::DeleteGameInSlot(SlotName + TempSuffix, 0);

	IFileManager& FileManager = IFileManager::Get();
	FileManager.Delete(*GetSaveFilePath(SlotName), false);
	FileManager.Delete(*GetSaveFilePath(SlotName + BackupSuffix), false);
	FileManager.Delete(*GetSaveFilePath(SlotName + TempSuffix), false);

	const bool bPrimaryRemaining = FileManager.FileExists(*GetSaveFilePath(SlotName));
	const bool bBackupRemaining = FileManager.FileExists(*GetSaveFilePath(SlotName + BackupSuffix));
	const bool bTempRemaining = FileManager.FileExists(*GetSaveFilePath(SlotName + TempSuffix));
	if (bPrimaryRemaining || bBackupRemaining || bTempRemaining)
	{
		SetError(FString::Printf(TEXT("Could not delete every file for save slot '%s'."), *SlotName));
		OutError = LastError;
		return false;
	}

	LastError.Reset();
	OutError.Reset();
	return true;
}

TArray<FDASaveSlotInfo> UDASaveSubsystem::EnumerateSlots() const
{
	TArray<FDASaveSlotInfo> Slots;
	Slots.Reserve(NumSlots);
	for (int32 Index = 0; Index < NumSlots; ++Index)
	{
		FDASaveSlotInfo Info = GetSlotInfo(GetSlotName(Index), Index);
		Info.SlotIndex = Index;
		Info.SlotName = GetSlotName(Index);
		Info.bIsAutosave = Index == AutosaveSlotIndex;
		Slots.Add(MoveTemp(Info));
	}
	return Slots;
}

bool UDASaveSubsystem::HasSave(int32 SlotIndex) const
{
	if (!IsValidSlotIndex(SlotIndex))
	{
		return false;
	}
	const FString SlotName = GetSlotName(SlotIndex);
	IFileManager& FileManager = IFileManager::Get();
	return FileManager.FileExists(*GetSaveFilePath(SlotName))
		|| FileManager.FileExists(*GetSaveFilePath(SlotName + BackupSuffix));
}

FDASaveSlotInfo UDASaveSubsystem::GetSlotInfo(const FString& SlotName, int32 SlotIndex) const
{
	FDASaveSlotInfo Info;
	Info.SlotIndex = SlotIndex;
	Info.SlotName = SlotName;
	Info.bIsAutosave = SlotIndex == AutosaveSlotIndex;

	if (!IsSafeSlotName(SlotName))
	{
		Info.bCorrupt = true;
		return Info;
	}

	IFileManager& FileManager = IFileManager::Get();
	const bool bPrimaryExists = FileManager.FileExists(*GetSaveFilePath(SlotName));
	const bool bBackupExists = FileManager.FileExists(*GetSaveFilePath(SlotName + BackupSuffix));
	Info.bExists = bPrimaryExists || bBackupExists;
	if (!Info.bExists)
	{
		return Info;
	}

	FString Json;
	bool bUsedBackup = false;
	FString Error;
	if (!ReadPayloadFile(SlotName, Json, bUsedBackup, Error))
	{
		Info.bCorrupt = true;
		return Info;
	}

	TSharedPtr<FJsonObject> Root;
	if (!ParseJsonObject(Json, Root))
	{
		Info.bCorrupt = true;
		return Info;
	}

	Info.bUsingBackup = bUsedBackup;
	Info.Version = GetVersionFromJson(Json);

	if (const TSharedPtr<FJsonObject>* Meta = nullptr; Root->TryGetObjectField(TEXT("meta"), Meta) && Meta && Meta->IsValid())
	{
		(*Meta)->TryGetStringField(TEXT("name"), Info.PlayerName);
		(*Meta)->TryGetStringField(TEXT("title"), Info.Title);
		(*Meta)->TryGetStringField(TEXT("saved_at"), Info.SavedAtUtc);
		FString DormKey;
		if ((*Meta)->TryGetStringField(TEXT("dorm"), DormKey))
		{
			Info.Dorm = DuelAcademyProfile::ParseDorm(DormKey);
		}
		(*Meta)->TryGetNumberField(TEXT("dp"), Info.DP);
		(*Meta)->TryGetNumberField(TEXT("playtime_seconds"), Info.PlaytimeSeconds);
		(*Meta)->TryGetNumberField(TEXT("year"), Info.Year);
		(*Meta)->TryGetNumberField(TEXT("month_index"), Info.MonthIndex);
		(*Meta)->TryGetNumberField(TEXT("day"), Info.Day);
		FString PeriodText;
		if ((*Meta)->TryGetStringField(TEXT("period"), PeriodText))
		{
			Info.Period = KeyToPeriod(PeriodText);
		}
	}

	// Legacy/migrated payloads may not have complete metadata yet.
	if (Info.PlayerName.IsEmpty())
	{
		if (const TSharedPtr<FJsonObject>* Profile = nullptr; Root->TryGetObjectField(TEXT("profile"), Profile) && Profile && Profile->IsValid())
		{
			(*Profile)->TryGetStringField(TEXT("name"), Info.PlayerName);
			(*Profile)->TryGetStringField(TEXT("title"), Info.Title);
			int32 DP = 0;
			if ((*Profile)->TryGetNumberField(TEXT("dp"), DP))
			{
				Info.DP = DP;
			}
			FString DormKey;
			if ((*Profile)->TryGetStringField(TEXT("dorm"), DormKey))
			{
				Info.Dorm = DuelAcademyProfile::ParseDorm(DormKey);
			}
		}
	}
	if (Info.SavedAtUtc.IsEmpty())
	{
		Root->TryGetStringField(TEXT("saved_at"), Info.SavedAtUtc);
	}
	return Info;
}

// ------------------------------------------------------------------------ autosave

void UDASaveSubsystem::RequestAutosave(const FString& Reason)
{
	LastAutosaveReason = Reason;
	if (!bAutosaveEnabled)
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Autosave skipped (%s): autosave disabled."), *Reason);
		return;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	if (!Profile || !Profile->IsInitialized())
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Autosave skipped (%s): profile is not initialized."), *Reason);
		return;
	}

	FString Error;
	if (SaveSlot(AutosaveSlotIndex, Error))
	{
		LastAutosaveTime = FPlatformTime::Seconds();
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Autosave complete (%s)."), *Reason);
	}
	else
	{
		SetError(FString::Printf(TEXT("Autosave failed (%s): %s"), *Reason, *Error));
	}
}

// ------------------------------------------------------------------------ payload

bool UDASaveSubsystem::BuildPayload(int32 LogicalSlotIndex, const FString& SlotName, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutJson, FString& OutError) const
{
	if (!Profile || !Calendar || !Settings)
	{
		OutError = TEXT("Cannot build save payload without profile, calendar and settings.");
		return false;
	}

	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("version"), CurrentVersion);
	Root->SetNumberField(TEXT("slot"), LogicalSlotIndex);
	Root->SetStringField(TEXT("slot_name"), SlotName);
	Root->SetStringField(TEXT("saved_at"), FDateTime::UtcNow().ToIso8601());

	Profile->WriteSaveData(Root);
	Calendar->WriteSaveData(Root);
	{
		TSharedPtr<FJsonObject> SettingsObject = MakeShared<FJsonObject>();
		Settings->WriteSaveData(SettingsObject);
		Root->SetObjectField(TEXT("settings"), SettingsObject);
	}

	TSharedPtr<FJsonObject> Meta = MakeShared<FJsonObject>();
	Meta->SetStringField(TEXT("name"), Profile->GetPlayerName());
	Meta->SetStringField(TEXT("title"), Profile->GetTitle());
	Meta->SetStringField(TEXT("dorm"), DuelAcademyProfile::DormToSaveKey(Profile->GetDorm()));
	Meta->SetNumberField(TEXT("dp"), Profile->GetDP());
	Meta->SetNumberField(TEXT("playtime_seconds"), Profile->GetPlaytimeSeconds());
	Meta->SetNumberField(TEXT("year"), Calendar->GetYear());
	Meta->SetNumberField(TEXT("month"), Calendar->GetMonthNumber());
	Meta->SetNumberField(TEXT("month_index"), Calendar->GetMonthIndex());
	Meta->SetNumberField(TEXT("day"), Calendar->GetDay());
	Meta->SetStringField(TEXT("period"), PeriodToKey(Calendar->GetPeriod()));
	Root->SetObjectField(TEXT("meta"), Meta);

	for (const TWeakObjectPtr<UObject>& WeakProvider : PayloadProviders)
	{
		UObject* ProviderObject = WeakProvider.Get();
		IDASavePayloadProvider* Provider = Cast<IDASavePayloadProvider>(ProviderObject);
		if (!Provider)
		{
			continue;
		}
		const FString SectionName = Provider->GetSaveSectionName();
		if (!IsSafeSlotName(SectionName) || IsReservedSaveSection(SectionName))
		{
			OutError = FString::Printf(TEXT("Save provider '%s' uses a reserved or invalid section name."), *SectionName);
			return false;
		}
		TSharedPtr<FJsonObject> Section = MakeShared<FJsonObject>();
		if (!Provider->WriteSaveSection(Section))
		{
			OutError = FString::Printf(TEXT("Save provider '%s' failed to write its section."), *SectionName);
			return false;
		}
		Root->SetObjectField(SectionName, Section);
	}

	OutJson = SerializeCanonical(Root);
	OutError.Reset();
	return true;
}

bool UDASaveSubsystem::ApplyPayload(const TSharedPtr<FJsonObject>& Root, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError) const
{
	if (!Root.IsValid() || !Profile || !Calendar || !Settings)
	{
		OutError = TEXT("Cannot apply an empty save payload.");
		return false;
	}

	// The calendar writes a root "calendar" object; ReadSaveData also accepts
	// legacy payloads that placed year/month/day/period directly at the root.
	if (!Calendar->ReadSaveData(Root, OutError))
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* SettingsObject = nullptr;
	if (Root->TryGetObjectField(TEXT("settings"), SettingsObject) && SettingsObject && SettingsObject->IsValid())
	{
		Settings->ResetToDefaults();
		if (!Settings->ReadSaveData(*SettingsObject, OutError))
		{
			return false;
		}
	}
	else
	{
		Settings->ResetToDefaults();
	}

	if (!Profile->ReadSaveData(Root, OutError))
	{
		return false;
	}

	for (const TWeakObjectPtr<UObject>& WeakProvider : PayloadProviders)
	{
		UObject* ProviderObject = WeakProvider.Get();
		IDASavePayloadProvider* Provider = Cast<IDASavePayloadProvider>(ProviderObject);
		if (!Provider)
		{
			continue;
		}
		const FString SectionName = Provider->GetSaveSectionName();
		const TSharedPtr<FJsonObject>* Section = nullptr;
		if (!Root->TryGetObjectField(SectionName, Section) || !Section || !Section->IsValid())
		{
			// Sections may be absent in older saves; the provider keeps its defaults.
			continue;
		}
		if (!Provider->ReadSaveSection(*Section, OutError))
		{
			OutError = FString::Printf(TEXT("Save provider '%s' failed to read its section: %s"), *SectionName, *OutError);
			return false;
		}
	}

	OutError.Reset();
	return true;
}

// ------------------------------------------------------------------------ file IO

bool UDASaveSubsystem::WriteAtomic(const FString& SlotName, const FString& Json, FString& OutError)
{
	OutError.Reset();
	const FString PrimaryPath = GetSaveFilePath(SlotName);
	const FString BackupPath = GetSaveFilePath(SlotName + BackupSuffix);
	const FString TempPath = GetSaveFilePath(SlotName + TempSuffix);

	IFileManager& FileManager = IFileManager::Get();
	FileManager.MakeDirectory(*FPaths::GetPath(PrimaryPath), true);
	FileManager.Delete(*TempPath, false);

	UDASaveGame* SaveObject = NewObject<UDASaveGame>();
	SaveObject->Version = CurrentVersion;
	SaveObject->JsonPayload = Json;
	SaveObject->PayloadHash = static_cast<int32>(FCrc::StrCrc32(*Json));

	TArray<uint8> Archive;
	if (!UGameplayStatics::SaveGameToMemory(SaveObject, Archive) || Archive.Num() == 0)
	{
		OutError = FString::Printf(TEXT("Could not serialize save slot '%s'."), *SlotName);
		return false;
	}

	TArray<uint8> FileBytes;
	if (!BuildSaveFileBytes(Archive, FileBytes, OutError))
	{
		return false;
	}
	if (!FFileHelper::SaveArrayToFile(FileBytes, *TempPath))
	{
		OutError = FString::Printf(TEXT("Could not write temporary save file for '%s'."), *SlotName);
		return false;
	}

	// Verify the staged file before touching the live slot.
	UDASaveGame* StagedSave = nullptr;
	FString StagedError;
	if (!LoadSaveObjectFromFile(TempPath, StagedSave, StagedError)
		|| !StagedSave
		|| StagedSave->PayloadHash != static_cast<int32>(FCrc::StrCrc32(*StagedSave->JsonPayload))
		|| StagedSave->JsonPayload != Json)
	{
		FileManager.Delete(*TempPath, false);
		OutError = FString::Printf(TEXT("Temporary save for '%s' failed verification: %s"), *SlotName, *StagedError);
		return false;
	}

	// Keep the previous primary as the recovery copy, but never overwrite a
	// good backup with a corrupt primary. IFileManager::Copy returns COPY_OK (0)
	// on success.
	FString ExistingJson;
	int32 ExistingVersion = 0;
	FString ExistingError;
	const bool bPrimaryIsValid = FileManager.FileExists(*PrimaryPath)
		&& ReadPayloadFromSlotName(SlotName, ExistingJson, ExistingVersion, ExistingError);
	if (bPrimaryIsValid)
	{
		if (FileManager.Copy(*BackupPath, *PrimaryPath, true, true) != COPY_OK)
		{
			FileManager.Delete(*TempPath, false);
			OutError = TEXT("Could not create the save backup; the existing slot was left untouched.");
			return false;
		}
	}

	if (!FileManager.Move(*PrimaryPath, *TempPath, true, true))
	{
		if (FileManager.Copy(*PrimaryPath, *TempPath, true, true) != COPY_OK)
		{
			FileManager.Delete(*TempPath, false);
			OutError = FString::Printf(TEXT("Could not commit save slot '%s'."), *SlotName);
			return false;
		}
		FileManager.Delete(*TempPath, false);
	}

	// Verify the committed slot too. A failure leaves the backup in place.
	UDASaveGame* VerifiedSave = nullptr;
	FString VerifiedError;
	if (!LoadSaveObjectFromFile(PrimaryPath, VerifiedSave, VerifiedError)
		|| !VerifiedSave
		|| VerifiedSave->PayloadHash != static_cast<int32>(FCrc::StrCrc32(*VerifiedSave->JsonPayload))
		|| VerifiedSave->JsonPayload != Json)
	{
		OutError = FString::Printf(TEXT("Committed save slot '%s' failed verification: %s"), *SlotName, *VerifiedError);
		return false;
	}

	OutError.Reset();
	return true;
}

bool UDASaveSubsystem::ReadPayloadFromSlotName(const FString& SlotName, FString& OutJson, int32& OutVersion, FString& OutError) const
{
	OutJson.Reset();
	OutVersion = -1;

	if (!IFileManager::Get().FileExists(*GetSaveFilePath(SlotName)))
	{
		OutError = FString::Printf(TEXT("Save slot '%s' does not exist."), *SlotName);
		return false;
	}

	UDASaveGame* Save = nullptr;
	FString LoadError;
	if (!LoadSaveObjectFromFile(GetSaveFilePath(SlotName), Save, LoadError) || !Save)
	{
		OutError = FString::Printf(TEXT("Save slot '%s' could not be loaded: %s"), *SlotName, *LoadError);
		return false;
	}
	if (Save->JsonPayload.IsEmpty())
	{
		OutError = FString::Printf(TEXT("Save slot '%s' has an empty payload."), *SlotName);
		return false;
	}
	if (Save->PayloadHash != static_cast<int32>(FCrc::StrCrc32(*Save->JsonPayload)))
	{
		OutError = FString::Printf(TEXT("Save slot '%s' failed its checksum."), *SlotName);
		return false;
	}
	if (Save->Version > CurrentVersion)
	{
		OutError = FString::Printf(TEXT("Save slot '%s' is version %d; this build supports up to %d."), *SlotName, Save->Version, CurrentVersion);
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	if (!ParseJsonObject(Save->JsonPayload, Root))
	{
		OutError = FString::Printf(TEXT("Save slot '%s' contains invalid JSON."), *SlotName);
		return false;
	}

	// The JSON schema version is authoritative when present, including version 0
	// (the legacy flat payload). This matters for v0 payloads that were archived
	// with a wrapper version of 1.
	int32 JsonVersion = -1;
	if (Root->TryGetNumberField(TEXT("version"), JsonVersion) && JsonVersion >= 0)
	{
		OutVersion = JsonVersion;
	}
	if (OutVersion < 0)
	{
		OutVersion = Save->Version;
	}
	if (OutVersion > CurrentVersion)
	{
		OutError = FString::Printf(TEXT("Save slot '%s' payload is version %d; this build supports up to %d."), *SlotName, OutVersion, CurrentVersion);
		return false;
	}

	OutJson = Save->JsonPayload;
	if (OutVersion < CurrentVersion)
	{
		if (!MigrateJson(OutJson, OutVersion, OutError))
		{
			OutError = FString::Printf(TEXT("Save slot '%s' could not be migrated: %s"), *SlotName, *OutError);
			return false;
		}
	}

	OutError.Reset();
	return true;
}

bool UDASaveSubsystem::ReadPayloadFile(const FString& SlotName, FString& OutJson, bool& bOutUsedBackup, FString& OutError) const
{
	bOutUsedBackup = false;
	FString PrimaryError;
	FString VersionError;
	int32 Version = 0;

	if (ReadPayloadFromSlotName(SlotName, OutJson, Version, PrimaryError))
	{
		OutError.Reset();
		return true;
	}

	const FString BackupSlotName = SlotName + BackupSuffix;
	if (ReadPayloadFromSlotName(BackupSlotName, OutJson, Version, VersionError))
	{
		bOutUsedBackup = true;
		OutError.Reset();
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Save slot '%s' was recovered from its backup."), *SlotName);
		return true;
	}

	OutError = FString::Printf(TEXT("%s Backup: %s"), *PrimaryError, *VersionError);
	return false;
}

// ------------------------------------------------------------------------ migrations

int32 UDASaveSubsystem::GetVersionFromJson(const FString& Json)
{
	TSharedPtr<FJsonObject> Root;
	if (!ParseJsonObject(Json, Root))
	{
		return -1;
	}
	int32 Version = -1;
	if (Root->TryGetNumberField(TEXT("version"), Version))
	{
		return Version;
	}
	return -1;
}

bool UDASaveSubsystem::MigrateJson(FString& Json, int32 FromVersion, FString& OutError) const
{
	TSharedPtr<FJsonObject> Root;
	if (!ParseJsonObject(Json, Root))
	{
		OutError = TEXT("Cannot migrate: payload is not valid JSON.");
		return false;
	}

	int32 Version = FromVersion;
	int32 JsonVersion = -1;
	if (Root->TryGetNumberField(TEXT("version"), JsonVersion) && JsonVersion >= 0)
	{
		Version = FMath::Max(Version, JsonVersion);
	}
	if (Version < 0)
	{
		Version = 0;
	}
	if (Version > CurrentVersion)
	{
		OutError = FString::Printf(TEXT("Cannot migrate payload from version %d: newer than supported version %d."), Version, CurrentVersion);
		return false;
	}

	while (Version < CurrentVersion)
	{
		switch (Version)
		{
		case 0:
			if (!MigrateLegacyPayloadToV1(Root, OutError))
			{
				return false;
			}
			Version = 1;
			break;
		default:
			OutError = FString::Printf(TEXT("No migration registered from version %d."), Version);
			return false;
		}
	}

	Root->SetNumberField(TEXT("version"), CurrentVersion);
	Json = SerializeCanonical(Root);
	OutError.Reset();
	return true;
}

// ------------------------------------------------------------------------ providers

void UDASaveSubsystem::RegisterPayloadProvider(UObject* Provider)
{
	if (!Provider || !Provider->GetClass()->ImplementsInterface(UDASavePayloadProvider::StaticClass()))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Save provider rejected: object does not implement IDASavePayloadProvider."));
		return;
	}
	PayloadProviders.AddUnique(Provider);
}

void UDASaveSubsystem::UnregisterPayloadProvider(UObject* Provider)
{
	PayloadProviders.RemoveAll([Provider](const TWeakObjectPtr<UObject>& Entry)
	{
		return !Entry.IsValid() || Entry.Get() == Provider;
	});
}

void UDASaveSubsystem::SetError(const FString& Error)
{
	LastError = Error;
	if (!Error.IsEmpty())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Save subsystem: %s"), *Error);
	}
}
