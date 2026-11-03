// Duel Academy Island - module-wide JSON helpers.
//
// One implementation of the small "read a field with a default" helpers that
// every data-driven subsystem needs. Keep behaviour identical to the copies
// these replaced; where two callers needed different semantics there are two
// explicitly named functions (for example ReadStringArray vs
// ReadStringArrayStrict, ReadFloat vs ReadFiniteDouble).

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace DAJson
{
	// ------------------------------------------------------------------ files

	/** Content/Data/<Relative> under the project content directory. */
	inline FString ContentDataPath(const FString& Relative)
	{
		return FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data"), Relative);
	}

	/** Reads and parses a JSON file whose root may be any JSON value. */
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

	/** Reads and parses a JSON file whose root must be an object. */
	inline bool LoadObjectFile(const FString& Path, TSharedPtr<FJsonObject>& OutObject, FString& OutError)
	{
		OutObject.Reset();
		TSharedPtr<FJsonValue> Root;
		if (!LoadFile(Path, Root, OutError))
		{
			return false;
		}
		OutObject = Root->AsObject();
		if (!OutObject.IsValid())
		{
			OutError = FString::Printf(TEXT("JSON root is not an object: %s"), *Path);
			return false;
		}
		return true;
	}

	/** Parses an in-memory JSON object. Empty text is rejected. */
	inline bool ParseObject(const FString& Json, TSharedPtr<FJsonObject>& OutObject)
	{
		OutObject.Reset();
		if (Json.IsEmpty())
		{
			return false;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		return FJsonSerializer::Deserialize(Reader, OutObject) && OutObject.IsValid();
	}

	/** Condensed (non-canonical) serialization. */
	inline FString WriteObject(const TSharedPtr<FJsonObject>& Object)
	{
		FString Out;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
		FJsonSerializer::Serialize(Object.ToSharedRef(), Writer);
		return Out;
	}

	/** FJsonObject::Values key -> FString, whatever FStringType is in this engine version. */
	inline FString KeyToString(const FJsonObject::FStringType& Key)
	{
		return FString(*Key);
	}

	// ------------------------------------------------------------------ scalars

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

	/** Number as float; no finiteness check (story command durations). */
	inline float ReadFloat(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, float Default = 0.f)
	{
		double Value = Default;
		if (Object.IsValid() && Object->TryGetNumberField(Field, Value))
		{
			return static_cast<float>(Value);
		}
		return Default;
	}

	/** Number, or Default when missing or not finite. */
	inline double ReadFiniteDouble(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, double Default)
	{
		double Value = Default;
		if (Object.IsValid() && Object->TryGetNumberField(Field, Value) && FMath::IsFinite(Value))
		{
			return Value;
		}
		return Default;
	}

	/** Finite number clamped to [Min, Max], or Default when missing/not finite. */
	inline double ReadClampedDouble(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, double Default, double Min, double Max)
	{
		double Value = Default;
		if (Object.IsValid() && Object->TryGetNumberField(Field, Value) && FMath::IsFinite(Value))
		{
			return FMath::Clamp(Value, Min, Max);
		}
		return Default;
	}

	/** Finite number clamped to [Min, Max] before the int conversion, or Default. */
	inline int32 ReadClampedInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default, int32 Min, int32 Max)
	{
		double Value = Default;
		if (Object.IsValid() && Object->TryGetNumberField(Field, Value) && FMath::IsFinite(Value))
		{
			return static_cast<int32>(FMath::Clamp(Value, static_cast<double>(Min), static_cast<double>(Max)));
		}
		return Default;
	}

	// ------------------------------------------------------------------ containers

	/** Object field, or null. */
	inline TSharedPtr<FJsonObject> ReadObject(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		const TSharedPtr<FJsonObject>* Found = nullptr;
		if (Object.IsValid() && Object->TryGetObjectField(Field, Found) && Found && Found->IsValid())
		{
			return *Found;
		}
		return nullptr;
	}

	/** Array field, or null. */
	inline const TArray<TSharedPtr<FJsonValue>>* ReadArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Array) && Array)
		{
			return Array;
		}
		return nullptr;
	}

	/** Object entries of an array field; non-object entries are skipped. */
	inline TArray<TSharedPtr<FJsonObject>> ReadObjectArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<TSharedPtr<FJsonObject>> Result;
		if (const TArray<TSharedPtr<FJsonValue>>* Values = ReadArray(Object, Field))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid() && Value->AsObject().IsValid())
				{
					Result.Add(Value->AsObject());
				}
			}
		}
		return Result;
	}

	/** Appends every valid entry as a number truncated to int32. */
	inline void AppendIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<int32>& Out)
	{
		if (const TArray<TSharedPtr<FJsonValue>>* Values = ReadArray(Object, Field))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid())
				{
					Out.Add(static_cast<int32>(Value->AsNumber()));
				}
			}
		}
	}

	inline TArray<int32> ReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<int32> Values;
		AppendIntArray(Object, Field, Values);
		return Values;
	}

	/** Appends every valid entry through AsString (numbers are converted). */
	inline void AppendStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<FString>& Out)
	{
		if (const TArray<TSharedPtr<FJsonValue>>* Values = ReadArray(Object, Field))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid())
				{
					Out.Add(Value->AsString());
				}
			}
		}
	}

	inline TArray<FString> ReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<FString> Values;
		AppendStringArray(Object, Field, Values);
		return Values;
	}

	/** Like ReadStringArray, but keeps only genuine JSON strings (save data). */
	inline TArray<FString> ReadStringArrayStrict(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<FString> Values;
		if (const TArray<TSharedPtr<FJsonValue>>* Array = ReadArray(Object, Field))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Array)
			{
				if (Value.IsValid() && Value->Type == EJson::String)
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
}
