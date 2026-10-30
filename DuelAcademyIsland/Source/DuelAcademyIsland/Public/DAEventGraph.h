// Duel Academy Island - story event graph.
//
// Loads the opening event manifest and evaluates event triggers/requirements
// against A02's profile and calendar. The graph is data-only: it never draws UI
// or moves actors. UDAStorySubsystem owns the runtime scene queue.

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UDAProfileSubsystem;
class UDACalendarSubsystem;

/** One event loaded from Content/Data/Story/opening.json. */
struct FDAEventDefinition
{
	FString Id;
	FString Title;
	FString Scene;
	int32 Priority = 0;
	bool bOnce = true;
	bool bRepeatable = false;
	bool bOptional = false;
	bool bCanonEvent = false;
	TSharedPtr<FJsonObject> Trigger;
	TArray<TSharedPtr<FJsonObject>> Requirements;
	TArray<TSharedPtr<FJsonObject>> Outcomes;
	TArray<FString> SceneQueue;
	TSharedPtr<FJsonObject> Raw;
};

/**
 * Event graph: triggers, requirements, completion state and availability.
 *
 * Completion is stored in the profile as event_<id>_cleared as well as in the
 * story subsystem's serialized state. The graph accepts both the authored
 * (opening.json) and contract (requires/rewards) condition shapes.
 */
class DUELACADEMYISLAND_API FDAEventGraph
{
public:
	bool LoadFromJson(const TSharedPtr<FJsonObject>& Root, FString& OutError);

	const FDAEventDefinition* FindEvent(const FString& EventId) const;
	const TArray<FDAEventDefinition>& GetEvents() const { return Events; }

	bool EvaluateTrigger(const FDAEventDefinition& Event, const UDAProfileSubsystem* Profile,
		const UDACalendarSubsystem* Calendar, FString& OutReason) const;
	bool EvaluateRequirements(const FDAEventDefinition& Event, const UDAProfileSubsystem* Profile,
		const UDACalendarSubsystem* Calendar, FString& OutReason) const;

	bool IsEventComplete(const FString& EventId, const UDAProfileSubsystem* Profile) const;
	TArray<FString> GetAvailableEvents(const UDAProfileSubsystem* Profile,
		const UDACalendarSubsystem* Calendar) const;

	static bool EvaluateCondition(const TSharedPtr<FJsonObject>& Condition,
		const UDAProfileSubsystem* Profile, const UDACalendarSubsystem* Calendar, FString& OutReason);
	static bool EvaluateConditionArray(const TArray<TSharedPtr<FJsonObject>>& Conditions,
		const UDAProfileSubsystem* Profile, const UDACalendarSubsystem* Calendar, FString& OutReason);

	/** E01 -> event_01_cleared, E01b -> event_01b_cleared, FJ01 -> event_fj01_cleared. */
	static FString EventCompletionFlag(const FString& EventId);

private:
	TArray<FDAEventDefinition> Events;
	TMap<FString, int32> EventIndex;
};
