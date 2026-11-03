// Duel Academy Island - JSON helpers used by the economy loaders.
//
// Thin forwarding header: the implementations live in DAJson.h (module-wide).
// Kept so DAInventorySubsystem/DAShopSubsystem/DADeckLogic can keep calling
// DAEconomyJson::... unchanged.

#pragma once

#include "CoreMinimal.h"
#include "DAEconomyTypes.h"
#include "DAJson.h"

namespace DAEconomyJson
{
	using DAJson::LoadFile;
	using DAJson::ReadString;
	using DAJson::ReadInt;
	using DAJson::ReadBool;
	using DAJson::ReadIntArray;
	using DAJson::ReadStringArray;
	using DAJson::IntArrayToJson;
	using DAJson::WriteObject;

	/** Parse a rarity string, returning false for unknown values. */
	inline bool ParseRarity(const FString& Text, EDAECardRarity& OutRarity)
	{
		return DAEconomy::ParseRarity(Text, OutRarity);
	}
}
