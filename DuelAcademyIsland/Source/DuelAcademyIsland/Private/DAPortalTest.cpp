// Duel Academy Island - PIE portal entry/exit self-test implementation.

#include "DAPortalTest.h"

#include "DAInteriorPortal.h"
#include "DAIslandSubsystem.h"
#include "DuelAcademyIsland.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"

namespace
{
	constexpr float PortalTestMoveTolerance = 250.f;
	constexpr float PortalTestZTolerance = 450.f;
	constexpr float PortalTestWaitEntry = 0.9f;
	constexpr float PortalTestWaitReturn = 2.8f;
	constexpr float PortalTestTimeout = 150.f;

	bool IsInteriorSide(const FVector& Location)
	{
		return FMath::Abs(Location.X) >= 200000.f || FMath::Abs(Location.Y) >= 200000.f;
	}
}

void UDAPortalTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	if (FParse::Param(FCommandLine::Get(), TEXT("DAPortalTest")))
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDAPortalTestSubsystem::Tick), 0.0f);
	}
}

void UDAPortalTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

void UDAPortalTestSubsystem::Check(bool bCondition, const FString& Name)
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

FVector UDAPortalTestSubsystem::ExpectedArrival(const ADAInteriorPortal* Portal) const
{
	if (!Portal)
	{
		return FVector::ZeroVector;
	}
	if (Portal->bSnapToLinkedPortal)
	{
		if (const ADAInteriorPortal* Linked = Portal->FindLinkedPortal())
		{
			return Linked->GetActorLocation() + Linked->GetActorForwardVector() * Portal->ArrivalOffset;
		}
	}
	return Portal->TargetLocation;
}

void UDAPortalTestSubsystem::CollectPortals(UWorld* World)
{
	bCollected = true;

	for (TActorIterator<ADAInteriorPortal> It(World); It; ++It)
	{
		if (ADAInteriorPortal* Portal = *It)
		{
			Portals.Add(Portal);
			if (IsInteriorSide(Portal->GetActorLocation()))
			{
				Returns.Add(Portal);
			}
			else
			{
				Entries.Add(Portal);
			}
		}
	}

	Portals.Sort([](const ADAInteriorPortal& A, const ADAInteriorPortal& B) { return A.PortalId < B.PortalId; });
	Entries.Sort([](const ADAInteriorPortal& A, const ADAInteriorPortal& B) { return A.PortalId < B.PortalId; });
	Returns.Sort([](const ADAInteriorPortal& A, const ADAInteriorPortal& B) { return A.PortalId < B.PortalId; });

	Check(Portals.Num() == 20, FString::Printf(TEXT("level contains 20 portals (found %d)"), Portals.Num()));
	Check(Entries.Num() == 10, FString::Printf(TEXT("10 exterior entry portals (found %d)"), Entries.Num()));
	Check(Returns.Num() == 10, FString::Printf(TEXT("10 interior return portals (found %d)"), Returns.Num()));

	TSet<FString> Ids;
	TSet<FString> LinkedTargets;
	for (const ADAInteriorPortal* Portal : Portals)
	{
		Check(!Portal->PortalId.IsEmpty(), TEXT("portal has a non-empty id"));
		Check(!Ids.Contains(Portal->PortalId), FString::Printf(TEXT("portal id unique: %s"), *Portal->PortalId));
		Ids.Add(Portal->PortalId);
		Check(!Portal->InteriorId.IsEmpty(), FString::Printf(TEXT("portal %s names an interior"), *Portal->PortalId));
		Check(!Portal->TargetLocation.IsNearlyZero(), FString::Printf(TEXT("portal %s has a destination"), *Portal->PortalId));

		Check(!Portal->TargetPortalId.IsEmpty(), FString::Printf(TEXT("%s names a paired portal"), *Portal->PortalId));
		Check(Portal->TargetPortalId != Portal->PortalId, FString::Printf(TEXT("%s does not link to itself"), *Portal->PortalId));
		if (!Portal->TargetPortalId.IsEmpty())
		{
			Check(!LinkedTargets.Contains(Portal->TargetPortalId),
				FString::Printf(TEXT("%s is the only portal linked to %s"), *Portal->PortalId, *Portal->TargetPortalId));
			LinkedTargets.Add(Portal->TargetPortalId);

			const ADAInteriorPortal* Linked = Portal->FindLinkedPortal();
			Check(Linked != nullptr, FString::Printf(TEXT("%s links to its paired portal"), *Portal->PortalId));
			if (Linked)
			{
				Check(Linked->TargetPortalId == Portal->PortalId,
					FString::Printf(TEXT("%s / %s are reciprocal"), *Portal->PortalId, *Linked->PortalId));
			}
		}
	}

	for (const ADAInteriorPortal* Entry : Entries)
	{
		const ADAInteriorPortal* Linked = Entry->FindLinkedPortal();
		Check(Linked != nullptr, FString::Printf(TEXT("%s links to its return portal"), *Entry->PortalId));
		if (Linked)
		{
			Check(Linked->TargetPortalId == Entry->PortalId,
				FString::Printf(TEXT("%s / %s are reciprocal"), *Entry->PortalId, *Linked->PortalId));
			Check(IsInteriorSide(Linked->GetActorLocation()),
				FString::Printf(TEXT("%s return portal sits inside the cell"), *Entry->PortalId));
			Check(IsInteriorSide(ExpectedArrival(Entry)),
				FString::Printf(TEXT("%s arrival is inside the cell"), *Entry->PortalId));
			Check(!IsInteriorSide(ExpectedArrival(Linked)),
				FString::Printf(TEXT("%s arrival returns outside"), *Entry->PortalId));
		}
	}

	VerifySaveStateContract();
	VerifyWorldSaveStateContract();
}

void UDAPortalTestSubsystem::VerifyWorldSaveStateContract()
{
	UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	UDAIslandSubsystem* Island = World ? World->GetSubsystem<UDAIslandSubsystem>() : nullptr;
	Check(Island != nullptr, TEXT("island subsystem owns the world save section"));
	if (!Island)
	{
		return;
	}
	Check(Island->GetSaveSectionName() == TEXT("world"), TEXT("world save section name is stable"));

	ADAInteriorPortal* Portal = Portals.Num() > 0 ? Portals[0].Get() : nullptr;
	if (!Portal)
	{
		Check(false, TEXT("world save-state probe has a portal"));
		return;
	}
	const bool bOriginalLocked = Portal->bLocked;
	const bool bOriginalUsed = Portal->bUsed;
	const TArray<FString> OriginalDiscovered = Island->GetDiscoveredLocationIds();

	TSharedPtr<FJsonObject> OriginalSection;
	Check(Island->WriteSaveSection(OriginalSection), TEXT("world save section writes"));

	// Round trip: mutate a portal, export the section, clear it, re-import.
	Portal->bLocked = true;
	Portal->bUsed = true;
	TSharedPtr<FJsonObject> MutatedSection;
	Check(Island->WriteSaveSection(MutatedSection), TEXT("world save section captures portal state"));
	Portal->bLocked = false;
	Portal->bUsed = false;

	FString Error;
	Check(Island->ReadSaveSection(MutatedSection, Error),
		FString::Printf(TEXT("world save section reads (%s)"), *Error));
	Check(Island->HasPendingWorldState(), TEXT("world save state is queued for the deferred pass"));
	Check(!Portal->IsPortalLocked() && !Portal->bUsed,
		TEXT("world save state is not applied during read"));
	Check(Island->ApplyPendingWorldState(), TEXT("queued world save state applies"));
	Check(Portal->IsPortalLocked() && Portal->bUsed, TEXT("world save round-trip restores portal flags"));
	Check(Island->ApplyPendingWorldState(), TEXT("world save apply is idempotent"));
	Check(Portal->IsPortalLocked() && Portal->bUsed,
		TEXT("re-applying world save state keeps portal flags"));

	// Duplicate, unknown and empty ids must never overwrite live doors. The
	// valid row wins, and W3: the row with no live actor stays queued.
	TSharedPtr<FJsonObject> HostileSection = MakeShared<FJsonObject>();
	HostileSection->SetNumberField(TEXT("version"), 1);
	TArray<TSharedPtr<FJsonValue>> PortalRows;
	{
		TSharedPtr<FJsonObject> First = MakeShared<FJsonObject>();
		First->SetStringField(TEXT("id"), Portal->PortalId);
		First->SetBoolField(TEXT("locked"), false);
		First->SetBoolField(TEXT("used"), false);
		PortalRows.Add(MakeShared<FJsonValueObject>(First));

		TSharedPtr<FJsonObject> Duplicate = MakeShared<FJsonObject>();
		Duplicate->SetStringField(TEXT("id"), Portal->PortalId);
		Duplicate->SetBoolField(TEXT("locked"), true);
		Duplicate->SetBoolField(TEXT("used"), true);
		PortalRows.Add(MakeShared<FJsonValueObject>(Duplicate));

		TSharedPtr<FJsonObject> Unknown = MakeShared<FJsonObject>();
		Unknown->SetStringField(TEXT("id"), TEXT("__missing_portal__"));
		Unknown->SetBoolField(TEXT("locked"), true);
		Unknown->SetBoolField(TEXT("used"), true);
		PortalRows.Add(MakeShared<FJsonValueObject>(Unknown));

		TSharedPtr<FJsonObject> Empty = MakeShared<FJsonObject>();
		Empty->SetStringField(TEXT("id"), FString());
		Empty->SetBoolField(TEXT("locked"), true);
		Empty->SetBoolField(TEXT("used"), true);
		PortalRows.Add(MakeShared<FJsonValueObject>(Empty));
	}
	HostileSection->SetArrayField(TEXT("portals"), PortalRows);

	Portal->bLocked = true;
	Portal->bUsed = true;
	Check(Island->ReadSaveSection(HostileSection, Error),
		FString::Printf(TEXT("world save section accepts duplicate/unknown ids (%s)"), *Error));
	Check(!Island->ApplyPendingWorldState(),
		TEXT("world save state with an unresolved actor id stays queued"));
	Check(Island->HasPendingWorldState(), TEXT("unresolved portal ids keep the queue pending"));
	Check(!Portal->IsPortalLocked() && !Portal->bUsed,
		TEXT("duplicate portal ids keep the first entry"));
	Check(!Island->ApplyPendingWorldState(),
		TEXT("unresolved portal ids retry every pass until resolved"));
	Check(!Portal->IsPortalLocked() && !Portal->bUsed,
		TEXT("resolved portal state is not re-toggled across retries"));
	Island->ExpirePendingWorldState();
	Check(!Island->HasPendingWorldState(), TEXT("expiry drops unresolved portal ids"));

	// A saved portal with no live actor must not fail the load, must not touch
	// the other doors and must keep retrying until the actor (or the wait
	// window, via ExpirePendingWorldState) ends the queue.
	TSharedPtr<FJsonObject> MissingActorSection = MakeShared<FJsonObject>();
	MissingActorSection->SetNumberField(TEXT("version"), 1);
	TArray<TSharedPtr<FJsonValue>> MissingRows;
	{
		TSharedPtr<FJsonObject> Missing = MakeShared<FJsonObject>();
		Missing->SetStringField(TEXT("id"), TEXT("__not_spawned_yet__"));
		Missing->SetBoolField(TEXT("locked"), true);
		Missing->SetBoolField(TEXT("used"), true);
		MissingRows.Add(MakeShared<FJsonValueObject>(Missing));
	}
	MissingActorSection->SetArrayField(TEXT("portals"), MissingRows);
	Check(Island->ReadSaveSection(MissingActorSection, Error),
		FString::Printf(TEXT("world save section accepts an id without a live actor (%s)"), *Error));
	Check(!Island->ApplyPendingWorldState(),
		TEXT("world save state with an unknown actor id stays pending"));
	Check(Island->HasPendingWorldState(), TEXT("unknown portal ids keep the queue pending for retry"));
	Check(!Island->ApplyPendingWorldState(),
		TEXT("unknown portal ids retry while no actor exists"));
	Check(!Portal->IsPortalLocked() && !Portal->bUsed,
		TEXT("unknown portal ids do not touch unrelated doors"));
	Island->ExpirePendingWorldState();
	Check(!Island->HasPendingWorldState(), TEXT("expiry clears the queue for the next probe"));

	// Zone discovery round-trips through the same section. P4-10: the applied
	// restore must UNION with the discoveries the session already made instead
	// of replacing them (same-frame discoveries must survive a load).
	const TArray<FString> PreUnionIds = Island->GetDiscoveredLocationIds();
	TSharedPtr<FJsonObject> DiscoverySection = MakeShared<FJsonObject>();
	DiscoverySection->SetNumberField(TEXT("version"), 1);
	TArray<TSharedPtr<FJsonValue>> DiscoveredRows;
	DiscoveredRows.Add(MakeShared<FJsonValueString>(TEXT("__test_zone_a__")));
	DiscoveredRows.Add(MakeShared<FJsonValueString>(TEXT("__test_zone_b__")));
	DiscoverySection->SetArrayField(TEXT("discovered"), DiscoveredRows);
	Check(Island->ReadSaveSection(DiscoverySection, Error),
		FString::Printf(TEXT("world save section accepts discovered ids (%s)"), *Error));
	Check(Island->ApplyPendingWorldState(), TEXT("world discovered state applies"));
	const TArray<FString> RestoredIds = Island->GetDiscoveredLocationIds();
	Check(RestoredIds.Contains(TEXT("__test_zone_a__")) && RestoredIds.Contains(TEXT("__test_zone_b__")),
		TEXT("world save restores discovered zone ids"));
	bool bUnionKept = true;
	for (const FString& PreUnionId : PreUnionIds)
	{
		if (!RestoredIds.Contains(PreUnionId))
		{
			bUnionKept = false;
		}
	}
	Check(bUnionKept, TEXT("world discovered restore unions with same-frame discoveries"));

	// Restore the live world exactly as it was before the probe.
	if (OriginalSection.IsValid())
	{
		Check(Island->ReadSaveSection(OriginalSection, Error),
			FString::Printf(TEXT("world save snapshot restores (%s)"), *Error));
		Check(Island->ApplyPendingWorldState(), TEXT("world save snapshot applies"));
	}
	Island->RestoreDiscoveredLocationIds(OriginalDiscovered);
	Portal->bLocked = bOriginalLocked;
	Portal->bUsed = bOriginalUsed;
	Check(!Island->HasPendingWorldState(), TEXT("world save state queue is empty after restore"));
}

void UDAPortalTestSubsystem::VerifySaveStateContract()
{
	ADAInteriorPortal* Portal = Portals.Num() > 0 ? Portals[0].Get() : nullptr;
	if (!Portal)
	{
		Check(false, TEXT("portal save-state probe has a portal"));
		return;
	}

	// Mutate and restore the live portal so the probe cannot affect the walk.
	const FString SavedId = Portal->PortalId;
	const bool bSavedLocked = Portal->bLocked;
	const bool bSavedUsed = Portal->bUsed;

	const FDAPortalSaveState Snapshot = Portal->GetSaveState();
	Check(Snapshot.PortalId == SavedId && Snapshot.bLocked == bSavedLocked && Snapshot.bUsed == bSavedUsed,
		TEXT("portal save state mirrors the live portal"));

	FDAPortalSaveState State;
	State.PortalId = SavedId;
	State.bLocked = true;
	State.bUsed = true;

	Portal->bLocked = false;
	Portal->bUsed = false;
	Portal->ApplySaveState(State);
	Check(Portal->IsPortalLocked() && Portal->bUsed, TEXT("portal save state applies to the matching id"));

	FDAPortalSaveState WrongId = State;
	WrongId.PortalId = SavedId + TEXT("_mismatch");
	Portal->bLocked = false;
	Portal->bUsed = false;
	Portal->ApplySaveState(WrongId);
	Check(!Portal->IsPortalLocked() && !Portal->bUsed, TEXT("portal save state ignores a different id"));

	FDAPortalSaveState EmptyId = State;
	EmptyId.PortalId.Reset();
	Portal->bLocked = false;
	Portal->bUsed = false;
	Portal->ApplySaveState(EmptyId);
	Check(!Portal->IsPortalLocked() && !Portal->bUsed, TEXT("portal save state ignores an empty id"));

	Portal->bLocked = bSavedLocked;
	Portal->bUsed = bSavedUsed;
}

void UDAPortalTestSubsystem::BeginEntry()
{
	Stage = 1;
	StageSeconds = 0.f;
	Expected = FVector::ZeroVector;

	if (!Entries.IsValidIndex(EntryIndex))
	{
		Finish();
		return;
	}

	ADAInteriorPortal* Portal = Entries[EntryIndex];
	APawn* Pawn = PlayerPawn.Get();
	if (!Portal || !Pawn)
	{
		Check(false, TEXT("entry pawn and portal are available"));
		++EntryIndex;
		// Do not leave the state machine waiting on a teleport that never began.
		Stage = 0;
		return;
	}

	CurrentPair = Portal->PortalId;
	Pawn->SetActorLocation(Portal->GetActorLocation(), false, nullptr, ETeleportType::TeleportPhysics);
	Expected = ExpectedArrival(Portal);
	// Moving the pawn onto the trigger may dispatch BeginOverlap synchronously,
	// so either the overlap or this explicit call may start the use.
	const bool bAccepted = Portal->bUsed || Portal->TryUse(Pawn);
	Check(bAccepted, FString::Printf(TEXT("%s accepts use"), *Portal->PortalId));
	if (const ADAInteriorPortal* Linked = Portal->FindLinkedPortal())
	{
		Check(Linked->IsOnCooldown(), FString::Printf(TEXT("%s arms the return portal cooldown"), *Portal->PortalId));
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Portal test: entering %s -> %s (%s)"),
		*Portal->PortalId, *Portal->InteriorId, *Expected.ToCompactString());
}

void UDAPortalTestSubsystem::VerifyEntry()
{
	APawn* Pawn = PlayerPawn.Get();
	ADAInteriorPortal* Portal = Entries.IsValidIndex(EntryIndex) ? Entries[EntryIndex].Get() : nullptr;
	if (!Pawn || !Portal)
	{
		Check(false, TEXT("entry arrival has a pawn and portal"));
		++EntryIndex;
		Stage = 0;
		return;
	}

	const FVector Actual = Pawn->GetActorLocation();
	const float Distance2D = FVector::Dist2D(Actual, Expected);
	Check(Distance2D <= PortalTestMoveTolerance,
		FString::Printf(TEXT("%s arrival X/Y within %.0f cm (actual %.0f cm)"),
			*Portal->PortalId, PortalTestMoveTolerance, Distance2D));
	Check(FMath::Abs(Actual.Z - Expected.Z) <= PortalTestZTolerance,
		FString::Printf(TEXT("%s arrival Z within %.0f cm (actual %.0f cm)"),
			*Portal->PortalId, PortalTestZTolerance, FMath::Abs(Actual.Z - Expected.Z)));
	Check(IsInteriorSide(Actual), FString::Printf(TEXT("%s places the player inside the interior"), *Portal->PortalId));
	Check(Portal->bUsed, FString::Printf(TEXT("%s reports first use"), *Portal->PortalId));

	if (!bScreenshotTaken && EntryIndex == 0)
	{
		bScreenshotTaken = true;
		FScreenshotRequest::RequestScreenshot(TEXT("DAPortalInterior.png"), false, false);
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Portal test: captured interior screenshot at %s"),
			*Actual.ToCompactString());
		Stage = 2;
		StageSeconds = 0.f;
		return;
	}

	++EntryIndex;
	Stage = 0;
}

void UDAPortalTestSubsystem::BeginReturn()
{
	Stage = 3;
	StageSeconds = 0.f;
	Expected = FVector::ZeroVector;

	ADAInteriorPortal* Entry = Entries.IsValidIndex(0) ? Entries[0].Get() : nullptr;
	APawn* Pawn = PlayerPawn.Get();
	ADAInteriorPortal* ReturnPortal = Entry ? Entry->FindLinkedPortal() : nullptr;
	if (!ReturnPortal || !Pawn)
	{
		Check(false, TEXT("classroom return portal is available"));
		Finish();
		return;
	}

	Pawn->SetActorLocation(ReturnPortal->GetActorLocation(), false, nullptr, ETeleportType::TeleportPhysics);
	Expected = ExpectedArrival(ReturnPortal);
	const bool bAccepted = ReturnPortal->bUsed || ReturnPortal->TryUse(Pawn);
	Check(bAccepted, FString::Printf(TEXT("%s accepts use after cooldown"), *ReturnPortal->PortalId));
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Portal test: returning %s -> %s"),
		*ReturnPortal->PortalId, *Expected.ToCompactString());
}

void UDAPortalTestSubsystem::VerifyReturn()
{
	APawn* Pawn = PlayerPawn.Get();
	ADAInteriorPortal* Entry = Entries.IsValidIndex(0) ? Entries[0].Get() : nullptr;
	ADAInteriorPortal* ReturnPortal = Entry ? Entry->FindLinkedPortal() : nullptr;
	if (!Pawn || !ReturnPortal)
	{
		Check(false, TEXT("return arrival has a pawn and portal"));
		Finish();
		return;
	}

	const FVector Actual = Pawn->GetActorLocation();
	const float Distance2D = FVector::Dist2D(Actual, Expected);
	Check(Distance2D <= PortalTestMoveTolerance,
		FString::Printf(TEXT("%s return X/Y within %.0f cm (actual %.0f cm)"),
			*ReturnPortal->PortalId, PortalTestMoveTolerance, Distance2D));
	Check(FMath::Abs(Actual.Z - Expected.Z) <= PortalTestZTolerance,
		FString::Printf(TEXT("%s return Z within %.0f cm (actual %.0f cm)"),
			*ReturnPortal->PortalId, PortalTestZTolerance, FMath::Abs(Actual.Z - Expected.Z)));
	Check(!IsInteriorSide(Actual), FString::Printf(TEXT("%s returns the player outside"), *ReturnPortal->PortalId));
	Check(ReturnPortal->bUsed, FString::Printf(TEXT("%s reports first use"), *ReturnPortal->PortalId));

	++EntryIndex;
	Stage = 0;
	StageSeconds = 0.f;
	if (EntryIndex >= Entries.Num())
	{
		Finish();
	}
}

void UDAPortalTestSubsystem::Finish()
{
	if (bFinished)
	{
		return;
	}
	bFinished = true;

	UE_LOG(LogDuelAcademyIsland, Log,
		TEXT("Portal test: %d passed, %d failed.%s"),
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

bool UDAPortalTestSubsystem::Tick(float DeltaTime)
{
	if (bFinished)
	{
		return false;
	}

	WaitSeconds += DeltaTime;
	if (WaitSeconds > PortalTestTimeout)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Portal test: timed out after %.0f seconds at stage %d."),
			PortalTestTimeout, Stage);
		Finish();
		return false;
	}

	UGameInstance* GameInstance = GetGameInstance();
	UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
	if (!World || !World->HasBegunPlay())
	{
		return true;
	}

	APlayerController* PC = World->GetFirstPlayerController();
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return true;
	}
	PlayerPawn = Pawn;

	if (!bCollected)
	{
		CollectPortals(World);
		if (Entries.Num() == 0)
		{
			Check(false, TEXT("at least one entry portal exists"));
			Finish();
			return false;
		}
	}

	StageSeconds += DeltaTime;
	switch (Stage)
	{
	case 0:
		BeginEntry();
		break;
	case 1:
		if (StageSeconds >= PortalTestWaitEntry)
		{
			VerifyEntry();
		}
		break;
	case 2:
		if (StageSeconds >= PortalTestWaitReturn)
		{
			BeginReturn();
		}
		break;
	case 3:
		if (StageSeconds >= PortalTestWaitEntry)
		{
			VerifyReturn();
		}
		break;
	default:
		Finish();
		break;
	}

	return !bFinished;
}
