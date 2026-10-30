// Duel Academy Island - title and dorm outcome implementation.

#include "DATitleSystem.h"

#include "DAProfileSubsystem.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	int32 DormRank(EDADorm Dorm)
	{
		switch (Dorm)
		{
		case EDADorm::Ra:      return 1;
		case EDADorm::Obelisk: return 2;
		case EDADorm::White:   return 3;
		case EDADorm::Slifer:
		default:               return 0;
		}
	}

	FString ReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Default = FString())
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Default;
	}

	int32 ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool ReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool Default = false)
	{
		bool bValue = Default;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	FDATitleDefinition MakeTitle(const TCHAR* Id, const TCHAR* Name, int32 Order, bool bPermanent = true)
	{
		FDATitleDefinition Definition;
		Definition.Id = Id;
		Definition.Name = Name;
		Definition.Order = Order;
		Definition.bPermanent = bPermanent;
		return Definition;
	}
}

// ------------------------------------------------------------------------ lifecycle

void UDATitleSystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	LoadDefinitions();
}

void UDATitleSystem::UseDefaultDefinitions()
{
	TArray<FDATitleDefinition> Defaults;

	FDATitleDefinition Dropout = MakeTitle(TEXT("dropout_boy"), TEXT("Dropout Boy"), 0);
	Dropout.Description = TEXT("Failed an exam. Win the recovery duel to return to the academy.");
	Dropout.bFailState = true;
	Defaults.Add(Dropout);

	FDATitleDefinition Apprentice = MakeTitle(TEXT("apprentice_duelist"), TEXT("Apprentice Duelist"), 10);
	Apprentice.Description = TEXT("A new student finding their feet at Duel Academy.");
	Defaults.Add(Apprentice);

	FDATitleDefinition Rookie = MakeTitle(TEXT("rookie_duelist"), TEXT("Rookie Duelist"), 20);
	Rookie.MinWinsTotal = 3;
	Rookie.MinDuelsTotal = 3;
	Defaults.Add(Rookie);

	FDATitleDefinition Intermediate = MakeTitle(TEXT("intermediate_duelist"), TEXT("Intermediate Duelist"), 30);
	Intermediate.MinWinsTotal = 8;
	Intermediate.MinDuelsTotal = 10;
	Intermediate.MinTimedClears = 1;
	Defaults.Add(Intermediate);

	FDATitleDefinition Advanced = MakeTitle(TEXT("advanced_duelist"), TEXT("Advanced Duelist"), 40);
	Advanced.MinWinsTotal = 15;
	Advanced.MinDuelsTotal = 20;
	Advanced.MinTimedClears = 3;
	Defaults.Add(Advanced);

	FDATitleDefinition Expert = MakeTitle(TEXT("expert_duelist"), TEXT("Expert Duelist"), 50);
	Expert.MinWinsTotal = 25;
	Expert.MinDuelsTotal = 32;
	Expert.MinTimedClears = 5;
	Expert.MinWrittenCorrect = 20;
	Defaults.Add(Expert);

	FDATitleDefinition Veteran = MakeTitle(TEXT("veteran_duelist"), TEXT("Veteran Duelist"), 60);
	Veteran.MinWinsTotal = 40;
	Veteran.MinDuelsTotal = 50;
	Veteran.MinTimedClears = 10;
	Veteran.MinWrittenCorrect = 40;
	Veteran.MinCardsOwned = 100;
	Defaults.Add(Veteran);

	FDATitleDefinition Elite = MakeTitle(TEXT("elite_duelist"), TEXT("Elite Duelist"), 70);
	Elite.MinWinsTotal = 60;
	Elite.MinDuelsTotal = 75;
	Elite.MinTimedClears = 15;
	Elite.MinWrittenCorrect = 60;
	Elite.MinCardsOwned = 250;
	Defaults.Add(Elite);

	FDATitleDefinition Champion = MakeTitle(TEXT("champion_duelist"), TEXT("Champion Duelist"), 80);
	Champion.MinWinsTotal = 80;
	Champion.MinDuelsTotal = 100;
	Champion.MinTimedClears = 25;
	Champion.MinWrittenCorrect = 80;
	Champion.MinCardsOwned = 400;
	Defaults.Add(Champion);

	FDATitleDefinition AcademyChampion = MakeTitle(TEXT("duel_academy_champion"), TEXT("Duel Academy Champion"), 90);
	AcademyChampion.MinWinsTotal = 100;
	AcademyChampion.MinDuelsTotal = 125;
	AcademyChampion.MinTimedClears = 40;
	AcademyChampion.MinWrittenCorrect = 100;
	AcademyChampion.MinCardsOwned = 600;
	AcademyChampion.bRequiresExamPassed = true;
	Defaults.Add(AcademyChampion);

	FDATitleDefinition DuelKing = MakeTitle(TEXT("duel_king"), TEXT("Duel King"), 100);
	DuelKing.MinWinsTotal = 150;
	DuelKing.MinDuelsTotal = 180;
	DuelKing.MinTimedClears = 60;
	DuelKing.MinWrittenCorrect = 140;
	DuelKing.MinCardsOwned = 800;
	DuelKing.MinStoryEvents = 20;
	DuelKing.bRequiresExamPassed = true;
	Defaults.Add(DuelKing);

	FDATitleDefinition KingOfGames = MakeTitle(TEXT("king_of_games"), TEXT("King of Games"), 110);
	KingOfGames.MinWinsTotal = 200;
	KingOfGames.MinDuelsTotal = 240;
	KingOfGames.MinTimedClears = 80;
	KingOfGames.MinWrittenCorrect = 180;
	KingOfGames.MinCardsOwned = 1000;
	KingOfGames.MinStoryEvents = 33;
	KingOfGames.bRequiresExamPassed = true;
	KingOfGames.bRequiresKingOfGames = true;
	Defaults.Add(KingOfGames);

	FDATitleDefinition Novice = MakeTitle(TEXT("novice_duelist"), TEXT("Novice Duelist"), 5, false);
	Novice.Description = TEXT("Temporary tutorial title.");
	Defaults.Add(Novice);

	FDATitleDefinition Occult = MakeTitle(TEXT("occult_duelist"), TEXT("Occult Duelist"), 15, false);
	Occult.Description = TEXT("Temporary title from the abandoned dorm events.");
	Defaults.Add(Occult);

	FDATitleDefinition Shadow = MakeTitle(TEXT("shadow_duelist"), TEXT("Shadow Duelist"), 25, false);
	Shadow.Description = TEXT("Temporary title from a shadow game.");
	Defaults.Add(Shadow);

	FDATitleDefinition Society = MakeTitle(TEXT("society_duelist"), TEXT("Society Duelist"), 35, false);
	Society.Description = TEXT("Temporary title while aligned with the Society of Light.");
	Defaults.Add(Society);

	Definitions = MoveTemp(Defaults);
	Definitions.Sort([](const FDATitleDefinition& A, const FDATitleDefinition& B)
	{
		return A.Order < B.Order;
	});
	DefaultTitleId = TEXT("apprentice_duelist");
	PromotionScore = 400;
	bDemoteOnFail = true;
	DropoutTitleId = TEXT("dropout_boy");
	DropoutFlag = TEXT("dropout_boy");
	RecoveryOpponentId = TEXT("fonda_fontaine");
	bDefinitionsLoaded = true;
}

bool UDATitleSystem::LoadDefinitions()
{
	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Profile/titles.json"));
	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *Path))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Title data not found at %s; using defaults."), *Path);
		UseDefaultDefinitions();
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Title data at %s could not be parsed; using defaults."), *Path);
		UseDefaultDefinitions();
		return false;
	}

	const FString LoadedDefault = ReadString(Root, TEXT("default_title"), TEXT("apprentice_duelist"));
	DefaultTitleId = LoadedDefault;

	const TSharedPtr<FJsonObject>* DormRules = nullptr;
	if (Root->TryGetObjectField(TEXT("dorm_rules"), DormRules) && DormRules && DormRules->IsValid())
	{
		PromotionScore = FMath::Max(0, ReadInt(*DormRules, TEXT("promotion_score"), 400));
		bDemoteOnFail = ReadBool(*DormRules, TEXT("demote_on_fail"), true);
		DropoutTitleId = ReadString(*DormRules, TEXT("dropout_title"), TEXT("dropout_boy"));
		DropoutFlag = ReadString(*DormRules, TEXT("dropout_flag"), TEXT("dropout_boy"));
		RecoveryOpponentId = ReadString(*DormRules, TEXT("recovery_opponent"), TEXT("fonda_fontaine"));
	}

	const TArray<TSharedPtr<FJsonValue>>* TitleArray = nullptr;
	if (!Root->TryGetArrayField(TEXT("titles"), TitleArray) || !TitleArray)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Title data has no 'titles' array; using defaults."));
		UseDefaultDefinitions();
		return false;
	}

	TArray<FDATitleDefinition> Loaded;
	for (const TSharedPtr<FJsonValue>& Value : *TitleArray)
	{
		const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			continue;
		}
		FDATitleDefinition Definition;
		Definition.Id = ReadString(Object, TEXT("id"));
		if (Definition.Id.IsEmpty())
		{
			continue;
		}
		Definition.Name = ReadString(Object, TEXT("name"), Definition.Id);
		Definition.Description = ReadString(Object, TEXT("description"));
		Definition.Order = ReadInt(Object, TEXT("order"));
		Definition.bPermanent = ReadBool(Object, TEXT("permanent"), true);
		Definition.bFailState = ReadBool(Object, TEXT("fail_state"), false);
		Definition.MinWinsTotal = FMath::Max(0, ReadInt(Object, TEXT("min_wins_total")));
		Definition.MinDuelsTotal = FMath::Max(0, ReadInt(Object, TEXT("min_duels_total")));
		Definition.MinTimedClears = FMath::Max(0, ReadInt(Object, TEXT("min_timed_clears")));
		Definition.MinWrittenCorrect = FMath::Max(0, ReadInt(Object, TEXT("min_written_correct")));
		Definition.MinCardsOwned = FMath::Max(0, ReadInt(Object, TEXT("min_cards_owned")));
		Definition.MinStoryEvents = FMath::Max(0, ReadInt(Object, TEXT("min_story_events")));
		Definition.MinDP = FMath::Max(0, ReadInt(Object, TEXT("min_dp")));
		Definition.bRequiresExamPassed = ReadBool(Object, TEXT("requires_exam_passed"), false);
		Definition.bRequiresKingOfGames = ReadBool(Object, TEXT("requires_king_of_games"), false);
		Definition.bRequiresDorm = ReadBool(Object, TEXT("requires_dorm"), false);
		Definition.RequiredDorm = DuelAcademyProfile::ParseDorm(ReadString(Object, TEXT("required_dorm"), TEXT("Slifer")));
		Definition.RequiredFlag = ReadString(Object, TEXT("required_flag"));
		Loaded.Add(MoveTemp(Definition));
	}

	if (Loaded.Num() == 0)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Title data contains no valid titles; using defaults."));
		UseDefaultDefinitions();
		return false;
	}

	Loaded.Sort([](const FDATitleDefinition& A, const FDATitleDefinition& B)
	{
		return A.Order < B.Order;
	});
	Definitions = MoveTemp(Loaded);
	bDefinitionsLoaded = true;

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded %d title definitions."), Definitions.Num());
	return true;
}

void UDATitleSystem::EnsureDefinitionsLoaded()
{
	if (!bDefinitionsLoaded || Definitions.Num() == 0)
	{
		LoadDefinitions();
	}
}

const FDATitleDefinition* UDATitleSystem::FindById(const FString& Id) const
{
	for (const FDATitleDefinition& Definition : Definitions)
	{
		if (Definition.Id.Equals(Id, ESearchCase::IgnoreCase))
		{
			return &Definition;
		}
	}
	return nullptr;
}

const FDATitleDefinition* UDATitleSystem::FindDefinition(const FString& TitleIdOrName) const
{
	for (const FDATitleDefinition& Definition : Definitions)
	{
		if (Definition.Id.Equals(TitleIdOrName, ESearchCase::IgnoreCase)
			|| Definition.Name.Equals(TitleIdOrName, ESearchCase::IgnoreCase))
		{
			return &Definition;
		}
	}
	return nullptr;
}

TArray<FDATitleDefinition> UDATitleSystem::GetPermanentTitles() const
{
	TArray<FDATitleDefinition> Out;
	for (const FDATitleDefinition& Definition : Definitions)
	{
		if (Definition.bPermanent)
		{
			Out.Add(Definition);
		}
	}
	return Out;
}

TArray<FDATitleDefinition> UDATitleSystem::GetTemporaryTitles() const
{
	TArray<FDATitleDefinition> Out;
	for (const FDATitleDefinition& Definition : Definitions)
	{
		if (!Definition.bPermanent)
		{
			Out.Add(Definition);
		}
	}
	return Out;
}

bool UDATitleSystem::GetTitleDefinition(const FString& TitleIdOrName, FDATitleDefinition& OutDefinition) const
{
	if (const FDATitleDefinition* Definition = FindDefinition(TitleIdOrName))
	{
		OutDefinition = *Definition;
		return true;
	}
	return false;
}

FString UDATitleSystem::GetDefaultTitle() const
{
	if (const FDATitleDefinition* Definition = FindById(DefaultTitleId))
	{
		return Definition->Name;
	}
	return TEXT("Apprentice Duelist");
}

FString UDATitleSystem::GetDropoutTitleName() const
{
	if (const FDATitleDefinition* Definition = FindById(DropoutTitleId))
	{
		return Definition->Name;
	}
	return TEXT("Dropout Boy");
}

// ------------------------------------------------------------------------ evaluation

FString UDATitleSystem::EvaluateTitle(const UDAProfileSubsystem* Profile)
{
	EnsureDefinitionsLoaded();
	if (!Profile)
	{
		return GetDefaultTitle();
	}

	const FString Temporary = Profile->GetTemporaryTitle();
	if (!Temporary.IsEmpty() && Profile->GetTemporaryTitleDaysRemaining() > 0)
	{
		if (const FDATitleDefinition* Definition = FindDefinition(Temporary))
		{
			return Definition->Name;
		}
		return Temporary;
	}

	if (Profile->GetFlag(DropoutFlag) || Profile->GetFlag(TEXT("dropout")))
	{
		return GetDropoutTitleName();
	}

	const FDATitleDefinition* Best = nullptr;
	for (const FDATitleDefinition& Definition : Definitions)
	{
		if (!Definition.bPermanent || Definition.bFailState)
		{
			continue;
		}
		if (!IsEligible(Profile, Definition))
		{
			continue;
		}
		if (!Best || Definition.Order > Best->Order)
		{
			Best = &Definition;
		}
	}
	return Best ? Best->Name : GetDefaultTitle();
}

bool UDATitleSystem::IsEligible(const UDAProfileSubsystem* Profile, const FDATitleDefinition& Definition) const
{
	if (!Profile || Definition.bFailState)
	{
		return false;
	}
	if (Profile->GetCounter(TEXT("wins_total")) < Definition.MinWinsTotal)
	{
		return false;
	}
	if (Profile->GetCounter(TEXT("duels_total")) < Definition.MinDuelsTotal)
	{
		return false;
	}
	if (Profile->GetCounter(TEXT("timed_clears")) < Definition.MinTimedClears)
	{
		return false;
	}
	if (Profile->GetCounter(TEXT("written_correct")) < Definition.MinWrittenCorrect)
	{
		return false;
	}
	if (Profile->GetCounter(TEXT("story_events_cleared")) < Definition.MinStoryEvents)
	{
		return false;
	}
	if (Definition.MinCardsOwned > 0 && Profile->GetDistinctCardsOwned() < Definition.MinCardsOwned)
	{
		return false;
	}
	if (Profile->GetDP() < Definition.MinDP)
	{
		return false;
	}
	if (Definition.bRequiresExamPassed
		&& Profile->GetCounter(TEXT("exams_passed")) <= 0
		&& !Profile->GetFlag(TEXT("exam_passed")))
	{
		return false;
	}
	if (Definition.bRequiresKingOfGames && !Profile->GetFlag(TEXT("king_of_games")))
	{
		return false;
	}
	if (!Definition.RequiredFlag.IsEmpty() && !Profile->GetFlag(Definition.RequiredFlag))
	{
		return false;
	}
	if (Definition.bRequiresDorm && DormRank(Profile->GetDorm()) < DormRank(Definition.RequiredDorm))
	{
		return false;
	}
	return true;
}

FString UDATitleSystem::ApplyBestTitle(UDAProfileSubsystem* Profile)
{
	if (!Profile)
	{
		return FString();
	}
	const FString Best = EvaluateTitle(Profile);
	Profile->SetTitle(Best);
	return Best;
}

bool UDATitleSystem::ForceTitle(UDAProfileSubsystem* Profile, const FString& TitleIdOrName, bool bAllowUnknown)
{
	EnsureDefinitionsLoaded();
	if (!Profile)
	{
		return false;
	}

	if (const FDATitleDefinition* Definition = FindDefinition(TitleIdOrName))
	{
		Profile->ClearTemporaryTitle();
		Profile->SetTitle(Definition->Name);
		return true;
	}

	if (bAllowUnknown && !TitleIdOrName.TrimStartAndEnd().IsEmpty())
	{
		Profile->ClearTemporaryTitle();
		Profile->SetTitle(TitleIdOrName);
		return true;
	}
	return false;
}

bool UDATitleSystem::GrantTemporaryTitle(UDAProfileSubsystem* Profile, const FString& TitleIdOrName, int32 DaysRemaining)
{
	EnsureDefinitionsLoaded();
	if (!Profile || DaysRemaining <= 0)
	{
		return false;
	}
	if (const FDATitleDefinition* Definition = FindDefinition(TitleIdOrName))
	{
		Profile->SetTemporaryTitle(Definition->Name, DaysRemaining);
		return true;
	}
	return false;
}

void UDATitleSystem::ClearTemporaryTitle(UDAProfileSubsystem* Profile)
{
	if (!Profile)
	{
		return;
	}
	Profile->ClearTemporaryTitle();
	ApplyBestTitle(Profile);
}

// ------------------------------------------------------------------------ dorm outcomes

bool UDATitleSystem::CanPromoteDorm(const UDAProfileSubsystem* Profile, int32 Score) const
{
	if (!Profile || Score < PromotionScore)
	{
		return false;
	}
	EDADorm Target = EDADorm::Slifer;
	return GetPromotionTarget(Profile->GetDorm(), Target);
}

bool UDATitleSystem::GetPromotionTarget(EDADorm CurrentDorm, EDADorm& OutDorm) const
{
	switch (CurrentDorm)
	{
	case EDADorm::Slifer:
		OutDorm = EDADorm::Ra;
		return true;
	case EDADorm::Ra:
		OutDorm = EDADorm::Obelisk;
		return true;
	case EDADorm::Obelisk:
	case EDADorm::White:
	default:
		OutDorm = CurrentDorm;
		return false;
	}
}

bool UDATitleSystem::PromoteDorm(UDAProfileSubsystem* Profile)
{
	if (!Profile)
	{
		return false;
	}
	EDADorm Target = Profile->GetDorm();
	if (!GetPromotionTarget(Profile->GetDorm(), Target) || Target == Profile->GetDorm())
	{
		return false;
	}
	Profile->SetDorm(Target);
	return true;
}

bool UDATitleSystem::DemoteDorm(UDAProfileSubsystem* Profile)
{
	if (!Profile)
	{
		return false;
	}
	switch (Profile->GetDorm())
	{
	case EDADorm::Obelisk:
		Profile->SetDorm(EDADorm::Ra);
		return true;
	case EDADorm::Ra:
		Profile->SetDorm(EDADorm::Slifer);
		return true;
	case EDADorm::White:
		Profile->SetDorm(EDADorm::Obelisk);
		return true;
	case EDADorm::Slifer:
	default:
		return false;
	}
}

FDAExamOutcome UDATitleSystem::ApplyExamOutcome(UDAProfileSubsystem* Profile, int32 Score, int32 PassMark, bool bPromotionEligible)
{
	FDAExamOutcome Result;
	if (!Profile)
	{
		Result.Outcome = EDAExamOutcomeKind::Failed;
		return Result;
	}

	EnsureDefinitionsLoaded();
	Result.Score = Score;
	Result.PassMark = PassMark;
	Result.PreviousTitle = Profile->GetTitle();
	Result.PreviousDorm = Profile->GetDorm();

	if (Score >= PassMark)
	{
		Result.Outcome = EDAExamOutcomeKind::Passed;
		Profile->IncrementCounter(TEXT("exams_passed"), 1);
		Profile->SetFlag(TEXT("exam_passed"), true);
		Profile->SetFlag(TEXT("last_exam_passed"), true);
		Profile->SetFlag(TEXT("last_exam_failed"), false);
		Profile->SetFlag(DropoutFlag, false);
		Profile->SetFlag(TEXT("dropout"), false);

		if (bPromotionEligible && Score >= PromotionScore)
		{
			Result.bPromoted = PromoteDorm(Profile);
		}
	}
	else
	{
		Result.Outcome = EDAExamOutcomeKind::Dropout;
		Profile->IncrementCounter(TEXT("exams_failed"), 1);
		Profile->SetFlag(TEXT("last_exam_failed"), true);
		Profile->SetFlag(TEXT("last_exam_passed"), false);
		Profile->SetFlag(DropoutFlag, true);
		Profile->SetFlag(TEXT("dropout"), true);
		Profile->SetTitle(GetDropoutTitleName());
		if (bDemoteOnFail)
		{
			Result.bDemoted = DemoteDorm(Profile);
		}
	}

	Result.NewTitle = ApplyBestTitle(Profile);
	Result.NewDorm = Profile->GetDorm();
	return Result;
}

bool UDATitleSystem::RecoverFromDropout(UDAProfileSubsystem* Profile, bool bWonRecoveryDuel)
{
	if (!Profile)
	{
		return false;
	}
	EnsureDefinitionsLoaded();

	if (!bWonRecoveryDuel)
	{
		Profile->SetFlag(DropoutFlag, true);
		Profile->SetFlag(TEXT("dropout"), true);
		ApplyBestTitle(Profile);
		return false;
	}

	Profile->SetFlag(DropoutFlag, false);
	Profile->SetFlag(TEXT("dropout"), false);
	Profile->SetFlag(TEXT("dropout_recovered"), true);
	Profile->IncrementCounter(TEXT("dropout_recoveries"), 1);
	ApplyBestTitle(Profile);
	return true;
}
