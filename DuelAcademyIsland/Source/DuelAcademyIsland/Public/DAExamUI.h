// Duel Academy Island - monthly exam screen (Canvas).
//
// UDAExamSubsystem owns selection, answers, scoring, phases and outcomes. This
// screen displays questions/objectives/result payloads and forwards input to
// SubmitWrittenAnswer / FinishWritten / BeginTimed / SubmitTimedResult /
// BeginPractical / FinishPractical / FinishExam.

#pragma once

#include "CoreMinimal.h"
#include "DAExamSubsystem.h"
#include "DAUIScreen.h"

DECLARE_MULTICAST_DELEGATE(FDAExamUIClosedSignature);

class FDAExamUI : public FDAUIScreen
{
public:
	explicit FDAExamUI(ADAHUD* InOwner);
	virtual ~FDAExamUI() override;

	/** MonthIndex is 1..12; 0 asks the calendar for the current school month. */
	void Open(int32 InMonthIndex = 0, int32 Seed = 0);
	void Close();
	bool IsOpen() const { return bOpen; }

	void Update(float DeltaSeconds);
	virtual void Draw(UCanvas* InCanvas) override;

	// Test/automation helpers. They call only UDAExamSubsystem APIs.
	void DebugAnswerAllWritten();
	void DebugResolveTimed(bool bSolved = true);
	void DebugFinishPractical();
	void DebugCompleteExam();

	const FDAExamResult& GetResult() const { return Result; }
	bool HasResult() const;
	int32 GetMonthIndex() const { return MonthIndex; }

	FDAExamUIClosedSignature OnClosed;

private:
	enum class EPanel : uint8
	{
		Written,
		WrittenDone,
		Timed,
		Practical,
		Result,
		Error
	};

	UDAExamSubsystem* GetExam() const;
	void SyncPanelFromPhase();
	void SubmitAnswer(int32 AnswerIndex);
	void StartTimed();
	void StartPractical();
	void FinishPracticalAndResult();
	void HandleClickAtMouse();
	void HandleHit(const FDAUIHitTarget& Hit);
	void SetStatus(const FString& Message, bool bError = false);

	FString GetMonthLabel() const;
	FString GetPhaseLabel() const;
	FString GetTimerLabel() const;
	FString GetGradeLabel() const;
	int32 GetOptionCount() const;

	void DrawHeader();
	void DrawWritten();
	void DrawWrittenDone();
	void DrawTimed();
	void DrawPractical();
	void DrawResult();
	void DrawError();
	void DrawFooter();
	void DrawStatus();
	void DrawOption(const FString& Label, int32 Index, float X, float Y, float W, float H, bool bSelected);
	void DrawButton(const FString& Label, const FString& Action, float X, float Y, float W, float H,
		bool bEnabled = true);

	UDAExamSubsystem* Exam = nullptr;
	EPanel Panel = EPanel::Written;
	int32 MonthIndex = 1;
	int32 AnswerSelection = 0;
	int32 HoveredAnswer = INDEX_NONE;
	bool bOpen = false;
	bool bOutcomeApplied = false;

	float Elapsed = 0.f;
	float StatusTime = 0.f;
	FString StatusMessage;
	bool bStatusError = false;

	FDAExamResult Result;
};
