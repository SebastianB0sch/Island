// Duel Academy Island - legacy 32-card fan list + NPC lines.
//
// This list is retained only as the fallback for the existing DAInteractable
// card-shop prop. The real 1,200-card trunk, 48-pack catalogue and deck rules
// live in UDAInventorySubsystem / UDAShopSubsystem / UDADeckLogic and
// Content/Data/Shop + Content/Data/Rules. Do not add canon cards here.

#pragma once

#include "CoreMinimal.h"
#include "DATypes.h"

namespace DuelAcademy
{
	enum class ERarity : uint8 { Common, Rare, SuperRare, UltraRare };

	struct FCardDef
	{
		const TCHAR* Name;
		const TCHAR* Type;
		int32 Atk;
		int32 Def;
		ERarity Rarity;
	};

	inline const TArray<FCardDef>& Cards()
	{
		static const TArray<FCardDef> List = {
			{ TEXT("Volcanic Wyrmling"),        TEXT("Pyro / Effect"),        1400, 1000, ERarity::Common },
			{ TEXT("Harbor Sentinel"),          TEXT("Machine / Normal"),     1500, 1800, ERarity::Common },
			{ TEXT("Cliffside Gull"),           TEXT("Winged Beast / Normal"), 1100,  700, ERarity::Common },
			{ TEXT("Lakeside Undine"),          TEXT("Aqua / Effect"),        1200, 1600, ERarity::Common },
			{ TEXT("Forest Shrine Wisp"),       TEXT("Fairy / Tuner"),         800,  800, ERarity::Common },
			{ TEXT("Curry Bread Golem"),        TEXT("Rock / Normal"),        1300, 2000, ERarity::Common },
			{ TEXT("Freshman Swordsman"),       TEXT("Warrior / Normal"),     1600, 1000, ERarity::Common },
			{ TEXT("Ferry Captain Gale"),       TEXT("Warrior / Effect"),     1700, 1200, ERarity::Common },
			{ TEXT("Practice Dummy Mk.II"),     TEXT("Machine / Effect"),        0, 2400, ERarity::Common },
			{ TEXT("Hot Spring Kappa"),         TEXT("Aqua / Effect"),        1000, 1900, ERarity::Common },
			{ TEXT("Lighthouse Keeper"),        TEXT("Spellcaster / Effect"), 1200, 1300, ERarity::Common },
			{ TEXT("Sunset Point Phoenix"),     TEXT("Pyro / Effect"),        1800, 1100, ERarity::Rare },
			{ TEXT("Academy Archivist"),        TEXT("Spellcaster / Effect"), 1500, 1700, ERarity::Rare },
			{ TEXT("Crimson Dorm Drake"),       TEXT("Dragon / Effect"),      1900, 1400, ERarity::Rare },
			{ TEXT("Golden Equation Sage"),     TEXT("Spellcaster / Effect"), 1750, 1750, ERarity::Rare },
			{ TEXT("Azure Palace Knight"),      TEXT("Warrior / Effect"),     2000, 1500, ERarity::Rare },
			{ TEXT("Abandoned Dorm Phantom"),   TEXT("Fiend / Effect"),       1900,  600, ERarity::Rare },
			{ TEXT("Magma Core Titan"),         TEXT("Pyro / Effect"),        2300, 1800, ERarity::SuperRare },
			{ TEXT("Spirit of the Falls"),      TEXT("Aqua / Fusion"),        2400, 2100, ERarity::SuperRare },
			{ TEXT("Holo-Field Commander"),     TEXT("Machine / Effect"),     2200, 2200, ERarity::SuperRare },
			{ TEXT("Kaiser of the Breakwater"), TEXT("Machine / Fusion"),     2800, 2100, ERarity::SuperRare },
			{ TEXT("Obelisk Blue Monarch"),     TEXT("Warrior / Ritual"),     2700, 2300, ERarity::SuperRare },
			{ TEXT("Duel Academy Guardian"),    TEXT("Divine-Beast / Effect"), 3000, 2500, ERarity::UltraRare },
			{ TEXT("Crimson Sky Serpent"),      TEXT("Dragon / Fusion"),      3000, 2400, ERarity::UltraRare },
			{ TEXT("Golden Sun Avatar"),        TEXT("Pyro / Fusion"),        2900, 2600, ERarity::UltraRare },
			{ TEXT("Azure Colossus"),           TEXT("Warrior / Fusion"),     3100, 2900, ERarity::UltraRare },
			{ TEXT("Pot of Fortune"),           TEXT("Spell / Normal"),          0,    0, ERarity::Common },
			{ TEXT("Island Ferry Ticket"),      TEXT("Spell / Quick-Play"),      0,    0, ERarity::Common },
			{ TEXT("Volcanic Eruption"),        TEXT("Spell / Field"),           0,    0, ERarity::Rare },
			{ TEXT("Lighthouse Beacon"),        TEXT("Trap / Continuous"),       0,    0, ERarity::Rare },
			{ TEXT("Mirror of the Lake"),       TEXT("Trap / Normal"),           0,    0, ERarity::Common },
			{ TEXT("Fusion Classroom"),         TEXT("Spell / Normal"),          0,    0, ERarity::SuperRare },
		};
		return List;
	}

	inline const TCHAR* RarityName(ERarity R)
	{
		switch (R)
		{
		case ERarity::Rare:      return TEXT("Rare");
		case ERarity::SuperRare: return TEXT("Super Rare");
		case ERarity::UltraRare: return TEXT("ULTRA RARE");
		case ERarity::Common:
		default:                 return TEXT("Common");
		}
	}

	/** Weighted pull: 70% common, 20% rare, 8% super, 2% ultra. */
	inline int32 PullCardIndex(FRandomStream& Rng)
	{
		const float Roll = Rng.FRand();
		const ERarity Wanted = Roll < 0.02f ? ERarity::UltraRare : Roll < 0.10f ? ERarity::SuperRare : Roll < 0.30f ? ERarity::Rare : ERarity::Common;
		TArray<int32> Pool;
		const TArray<FCardDef>& All = Cards();
		for (int32 i = 0; i < All.Num(); ++i)
		{
			if (All[i].Rarity == Wanted)
			{
				Pool.Add(i);
			}
		}
		return Pool.Num() > 0 ? Pool[Rng.RandRange(0, Pool.Num() - 1)] : 0;
	}

	inline const TArray<FString>& NpcLines(EDADorm Dorm)
	{
		static const TArray<FString> Slifer = {
			TEXT("Curry again tonight! ...At least it's spicy curry."),
			TEXT("I overslept and missed the entrance quiz. Again."),
			TEXT("Our dorm creaks when the wind blows, but the sunsets make up for it."),
			TEXT("Lower rank? Sure. Lower spirit? Never!"),
			TEXT("Dr. Crowler gave us a pop quiz on Fusion Summoning. I fused my sandwich instead."),
			TEXT("Down by the cliff you can fish all afternoon. Nobody comes looking for Slifers."),
		};
		static const TArray<FString> Ra = {
			TEXT("By my calculations there's a 73.2% chance you're about to ask for directions."),
			TEXT("The cafeteria here is honestly the best on the island. Don't tell Obelisk."),
			TEXT("I'm studying for the promotion exam. Obelisk Blue, here I come!"),
			TEXT("Ra Yellow - the sensible choice. Comfortable beds and good grades."),
			TEXT("Have you seen the equations on the dorm walls? Someone ran out of paper."),
		};
		static const TArray<FString> Obelisk = {
			TEXT("Hmph. Don't stand so close - you'll wrinkle the blazer."),
			TEXT("Our dorm has a five-star chef. What do you eat, instant noodles?"),
			TEXT("The Grand Duel Arena is basically our second home."),
			TEXT("Elite duelists don't 'hang out'. We network."),
			TEXT("Boys aren't allowed near the girls' dorm lake. Trust me, she WILL find out."),
		};
		static const TArray<FString> White = {
			TEXT("Have you seen the light? Everything is so much clearer in white."),
			TEXT("Join the Society of Light. It's... very bright."),
		};
		switch (Dorm)
		{
		case EDADorm::Ra: return Ra;
		case EDADorm::Obelisk: return Obelisk;
		case EDADorm::White: return White;
		case EDADorm::Slifer:
		default: return Slifer;
		}
	}
}
