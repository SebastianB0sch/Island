// Duel Academy Island - permanent/temporary titles, dorm outcomes and the
// Dropout Boy fail state.
//
// Title thresholds come from Content/Data/Profile/titles.json. The hardcoded
// defaults in the cpp are a deliberately conservative stub until A01 freezes
// the canon table; the JSON file is the authoritative source at runtime.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DATypes.h"
#include "DATitleSystem.generated.h"

class UDAProfileSubsystem;

/** One title, permanent or temporary. Order is the prestige ordering (higher = better). */
USTRUCT(BlueprintType)
struct DUELACADEMYISLAND_API FDATitleDefinition
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	FString Id;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	FString Name;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	FString Description;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 Order = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	bool bPermanent = true;

	/** Dropout Boy and any other failure title. Never selected by normal evaluation. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	bool bFailState = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 MinWinsTotal = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 MinDuelsTotal = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 MinTimedClears = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 MinWrittenCorrect = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 MinCardsOwned = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 MinStoryEvents = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	int32 MinDP = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	bool bRequiresExamPassed = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	bool bRequiresKingOfGames = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	bool bRequiresDorm = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	EDADorm RequiredDorm = EDADorm::Slifer;

	/** Optional extra flag required by this title. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Title")
	FString RequiredFlag;
};

UENUM(BlueprintType)
enum class EDAExamOutcomeKind : uint8
{
	Passed  UMETA(DisplayName = "Passed"),
	Failed  UMETA(DisplayName = "Failed"),
	Dropout UMETA(DisplayName = "Dropout Boy")
};

/** Result of applying one monthly exam. */
USTRUCT(BlueprintType)
struct DUELACADEMYISLAND_API FDAExamOutcome
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	EDAExamOutcomeKind Outcome = EDAExamOutcomeKind::Passed;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	int32 Score = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	int32 PassMark = 300;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	bool bPromoted = false;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	bool bDemoted = false;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	FString PreviousTitle;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	FString NewTitle;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	EDADorm PreviousDorm = EDADorm::Slifer;

	UPROPERTY(BlueprintReadOnly, Category = "Duel Academy|Exam")
	EDADorm NewDorm = EDADorm::Slifer;
};

UCLASS()
class DUELACADEMYISLAND_API UDATitleSystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	/** Loads Content/Data/Profile/titles.json. Falls back to hardcoded defaults. */
	bool LoadDefinitions();

	/** Restores the conservative hardcoded table (used if the JSON is missing). */
	void UseDefaultDefinitions();

	const TArray<FDATitleDefinition>& GetDefinitions() const { return Definitions; }

	/** Permanent definitions sorted from lowest to highest prestige. */
	TArray<FDATitleDefinition> GetPermanentTitles() const;

	TArray<FDATitleDefinition> GetTemporaryTitles() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Title")
	bool GetTitleDefinition(const FString& TitleIdOrName, FDATitleDefinition& OutDefinition) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Title")
	FString GetDefaultTitle() const;

	/** Best eligible title for the profile: active temporary title, Dropout Boy, or best permanent. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	FString EvaluateTitle(const UDAProfileSubsystem* Profile);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	FString ApplyBestTitle(UDAProfileSubsystem* Profile);

	/** Debug/event override. Accepts id or display name. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	bool ForceTitle(UDAProfileSubsystem* Profile, const FString& TitleIdOrName, bool bAllowUnknown = false);

	/** Grants a temporary story/event title and makes it active. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	bool GrantTemporaryTitle(UDAProfileSubsystem* Profile, const FString& TitleIdOrName, int32 DaysRemaining);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	void ClearTemporaryTitle(UDAProfileSubsystem* Profile);

	// ---------------------------------------------------------------- dorm outcomes
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Title")
	bool CanPromoteDorm(const UDAProfileSubsystem* Profile, int32 Score) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Title")
	bool GetPromotionTarget(EDADorm CurrentDorm, EDADorm& OutDorm) const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	bool PromoteDorm(UDAProfileSubsystem* Profile);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	bool DemoteDorm(UDAProfileSubsystem* Profile);

	/** Pass -> maybe promote; fail -> demote and Dropout Boy. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	FDAExamOutcome ApplyExamOutcome(UDAProfileSubsystem* Profile, int32 Score, int32 PassMark = 300, bool bPromotionEligible = true);

	/** Recovery duel against Fonda Fontaine. Winning clears Dropout Boy. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Title")
	bool RecoverFromDropout(UDAProfileSubsystem* Profile, bool bWonRecoveryDuel);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Title")
	int32 GetPromotionScore() const { return PromotionScore; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Title")
	FString GetDropoutFlag() const { return DropoutFlag; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Title")
	FString GetRecoveryOpponentId() const { return RecoveryOpponentId; }

private:
	void EnsureDefinitionsLoaded();
	bool IsEligible(const UDAProfileSubsystem* Profile, const FDATitleDefinition& Definition) const;
	const FDATitleDefinition* FindDefinition(const FString& TitleIdOrName) const;
	const FDATitleDefinition* FindById(const FString& Id) const;
	FString GetDropoutTitleName() const;

	UPROPERTY()
	TArray<FDATitleDefinition> Definitions;

	UPROPERTY()
	FString DefaultTitleId = TEXT("apprentice_duelist");

	UPROPERTY()
	int32 PromotionScore = 400;

	UPROPERTY()
	bool bDemoteOnFail = true;

	UPROPERTY()
	FString DropoutTitleId = TEXT("dropout_boy");

	UPROPERTY()
	FString DropoutFlag = TEXT("dropout_boy");

	UPROPERTY()
	FString RecoveryOpponentId = TEXT("fonda_fontaine");

	bool bDefinitionsLoaded = false;
};
