// Duel Academy Island - duel engine diagnostics and AI-vs-AI self-test.
//
// Split out of DADuelEngine.cpp so the runtime rules file stays focused on
// gameplay.  These are private FDuelEngine member definitions declared in
// DADuelEngine.h; behaviour, messages, ordering and output strings are
// unchanged by the move.

#include "DADuelEngine.h"

#include "DACardRecords.h"
#include "DADuelRulesSelfTest.h"
#include "DuelAcademyIsland.h"

#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Engine/World.h"
#include "Engine/GameInstance.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	int32 SelfTestCountOwnedCards(const FDuelSide& First, const FDuelSide& Second, EDuelOwner Owner);
}

bool FDuelEngine::CheckDuelStateInvariants(int32 ExpectedPlayerCards, int32 ExpectedOpponentCards,
	TArray<FString>& OutErrors) const
{
	const int32 StartErrorCount = OutErrors.Num();
	auto AddError = [&OutErrors](const FString& Message)
	{
		OutErrors.Add(Message);
	};

	if (Player.Monsters.Num() != 5 || Opponent.Monsters.Num() != 5)
	{
		AddError(TEXT("Monster Zone arrays must always contain five slots."));
	}
	if (Player.Spells.Num() != 5 || Opponent.Spells.Num() != 5)
	{
		AddError(TEXT("Spell & Trap Zone arrays must always contain five slots."));
	}
	if (Player.LP < 0 || Opponent.LP < 0)
	{
		AddError(FString::Printf(TEXT("Life Points went negative (player %d, opponent %d)."), Player.LP, Opponent.LP));
	}
	if (bWinnerSet)
	{
		if (Phase != EDuelPhase::Over)
		{
			AddError(TEXT("A finished duel must be in the Over phase."));
		}
		if (ResultStats.bDraw != bDraw)
		{
			AddError(TEXT("ResultStats.bDraw disagrees with the engine draw outcome."));
		}
		if (bDraw && ResultStats.bPlayerWon)
		{
			AddError(TEXT("A drawn duel must not report a player win."));
		}
		if (!bDraw && ResultStats.bPlayerWon != (Winner == EDuelOwner::Player))
		{
			AddError(TEXT("ResultStats.bPlayerWon disagrees with the winning side."));
		}
	}
	else if (Phase == EDuelPhase::Over)
	{
		AddError(TEXT("The Over phase is only legal after a winner is set."));
	}
	if (bDraw && !bWinnerSet)
	{
		AddError(TEXT("A draw flag is only legal after the duel has finished."));
	}
	if (bStarted && TurnNumber <= 0)
	{
		AddError(TEXT("A started duel must have a positive turn number."));
	}
	if (ActiveSide != EDuelOwner::Player && ActiveSide != EDuelOwner::Opponent)
	{
		AddError(TEXT("Active side is not a valid duelist."));
	}
	if (bAwaitingDiscard && Player.Hand.Num() <= HandLimit)
	{
		AddError(TEXT("A discard is pending even though the player is at or below the hand limit."));
	}
	if (HasPendingChoice())
	{
		AddError(TEXT("A pending choice was left unanswered after a completed step."));
	}
	if (IsChainOpen())
	{
		AddError(FString::Printf(TEXT("A chain was left open (%d link(s))."), ChainLinks.Num()));
	}

	TSet<int32> SeenUids;
	TArray<int32> EquipTargets;
	TArray<int32> TiedTargets;

	auto CheckCard = [&](const FDuelCard& Card, EDuelOwner Side, const TCHAR* Zone,
		bool bFieldZone, bool bExtraZone, bool bMainDeckZone)
	{
		const TCHAR* SideName = Side == EDuelOwner::Player ? TEXT("Player") : TEXT("Opponent");
		if (Card.Uid <= 0)
		{
			AddError(FString::Printf(TEXT("%s %s contains a card with no instance uid."), SideName, Zone));
			return;
		}
		if (Card.Data.Id <= 0)
		{
			AddError(FString::Printf(TEXT("%s %s uid %d has no card id."), SideName, Zone, Card.Uid));
		}
		if (!bFieldZone && Card.Owner != Side)
		{
			AddError(FString::Printf(TEXT("%s %s uid %d is owned by the other duelist."), SideName, Zone, Card.Uid));
		}
		if (Card.Controller != EDuelOwner::Player && Card.Controller != EDuelOwner::Opponent)
		{
			AddError(FString::Printf(TEXT("%s %s uid %d has an invalid controller."), SideName, Zone, Card.Uid));
		}
		if (SeenUids.Contains(Card.Uid))
		{
			AddError(FString::Printf(TEXT("Duplicate card instance uid %d."), Card.Uid));
		}
		else
		{
			SeenUids.Add(Card.Uid);
		}
		if (bExtraZone && !Card.bExtra)
		{
			AddError(FString::Printf(TEXT("Extra Deck uid %d is not marked as an Extra Deck card."), Card.Uid));
		}
		if (bMainDeckZone && Card.bExtra)
		{
			AddError(FString::Printf(TEXT("Main Deck uid %d is marked as an Extra Deck card."), Card.Uid));
		}
		if (Card.Counters < 0 || Card.AttacksUsed < 0 || Card.ExtraAttacks < 0)
		{
			AddError(FString::Printf(TEXT("Card uid %d has a negative counter/attack value."), Card.Uid));
		}
		if (Card.EquippedToUid < 0 || Card.TiedToUid < 0)
		{
			AddError(FString::Printf(TEXT("Card uid %d has a negative equipment/tie target."), Card.Uid));
		}
		if (Card.SummonedTurn > TurnNumber || Card.PositionChangedTurn > TurnNumber
			|| Card.SetTurn > TurnNumber || Card.EffectUsedTurn > TurnNumber)
		{
			AddError(FString::Printf(TEXT("Card uid %d has a turn stamp from the future."), Card.Uid));
		}
		if (Card.EquippedToUid != 0)
		{
			EquipTargets.Add(Card.EquippedToUid);
		}
		if (Card.TiedToUid != 0)
		{
			TiedTargets.Add(Card.TiedToUid);
		}
	};

	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		const FDuelSide& State = SideRef(Side);
		const TCHAR* SideName = Side == EDuelOwner::Player ? TEXT("Player") : TEXT("Opponent");

		auto VisitArray = [&](const TArray<FDuelCard>& Cards, const TCHAR* Zone,
			bool bExtraZone, bool bMainDeckZone)
		{
			for (const FDuelCard& Card : Cards)
			{
				if (Card.Uid <= 0)
				{
					AddError(FString::Printf(TEXT("%s %s contains an invalid card entry."), SideName, Zone));
					continue;
				}
				CheckCard(Card, Side, Zone, false, bExtraZone, bMainDeckZone);
			}
		};

		VisitArray(State.Deck, TEXT("Deck"), false, true);
		VisitArray(State.Hand, TEXT("Hand"), false, false);
		VisitArray(State.Graveyard, TEXT("Graveyard"), false, false);
		VisitArray(State.Banished, TEXT("Banished"), false, false);
		VisitArray(State.Extra, TEXT("Extra Deck"), true, false);

		for (int32 I = 0; I < State.Monsters.Num(); ++I)
		{
			const FDuelCard& Card = State.Monsters[I];
			if (!Card.IsValid())
			{
				continue;
			}
			CheckCard(Card, Side, TEXT("Monster Zone"), true, false, false);
			if (!Card.IsMonster())
			{
				AddError(FString::Printf(TEXT("%s Monster Zone %d contains a non-monster card uid %d."),
					SideName, I, Card.Uid));
			}
		}
		for (int32 I = 0; I < State.Spells.Num(); ++I)
		{
			const FDuelCard& Card = State.Spells[I];
			if (!Card.IsValid())
			{
				continue;
			}
			CheckCard(Card, Side, TEXT("Spell & Trap Zone"), true, false, false);
			if (!Card.IsSpell() && !Card.IsTrap())
			{
				AddError(FString::Printf(TEXT("%s Spell & Trap Zone %d contains a non-Spell/Trap uid %d."),
					SideName, I, Card.Uid));
			}
		}
		if (State.Field.IsValid())
		{
			CheckCard(State.Field, Side, TEXT("Field Zone"), true, false, false);
			if (!State.Field.IsSpell())
			{
				AddError(FString::Printf(TEXT("%s Field Zone contains a non-Spell uid %d."), SideName, State.Field.Uid));
			}
		}
	}

	for (int32 Uid : EquipTargets)
	{
		if (!SeenUids.Contains(Uid))
		{
			AddError(FString::Printf(TEXT("Equipment points at missing card uid %d."), Uid));
		}
	}
	for (int32 Uid : TiedTargets)
	{
		if (!SeenUids.Contains(Uid))
		{
			AddError(FString::Printf(TEXT("Card tie points at missing card uid %d."), Uid));
		}
	}

	if (ExpectedPlayerCards >= 0)
	{
		const int32 Actual = SelfTestCountOwnedCards(Player, Opponent, EDuelOwner::Player);
		if (Actual != ExpectedPlayerCards)
		{
			AddError(FString::Printf(TEXT("Player card count changed from %d to %d."), ExpectedPlayerCards, Actual));
		}
	}
	if (ExpectedOpponentCards >= 0)
	{
		const int32 Actual = SelfTestCountOwnedCards(Player, Opponent, EDuelOwner::Opponent);
		if (Actual != ExpectedOpponentCards)
		{
			AddError(FString::Printf(TEXT("Opponent card count changed from %d to %d."), ExpectedOpponentCards, Actual));
		}
	}

	return OutErrors.Num() == StartErrorCount;
}

namespace
{
	constexpr int32 SelfTestMaxIterations = 10000;
	constexpr int32 SelfTestMaxSteps = 240;
	constexpr int32 SelfTestMaxTurns = 120;

	FString SelfTestJoinErrors(const TArray<FString>& Errors)
	{
		return Errors.Num() > 0 ? FString::Join(Errors, TEXT(" | ")) : FString();
	}

	bool SelfTestLoadJsonObject(const FString& Path, TSharedPtr<FJsonObject>& OutObject, FString& OutError)
	{
		OutObject.Reset();
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			OutError = FString::Printf(TEXT("cannot read %s"), *Path);
			return false;
		}
		TSharedPtr<FJsonValue> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || !Root->AsObject().IsValid())
		{
			OutError = FString::Printf(TEXT("invalid JSON object in %s"), *Path);
			return false;
		}
		OutObject = Root->AsObject();
		return true;
	}

	FString SelfTestReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Default = FString())
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Default;
	}

	int32 SelfTestReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool SelfTestReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bDefault = false)
	{
		bool bValue = bDefault;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	void SelfTestReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<int32>& OutValues)
	{
		OutValues.Reset();
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!Object.IsValid() || !Object->TryGetArrayField(Field, Values) || !Values)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			if (Value.IsValid() && Value->Type == EJson::Number)
			{
				OutValues.Add(static_cast<int32>(Value->AsNumber()));
			}
		}
	}

	int32 SelfTestCountOwnedCards(const FDuelSide& First, const FDuelSide& Second, EDuelOwner Owner)
	{
		int32 Count = 0;
		auto CountSide = [&Count, Owner](const FDuelSide& Side)
		{
			auto CountArray = [&Count, Owner](const TArray<FDuelCard>& Cards)
			{
				for (const FDuelCard& Card : Cards)
				{
					if (Card.IsValid() && Card.Owner == Owner)
					{
						++Count;
					}
				}
			};
			CountArray(Side.Deck);
			CountArray(Side.Hand);
			CountArray(Side.Graveyard);
			CountArray(Side.Banished);
			CountArray(Side.Extra);
			for (const FDuelCard& Card : Side.Monsters)
			{
				if (Card.IsValid() && Card.Owner == Owner)
				{
					++Count;
				}
			}
			for (const FDuelCard& Card : Side.Spells)
			{
				if (Card.IsValid() && Card.Owner == Owner)
				{
					++Count;
				}
			}
			if (Side.Field.IsValid() && Side.Field.Owner == Owner)
			{
				++Count;
			}
		};
		CountSide(First);
		CountSide(Second);
		return Count;
	}

	bool SelfTestHasWinCondition(UCardDatabaseSubsystem* Database, const TArray<int32>& CardIds)
	{
		if (!Database)
		{
			return false;
		}
		for (int32 CardId : CardIds)
		{
			const FCardRecord* Card = Database->FindCard(CardId);
			if (!Card)
			{
				continue;
			}
			if (Card->IsMonster() && Card->Atk > 0)
			{
				return true;
			}
			if (Card->Name.Contains(TEXT("Exodia"), ESearchCase::IgnoreCase)
				|| Card->Name.Contains(TEXT("Final Countdown"), ESearchCase::IgnoreCase)
				|| Card->Name.Contains(TEXT("Destiny Board"), ESearchCase::IgnoreCase)
				|| Card->Name.Contains(TEXT("Last Turn"), ESearchCase::IgnoreCase))
			{
				return true;
			}
			if (!Card->IsMonster()
				&& (Card->Description.Contains(TEXT("inflict"), ESearchCase::IgnoreCase)
					|| Card->Description.Contains(TEXT("damage to your opponent"), ESearchCase::IgnoreCase)
					|| Card->Description.Contains(TEXT("damage to both players"), ESearchCase::IgnoreCase)))
			{
				return true;
			}
		}
		return false;
	}

	FDuelScenario SelfTestBuildPuzzleScenario(const TSharedPtr<FJsonObject>& Puzzle)
	{
		FDuelScenario Scenario;
		Scenario.Id = SelfTestReadString(Puzzle, TEXT("id"));
		Scenario.Name = SelfTestReadString(Puzzle, TEXT("title"));
		Scenario.Mode = TEXT("puzzle");
		Scenario.Seed = SelfTestReadInt(Puzzle, TEXT("seed"));
		Scenario.TurnLimit = SelfTestReadInt(Puzzle, TEXT("turn_limit"));
		Scenario.TimeLimitSeconds = static_cast<float>(SelfTestReadInt(Puzzle, TEXT("time_limit")));
		Scenario.bPlayerGoesFirst = true;
		Scenario.bDrawOnFirstTurn = false;

		auto ReadSide = [&](const TCHAR* SideField, int32& OutLp, TArray<int32>& Hand,
			TArray<int32>& Deck, TArray<int32>& Graveyard, TArray<int32>& Extra,
			TArray<FDuelScenarioCard>& OutField)
		{
			const TSharedPtr<FJsonObject>* SideObject = nullptr;
			if (!Puzzle.IsValid() || !Puzzle->TryGetObjectField(SideField, SideObject)
				|| !SideObject || !SideObject->IsValid())
			{
				return;
			}
			const TSharedPtr<FJsonObject> Side = *SideObject;
			OutLp = SelfTestReadInt(Side, TEXT("lp"), OutLp);
			SelfTestReadIntArray(Side, TEXT("hand"), Hand);
			SelfTestReadIntArray(Side, TEXT("deck"), Deck);
			SelfTestReadIntArray(Side, TEXT("graveyard"), Graveyard);
			SelfTestReadIntArray(Side, TEXT("extra"), Extra);

			const TArray<TSharedPtr<FJsonValue>>* FieldValues = nullptr;
			if (Side->TryGetArrayField(TEXT("field"), FieldValues) && FieldValues)
			{
				for (int32 I = 0; I < FieldValues->Num(); ++I)
				{
					const TSharedPtr<FJsonValue>& Value = (*FieldValues)[I];
					const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
					if (!Entry.IsValid())
					{
						continue;
					}
					FDuelScenarioCard Spec;
					Spec.CardId = SelfTestReadInt(Entry, TEXT("card_id"));
					Spec.Zone = EDuelZone::Monster;
					Spec.ZoneIndex = I;
					Spec.bFaceDown = !SelfTestReadBool(Entry, TEXT("face_up"), true);
					Spec.bDefense = SelfTestReadString(Entry, TEXT("position"), TEXT("attack")).Equals(
						TEXT("defense"), ESearchCase::IgnoreCase);
					OutField.Add(Spec);
				}
			}

			const TArray<TSharedPtr<FJsonValue>>* SpellValues = nullptr;
			if (Side->TryGetArrayField(TEXT("spell_traps"), SpellValues) && SpellValues)
			{
				for (int32 I = 0; I < SpellValues->Num(); ++I)
				{
					const TSharedPtr<FJsonValue>& Value = (*SpellValues)[I];
					const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
					if (!Entry.IsValid())
					{
						continue;
					}
					FDuelScenarioCard Spec;
					Spec.CardId = SelfTestReadInt(Entry, TEXT("card_id"));
					Spec.Zone = EDuelZone::SpellTrap;
					Spec.ZoneIndex = I;
					Spec.bFaceDown = !SelfTestReadBool(Entry, TEXT("face_up"), false);
					OutField.Add(Spec);
				}
			}
		};

		ReadSide(TEXT("player"), Scenario.PlayerLp, Scenario.PlayerHand, Scenario.PlayerDeck,
			Scenario.PlayerGraveyard, Scenario.PlayerExtra, Scenario.PlayerField);
		ReadSide(TEXT("opponent_state"), Scenario.OpponentLp, Scenario.OpponentHand, Scenario.OpponentDeck,
			Scenario.OpponentGraveyard, Scenario.OpponentExtra, Scenario.OpponentField);
		return Scenario;
	}
}

FString FDuelEngine::RunSelfTest(UCardDatabaseSubsystem* Database, int32 Iterations)
{
	const double StartSeconds = FPlatformTime::Seconds();
	if (!Database)
	{
		return TEXT("Duel self-test: card database missing.");
	}

	// -DADuelSelfTest=N, on top of the legacy -DADuelSelfTest switch handled by
	// the HUD.  DADuelSelfTestArgs owns the parse so this batch and the
	// rules-self-test subsystem cannot drift apart.
	int32 RequestedIterations = DADuelSelfTestArgs::ParseRequestedIterations(Iterations, SelfTestMaxIterations);

	// Load the A06/Judge list once; every gate duel and every deck audit below
	// shares the same ruleset.
	FDuelEngine RulesEngine(Database, 0);
	FString BanlistError;
	const bool bBanlistLoaded = RulesEngine.LoadDefaultBannedList(BanlistError);
	if (!bBanlistLoaded)
	{
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("[DeckLegality] banned_limited.json unavailable (%s); only copy/size checks are authoritative."),
			*BanlistError);
	}
	const FDuelBannedListRuleset GateBanned = RulesEngine.GetBannedList();

	int32 ConstructedTotal = 0;
	int32 ConstructedPass = 0;
	int32 PuzzleTotal = 0;
	int32 PuzzlePass = 0;

	auto AuditConstructedDeck = [&](const FString& DeckId, const TCHAR* Source,
		const TArray<int32>& Main, const TArray<int32>& Extra)
	{
		++ConstructedTotal;
		FDuelDeckValidationResult Result = RulesEngine.ValidateDeck(Main, Extra);
		TArray<int32> AllCards = Main;
		AllCards.Append(Extra);
		if (!SelfTestHasWinCondition(Database, AllCards))
		{
			Result.AddError(TEXT("no legal win condition (no attack-capable monster or damage/alternate-win card)"));
		}
		if (Result.bValid)
		{
			++ConstructedPass;
			UE_LOG(LogDuelAcademyIsland, Log,
				TEXT("[DeckLegality] PASS %s (%s, main=%d extra=%d)"), *DeckId, Source, Main.Num(), Extra.Num());
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("[DeckLegality] FAIL %s (%s, main=%d extra=%d): %s"),
				*DeckId, Source, Main.Num(), Extra.Num(), *SelfTestJoinErrors(Result.Errors));
		}
	};

	// Starter/shop decks owned by A06 and consumed by FDuelEngine::Start.
	for (const FStarterDeckDef& Deck : Database->GetDecks())
	{
		AuditConstructedDeck(Deck.Id, TEXT("Data/decks.json"), Deck.Cards, Deck.Extra);
	}

	// A06's saved player-deck catalogue (one deck per object in "decks").
	{
		const FString PlayerDeckPath = FPaths::ProjectContentDir() / TEXT("Data/Decks/player_decks.json");
		TSharedPtr<FJsonObject> Root;
		FString LoadError;
		if (SelfTestLoadJsonObject(PlayerDeckPath, Root, LoadError))
		{
			const TArray<TSharedPtr<FJsonValue>>* Decks = nullptr;
			if (Root->TryGetArrayField(TEXT("decks"), Decks) && Decks)
			{
				for (const TSharedPtr<FJsonValue>& Value : *Decks)
				{
					const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
					if (!Entry.IsValid())
					{
						continue;
					}
					TArray<int32> Main;
					TArray<int32> Extra;
					SelfTestReadIntArray(Entry, TEXT("main"), Main);
					SelfTestReadIntArray(Entry, TEXT("extra"), Extra);
					AuditConstructedDeck(SelfTestReadString(Entry, TEXT("id"), TEXT("player_deck")),
						TEXT("Data/Decks/player_decks.json"), Main, Extra);
				}
			}
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DeckLegality] %s"), *LoadError);
		}
	}

	// A07/A06 opponent decks.  FDuelEngine itself does not register these in
	// UCardDatabaseSubsystem yet, so the gate reads the same files the opponent
	// loader ships and validates the lists the port will hand to the engine.
	{
		const FString OpponentDeckDir = FPaths::ProjectContentDir() / TEXT("Data/Opponents/decks");
		TArray<FString> Files;
		IFileManager::Get().FindFiles(Files, *OpponentDeckDir, TEXT("*.json"));
		Files.Sort();
		for (const FString& File : Files)
		{
			const FString Path = OpponentDeckDir / File;
			TSharedPtr<FJsonObject> Root;
			FString LoadError;
			if (!SelfTestLoadJsonObject(Path, Root, LoadError))
			{
				++ConstructedTotal;
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DeckLegality] FAIL %s: %s"), *File, *LoadError);
				continue;
			}
			TArray<int32> Main;
			TArray<int32> Extra;
			SelfTestReadIntArray(Root, TEXT("cards"), Main);
			if (Main.Num() == 0)
			{
				SelfTestReadIntArray(Root, TEXT("main"), Main);
			}
			SelfTestReadIntArray(Root, TEXT("extra"), Extra);
			AuditConstructedDeck(SelfTestReadString(Root, TEXT("id"), FPaths::GetBaseFilename(File)),
				TEXT("Data/Opponents/decks"), Main, Extra);
		}
	}

	// Puzzle boards are fixed scenarios, not 40-card constructed decks.  They
	// are still checked for known ids, copy/limit legality and a legal win
	// condition, then actually constructed through StartScenario.
	{
		const FString PuzzleDir = FPaths::ProjectContentDir() / TEXT("Data/Puzzles");
		TArray<FString> Files;
		IFileManager::Get().FindFiles(Files, *PuzzleDir, TEXT("P*.json"));
		Files.Sort();
		FDuelEngine PuzzleProbe(Database, 1);
		PuzzleProbe.SetBannedList(GateBanned);
		PuzzleProbe.SetAutoAnswerAllChoices(true);
		for (const FString& File : Files)
		{
			++PuzzleTotal;
			TSharedPtr<FJsonObject> Root;
			FString LoadError;
			TArray<FString> Errors;
			if (!SelfTestLoadJsonObject(PuzzleDir / File, Root, LoadError))
			{
				Errors.Add(LoadError);
			}
			else
			{
				const FDuelScenario Scenario = SelfTestBuildPuzzleScenario(Root);
				TArray<int32> PlayerIds = Scenario.PlayerHand;
				PlayerIds.Append(Scenario.PlayerDeck);
				PlayerIds.Append(Scenario.PlayerGraveyard);
				PlayerIds.Append(Scenario.PlayerExtra);
				for (const FDuelScenarioCard& Spec : Scenario.PlayerField)
				{
					PlayerIds.Add(Spec.CardId);
				}
				TArray<int32> AllIds = PlayerIds;
				AllIds.Append(Scenario.OpponentHand);
				AllIds.Append(Scenario.OpponentDeck);
				AllIds.Append(Scenario.OpponentGraveyard);
				AllIds.Append(Scenario.OpponentExtra);
				for (const FDuelScenarioCard& Spec : Scenario.OpponentField)
				{
					AllIds.Add(Spec.CardId);
				}

				TMap<int32, int32> Counts;
				for (int32 CardId : AllIds)
				{
					if (CardId <= 0)
					{
						Errors.Add(TEXT("board contains an invalid card id"));
						continue;
					}
					if (!Database->FindCard(CardId))
					{
						Errors.Add(FString::Printf(TEXT("unknown card %d"), CardId));
					}
					++Counts.FindOrAdd(CardId);
				}
				for (const TPair<int32, int32>& Pair : Counts)
				{
					const int32 Limit = FMath::Min(GateBanned.GetLimit(Pair.Key), GateBanned.MaxCopies);
					if (Limit == 0)
					{
						Errors.Add(FString::Printf(TEXT("banned card %d"), Pair.Key));
					}
					else if (Pair.Value > Limit)
					{
						Errors.Add(FString::Printf(TEXT("card %d has %d copies; limit %d"), Pair.Key, Pair.Value, Limit));
					}
				}
				if (Scenario.PlayerExtra.Num() > GateBanned.MaxExtra)
				{
					Errors.Add(FString::Printf(TEXT("player Extra Deck has %d cards; limit %d"),
						Scenario.PlayerExtra.Num(), GateBanned.MaxExtra));
				}
				if (Scenario.OpponentExtra.Num() > GateBanned.MaxExtra)
				{
					Errors.Add(FString::Printf(TEXT("opponent Extra Deck has %d cards; limit %d"),
						Scenario.OpponentExtra.Num(), GateBanned.MaxExtra));
				}
				// Fixed puzzle boards may win through the opponent's Graveyard
				// (Autonomous Action Unit, Premature Burial, etc.), so the
				// player-only win-condition heuristic is not meaningful here.
				// A07's PuzzleSelfTest replays every authored solution instead.
				if (Errors.Num() == 0)
				{
					FString StartError;
					if (!PuzzleProbe.StartScenario(Scenario, StartError))
					{
						Errors.Add(FString::Printf(TEXT("StartScenario failed: %s"), *StartError));
					}
					else
					{
						TArray<FString> StateErrors;
						PuzzleProbe.CheckDuelStateInvariants(-1, -1, StateErrors);
						Errors.Append(StateErrors);
					}
				}
			}

			if (Errors.Num() == 0)
			{
				++PuzzlePass;
				UE_LOG(LogDuelAcademyIsland, Log, TEXT("[PuzzleLegality] PASS %s"), *File);
			}
			else
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[PuzzleLegality] FAIL %s: %s"),
					*File, *SelfTestJoinErrors(Errors));
			}
		}
	}

	const TCHAR* Starters[] = { TEXT("fire"), TEXT("water"), TEXT("wind") };
	int32 PlayerWins = 0;
	int32 OpponentWins = 0;
	int32 Draws = 0;
	int32 Stalls = 0;
	int32 TotalTurns = 0;
	int32 GamesWithErrors = 0;
	int32 DeckGameFailures = 0;
	TArray<FString> FailureDetails;

	for (int32 Iteration = 0; Iteration < RequestedIterations; ++Iteration)
	{
		const int32 Seed = 1200 + Iteration * 37;
		const FString PlayerDeckId = Starters[Iteration % 3];
		FDuelEngine Duel(Database, Seed);
		Duel.SetBannedList(GateBanned);
		Duel.SetAutoAnswerAllChoices(true);

		TArray<FString> Errors;
		const FStarterDeckDef* PlayerDeck = Database->FindDeck(PlayerDeckId);
		const FStarterDeckDef* OpponentDeck = Database->FindDeck(TEXT("jaden"));
		if (!PlayerDeck || !OpponentDeck)
		{
			Errors.Add(TEXT("gate starter deck is missing from the card database"));
		}
		else
		{
			const FDuelDeckValidationResult PlayerValid = Duel.ValidateDeck(PlayerDeck->Cards, PlayerDeck->Extra);
			const FDuelDeckValidationResult OpponentValid = Duel.ValidateDeck(OpponentDeck->Cards, OpponentDeck->Extra);
			if (!PlayerValid.bValid || !OpponentValid.bValid)
			{
				++DeckGameFailures;
				if (!PlayerValid.bValid)
				{
					Errors.Add(FString::Printf(TEXT("player deck '%s': %s"), *PlayerDeckId,
						*SelfTestJoinErrors(PlayerValid.Errors)));
				}
				if (!OpponentValid.bValid)
				{
					Errors.Add(FString::Printf(TEXT("opponent deck 'jaden': %s"),
						*SelfTestJoinErrors(OpponentValid.Errors)));
				}
			}
		}

		Duel.Start(PlayerDeckId, TEXT("jaden"));
		if (!Duel.IsStarted())
		{
			Errors.Add(TEXT("duel did not start"));
		}

		const int32 InitialPlayerCards = SelfTestCountOwnedCards(
			Duel.GetSide(EDuelOwner::Player), Duel.GetSide(EDuelOwner::Opponent), EDuelOwner::Player);
		const int32 InitialOpponentCards = SelfTestCountOwnedCards(
			Duel.GetSide(EDuelOwner::Player), Duel.GetSide(EDuelOwner::Opponent), EDuelOwner::Opponent);

		EDuelPhase LastPhase = Duel.GetPhase();
		int32 LastTurn = Duel.GetTurnNumber();
		auto PhaseName = [](EDuelPhase InPhase) -> FString
		{
			switch (InPhase)
			{
			case EDuelPhase::Main1: return TEXT("Main1");
			case EDuelPhase::Battle: return TEXT("Battle");
			case EDuelPhase::Main2: return TEXT("Main2");
			case EDuelPhase::Over: return TEXT("Over");
			default: return TEXT("Unknown");
			}
		};
		auto ObservePhase = [&]()
		{
			const EDuelPhase CurrentPhase = Duel.GetPhase();
			const int32 CurrentTurn = Duel.GetTurnNumber();
			const bool bTurnAdvanced = CurrentTurn > LastTurn;
			bool bLegal = false;
			if (CurrentPhase == LastPhase && CurrentTurn == LastTurn)
			{
				bLegal = true;
			}
			else if (Duel.IsOver() && CurrentPhase == EDuelPhase::Over)
			{
				bLegal = true;
			}
			else if (bTurnAdvanced)
			{
				bLegal = CurrentPhase == EDuelPhase::Main1;
			}
			else
			{
				switch (LastPhase)
				{
				case EDuelPhase::Main1:
					bLegal = CurrentPhase == EDuelPhase::Battle || CurrentPhase == EDuelPhase::Main2;
					break;
				case EDuelPhase::Battle:
					bLegal = CurrentPhase == EDuelPhase::Main2;
					break;
				default:
					bLegal = false;
					break;
				}
			}
			if (!bLegal)
			{
				Errors.Add(FString::Printf(TEXT("illegal phase transition turn %d: %s -> %s"),
					CurrentTurn, *PhaseName(LastPhase), *PhaseName(CurrentPhase)));
			}
			LastPhase = CurrentPhase;
			LastTurn = CurrentTurn;
		};

		auto AnswerPending = [&]()
		{
			int32 Guard = 0;
			while (Duel.HasPendingChoice() && Guard++ < 64)
			{
				FString ChoiceError;
				if (!Duel.AutoAnswerPendingChoice(&ChoiceError))
				{
					Errors.Add(FString::Printf(TEXT("could not answer pending choice: %s"), *ChoiceError));
					break;
				}
			}
			if (Duel.HasPendingChoice())
			{
				Errors.Add(TEXT("pending choice remained after auto-answer"));
			}
		};

		auto FlushChain = [&]()
		{
			if (Duel.IsChainOpen())
			{
				Errors.Add(FString::Printf(TEXT("open chain of %d link(s) left after a step"), Duel.GetChainLinks().Num()));
				FString ChainError;
				Duel.ResolveChain(ChainError);
			}
		};

		auto CheckState = [&]()
		{
			TArray<FString> StateErrors;
			Duel.CheckDuelStateInvariants(InitialPlayerCards, InitialOpponentCards, StateErrors);
			Errors.Append(StateErrors);
		};

		CheckState();
		ObservePhase();
		int32 Steps = 0;
		while (!Duel.IsOver() && Steps < SelfTestMaxSteps && Duel.GetTurnNumber() <= SelfTestMaxTurns)
		{
			++Steps;
			if (Duel.GetActiveSide() == EDuelOwner::Player)
			{
				Duel.AiPlayMainPhase();
				AnswerPending();
				FlushChain();
				ObservePhase();
				CheckState();
				if (!Duel.IsOver())
				{
					// Public phase actions instead of direct Phase writes, so
					// the batch enters the Battle Phase like the HUD does.
					Duel.EnterBattlePhase();
					ObservePhase();
					Duel.AiPlayBattlePhase();
					AnswerPending();
					FlushChain();
					ObservePhase();
					CheckState();
				}
				if (Duel.IsOver())
				{
					break;
				}
				Duel.EndBattlePhase();
				ObservePhase();
				// EndTurn routes the hand limit and the End-Phase effects
				// through FinishPlayerTurn like a player-driven duel.
				Duel.EndTurn();
				if (Duel.IsAwaitingDiscard())
				{
					while (Duel.IsAwaitingDiscard() && Duel.Player.Hand.Num() > HandLimit)
					{
						FString DiscardError;
						if (!Duel.DiscardFromHand(Duel.Player.Hand[0].Uid, DiscardError))
						{
							Errors.Add(FString::Printf(TEXT("hand-limit discard failed: %s"), *DiscardError));
							break;
						}
					}
				}
				Duel.bAiTurnPending = true;
				Duel.RunOpponentTurn();
			}
			else
			{
				Duel.bAiTurnPending = true;
				Duel.RunOpponentTurn();
			}
			AnswerPending();
			FlushChain();
			ObservePhase();
			CheckState();
		}

		TotalTurns += Duel.GetTurnNumber();
		if (!Duel.IsOver())
		{
			++Stalls;
			Errors.Add(FString::Printf(TEXT("stalled after %d step(s), turn %d"), Steps, Duel.GetTurnNumber()));
		}
		else if (Duel.IsDraw())
		{
			++Draws;
		}
		else
		{
			EDuelOwner WinnerSide = EDuelOwner::Opponent;
			if (Duel.TryGetWinner(WinnerSide) && WinnerSide == EDuelOwner::Player)
			{
				++PlayerWins;
			}
			else
			{
				++OpponentWins;
			}
		}

		if (Duel.IsOver())
		{
			if (Duel.GetResultStats().Turns != Duel.GetTurnNumber())
			{
				Errors.Add(TEXT("result stats did not finalize the turn count"));
			}
			if (Duel.GetResultStats().PlayerLp != Duel.GetSide(EDuelOwner::Player).LP
				|| Duel.GetResultStats().OpponentLp != Duel.GetSide(EDuelOwner::Opponent).LP)
			{
				Errors.Add(TEXT("result stats do not match the final Life Points"));
			}
		}
		AnswerPending();
		FlushChain();
		CheckState();

		if (Errors.Num() > 0)
		{
			++GamesWithErrors;
			if (FailureDetails.Num() < 40)
			{
				FailureDetails.Add(FString::Printf(TEXT("game %d (deck %s, seed %d, turn %d): %s"),
					Iteration, *PlayerDeckId, Seed, Duel.GetTurnNumber(), *SelfTestJoinErrors(Errors)));
			}
		}
	}

	for (const FString& Detail : FailureDetails)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DuelSelfTest] %s"), *Detail);
	}
	if (GamesWithErrors > FailureDetails.Num())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DuelSelfTest] %d additional failing game(s) not shown."),
			GamesWithErrors - FailureDetails.Num());
	}

	const double ElapsedSeconds = FPlatformTime::Seconds() - StartSeconds;
	const bool bEnginePass = Stalls == 0 && GamesWithErrors == 0;
	return FString::Printf(
		TEXT("Duel self-test: %d iterations, %d player wins, %d opponent wins, %d draws, %d stalls, average turns %.1f, ")
		TEXT("invariant failures %d, gate deck failures %d, deck audit %d/%d, puzzle audit %d/%d, elapsed %.1fs, RESULT %s"),
		RequestedIterations, PlayerWins, OpponentWins, Draws, Stalls,
		RequestedIterations > 0 ? static_cast<float>(TotalTurns) / RequestedIterations : 0.0f,
		GamesWithErrors, DeckGameFailures, ConstructedPass, ConstructedTotal, PuzzlePass, PuzzleTotal, ElapsedSeconds,
		bEnginePass ? TEXT("PASS") : TEXT("FAIL"));
}

// ---------------------------------------------------------------------------
// Interactive smoke: response windows and player prompts through the public
// player API, every question answered at random.
// ---------------------------------------------------------------------------

FString FDuelEngine::RunInteractiveSelfTest(UCardDatabaseSubsystem* Database, int32 Games)
{
	if (!Database)
	{
		return TEXT("Interactive duel self-test: missing card database, RESULT FAIL");
	}
	const int32 RequestedGames = FMath::Clamp(Games, 1, 10000);
	const TCHAR* Starters[3] = { TEXT("fire"), TEXT("water"), TEXT("wind") };
	int32 Stalls = 0;
	int32 InvariantFailures = 0;
	int32 Windows = 0;
	int32 Prompts = 0;
	int32 Finished = 0;

	for (int32 Game = 0; Game < RequestedGames; ++Game)
	{
		FDuelEngine Duel(Database, 9000 + Game * 13);
		FRandomStream Rng(777 + Game);
		Duel.Start(Starters[Game % 3], TEXT("jaden"));
		const int32 PlayerCards = SelfTestCountOwnedCards(Duel.Player, Duel.Opponent, EDuelOwner::Player);
		const int32 OpponentCards = SelfTestCountOwnedCards(Duel.Player, Duel.Opponent, EDuelOwner::Opponent);
		bool bGameFailed = false;

		auto AnswerAll = [&]()
		{
			int32 Guard = 0;
			while (Duel.HasPendingChoice() && Guard++ < 64)
			{
				const FDuelChoiceRequest Request = *Duel.GetPendingChoice();
				if (Request.Side != EDuelOwner::Player)
				{
					Duel.AutoAnswerPendingChoice();
					continue;
				}
				++Prompts;
				if (Request.Type == EDuelChoiceType::ChainResponse)
				{
					++Windows;
				}
				FString ChoiceError;
				if (Request.bCancellable && Rng.FRand() < 0.15f)
				{
					Duel.CancelChoice(Request.RequestId, ChoiceError);
					continue;
				}
				TArray<int32> Enabled;
				for (const FDuelChoiceOption& Option : Request.Options)
				{
					if (Option.bEnabled)
					{
						Enabled.Add(Option.Id);
					}
				}
				const int32 Extra = Request.MaxSelections > Request.MinSelections
					? Rng.RandRange(0, Request.MaxSelections - Request.MinSelections) : 0;
				TArray<int32> Pick;
				while (Pick.Num() < Request.MinSelections + Extra && Enabled.Num() > 0)
				{
					const int32 Index = Rng.RandRange(0, Enabled.Num() - 1);
					Pick.Add(Enabled[Index]);
					Enabled.RemoveAt(Index);
				}
				if (!Duel.AnswerChoice(Request.RequestId, Pick, ChoiceError))
				{
					Duel.AutoAnswerPendingChoice();
				}
			}
		};
		auto CheckState = [&]()
		{
			TArray<FString> Errors;
			Duel.CheckDuelStateInvariants(PlayerCards, OpponentCards, Errors);
			if (Errors.Num() > 0 && !bGameFailed)
			{
				bGameFailed = true;
				++InvariantFailures;
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Interactive self-test game %d turn %d: %s"),
					Game, Duel.GetTurnNumber(), *Errors[0]);
			}
		};

		int32 Steps = 0;
		while (!Duel.IsOver() && Steps++ < 400 && Duel.GetTurnNumber() < 120)
		{
			if (!Duel.IsPlayerTurn() || Duel.IsAwaitingAi())
			{
				int32 Guard = 0;
				while (!Duel.IsOver() && (Duel.IsAwaitingAi() || Duel.HasPendingChoice()) && Guard++ < 200)
				{
					Duel.RunOpponentTurn();
					AnswerAll();
					CheckState();
				}
				if (!Duel.IsOver() && !Duel.IsPlayerTurn())
				{
					++Stalls;
					UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Interactive self-test game %d: the opponent's turn did not hand back (turn %d)."),
						Game, Duel.GetTurnNumber());
					break;
				}
				continue;
			}

			// Main Phase: a handful of random legal actions.
			for (int32 ActionIndex = 0; ActionIndex < 12 && !Duel.IsOver(); ++ActionIndex)
			{
				AnswerAll();
				struct FCandidate
				{
					EDuelAction Action = EDuelAction::None;
					int32 Uid = 0;
					int32 Tributes = 0;
					bool bSetCard = false;
				};
				TArray<FCandidate> Candidates;
				for (const FDuelCard& Card : Duel.Player.Hand)
				{
					for (const FDuelActionInfo& Info : Duel.GetHandActions(Card.Uid))
					{
						Candidates.Add({ Info.Action, Card.Uid, Info.TributeCount, false });
					}
				}
				for (const FDuelCard& Card : Duel.Player.Spells)
				{
					if (Card.IsValid() && Duel.GetSpellTrapActions(Card.Uid).Num() > 0)
					{
						Candidates.Add({ EDuelAction::ActivateTrap, Card.Uid, 0, true });
					}
				}
				for (const FDuelCard& Card : Duel.Player.Monsters)
				{
					if (!Card.IsValid())
					{
						continue;
					}
					for (const FDuelActionInfo& Info : Duel.GetMonsterActions(Card.Uid))
					{
						if (Info.Action != EDuelAction::None)
						{
							Candidates.Add({ Info.Action, Card.Uid, 0, false });
						}
					}
				}
				if (Candidates.Num() == 0 || Rng.FRand() < 0.15f)
				{
					break;
				}
				const FCandidate Chosen = Candidates[Rng.RandRange(0, Candidates.Num() - 1)];
				TArray<int32> TributeUids;
				for (const FDuelCard& Card : Duel.Player.Monsters)
				{
					if (Card.IsValid() && TributeUids.Num() < Chosen.Tributes)
					{
						TributeUids.Add(Card.Uid);
					}
				}
				FString ActionError;
				switch (Chosen.Action)
				{
				case EDuelAction::NormalSummon:
				case EDuelAction::TributeSummon: Duel.NormalSummon(Chosen.Uid, TributeUids, false, ActionError); break;
				case EDuelAction::SetMonster: Duel.NormalSummon(Chosen.Uid, TributeUids, true, ActionError); break;
				case EDuelAction::SpecialSummon: Duel.SpecialSummon(Chosen.Uid, ActionError); break;
				case EDuelAction::ActivateSpell: Duel.ActivateSpell(Chosen.Uid, ActionError); break;
				case EDuelAction::SetSpellTrap: Duel.SetSpellTrap(Chosen.Uid, ActionError); break;
				case EDuelAction::FlipSummon: Duel.FlipSummon(Chosen.Uid, ActionError); break;
				case EDuelAction::ChangePosition: Duel.ChangePosition(Chosen.Uid, ActionError); break;
				case EDuelAction::ActivateEffect: Duel.ActivateMonsterEffect(Chosen.Uid, ActionError); break;
				case EDuelAction::ActivateTrap: Duel.ActivateSetTrap(Chosen.Uid, ActionError); break;
				default: break;
				}
				AnswerAll();
				CheckState();
			}
			if (Duel.IsOver())
			{
				break;
			}

			// Battle Phase: random attacks, with the odd Set card used mid-battle.
			if (Duel.GetPhase() == EDuelPhase::Main1 && Rng.FRand() < 0.85f)
			{
				Duel.EnterBattlePhase();
				AnswerAll();
				for (int32 AttackIndex = 0; AttackIndex < 8 && !Duel.IsOver(); ++AttackIndex)
				{
					TArray<int32> Attackers;
					for (const FDuelCard& Card : Duel.Player.Monsters)
					{
						if (Card.IsValid() && Duel.GetAttackTargets(Card.Uid).Num() > 0)
						{
							Attackers.Add(Card.Uid);
						}
					}
					if (Attackers.Num() == 0)
					{
						break;
					}
					const int32 AttackerUid = Attackers[Rng.RandRange(0, Attackers.Num() - 1)];
					const TArray<FDuelAttackTarget> Targets = Duel.GetAttackTargets(AttackerUid);
					const FDuelAttackTarget Target = Targets[Rng.RandRange(0, Targets.Num() - 1)];
					FString AttackError;
					Duel.Attack(AttackerUid, Target.bDirect ? 0 : Target.Uid, AttackError);
					AnswerAll();
					CheckState();
					for (const FDuelCard& Card : Duel.Player.Spells)
					{
						if (Card.IsValid() && Duel.GetSpellTrapActions(Card.Uid).Num() > 0 && Rng.FRand() < 0.3f)
						{
							const int32 SetUid = Card.Uid;
							Duel.ActivateSetTrap(SetUid, AttackError);
							AnswerAll();
							CheckState();
							break;
						}
					}
				}
				if (!Duel.IsOver())
				{
					Duel.EndBattlePhase();
					AnswerAll();
				}
			}
			if (Duel.IsOver())
			{
				break;
			}
			Duel.EndTurn();
			AnswerAll();
			int32 DiscardGuard = 0;
			while (Duel.IsAwaitingDiscard() && Duel.Player.Hand.Num() > 0 && DiscardGuard++ < 12)
			{
				FString DiscardError;
				Duel.DiscardFromHand(Duel.Player.Hand[0].Uid, DiscardError);
				AnswerAll();
			}
			CheckState();
		}
		if (Duel.IsOver())
		{
			++Finished;
		}
	}

	const bool bPass = Stalls == 0 && InvariantFailures == 0;
	return FString::Printf(
		TEXT("Interactive duel self-test: %d games, %d finished, %d stalls, invariant failures %d, %d prompts answered (%d response windows), RESULT %s"),
		RequestedGames, Finished, Stalls, InvariantFailures, Prompts, Windows, bPass ? TEXT("PASS") : TEXT("FAIL"));
}


namespace
{
	FAutoConsoleCommandWithWorldAndArgs GDADuelSelfTestCommand(
		TEXT("da.DuelSelfTest"),
		TEXT("Run N AI-vs-AI duels through the card engine and log the result summary. Usage: da.DuelSelfTest [iterations] (1-10000; default 24). Launch switch: -DADuelSelfTest=N"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (!World || !World->GetGameInstance())
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("da.DuelSelfTest: no game instance."));
				return;
			}
			UCardDatabaseSubsystem* Database = World->GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>();
			const int32 Iterations = Args.Num() > 0 ? FMath::Clamp(FCString::Atoi(*Args[0]), 1, 10000) : 24;
			const FString Summary = FDuelEngine::RunSelfTest(Database, Iterations);
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Summary);
		}));
}
