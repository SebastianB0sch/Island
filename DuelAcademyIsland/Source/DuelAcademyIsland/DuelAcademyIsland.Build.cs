using UnrealBuildTool;

public class DuelAcademyIsland : ModuleRules
{
	public DuelAcademyIsland(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"AudioMixer",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"RenderCore",
			"Slate",
			"SlateCore",
			"Json",
			"JsonUtilities"
		});
	}
}
