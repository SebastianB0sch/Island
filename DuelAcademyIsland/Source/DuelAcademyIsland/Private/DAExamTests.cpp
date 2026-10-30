// Duel Academy Island - exam lifecycle/scoring automation tests.

#include "Misc/AutomationTest.h"
#include "DAExamSubsystem.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDAExamScoringTest, "DuelAcademy.Exams.Scoring",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FDAExamScoringTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	UDAExamSubsystem* Exam = NewObject<UDAExamSubsystem>(GetTransientPackage());
	if (!TestNotNull(TEXT("Exam subsystem created"), Exam))
	{
		return false;
	}
	FString Error;
	if (!TestTrue(TEXT("Exam data loads"), Exam->Reload(Error)))
	{
		AddError(Error);
		return false;
	}

	TestTrue(TEXT("Question bank has at least 30 questions"), Exam->GetQuestionBankSize() >= 30);
	TestEqual(TEXT("Seven practical objectives"), Exam->GetPracticalObjectives().Num(), 7);
	TestEqual(TEXT("Pass mark is 300"), Exam->GetPassMark(), 300);
	TestEqual(TEXT("Max points are 500"), Exam->GetMaxPoints(), 500);
	TestTrue(TEXT("Friday is an exam day"), Exam->IsExamDay(TEXT("Friday")));

	if (!TestTrue(TEXT("Exam 1 starts"), Exam->StartExam(1, 1234, Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("Exam id"), Exam->GetExamId(), FString(TEXT("EXAM_01")));
	TestEqual(TEXT("Ten questions selected"), Exam->GetQuestionCount(), 10);
	TestTrue(TEXT("Written phase"), Exam->GetPhase() == EDAExamPhase::Written);
	TestEqual(TEXT("Timed puzzle is deterministic"), Exam->PickTimedPuzzle(1), Exam->PickTimedPuzzle(1));

	for (const FString& QuestionId : Exam->GetCurrentQuestionIds())
	{
		const FDAExamQuestion* Question = Exam->GetQuestion(QuestionId);
		if (!TestNotNull(TEXT("Question data exists"), Question))
		{
			return false;
		}
		if (!TestTrue(TEXT("Correct answer accepted"), Exam->SubmitWrittenAnswer(QuestionId, Question->AnswerIndex, Error)))
		{
			AddError(Error);
			return false;
		}
	}
	TestEqual(TEXT("All questions answered"), Exam->GetAnsweredCount(), 10);
	TestEqual(TEXT("All questions correct"), Exam->GetCorrectAnswerCount(), 10);
	TestEqual(TEXT("Written points are 200"), Exam->GetWrittenPoints(), 200);

	if (!TestTrue(TEXT("Finish written"), Exam->FinishWritten(Error)))
	{
		AddError(Error);
		return false;
	}
	if (!TestTrue(TEXT("Begin timed"), Exam->BeginTimed(TEXT(""), Error)))
	{
		AddError(Error);
		return false;
	}
	TestFalse(TEXT("Timed puzzle selected"), Exam->GetSelectedPuzzleId().IsEmpty());
	if (!TestTrue(TEXT("Submit timed result"), Exam->SubmitTimedResult(true, 1, 20.f, Error)))
	{
		AddError(Error);
		return false;
	}
	if (!TestTrue(TEXT("Begin practical"), Exam->BeginPractical(Error)))
	{
		AddError(Error);
		return false;
	}
	Exam->RecordPracticalStats(3000, 3, 1, 1, 2, 3, 2);
	TestEqual(TEXT("All practical objectives complete"), Exam->GetPracticalProgress().Num(), 7);
	TestEqual(TEXT("Practical points are 200"), Exam->GetPracticalPoints(), 200);
	if (!TestTrue(TEXT("Finish practical"), Exam->FinishPractical(Error)))
	{
		AddError(Error);
		return false;
	}

	FDAExamResult Result;
	if (!TestTrue(TEXT("Finish exam"), Exam->FinishExam(Result, Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("Perfect score is 500"), Result.TotalPoints, 500);
	TestTrue(TEXT("Perfect exam passes"), Result.bPassed);
	TestEqual(TEXT("Grade is S"), Result.Grade, FString(TEXT("S")));
	TestEqual(TEXT("All seven objectives completed"), Result.CompletedObjectives.Num(), 7);
	TestTrue(TEXT("Practical passed flag"), Result.Flags.Contains(FString(TEXT("practical_passed"))));
	TestTrue(TEXT("Exam passed flag"), Result.Flags.Contains(FString(TEXT("exam_passed"))));

	// Fail path, including a new exam reset.
	if (!TestTrue(TEXT("Exam 2 starts"), Exam->StartExam(2, 99, Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("Exam 2 id"), Exam->GetExamId(), FString(TEXT("EXAM_02")));
	TestEqual(TEXT("Exam 2 has ten questions"), Exam->GetQuestionCount(), 10);
	TestTrue(TEXT("Finish empty written"), Exam->FinishWritten(Error));
	TestTrue(TEXT("Begin timed 2"), Exam->BeginTimed(TEXT(""), Error));
	TestTrue(TEXT("Fail timed"), Exam->SubmitTimedResult(false, 10, 60.f, Error));
	TestTrue(TEXT("Begin practical 2"), Exam->BeginPractical(Error));
	TestTrue(TEXT("Finish empty practical"), Exam->FinishPractical(Error));
	FDAExamResult Failed;
	if (!TestTrue(TEXT("Finish failed exam"), Exam->FinishExam(Failed, Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("Failed score is 0"), Failed.TotalPoints, 0);
	TestFalse(TEXT("Failed exam does not pass"), Failed.bPassed);
	TestEqual(TEXT("Failed grade is F"), Failed.Grade, FString(TEXT("F")));
	TestTrue(TEXT("Dropout Boy flag"), Failed.Flags.Contains(FString(TEXT("dropout_boy"))));
	TestTrue(TEXT("Exam failed flag"), Failed.Flags.Contains(FString(TEXT("exam_failed"))));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

