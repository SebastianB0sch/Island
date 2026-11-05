// Duel Academy Island - cosmetic anime puppet built from the licensed Fab Anime Character Pack.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TimerManager.h"
#include "DAFabAnimePuppet.generated.h"

class AActor;
class USkeletalMeshComponent;

/**
 * One modular look from the Fab Anime Character Pack.
 *
 * The pack supplies a shared UE4-Mannequin-named skeleton, separate head / hair /
 * top / bottom meshes and the locomotion AnimBlueprint.  A look only selects which
 * meshes and face material to swap in; the puppet itself keeps the pack's animation
 * and cel-shading components.
 */
struct FDAFabAnimeLook
{
	const TCHAR* Id;
	bool bFemale;
	const TCHAR* HeadMesh;
	const TCHAR* HairMesh;
	const TCHAR* TopMesh;
	const TCHAR* BottomMesh;
	const TCHAR* HeadMaterial;
	FLinearColor HairColor;
};

/**
 * Spawns and drives a cosmetic `bp_AnimeCharacter` puppet for its owner.
 *
 * The component is dormant until Activate(LookId) is called.  It hides the owner's
 * native UDAAvatarComponent on success and restores it on Deactivate/EndPlay.  If
 * the Fab pack is not installed the component fails closed: the NPC keeps its
 * native GX cast avatar.
 */
UCLASS(ClassGroup = (DuelAcademy), meta = (BlueprintSpawnableComponent))
class DUELACADEMYISLAND_API UDAFabAnimeComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UDAFabAnimeComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

	/** Spawn the puppet for `LookId`. Returns false (and keeps the native avatar) if the pack is missing. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Fab Anime")
	bool ActivateLook(const FString& LookId);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Fab Anime")
	void DeactivateLook();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Fab Anime")
	bool IsLookActive() const { return Puppet.IsValid(); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Fab Anime")
	FString GetActiveLook() const { return ActiveLook; }

private:
	bool ApplyLook(AActor* InPuppet, const FDAFabAnimeLook& Look);
	void HideNativeAvatar(bool bHide);
	void RefreshLook();

	TWeakObjectPtr<AActor> Puppet;
	FString ActiveLook;
	FTimerHandle RefreshTimer;
};
