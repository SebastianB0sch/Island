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

	bool IsKnownOp(const FString& Op)
	{
		static const TSet<FString> Known = {
			TEXT("add_counter"), TEXT("allow_fusion"), TEXT("attack_directly"), TEXT("banish"),
			TEXT("battle_damage_zero"), TEXT("change_position"), TEXT("copy"), TEXT("declare_name"),
			TEXT("destroy"), TEXT("discard"), TEXT("draw"), TEXT("equip"), TEXT("excavate"),
			TEXT("extra_attack"), TEXT("fusion"), TEXT("gain_lp"), TEXT("heal"), TEXT("inflict_damage"),
			TEXT("lock_activation"), TEXT("look_at_deck"), TEXT("mill"), TEXT("modify_atk"),
			TEXT("modify_def"), TEXT("negate"), TEXT("place_counter"), TEXT("prevent_battle_damage"),
			TEXT("redirect_attack"), TEXT("redirect_battle_damage"), TEXT("remove_counter"),
			TEXT("return_to_extra"), TEXT("return_to_hand"), TEXT("return_to_deck"), TEXT("reveal"),
			TEXT("ritual"), TEXT("roll_die"), TEXT("search"), TEXT("send_to_grave"), TEXT("set"),
			TEXT("shuffle"), TEXT("skip_phase"), TEXT("special_summon"), TEXT("summon"),
			TEXT("take_control"), TEXT("control"), TEXT("toss_coin"), TEXT("damage")
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
			TEXT("banished"), TEXT("graveyard"), TEXT("deck"), TEXT("hand"), TEXT("extra")
		};
		return Known.Contains(Zone);
	}

	bool IsKnownConditionKey(const FString& Key)
	{
		static const TSet<FString> Known = {
			TEXT("all"), TEXT("any"), TEXT("not"), TEXT("controller"), TEXT("face_up"),
			TEXT("position"), TEXT("zone"), TEXT("card_type"), TEXT("subtype"), TEXT("attribute"),
			TEXT("monster_type"), TEXT("level_min"), TEXT("level_max"), TEXT("atk_min"), TEXT("atk_max"),
			TEXT("def_min"), TEXT("def_max"), TEXT("name"), TEXT("has_counter"), TEXT("lp_min"),
			TEXT("lp_max"), TEXT("hand_min"), TEXT("hand_max"), TEXT("field_spell"), TEXT("summon_type"),
			TEXT("reason"), TEXT("custom")
		};
		return Known.Contains(Key);
	}

	bool IsKnownCustom(const FString& Custom)
	{
		return Custom == TEXT("sent_from_field_to_graveyard")
			|| Custom == TEXT("ignition_main_phase")
			|| Custom == TEXT("battle_involving_self")
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
			const FString OpName = ReadString(Op, TEXT("op"));
			if (!IsKnownOp(OpName))
			{
				OutError = FString::Printf(TEXT("Card %d script '%s' uses unknown operation '%s'."), CardId, *Script.Id, *OpName);
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
				OutError = FString::Printf(TEXT("Card %d script '%s' uses unknown destination '%s'."), CardId, *Script.Id, *Destination);
				return false;
			}
			Script.Operations.Add(Op);
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
	bTrapActivationLocked = false;
	bTrapEffectNegated = false;
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
	case EDEffectTrigger::OnDamageCalculated: return TEXT("on_damage_calculated");
	case EDEffectTrigger::OnBattleDestroy: return TEXT("on_battle_destroy");
	case EDEffectTrigger::OnDestroy: return TEXT("on_destroy");
	case EDEffectTrigger::OnSentToGraveyard: return TEXT("on_sent_to_graveyard");
	case EDEffectTrigger::OnRemovedFromField: return TEXT("on_removed_from_field");
	case EDEffectTrigger::OnDraw: return TEXT("on_draw");
	case EDEffectTrigger::OnStandby: return TEXT("on_standby");
	case EDEffectTrigger::OnMain: return TEXT("on_main");
	case EDEffectTrigger::OnEnd: return TEXT("on_end");
	case EDEffectTrigger::OnChain: return TEXT("on_chain");
	case EDEffectTrigger::OnRitualSummon: return TEXT("on_ritual_summon");
	case EDEffectTrigger::OnFusionSummon: return TEXT("on_fusion_summon");
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
		{ TEXT("on_damage_calculated"), EDEffectTrigger::OnDamageCalculated },
		{ TEXT("on_battle_destroy"), EDEffectTrigger::OnBattleDestroy },
		{ TEXT("on_destroy"), EDEffectTrigger::OnDestroy },
		{ TEXT("on_sent_to_graveyard"), EDEffectTrigger::OnSentToGraveyard },
		{ TEXT("on_removed_from_field"), EDEffectTrigger::OnRemovedFromField },
		{ TEXT("on_draw"), EDEffectTrigger::OnDraw },
		{ TEXT("on_standby"), EDEffectTrigger::OnStandby },
		{ TEXT("on_main"), EDEffectTrigger::OnMain },
		{ TEXT("on_end"), EDEffectTrigger::OnEnd },
		{ TEXT("on_chain"), EDEffectTrigger::OnChain },
		{ TEXT("on_ritual_summon"), EDEffectTrigger::OnRitualSummon },
		{ TEXT("on_fusion_summon"), EDEffectTrigger::OnFusionSummon },
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
	ExpireLingering(EDuelOwner::Player, true);
	RecomputeContinuous();
}

void FDAEffectRuntime::OnEnd(EDuelOwner Side)
{
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

	int32 Started = 0;
	TSet<FString> Seen;
	auto ConsiderCard = [&](const FDuelCard& Source)
	{
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
		|| Event.Trigger == EDEffectTrigger::OnBattleStart
		|| Event.Trigger == EDEffectTrigger::OnDamageCalculated
		|| Event.Trigger == EDEffectTrigger::OnDestroy
		|| Event.Trigger == EDEffectTrigger::OnBattleDestroy
		|| Event.Trigger == EDEffectTrigger::OnSentToGraveyard
		|| Event.Trigger == EDEffectTrigger::OnRemovedFromField
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
		return Event.AttackerUid == Subject.Uid || Event.AttackTargetUid == Subject.Uid;
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
		const FString Actual = ZoneStringOf(Subject);
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

	int32 Number = 0;
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
		if (Zone == P + TEXT("_deck") || Zone == TEXT("deck"))
		{
			AddArray(State.Deck);
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
		if (Zone == TEXT("all_cards") || Zone == P)
		{
			AddArray(State.Monsters);
			AddArray(State.Spells);
			if (State.Field.IsValid()) Result.Add(State.Field);
		}
	};

	const EDuelOwner OtherSide = Other(Side);
	const bool bBoth = Zone == TEXT("any_monster") || Zone == TEXT("all_monsters")
		|| Zone == TEXT("any_spell_trap") || Zone == TEXT("all_spell_traps")
		|| Zone == TEXT("all_hands") || Zone == TEXT("all_cards")
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
		if (Links.Num() > 0)
		{
			if (const FDuelCard* Card = Engine->FindCard(Links.Last().CardUid))
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
		return false;
	}
	if (Live->IsTrap() && bTrapActivationLocked)
	{
		return false;
	}
	const FString Zone = ZoneStringOf(*Live);

	if (Script.Trigger == EDEffectTrigger::Manual)
	{
		return Live->IsMonster() && Live->bFaceUp && Zone.Contains(TEXT("monster"))
			&& Engine->IsMainPhase() && !Engine->bWinnerSet;
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

	for (int32 Uid : CandidateUids)
	{
		const FDuelCard* Card = Engine->FindCard(Uid);
		if (!Card)
		{
			continue;
		}
		FDuelChoiceOption Option;
		Option.Id = Uid;
		Option.Label = CardName(*Card);
		Option.CardUid = Uid;
		Option.CardId = Card->Data.Id;
		Option.Zone = EDuelZone::None;
		Request.Options.Add(Option);
	}
	TSet<int32> Added;
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
	for (const FDuelCard& Candidate : CollectCandidates(Zone, SourceCard, Event))
	{
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
	OutPrompt = FString::Printf(TEXT("Select %d-%d card(s) for %s"),
		Min, Max, Script.SourceText.IsEmpty() ? *Script.Id : *Script.SourceText);
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
		if (!Engine->PlaceMonster(Copy.Owner, Copy, true, EDuelPosition::Attack))
		{
			Engine->MoveToGrave(Copy);
			continue;
		}
		if (FDuelCard* Placed = Engine->FindMonster(Uid))
		{
			Placed->bSpecialSummoned = bSpecial;
			Engine->Log(FString::Printf(TEXT("%s %s %s."), *Engine->GetSide(Copy.Owner).Name,
				bSpecial ? TEXT("Special Summons") : TEXT("Summons"), *CardName(*Placed)), TEXT("summon"));
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
			Card->bFaceUp = Position != TEXT("face_down");
			Card->Position = Position == TEXT("defense") || Position == TEXT("face_down")
				? EDuelPosition::Defense : EDuelPosition::Attack;
			Card->PositionChangedTurn = Engine->TurnNumber;
			Engine->EmitVisual(EDuelVisualEventType::Position, Card->Controller, Card, 0,
				Card->Position == EDuelPosition::Attack ? TEXT("ATTACK") : TEXT("DEFENSE"));
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
	const int32 Amount = ReadInt(Operation, TEXT("amount"), 0);
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
			Engine->MoveToDeckBottom(Copy);
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
		}
	}
	if (Engine->ChainLinks.Num() > 0)
	{
		Engine->ChainLinks.Last().bNegated = true;
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
	if (Op == TEXT("lock_activation")) { bTrapActivationLocked = true; bTrapEffectNegated = true; return true; }
	if (Op == TEXT("allow_fusion"))
	{
		AllowedFusionTypes.Add(ReadString(Operation, TEXT("fusion_type"), TEXT("Fusion Gate")));
		return true;
	}
	if (Op == TEXT("redirect_battle_damage")) { RedirectBattleDamageUids.Add(Context.SourceCard.Uid); return true; }
	if (Op == TEXT("prevent_battle_damage")) { PreventBattleDamageSides.Add(static_cast<uint8>(Context.SourceCard.Controller)); return true; }
	if (Op == TEXT("battle_damage_zero")) { BattleDamageZeroUids.Add(Context.SourceCard.Uid); return true; }
	if (Op == TEXT("skip_phase") || Op == TEXT("skip_draw")) { Engine->SideRef(Context.SourceCard.Controller).bSkipDraw = true; return true; }
	if (Op == TEXT("extra_attack"))
	{
		for (int32 Uid : Context.TargetUids)
		{
			if (FDuelCard* Card = Engine->FindMonster(Uid))
			{
				Card->ExtraAttacks += FMath::Max(1, ReadInt(Operation, TEXT("count"), 1));
			}
		}
		return true;
	}
	if (Op == TEXT("attack_directly") || Op == TEXT("redirect_attack") || Op == TEXT("declare_name") || Op == TEXT("look_at_deck"))
	{
		Engine->Log(FString::Printf(TEXT("Effect operation '%s' is recorded but not yet visualised."), *Op), TEXT("effect"));
		return true;
	}
	if (Op == TEXT("roll_die") || Op == TEXT("toss_coin"))
	{
		const int32 Result = Engine->Random.RandRange(1, Op == TEXT("roll_die") ? 6 : 2);
		Engine->EmitVisual(EDuelVisualEventType::Effect, Context.SourceCard.Controller, &Context.SourceCard, Result,
			Op == TEXT("roll_die") ? TEXT("DIE") : TEXT("COIN"));
		return true;
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
	bTrapActivationLocked = false;
	bTrapEffectNegated = false;

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
			FDEffectEvent Event;
			Event.Trigger = Script.Trigger;
			Event.SourceCard = Card;
			Event.EventCard = Card;
			Event.SourceController = Side;
			Event.EventController = Side;
			if (!EvaluateCondition(Script.Condition, Card, Card, Event, true))
			{
				continue;
			}
			for (const TSharedPtr<FJsonObject>& Operation : Script.Operations)
			{
				const FString Op = ReadString(Operation, TEXT("op"));
				if (Op == TEXT("modify_atk") || Op == TEXT("modify_def"))
				{
					int32 Amount = ReadInt(Operation, TEXT("amount"), 0);
					const FString Mode = ReadString(Operation, TEXT("mode"));
					const FString Counter = ReadString(Operation, TEXT("counter"));
					if (Mode == TEXT("per_counter") && !Counter.IsEmpty())
					{
						Amount *= GetCounterCount(Card.Uid, Counter);
					}
					if (Op == TEXT("modify_atk"))
					{
						ContinuousAtkModifiers.FindOrAdd(Card.Uid) += Amount;
					}
					else
					{
						ContinuousDefModifiers.FindOrAdd(Card.Uid) += Amount;
					}
				}
				else if (Op == TEXT("lock_activation"))
				{
					bTrapActivationLocked = true;
					if (ReadString(Operation, TEXT("mode")).Contains(TEXT("effect")))
					{
						bTrapEffectNegated = true;
					}
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
	return Card.IsTrap() && (bTrapActivationLocked || bTrapEffectNegated);
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
	for (int32 I = LingeringModifiers.Num() - 1; I >= 0; --I)
	{
		if (LingeringModifiers[I].Uid == Uid)
		{
			LingeringModifiers.RemoveAt(I);
		}
	}
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
