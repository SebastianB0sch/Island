// Duel Academy Island - player profile, progression state and duel rewards.
//
// UDAProfileSubsystem is the single source of truth for the player's identity,
// dorm, title, DP, counters, flags, email state and playtime. Inventory and
// deck ownership live in other lanes and are exposed here only through
// interfaces.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DATypes.h"
#include "DAProfileSubsystem.generated.h"

class UDASaveSubsystem;

/** How a duel was won. Drives the one-off DP bonuses. */
UENUM(BlueprintType)
enum class EDAWinCondition : uint8
{
	LifePoints      UMETA(DisplayName = "Life Points"),
	Exodia          UMETA(DisplayName = "Exodia"),
	DeckOut         UMETA(DisplayName = "Deck Out"),
	FinalCountdown  UMETA(DisplayName = "Final Countdown"),
	DestinyBoard    UMETA(DisplayName = "Destiny Board"),
	Surrender       UMETA(DisplayName = "Surrender"),
	Other           UMETA(DisplayName = "Other")
};

/** Result of one duel, as reported by the rules lane (A04) or duelist lane (A07). */
USTRUCT(BlueprintType)
struct DUELACADEMYISLAND_API FDAProfileDuelResult
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	FString OpponentId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	FString Mode = TEXT("free");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	bool bPlayerWon = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	bool bDraw = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	int32 Turns = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	int32 PlayerLp = 8000;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	int32 OpponentLp = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	int32 BattleDamageDealt = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	int32 MonstersDestroyedByBattle = 0;

	/** True when the player took the second turn of the duel. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	bool bWentSecond = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	EDAWinCondition WinCondition = EDAWinCondition::LifePoints;

	/** Additional event/story DP. Applied before turn multipliers. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	int32 BonusDP = 0;
};

/** Per-contact email state. Content is owned by A03; read/unlock state lives here. */
USTRUCT(BlueprintType)
struct DUELACADEMYISLAND_API FDAEmailState
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Email")
	bool bUnlocked = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Email")
	TArray<FString> ReadIds;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Email")
	TArray<FString> PendingDuelRequests;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnDPChanged, int32, OldDP, int32, NewDP);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnTitleChanged, FString, OldTitle, FString, NewTitle);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnDormChanged, EDADorm, OldDorm, EDADorm, NewDorm);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnFlagChanged, FString, Flag, bool, bValue);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FDAOnDayChanged, int32, Year, int32, MonthIndex, int32, Day);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FDAOnProfileLoaded);

/**
 * Read-only inventory handle supplied by A06. The profile never stores card
 * counts itself; it only asks the registered provider for collection totals
 * when evaluating title requirements.
 */
UINTERFACE(MinimalAPI)
class UDAProfileInventoryInterface : public UInterface
{
	GENERATED_BODY()
};

class DUELACADEMYISLAND_API IDAProfileInventoryInterface
{
	GENERATED_BODY()

public:
	virtual int32 GetOwnedCardCount(int32 CardId) const = 0;
	virtual int32 GetDistinctCardsOwned() const = 0;
};

/** Read-only deck handle supplied by A06. */
UINTERFACE(MinimalAPI)
class UDAProfileDeckInterface : public UInterface
{
	GENERATED_BODY()
};

class DUELACADEMYISLAND_API IDAProfileDeckInterface
{
	GENERATED_BODY()

public:
	virtual TArray<FString> GetDeckIds() const = 0;
	virtual FString GetActiveDeckId() const = 0;
	virtual void SetActiveDeckId(const FString& DeckId) = 0;
};

namespace DuelAcademyProfile
{
	/** Accepts the short and long names used by the save schema. */
	DUELACADEMYISLAND_API EDADorm ParseDorm(const FString& Value, EDADorm Fallback = EDADorm::Slifer);

	/** Short, stable save key: "Slifer", "Ra", "Obelisk", "White". */
	DUELACADEMYISLAND_API FString DormToSaveKey(EDADorm Dorm);

	/** Normalises ids for counter keys ("Jaden Yuki" -> "jaden_yuki"). */
	DUELACADEMYISLAND_API FString NormalizeId(const FString& Value);
}

UCLASS()
class DUELACADEMYISLAND_API UDAProfileSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	static UDAProfileSubsystem* Get(const UObject* WorldContext);

	// ---------------------------------------------------------------- new game / identity
	/** Resets all progression and applies the canonical new-game defaults. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void InitializeNewGame(const FString& InName);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	bool IsInitialized() const { return bInitialized; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	FString GetPlayerName() const { return PlayerName; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void SetPlayerName(const FString& InName);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	FString GetGender() const { return Gender; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void SetGender(const FString& InGender);

	// ---------------------------------------------------------------- DP
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	int32 GetDP() const { return DP; }

	/** Adds DP. Negative input is ignored. Returns the actual amount added. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	int32 AwardDP(int32 Amount);

	/** Attempts to spend DP. Returns false (and changes nothing) if the balance is too low. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	bool SpendDP(int32 Amount);

	/** Canonical DP formula. Does not mutate the profile. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	static int32 CalculateDuelDP(const FDAProfileDuelResult& Result);

	/**
	 * Applies a duel result: counters, reward DP, title reevaluation and an
	 * autosave request. Returns DP earned.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	int32 RecordDuelResult(const FDAProfileDuelResult& Result);

	// ---------------------------------------------------------------- flags
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	bool GetFlag(const FString& Flag) const;

	/** Sets a flag. Broadcasts only when the value changes. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void SetFlag(const FString& Flag, bool bValue = true);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void ClearFlag(const FString& Flag);

	const TMap<FString, bool>& GetFlags() const { return Flags; }

	// ---------------------------------------------------------------- counters
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	int32 GetCounter(const FString& Counter) const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void SetCounter(const FString& Counter, int32 Value);

	/** Adds Amount (may be negative, clamped at zero). Returns the new value. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	int32 IncrementCounter(const FString& Counter, int32 Amount = 1);

	const TMap<FString, int32>& GetCounters() const { return Counters; }

	// ---------------------------------------------------------------- dorm / title
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	EDADorm GetDorm() const { return Dorm; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void SetDorm(EDADorm NewDorm);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	FString GetTitle() const { return Title; }

	/** Raw title setter. Prefer UDATitleSystem::ApplyBestTitle / ForceTitle. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void SetTitle(const FString& NewTitle);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	FString GetTemporaryTitle() const { return TemporaryTitle; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	int32 GetTemporaryTitleDaysRemaining() const { return TemporaryTitleDaysRemaining; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void SetTemporaryTitle(const FString& InTitle, int32 DaysRemaining);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void ClearTemporaryTitle();

	// ---------------------------------------------------------------- email
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void UnlockEmail(const FString& ContactId);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	bool IsEmailUnlocked(const FString& ContactId) const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void MarkEmailRead(const FString& ContactId, const FString& MessageId);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	bool IsEmailRead(const FString& ContactId, const FString& MessageId) const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void AddDuelRequest(const FString& ContactId, const FString& RequestId);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	bool HasPendingDuelRequest(const FString& ContactId) const;

	/** Removes and returns the oldest pending request for a contact. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	bool ConsumeDuelRequest(const FString& ContactId, FString& OutRequestId);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	FDAEmailState GetEmailState(const FString& ContactId) const;

	const TMap<FString, FDAEmailState>& GetEmails() const { return Emails; }

	// ---------------------------------------------------------------- inventory / deck handles
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	bool SetInventoryProvider(UObject* Provider);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	UObject* GetInventoryProvider() const { return InventoryProvider.Get(); }

	/** Provider count when available, otherwise the cards_owned counter. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	int32 GetDistinctCardsOwned() const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	bool SetDeckProvider(UObject* Provider);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	UObject* GetDeckProvider() const { return DeckProvider.Get(); }

	// ---------------------------------------------------------------- playtime
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	double GetPlaytimeSeconds() const { return PlaytimeSeconds; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Profile")
	void AddPlaytime(double Seconds);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Profile")
	FString GetPlaytimeText() const;

	// ---------------------------------------------------------------- calendar bridge
	/** Called by UDACalendarSubsystem when the date advances. */
	void NotifyDayChanged(int32 InYear, int32 InMonthIndex, int32 InDay);

	/** Re-evaluates the title through UDATitleSystem when a game instance is present. */
	void RefreshTitleFromSystem();

	// ---------------------------------------------------------------- persistence
	void WriteSaveData(TSharedPtr<FJsonObject>& Root) const;
	bool ReadSaveData(const TSharedPtr<FJsonObject>& Root, FString& OutError);

	/** New-game defaults, without a name. Kept public for tests and save recovery. */
	void ResetToDefaults();

	// ---------------------------------------------------------------- delegates
	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Profile")
	FDAOnDPChanged OnDPChanged;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Profile")
	FDAOnTitleChanged OnTitleChanged;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Profile")
	FDAOnDormChanged OnDormChanged;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Profile")
	FDAOnFlagChanged OnFlagChanged;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Profile")
	FDAOnDayChanged OnDayChanged;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Profile")
	FDAOnProfileLoaded OnProfileLoaded;

private:
	bool TickPlaytime(float DeltaSeconds);
	void RequestProgressionAutosave(const FString& Reason);
	void ApplyCounterDelta(const FString& Counter, int32 Delta);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	FString PlayerName;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	FString Gender = TEXT("unspecified");

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	EDADorm Dorm = EDADorm::Slifer;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	FString Title;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	int32 DP = 3000;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	FString TemporaryTitle;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	int32 TemporaryTitleDaysRemaining = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Profile", meta = (AllowPrivateAccess = "true"))
	double PlaytimeSeconds = 0.0;

	UPROPERTY()
	TMap<FString, bool> Flags;

	UPROPERTY()
	TMap<FString, int32> Counters;

	UPROPERTY()
	TMap<FString, FDAEmailState> Emails;

	TWeakObjectPtr<UObject> InventoryProvider;
	TWeakObjectPtr<UObject> DeckProvider;

	FTSTicker::FDelegateHandle PlaytimeTickerHandle;

	bool bInitialized = false;
};
