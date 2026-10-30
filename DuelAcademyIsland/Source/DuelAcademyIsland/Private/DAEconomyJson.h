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
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Default;
	}

	inline int32 ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid() && Object->TryGetNumberField(Field, Value))
		{
			return Value;
		}
		return Default;
	}

	inline bool ReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bDefault = false)
	{
		bool bValue = bDefault;
		if (Object.IsValid() && Object->TryGetBoolField(Field, bValue))
		{
			return bValue;
		}
		return bDefault;
	}

	inline TArray<int32> ReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<int32> Values;
		const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Array) && Array)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Array)
			{
				if (Value.IsValid())
				{
					Values.Add(static_cast<int32>(Value->AsNumber()));
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
				if (Value.IsValid())
				{
					Values.Add(Value->AsString());
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
