// Duel Academy Island - ambient NPC chatter lines per dorm.
//
// (Formerly also held a 32-card fan list for a free card-shop booster; the
// shop counter now opens the A06 shop, and the real 1,200-card trunk, pack
// catalogue and deck rules live in UDAInventorySubsystem / UDAShopSubsystem /
// UDADeckLogic and Content/Data.)

#pragma once

#include "CoreMinimal.h"
#include "DATypes.h"

namespace DuelAcademy
{
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
