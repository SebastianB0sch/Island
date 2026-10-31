#include "DAEffectRuntime.h"

#include "DACardRecords.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	FString ReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, const FString& Default = FString())
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Key, Value))
		{
			return Value;
		}
		return Default;
	}

	int32 ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid() && Object->TryGetNumberField(Key, Value))
		{
			return Value;
		}
		return Default;
	}

	bool ReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, bool Default = false)
	{
		bool bValue = Default;
		if (Object.IsValid() && Object->TryGetBoolField(Key, bValue))
		{
			return bValue;
		}
		return Default;
	}

	bool ScriptHasOperation(const FDEffectScript& Script, const TCHAR* Operation)
	{
		for (const TSharedPtr<FJsonObject>& Step : Script.Operations)
		{
			if (ReadString(Step, TEXT("op")) == Operation)
			{
				return true;
			}
		}
		return false;
	}

	/** Triggers that belong to the card the event happened to.  A script on a
	 *  different copy of the same card must not fire for another copy's event.
	 *  Spell/Trap field responses are still scanned (Bottomless, Sakuretsu). */
	bool IsSourceBoundTrigger(EDEffectTrigger Trigger)
	{
		switch (Trigger)
		{
		case EDEffectTrigger::OnSummon:
		case EDEffectTrigger::OnNormalSummon:
		case EDEffectTrigger::OnSpecialSummon:
		case EDEffectTrigger::OnFlipSummon:
		case EDEffectTrigger::OnFlip:
		case EDEffectTrigger::OnFusionSummon:
		case EDEffectTrigger::OnRitualSummon:
		case EDEffectTrigger::OnActivate:
		case EDEffectTrigger::OnChain:
		case EDEffectTrigger::OnAttackDeclared:
		case EDEffectTrigger::OnAttackTarget:
		case EDEffectTrigger::OnDamageStep:
		case EDEffectTrigger::OnDamageCalculated:
		case EDEffectTrigger::OnBattleDamage:
		case EDEffectTrigger::OnBattleDestroy:
		case EDEffectTrigger::OnBattleDestroyByAttacker:
		case EDEffectTrigger::OnDestroy:
		case EDEffectTrigger::OnSentToGraveyard:
		case EDEffectTrigger::OnRemovedFromField:
		case EDEffectTrigger::OnPositionChange:
		case EDEffectTrigger::OnTributeSummon:
		case EDEffectTrigger::InherentSummon:
			return true;
		default:
			return false;
		}
	}

	/** Triggers whose natural subject is the card they happened to.  A05's
	 *  scripts can opt into a field-wide scan with `field_scan: true` or
	 *  `event_source_is_self: false`. */
	bool IsSelfOnlyTrigger(EDEffectTrigger Trigger)
	{
		switch (Trigger)
		{
		case EDEffectTrigger::OnBattleDestroy:
		case EDEffectTrigger::OnSentToGraveyard:
		case EDEffectTrigger::OnTributeSummon:
		case EDEffectTrigger::OnPositionChange:
		case EDEffectTrigger::OnBattleDestroyByAttacker:
		case EDEffectTrigger::OnBattleDamage:
			return true;
		default:
			return false;
		}
	}

	bool IsSummonTrigger(EDEffectTrigger Trigger)
	{
		return Trigger == EDEffectTrigger::OnSummon
			|| Trigger == EDEffectTrigger::OnNormalSummon
			|| Trigger == EDEffectTrigger::OnSpecialSummon
			|| Trigger == EDEffectTrigger::OnFlipSummon;
	}

	bool ConditionRequestsFieldScan(const TSharedPtr<FJsonObject>& Condition)
	{
		if (!Condition.IsValid())
		{
			return false;
		}
		bool bValue = false;
		if (Condition->TryGetBoolField(TEXT("field_scan"), bValue) && bValue)
		{
			return true;
		}
		if (Condition->TryGetBoolField(TEXT("event_source_is_self"), bValue) && !bValue)
		{
			return true;
		}
		for (const TCHAR* Key : { TEXT("all"), TEXT("any") })
		{
			const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
			if (Condition->TryGetArrayField(Key, Values) && Values)
			{
				for (const TSharedPtr<FJsonValue>& Value : *Values)
				{
					if (Value.IsValid() && ConditionRequestsFieldScan(Value->AsObject()))
					{
						return true;
					}
				}
			}
		}
		const TSharedPtr<FJsonObject>* NotCondition = nullptr;
		if (Condition->TryGetObjectField(TEXT("not"), NotCondition) && NotCondition && NotCondition->IsValid())
		{
			if (ConditionRequestsFieldScan(*NotCondition))
			{
				return true;
			}
		}
		return false;
	}

	bool IsKnownOp(const FString& Op)
	{
		static const TSet<FString> Known = {
			TEXT("add_counter"), TEXT("allow_fusion"), TEXT("attack_directly"), TEXT("attack_lock"),
			TEXT("banish"), TEXT("battle_damage_zero"), TEXT("battle_damage_modifier"), TEXT("battle_position_lock"),
			TEXT("change_position"), TEXT("copy"), TEXT("declare_name"), TEXT("destroy"),
			TEXT("destruction_replacement"), TEXT("destroy_replace"), TEXT("discard"), TEXT("draw"),
			TEXT("equip"), TEXT("excavate"), TEXT("extra_attack"), TEXT("fusion"), TEXT("gain_lp"),
			TEXT("heal"), TEXT("inherent_special_summon"), TEXT("inflict_damage"), TEXT("lock_activation"),
			TEXT("look_at_deck"), TEXT("mill"), TEXT("modify_atk"), TEXT("modify_def"), TEXT("must_attack"),
			TEXT("negate"), TEXT("negate_activation"), TEXT("negate_attack"), TEXT("piercing"),
			TEXT("place_counter"), TEXT("prevent_battle_damage"), TEXT("redirect_attack"),
			TEXT("redirect_battle_damage"), TEXT("remove_counter"), TEXT("return_to_extra"),
			TEXT("return_to_hand"), TEXT("return_to_deck"), TEXT("reveal"), TEXT("ritual"),
			TEXT("roll_die"), TEXT("search"), TEXT("send_to_grave"), TEXT("send_to_graveyard"), TEXT("set"),
			TEXT("shuffle"), TEXT("skip_phase"), TEXT("special_summon"), TEXT("spirit_return"),
			TEXT("summon"), TEXT("summon_lock"), TEXT("take_control"), TEXT("control"), TEXT("toss_coin"),
			TEXT("union_equip"), TEXT("union_unequip"), TEXT("damage")
		};
		return Known.Contains(Op);
	}

	bool IsKnownCostOp(const FString& Op)
	{
		static const TSet<FString> Known = {
			TEXT("pay_lp"), TEXT("discard"), TEXT("discard_random"), TEXT("tribute"),
			TEXT("send_to_graveyard"), TEXT("banish"), TEXT("return_to_hand"), TEXT("return_to_deck"),
			TEXT("reveal"), TEXT("mill"), TEXT("remove_counter"), TEXT("change_position"),
			TEXT("skip_draw"), TEXT("destroy_self"), TEXT("shuffle")
		};
		return Known.Contains(Op);
	}

	bool IsKnownZone(const FString& Zone)
	{
		static const TSet<FString> Known = {
			TEXT("self"), TEXT("self_monster"), TEXT("self_spell_trap"), TEXT("self_field"),
			TEXT("self_hand"), TEXT("self_deck"), TEXT("self_graveyard"), TEXT("self_banished"),
			TEXT("self_extra"), TEXT("opponent"), TEXT("opponent_monster"), TEXT("opponent_spell_trap"),
			TEXT("opponent_field"), TEXT("opponent_hand"), TEXT("opponent_deck"), TEXT("opponent_graveyard"),
			TEXT("opponent_banished"), TEXT("opponent_extra"), TEXT("any_monster"), TEXT("any_spell_trap"),
			TEXT("all_monsters"), TEXT("all_spell_traps"), TEXT("all_cards"), TEXT("all_hands"),
			TEXT("attacking_monster"), TEXT("attack_target"), TEXT("trigger_source"), TEXT("chain_link"),
			TEXT("banished"), TEXT("graveyard"), TEXT("deck"), TEXT("hand"), TEXT("extra"),
			TEXT("deck_top"), TEXT("equipped_monster"), TEXT("self_all"), TEXT("opponent_all"),
			TEXT("all_cards_and_hands")
		};
		return Known.Contains(Zone);
	}

	bool IsKnownConditionKey(const FString& Key)
	{
		static const TSet<FString> Known = {
			TEXT("all"), TEXT("any"), TEXT("not"), TEXT("controller"), TEXT("face_up"),
			TEXT("position"), TEXT("zone"), TEXT("card_type"), TEXT("subtype"), TEXT("attribute"),
			TEXT("monster_type"), TEXT("level_min"), TEXT("level_max"), TEXT("atk_min"), TEXT("atk_max"),
			TEXT("def_min"), TEXT("def_max"), TEXT("name"), TEXT("name_contains"), TEXT("name_on_field"),
			TEXT("has_counter"), TEXT("lp_min"), TEXT("lp_max"), TEXT("hand_min"), TEXT("hand_max"),
			TEXT("field_spell"), TEXT("summon_type"), TEXT("reason"), TEXT("custom"),
			TEXT("turn"), TEXT("phase"), TEXT("count_zone"), TEXT("count_zones"), TEXT("count_filter"),
			TEXT("count_min"), TEXT("count_max"), TEXT("equipped_min"), TEXT("tribute_min"),
			TEXT("graveyard_min"), TEXT("banished_min"), TEXT("deck_min"), TEXT("extra_min"),
			TEXT("monster_min"), TEXT("spell_trap_min"), TEXT("damage_step"), TEXT("attack_direct"),
			TEXT("has_attacked"), TEXT("is_turn_player"), TEXT("event_source_is_self"), TEXT("field_scan")
		};
		return Known.Contains(Key);
	}

	bool IsKnownCustom(const FString& Custom)
	{
		return Custom == TEXT("sent_from_field_to_graveyard")
			|| Custom == TEXT("ignition_main_phase")
			|| Custom == TEXT("battle_involving_self")
			|| Custom == TEXT("damage_step")
			|| Custom == TEXT("inherent_summon")
			|| Custom == TEXT("opponent_activation")
			|| Custom == TEXT("attack_declared_against_controller");
	}

	bool ValidateConditionJson(const TSharedPtr<FJsonObject>& Condition, FString& OutError, int32 Depth = 0)
	{
		if (!Condition.IsValid())
		{
			return true;
		}
		if (Depth > 8)
		{
			OutError = TEXT("condition nesting is too deep");
			return false;
		}
		const TArray<TSharedPtr<FJsonValue>>* AllValues = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* AnyValues = nullptr;
		Condition->TryGetArrayField(TEXT("all"), AllValues);
		Condition->TryGetArrayField(TEXT("any"), AnyValues);
		auto ValidateList = [&OutError, Depth](const TArray<TSharedPtr<FJsonValue>>* Values) -> bool
		{
			if (!Values)
			{
				return true;
			}
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (!ValidateConditionJson(Value.IsValid() ? Value->AsObject() : nullptr, OutError, Depth + 1))
				{
					return false;
				}
			}
			return true;
		};
		if (!ValidateList(AllValues) || !ValidateList(AnyValues))
		{
			return false;
		}
		const TSharedPtr<FJsonObject>* NotCondition = nullptr;
		if (Condition->TryGetObjectField(TEXT("not"), NotCondition) && NotCondition && NotCondition->IsValid())
		{
			if (!ValidateConditionJson(*NotCondition, OutError, Depth + 1))
			{
				return false;
			}
		}
		const TSharedPtr<FJsonObject>* CountFilter = nullptr;
		if (Condition->TryGetObjectField(TEXT("count_filter"), CountFilter) && CountFilter && CountFilter->IsValid())
		{
			if (!ValidateConditionJson(*CountFilter, OutError, Depth + 1))
			{
				return false;
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* CountZones = nullptr;
		if (Condition->TryGetArrayField(TEXT("count_zones"), CountZones) && CountZones)
		{
			for (const TSharedPtr<FJsonValue>& Value : *CountZones)
			{
				if (!Value.IsValid() || !IsKnownZone(Value->AsString()))
				{
					OutError = FString::Printf(TEXT("unknown count zone '%s'"),
						Value.IsValid() ? *Value->AsString() : TEXT(""));
					return false;
				}
			}
		}
		for (const auto& Pair : Condition->Values)
		{
			const FString ConditionKey(*Pair.Key);
			if (!IsKnownConditionKey(ConditionKey))
			{
				OutError = FString::Printf(TEXT("unknown condition key '%s'"), *ConditionKey);
				return false;
			}
		}
		const FString Zone = ReadString(Condition, TEXT("zone"));
		if (!Zone.IsEmpty() && !IsKnownZone(Zone))
		{
			OutError = FString::Printf(TEXT("unknown condition zone '%s'"), *Zone);
			return false;
		}
		const FString Custom = ReadString(Condition, TEXT("custom"));
		if (!Custom.IsEmpty() && !IsKnownCustom(Custom))
		{
			OutError = FString::Printf(TEXT("unknown condition custom '%s'"), *Custom);
			return false;
		}
		return true;
	}

	bool ValidateTargetJson(const TSharedPtr<FJsonObject>& Target, FString& OutError)
	{
		if (!Target.IsValid())
		{
			return true;
		}
		const FString Zone = ReadString(Target, TEXT("zone"));
		if (Zone.IsEmpty() || !IsKnownZone(Zone))
		{
			OutError = FString::Printf(TEXT("unknown target zone '%s'"), *Zone);
			return false;
		}
		const TSharedPtr<FJsonObject>* Filter = nullptr;
		if (Target->TryGetObjectField(TEXT("filter"), Filter) && Filter && Filter->IsValid())
		{
			if (!ValidateConditionJson(*Filter, OutError))
			{
				return false;
			}
		}
		const TSharedPtr<FJsonObject>* Count = nullptr;
		if (Target->TryGetObjectField(TEXT("count"), Count) && Count && Count->IsValid())
		{
			for (const auto& Pair : (*Count)->Values)
			{
				if (Pair.Key != TEXT("min") && Pair.Key != TEXT("max"))
				{
					OutError = FString::Printf(TEXT("unknown target count key '%s'"), *FString(Pair.Key));
					return false;
				}
			}
		}
		return true;
	}

	bool ValidateOperationJsonArray(const TArray<TSharedPtr<FJsonValue>>& Values, FString& OutError, int32 Depth = 0)
	{
		if (Depth > 8)
		{
			OutError = TEXT("operation nesting is too deep");
			return false;
		}
		for (const TSharedPtr<FJsonValue>& OpValue : Values)
		{
			const TSharedPtr<FJsonObject> Op = OpValue.IsValid() ? OpValue->AsObject() : nullptr;
			if (!Op.IsValid())
			{
				OutError = TEXT("contains a non-object operation");
				return false;
			}
			const FString OpName = ReadString(Op, TEXT("op"));
			if (!IsKnownOp(OpName))
			{
				OutError = FString::Printf(TEXT("uses unknown operation '%s'"), *OpName);
				return false;
			}
			const TSharedPtr<FJsonObject>* OpTarget = nullptr;
			if (Op->TryGetObjectField(TEXT("target"), OpTarget) && OpTarget && OpTarget->IsValid())
			{
				if (!ValidateTargetJson(*OpTarget, OutError))
				{
					return false;
				}
			}
			const FString Destination = ReadString(Op, TEXT("destination"));
			if (!Destination.IsEmpty() && !IsKnownZone(Destination))
			{
				OutError = FString::Printf(TEXT("uses unknown destination '%s'"), *Destination);
				return false;
			}
			const TArray<TSharedPtr<FJsonValue>>* CountZones = nullptr;
			if (Op->TryGetArrayField(TEXT("count_zones"), CountZones) && CountZones)
			{
				for (const TSharedPtr<FJsonValue>& Value : *CountZones)
				{
					if (!Value.IsValid() || !IsKnownZone(Value->AsString()))
					{
						OutError = FString::Printf(TEXT("uses unknown count zone '%s'"),
							Value.IsValid() ? *Value->AsString() : TEXT(""));
						return false;
					}
				}
			}
			for (const TCHAR* BranchKey : { TEXT("success_operations"), TEXT("failure_operations") })
			{
				const TArray<TSharedPtr<FJsonValue>>* Branch = nullptr;
				if (Op->TryGetArrayField(BranchKey, Branch) && Branch)
				{
					if (!ValidateOperationJsonArray(*Branch, OutError, Depth + 1))
					{
						return false;
					}
				}
			}
		}
		return true;
	}

	bool IsFieldZoneString(const FString& Zone)
	{
		return Zone.Contains(TEXT("monster")) || Zone.Contains(TEXT("spell_trap"))
			|| Zone.Contains(TEXT("field")) || Zone == TEXT("self") || Zone == TEXT("opponent");
	}
}

FDAEffectRuntime::FDAEffectRuntime(FDuelEngine* InEngine)
	: Engine(InEngine)
{
}

FDAEffectRuntime::~FDAEffectRuntime() = default;

bool FDAEffectRuntime::LoadDefaultScripts(FString& OutError)
{
	const FString Directory = FPaths::ProjectContentDir() / TEXT("Data/Effects/scripts");
	if (!FPaths::DirectoryExists(Directory))
	{
		OutError = FString::Printf(TEXT("Effect script directory '%s' does not exist."), *Directory);
		return false;
	}
	return LoadScriptsFromDirectory(Directory, OutError);
}

bool FDAEffectRuntime::LoadScriptsFromDirectory(const FString& Directory, FString& OutError)
{
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *(Directory / TEXT("*.json")), true, false);
	Files.Sort();
	if (Files.Num() == 0)
	{
		OutError = FString::Printf(TEXT("No effect scripts found in '%s'."), *Directory);
		return false;
	}

	int32 Loaded = 0;
	for (const FString& File : Files)
	{
		FString JsonText;
		const FString Path = Directory / File;
		if (!FFileHelper::LoadFileToString(JsonText, *Path))
		{
			OutError = FString::Printf(TEXT("Could not read effect script '%s'."), *Path);
			return false;
		}
		if (!LoadScriptJsonText(JsonText, OutError))
		{
			OutError = FString::Printf(TEXT("%s: %s"), *Path, *OutError);
			return false;
		}
		++Loaded;
	}
	if (Loaded == 0)
	{
		OutError = TEXT("No effect scripts were loaded.");
		return false;
	}
	return true;
}

bool FDAEffectRuntime::LoadScriptJsonText(const FString& JsonText, FString& OutError)
{
	TSharedPtr<FJsonValue> RootValue;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, RootValue) || !RootValue.IsValid())
	{
		OutError = TEXT("Effect script JSON could not be parsed.");
		return false;
	}
	const TSharedPtr<FJsonObject> Root = RootValue->AsObject();
	if (!Root.IsValid())
	{
		OutError = TEXT("Effect script root must be an object.");
		return false;
	}

	const int32 CardId = ReadInt(Root, TEXT("card_id"), 0);
	if (CardId <= 0)
	{
		OutError = TEXT("Effect script has no valid card_id.");
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>* ScriptValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("scripts"), ScriptValues) || !ScriptValues)
	{
		OutError = FString::Printf(TEXT("Card %d has no scripts array."), CardId);
		return false;
	}

	TArray<FDEffectScript> Parsed;
	for (const TSharedPtr<FJsonValue>& Value : *ScriptValues)
	{
		const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			OutError = FString::Printf(TEXT("Card %d contains a non-object script."), CardId);
			return false;
		}

		FDEffectScript Script;
		Script.CardId = CardId;
		Script.Id = ReadString(Object, TEXT("id"));
		Script.Trigger = TriggerFromString(ReadString(Object, TEXT("trigger")));
		if (Script.Id.IsEmpty() || Script.Trigger == EDEffectTrigger::None)
		{
			OutError = FString::Printf(TEXT("Card %d has a script with a missing id or unknown trigger."), CardId);
			return false;
		}

		const TSharedPtr<FJsonObject>* Condition = nullptr;
		if (Object->TryGetObjectField(TEXT("condition"), Condition) && Condition && Condition->IsValid())
		{
			Script.Condition = *Condition;
			if (!ValidateConditionJson(Script.Condition, OutError))
			{
				OutError = FString::Printf(TEXT("Card %d script '%s': %s"), CardId, *Script.Id, *OutError);
				return false;
			}
		}
		const TSharedPtr<FJsonObject>* Target = nullptr;
		if (Object->TryGetObjectField(TEXT("target"), Target) && Target && Target->IsValid())
		{
			Script.Target = *Target;
			if (!ValidateTargetJson(Script.Target, OutError))
			{
				OutError = FString::Printf(TEXT("Card %d script '%s': %s"), CardId, *Script.Id, *OutError);
				return false;
			}
		}

		const TArray<TSharedPtr<FJsonValue>>* Costs = nullptr;
		if (Object->TryGetArrayField(TEXT("cost"), Costs) && Costs)
		{
			for (const TSharedPtr<FJsonValue>& CostValue : *Costs)
			{
				const TSharedPtr<FJsonObject> Cost = CostValue.IsValid() ? CostValue->AsObject() : nullptr;
				if (!Cost.IsValid())
				{
					OutError = FString::Printf(TEXT("Card %d script '%s' contains a non-object cost."), CardId, *Script.Id);
					return false;
				}
				const FString CostOp = ReadString(Cost, TEXT("op"));
				if (!IsKnownCostOp(CostOp))
				{
					OutError = FString::Printf(TEXT("Card %d script '%s' uses unknown cost op '%s'."), CardId, *Script.Id, *CostOp);
					return false;
				}
				const TSharedPtr<FJsonObject>* CostTarget = nullptr;
				if (Cost->TryGetObjectField(TEXT("target"), CostTarget) && CostTarget && CostTarget->IsValid())
				{
					if (!ValidateTargetJson(*CostTarget, OutError))
					{
						return false;
					}
				}
				const FString CostZone = ReadString(Cost, TEXT("zone"));
				if (!CostZone.IsEmpty() && !IsKnownZone(CostZone))
				{
					OutError = FString::Printf(TEXT("Card %d script '%s' uses unknown cost zone '%s'."), CardId, *Script.Id, *CostZone);
					return false;
				}
				Script.Costs.Add(Cost);
			}
		}

		const TArray<TSharedPtr<FJsonValue>>* Operations = nullptr;
		if (!Object->TryGetArrayField(TEXT("operations"), Operations) || !Operations || Operations->Num() == 0)
		{
			OutError = FString::Printf(TEXT("Card %d script '%s' has no operations."), CardId, *Script.Id);
			return false;
		}
		for (const TSharedPtr<FJsonValue>& OpValue : *Operations)
		{
			const TSharedPtr<FJsonObject> Op = OpValue.IsValid() ? OpValue->AsObject() : nullptr;
			if (!Op.IsValid())
			{
				OutError = FString::Printf(TEXT("Card %d script '%s' contains a non-object operation."), CardId, *Script.Id);
				return false;
			}
		}
		if (!ValidateOperationJsonArray(*Operations, OutError))
		{
			OutError = FString::Printf(TEXT("Card %d script '%s' %s."), CardId, *Script.Id, *OutError);
			return false;
		}
		for (const TSharedPtr<FJsonValue>& OpValue : *Operations)
		{
			Script.Operations.Add(OpValue->AsObject());
		}

		Script.Duration = ReadString(Object, TEXT("duration"), TEXT("instant"));
		Script.bOptional = ReadBool(Object, TEXT("optional"), false);
		Script.SpellSpeed = FMath::Clamp(ReadInt(Object, TEXT("spell_speed"), 1), 1, 3);
		bool bOnce = false;
		if (Object->TryGetBoolField(TEXT("once_per_turn"), bOnce))
		{
			Script.bOncePerTurn = bOnce;
		}
		else
		{
			const FString OnceValue = ReadString(Object, TEXT("once_per_turn"));
			if (OnceValue == TEXT("duel"))
			{
				Script.bOncePerDuel = true;
			}
		}
		Script.SourceText = ReadString(Object, TEXT("source_text"));
		Parsed.Add(Script);
	}

	if (Parsed.Num() == 0)
	{
		OutError = FString::Printf(TEXT("Card %d has an empty scripts array."), CardId);
		return false;
	}
	TArray<FDEffectScript>& Existing = ScriptsByCard.FindOrAdd(CardId);
	Existing.Append(Parsed);
	return true;
}

void FDAEffectRuntime::ResetForNewDuel()
{
	UsedThisTurn.Reset();
	UsedThisDuel.Reset();
	Counters.Reset();
	LingeringModifiers.Reset();
	ContinuousAtkModifiers.Reset();
	ContinuousDefModifiers.Reset();
	AllowedFusionTypes.Reset();
	RedirectBattleDamageUids.Reset();
	PreventBattleDamageSides.Reset();
	BattleDamageZeroUids.Reset();
	BattleDamageMultipliers.Reset();
	ContinuousBattleDamageMultipliers.Reset();
	CannotAttackUids.Reset();
	MustAttackUids.Reset();
	DirectAttackAllowedUids.Reset();
	DirectAttackForbiddenUids.Reset();
	PiercingUids.Reset();
	ExtraAttackUids.Reset();
	CannotChangePositionUids.Reset();
	EndBattleDefenseUids.Reset();
	PreventDestructionUids.Reset();
	PreventBattleDestructionUids.Reset();
	BanishInsteadOfGraveUids.Reset();
	SpiritReturnUids.Reset();
	ContinuousCannotAttackUids.Reset();
	ContinuousMustAttackUids.Reset();
	ContinuousDirectAttackAllowedUids.Reset();
	ContinuousDirectAttackForbiddenUids.Reset();
	ContinuousPiercingUids.Reset();
	ContinuousExtraAttackUids.Reset();
	ContinuousCannotChangePositionUids.Reset();
	ContinuousPreventDestructionUids.Reset();
	ContinuousPreventBattleDestructionUids.Reset();
	ContinuousBanishInsteadOfGraveUids.Reset();
	ContinuousSpiritReturnUids.Reset();
	CannotAttackSidesThisTurn.Reset();
	CannotAttackDirectlySidesThisTurn.Reset();
	MaxAttackersPerSide.Reset();
	MaxAttackersThisTurn.Reset();
	NormalSummonLockSides.Reset();
	SpecialSummonLockSides.Reset();
	ContinuousNormalSummonLockSides.Reset();
	ContinuousSpecialSummonLockSides.Reset();
	NegatedActivationUids.Reset();
	LastRandomResult = 0;
	LastRandomResults.Reset();
	AttackRestrictionExpiryTurn = -1;
	bTrapActivationLocked = false;
	bTrapEffectNegated = false;
	bSpellActivationLocked = false;
	bMonsterEffectLocked = false;
	bAttackNegated = false;
	bExecuting = false;
	bRecomputing = false;
	PromptCount = 0;
	ExecutedScripts = 0;
	FailedScripts = 0;
}

void FDAEffectRuntime::ResetTestStats()
{
	PromptCount = 0;
	ExecutedScripts = 0;
	FailedScripts = 0;
}

int32 FDAEffectRuntime::GetLoadedScriptCount() const
{
	int32 Count = 0;
	for (const TPair<int32, TArray<FDEffectScript>>& Pair : ScriptsByCard)
	{
		Count += Pair.Value.Num();
	}
	return Count;
}

int32 FDAEffectRuntime::GetScriptCount(int32 CardId) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(CardId);
	return Scripts ? Scripts->Num() : 0;
}

FString FDAEffectRuntime::GetScriptId(int32 CardId, int32 ScriptIndex) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(CardId);
	return Scripts && Scripts->IsValidIndex(ScriptIndex) ? (*Scripts)[ScriptIndex].Id : FString();
}

EDEffectTrigger FDAEffectRuntime::GetScriptTrigger(int32 CardId, int32 ScriptIndex) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(CardId);
	return Scripts && Scripts->IsValidIndex(ScriptIndex) ? (*Scripts)[ScriptIndex].Trigger : EDEffectTrigger::None;
}

FString FDAEffectRuntime::TriggerToString(EDEffectTrigger Trigger) const
{
	switch (Trigger)
	{
	case EDEffectTrigger::OnDuelStart: return TEXT("on_duel_start");
	case EDEffectTrigger::OnTurnStart: return TEXT("on_turn_start");
	case EDEffectTrigger::OnTurnEnd: return TEXT("on_turn_end");
	case EDEffectTrigger::OnActivate: return TEXT("on_activate");
	case EDEffectTrigger::OnNormalSummon: return TEXT("on_normal_summon");
	case EDEffectTrigger::OnSpecialSummon: return TEXT("on_special_summon");
	case EDEffectTrigger::OnFlipSummon: return TEXT("on_flip_summon");
	case EDEffectTrigger::OnSummon: return TEXT("on_summon");
	case EDEffectTrigger::OnFlip: return TEXT("on_flip");
	case EDEffectTrigger::OnBattleStart: return TEXT("on_battle_start");
	case EDEffectTrigger::OnAttackDeclared: return TEXT("on_attack_declared");
	case EDEffectTrigger::OnAttackTarget: return TEXT("on_attack_target");
	case EDEffectTrigger::OnDamageStep: return TEXT("on_damage_step");
	case EDEffectTrigger::OnDamageCalculated: return TEXT("on_damage_calculated");
	case EDEffectTrigger::OnBattleDamage: return TEXT("on_battle_damage");
	case EDEffectTrigger::OnBattleDestroy: return TEXT("on_battle_destroy");
	case EDEffectTrigger::OnBattleDestroyByAttacker: return TEXT("on_battle_destroy_by_attacker");
	case EDEffectTrigger::OnDestroy: return TEXT("on_destroy");
	case EDEffectTrigger::OnSentToGraveyard: return TEXT("on_sent_to_graveyard");
	case EDEffectTrigger::OnRemovedFromField: return TEXT("on_removed_from_field");
	case EDEffectTrigger::OnPositionChange: return TEXT("on_position_change");
	case EDEffectTrigger::OnDraw: return TEXT("on_draw");
	case EDEffectTrigger::OnStandby: return TEXT("on_standby");
	case EDEffectTrigger::OnMain: return TEXT("on_main");
	case EDEffectTrigger::OnEnd: return TEXT("on_end");
	case EDEffectTrigger::OnChain: return TEXT("on_chain");
	case EDEffectTrigger::OnRitualSummon: return TEXT("on_ritual_summon");
	case EDEffectTrigger::OnFusionSummon: return TEXT("on_fusion_summon");
	case EDEffectTrigger::OnTributeSummon: return TEXT("on_tribute_summon");
	case EDEffectTrigger::InherentSummon: return TEXT("inherent_summon");
	case EDEffectTrigger::Continuous: return TEXT("continuous");
	case EDEffectTrigger::EquipContinuous: return TEXT("equip_continuous");
	case EDEffectTrigger::FieldContinuous: return TEXT("field_continuous");
	case EDEffectTrigger::Manual: return TEXT("manual");
	default: return TEXT("none");
	}
}

EDEffectTrigger FDAEffectRuntime::TriggerFromString(const FString& Value) const
{
	static const TMap<FString, EDEffectTrigger> Triggers = {
		{ TEXT("on_duel_start"), EDEffectTrigger::OnDuelStart },
		{ TEXT("on_turn_start"), EDEffectTrigger::OnTurnStart },
		{ TEXT("on_turn_end"), EDEffectTrigger::OnTurnEnd },
		{ TEXT("on_activate"), EDEffectTrigger::OnActivate },
		{ TEXT("on_normal_summon"), EDEffectTrigger::OnNormalSummon },
		{ TEXT("on_special_summon"), EDEffectTrigger::OnSpecialSummon },
		{ TEXT("on_flip_summon"), EDEffectTrigger::OnFlipSummon },
		{ TEXT("on_summon"), EDEffectTrigger::OnSummon },
		{ TEXT("on_flip"), EDEffectTrigger::OnFlip },
		{ TEXT("on_battle_start"), EDEffectTrigger::OnBattleStart },
		{ TEXT("on_attack_declared"), EDEffectTrigger::OnAttackDeclared },
		{ TEXT("on_attack_target"), EDEffectTrigger::OnAttackTarget },
		{ TEXT("on_damage_step"), EDEffectTrigger::OnDamageStep },
		{ TEXT("on_damage_calculated"), EDEffectTrigger::OnDamageCalculated },
		{ TEXT("on_battle_damage"), EDEffectTrigger::OnBattleDamage },
		{ TEXT("on_battle_destroy"), EDEffectTrigger::OnBattleDestroy },
		{ TEXT("on_battle_destroy_by_attacker"), EDEffectTrigger::OnBattleDestroyByAttacker },
		{ TEXT("on_destroy"), EDEffectTrigger::OnDestroy },
		{ TEXT("on_sent_to_graveyard"), EDEffectTrigger::OnSentToGraveyard },
		{ TEXT("on_removed_from_field"), EDEffectTrigger::OnRemovedFromField },
		{ TEXT("on_position_change"), EDEffectTrigger::OnPositionChange },
		{ TEXT("on_draw"), EDEffectTrigger::OnDraw },
		{ TEXT("on_standby"), EDEffectTrigger::OnStandby },
		{ TEXT("on_main"), EDEffectTrigger::OnMain },
		{ TEXT("on_end"), EDEffectTrigger::OnEnd },
		{ TEXT("on_chain"), EDEffectTrigger::OnChain },
		{ TEXT("on_ritual_summon"), EDEffectTrigger::OnRitualSummon },
		{ TEXT("on_fusion_summon"), EDEffectTrigger::OnFusionSummon },
		{ TEXT("on_tribute_summon"), EDEffectTrigger::OnTributeSummon },
		{ TEXT("inherent_summon"), EDEffectTrigger::InherentSummon },
		{ TEXT("continuous"), EDEffectTrigger::Continuous },
		{ TEXT("equip_continuous"), EDEffectTrigger::EquipContinuous },
		{ TEXT("field_continuous"), EDEffectTrigger::FieldContinuous },
		{ TEXT("manual"), EDEffectTrigger::Manual }
	};
	const EDEffectTrigger* Found = Triggers.Find(Value);
	return Found ? *Found : EDEffectTrigger::None;
}

FString FDAEffectRuntime::CardName(const FDuelCard& Card) const
{
	return Card.Data.Name.IsEmpty() ? FString::Printf(TEXT("Card %d"), Card.Data.Id) : Card.Data.Name;
}

EDuelOwner FDAEffectRuntime::Other(EDuelOwner Side) const
{
	return Side == EDuelOwner::Player ? EDuelOwner::Opponent : EDuelOwner::Player;
}

FString FDAEffectRuntime::ZoneStringOf(const FDuelCard& Card) const
{
	if (!Engine || Card.Uid <= 0)
	{
		return TEXT("none");
	}
	auto ZoneOf = [&Card](const FDuelSide& Side, const TCHAR* Prefix) -> FString
	{
		for (const FDuelCard& C : Side.Monsters) if (C.Uid == Card.Uid) return FString::Printf(TEXT("%s_monster"), Prefix);
		for (const FDuelCard& C : Side.Spells) if (C.Uid == Card.Uid) return FString::Printf(TEXT("%s_spell_trap"), Prefix);
		if (Side.Field.Uid == Card.Uid) return FString::Printf(TEXT("%s_field"), Prefix);
		for (const FDuelCard& C : Side.Hand) if (C.Uid == Card.Uid) return FString::Printf(TEXT("%s_hand"), Prefix);
		for (const FDuelCard& C : Side.Deck) if (C.Uid == Card.Uid) return FString::Printf(TEXT("%s_deck"), Prefix);
		for (const FDuelCard& C : Side.Graveyard) if (C.Uid == Card.Uid) return FString::Printf(TEXT("%s_graveyard"), Prefix);
		for (const FDuelCard& C : Side.Banished) if (C.Uid == Card.Uid) return FString::Printf(TEXT("%s_banished"), Prefix);
		for (const FDuelCard& C : Side.Extra) if (C.Uid == Card.Uid) return FString::Printf(TEXT("%s_extra"), Prefix);
		return FString();
	};
	FString Result = ZoneOf(Engine->Player, TEXT("self"));
	if (!Result.IsEmpty())
	{
		return Result;
	}
	Result = ZoneOf(Engine->Opponent, TEXT("opponent"));
	return Result.IsEmpty() ? TEXT("none") : Result;
}

FString FDAEffectRuntime::ScriptKey(int32 SourceUid, const FDEffectScript& Script) const
{
	return FString::Printf(TEXT("%d:%d:%s"), SourceUid, Script.CardId, *Script.Id);
}

// ---------------------------------------------------------------------------
// Event bus
// ---------------------------------------------------------------------------

void FDAEffectRuntime::OnDuelStart()
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnDuelStart;
	FireEvent(Event);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnTurnStart(EDuelOwner Side)
{
	UsedThisTurn.Reset();
	ResetTurnRestrictions();
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnTurnStart;
	Event.SourceController = Side;
	Event.EventController = Side;
	FireEvent(Event);
	ExpireLingering(Side, false);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnDraw(EDuelOwner Side, const FDuelCard& Card)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnDraw;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Side;
	Event.EventController = Side;
	Event.SummonType = TEXT("draw");
	FireEvent(Event);
}

void FDAEffectRuntime::OnStandby(EDuelOwner Side)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnStandby;
	Event.SourceController = Side;
	Event.EventController = Side;
	FireEvent(Event);
}

void FDAEffectRuntime::OnMain(EDuelOwner Side)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnMain;
	Event.SourceController = Side;
	Event.EventController = Side;
	FireEvent(Event);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnBattleStart(EDuelOwner Side)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnBattleStart;
	Event.SourceController = Side;
	Event.EventController = Side;
	FireEvent(Event);
}

void FDAEffectRuntime::OnBattleEnd()
{
	TArray<int32> Positions = EndBattleDefenseUids.Array();
	for (int32 Uid : Positions)
	{
		FDuelCard* Card = Engine ? Engine->FindMonster(Uid) : nullptr;
		if (Card && Card->bFaceUp && Card->Position != EDuelPosition::Defense)
		{
			const EDuelPosition Previous = Card->Position;
			Card->Position = EDuelPosition::Defense;
			Card->PositionChangedTurn = Engine->TurnNumber;
			Engine->Log(FString::Printf(TEXT("%s changes to Defense Position at the end of the Battle Phase."),
				*CardName(*Card)), TEXT("effect"));
			Engine->EmitVisual(EDuelVisualEventType::Position, Card->Controller, Card, 0, TEXT("BATTLE END: DEFENSE"));
			OnPositionChanged(*Card, Previous);
		}
	}
	EndBattleDefenseUids.Reset();
	ExpireLingering(EDuelOwner::Player, true);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnEnd(EDuelOwner Side)
{
	// Spirit Monsters return to the owner's hand during their controller's End
	// Phase.  The marker is registered by a continuous/ignition script so the
	// legacy engine does not need a card-name table.
	TArray<int32> Spirits;
	TSet<int32> AllSpirits = SpiritReturnUids;
	for (int32 Uid : ContinuousSpiritReturnUids)
	{
		AllSpirits.Add(Uid);
	}
	for (int32 Uid : AllSpirits)
	{
		const FDuelCard* Card = Engine ? Engine->FindMonster(Uid) : nullptr;
		if (Card && Card->Controller == Side && Card->bFaceUp)
		{
			Spirits.Add(Uid);
		}
	}
	for (int32 Uid : Spirits)
	{
		FDuelCard Copy;
		if (Engine && Engine->RemoveFromZone(Copy, Uid))
		{
			Engine->CleanupEquips(Copy);
			Engine->MoveToHand(Copy);
			Engine->Log(FString::Printf(TEXT("%s returns to the hand during the End Phase."), *CardName(Copy)), TEXT("effect"));
		}
	}

	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnTurnEnd;
	Event.SourceController = Side;
	Event.EventController = Side;
	FireEvent(Event);
	Event.Trigger = EDEffectTrigger::OnEnd;
	FireEvent(Event);
	ExpireLingering(Side, true);
	ExpireLingering(Side, false);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnSummon(FDuelCard& Card, bool bSpecial, bool bFlipSummon, int32 TributeCount)
{
	FDEffectEvent Event;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	Event.SummonType = bSpecial ? TEXT("special") : (bFlipSummon ? TEXT("flip") : TEXT("normal"));
	Event.Reason = FString::Printf(TEXT("%s summon"), *Event.SummonType);
	Event.TributeCount = TributeCount;
	Event.Trigger = EDEffectTrigger::OnSummon;
	FireEvent(Event);

	if (bSpecial)
	{
		Event.Trigger = EDEffectTrigger::OnSpecialSummon;
		FireEvent(Event);
	}
	else if (bFlipSummon)
	{
		Event.Trigger = EDEffectTrigger::OnFlipSummon;
		FireEvent(Event);
	}
	else
	{
		Event.Trigger = EDEffectTrigger::OnNormalSummon;
		FireEvent(Event);
		if (TributeCount > 0)
		{
			Event.Trigger = EDEffectTrigger::OnTributeSummon;
			FireEvent(Event);
		}
	}
	RecomputeContinuous();
}

void FDAEffectRuntime::OnFlip(FDuelCard& Card)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnFlip;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	FireEvent(Event);
}

void FDAEffectRuntime::OnFusionSummon(FDuelCard& Card)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnFusionSummon;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	Event.SummonType = TEXT("fusion");
	FireEvent(Event);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnRitualSummon(FDuelCard& Card)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnRitualSummon;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	Event.SummonType = TEXT("ritual");
	FireEvent(Event);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnActivate(FDuelCard& Card)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnActivate;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	FireEvent(Event);
}

void FDAEffectRuntime::OnChain(const FDuelChainLink& Link)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnChain;
	Event.ChainLink = Link.LinkIndex;
	Event.SourceController = Link.Controller;
	Event.EventController = Link.Controller;
	if (const FDuelCard* Card = Engine ? Engine->FindCard(Link.CardUid) : nullptr)
	{
		Event.SourceCard = *Card;
		Event.EventCard = *Card;
	}
	FireEvent(Event);
}

void FDAEffectRuntime::OnAttackDeclared(FDuelCard& Attacker, FDuelCard* Target)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnAttackDeclared;
	Event.SourceCard = Attacker;
	Event.EventCard = Attacker;
	Event.SourceController = Attacker.Controller;
	Event.EventController = Attacker.Controller;
	Event.AttackerUid = Attacker.Uid;
	Event.AttackTargetUid = Target ? Target->Uid : 0;
	Event.Reason = TEXT("attack declared");
	FireEvent(Event);
}

void FDAEffectRuntime::OnAttackTarget(FDuelCard& Attacker, FDuelCard* Target)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnAttackTarget;
	Event.SourceCard = Attacker;
	Event.EventCard = Target ? *Target : Attacker;
	Event.SourceController = Attacker.Controller;
	Event.EventController = Target ? Target->Controller : Attacker.Controller;
	Event.AttackerUid = Attacker.Uid;
	Event.AttackTargetUid = Target ? Target->Uid : 0;
	Event.Reason = TEXT("attack target");
	FireEvent(Event);
}

void FDAEffectRuntime::OnDamageStep(FDuelCard& Attacker, FDuelCard* Target)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnDamageStep;
	Event.SourceCard = Attacker;
	Event.EventCard = Target ? *Target : Attacker;
	Event.SourceController = Attacker.Controller;
	Event.EventController = Target ? Target->Controller : Attacker.Controller;
	Event.AttackerUid = Attacker.Uid;
	Event.AttackTargetUid = Target ? Target->Uid : 0;
	Event.bDamageStep = true;
	Event.Reason = TEXT("damage step");
	FireEvent(Event);
}

void FDAEffectRuntime::OnDamageCalculated(FDuelCard& Attacker, FDuelCard* Target)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnDamageCalculated;
	Event.SourceCard = Attacker;
	Event.EventCard = Target ? *Target : Attacker;
	Event.SourceController = Attacker.Controller;
	Event.EventController = Target ? Target->Controller : Attacker.Controller;
	Event.AttackerUid = Attacker.Uid;
	Event.AttackTargetUid = Target ? Target->Uid : 0;
	Event.bDamageStep = true;
	Event.Reason = TEXT("damage calculation");
	FireEvent(Event);
}

void FDAEffectRuntime::OnBattleDamage(EDuelOwner Receiver, int32 Amount, FDuelCard& Attacker, FDuelCard* Target, bool bDirect)
{
	if (Amount <= 0)
	{
		return;
	}
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnBattleDamage;
	Event.SourceCard = Attacker;
	Event.EventCard = Target ? *Target : Attacker;
	Event.SourceController = Attacker.Controller;
	Event.EventController = Target ? Target->Controller : Receiver;
	Event.AttackerUid = Attacker.Uid;
	Event.AttackTargetUid = Target ? Target->Uid : 0;
	Event.DamagedUid = Target ? Target->Uid : 0;
	Event.DamageReceiver = Receiver;
	Event.DamageAmount = Amount;
	Event.bDirectAttack = bDirect;
	Event.Reason = bDirect ? TEXT("direct battle damage") : TEXT("battle damage");
	FireEvent(Event);
}

void FDAEffectRuntime::OnBattleDestroyByAttacker(FDuelCard& Attacker, const FDuelCard& Destroyed)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnBattleDestroyByAttacker;
	Event.SourceCard = Attacker;
	Event.EventCard = Destroyed;
	Event.SourceController = Attacker.Controller;
	Event.EventController = Destroyed.Controller;
	Event.AttackerUid = Attacker.Uid;
	Event.DamagedUid = Destroyed.Uid;
	Event.bByBattle = true;
	Event.Reason = TEXT("destroyed by battle");
	FireEvent(Event);
}

void FDAEffectRuntime::OnPositionChanged(FDuelCard& Card, EDuelPosition PreviousPosition)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnPositionChange;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	Event.PreviousPosition = PreviousPosition;
	Event.Reason = TEXT("position change");
	FireEvent(Event);
}

void FDAEffectRuntime::OnCounterTrapResponse(FDuelCard& Trap, int32 TargetChainLink)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnActivate;
	Event.SourceCard = Trap;
	Event.EventCard = Trap;
	Event.SourceController = Trap.Controller;
	Event.EventController = Trap.Controller;
	Event.ChainLink = TargetChainLink;
	Event.Reason = TEXT("counter trap response");
	FireEvent(Event);
}

void FDAEffectRuntime::OnDestroyed(const FDuelCard& Card, bool bByBattle, const FString& Reason)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnDestroy;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	Event.Reason = Reason;
	Event.bByBattle = bByBattle;
	Event.bFromField = true;
	FireEvent(Event);

	if (bByBattle)
	{
		Event.Trigger = EDEffectTrigger::OnBattleDestroy;
		FireEvent(Event);
	}

	Event.Trigger = EDEffectTrigger::OnSentToGraveyard;
	FireEvent(Event);
	ClearCardState(Card.Uid);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnSentToGraveyard(const FDuelCard& Card, bool bFromField, const FString& Reason)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnSentToGraveyard;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	Event.Reason = Reason;
	Event.bFromField = bFromField;
	FireEvent(Event);
}

void FDAEffectRuntime::OnCardLeftField(const FDuelCard& Card)
{
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnRemovedFromField;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;
	Event.bFromField = true;
	FireEvent(Event);
	ClearCardState(Card.Uid);
	RecomputeContinuous();
}

int32 FDAEffectRuntime::FireEvent(const FDEffectEvent& Event)
{
	if (!Engine || bExecuting)
	{
		return 0;
	}
	bExecuting = true;

	FDEffectEvent LocalEvent = Event;
	if (LocalEvent.SourceController != LocalEvent.SourceCard.Controller
		&& LocalEvent.SourceCard.Uid > 0)
	{
		LocalEvent.SourceController = LocalEvent.SourceCard.Controller;
	}
	if (LocalEvent.EventController != LocalEvent.EventCard.Controller
		&& LocalEvent.EventCard.Uid > 0)
	{
		LocalEvent.EventController = LocalEvent.EventCard.Controller;
	}
	if (LocalEvent.SourceZoneAtEvent.IsEmpty() && LocalEvent.SourceCard.Uid > 0)
	{
		LocalEvent.SourceZoneAtEvent = ZoneStringOf(LocalEvent.SourceCard);
	}

	int32 Started = 0;
	TSet<FString> Seen;
	const bool bSourceBoundTrigger = IsSourceBoundTrigger(LocalEvent.Trigger);
	const bool bSelfOnlyTrigger = IsSelfOnlyTrigger(LocalEvent.Trigger);
	const bool bSummonTrigger = IsSummonTrigger(LocalEvent.Trigger);
	const bool bStrictSourceOnly = LocalEvent.Trigger == EDEffectTrigger::OnActivate
		|| LocalEvent.Trigger == EDEffectTrigger::OnChain;
	auto ConsiderCard = [&](const FDuelCard& Source)
	{
		const bool bIsSource = Source.Uid == LocalEvent.SourceCard.Uid;
		if (bStrictSourceOnly && !bIsSource)
		{
			return;
		}

		const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Source.Data.Id);
		if (!Scripts)
		{
			return;
		}
		for (int32 Index = 0; Index < Scripts->Num(); ++Index)
		{
			const FDEffectScript& Script = (*Scripts)[Index];
			if (Script.Trigger != LocalEvent.Trigger)
			{
				continue;
			}

			// Self triggers only react to their own card's event.  A05 can
			// explicitly opt into a field-wide scan with field_scan:true or
			// event_source_is_self:false.  Summon responses from Spell/Trap
			// cards (Bottomless, Mispolymerization) remain field-scanned.
			bool bRequiresSelf = bSelfOnlyTrigger;
			if (bSummonTrigger && !(Source.IsSpell() || Source.IsTrap()))
			{
				bRequiresSelf = true;
			}
			if (ConditionRequestsFieldScan(Script.Condition))
			{
				bRequiresSelf = false;
			}
			if (bRequiresSelf && !bIsSource)
			{
				continue;
			}
			// A different copy of the same card never fires merely because it
			// shares the card id.  Different cards can still be field-wide
			// responses for non-self triggers.
			if (bSourceBoundTrigger && !bRequiresSelf && !bIsSource
				&& Source.Data.Id == LocalEvent.SourceCard.Data.Id)
			{
				continue;
			}

			const FString Key = FString::Printf(TEXT("%d:%d"), Source.Uid, Index);
			if (Seen.Contains(Key))
			{
				continue;
			}
			Seen.Add(Key);
			if (TryStartScript(Script, Source, LocalEvent))
			{
				++Started;
			}
		}
	};

	if (LocalEvent.SourceCard.Uid > 0)
	{
		ConsiderCard(LocalEvent.SourceCard);
	}

	const bool bScanField = Event.Trigger == EDEffectTrigger::OnTurnStart
		|| Event.Trigger == EDEffectTrigger::OnTurnEnd
		|| Event.Trigger == EDEffectTrigger::OnSummon
		|| Event.Trigger == EDEffectTrigger::OnNormalSummon
		|| Event.Trigger == EDEffectTrigger::OnSpecialSummon
		|| Event.Trigger == EDEffectTrigger::OnFlipSummon
		|| Event.Trigger == EDEffectTrigger::OnAttackDeclared
		|| Event.Trigger == EDEffectTrigger::OnAttackTarget
		|| Event.Trigger == EDEffectTrigger::OnDamageStep
		|| Event.Trigger == EDEffectTrigger::OnBattleStart
		|| Event.Trigger == EDEffectTrigger::OnDamageCalculated
		|| Event.Trigger == EDEffectTrigger::OnBattleDamage
		|| Event.Trigger == EDEffectTrigger::OnDestroy
		|| Event.Trigger == EDEffectTrigger::OnBattleDestroy
		|| Event.Trigger == EDEffectTrigger::OnBattleDestroyByAttacker
		|| Event.Trigger == EDEffectTrigger::OnSentToGraveyard
		|| Event.Trigger == EDEffectTrigger::OnRemovedFromField
		|| Event.Trigger == EDEffectTrigger::OnPositionChange
		|| Event.Trigger == EDEffectTrigger::OnTributeSummon
		|| Event.Trigger == EDEffectTrigger::OnDraw
		|| Event.Trigger == EDEffectTrigger::OnStandby
		|| Event.Trigger == EDEffectTrigger::OnMain
		|| Event.Trigger == EDEffectTrigger::OnEnd;
	if (bScanField)
	{
		for (const FDuelCard& Card : CollectCardsInZone(TEXT("all_cards"), EDuelOwner::Player))
		{
			ConsiderCard(Card);
		}
	}

	bExecuting = false;
	return Started;
}

// ---------------------------------------------------------------------------
// Conditions and selectors
// ---------------------------------------------------------------------------

bool FDAEffectRuntime::EvaluateCustomCondition(const FString& Custom, const FDuelCard& Subject,
	const FDuelCard& SourceCard, const FDEffectEvent& Event) const
{
	if (Custom == TEXT("sent_from_field_to_graveyard"))
	{
		return Event.bFromField && (Event.Trigger == EDEffectTrigger::OnSentToGraveyard
			|| Event.Trigger == EDEffectTrigger::OnDestroy
			|| Event.Trigger == EDEffectTrigger::OnBattleDestroy);
	}
	if (Custom == TEXT("ignition_main_phase"))
	{
		return Engine && Engine->IsMainPhase() && !Engine->bWinnerSet
			&& Engine->ActiveSide == SourceCard.Controller;
	}
	if (Custom == TEXT("battle_involving_self"))
	{
		return Event.AttackerUid == Subject.Uid || Event.AttackTargetUid == Subject.Uid
			|| Event.AttackerUid == SourceCard.Uid || Event.AttackTargetUid == SourceCard.Uid;
	}
	if (Custom == TEXT("damage_step"))
	{
		return Event.bDamageStep || Event.Trigger == EDEffectTrigger::OnDamageStep
			|| Event.Trigger == EDEffectTrigger::OnDamageCalculated;
	}
	if (Custom == TEXT("inherent_summon"))
	{
		return Event.Trigger == EDEffectTrigger::InherentSummon
			|| (Event.Trigger == EDEffectTrigger::OnSpecialSummon && Event.SourceCard.Uid == Subject.Uid);
	}
	if (Custom == TEXT("opponent_activation"))
	{
		return (Event.Trigger == EDEffectTrigger::OnActivate || Event.Trigger == EDEffectTrigger::OnChain)
			&& Event.SourceController != SourceCard.Controller;
	}
	if (Custom == TEXT("attack_declared_against_controller"))
	{
		if (!Engine || Event.AttackerUid == 0)
		{
			return false;
		}
		const FDuelCard* Attacker = Engine->FindMonster(Event.AttackerUid);
		return Attacker && Attacker->Controller != SourceCard.Controller;
	}
	return false;
}

bool FDAEffectRuntime::EvaluateCondition(const TSharedPtr<FJsonObject>& Condition, const FDuelCard& Subject,
	const FDuelCard& SourceCard, const FDEffectEvent& Event, bool bContinuousRegistration) const
{
	if (!Condition.IsValid())
	{
		return true;
	}

	const TArray<TSharedPtr<FJsonValue>>* AllValues = nullptr;
	if (Condition->TryGetArrayField(TEXT("all"), AllValues) && AllValues)
	{
		for (const TSharedPtr<FJsonValue>& Value : *AllValues)
		{
			const TSharedPtr<FJsonObject> Child = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!EvaluateCondition(Child, Subject, SourceCard, Event, bContinuousRegistration))
			{
				return false;
			}
		}
	}
	const TArray<TSharedPtr<FJsonValue>>* AnyValues = nullptr;
	if (Condition->TryGetArrayField(TEXT("any"), AnyValues) && AnyValues && AnyValues->Num() > 0)
	{
		bool bAny = false;
		for (const TSharedPtr<FJsonValue>& Value : *AnyValues)
		{
			const TSharedPtr<FJsonObject> Child = Value.IsValid() ? Value->AsObject() : nullptr;
			if (EvaluateCondition(Child, Subject, SourceCard, Event, bContinuousRegistration))
			{
				bAny = true;
				break;
			}
		}
		if (!bAny)
		{
			return false;
		}
	}
	const TSharedPtr<FJsonObject>* NotCondition = nullptr;
	if (Condition->TryGetObjectField(TEXT("not"), NotCondition) && NotCondition && NotCondition->IsValid())
	{
		if (EvaluateCondition(*NotCondition, Subject, SourceCard, Event, bContinuousRegistration))
		{
			return false;
		}
	}

	const FString Controller = ReadString(Condition, TEXT("controller"));
	if (!Controller.IsEmpty())
	{
		if (Controller == TEXT("self") && Subject.Controller != SourceCard.Controller) return false;
		if (Controller == TEXT("opponent") && Subject.Controller == SourceCard.Controller) return false;
	}

	bool bHasFaceUp = false;
	if (Condition->TryGetBoolField(TEXT("face_up"), bHasFaceUp) && Subject.bFaceUp != bHasFaceUp)
	{
		return false;
	}

	const FString Position = ReadString(Condition, TEXT("position"));
	if (!Position.IsEmpty() && Position != TEXT("any"))
	{
		if (Position == TEXT("attack") && (Subject.Position != EDuelPosition::Attack || !Subject.bFaceUp)) return false;
		if (Position == TEXT("defense") && (Subject.Position != EDuelPosition::Defense || !Subject.bFaceUp)) return false;
		if (Position == TEXT("face_down") && Subject.bFaceUp) return false;
	}

	const FString Zone = ReadString(Condition, TEXT("zone"));
	if (!Zone.IsEmpty())
	{
		const FString Actual = (!Event.SourceZoneAtEvent.IsEmpty()
			&& Subject.Uid == Event.SourceCard.Uid)
			? Event.SourceZoneAtEvent
			: ZoneStringOf(Subject);
		const bool bFromFieldSpecial = Event.bFromField && Subject.Uid == Event.SourceCard.Uid
			&& IsFieldZoneString(Zone) && Event.Trigger != EDEffectTrigger::None;
		if (!bFromFieldSpecial)
		{
			if ((Zone == TEXT("self") || Zone == TEXT("opponent")))
			{
				if (!Actual.StartsWith(Zone + TEXT("_"))) return false;
			}
			else if (Actual != Zone)
			{
				return false;
			}
		}
	}

	const FString CardType = ReadString(Condition, TEXT("card_type"));
	if (!CardType.IsEmpty())
	{
		if (CardType == TEXT("Monster") && !Subject.IsMonster()) return false;
		else if (CardType != TEXT("Monster") && !Subject.Data.CardType.Contains(CardType)) return false;
	}
	const FString Subtype = ReadString(Condition, TEXT("subtype"));
	if (!Subtype.IsEmpty() && Subject.Data.Subtype != Subtype) return false;
	const FString Attribute = ReadString(Condition, TEXT("attribute"));
	if (!Attribute.IsEmpty() && Subject.Data.Attribute != Attribute) return false;
	const FString MonsterType = ReadString(Condition, TEXT("monster_type"));
	if (!MonsterType.IsEmpty() && Subject.Data.MonsterType != MonsterType) return false;
	const FString Name = ReadString(Condition, TEXT("name"));
	if (!Name.IsEmpty() && Subject.Data.Name != Name) return false;
	const FString NameContains = ReadString(Condition, TEXT("name_contains"));
	if (!NameContains.IsEmpty() && !Subject.Data.Name.Contains(NameContains, ESearchCase::IgnoreCase)) return false;

	auto HasNamedCardOnField = [this, &SourceCard](const FString& Wanted, bool bSubstring) -> bool
	{
		if (!Engine)
		{
			return false;
		}
		for (const FDuelCard& Card : CollectCardsInZone(TEXT("all_cards"), SourceCard.Controller))
		{
			if (!Card.IsValid())
			{
				continue;
			}
			if (bSubstring ? Card.Data.Name.Contains(Wanted, ESearchCase::IgnoreCase) : Card.Data.Name == Wanted)
			{
				return true;
			}
		}
		return false;
	};
	const FString NameOnField = ReadString(Condition, TEXT("name_on_field"));
	if (!NameOnField.IsEmpty() && !HasNamedCardOnField(NameOnField, false)) return false;

	const FString Turn = ReadString(Condition, TEXT("turn"));
	if (!Turn.IsEmpty() && Turn != TEXT("any"))
	{
		const EDuelOwner TurnSide = Event.SourceController;
		if (Turn == TEXT("self") && TurnSide != SourceCard.Controller) return false;
		if (Turn == TEXT("opponent") && TurnSide == SourceCard.Controller) return false;
	}
	const FString PhaseName = ReadString(Condition, TEXT("phase"));
	if (!PhaseName.IsEmpty() && PhaseName != TEXT("any"))
	{
		if (!Engine) return false;
		const bool bBattle = Engine->GetPhase() == EDuelPhase::Battle;
		const bool bMain = Engine->GetPhase() == EDuelPhase::Main1 || Engine->GetPhase() == EDuelPhase::Main2;
		if (PhaseName == TEXT("battle") && !bBattle) return false;
		if (PhaseName == TEXT("main") && !bMain) return false;
	}
	bool bBoolValue = false;
	if (Condition->TryGetBoolField(TEXT("damage_step"), bBoolValue) && bBoolValue
		&& !(Event.bDamageStep || Event.Trigger == EDEffectTrigger::OnDamageStep
			|| Event.Trigger == EDEffectTrigger::OnDamageCalculated))
	{
		return false;
	}
	if (Condition->TryGetBoolField(TEXT("attack_direct"), bBoolValue) && Event.bDirectAttack != bBoolValue) return false;
	if (Condition->TryGetBoolField(TEXT("has_attacked"), bBoolValue) && Subject.bHasAttacked != bBoolValue) return false;
	if (Condition->TryGetBoolField(TEXT("event_source_is_self"), bBoolValue) && bBoolValue
		&& Event.SourceCard.Uid != SourceCard.Uid) return false;
	if (Condition->TryGetBoolField(TEXT("is_turn_player"), bBoolValue) && Engine
		&& (Engine->ActiveSide == SourceCard.Controller) != bBoolValue) return false;
	int32 Number = 0;
	if (Condition->TryGetNumberField(TEXT("tribute_min"), Number) && Event.TributeCount < Number) return false;
	if (Condition->TryGetNumberField(TEXT("equipped_min"), Number))
	{
		int32 Equipped = 0;
		if (Engine)
		{
			for (EDuelOwner EquipSide : { EDuelOwner::Player, EDuelOwner::Opponent })
			{
				for (const FDuelCard& Spell : Engine->GetSide(EquipSide).Spells)
				{
					if (Spell.IsValid() && Spell.EquippedToUid == Subject.Uid) ++Equipped;
				}
			}
		}
		if (Equipped < Number) return false;
	}

	auto CountConditionZone = [this, &Condition, &Subject, &SourceCard, &Event](const FString& Zone) -> int32
	{
		const TSharedPtr<FJsonObject>* CountFilter = nullptr;
		Condition->TryGetObjectField(TEXT("count_filter"), CountFilter);
		int32 Count = 0;
		for (const FDuelCard& Card : CollectCandidates(Zone, SourceCard, Event))
		{
			if (!CountFilter || MatchesFilter(Card, CountFilter ? *CountFilter : nullptr, SourceCard, Event))
			{
				++Count;
			}
		}
		return Count;
	};
	int32 CountTotal = 0;
	bool bHasCount = false;
	const FString CountZone = ReadString(Condition, TEXT("count_zone"));
	if (!CountZone.IsEmpty())
	{
		bHasCount = true;
		CountTotal += CountConditionZone(CountZone);
	}
	const TArray<TSharedPtr<FJsonValue>>* CountZones = nullptr;
	if (Condition->TryGetArrayField(TEXT("count_zones"), CountZones) && CountZones)
	{
		bHasCount = true;
		for (const TSharedPtr<FJsonValue>& Value : *CountZones)
		{
			if (Value.IsValid())
			{
				CountTotal += CountConditionZone(Value->AsString());
			}
		}
	}
	if (Condition->TryGetNumberField(TEXT("count_min"), Number) && CountTotal < Number) return false;
	if (Condition->TryGetNumberField(TEXT("count_max"), Number) && CountTotal > Number) return false;
	if (bHasCount && Condition->HasField(TEXT("count_min")) == false
		&& Condition->HasField(TEXT("count_max")) == false && CountTotal <= 0)
	{
		return false;
	}

	auto SideCount = [this, &SourceCard](EDuelOwner Side, const FString& What) -> int32
	{
		if (!Engine) return 0;
		const FDuelSide& State = Engine->GetSide(Side);
		if (What == TEXT("hand")) return State.Hand.Num();
		if (What == TEXT("graveyard")) return State.Graveyard.Num();
		if (What == TEXT("banished")) return State.Banished.Num();
		if (What == TEXT("deck")) return State.Deck.Num();
		if (What == TEXT("extra")) return State.Extra.Num();
		if (What == TEXT("monster")) return State.Monsters.FilterByPredicate([](const FDuelCard& C) { return C.IsValid(); }).Num();
		if (What == TEXT("spell_trap")) return State.Spells.FilterByPredicate([](const FDuelCard& C) { return C.IsValid(); }).Num();
		return 0;
	};
	const TPair<FString, FString> MinimumKeys[] = {
		{ TEXT("graveyard_min"), TEXT("graveyard") }, { TEXT("banished_min"), TEXT("banished") },
		{ TEXT("deck_min"), TEXT("deck") }, { TEXT("extra_min"), TEXT("extra") },
		{ TEXT("monster_min"), TEXT("monster") }, { TEXT("spell_trap_min"), TEXT("spell_trap") }
	};
	for (const TPair<FString, FString>& Pair : MinimumKeys)
	{
		if (Condition->TryGetNumberField(*Pair.Key, Number)
			&& SideCount(SourceCard.Controller, Pair.Value) < Number) return false;
	}

	auto EffectiveLevel = [this, &Subject]() -> int32
	{
		return Engine && Engine->FindMonster(Subject.Uid) ? Engine->GetEffectiveLevel(Subject) : Subject.Data.Level;
	};
	auto EffectiveAtk = [this, &Subject]() -> int32
	{
		return Engine && Engine->FindMonster(Subject.Uid) ? Engine->GetAtk(Subject) : Subject.Data.Atk;
	};
	auto EffectiveDef = [this, &Subject]() -> int32
	{
		return Engine && Engine->FindMonster(Subject.Uid) ? Engine->GetDef(Subject) : Subject.Data.Def;
	};

	if (Condition->TryGetNumberField(TEXT("level_min"), Number) && EffectiveLevel() < Number) return false;
	if (Condition->TryGetNumberField(TEXT("level_max"), Number) && EffectiveLevel() > Number) return false;
	if (Condition->TryGetNumberField(TEXT("atk_min"), Number) && EffectiveAtk() < Number) return false;
	if (Condition->TryGetNumberField(TEXT("atk_max"), Number) && EffectiveAtk() > Number) return false;
	if (Condition->TryGetNumberField(TEXT("def_min"), Number) && EffectiveDef() < Number) return false;
	if (Condition->TryGetNumberField(TEXT("def_max"), Number) && EffectiveDef() > Number) return false;

	const TSharedPtr<FJsonObject>* Counter = nullptr;
	if (Condition->TryGetObjectField(TEXT("has_counter"), Counter) && Counter && Counter->IsValid())
	{
		const FString CounterName = ReadString(*Counter, TEXT("counter"));
		const int32 Minimum = ReadInt(*Counter, TEXT("min"), 1);
		if (GetCounterCount(Subject.Uid, CounterName) < Minimum)
		{
			return false;
		}
	}

	if (Condition->TryGetNumberField(TEXT("lp_min"), Number)
		&& Engine && Engine->GetSide(SourceCard.Controller).LP < Number) return false;
	if (Condition->TryGetNumberField(TEXT("lp_max"), Number)
		&& Engine && Engine->GetSide(SourceCard.Controller).LP > Number) return false;
	if (Condition->TryGetNumberField(TEXT("hand_min"), Number)
		&& Engine && Engine->GetSide(SourceCard.Controller).Hand.Num() < Number) return false;
	if (Condition->TryGetNumberField(TEXT("hand_max"), Number)
		&& Engine && Engine->GetSide(SourceCard.Controller).Hand.Num() > Number) return false;

	const FString FieldSpell = ReadString(Condition, TEXT("field_spell"));
	if (!FieldSpell.IsEmpty() && (!Engine || !Engine->HasField(SourceCard.Controller, *FieldSpell)))
	{
		return false;
	}

	const FString SummonType = ReadString(Condition, TEXT("summon_type"));
	if (!SummonType.IsEmpty() && SummonType != TEXT("any") && Event.SummonType != SummonType)
	{
		return false;
	}

	const FString Reason = ReadString(Condition, TEXT("reason"));
	if (!Reason.IsEmpty() && !Event.Reason.Contains(Reason))
	{
		return false;
	}

	const FString Custom = ReadString(Condition, TEXT("custom"));
	if (!Custom.IsEmpty())
	{
		if (!(bContinuousRegistration && Custom == TEXT("battle_involving_self")))
		{
			if (!EvaluateCustomCondition(Custom, Subject, SourceCard, Event))
			{
				return false;
			}
		}
	}
	return true;
}

bool FDAEffectRuntime::MatchesFilter(const FDuelCard& Candidate, const TSharedPtr<FJsonObject>& Filter,
	const FDuelCard& SourceCard, const FDEffectEvent& Event) const
{
	return !Filter.IsValid() || EvaluateCondition(Filter, Candidate, SourceCard, Event);
}

TArray<FDuelCard> FDAEffectRuntime::CollectCardsInZone(const FString& Zone, EDuelOwner Side) const
{
	TArray<FDuelCard> Result;
	if (!Engine)
	{
		return Result;
	}

	auto AddSide = [&Result, Zone](const FDuelSide& State, const TCHAR* Prefix)
	{
		const FString P(Prefix);
		auto AddArray = [&Result](const TArray<FDuelCard>& Cards)
		{
			for (const FDuelCard& Card : Cards)
			{
				if (Card.IsValid())
				{
					Result.Add(Card);
				}
			}
		};
		if (Zone == P + TEXT("_monster") || Zone == TEXT("all_monsters") || Zone == TEXT("any_monster"))
		{
			AddArray(State.Monsters);
		}
		if (Zone == P + TEXT("_spell_trap") || Zone == TEXT("all_spell_traps") || Zone == TEXT("any_spell_trap"))
		{
			AddArray(State.Spells);
			if (State.Field.IsValid()) Result.Add(State.Field);
		}
		if (Zone == P + TEXT("_field"))
		{
			if (State.Field.IsValid()) Result.Add(State.Field);
		}
		if (Zone == P + TEXT("_hand") || Zone == TEXT("all_hands"))
		{
			AddArray(State.Hand);
		}
		if (Zone == P + TEXT("_deck") || Zone == TEXT("deck") || Zone == TEXT("deck_top"))
		{
			if (Zone == TEXT("deck_top"))
			{
				if (State.Deck.Num() > 0) Result.Add(State.Deck.Last());
			}
			else
			{
				AddArray(State.Deck);
			}
		}
		if (Zone == P + TEXT("_graveyard") || Zone == TEXT("graveyard"))
		{
			AddArray(State.Graveyard);
		}
		if (Zone == P + TEXT("_banished") || Zone == TEXT("banished"))
		{
			AddArray(State.Banished);
		}
		if (Zone == P + TEXT("_extra") || Zone == TEXT("extra"))
		{
			AddArray(State.Extra);
		}
		if (Zone == TEXT("all_cards") || Zone == P || Zone == P + TEXT("_all"))
		{
			AddArray(State.Monsters);
			AddArray(State.Spells);
			if (State.Field.IsValid()) Result.Add(State.Field);
			if (Zone != TEXT("all_cards")) AddArray(State.Hand);
		}
		if (Zone == TEXT("all_cards_and_hands"))
		{
			AddArray(State.Monsters);
			AddArray(State.Spells);
			if (State.Field.IsValid()) Result.Add(State.Field);
			AddArray(State.Hand);
		}
	};

	const EDuelOwner OtherSide = Other(Side);
	const bool bBoth = Zone == TEXT("any_monster") || Zone == TEXT("all_monsters")
		|| Zone == TEXT("any_spell_trap") || Zone == TEXT("all_spell_traps")
		|| Zone == TEXT("all_hands") || Zone == TEXT("all_cards")
		|| Zone == TEXT("all_cards_and_hands")
		|| Zone == TEXT("graveyard") || Zone == TEXT("deck") || Zone == TEXT("banished")
		|| Zone == TEXT("hand") || Zone == TEXT("extra");
	if (bBoth || Zone.StartsWith(TEXT("self")) || Zone == TEXT("all_cards"))
	{
		AddSide(Engine->Player, TEXT("self"));
	}
	if (bBoth || Zone.StartsWith(TEXT("opponent")) || Zone == TEXT("all_cards"))
	{
		AddSide(Engine->Opponent, TEXT("opponent"));
	}
	return Result;
}

TArray<FDuelCard> FDAEffectRuntime::CollectCandidates(const FString& Zone, const FDuelCard& SourceCard,
	const FDEffectEvent& Event) const
{
	if (!Engine)
	{
		return TArray<FDuelCard>();
	}
	if (Zone == TEXT("trigger_source"))
	{
		TArray<FDuelCard> Result;
		if (const FDuelCard* Card = Engine->FindCard(Event.EventCard.Uid))
		{
			Result.Add(*Card);
		}
		return Result;
	}
	if (Zone == TEXT("attacking_monster"))
	{
		TArray<FDuelCard> Result;
		if (const FDuelCard* Card = Engine->FindMonster(Event.AttackerUid))
		{
			Result.Add(*Card);
		}
		return Result;
	}
	if (Zone == TEXT("attack_target"))
	{
		TArray<FDuelCard> Result;
		if (const FDuelCard* Card = Engine->FindMonster(Event.AttackTargetUid))
		{
			Result.Add(*Card);
		}
		return Result;
	}
	if (Zone == TEXT("chain_link"))
	{
		TArray<FDuelCard> Result;
		const TArray<FDuelChainLink>& Links = Engine->GetChainLinks();
		const int32 WantedLink = Event.ChainLink > 0 ? Event.ChainLink : (Links.Num() > 0 ? Links.Last().LinkIndex : 0);
		for (const FDuelChainLink& Link : Links)
		{
			if (Link.LinkIndex == WantedLink)
			{
				if (const FDuelCard* Card = Engine->FindCard(Link.CardUid))
				{
					Result.Add(*Card);
				}
				break;
			}
		}
		return Result;
	}
	if (Zone == TEXT("equipped_monster"))
	{
		TArray<FDuelCard> Result;
		const FDuelCard* Source = Engine->FindCard(SourceCard.Uid);
		const int32 EquippedUid = Source ? Source->EquippedToUid : SourceCard.EquippedToUid;
		if (EquippedUid != 0)
		{
			if (const FDuelCard* Card = Engine->FindMonster(EquippedUid))
			{
				Result.Add(*Card);
			}
		}
		return Result;
	}
	return CollectCardsInZone(Zone, SourceCard.Controller);
}

TArray<FDuelCard> FDAEffectRuntime::CollectAllCards() const
{
	return CollectCardsInZone(TEXT("all_cards"), EDuelOwner::Player);
}

bool FDAEffectRuntime::IsSourceAvailable(const FDEffectScript& Script, const FDuelCard& Source,
	const FDEffectEvent& Event) const
{
	if (!Engine || Source.Uid <= 0)
	{
		return false;
	}
	const FDuelCard* Live = Engine->FindCard(Source.Uid);
	if (!Live)
	{
		// A leave-field trigger is dispatched after the card has been removed
		// from its zone.  The event carries the last known card snapshot, so the
		// source-bound script can still run without a live zone lookup.
		if (Script.Trigger == EDEffectTrigger::OnRemovedFromField
			&& Event.Trigger == EDEffectTrigger::OnRemovedFromField
			&& Event.SourceCard.Uid == Source.Uid
			&& Event.bFromField)
		{
			return true;
		}
		return false;
	}
	if (Live->IsTrap() && bTrapActivationLocked)
	{
		return false;
	}
	const FString Zone = ZoneStringOf(*Live);

	if (Script.Trigger == EDEffectTrigger::Manual
		|| Script.Trigger == EDEffectTrigger::InherentSummon)
	{
		if (Live->IsMonster() && Live->bFaceUp && Zone.Contains(TEXT("monster"))
			&& Engine->IsMainPhase() && !Engine->bWinnerSet)
		{
			return true;
		}
		if (Script.Trigger == EDEffectTrigger::InherentSummon && Live->IsMonster()
			&& Zone.Contains(TEXT("hand")) && Engine->IsMainPhase() && !Engine->bWinnerSet)
		{
			return true;
		}
		return false;
	}
	if (Script.Trigger == EDEffectTrigger::Continuous
		|| Script.Trigger == EDEffectTrigger::EquipContinuous
		|| Script.Trigger == EDEffectTrigger::FieldContinuous)
	{
		return Live->bFaceUp && (Zone.Contains(TEXT("monster")) || Zone.Contains(TEXT("spell_trap")) || Zone.Contains(TEXT("field")));
	}
	if (Script.Trigger == EDEffectTrigger::OnActivate)
	{
		return true;
	}
	if (Live->IsTrap()
		&& (Script.Trigger == EDEffectTrigger::OnSummon
			|| Script.Trigger == EDEffectTrigger::OnAttackDeclared
			|| Script.Trigger == EDEffectTrigger::OnAttackTarget
			|| Script.Trigger == EDEffectTrigger::OnBattleStart
			|| Script.Trigger == EDEffectTrigger::OnDamageCalculated))
	{
		return !Live->bFaceUp && Live->SetTurn < Engine->TurnNumber;
	}
	return true;
}

bool FDAEffectRuntime::IsOncePerTurnBlocked(const FDEffectScript& Script, const FDuelCard& Source) const
{
	const FString Key = ScriptKey(Source.Uid, Script);
	return (Script.bOncePerTurn && UsedThisTurn.Contains(Key))
		|| (Script.bOncePerDuel && UsedThisDuel.Contains(Key));
}

void FDAEffectRuntime::MarkUsed(const FDEffectScript& Script, const FDuelCard& Source)
{
	const FString Key = ScriptKey(Source.Uid, Script);
	if (Script.bOncePerTurn)
	{
		UsedThisTurn.Add(Key);
	}
	if (Script.bOncePerDuel)
	{
		UsedThisDuel.Add(Key);
	}
}

bool FDAEffectRuntime::TryStartScript(const FDEffectScript& Script, const FDuelCard& SourceCard,
	const FDEffectEvent& Event)
{
	if (!Engine || !Script.IsValid() || Engine->bWinnerSet)
	{
		return false;
	}
	if (Script.Trigger == EDEffectTrigger::Continuous
		|| Script.Trigger == EDEffectTrigger::EquipContinuous
		|| Script.Trigger == EDEffectTrigger::FieldContinuous)
	{
		return false;
	}
	if (IsOncePerTurnBlocked(Script, SourceCard) || !IsSourceAvailable(Script, SourceCard, Event))
	{
		return false;
	}

	const FDuelCard ConditionSubject = Event.EventCard.Uid > 0 ? Event.EventCard : SourceCard;
	if (!EvaluateCondition(Script.Condition, ConditionSubject, SourceCard, Event))
	{
		return false;
	}

	FDEffectContext Context;
	Context.Script = Script;
	Context.SourceCard = SourceCard;
	Context.Event = Event;
	Context.Chooser = SourceCard.Controller;

	if (Script.bOptional)
	{
		const FString Prompt = FString::Printf(TEXT("Activate %s?"), *CardName(SourceCard));
		if (SourceCard.Controller == EDuelOwner::Player)
		{
			++PromptCount;
			Engine->RequestOptionalTrigger(SourceCard, Prompt, true,
				[this, Context](bool bActivate)
				{
					ContinueAfterOptional(Context, bActivate);
				});
		}
		else
		{
			ContinueAfterOptional(Context, true);
		}
		return true;
	}

	ContinueToTargets(Context);
	return true;
}

void FDAEffectRuntime::ContinueAfterOptional(FDEffectContext Context, bool bActivate)
{
	if (!bActivate || !Engine || Engine->bWinnerSet)
	{
		return;
	}
	ContinueToTargets(Context);
}

void FDAEffectRuntime::ContinueToTargets(FDEffectContext Context)
{
	if (!Engine || Engine->bWinnerSet)
	{
		return;
	}
	if (!Context.Script.Target.IsValid())
	{
		ContinueAfterTargets(Context, TArray<int32>());
		return;
	}

	TArray<int32> TargetUids;
	TArray<int32> CandidateUids;
	bool bNeedsPrompt = false;
	EDuelOwner Chooser = Context.SourceCard.Controller;
	int32 Min = 0;
	int32 Max = 0;
	FString Prompt;
	if (!ResolveScriptTarget(Context.Script, Context.SourceCard, Context.Event, TargetUids,
		CandidateUids, bNeedsPrompt, Chooser, Min, Max, Prompt))
	{
		++FailedScripts;
		Engine->Log(FString::Printf(TEXT("Effect %s could not resolve a target."), *Context.Script.Id), TEXT("effect"));
		return;
	}
	Context.Chooser = Chooser;
	if (!bNeedsPrompt)
	{
		ContinueAfterTargets(Context, TargetUids);
		return;
	}

	FDuelChoiceRequest Request;
	Request.Type = CandidateUids.Num() > 1 ? EDuelChoiceType::SelectCards : EDuelChoiceType::SelectCard;
	Request.Prompt = Prompt;
	Request.Side = Chooser;
	Request.MinSelections = Min;
	Request.MaxSelections = Max;
	Request.SourceCardUid = Context.SourceCard.Uid;
	Request.SourceCardId = Context.SourceCard.Data.Id;
	Request.bCancellable = Min == 0;
	Request.Context = Context.Script.Id;

	const bool bEquipScript = ScriptHasOperation(Context.Script, TEXT("equip"));
	int32 BestEquipUid = 0;
	int32 BestEquipAtk = -1;
	for (int32 Uid : CandidateUids)
	{
		const FDuelCard* Card = Engine->FindCard(Uid);
		if (!Card)
		{
			continue;
		}
		FDuelChoiceOption Option;
		Option.Id = Uid;
		Option.Label = Card->IsMonster()
			? FString::Printf(TEXT("%s (%d/%d)"), *CardName(*Card), Engine->GetAtk(*Card), Engine->GetDef(*Card))
			: CardName(*Card);
		Option.CardUid = Uid;
		Option.CardId = Card->Data.Id;
		Option.Zone = EDuelZone::None;
		Request.Options.Add(Option);
		if (bEquipScript && Card->IsMonster())
		{
			const int32 Atk = Engine->GetAtk(*Card);
			if (Atk > BestEquipAtk)
			{
				BestEquipAtk = Atk;
				BestEquipUid = Uid;
			}
		}
	}
	TSet<int32> Added;
	if (bEquipScript && BestEquipUid != 0)
	{
		Added.Add(BestEquipUid);
		Request.DefaultOptionIds.Add(BestEquipUid);
	}
	for (int32 Uid : CandidateUids)
	{
		if (Request.DefaultOptionIds.Num() >= FMath::Max(1, Min))
		{
			break;
		}
		if (Uid != Context.SourceCard.Uid && !Added.Contains(Uid))
		{
			Added.Add(Uid);
			Request.DefaultOptionIds.Add(Uid);
		}
	}
	if (Request.DefaultOptionIds.Num() < FMath::Max(1, Min))
	{
		for (int32 Uid : CandidateUids)
		{
			if (Request.DefaultOptionIds.Num() >= FMath::Max(1, Min))
			{
				break;
			}
			if (!Added.Contains(Uid))
			{
				Added.Add(Uid);
				Request.DefaultOptionIds.Add(Uid);
			}
		}
	}

	++PromptCount;
	if (Engine->RequestChoice(Request,
		[this, Context](const FDuelChoiceRequest&, const TArray<int32>& OptionIds)
		{
			ContinueAfterTargets(Context, OptionIds);
		}) == 0)
	{
		++FailedScripts;
	}
}

bool FDAEffectRuntime::ResolveScriptTarget(const FDEffectScript& Script, const FDuelCard& SourceCard,
	const FDEffectEvent& Event, TArray<int32>& OutUids, TArray<int32>& OutCandidateUids,
	bool& bOutNeedsPrompt, EDuelOwner& OutChooser, int32& OutMin, int32& OutMax, FString& OutPrompt) const
{
	OutUids.Reset();
	OutCandidateUids.Reset();
	bOutNeedsPrompt = false;
	OutChooser = SourceCard.Controller;
	OutMin = 0;
	OutMax = 0;

	if (!Script.Target.IsValid())
	{
		return true;
	}
	const FString Zone = ReadString(Script.Target, TEXT("zone"));
	if (Zone.IsEmpty())
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* Filter = nullptr;
	Script.Target->TryGetObjectField(TEXT("filter"), Filter);
	// An Equip Spell is equipped to a face-up monster its controller controls.
	// The shipped scripts use "any_monster" as a shorthand, which would
	// otherwise let the player equip the opponent's monsters (and would offer
	// face-down monsters that cannot legally hold an Equip Spell).
	const bool bEquipScript = ScriptHasOperation(Script, TEXT("equip"))
		&& !Zone.StartsWith(TEXT("opponent"));
	for (const FDuelCard& Candidate : CollectCandidates(Zone, SourceCard, Event))
	{
		if (bEquipScript
			&& (Candidate.Controller != SourceCard.Controller || !Candidate.bFaceUp))
		{
			continue;
		}
		if (MatchesFilter(Candidate, Filter ? *Filter : nullptr, SourceCard, Event))
		{
			OutCandidateUids.Add(Candidate.Uid);
		}
	}

	int32 Min = 1;
	int32 Max = 1;
	const TSharedPtr<FJsonObject>* CountObject = nullptr;
	if (Script.Target->TryGetObjectField(TEXT("count"), CountObject) && CountObject && CountObject->IsValid())
	{
		Min = ReadInt(*CountObject, TEXT("min"), 1);
		Max = ReadInt(*CountObject, TEXT("max"), Min);
	}
	else
	{
		FString CountString;
		if (Script.Target->TryGetStringField(TEXT("count"), CountString) && CountString == TEXT("all"))
		{
			Min = OutCandidateUids.Num();
			Max = OutCandidateUids.Num();
		}
		else
		{
			int32 Count = 1;
			if (Script.Target->TryGetNumberField(TEXT("count"), Count))
			{
				Min = Count;
				Max = Count;
			}
		}
	}
	if (ReadBool(Script.Target, TEXT("optional"), false))
	{
		Min = 0;
	}
	Max = FMath::Min(Max, OutCandidateUids.Num());
	if (Min > OutCandidateUids.Num() || Min > Max || Max < 0)
	{
		return false;
	}
	OutMin = Min;
	OutMax = Max;
	const FString ChooserValue = ReadString(Script.Target, TEXT("chooser"), TEXT("controller"));
	if (ChooserValue == TEXT("opponent"))
	{
		OutChooser = Other(SourceCard.Controller);
	}
	else if (ChooserValue == TEXT("random"))
	{
		OutUids.Reset();
		const int32 SelectCount = FMath::Min(Max, OutCandidateUids.Num());
		TArray<int32> Pool = OutCandidateUids;
		for (int32 I = 0; I < SelectCount && Pool.Num() > 0; ++I)
		{
			const int32 Index = Engine ? Engine->Random.RandRange(0, Pool.Num() - 1) : 0;
			OutUids.Add(Pool[Index]);
			Pool.RemoveAt(Index);
		}
		return true;
	}
	else
	{
		OutChooser = SourceCard.Controller;
	}

	if (Min == 0 && Max == 0)
	{
		return true;
	}
	if (Min == Max && Min == OutCandidateUids.Num())
	{
		OutUids = OutCandidateUids;
		return true;
	}
	if (Min == Max && Min <= OutCandidateUids.Num() && OutCandidateUids.Num() <= Min)
	{
		OutUids = OutCandidateUids;
		return true;
	}
	if (Min == 0 && OutCandidateUids.Num() == 0)
	{
		return true;
	}

	bOutNeedsPrompt = true;
	if (bEquipScript)
	{
		OutPrompt = FString::Printf(TEXT("Choose a face-up monster you control to equip with %s."),
			*CardName(SourceCard));
	}
	else
	{
		OutPrompt = FString::Printf(TEXT("Select %d-%d card(s) for %s"),
			Min, Max, Script.SourceText.IsEmpty() ? *Script.Id : *Script.SourceText);
	}
	return true;
}

void FDAEffectRuntime::ContinueAfterTargets(FDEffectContext Context, const TArray<int32>& TargetUids)
{
	if (!Engine || Engine->bWinnerSet)
	{
		return;
	}
	Context.TargetUids = TargetUids;
	if (Context.TargetUids.Num() == 0 && Context.Script.Target.IsValid()
		&& !ReadBool(Context.Script.Target, TEXT("optional"), false))
	{
		++FailedScripts;
		return;
	}

	const bool bPreviousExecuting = bExecuting;
	bExecuting = true;
	FString Error;
	if (!PayCosts(Context, Error))
	{
		++FailedScripts;
		Engine->Log(FString::Printf(TEXT("Effect %s cost failed: %s"), *Context.Script.Id, *Error), TEXT("effect"));
		bExecuting = bPreviousExecuting;
		return;
	}

	MarkUsed(Context.Script, Context.SourceCard);
	if (ExecuteOperations(Context, Error))
	{
		++ExecutedScripts;
	}
	else
	{
		++FailedScripts;
		Engine->Log(FString::Printf(TEXT("Effect %s failed: %s"), *Context.Script.Id, *Error), TEXT("effect"));
	}

	// Runtime-triggered Trap Cards are not sent to the Graveyard by the legacy
	// activation path.  Do it here for one-shot Trap scripts.
	if (Context.SourceCard.IsTrap()
		&& Context.Script.Duration != TEXT("while_face_up")
		&& Context.Script.Trigger != EDEffectTrigger::Continuous)
	{
		if (FDuelCard* Trap = Engine->FindSpellTrap(Context.SourceCard.Uid))
		{
			Trap->bFaceUp = true;
			Engine->DestroySpellTrap(*Trap, true);
		}
	}
	bExecuting = bPreviousExecuting;

	if (!Engine->bWinnerSet)
	{
		RecomputeContinuous();
		Engine->CheckWinner();
	}
}

// ---------------------------------------------------------------------------
// Costs
// ---------------------------------------------------------------------------

bool FDAEffectRuntime::CanPayCost(const TSharedPtr<FJsonObject>& Cost, const FDEffectContext& Context,
	FString& OutError) const
{
	if (!Cost.IsValid())
	{
		return false;
	}
	const FString Op = ReadString(Cost, TEXT("op"));
	const int32 Amount = ReadInt(Cost, TEXT("amount"), 0);
	const int32 Count = ReadInt(Cost, TEXT("count"), 1);

	TArray<int32> Targets;
	ResolveCostTargets(Cost, Context, Targets);
	const FDuelSide& Side = Engine->GetSide(Context.SourceCard.Controller);

	if (Op == TEXT("pay_lp") && Side.LP < Amount)
	{
		OutError = TEXT("not enough Life Points");
		return false;
	}
	if (Op == TEXT("discard") || Op == TEXT("discard_random"))
	{
		const int32 Needed = Targets.Num() > 0 ? Targets.Num() : FMath::Max(1, Count);
		if (Side.Hand.Num() < Needed)
		{
			OutError = TEXT("not enough cards in hand");
			return false;
		}
		return true;
	}
	if (Op == TEXT("tribute"))
	{
		if (Targets.Num() == 0)
		{
			OutError = TEXT("no tribute target");
			return false;
		}
		for (int32 Uid : Targets)
		{
			if (!Engine->FindMonster(Uid))
			{
				OutError = TEXT("tribute target is not a monster");
				return false;
			}
		}
		return true;
	}
	if (Op == TEXT("remove_counter"))
	{
		const FString Counter = ReadString(Cost, TEXT("counter"), TEXT("spell"));
		const int32 Uid = Targets.Num() > 0 ? Targets[0] : Context.SourceCard.Uid;
		if (GetCounterCount(Uid, Counter) < FMath::Max(1, Count))
		{
			OutError = TEXT("not enough counters");
			return false;
		}
		return true;
	}
	if (Op == TEXT("destroy_self"))
	{
		if (!Engine->FindCard(Context.SourceCard.Uid))
		{
			OutError = TEXT("source is no longer on the field");
			return false;
		}
		return true;
	}
	if (Op == TEXT("skip_draw") || Op == TEXT("shuffle") || Op == TEXT("mill"))
	{
		return true;
	}
	if (Targets.Num() == 0)
	{
		OutError = TEXT("no cost target");
		return false;
	}
	return true;
}

bool FDAEffectRuntime::PayCosts(const FDEffectContext& Context, FString& OutError)
{
	for (const TSharedPtr<FJsonObject>& Cost : Context.Script.Costs)
	{
		if (!CanPayCost(Cost, Context, OutError))
		{
			return false;
		}
	}

	for (const TSharedPtr<FJsonObject>& Cost : Context.Script.Costs)
	{
		const FString Op = ReadString(Cost, TEXT("op"));
		const int32 Amount = ReadInt(Cost, TEXT("amount"), 0);
		const int32 Count = ReadInt(Cost, TEXT("count"), 1);
		TArray<int32> Targets;
		ResolveCostTargets(Cost, Context, Targets);

		if (Op == TEXT("pay_lp"))
		{
			Engine->PayLp(Context.SourceCard.Controller, Amount, Context.Script.Id);
		}
		else if (Op == TEXT("discard") || Op == TEXT("discard_random"))
		{
			if (Op == TEXT("discard_random") || Targets.Num() == 0)
			{
				const int32 Needed = FMath::Max(1, Count);
				for (int32 I = 0; I < Needed && Engine->GetSide(Context.SourceCard.Controller).Hand.Num() > 0; ++I)
				{
					const int32 Index = Engine->Random.RandRange(0, Engine->GetSide(Context.SourceCard.Controller).Hand.Num() - 1);
					Engine->DiscardCard(Engine->SideRef(Context.SourceCard.Controller).Hand[Index], Context.Script.Id);
				}
			}
			else
			{
				for (int32 Uid : Targets)
				{
					if (FDuelCard* Card = Engine->FindCard(Uid))
					{
						Engine->DiscardCard(*Card, Context.Script.Id);
					}
				}
			}
		}
		else if (Op == TEXT("tribute"))
		{
			for (int32 Uid : Targets)
			{
				FDuelCard Copy;
				if (Engine->RemoveFromZone(Copy, Uid))
				{
					Engine->CleanupEquips(Copy);
					Engine->MoveToGrave(Copy);
					Engine->Log(FString::Printf(TEXT("%s is tributed for %s."), *CardName(Copy), *Context.Script.Id), TEXT("cost"));
				}
			}
		}
		else if (Op == TEXT("send_to_graveyard"))
		{
			for (int32 Uid : Targets)
			{
				FDuelCard Copy;
				if (Engine->RemoveFromZone(Copy, Uid))
				{
					Engine->MoveToGrave(Copy);
				}
			}
		}
		else if (Op == TEXT("banish"))
		{
			for (int32 Uid : Targets)
			{
				FDuelCard Copy;
				if (Engine->RemoveFromZone(Copy, Uid))
				{
					Engine->MoveToBanished(Copy);
				}
			}
		}
		else if (Op == TEXT("return_to_hand"))
		{
			for (int32 Uid : Targets)
			{
				FDuelCard Copy;
				if (Engine->RemoveFromZone(Copy, Uid))
				{
					Engine->MoveToHand(Copy);
				}
			}
		}
		else if (Op == TEXT("return_to_deck"))
		{
			for (int32 Uid : Targets)
			{
				FDuelCard Copy;
				if (Engine->RemoveFromZone(Copy, Uid))
				{
					Engine->MoveToDeckBottom(Copy);
				}
			}
		}
		else if (Op == TEXT("reveal"))
		{
			for (int32 Uid : Targets)
			{
				if (const FDuelCard* Card = Engine->FindCard(Uid))
				{
					Engine->EmitVisual(EDuelVisualEventType::Search, Context.SourceCard.Controller, Card, 0, TEXT("REVEAL"));
				}
			}
		}
		else if (Op == TEXT("mill"))
		{
			Engine->Mill(Context.SourceCard.Controller, FMath::Max(1, Count));
		}
		else if (Op == TEXT("remove_counter"))
		{
			const FString Counter = ReadString(Cost, TEXT("counter"), TEXT("spell"));
			const int32 Uid = Targets.Num() > 0 ? Targets[0] : Context.SourceCard.Uid;
			RemoveCounter(Uid, Counter, FMath::Max(1, Count));
		}
		else if (Op == TEXT("change_position"))
		{
			if (Targets.Num() > 0)
			{
				if (FDuelCard* Card = Engine->FindMonster(Targets[0]))
				{
					Card->Position = Card->Position == EDuelPosition::Attack ? EDuelPosition::Defense : EDuelPosition::Attack;
					Card->PositionChangedTurn = Engine->TurnNumber;
				}
			}
		}
		else if (Op == TEXT("skip_draw"))
		{
			Engine->SideRef(Context.SourceCard.Controller).bSkipDraw = true;
		}
		else if (Op == TEXT("destroy_self"))
		{
			if (FDuelCard* Monster = Engine->FindMonster(Context.SourceCard.Uid))
			{
				Engine->DestroyMonster(*Monster, false, nullptr, false, Context.Script.Id);
			}
			else if (FDuelCard* Spell = Engine->FindSpellTrap(Context.SourceCard.Uid))
			{
				Engine->DestroySpellTrap(*Spell, true);
			}
		}
		else if (Op == TEXT("shuffle"))
		{
			Engine->ShuffleSide(Engine->SideRef(Context.SourceCard.Controller));
		}
	}
	return true;
}

bool FDAEffectRuntime::ResolveCostTargets(const TSharedPtr<FJsonObject>& Cost, const FDEffectContext& Context,
	TArray<int32>& OutUids) const
{
	OutUids.Reset();
	if (!Cost.IsValid())
	{
		return false;
	}
	FString TargetString;
	if (Cost->TryGetStringField(TEXT("target"), TargetString))
	{
		if (TargetString == TEXT("$self")) OutUids.Add(Context.SourceCard.Uid);
		else if (TargetString == TEXT("$target")) OutUids = Context.TargetUids;
		else if (TargetString == TEXT("$trigger")) OutUids.Add(Context.Event.EventCard.Uid);
		return OutUids.Num() > 0;
	}

	const TSharedPtr<FJsonObject>* TargetObject = nullptr;
	if (Cost->TryGetObjectField(TEXT("target"), TargetObject) && TargetObject && TargetObject->IsValid())
	{
		const FString Zone = ReadString(*TargetObject, TEXT("zone"));
		const TSharedPtr<FJsonObject>* Filter = nullptr;
		(*TargetObject)->TryGetObjectField(TEXT("filter"), Filter);
		TArray<FDuelCard> Candidates = CollectCandidates(Zone, Context.SourceCard, Context.Event);
		int32 Count = 1;
		FString CountString;
		const TSharedPtr<FJsonObject>* CountObject = nullptr;
		if ((*TargetObject)->TryGetStringField(TEXT("count"), CountString) && CountString == TEXT("all"))
		{
			Count = Candidates.Num();
		}
		else if ((*TargetObject)->TryGetObjectField(TEXT("count"), CountObject) && CountObject && CountObject->IsValid())
		{
			Count = ReadInt(*CountObject, TEXT("max"), ReadInt(*CountObject, TEXT("min"), 1));
		}
		else
		{
			(*TargetObject)->TryGetNumberField(TEXT("count"), Count);
		}
		for (const FDuelCard& Card : Candidates)
		{
			if (OutUids.Num() >= FMath::Max(0, Count))
			{
				break;
			}
			if (MatchesFilter(Card, Filter ? *Filter : nullptr, Context.SourceCard, Context.Event))
			{
				OutUids.Add(Card.Uid);
			}
		}
		return OutUids.Num() > 0;
	}

	const FString Zone = ReadString(Cost, TEXT("zone"));
	if (!Zone.IsEmpty())
	{
		for (const FDuelCard& Card : CollectCandidates(Zone, Context.SourceCard, Context.Event))
		{
			OutUids.Add(Card.Uid);
		}
	}
	return OutUids.Num() > 0;
}

// ---------------------------------------------------------------------------
// Operations
// ---------------------------------------------------------------------------

bool FDAEffectRuntime::ResolveOperationTargets(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
	const FDuelCard& SourceCard, const FDEffectEvent& Event, TArray<int32>& OutUids) const
{
	OutUids.Reset();
	if (!Operation.IsValid())
	{
		return false;
	}
	FString TargetString;
	if (Operation->TryGetStringField(TEXT("target"), TargetString))
	{
		if (TargetString == TEXT("$self")) OutUids.Add(SourceCard.Uid);
		else if (TargetString == TEXT("$equipped"))
		{
			const FDuelCard* Source = Engine ? Engine->FindCard(SourceCard.Uid) : nullptr;
			const int32 EquippedUid = Source ? Source->EquippedToUid : SourceCard.EquippedToUid;
			if (EquippedUid != 0) OutUids.Add(EquippedUid);
		}
		else if (TargetString == TEXT("$target")) OutUids = Context.TargetUids;
		else if (TargetString == TEXT("$cost")) OutUids = Context.CostUids;
		else if (TargetString == TEXT("$trigger")) OutUids.Add(Event.EventCard.Uid);
		else if (TargetString == TEXT("$attacker")) OutUids.Add(Event.AttackerUid);
		else if (TargetString == TEXT("$attack_target")) OutUids.Add(Event.AttackTargetUid);
		return OutUids.Num() > 0;
	}

	const TSharedPtr<FJsonObject>* TargetObject = nullptr;
	if (Operation->TryGetObjectField(TEXT("target"), TargetObject) && TargetObject && TargetObject->IsValid())
	{
		const FString Zone = ReadString(*TargetObject, TEXT("zone"));
		const TSharedPtr<FJsonObject>* Filter = nullptr;
		(*TargetObject)->TryGetObjectField(TEXT("filter"), Filter);
		const TArray<FDuelCard> Candidates = CollectCandidates(Zone, SourceCard, Event);
		int32 Count = 1;
		FString CountString;
		const TSharedPtr<FJsonObject>* CountObject = nullptr;
		if ((*TargetObject)->TryGetStringField(TEXT("count"), CountString) && CountString == TEXT("all"))
		{
			Count = Candidates.Num();
		}
		else if ((*TargetObject)->TryGetObjectField(TEXT("count"), CountObject) && CountObject && CountObject->IsValid())
		{
			Count = ReadInt(*CountObject, TEXT("max"), ReadInt(*CountObject, TEXT("min"), 1));
		}
		else
		{
			(*TargetObject)->TryGetNumberField(TEXT("count"), Count);
		}
		for (const FDuelCard& Card : Candidates)
		{
			if (OutUids.Num() >= FMath::Max(0, Count))
			{
				break;
			}
			if (MatchesFilter(Card, Filter ? *Filter : nullptr, SourceCard, Event))
			{
				OutUids.Add(Card.Uid);
			}
		}
		return OutUids.Num() > 0;
	}
	return false;
}

bool FDAEffectRuntime::ExecuteDraw(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	const FString Player = ReadString(Operation, TEXT("player"), ReadString(Operation, TEXT("to"), TEXT("self")));
	const int32 Count = FMath::Max(1, ReadInt(Operation, TEXT("count"), 1));
	auto DrawSide = [this, Count](EDuelOwner Side)
	{
		Engine->Draw(Side, Count, false);
	};
	if (Player == TEXT("both"))
	{
		DrawSide(Context.SourceCard.Controller);
		if (!Engine->bWinnerSet) DrawSide(Other(Context.SourceCard.Controller));
	}
	else if (Player == TEXT("opponent"))
	{
		DrawSide(Other(Context.SourceCard.Controller));
	}
	else
	{
		DrawSide(Context.SourceCard.Controller);
	}
	return true;
}

bool FDAEffectRuntime::ExecuteDiscard(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const FString Player = ReadString(Operation, TEXT("player"), TEXT("self"));
	const int32 Count = FMath::Max(1, ReadInt(Operation, TEXT("count"), 1));

	if (Targets.Num() == 0)
	{
		auto DiscardFrom = [this, Count, &Context](EDuelOwner Side)
		{
			for (int32 I = 0; I < Count && Engine->GetSide(Side).Hand.Num() > 0; ++I)
			{
				Engine->DiscardCard(Engine->SideRef(Side).Hand[0], Context.Script.Id);
			}
		};
		if (Player == TEXT("both"))
		{
			DiscardFrom(Context.SourceCard.Controller);
			DiscardFrom(Other(Context.SourceCard.Controller));
		}
		else if (Player == TEXT("opponent"))
		{
			DiscardFrom(Other(Context.SourceCard.Controller));
		}
		else
		{
			DiscardFrom(Context.SourceCard.Controller);
		}
		return true;
	}

	for (int32 Uid : Targets)
	{
		if (FDuelCard* Card = Engine->FindCard(Uid))
		{
			Engine->DiscardCard(*Card, Context.Script.Id);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteSearch(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const bool bReveal = ReadBool(Operation, TEXT("reveal"), true);
	const bool bShuffle = ReadBool(Operation, TEXT("shuffle"), true);

	for (int32 Uid : Targets)
	{
		FDuelCard* Card = Engine->FindCard(Uid);
		if (!Card)
		{
			continue;
		}
		const EDuelOwner Owner = Card->Owner;
		FDuelCard Copy;
		if (Engine->RemoveFromZone(Copy, Uid))
		{
			if (bReveal)
			{
				Engine->EmitVisual(EDuelVisualEventType::Search, Context.SourceCard.Controller, &Copy, 0, TEXT("SEARCH"));
			}
			Engine->MoveToHand(Copy);
			Engine->Log(FString::Printf(TEXT("%s adds %s to the hand."), *CardName(Context.SourceCard), *CardName(Copy)), TEXT("effect"));
		}
		if (bShuffle)
		{
			Engine->ShuffleSide(Engine->SideRef(Owner));
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteMill(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	const FString Player = ReadString(Operation, TEXT("player"), ReadString(Operation, TEXT("to"), TEXT("self")));
	const int32 Count = FMath::Max(1, ReadInt(Operation, TEXT("count"), 1));
	if (Player == TEXT("both"))
	{
		Engine->Mill(Context.SourceCard.Controller, Count);
		Engine->Mill(Other(Context.SourceCard.Controller), Count);
	}
	else if (Player == TEXT("opponent"))
	{
		Engine->Mill(Other(Context.SourceCard.Controller), Count);
	}
	else
	{
		Engine->Mill(Context.SourceCard.Controller, Count);
	}
	return true;
}

bool FDAEffectRuntime::ExecuteBanish(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	for (int32 Uid : Targets)
	{
		FDuelCard Copy;
		if (Engine->RemoveFromZone(Copy, Uid))
		{
			Engine->MoveToBanished(Copy);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteDestroy(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const FString Reason = ReadString(Operation, TEXT("reason"), Context.Script.Id);
	for (int32 Uid : Targets)
	{
		if (FDuelCard* Monster = Engine->FindMonster(Uid))
		{
			Engine->DestroyMonster(*Monster, false, nullptr, false, Reason);
		}
		else if (FDuelCard* Spell = Engine->FindSpellTrap(Uid))
		{
			Engine->DestroySpellTrap(*Spell, true);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteSendToGrave(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	for (int32 Uid : Targets)
	{
		FDuelCard Copy;
		if (Engine->RemoveFromZone(Copy, Uid))
		{
			Engine->MoveToGrave(Copy);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteSummon(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
	bool bSpecial, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const FString PositionValue = ReadString(Operation, TEXT("position"), TEXT("attack"));
	const bool bFaceUp = PositionValue != TEXT("face_down") && PositionValue != TEXT("faceDown");
	const EDuelPosition Position = (PositionValue == TEXT("defense") || PositionValue == TEXT("face_down")
		|| PositionValue == TEXT("faceDown")) ? EDuelPosition::Defense : EDuelPosition::Attack;
	for (int32 Uid : Targets)
	{
		FDuelCard* Card = Engine->FindCard(Uid);
		if (!Card)
		{
			continue;
		}
		if (bSpecial && !Engine->CanBeSpecialSummonedByEffect(*Card))
		{
			continue;
		}
		FDuelCard Copy;
		if (!Engine->RemoveFromZone(Copy, Uid))
		{
			continue;
		}
		if (!Engine->PlaceMonster(Copy.Owner, Copy, bFaceUp, Position))
		{
			Engine->MoveToGrave(Copy);
			continue;
		}
		if (FDuelCard* Placed = Engine->FindMonster(Uid))
		{
			Placed->bSpecialSummoned = bSpecial;
			Engine->Log(FString::Printf(TEXT("%s %s %s in %s Position."), *Engine->GetSide(Copy.Owner).Name,
				bSpecial ? TEXT("Special Summons") : TEXT("Summons"), *CardName(*Placed),
				bFaceUp ? (Position == EDuelPosition::Attack ? TEXT("Attack") : TEXT("Defense")) : TEXT("face-down Defense")),
				TEXT("summon"));
			Engine->OnSummon(*Placed, bSpecial, 0);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteSet(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	for (int32 Uid : Targets)
	{
		FDuelCard* Card = Engine->FindCard(Uid);
		if (!Card)
		{
			continue;
		}
		FDuelCard Copy;
		if (!Engine->RemoveFromZone(Copy, Uid))
		{
			continue;
		}
		if (Copy.IsMonster())
		{
			Engine->PlaceMonster(Copy.Owner, Copy, false, EDuelPosition::Defense);
		}
		else
		{
			Engine->PlaceSpellTrap(Copy.Owner, Copy, false, false);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecutePosition(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const FString Position = ReadString(Operation, TEXT("position"), TEXT("attack"));
	for (int32 Uid : Targets)
	{
		if (FDuelCard* Card = Engine->FindMonster(Uid))
		{
			const EDuelPosition Previous = Card->Position;
			Card->bFaceUp = Position != TEXT("face_down");
			Card->Position = Position == TEXT("defense") || Position == TEXT("face_down")
				? EDuelPosition::Defense : EDuelPosition::Attack;
			Card->PositionChangedTurn = Engine->TurnNumber;
			Engine->EmitVisual(EDuelVisualEventType::Position, Card->Controller, Card, 0,
				Card->Position == EDuelPosition::Attack ? TEXT("ATTACK") : TEXT("DEFENSE"));
			OnPositionChanged(*Card, Previous);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteStatModifier(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
	bool bAtk, FString& OutError)
{
	if (Context.Script.Trigger == EDEffectTrigger::Continuous
		|| Context.Script.Trigger == EDEffectTrigger::EquipContinuous
		|| Context.Script.Trigger == EDEffectTrigger::FieldContinuous)
	{
		return true;
	}
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const FString Mode = ReadString(Operation, TEXT("mode"));
	const FString Counter = ReadString(Operation, TEXT("counter"));
	int32 Amount = ReadInt(Operation, TEXT("amount"), 0);
	if (Mode == TEXT("per_counter") && !Counter.IsEmpty() && Targets.Num() > 0)
	{
		Amount *= GetCounterCount(Targets[0], Counter);
	}
	else if (!Mode.IsEmpty() && Mode != TEXT("flat"))
	{
		Amount = ComputeDynamicAmount(Operation, Context, Context.SourceCard);
	}
	const FString Duration = Context.Script.Duration;
	int32 ExpiryTurn = -1;
	if (Duration == TEXT("until_end_of_turn") || Duration == TEXT("until_end_of_battle_phase"))
	{
		ExpiryTurn = Engine->TurnNumber;
	}
	else if (Duration == TEXT("until_next_standby"))
	{
		ExpiryTurn = Engine->TurnNumber + 1;
	}
	for (int32 Uid : Targets)
	{
		const FDuelCard* TargetCard = Engine->FindCard(Uid);
		if (Mode == TEXT("set_atk") || Mode == TEXT("set_def"))
		{
			if (!TargetCard) continue;
			Amount = ReadInt(Operation, TEXT("amount"), bAtk ? TargetCard->Data.Atk : TargetCard->Data.Def)
				- (bAtk ? TargetCard->Data.Atk : TargetCard->Data.Def);
		}
		FDEffectModifier Modifier;
		Modifier.Uid = Uid;
		Modifier.Atk = bAtk ? Amount : 0;
		Modifier.Def = bAtk ? 0 : Amount;
		Modifier.ExpiryTurn = ExpiryTurn;
		Modifier.SourceId = Context.Script.Id;
		Modifier.Duration = Duration;
		LingeringModifiers.Add(Modifier);
		Engine->EmitVisual(EDuelVisualEventType::Effect, Context.SourceCard.Controller, Context.SourceCard.Uid > 0 ? &Context.SourceCard : nullptr,
			Amount, bAtk ? TEXT("ATK") : TEXT("DEF"));
	}
	return true;
}

bool FDAEffectRuntime::ExecuteDamageOrHeal(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
	bool bHeal, FString& OutError)
{
	const FString Mode = ReadString(Operation, TEXT("mode"));
	int32 Amount = ReadInt(Operation, TEXT("amount"), 0);
	if (!Mode.IsEmpty() && Mode != TEXT("flat"))
	{
		Amount = ComputeDynamicAmount(Operation, Context, Context.SourceCard);
	}
	const FString Player = ReadString(Operation, TEXT("player"), ReadString(Operation, TEXT("to"), TEXT("self")));
	const FString Reason = ReadString(Operation, TEXT("reason"), Context.Script.Id);
	if (Amount <= 0)
	{
		return true;
	}
	auto Apply = [this, Amount, bHeal, &Reason](EDuelOwner Side)
	{
		if (bHeal) Engine->GainLp(Side, Amount, Reason);
		else Engine->InflictDamage(Side, Amount, Reason);
	};
	if (Player == TEXT("both"))
	{
		Apply(Context.SourceCard.Controller);
		Apply(Other(Context.SourceCard.Controller));
	}
	else if (Player == TEXT("opponent"))
	{
		Apply(Other(Context.SourceCard.Controller));
	}
	else
	{
		Apply(Context.SourceCard.Controller);
	}
	return true;
}

bool FDAEffectRuntime::ExecuteCounter(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
	bool bRemove, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0)
	{
		Targets.Add(Context.SourceCard.Uid);
	}
	const FString Counter = ReadString(Operation, TEXT("counter"), TEXT("spell"));
	const int32 Amount = FMath::Max(1, ReadInt(Operation, TEXT("amount"), ReadInt(Operation, TEXT("count"), 1)));
	for (int32 Uid : Targets)
	{
		if (bRemove)
		{
			if (!RemoveCounter(Uid, Counter, Amount))
			{
				OutError = TEXT("counter removal failed");
				return false;
			}
		}
		else
		{
			const int32 Max = ReadInt(Operation, TEXT("max"), 99);
			if (!AddCounter(Uid, Counter, Amount, Max))
			{
				OutError = TEXT("counter addition failed");
				return false;
			}
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteReturn(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const FString Op = ReadString(Operation, TEXT("op"));
	for (int32 Uid : Targets)
	{
		FDuelCard* Card = Engine->FindCard(Uid);
		if (!Card)
		{
			continue;
		}
		const EDuelOwner Owner = Card->Owner;
		FDuelCard Copy;
		if (!Engine->RemoveFromZone(Copy, Uid))
		{
			continue;
		}
		if (Op == TEXT("return_to_extra"))
		{
			Copy.bExtra = true;
			Engine->SideRef(Owner).Extra.Add(Copy);
		}
		else if (Op == TEXT("return_to_deck"))
		{
			const FString Destination = ReadString(Operation, TEXT("destination"));
			const FString Placement = ReadString(Operation, TEXT("position"));
			if (Destination == TEXT("deck_top") || Placement == TEXT("top"))
			{
				Engine->MoveToDeckTop(Copy);
			}
			else
			{
				Engine->MoveToDeckBottom(Copy);
			}
		}
		else
		{
			Engine->MoveToHand(Copy);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteEquip(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0 || !Engine->FindSpellTrap(Context.SourceCard.Uid))
	{
		return true;
	}
	if (FDuelCard* Target = Engine->FindMonster(Targets[0]))
	{
		if (FDuelCard* Equip = Engine->FindSpellTrap(Context.SourceCard.Uid))
		{
			Engine->AttachEquip(*Equip, *Target);
			Engine->Log(FString::Printf(TEXT("%s equips to %s."), *CardName(*Equip), *CardName(*Target)), TEXT("effect"));
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteControl(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	for (int32 Uid : Targets)
	{
		if (FDuelCard* Card = Engine->FindMonster(Uid))
		{
			Card->Controller = Context.SourceCard.Controller;
			Card->TiedToUid = Context.SourceCard.Uid;
			Engine->EmitVisual(EDuelVisualEventType::Position, Card->Controller, Card, 0, TEXT("CONTROL"));
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteFusion(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	const FString FusionType = ReadString(Operation, TEXT("fusion_type"), TEXT("Polymerization"));
	if (!Engine->PerformFusion(FusionType))
	{
		OutError = FString::Printf(TEXT("fusion '%s' failed"), *FusionType);
		return false;
	}
	return true;
}

bool FDAEffectRuntime::ExecuteRitual(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	int32 MonsterId = 0;
	Operation->TryGetNumberField(TEXT("card_id"), MonsterId);
	TArray<int32> Tributes = Context.TargetUids;
	if (Tributes.Num() == 0)
	{
		OutError = TEXT("ritual requires tribute targets");
		return false;
	}

	FDuelCard* RitualMonster = nullptr;
	FDuelSide& SourceSide = Engine->SideRef(Context.SourceCard.Controller);
	if (MonsterId > 0)
	{
		for (FDuelCard& Card : SourceSide.Hand)
		{
			if (Card.Data.Id == MonsterId)
			{
				RitualMonster = &Card;
				break;
			}
		}
	}
	else
	{
		for (FDuelCard& Card : SourceSide.Hand)
		{
			if (Card.Data.CardType.Contains(TEXT("Ritual")))
			{
				RitualMonster = &Card;
				break;
			}
		}
	}
	if (!RitualMonster)
	{
		OutError = TEXT("ritual monster is not in hand");
		return false;
	}

	int32 TotalLevel = 0;
	for (int32 Uid : Tributes)
	{
		if (const FDuelCard* Tribute = Engine->FindCard(Uid))
		{
			TotalLevel += Engine->GetEffectiveLevel(*Tribute);
		}
	}
	if (TotalLevel < Engine->GetEffectiveLevel(*RitualMonster))
	{
		OutError = TEXT("ritual tribute levels are too low");
		return false;
	}
	const int32 RitualUid = RitualMonster->Uid;
	for (int32 Uid : Tributes)
	{
		FDuelCard Copy;
		if (Engine->RemoveFromZone(Copy, Uid))
		{
			Engine->CleanupEquips(Copy);
			Engine->MoveToGrave(Copy);
		}
	}
	FDuelCard Copy;
	if (!Engine->RemoveFromZone(Copy, RitualUid))
	{
		OutError = TEXT("ritual monster left the hand");
		return false;
	}
	if (!Engine->PlaceMonster(Context.SourceCard.Controller, Copy, true, EDuelPosition::Attack))
	{
		Engine->MoveToGrave(Copy);
		OutError = TEXT("ritual summon had no room");
		return false;
	}
	if (FDuelCard* Placed = Engine->FindMonster(RitualUid))
	{
		Placed->bSpecialSummoned = true;
		Engine->OnSummon(*Placed, true, 0);
		OnRitualSummon(*Placed);
	}
	return true;
}

bool FDAEffectRuntime::ExecuteReveal(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	for (int32 Uid : Targets)
	{
		if (const FDuelCard* Card = Engine->FindCard(Uid))
		{
			Engine->EmitVisual(EDuelVisualEventType::Search, Context.SourceCard.Controller, Card, 0, TEXT("REVEAL"));
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteShuffle(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	const FString Player = ReadString(Operation, TEXT("player"), ReadString(Operation, TEXT("to"), TEXT("self")));
	if (Player == TEXT("both"))
	{
		Engine->ShuffleSide(Engine->SideRef(Context.SourceCard.Controller));
		Engine->ShuffleSide(Engine->SideRef(Other(Context.SourceCard.Controller)));
	}
	else if (Player == TEXT("opponent"))
	{
		Engine->ShuffleSide(Engine->SideRef(Other(Context.SourceCard.Controller)));
	}
	else
	{
		Engine->ShuffleSide(Engine->SideRef(Context.SourceCard.Controller));
	}
	return true;
}

bool FDAEffectRuntime::ExecuteNegate(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	for (FDuelChainLink& Link : Engine->ChainLinks)
	{
		if (Targets.Contains(Link.CardUid))
		{
			Link.bNegated = true;
			NegatedActivationUids.Add(Link.CardUid);
		}
	}
	if (Context.Event.ChainLink > 0)
	{
		for (FDuelChainLink& Link : Engine->ChainLinks)
		{
			if (Link.LinkIndex == Context.Event.ChainLink && (Targets.Num() == 0 || Targets.Contains(Link.CardUid)))
			{
				Link.bNegated = true;
				NegatedActivationUids.Add(Link.CardUid);
			}
		}
	}
	if (Engine->ChainLinks.Num() > 0 && Targets.Num() == 0 && Context.Event.ChainLink <= 0)
	{
		Engine->ChainLinks.Last().bNegated = true;
		NegatedActivationUids.Add(Engine->ChainLinks.Last().CardUid);
	}
	bTrapEffectNegated = true;
	return true;
}

bool FDAEffectRuntime::ExecuteOperations(const FDEffectContext& Context, FString& OutError)
{
	for (const TSharedPtr<FJsonObject>& Operation : Context.Script.Operations)
	{
		if (!ExecuteOperation(Operation, Context, OutError))
		{
			return false;
		}
		if (Engine->bWinnerSet)
		{
			break;
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteOperationsList(const TArray<TSharedPtr<FJsonObject>>& Operations,
	const FDEffectContext& Context, FString& OutError)
{
	for (const TSharedPtr<FJsonObject>& Operation : Operations)
	{
		if (!ExecuteOperation(Operation, Context, OutError))
		{
			return false;
		}
		if (Engine->bWinnerSet)
		{
			break;
		}
	}
	return true;
}

int32 FDAEffectRuntime::CountZoneForOperation(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, const FDuelCard& Subject, const FString& Zone,
	const TSharedPtr<FJsonObject>& Filter) const
{
	int32 Count = 0;
	for (const FDuelCard& Card : CollectCandidates(Zone, Context.SourceCard, Context.Event))
	{
		if (!Filter.IsValid() || EvaluateCondition(Filter, Card, Context.SourceCard, Context.Event))
		{
			++Count;
		}
	}
	(void)Subject;
	return Count;
}

int32 FDAEffectRuntime::ComputeDynamicAmount(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, const FDuelCard& Subject) const
{
	const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("flat"));
	int32 Base = ReadInt(Operation, TEXT("amount"), 0);
	const int32 Multiplier = FMath::Max(1, ReadInt(Operation, TEXT("multiplier"), 1));
	const int32 Divisor = FMath::Max(1, ReadInt(Operation, TEXT("divisor"), 1));
	const TSharedPtr<FJsonObject>* Filter = nullptr;
	Operation->TryGetObjectField(TEXT("count_filter"), Filter);

	int32 Count = 0;
	bool bHasCount = false;
	const FString CountZone = ReadString(Operation, TEXT("count_zone"));
	if (!CountZone.IsEmpty())
	{
		bHasCount = true;
		Count += CountZoneForOperation(Operation, Context, Subject, CountZone, Filter ? *Filter : nullptr);
	}
	const TArray<TSharedPtr<FJsonValue>>* CountZones = nullptr;
	if (Operation->TryGetArrayField(TEXT("count_zones"), CountZones) && CountZones)
	{
		bHasCount = true;
		for (const TSharedPtr<FJsonValue>& Value : *CountZones)
		{
			if (Value.IsValid())
			{
				Count += CountZoneForOperation(Operation, Context, Subject, Value->AsString(), Filter ? *Filter : nullptr);
			}
		}
	}

	const FDuelCard* LiveSubject = Engine ? Engine->FindCard(Subject.Uid) : nullptr;
	const FDuelCard& StatSubject = LiveSubject ? *LiveSubject : Subject;
	const EDuelOwner Controller = Context.SourceCard.Controller;

	if (Mode == TEXT("per_counter"))
	{
		const FString Counter = ReadString(Operation, TEXT("counter"), TEXT("spell"));
		return Base * GetCounterCount(StatSubject.Uid, Counter);
	}
	if (Mode == TEXT("per_level"))
	{
		return Base * Engine->GetEffectiveLevel(StatSubject);
	}
	if (Mode == TEXT("per_atk") || Mode == TEXT("atk"))
	{
		return Engine->GetAtk(StatSubject) * Multiplier / Divisor;
	}
	if (Mode == TEXT("per_def") || Mode == TEXT("def"))
	{
		return Engine->GetDef(StatSubject) * Multiplier / Divisor;
	}
	if (Mode == TEXT("half_atk"))
	{
		return Engine->GetAtk(StatSubject) / 2;
	}
	if (Mode == TEXT("half_def"))
	{
		return Engine->GetDef(StatSubject) / 2;
	}
	if (Mode == TEXT("per_hand"))
	{
		return Base * Engine->GetSide(Controller).Hand.Num();
	}
	if (Mode == TEXT("per_graveyard"))
	{
		return Base * Engine->GetSide(Controller).Graveyard.Num();
	}
	if (Mode == TEXT("per_banished"))
	{
		return Base * Engine->GetSide(Controller).Banished.Num();
	}
	if (Mode == TEXT("per_deck"))
	{
		return Base * Engine->GetSide(Controller).Deck.Num();
	}
	if (Mode == TEXT("per_extra"))
	{
		return Base * Engine->GetSide(Controller).Extra.Num();
	}
	if (Mode == TEXT("per_monster"))
	{
		int32 Monsters = 0;
		for (const FDuelCard& Card : Engine->GetSide(Controller).Monsters)
		{
			if (Card.IsValid() && Card.bFaceUp) ++Monsters;
		}
		return Base * Monsters;
	}
	if (Mode == TEXT("per_spell_trap"))
	{
		return Base * Engine->GetSide(Controller).Spells.FilterByPredicate(
			[](const FDuelCard& Card) { return Card.IsValid(); }).Num();
	}
	if (bHasCount || Mode == TEXT("per_card") || Mode == TEXT("count"))
	{
		return Base * Count * Multiplier / Divisor;
	}
	return Base * Multiplier / Divisor;
}

bool FDAEffectRuntime::ExecuteAttackLock(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, FString& OutError)
{
	(void)OutError;
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	const FString Op = ReadString(Operation, TEXT("op"));
	const FString Mode = ReadString(Operation, TEXT("mode"), Op == TEXT("must_attack") ? TEXT("must_attack") : TEXT("cannot_attack"));
	const FString Player = ReadString(Operation, TEXT("player"), TEXT("self"));
	const FString Duration = Context.Script.Duration;
	const bool bTurnScoped = Duration == TEXT("until_end_of_turn");
	if (bTurnScoped)
	{
		AttackRestrictionExpiryTurn = Engine->TurnNumber;
	}

	auto ApplySide = [this, &Mode, bTurnScoped](EDuelOwner Side)
	{
		if (Mode == TEXT("max_attackers") || Mode == TEXT("only_one_attacker"))
		{
			MaxAttackersThisTurn.Add(static_cast<uint8>(Side), 1);
		}
		else if (Mode == TEXT("cannot_attack_directly"))
		{
			CannotAttackDirectlySidesThisTurn.Add(static_cast<uint8>(Side));
		}
		else if (Mode == TEXT("must_attack"))
		{
			for (FDuelCard& Card : Engine->SideRef(Side).Monsters)
			{
				if (Card.IsValid()) MustAttackUids.Add(Card.Uid);
			}
		}
		else if (bTurnScoped)
		{
			CannotAttackSidesThisTurn.Add(static_cast<uint8>(Side));
		}
		else
		{
			for (FDuelCard& Card : Engine->SideRef(Side).Monsters)
			{
				if (Card.IsValid()) CannotAttackUids.Add(Card.Uid);
			}
		}
	};

	const bool bSideWide = Targets.Num() == 0 || ReadBool(Operation, TEXT("side_wide"), false);
	if (bSideWide)
	{
		if (Player == TEXT("both")) { ApplySide(EDuelOwner::Player); ApplySide(EDuelOwner::Opponent); }
		else if (Player == TEXT("opponent")) ApplySide(Other(Context.SourceCard.Controller));
		else ApplySide(Context.SourceCard.Controller);
	}
	for (int32 Uid : Targets)
	{
		const FDuelCard* Card = Engine->FindMonster(Uid);
		if (!Card)
		{
			continue;
		}
		if (Mode == TEXT("max_attackers") || Mode == TEXT("only_one_attacker"))
		{
			MaxAttackersThisTurn.Add(static_cast<uint8>(Card->Controller), 1);
		}
		else if (Mode == TEXT("cannot_attack_directly"))
		{
			DirectAttackForbiddenUids.Add(Uid);
		}
		else if (Mode == TEXT("must_attack"))
		{
			MustAttackUids.Add(Uid);
		}
		else
		{
			CannotAttackUids.Add(Uid);
			if (bTurnScoped)
			{
				CannotAttackSidesThisTurn.Add(static_cast<uint8>(Card->Controller));
			}
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteAttackDirectly(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, FString& OutError)
{
	(void)OutError;
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0)
	{
		Targets.Add(Context.SourceCard.Uid);
	}
	for (int32 Uid : Targets)
	{
		DirectAttackAllowedUids.Add(Uid);
	}
	return true;
}

bool FDAEffectRuntime::ExecutePiercing(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, FString& OutError)
{
	(void)OutError;
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0)
	{
		Targets.Add(Context.SourceCard.Uid);
	}
	for (int32 Uid : Targets)
	{
		PiercingUids.Add(Uid);
	}
	return true;
}

bool FDAEffectRuntime::ExecuteDestructionReplacement(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, FString& OutError)
{
	(void)OutError;
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0)
	{
		Targets.Add(Context.SourceCard.Uid);
	}
	const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("cannot_be_destroyed"));
	for (int32 Uid : Targets)
	{
		if (Mode.Contains(TEXT("battle")) && !Mode.Contains(TEXT("effect")))
		{
			PreventBattleDestructionUids.Add(Uid);
		}
		else if (Mode.Contains(TEXT("banish")))
		{
			BanishInsteadOfGraveUids.Add(Uid);
		}
		else if (Mode.Contains(TEXT("destroy") ) && Mode.Contains(TEXT("cannot")))
		{
			PreventDestructionUids.Add(Uid);
		}
		else
		{
			PreventDestructionUids.Add(Uid);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecutePositionLock(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, FString& OutError)
{
	(void)OutError;
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0)
	{
		Targets.Add(Context.SourceCard.Uid);
	}
	const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("cannot_change"));
	for (int32 Uid : Targets)
	{
		if (Mode.Contains(TEXT("end")) || Mode.Contains(TEXT("battle")))
		{
			EndBattleDefenseUids.Add(Uid);
		}
		else
		{
			CannotChangePositionUids.Add(Uid);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteSpiritReturn(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, FString& OutError)
{
	(void)OutError;
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0)
	{
		Targets.Add(Context.SourceCard.Uid);
	}
	for (int32 Uid : Targets)
	{
		SpiritReturnUids.Add(Uid);
	}
	return true;
}

bool FDAEffectRuntime::ExecuteUnionEquip(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, bool bUnequip, FString& OutError)
{
	if (!bUnequip)
	{
		FDuelCard* Source = Engine->FindMonster(Context.SourceCard.Uid);
		if (!Source)
		{
			OutError = TEXT("union source is not a face-up monster");
			return false;
		}
		TArray<int32> Targets;
		ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
		const int32 TargetUid = Targets.Num() > 0 ? Targets[0] : 0;
		FDuelCard* Target = Engine->FindMonster(TargetUid);
		if (!Target || Target->Uid == Source->Uid)
		{
			OutError = TEXT("union equip needs another monster target");
			return false;
		}
		const int32 SourceUid = Source->Uid;
		FDuelCard Copy;
		if (!Engine->RemoveFromZone(Copy, SourceUid))
		{
			OutError = TEXT("union source left the field");
			return false;
		}
		if (!Engine->PlaceSpellTrap(Copy.Owner, Copy, true, false))
		{
			Engine->MoveToGrave(Copy);
			OutError = TEXT("no Spell/Trap zone for the Union monster");
			return false;
		}
		if (FDuelCard* Equip = Engine->FindSpellTrap(SourceUid))
		{
			Equip->EquippedToUid = TargetUid;
		}
		Engine->Log(FString::Printf(TEXT("%s equips to %s as a Union monster."), *CardName(Copy), *CardName(*Target)), TEXT("effect"));
		RecomputeContinuous();
		return true;
	}

	FDuelCard* Equip = Engine->FindSpellTrap(Context.SourceCard.Uid);
	if (!Equip)
	{
		OutError = TEXT("union card is not equipped");
		return false;
	}
	const int32 EquipUid = Equip->Uid;
	FDuelCard Copy;
	if (!Engine->RemoveFromZone(Copy, EquipUid))
	{
		OutError = TEXT("union card left the field");
		return false;
	}
	Copy.EquippedToUid = 0;
	const FString PositionValue = ReadString(Operation, TEXT("position"), TEXT("attack"));
	const EDuelPosition Position = PositionValue == TEXT("defense") ? EDuelPosition::Defense : EDuelPosition::Attack;
	if (!Engine->PlaceMonster(Copy.Owner, Copy, true, Position))
	{
		Engine->MoveToGrave(Copy);
		OutError = TEXT("no monster zone for the Union monster");
		return false;
	}
	if (FDuelCard* Placed = Engine->FindMonster(EquipUid))
	{
		Placed->bSpecialSummoned = true;
		Engine->OnSummon(*Placed, true, 0);
	}
	RecomputeContinuous();
	return true;
}

bool FDAEffectRuntime::ExecuteInherentSummon(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, FString& OutError)
{
	TArray<int32> Targets;
	ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
	if (Targets.Num() == 0)
	{
		Targets.Add(Context.SourceCard.Uid);
	}
	const FString PositionValue = ReadString(Operation, TEXT("position"), TEXT("attack"));
	const EDuelPosition Position = PositionValue == TEXT("defense") ? EDuelPosition::Defense : EDuelPosition::Attack;
	for (int32 Uid : Targets)
	{
		FDuelCard* Card = Engine->FindCard(Uid);
		if (!Card)
		{
			continue;
		}
		FDuelCard Copy;
		if (!Engine->RemoveFromZone(Copy, Uid))
		{
			continue;
		}
		if (!Engine->PlaceMonster(Copy.Owner, Copy, true, Position))
		{
			Engine->MoveToGrave(Copy);
			continue;
		}
		if (FDuelCard* Placed = Engine->FindMonster(Uid))
		{
			Placed->bSpecialSummoned = true;
			Engine->Log(FString::Printf(TEXT("%s Special Summons %s by its inherent procedure."),
				*Engine->GetSide(Copy.Owner).Name, *CardName(*Placed)), TEXT("summon"));
			Engine->OnSummon(*Placed, true, 0);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteRandomOutcome(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, bool bDie, FString& OutError)
{
	const bool bCoin = !bDie;
	const int32 Count = FMath::Clamp(ReadInt(Operation, TEXT("count"), 1), 1, 10);
	LastRandomResults.Reset();
	int32 Sum = 0;
	int32 Heads = 0;
	for (int32 I = 0; I < Count; ++I)
	{
		const int32 Result = Engine->Random.RandRange(1, bDie ? 6 : 2);
		LastRandomResults.Add(Result);
		Sum += Result;
		if (bCoin && Result == 1)
		{
			++Heads;
		}
	}
	LastRandomResult = Sum;
	int32 SuccessMin = ReadInt(Operation, TEXT("success_min"), ReadInt(Operation, TEXT("threshold"), bCoin ? 1 : 1));
	int32 SuccessMax = ReadInt(Operation, TEXT("success_max"), 999);
	if (bCoin && ReadInt(Operation, TEXT("success_min"), -1) < 0 && !Operation->HasField(TEXT("threshold")))
	{
		SuccessMin = 1;
	}
	const int32 CompareValue = bCoin ? Heads : Sum;
	const bool bSuccess = CompareValue >= SuccessMin && CompareValue <= SuccessMax;

	Engine->EmitVisual(EDuelVisualEventType::Effect, Context.SourceCard.Controller, &Context.SourceCard,
		bCoin ? Heads : Sum, bCoin ? (bSuccess ? TEXT("COIN HEADS") : TEXT("COIN TAILS")) : TEXT("DIE"));

	auto RunBranch = [this, &Operation, &Context, &OutError](const TCHAR* Key) -> bool
	{
		const TArray<TSharedPtr<FJsonValue>>* Branch = nullptr;
		if (!Operation->TryGetArrayField(Key, Branch) || !Branch)
		{
			return true;
		}
		TArray<TSharedPtr<FJsonObject>> BranchOps;
		for (const TSharedPtr<FJsonValue>& Value : *Branch)
		{
			if (Value.IsValid() && Value->AsObject().IsValid())
			{
				BranchOps.Add(Value->AsObject());
			}
		}
		return ExecuteOperationsList(BranchOps, Context, OutError);
	};
	if (!RunBranch(bSuccess ? TEXT("success_operations") : TEXT("failure_operations")))
	{
		return false;
	}
	return true;
}

bool FDAEffectRuntime::ApplyContinuousStat(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context, bool bAtk)
{
	const FDuelCard& Card = Context.SourceCard;
	TArray<int32> Targets;
	FString TargetString;
	const bool bStringTarget = Operation->TryGetStringField(TEXT("target"), TargetString);
	if (bStringTarget && (TargetString == TEXT("$self") || TargetString == TEXT("$equipped")))
	{
		if (Context.Script.Trigger == EDEffectTrigger::EquipContinuous || TargetString == TEXT("$equipped"))
		{
			if (Card.EquippedToUid != 0) Targets.Add(Card.EquippedToUid);
		}
		else if (Context.Script.Trigger == EDEffectTrigger::FieldContinuous)
		{
			for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
			{
				for (const FDuelCard& Monster : Engine->GetSide(Side).Monsters)
				{
					if (Monster.IsValid() && Monster.bFaceUp) Targets.Add(Monster.Uid);
				}
			}
		}
		else
		{
			Targets.Add(Card.Uid);
		}
	}
	else if (Operation->HasField(TEXT("target")))
	{
		const TSharedPtr<FJsonObject>* TargetObject = nullptr;
		Operation->TryGetObjectField(TEXT("target"), TargetObject);
		bool bWholeZoneTarget = false;
		if (TargetObject && TargetObject->IsValid())
		{
			const FString Zone = ReadString(*TargetObject, TEXT("zone"));
			bWholeZoneTarget = !(*TargetObject)->HasField(TEXT("count"))
				&& (Zone == TEXT("all_monsters") || Zone == TEXT("all_spell_traps")
					|| Zone == TEXT("all_cards") || Zone == TEXT("all_hands")
					|| Zone == TEXT("all_cards_and_hands"));
		}
		if (bWholeZoneTarget)
		{
			const FString Zone = ReadString(*TargetObject, TEXT("zone"));
			const TSharedPtr<FJsonObject>* Filter = nullptr;
			(*TargetObject)->TryGetObjectField(TEXT("filter"), Filter);
			for (const FDuelCard& Candidate : CollectCandidates(Zone, Card, Context.Event))
			{
				if (MatchesFilter(Candidate, Filter ? *Filter : nullptr, Card, Context.Event))
				{
					Targets.Add(Candidate.Uid);
				}
			}
		}
		else
		{
			ResolveOperationTargets(Operation, Context, Card, Context.Event, Targets);
		}
	}
	else if (Context.Script.Trigger == EDEffectTrigger::EquipContinuous)
	{
		if (Card.EquippedToUid != 0) Targets.Add(Card.EquippedToUid);
	}
	else if (Context.Script.Trigger == EDEffectTrigger::FieldContinuous)
	{
		for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			for (const FDuelCard& Monster : Engine->GetSide(Side).Monsters)
			{
				if (Monster.IsValid() && Monster.bFaceUp) Targets.Add(Monster.Uid);
			}
		}
	}
	else
	{
		Targets.Add(Card.Uid);
	}

	const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("flat"));
	for (int32 Uid : Targets)
	{
		const FDuelCard* Target = Engine->FindCard(Uid);
		if (!Target || !Target->IsMonster())
		{
			continue;
		}
		int32 Amount = ComputeDynamicAmount(Operation, Context, *Target);
		if (Mode == TEXT("set_atk") || Mode == TEXT("set_def"))
		{
			const int32 Wanted = ReadInt(Operation, TEXT("amount"), bAtk ? Target->Data.Atk : Target->Data.Def);
			Amount = Wanted - (bAtk ? Target->Data.Atk : Target->Data.Def);
		}
		if (bAtk)
		{
			ContinuousAtkModifiers.FindOrAdd(Uid) += Amount;
		}
		else
		{
			ContinuousDefModifiers.FindOrAdd(Uid) += Amount;
		}
	}
	return true;
}

bool FDAEffectRuntime::ApplyContinuousRestriction(const TSharedPtr<FJsonObject>& Operation,
	const FDEffectContext& Context)
{
	const FDuelCard& Card = Context.SourceCard;
	const FString Op = ReadString(Operation, TEXT("op"));
	TArray<int32> Targets;
	if (Operation->HasField(TEXT("target")))
	{
		ResolveOperationTargets(Operation, Context, Card, Context.Event, Targets);
	}
	else if (Context.Script.Trigger == EDEffectTrigger::EquipContinuous)
	{
		if (Card.EquippedToUid != 0) Targets.Add(Card.EquippedToUid);
	}
	else if (Context.Script.Trigger == EDEffectTrigger::FieldContinuous)
	{
		for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			for (const FDuelCard& Monster : Engine->GetSide(Side).Monsters)
			{
				if (Monster.IsValid() && Monster.bFaceUp) Targets.Add(Monster.Uid);
			}
		}
	}
	else
	{
		Targets.Add(Card.Uid);
	}

	const FString Mode = ReadString(Operation, TEXT("mode"), Op == TEXT("must_attack") ? TEXT("must_attack") : TEXT("cannot_attack"));
	const FString Player = ReadString(Operation, TEXT("player"), TEXT("self"));
	auto ApplySide = [this, &Mode](EDuelOwner Side)
	{
		if (Mode == TEXT("max_attackers") || Mode == TEXT("only_one_attacker"))
		{
			MaxAttackersPerSide.Add(static_cast<uint8>(Side), 1);
		}
		else if (Mode == TEXT("cannot_attack_directly"))
		{
			for (const FDuelCard& Monster : Engine->GetSide(Side).Monsters)
			{
				if (Monster.IsValid()) ContinuousDirectAttackForbiddenUids.Add(Monster.Uid);
			}
		}
		else if (Mode == TEXT("must_attack"))
		{
			for (const FDuelCard& Monster : Engine->GetSide(Side).Monsters)
			{
				if (Monster.IsValid()) ContinuousMustAttackUids.Add(Monster.Uid);
			}
		}
		else
		{
			for (const FDuelCard& Monster : Engine->GetSide(Side).Monsters)
			{
				if (Monster.IsValid()) ContinuousCannotAttackUids.Add(Monster.Uid);
			}
		}
	};
	if (Targets.Num() == 0 || ReadBool(Operation, TEXT("side_wide"), false))
	{
		if (Player == TEXT("both")) { ApplySide(EDuelOwner::Player); ApplySide(EDuelOwner::Opponent); }
		else if (Player == TEXT("opponent")) ApplySide(Other(Card.Controller));
		else ApplySide(Card.Controller);
	}
	for (int32 Uid : Targets)
	{
		if (Mode == TEXT("max_attackers") || Mode == TEXT("only_one_attacker"))
		{
			if (const FDuelCard* Monster = Engine->FindMonster(Uid))
			{
				MaxAttackersPerSide.Add(static_cast<uint8>(Monster->Controller), 1);
			}
		}
		else if (Mode == TEXT("cannot_attack_directly"))
		{
			ContinuousDirectAttackForbiddenUids.Add(Uid);
		}
		else if (Mode == TEXT("must_attack"))
		{
			ContinuousMustAttackUids.Add(Uid);
		}
		else
		{
			ContinuousCannotAttackUids.Add(Uid);
		}
	}
	return true;
}

bool FDAEffectRuntime::ExecuteOperation(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
	FString& OutError)
{
	const FString Op = ReadString(Operation, TEXT("op"));
	if (Op == TEXT("draw")) return ExecuteDraw(Operation, Context, OutError);
	if (Op == TEXT("discard")) return ExecuteDiscard(Operation, Context, OutError);
	if (Op == TEXT("search")) return ExecuteSearch(Operation, Context, OutError);
	if (Op == TEXT("mill")) return ExecuteMill(Operation, Context, OutError);
	if (Op == TEXT("banish")) return ExecuteBanish(Operation, Context, OutError);
	if (Op == TEXT("destroy")) return ExecuteDestroy(Operation, Context, OutError);
	if (Op == TEXT("send_to_grave") || Op == TEXT("send_to_graveyard")) return ExecuteSendToGrave(Operation, Context, OutError);
	if (Op == TEXT("summon")) return ExecuteSummon(Operation, Context, false, OutError);
	if (Op == TEXT("special_summon")) return ExecuteSummon(Operation, Context, true, OutError);
	if (Op == TEXT("set")) return ExecuteSet(Operation, Context, OutError);
	if (Op == TEXT("change_position")) return ExecutePosition(Operation, Context, OutError);
	if (Op == TEXT("modify_atk")) return ExecuteStatModifier(Operation, Context, true, OutError);
	if (Op == TEXT("modify_def")) return ExecuteStatModifier(Operation, Context, false, OutError);
	if (Op == TEXT("damage") || Op == TEXT("inflict_damage")) return ExecuteDamageOrHeal(Operation, Context, false, OutError);
	if (Op == TEXT("heal") || Op == TEXT("gain_lp")) return ExecuteDamageOrHeal(Operation, Context, true, OutError);
	if (Op == TEXT("add_counter") || Op == TEXT("place_counter")) return ExecuteCounter(Operation, Context, false, OutError);
	if (Op == TEXT("remove_counter")) return ExecuteCounter(Operation, Context, true, OutError);
	if (Op == TEXT("return_to_hand") || Op == TEXT("return_to_deck") || Op == TEXT("return_to_extra")) return ExecuteReturn(Operation, Context, OutError);
	if (Op == TEXT("equip")) return ExecuteEquip(Operation, Context, OutError);
	if (Op == TEXT("take_control") || Op == TEXT("control")) return ExecuteControl(Operation, Context, OutError);
	if (Op == TEXT("fusion")) return ExecuteFusion(Operation, Context, OutError);
	if (Op == TEXT("ritual")) return ExecuteRitual(Operation, Context, OutError);
	if (Op == TEXT("reveal")) return ExecuteReveal(Operation, Context, OutError);
	if (Op == TEXT("shuffle")) return ExecuteShuffle(Operation, Context, OutError);
	if (Op == TEXT("negate")) return ExecuteNegate(Operation, Context, OutError);
	if (Op == TEXT("negate_activation")) return ExecuteNegate(Operation, Context, OutError);
	if (Op == TEXT("lock_activation"))
	{
		const FString Mode = ReadString(Operation, TEXT("mode"));
		if (Mode.Contains(TEXT("spell"))) bSpellActivationLocked = true;
		if (Mode.Contains(TEXT("monster"))) bMonsterEffectLocked = true;
		if (Mode.Contains(TEXT("trap")) || Mode.IsEmpty()) bTrapActivationLocked = true;
		if (Mode.Contains(TEXT("effect"))) bTrapEffectNegated = true;
		return true;
	}
	if (Op == TEXT("allow_fusion"))
	{
		AllowedFusionTypes.Add(ReadString(Operation, TEXT("fusion_type"), TEXT("Fusion Gate")));
		return true;
	}
	if (Op == TEXT("redirect_battle_damage")) { RedirectBattleDamageUids.Add(Context.SourceCard.Uid); return true; }
	if (Op == TEXT("prevent_battle_damage")) { PreventBattleDamageSides.Add(static_cast<uint8>(Context.SourceCard.Controller)); return true; }
	if (Op == TEXT("battle_damage_zero")) { BattleDamageZeroUids.Add(Context.SourceCard.Uid); return true; }
	if (Op == TEXT("battle_damage_modifier"))
	{
		TArray<int32> Targets;
		ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
		if (Targets.Num() == 0) Targets.Add(Context.SourceCard.Uid);
		const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("zero"));
		const float Multiplier = Mode == TEXT("half") ? 0.5f : (Mode == TEXT("double") ? 2.f : 0.f);
		for (int32 Uid : Targets)
		{
			BattleDamageMultipliers.Add(Uid, Multiplier);
		}
		return true;
	}
	if (Op == TEXT("skip_phase") || Op == TEXT("skip_draw")) { Engine->SideRef(Context.SourceCard.Controller).bSkipDraw = true; return true; }
	if (Op == TEXT("extra_attack"))
	{
		TArray<int32> Targets;
		ResolveOperationTargets(Operation, Context, Context.SourceCard, Context.Event, Targets);
		if (Targets.Num() == 0) Targets = Context.TargetUids;
		for (int32 Uid : Targets)
		{
			if (FDuelCard* Card = Engine->FindMonster(Uid))
			{
				Card->ExtraAttacks += FMath::Max(1, ReadInt(Operation, TEXT("count"), 1));
			}
		}
		return true;
	}
	if (Op == TEXT("attack_directly")) return ExecuteAttackDirectly(Operation, Context, OutError);
	if (Op == TEXT("attack_lock") || Op == TEXT("must_attack")) return ExecuteAttackLock(Operation, Context, OutError);
	if (Op == TEXT("negate_attack")) { bAttackNegated = true; return true; }
	if (Op == TEXT("piercing")) return ExecutePiercing(Operation, Context, OutError);
	if (Op == TEXT("destruction_replacement") || Op == TEXT("destroy_replace"))
	{
		return ExecuteDestructionReplacement(Operation, Context, OutError);
	}
	if (Op == TEXT("battle_position_lock")) return ExecutePositionLock(Operation, Context, OutError);
	if (Op == TEXT("spirit_return")) return ExecuteSpiritReturn(Operation, Context, OutError);
	if (Op == TEXT("summon_lock"))
	{
		const FString Player = ReadString(Operation, TEXT("player"), TEXT("both"));
		const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("both"));
		const bool bSpecialOnly = Mode.Contains(TEXT("special_only"));
		const bool bNormalOnly = Mode.Contains(TEXT("normal_only"));
		const bool bLockSpecial = !bNormalOnly && (bSpecialOnly || Mode.Contains(TEXT("special")) || Mode == TEXT("both"));
		const bool bLockNormal = !bSpecialOnly && (bNormalOnly || Mode.Contains(TEXT("normal")) || Mode == TEXT("both"));
		auto LockSide = [this, bLockSpecial, bLockNormal](EDuelOwner Side)
		{
			if (bLockNormal) NormalSummonLockSides.Add(static_cast<uint8>(Side));
			if (bLockSpecial) SpecialSummonLockSides.Add(static_cast<uint8>(Side));
		};
		if (Player == TEXT("both")) { LockSide(EDuelOwner::Player); LockSide(EDuelOwner::Opponent); }
		else if (Player == TEXT("opponent")) LockSide(Other(Context.SourceCard.Controller));
		else LockSide(Context.SourceCard.Controller);
		return true;
	}
	if (Op == TEXT("union_equip")) return ExecuteUnionEquip(Operation, Context, false, OutError);
	if (Op == TEXT("union_unequip")) return ExecuteUnionEquip(Operation, Context, true, OutError);
	if (Op == TEXT("inherent_special_summon")) return ExecuteInherentSummon(Operation, Context, OutError);
	if (Op == TEXT("declare_name") || Op == TEXT("look_at_deck") || Op == TEXT("redirect_attack"))
	{
		Engine->Log(FString::Printf(TEXT("Effect operation '%s' is recorded but has no visual callback."), *Op), TEXT("effect"));
		return true;
	}
	if (Op == TEXT("roll_die") || Op == TEXT("toss_coin"))
	{
		return ExecuteRandomOutcome(Operation, Context, Op == TEXT("roll_die"), OutError);
	}
	if (Op == TEXT("excavate"))
	{
		const int32 Count = FMath::Max(1, ReadInt(Operation, TEXT("count"), 1));
		Engine->Mill(Context.SourceCard.Controller, Count);
		return true;
	}
	if (Op == TEXT("copy"))
	{
		int32 SourceId = 0;
		Operation->TryGetNumberField(TEXT("card_id"), SourceId);
		if (SourceId > 0 && Engine)
		{
			if (const FCardRecord* Record = Engine->Database ? Engine->Database->FindCard(SourceId) : nullptr)
			{
				for (int32 Uid : Context.TargetUids)
				{
					if (FDuelCard* Card = Engine->FindCard(Uid))
					{
						Card->Data = *Record;
					}
				}
			}
		}
		return true;
	}

	OutError = FString::Printf(TEXT("unsupported operation '%s'"), *Op);
	return false;
}

void FDAEffectRuntime::RecomputeContinuous()
{
	if (!Engine || bRecomputing)
	{
		return;
	}
	bRecomputing = true;
	ContinuousAtkModifiers.Reset();
	ContinuousDefModifiers.Reset();
	AllowedFusionTypes.Reset();
	RedirectBattleDamageUids.Reset();
	PreventBattleDamageSides.Reset();
	BattleDamageZeroUids.Reset();
	ContinuousCannotAttackUids.Reset();
	ContinuousMustAttackUids.Reset();
	ContinuousDirectAttackAllowedUids.Reset();
	ContinuousDirectAttackForbiddenUids.Reset();
	ContinuousPiercingUids.Reset();
	ContinuousExtraAttackUids.Reset();
	ContinuousCannotChangePositionUids.Reset();
	ContinuousPreventDestructionUids.Reset();
	ContinuousPreventBattleDestructionUids.Reset();
	ContinuousBanishInsteadOfGraveUids.Reset();
	ContinuousSpiritReturnUids.Reset();
	MaxAttackersPerSide.Reset();
	ContinuousNormalSummonLockSides.Reset();
	ContinuousSpecialSummonLockSides.Reset();
	ContinuousBattleDamageMultipliers.Reset();
	bTrapActivationLocked = false;
	bTrapEffectNegated = false;
	bSpellActivationLocked = false;
	bMonsterEffectLocked = false;

	auto ProcessCard = [this](const FDuelCard& Card, EDuelOwner Side)
	{
		if (!Card.IsValid() || !Card.bFaceUp)
		{
			return;
		}
		const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card.Data.Id);
		if (!Scripts)
		{
			return;
		}
		for (const FDEffectScript& Script : *Scripts)
		{
			if (Script.Trigger != EDEffectTrigger::Continuous
				&& Script.Trigger != EDEffectTrigger::EquipContinuous
				&& Script.Trigger != EDEffectTrigger::FieldContinuous)
			{
				continue;
			}
			const FDuelCard* EquippedTarget = nullptr;
			if (Script.Trigger == EDEffectTrigger::EquipContinuous)
			{
				if (Card.EquippedToUid == 0)
				{
					continue;
				}
				EquippedTarget = Engine->FindMonster(Card.EquippedToUid);
				if (!EquippedTarget)
				{
					continue;
				}
			}
			const FDuelCard& Subject = EquippedTarget ? *EquippedTarget : Card;
			FDEffectEvent Event;
			Event.Trigger = Script.Trigger;
			Event.SourceCard = Card;
			Event.EventCard = Subject;
			Event.SourceController = Side;
			Event.EventController = Subject.Controller;
			if (!EvaluateCondition(Script.Condition, Subject, Card, Event, true))
			{
				continue;
			}
			FDEffectContext Context;
			Context.Script = Script;
			Context.SourceCard = Card;
			Context.Event = Event;
			Context.Chooser = Side;
			for (const TSharedPtr<FJsonObject>& Operation : Script.Operations)
			{
				const FString Op = ReadString(Operation, TEXT("op"));
				if (Op == TEXT("modify_atk") || Op == TEXT("modify_def"))
				{
					ApplyContinuousStat(Operation, Context, Op == TEXT("modify_atk"));
				}
				else if (Op == TEXT("attack_lock") || Op == TEXT("must_attack"))
				{
					ApplyContinuousRestriction(Operation, Context);
				}
				else if (Op == TEXT("lock_activation"))
				{
					const FString Mode = ReadString(Operation, TEXT("mode"));
					if (Mode.Contains(TEXT("spell"))) bSpellActivationLocked = true;
					if (Mode.Contains(TEXT("monster"))) bMonsterEffectLocked = true;
					if (Mode.Contains(TEXT("trap")) || Mode.IsEmpty()) bTrapActivationLocked = true;
					if (Mode.Contains(TEXT("effect"))) bTrapEffectNegated = true;
				}
				else if (Op == TEXT("allow_fusion"))
				{
					AllowedFusionTypes.Add(ReadString(Operation, TEXT("fusion_type"), TEXT("Fusion Gate")));
				}
				else if (Op == TEXT("redirect_battle_damage"))
				{
					RedirectBattleDamageUids.Add(Card.Uid);
				}
				else if (Op == TEXT("prevent_battle_damage"))
				{
					PreventBattleDamageSides.Add(static_cast<uint8>(Side));
				}
				else if (Op == TEXT("battle_damage_zero"))
				{
					BattleDamageZeroUids.Add(Card.Uid);
				}
				else if (Op == TEXT("attack_directly"))
				{
					TArray<int32> Targets;
					FString TargetString;
					if (Operation->TryGetStringField(TEXT("target"), TargetString) && TargetString == TEXT("$self"))
					{
						Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					}
					else if (Operation->HasField(TEXT("target")))
					{
						ResolveOperationTargets(Operation, Context, Card, Event, Targets);
					}
					else
					{
						Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					}
					for (int32 Uid : Targets)
					{
						ContinuousDirectAttackAllowedUids.Add(Uid);
					}
				}
				else if (Op == TEXT("piercing"))
				{
					TArray<int32> Targets;
					if (Operation->HasField(TEXT("target")))
					{
						ResolveOperationTargets(Operation, Context, Card, Event, Targets);
					}
					if (Targets.Num() == 0) Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					for (int32 Uid : Targets)
					{
						ContinuousPiercingUids.Add(Uid);
					}
				}
				else if (Op == TEXT("extra_attack"))
				{
					TArray<int32> Targets;
					if (Operation->HasField(TEXT("target")))
					{
						ResolveOperationTargets(Operation, Context, Card, Event, Targets);
					}
					if (Targets.Num() == 0) Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					for (int32 Uid : Targets)
					{
						ContinuousExtraAttackUids.Add(Uid);
					}
				}
				else if (Op == TEXT("destruction_replacement") || Op == TEXT("destroy_replace"))
				{
					TArray<int32> Targets;
					if (Operation->HasField(TEXT("target")))
					{
						ResolveOperationTargets(Operation, Context, Card, Event, Targets);
					}
					if (Targets.Num() == 0) Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("cannot_be_destroyed"));
					for (int32 Uid : Targets)
					{
						if (Mode.Contains(TEXT("battle")) && !Mode.Contains(TEXT("effect")))
						{
							ContinuousPreventBattleDestructionUids.Add(Uid);
						}
						else if (Mode.Contains(TEXT("banish")))
						{
							ContinuousBanishInsteadOfGraveUids.Add(Uid);
						}
						else
						{
							ContinuousPreventDestructionUids.Add(Uid);
						}
					}
				}
				else if (Op == TEXT("battle_position_lock"))
				{
					TArray<int32> Targets;
					if (Operation->HasField(TEXT("target")))
					{
						ResolveOperationTargets(Operation, Context, Card, Event, Targets);
					}
					if (Targets.Num() == 0) Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("cannot_change"));
					for (int32 Uid : Targets)
					{
						if (Mode.Contains(TEXT("end")) || Mode.Contains(TEXT("battle")))
						{
							EndBattleDefenseUids.Add(Uid);
						}
						else
						{
							ContinuousCannotChangePositionUids.Add(Uid);
						}
					}
				}
				else if (Op == TEXT("spirit_return"))
				{
					TArray<int32> Targets;
					if (Operation->HasField(TEXT("target")))
					{
						ResolveOperationTargets(Operation, Context, Card, Event, Targets);
					}
					if (Targets.Num() == 0) Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					for (int32 Uid : Targets)
					{
						ContinuousSpiritReturnUids.Add(Uid);
					}
				}
				else if (Op == TEXT("summon_lock"))
				{
					const FString Player = ReadString(Operation, TEXT("player"), TEXT("both"));
					const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("both"));
					const bool bSpecialOnly = Mode.Contains(TEXT("special_only"));
					const bool bNormalOnly = Mode.Contains(TEXT("normal_only"));
					const bool bLockSpecial = !bNormalOnly && (bSpecialOnly || Mode.Contains(TEXT("special")) || Mode == TEXT("both"));
					const bool bLockNormal = !bSpecialOnly && (bNormalOnly || Mode.Contains(TEXT("normal")) || Mode == TEXT("both"));
					auto Lock = [this, bLockSpecial, bLockNormal](EDuelOwner LockSide)
					{
						if (bLockNormal) ContinuousNormalSummonLockSides.Add(static_cast<uint8>(LockSide));
						if (bLockSpecial) ContinuousSpecialSummonLockSides.Add(static_cast<uint8>(LockSide));
					};
					if (Player == TEXT("both")) { Lock(EDuelOwner::Player); Lock(EDuelOwner::Opponent); }
					else if (Player == TEXT("opponent")) Lock(Other(Side));
					else Lock(Side);
				}
				else if (Op == TEXT("battle_damage_modifier"))
				{
					TArray<int32> Targets;
					if (Operation->HasField(TEXT("target")))
					{
						ResolveOperationTargets(Operation, Context, Card, Event, Targets);
					}
					if (Targets.Num() == 0) Targets.Add(EquippedTarget ? EquippedTarget->Uid : Card.Uid);
					const FString Mode = ReadString(Operation, TEXT("mode"), TEXT("zero"));
					const float Value = Mode == TEXT("half") ? 0.5f : (Mode == TEXT("double") ? 2.f : 0.f);
					for (int32 Uid : Targets)
					{
						ContinuousBattleDamageMultipliers.Add(Uid, Value);
					}
				}
			}
		}
	};

	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		const FDuelSide& State = Engine->GetSide(Side);
		for (const FDuelCard& Card : State.Monsters) ProcessCard(Card, Side);
		for (const FDuelCard& Card : State.Spells) ProcessCard(Card, Side);
		ProcessCard(State.Field, Side);
	}
	bRecomputing = false;
}

int32 FDAEffectRuntime::GetAtkModifier(int32 Uid) const
{
	int32 Value = 0;
	if (const int32* Found = ContinuousAtkModifiers.Find(Uid))
	{
		Value += *Found;
	}
	for (const FDEffectModifier& Modifier : LingeringModifiers)
	{
		if (Modifier.Uid == Uid
			&& (Modifier.ExpiryTurn < 0 || !Engine || Engine->TurnNumber <= Modifier.ExpiryTurn))
		{
			Value += Modifier.Atk;
		}
	}
	return Value;
}

int32 FDAEffectRuntime::GetDefModifier(int32 Uid) const
{
	int32 Value = 0;
	if (const int32* Found = ContinuousDefModifiers.Find(Uid))
	{
		Value += *Found;
	}
	for (const FDEffectModifier& Modifier : LingeringModifiers)
	{
		if (Modifier.Uid == Uid
			&& (Modifier.ExpiryTurn < 0 || !Engine || Engine->TurnNumber <= Modifier.ExpiryTurn))
		{
			Value += Modifier.Def;
		}
	}
	return Value;
}

int32 FDAEffectRuntime::GetSpellSpeedOverride(int32 CardId) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(CardId);
	if (!Scripts)
	{
		return 0;
	}
	int32 Speed = 0;
	for (const FDEffectScript& Script : *Scripts)
	{
		Speed = FMath::Max(Speed, Script.SpellSpeed);
	}
	return Speed > 1 ? Speed : 0;
}

bool FDAEffectRuntime::IsCardActivationLocked(const FDuelCard& Card) const
{
	if (Card.IsTrap() && (bTrapActivationLocked || bTrapEffectNegated))
	{
		return true;
	}
	if (Card.IsSpell() && bSpellActivationLocked)
	{
		return true;
	}
	return false;
}

bool FDAEffectRuntime::CanCardAttack(const FDuelCard& Attacker) const
{
	if (!Attacker.IsValid())
	{
		return false;
	}
	if (CannotAttackUids.Contains(Attacker.Uid) || ContinuousCannotAttackUids.Contains(Attacker.Uid))
	{
		return false;
	}
	if (CannotAttackSidesThisTurn.Contains(static_cast<uint8>(Attacker.Controller)))
	{
		return false;
	}
	const int32 MaxAttackers = GetMaxAttackers(Attacker.Controller);
	if (MaxAttackers > 0)
	{
		int32 Used = 0;
		for (const FDuelCard& Monster : Engine->GetSide(Attacker.Controller).Monsters)
		{
			if (Monster.IsValid() && (Monster.bHasAttacked || Monster.Uid == Attacker.Uid && Monster.AttacksUsed > 0))
			{
				++Used;
			}
		}
		if (Used >= MaxAttackers && Attacker.AttacksUsed == 0)
		{
			return false;
		}
	}
	return true;
}

bool FDAEffectRuntime::CanDeclareAttack(const FDuelCard& Attacker, bool bDirect) const
{
	if (!CanCardAttack(Attacker))
	{
		return false;
	}
	if (bDirect)
	{
		if (CannotAttackDirectlySidesThisTurn.Contains(static_cast<uint8>(Attacker.Controller))
			|| DirectAttackForbiddenUids.Contains(Attacker.Uid)
			|| ContinuousDirectAttackForbiddenUids.Contains(Attacker.Uid))
		{
			return false;
		}
	}
	return true;
}

bool FDAEffectRuntime::CanAttackDirectly(const FDuelCard& Attacker) const
{
	return DirectAttackAllowedUids.Contains(Attacker.Uid)
		|| ContinuousDirectAttackAllowedUids.Contains(Attacker.Uid);
}

bool FDAEffectRuntime::MustAttack(const FDuelCard& Attacker) const
{
	return MustAttackUids.Contains(Attacker.Uid) || ContinuousMustAttackUids.Contains(Attacker.Uid);
}

bool FDAEffectRuntime::IsPositionChangeLocked(const FDuelCard& Card) const
{
	return CannotChangePositionUids.Contains(Card.Uid) || ContinuousCannotChangePositionUids.Contains(Card.Uid);
}

int32 FDAEffectRuntime::GetMaxAttackers(EDuelOwner Side) const
{
	int32 Max = 0;
	if (const int32* Found = MaxAttackersPerSide.Find(static_cast<uint8>(Side)))
	{
		Max = FMath::Max(Max, *Found);
	}
	if (const int32* Found = MaxAttackersThisTurn.Find(static_cast<uint8>(Side)))
	{
		Max = Max > 0 ? FMath::Min(Max, *Found) : *Found;
	}
	return Max;
}

bool FDAEffectRuntime::ConsumeAttackNegated()
{
	const bool bWasNegated = bAttackNegated;
	bAttackNegated = false;
	return bWasNegated;
}

bool FDAEffectRuntime::ShouldPreventDestruction(const FDuelCard& Card, bool bByBattle, const FString& Reason) const
{
	(void)Reason;
	if (PreventDestructionUids.Contains(Card.Uid) || ContinuousPreventDestructionUids.Contains(Card.Uid))
	{
		return true;
	}
	if (bByBattle && (PreventBattleDestructionUids.Contains(Card.Uid)
		|| ContinuousPreventBattleDestructionUids.Contains(Card.Uid)))
	{
		return true;
	}
	return false;
}

bool FDAEffectRuntime::ShouldBanishInsteadOfGrave(const FDuelCard& Card) const
{
	return BanishInsteadOfGraveUids.Contains(Card.Uid)
		|| ContinuousBanishInsteadOfGraveUids.Contains(Card.Uid);
}

bool FDAEffectRuntime::IsSummonLocked(EDuelOwner Side, bool bSpecial) const
{
	const uint8 Key = static_cast<uint8>(Side);
	return bSpecial
		? (SpecialSummonLockSides.Contains(Key) || ContinuousSpecialSummonLockSides.Contains(Key))
		: (NormalSummonLockSides.Contains(Key) || ContinuousNormalSummonLockSides.Contains(Key));
}

bool FDAEffectRuntime::ShouldStayOnFieldAfterActivation(const FDuelCard& Card) const
{
	if (!Card.IsSpell() && !Card.IsTrap())
	{
		return false;
	}
	// Printed card category is the primary rule.  A05's data scripts then
	// refine it for cards whose subtype metadata is generic.
	const FString& Subtype = Card.Data.Subtype;
	if (Subtype == TEXT("Equip") || Subtype == TEXT("Field") || Subtype == TEXT("Continuous"))
	{
		return true;
	}

	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card.Data.Id);
	if (!Scripts)
	{
		return false;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger == EDEffectTrigger::EquipContinuous
			|| Script.Trigger == EDEffectTrigger::FieldContinuous)
		{
			return true;
		}
		if (Script.Trigger == EDEffectTrigger::Continuous
			&& (Script.Duration == TEXT("while_face_up") || Script.Duration == TEXT("permanent")))
		{
			return true;
		}
		if (Script.Trigger == EDEffectTrigger::OnActivate
			&& (Script.Duration == TEXT("while_face_up") || Script.Duration == TEXT("permanent")))
		{
			return true;
		}
	}
	return false;
}

bool FDAEffectRuntime::HasEquipStatScript(int32 CardId) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(CardId);
	if (!Scripts)
	{
		return false;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger != EDEffectTrigger::EquipContinuous)
		{
			continue;
		}
		for (const TSharedPtr<FJsonObject>& Operation : Script.Operations)
		{
			const FString Op = ReadString(Operation, TEXT("op"));
			if (Op == TEXT("modify_atk") || Op == TEXT("modify_def"))
			{
				return true;
			}
		}
	}
	return false;
}

bool FDAEffectRuntime::HasFieldStatScript(int32 CardId) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(CardId);
	if (!Scripts)
	{
		return false;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger != EDEffectTrigger::FieldContinuous)
		{
			continue;
		}
		for (const TSharedPtr<FJsonObject>& Operation : Script.Operations)
		{
			const FString Op = ReadString(Operation, TEXT("op"));
			if (Op == TEXT("modify_atk") || Op == TEXT("modify_def"))
			{
				return true;
			}
		}
	}
	return false;
}

bool FDAEffectRuntime::HasLegalEquipTarget(const FDuelCard& Card) const
{
	if (!Engine)
	{
		return false;
	}
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card.Data.Id);
	if (!Scripts)
	{
		return false;
	}

	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::OnActivate;
	Event.SourceCard = Card;
	Event.EventCard = Card;
	Event.SourceController = Card.Controller;
	Event.EventController = Card.Controller;

	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger != EDEffectTrigger::OnActivate || !ScriptHasOperation(Script, TEXT("equip")))
		{
			continue;
		}
		TArray<int32> Resolved;
		TArray<int32> Candidates;
		bool bNeedsPrompt = false;
		EDuelOwner Chooser = Card.Controller;
		int32 Min = 0;
		int32 Max = 0;
		FString Prompt;
		if (ResolveScriptTarget(Script, Card, Event, Resolved, Candidates, bNeedsPrompt, Chooser, Min, Max, Prompt)
			&& (Resolved.Num() > 0 || Candidates.Num() > 0))
		{
			return true;
		}
	}
	return false;
}

bool FDAEffectRuntime::HasScriptTrigger(int32 CardId, EDEffectTrigger Trigger) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(CardId);
	if (!Scripts)
	{
		return false;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger == Trigger)
		{
			return true;
		}
	}
	return false;
}

float FDAEffectRuntime::GetBattleDamageMultiplier(int32 CardUid) const
{
	if (const float* Found = BattleDamageMultipliers.Find(CardUid))
	{
		return *Found;
	}
	if (const float* Found = ContinuousBattleDamageMultipliers.Find(CardUid))
	{
		return *Found;
	}
	return 1.f;
}

bool FDAEffectRuntime::ShouldRedirectBattleDamage(int32 CardUid, EDuelOwner DamageReceiver, EDuelOwner& OutReceiver) const
{
	if (!Engine || !RedirectBattleDamageUids.Contains(CardUid))
	{
		return false;
	}
	const FDuelCard* Card = Engine->FindCard(CardUid);
	if (!Card || Card->Controller != DamageReceiver)
	{
		return false;
	}
	OutReceiver = Other(DamageReceiver);
	return true;
}

int32 FDAEffectRuntime::GetCounterCount(int32 Uid, const FString& Counter) const
{
	const TMap<FString, int32>* Map = Counters.Find(Uid);
	if (!Map)
	{
		return 0;
	}
	const int32* Found = Map->Find(Counter);
	return Found ? *Found : 0;
}

bool FDAEffectRuntime::AddCounter(int32 Uid, const FString& Counter, int32 Amount, int32 Max)
{
	if (Uid <= 0 || Amount <= 0)
	{
		return false;
	}
	TMap<FString, int32>& Map = Counters.FindOrAdd(Uid);
	int32& Value = Map.FindOrAdd(Counter);
	if (Value >= Max)
	{
		return false;
	}
	Value = FMath::Min(Value + Amount, Max);
	if (FDuelCard* Card = Engine ? Engine->FindCard(Uid) : nullptr)
	{
		int32 Total = 0;
		for (const TPair<FString, int32>& Pair : Map)
		{
			Total += Pair.Value;
		}
		Card->Counters = Total;
	}
	return true;
}

bool FDAEffectRuntime::RemoveCounter(int32 Uid, const FString& Counter, int32 Amount)
{
	if (Uid <= 0 || Amount <= 0)
	{
		return false;
	}
	TMap<FString, int32>* Map = Counters.Find(Uid);
	if (!Map)
	{
		return false;
	}
	int32* Value = Map->Find(Counter);
	if (!Value || *Value < Amount)
	{
		return false;
	}
	*Value -= Amount;
	if (*Value <= 0)
	{
		Map->Remove(Counter);
	}
	if (FDuelCard* Card = Engine ? Engine->FindCard(Uid) : nullptr)
	{
		int32 Total = 0;
		for (const TPair<FString, int32>& Pair : *Map)
		{
			Total += Pair.Value;
		}
		Card->Counters = Total;
	}
	return true;
}

void FDAEffectRuntime::ClearCardState(int32 Uid)
{
	Counters.Remove(Uid);
	ContinuousAtkModifiers.Remove(Uid);
	ContinuousDefModifiers.Remove(Uid);
	RedirectBattleDamageUids.Remove(Uid);
	BattleDamageZeroUids.Remove(Uid);
	CannotAttackUids.Remove(Uid);
	MustAttackUids.Remove(Uid);
	DirectAttackAllowedUids.Remove(Uid);
	DirectAttackForbiddenUids.Remove(Uid);
	PiercingUids.Remove(Uid);
	ExtraAttackUids.Remove(Uid);
	CannotChangePositionUids.Remove(Uid);
	EndBattleDefenseUids.Remove(Uid);
	PreventDestructionUids.Remove(Uid);
	PreventBattleDestructionUids.Remove(Uid);
	BanishInsteadOfGraveUids.Remove(Uid);
	SpiritReturnUids.Remove(Uid);
	ContinuousCannotAttackUids.Remove(Uid);
	ContinuousMustAttackUids.Remove(Uid);
	ContinuousDirectAttackAllowedUids.Remove(Uid);
	ContinuousDirectAttackForbiddenUids.Remove(Uid);
	ContinuousPiercingUids.Remove(Uid);
	ContinuousExtraAttackUids.Remove(Uid);
	ContinuousCannotChangePositionUids.Remove(Uid);
	ContinuousPreventDestructionUids.Remove(Uid);
	ContinuousPreventBattleDestructionUids.Remove(Uid);
	ContinuousBanishInsteadOfGraveUids.Remove(Uid);
	ContinuousSpiritReturnUids.Remove(Uid);
	BattleDamageMultipliers.Remove(Uid);
	ContinuousBattleDamageMultipliers.Remove(Uid);
	for (int32 I = LingeringModifiers.Num() - 1; I >= 0; --I)
	{
		if (LingeringModifiers[I].Uid == Uid)
		{
			LingeringModifiers.RemoveAt(I);
		}
	}
}

void FDAEffectRuntime::ResetTurnRestrictions()
{
	CannotAttackSidesThisTurn.Reset();
	CannotAttackDirectlySidesThisTurn.Reset();
	MaxAttackersThisTurn.Reset();
	NormalSummonLockSides.Reset();
	SpecialSummonLockSides.Reset();
	AttackRestrictionExpiryTurn = -1;
}

void FDAEffectRuntime::ExpireLingering(EDuelOwner EndingSide, bool bBattlePhaseOnly)
{
	for (int32 I = LingeringModifiers.Num() - 1; I >= 0; --I)
	{
		const FDEffectModifier& Modifier = LingeringModifiers[I];
		if (bBattlePhaseOnly)
		{
			if (Modifier.Duration == TEXT("until_end_of_battle_phase"))
			{
				LingeringModifiers.RemoveAt(I);
			}
			continue;
		}
		if (Modifier.Duration == TEXT("until_end_of_battle_phase"))
		{
			continue;
		}
		if (Modifier.ExpiryTurn >= 0 && Engine && Engine->TurnNumber > Modifier.ExpiryTurn)
		{
			LingeringModifiers.RemoveAt(I);
		}
	}
	(void)EndingSide;
}

bool FDAEffectRuntime::HasInherentSummon(const FDuelCard& Card) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card.Data.Id);
	if (!Scripts)
	{
		return false;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger == EDEffectTrigger::InherentSummon)
		{
			return true;
		}
	}
	return false;
}

bool FDAEffectRuntime::ActivateInherentSummon(int32 CardUid, FString& OutError)
{
	if (!Engine)
	{
		OutError = TEXT("effect runtime has no engine");
		return false;
	}
	FDuelCard* Card = Engine->FindCard(CardUid);
	if (!Card || !Card->IsMonster())
	{
		OutError = TEXT("inherent summon source is not a monster");
		return false;
	}
	if (Engine->EmptyMonsterZone(Card->Controller) == INDEX_NONE)
	{
		OutError = TEXT("there is no empty Monster Zone for the inherent summon");
		return false;
	}
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card->Data.Id);
	if (!Scripts)
	{
		OutError = TEXT("inherent summon source has no script");
		return false;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger != EDEffectTrigger::InherentSummon)
		{
			continue;
		}
		FDEffectEvent Event;
		Event.Trigger = EDEffectTrigger::InherentSummon;
		Event.SourceCard = *Card;
		Event.EventCard = *Card;
		Event.SourceController = Card->Controller;
		Event.EventController = Card->Controller;
		if (TryStartScript(Script, *Card, Event))
		{
			if (FDuelCard* Placed = Engine->FindMonster(CardUid))
			{
				Engine->TriggerSummonTraps(*Placed, false);
			}
			Engine->CheckWinner();
			return true;
		}
	}
	OutError = FString::Printf(TEXT("%s cannot be inherently Special Summoned right now."), *CardName(*Card));
	return false;
}

bool FDAEffectRuntime::HasManualEffect(const FDuelCard& Card) const
{
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card.Data.Id);
	if (!Scripts)
	{
		return false;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger == EDEffectTrigger::Manual)
		{
			return true;
		}
	}
	return false;
}

TArray<FDuelActionInfo> FDAEffectRuntime::GetManualActions(const FDuelCard& Card) const
{
	TArray<FDuelActionInfo> Actions;
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card.Data.Id);
	if (!Scripts)
	{
		return Actions;
	}
	for (const FDEffectScript& Script : *Scripts)
	{
		if (Script.Trigger != EDEffectTrigger::Manual)
		{
			continue;
		}
		FDEffectEvent Event;
		Event.Trigger = EDEffectTrigger::Manual;
		Event.SourceCard = Card;
		Event.EventCard = Card;
		Event.SourceController = Card.Controller;
		Event.EventController = Card.Controller;
		if (IsSourceAvailable(Script, Card, Event)
			&& EvaluateCondition(Script.Condition, Card, Card, Event))
		{
			FDuelActionInfo Action;
			Action.Action = EDuelAction::ActivateEffect;
			Action.Label = Script.SourceText.IsEmpty() ? FString::Printf(TEXT("Activate %s"), *Script.Id) : Script.SourceText;
			Actions.Add(Action);
		}
	}
	return Actions;
}

bool FDAEffectRuntime::ActivateManualScript(int32 CardUid, int32 ScriptIndex, FString& OutError)
{
	if (!Engine)
	{
		OutError = TEXT("effect runtime has no engine");
		return false;
	}
	FDuelCard* Card = Engine->FindMonster(CardUid);
	if (!Card)
	{
		OutError = TEXT("manual effect source is not a monster");
		return false;
	}
	const TArray<FDEffectScript>* Scripts = ScriptsByCard.Find(Card->Data.Id);
	if (!Scripts || !Scripts->IsValidIndex(ScriptIndex))
	{
		OutError = TEXT("manual effect script index is invalid");
		return false;
	}
	const FDEffectScript& Script = (*Scripts)[ScriptIndex];
	if (Script.Trigger != EDEffectTrigger::Manual)
	{
		OutError = TEXT("script is not a manual effect");
		return false;
	}
	FDEffectEvent Event;
	Event.Trigger = EDEffectTrigger::Manual;
	Event.SourceCard = *Card;
	Event.EventCard = *Card;
	Event.SourceController = Card->Controller;
	Event.EventController = Card->Controller;
	if (!Engine->IsActivationLegal(*Card, Engine->GetCurrentTimingWindow()))
	{
		OutError = TEXT("manual effect is outside its activation window");
		return false;
	}
	if (TryStartScript(Script, *Card, Event))
	{
		return true;
	}
	OutError = FString::Printf(TEXT("%s cannot be activated right now."), *CardName(*Card));
	return false;
}
