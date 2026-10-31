// Duel Academy Island - in-engine 12-cycle exam self-test.

#include "DAExamSelfTest.h"

#include "DACardRecords.h"
#include "DAExamSubsystem.h"
#include "DAPuzzleRuntime.h"
#include "DuelAcademyIsland.h"

#include "UObject/Package.h"

namespace
{
	struct FExamCycleCheck
	{
		bool bPass = true;
		FString Failure;

		void Expect(bool bCondition, const FString& Message)
		{
			if (!bCondition && bPass)
			{
				bPass = false;
				Failure = Message;
			}
		}
	};

	FString WithFailure(const FString& Detail, const FExamCycleCheck& Check)
	{
		return Check.bPass ? Detail : FString::Printf(TEXT("%s [%s]"), *Detail, *Check.Failure);
	}

	bool AnswerCorrect(UDAExamSubsystem* Exam, FString& OutError)
	{
		for (const FString& QuestionId : Exam->GetCurrentQuestionIds())
		{
			const FDAExamQuestion* Question = Exam->GetQuestion(QuestionId);
			if (!Question)
			{
				OutError = FString::Printf(TEXT("question '%s' is missing."), *QuestionId);
				return false;
			}
			if (!Exam->SubmitWrittenAnswer(QuestionId, Question->AnswerIndex, OutError))
			{
				return false;
			}
		}
		return true;
	}

	bool AnswerMixed(UDAExamSubsystem* Exam, int32 CorrectCount, FString& OutError)
	{
		int32 Index = 0;
		for (const FString& QuestionId : Exam->GetCurrentQuestionIds())
		{
			const FDAExamQuestion* Question = Exam->GetQuestion(QuestionId);
			if (!Question)
			{
				OutError = FString::Printf(TEXT("question '%s' is missing."), *QuestionId);
				return false;
			}
			const int32 Answer = Index < CorrectCount
				? Question->AnswerIndex
				: (Question->AnswerIndex + 1) % FMath::Max(1, Question->Options.Num());
			if (!Exam->SubmitWrittenAnswer(QuestionId, Answer, OutError))
			{
				return false;
			}
			++Index;
		}
		return true;
	}

	void RecordAllPractical(UDAExamSubsystem* Exam)
	{
		int32 Damage = 0;
		int32 Battle = 0;
		int32 Fusion = 0;
		int32 Ritual = 0;
		int32 Special = 0;
		int32 Spells = 0;
		int32 Traps = 0;
		for (const FDAExamPracticalObjective& Objective : Exam->GetPracticalObjectives())
		{
			if (Objective.Id.Equals(TEXT("damage"), ESearchCase::IgnoreCase)) Damage = Objective.Target;
			else if (Objective.Id.Equals(TEXT("battle"), ESearchCase::IgnoreCase)) Battle = Objective.Target;
			else if (Objective.Id.Equals(TEXT("fusion"), ESearchCase::IgnoreCase)) Fusion = Objective.Target;
			else if (Objective.Id.Equals(TEXT("ritual"), ESearchCase::IgnoreCase)) Ritual = Objective.Target;
			else if (Objective.Id.Equals(TEXT("special_summon"), ESearchCase::IgnoreCase)) Special = Objective.Target;
			else if (Objective.Id.Equals(TEXT("spells"), ESearchCase::IgnoreCase)) Spells = Objective.Target;
			else if (Objective.Id.Equals(TEXT("traps"), ESearchCase::IgnoreCase)) Traps = Objective.Target;
		}
		// Exercise the FDuelResultStats adapter as the only perfect-run source;
		// the partial run covers the generic per-objective path separately.
		Exam->RecordPracticalStats(Damage, Battle, Fusion, Ritual, Special, Spells, Traps);
	}

	void RunPerfectCycle(UDAExamSubsystem* Exam, UCardDatabaseSubsystem* Database, const FDAExamCycle& Cycle,
		FExamCycleCheck& Check)
	{
		FString Error;
		Check.Expect(Exam->StartExam(Cycle.MonthIndex, 1000 + Cycle.MonthIndex * 31, Error),
			FString::Printf(TEXT("StartExam: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(Exam->GetPhase() == EDAExamPhase::Written, TEXT("phase is Written after StartExam"));
		Check.Expect(Exam->GetExamId() == Cycle.ExamId, TEXT("exam id matches the cycle"));
		Check.Expect(Exam->GetCurrentQuestionIds() == Cycle.QuestionIds, TEXT("question ids match exams.json"));
		Check.Expect(Exam->PickTimedPuzzle(Cycle.MonthIndex) == Cycle.TimedPuzzleId, TEXT("authored timed puzzle is selected"));
		Check.Expect(Exam->PickTimedPuzzle(Cycle.MonthIndex) == Exam->PickTimedPuzzle(Cycle.MonthIndex),
			TEXT("timed puzzle selection is deterministic"));

		Check.Expect(AnswerCorrect(Exam, Error), FString::Printf(TEXT("all answers accepted: %s"), *Error));
		Check.Expect(Exam->GetAnsweredCount() == 10, TEXT("ten written answers stored"));
		Check.Expect(Exam->GetCorrectAnswerCount() == 10, TEXT("ten written answers correct"));
		Check.Expect(Exam->GetWrittenPoints() == 200, TEXT("written points are 200"));
		Check.Expect(Exam->FinishWritten(Error), FString::Printf(TEXT("FinishWritten: %s"), *Error));
		Check.Expect(Exam->BeginTimed(TEXT(""), Error), FString::Printf(TEXT("BeginTimed: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(Exam->GetPhase() == EDAExamPhase::Timed, TEXT("phase is Timed"));
		Check.Expect(Exam->GetSelectedPuzzleId() == Cycle.TimedPuzzleId, TEXT("selected puzzle is the authored cycle puzzle"));

		FDAPuzzleReplayResult Replay;
		Check.Expect(FDAPuzzleRuntime::ReplayById(Database, Cycle.TimedPuzzleId, Replay, Error),
			FString::Printf(TEXT("authored timed puzzle is solvable: %s"), *Error));
		Check.Expect(Replay.bWon, TEXT("timed-puzzle replay wins"));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(Exam->SubmitTimedResult(true, FMath::Max(1, Replay.StepsExecuted), 1.f, Error),
			FString::Printf(TEXT("SubmitTimedResult: %s"), *Error));
		Check.Expect(Exam->BeginPractical(Error), FString::Printf(TEXT("BeginPractical: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		RecordAllPractical(Exam);
		Check.Expect(Exam->GetPracticalProgress().Num() == 7, TEXT("seven practical rows exist"));
		Check.Expect(Exam->GetPracticalPoints() == 200, TEXT("practical points are 200"));
		for (const FDAExamPracticalProgress& Progress : Exam->GetPracticalProgress())
		{
			Check.Expect(Progress.bComplete, FString::Printf(TEXT("practical objective '%s' completes"), *Progress.ObjectiveId));
		}
		Check.Expect(Exam->FinishPractical(Error), FString::Printf(TEXT("FinishPractical: %s"), *Error));
		FDAExamResult Result;
		Check.Expect(Exam->FinishExam(Result, Error), FString::Printf(TEXT("FinishExam: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}

		Check.Expect(Exam->GetPhase() == EDAExamPhase::Finished, TEXT("phase is Finished"));
		Check.Expect(Exam->HasResult(), TEXT("result is valid"));
		Check.Expect(Result.MonthIndex == Cycle.MonthIndex, TEXT("result month matches the cycle"));
		Check.Expect(Result.WrittenCorrect == 10 && Result.WrittenPoints == 200, TEXT("result written score is 200"));
		Check.Expect(Result.bTimedSolved && Result.TimedPoints == 100, TEXT("result timed score is 100"));
		Check.Expect(Result.PracticalPoints == 200, TEXT("result practical score is 200"));
		Check.Expect(Result.TotalPoints == 500, TEXT("result total is 500"));
		Check.Expect(Result.bPassed, TEXT("perfect exam passes"));
		Check.Expect(Result.Grade == TEXT("S"), TEXT("perfect exam grades S"));
		Check.Expect(Result.TitleOutcome == TEXT("promotion_eligible"), TEXT("title outcome is promotion_eligible"));
		Check.Expect(Result.DormOutcome == TEXT("promotion_candidate"), TEXT("dorm outcome is promotion_candidate"));
		Check.Expect(Result.DPReward == Cycle.DPReward, TEXT("validated DP reward matches the cycle"));
		Check.Expect(Result.CompletedObjectives.Num() == 7, TEXT("seven objectives complete"));
		Check.Expect(Result.FailedObjectives.Num() == 0, TEXT("no objectives failed"));
		Check.Expect(Result.Flags.Contains(TEXT("exam_passed")), TEXT("exam_passed flag"));
		Check.Expect(Result.Flags.Contains(TEXT("practical_passed")), TEXT("practical_passed flag"));
		Check.Expect(!Result.Flags.Contains(TEXT("exam_failed")), TEXT("no exam_failed flag"));
		Check.Expect(!Result.Flags.Contains(TEXT("dropout_boy")), TEXT("no dropout_boy flag"));

		// Retry reset: BeginWritten keeps the month but clears answers/result.
		Check.Expect(Exam->BeginWritten(Error), FString::Printf(TEXT("BeginWritten retry: %s"), *Error));
		Check.Expect(Exam->GetPhase() == EDAExamPhase::Written, TEXT("retry returns to Written"));
		Check.Expect(Exam->GetAnsweredCount() == 0, TEXT("retry clears written answers"));
		Check.Expect(Exam->GetSelectedPuzzleId().IsEmpty(), TEXT("retry clears the timed puzzle"));
		Check.Expect(!Exam->HasResult(), TEXT("retry clears the result"));
	}

	void RunFailingCycle(UDAExamSubsystem* Exam, const FDAExamCycle& Cycle, FExamCycleCheck& Check)
	{
		FString Error;
		Check.Expect(Exam->StartExam(Cycle.MonthIndex, 5000 + Cycle.MonthIndex * 17, Error),
			FString::Printf(TEXT("StartExam: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(AnswerMixed(Exam, 6, Error), FString::Printf(TEXT("mixed answers accepted: %s"), *Error));
		Check.Expect(Exam->GetAnsweredCount() == 10, TEXT("ten mixed answers stored"));
		Check.Expect(Exam->GetCorrectAnswerCount() == 6, TEXT("six mixed answers correct"));
		Check.Expect(Exam->GetWrittenPoints() == 120, TEXT("mixed written points are 120"));
		Check.Expect(Exam->FinishWritten(Error), FString::Printf(TEXT("FinishWritten: %s"), *Error));
		Check.Expect(Exam->BeginTimed(TEXT(""), Error), FString::Printf(TEXT("BeginTimed: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(Exam->GetSelectedPuzzleId() == Cycle.TimedPuzzleId, TEXT("failing mix still selects the authored puzzle"));
		Check.Expect(Exam->SubmitTimedResult(false, 0, 0.f, Error), FString::Printf(TEXT("SubmitTimedResult: %s"), *Error));
		Check.Expect(Exam->BeginPractical(Error), FString::Printf(TEXT("BeginPractical: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(Exam->FinishPractical(Error), FString::Printf(TEXT("FinishPractical: %s"), *Error));
		FDAExamResult Result;
		Check.Expect(Exam->FinishExam(Result, Error), FString::Printf(TEXT("FinishExam: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(Result.WrittenCorrect == 6 && Result.WrittenPoints == 120, TEXT("failing mix written score is 120"));
		Check.Expect(!Result.bTimedSolved && Result.TimedPoints == 0, TEXT("failed timed duel scores zero"));
		Check.Expect(Result.PracticalPoints == 0, TEXT("empty practical scores zero"));
		Check.Expect(Result.TotalPoints == 120, TEXT("failing mix total is 120"));
		Check.Expect(!Result.bPassed, TEXT("failing mix does not pass"));
		Check.Expect(Result.Grade == TEXT("F"), TEXT("failing mix grades F"));
		Check.Expect(Result.TitleOutcome == TEXT("Dropout Boy"), TEXT("failing title outcome is Dropout Boy"));
		Check.Expect(Result.DormOutcome == TEXT("dropout"), TEXT("failing dorm outcome is dropout"));
		Check.Expect(Result.DPReward == Cycle.DPReward, TEXT("failing DP reward matches the cycle"));
		Check.Expect(Result.CompletedObjectives.Num() == 0, TEXT("no objectives complete on the failing mix"));
		Check.Expect(Result.FailedObjectives.Num() == 7, TEXT("all seven objectives fail on the failing mix"));
		Check.Expect(Result.Flags.Contains(TEXT("exam_failed")), TEXT("exam_failed flag"));
		Check.Expect(Result.Flags.Contains(TEXT("practical_failed")), TEXT("practical_failed flag"));
		Check.Expect(Result.Flags.Contains(TEXT("dropout_boy")), TEXT("dropout_boy flag"));

		Check.Expect(Exam->BeginWritten(Error), FString::Printf(TEXT("BeginWritten retry after failure: %s"), *Error));
		Check.Expect(Exam->GetPhase() == EDAExamPhase::Written, TEXT("failed-exam retry returns to Written"));
		Check.Expect(Exam->GetAnsweredCount() == 0, TEXT("failed-exam retry clears answers"));
		Check.Expect(!Exam->HasResult(), TEXT("failed-exam retry clears the result"));
	}

	void RunPartialPass(UDAExamSubsystem* Exam, UCardDatabaseSubsystem* Database, FExamCycleCheck& Check)
	{
		FString Error;
		Check.Expect(Exam->StartExam(1, 777, Error), FString::Printf(TEXT("partial StartExam: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(AnswerCorrect(Exam, Error), FString::Printf(TEXT("partial answers: %s"), *Error));
		Check.Expect(Exam->FinishWritten(Error), FString::Printf(TEXT("partial FinishWritten: %s"), *Error));
		Check.Expect(Exam->BeginTimed(TEXT(""), Error), FString::Printf(TEXT("partial BeginTimed: %s"), *Error));
		const FDAExamCycle* Cycle = Exam->GetCycle(1);
		if (!Cycle)
		{
			Check.Expect(false, TEXT("month 1 cycle is missing"));
			return;
		}
		FDAPuzzleReplayResult Replay;
		Check.Expect(FDAPuzzleRuntime::ReplayById(Database, Cycle->TimedPuzzleId, Replay, Error),
			FString::Printf(TEXT("partial timed puzzle: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		Check.Expect(Exam->SubmitTimedResult(true, FMath::Max(1, Replay.StepsExecuted), 1.f, Error),
			FString::Printf(TEXT("partial SubmitTimedResult: %s"), *Error));
		Check.Expect(Exam->BeginPractical(Error), FString::Printf(TEXT("partial BeginPractical: %s"), *Error));
		const FDAExamPracticalObjective* FirstObjective = Exam->GetPracticalObjectives().Num() > 0
			? &Exam->GetPracticalObjectives()[0] : nullptr;
		if (!FirstObjective)
		{
			Check.Expect(false, TEXT("practical objective 0 is missing"));
			return;
		}
		Exam->RecordPracticalEvent(FirstObjective->Id, FirstObjective->Target);
		Check.Expect(Exam->FinishPractical(Error), FString::Printf(TEXT("partial FinishPractical: %s"), *Error));
		FDAExamResult Result;
		Check.Expect(Exam->FinishExam(Result, Error), FString::Printf(TEXT("partial FinishExam: %s"), *Error));
		if (!Check.bPass)
		{
			return;
		}
		const int32 ExpectedPractical = FirstObjective->Points;
		Check.Expect(Result.WrittenPoints == 200 && Result.TimedPoints == 100, TEXT("partial written/timed scores"));
		Check.Expect(Result.PracticalPoints == ExpectedPractical, TEXT("partial practical score matches objective points"));
		Check.Expect(Result.TotalPoints == 300 + ExpectedPractical, TEXT("partial total is 300 + focus points"));
		Check.Expect(Result.bPassed, TEXT("partial score above 300 passes"));
		Check.Expect(Result.Grade == TEXT("C"), TEXT("partial score in the 300-349 band grades C"));
		Check.Expect(Result.DormOutcome == TEXT("retain"), TEXT("partial pass retains the dorm"));
		Check.Expect(Result.CompletedObjectives.Num() == 1, TEXT("partial run completes one objective"));
		Check.Expect(Result.FailedObjectives.Num() == 6, TEXT("partial run fails six objectives"));
		Check.Expect(Result.Flags.Contains(TEXT("practical_failed")), TEXT("partial practical below 120 is flagged failed"));
	}
}

FDASelfTestReport FDAExamSelfTest::Run(UCardDatabaseSubsystem* Database)
{
	FDASelfTestReport Report;
	Report.Suite = TEXT("ExamSelfTest");
	if (!Database)
	{
		Report.Check(false, TEXT("card database is available"));
		return Report;
	}

	UDAExamSubsystem* Exam = NewObject<UDAExamSubsystem>(Database->GetGameInstance());
	if (!Exam)
	{
		Report.Check(false, TEXT("transient exam subsystem was created"));
		return Report;
	}
	FString Error;
	if (!Exam->Reload(Error))
	{
		Report.Check(false, FString::Printf(TEXT("exam data loads: %s"), *Error));
		return Report;
	}

	Report.Check(Exam->GetQuestionBankSize() >= 30, TEXT("question bank has at least 30 questions"));
	Report.Check(Exam->GetPracticalObjectives().Num() == 7, TEXT("seven practical objectives load"));
	Report.Check(Exam->GetPassMark() == 300, TEXT("global pass mark is 300"));
	Report.Check(Exam->GetMaxPoints() == 500, TEXT("global max points are 500"));
	Report.Check(Exam->GetPracticalPassPoints() == 120, TEXT("practical pass points are 120"));
	Report.Check(Exam->IsExamDay(TEXT("Friday")), TEXT("Friday is an exam day"));
	Report.Check(!Exam->IsExamDay(TEXT("Monday")), TEXT("Monday is not an exam day"));
	Report.Check(Exam->GetCycleCount() == 12, FString::Printf(TEXT("12 authored cycles load (found %d)"), Exam->GetCycleCount()));

	// Invalid-month guards must fail before mutating the active exam.
	Report.Check(!Exam->StartExam(0, 1, Error), TEXT("month 0 is rejected"));
	Report.Check(!Exam->StartExam(13, 1, Error), TEXT("month 13 is rejected"));

	for (int32 Month = 1; Month <= 12; ++Month)
	{
		const FDAExamCycle* Cycle = Exam->GetCycle(Month);
		if (!Cycle)
		{
			Report.Check(false, FString::Printf(TEXT("cycle month %d is present"), Month));
			continue;
		}
		Report.Check(Cycle->ExamId == FString::Printf(TEXT("EXAM_%02d"), Month),
			FString::Printf(TEXT("month %d exam id is EXAM_%02d"), Month, Month));
		Report.Check(Cycle->QuestionIds.Num() == 10, FString::Printf(TEXT("month %d has ten questions"), Month));
		Report.Check(!Cycle->TimedPuzzleId.IsEmpty() && Exam->GetPuzzleIds().Contains(Cycle->TimedPuzzleId),
			FString::Printf(TEXT("month %d timed puzzle '%s' exists"), Month, *Cycle->TimedPuzzleId));
		Report.Check(Exam->GetPracticalObjectives().ContainsByPredicate([Cycle](const FDAExamPracticalObjective& Objective)
		{
			return Objective.Id.Equals(Cycle->PracticalObjectiveId, ESearchCase::IgnoreCase);
		}), FString::Printf(TEXT("month %d practical focus '%s' exists"), Month, *Cycle->PracticalObjectiveId));
		Report.Check(Cycle->PassMark == Exam->GetPassMark() && Cycle->MaxPoints == Exam->GetMaxPoints(),
			FString::Printf(TEXT("month %d scoring matches the global scoring file"), Month));

		FExamCycleCheck Perfect;
		RunPerfectCycle(Exam, Database, *Cycle, Perfect);
		Report.Check(Perfect.bPass, WithFailure(FString::Printf(TEXT("%s month %d perfect cycle: 500 / S"), *Cycle->ExamId, Month), Perfect));
		Exam->AbortExam();

		FExamCycleCheck Failing;
		RunFailingCycle(Exam, *Cycle, Failing);
		Report.Check(Failing.bPass, WithFailure(FString::Printf(TEXT("%s month %d failing mix: 120 / F / dropout"), *Cycle->ExamId, Month), Failing));
		Exam->AbortExam();
	}

	FExamCycleCheck Partial;
	RunPartialPass(Exam, Database, Partial);
	Report.Check(Partial.bPass, WithFailure(TEXT("EXAM_01 partial pass: 330 / C / retain"), Partial));
	Exam->AbortExam();

	// Next-cycle/rollover reset: month 12 -> month 1 starts a clean written section.
	Report.Check(Exam->StartExam(12, 9001, Error), FString::Printf(TEXT("month 12 starts: %s"), *Error));
	Report.Check(Exam->StartExam(1, 9002, Error), FString::Printf(TEXT("month 1 restarts after month 12: %s"), *Error));
	Report.Check(Exam->GetMonthIndex() == 1 && Exam->GetExamId() == TEXT("EXAM_01"), TEXT("rollover resets to EXAM_01"));
	Report.Check(Exam->GetPhase() == EDAExamPhase::Written, TEXT("rollover phase is Written"));
	Report.Check(Exam->GetAnsweredCount() == 0, TEXT("rollover clears written answers"));
	Report.Check(Exam->GetSelectedPuzzleId().IsEmpty(), TEXT("rollover clears the timed puzzle"));
	Report.Check(!Exam->HasResult(), TEXT("rollover clears the result"));
	Exam->AbortExam();
	Report.Check(Exam->GetPhase() == EDAExamPhase::None, TEXT("AbortExam returns to None"));
	Report.Check(Exam->GetMonthIndex() == 0, TEXT("AbortExam clears the month"));

	Report.Info(TEXT("12 cycles x (10/10 perfect + 6/10 failing) + one partial pass; timed puzzles solved through FDuelEngine"));
	Report.Info(TEXT("exam DP reward is data-driven (0 in current content; no canonical exam DP amount extracted)"));
	return Report;
}
