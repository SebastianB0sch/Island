"""Audit spawned world actors in the current level."""

import collections

import unreal

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
counts = collections.Counter(a.get_class().get_name() for a in actors)
for name in ("DAInteriorPortal", "DASceneAnchor", "DANpcSpawnPoint", "DANpcDirector", "DAStudentNPC", "DAInteractable"):
    unreal.log(f"[DuelAcademy] {name}: {counts.get(name, 0)}")
unreal.log(f"[DuelAcademy] total actors: {len(actors)}")
