// Duel Academy Island - frozen duel request/result contract (v1).
//
// This header is the integration reference for A04 (engine), A02 (DP/titles),
// A03 (story outcomes), A07 (opponents/exams/puzzles) and A09 (result screens).
// Copy it into Source/DuelAcademyIsland/Public/ when a lane needs the types;
// A10 owns changes to the field layout.
//
// JSON mirror: Docs/Contracts/schemas/duel-request.schema.json
//              Docs/Contracts/schemas/duel-result.schema.json
//
// Mode strings are deliberately stable and lowercase:
//   "story" | "free" | "tutorial" | "exam_timed" | "exam_practical" | "puzzle" | "ante"

#pragma once

#include "CoreMinimal.h"
#include "DADuelContract.generated.h"

UENUM(BlueprintType)
enum class EDuelMode : uint8
{
	Story          UMETA(DisplayName = "Story"),
	Free           UMETA(DisplayName = "Free Duel"),
	Tutorial       UMETA(DisplayName = "Tutorial"),
	ExamTimed      UMETA(DisplayName = "Exam - Timed"),
	ExamPractical  UMETA(DisplayName = "Exam - Practical"),
	Puzzle         UMETA(DisplayName = "Puzzle"),
	Ante           UMETA(DisplayName = "Ante")
};

namespace DuelModes
{
	inline const TCHAR* Story         = TEXT("story");
	inline const TCHAR* Free          = TEXT("free");
	inline const TCHAR* Tutorial      = TEXT("tutorial");
	inline const TCHAR* ExamTimed     = TEXT("exam_timed");
	inline const TCHAR* ExamPractical = TEXT("exam_practical");
	inline const TCHAR* Puzzle        = TEXT("puzzle");
	inline const TCHAR* Ante          = TEXT("ante");

	inline const TCHAR* ToString(EDuelMode Mode)
	{
		switch (Mode)
		{
		case EDuelMode::Story:         return Story;
		case EDuelMode::Free:          return Free;
		case EDuelMode::Tutorial:      return Tutorial;
		case EDuelMode::ExamTimed:     return ExamTimed;
		case EDuelMode::ExamPractical: return ExamPractical;
		case EDuelMode::Puzzle:        return Puzzle;
		case EDuelMode::Ante:          return Ante;
		default:                       return Story;
		}
	}

	inline bool Parse(const FString& Value, EDuelMode& OutMode)
	{
		if (Value == Story)         { OutMode = EDuelMode::Story; return true; }
		if (Value == Free)          { OutMode = EDuelMode::Free; return true; }
		if (Value == Tutorial)      { OutMode = EDuelMode::Tutorial; return true; }
		if (Value == ExamTimed)     { OutMode = EDuelMode::ExamTimed; return true; }
		if (Value == ExamPractical) { OutMode = EDuelMode::ExamPractical; return true; }
		if (Value == Puzzle)        { OutMode = EDuelMode::Puzzle; return true; }
		if (Value == Ante)          { OutMode = EDuelMode::Ante; return true; }
		return false;
	}
}

/**
 * Everything the caller must decide before the engine starts.
 * OpponentId is a roster slug; OpponentDeckId is a decks.json/Decks entry.
 * PlayerDeckId is an inventory deck slot id, not a starter template.
 */
USTRUCT(BlueprintType)
struct FDuelRequest
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString OpponentId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString OpponentDeckId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString PlayerDeckId;

	/** Canonical mode string; see DuelModes. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString Mode = TEXT("free");

	/** Required when Mode == "puzzle". */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString PuzzleId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	bool bAnte = false;

	/** Deterministic seed; 0 means "generate and record one". */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 Seed = 0;

	/** 0 = no additional limit. Puzzle/exam modes set this from data. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 TurnLimit = 0;

	/** 0 = no timer. Puzzle/exam modes set this from data. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 TimeLimitSeconds = 0;

	bool IsValid() const
	{
		EDuelMode Parsed;
		if (!DuelModes::Parse(Mode, Parsed))
		{
			return false;
		}
		if (OpponentId.IsEmpty() || OpponentDeckId.IsEmpty() || PlayerDeckId.IsEmpty())
		{
			return false;
		}
		return Parsed != EDuelMode::Puzzle || !PuzzleId.IsEmpty();
	}
};

/**
 * Engine result. A04 fills the statistics; A02 applies DP/title/counters;
 * A03 consumes story outcomes; A07 consumes exam/puzzle outcomes.
 * DpEarned is the final awarded value after A02's formula and multipliers.
 */
USTRUCT(BlueprintType)
struct FDuelResult
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString OpponentId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString Mode;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	bool bPlayerWon = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	bool bDraw = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 Turns = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 PlayerLp = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 OpponentLp = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 BattleDamageDealt = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 MonstersDestroyedByBattle = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 DpEarned = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	TArray<FString> FlagsSet;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 Seed = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	FString Reason;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	bool bPuzzleSolved = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 TimeRemainingSeconds = 0;

	// Additional statistics already produced by FDuelResultStats (A04) and
	// consumed by A02/A07. They are additive v1 fields.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	bool bWentSecond = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 BattleDamageTaken = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 EffectDamageDealt = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 MonstersLostByBattle = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 FusionSummons = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 RitualSummons = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 SpecialSummons = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 SpellsActivated = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 TrapsActivated = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 CardsDrawn = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel")
	int32 CardsDiscarded = 0;

	bool IsValid() const
	{
		return !OpponentId.IsEmpty() && !Mode.IsEmpty() && Turns >= 0 && PlayerLp >= 0 && OpponentLp >= 0;
	}
};
