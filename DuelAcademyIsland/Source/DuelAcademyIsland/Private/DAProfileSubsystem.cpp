// Duel Academy Island - profile/progression implementation.

#include "DAProfileSubsystem.h"

#include "DACalendarSubsystem.h"
#include "DATitleSystem.h"
#include "DASaveGame.h"
#include "DuelAcademyIsland.h"

#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	const TCHAR* const DefaultTitle = TEXT("Apprentice Duelist");

	FString ProfileJsonKeyToString(const FJsonObject::FStringType& Key)
	{
		return FString(*Key);
	}

	void ReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<FString>& OutValues)
	{
		OutValues.Reset();
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Values) && Values)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid() && Value->Type == EJson::String)
				{
					OutValues.Add(Value->AsString());
				}
			}
		}
	}
}

EDADorm DuelAcademyProfile::ParseDorm(const FString& Value, EDADorm Fallback)
{
	const FString Lower = Value.TrimStartAndEnd().ToLower();
	if (Lower.Contains(TEXT("obelisk")) || Lower == TEXT("blue"))
	{
		return EDADorm::Obelisk;
	}
	if (Lower.Contains(TEXT("white")) || Lower.Contains(TEXT("society")) || Lower.Contains(TEXT("light")))
	{
		return EDADorm::White;
	}
	if (Lower.Contains(TEXT("ra")) || Lower.Contains(TEXT("yellow")))
	{
		return EDADorm::Ra;
	}
	if (Lower.Contains(TEXT("slifer")) || Lower.Contains(TEXT("red")))
	{
		return EDADorm::Slifer;
	}
	return Fallback;
}

FString DuelAcademyProfile::DormToSaveKey(EDADorm Dorm)
{
	switch (Dorm)
	{
	case EDADorm::Ra:      return TEXT("Ra");
	case EDADorm::Obelisk: return TEXT("Obelisk");
	case EDADorm::White:   return TEXT("White");
	case EDADorm::Slifer:
	default:               return TEXT("Slifer");
	}
}

FString DuelAcademyProfile::NormalizeId(const FString& Value)
{
	FString Out = Value.TrimStartAndEnd().ToLower();
	for (TCHAR& Character : Out)
	{
		if (!FChar::IsAlnum(Character))
		{
			Character = TCHAR('_');
		}
	}
	while (Out.StartsWith(TEXT("_")))
	{
		Out.RightChopInline(1);
	}
	while (Out.EndsWith(TEXT("_")))
	{
		Out.LeftChopInline(1);
	}
	return Out;
}

// ------------------------------------------------------------------------ lifecycle

void UDAProfileSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	ResetToDefaults();
	PlaytimeTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateUObject(this, &UDAProfileSubsystem::TickPlaytime));
}

void UDAProfileSubsystem::Deinitialize()
{
	if (PlaytimeTickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(PlaytimeTickerHandle);
		PlaytimeTickerHandle.Reset();
	}
	Super::Deinitialize();
}

UDAProfileSubsystem* UDAProfileSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	if (const UWorld* World = WorldContext->GetWorld())
	{
		if (UGameInstance* GameInstance = World->GetGameInstance())
		{
			return GameInstance->GetSubsystem<UDAProfileSubsystem>();
		}
	}
	return nullptr;
}

bool UDAProfileSubsystem::TickPlaytime(float DeltaSeconds)
{
	if (bInitialized && GetGameInstance() && DeltaSeconds > 0.f)
	{
		PlaytimeSeconds += static_cast<double>(DeltaSeconds);
	}
	return true;
}

// ------------------------------------------------------------------------ new game / identity

void UDAProfileSubsystem::InitializeNewGame(const FString& InName)
{
	ResetToDefaults();

	PlayerName = InName.TrimStartAndEnd();
	if (PlayerName.IsEmpty())
	{
		PlayerName = TEXT("New Student");
	}
	bInitialized = true;
	SetFlag(TEXT("new_game"), true);

	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UDACalendarSubsystem* Calendar = GameInstance->GetSubsystem<UDACalendarSubsystem>())
		{
			Calendar->ResetToDefaults();
		}
	}

	OnProfileLoaded.Broadcast();
}

void UDAProfileSubsystem::ResetToDefaults()
{
	const int32 OldDP = DP;
	const EDADorm OldDorm = Dorm;
	const FString OldTitle = Title;

	PlayerName.Reset();
	Gender = TEXT("unspecified");
	Dorm = EDADorm::Slifer;
	Title = DefaultTitle;
	DP = 3000;
	TemporaryTitle.Reset();
	TemporaryTitleDaysRemaining = 0;
	PlaytimeSeconds = 0.0;
	Flags.Reset();
	Counters.Reset();
	Emails.Reset();
	bInitialized = false;

	Counters.Add(TEXT("wins_total"), 0);
	Counters.Add(TEXT("duels_total"), 0);
	Counters.Add(TEXT("losses_total"), 0);
	Counters.Add(TEXT("draws_total"), 0);
	Counters.Add(TEXT("timed_clears"), 0);
	Counters.Add(TEXT("written_correct"), 0);
	Counters.Add(TEXT("written_total"), 0);
	Counters.Add(TEXT("cards_owned"), 0);
	Counters.Add(TEXT("story_events_cleared"), 0);

	if (OldDP != DP)
	{
		OnDPChanged.Broadcast(OldDP, DP);
	}
	if (OldDorm != Dorm)
	{
		OnDormChanged.Broadcast(OldDorm, Dorm);
	}
	if (!OldTitle.Equals(Title))
	{
		OnTitleChanged.Broadcast(OldTitle, Title);
	}
}

void UDAProfileSubsystem::SetPlayerName(const FString& InName)
{
	const FString Trimmed = InName.TrimStartAndEnd();
	if (!Trimmed.IsEmpty())
	{
		PlayerName = Trimmed;
	}
}

void UDAProfileSubsystem::SetGender(const FString& InGender)
{
	const FString Trimmed = InGender.TrimStartAndEnd();
	Gender = Trimmed.IsEmpty() ? TEXT("unspecified") : Trimmed;
}

// ------------------------------------------------------------------------ DP

int32 UDAProfileSubsystem::AwardDP(int32 Amount)
{
	if (Amount <= 0)
	{
		return 0;
	}
	const int32 OldDP = DP;
	const int64 Clamped = FMath::Clamp<int64>(static_cast<int64>(DP) + Amount, 0, TNumericLimits<int32>::Max());
	DP = static_cast<int32>(Clamped);
	OnDPChanged.Broadcast(OldDP, DP);
	return DP - OldDP;
}

bool UDAProfileSubsystem::SpendDP(int32 Amount)
{
	if (Amount < 0)
	{
		return false;
	}
	if (Amount == 0)
	{
		return true;
	}
	if (DP < Amount)
	{
		return false;
	}
	const int32 OldDP = DP;
	DP -= Amount;
	OnDPChanged.Broadcast(OldDP, DP);
	return true;
}

int32 UDAProfileSubsystem::CalculateDuelDP(const FDAProfileDuelResult& Result)
{
	if (!Result.bPlayerWon || Result.bDraw)
	{
		return 0;
	}
	if (Result.WinCondition == EDAWinCondition::Surrender)
	{
		return 0;
	}

	const int32 LpLost = FMath::Clamp(8000 - Result.PlayerLp, 0, 8000);
	const int32 BattleDamage = FMath::Max(0, Result.BattleDamageDealt);
	const int32 MonstersDestroyed = FMath::Max(0, Result.MonstersDestroyedByBattle);

	int64 Raw = 100
		+ (LpLost / 100)
		+ (BattleDamage / 100)
		+ (static_cast<int64>(MonstersDestroyed) * 50);

	switch (Result.WinCondition)
	{
	case EDAWinCondition::Exodia:
	case EDAWinCondition::DeckOut:
		Raw += 500;
		break;
	case EDAWinCondition::FinalCountdown:
		Raw += 1000;
		break;
	case EDAWinCondition::DestinyBoard:
		Raw += 3000;
		break;
	case EDAWinCondition::LifePoints:
	case EDAWinCondition::Surrender:
	case EDAWinCondition::Other:
	default:
		break;
	}

	Raw += FMath::Max(0, Result.BonusDP);

	double Multiplier = 1.0;
	if (Result.bWentSecond && Result.Turns > 0 && Result.Turns <= 2)
	{
		// Canonical "win on turn two while going second" bonus.
		Multiplier = 10.0;
	}
	else if (Result.Turns > 0 && Result.Turns < 5)
	{
		Multiplier = 5.0;
	}
	else if (Result.Turns > 0 && Result.Turns < 7)
	{
		Multiplier = 2.0;
	}
	else if (Result.Turns > 40)
	{
		Multiplier = 0.5;
	}

	const int64 Awarded = static_cast<int64>(FMath::FloorToDouble(static_cast<double>(Raw) * Multiplier));
	return static_cast<int32>(FMath::Clamp<int64>(Awarded, 0, TNumericLimits<int32>::Max()));
}

int32 UDAProfileSubsystem::RecordDuelResult(const FDAProfileDuelResult& Result)
{
	IncrementCounter(TEXT("duels_total"), 1);

	const FString OpponentKey = DuelAcademyProfile::NormalizeId(Result.OpponentId);
	int32 DpEarned = 0;

	if (Result.bDraw)
	{
		IncrementCounter(TEXT("draws_total"), 1);
	}
	else if (!Result.bPlayerWon)
	{
		IncrementCounter(TEXT("losses_total"), 1);
		if (!OpponentKey.IsEmpty())
		{
			IncrementCounter(FString::Printf(TEXT("losses_%s"), *OpponentKey), 1);
		}
	}
	else
	{
		IncrementCounter(TEXT("wins_total"), 1);
		if (!OpponentKey.IsEmpty())
		{
			IncrementCounter(FString::Printf(TEXT("wins_%s"), *OpponentKey), 1);
		}
		IncrementCounter(TEXT("battle_damage_total"), FMath::Max(0, Result.BattleDamageDealt));
		IncrementCounter(TEXT("monsters_destroyed_total"), FMath::Max(0, Result.MonstersDestroyedByBattle));
		IncrementCounter(TEXT("lp_lost_total"), FMath::Clamp(8000 - Result.PlayerLp, 0, 8000));

		const FString Mode = Result.Mode.ToLower();
		if (Mode.Contains(TEXT("timed")) || Mode.Contains(TEXT("puzzle")))
		{
			IncrementCounter(TEXT("timed_clears"), 1);
		}
		if (Mode.Equals(TEXT("story")))
		{
			IncrementCounter(TEXT("story_duels_won"), 1);
		}

		DpEarned = CalculateDuelDP(Result);
		if (DpEarned > 0)
		{
			AwardDP(DpEarned);
		}
	}

	RefreshTitleFromSystem();
	RequestProgressionAutosave(TEXT("duel_result"));
	return DpEarned;
}

// ------------------------------------------------------------------------ flags

bool UDAProfileSubsystem::GetFlag(const FString& Flag) const
{
	return Flags.FindRef(Flag);
}

void UDAProfileSubsystem::SetFlag(const FString& Flag, bool bValue)
{
	const FString Key = Flag.TrimStartAndEnd();
	if (Key.IsEmpty())
	{
		return;
	}
	const bool bOldValue = Flags.Contains(Key);
	if (bValue)
	{
		Flags.Add(Key, true);
	}
	else
	{
		Flags.Remove(Key);
	}
	if (bOldValue != bValue)
	{
		OnFlagChanged.Broadcast(Key, bValue);
	}
}

void UDAProfileSubsystem::ClearFlag(const FString& Flag)
{
	SetFlag(Flag, false);
}

// ------------------------------------------------------------------------ counters

int32 UDAProfileSubsystem::GetCounter(const FString& Counter) const
{
	return Counters.FindRef(Counter);
}

void UDAProfileSubsystem::SetCounter(const FString& Counter, int32 Value)
{
	const FString Key = Counter.TrimStartAndEnd();
	if (Key.IsEmpty())
	{
		return;
	}
	Counters.Add(Key, FMath::Max(0, Value));
}

int32 UDAProfileSubsystem::IncrementCounter(const FString& Counter, int32 Amount)
{
	const FString Key = Counter.TrimStartAndEnd();
	if (Key.IsEmpty())
	{
		return 0;
	}
	const int64 NewValue = FMath::Clamp<int64>(
		static_cast<int64>(Counters.FindRef(Key)) + Amount,
		0,
		TNumericLimits<int32>::Max());
	Counters.Add(Key, static_cast<int32>(NewValue));
	return static_cast<int32>(NewValue);
}

void UDAProfileSubsystem::ApplyCounterDelta(const FString& Counter, int32 Delta)
{
	IncrementCounter(Counter, Delta);
}

// ------------------------------------------------------------------------ dorm / title

void UDAProfileSubsystem::SetDorm(EDADorm NewDorm)
{
	if (Dorm == NewDorm)
	{
		return;
	}
	const EDADorm OldDorm = Dorm;
	Dorm = NewDorm;
	OnDormChanged.Broadcast(OldDorm, Dorm);
}

void UDAProfileSubsystem::SetTitle(const FString& NewTitle)
{
	const FString Trimmed = NewTitle.TrimStartAndEnd();
	if (Title.Equals(Trimmed))
	{
		return;
	}
	const FString OldTitle = Title;
	Title = Trimmed;
	OnTitleChanged.Broadcast(OldTitle, Title);
}

void UDAProfileSubsystem::SetTemporaryTitle(const FString& InTitle, int32 DaysRemaining)
{
	const FString Trimmed = InTitle.TrimStartAndEnd();
	if (Trimmed.IsEmpty() || DaysRemaining <= 0)
	{
		ClearTemporaryTitle();
		return;
	}
	TemporaryTitle = Trimmed;
	TemporaryTitleDaysRemaining = DaysRemaining;
	SetTitle(TemporaryTitle);
}

void UDAProfileSubsystem::ClearTemporaryTitle()
{
	const bool bWasActive = !TemporaryTitle.IsEmpty() && Title.Equals(TemporaryTitle);
	TemporaryTitle.Reset();
	TemporaryTitleDaysRemaining = 0;
	if (bWasActive)
	{
		SetTitle(DefaultTitle);
		RefreshTitleFromSystem();
	}
}

// ------------------------------------------------------------------------ email

void UDAProfileSubsystem::UnlockEmail(const FString& ContactId)
{
	const FString Key = ContactId.TrimStartAndEnd();
	if (Key.IsEmpty())
	{
		return;
	}
	FDAEmailState& State = Emails.FindOrAdd(Key);
	State.bUnlocked = true;
}

bool UDAProfileSubsystem::IsEmailUnlocked(const FString& ContactId) const
{
	const FDAEmailState* State = Emails.Find(ContactId);
	return State && State->bUnlocked;
}

void UDAProfileSubsystem::MarkEmailRead(const FString& ContactId, const FString& MessageId)
{
	const FString Key = ContactId.TrimStartAndEnd();
	const FString MessageKey = MessageId.TrimStartAndEnd();
	if (Key.IsEmpty() || MessageKey.IsEmpty())
	{
		return;
	}
	FDAEmailState& State = Emails.FindOrAdd(Key);
	State.bUnlocked = true;
	State.ReadIds.AddUnique(MessageKey);
}

bool UDAProfileSubsystem::IsEmailRead(const FString& ContactId, const FString& MessageId) const
{
	const FDAEmailState* State = Emails.Find(ContactId);
	return State && State->ReadIds.Contains(MessageId);
}

void UDAProfileSubsystem::AddDuelRequest(const FString& ContactId, const FString& RequestId)
{
	const FString Key = ContactId.TrimStartAndEnd();
	const FString RequestKey = RequestId.TrimStartAndEnd();
	if (Key.IsEmpty() || RequestKey.IsEmpty())
	{
		return;
	}
	FDAEmailState& State = Emails.FindOrAdd(Key);
	State.PendingDuelRequests.AddUnique(RequestKey);
}

bool UDAProfileSubsystem::HasPendingDuelRequest(const FString& ContactId) const
{
	const FDAEmailState* State = Emails.Find(ContactId);
	return State && State->PendingDuelRequests.Num() > 0;
}

bool UDAProfileSubsystem::ConsumeDuelRequest(const FString& ContactId, FString& OutRequestId)
{
	OutRequestId.Reset();
	FDAEmailState* State = Emails.Find(ContactId);
	if (!State || State->PendingDuelRequests.Num() == 0)
	{
		return false;
	}
	OutRequestId = State->PendingDuelRequests[0];
	State->PendingDuelRequests.RemoveAt(0);
	return true;
}

FDAEmailState UDAProfileSubsystem::GetEmailState(const FString& ContactId) const
{
	if (const FDAEmailState* State = Emails.Find(ContactId))
	{
		return *State;
	}
	return FDAEmailState();
}

// ------------------------------------------------------------------------ handles

bool UDAProfileSubsystem::SetInventoryProvider(UObject* Provider)
{
	if (!Provider)
	{
		InventoryProvider.Reset();
		return true;
	}
	if (!Provider->GetClass()->ImplementsInterface(UDAProfileInventoryInterface::StaticClass()))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Inventory provider '%s' does not implement IDAProfileInventoryInterface."), *Provider->GetName());
		return false;
	}
	InventoryProvider = Provider;
	return true;
}

int32 UDAProfileSubsystem::GetDistinctCardsOwned() const
{
	const int32 CounterValue = GetCounter(TEXT("cards_owned"));
	if (UObject* Provider = InventoryProvider.Get())
	{
		if (const IDAProfileInventoryInterface* Interface = Cast<IDAProfileInventoryInterface>(Provider))
		{
			return FMath::Max(CounterValue, Interface->GetDistinctCardsOwned());
		}
	}
	return CounterValue;
}

bool UDAProfileSubsystem::SetDeckProvider(UObject* Provider)
{
	if (!Provider)
	{
		DeckProvider.Reset();
		return true;
	}
	if (!Provider->GetClass()->ImplementsInterface(UDAProfileDeckInterface::StaticClass()))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Deck provider '%s' does not implement IDAProfileDeckInterface."), *Provider->GetName());
		return false;
	}
	DeckProvider = Provider;
	return true;
}

// ------------------------------------------------------------------------ playtime

void UDAProfileSubsystem::AddPlaytime(double Seconds)
{
	if (Seconds > 0.0)
	{
		PlaytimeSeconds += Seconds;
	}
}

FString UDAProfileSubsystem::GetPlaytimeText() const
{
	const int64 TotalSeconds = FMath::Max<int64>(0, static_cast<int64>(FMath::FloorToDouble(PlaytimeSeconds)));
	const int64 Hours = TotalSeconds / 3600;
	const int64 Minutes = (TotalSeconds % 3600) / 60;
	const int64 SecondsPart = TotalSeconds % 60;
	if (Hours > 0)
	{
		return FString::Printf(TEXT("%lld:%02lld:%02lld"), Hours, Minutes, SecondsPart);
	}
	return FString::Printf(TEXT("%02lld:%02lld"), Minutes, SecondsPart);
}

// ------------------------------------------------------------------------ calendar bridge

void UDAProfileSubsystem::NotifyDayChanged(int32 InYear, int32 InMonthIndex, int32 InDay)
{
	if (!TemporaryTitle.IsEmpty())
	{
		TemporaryTitleDaysRemaining = FMath::Max(0, TemporaryTitleDaysRemaining - 1);
		if (TemporaryTitleDaysRemaining == 0)
		{
			TemporaryTitle.Reset();
			SetTitle(DefaultTitle);
			RefreshTitleFromSystem();
		}
	}
	OnDayChanged.Broadcast(InYear, InMonthIndex, InDay);
}

void UDAProfileSubsystem::RefreshTitleFromSystem()
{
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UDATitleSystem* Titles = GameInstance->GetSubsystem<UDATitleSystem>())
		{
			Titles->ApplyBestTitle(this);
		}
	}
}

void UDAProfileSubsystem::RequestProgressionAutosave(const FString& Reason)
{
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UDASaveSubsystem* Save = GameInstance->GetSubsystem<UDASaveSubsystem>())
		{
			Save->RequestAutosave(Reason);
		}
	}
}

// ------------------------------------------------------------------------ persistence

void UDAProfileSubsystem::WriteSaveData(TSharedPtr<FJsonObject>& Root) const
{
	if (!Root.IsValid())
	{
		return;
	}

	TSharedPtr<FJsonObject> ProfileObject = MakeShared<FJsonObject>();
	ProfileObject->SetStringField(TEXT("name"), PlayerName);
	ProfileObject->SetStringField(TEXT("dorm"), DuelAcademyProfile::DormToSaveKey(Dorm));
	ProfileObject->SetStringField(TEXT("title"), Title);
	ProfileObject->SetNumberField(TEXT("dp"), DP);
	ProfileObject->SetStringField(TEXT("gender"), Gender);
	ProfileObject->SetNumberField(TEXT("playtime_seconds"), PlaytimeSeconds);
	ProfileObject->SetStringField(TEXT("temporary_title"), TemporaryTitle);
	ProfileObject->SetNumberField(TEXT("temporary_title_days"), TemporaryTitleDaysRemaining);
	ProfileObject->SetBoolField(TEXT("initialized"), bInitialized);
	Root->SetObjectField(TEXT("profile"), ProfileObject);

	TSharedPtr<FJsonObject> FlagsObject = MakeShared<FJsonObject>();
	for (const TPair<FString, bool>& Pair : Flags)
	{
		if (Pair.Value)
		{
			FlagsObject->SetBoolField(Pair.Key, true);
		}
	}
	Root->SetObjectField(TEXT("flags"), FlagsObject);

	TSharedPtr<FJsonObject> CountersObject = MakeShared<FJsonObject>();
	for (const TPair<FString, int32>& Pair : Counters)
	{
		CountersObject->SetNumberField(Pair.Key, Pair.Value);
	}
	Root->SetObjectField(TEXT("counters"), CountersObject);

	TSharedPtr<FJsonObject> EmailsObject = MakeShared<FJsonObject>();
	for (const TPair<FString, FDAEmailState>& Pair : Emails)
	{
		TSharedPtr<FJsonObject> ContactObject = MakeShared<FJsonObject>();
		ContactObject->SetBoolField(TEXT("unlocked"), Pair.Value.bUnlocked);

		TArray<TSharedPtr<FJsonValue>> ReadArray;
		for (const FString& ReadId : Pair.Value.ReadIds)
		{
			ReadArray.Add(MakeShared<FJsonValueString>(ReadId));
		}
		ContactObject->SetArrayField(TEXT("read"), ReadArray);

		TArray<TSharedPtr<FJsonValue>> RequestArray;
		for (const FString& RequestId : Pair.Value.PendingDuelRequests)
		{
			RequestArray.Add(MakeShared<FJsonValueString>(RequestId));
		}
		ContactObject->SetArrayField(TEXT("requests"), RequestArray);
		EmailsObject->SetObjectField(Pair.Key, ContactObject);
	}
	Root->SetObjectField(TEXT("emails"), EmailsObject);
}

bool UDAProfileSubsystem::ReadSaveData(const TSharedPtr<FJsonObject>& Root, FString& OutError)
{
	if (!Root.IsValid())
	{
		OutError = TEXT("Profile save data is missing.");
		return false;
	}

	const TSharedPtr<FJsonObject>* ProfileObject = nullptr;
	if (!Root->TryGetObjectField(TEXT("profile"), ProfileObject) || !ProfileObject || !ProfileObject->IsValid())
	{
		OutError = TEXT("Profile save data has no 'profile' object.");
		return false;
	}

	const int32 OldDP = DP;
	const FString OldTitle = Title;
	const EDADorm OldDorm = Dorm;

	PlayerName.Reset();
	Gender = TEXT("unspecified");
	Title = DefaultTitle;
	TemporaryTitle.Reset();
	TemporaryTitleDaysRemaining = 0;
	DP = 3000;
	PlaytimeSeconds = 0.0;
	Dorm = EDADorm::Slifer;

	const TSharedPtr<FJsonObject>& Source = *ProfileObject;
	Source->TryGetStringField(TEXT("name"), PlayerName);
	Source->TryGetStringField(TEXT("gender"), Gender);
	Source->TryGetStringField(TEXT("title"), Title);
	Source->TryGetStringField(TEXT("temporary_title"), TemporaryTitle);
	Source->TryGetNumberField(TEXT("temporary_title_days"), TemporaryTitleDaysRemaining);
	Source->TryGetNumberField(TEXT("dp"), DP);

	double LoadedPlaytime = 0.0;
	if (Source->TryGetNumberField(TEXT("playtime_seconds"), LoadedPlaytime))
	{
		PlaytimeSeconds = FMath::Max(0.0, LoadedPlaytime);
	}

	FString DormKey;
	if (Source->TryGetStringField(TEXT("dorm"), DormKey))
	{
		Dorm = DuelAcademyProfile::ParseDorm(DormKey, EDADorm::Slifer);
	}

	if (PlayerName.IsEmpty())
	{
		PlayerName = TEXT("New Student");
	}
	if (Gender.IsEmpty())
	{
		Gender = TEXT("unspecified");
	}
	if (Title.IsEmpty())
	{
		Title = DefaultTitle;
	}
	DP = FMath::Max(0, DP);
	TemporaryTitleDaysRemaining = FMath::Max(0, TemporaryTitleDaysRemaining);
	if (TemporaryTitleDaysRemaining == 0)
	{
		TemporaryTitle.Reset();
	}

	Flags.Reset();
	const TSharedPtr<FJsonObject>* FlagsObject = nullptr;
	if (Root->TryGetObjectField(TEXT("flags"), FlagsObject) && FlagsObject && FlagsObject->IsValid())
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*FlagsObject)->Values)
		{
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Boolean && Pair.Value->AsBool())
			{
				Flags.Add(ProfileJsonKeyToString(Pair.Key), true);
			}
		}
	}

	Counters.Reset();
	const TSharedPtr<FJsonObject>* CountersObject = nullptr;
	if (Root->TryGetObjectField(TEXT("counters"), CountersObject) && CountersObject && CountersObject->IsValid())
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*CountersObject)->Values)
		{
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Number)
			{
				Counters.Add(ProfileJsonKeyToString(Pair.Key), FMath::Max(0, static_cast<int32>(Pair.Value->AsNumber())));
			}
		}
	}

	Emails.Reset();
	const TSharedPtr<FJsonObject>* EmailsObject = nullptr;
	if (Root->TryGetObjectField(TEXT("emails"), EmailsObject) && EmailsObject && EmailsObject->IsValid())
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*EmailsObject)->Values)
		{
			if (!Pair.Value.IsValid() || Pair.Value->Type != EJson::Object)
			{
				continue;
			}
			const TSharedPtr<FJsonObject> ContactObject = Pair.Value->AsObject();
			if (!ContactObject.IsValid())
			{
				continue;
			}
			FDAEmailState State;
			ContactObject->TryGetBoolField(TEXT("unlocked"), State.bUnlocked);
			ReadStringArray(ContactObject, TEXT("read"), State.ReadIds);
			ReadStringArray(ContactObject, TEXT("requests"), State.PendingDuelRequests);
			Emails.Add(ProfileJsonKeyToString(Pair.Key), MoveTemp(State));
		}
	}

	bInitialized = true;

	if (OldDP != DP)
	{
		OnDPChanged.Broadcast(OldDP, DP);
	}
	if (!OldTitle.Equals(Title))
	{
		OnTitleChanged.Broadcast(OldTitle, Title);
	}
	if (OldDorm != Dorm)
	{
		OnDormChanged.Broadcast(OldDorm, Dorm);
	}
	OnProfileLoaded.Broadcast();
	OutError.Reset();
	return true;
}
