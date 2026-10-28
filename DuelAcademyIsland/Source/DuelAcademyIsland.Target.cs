using UnrealBuildTool;
using System.Collections.Generic;

public class DuelAcademyIslandTarget : TargetRules
{
	public DuelAcademyIslandTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("DuelAcademyIsland");
	}
}
