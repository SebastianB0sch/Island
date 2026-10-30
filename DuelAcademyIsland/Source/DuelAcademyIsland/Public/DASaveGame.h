// Duel Academy Island - save game object, slot subsystem, versioning and
// migrations.
//
// Only UDASaveSubsystem touches disk. The payload is canonical JSON stored in
// a UDASaveGame; writes go to a temporary slot, are verified, and only then
// replace the primary file. The previous primary is kept in a "_backup" slot
// and is used automatically when the primary is missing or corrupt. Each file
// carries a 16-byte CRC trailer so corrupt input is rejected before the
// USaveGame archive is deserialized.

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "GameFramework/SaveGame.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DATypes.h"
#include "DASaveGame.generated.h"

class UDAProfileSubsystem;
class UDASettings;

/**
 * A USaveGame wrapper around a versioned JSON payload.
 *
 * Keep this class data-only. A02 owns the schema; other lanes contribute
 * sections through IDASavePayloadProvider instead of adding fields here.
 */
UCLASS()
class DUELACADEMYISLAND_API UDASaveGame : public USaveGame
{
	GENERATED_BODY()

public:
	UDASaveGame();

	/** Schema version of JsonPayload. See UDASaveSubsystem::CurrentVersion. */
	UPROPERTY()
	int32 Version = 1;

	/** Canonical JSON payload. Always UTF-16 in memory and serialized by UE. */
	UPROPERTY()
	FString JsonPayload;

	/** FCrc::StrCrc32 of JsonPayload. Used for corruption detection. */
	UPROPERTY()
	int32 PayloadHash = 0;

	/** Convenience copy of the player name for diagnostics. Metadata lives in the payload. */
	UPROPERTY()
	FString PlayerName;
};

/**
 * Optional extension point for lanes that own their own save sections
 * (inventory/decks for A06, story/events for A03, exams for A07).
 *
 * Providers are registered on UDASaveSubsystem. The save subsystem writes
 * each provider under its section name at the root of the payload and reads
 * it back on load. Unknown root sections are ignored, so adding a provider
 * does not require a schema migration.
 */
UINTERFACE(MinimalAPI)
class UDASavePayloadProvider : public UInterface
{
	GENERATED_BODY()
};

class DUELACADEMYISLAND_API IDASavePayloadProvider
{
	GENERATED_BODY()

public:
	/** Root key for this provider. Reserved names are rejected by the save subsystem. */
	virtual FString GetSaveSectionName() const = 0;

	/** Fill OutSection with this lane's state. Return false to fail the save. */
	virtual bool WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const = 0;

	/** Restore this lane's state. Return false to fail the load. */
	virtual bool ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) = 0;
};

/** UI-facing metadata for one slot. Populated without loading the profile. */
USTRUCT(BlueprintType)
struct DUELACADEMYISLAND_API FDASaveSlotInfo
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	int32 SlotIndex = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	FString SlotName;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	bool bExists = false;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	bool bIsAutosave = false;

	/** Primary slot exists but neither it nor the backup could be parsed. */
	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	bool bCorrupt = false;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	bool bUsingBackup = false;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	FString PlayerName;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	FString Title;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	EDADorm Dorm = EDADorm::Slifer;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	int32 DP = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	int32 Year = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	int32 MonthIndex = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	int32 Day = 7;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	EDADayPeriod Period = EDADayPeriod::AM;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	double PlaytimeSeconds = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	FString SavedAtUtc;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Save")
	int32 Version = 0;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnSaveCompleted, int32, SlotIndex, bool, bSuccess);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnLoadCompleted, int32, SlotIndex, bool, bSuccess);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FDAOnSaveError, FString, Error);

UCLASS()
class DUELACADEMYISLAND_API UDASaveSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** Slot 0 is the autosave; 1..3 are manual slots. */
	static constexpr int32 AutosaveSlotIndex = 0;
	static constexpr int32 NumManualSlots = 3;
	static constexpr int32 NumSlots = NumManualSlots + 1;
	static constexpr int32 CurrentVersion = 1;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	static UDASaveSubsystem* Get(const UObject* WorldContext);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Save")
	static bool IsValidSlotIndex(int32 SlotIndex);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Save")
	static FString GetSlotName(int32 SlotIndex);

	/** Full path of a slot's primary .sav file. Exposed for diagnostics/tests. */
	static FString GetSaveFilePath(const FString& SlotName);

	// ---------------------------------------------------------------- slots
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Save")
	bool SaveSlot(int32 SlotIndex, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Save")
	bool LoadSlot(int32 SlotIndex, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Save")
	bool DeleteSlot(int32 SlotIndex, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Save")
	TArray<FDASaveSlotInfo> EnumerateSlots() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Save")
	bool HasSave(int32 SlotIndex) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Save")
	FString GetLastError() const { return LastError; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Save")
	FString GetLastAutosaveReason() const { return LastAutosaveReason; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Save")
	double GetLastAutosaveTime() const { return LastAutosaveTime; }

	/** Debug alias used by console commands. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Save")
	bool SaveNow(int32 SlotIndex, FString& OutError) { return SaveSlot(SlotIndex, OutError); }

	// ---------------------------------------------------------------- autosave
	/** Called by day changes, exam results, event completion, purchases and duels. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Save")
	void RequestAutosave(const FString& Reason);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Save")
	bool bAutosaveEnabled = true;

	// ---------------------------------------------------------------- migrations
	/**
	 * Migrates a JSON payload to CurrentVersion in place.
	 * FromVersion < 0 means "read the version from the payload".
	 * Unknown/newer versions are rejected, never silently loaded.
	 */
	bool MigrateJson(FString& Json, int32 FromVersion, FString& OutError) const;

	static int32 GetVersionFromJson(const FString& Json);

	// ---------------------------------------------------------------- extension providers
	void RegisterPayloadProvider(UObject* Provider);
	void UnregisterPayloadProvider(UObject* Provider);

	// ---------------------------------------------------------------- context API (automation/self-test)
	// These mirror SaveSlot/LoadSlot but use explicit subsystems so tests and
	// commandlets do not need a fully initialised UGameInstance.
	bool SaveSlotWithContext(int32 SlotIndex, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError);
	bool LoadSlotWithContext(int32 SlotIndex, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError, bool* bOutRecoveredFromBackup = nullptr);

	bool SaveNamedSlotWithContext(const FString& SlotName, int32 LogicalSlotIndex, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError);
	bool LoadNamedSlotWithContext(const FString& SlotName, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError, bool* bOutRecoveredFromBackup = nullptr);
	bool DeleteNamedSlot(const FString& SlotName, FString& OutError);

	FDASaveSlotInfo GetSlotInfo(const FString& SlotName, int32 SlotIndex = -1) const;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Save")
	FDAOnSaveCompleted OnSaveCompleted;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Save")
	FDAOnLoadCompleted OnLoadCompleted;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Save")
	FDAOnSaveError OnSaveError;

private:
	UDAProfileSubsystem* ResolveProfile() const;
	UDACalendarSubsystem* ResolveCalendar() const;
	UDASettings* ResolveSettings() const;

	bool BuildPayload(int32 LogicalSlotIndex, const FString& SlotName, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutJson, FString& OutError) const;
	bool ApplyPayload(const TSharedPtr<FJsonObject>& Root, UDAProfileSubsystem* Profile, UDACalendarSubsystem* Calendar, UDASettings* Settings, FString& OutError) const;

	bool WriteAtomic(const FString& SlotName, const FString& Json, FString& OutError);
	bool ReadPayloadFile(const FString& SlotName, FString& OutJson, bool& bOutUsedBackup, FString& OutError) const;
	bool ReadPayloadFromSlotName(const FString& SlotName, FString& OutJson, int32& OutVersion, FString& OutError) const;
	void SetError(const FString& Error);

	TArray<TWeakObjectPtr<UObject>> PayloadProviders;

	FString LastError;
	FString LastAutosaveReason;
	double LastAutosaveTime = -1.0;
};
