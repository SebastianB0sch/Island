// Duel Academy Island - puzzle JSON loader and authored-line replay.

#include "DAPuzzleRuntime.h"

#include "DACardRecords.h"
#include "DADuelEngine.h"

#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	bool PuzzleReadJsonFile(const FString& Path, TSharedPtr<FJsonObject>& OutObject, FString& OutError)
	{
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			OutError = FString::Printf(TEXT("Could not read puzzle file '%s'."), *Path);
			return false;
		}
		TSharedPtr<FJsonValue> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			OutError = FString::Printf(TEXT("Puzzle JSON parse failed: '%s'."), *Path);
			return false;
		}
		OutObject = Root->AsObject();
		if (!OutObject.IsValid())
		{
			OutError = FString::Printf(TEXT("Puzzle JSON root is not an object: '%s'."), *Path);
			return false;
		}
		return true;
	}

	FString PuzzleReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		FString Value;
		if (Object.IsValid())
		{
			Object->TryGetStringField(Field, Value);
		}
		return Value;
	}

	int32 PuzzleReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool PuzzleReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bDefault = false)
	{
		bool bValue = bDefault;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	TSharedPtr<FJsonObject> PuzzleReadObject(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		const TSharedPtr<FJsonObject>* Found = nullptr;
		if (Object.IsValid() && Object->TryGetObjectField(Field, Found) && Found && Found->IsValid())
		{
			return *Found;
		}
		return nullptr;
	}

	void PuzzleReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<int32>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!Object.IsValid() || !Object->TryGetArrayField(Field, Values))
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			if (Value.IsValid())
			{
				Out.Add(static_cast<int32>(Value->AsNumber()));
			}
		}
	}

	bool PuzzleReadSide(const TSharedPtr<FJsonObject>& Side, const TCHAR* Label,
		int32& OutLp, TArray<int32>& OutHand, TArray<int32>& OutDeck, TArray<int32>& OutGraveyard,
		TArray<int32>& OutExtra, TArray<FDuelScenarioCard>& OutField, FString& OutError)
	{
		if (!Side.IsValid())
		{
			OutError = FString::Printf(TEXT("%s state is missing."), Label);
			return false;
		}
		OutLp = PuzzleReadInt(Side, TEXT("lp"));
		if (OutLp <= 0)
		{
			OutError = FString::Printf(TEXT("%s.lp must be positive."), Label);
			return false;
		}
		PuzzleReadIntArray(Side, TEXT("hand"), OutHand);
		PuzzleReadIntArray(Side, TEXT("deck"), OutDeck);
		PuzzleReadIntArray(Side, TEXT("graveyard"), OutGraveyard);
		PuzzleReadIntArray(Side, TEXT("extra"), OutExtra);

		const TArray<TSharedPtr<FJsonValue>>* FieldValues = nullptr;
		if (Side->TryGetArrayField(TEXT("field"), FieldValues))
		{
			int32 ZoneIndex = 0;
			for (const TSharedPtr<FJsonValue>& Value : *FieldValues)
			{
				const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
				if (!Entry.IsValid())
				{
					OutError = FString::Printf(TEXT("%s.field has a non-object entry."), Label);
					return false;
				}
				FDuelScenarioCard Card;
				Card.CardId = PuzzleReadInt(Entry, TEXT("card_id"));
				Card.Zone = EDuelZone::Monster;
				Card.ZoneIndex = ZoneIndex++;
				const FString Position = PuzzleReadString(Entry, TEXT("position")).ToLower();
				Card.bDefense = Position == TEXT("defense");
				Card.bFaceDown = !PuzzleReadBool(Entry, TEXT("face_up"), true);
				if (Card.CardId <= 0 || Card.ZoneIndex >= 5 || (!Position.IsEmpty() && Position != TEXT("attack") && Position != TEXT("defense")))
				{
					OutError = FString::Printf(TEXT("%s.field entry is invalid (card %d, position '%s')."),
						Label, Card.CardId, *Position);
					return false;
				}
				OutField.Add(Card);
			}
			if (ZoneIndex > 5)
			{
				OutError = FString::Printf(TEXT("%s.field has more than five monsters."), Label);
				return false;
			}
		}

		const TArray<TSharedPtr<FJsonValue>>* SpellValues = nullptr;
		if (Side->TryGetArrayField(TEXT("spell_traps"), SpellValues))
		{
			int32 ZoneIndex = 0;
			for (const TSharedPtr<FJsonValue>& Value : *SpellValues)
			{
				const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
				if (!Entry.IsValid())
				{
					OutError = FString::Printf(TEXT("%s.spell_traps has a non-object entry."), Label);
					return false;
				}
				FDuelScenarioCard Card;
				Card.CardId = PuzzleReadInt(Entry, TEXT("card_id"));
				Card.Zone = EDuelZone::SpellTrap;
				Card.ZoneIndex = ZoneIndex++;
				Card.bFaceDown = !PuzzleReadBool(Entry, TEXT("face_up"), false);
				if (Card.CardId <= 0 || Card.ZoneIndex >= 5)
				{
					OutError = FString::Printf(TEXT("%s.spell_traps entry is invalid (card %d)."), Label, Card.CardId);
					return false;
				}
				OutField.Add(Card);
			}
			if (ZoneIndex > 5)
			{
				OutError = FString::Printf(TEXT("%s.spell_traps has more than five cards."), Label);
				return false;
			}
		}
		return true;
	}

	bool PuzzleReadSolution(const TArray<TSharedPtr<FJsonValue>>* Values,
		TArray<FDAPuzzleSolutionStep>& OutSolution, FString& OutError)
	{
		if (!Values || Values->Num() == 0)
		{
			OutError = TEXT("solution must be a non-empty array.");
			return false;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			const TSharedPtr<FJsonObject> StepObject = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!StepObject.IsValid())
			{
				OutError = TEXT("solution contains a non-object step.");
				return false;
			}
			FDAPuzzleSolutionStep Step;
			Step.Action = PuzzleReadString(StepObject, TEXT("action"));
			Step.CardId = PuzzleReadInt(StepObject, TEXT("card_id"));
			Step.AttackerCardId = PuzzleReadInt(StepObject, TEXT("attacker_card_id"));
			Step.Position = PuzzleReadString(StepObject, TEXT("position")).ToLower();
			PuzzleReadIntArray(StepObject, TEXT("tribute_card_ids"), Step.TributeCardIds);
			if (Step.Action.IsEmpty())
			{
				OutError = TEXT("solution step has no action.");
				return false;
			}
			FString TargetText;
			if (StepObject->TryGetStringField(TEXT("target"), TargetText))
			{
				Step.bTargetDirect = TargetText.Equals(TEXT("direct"), ESearchCase::IgnoreCase);
				if (!Step.bTargetDirect)
				{
					// UE's JSON reader may coerce a numeric target into a string;
					// accept both "363" and 363 as a card id.
					const int32 ParsedTarget = FCString::Atoi(*TargetText);
					if (ParsedTarget > 0)
					{
						Step.TargetCardId = ParsedTarget;
					}
					else
					{
						OutError = FString::Printf(TEXT("solution step target '%s' is not supported."), *TargetText);
						return false;
					}
				}
			}
			else
			{
				Step.TargetCardId = PuzzleReadInt(StepObject, TEXT("target"));
			}
			OutSolution.Add(MoveTemp(Step));
		}
		return true;
	}

	int32 PuzzleFindHandUid(const FDuelEngine& Engine, EDuelOwner Side, int32 CardId)
	{
		for (const FDuelCard& Card : Engine.GetSide(Side).Hand)
		{
			if (Card.Data.Id == CardId)
			{
				return Card.Uid;
			}
		}
		return 0;
	}

	int32 PuzzleFindMonsterUid(const FDuelEngine& Engine, EDuelOwner Side, int32 CardId,
		bool bRequireUnattacked = false, bool bRequireFaceUpAttack = false)
	{
		for (const FDuelCard& Card : Engine.GetSide(Side).Monsters)
		{
			if (!Card.IsValid() || Card.Data.Id != CardId)
			{
				continue;
			}
			if (bRequireFaceUpAttack && (!Card.bFaceUp || Card.Position != EDuelPosition::Attack))
			{
				continue;
			}
			if (bRequireUnattacked && Card.bHasAttacked)
			{
				continue;
			}
			return Card.Uid;
		}
		return 0;
	}

	int32 PuzzleFindSpellTrapUid(const FDuelEngine& Engine, EDuelOwner Side, int32 CardId, bool bFaceDown)
	{
		for (const FDuelCard& Card : Engine.GetSide(Side).Spells)
		{
			if (Card.IsValid() && Card.Data.Id == CardId && Card.bFaceUp != bFaceDown)
			{
				return Card.Uid;
			}
		}
		return 0;
	}

	bool PuzzleExecuteStep(FDuelEngine& Duel, const FDAPuzzleSolutionStep& Step,
		int32 StepIndex, FDAPuzzleReplayResult& OutResult, FString& OutError)
	{
		if (Step.Action == TEXT("attack"))
		{
			if (Duel.GetPhase() != EDuelPhase::Battle)
			{
				Duel.EnterBattlePhase();
			}
			const int32 AttackerUid = PuzzleFindMonsterUid(Duel, EDuelOwner::Player, Step.AttackerCardId, true, true);
			if (AttackerUid == 0)
			{
				OutError = FString::Printf(TEXT("step %d: attacker card %d is not a face-up, unused Attack Position monster."),
					StepIndex, Step.AttackerCardId);
				return false;
			}
			int32 TargetUid = 0;
			if (!Step.bTargetDirect && Step.TargetCardId != 0)
			{
				TargetUid = PuzzleFindMonsterUid(Duel, EDuelOwner::Opponent, Step.TargetCardId);
				if (TargetUid == 0)
				{
					OutError = FString::Printf(TEXT("step %d: attack target card %d is not on the opponent's field."),
						StepIndex, Step.TargetCardId);
					return false;
				}
			}
			if (!Duel.Attack(AttackerUid, TargetUid, OutError))
			{
				OutError = FString::Printf(TEXT("step %d attack failed: %s"), StepIndex, *OutError);
				return false;
			}
			OutResult.StepLog.Add(FString::Printf(TEXT("attack card=%d target=%s"),
				Step.AttackerCardId, Step.bTargetDirect ? TEXT("direct") : *FString::FromInt(Step.TargetCardId)));
			return true;
		}

		if (Step.Action == TEXT("normal_summon"))
		{
			const int32 SummonUid = PuzzleFindHandUid(Duel, EDuelOwner::Player, Step.CardId);
			if (SummonUid == 0)
			{
				OutError = FString::Printf(TEXT("step %d: summon card %d is not in hand."), StepIndex, Step.CardId);
				return false;
			}
			TArray<int32> TributeUids;
			TSet<int32> Used;
			for (int32 TributeId : Step.TributeCardIds)
			{
				int32 TributeUid = 0;
				for (const FDuelCard& Card : Duel.GetSide(EDuelOwner::Player).Monsters)
				{
					if (Card.IsValid() && Card.Data.Id == TributeId && !Used.Contains(Card.Uid))
					{
						TributeUid = Card.Uid;
						break;
					}
				}
				if (TributeUid == 0)
				{
					OutError = FString::Printf(TEXT("step %d: tribute card %d is not on the player's field."),
						StepIndex, TributeId);
					return false;
				}
				Used.Add(TributeUid);
				TributeUids.Add(TributeUid);
			}
			if (!Duel.NormalSummon(SummonUid, TributeUids, false, OutError))
			{
				OutError = FString::Printf(TEXT("step %d summon failed: %s"), StepIndex, *OutError);
				return false;
			}
			OutResult.StepLog.Add(FString::Printf(TEXT("normal_summon card=%d tributes=%d"),
				Step.CardId, TributeUids.Num()));
			return true;
		}

		if (Step.Action == TEXT("activate_spell"))
		{
			const int32 Uid = PuzzleFindHandUid(Duel, EDuelOwner::Player, Step.CardId);
			if (Uid == 0)
			{
				OutError = FString::Printf(TEXT("step %d: spell card %d is not in hand."), StepIndex, Step.CardId);
				return false;
			}
			if (!Duel.ActivateSpell(Uid, OutError))
			{
				OutError = FString::Printf(TEXT("step %d spell activation failed: %s"), StepIndex, *OutError);
				return false;
			}
			OutResult.StepLog.Add(FString::Printf(TEXT("activate_spell card=%d"), Step.CardId));
			return true;
		}

		if (Step.Action == TEXT("set_spell_trap"))
		{
			const int32 Uid = PuzzleFindHandUid(Duel, EDuelOwner::Player, Step.CardId);
			if (Uid == 0)
			{
				OutError = FString::Printf(TEXT("step %d: set card %d is not in hand."), StepIndex, Step.CardId);
				return false;
			}
			if (!Duel.SetSpellTrap(Uid, OutError))
			{
				OutError = FString::Printf(TEXT("step %d set failed: %s"), StepIndex, *OutError);
				return false;
			}
			OutResult.StepLog.Add(FString::Printf(TEXT("set_spell_trap card=%d"), Step.CardId));
			return true;
		}

		if (Step.Action == TEXT("activate_trap"))
		{
			const int32 Uid = PuzzleFindSpellTrapUid(Duel, EDuelOwner::Player, Step.CardId, true);
			if (Uid == 0)
			{
				OutError = FString::Printf(TEXT("step %d: trap card %d is not Set."), StepIndex, Step.CardId);
				return false;
			}
			if (!Duel.ActivateSetTrap(Uid, OutError))
			{
				OutError = FString::Printf(TEXT("step %d trap activation failed: %s"), StepIndex, *OutError);
				return false;
			}
			OutResult.StepLog.Add(FString::Printf(TEXT("activate_trap card=%d"), Step.CardId));
			return true;
		}

		if (Step.Action == TEXT("change_position"))
		{
			const int32 Uid = PuzzleFindMonsterUid(Duel, EDuelOwner::Player, Step.CardId, false, false);
			if (Uid == 0)
			{
				OutError = FString::Printf(TEXT("step %d: position-change card %d is not on the player's field."),
					StepIndex, Step.CardId);
				return false;
			}
			if (!Duel.ChangePosition(Uid, OutError))
			{
				OutError = FString::Printf(TEXT("step %d position change failed: %s"), StepIndex, *OutError);
				return false;
			}
			const FDuelCard* Changed = Duel.FindMonster(Uid);
			const EDuelPosition Wanted = Step.Position == TEXT("defense") ? EDuelPosition::Defense : EDuelPosition::Attack;
			if (!Changed || Changed->Position != Wanted)
			{
				OutError = FString::Printf(TEXT("step %d did not reach the authored '%s' position."),
					StepIndex, *Step.Position);
				return false;
			}
			OutResult.StepLog.Add(FString::Printf(TEXT("change_position card=%d position=%s"),
				Step.CardId, *Step.Position));
			return true;
		}

		OutError = FString::Printf(TEXT("step %d uses unsupported action '%s'."), StepIndex, *Step.Action);
		return false;
	}

	int32 PuzzleCountValid(const TArray<FDuelCard>& Cards)
	{
		int32 Count = 0;
		for (const FDuelCard& Card : Cards)
		{
			if (Card.IsValid())
			{
				++Count;
			}
		}
		return Count;
	}

	int32 PuzzleCountSpellTraps(const FDuelSide& Side)
	{
		return PuzzleCountValid(Side.Spells);
	}
}

bool FDAPuzzleRuntime::LoadPuzzleFile(const FString& Path, FDAPuzzleDefinition& OutPuzzle, FString& OutError)
{
	OutError.Reset();
	TSharedPtr<FJsonObject> Root;
	if (!PuzzleReadJsonFile(Path, Root, OutError))
	{
		return false;
	}

	FDAPuzzleDefinition Puzzle;
	Puzzle.Id = PuzzleReadString(Root, TEXT("id"));
	Puzzle.Title = PuzzleReadString(Root, TEXT("title"));
	Puzzle.Objective = PuzzleReadString(Root, TEXT("objective"));
	Puzzle.Opponent = PuzzleReadString(Root, TEXT("opponent"));
	Puzzle.Template = PuzzleReadString(Root, TEXT("template"));
	Puzzle.Level = PuzzleReadInt(Root, TEXT("level"));
	Puzzle.Seed = PuzzleReadInt(Root, TEXT("seed"));
	Puzzle.TurnLimit = PuzzleReadInt(Root, TEXT("turn_limit"));
	Puzzle.TimeLimitSeconds = PuzzleReadInt(Root, TEXT("time_limit"));
	Puzzle.bEngineReady = PuzzleReadBool(Root, TEXT("engine_ready"), false);
	if (const TSharedPtr<FJsonObject> Reward = PuzzleReadObject(Root, TEXT("reward")))
	{
		Puzzle.RewardDp = PuzzleReadInt(Reward, TEXT("dp"));
	}

	if (Puzzle.Id.IsEmpty())
	{
		OutError = FString::Printf(TEXT("%s has no puzzle id."), *Path);
		return false;
	}
	if (Puzzle.Level < 1 || Puzzle.Level > 5)
	{
		OutError = FString::Printf(TEXT("%s: level %d is outside 1-5."), *Puzzle.Id, Puzzle.Level);
		return false;
	}
	if (Puzzle.Objective.IsEmpty() || Puzzle.TurnLimit < 1 || Puzzle.TimeLimitSeconds < 10 || Puzzle.RewardDp < 0)
	{
		OutError = FString::Printf(TEXT("%s: objective/turn_limit/time_limit/reward are invalid."), *Puzzle.Id);
		return false;
	}

	if (!PuzzleReadSide(PuzzleReadObject(Root, TEXT("player")), TEXT("player"), Puzzle.PlayerLp,
			Puzzle.PlayerHand, Puzzle.PlayerDeck, Puzzle.PlayerGraveyard, Puzzle.PlayerExtra,
			Puzzle.PlayerField, OutError))
	{
		return false;
	}
	if (!PuzzleReadSide(PuzzleReadObject(Root, TEXT("opponent_state")), TEXT("opponent_state"), Puzzle.OpponentLp,
			Puzzle.OpponentHand, Puzzle.OpponentDeck, Puzzle.OpponentGraveyard, Puzzle.OpponentExtra,
			Puzzle.OpponentField, OutError))
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* SolutionValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("solution"), SolutionValues)
		|| !PuzzleReadSolution(SolutionValues, Puzzle.Solution, OutError))
	{
		return false;
	}

	OutPuzzle = MoveTemp(Puzzle);
	return true;
}

bool FDAPuzzleRuntime::LoadPuzzleDirectory(const FString& Directory, TArray<FDAPuzzleDefinition>& OutPuzzles, FString& OutError)
{
	OutError.Reset();
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *FPaths::Combine(Directory, TEXT("P*.json")), true, false);
	Files.Sort();
	if (Files.Num() == 0)
	{
		OutError = FString::Printf(TEXT("No puzzle files found in '%s'."), *Directory);
		return false;
	}
	for (const FString& File : Files)
	{
		FDAPuzzleDefinition Puzzle;
		if (!LoadPuzzleFile(FPaths::Combine(Directory, File), Puzzle, OutError))
		{
			return false;
		}
		OutPuzzles.Add(MoveTemp(Puzzle));
	}
	return true;
}

bool FDAPuzzleRuntime::BuildScenario(const FDAPuzzleDefinition& Puzzle, FDuelScenario& OutScenario, FString& OutError)
{
	OutError.Reset();
	OutScenario = FDuelScenario();
	OutScenario.Id = Puzzle.Id;
	OutScenario.Name = Puzzle.Title;
	OutScenario.Objective = Puzzle.Objective;
	OutScenario.Mode = TEXT("puzzle");
	OutScenario.PlayerLp = Puzzle.PlayerLp;
	OutScenario.OpponentLp = Puzzle.OpponentLp;
	OutScenario.PlayerHand = Puzzle.PlayerHand;
	OutScenario.PlayerDeck = Puzzle.PlayerDeck;
	OutScenario.PlayerGraveyard = Puzzle.PlayerGraveyard;
	OutScenario.PlayerExtra = Puzzle.PlayerExtra;
	OutScenario.OpponentHand = Puzzle.OpponentHand;
	OutScenario.OpponentDeck = Puzzle.OpponentDeck;
	OutScenario.OpponentGraveyard = Puzzle.OpponentGraveyard;
	OutScenario.OpponentExtra = Puzzle.OpponentExtra;
	OutScenario.PlayerField = Puzzle.PlayerField;
	OutScenario.OpponentField = Puzzle.OpponentField;
	OutScenario.TurnLimit = Puzzle.TurnLimit;
	OutScenario.TimeLimitSeconds = static_cast<float>(Puzzle.TimeLimitSeconds);
	OutScenario.bPlayerGoesFirst = true;
	OutScenario.bDrawOnFirstTurn = false;
	OutScenario.Seed = Puzzle.Seed;
	return true;
}

bool FDAPuzzleRuntime::Replay(UCardDatabaseSubsystem* Database, const FDAPuzzleDefinition& Puzzle,
	FDAPuzzleReplayResult& OutResult, FString& OutError)
{
	OutResult = FDAPuzzleReplayResult();
	OutError.Reset();
	if (!Database)
	{
		OutError = TEXT("A card database is required to replay puzzles.");
		return false;
	}

	FDuelScenario Scenario;
	if (!BuildScenario(Puzzle, Scenario, OutError))
	{
		return false;
	}

	FDuelEngine Duel(Database, Puzzle.Seed);
	Duel.SetAutoAnswerAllChoices(true);
	Duel.SetLegacyAutomaticTraps(true);
	if (!Duel.StartScenario(Scenario, OutError))
	{
		OutError = FString::Printf(TEXT("start failed: %s"), *OutError);
		return false;
	}
	OutResult.bStarted = true;
	OutResult.PlayerLp = Duel.GetSide(EDuelOwner::Player).LP;
	OutResult.OpponentLp = Duel.GetSide(EDuelOwner::Opponent).LP;
	OutResult.PlayerTurns = Duel.GetScenarioPlayerTurnsTaken();

	const FDuelScenario& Active = Duel.GetActiveScenario();
	if (Active.Id != Puzzle.Id || Active.Objective != Puzzle.Objective || Active.Seed != Puzzle.Seed
		|| Active.TurnLimit != Puzzle.TurnLimit || !FMath::IsNearlyEqual(Active.TimeLimitSeconds, (float)Puzzle.TimeLimitSeconds))
	{
		OutError = TEXT("scenario metadata does not match the puzzle JSON.");
		return false;
	}
	int32 ExpectedPlayerMonsters = 0;
	int32 ExpectedPlayerSpells = 0;
	int32 ExpectedOpponentMonsters = 0;
	int32 ExpectedOpponentSpells = 0;
	for (const FDuelScenarioCard& Card : Puzzle.PlayerField)
	{
		if (Card.Zone == EDuelZone::Monster)
		{
			++ExpectedPlayerMonsters;
		}
		else
		{
			++ExpectedPlayerSpells;
		}
	}
	for (const FDuelScenarioCard& Card : Puzzle.OpponentField)
	{
		if (Card.Zone == EDuelZone::Monster)
		{
			++ExpectedOpponentMonsters;
		}
		else
		{
			++ExpectedOpponentSpells;
		}
	}

	const FDuelSide& Player = Duel.GetSide(EDuelOwner::Player);
	const FDuelSide& Opponent = Duel.GetSide(EDuelOwner::Opponent);
	if (Player.LP != Puzzle.PlayerLp || Opponent.LP != Puzzle.OpponentLp
		|| Player.Hand.Num() != Puzzle.PlayerHand.Num()
		|| Opponent.Hand.Num() != Puzzle.OpponentHand.Num()
		|| Player.Deck.Num() != Puzzle.PlayerDeck.Num()
		|| Opponent.Deck.Num() != Puzzle.OpponentDeck.Num()
		|| Player.Graveyard.Num() != Puzzle.PlayerGraveyard.Num()
		|| Opponent.Graveyard.Num() != Puzzle.OpponentGraveyard.Num()
		|| Player.Extra.Num() != Puzzle.PlayerExtra.Num()
		|| Opponent.Extra.Num() != Puzzle.OpponentExtra.Num()
		|| PuzzleCountValid(Player.Monsters) != ExpectedPlayerMonsters
		|| PuzzleCountValid(Opponent.Monsters) != ExpectedOpponentMonsters
		|| PuzzleCountSpellTraps(Player) != ExpectedPlayerSpells
		|| PuzzleCountSpellTraps(Opponent) != ExpectedOpponentSpells)
	{
		OutError = TEXT("starting board does not match the authored puzzle state.");
		return false;
	}
	if (Duel.GetScenarioPlayerTurnsTaken() != 1
		|| Duel.GetScenarioTurnsRemaining() != FMath::Max(0, Puzzle.TurnLimit - 1))
	{
		OutError = TEXT("scenario turn counter is not in the authored first-turn state.");
		return false;
	}
	if (Duel.CheckScenarioTimeout(FMath::Max(0.f, (float)Puzzle.TimeLimitSeconds - 0.5f)) || Duel.IsOver())
	{
		OutError = TEXT("scenario timed out before the authored solution started.");
		return false;
	}

	for (int32 StepIndex = 0; StepIndex < Puzzle.Solution.Num(); ++StepIndex)
	{
		if (!PuzzleExecuteStep(Duel, Puzzle.Solution[StepIndex], StepIndex, OutResult, OutError))
		{
			return false;
		}
		if (Duel.HasPendingChoice())
		{
			FString ChoiceError;
			if (!Duel.AutoAnswerPendingChoice(&ChoiceError))
			{
				OutError = FString::Printf(TEXT("step %d could not resolve a choice: %s"), StepIndex, *ChoiceError);
				return false;
			}
		}
		++OutResult.StepsExecuted;
		OutResult.PlayerLp = Duel.GetSide(EDuelOwner::Player).LP;
		OutResult.OpponentLp = Duel.GetSide(EDuelOwner::Opponent).LP;
		if (Duel.IsOver())
		{
			const bool bLastStep = StepIndex == Puzzle.Solution.Num() - 1;
			if (!bLastStep)
			{
				OutError = FString::Printf(TEXT("duel ended after step %d, before the final authored step."), StepIndex);
				return false;
			}
			break;
		}
	}

	if (!Duel.IsOver() || Duel.GetWinner() != EDuelOwner::Player || Duel.GetSide(EDuelOwner::Opponent).LP > 0)
	{
		OutError = FString::Printf(TEXT("solution did not win (phase %d, player LP %d, opponent LP %d)."),
			static_cast<int32>(Duel.GetPhase()), Duel.GetSide(EDuelOwner::Player).LP,
			Duel.GetSide(EDuelOwner::Opponent).LP);
		return false;
	}
	if (Duel.HasPendingChoice())
	{
		OutError = TEXT("solution left a pending choice unresolved.");
		return false;
	}

	OutResult.bWon = true;
	OutResult.PlayerLp = Duel.GetSide(EDuelOwner::Player).LP;
	OutResult.OpponentLp = Duel.GetSide(EDuelOwner::Opponent).LP;
	OutResult.PlayerTurns = Duel.GetScenarioPlayerTurnsTaken();
	return true;
}

bool FDAPuzzleRuntime::ReplayById(UCardDatabaseSubsystem* Database, const FString& PuzzleId,
	FDAPuzzleReplayResult& OutResult, FString& OutError)
{
	OutResult = FDAPuzzleReplayResult();
	OutError.Reset();
	if (PuzzleId.IsEmpty())
	{
		OutError = TEXT("Puzzle id is empty.");
		return false;
	}
	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Puzzles"), PuzzleId + TEXT(".json"));
	FDAPuzzleDefinition Puzzle;
	if (!LoadPuzzleFile(Path, Puzzle, OutError))
	{
		return false;
	}
	return Replay(Database, Puzzle, OutResult, OutError);
}
