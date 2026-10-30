// Duel Academy Island - school calendar implementation.

#include "DACalendarSubsystem.h"

#include "DAProfileSubsystem.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	const TCHAR* const MonthNames[12] = {
		TEXT("October"), TEXT("November"), TEXT("December"),
		TEXT("January"), TEXT("February"), TEXT("March"),
		TEXT("April"), TEXT("May"), TEXT("June"),
		TEXT("July"), TEXT("August"), TEXT("September")
	};

	const TCHAR* const MonthShortNames[12] = {
		TEXT("Oct"), TEXT("Nov"), TEXT("Dec"),
		TEXT("Jan"), TEXT("Feb"), TEXT("Mar"),
		TEXT("Apr"), TEXT("May"), TEXT("Jun"),
		TEXT("Jul"), TEXT("Aug"), TEXT("Sep")
	};

	const TCHAR* const WeekdayNames[7] = {
		TEXT("Sunday"), TEXT("Monday"), TEXT("Tuesday"), TEXT("Wednesday"),
		TEXT("Thursday"), TEXT("Friday"), TEXT("Saturday")
	};

	const TCHAR* const WeekdayShortNames[7] = {
		TEXT("Sun"), TEXT("Mon"), TEXT("Tue"), TEXT("Wed"), TEXT("Thu"), TEXT("Fri"), TEXT("Sat")
	};

	FString PeriodKey(EDADayPeriod Period)
	{
		switch (Period)
		{
		case EDADayPeriod::PM:    return TEXT("PM");
		case EDADayPeriod::Night: return TEXT("Night");
		case EDADayPeriod::AM:
		default:                  return TEXT("AM");
		}
	}

	EDADayPeriod KeyToPeriod(const FString& Value, EDADayPeriod Fallback)
	{
		if (Value.Equals(TEXT("AM"), ESearchCase::IgnoreCase))
		{
			return EDADayPeriod::AM;
		}
		if (Value.Equals(TEXT("PM"), ESearchCase::IgnoreCase))
		{
			return EDADayPeriod::PM;
		}
		if (Value.Equals(TEXT("Night"), ESearchCase::IgnoreCase))
		{
			return EDADayPeriod::Night;
		}
		return Fallback;
	}

	EDADayOfWeek StringToWeekday(const FString& Value, EDADayOfWeek Fallback)
	{
		const FString Lower = Value.TrimStartAndEnd().ToLower();
		static const TCHAR* const Names[7] = { TEXT("sunday"), TEXT("monday"), TEXT("tuesday"), TEXT("wednesday"), TEXT("thursday"), TEXT("friday"), TEXT("saturday") };
		static const TCHAR* const ShortNames[7] = { TEXT("sun"), TEXT("mon"), TEXT("tue"), TEXT("wed"), TEXT("thu"), TEXT("fri"), TEXT("sat") };
		for (int32 Index = 0; Index < 7; ++Index)
		{
			if (Lower == Names[Index] || Lower == ShortNames[Index])
			{
				return static_cast<EDADayOfWeek>(Index);
			}
		}
		return Fallback;
	}

	EDAExamWeekRule StringToExamWeek(const FString& Value, EDAExamWeekRule Fallback)
	{
		const FString Lower = Value.TrimStartAndEnd().ToLower();
		if (Lower == TEXT("first") || Lower == TEXT("1"))
		{
			return EDAExamWeekRule::First;
		}
		if (Lower == TEXT("second") || Lower == TEXT("2"))
		{
			return EDAExamWeekRule::Second;
		}
		if (Lower == TEXT("third") || Lower == TEXT("3"))
		{
			return EDAExamWeekRule::Third;
		}
		if (Lower == TEXT("fourth") || Lower == TEXT("4"))
		{
			return EDAExamWeekRule::Fourth;
		}
		if (Lower == TEXT("last"))
		{
			return EDAExamWeekRule::Last;
		}
		return Fallback;
	}

	int32 ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}
}

// ------------------------------------------------------------------------ lifecycle

void UDACalendarSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	ResetToDefaults();
	LoadCalendarData();
}

void UDACalendarSubsystem::Deinitialize()
{
	Super::Deinitialize();
}

UDACalendarSubsystem* UDACalendarSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	if (const UWorld* World = WorldContext->GetWorld())
	{
		if (UGameInstance* GameInstance = World->GetGameInstance())
		{
			return GameInstance->GetSubsystem<UDACalendarSubsystem>();
		}
	}
	return nullptr;
}

void UDACalendarSubsystem::ResetToDefaults()
{
	Year = 1;
	MonthIndex = 0;
	Day = 7;
	Period = EDADayPeriod::AM;
	PeriodHours.Reset();
	PeriodHours.Add(8);
	PeriodHours.Add(14);
	PeriodHours.Add(20);
	Hour = GetPeriodStartHour(Period);
	ExamWeekday = EDADayOfWeek::Friday;
	ExamWeekRule = EDAExamWeekRule::Last;
	ExamPassMark = 300;
	Weekday = ComputeWeekday(Year, MonthIndex, Day);

	OnCalendarChanged.Broadcast();
	OnVisualHourChanged.Broadcast(Hour);
}

bool UDACalendarSubsystem::LoadCalendarData()
{
	ResetToDefaults();

	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Profile/calendar.json"));
	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *Path))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Calendar data not found at %s; using defaults."), *Path);
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Calendar data at %s could not be parsed; using defaults."), *Path);
		return false;
	}

	const TSharedPtr<FJsonObject>* Start = nullptr;
	if (Root->TryGetObjectField(TEXT("start"), Start) && Start && Start->IsValid())
	{
		const int32 StartYear = FMath::Max(1, ReadInt(*Start, TEXT("year"), 1));
		const int32 StartMonth = FMath::Clamp(ReadInt(*Start, TEXT("month_index"), 0), 0, 11);
		const int32 StartDay = FMath::Max(1, ReadInt(*Start, TEXT("day"), 7));
		EDADayPeriod StartPeriod = EDADayPeriod::AM;
		FString PeriodText;
		if ((*Start)->TryGetStringField(TEXT("period"), PeriodText))
		{
			StartPeriod = KeyToPeriod(PeriodText, EDADayPeriod::AM);
		}
		ApplyDateInternal(StartYear, StartMonth, StartDay, StartPeriod);
	}

	const TSharedPtr<FJsonObject>* PeriodHoursObject = nullptr;
	if (Root->TryGetObjectField(TEXT("period_hours"), PeriodHoursObject) && PeriodHoursObject && PeriodHoursObject->IsValid())
	{
		PeriodHours.SetNum(3);
		PeriodHours[0] = FMath::Clamp(ReadInt(*PeriodHoursObject, TEXT("AM"), 8), 0, 23);
		PeriodHours[1] = FMath::Clamp(ReadInt(*PeriodHoursObject, TEXT("PM"), 14), 0, 23);
		PeriodHours[2] = FMath::Clamp(ReadInt(*PeriodHoursObject, TEXT("Night"), 20), 0, 23);
		Hour = GetPeriodStartHour(Period);
	}

	const TSharedPtr<FJsonObject>* Exam = nullptr;
	if (Root->TryGetObjectField(TEXT("exam"), Exam) && Exam && Exam->IsValid())
	{
		FString WeekdayText;
		if ((*Exam)->TryGetStringField(TEXT("weekday"), WeekdayText))
		{
			ExamWeekday = StringToWeekday(WeekdayText, EDADayOfWeek::Friday);
		}
		FString WeekText;
		if ((*Exam)->TryGetStringField(TEXT("week"), WeekText))
		{
			ExamWeekRule = StringToExamWeek(WeekText, EDAExamWeekRule::Last);
		}
		ExamPassMark = FMath::Max(0, ReadInt(*Exam, TEXT("pass_mark"), 300));
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded school calendar: year %d, month %s, day %d, exam weekday %s (%s)."),
		Year, *GetMonthName(MonthIndex), Day, *GetWeekdayName(ExamWeekday), *GetPeriodName(Period));
	OnCalendarChanged.Broadcast();
	OnVisualHourChanged.Broadcast(Hour);
	return true;
}

// ------------------------------------------------------------------------ date

int32 UDACalendarSubsystem::GetMonthNumber() const
{
	return ((MonthIndex + 9) % 12) + 1;
}

void UDACalendarSubsystem::SetDate(int32 InYear, int32 InMonthIndex, int32 InDay, EDADayPeriod InPeriod)
{
	const EDADayPeriod OldPeriod = Period;
	const int32 OldAbsoluteDay = GetAbsoluteDay();
	ApplyDateInternal(InYear, InMonthIndex, InDay, InPeriod);
	const bool bDayChanged = OldAbsoluteDay != GetAbsoluteDay();
	BroadcastDateChanged(OldPeriod, bDayChanged);
}

bool UDACalendarSubsystem::SkipToDate(int32 InYear, int32 InMonthIndex, int32 InDay, EDADayPeriod InPeriod)
{
	const int32 TargetAbsoluteDay = GetAbsoluteDayFor(FMath::Max(1, InYear), FMath::Clamp(InMonthIndex, 0, 11), InDay);
	const int32 CurrentAbsoluteDay = GetAbsoluteDay();
	if (TargetAbsoluteDay < CurrentAbsoluteDay)
	{
		return false;
	}
	if (TargetAbsoluteDay == CurrentAbsoluteDay && GetPeriodRank(InPeriod) < GetPeriodRank(Period))
	{
		return false;
	}

	while (GetAbsoluteDay() < TargetAbsoluteDay)
	{
		AdvanceDay();
	}
	while (GetPeriodRank(Period) < GetPeriodRank(InPeriod))
	{
		AdvancePeriod();
	}
	return true;
}

void UDACalendarSubsystem::AdvancePeriod()
{
	switch (Period)
	{
	case EDADayPeriod::AM:
		Period = EDADayPeriod::PM;
		Hour = GetPeriodStartHour(Period);
		OnPeriodChanged.Broadcast(EDADayPeriod::AM, EDADayPeriod::PM);
		OnCalendarChanged.Broadcast();
		OnVisualHourChanged.Broadcast(Hour);
		break;
	case EDADayPeriod::PM:
		Period = EDADayPeriod::Night;
		Hour = GetPeriodStartHour(Period);
		OnPeriodChanged.Broadcast(EDADayPeriod::PM, EDADayPeriod::Night);
		OnCalendarChanged.Broadcast();
		OnVisualHourChanged.Broadcast(Hour);
		break;
	case EDADayPeriod::Night:
	default:
		AdvanceDay();
		break;
	}
}

void UDACalendarSubsystem::AdvanceDay()
{
	const EDADayPeriod OldPeriod = Period;
	++Day;
	if (Day > GetDaysInMonth(Year, MonthIndex))
	{
		Day = 1;
		++MonthIndex;
		if (MonthIndex > 11)
		{
			MonthIndex = 0;
			++Year;
		}
	}
	Weekday = ComputeWeekday(Year, MonthIndex, Day);
	Period = EDADayPeriod::AM;
	Hour = GetPeriodStartHour(Period);
	BroadcastDateChanged(OldPeriod, true);
}

void UDACalendarSubsystem::Sleep()
{
	AdvanceDay();
}

bool UDACalendarSubsystem::IsWeekend() const
{
	return Weekday == EDADayOfWeek::Saturday || Weekday == EDADayOfWeek::Sunday;
}

void UDACalendarSubsystem::ApplyDateInternal(int32 InYear, int32 InMonthIndex, int32 InDay, EDADayPeriod InPeriod)
{
	Year = FMath::Max(1, InYear);
	MonthIndex = FMath::Clamp(InMonthIndex, 0, 11);
	Day = FMath::Clamp(InDay, 1, GetDaysInMonth(Year, MonthIndex));
	Period = InPeriod;
	Hour = GetPeriodStartHour(Period);
	Weekday = ComputeWeekday(Year, MonthIndex, Day);
}

void UDACalendarSubsystem::BroadcastDateChanged(EDADayPeriod OldPeriod, bool bDayChanged)
{
	if (bDayChanged)
	{
		OnDayChanged.Broadcast(Year, MonthIndex, Day);
		NotifyProfileDayChanged();
	}
	if (OldPeriod != Period)
	{
		OnPeriodChanged.Broadcast(OldPeriod, Period);
	}
	OnCalendarChanged.Broadcast();
	OnVisualHourChanged.Broadcast(Hour);
	if (IsExamDay())
	{
		OnExamDay.Broadcast(Day);
	}
}

void UDACalendarSubsystem::BroadcastVisualHour()
{
	OnVisualHourChanged.Broadcast(Hour);
	if (IsExamDay())
	{
		OnExamDay.Broadcast(Day);
	}
}

void UDACalendarSubsystem::NotifyProfileDayChanged()
{
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UDAProfileSubsystem* Profile = GameInstance->GetSubsystem<UDAProfileSubsystem>())
		{
			Profile->NotifyDayChanged(Year, MonthIndex, Day);
		}
	}
}

// ------------------------------------------------------------------------ months / weekdays

int32 UDACalendarSubsystem::GetDaysInMonth(int32 InYear, int32 InMonthIndex) const
{
	static const int32 FixedDays[12] = { 31, 30, 31, 31, 28, 31, 30, 31, 30, 31, 31, 30 };
	const int32 SafeIndex = FMath::Clamp(InMonthIndex, 0, 11);
	if (SafeIndex == 4 && IsLeapYear(GetCalendarYearForMonth(FMath::Max(1, InYear), SafeIndex)))
	{
		return 29;
	}
	return FixedDays[SafeIndex];
}

FString UDACalendarSubsystem::GetMonthName(int32 InMonthIndex) const
{
	return MonthNames[FMath::Clamp(InMonthIndex, 0, 11)];
}

FString UDACalendarSubsystem::GetMonthShortName(int32 InMonthIndex) const
{
	return MonthShortNames[FMath::Clamp(InMonthIndex, 0, 11)];
}

FString UDACalendarSubsystem::GetWeekdayName(EDADayOfWeek InWeekday) const
{
	return WeekdayNames[FMath::Clamp(static_cast<int32>(InWeekday), 0, 6)];
}

FString UDACalendarSubsystem::GetPeriodName(EDADayPeriod InPeriod) const
{
	return PeriodKey(InPeriod);
}

FString UDACalendarSubsystem::GetDateText() const
{
	return FString::Printf(TEXT("%s, %s %d"), *GetWeekdayName(Weekday), *GetMonthName(MonthIndex), Day);
}

FString UDACalendarSubsystem::GetFullDateText() const
{
	if (Year > 1)
	{
		return FString::Printf(TEXT("%s, %s %d, Year %d - %s"), *GetWeekdayName(Weekday), *GetMonthName(MonthIndex), Day, Year, *GetPeriodName(Period));
	}
	return FString::Printf(TEXT("%s, %s %d - %s"), *GetWeekdayName(Weekday), *GetMonthName(MonthIndex), Day, *GetPeriodName(Period));
}

FString UDACalendarSubsystem::GetTimeText() const
{
	return FString::Printf(TEXT("%02d:00"), Hour);
}

// ------------------------------------------------------------------------ exams

int32 UDACalendarSubsystem::GetExamDay(int32 InYear, int32 InMonthIndex) const
{
	const int32 SafeYear = FMath::Max(1, InYear);
	const int32 SafeMonth = FMath::Clamp(InMonthIndex, 0, 11);
	const int32 DaysInMonth = GetDaysInMonth(SafeYear, SafeMonth);
	const EDADayOfWeek FirstWeekday = ComputeWeekday(SafeYear, SafeMonth, 1);
	const int32 FirstOffset = (static_cast<int32>(ExamWeekday) - static_cast<int32>(FirstWeekday) + 7) % 7;
	const int32 FirstMatch = 1 + FirstOffset;

	const EDADayOfWeek LastWeekday = ComputeWeekday(SafeYear, SafeMonth, DaysInMonth);
	const int32 LastOffset = (static_cast<int32>(LastWeekday) - static_cast<int32>(ExamWeekday) + 7) % 7;
	const int32 LastMatch = DaysInMonth - LastOffset;

	if (ExamWeekRule == EDAExamWeekRule::Last)
	{
		return LastMatch;
	}

	const int32 WeekIndex = FMath::Clamp(static_cast<int32>(ExamWeekRule), 0, 3);
	const int32 Candidate = FirstMatch + WeekIndex * 7;
	return Candidate <= DaysInMonth ? Candidate : LastMatch;
}

bool UDACalendarSubsystem::IsExamDay() const
{
	return IsExamDayFor(Year, MonthIndex, Day);
}

bool UDACalendarSubsystem::IsExamDayFor(int32 InYear, int32 InMonthIndex, int32 InDay) const
{
	if (InMonthIndex < 0 || InMonthIndex > 11)
	{
		return false;
	}
	if (InDay < 1 || InDay > GetDaysInMonth(FMath::Max(1, InYear), InMonthIndex))
	{
		return false;
	}
	return GetExamDay(InYear, InMonthIndex) == InDay;
}

bool UDACalendarSubsystem::GetNextExamDate(int32& OutYear, int32& OutMonthIndex, int32& OutDay) const
{
	for (int32 Offset = 0; Offset <= 12; ++Offset)
	{
		int32 CandidateMonth = MonthIndex + Offset;
		const int32 CandidateYear = Year + CandidateMonth / 12;
		CandidateMonth %= 12;
		const int32 ExamDay = GetExamDay(CandidateYear, CandidateMonth);
		if (Offset == 0 && ExamDay < Day)
		{
			continue;
		}
		OutYear = CandidateYear;
		OutMonthIndex = CandidateMonth;
		OutDay = ExamDay;
		return true;
	}
	return false;
}

// ------------------------------------------------------------------------ helpers

int32 UDACalendarSubsystem::GetPeriodStartHour(EDADayPeriod InPeriod) const
{
	const int32 Index = GetPeriodRank(InPeriod);
	if (PeriodHours.IsValidIndex(Index))
	{
		return PeriodHours[Index];
	}
	static const int32 Fallback[3] = { 8, 14, 20 };
	return Fallback[FMath::Clamp(Index, 0, 2)];
}

int32 UDACalendarSubsystem::GetPeriodRank(EDADayPeriod InPeriod)
{
	switch (InPeriod)
	{
	case EDADayPeriod::PM:    return 1;
	case EDADayPeriod::Night: return 2;
	case EDADayPeriod::AM:
	default:                  return 0;
	}
}

int32 UDACalendarSubsystem::GetAbsoluteDay() const
{
	return GetAbsoluteDayFor(Year, MonthIndex, Day);
}

int32 UDACalendarSubsystem::GetAbsoluteDayFor(int32 InYear, int32 InMonthIndex, int32 InDay) const
{
	const int32 SafeYear = FMath::Max(1, InYear);
	const int32 SafeMonth = FMath::Clamp(InMonthIndex, 0, 11);
	const int32 SafeDay = FMath::Clamp(InDay, 1, GetDaysInMonth(SafeYear, SafeMonth));
	int32 Days = 0;
	for (int32 YearIndex = 1; YearIndex < SafeYear; ++YearIndex)
	{
		// A school year runs October..September; February belongs to the next
		// calendar year (YearIndex + 1).
		Days += 365 + (IsLeapYear(YearIndex + 1) ? 1 : 0);
	}
	for (int32 Month = 0; Month < SafeMonth; ++Month)
	{
		Days += GetDaysInMonth(SafeYear, Month);
	}
	Days += SafeDay - 1;
	return Days;
}

EDADayOfWeek UDACalendarSubsystem::GetWeekdayForDate(int32 InYear, int32 InMonthIndex, int32 InDay) const
{
	return ComputeWeekday(InYear, InMonthIndex, InDay);
}

EDADayOfWeek UDACalendarSubsystem::ComputeWeekday(int32 InYear, int32 InMonthIndex, int32 InDay) const
{
	const int32 AbsoluteDay = GetAbsoluteDayFor(InYear, InMonthIndex, InDay);
	const int32 Mod = ((AbsoluteDay % 7) + 7) % 7;
	// October 1, Year 1 is a Sunday.
	return static_cast<EDADayOfWeek>((static_cast<int32>(EDADayOfWeek::Sunday) + Mod) % 7);
}

bool UDACalendarSubsystem::IsLeapYear(int32 InYear)
{
	if (InYear <= 0)
	{
		return false;
	}
	return (InYear % 4 == 0) && ((InYear % 100 != 0) || (InYear % 400 == 0));
}

int32 UDACalendarSubsystem::GetCalendarYearForMonth(int32 InYear, int32 InMonthIndex) const
{
	return FMath::Max(1, InYear) + (InMonthIndex >= 3 ? 1 : 0);
}

void UDACalendarSubsystem::ParseExamWeekday(const FString& Value)
{
	ExamWeekday = StringToWeekday(Value, EDADayOfWeek::Friday);
}

void UDACalendarSubsystem::ParseExamWeekRule(const FString& Value)
{
	ExamWeekRule = StringToExamWeek(Value, EDAExamWeekRule::Last);
}

FString UDACalendarSubsystem::PeriodToSaveKey(EDADayPeriod InPeriod)
{
	return PeriodKey(InPeriod);
}

EDADayPeriod UDACalendarSubsystem::ParsePeriod(const FString& Value, EDADayPeriod Fallback)
{
	return KeyToPeriod(Value, Fallback);
}

// ------------------------------------------------------------------------ persistence

void UDACalendarSubsystem::WriteSaveData(TSharedPtr<FJsonObject>& Root) const
{
	if (!Root.IsValid())
	{
		return;
	}
	TSharedPtr<FJsonObject> CalendarObject = MakeShared<FJsonObject>();
	CalendarObject->SetNumberField(TEXT("year"), Year);
	CalendarObject->SetNumberField(TEXT("month"), GetMonthNumber());
	CalendarObject->SetNumberField(TEXT("month_index"), MonthIndex);
	CalendarObject->SetNumberField(TEXT("day"), Day);
	CalendarObject->SetStringField(TEXT("period"), PeriodToSaveKey(Period));
	CalendarObject->SetStringField(TEXT("weekday"), GetWeekdayName(Weekday));
	CalendarObject->SetNumberField(TEXT("hour"), Hour);
	Root->SetObjectField(TEXT("calendar"), CalendarObject);
}

bool UDACalendarSubsystem::ReadSaveData(const TSharedPtr<FJsonObject>& Root, FString& OutError)
{
	if (!Root.IsValid())
	{
		OutError = TEXT("Calendar save data is missing.");
		return false;
	}

	const TSharedPtr<FJsonObject>* CalendarObject = nullptr;
	const TSharedPtr<FJsonObject>& Source =
		(Root->TryGetObjectField(TEXT("calendar"), CalendarObject) && CalendarObject && CalendarObject->IsValid())
			? *CalendarObject
			: Root;

	const int32 OldYear = Year;
	const int32 OldMonth = MonthIndex;
	const int32 OldDay = Day;
	const EDADayPeriod OldPeriod = Period;

	int32 LoadedYear = 1;
	int32 LoadedMonthIndex = 0;
	int32 LoadedDay = 7;
	Source->TryGetNumberField(TEXT("year"), LoadedYear);
	if (!Source->TryGetNumberField(TEXT("month_index"), LoadedMonthIndex))
	{
		int32 MonthNumber = 10;
		if (Source->TryGetNumberField(TEXT("month"), MonthNumber))
		{
			LoadedMonthIndex = ((MonthNumber - 10) % 12 + 12) % 12;
		}
	}
	Source->TryGetNumberField(TEXT("day"), LoadedDay);

	EDADayPeriod LoadedPeriod = EDADayPeriod::AM;
	FString PeriodText;
	if (Source->TryGetStringField(TEXT("period"), PeriodText))
	{
		LoadedPeriod = ParsePeriod(PeriodText, EDADayPeriod::AM);
	}

	ApplyDateInternal(LoadedYear, LoadedMonthIndex, LoadedDay, LoadedPeriod);

	const bool bDateChanged = OldYear != Year || OldMonth != MonthIndex || OldDay != Day;
	OnCalendarChanged.Broadcast();
	if (bDateChanged)
	{
		OnDayChanged.Broadcast(Year, MonthIndex, Day);
	}
	if (OldPeriod != Period)
	{
		OnPeriodChanged.Broadcast(OldPeriod, Period);
	}
	OnVisualHourChanged.Broadcast(Hour);

	OutError.Reset();
	return true;
}
