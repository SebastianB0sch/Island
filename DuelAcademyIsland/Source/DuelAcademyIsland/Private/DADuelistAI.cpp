// Duel Academy Island - deterministic duelist AI policy.

#include "DADuelistAI.h"

#include "DACardRecords.h"

FDAIDuelistAI::FDAIDuelistAI()
{
	Random.Initialize(0);
}

void FDAIDuelistAI::Configure(const FDAIProfileDef& InProfile, int32 InSeed)
{
	Profile = InProfile;
	Strategy = StrategyFromString(Profile.Strategy);
	Random.Initialize(InSeed);
	bConfigured = true;
}

EDAAIStrategy FDAIDuelistAI::StrategyFromString(const FString& StrategyId)
{
	const FString Id = StrategyId.ToLower();
	if (Id == TEXT("beatdown")) return EDAAIStrategy::Beatdown;
	if (Id == TEXT("burn")) return EDAAIStrategy::Burn;
	if (Id == TEXT("stall")) return EDAAIStrategy::Stall;
	if (Id == TEXT("fusion")) return EDAAIStrategy::Fusion;
	if (Id == TEXT("ritual")) return EDAAIStrategy::Ritual;
	if (Id == TEXT("control")) return EDAAIStrategy::Control;
	if (Id == TEXT("draw")) return EDAAIStrategy::Draw;
	if (Id == TEXT("goblin")) return EDAAIStrategy::Goblin;
	if (Id == TEXT("machine")) return EDAAIStrategy::Machine;
	if (Id == TEXT("fairy")) return EDAAIStrategy::Fairy;
	if (Id == TEXT("dragon")) return EDAAIStrategy::Dragon;
	if (Id == TEXT("warrior")) return EDAAIStrategy::Warrior;
	if (Id == TEXT("beast")) return EDAAIStrategy::Beast;
	if (Id == TEXT("insect")) return EDAAIStrategy::Insect;
	if (Id == TEXT("rock")) return EDAAIStrategy::Rock;
	if (Id == TEXT("spellcaster")) return EDAAIStrategy::Spellcaster;
	if (Id == TEXT("aquatic")) return EDAAIStrategy::Aquatic;
	if (Id == TEXT("cyber")) return EDAAIStrategy::Cyber;
	if (Id == TEXT("ojama")) return EDAAIStrategy::Ojama;
	if (Id == TEXT("ancient_gear")) return EDAAIStrategy::AncientGear;
	if (Id == TEXT("amazoness")) return EDAAIStrategy::Amazoness;
	if (Id == TEXT("copycat")) return EDAAIStrategy::Copycat;
	if (Id == TEXT("toon")) return EDAAIStrategy::Toon;
	if (Id == TEXT("dinosaur")) return EDAAIStrategy::Dinosaur;
	if (Id == TEXT("shadow")) return EDAAIStrategy::Shadow;
	if (Id == TEXT("exodia")) return EDAAIStrategy::Exodia;
	if (Id == TEXT("exam_stall")) return EDAAIStrategy::ExamStall;
	return EDAAIStrategy::Unknown;
}

float FDAIDuelistAI::GetWeight(const FString& Key, float Default) const
{
	if (const float* Value = Profile.Weights.Find(Key))
	{
		return *Value;
	}
	return Default;
}

int32 FDAIDuelistAI::GetThreshold(const FString& Key, int32 Default) const
{
	if (const float* Value = Profile.Thresholds.Find(Key))
	{
		return FMath::RoundToInt(*Value);
	}
	return Default;
}

int32 FDAIDuelistAI::StrategyBonus(const FCardRecord& Card) const
{
	const FString& Name = Card.Name;
	const bool bMonster = Card.IsMonster();
	const bool bFusion = Card.CardType.Contains(TEXT("Fusion"));
	const bool bRitual = Card.CardType.Contains(TEXT("Ritual"));

	switch (Strategy)
	{
	case EDAAIStrategy::Beatdown:
		return bMonster ? FMath::Max(0, Card.Atk - 1500) / 100 : 0;
	case EDAAIStrategy::Burn:
		if (Name.Contains(TEXT("Sparks")) || Name.Contains(TEXT("Meteor of Destruction")) || Name.Contains(TEXT("Kurenai"))
			|| Name.Contains(TEXT("Nightmare")) || Name.Contains(TEXT("Secret Barrel")) || Name.Contains(TEXT("Cannon Soldier")))
		{
			return 30;
		}
		return 0;
	case EDAAIStrategy::Stall:
		if (Card.IsTrap() || Name.Contains(TEXT("Messenger")) || Name.Contains(TEXT("Gravity Bind"))
			|| Name.Contains(TEXT("Swords of Revealing")) || Name.Contains(TEXT("Solemn Wishes")) || Name.Contains(TEXT("Fairy Box")))
		{
			return 30;
		}
		return 0;
	case EDAAIStrategy::Fusion:
		if (bFusion) return 25;
		if (Name.Contains(TEXT("Polymerization")) || Name.Contains(TEXT("Miracle Fusion")) || Name.Contains(TEXT("Dragon's Mirror"))) return 30;
		return 0;
	case EDAAIStrategy::Ritual:
		if (bRitual) return 30;
		if (Name.Contains(TEXT("Ritual")) || Name.Contains(TEXT("Relinquished")) || Name.Contains(TEXT("Senju"))) return 25;
		return 0;
	case EDAAIStrategy::Control:
		return Card.IsTrap() ? 18 : (Name.Contains(TEXT("Fissure")) || Name.Contains(TEXT("Tribute")) ? 18 : 0);
	case EDAAIStrategy::Draw:
		if (Name.Contains(TEXT("Pot of Greed")) || Name.Contains(TEXT("Graceful Charity")) || Name.Contains(TEXT("Upstart Goblin"))
			|| Name.Contains(TEXT("Card Destruction")) || Name.Contains(TEXT("Sangan")) || Name.Contains(TEXT("Witch of the Black Forest")))
		{
			return 30;
		}
		return 0;
	case EDAAIStrategy::Goblin:
		return Name.Contains(TEXT("Goblin")) ? 30 : 0;
	case EDAAIStrategy::Machine:
		return bMonster && Card.MonsterType == TEXT("Machine") ? 20 : 0;
	case EDAAIStrategy::Fairy:
		return bMonster && Card.MonsterType == TEXT("Fairy") ? 20 : 0;
	case EDAAIStrategy::Dragon:
		return bMonster && Card.MonsterType == TEXT("Dragon") ? 20 : 0;
	case EDAAIStrategy::Warrior:
		return bMonster && Card.MonsterType == TEXT("Warrior") ? 20 : 0;
	case EDAAIStrategy::Beast:
		return bMonster && Card.MonsterType == TEXT("Beast") ? 20 : 0;
	case EDAAIStrategy::Insect:
		return bMonster && Card.MonsterType == TEXT("Insect") ? 20 : 0;
	case EDAAIStrategy::Rock:
		return bMonster && Card.MonsterType == TEXT("Rock") ? 20 : 0;
	case EDAAIStrategy::Spellcaster:
		return bMonster && Card.MonsterType == TEXT("Spellcaster") ? 20 : 0;
	case EDAAIStrategy::Aquatic:
		if (bMonster && (Card.MonsterType == TEXT("Aqua") || Card.MonsterType == TEXT("Fish") || Card.MonsterType == TEXT("Sea Serpent"))) return 20;
		if (Name.Contains(TEXT("Umi")) || Name.Contains(TEXT("Legendary Ocean"))) return 25;
		return 0;
	case EDAAIStrategy::Cyber:
		return Name.Contains(TEXT("Cyber")) ? 28 : 0;
	case EDAAIStrategy::Ojama:
		return Name.Contains(TEXT("Ojama")) ? 30 : 0;
	case EDAAIStrategy::AncientGear:
		return Name.Contains(TEXT("Ancient Gear")) ? 30 : 0;
	case EDAAIStrategy::Amazoness:
		return Name.Contains(TEXT("Amazoness")) ? 30 : 0;
	case EDAAIStrategy::Copycat:
		if (Name == TEXT("Dark Magician") || Name == TEXT("Blue-Eyes White Dragon") || Name == TEXT("Red-Eyes B. Dragon")
			|| Name == TEXT("Monster Reborn") || Name == TEXT("Snatch Steal"))
		{
			return 20;
		}
		return 0;
	case EDAAIStrategy::Toon:
		return Name.Contains(TEXT("Toon")) ? 25 : 0;
	case EDAAIStrategy::Dinosaur:
		return bMonster && Card.MonsterType == TEXT("Dinosaur") ? 25 : 0;
	case EDAAIStrategy::Shadow:
		return bMonster && Card.MonsterType == TEXT("Fiend") ? 22 : 0;
	case EDAAIStrategy::Exodia:
		return Name.Contains(TEXT("Forbidden One")) || Name == TEXT("Exodia the Forbidden One") ? 35 : 0;
	case EDAAIStrategy::ExamStall:
		if (Card.IsTrap() || Name.Contains(TEXT("Messenger")) || Name.Contains(TEXT("Gravity Bind")) || Name.Contains(TEXT("Swords of Revealing"))) return 35;
		return 0;
	case EDAAIStrategy::Unknown:
	default:
		return 0;
	}
}

int32 FDAIDuelistAI::ScoreCard(const FCardRecord& Card) const
{
	if (!bConfigured)
	{
		return 0;
	}

	int32 Score = 0;
	if (Card.IsMonster())
	{
		Score = Card.Atk / 100 + Card.Def / 200 + Card.Level * 3;
		if (!Card.CardType.Equals(TEXT("Normal Monster"))) Score += 8;
		if (Card.CardType.Contains(TEXT("Fusion"))) Score += 12;
		if (Card.CardType.Contains(TEXT("Ritual"))) Score += 10;
	}
	else
	{
		Score = 8 + FMath::RoundToInt(GetWeight(Card.IsTrap() ? TEXT("set_trap") : TEXT("removal"), 0.5f) * 8.f);
	}

	if (Profile.PreferredCardNames.Contains(Card.Name))
	{
		Score += 25;
	}
	if (Profile.AvoidCardNames.Contains(Card.Name))
	{
		Score -= 20;
	}
	Score += StrategyBonus(Card);

	if (Card.IsMonster())
	{
		Score += FMath::RoundToInt(GetWeight(TEXT("attack"), 0.8f) * 8.f);
		if (Card.Atk >= 2400)
		{
			Score += FMath::RoundToInt(GetWeight(TEXT("big_monster"), 0.6f) * 10.f);
		}
	}
	else if (Card.IsTrap())
	{
		Score += FMath::RoundToInt(GetWeight(TEXT("set_trap"), 0.7f) * 8.f);
	}
	return Score;
}

int32 FDAIDuelistAI::ScoreCardId(int32 CardId) const
{
	if (!Database)
	{
		return 0;
	}
	if (const FCardRecord* Card = Database->FindCard(CardId))
	{
		return ScoreCard(*Card);
	}
	return 0;
}

FDAAIDecision FDAIDuelistAI::ChooseAction(const FDAAIDuelSnapshot& Snapshot) const
{
	FDAAIDecision Decision;
	if (!bConfigured)
	{
		return Decision;
	}

	if (Snapshot.bBattlePhase)
	{
		if (Snapshot.OwnMonsterIds.Num() == 0)
		{
			Decision.Action = EDAAIAction::EndTurn;
			Decision.Reason = TEXT("No attackers.");
			return Decision;
		}
		if (Snapshot.bCanAttackDirectly && GetWeight(TEXT("direct_attack"), 0.8f) >= 0.25f)
		{
			Decision.Action = EDAAIAction::DirectAttack;
			Decision.CardId = Snapshot.OwnMonsterIds[0];
			Decision.Score = 1000;
			Decision.Reason = TEXT("Direct attack available.");
			return Decision;
		}
		if (Snapshot.OpponentMonsterIds.Num() > 0 && GetWeight(TEXT("attack"), 0.8f) >= 0.35f)
		{
			Decision.Action = EDAAIAction::Attack;
			Decision.CardId = Snapshot.OwnMonsterIds[0];
			Decision.TargetCardId = Snapshot.OpponentMonsterIds[0];
			Decision.Score = FMath::RoundToInt(GetWeight(TEXT("attack"), 0.8f) * 100.f);
			Decision.Reason = TEXT("Attack the opposing board.");
			return Decision;
		}
		Decision.Action = EDAAIAction::EndTurn;
		Decision.Reason = TEXT("Holding attackers back.");
		return Decision;
	}

	if (Snapshot.bNormalSummonUsed && Snapshot.HandCardIds.Num() == 0)
	{
		Decision.Action = EDAAIAction::EndTurn;
		return Decision;
	}

	int32 BestScore = TNumericLimits<int32>::Lowest();
	EDAAIAction BestAction = EDAAIAction::None;
	int32 BestCard = 0;

	for (int32 CardId : Snapshot.HandCardIds)
	{
		if (!Database)
		{
			continue;
		}
		const FCardRecord* Card = Database->FindCard(CardId);
		if (!Card)
		{
			continue;
		}
		const int32 CardScore = ScoreCard(*Card);
		if (Card->IsMonster())
		{
			if (Snapshot.bNormalSummonUsed)
			{
				continue;
			}
			const bool bSet = GetWeight(TEXT("stall"), 0.1f) >= 0.7f && Snapshot.OwnMonsterIds.Num() == 0;
			const EDAAIAction Action = bSet ? EDAAIAction::SetMonster : EDAAIAction::NormalSummon;
			const int32 ActionScore = CardScore + (bSet ? FMath::RoundToInt(GetWeight(TEXT("stall"), 0.1f) * 10.f) : FMath::RoundToInt(GetWeight(TEXT("summon"), 1.0f) * 8.f));
			if (ActionScore > BestScore)
			{
				BestScore = ActionScore;
				BestAction = Action;
				BestCard = CardId;
			}
		}
		else if (Card->IsSpell())
		{
			const int32 ActionScore = CardScore + FMath::RoundToInt(GetWeight(TEXT("removal"), 0.6f) * 6.f);
			if (ActionScore > BestScore)
			{
				BestScore = ActionScore;
				BestAction = EDAAIAction::ActivateSpell;
				BestCard = CardId;
			}
		}
		else if (Card->IsTrap())
		{
			if (!ShouldSetTrap(Snapshot))
			{
				continue;
			}
			const int32 ActionScore = CardScore + FMath::RoundToInt(GetWeight(TEXT("set_trap"), 0.7f) * 6.f);
			if (ActionScore > BestScore)
			{
				BestScore = ActionScore;
				BestAction = EDAAIAction::SetSpellTrap;
				BestCard = CardId;
			}
		}
	}

	if (BestAction == EDAAIAction::None)
	{
		Decision.Action = EDAAIAction::EndTurn;
		Decision.Reason = TEXT("No profitable main-phase action.");
		return Decision;
	}

	Decision.Action = BestAction;
	Decision.CardId = BestCard;
	Decision.Score = BestScore;
	Decision.Reason = Profile.Label;
	return Decision;
}

bool FDAIDuelistAI::ShouldAttack(const FDAAIDuelSnapshot& Snapshot, int32 AttackerCardId, int32 TargetCardId, bool bDirect) const
{
	if (!bConfigured || Snapshot.bBattlePhase == false)
	{
		return false;
	}
	if (bDirect)
	{
		return GetWeight(TEXT("direct_attack"), 0.8f) >= 0.25f;
	}
	if (TargetCardId == 0)
	{
		return false;
	}
	if (Snapshot.OpponentLp <= 0)
	{
		return false;
	}
	const int32 AttackWeight = GetThreshold(TEXT("attack_into_set_atk"), 1900);
	(void)AttackerCardId;
	(void)AttackWeight;
	return GetWeight(TEXT("attack"), 0.8f) >= 0.45f;
}

bool FDAIDuelistAI::ShouldSetTrap(const FDAAIDuelSnapshot& Snapshot) const
{
	(void)Snapshot;
	return GetWeight(TEXT("set_trap"), 0.7f) >= 0.5f;
}
