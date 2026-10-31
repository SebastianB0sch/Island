// Duel Academy Island - headless NPC schedule/event/spawn self-test implementation.

#include "DANpcScheduleTest.h"

#include "DANpcDirector.h"
#include "DANpcSpawnPoint.h"
#include "DAStudentNPC.h"
#include "DuelAcademyIsland.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	constexpr float NpcScheduleTestTimeout = 180.f;
	constexpr int32 NpcScheduleExpectedPoints = 28;

	const TCHAR* const NpcScheduleWeekdays[] = {
		TEXT("Monday"), TEXT("Tuesday"), TEXT("Wednesday"), TEXT("Thursday"),
		TEXT("Friday"), TEXT("Saturday"), TEXT("Sunday")
	};

	bool NpcScheduleIsWeekday(const FString& Day)
	{
		return Day.Equals(TEXT("Monday"), ESearchCase::IgnoreCase)
			|| Day.Equals(TEXT("Tuesday"), ESearchCase::IgnoreCase)
			|| Day.Equals(TEXT("Wednesday"), ESearchCase::IgnoreCase)
			|| Day.Equals(TEXT("Thursday"), ESearchCase::IgnoreCase)
			|| Day.Equals(TEXT("Friday"), ESearchCase::IgnoreCase);
	}

	bool NpcScheduleIsWeekend(const FString& Day)
	{
		return Day.Equals(TEXT("Saturday"), ESearchCase::IgnoreCase)
			|| Day.Equals(TEXT("Sunday"), ESearchCase::IgnoreCase);
	}

	bool NpcScheduleSameTagSet(const TArray<FString>& Left, const TArray<FString>& Right)
	{
		if (Left.Num() != Right.Num())
		{
			return false;
		}

		TSet<FString> LeftSet;
		for (const FString& Tag : Left)
		{
			LeftSet.Add(Tag.ToLower());
		}
		for (const FString& Tag : Right)
		{
			if (!LeftSet.Contains(Tag.ToLower()))
			{
				return false;
			}
		}
		return true;
	}
}

void UDANpcScheduleTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	if (FParse::Param(FCommandLine::Get(), TEXT("DANpcScheduleTest")))
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDANpcScheduleTestSubsystem::Tick), 0.0f);
	}
}

void UDANpcScheduleTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

void UDANpcScheduleTestSubsystem::Check(bool bCondition, const FString& Name)
{
	if (bCondition)
	{
		++Passed;
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("PASS: %s"), *Name);
	}
	else
	{
		++Failed;
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("FAIL: %s"), *Name);
	}
}

bool UDANpcScheduleTestSubsystem::LoadSpawnData()
{
	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/World/spawns.json"));
	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *Path))
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("NPC schedule test: could not read %s"), *Path);
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("NPC schedule test: %s could not be parsed"), *Path);
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
	if (!Root->TryGetArrayField(TEXT("spawns"), Rows) || !Rows)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("NPC schedule test: %s has no spawns array"), *Path);
		return false;
	}

	SpawnData.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *Rows)
	{
		const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			continue;
		}

		FDANpcSchedulePointData Row;
		if (!Object->TryGetStringField(TEXT("id"), Row.Id) || Row.Id.IsEmpty())
		{
			continue;
		}

		Object->TryGetStringField(TEXT("schedule_id"), Row.ScheduleId);
		Object->TryGetStringField(TEXT("event_override"), Row.EventOverride);

		const TArray<TSharedPtr<FJsonValue>>* Tags = nullptr;
		if (Object->TryGetArrayField(TEXT("schedule_tags"), Tags) && Tags)
		{
			for (const TSharedPtr<FJsonValue>& Tag : *Tags)
			{
				if (Tag.IsValid())
				{
					Row.ScheduleTags.Add(Tag->AsString());
				}
			}
		}

		bool bFlag = false;
		if (Object->TryGetBoolField(TEXT("enabled"), bFlag))
		{
			Row.bEnabled = bFlag;
		}
		if (Object->TryGetBoolField(TEXT("event_only"), bFlag))
		{
			Row.bEventOnly = bFlag;
		}
		if (Object->TryGetBoolField(TEXT("spawn_on_begin_play"), bFlag))
		{
			Row.bSpawnOnBeginPlay = bFlag;
		}

		SpawnData.Add(Row);
	}

	RequiredSpawnIds.Reset();
	const TArray<TSharedPtr<FJsonValue>>* Required = nullptr;
	if (Root->TryGetArrayField(TEXT("opening_spawn_requirements"), Required) && Required)
	{
		for (const TSharedPtr<FJsonValue>& Value : *Required)
		{
			if (Value.IsValid())
			{
				RequiredSpawnIds.Add(Value->AsString());
			}
		}
	}

	return SpawnData.Num() > 0;
}

void UDANpcScheduleTestSubsystem::CollectWorld()
{
	SpawnPoints.Reset();
	SpawnPointsById.Reset();
	Director = ADANpcDirector::Get(GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr);

	UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	if (!World)
	{
		return;
	}

	for (TActorIterator<ADANpcSpawnPoint> It(World); It; ++It)
	{
		if (ADANpcSpawnPoint* Point = *It)
		{
			SpawnPoints.Add(Point);
			if (Point->SpawnPointId.IsEmpty() || SpawnPointsById.Contains(Point->SpawnPointId))
			{
				continue;
			}
			SpawnPointsById.Add(Point->SpawnPointId, Point);
		}
	}
}

ADANpcSpawnPoint* UDANpcScheduleTestSubsystem::FindPoint(const FString& SpawnPointId) const
{
	if (const TObjectPtr<ADANpcSpawnPoint>* Found = SpawnPointsById.Find(SpawnPointId))
	{
		return Found->Get();
	}
	return nullptr;
}

int32 UDANpcScheduleTestSubsystem::CountDirectorNpcs() const
{
	UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	ADANpcDirector* Owner = Director.Get();
	if (!World || !Owner)
	{
		return 0;
	}

	int32 Count = 0;
	for (TActorIterator<ADAStudentNPC> It(World); It; ++It)
	{
		ADAStudentNPC* Npc = *It;
		if (IsValid(Npc) && Npc->GetOwner() == Owner)
		{
			++Count;
		}
	}
	return Count;
}

void UDANpcScheduleTestSubsystem::VerifyRegistration()
{
	ADANpcDirector* D = Director.Get();
	Check(D != nullptr, TEXT("exactly one NPC director exists"));
	Check(SpawnData.Num() == NpcScheduleExpectedPoints,
		FString::Printf(TEXT("spawns.json declares %d points (found %d)"), NpcScheduleExpectedPoints, SpawnData.Num()));
	Check(SpawnPoints.Num() == NpcScheduleExpectedPoints,
		FString::Printf(TEXT("level contains %d spawn points (found %d)"), NpcScheduleExpectedPoints, SpawnPoints.Num()));

	if (!D)
	{
		return;
	}

	Check(D->GetRegisteredSpawnPointCount() == SpawnData.Num(),
		FString::Printf(TEXT("director registered %d points (expected %d)"),
			D->GetRegisteredSpawnPointCount(), SpawnData.Num()));
	Check(D->GetDefaultNpcClass() != nullptr, TEXT("director has a default NPC class"));

	TSet<FString> DataIds;
	for (const FDANpcSchedulePointData& Row : SpawnData)
	{
		Check(!DataIds.Contains(Row.Id), FString::Printf(TEXT("spawns.json id is unique: %s"), *Row.Id));
		DataIds.Add(Row.Id);
		Check(Row.ScheduleTags.Num() > 0, FString::Printf(TEXT("spawns.json %s has schedule tags"), *Row.Id));
	}

	TSet<FString> RuntimeIds;
	for (ADANpcSpawnPoint* Point : SpawnPoints)
	{
		if (!Point)
		{
			continue;
		}
		Check(!Point->SpawnPointId.IsEmpty(), TEXT("every level spawn point has an id"));
		Check(!RuntimeIds.Contains(Point->SpawnPointId),
			FString::Printf(TEXT("level spawn point id is unique: %s"), *Point->SpawnPointId));
		RuntimeIds.Add(Point->SpawnPointId);
		Check(DataIds.Contains(Point->SpawnPointId),
			FString::Printf(TEXT("level spawn point exists in spawns.json: %s"), *Point->SpawnPointId));
	}

	for (const FString& RequiredId : RequiredSpawnIds)
	{
		Check(SpawnPointsById.Contains(RequiredId),
			FString::Printf(TEXT("opening spawn requirement is registered: %s"), *RequiredId));
	}

	for (const FDANpcSchedulePointData& Row : SpawnData)
	{
		ADANpcSpawnPoint* Point = FindPoint(Row.Id);
		Check(Point != nullptr, FString::Printf(TEXT("%s exists in the level"), *Row.Id));
		if (!Point)
		{
			continue;
		}

		Check(Point->ScheduleId.Equals(Row.ScheduleId, ESearchCase::IgnoreCase),
			FString::Printf(TEXT("%s schedule id matches spawns.json ('%s')"), *Row.Id, *Row.ScheduleId));
		Check(NpcScheduleSameTagSet(Point->ScheduleTags, Row.ScheduleTags),
			FString::Printf(TEXT("%s schedule tags match spawns.json"), *Row.Id));
		Check(Point->EventOverride.Equals(Row.EventOverride, ESearchCase::IgnoreCase),
			FString::Printf(TEXT("%s event override matches spawns.json ('%s')"), *Row.Id, *Row.EventOverride));
		Check(Point->bEnabled == Row.bEnabled
				&& Point->bEventOnly == Row.bEventOnly
				&& Point->bSpawnOnBeginPlay == Row.bSpawnOnBeginPlay,
			FString::Printf(TEXT("%s enabled/event-only/begin-play flags match spawns.json"), *Row.Id));
	}
}

bool UDANpcScheduleTestSubsystem::ExpectedActive(const FDANpcSchedulePointData& Point, const FString& ScheduleId,
	const FString& Weekday, const FString& Period, const FString& Event) const
{
	if (!Point.bEnabled)
	{
		return false;
	}

	// Event overrides win: an event-pinned point only exists during that event.
	if (!Point.EventOverride.IsEmpty())
	{
		return Point.EventOverride.Equals(Event, ESearchCase::IgnoreCase);
	}

	if (Point.bEventOnly && Event.IsEmpty())
	{
		return false;
	}

	TArray<FString> Query;
	if (!ScheduleId.IsEmpty())
	{
		Query.Add(ScheduleId);
	}
	if (!Weekday.IsEmpty())
	{
		Query.Add(Weekday);
	}
	if (!Period.IsEmpty())
	{
		Query.Add(Period);
	}

	if (Query.Num() == 0)
	{
		return true;
	}

	if (NpcScheduleIsWeekday(Weekday))
	{
		Query.Add(TEXT("weekday"));
		if (Period.Equals(TEXT("AM"), ESearchCase::IgnoreCase))
		{
			Query.Add(TEXT("weekday_am"));
		}
		else if (Period.Equals(TEXT("PM"), ESearchCase::IgnoreCase))
		{
			Query.Add(TEXT("weekday_pm"));
		}
	}
	else if (NpcScheduleIsWeekend(Weekday))
	{
		Query.Add(TEXT("weekend"));
	}

	if (ScheduleId.Equals(TEXT("weekday"), ESearchCase::IgnoreCase))
	{
		Query.Add(TEXT("weekday"));
	}
	else if (ScheduleId.Equals(TEXT("weekend"), ESearchCase::IgnoreCase))
	{
		Query.Add(TEXT("weekend"));
	}

	for (const FString& Tag : Point.ScheduleTags)
	{
		for (const FString& Value : Query)
		{
			if (Tag.Equals(Value, ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
	}

	if (!Point.ScheduleId.IsEmpty())
	{
		for (const FString& Value : Query)
		{
			if (Point.ScheduleId.Equals(Value, ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
		return false;
	}

	return Point.ScheduleTags.Num() == 0;
}

void UDANpcScheduleTestSubsystem::VerifyActiveSet(const FString& CaseName, const FString& ScheduleId,
	const FString& Weekday, const FString& Period, const FString& Event)
{
	TSet<FString> Expected;
	for (const FDANpcSchedulePointData& Row : SpawnData)
	{
		if (ExpectedActive(Row, ScheduleId, Weekday, Period, Event))
		{
			Expected.Add(Row.Id);
		}
	}

	TSet<FString> Actual;
	TSet<AActor*> SeenNpcs;
	bool bDuplicate = false;
	int32 Occupied = 0;
	for (ADANpcSpawnPoint* Point : SpawnPoints)
	{
		if (!Point)
		{
			continue;
		}
		AActor* Npc = Point->GetSpawnedNpc();
		if (!IsValid(Npc))
		{
			continue;
		}
		++Occupied;
		Actual.Add(Point->SpawnPointId);
		if (SeenNpcs.Contains(Npc))
		{
			bDuplicate = true;
		}
		SeenNpcs.Add(Npc);
	}

	TArray<FString> Missing;
	for (const FString& Id : Expected)
	{
		if (!Actual.Contains(Id))
		{
			Missing.Add(Id);
		}
	}
	TArray<FString> Unexpected;
	for (const FString& Id : Actual)
	{
		if (!Expected.Contains(Id))
		{
			Unexpected.Add(Id);
		}
	}
	if (Missing.Num() > 0 || Unexpected.Num() > 0)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("NPC schedule test %s: missing [%s] unexpected [%s]"),
			*CaseName, *FString::Join(Missing, TEXT(", ")), *FString::Join(Unexpected, TEXT(", ")));
	}

	Check(Missing.Num() == 0 && Unexpected.Num() == 0,
		FString::Printf(TEXT("%s: active set matches spawns.json (%d expected, %d active)"),
			*CaseName, Expected.Num(), Actual.Num()));
	Check(!bDuplicate, FString::Printf(TEXT("%s: no NPC is assigned to two spawn points"), *CaseName));
	Check(Occupied == Expected.Num() && CountDirectorNpcs() == Expected.Num(),
		FString::Printf(TEXT("%s: spawned NPC count is %d with no orphans (actual %d/%d)"),
			*CaseName, Expected.Num(), Occupied, CountDirectorNpcs()));
}

void UDANpcScheduleTestSubsystem::RunScheduleCases()
{
	ADANpcDirector* D = Director.Get();
	if (!D)
	{
		Check(false, TEXT("schedule week has a director"));
		return;
	}

	D->SetActiveEvent(FString());
	for (const TCHAR* Day : NpcScheduleWeekdays)
	{
		for (int32 PeriodIndex = 0; PeriodIndex < 2; ++PeriodIndex)
		{
			const FString Weekday(Day);
			const FString Period = PeriodIndex == 0 ? TEXT("AM") : TEXT("PM");
			D->ApplySchedule(TEXT("default"), Weekday, Period);
			VerifyActiveSet(FString::Printf(TEXT("week %s %s"), *Weekday, *Period),
				TEXT("default"), Weekday, Period, FString());
		}
	}

	int32 DisabledActive = 0;
	int32 EventOnlyActive = 0;
	for (const FDANpcSchedulePointData& Row : SpawnData)
	{
		ADANpcSpawnPoint* Point = FindPoint(Row.Id);
		if (!Point || !Point->IsOccupied())
		{
			continue;
		}
		if (!Row.bEnabled)
		{
			++DisabledActive;
		}
		if (Row.bEventOnly && Row.EventOverride.IsEmpty())
		{
			++EventOnlyActive;
		}
	}
	Check(DisabledActive == 0, TEXT("full week: disabled spawn points stay inactive"));
	Check(EventOnlyActive == 0, TEXT("full week: event-only spawn points stay inactive without an event"));
}

void UDANpcScheduleTestSubsystem::RunEventCases()
{
	ADANpcDirector* D = Director.Get();
	if (!D)
	{
		Check(false, TEXT("event cases have a director"));
		return;
	}

	D->SetActiveEvent(FString());
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
	VerifyActiveSet(TEXT("event baseline"), TEXT("default"), TEXT("Monday"), TEXT("AM"), FString());

	D->SetActiveEvent(TEXT("tutorial_duel"));
	VerifyActiveSet(TEXT("event tutorial_duel"), TEXT("default"), TEXT("Monday"), TEXT("AM"), TEXT("tutorial_duel"));
	ADANpcSpawnPoint* Arena = FindPoint(TEXT("academy_arena_jaden"));
	Check(Arena && Arena->IsOccupied(), TEXT("tutorial_duel activates academy_arena_jaden"));

	D->SetActiveEvent(TEXT("E24"));
	VerifyActiveSet(TEXT("event E24"), TEXT("default"), TEXT("Monday"), TEXT("AM"), TEXT("E24"));
	ADANpcSpawnPoint* Titan = FindPoint(TEXT("abandoned_dorm_titan"));
	ADANpcSpawnPoint* Shadow = FindPoint(TEXT("volcano_shadow_duelist"));
	Check(Titan && Titan->IsOccupied(), TEXT("E24 activates abandoned_dorm_titan"));
	Check(Shadow && Shadow->IsOccupied(), TEXT("E24 activates volcano_shadow_duelist"));
	Check(Arena && !Arena->IsOccupied(), TEXT("E24 leaves tutorial_duel spawn inactive"));

	D->ApplySchedule(TEXT("E01"), TEXT("Monday"), TEXT("AM"));
	D->SetActiveEvent(TEXT("E01"));
	VerifyActiveSet(TEXT("event E01 assembly"), TEXT("E01"), TEXT("Monday"), TEXT("AM"), TEXT("E01"));
	ADANpcSpawnPoint* Instructor = FindPoint(TEXT("gym_assembly_instructor"));
	Check(Instructor && Instructor->IsOccupied(), TEXT("E01 activates gym_assembly_instructor"));

	D->SetActiveEvent(FString());
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
	VerifyActiveSet(TEXT("event restore"), TEXT("default"), TEXT("Monday"), TEXT("AM"), FString());
	Check(Arena && !Arena->IsOccupied(), TEXT("event restore clears academy_arena_jaden"));
	Check(Titan && !Titan->IsOccupied(), TEXT("event restore clears abandoned_dorm_titan"));
	Check(Shadow && !Shadow->IsOccupied(), TEXT("event restore clears volcano_shadow_duelist"));
}

void UDANpcScheduleTestSubsystem::RunSpawnDespawnCases()
{
	ADANpcDirector* D = Director.Get();
	if (!D)
	{
		Check(false, TEXT("spawn/despawn cases have a director"));
		return;
	}

	D->SetActiveEvent(FString());
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));

	ADANpcSpawnPoint* ActivePoint = FindPoint(TEXT("academy_receptionist"));
	ADANpcSpawnPoint* InactivePoint = FindPoint(TEXT("academy_arena_jaden"));
	Check(ActivePoint != nullptr && InactivePoint != nullptr, TEXT("spawn/despawn probes resolve"));
	if (!ActivePoint || !InactivePoint)
	{
		return;
	}

	const int32 Baseline = CountDirectorNpcs();
	AActor* ActiveNpc = ActivePoint->GetSpawnedNpc();
	D->DespawnAtPoint(TEXT("academy_receptionist"));
	Check(!ActivePoint->IsOccupied() && !IsValid(ActiveNpc),
		TEXT("DespawnAtPoint destroys academy_receptionist"));
	D->DespawnAtPoint(TEXT("academy_receptionist"));
	Check(!ActivePoint->IsOccupied(), TEXT("DespawnAtPoint is idempotent"));
	Check(CountDirectorNpcs() == Baseline - 1,
		FString::Printf(TEXT("despawn lowers director NPC count to %d"), Baseline - 1));

	AActor* First = D->SpawnAtPoint(TEXT("academy_arena_jaden"));
	Check(IsValid(First) && InactivePoint->IsOccupied(), TEXT("SpawnAtPoint spawns academy_arena_jaden"));
	AActor* Second = D->SpawnAtPoint(TEXT("academy_arena_jaden"));
	Check(First == Second && CountDirectorNpcs() == Baseline,
		TEXT("SpawnAtPoint returns the existing NPC without a duplicate"));
	D->DespawnAtPoint(TEXT("academy_arena_jaden"));
	Check(!InactivePoint->IsOccupied() && CountDirectorNpcs() == Baseline - 1,
		TEXT("manual despawn removes only academy_arena_jaden"));
	Check(D->SpawnAtPoint(TEXT("__missing_spawn__")) == nullptr,
		TEXT("SpawnAtPoint rejects an unknown spawn id"));

	D->SpawnAtPoint(TEXT("academy_receptionist"));
	Check(ActivePoint->IsOccupied() && CountDirectorNpcs() == Baseline,
		TEXT("spawn/despawn cycle restores the baseline NPC count"));

	ActivePoint->bEnabled = false;
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
	Check(!ActivePoint->IsOccupied(), TEXT("disabled spawn point despawns on schedule apply"));
	ActivePoint->bEnabled = true;
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
	Check(ActivePoint->IsOccupied() && CountDirectorNpcs() == Baseline,
		TEXT("re-enabled spawn point returns on schedule apply"));

	ActivePoint->bEventOnly = true;
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
	Check(!ActivePoint->IsOccupied(), TEXT("event-only spawn point stays off without an event"));
	D->SetActiveEvent(TEXT("gate3_test_event"));
	Check(ActivePoint->IsOccupied(), TEXT("event-only spawn point activates while an event runs"));
	D->SetActiveEvent(FString());
	ActivePoint->bEventOnly = false;
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
	Check(ActivePoint->IsOccupied() && CountDirectorNpcs() == Baseline,
		TEXT("event-only flag restore returns to the baseline set"));
}

void UDANpcScheduleTestSubsystem::RunRefreshCases()
{
	ADANpcDirector* D = Director.Get();
	if (!D)
	{
		Check(false, TEXT("refresh cases have a director"));
		return;
	}

	D->SetActiveEvent(FString());
	D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
	VerifyActiveSet(TEXT("refresh baseline"), TEXT("default"), TEXT("Monday"), TEXT("AM"), FString());

	ADANpcSpawnPoint* StablePoint = FindPoint(TEXT("academy_receptionist"));
	AActor* StableNpc = StablePoint ? StablePoint->GetSpawnedNpc() : nullptr;
	const int32 Baseline = CountDirectorNpcs();

	for (int32 Cycle = 0; Cycle < 3; ++Cycle)
	{
		const int32 Registered = D->RefreshSpawnPoints();
		Check(Registered == SpawnData.Num(),
			FString::Printf(TEXT("refresh cycle %d registers %d points"), Cycle + 1, SpawnData.Num()));
		Check(StablePoint && StablePoint->GetSpawnedNpc() == StableNpc,
			FString::Printf(TEXT("refresh cycle %d preserves existing NPCs without churn"), Cycle + 1));
		VerifyActiveSet(FString::Printf(TEXT("refresh cycle %d keeps AM"), Cycle + 1),
			TEXT("default"), TEXT("Monday"), TEXT("AM"), FString());

		D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("PM"));
		VerifyActiveSet(FString::Printf(TEXT("refresh cycle %d applies PM"), Cycle + 1),
			TEXT("default"), TEXT("Monday"), TEXT("PM"), FString());
		D->ApplySchedule(TEXT("default"), TEXT("Monday"), TEXT("AM"));
		VerifyActiveSet(FString::Printf(TEXT("refresh cycle %d restores AM"), Cycle + 1),
			TEXT("default"), TEXT("Monday"), TEXT("AM"), FString());
		Check(CountDirectorNpcs() == Baseline,
			FString::Printf(TEXT("refresh cycle %d leaves no NPC leak (%d expected)"), Cycle + 1, Baseline));
	}
}

void UDANpcScheduleTestSubsystem::Finish()
{
	if (bFinished)
	{
		return;
	}
	bFinished = true;

	UE_LOG(LogDuelAcademyIsland, Log,
		TEXT("NPC schedule test: %d passed, %d failed.%s"),
		Passed, Failed, Failed == 0 ? TEXT(" ALL PASS") : TEXT(" FAILURES PRESENT"));

	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}

	FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float)
	{
		FPlatformMisc::RequestExit(false);
		return false;
	}), 1.0f);
}

bool UDANpcScheduleTestSubsystem::Tick(float DeltaTime)
{
	if (bFinished)
	{
		return false;
	}

	WaitSeconds += DeltaTime;
	if (WaitSeconds > NpcScheduleTestTimeout)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("NPC schedule test: timed out after %.0f seconds."),
			NpcScheduleTestTimeout);
		Check(false, TEXT("NPC schedule test completed before the timeout"));
		Finish();
		return false;
	}

	UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	if (!World || !World->HasBegunPlay())
	{
		return true;
	}

	if (!Director.IsValid())
	{
		Director = ADANpcDirector::Get(World);
	}
	if (!Director.IsValid())
	{
		if (WaitSeconds >= 5.f)
		{
			Check(false, TEXT("exactly one NPC director exists"));
			Finish();
			return false;
		}
		return true;
	}

	if (!bDataLoaded)
	{
		bDataLoaded = LoadSpawnData();
		Check(bDataLoaded, TEXT("Content/Data/World/spawns.json loads"));
		if (!bDataLoaded)
		{
			Finish();
			return false;
		}
	}

	if (!bWorldCollected)
	{
		// Give actor BeginPlay a couple of frames to auto-register the points.
		ADANpcDirector* D = Director.Get();
		if (D && D->GetRegisteredSpawnPointCount() == 0 && WaitSeconds < 5.f)
		{
			return true;
		}

		CollectWorld();
		if (SpawnPoints.Num() == 0 && WaitSeconds < 5.f)
		{
			return true;
		}

		bWorldCollected = true;
		VerifyRegistration();
		RunScheduleCases();
		RunEventCases();
		RunSpawnDespawnCases();
		RunRefreshCases();
		Finish();
	}

	return !bFinished;
}
