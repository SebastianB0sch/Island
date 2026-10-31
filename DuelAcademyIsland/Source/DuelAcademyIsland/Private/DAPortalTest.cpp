// Duel Academy Island - PIE portal entry/exit self-test implementation.

#include "DAPortalTest.h"

#include "DAInteriorPortal.h"
#include "DuelAcademyIsland.h"
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
	for (const ADAInteriorPortal* Portal : Portals)
	{
		Check(!Portal->PortalId.IsEmpty(), TEXT("portal has a non-empty id"));
		Check(!Ids.Contains(Portal->PortalId), FString::Printf(TEXT("portal id unique: %s"), *Portal->PortalId));
		Ids.Add(Portal->PortalId);
		Check(!Portal->InteriorId.IsEmpty(), FString::Printf(TEXT("portal %s names an interior"), *Portal->PortalId));
		Check(!Portal->TargetLocation.IsNearlyZero(), FString::Printf(TEXT("portal %s has a destination"), *Portal->PortalId));
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
		return;
	}

	CurrentPair = Portal->PortalId;
	Pawn->SetActorLocation(Portal->GetActorLocation(), false, nullptr, ETeleportType::TeleportPhysics);
	Expected = ExpectedArrival(Portal);
	// Moving the pawn onto the trigger may dispatch BeginOverlap synchronously,
	// so either the overlap or this explicit call may start the use.
	const bool bAccepted = Portal->bUsed || Portal->TryUse(Pawn);
	Check(bAccepted, FString::Printf(TEXT("%s accepts use"), *Portal->PortalId));
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
