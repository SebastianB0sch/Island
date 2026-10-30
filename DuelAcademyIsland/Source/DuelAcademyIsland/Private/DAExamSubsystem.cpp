// Duel Academy Island - exam lifecycle and scoring.

#include "DAExamSubsystem.h"

#include "DuelAcademyIsland.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	FString ExReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		FString Value;
		if (Object.IsValid())
		{
			Object->TryGetStringField(Field, Value);
		}
		return Value;
	}

	int32 ExReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool ExReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bDefault = false)
	{
		bool bValue = bDefault;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	TSharedPtr<FJsonObject> ExReadObject(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		const TSharedPtr<FJsonObject>* Found = nullptr;
		if (Object.IsValid() && Object->TryGetObjectField(Field, Found) && Found && Found->IsValid())
		{
			return *Found;
		}
		return nullptr;
	}

	void ExReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<FString>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Values))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid())
				{
					Out.Add(Value->AsString());
				}
			}
		}
	}

	bool ExLoadJson(const FString& Path, TSharedPtr<FJsonValue>& OutRoot, FString& OutError)
	{
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			OutError = FString::Printf(TEXT("File not found: %s"), *Path);
			return false;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, OutRoot) || !OutRoot.IsValid())
		{
			OutError = FString::Printf(TEXT("JSON parse failed: %s"), *Path);
			return false;
		}
		return true;
	}
}

void UDAExamSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	FString Error;
	Reload(Error);
}

bool UDAExamSubsystem::Reload(FString& OutError)
{
	OutError.Reset();
	QuestionsById.Reset();
	ExamSets.Reset();
	PracticalObjectives.Reset();
	GradeBands.Reset();
	PuzzleIds.Reset();
	CurrentQuestionIds.Reset();
	WrittenAnswers.Reset();
	PracticalProgress.Reset();
	Result = FDAExamResult();
	Phase = EDAExamPhase::None;
	MonthIndex = 0;
	Seed = 0;
	CurrentQuestionIndex = 0;
	bResultValid = false;
	bLoaded = false;

	const FString ExamRoot = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Exams"));
	FString Error;
	if (!LoadQuestionsFile(FPaths::Combine(ExamRoot, TEXT("questions.json")), Error))
	{
		OutError = Error;
		return false;
	}
	if (!LoadPracticalsFile(FPaths::Combine(ExamRoot, TEXT("practicals.json")), Error))
	{
		OutError = Error;
		return false;
	}
	if (!LoadScoringFile(FPaths::Combine(ExamRoot, TEXT("scoring.json")), Error))
	{
		OutError = Error;
		return false;
	}
	LoadPuzzleCatalog(FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Puzzles")));

	if (QuestionsById.Num() == 0 || ExamSets.Num() == 0)
	{
		OutError = TEXT("Exam question bank or exam sets are empty.");
		return false;
	}
	if (PracticalObjectives.Num() != 7)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[Exams] Expected 7 practical objectives, found %d."), PracticalObjectives.Num());
	}
	bLoaded = true;
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("[Exams] %d questions, %d exam sets, %d practical objectives, %d puzzles."),
		QuestionsById.Num(), ExamSets.Num(), PracticalObjectives.Num(), PuzzleIds.Num());
	return true;
}

bool UDAExamSubsystem::LoadQuestionsFile(const FString& Path, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	if (!ExLoadJson(Path, Root, OutError))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	if (!Object.IsValid())
	{
		OutError = TEXT("questions.json root must be an object.");
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* QuestionValues = nullptr;
	if (!Object->TryGetArrayField(TEXT("questions"), QuestionValues))
	{
		OutError = TEXT("questions.json has no questions array.");
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Value : *QuestionValues)
	{
		const TSharedPtr<FJsonObject> QuestionObject = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!QuestionObject.IsValid())
		{
			continue;
		}
		FDAExamQuestion Question;
		Question.Id = ExReadString(QuestionObject, TEXT("id"));
		Question.Topic = ExReadString(QuestionObject, TEXT("topic"));
		Question.Difficulty = ExReadInt(QuestionObject, TEXT("difficulty"), 1);
		Question.Text = ExReadString(QuestionObject, TEXT("text"));
		ExReadStringArray(QuestionObject, TEXT("options"), Question.Options);
		Question.AnswerIndex = ExReadInt(QuestionObject, TEXT("answer_index"));
		Question.Explanation = ExReadString(QuestionObject, TEXT("explanation"));
		Question.Confidence = ExReadString(QuestionObject, TEXT("confidence"));
		Question.Source = ExReadString(QuestionObject, TEXT("source"));
		if (Question.Id.IsEmpty() || Question.Options.Num() == 0)
		{
			continue;
		}
		if (Question.AnswerIndex < 0 || Question.AnswerIndex >= Question.Options.Num())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[Exams] Question %s has an invalid answer index."), *Question.Id);
			continue;
		}
		QuestionsById.Add(Question.Id, MoveTemp(Question));
	}

	const TArray<TSharedPtr<FJsonValue>>* SetValues = nullptr;
	if (Object->TryGetArrayField(TEXT("exam_sets"), SetValues))
	{
		for (const TSharedPtr<FJsonValue>& Value : *SetValues)
		{
			const TSharedPtr<FJsonObject> SetObject = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!SetObject.IsValid())
			{
				continue;
			}
			const int32 SetMonth = ExReadInt(SetObject, TEXT("month_index"));
			TArray<FString> SetQuestions;
			ExReadStringArray(SetObject, TEXT("question_ids"), SetQuestions);
			if (SetMonth > 0 && SetQuestions.Num() > 0)
			{
				ExamSets.Add(SetMonth, MoveTemp(SetQuestions));
			}
		}
	}
	return QuestionsById.Num() > 0;
}

bool UDAExamSubsystem::LoadPracticalsFile(const FString& Path, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	if (!ExLoadJson(Path, Root, OutError))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	if (!Object.IsValid())
	{
		OutError = TEXT("practicals.json root must be an object.");
		return false;
	}
	PracticalOpponent = ExReadString(Object, TEXT("opponent"));
	PracticalDeck = ExReadString(Object, TEXT("deck"));
	PracticalPlayerLp = ExReadInt(Object, TEXT("player_lp"), 8000);
	PracticalOpponentLp = ExReadInt(Object, TEXT("opponent_lp"), 8000);
	PracticalTurnLimit = ExReadInt(Object, TEXT("turn_limit"), 10);
	PracticalTimeLimit = ExReadInt(Object, TEXT("time_limit"), 600);
	PracticalPassPoints = ExReadInt(Object, TEXT("pass_points"), 120);
	PracticalMax = ExReadInt(Object, TEXT("max_points"), 200);

	const TArray<TSharedPtr<FJsonValue>>* ObjectiveValues = nullptr;
	if (!Object->TryGetArrayField(TEXT("objectives"), ObjectiveValues))
	{
		OutError = TEXT("practicals.json has no objectives array.");
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Value : *ObjectiveValues)
	{
		const TSharedPtr<FJsonObject> ObjectiveObject = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!ObjectiveObject.IsValid())
		{
			continue;
		}
		FDAExamPracticalObjective Objective;
		Objective.Id = ExReadString(ObjectiveObject, TEXT("id"));
		Objective.Label = ExReadString(ObjectiveObject, TEXT("label"));
		Objective.Event = ExReadString(ObjectiveObject, TEXT("event"));
		Objective.Target = ExReadInt(ObjectiveObject, TEXT("target"), 1);
		Objective.Points = ExReadInt(ObjectiveObject, TEXT("points"));
		Objective.bRepeatable = ExReadBool(ObjectiveObject, TEXT("repeatable"), true);
		if (!Objective.Id.IsEmpty())
		{
			PracticalObjectives.Add(MoveTemp(Objective));
		}
	}
	return PracticalObjectives.Num() > 0;
}

bool UDAExamSubsystem::LoadScoringFile(const FString& Path, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	if (!ExLoadJson(Path, Root, OutError))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	if (!Object.IsValid())
	{
		OutError = TEXT("scoring.json root must be an object.");
		return false;
	}

	MaxPoints = ExReadInt(Object, TEXT("max_points"), 500);
	PassMark = ExReadInt(Object, TEXT("pass_mark"), 300);
	if (const TSharedPtr<FJsonObject> Sections = ExReadObject(Object, TEXT("sections")))
	{
		if (const TSharedPtr<FJsonObject> Written = ExReadObject(Sections, TEXT("written")))
		{
			WrittenMax = ExReadInt(Written, TEXT("max_points"), 200);
			PointsPerCorrect = ExReadInt(Written, TEXT("points_per_correct"), 20);
		}
		if (const TSharedPtr<FJsonObject> Timed = ExReadObject(Sections, TEXT("timed")))
		{
			TimedMax = ExReadInt(Timed, TEXT("max_points"), 100);
		}
		if (const TSharedPtr<FJsonObject> Practical = ExReadObject(Sections, TEXT("practical")))
		{
			PracticalMax = ExReadInt(Practical, TEXT("max_points"), 200);
		}
	}

	const TArray<TSharedPtr<FJsonValue>>* BandValues = nullptr;
	if (Object->TryGetArrayField(TEXT("grade_bands"), BandValues))
	{
		for (const TSharedPtr<FJsonValue>& Value : *BandValues)
		{
			const TSharedPtr<FJsonObject> BandObject = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!BandObject.IsValid())
			{
				continue;
			}
			FDAGradeBand Band;
			Band.MinPoints = ExReadInt(BandObject, TEXT("min_points"));
			Band.Grade = ExReadString(BandObject, TEXT("grade"));
			Band.Label = ExReadString(BandObject, TEXT("label"));
			GradeBands.Add(MoveTemp(Band));
		}
	}
	GradeBands.Sort([](const FDAGradeBand& A, const FDAGradeBand& B) { return A.MinPoints > B.MinPoints; });
	return true;
}

void UDAExamSubsystem::LoadPuzzleCatalog(const FString& Directory)
{
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *FPaths::Combine(Directory, TEXT("P*.json")), true, false);
	Files.Sort();
	for (const FString& File : Files)
	{
		const FString Id = FPaths::GetBaseFilename(File);
		if (!Id.IsEmpty())
		{
			PuzzleIds.Add(Id);
		}
	}
}

bool UDAExamSubsystem::StartExam(int32 InMonthIndex, int32 InSeed, FString& OutError)
{
	OutError.Reset();
	if (!bLoaded)
	{
		OutError = TEXT("Exam data is not loaded.");
		return false;
	}
	if (InMonthIndex < 1 || InMonthIndex > 12)
	{
		OutError = FString::Printf(TEXT("Month index %d is outside 1-12."), InMonthIndex);
		return false;
	}
	const TArray<FString>* Set = ExamSets.Find(InMonthIndex);
	if (!Set || Set->Num() == 0)
	{
		OutError = FString::Printf(TEXT("No exam set for month %d."), InMonthIndex);
		return false;
	}

	MonthIndex = InMonthIndex;
	Seed = InSeed;
	CurrentQuestionIds = *Set;
	CurrentQuestionIndex = 0;
	WrittenAnswers.Reset();
	PracticalProgress.Reset();
	SelectedPuzzleId.Reset();
	bTimedSolved = false;
	TimedTurns = 0;
	TimedSeconds = 0.f;
	Result = FDAExamResult();
	bResultValid = false;
	Phase = EDAExamPhase::Written;
	return true;
}

bool UDAExamSubsystem::BeginWritten(FString& OutError)
{
	OutError.Reset();
	if (MonthIndex <= 0 || CurrentQuestionIds.Num() == 0)
	{
		OutError = TEXT("StartExam must be called before BeginWritten.");
		return false;
	}
	WrittenAnswers.Reset();
	CurrentQuestionIndex = 0;
	bTimedSolved = false;
	PracticalProgress.Reset();
	SelectedPuzzleId.Reset();
	Result = FDAExamResult();
	bResultValid = false;
	Phase = EDAExamPhase::Written;
	return true;
}

bool UDAExamSubsystem::SubmitWrittenAnswer(const FString& QuestionId, int32 AnswerIndex, FString& OutError)
{
	OutError.Reset();
	if (Phase != EDAExamPhase::Written)
	{
		OutError = TEXT("Not in the written section.");
		return false;
	}
	if (!CurrentQuestionIds.Contains(QuestionId))
	{
		OutError = FString::Printf(TEXT("Question %s is not part of this exam."), *QuestionId);
		return false;
	}
	const FDAExamQuestion* Question = QuestionsById.Find(QuestionId);
	if (!Question)
	{
		OutError = TEXT("Unknown question.");
		return false;
	}
	if (AnswerIndex < 0 || AnswerIndex >= Question->Options.Num())
	{
		OutError = TEXT("Answer index is out of range.");
		return false;
	}
	WrittenAnswers.Add(QuestionId, AnswerIndex);
	CurrentQuestionIndex = FMath::Max(CurrentQuestionIndex, CurrentQuestionIds.IndexOfByKey(QuestionId) + 1);
	return true;
}

bool UDAExamSubsystem::FinishWritten(FString& OutError)
{
	OutError.Reset();
	if (Phase != EDAExamPhase::Written)
	{
		OutError = TEXT("Not in the written section.");
		return false;
	}
	Phase = EDAExamPhase::WrittenDone;
	return true;
}

bool UDAExamSubsystem::BeginTimed(const FString& PuzzleId, FString& OutError)
{
	OutError.Reset();
	if (Phase != EDAExamPhase::WrittenDone)
	{
		OutError = TEXT("Finish the written section before the timed duel.");
		return false;
	}
	FString Wanted = PuzzleId;
	if (Wanted.IsEmpty())
	{
		Wanted = PickTimedPuzzle(MonthIndex);
	}
	if (Wanted.IsEmpty() || !PuzzleIds.Contains(Wanted))
	{
		OutError = FString::Printf(TEXT("Unknown timed puzzle '%s'."), *Wanted);
		return false;
	}
	SelectedPuzzleId = Wanted;
	bTimedSolved = false;
	TimedTurns = 0;
	TimedSeconds = 0.f;
	Phase = EDAExamPhase::Timed;
	return true;
}

bool UDAExamSubsystem::SubmitTimedResult(bool bSolved, int32 TurnsUsed, float SecondsUsed, FString& OutError)
{
	OutError.Reset();
	if (Phase != EDAExamPhase::Timed)
	{
		OutError = TEXT("Not in the timed-duel section.");
		return false;
	}
	bTimedSolved = bSolved;
	TimedTurns = FMath::Max(0, TurnsUsed);
	TimedSeconds = FMath::Max(0.f, SecondsUsed);
	Phase = EDAExamPhase::TimedDone;
	return true;
}

bool UDAExamSubsystem::BeginPractical(FString& OutError)
{
	OutError.Reset();
	if (Phase != EDAExamPhase::TimedDone)
	{
		OutError = TEXT("Finish the timed duel before the practical.");
		return false;
	}
	PracticalProgress.Reset();
	for (const FDAExamPracticalObjective& Objective : PracticalObjectives)
	{
		FDAExamPracticalProgress Progress;
		Progress.ObjectiveId = Objective.Id;
		Progress.Label = Objective.Label;
		Progress.Target = FMath::Max(1, Objective.Target);
		PracticalProgress.Add(MoveTemp(Progress));
	}
	Phase = EDAExamPhase::Practical;
	return true;
}

void UDAExamSubsystem::RecordPracticalEvent(const FString& ObjectiveId, int32 Amount)
{
	if (Phase != EDAExamPhase::Practical || Amount <= 0)
	{
		return;
	}
	for (FDAExamPracticalProgress& Progress : PracticalProgress)
	{
		if (!Progress.ObjectiveId.Equals(ObjectiveId, ESearchCase::IgnoreCase) || Progress.bComplete)
		{
			continue;
		}
		const FDAExamPracticalObjective* Objective = PracticalObjectives.FindByPredicate([&ObjectiveId](const FDAExamPracticalObjective& Candidate)
		{
			return Candidate.Id.Equals(ObjectiveId, ESearchCase::IgnoreCase);
		});
		if (!Objective)
		{
			return;
		}
		Progress.Progress = FMath::Min(Progress.Target, Progress.Progress + Amount);
		if (Progress.Progress >= Progress.Target && !Progress.bComplete)
		{
			Progress.bComplete = true;
			Progress.AwardedPoints = Objective->Points;
		}
		return;
	}
}

void UDAExamSubsystem::RecordPracticalStats(int32 BattleDamageDealt, int32 MonstersDestroyedByBattle,
	int32 FusionSummons, int32 RitualSummons, int32 SpecialSummons, int32 SpellsActivated, int32 TrapsActivated)
{
	RecordPracticalEvent(TEXT("damage"), BattleDamageDealt);
	RecordPracticalEvent(TEXT("battle"), MonstersDestroyedByBattle);
	RecordPracticalEvent(TEXT("fusion"), FusionSummons);
	RecordPracticalEvent(TEXT("ritual"), RitualSummons);
	RecordPracticalEvent(TEXT("special_summon"), SpecialSummons);
	RecordPracticalEvent(TEXT("spells"), SpellsActivated);
	RecordPracticalEvent(TEXT("traps"), TrapsActivated);
}

bool UDAExamSubsystem::FinishPractical(FString& OutError)
{
	OutError.Reset();
	if (Phase != EDAExamPhase::Practical)
	{
		OutError = TEXT("Not in the practical section.");
		return false;
	}
	Phase = EDAExamPhase::PracticalDone;
	return true;
}

int32 UDAExamSubsystem::ScoreWritten() const
{
	return FMath::Min(GetCorrectAnswerCount() * PointsPerCorrect, WrittenMax);
}

int32 UDAExamSubsystem::ScorePractical() const
{
	int32 Points = 0;
	for (const FDAExamPracticalProgress& Progress : PracticalProgress)
	{
		Points += Progress.AwardedPoints;
	}
	return FMath::Min(Points, PracticalMax);
}

int32 UDAExamSubsystem::GetCorrectAnswerCount() const
{
	int32 Correct = 0;
	for (const TPair<FString, int32>& Pair : WrittenAnswers)
	{
		const FDAExamQuestion* Question = QuestionsById.Find(Pair.Key);
		if (Question && Question->AnswerIndex == Pair.Value)
		{
			++Correct;
		}
	}
	return Correct;
}

int32 UDAExamSubsystem::GetWrittenPoints() const
{
	return ScoreWritten();
}

int32 UDAExamSubsystem::GetPracticalPoints() const
{
	return ScorePractical();
}

FString UDAExamSubsystem::GradeForPoints(int32 Points) const
{
	for (const FDAGradeBand& Band : GradeBands)
	{
		if (Points >= Band.MinPoints)
		{
			return Band.Grade;
		}
	}
	return TEXT("F");
}

bool UDAExamSubsystem::FinishExam(FDAExamResult& OutResult, FString& OutError)
{
	OutError.Reset();
	if (Phase != EDAExamPhase::PracticalDone)
	{
		OutError = TEXT("Finish the practical before submitting the exam.");
		return false;
	}

	Result = FDAExamResult();
	Result.MonthIndex = MonthIndex;
	Result.WrittenCorrect = GetCorrectAnswerCount();
	Result.WrittenPoints = ScoreWritten();
	Result.bTimedSolved = bTimedSolved;
	Result.TimedPoints = bTimedSolved ? TimedMax : 0;
	Result.PracticalPoints = ScorePractical();
	Result.TotalPoints = Result.WrittenPoints + Result.TimedPoints + Result.PracticalPoints;
	Result.bPassed = Result.TotalPoints >= PassMark;
	Result.Grade = GradeForPoints(Result.TotalPoints);
	Result.TitleOutcome = Result.bPassed ? TEXT("promotion_eligible") : TEXT("Dropout Boy");
	Result.DormOutcome = Result.bPassed
		? (Result.TotalPoints >= 450 ? TEXT("promotion_candidate") : TEXT("retain"))
		: TEXT("dropout");

	for (const FDAExamPracticalProgress& Progress : PracticalProgress)
	{
		if (Progress.bComplete)
		{
			Result.CompletedObjectives.Add(Progress.ObjectiveId);
		}
		else
		{
			Result.FailedObjectives.Add(Progress.ObjectiveId);
		}
	}

	Result.Flags.AddUnique(FString(Result.bPassed ? TEXT("exam_passed") : TEXT("exam_failed")));
	Result.Flags.AddUnique(FString(Result.PracticalPoints >= PracticalPassPoints ? TEXT("practical_passed") : TEXT("practical_failed")));
	if (!Result.bPassed)
	{
		Result.Flags.AddUnique(TEXT("dropout_boy"));
	}

	Phase = EDAExamPhase::Finished;
	bResultValid = true;
	OutResult = Result;
	return true;
}

void UDAExamSubsystem::AbortExam()
{
	Phase = EDAExamPhase::None;
	MonthIndex = 0;
	Seed = 0;
	CurrentQuestionIds.Reset();
	WrittenAnswers.Reset();
	PracticalProgress.Reset();
	SelectedPuzzleId.Reset();
	bTimedSolved = false;
	TimedTurns = 0;
	TimedSeconds = 0.f;
	Result = FDAExamResult();
	bResultValid = false;
}

const FDAExamQuestion* UDAExamSubsystem::GetQuestion(const FString& QuestionId) const
{
	return QuestionsById.Find(QuestionId);
}

const FDAExamQuestion* UDAExamSubsystem::GetCurrentQuestion() const
{
	if (!CurrentQuestionIds.IsValidIndex(CurrentQuestionIndex))
	{
		return nullptr;
	}
	return GetQuestion(CurrentQuestionIds[CurrentQuestionIndex]);
}

FString UDAExamSubsystem::GetExamId() const
{
	return MonthIndex > 0 ? FString::Printf(TEXT("EXAM_%02d"), MonthIndex) : FString();
}

FString UDAExamSubsystem::PickTimedPuzzle(int32 InMonthIndex) const
{
	if (PuzzleIds.Num() == 0)
	{
		return FString();
	}
	const int32 Index = ((Seed + InMonthIndex * 7) % PuzzleIds.Num() + PuzzleIds.Num()) % PuzzleIds.Num();
	return PuzzleIds[Index];
}

bool UDAExamSubsystem::IsExamDay(const FString& Weekday) const
{
	return Weekday.Equals(TEXT("Friday"), ESearchCase::IgnoreCase);
}

