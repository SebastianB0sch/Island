// Duel Academy Island - the twelve-month school calendar.
//
// The calendar owns the date, weekday, period and hour. ADAIslandManager owns
// only the visual time of day; A09/A10 bridge the two by reading GetHour().
//
// MonthIndex is 0..11 and maps to October..September. Year 1 begins in
// October and rolls over after September. The canonical first playable day is
// Saturday, October 7, Year 1, AM.

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DACalendarSubsystem.generated.h"

class UDAProfileSubsystem;

UENUM(BlueprintType)
enum class EDADayPeriod : uint8
{
	AM    UMETA(DisplayName = "AM"),
	PM    UMETA(DisplayName = "PM"),
	Night UMETA(DisplayName = "Night")
};

/** Sunday = 0, matching the original game's week order. */
UENUM(BlueprintType)
enum class EDADayOfWeek : uint8
{
	Sunday,
	Monday,
	Tuesday,
	Wednesday,
	Thursday,
	Friday,
	Saturday
};

/** Which Friday of the month is exam day. Data-driven; canon still pending A01. */
UENUM(BlueprintType)
enum class EDAExamWeekRule : uint8
{
	First,
	Second,
	Third,
	Fourth,
	Last
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FDAOnCalendarDayChanged, int32, Year, int32, MonthIndex, int32, Day);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnCalendarPeriodChanged, EDADayPeriod, OldPeriod, EDADayPeriod, NewPeriod);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FDAOnCalendarChanged);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FDAOnExamDay, int32, Day);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FDAOnVisualHourChanged, int32, Hour);

UCLASS()
class DUELACADEMYISLAND_API UDACalendarSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** Upper bound for save-driven dates. Keeps absolute-day math and exam scans bounded. */
	static constexpr int32 MaxSupportedYear = 9999;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	static UDACalendarSubsystem* Get(const UObject* WorldContext);

	// ---------------------------------------------------------------- data
	/** Loads Content/Data/Profile/calendar.json, falling back to hardcoded defaults. */
	bool LoadCalendarData();

	/** Canonical new-game date and period. Does not notify listeners. */
	void ResetToDefaults();

	// ---------------------------------------------------------------- date
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetYear() const { return Year; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetMonthIndex() const { return MonthIndex; }

	/** Calendar month number (October = 10, January = 1). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetMonthNumber() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetDay() const { return Day; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	EDADayOfWeek GetWeekday() const { return Weekday; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	EDADayPeriod GetPeriod() const { return Period; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetHour() const { return Hour; }

	/** Allows arbitrary jumps for debug/teleport-to-scene. Prefer SkipToDate for gameplay. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Calendar")
	void SetDate(int32 InYear, int32 InMonthIndex, int32 InDay, EDADayPeriod InPeriod);

	/** Forward-only fast-forward. Returns false when the target is in the past. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Calendar")
	bool SkipToDate(int32 InYear, int32 InMonthIndex, int32 InDay, EDADayPeriod InPeriod);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Calendar")
	void AdvancePeriod();

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Calendar")
	void AdvanceDay();

	/** Advances to the next morning. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Calendar")
	void Sleep();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	bool IsWeekend() const;

	// ---------------------------------------------------------------- months / weekdays
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetDaysInMonth(int32 InYear, int32 InMonthIndex) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	FString GetMonthName(int32 InMonthIndex) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	FString GetMonthShortName(int32 InMonthIndex) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	FString GetWeekdayName(EDADayOfWeek InWeekday) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	FString GetPeriodName(EDADayPeriod InPeriod) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	FString GetDateText() const;

	/** "Saturday, October 7 - AM" (year included once it is no longer Year 1). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	FString GetFullDateText() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	FString GetTimeText() const;

	// ---------------------------------------------------------------- exams
	/** Day number of this month's exam (last Friday by default). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetExamDay(int32 InYear, int32 InMonthIndex) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	bool IsExamDay() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	bool IsExamDayFor(int32 InYear, int32 InMonthIndex, int32 InDay) const;

	/** First exam day on or after the current date. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	bool GetNextExamDate(int32& OutYear, int32& OutMonthIndex, int32& OutDay) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetExamPassMark() const { return ExamPassMark; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	EDADayOfWeek GetExamWeekday() const { return ExamWeekday; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	EDAExamWeekRule GetExamWeekRule() const { return ExamWeekRule; }

	// ---------------------------------------------------------------- time helpers
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetPeriodStartHour(EDADayPeriod InPeriod) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	static int32 GetPeriodRank(EDADayPeriod InPeriod);

	/** Days since October 1, Year 1 (a Sunday). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetAbsoluteDay() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	int32 GetAbsoluteDayFor(int32 InYear, int32 InMonthIndex, int32 InDay) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Calendar")
	EDADayOfWeek GetWeekdayForDate(int32 InYear, int32 InMonthIndex, int32 InDay) const;

	static bool IsLeapYear(int32 InYear);

	// ---------------------------------------------------------------- persistence
	void WriteSaveData(TSharedPtr<FJsonObject>& Root) const;
	bool ReadSaveData(const TSharedPtr<FJsonObject>& Root, FString& OutError);

	// ---------------------------------------------------------------- delegates
	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Calendar")
	FDAOnCalendarDayChanged OnDayChanged;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Calendar")
	FDAOnCalendarPeriodChanged OnPeriodChanged;

	/** Fires for any date or period change, including SetDate/Load. */
	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Calendar")
	FDAOnCalendarChanged OnCalendarChanged;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Calendar")
	FDAOnExamDay OnExamDay;

	/** Drives the visual clock. A09/A10 binds this to ADAIslandManager::SetHour. */
	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Calendar")
	FDAOnVisualHourChanged OnVisualHourChanged;

	/** Bridge used by A09/A10 to drive ADAIslandManager::SetHour without a hard dependency. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Calendar")
	void BroadcastVisualHour();

private:
	void ApplyDateInternal(int32 InYear, int32 InMonthIndex, int32 InDay, EDADayPeriod InPeriod);
	void BroadcastDateChanged(EDADayPeriod OldPeriod, bool bDayChanged);
	void NotifyProfileDayChanged();
	EDADayOfWeek ComputeWeekday(int32 InYear, int32 InMonthIndex, int32 InDay) const;
	int32 GetCalendarYearForMonth(int32 InYear, int32 InMonthIndex) const;
	void ParseExamWeekday(const FString& Value);
	void ParseExamWeekRule(const FString& Value);
	static FString PeriodToSaveKey(EDADayPeriod InPeriod);
	static EDADayPeriod ParsePeriod(const FString& Value, EDADayPeriod Fallback);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Calendar", meta = (AllowPrivateAccess = "true"))
	int32 Year = 1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Calendar", meta = (AllowPrivateAccess = "true"))
	int32 MonthIndex = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Calendar", meta = (AllowPrivateAccess = "true"))
	int32 Day = 7;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Calendar", meta = (AllowPrivateAccess = "true"))
	EDADayOfWeek Weekday = EDADayOfWeek::Saturday;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Calendar", meta = (AllowPrivateAccess = "true"))
	EDADayPeriod Period = EDADayPeriod::AM;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Calendar", meta = (AllowPrivateAccess = "true"))
	int32 Hour = 8;

	/** Start hour for AM/PM/Night. Data-driven, indexed by EDADayPeriod. */
	UPROPERTY()
	TArray<int32> PeriodHours;

	UPROPERTY()
	EDADayOfWeek ExamWeekday = EDADayOfWeek::Friday;

	UPROPERTY()
	EDAExamWeekRule ExamWeekRule = EDAExamWeekRule::Last;

	UPROPERTY()
	int32 ExamPassMark = 300;
};
