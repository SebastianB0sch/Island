"""Import generated SourceAssets (FBX meshes, PNG textures, WAV sounds) into /Game/DuelAcademy."""

import glob
import os

import unreal

from . import common as C

# texture categories -> (compression, sRGB, sampler)
#   _D detail maps      linear colour     (LinearColor sampler)
#   _N normal maps      normal map        (Normal sampler)
#   splat maps          masks             (Masks sampler)
#   colour textures     default sRGB      (Color sampler)
LINEAR = {"T_Noise"}
MASKS = {"T_TerrainSplatA", "T_TerrainSplatB"}
UI = {"T_IslandMap"}


def texture_kind(name):
    if name.endswith("_N") or name in ("T_WaterNormal", "T_FlatNormal"):
        return "normal"
    if name in MASKS or name.endswith("_ORM") or name.endswith("_R") or name == "T_DefaultMask":
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
    C.log(f"textures: {len(names)}")
    return names


# --------------------------------------------------------------------------- audio
def import_audio():
    C.ensure_dir(C.AUDIO_DIR)
    files = sorted(glob.glob(os.path.join(C.source_dir(), "Audio", "*.wav")))
    names = [os.path.splitext(os.path.basename(f))[0] for f in files]
    _import_tasks(files, C.AUDIO_DIR, names=names)
    loops = {"A_Ocean", "A_Wind", "A_Forest", "A_Volcano", "A_Waterfall", "A_HotSpring", "A_Crowd"}
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
    C.set_props(sm, combine_meshes=True, auto_generate_collision=False, generate_lightmap_u_vs=False,
                remove_degenerates=True, one_convex_hull_per_ucx=True)
    try:
        sm.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    except Exception:  # noqa: BLE001
        pass
    try:
        sm.set_editor_property("build_nanite", bool(nanite))
    except Exception:  # noqa: BLE001
        pass
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


def import_meshes(manifest, slow=None, only=None):
    """Import every FBX listed in assets.json. Returns {asset name: StaticMesh}."""
    groups = {}
    for e in manifest:
        if only and e["category"] not in only:
            continue
        groups.setdefault((e["folder"], bool(e.get("nanite"))), []).append(e)
    result = {}
    total = sum(len(v) for v in groups.values())
    done = 0
    _set_fbx_interchange(False)
    try:
        for (folder, nanite), entries in sorted(groups.items()):
            dest = f"{C.MESH_DIR}/{folder}"
            C.ensure_dir(dest)
            files = [os.path.join(C.source_dir(), e["file"]) for e in entries]
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
        data = unreal.EditorAssetLibrary.find_asset_data(path)
        cls = str(data.get_editor_property("asset_class_path").get_editor_property("asset_name")) if hasattr(data, "asset_class_path") else str(data.asset_class)
        if cls in ("Material", "MaterialInstanceConstant", "Texture2D"):
            if unreal.EditorAssetLibrary.delete_asset(path):
                removed += 1
    if removed:
        C.log(f"removed {removed} importer-generated materials/textures")


# --------------------------------------------------------------------------- skeletal student
CHAR_DIR = C.ROOT + "/Characters"
# cm/s the Walk / Run clips cover at play rate 1 after import (keep in sync with UDAAvatarComponent)
REF_SPEED = {"Walk": 300.0, "Run": 600.0}


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
            C.set_props(ad, remove_redundant_keys=True, import_bone_tracks=True, import_custom_attribute=False)
            ad.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            sd = ui.get_editor_property("skeletal_mesh_import_data")
            C.set_props(sd, import_morph_targets=False, update_skeleton_reference_pose=False)
            sd.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        except Exception:  # noqa: BLE001
            pass
    return ui


def _find_in(folder, cls_name, contains=None):
    for path in unreal.EditorAssetLibrary.list_assets(folder, recursive=False, include_folder=False):
        obj = unreal.EditorAssetLibrary.load_asset(path)
        if obj is not None and obj.get_class().get_name() == cls_name:
            if contains is None or contains.lower() in obj.get_name().lower():
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
    C.ensure_dir(CHAR_DIR)
    _set_fbx_interchange(False)
    try:
        _import_tasks([os.path.join(C.source_dir(), info["mesh"])], CHAR_DIR, _skeletal_options(), ["SK_Student"])
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
        for state, rel in sorted(info.get("anims", {}).items()):
            name = f"A_Student_{state}"
            _import_tasks([os.path.join(C.source_dir(), rel)], CHAR_DIR, _skeletal_options(skeleton), [name])
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
            ref = REF_SPEED.get(state)
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
    C.log(f"character: SK_Student + {len(info.get('anims', {}))} animations")
    return mesh
