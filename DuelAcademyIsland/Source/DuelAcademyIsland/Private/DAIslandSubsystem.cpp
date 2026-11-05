// Duel Academy Island - world subsystem.

#include "DAIslandSubsystem.h"

#include "DAInteriorPortal.h"
#include "DAIslandManager.h"
#include "DALocationVolume.h"
#include "DACalendarSubsystem.h"
#include "DANpcDirector.h"
#include "Dom/JsonValue.h"
#include "DuelAcademyIsland.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

namespace
{
	const TCHAR* const WorldSectionVersionField = TEXT("version");
	constexpr float WorldStateDirectorWaitSeconds = 10.f;
}

void UDAIslandSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	TryRegisterSaveProvider();
}

void UDAIslandSubsystem::Deinitialize()
{
	if (bSaveProviderRegistered)
	{
		if (UGameInstance* GameInstance = GetWorld() ? GetWorld()->GetGameInstance() : nullptr)
		{
			if (UDASaveSubsystem* Save = GameInstance->GetSubsystem<UDASaveSubsystem>())
			{
				Save->UnregisterPayloadProvider(this);
			}
		}
		bSaveProviderRegistered = false;
	}

	Zones.Reset();
	Interactables.Reset();
	MessageQueue.Reset();
	PendingWorldState = FDAWorldSaveState();
	bWorldStatePending = false;
	Super::Deinitialize();
}

void UDAIslandSubsystem::TryRegisterSaveProvider()
{
	if (bSaveProviderRegistered)
	{
		return;
	}
	UWorld* World = GetWorld();
	UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
	if (!GameInstance)
	{
		return;
	}
	if (UDASaveSubsystem* Save = GameInstance->GetSubsystem<UDASaveSubsystem>())
	{
		Save->RegisterPayloadProvider(this);
		bSaveProviderRegistered = true;
	}
}

TStatId UDAIslandSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UDAIslandSubsystem, STATGROUP_Tickables);
}

UDAIslandSubsystem* UDAIslandSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	const UWorld* World = WorldContext->GetWorld();
	return World ? World->GetSubsystem<UDAIslandSubsystem>() : nullptr;
}

void UDAIslandSubsystem::Tick(float DeltaTime)
{
	UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld())
	{
		return;
	}

	// The world state provider may have been registered before the game
	// instance finished creating the save subsystem, or not at all in editor
	// worlds. Retry cheaply; this is a no-op once registered.
	TryRegisterSaveProvider();

	if (bWorldStatePending)
	{
		PendingWorldStateSeconds += DeltaTime;
		if (!ApplyPendingWorldState() && PendingWorldStateSeconds >= WorldStateDirectorWaitSeconds)
		{
			ExpirePendingWorldState();
		}
	}

	ZonePollAccumulator += DeltaTime;
	if (ZonePollAccumulator >= 0.25f)
	{
		ZonePollAccumulator = 0.f;
		UpdateCurrentZone();

		// W2: weekday/period cast bridge. Suppressed on the one poll that
		// follows a pass of ApplyPendingWorldState materializing the saved
		// NPC schedule (or holding it for a director) so the restored
		// schedule is never double-applied. The pending queue may
		// legitimately still hold unresolved portal ids (retry window);
		// those do not touch the cast, so the bridge keeps running.
		// The flag is consumed on read: exactly one poll is suppressed.
		const bool bSuppressThisPoll = bScheduleBridgeSuppressTick;
		bScheduleBridgeSuppressTick = false;
		if (!bSuppressThisPoll)
		{
			if (bScheduleBridgeHoldPrev)
			{
				// Hold->resume edge, taken once: prime instead of re-applying
				// what the restore already applied.
				bScheduleBridgeHoldPrev = false;
				bScheduleBridgePrimed = false;
			}
			UpdateScheduleBridge();
		}
		else
		{
			bScheduleBridgeHoldPrev = true;
		}
	}

	// Expire timed messages.
	if (MessageQueue.Num() > 0)
	{
		const FDAMessage& Msg = MessageQueue[0];
		if (Msg.Duration > 0.f && World->GetTimeSeconds() - ActiveMessageStart > Msg.Duration)
		{
			DismissMessage();
		}
	}
}

// ------------------------------------------------------------------------ zones

void UDAIslandSubsystem::RegisterZone(ADALocationVolume* Zone)
{
	if (Zone)
	{
		Zones.AddUnique(Zone);
	}
}

void UDAIslandSubsystem::UnregisterZone(ADALocationVolume* Zone)
{
	Zones.Remove(Zone);
}

TArray<ADALocationVolume*> UDAIslandSubsystem::GetZones() const
{
	TArray<ADALocationVolume*> Out;
	for (const TWeakObjectPtr<ADALocationVolume>& Z : Zones)
	{
		if (Z.IsValid())
		{
			Out.Add(Z.Get());
		}
	}
	Out.Sort([](const ADALocationVolume& A, const ADALocationVolume& B)
	{
		if (A.SortOrder != B.SortOrder)
		{
			return A.SortOrder < B.SortOrder;
		}
		return A.LocationId < B.LocationId;
	});
	return Out;
}

bool UDAIslandSubsystem::IsDiscovered(const ADALocationVolume* Zone) const
{
	return Zone && Discovered.Contains(Zone->LocationId);
}

void UDAIslandSubsystem::UpdateCurrentZone()
{
	UWorld* World = GetWorld();
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return;
	}
	const FVector P = Pawn->GetActorLocation();

	ADALocationVolume* Best = nullptr;
	double BestVolume = TNumericLimits<double>::Max();
	for (const TWeakObjectPtr<ADALocationVolume>& WeakZone : Zones)
	{
		ADALocationVolume* Zone = WeakZone.Get();
		if (!Zone || !Zone->ContainsPoint(P))
		{
			continue;
		}
		const double Vol = Zone->GetZoneVolume();
		// Equal-volume nesting is possible (two boxes with the same extents);
		// use the authored map order and then the id so the result is stable.
		const bool bBetter = !Best
			|| Vol < BestVolume
			|| (FMath::Abs(Vol - BestVolume) <= 1.0
				&& (Zone->SortOrder < Best->SortOrder
					|| (Zone->SortOrder == Best->SortOrder && Zone->LocationId < Best->LocationId)));
		if (bBetter)
		{
			BestVolume = Vol;
			Best = Zone;
		}
	}

	if (Best != CurrentZone.Get())
	{
		CurrentZone = Best;
		ZoneChangeTime = World->GetTimeSeconds();
		bLastZoneFirstVisit = false;
		if (Best && !Best->LocationId.IsEmpty())
		{
			bool bAlreadyKnown = false;
			Discovered.Add(Best->LocationId, &bAlreadyKnown);
			bLastZoneFirstVisit = !bAlreadyKnown;
			PlayUISound(bLastZoneFirstVisit ? FName(TEXT("A_Discover")) : FName(TEXT("A_UIClick")), bLastZoneFirstVisit ? 0.8f : 0.3f);
		}
		OnZoneChanged.Broadcast(Best, bLastZoneFirstVisit);
	}
}

// ------------------------------------------------------------------------ interactables

void UDAIslandSubsystem::RegisterInteractable(AActor* Interactable)
{
	if (Interactable)
	{
		Interactables.AddUnique(Interactable);
	}
}

void UDAIslandSubsystem::UnregisterInteractable(AActor* Interactable)
{
	Interactables.Remove(Interactable);
}

// ------------------------------------------------------------------------ messages

void UDAIslandSubsystem::PushMessage(const FDAMessage& Message)
{
	// A new message replaces whatever is on screen - interactions should feel immediate.
	MessageQueue.Reset();
	MessageQueue.Add(Message);
	if (const UWorld* World = GetWorld())
	{
		ActiveMessageStart = World->GetTimeSeconds();
	}
}

const FDAMessage* UDAIslandSubsystem::GetActiveMessage() const
{
	return MessageQueue.Num() > 0 ? &MessageQueue[0] : nullptr;
}

float UDAIslandSubsystem::GetActiveMessageAge() const
{
	const UWorld* World = GetWorld();
	return World ? World->GetTimeSeconds() - ActiveMessageStart : 0.f;
}

void UDAIslandSubsystem::DismissMessage()
{
	if (MessageQueue.Num() > 0)
	{
		MessageQueue.RemoveAt(0);
		if (const UWorld* World = GetWorld())
		{
			ActiveMessageStart = World->GetTimeSeconds();
		}
	}
}

// ------------------------------------------------------------------------ environment

ADAIslandManager* UDAIslandSubsystem::GetManager() const
{
	if (!CachedManager.IsValid())
	{
		if (UWorld* World = GetWorld())
		{
			for (TActorIterator<ADAIslandManager> It(World); It; ++It)
			{
				CachedManager = *It;
				break;
			}
		}
	}
	return CachedManager.Get();
}

float UDAIslandSubsystem::GetWaterSurfaceZ(const FVector& WorldLocation) const
{
	if (const ADAIslandManager* M = GetManager())
	{
		return M->GetWaterSurfaceZ(WorldLocation);
	}
	return 0.f;
}

void UDAIslandSubsystem::PlayUISound(const FName SoundName, float Volume) const
{
	const FString Path = FString::Printf(TEXT("%s%s.%s"), DuelAcademy::SoundFolder, *SoundName.ToString(), *SoundName.ToString());
	if (USoundBase* Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		UGameplayStatics::PlaySound2D(this, Sound, Volume);
	}
}

// ------------------------------------------------------------------------ discovery persistence

TArray<FString> UDAIslandSubsystem::GetDiscoveredLocationIds() const
{
	TArray<FString> Ids = Discovered.Array();
	Ids.Sort();
	return Ids;
}

void UDAIslandSubsystem::RestoreDiscoveredLocationIds(const TArray<FString>& LocationIds)
{
	Discovered.Reset();
	for (const FString& LocationId : LocationIds)
	{
		if (!LocationId.IsEmpty())
		{
			Discovered.Add(LocationId);
		}
	}
}

// ------------------------------------------------------------------------ world save state

FString UDAIslandSubsystem::GetSaveSectionName() const
{
	return TEXT("world");
}

bool UDAIslandSubsystem::WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const
{
	if (!OutSection.IsValid())
	{
		OutSection = MakeShared<FJsonObject>();
	}
	OutSection->SetNumberField(WorldSectionVersionField, 1);

	TArray<FDAPortalSaveState> PortalStates;
	ADAInteriorPortal::CollectSaveStates(GetWorld(), PortalStates);
	TArray<TSharedPtr<FJsonValue>> PortalArray;
	PortalArray.Reserve(PortalStates.Num());
	for (const FDAPortalSaveState& State : PortalStates)
	{
		TSharedPtr<FJsonObject> PortalObject = MakeShared<FJsonObject>();
		PortalObject->SetStringField(TEXT("id"), State.PortalId);
		PortalObject->SetBoolField(TEXT("locked"), State.bLocked);
		PortalObject->SetBoolField(TEXT("used"), State.bUsed);
		PortalArray.Add(MakeShared<FJsonValueObject>(PortalObject));
	}
	OutSection->SetArrayField(TEXT("portals"), PortalArray);

	TArray<TSharedPtr<FJsonValue>> DiscoveredArray;
	for (const FString& LocationId : GetDiscoveredLocationIds())
	{
		DiscoveredArray.Add(MakeShared<FJsonValueString>(LocationId));
	}
	OutSection->SetArrayField(TEXT("discovered"), DiscoveredArray);

	// Schedule inputs only: spawned actor identity is reconstructed by
	// ApplySchedule, so no actor references are serialized here.
	if (const ADANpcDirector* Director = ADANpcDirector::Get(this))
	{
		OutSection->SetBoolField(TEXT("npc_schedule_applied"), Director->HasAppliedSchedule());
		OutSection->SetStringField(TEXT("npc_schedule_id"), Director->GetCurrentScheduleId());
		OutSection->SetStringField(TEXT("npc_weekday"), Director->GetCurrentWeekday());
		OutSection->SetStringField(TEXT("npc_period"), Director->GetCurrentPeriod());
		OutSection->SetStringField(TEXT("npc_active_event"), Director->GetActiveEvent());
	}

	return true;
}

bool UDAIslandSubsystem::ValidateSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) const
{
	if (!InSection.IsValid())
	{
		OutError = TEXT("World save section is missing.");
		return false;
	}

	if (InSection->HasField(WorldSectionVersionField))
	{
		double Version = 0.0;
		if (!InSection->TryGetNumberField(WorldSectionVersionField, Version) || !FMath::IsFinite(Version))
		{
			OutError = TEXT("World save section has an invalid version.");
			return false;
		}
	}

	if (InSection->HasField(TEXT("discovered")))
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!InSection->TryGetArrayField(TEXT("discovered"), Values) || !Values)
		{
			OutError = TEXT("World save field 'discovered' is not an array.");
			return false;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			if (!Value.IsValid() || Value->Type != EJson::String)
			{
				OutError = TEXT("World save 'discovered' contains a non-string id.");
				return false;
			}
		}
	}

	if (InSection->HasField(TEXT("portals")))
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!InSection->TryGetArrayField(TEXT("portals"), Values) || !Values)
		{
			OutError = TEXT("World save field 'portals' is not an array.");
			return false;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			if (!Value.IsValid() || Value->Type != EJson::Object || !Value->AsObject().IsValid())
			{
				OutError = TEXT("World save 'portals' contains a non-object entry.");
				return false;
			}
			const TSharedPtr<FJsonObject> PortalObject = Value->AsObject();
			if (PortalObject->HasField(TEXT("id")))
			{
				FString PortalId;
				if (!PortalObject->TryGetStringField(TEXT("id"), PortalId))
				{
					OutError = TEXT("World save portal entry has a non-string id.");
					return false;
				}
			}
			for (const TCHAR* FlagField : { TEXT("locked"), TEXT("used") })
			{
				if (PortalObject->HasField(FlagField))
				{
					bool bValue = false;
					if (!PortalObject->TryGetBoolField(FlagField, bValue))
					{
						OutError = FString::Printf(TEXT("World save portal entry has a non-boolean '%s'."), FlagField);
						return false;
					}
				}
			}
		}
	}

	if (InSection->HasField(TEXT("npc_schedule_applied")))
	{
		bool bApplied = false;
		if (!InSection->TryGetBoolField(TEXT("npc_schedule_applied"), bApplied))
		{
			OutError = TEXT("World save field 'npc_schedule_applied' is not a boolean.");
			return false;
		}
	}
	for (const TCHAR* StringField : { TEXT("npc_schedule_id"), TEXT("npc_weekday"), TEXT("npc_period"), TEXT("npc_active_event") })
	{
		if (InSection->HasField(StringField))
		{
			FString Text;
			if (!InSection->TryGetStringField(StringField, Text))
			{
				OutError = FString::Printf(TEXT("World save field '%s' is not a string."), StringField);
				return false;
			}
		}
	}

	OutError.Reset();
	return true;
}

bool UDAIslandSubsystem::ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError)
{
	if (!ValidateSaveSection(InSection, OutError))
	{
		return false;
	}

	FDAWorldSaveState Loaded;

	const TArray<TSharedPtr<FJsonValue>>* DiscoveredValues = nullptr;
	if (InSection->TryGetArrayField(TEXT("discovered"), DiscoveredValues) && DiscoveredValues)
	{
		Loaded.bHasDiscoveredState = true;
		for (const TSharedPtr<FJsonValue>& Value : *DiscoveredValues)
		{
			if (Value.IsValid() && Value->Type == EJson::String)
			{
				const FString LocationId = Value->AsString();
				if (!LocationId.IsEmpty())
				{
					Loaded.Discovered.AddUnique(LocationId);
				}
			}
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* PortalValues = nullptr;
	if (InSection->TryGetArrayField(TEXT("portals"), PortalValues) && PortalValues)
	{
		TSet<FString> SeenIds;
		for (const TSharedPtr<FJsonValue>& Value : *PortalValues)
		{
			const TSharedPtr<FJsonObject> PortalObject = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!PortalObject.IsValid())
			{
				continue;
			}
			FString PortalId;
			if (!PortalObject->TryGetStringField(TEXT("id"), PortalId) || PortalId.IsEmpty())
			{
				// Empty ids are ignored, never treated as a wildcard.
				continue;
			}
			if (SeenIds.Contains(PortalId))
			{
				// Duplicate entries: first one wins, matching the batch applier.
				continue;
			}
			SeenIds.Add(PortalId);

			FDAWorldPortalSaveEntry Entry;
			Entry.PortalId = PortalId;
			PortalObject->TryGetBoolField(TEXT("locked"), Entry.bLocked);
			PortalObject->TryGetBoolField(TEXT("used"), Entry.bUsed);
			Loaded.Portals.Add(MoveTemp(Entry));
		}
	}

	bool bScheduleApplied = false;
	if (InSection->TryGetBoolField(TEXT("npc_schedule_applied"), bScheduleApplied))
	{
		Loaded.bHasNpcSchedule = true;
		Loaded.bNpcScheduleApplied = bScheduleApplied;
		InSection->TryGetStringField(TEXT("npc_schedule_id"), Loaded.ScheduleId);
		InSection->TryGetStringField(TEXT("npc_weekday"), Loaded.Weekday);
		InSection->TryGetStringField(TEXT("npc_period"), Loaded.Period);
		InSection->TryGetStringField(TEXT("npc_active_event"), Loaded.ActiveEvent);
	}

	PendingWorldState = MoveTemp(Loaded);
	bWorldStatePending = PendingWorldState.Portals.Num() > 0
		|| PendingWorldState.bHasDiscoveredState
		|| PendingWorldState.bHasNpcSchedule;
	PendingWorldStateSeconds = 0.f;

	// Deliberately deferred: the payload may be applied while the world is
	// still loading actors. Tick (or an explicit game-mode/test hook) applies
	// it; ApplyPendingWorldState is idempotent.
	OutError.Reset();
	return true;
}

bool UDAIslandSubsystem::ApplyPendingWorldState()
{
	if (!bWorldStatePending)
	{
		return true;
	}

	// W3: portals resolve what exists now and keep the rest queued. Every
	// resolved entry already holds its saved flags (assignment is idempotent),
	// so only the unresolved ids are retried on the next pass.
	if (PendingWorldState.Portals.Num() > 0)
	{
		TArray<FDAPortalSaveState> States;
		States.Reserve(PendingWorldState.Portals.Num());
		for (const FDAWorldPortalSaveEntry& Entry : PendingWorldState.Portals)
		{
			FDAPortalSaveState State;
			State.PortalId = Entry.PortalId;
			State.bLocked = Entry.bLocked;
			State.bUsed = Entry.bUsed;
			States.Add(MoveTemp(State));
		}

		TArray<FString> UnresolvedIds;
		ADAInteriorPortal::ApplySaveStates(GetWorld(), States, &UnresolvedIds);
		if (UnresolvedIds.Num() > 0)
		{
			// Keep exactly the ids whose actor does not exist yet (level still
			// spawning, future streaming); the resolved rows are not re-run.
			TArray<FDAWorldPortalSaveEntry> Remaining;
			for (const FDAWorldPortalSaveEntry& Entry : PendingWorldState.Portals)
			{
				if (UnresolvedIds.Contains(Entry.PortalId))
				{
					Remaining.Add(Entry);
				}
			}
			PendingWorldState.Portals = MoveTemp(Remaining);
			UE_LOG(LogDuelAcademyIsland, Verbose,
				TEXT("World: %d saved portal id(s) resolved to no live actor yet; queued for retry."),
				UnresolvedIds.Num());
		}
		else
		{
			PendingWorldState.Portals.Reset();
		}
	}

	if (PendingWorldState.bHasDiscoveredState)
	{
		// P4-10: merge into the live set instead of replacing it. The queue can
		// apply after the zone poll already discovered the player's spawn zone
		// this session; a replace here would wipe that discovery permanently
		// because later saves re-export the reduced set.
		int32 AddedCount = 0;
		for (const FString& LocationId : PendingWorldState.Discovered)
		{
			if (!LocationId.IsEmpty() && !Discovered.Contains(LocationId))
			{
				Discovered.Add(LocationId);
				++AddedCount;
			}
		}
		if (AddedCount > 0)
		{
			UE_LOG(LogDuelAcademyIsland, Log,
				TEXT("World: merged %d saved discovered location id(s) into the live set (%d total); same-frame discoveries are kept."),
				AddedCount, Discovered.Num());
		}
		PendingWorldState.bHasDiscoveredState = false;
	}

	if (PendingWorldState.bHasNpcSchedule)
	{
		ADANpcDirector* Director = ADANpcDirector::Get(this);
		if (!Director)
		{
			// The level may still be starting. Keep the queue; Tick retries.
			bWorldStatePending = true;
			// W2: suppress the schedule bridge on this pass; the slice is
			// still queued and will apply on a later pass.
			bScheduleBridgeSuppressTick = true;
			return false;
		}
		Director->RestoreScheduleState(PendingWorldState.bNpcScheduleApplied,
			PendingWorldState.ScheduleId, PendingWorldState.Weekday,
			PendingWorldState.Period, PendingWorldState.ActiveEvent);
		// Applied once: a later retry pass must not re-run the schedule
		// (the no-schedule baseline branch is not idempotent across retries).
		PendingWorldState.bHasNpcSchedule = false;
		// W2: suppress the schedule bridge on this pass so a live calendar
		// change cannot race the just-restored schedule into a double apply.
		bScheduleBridgeSuppressTick = true;
	}

	bWorldStatePending = PendingWorldState.Portals.Num() > 0 || PendingWorldState.bHasNpcSchedule;
	if (bWorldStatePending)
	{
		// Discovery state is applied atomically; never carry it into retries.
		PendingWorldState.Discovered.Reset();
		PendingWorldState.bHasDiscoveredState = false;
		return false;
	}

	PendingWorldStateSeconds = 0.f;
	PendingWorldState = FDAWorldSaveState();
	return true;
}

void UDAIslandSubsystem::ExpirePendingWorldState()
{
	if (!bWorldStatePending)
	{
		return;
	}

	UE_LOG(LogDuelAcademyIsland, Warning,
		TEXT("World: pending world state still unresolved after %.0f s (missing NPC director and/or portal actors); dropping the remainder."),
		PendingWorldStateSeconds);
	PendingWorldState = FDAWorldSaveState();
	bWorldStatePending = false;
	PendingWorldStateSeconds = 0.f;
}

void UDAIslandSubsystem::UpdateScheduleBridge()
{
	const UDACalendarSubsystem* Calendar = UDACalendarSubsystem::Get(this);
	if (!Calendar)
	{
		UE_LOG(LogTemp, Verbose, TEXT("[BRIDGE] no calendar"));
		return;
	}

	const FString Weekday = Calendar->GetWeekdayName(Calendar->GetWeekday());
	const FString Period = Calendar->GetPeriodName(Calendar->GetPeriod());

	if (!bScheduleBridgePrimed)
	{
		// Baseline = the last cast alignment. The director's state IS that
		// alignment whenever it has applied a schedule (its begin play, a
		// restore, tests); only fall back to the calendar while no director
		// has ever applied anything. Priming from the calendar here would
		// treat the difference between the director's state and the current
		// calendar moment as "no change" and silently swallow it.
		if (ADANpcDirector* Director = ADANpcDirector::Get(this))
		{
			if (Director->HasAppliedSchedule())
			{
				bScheduleBridgePrimed = true;
				ScheduleBridgeWeekday = Director->GetCurrentWeekday();
				ScheduleBridgePeriod = Director->GetCurrentPeriod();
				UE_LOG(LogTemp, Verbose,
					TEXT("[BRIDGE] priming from director %s / %s"),
					*ScheduleBridgeWeekday, *ScheduleBridgePeriod);
				return;
			}
		}
		bScheduleBridgePrimed = true;
		ScheduleBridgeWeekday = Weekday;
		ScheduleBridgePeriod = Period;
		UE_LOG(LogTemp, Verbose, TEXT("[BRIDGE] priming from calendar %s / %s"), *Weekday, *Period);
		return;
	}

	if (Weekday.Equals(ScheduleBridgeWeekday, ESearchCase::IgnoreCase)
		&& Period.Equals(ScheduleBridgePeriod, ESearchCase::IgnoreCase))
	{
		// Unchanged combo: never re-apply an identical schedule.
		return;
	}

	ScheduleBridgeWeekday = Weekday;
	ScheduleBridgePeriod = Period;

	ADANpcDirector* Director = ADANpcDirector::Get(this);
	if (Director)
	{
		// A period change re-runs the director's CURRENT schedule id with the
		// new weekday/period, so save-restored filters and story-pinned
		// schedules keep their id. Event-only points keep following
		// SetActiveEvent; a missing director is not an error (record the combo
		// and let the first real application come from its owner).
		Director->ApplySchedule(Director->GetCurrentScheduleId(), Weekday, Period);
	}
	else
	{
		UE_LOG(LogTemp, Verbose, TEXT("[BRIDGE] no director, combo recorded only"));
	}
}

void UDAIslandSubsystem::NotifyScheduleApplied(const FString& Weekday, const FString& Period)
{
	// Re-baseline the bridge to the combo the just-applied cast represents.
	bScheduleBridgePrimed = true;
	ScheduleBridgeWeekday = Weekday;
	ScheduleBridgePeriod = Period;
	UE_LOG(LogTemp, Verbose,
		TEXT("[ISLAND] bridge re-baselined from schedule apply %s / %s"),
		*Weekday, *Period);
}
