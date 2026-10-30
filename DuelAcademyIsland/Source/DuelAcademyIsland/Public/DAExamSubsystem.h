// Duel Academy Island - monthly exam lifecycle and scoring.
//
// Written -> timed puzzle -> practical, scored out of 500. This subsystem owns
// the lifecycle and the result payload only; A09 draws the screens, A04 emits
// practical objective events, and A02 applies title/dorm outcomes.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAExamSubsystem.generated.h"

UENUM(BlueprintType)
enum class EDAExamPhase : uint8
{
	None,
	Written,
	WrittenDone,
	Timed,
	TimedDone,
	Practical,
	PracticalDone,
	Finished
};

USTRUCT(BlueprintType)
struct FDAExamQuestion
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Topic;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 Difficulty = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Text;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	TArray<FString> Options;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 AnswerIndex = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Explanation;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Confidence;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Source;
};

USTRUCT(BlueprintType)
struct FDAExamPracticalObjective
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Label;

	/** Engine event key, e.g. monster_destroyed_by_battle. */
	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Event;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 Target = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 Points = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	bool bRepeatable = true;
};

USTRUCT(BlueprintType)
struct FDAExamPracticalProgress
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString ObjectiveId;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Label;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 Progress = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 Target = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 AwardedPoints = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	bool bComplete = false;
};

USTRUCT(BlueprintType)
struct FDAGradeBand
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 MinPoints = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Grade;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Label;
};

/** Result payload for A02 (title/dorm/DP) and A09 (breakdown). */
USTRUCT(BlueprintType)
struct FDAExamResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 MonthIndex = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 WrittenCorrect = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 WrittenPoints = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	bool bTimedSolved = false;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 TimedPoints = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 PracticalPoints = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	int32 TotalPoints = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	bool bPassed = false;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString Grade;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString TitleOutcome;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	FString DormOutcome;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	TArray<FString> CompletedObjectives;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	TArray<FString> FailedObjectives;

	UPROPERTY(BlueprintReadOnly, Category = "Exam")
	TArray<FString> Flags;
};

/**
 * Exam lifecycle:
 *   StartExam -> Written -> FinishWritten -> BeginTimed -> SubmitTimedResult
 *   -> BeginPractical -> RecordPracticalEvent* -> FinishPractical -> FinishExam.
 *
 * All selection is deterministic from (MonthIndex, Seed). Data lives in
 * Content/Data/Exams/questions.json, practicals.json and scoring.json.
 */
UCLASS()
class DUELACADEMYISLAND_API UDAExamSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	bool Reload(FString& OutError);

	/** Starts the written section for the given month (1-12). */
	bool StartExam(int32 MonthIndex, int32 Seed, FString& OutError);

	/** Reset/retry the written section of the current exam. */
	bool BeginWritten(FString& OutError);

	bool SubmitWrittenAnswer(const FString& QuestionId, int32 AnswerIndex, FString& OutError);
	bool FinishWritten(FString& OutError);

	bool BeginTimed(const FString& PuzzleId, FString& OutError);
	bool SubmitTimedResult(bool bSolved, int32 TurnsUsed, float SecondsUsed, FString& OutError);

	bool BeginPractical(FString& OutError);
	void RecordPracticalEvent(const FString& ObjectiveId, int32 Amount = 1);

	/** Convenience adapter for FDuelResultStats: pass the cumulative duel totals once, at duel end. */
	void RecordPracticalStats(int32 BattleDamageDealt, int32 MonstersDestroyedByBattle, int32 FusionSummons,
		int32 RitualSummons, int32 SpecialSummons, int32 SpellsActivated, int32 TrapsActivated);

	bool FinishPractical(FString& OutError);

	bool FinishExam(FDAExamResult& OutResult, FString& OutError);
	void AbortExam();

	EDAExamPhase GetPhase() const { return Phase; }
	int32 GetMonthIndex() const { return MonthIndex; }
	int32 GetSeed() const { return Seed; }
	FString GetExamId() const;
	FString GetSelectedPuzzleId() const { return SelectedPuzzleId; }

	const TArray<FString>& GetCurrentQuestionIds() const { return CurrentQuestionIds; }
	const TArray<FString>& GetPuzzleIds() const { return PuzzleIds; }
	const FDAExamQuestion* GetQuestion(const FString& QuestionId) const;
	const FDAExamQuestion* GetCurrentQuestion() const;
	int32 GetCurrentQuestionIndex() const { return CurrentQuestionIndex; }
	int32 GetQuestionCount() const { return CurrentQuestionIds.Num(); }
	int32 GetQuestionBankSize() const { return QuestionsById.Num(); }
	int32 GetAnsweredCount() const { return WrittenAnswers.Num(); }
	int32 GetCorrectAnswerCount() const;
	int32 GetWrittenPoints() const;

	const TArray<FDAExamPracticalProgress>& GetPracticalProgress() const { return PracticalProgress; }
	const TArray<FDAExamPracticalObjective>& GetPracticalObjectives() const { return PracticalObjectives; }
	const TArray<FDAGradeBand>& GetGradeBands() const { return GradeBands; }

	int32 GetPracticalPoints() const;
	int32 GetTimedTurns() const { return TimedTurns; }
	float GetTimedSeconds() const { return TimedSeconds; }
	int32 GetPassMark() const { return PassMark; }
	int32 GetMaxPoints() const { return MaxPoints; }
	int32 GetPracticalPassPoints() const { return PracticalPassPoints; }
	int32 GetPracticalTurnLimit() const { return PracticalTurnLimit; }
	int32 GetPracticalTimeLimit() const { return PracticalTimeLimit; }
	int32 GetPracticalPlayerLp() const { return PracticalPlayerLp; }
	int32 GetPracticalOpponentLp() const { return PracticalOpponentLp; }
	const FString& GetPracticalOpponent() const { return PracticalOpponent; }
	const FString& GetPracticalDeck() const { return PracticalDeck; }
	bool IsExamDay(const FString& Weekday) const;
	bool HasResult() const { return bResultValid; }
	const FDAExamResult& GetResult() const { return Result; }

	/** Deterministic timed-puzzle choice for a month, using the current seed. */
	FString PickTimedPuzzle(int32 InMonthIndex) const;

private:
	bool LoadQuestionsFile(const FString& Path, FString& OutError);
	bool LoadPracticalsFile(const FString& Path, FString& OutError);
	bool LoadScoringFile(const FString& Path, FString& OutError);
	void LoadPuzzleCatalog(const FString& Directory);

	int32 ScoreWritten() const;
	int32 ScorePractical() const;
	FString GradeForPoints(int32 Points) const;

	TMap<FString, FDAExamQuestion> QuestionsById;
	TMap<int32, TArray<FString>> ExamSets;
	TArray<FDAExamPracticalObjective> PracticalObjectives;
	TArray<FDAGradeBand> GradeBands;
	TArray<FString> PuzzleIds;

	TArray<FString> CurrentQuestionIds;
	TMap<FString, int32> WrittenAnswers;
	TArray<FDAExamPracticalProgress> PracticalProgress;
	FString SelectedPuzzleId;
	FDAExamResult Result;

	EDAExamPhase Phase = EDAExamPhase::None;
	int32 MonthIndex = 0;
	int32 Seed = 0;
	int32 CurrentQuestionIndex = 0;
	int32 WrittenMax = 200;
	int32 PointsPerCorrect = 20;
	int32 TimedMax = 100;
	int32 PracticalMax = 200;
	int32 PassMark = 300;
	int32 MaxPoints = 500;
	int32 PracticalPassPoints = 120;
	int32 PracticalPlayerLp = 8000;
	int32 PracticalOpponentLp = 8000;
	int32 PracticalTurnLimit = 10;
	int32 PracticalTimeLimit = 600;
	FString PracticalOpponent;
	FString PracticalDeck;
	bool bTimedSolved = false;
	int32 TimedTurns = 0;
	float TimedSeconds = 0.f;
	bool bResultValid = false;
	bool bLoaded = false;
};
