// Duel Academy Island - frozen story command contract (v1).
//
// This header is the integration reference. When a lane adopts it, copy it to
// Source/DuelAcademyIsland/Public/ and let the owning lane (A03/A09) keep the
// implementation. Do not rename fields or enum values without an A10 contract
// change. See Docs/Contracts/README.md and Docs/Contracts/API_CHANGELOG.md.
//
// JSON mirror: Docs/Contracts/schemas/story-scene.schema.json
// Scene files:  DuelAcademyIsland/Content/Data/Story/scenes/<scene>.json
//
// Invariants:
//   * A scene is a serializable queue of FStoryCommand values.
//   * Dialogue/Choice pause the queue until A09 returns a result.
//   * Duel pauses the queue until A04/A07 returns FDuelResult.
//   * Reward/SetFlag are applied by A02/A06, never directly by A09.
//   * End is terminal; no command may follow it.

#pragma once

#include "CoreMinimal.h"
#include "DAStoryContract.generated.h"

/** Command types shared by A03 (producer), A08/A09 (presentation) and A02/A06 (outcomes). */
UENUM(BlueprintType)
enum class EStoryCommand : uint8
{
	Dialogue  UMETA(DisplayName = "Dialogue"),
	Choice    UMETA(DisplayName = "Choice"),
	Camera    UMETA(DisplayName = "Camera"),
	MoveNpc   UMETA(DisplayName = "Move NPC"),
	Fade      UMETA(DisplayName = "Fade"),
	Wait      UMETA(DisplayName = "Wait"),
	Banner    UMETA(DisplayName = "Banner"),
	PlaySfx   UMETA(DisplayName = "Play SFX"),
	Music     UMETA(DisplayName = "Music"),
	Duel      UMETA(DisplayName = "Duel"),
	Reward    UMETA(DisplayName = "Reward"),
	SetFlag   UMETA(DisplayName = "Set Flag"),
	End       UMETA(DisplayName = "End")
};

/**
 * One command in a scene queue.
 *
 * Field use by type:
 *   Dialogue  SpeakerId, Portrait, TextKey, bSkippable
 *   Choice    TextKey, Args (choice ids; see FStoryChoice), bSkippable
 *   Camera    Args[0] = anchor id, Duration
 *   MoveNpc   Args[0] = npc id, Args[1] = anchor id, Duration
 *   Fade      Args[0] = "out"|"in", Duration
 *   Wait      Duration
 *   Banner    Args[0] = localization/banner key or literal fallback
 *   PlaySfx   Args[0] = cue id
 *   Music     Args[0] = cue id (empty = stop)
 *   Duel      Args[0] = opponent id, Args[1] = opponent deck id, Args[2] = mode
 *   Reward    Args[] = "dp:100", "card:1", "pack:basic_1a", "flag:name", "title:...", "dorm:Ra"
 *   SetFlag   Args[0] = flag name
 *   End       no args
 */
USTRUCT(BlueprintType)
struct FStoryCommand
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	EStoryCommand Type = EStoryCommand::Dialogue;

	/** Stable id for save/resume idempotency. Optional in hand-authored data. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString CommandId;

	/** Speaker slug ("jaden"), not a display name. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString SpeakerId;

	/** Portrait/expression key ("jaden_happy"); empty means the speaker fallback. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString Portrait;

	/** Localization and trace key ("E01.sheppard_01"). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString TextKey;

	/** Command-specific arguments. Keep strings so the queue is JSON-safe. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	TArray<FString> Args;

	/** Seconds for Camera/Fade/Wait/MoveNpc; 0 means "use the presentation default". */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	float Duration = 0.f;

	/** False for forced story beats; true for ordinary dialogue. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	bool bSkippable = true;
};

/** Presentation-side choice descriptor. The command's Args carry the ids. */
USTRUCT(BlueprintType)
struct FStoryChoice
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString Id;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString TextKey;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	TArray<FString> Args;
};

/** Serializable queue. Save this verbatim for mid-scene save/load. */
USTRUCT(BlueprintType)
struct FStoryCommandQueue
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString EventId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	FString SceneId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	int32 Version = 1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	TArray<FStoryCommand> Commands;

	/** Next command to execute; persisted for resume. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Story")
	int32 ResumeIndex = 0;

	bool IsValid() const
	{
		if (SceneId.IsEmpty() || Commands.Num() == 0)
		{
			return false;
		}
		return ResumeIndex >= 0 && ResumeIndex <= Commands.Num();
	}
};

namespace DAStoryContract
{
	inline const TCHAR* LexToString(EStoryCommand Command)
	{
		switch (Command)
		{
		case EStoryCommand::Dialogue: return TEXT("Dialogue");
		case EStoryCommand::Choice:   return TEXT("Choice");
		case EStoryCommand::Camera:   return TEXT("Camera");
		case EStoryCommand::MoveNpc:  return TEXT("MoveNpc");
		case EStoryCommand::Fade:     return TEXT("Fade");
		case EStoryCommand::Wait:     return TEXT("Wait");
		case EStoryCommand::Banner:   return TEXT("Banner");
		case EStoryCommand::PlaySfx:  return TEXT("PlaySfx");
		case EStoryCommand::Music:    return TEXT("Music");
		case EStoryCommand::Duel:     return TEXT("Duel");
		case EStoryCommand::Reward:   return TEXT("Reward");
		case EStoryCommand::SetFlag:  return TEXT("SetFlag");
		case EStoryCommand::End:      return TEXT("End");
		default:                      return TEXT("Unknown");
		}
	}

	inline bool IsTerminal(EStoryCommand Command)
	{
		return Command == EStoryCommand::End;
	}
}
