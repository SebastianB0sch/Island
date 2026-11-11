"""Import generated SourceAssets (FBX meshes, PNG textures, WAV sounds) into /Game/DuelAcademy."""

import glob
import json
import os
import sys

import unreal

from . import asset_paths as AP
from . import common as C

# texture categories -> (compression, sRGB, sampler)
#   _D detail maps      linear colour     (LinearColor sampler)
#   _N normal maps      normal map        (Normal sampler)
#   splat maps          masks             (Masks sampler)
#   colour textures     default sRGB      (Color sampler)
# water data textures (Tools/dai/water.py): foam / caustics / rain rings are plain linear data ...
LINEAR = {"T_Noise", "T_WaterStreaks", "T_WaterFoam", "T_Caustics", "T_Ripples"}
# ... the island-wide maps are channel masks, clamped like the splat maps (they must not wrap at the edge)
MASKS = {"T_TerrainSplatA", "T_TerrainSplatB", "T_WaveMask", "T_WaterShore"}
NORMALS = {"T_WaterNormal", "T_WaterDetailN", "T_FlatNormal"}
UI = {"T_IslandMap"}


def texture_kind(name):
    if name.endswith("_N") or name in NORMALS:
        return "normal"
    if name in MASKS or name.endswith("_ORM") or name.endswith("_R") or name == "T_DefaultMask" \
            or (name.startswith("T_Terrain_") and name.endswith("_H")):      # layer relief (height blend)
        return "masks"
    if name.endswith("_D") or name in LINEAR:
        return "linear"
    return "color"


def _import_tasks(files, dest, options=None, names=None):
    tasks = []
    for i, f in enumerate(files):
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", f)
        t.set_editor_property("destination_path", dest)
        if names:
            t.set_editor_property("destination_name", names[i])
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("automated", True)
        t.set_editor_property("save", False)
        if options is not None:
            t.set_editor_property("options", options)
        tasks.append(t)
    if tasks:
        C.asset_tools().import_asset_tasks(tasks)
    out = []
    for t in tasks:
        try:
            out.extend(list(t.get_editor_property("imported_object_paths") or []))
        except Exception:  # noqa: BLE001
            pass
    return out


# --------------------------------------------------------------------------- textures
def import_textures(slow=None):
    """Imports Textures/*.png|jpg and Textures/<sub>/**/ (third-party PBR sets keep their sub folders)."""
    C.ensure_dir(C.TEX_DIR)
    root = os.path.join(C.source_dir(), "Textures")
    by_dir = {}
    for f in sorted(glob.glob(os.path.join(root, "**", "*.*"), recursive=True)):
        if os.path.splitext(f)[1].lower() not in (".png", ".jpg", ".jpeg", ".tga"):
            continue
        rel = os.path.relpath(os.path.dirname(f), root).replace(os.sep, "/")
        dest = C.TEX_DIR if rel in (".", "") else f"{C.TEX_DIR}/{rel}"
        by_dir.setdefault(dest, []).append(f)
    names = []
    for dest, files in by_dir.items():
        C.ensure_dir(dest)
        base = [os.path.splitext(os.path.basename(f))[0] for f in files]
        _import_tasks(files, dest, names=base)
        names += [f"{dest[len(C.TEX_DIR) + 1:]}/{b}" if dest != C.TEX_DIR else b for b in base]
    for rel in names:
        n = rel.split("/")[-1]
        tex = C.load(f"{C.TEX_DIR}/{rel}")
        if tex is None:
            C.warn(f"texture {rel} failed to import")
            continue
        kind = texture_kind(n)
        if kind == "normal":
            C.set_props(tex, compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP, srgb=False)
        elif kind == "masks":
            C.set_props(tex, compression_settings=unreal.TextureCompressionSettings.TC_MASKS, srgb=False)
        elif kind == "linear":
            C.set_props(tex, compression_settings=unreal.TextureCompressionSettings.TC_DEFAULT, srgb=False)
        else:
            C.set_props(tex, srgb=True)
        if n in UI:
            C.set_props(tex, lod_group=unreal.TextureGroup.TEXTUREGROUP_UI,
                        address_x=unreal.TextureAddress.TA_CLAMP, address_y=unreal.TextureAddress.TA_CLAMP,
                        mip_gen_settings=unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        if n in MASKS or n == "T_TerrainColor":
            C.set_props(tex, address_x=unreal.TextureAddress.TA_CLAMP, address_y=unreal.TextureAddress.TA_CLAMP)
        if n == "T_WaveMask":
            # 256 x 256, sampled in the vertex shader at mip 0 and bilinearly by ADAIslandManager: keep it exact
            C.set_props(tex, mip_gen_settings=unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    C.log(f"textures: {len(names)}")
    return names


# --------------------------------------------------------------------------- audio
def import_audio():
    C.ensure_dir(C.AUDIO_DIR)
    files = sorted(glob.glob(os.path.join(C.source_dir(), "Audio", "*.wav")))
    names = [os.path.splitext(os.path.basename(f))[0] for f in files]
    _import_tasks(files, C.AUDIO_DIR, names=names)
    loops = {"A_Ocean", "A_Wind", "A_Forest", "A_Volcano", "A_Waterfall", "A_HotSpring", "A_Crowd"}
    # Zone/title music beds are continuous too (M_<Track>).
    loops.update(n for n in names if n.startswith("M_"))
    for n in names:
        snd = C.load(f"{C.AUDIO_DIR}/{n}")
        if snd is None:
            C.warn(f"sound {n} failed to import")
            continue
        C.set_props(snd, looping=n in loops)
    C.log(f"sounds: {len(names)}")


# --------------------------------------------------------------------------- meshes
def _fbx_options(nanite):
    ui = unreal.FbxImportUI()
    C.set_props(ui, import_mesh=True, import_as_skeletal=False, import_materials=False, import_textures=False,
                import_animations=False, create_physics_asset=False, automated_import_should_detect_type=False)
    try:
        ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    except Exception:  # noqa: BLE001
        pass
    sm = ui.get_editor_property("static_mesh_import_data")
    # convert_scene_unit defaults to False on programmatically created import options in UE 5.8; the FBX
    # files are exported in metres, so without it every mesh imports 100x too small. Collision and unit
    # flags are gameplay-relevant -> strict: a silent failure here must abort the import.
    C.set_props(sm, combine_meshes=True, auto_generate_collision=False, generate_lightmap_u_vs=False,
                remove_degenerates=True, one_convex_hull_per_ucx=True, convert_scene_unit=True, strict=True)
    try:
        sm.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    except Exception:  # noqa: BLE001
        pass
    try:
        sm.set_editor_property("build_nanite", bool(nanite))
    except Exception:  # noqa: BLE001
        pass
    try:
        # road ribbons carry their paving coverage as vertex colour (M_DA_Road); every other mesh has none
        # and keeps the default white
        sm.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    except Exception as e:  # noqa: BLE001 - without it the roads are simply paved to their very edge
        C.warn(f"vertex colour import not enabled: {e}")
    return ui


def _set_fbx_interchange(enabled):
    """UE 5.5+ routes FBX through Interchange; the legacy importer honours our explicit options."""
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    except Exception:  # noqa: BLE001
        world = None
    try:
        unreal.SystemLibrary.execute_console_command(world, f"Interchange.FeatureFlags.Import.FBX {1 if enabled else 0}")
    except Exception:  # noqa: BLE001
        pass


def _source_path(rel):
    """Resolve a manifest path inside SourceAssets (raises on traversal/absolute paths)."""
    try:
        return AP.source_path(C.source_dir(), rel)
    except ValueError as exc:
        raise RuntimeError(f"invalid SourceAssets path {rel!r}: {exc}") from exc


def _report_preflight_failure(kind, problems):
    for rel, reason in problems:
        C.error(f"{kind} preflight: {rel}: {reason}")
    raise RuntimeError(
        f"{kind} import preflight failed ({len(problems)} problem(s)); "
        "no assets were changed - rebuild SourceAssets first"
    )


def _manifest_problems(entries):
    """Validate names and files before asking Unreal to replace anything."""
    problems = []
    seen = {}
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append(("<manifest>", "asset manifest entry is not an object"))
            continue
        name = entry.get("name")
        rel = entry.get("file")
        if not name:
            problems.append(("<unnamed>", "manifest entry has no name"))
            continue
        if name in seen:
            problems.append((rel or name, f"duplicate asset name {name!r}"))
        seen[name] = True
        if not rel:
            problems.append((name, "manifest entry has no file"))
        if not entry.get("folder"):
            problems.append((name, "manifest entry has no folder"))
    files = [(entry.get("file"), entry.get("name", "?")) for entry in entries
             if isinstance(entry, dict) and entry.get("file")]
    for rel, _name in files:
        try:
            AP.source_path(C.source_dir(), rel)
        except ValueError as exc:
            problems.append((str(rel), str(exc)))
    problems.extend(AP.missing_sources(C.source_dir(), [rel for rel, _ in files]))
    return problems


def import_meshes(manifest, slow=None, only=None):
    """Import every FBX listed in assets.json. Returns {asset name: StaticMesh}.

    Every selected source file is checked before the first import task runs: a
    missing/stale manifest entry aborts the stage instead of leaving half of the
    asset set replaced (Unreal's importer is not transactional).
    """
    entries = [e for e in manifest if not only or e.get("category") in only]
    problems = _manifest_problems(entries)
    if problems:
        _report_preflight_failure("mesh", problems)
    groups = {}
    for e in entries:
        groups.setdefault((e["folder"], bool(e.get("nanite"))), []).append(e)
    result = {}
    total = sum(len(v) for v in groups.values())
    done = 0
    _set_fbx_interchange(False)
    try:
        for (folder, nanite), entries in sorted(groups.items()):
            dest = f"{C.MESH_DIR}/{folder}"
            C.ensure_dir(dest)
            files = [_source_path(e["file"]) for e in entries]
            names = [e["name"] for e in entries]
            # chunk the batch so the progress bar moves
            for i in range(0, len(files), 12):
                fb, nb = files[i:i + 12], names[i:i + 12]
                if slow:
                    slow.enter_progress_frame(len(fb), f"Importing meshes ({done}/{total})  {folder}")
                _import_tasks(fb, dest, _fbx_options(nanite), nb)
                missing = [(f, n) for f, n in zip(fb, nb) if not C.exists(f"{dest}/{n}")]
                if missing:
                    # Legacy importer unavailable in this engine build -> let Interchange do it.
                    _set_fbx_interchange(True)
                    _import_tasks([m[0] for m in missing], dest, None, [m[1] for m in missing])
                    _set_fbx_interchange(False)
                done += len(fb)
            for e in entries:
                mesh = C.load(f"{dest}/{e['name']}")
                if mesh is None:
                    C.error(f"mesh {e['name']} failed to import ({e['file']})")
                    continue
                result[e["name"]] = mesh
    finally:
        _set_fbx_interchange(True)
    C.log(f"meshes: {len(result)}/{total} imported")
    return result


def configure_mesh(mesh, entry, materials):
    """Collision, nanite and material slots after import."""
    name = entry["name"]
    # ---- material slots: slot names are the palette names exported from Blender
    try:
        static_mats = mesh.get_editor_property("static_materials")
        for i, sm in enumerate(static_mats):
            slot = str(sm.get_editor_property("material_slot_name"))
            key = _palette_key(slot, materials)
            if key:
                mesh.set_material(i, materials[key])
            else:
                C.warn(f"{name}: no material for slot '{slot}'")
    except Exception as e:  # noqa: BLE001
        C.warn(f"{name}: material assignment failed: {e}")

    # ---- collision
    col = entry.get("collision", "complex")
    try:
        body = mesh.get_editor_property("body_setup")
        if body is not None:
            if col == "complex":
                body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            elif col == "simple":
                body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_DEFAULT)
            else:
                body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
    except Exception as e:  # noqa: BLE001
        C.warn(f"{name}: collision setup failed: {e}")
    if col == "none":
        try:
            unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).remove_collisions(mesh)
        except Exception:  # noqa: BLE001
            pass

    # ---- nanite (vegetation / rocks) - keeps 90k instances cheap
    if entry.get("nanite"):
        try:
            settings = mesh.get_editor_property("nanite_settings")
            settings.set_editor_property("enabled", True)
            try:
                unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(mesh, settings, True)
            except Exception:  # noqa: BLE001
                mesh.set_editor_property("nanite_settings", settings)
        except Exception as e:  # noqa: BLE001
            C.warn(f"{name}: nanite not enabled: {e}")


def _palette_key(slot, materials):
    if slot in materials:
        return slot
    # strip importer suffixes like "M_Wood_001", "M_Wood.001", "M_Wood_Mat"
    base = slot.split(".")[0]
    for cut in range(3):
        if base in materials:
            return base
        if "_" in base:
            head, tail = base.rsplit("_", 1)
            if tail.isdigit() or tail.lower() in ("mat", "material", "skinned"):
                base = head
                continue
        break
    return None


def cleanup_imported_materials():
    """Delete material/texture assets that an importer may have created next to the meshes."""
    removed = 0
    for path in unreal.EditorAssetLibrary.list_assets(C.MESH_DIR, recursive=True, include_folder=False):
        try:
            data = unreal.EditorAssetLibrary.find_asset_data(path)
            cls = str(data.get_editor_property("asset_class_path").get_editor_property("asset_name")) if hasattr(data, "asset_class_path") else str(data.asset_class)
        except Exception:  # noqa: BLE001 - asset registry not ready / stale path
            continue
        if cls in ("Material", "MaterialInstanceConstant", "Texture2D"):
            if unreal.EditorAssetLibrary.delete_asset(path):
                removed += 1
    if removed:
        C.log(f"removed {removed} importer-generated materials/textures")


# --------------------------------------------------------------------------- skeletal student
CHAR_DIR = C.ROOT + "/Characters"
# Walk / Run reference speed lives in common.REF_SPEED (shared with the terrain
# material scale fallback and documented against UDAAvatarComponent).


def _skeletal_options(skeleton=None):
    """Legacy FBX options for the student mesh (skeleton None) or for one animation take."""
    ui = unreal.FbxImportUI()
    anim_only = skeleton is not None
    C.set_props(ui, import_mesh=not anim_only, import_as_skeletal=True, import_materials=False,
                import_textures=False, import_animations=anim_only, create_physics_asset=False,
                automated_import_should_detect_type=False, override_full_name=True)
    try:
        ui.set_editor_property("mesh_type_to_import",
                               unreal.FBXImportType.FBXIT_ANIMATION if anim_only else unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    except Exception:  # noqa: BLE001
        pass
    if anim_only:
        ui.set_editor_property("skeleton", skeleton)
        try:
            ad = ui.get_editor_property("anim_sequence_import_data")
            C.set_props(ad, remove_redundant_keys=True, import_bone_tracks=True,
                        import_custom_attribute=False, convert_scene_unit=True)
            ad.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            sd = ui.get_editor_property("skeletal_mesh_import_data")
            # morph targets: the cast faces carry blink / viseme / emotion morphs (Tools/dai/anime/models.py)
            C.set_props(sd, import_morph_targets=True, update_skeleton_reference_pose=False,
                        convert_scene_unit=True)
            sd.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        except Exception:  # noqa: BLE001
            pass
    return ui


def _cast_anim_path(rel):
    """Source path for a cast animation take.

    The pipeline exports armature-only FBX takes, which UE 5.8's legacy FBX importer mishandles
    (it can leave a stale sequence or silently import the wrong length). import_cast feeds these
    files through Interchange, which binds them directly to the existing skeleton and preserves
    the authored time range."""
    return _source_path(rel)


def _interchange_animation(file, name, skeleton):
    """Fallback for armature-only animation FBX files.

    UE 5.8's legacy FBX animation importer looks for a skinned mesh bound to the skeleton's root bone and
    rejects files that only contain the armature ("Mesh contains root_001 bone as root but animation
    doesn't contain the root track"). Interchange binds the take to an existing skeleton directly."""
    _set_fbx_interchange(True)
    try:
        pipe = unreal.new_object(unreal.InterchangeGenericAssetsPipeline)
        common = pipe.get_editor_property("common_skeletal_meshes_and_animations_properties")
        C.set_props(common, skeleton=skeleton, import_only_animations=True, try_auto_select_skeleton=False)
        anim_pipe = pipe.get_editor_property("animation_pipeline")
        C.set_props(anim_pipe, import_animations=True, import_bone_tracks=True)
        override = unreal.new_object(unreal.InterchangePipelineStackOverride)
        override.add_pipeline(pipe)
        _import_tasks([file], CHAR_DIR, override, [name])
    finally:
        _set_fbx_interchange(False)


def _find_in(folder, cls_name, contains=None):
    for path in unreal.EditorAssetLibrary.list_assets(folder, recursive=False, include_folder=False):
        obj = unreal.EditorAssetLibrary.load_asset(path)
        if obj is not None and obj.get_class().get_name() == cls_name:
            name = obj.get_name()
            if name.endswith("__DAOld"):
                continue  # our own rollback backup, not a new import
            if contains is None or contains.lower() in name.lower():
                return obj
    return None


def import_character(materials):
    """SourceAssets/Data/character.json -> /Game/DuelAcademy/Characters/SK_Student + A_Student_<State>.

    The C++ avatar component (UDAAvatarComponent::SetupSkeletal) picks these up by name and recolours
    the jacket slot per dorm; without them the procedural avatar is used."""
    try:
        info = C.load_json("character.json")
    except Exception:  # noqa: BLE001
        C.log("character: none exported (procedural avatar will be used)")
        return None
    if not isinstance(info, dict) or not info:
        C.error("character: character.json is empty or not an object; keeping the procedural avatar")
        return None
    mesh_rel = info.get("mesh")
    problems = AP.missing_sources(C.source_dir(), [mesh_rel] if mesh_rel else [])
    if not mesh_rel:
        problems.append(("<character>", "character.json has no mesh"))
    if problems:
        for rel, reason in problems:
            C.error(f"character preflight: {rel}: {reason}")
        C.warn("character: source missing; keeping the previously imported SK_Student (if any)")
        return None
    # Animation files are optional per state: preflight first so one missing take
    # is skipped with a warning instead of failing midway through an import.
    anim_spec = info.get("anims")
    anims = {state: rel for state, rel in anim_spec.items() if rel} if isinstance(anim_spec, dict) else {}
    missing_anims = {rel for rel, _reason in AP.missing_sources(C.source_dir(), list(anims.values()))}
    for state in list(anims):
        if anims[state] in missing_anims:
            C.warn(f"character: animation {state} skipped (source file missing)")
            anims.pop(state)
    C.ensure_dir(CHAR_DIR)
    _set_fbx_interchange(False)
    try:
        _import_tasks([_source_path(mesh_rel)], CHAR_DIR, _skeletal_options(), ["SK_Student"])
        mesh = C.load(f"{CHAR_DIR}/SK_Student")
        if mesh is None:
            # the importer may have named it after the FBX node: rename so the C++ side finds it
            found = _find_in(CHAR_DIR, "SkeletalMesh")
            if found is not None:
                unreal.EditorAssetLibrary.rename_asset(found.get_path_name().split(".")[0], f"{CHAR_DIR}/SK_Student")
                mesh = C.load(f"{CHAR_DIR}/SK_Student")
        if mesh is None:
            C.error("character: SK_Student failed to import")
            return None
        skeleton = mesh.get_editor_property("skeleton")
        for state, rel in sorted(anims.items()):
            name = f"A_Student_{state}"
            file = _source_path(rel)
            _import_tasks([file], CHAR_DIR, _skeletal_options(skeleton), [name])
            if not C.exists(f"{CHAR_DIR}/{name}"):
                # armature-only FBX: legacy importer cannot find the root track, use Interchange
                _interchange_animation(file, name, skeleton)
            if not C.exists(f"{CHAR_DIR}/{name}"):
                # importer appended the take name: rename whatever sequence carries the state name
                seq = _find_in(CHAR_DIR, "AnimSequence", name)
                if seq is not None:
                    unreal.EditorAssetLibrary.rename_asset(seq.get_path_name().split(".")[0], f"{CHAR_DIR}/{name}")
            if not C.exists(f"{CHAR_DIR}/{name}"):
                C.warn(f"character: animation {state} failed to import")
                continue
            # normalise each locomotion clip to a reference ground speed (UDAAvatarComponent::WalkAnimSpeed /
            # RunAnimSpeed) using the speed measured by Tools/dai/character.py, so play rates match any rig
            speed = info.get("ground_speed", {}).get(state)
            ref = C.REF_SPEED.get(state)
            if speed and ref:
                seq = C.load(f"{CHAR_DIR}/{name}")
                try:
                    seq.set_editor_property("rate_scale", max(0.2, min(5.0, ref / float(speed))))
                except Exception as e:  # noqa: BLE001
                    C.warn(f"character: rate scale for {state}: {e}")
    finally:
        _set_fbx_interchange(True)

    # material slots keep the source material names (e.g. MT_Student_Shirt) so the avatar component can
    # find the jacket / hair slots; palette instances carry the textures
    try:
        mats = list(mesh.get_editor_property("materials"))
        for sm in mats:
            slot = str(sm.get_editor_property("material_slot_name"))
            key = _palette_key(slot, materials) or _palette_key(slot.replace("MT_", "MT_Student_", 1), materials)
            if key:
                sm.set_editor_property("material_interface", materials[key])
            else:
                C.warn(f"SK_Student: no material for slot '{slot}'")
        mesh.set_editor_property("materials", mats)
    except Exception as e:  # noqa: BLE001
        C.warn(f"SK_Student: material assignment failed: {e}")
    for path in unreal.EditorAssetLibrary.list_assets(CHAR_DIR, recursive=False, include_folder=False):
        obj = unreal.EditorAssetLibrary.load_asset(path)
        if obj is not None and obj.get_class().get_name() in ("Material", "MaterialInstanceConstant", "Texture2D"):
            unreal.EditorAssetLibrary.delete_asset(path)
    C.log(f"character: SK_Student + {len(anims)} animations")
    return mesh


# --------------------------------------------------------------------------- anime cast
def _skeletal_mesh_options(skeleton=None):
    """Legacy FBX options for a cast mesh; with `skeleton` the mesh joins an existing Skeleton asset."""
    ui = _skeletal_options()
    if skeleton is not None:
        ui.set_editor_property("skeleton", skeleton)
    return ui


def _import_one(rel, name, options):
    _import_tasks([_source_path(rel)], CHAR_DIR, options, [name])
    return C.load(f"{CHAR_DIR}/{name}")


def _assign_slots(mesh, lookup, instances, label):
    """Set every material slot of a skeletal mesh: lookup(slot name) -> palette name -> instance."""
    try:
        mats = list(mesh.get_editor_property("materials"))
        for sm in mats:
            slot = str(sm.get_editor_property("material_slot_name"))
            key = lookup(slot) or lookup(_palette_key(slot, instances) or "")
            mi = instances.get(key) if key else None
            if mi is not None:
                sm.set_editor_property("material_interface", mi)
            else:
                C.warn(f"{label}: no material for slot '{slot}'")
        mesh.set_editor_property("materials", mats)
    except Exception as e:  # noqa: BLE001
        C.warn(f"{label}: material assignment failed: {e}")


def _backup_asset(path):
    """Move an existing generated asset aside before replacing it.

    Unreal's FBX/Interchange import is not transactional: deleting the old take
    first loses it if the new import fails.  A rename is cheap and lets the
    animation loop restore the previous take.  Returns the backup path or None.
    """
    if not C.exists(path):
        return None
    backup = path + "__DAOld"
    try:
        if C.exists(backup):
            unreal.EditorAssetLibrary.delete_asset(backup)
        if unreal.EditorAssetLibrary.rename_asset(path, backup):
            return backup
        C.warn(f"cast: could not back up {path}; the existing asset will be replaced in place")
    except Exception as e:  # noqa: BLE001
        C.warn(f"cast: backing up {path} failed: {e}")
    return None


def _restore_asset(backup, path):
    """Undo _backup_asset after a failed replacement."""
    if backup is None:
        return
    try:
        if C.exists(path):
            unreal.EditorAssetLibrary.delete_asset(path)
        if not unreal.EditorAssetLibrary.rename_asset(backup, path):
            C.error(f"cast: could not restore {path} from {backup}")
    except Exception as e:  # noqa: BLE001
        C.error(f"cast: restoring {path} failed: {e}")


def _drop_backup(backup):
    if backup is None:
        return
    try:
        unreal.EditorAssetLibrary.delete_asset(backup)
    except Exception as e:  # noqa: BLE001
        C.warn(f"cast: could not remove backup {backup}: {e}")


def _cleanup_abandoned_backups():
    """Remove ``__DAOld`` leftovers only when the replacement asset exists.

    A backup whose original is still missing is the only remaining copy after a
    failed restore; keep it for manual recovery instead of deleting it.
    """
    try:
        paths = list(unreal.EditorAssetLibrary.list_assets(CHAR_DIR, recursive=False, include_folder=False))
    except Exception as e:  # noqa: BLE001
        C.warn(f"cast: backup cleanup skipped: {e}")
        return
    for path in paths:
        name = AP.asset_name(path)
        if not name.endswith("__DAOld") or not AP.is_cast_owned(name):
            continue
        original = name[: -len("__DAOld")]
        try:
            if C.exists(f"{CHAR_DIR}/{original}"):
                unreal.EditorAssetLibrary.delete_asset(path)
        except Exception as e:  # noqa: BLE001
            C.warn(f"cast: cleanup of {name} failed: {e}")


def _lods(mesh, count=3):
    """Auto LODs - the cast models are 45-50k triangles and dozens of students walk around."""
    try:
        unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem).regenerate_lod(mesh, count)
    except Exception as e:  # noqa: BLE001
        C.warn(f"{mesh.get_name()}: LOD generation skipped ({e})")


CAST_STATE_REL = os.path.join("Saved", "DuelAcademy", "cast_assets.json")


def _cast_state_path():
    return os.path.join(C.project_dir(), CAST_STATE_REL)


def _cast_source_entries(info):
    """(label, manifest path) for every source file the cast import will touch."""
    entries = []
    meshes = info.get("meshes")
    groups = info.get("groups")
    for cid, m in (meshes if isinstance(meshes, dict) else {}).items():
        if isinstance(m, dict) and m.get("file"):
            entries.append((f"mesh {cid}", m["file"]))
    for group, g in (groups if isinstance(groups, dict) else {}).items():
        if not isinstance(g, dict):
            continue
        base = g.get("base_mesh") or {}
        if isinstance(base, dict) and base.get("file"):
            entries.append((f"group {group} base", base["file"]))
        anims = g.get("anims")
        for state, anim in (anims if isinstance(anims, dict) else {}).items():
            if isinstance(anim, dict) and anim.get("file"):
                entries.append((f"group {group} anim {state}", anim["file"]))
        disk = g.get("duel_disk") or {}
        if isinstance(disk, dict) and disk.get("file"):
            entries.append((f"group {group} duel disk", disk["file"]))
    return entries


def _validate_cast_manifest(info):
    """Names/paths that import_cast indexes directly; fail before changing assets."""
    problems = []
    meshes = info.get("meshes")
    if not isinstance(meshes, dict) or not meshes:
        problems.append(("<cast.json>", "no 'meshes' section"))
    mesh_entries = meshes if isinstance(meshes, dict) else {}
    groups = info.get("groups")
    if not isinstance(groups, dict):
        problems.append(("<cast.json>", "no 'groups' section"))
        groups = {}
    for cid, m in mesh_entries.items():
        if not isinstance(m, dict):
            problems.append((str(cid), "mesh entry is not an object"))
            continue
        if not m.get("name"):
            problems.append((str(cid), "mesh entry has no name"))
        if "group" not in m:
            problems.append((str(cid), "mesh entry has no skeleton group"))
        elif m.get("group") not in groups:
            problems.append((str(cid), f"mesh references unknown skeleton group {m.get('group')!r}"))
        if "file" in m and not m.get("file"):
            problems.append((str(cid), "mesh entry has an empty file path"))
    for group, g in (groups or {}).items():
        if not isinstance(g, dict):
            problems.append((str(group), "group entry is not an object"))
            continue
        for label, item in (("base mesh", g.get("base_mesh")), ("duel disk", g.get("duel_disk"))):
            if item is not None and not (isinstance(item, dict) and item.get("name") and item.get("file")):
                problems.append((str(group), f"incomplete {label} entry"))
        anims = g.get("anims")
        if anims is not None and not isinstance(anims, dict):
            problems.append((str(group), "anims is not an object"))
            continue
        for state, anim in (anims or {}).items():
            if not isinstance(anim, dict) or not anim.get("name") or not anim.get("file"):
                problems.append((str(group), f"incomplete animation entry {state}"))
    entries = _cast_source_entries(info)
    problems.extend(AP.missing_sources(C.source_dir(), [rel for _label, rel in entries]))
    return problems


def _prune_stale_cast(info, prune=True):
    """Delete only cast-asset names this importer created and the new manifest dropped.

    Ownership is recorded in Saved/DuelAcademy/cast_assets.json after a cast
    import.  A missing record is bootstrapped without deleting anything, and an
    unreadable record is left alone: both cases are non-destructive.  Skeleton /
    PhysicsAsset helpers and anything outside ``SK_Anime_*`` / ``A_Anime_*`` are
    never touched.
    """
    if not prune:
        return 0
    expected = AP.expected_cast_assets(info)
    if not expected:
        C.warn("cast: manifest lists no assets; stale cleanup skipped")
        return 0
    try:
        state_path = _cast_state_path()
    except Exception as e:  # noqa: BLE001 - never fail an import over the cleanup record
        C.warn(f"cast: stale cleanup skipped (cannot resolve Saved/: {e})")
        return 0
    if not os.path.exists(state_path):
        try:
            AP.write_json_atomic(state_path, AP.state_document(expected))
            C.log("cast: asset ownership recorded (old assets from earlier builds are left for the next run)")
        except OSError as e:
            C.warn(f"cast: could not record asset ownership: {e}")
        return 0
    try:
        with open(state_path, "r", encoding="utf-8") as fp:
            owned = AP.owned_names(json.load(fp))
    except (OSError, ValueError) as e:
        C.warn(f"cast: stale cleanup skipped (unreadable ownership record: {e})")
        return 0

    removed = 0
    for name in AP.stale_owned_assets(owned, expected):
        path = f"{CHAR_DIR}/{name}"
        try:
            if not C.exists(path):
                continue
            if unreal.EditorAssetLibrary.delete_asset(path):
                removed += 1
            else:
                C.warn(f"cast: could not delete stale asset {name}")
        except Exception as e:  # noqa: BLE001
            C.warn(f"cast: deleting stale asset {name} failed: {e}")
    try:
        AP.write_json_atomic(state_path, AP.state_document(expected))
    except OSError as e:
        C.warn(f"cast: could not update asset ownership: {e}")
    if removed:
        C.log(f"cast: removed {removed} stale SK_Anime_/A_Anime_ asset(s)")
    return removed


def _apply_fab_locomotion():
    """Install the optional local Fab locomotion retarget after a cast rebuild.

    The cast rebuild regenerates the procedural gait A_Anime_<Group>_Idle/Walk/Run
    takes, which would otherwise silently replace the retargeted Fab takes.  When
    the local-only retargeted FBXs exist (Tools/retarget_fab_anime.py), re-import
    them over the fresh gait clips.  A fresh checkout has no such folder and keeps
    the gait clips exactly as before.
    """
    repo = os.path.dirname(C.project_dir())
    retarget_dir = os.path.join(repo, "Tools", "thirdparty", "fab_anime", "retargeted")
    if not os.path.isdir(retarget_dir):
        return
    tools = os.path.join(repo, "Tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        import apply_fab_locomotion as fab_locomotion
    except Exception as exc:  # noqa: BLE001 - the gait clips are a valid fallback
        C.warn(f"cast: Fab locomotion installer unavailable: {exc}")
        return
    C.log("cast: re-applying local Fab locomotion retarget takes")
    try:
        result = fab_locomotion.main()
        if result:
            C.warn("cast: Fab locomotion install reported failures; a group may have kept its gait takes")
    except Exception as exc:  # noqa: BLE001
        C.warn(f"cast: Fab locomotion takes not re-applied: {exc}")


def import_cast(masters, prune=True):
    """SourceAssets/Data/cast.json -> /Game/DuelAcademy/Characters: the anime cast.

    Per skeleton group (one per base anime model, plus the procedural fallback rig): the first member's FBX
    creates the Skeleton, the A_Anime_<Group>_<State> takes, SK_Anime_<Group>_DuelDisk and every other cast
    member SK_Anime_<Name> (own FBX: individually tailored uniform / hairstyle) use it. Older exports with a
    shared base mesh + per-member material slot maps still import. UDAAvatarComponent loads them by name
    (CastMesh / AnimGroup). Every source file is preflighted before the first asset is replaced; pruning of
    removed cast assets is opt-out (``prune=False``) and ownership-based (see _prune_stale_cast)."""
    from . import materials as MAT
    try:
        info = C.load_json("cast.json")
    except Exception:  # noqa: BLE001
        C.log("cast: none exported (SK_Student / procedural avatar will be used)")
        return {}
    if not isinstance(info, dict):
        C.error("cast: cast.json is not an object; nothing imported")
        return {}
    problems = _validate_cast_manifest(info)
    if problems:
        _report_preflight_failure("cast", problems)
    instances = MAT.build_instances(info.get("materials", {}), masters)
    C.ensure_dir(CHAR_DIR)
    meshes = {}
    _set_fbx_interchange(False)
    try:
        cast_groups = info.get("groups") or {}
        cast_meshes = info.get("meshes") or {}
        for group, g in cast_groups.items():
            members = {cid: m for cid, m in cast_meshes.items() if m.get("group") == group}
            if not members:
                C.warn(f"cast: skeleton group {group} has no meshes; skipped")
                continue
            base = g.get("base_mesh")
            if base:
                base_mesh = _import_one(base["file"], base["name"], _skeletal_mesh_options())
            else:   # procedural group: the first member's FBX creates the skeleton
                first = next(iter(members.values()))
                base_mesh = _import_one(first["file"], first["name"], _skeletal_mesh_options())
            if base_mesh is None:
                C.error(f"cast: {group} base mesh failed to import")
                continue
            skeleton = base_mesh.get_editor_property("skeleton")
            for state, a in sorted(g.get("anims", {}).items()):
                file = _cast_anim_path(a["file"])
                seq_path = f"{CHAR_DIR}/{a['name']}"
                # Replace through a rename-backup: a failed import restores the old
                # take instead of leaving the cut/scene without an animation.
                backup = _backup_asset(seq_path)
                try:
                    # Armature-only takes: Interchange binds them to the existing skeleton directly.
                    _interchange_animation(file, a["name"], skeleton)
                    if not C.exists(seq_path):
                        # Fallback for engine versions where the Interchange pipeline is unavailable.
                        _import_tasks([file], CHAR_DIR, _skeletal_options(skeleton), [a["name"]])
                    if not C.exists(seq_path):
                        seq = _find_in(CHAR_DIR, "AnimSequence", a["name"])
                        if seq is not None:
                            unreal.EditorAssetLibrary.rename_asset(seq.get_path_name().split(".")[0], seq_path)
                    if not C.exists(seq_path):
                        raise RuntimeError("importer produced no sequence")
                except Exception as exc:  # noqa: BLE001
                    _restore_asset(backup, seq_path)
                    C.warn(f"cast: animation {a['name']} failed to import: {exc}")
                    continue
                _drop_backup(backup)
                if a.get("seconds"):
                    seq = C.load(seq_path)
                    actual = seq.get_play_length() if seq else -1.0
                    if actual >= 0.0 and abs(actual - float(a["seconds"])) > 0.02:
                        C.warn(f"cast: {a['name']} length {actual:.3f}s, expected {a['seconds']}s")
            disk = g.get("duel_disk")
            if disk:
                dm = _import_one(disk["file"], disk["name"], _skeletal_mesh_options(skeleton))
                if dm is not None:
                    _assign_slots(dm, lambda s: s, instances, disk["name"])
            for cid, m in members.items():
                path = f"{CHAR_DIR}/{m['name']}"
                if "file" in m:
                    mesh = base_mesh if m["name"] == base_mesh.get_name() else _import_one(
                        m["file"], m["name"], _skeletal_mesh_options(skeleton))
                    lookup = (lambda s: s)
                else:
                    if C.exists(path):
                        unreal.EditorAssetLibrary.delete_asset(path)
                    mesh = unreal.EditorAssetLibrary.duplicate_asset(base_mesh.get_path_name().split(".")[0], path)
                    slots = m.get("slots", {})
                    lookup = (lambda s, slots=slots: slots.get(s))
                if mesh is None:
                    C.error(f"cast: {m['name']} failed")
                    continue
                _assign_slots(mesh, lookup, instances, m["name"])
                _lods(mesh)
                unreal.EditorAssetLibrary.save_loaded_asset(mesh)
                meshes[cid] = mesh
    finally:
        _set_fbx_interchange(True)
    try:
        _prune_stale_cast(info, prune)
    except Exception as e:  # noqa: BLE001 - cleanup must not fail a successful import
        C.warn(f"cast: stale cleanup skipped after an internal error: {e}")
    _cleanup_abandoned_backups()
    for path in unreal.EditorAssetLibrary.list_assets(CHAR_DIR, recursive=False, include_folder=False):
        obj = unreal.EditorAssetLibrary.load_asset(path)
        if obj is not None and obj.get_class().get_name() in ("Material", "MaterialInstanceConstant", "Texture2D"):
            unreal.EditorAssetLibrary.delete_asset(path)
    C.log(f"cast: {len(meshes)} characters in {len(info.get('groups', {}))} skeleton groups")
    _apply_fab_locomotion()
    return meshes
