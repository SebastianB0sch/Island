// Duel Academy Island - monthly exam implementation.

#include "DAExamUI.h"

#include "DACalendarSubsystem.h"
#include "DuelAcademyIsland.h"
#include "Engine/Canvas.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"

namespace
{
	const FLinearColor ExamGold(1.f, 0.78f, 0.25f);
	const FLinearColor ExamInk(0.008f, 0.014f, 0.028f);
	const FLinearColor ExamPaper(0.95f, 0.95f, 0.97f);
	const FLinearColor ExamMuted(0.58f, 0.63f, 0.72f);
	const FLinearColor ExamCyan(0.35f, 0.82f, 0.92f);
	const FLinearColor ExamGreen(0.42f, 0.82f, 0.48f);
	const FLinearColor ExamRed(0.90f, 0.28f, 0.24f);
	const FLinearColor ExamPurple(0.72f, 0.44f, 0.95f);

	FLinearColor ExamAlpha(FLinearColor C, float A)
	{
		C.A = A;
		return C;
	}
}

FDAExamUI::FDAExamUI(ADAHUD* InOwner)
	: FDAUIScreen(InOwner)
{
}

FDAExamUI::~FDAExamUI() = default;

UDAExamSubsystem* FDAExamUI::GetExam() const
{
	UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetSubsystem<UDAExamSubsystem>() : nullptr;
}

void FDAExamUI::Open(int32 InMonthIndex, int32 Seed)
{
	bOpen = true;
	Elapsed = 0.f;
	AnswerSelection = 0;
	HoveredAnswer = INDEX_NONE;
	StatusMessage.Reset();
	StatusTime = 0.f;
	bStatusError = false;
	Exam = GetExam();
	if (!Exam)
	{
		Panel = EPanel::Error;
		SetStatus(TEXT("Exam subsystem unavailable."), true);
		return;
	}

	MonthIndex = InMonthIndex;
	if (MonthIndex <= 0)
	{
		if (UDACalendarSubsystem* Calendar = GetGameInstance() ? GetGameInstance()->GetSubsystem<UDACalendarSubsystem>() : nullptr)
		{
			MonthIndex = Calendar->GetMonthIndex() + 1;
		}
	}
	MonthIndex = FMath::Clamp(MonthIndex, 1, 12);

	const EDAExamPhase Phase = Exam->GetPhase();
	if (Phase == EDAExamPhase::None || Phase == EDAExamPhase::Finished)
	{
		FString Error;
		if (!Exam->StartExam(MonthIndex, Seed != 0 ? Seed : FMath::Rand(), Error))
		{
			Panel = EPanel::Error;
			SetStatus(Error.IsEmpty() ? TEXT("Could not start the exam.") : Error, true);
			return;
		}
	}
	else if (Exam->GetMonthIndex() > 0)
	{
		MonthIndex = Exam->GetMonthIndex();
	}

	if (Exam->HasResult())
	{
		Result = Exam->GetResult();
	}
	SyncPanelFromPhase();
	PlaySfx(TEXT("A_UIClick"), 0.45f);
}

void FDAExamUI::Close()
{
	if (!bOpen)
	{
		return;
	}
	bOpen = false;
	HitTargets.Reset();
	OnClosed.Broadcast();
}

void FDAExamUI::SyncPanelFromPhase()
{
	if (!Exam)
	{
		Panel = EPanel::Error;
		return;
	}
	switch (Exam->GetPhase())
	{
	case EDAExamPhase::Written:       Panel = EPanel::Written; break;
	case EDAExamPhase::WrittenDone:   Panel = EPanel::WrittenDone; break;
	case EDAExamPhase::Timed:
	case EDAExamPhase::TimedDone:     Panel = EPanel::Timed; break;
	case EDAExamPhase::Practical:
	case EDAExamPhase::PracticalDone: Panel = EPanel::Practical; break;
	case EDAExamPhase::Finished:      Panel = EPanel::Result; break;
	case EDAExamPhase::None:
	default:                          Panel = EPanel::Error; break;
	}
	if (Exam->HasResult())
	{
		Result = Exam->GetResult();
	}
}

bool FDAExamUI::HasResult() const
{
	return Exam && Exam->HasResult();
}

void FDAExamUI::SetStatus(const FString& Message, bool bError)
{
	StatusMessage = Message;
	StatusTime = 5.f;
	bStatusError = bError;
}

FString FDAExamUI::GetMonthLabel() const
{
	if (UDACalendarSubsystem* Calendar = GetGameInstance() ? GetGameInstance()->GetSubsystem<UDACalendarSubsystem>() : nullptr)
	{
		return Calendar->GetMonthName(FMath::Clamp(MonthIndex - 1, 0, 11));
	}
	return FString::Printf(TEXT("Month %d"), MonthIndex);
}

FString FDAExamUI::GetPhaseLabel() const
{
	return Exam ? FString::Printf(TEXT("PHASE %d"), static_cast<int32>(Exam->GetPhase())) : FString(TEXT("NO EXAM"));
}

FString FDAExamUI::GetTimerLabel() const
{
	const int32 Total = FMath::Max(0, FMath::FloorToInt(Elapsed));
	return FString::Printf(TEXT("%02d:%02d"), Total / 60, Total % 60);
}

FString FDAExamUI::GetGradeLabel() const
{
	return Result.Grade.IsEmpty() ? FString(TEXT("-")) : Result.Grade;
}

int32 FDAExamUI::GetOptionCount() const
{
	if (!Exam)
	{
		return 0;
	}
	const FDAExamQuestion* Question = Exam->GetCurrentQuestion();
	return Question ? Question->Options.Num() : 0;
}

void FDAExamUI::SubmitAnswer(int32 AnswerIndex)
{
	if (!Exam)
	{
		return;
	}
	const FDAExamQuestion* Question = Exam->GetCurrentQuestion();
	if (!Question)
	{
		FString Error;
		if (Exam->FinishWritten(Error))
		{
			SyncPanelFromPhase();
			SetStatus(TEXT("Written section complete."), false);
		}
		else
		{
			SetStatus(Error, true);
		}
		return;
	}
	if (!Question->Options.IsValidIndex(AnswerIndex))
	{
		return;
	}
	FString Error;
	if (!Exam->SubmitWrittenAnswer(Question->Id, AnswerIndex, Error))
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not submit the answer.") : Error, true);
		return;
	}
	AnswerSelection = 0;
	PlaySfx(TEXT("A_UIClick"), 0.35f);
	if (Exam->GetCurrentQuestionIndex() >= Exam->GetQuestionCount())
	{
		if (Exam->FinishWritten(Error))
		{
			SyncPanelFromPhase();
			SetStatus(TEXT("Written section complete."), false);
		}
		else
		{
			SetStatus(Error, true);
		}
	}
}

void FDAExamUI::StartTimed()
{
	if (!Exam)
	{
		return;
	}
	FString Error;
	if (Exam->BeginTimed(Exam->PickTimedPuzzle(MonthIndex), Error))
	{
		SyncPanelFromPhase();
		SetStatus(TEXT("Timed puzzle selected."), false);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not start the timed section.") : Error, true);
	}
}

void FDAExamUI::StartPractical()
{
	if (!Exam)
	{
		return;
	}
	FString Error;
	if (Exam->BeginPractical(Error))
	{
		SyncPanelFromPhase();
		SetStatus(TEXT("Practical section started."), false);
	}
	else
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not start the practical.") : Error, true);
	}
}

void FDAExamUI::FinishPracticalAndResult()
{
	if (!Exam)
	{
		return;
	}
	FString Error;
	if (Exam->GetPhase() == EDAExamPhase::Practical)
	{
		if (!Exam->FinishPractical(Error))
		{
			SetStatus(Error.IsEmpty() ? TEXT("Could not finish the practical.") : Error, true);
			return;
		}
	}
	FDAExamResult OutResult;
	if (!Exam->FinishExam(OutResult, Error))
	{
		SetStatus(Error.IsEmpty() ? TEXT("Could not finish the exam.") : Error, true);
		return;
	}
	Result = OutResult;
	Panel = EPanel::Result;
	PlaySfx(TEXT("A_UIClick"), 0.7f);
}

void FDAExamUI::DebugAnswerAllWritten()
{
	if (!Exam || Exam->GetPhase() != EDAExamPhase::Written)
	{
		return;
	}
	for (const FString& QuestionId : Exam->GetCurrentQuestionIds())
	{
		if (const FDAExamQuestion* Question = Exam->GetQuestion(QuestionId))
		{
			FString Error;
			Exam->SubmitWrittenAnswer(QuestionId, Question->AnswerIndex, Error);
		}
	}
	FString Error;
	Exam->FinishWritten(Error);
	SyncPanelFromPhase();
}

void FDAExamUI::DebugResolveTimed(bool bSolved)
{
	if (!Exam)
	{
		return;
	}
	if (Exam->GetPhase() == EDAExamPhase::WrittenDone)
	{
		StartTimed();
	}
	if (Exam->GetPhase() == EDAExamPhase::Timed)
	{
		FString Error;
		Exam->SubmitTimedResult(bSolved, bSolved ? 1 : 0, bSolved ? 4.f : 0.f, Error);
		SyncPanelFromPhase();
	}
}

void FDAExamUI::DebugFinishPractical()
{
	if (!Exam)
	{
		return;
	}
	if (Exam->GetPhase() == EDAExamPhase::TimedDone)
	{
		StartPractical();
	}
	if (Exam->GetPhase() == EDAExamPhase::Practical)
	{
		Exam->RecordPracticalStats(3000, 2, 1, 1, 1, 4, 2);
	}
	if (Exam->GetPhase() == EDAExamPhase::Practical)
	{
		FinishPracticalAndResult();
	}
	else if (Exam->GetPhase() == EDAExamPhase::PracticalDone)
	{
		FinishPracticalAndResult();
	}
}

void FDAExamUI::DebugCompleteExam()
{
	DebugAnswerAllWritten();
	DebugResolveTimed(true);
	DebugFinishPractical();
}

void FDAExamUI::Update(float DeltaSeconds)
{
	if (!bOpen)
	{
		return;
	}
	PlayerOwner = GetPlayerController();
	Elapsed += DeltaSeconds;
	if (StatusTime > 0.f)
	{
		StatusTime -= DeltaSeconds;
		if (StatusTime <= 0.f)
		{
			StatusTime = 0.f;
			StatusMessage.Reset();
		}
	}
	Exam = GetExam();

	HoveredAnswer = INDEX_NONE;
	FVector2D Mouse;
	if (GetMousePosition(Mouse))
	{
		for (const FDAUIHitTarget& Hit : HitTargets)
		{
			if (Hit.Action == TEXT("answer") && Hit.Contains(Mouse))
			{
				HoveredAnswer = Hit.Index;
			}
		}
	}

	if (!PlayerOwner)
	{
		return;
	}
	if (PlayerOwner->WasInputKeyJustPressed(EKeys::Escape) || PlayerOwner->WasInputKeyJustPressed(EKeys::P)
		|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right))
	{
		Close();
		return;
	}
	if (!Exam)
	{
		Panel = EPanel::Error;
		return;
	}

	const EDAExamPhase Phase = Exam->GetPhase();
	if (Panel == EPanel::Result)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
		{
			Close();
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}
	if (Panel == EPanel::Error)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}
	if (Panel == EPanel::Written && Phase == EDAExamPhase::Written)
	{
		const FDAExamQuestion* Question = Exam->GetCurrentQuestion();
		const int32 Options = Question ? Question->Options.Num() : 0;
		if (Options > 0)
		{
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::Up) || PlayerOwner->WasInputKeyJustPressed(EKeys::W))
			{
				AnswerSelection = (AnswerSelection - 1 + Options) % Options;
			}
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::Down) || PlayerOwner->WasInputKeyJustPressed(EKeys::S))
			{
				AnswerSelection = (AnswerSelection + 1) % Options;
			}
			static const FKey NumberKeys[] = { EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four };
			for (int32 Index = 0; Index < UE_ARRAY_COUNT(NumberKeys) && Index < Options; ++Index)
			{
				if (PlayerOwner->WasInputKeyJustPressed(NumberKeys[Index]))
				{
					AnswerSelection = Index;
				}
			}
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))
		{
			SubmitAnswer(AnswerSelection);
			return;
		}
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}
	if (Panel == EPanel::WrittenDone && Phase == EDAExamPhase::WrittenDone)
	{
		if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)
			|| PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			StartTimed();
		}
		return;
	}
	if (Panel == EPanel::Timed)
	{
		if (Phase == EDAExamPhase::TimedDone)
		{
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
				|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)
				|| PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
			{
				StartPractical();
			}
		}
		else if (PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
		{
			HandleClickAtMouse();
		}
		return;
	}
	if (Panel == EPanel::Practical)
	{
		if (Phase == EDAExamPhase::Practical)
		{
			if (PlayerOwner->WasInputKeyJustPressed(EKeys::Enter) || PlayerOwner->WasInputKeyJustPressed(EKeys::SpaceBar)
				|| PlayerOwner->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)
				|| PlayerOwner->WasInputKeyJustPressed(EKeys::LeftMouseButton))
			{
				FinishPracticalAndResult();
			}
		}
		else if (Phase == EDAExamPhase::PracticalDone)
		{
			FinishPracticalAndResult();
		}
		return;
	}
}

void FDAExamUI::HandleClickAtMouse()
{
	FVector2D Mouse;
	if (!GetMousePosition(Mouse))
	{
		return;
	}
	for (int32 Index = HitTargets.Num() - 1; Index >= 0; --Index)
	{
		if (HitTargets[Index].Contains(Mouse))
		{
			HandleHit(HitTargets[Index]);
			return;
		}
	}
}

void FDAExamUI::HandleHit(const FDAUIHitTarget& Hit)
{
	if (Hit.Action == TEXT("answer"))
	{
		AnswerSelection = Hit.Index;
		PlaySfx(TEXT("A_UIClick"), 0.22f);
	}
	else if (Hit.Action == TEXT("submit"))
	{
		SubmitAnswer(AnswerSelection);
	}
	else if (Hit.Action == TEXT("finish_written"))
	{
		FString Error;
		if (Exam && Exam->FinishWritten(Error))
		{
			SyncPanelFromPhase();
		}
	}
	else if (Hit.Action == TEXT("begin_timed"))
	{
		StartTimed();
	}
	else if (Hit.Action == TEXT("skip_timed"))
	{
		if (Exam && Exam->GetPhase() == EDAExamPhase::Timed)
		{
			FString Error;
			Exam->SubmitTimedResult(false, 0, 0.f, Error);
			SyncPanelFromPhase();
		}
	}
	else if (Hit.Action == TEXT("begin_practical"))
	{
		StartPractical();
	}
	else if (Hit.Action == TEXT("finish_practical"))
	{
		FinishPracticalAndResult();
	}
	else if (Hit.Action == TEXT("close"))
	{
		Close();
	}
}

void FDAExamUI::Draw(UCanvas* InCanvas)
{
	if (!bOpen || !InCanvas)
	{
		return;
	}
	BeginFrame(InCanvas);
	DrawRect(FLinearColor(ExamInk.R, ExamInk.G, ExamInk.B, 0.97f), 0.f, 0.f, Canvas->ClipX, Canvas->ClipY);
	DrawHeader();
	switch (Panel)
	{
	case EPanel::Written:     DrawWritten(); break;
	case EPanel::WrittenDone: DrawWrittenDone(); break;
	case EPanel::Timed:       DrawTimed(); break;
	case EPanel::Practical:   DrawPractical(); break;
	case EPanel::Result:      DrawResult(); break;
	case EPanel::Error:       DrawError(); break;
	default:                  DrawError(); break;
	}
	DrawFooter();
	DrawStatus();
}

void FDAExamUI::DrawHeader()
{
	const float CW = Canvas->ClipX;
	const float S = UIScale;
	const float H = 78.f * S;
	DrawRect(FLinearColor(0.004f, 0.009f, 0.02f, 0.96f), 0.f, 0.f, CW, H);
	DrawRect(ExamAlpha(ExamGold, 0.55f), 0.f, H - 2.f * S, CW, 2.f * S);
	DrawText(TEXT("MONTHLY EXAM"), 28.f * S, 10.f * S, ExamGold, 1.55f, false, GetFont(true));
	DrawText(GetMonthLabel(), 28.f * S, 46.f * S, ExamPaper, 0.86f);
	DrawText(GetPhaseLabel(), CW * 0.42f, 16.f * S, ExamMuted, 0.75f);
	DrawText(FString::Printf(TEXT("TIME %s"), *GetTimerLabel()), CW - 170.f * S, 16.f * S, ExamCyan, 0.8f);
	if (Exam && Exam->GetQuestionCount() > 0)
	{
		DrawText(FString::Printf(TEXT("Q %d / %d"), FMath::Min(Exam->GetCurrentQuestionIndex() + 1, Exam->GetQuestionCount()),
			Exam->GetQuestionCount()), CW - 170.f * S, 44.f * S, ExamMuted, 0.7f);
	}
}

void FDAExamUI::DrawWritten()
{
	const float S = UIScale;
	const float W = FMath::Min(Canvas->ClipX * 0.72f, 1180.f * S);
	const float X = (Canvas->ClipX - W) * 0.5f;
	const float Y = 112.f * S;
	const FDAExamQuestion* Question = Exam ? Exam->GetCurrentQuestion() : nullptr;

	DrawPanel(X, Y, W, Canvas->ClipY - Y - 52.f * S, ExamAlpha(ExamInk, 0.94f), ExamAlpha(ExamGold, 0.8f));
	if (!Question)
	{
		DrawText(TEXT("All questions answered."), X + 32.f * S, Y + 32.f * S, ExamGold, 1.35f, false, GetFont(true));
		DrawText(TEXT("Press ENTER to finish the written section."), X + 32.f * S, Y + 80.f * S, ExamMuted, 0.85f);
		DrawButton(TEXT("FINISH WRITTEN"), TEXT("finish_written"), X + 32.f * S, Y + 136.f * S, 280.f * S, 44.f * S);
		return;
	}

	DrawText(FString::Printf(TEXT("QUESTION %d OF %d"), Exam->GetCurrentQuestionIndex() + 1, Exam->GetQuestionCount()),
		X + 32.f * S, Y + 24.f * S, ExamGold, 0.9f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("%s  -  DIFFICULTY %d"), *Question->Topic, Question->Difficulty),
		X + 32.f * S, Y + 56.f * S, ExamMuted, 0.72f);
	DrawRect(ExamAlpha(ExamGold, 0.35f), X + 32.f * S, Y + 84.f * S, W - 64.f * S, 1.f * S);

	float TextY = Y + 102.f * S;
	for (const FString& Line : WrapText(Question->Text, W - 64.f * S, 0.95f))
	{
		DrawText(Line, X + 32.f * S, TextY, ExamPaper, 0.95f);
		TextY += Measure(TEXT("Ag"), 0.95f).Y + 4.f * S;
	}

	const float OptionsTop = TextY + 18.f * S;
	const float OptionH = 42.f * S;
	for (int32 Index = 0; Index < Question->Options.Num(); ++Index)
	{
		DrawOption(Question->Options[Index], Index, X + 32.f * S,
			OptionsTop + Index * (OptionH + 8.f * S), W - 64.f * S, OptionH, Index == AnswerSelection);
	}
	DrawText(FString::Printf(TEXT("ANSWERED %d / %d"), Exam->GetAnsweredCount(), Exam->GetQuestionCount()),
		X + 32.f * S, Canvas->ClipY - 146.f * S, ExamMuted, 0.72f);
	DrawButton(TEXT("SUBMIT ANSWER"), TEXT("submit"), X + W - 260.f * S, Canvas->ClipY - 158.f * S,
		220.f * S, 44.f * S, Question->Options.Num() > 0);
}

void FDAExamUI::DrawWrittenDone()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float W = FMath::Min(CW * 0.56f, 860.f * S);
	const float X = (CW - W) * 0.5f;
	const float Y = 170.f * S;
	DrawPanel(X, Y, W, 430.f * S, ExamAlpha(ExamInk, 0.95f), ExamGreen);
	DrawText(TEXT("WRITTEN SECTION COMPLETE"), X + 28.f * S, Y + 22.f * S, ExamGreen, 1.35f, false, GetFont(true));
	const int32 Correct = Exam ? Exam->GetCorrectAnswerCount() : 0;
	const int32 Points = Exam ? Exam->GetWrittenPoints() : 0;
	DrawText(FString::Printf(TEXT("CORRECT %d / %d"), Correct, Exam ? Exam->GetQuestionCount() : 10),
		X + 30.f * S, Y + 80.f * S, ExamPaper, 1.0f);
	DrawText(FString::Printf(TEXT("WRITTEN POINTS %d"), Points), X + 30.f * S, Y + 114.f * S, ExamGold, 0.9f);
	DrawText(TEXT("Next: timed puzzle. The puzzle duel itself is wired by A04/A07 in a later pass."),
		X + 30.f * S, Y + 166.f * S, ExamMuted, 0.78f);
	DrawButton(TEXT("BEGIN TIMED DUEL"), TEXT("begin_timed"), X + 30.f * S, Y + 230.f * S, 300.f * S, 48.f * S);
}

void FDAExamUI::DrawTimed()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float W = FMath::Min(CW * 0.58f, 900.f * S);
	const float X = (CW - W) * 0.5f;
	const float Y = 166.f * S;
	const bool bDone = Exam && Exam->GetPhase() == EDAExamPhase::TimedDone;
	DrawPanel(X, Y, W, 430.f * S, ExamAlpha(ExamInk, 0.95f), bDone ? ExamGreen : ExamCyan);
	DrawText(bDone ? TEXT("TIMED PUZZLE RECORDED") : TEXT("TIMED PUZZLE"),
		X + 28.f * S, Y + 22.f * S, bDone ? ExamGreen : ExamCyan, 1.35f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("PUZZLE %s"), Exam ? *Exam->GetSelectedPuzzleId() : TEXT("-")),
		X + 30.f * S, Y + 80.f * S, ExamPaper, 1.0f);
	DrawText(FString::Printf(TEXT("TURN LIMIT %d   TIME LIMIT %d s"),
		Exam ? Exam->GetPracticalTurnLimit() : 0, Exam ? Exam->GetPracticalTimeLimit() : 0),
		X + 30.f * S, Y + 114.f * S, ExamMuted, 0.78f);
	if (bDone)
	{
		DrawText(TEXT("STATUS: RESULT RECORDED"), X + 30.f * S, Y + 166.f * S, ExamGreen, 0.9f);
		DrawButton(TEXT("BEGIN PRACTICAL"), TEXT("begin_practical"), X + 30.f * S, Y + 230.f * S, 300.f * S, 48.f * S);
	}
	else
	{
		DrawText(TEXT("The timed puzzle duel is launched by A04/A07. This shell waits for its result."),
			X + 30.f * S, Y + 166.f * S, ExamMuted, 0.78f);
		DrawText(TEXT("For the current build, CONTINUE WITHOUT CLEARING records a failed timed section."),
			X + 30.f * S, Y + 198.f * S, ExamMuted, 0.72f);
		DrawButton(TEXT("CONTINUE WITHOUT CLEARING (0)"), TEXT("skip_timed"), X + 30.f * S, Y + 246.f * S,
			380.f * S, 46.f * S);
	}
}

void FDAExamUI::DrawPractical()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float W = FMath::Min(CW * 0.68f, 1080.f * S);
	const float X = (CW - W) * 0.5f;
	const float Y = 112.f * S;
	const float H = Canvas->ClipY - Y - 52.f * S;
	DrawPanel(X, Y, W, H, ExamAlpha(ExamInk, 0.94f), ExamGold);
	DrawText(TEXT("PRACTICAL EXAM"), X + 28.f * S, Y + 20.f * S, ExamGold, 1.35f, false, GetFont(true));
	DrawText(FString::Printf(TEXT("OPPONENT %s   DECK %s   LP %d"),
		Exam ? *Exam->GetPracticalOpponent() : TEXT("-"), Exam ? *Exam->GetPracticalDeck() : TEXT("-"),
		Exam ? Exam->GetPracticalOpponentLp() : 8000), X + 30.f * S, Y + 58.f * S, ExamMuted, 0.76f);
	DrawText(FString::Printf(TEXT("TURN LIMIT %d   TIME LIMIT %d s   POINTS %d"),
		Exam ? Exam->GetPracticalTurnLimit() : 0, Exam ? Exam->GetPracticalTimeLimit() : 0,
		Exam ? Exam->GetPracticalPoints() : 0), X + 30.f * S, Y + 82.f * S, ExamMuted, 0.72f);

	const TArray<FDAExamPracticalProgress>* Progress = Exam ? &Exam->GetPracticalProgress() : nullptr;
	float RY = Y + 122.f * S;
	if (Progress && Progress->Num() > 0)
	{
		for (const FDAExamPracticalProgress& Row : *Progress)
		{
			DrawRect(ExamAlpha(Row.bComplete ? ExamGreen : ExamMuted, 0.1f), X + 30.f * S, RY, W - 60.f * S, 36.f * S);
			DrawText(Row.Label, X + 42.f * S, RY + 7.f * S, Row.bComplete ? ExamGreen : ExamPaper, 0.78f);
			DrawText(FString::Printf(TEXT("%d / %d   +%d"), Row.Progress, Row.Target, Row.AwardedPoints),
				X + W - 190.f * S, RY + 7.f * S, Row.bComplete ? ExamGreen : ExamMuted, 0.72f);
			RY += 42.f * S;
		}
	}
	else if (Exam)
	{
		for (const FDAExamPracticalObjective& Objective : Exam->GetPracticalObjectives())
		{
			DrawText(FString::Printf(TEXT("%s   TARGET %d   +%d PTS"), *Objective.Label, Objective.Target, Objective.Points),
				X + 42.f * S, RY + 7.f * S, ExamMuted, 0.74f);
			RY += 32.f * S;
		}
	}

	DrawButton(TEXT("FINISH PRACTICAL"), TEXT("finish_practical"), X + 30.f * S, Y + H - 72.f * S,
		300.f * S, 46.f * S);
}

void FDAExamUI::DrawResult()
{
	const float S = UIScale;
	if (Exam && Exam->HasResult())
	{
		Result = Exam->GetResult();
	}
	const float CW = Canvas->ClipX;
	const float W = FMath::Min(CW * 0.66f, 1000.f * S);
	const float X = (CW - W) * 0.5f;
	const float Y = 100.f * S;
	const float H = Canvas->ClipY - Y - 52.f * S;
	const FLinearColor Accent = Result.bPassed ? ExamGreen : ExamRed;
	DrawPanel(X, Y, W, H, ExamAlpha(ExamInk, 0.96f), Accent);
	DrawText(TEXT("EXAM RESULT"), X + 28.f * S, Y + 18.f * S, Accent, 1.45f, false, GetFont(true));
	DrawText(Result.bPassed ? TEXT("PASS") : TEXT("FAIL"), X + W - 140.f * S, Y + 20.f * S, Accent, 1.2f, false, GetFont(true));

	float RY = Y + 70.f * S;
	const float RowH = 34.f * S;
	auto Row = [&](const FString& Label, const FString& Value, const FLinearColor& Color)
	{
		DrawText(Label, X + 30.f * S, RY, ExamMuted, 0.8f);
		DrawText(Value, X + W * 0.55f, RY, Color, 0.8f);
		RY += RowH;
	};
	Row(TEXT("WRITTEN"), FString::Printf(TEXT("%d correct  /  %d points"), Result.WrittenCorrect, Result.WrittenPoints), ExamPaper);
	Row(TEXT("TIMED"), Result.bTimedSolved ? FString::Printf(TEXT("SOLVED  /  %d points"), Result.TimedPoints)
		: FString(TEXT("NOT CLEARED  /  0 points")), Result.bTimedSolved ? ExamGreen : ExamRed);
	Row(TEXT("PRACTICAL"), FString::Printf(TEXT("%d points"), Result.PracticalPoints), ExamPaper);
	Row(TEXT("TOTAL"), FString::Printf(TEXT("%d / %d"), Result.TotalPoints, Exam ? Exam->GetMaxPoints() : 500), ExamGold);
	Row(TEXT("GRADE"), GetGradeLabel(), ExamGold);
	Row(TEXT("TITLE OUTCOME"), Result.TitleOutcome, ExamMuted);
	Row(TEXT("DORM OUTCOME"), Result.DormOutcome, ExamMuted);

	DrawRect(ExamAlpha(Accent, 0.35f), X + 30.f * S, RY, W - 60.f * S, 1.f * S);
	RY += 18.f * S;
	DrawText(TEXT("OBJECTIVES"), X + 30.f * S, RY, ExamGold, 0.82f);
	RY += 28.f * S;
	for (const FString& Objective : Result.CompletedObjectives)
	{
		DrawText(FString::Printf(TEXT("PASS  %s"), *Objective), X + 42.f * S, RY, ExamGreen, 0.72f);
		RY += 24.f * S;
	}
	for (const FString& Objective : Result.FailedObjectives)
	{
		DrawText(FString::Printf(TEXT("FAIL  %s"), *Objective), X + 42.f * S, RY, ExamRed, 0.72f);
		RY += 24.f * S;
	}
	DrawButton(TEXT("CLOSE"), TEXT("close"), X + W - 220.f * S, Y + H - 62.f * S, 190.f * S, 42.f * S);
}

void FDAExamUI::DrawError()
{
	const float S = UIScale;
	const float CW = Canvas->ClipX;
	const float W = FMath::Min(CW * 0.5f, 760.f * S);
	const float X = (CW - W) * 0.5f;
	const float Y = 200.f * S;
	DrawPanel(X, Y, W, 240.f * S, ExamAlpha(ExamInk, 0.95f), ExamRed);
	DrawText(TEXT("EXAM UNAVAILABLE"), X + 24.f * S, Y + 20.f * S, ExamRed, 1.3f, false, GetFont(true));
	DrawText(StatusMessage.IsEmpty() ? TEXT("The exam subsystem did not start.") : StatusMessage,
		X + 24.f * S, Y + 76.f * S, ExamPaper, 0.85f);
	DrawButton(TEXT("CLOSE"), TEXT("close"), X + 24.f * S, Y + 160.f * S, 190.f * S, 42.f * S);
}

void FDAExamUI::DrawOption(const FString& Label, int32 Index, float X, float Y, float W, float H, bool bSelected)
{
	const float S = UIScale;
	const bool bHovered = Index == HoveredAnswer;
	if (bSelected || bHovered)
	{
		DrawRect(ExamAlpha(ExamGold, bSelected ? 0.22f : 0.08f), X, Y, W, H);
		DrawRect(ExamGold, X, Y, 4.f * S, H);
	}
	DrawText(FString::Printf(TEXT("%d.  %s"), Index + 1, *Label), X + 16.f * S, Y + 8.f * S,
		bSelected ? ExamPaper : ExamMuted, 0.82f);
	AddHit(TEXT("answer"), Index, X, Y, W, H);
}

void FDAExamUI::DrawButton(const FString& Label, const FString& Action, float X, float Y, float W, float H, bool bEnabled)
{
	const float S = UIScale;
	const FLinearColor Accent = bEnabled ? ExamGold : ExamMuted;
	DrawRect(ExamAlpha(Accent, bEnabled ? 0.2f : 0.08f), X, Y, W, H);
	DrawRect(Accent, X, Y, 4.f * S, H);
	DrawText(Label, X + 16.f * S, Y + 8.f * S, bEnabled ? ExamPaper : ExamMuted, 0.78f);
	if (bEnabled)
	{
		AddHit(Action, INDEX_NONE, X, Y, W, H);
	}
}

void FDAExamUI::DrawFooter()
{
	const float S = UIScale;
	const float CH = Canvas->ClipY;
	const float H = 30.f * S;
	DrawRect(FLinearColor(0.004f, 0.008f, 0.018f, 0.94f), 0.f, CH - H, Canvas->ClipX, H);
	FString Hint = TEXT("ESC / P close exam");
	switch (Panel)
	{
	case EPanel::Written:
		Hint = TEXT("UP/DOWN or 1-4 choose   ENTER submit   ESC close");
		break;
	case EPanel::WrittenDone:
		Hint = TEXT("ENTER begin timed section   ESC close");
		break;
	case EPanel::Timed:
		Hint = TEXT("Wait for puzzle result or continue without clearing   ESC close");
		break;
	case EPanel::Practical:
		Hint = TEXT("ENTER finish practical   ESC close");
		break;
	case EPanel::Result:
		Hint = TEXT("ENTER / ESC close");
		break;
	default:
		break;
	}
	DrawText(Hint, 20.f * S, CH - H + 7.f * S, ExamMuted, 0.68f);
}

void FDAExamUI::DrawStatus()
{
	if (StatusMessage.IsEmpty() || !Canvas)
	{
		return;
	}
	const float S = UIScale;
	const float W = FMath::Min(Canvas->ClipX * 0.6f, 900.f * S);
	const float H = 40.f * S;
	const float X = 20.f * S;
	const float Y = Canvas->ClipY - 84.f * S;
	DrawRect(ExamAlpha(ExamInk, 0.94f), X, Y, W, H);
	DrawRect(bStatusError ? ExamRed : ExamGold, X, Y, 4.f * S, H);
	FString Message = StatusMessage;
	while (Message.Len() > 4 && Measure(Message, 0.76f).X > W - 30.f * S)
	{
		Message = Message.LeftChop(4) + TEXT("...");
	}
	DrawText(Message, X + 14.f * S, Y + 8.f * S, bStatusError ? ExamRed : ExamPaper, 0.76f);
}
