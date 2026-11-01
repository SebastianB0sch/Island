// Duel Academy Island - small JSON helpers shared by the economy loaders.

#pragma once

#include "CoreMinimal.h"
#include "DAEconomyTypes.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace DAEconomyJson
{
	inline bool LoadFile(const FString& Path, TSharedPtr<FJsonValue>& OutRoot, FString& OutError)
	{
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			OutError = FString::Printf(TEXT("File not found: %s"), *Path);
			return false;
		}

		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, OutRoot) || !OutRoot.IsValid())
		{
			OutError = FString::Printf(TEXT("JSON could not be parsed: %s"), *Path);
			return false;
		}
		return true;
	}

	inline FString ReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Default = FString())
	{
		const TSharedPtr<FJsonValue> Value = Object.IsValid() ? Object->TryGetField(Field) : nullptr;
		FString Text;
		if (!Value.IsValid() || Value->Type != EJson::String || !Value->TryGetString(Text))
		{
			return Default;
		}
		return Text;
	}

	/**
	 * Reads an integer field.  Only a real JSON number with an integral value in
	 * int32 range is accepted.  In particular JSON booleans are not numbers:
	 * UE's generic number conversion would silently turn true/false into 1/0,
	 * which previously let malformed card ids and weights through.
	 */
	inline bool TryReadInt(const TSharedPtr<FJsonValue>& Value, int32& OutValue)
	{
		if (!Value.IsValid() || Value->Type != EJson::Number)
		{
			return false;
		}
		double Number = 0.0;
		if (!Value->TryGetNumber(Number) || !FMath::IsFinite(Number)
			|| FMath::FloorToDouble(Number) != Number
			|| Number < static_cast<double>(TNumericLimits<int32>::Min())
			|| Number > static_cast<double>(TNumericLimits<int32>::Max()))
		{
			return false;
		}
		OutValue = static_cast<int32>(Number);
		return true;
	}

	/** Strict positive card-id reader; used by save-section validators. */
	inline bool TryReadCardId(const TSharedPtr<FJsonValue>& Value, int32& OutCardId)
	{
		int32 Parsed = 0;
		if (!TryReadInt(Value, Parsed) || Parsed <= 0)
		{
			return false;
		}
		OutCardId = Parsed;
		return true;
	}

	inline int32 ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		const TSharedPtr<FJsonValue> Value = Object.IsValid() ? Object->TryGetField(Field) : nullptr;
		int32 Parsed = 0;
		return TryReadInt(Value, Parsed) ? Parsed : Default;
	}

	inline bool ReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bDefault = false)
	{
		// Require a JSON boolean. UE's numeric conversion would also accept 1/0
		// here, which can hide malformed content flags.
		const TSharedPtr<FJsonValue> Value = Object.IsValid() ? Object->TryGetField(Field) : nullptr;
		bool bValue = bDefault;
		if (!Value.IsValid() || Value->Type != EJson::Boolean || !Value->TryGetBool(bValue))
		{
			return bDefault;
		}
		return bValue;
	}

	inline TArray<int32> ReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<int32> Values;
		const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Array) && Array)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Array)
			{
				// This helper is used for card-id lists.  Skip booleans,
				// strings, fractional numbers and non-positive ids instead of
				// coercing them into a bogus card id such as 0 or 1.
				int32 Parsed = 0;
				if (TryReadInt(Value, Parsed) && Parsed > 0)
				{
					Values.Add(Parsed);
				}
			}
		}
		return Values;
	}

	inline TArray<FString> ReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<FString> Values;
		const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Array) && Array)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Array)
			{
				FString Text;
				if (Value.IsValid() && Value->Type == EJson::String && Value->TryGetString(Text))
				{
					Values.Add(MoveTemp(Text));
				}
			}
		}
		return Values;
	}

	inline TArray<TSharedPtr<FJsonValue>> IntArrayToJson(const TArray<int32>& Values)
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		Out.Reserve(Values.Num());
		for (const int32 Value : Values)
		{
			Out.Add(MakeShared<FJsonValueNumber>(Value));
		}
		return Out;
	}

	inline TArray<TSharedPtr<FJsonValue>> StringArrayToJson(const TArray<FString>& Values)
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		Out.Reserve(Values.Num());
		for (const FString& Value : Values)
		{
			Out.Add(MakeShared<FJsonValueString>(Value));
		}
		return Out;
	}

	inline FString WriteObject(const TSharedPtr<FJsonObject>& Object)
	{
		FString Out;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
		FJsonSerializer::Serialize(Object.ToSharedRef(), Writer);
		return Out;
	}

	/** Parse a rarity string, returning false for unknown values. */
	inline bool ParseRarity(const FString& Text, EDAECardRarity& OutRarity)
	{
		return DAEconomy::ParseRarity(Text, OutRarity);
	}

	inline FString RarityName(EDAECardRarity Rarity)
	{
		return DAEconomy::RarityToString(Rarity);
	}

	inline const TArray<TSharedPtr<FJsonValue>>* ReadArrayField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
		if (Object.IsValid())
		{
			Object->TryGetArrayField(Field, Array);
		}
		return Array;
	}
}
