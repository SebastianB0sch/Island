"""Assemble /Game/DuelAcademy/Maps/DuelAcademyIsland from Data/layout.json."""

import base64
import json
import os
import sys

import unreal

from . import common as C

EAS = None


def _fab_module(name):
    """Optional Fab swapper module from Tools/dai (None if the pipeline is absent)."""
    tools = os.path.join(os.path.dirname(C.project_dir()), "Tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        import importlib
        return importlib.import_module(f"dai.{name}")
    except Exception as exc:  # noqa: BLE001 - the level still builds with native assets
        C.warn(f"Fab {name} module unavailable: {exc}")
        return None


def fab_nature():
    """Optional Fab nature swapper (None if the pipeline is absent)."""
    return _fab_module("fab_nature")


def fab_props():
    """Optional Fab prop/rock swapper (None if the pipeline is absent)."""
    return _fab_module("fab_props")


def world_json(name):
    """Read a Content/Data/World JSON file (portals, anchors, spawns)."""
    path = os.path.join(C.project_dir(), "Content", "Data", "World", name)
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def eas():
    global EAS
    if EAS is None:
        EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return EAS


def les():
    return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)


def editor_world():
    try:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    except Exception:  # noqa: BLE001
        return unreal.EditorLevelLibrary.get_editor_world()


class Placer:
    def __init__(self, layout, meshes, materials, ysign=1.0):
        self.layout = layout
        self.meshes = meshes          # name -> StaticMesh
        self.materials = materials    # palette name -> MaterialInstance
        self.ysign = ysign            # +1 if the exported convention matched the import, -1 to mirror Y
        self.count = 0
        self._bounds_done = set()     # water meshes whose bounds were already extended

    # ------------------------------------------------------------------ helpers
    def loc(self, v):
        return unreal.Vector(float(v[0]), float(v[1]) * self.ysign, float(v[2]))

    def yaw(self, y):
        return float(y) * self.ysign

    def spawn(self, cls, loc, yaw=0.0, label=None, folder=None, pitch=0.0):
        actor = eas().spawn_actor_from_class(cls, loc, C.rot(yaw=yaw, pitch=pitch))
        if actor is None:
            return None
        tags = list(actor.get_editor_property("tags") or [])
        tags.append(C.GENERATED_TAG)
        actor.set_editor_property("tags", tags)
        if label:
            actor.set_actor_label(label)
        if folder:
            actor.set_folder_path(folder)
        self.count += 1
        return actor

    def mesh(self, name):
        # Fab content (installed locally by Tools/import_fab_nature.py) is
        # referenced by its full Unreal object path, not by a generated SM_ name.
        if name.startswith("/Game/"):
            m = C.load(name)
            if m is None and "." in name.rsplit("/", 1)[-1]:
                m = C.load(name.rsplit(".", 1)[0])
            return m
        m = self.meshes.get(name)
        if m is None:
            for folder in ("Props", "Doors", "Terrain", "Water", "Roads", "Characters"):
                m = C.load(f"{C.MESH_DIR}/{folder}/{name}")
                if m:
                    break
        return m

    @staticmethod
    def mesh_label(name):
        return name.rsplit("/", 1)[-1].split(".", 1)[0].replace("SM_", "")

    # ------------------------------------------------------------------ environment
    def environment(self, mpc):
        env = {}
        sun = self.spawn(unreal.DirectionalLight, unreal.Vector(0, 0, 50000), -40.0, "Sun", "Environment", pitch=-35.0)
        sc = sun.get_component_by_class(unreal.DirectionalLightComponent)
        sc.set_mobility(unreal.ComponentMobility.MOVABLE)
        C.set_props(sc, intensity=10.0, atmosphere_sun_light=True, atmosphere_sun_light_index=0,
                    light_color=unreal.Color(r=255, g=244, b=228, a=255), dynamic_shadow_distance_movable_light=60000.0,
                    light_source_angle=0.55)
        env["sun"] = sun
        moon = self.spawn(unreal.DirectionalLight, unreal.Vector(0, 0, 50000), 140.0, "Moon", "Environment", pitch=-40.0)
        mc = moon.get_component_by_class(unreal.DirectionalLightComponent)
        mc.set_mobility(unreal.ComponentMobility.MOVABLE)
        C.set_props(mc, intensity=0.6, atmosphere_sun_light=True, atmosphere_sun_light_index=1,
                    light_color=unreal.Color(r=170, g=190, b=255, a=255), cast_shadows=True)
        env["moon"] = moon
        self.spawn(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), 0.0, "SkyAtmosphere", "Environment")
        sky = self.spawn(unreal.SkyLight, unreal.Vector(0, 0, 20000), 0.0, "SkyLight", "Environment")
        slc = sky.get_component_by_class(unreal.SkyLightComponent)
        slc.set_mobility(unreal.ComponentMobility.MOVABLE)
        C.set_props(slc, real_time_capture=True, intensity=1.0)
        env["sky"] = sky
        fog = self.spawn(unreal.ExponentialHeightFog, unreal.Vector(0, 0, -500), 0.0, "HeightFog", "Environment")
        fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
        C.set_props(fc, fog_density=0.006, fog_height_falloff=0.08, enable_volumetric_fog=True,
                    volumetric_fog_scattering_distribution=0.4, start_distance=3000.0)
        env["fog"] = fog
        try:
            self.spawn(unreal.VolumetricCloud, unreal.Vector(0, 0, 0), 0.0, "VolumetricClouds", "Environment")
        except Exception as e:  # noqa: BLE001
            C.warn(f"volumetric clouds unavailable: {e}")
        ppv = self.spawn(unreal.PostProcessVolume, unreal.Vector(0, 0, 0), 0.0, "PostProcess", "Environment")
        C.set_props(ppv, unbound=True)
        try:
            s = ppv.get_editor_property("settings")
            for k, v in (("auto_exposure_min_brightness", -1.5), ("auto_exposure_max_brightness", 14.0),
                         ("auto_exposure_bias", 0.6), ("bloom_intensity", 0.55), ("vignette_intensity", 0.25),
                         ("auto_exposure_speed_up", 2.0), ("auto_exposure_speed_down", 1.5)):
                try:
                    s.set_editor_property("override_" + k, True)
                    s.set_editor_property(k, v)
                except Exception:  # noqa: BLE001
                    pass
            # anime cast cel banding (materials.build_cel_post; stencil 1 = cast, set by UDAAvatarComponent)
            pp = C.load(f"{C.MAT_DIR}/PP_DA_Cel")
            if pp is not None:
                try:
                    wb = unreal.WeightedBlendables()
                    wb.set_editor_property("array", [unreal.WeightedBlendable(weight=1.0, object=pp)])
                    s.set_editor_property("weighted_blendables", wb)
                except Exception as e:  # noqa: BLE001
                    C.warn(f"post process: cel blendable: {e}")
            else:
                C.warn("post process: PP_DA_Cel missing (build the materials first); cast renders without cel banding")
            ppv.set_editor_property("settings", s)
        except Exception as e:  # noqa: BLE001
            C.warn(f"post process settings: {e}")
        return env

    def manager(self, env, mpc, map_tex):
        cls = C.native_class("DAIslandManager")
        if cls is None:
            C.error("DAIslandManager class missing - is the DuelAcademyIsland C++ module compiled?")
            return None
        w = self.layout["world"]
        m = self.spawn(cls, unreal.Vector(0, 0, 10000), 0.0, "IslandManager", "Environment")
        lake = w["lake"]
        # strict: a silently-failed property leaves the manager with a null sun / map /
        # lake centre, which breaks the day-night cycle and the minimap at runtime.
        C.set_props(m, sun=env.get("sun"), moon=env.get("moon"), sky_light=env.get("sky"), height_fog=env.get("fog"),
                    parameter_collection=mpc, hour=float(self.layout["environment"]["start_hour"]),
                    day_length_minutes=float(self.layout["environment"]["day_minutes"]), map_texture=map_tex,
                    map_min=unreal.Vector2D(w["map"]["min"][0], w["map"]["min"][1]),
                    map_max=unreal.Vector2D(w["map"]["max"][0], w["map"]["max"][1]),
                    sea_level=float(w["sea_level"]), lake_center=self.loc(lake["center"]),
                    lake_radii=unreal.Vector2D(lake["radii"][0], lake["radii"][1]),
                    lake_yaw=self.yaw(lake["rot"]), lake_level=float(w["lake_level"]), strict=True)
        if self.ysign < 0:
            # the map texture's north edge is now at +Y
            C.set_props(m, map_min=unreal.Vector2D(w["map"]["min"][0], w["map"]["max"][1]),
                        map_max=unreal.Vector2D(w["map"]["max"][0], w["map"]["min"][1]), strict=True)
        self.water(m)
        return m

    # ------------------------------------------------------------------ waves / rivers (Data/water.json)
    @staticmethod
    def pack_waves(waves, ysign=1.0):
        """water.json wave list -> the flat float list ADAIslandManager.SetWaveSet takes (7 per wave:
        dir x, dir y, wavelength, amplitude, steepness, speed, phase); at most 6 waves, bad entries skipped."""
        out = []
        for w in list(waves or [])[:6]:
            try:
                out += [float(w["dir"][0]), float(w["dir"][1]) * ysign, float(w["wavelength"]), float(w["amplitude"]),
                        float(w.get("steepness", 0.0)), float(w.get("speed", 0.0)), float(w.get("phase", 0.0))]
            except (KeyError, IndexError, TypeError, ValueError):
                continue
        return out

    @staticmethod
    def mirror_mask(data, size):
        """Base64 wave mask with its rows reversed (row 0 = north becomes row 0 = south): the mask of a level
        built with a mirrored Y axis. Returns None when the data does not hold size * size bytes."""
        raw = base64.b64decode(data)
        if size <= 0 or len(raw) != size * size:
            return None
        rows = [raw[i * size:(i + 1) * size] for i in range(size)]
        return base64.b64encode(b"".join(reversed(rows))).decode("ascii")

    def water(self, manager):
        """Wave sets, the sea's amplitude mask and the rivers -> ADAIslandManager, so gameplay (buoyancy,
        swimming, wading) sees the same surface M_DA_Water draws. Optional: without Data/water.json the
        manager keeps its flat sea and lake."""
        try:
            data = C.load_json("water.json")
        except Exception:  # noqa: BLE001 - SourceAssets from before the water upgrade
            C.log("water.json not found: flat water (no waves, no rivers)")
            return False
        if manager is None or not hasattr(manager, "set_wave_set"):
            C.warn("water.json present but ADAIslandManager has no wave API - rebuild the C++ module")
            return False
        try:
            manager.clear_water_data()
            ocean, lake = data.get("ocean") or {}, data.get("lake") or {}
            manager.set_wave_set(False, self.pack_waves(ocean.get("waves"), self.ysign))
            manager.set_wave_set(True, self.pack_waves(lake.get("waves"), self.ysign))
            fade = ocean.get("fade")
            if isinstance(fade, (list, tuple)) and len(fade) == 2:
                C.set_props(manager, wave_fade_start=float(fade[0]), wave_fade_end=float(fade[1]))
            mask = data.get("wave_mask") or {}
            if mask.get("data"):
                size = int(mask.get("size", 0))
                lo, hi = mask.get("min", [-153600.0, -153600.0]), mask.get("max", [153600.0, 153600.0])
                encoded = mask["data"]
                y0, y1 = float(lo[1]), float(hi[1])
                if self.ysign < 0:
                    # mirrored level: world y -> -y, so the rows run the other way and the bounds swap
                    encoded = self.mirror_mask(encoded, size)
                    y0, y1 = -float(hi[1]), -float(lo[1])
                if not encoded or not manager.set_wave_mask_base64(encoded, size, unreal.Vector2D(float(lo[0]), y0),
                                                                   unreal.Vector2D(float(hi[0]), y1)):
                    C.warn("water.json: wave mask rejected (size / data mismatch) - the sea keeps full waves")
            rivers = 0
            # the lake's arms reach beyond the ellipse the manager tests for the lake: they are added like the
            # rivers (a flat sheet at the lake's level), so gameplay finds water wherever M_LakeWater is drawn
            for river in list(data.get("rivers") or []) + list(data.get("inlets") or []):
                packed = []
                for p in river.get("points") or []:
                    if len(p) >= 4:
                        packed += [float(p[0]), float(p[1]) * self.ysign, float(p[2]), float(p[3])]
                if packed:
                    manager.add_river(str(river.get("id", f"river_{rivers}")), packed)
                    rivers += 1
            C.log(f"water: {len(ocean.get('waves') or [])} sea waves, {len(lake.get('waves') or [])} lake waves, "
                  f"{rivers} rivers and lake arms")
            return True
        except Exception as e:  # noqa: BLE001 - never lose the level over the water data
            C.warn(f"water.json could not be applied ({e}); the level keeps flat water")
            return False

    # ------------------------------------------------------------------ static meshes
    def statics(self):
        for e in self.layout["static"]:
            mesh = self.mesh(e["mesh"])
            if mesh is None:
                C.warn(f"missing mesh {e['mesh']}")
                continue
            a = self.spawn(unreal.StaticMeshActor, self.loc(e["loc"]), self.yaw(e["yaw"]), e.get("label"),
                           f"Island/{e.get('group', 'misc')}")
            smc = a.static_mesh_component
            smc.set_static_mesh(mesh)
            smc.set_mobility(unreal.ComponentMobility.STATIC)
            if e.get("collision") == "none":
                smc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                if e.get("group") == "water":
                    C.set_props(smc, cast_shadow=False)
                    self.extend_water_bounds(mesh, e["mesh"])
            if e.get("hidden"):
                # collision-only furniture boxes (Tools/dai/collision.py): never drawn, block people only -
                # cameras and visibility traces pass through them
                C.set_props(smc, cast_shadow=False, hidden_in_game=True, visible=False)
                a.set_actor_hidden_in_game(True)
                try:
                    smc.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA,
                                                          unreal.CollisionResponseType.ECR_IGNORE)
                    smc.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,
                                                          unreal.CollisionResponseType.ECR_IGNORE)
                except Exception as ex:  # noqa: BLE001
                    C.warn(f"{e['mesh']}: collision channels: {ex}")

    def extend_water_bounds(self, mesh, name):
        """The sea and the lake are displaced by their material (Gerstner waves, up to ~1 m): grow the mesh
        bounds by 2 m so a flat sheet seen edge-on is not culled while its crests are still in view."""
        if name in self._bounds_done or not any(k in name for k in ("Ocean", "Lake")):
            return
        self._bounds_done.add(name)
        try:
            grow = unreal.Vector(200.0, 200.0, 200.0)
            mesh.set_editor_property("positive_bounds_extension", grow)
            mesh.set_editor_property("negative_bounds_extension", grow)
        except Exception as ex:  # noqa: BLE001 - cosmetic: worst case a wave crest pops at the screen edge
            C.warn(f"{name}: bounds extension not set: {ex}")

    def floating(self):
        cls = C.native_class("DAFloatingActor")
        for e in self.layout["floating"]:
            mesh = self.mesh(e["mesh"])
            if mesh is None or cls is None:
                continue
            a = self.spawn(cls, self.loc(e["loc"]), self.yaw(e["yaw"]), e["mesh"].replace("SM_", "Floating_"), "Island/water_craft")
            a.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(mesh)
            s = float(e.get("scale", 1.0))
            a.set_actor_scale3d(unreal.Vector(s, s, s))
            C.set_props(a, amplitude=float(e.get("amplitude", 10.0)), period=float(e.get("period", 5.0)),
                        sway=float(e.get("sway", 1.0)))

    # ------------------------------------------------------------------ instances
    def instances(self, slow=None):
        cls = C.native_class("DAInstancedScatter")
        groups = dict(self.layout["instances"])
        fab_n = fab_nature()
        fab_p = fab_props()
        root = os.path.dirname(C.project_dir())
        use_nature = fab_n is not None and fab_n.available(root)
        use_props = fab_p is not None and fab_p.available(root)
        if use_nature or use_props:
            # Drop any Fab groups left by an older translated layout, so a
            # rebuild cannot place the same asset twice.
            fab_prefixes = ("/Game/StyleHex_Studio", "/Game/Stylized_PBR_Nature", "/Game/TropicalGardenLounge",
                            "/Game/CollegeRaimon")
            for stale in [k for k, v in groups.items() if str(v.get("mesh", "")).startswith(fab_prefixes)]:
                groups.pop(stale, None)
        if use_nature:
            native = {k: v["items"] for k, v in groups.items() if fab_n.is_replaced(k)}
            fab_groups, fab_stats = fab_n.translate(native)
            for name in native:
                groups.pop(name, None)
            groups.update(fab_groups)
            if fab_stats:
                C.log(f"Fab nature: {sum(s['count'] for s in fab_stats.values())} native instances -> "
                      f"{len(fab_groups)} Fab meshes")
        elif fab_n is not None:
            C.log("Fab nature packs not installed; using the native procedural vegetation")
        if use_props:
            native = {k: v for k, v in groups.items() if fab_p.is_replaced(k)}
            fab_groups, fab_stats = fab_p.translate(native)
            for name in native:
                groups.pop(name, None)
            groups.update(fab_groups)
            if fab_stats:
                C.log(f"Fab props/rocks: {sum(s['count'] for s in fab_stats.values())} native instances -> "
                      f"{len(fab_groups)} Fab meshes")
        elif fab_p is not None:
            C.log("Fab prop/rock packs not installed; using the native/third-party props")
        for name, g in groups.items():
            mesh_name = g.get("mesh", name)
            mesh = self.mesh(mesh_name)
            if mesh is None:
                C.warn(f"missing instanced mesh {mesh_name}")
                continue
            items = g["items"]
            label = g.get("label") or f"Scatter_{self.mesh_label(mesh_name)}"
            if slow:
                slow.enter_progress_frame(1, f"Scattering {label} ({len(items)})")
            rot = g.get("rot") or (0.0, 0.0, 0.0)
            xforms = []
            for x, y, z, yaw, s in items:
                xforms.append(unreal.Transform(unreal.Vector(x, y * self.ysign, z),
                                               C.rot(yaw=yaw * self.ysign + float(rot[1]),
                                                     pitch=float(rot[0]), roll=float(rot[2])),
                                               unreal.Vector(s, s, s)))
            folder = g.get("folder")
            if not folder:
                folder = "Island/vegetation" if any(k in mesh_name for k in ("Tree", "Palm", "Bush", "Fern", "Grass", "Flower", "Rock")) else "Island/props"
            if cls is not None:
                a = self.spawn(cls, unreal.Vector(0, 0, 0), 0.0, label, folder)
                a.set_instances(mesh, xforms, int(g["cull"][0]), int(g["cull"][1]), bool(g["collision"]), bool(g["shadow"]))
            else:
                # fallback without the C++ module: individual actors (slow, props only)
                if len(xforms) > 600:
                    continue
                for i, t in enumerate(xforms):
                    a = self.spawn(unreal.StaticMeshActor, t.translation, 0.0, None, folder)
                    a.set_actor_transform(t, False, False)
                    a.static_mesh_component.set_static_mesh(mesh)

    # ------------------------------------------------------------------ lights
    def lights(self):
        for i, L in enumerate(self.layout["lights"]):
            spot = L.get("spot")
            cls = unreal.SpotLight if spot else unreal.PointLight
            yaw = self.yaw(spot["yaw"]) if spot else 0.0
            pitch = float(spot["pitch"]) if spot else 0.0
            a = self.spawn(cls, self.loc(L["loc"]), yaw, None, "Island/lights", pitch=pitch)
            lc = a.get_component_by_class(unreal.PointLightComponent)
            lc.set_mobility(unreal.ComponentMobility.MOVABLE)
            try:
                lc.set_intensity_units(unreal.LightUnits.UNITLESS)
            except Exception:  # noqa: BLE001
                pass
            lc.set_intensity(float(L["intensity"]))
            lc.set_attenuation_radius(float(L["radius"]))
            lc.set_light_color(C.lc(L["color"]), True)
            lc.set_cast_shadows(bool(L.get("shadows", False)))
            C.set_props(lc, source_radius=8.0)
            if spot:
                C.set_props(lc, inner_cone_angle=float(spot["cone"]) * 0.5, outer_cone_angle=float(spot["cone"]))
            if L.get("night_only"):
                tags = list(a.get_editor_property("tags") or [])
                tags.append("DA_NightOnly")
                a.set_editor_property("tags", tags)
                lc.set_visibility(False)

    # ------------------------------------------------------------------ text / gameplay actors
    def texts(self):
        for T in self.layout["texts"]:
            a = self.spawn(unreal.TextRenderActor, self.loc(T["loc"]), self.yaw(T["yaw"]) + 90.0, None, "Island/signs")
            tr = a.get_component_by_class(unreal.TextRenderComponent)
            tr.set_text(T["text"])
            tr.set_world_size(float(T["size"]))
            c = T.get("color", [1, 1, 1])
            tr.set_text_render_color(unreal.Color(r=int(min(1.0, c[0]) * 255), g=int(min(1.0, c[1]) * 255),
                                                  b=int(min(1.0, c[2]) * 255), a=255))
            tr.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
            try:
                tr.set_vertical_alignment(unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
            except Exception:  # noqa: BLE001
                pass

    def zones(self):
        cls = C.native_class("DALocationVolume")
        if cls is None:
            return
        for i, z in enumerate(self.layout["zones"]):
            a = self.spawn(cls, self.loc(z["center"]), self.yaw(z.get("yaw", 0.0)), f"Zone_{z['id']}", "Gameplay/zones")
            C.set_props(a, location_id=z["id"], display_name=z["name"], subtitle=z["subtitle"], description=z["desc"],
                        theme_color=C.lc(z["color"]), zone_extent=C.vec(z["extent"]), sort_order=i,
                        spawn_location=self.loc(z["spawn"]["loc"]), spawn_yaw=self.yaw(z["spawn"]["yaw"]),
                        parent_id=z.get("parent", ""))
            box = a.get_component_by_class(unreal.BoxComponent)
            if box:
                box.set_box_extent(C.vec(z["extent"]), False)

    def interactables(self):
        cls = C.native_class("DAInteractable")
        if cls is None:
            return
        kinds = {"sign": "SIGN", "card_shop": "CARD_SHOP", "duel_field": "DUEL_FIELD", "info": "INFO",
                 "room_bed": "ROOM_BED", "walk_home": "WALK_HOME"}
        enum = getattr(unreal, "DAInteractKind", None)
        for it in self.layout["interacts"]:
            a = self.spawn(cls, self.loc(it["loc"]), self.yaw(it["yaw"]), f"Interact_{it.get('title', 'Sign')}"[:60],
                           f"Gameplay/{it.get('group', 'misc')}")
            if enum is not None:
                C.set_props(a, kind=getattr(enum, kinds.get(it["kind"], "SIGN")))
            C.set_props(a, title=it.get("title", ""), text=it.get("text", ""), radius=float(it.get("radius", 300.0)))

    def emitters(self):
        cls = C.native_class("DAEmitter")
        enum = getattr(unreal, "DAEmitterKind", None)
        if cls is None or enum is None:
            return
        for e in self.layout["emitters"]:
            a = self.spawn(cls, self.loc(e["loc"]), self.yaw(e.get("yaw", 0.0)), f"Emitter_{e['kind']}", "Gameplay/fx")
            C.set_props(a, kind=getattr(enum, e["kind"].upper(), enum.STEAM), effect_scale=float(e["scale"]),
                        rate=float(e.get("rate", 1.0)))
            if e.get("ring"):       # fountain spray: start on a circle (or at points on it) instead of a disc
                C.set_props(a, ring=float(e["ring"]), ring_points=int(e.get("points", 0)),
                            ring_angle=float(e.get("angle0", 0.0)))
            if e["kind"] == "jet":  # fountain jet: ballistic droplets from the nozzle down to the pool
                vel = e.get("vel") or [0.0, 0.0, 600.0]
                C.set_props(a, jet_velocity=unreal.Vector(float(vel[0]), float(vel[1]) * self.ysign, float(vel[2])),
                            floor_z=float(e.get("floor", e["loc"][2])), jet_spread=float(e.get("spread", 2.5)))

    def audio(self):
        cls = C.native_class("DAAmbientSound")
        if cls is None:
            return
        for s in self.layout["audio"]:
            snd = C.load(f"{C.AUDIO_DIR}/{s['sound']}")
            if snd is None:
                continue
            a = self.spawn(cls, self.loc(s["loc"]), 0.0, f"Ambience_{s['sound']}", "Gameplay/audio")
            C.set_props(a, sound=snd, radius=float(s["radius"]), volume=float(s.get("volume", 1.0)))

    def npcs(self):
        cls = C.native_class("DAStudentNPC")
        enum = getattr(unreal, "DADorm", None)
        if cls is None or enum is None:
            return
        try:
            cast = C.load_json("cast.json").get("meshes", {})
        except Exception:  # noqa: BLE001
            cast = {}
        for n in self.layout["npcs"]:
            c = cast.get(n.get("cast", ""), {})
            label = n.get("name", f"Student_{n['dorm']}").replace(" ", "_").replace(".", "")
            a = self.spawn(cls, self.loc(n["loc"]), self.yaw(n["yaw"]), label, "Gameplay/npcs")
            C.set_props(a, dorm=getattr(enum, n["dorm"].upper(), enum.SLIFER), wander_radius=float(n.get("wander", 800.0)))
            if "points" in n:      # precomputed clear strolls (Tools/dai/placement.py); none = stands still
                C.set_props(a, wander_points=[self.loc(p) for p in n["points"]], wander_points_only=True)
            if c:
                # anime cast member (see Tools/dai/anime): mesh, skeleton group, name and dialogue
                C.set_props(a, cast_mesh=c["name"], anim_group=c["group"], dorm_tint=bool(n.get("tint", True)),
                            body_scale=float(n.get("scale", c.get("scale", 1.0))))
            if n.get("name"):
                C.set_props(a, display_name=n["name"], lines=list(n.get("lines", [])))
            if n.get("fab_look"):
                # optional licensed Fab Anime Character Pack puppet (local-only)
                C.set_props(a, fab_look=n["fab_look"])
            if n.get("hair"):
                # stable per-NPC hair colour from the ambient roster
                C.set_props(a, hair_color=C.lc(n["hair"]), override_hair_color=True)

    def world_actors(self):
        """Spawn the A08 world data: portals, anchors, interior nav, NPC spawn points and director."""
        self.portals()
        self.scene_anchors()
        self.interior_nav()
        self.story_interactables()
        self.npc_spawn_points()
        self.npc_director()

    def story_interactables(self):
        """World hooks for E30 (room weekend) and E31 (walk home)."""
        cls = C.native_class("DAInteractable")
        enum = getattr(unreal, "DAInteractKind", None)
        if cls is None or enum is None:
            return
        try:
            anchors = {a["id"]: a for a in world_json("anchors.json").get("anchors", [])}
        except Exception as e:  # noqa: BLE001
            C.warn(f"story interactable anchors unavailable: {e}")
            return
        hooks = [
            ("slifer_player_room_bed", "ROOM_BED", "Your Bed",
             "Spend the weekend in your room. Three weekends make your friends worry.", 220.0),
            ("ra_player_room_bed", "ROOM_BED", "Your Bed",
             "Spend the weekend in your room. Three weekends make your friends worry.", 220.0),
            ("obelisk_player_room_bed", "ROOM_BED", "Your Bed",
             "Spend the weekend in your room. Three weekends make your friends worry.", 220.0),
            ("harbor_dock", "WALK_HOME", "Walk Home",
             "Walk back to the dorm with a friend. Three walks with the same friend will matter.", 300.0),
        ]
        for anchor_id, kind_name, title, text, radius in hooks:
            anchor = anchors.get(anchor_id)
            if anchor is None:
                C.warn(f"story hook anchor {anchor_id} missing")
                continue
            a = self.spawn(cls, self.loc(anchor["position_ue"]), self.yaw(anchor.get("yaw", 0.0)),
                           f"Story_{anchor_id}", "Gameplay/story")
            if a is None:
                continue
            C.set_props(a, kind=getattr(enum, kind_name), title=title, text=text, radius=radius,
                        show_marker=False)

    def portals(self):
        cls = C.native_class("DAInteriorPortal")
        if cls is None:
            C.warn("ADAInteriorPortal missing - interior portals skipped")
            return
        try:
            data = world_json("portals.json")
        except Exception as e:  # noqa: BLE001
            C.warn(f"portals.json unavailable: {e}")
            return
        for p in data.get("portals", []):
            a = self.spawn(cls, self.loc(p["location_ue"]), self.yaw(p.get("yaw", 0.0)),
                           f"Portal_{p['id']}", "Gameplay/portals")
            if a is None:
                continue
            lock = p.get("lock", {}) or {}
            fade = p.get("fade", {}) or {}
            C.set_props(a,
                        portal_id=p.get("id", ""),
                        interior_id=p.get("interior_id", ""),
                        target_portal_id=p.get("target_portal_id", ""),
                        target_location=self.loc(p.get("target_location_ue", [0, 0, 0])),
                        target_yaw=self.yaw(p.get("target_yaw", 0.0)),
                        trigger_extent=C.vec(p.get("trigger_extent", [110, 110, 120])),
                        auto_trigger=bool(p.get("auto_trigger", True)),
                        interactable=bool(p.get("interactable", True)),
                        display_name=p.get("display_name", "Door"),
                        prompt=p.get("prompt", "Enter"),
                        cooldown_seconds=float(p.get("cooldown", 1.5)),
                        fade_out_seconds=float(fade.get("out", 0.35)),
                        fade_in_seconds=float(fade.get("in", 0.35)),
                        fade_color=C.lc(fade.get("color", [0, 0, 0, 1])),
                        locked=bool(lock.get("locked", False)),
                        required_flag=str(lock.get("required_flag", "")),
                        fail_closed_when_flag_query_missing=bool(lock.get("fail_closed", False)),
                        lock_reason=str(lock.get("reason", "This door is locked.")),
                        return_portal=bool(p.get("return_portal", False)))

    def scene_anchors(self):
        cls = C.native_class("DASceneAnchor")
        if cls is None:
            C.warn("ADASceneAnchor missing - scene anchors skipped")
            return
        try:
            data = world_json("anchors.json")
        except Exception as e:  # noqa: BLE001
            C.warn(f"anchors.json unavailable: {e}")
            return
        enum = getattr(unreal, "DASceneAnchorKind", None)
        for entry in data.get("anchors", []):
            a = self.spawn(cls, self.loc(entry["position_ue"]), self.yaw(entry.get("yaw", 0.0)),
                           f"Anchor_{entry['id']}", "Gameplay/anchors")
            if a is None:
                continue
            kind_name = str(entry.get("kind", "camera")).upper().replace("-", "_")
            default_kind = getattr(enum, "CAMERA", None) if enum else None
            kind = getattr(enum, kind_name, default_kind) if enum else None
            look_at = entry.get("look_at_ue")
            props = dict(anchor_id=entry.get("id", ""),
                         fov=float(entry.get("fov", 50.0)),
                         use_look_at=bool(look_at),
                         anchor_tags=list(entry.get("tags", [])),
                         description=entry.get("notes", ""))
            if kind is not None:
                props["kind"] = kind
            if look_at:
                props["look_at_target"] = self.loc(look_at)
            C.set_props(a, **props)

    def interior_nav(self):
        """Place one NavMeshBoundsVolume over each generated interior cell.

        The cells sit far below the island, so without an explicit volume the
        runtime navmesh would stop at the exterior terrain. Each volume covers
        the cell's bounds_ue plus a 1.5 m XY margin and 2.5 m of Z headroom,
        which keeps the floor, door path and every spawn anchor inside.
        """
        try:
            data = world_json("interiors.json")
        except Exception as e:  # noqa: BLE001
            C.warn(f"interiors.json unavailable for interior nav: {e}")
            return
        cls = getattr(unreal, "NavMeshBoundsVolume", None)
        if cls is None:
            C.warn("NavMeshBoundsVolume missing - interior nav skipped")
            return

        placed = 0
        for cell in data.get("cells", []):
            box = cell.get("bounds_ue")
            if not isinstance(box, (list, tuple)) or len(box) != 6:
                C.warn(f"interior nav: cell {cell.get('id')} has no valid bounds_ue")
                continue
            center = unreal.Vector((box[0] + box[3]) * 0.5, (box[1] + box[4]) * 0.5, (box[2] + box[5]) * 0.5)
            desired = unreal.Vector((box[3] - box[0]) * 0.5 + 150.0,
                                    (box[4] - box[1]) * 0.5 + 150.0,
                                    (box[5] - box[2]) * 0.5 + 250.0)
            a = self.spawn(cls, center, 0.0, f"Nav_{cell['id']}", "Gameplay/nav")
            if a is None:
                continue

            try:
                origin, extent = a.get_actor_bounds(False)
            except Exception as e:  # noqa: BLE001
                C.warn(f"interior nav: {cell['id']} bounds query failed: {e}")
                origin, extent = center, unreal.Vector(100.0, 100.0, 100.0)
            if extent.x < 1.0 or extent.y < 1.0 or extent.z < 1.0:
                # A class-spawned volume can report an empty brush until its
                # default cube is realized; UE's default volume extent is 100.
                origin, extent = center, unreal.Vector(100.0, 100.0, 100.0)

            scale = unreal.Vector(desired.x / extent.x, desired.y / extent.y, desired.z / extent.z)
            a.set_actor_scale3d(scale)
            offset = origin - a.get_actor_location()
            offset = unreal.Vector(offset.x * scale.x, offset.y * scale.y, offset.z * scale.z)
            a.set_actor_location(center - offset, False, False)
            placed += 1

        C.log(f"placed {placed} interior nav bounds volumes")

    def npc_spawn_points(self):
        cls = C.native_class("DANpcSpawnPoint")
        if cls is None:
            C.warn("ADANpcSpawnPoint missing - schedule spawns skipped")
            return
        try:
            anchors = {a["id"]: a for a in world_json("anchors.json").get("anchors", [])}
            data = world_json("spawns.json")
        except Exception as e:  # noqa: BLE001
            C.warn(f"spawns.json unavailable: {e}")
            return
        try:
            cast = C.load_json("cast.json").get("meshes", {})
        except Exception as e:  # noqa: BLE001
            C.warn(f"cast.json unavailable for NPC looks: {e}")
            cast = {}
        dorm_enum = getattr(unreal, "DADorm", None)
        for s in data.get("spawns", []):
            anchor = anchors.get(s.get("anchor_id"))
            if anchor is None:
                C.warn(f"spawn {s.get('id')} references missing anchor {s.get('anchor_id')}")
                continue
            a = self.spawn(cls, self.loc(anchor["position_ue"]), self.yaw(anchor.get("yaw", 0.0)),
                           f"Spawn_{s['id']}", "Gameplay/npcs")
            if a is None:
                continue
            default_dorm = getattr(dorm_enum, "SLIFER", None) if dorm_enum else None
            dorm = getattr(dorm_enum, str(s.get("dorm", "slifer")).upper(), default_dorm) if dorm_enum else None
            props = dict(spawn_point_id=s.get("id", ""),
                         schedule_id=s.get("schedule_id", ""),
                         schedule_tags=list(s.get("schedule_tags", [])),
                         spawn_role=s.get("role", "student"),
                         wander_radius=float(s.get("wander_radius_cm", 500.0)),
                         event_override=s.get("event_override", ""),
                         enabled=bool(s.get("enabled", True)),
                         event_only=bool(s.get("event_only", False)),
                         spawn_on_begin_play=bool(s.get("spawn_on_begin_play", False)),
                         spawn_z_offset=float(s.get("spawn_z_offset_cm", 90.0)),
                         display_name=s.get("display_name", ""))
            if dorm is not None:
                props["dorm"] = dorm
            cast_id = s.get("cast", "")
            look = cast.get(cast_id, {})
            if look:
                props.update(cast_mesh=look["name"], anim_group=look["group"],
                             dorm_tint=bool(s.get("tint", True)),
                             body_scale=float(s.get("scale", look.get("scale", 1.0))))
            if s.get("lines"):
                props["lines"] = list(s["lines"])
            if s.get("fab_look"):
                props["fab_look"] = s["fab_look"]
            if s.get("hair"):
                props["hair_color"] = C.lc(s["hair"])
                props["override_hair_color"] = True
            C.set_props(a, **props)

    def npc_director(self):
        cls = C.native_class("DANpcDirector")
        if cls is None:
            C.warn("ADANpcDirector missing - schedule director skipped")
            return
        a = self.spawn(cls, unreal.Vector(0, 0, 0), 0.0, "NPCDirector", "Gameplay/npcs")
        if a is None:
            return
        npc_cls = C.native_class("DAStudentNPC")
        props = dict(auto_register_spawn_points=True, auto_apply_on_begin_play=False)
        if npc_cls is not None:
            props["default_npc_class"] = npc_cls
        C.set_props(a, **props)

    def specials(self):
        beam_cls = C.native_class("DALighthouseBeam")
        spinner_cls = C.native_class("DASpinner")
        flock_cls = C.native_class("DABirdFlock")
        bird_enum = getattr(unreal, "DABirdKind", None)
        axes = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
        for s in self.layout["specials"]:
            props = s.get("props") or {}
            if s["kind"] == "lighthouse_beam" and beam_cls is not None:
                a = self.spawn(beam_cls, self.loc(s["loc"]), self.yaw(s["yaw"]), "LighthouseBeam", "Gameplay/fx")
                if "beam_length" in props:
                    C.set_props(a, beam_length=float(props["beam_length"]))
            elif s["kind"] == "spinner" and spinner_cls is not None:
                # a mesh turning about one of its own axes (water wheel, windmill sails)
                name = str(props.get("mesh", ""))
                mesh = self.mesh(name)
                if mesh is None and props.get("folder"):
                    mesh = C.load(f"{C.MESH_DIR}/{props['folder']}/{name}")
                if mesh is None:
                    C.warn(f"spinner: missing mesh {name}")
                    continue
                a = self.spawn(spinner_cls, self.loc(s["loc"]), self.yaw(s.get("yaw", 0.0)),
                               f"Spinner_{self.mesh_label(name)}", f"Island/{s.get('group', 'misc')}")
                if a is None:
                    continue
                a.get_component_by_class(unreal.StaticMeshComponent).set_static_mesh(mesh)
                ax = axes.get(str(props.get("axis", "y")).lower(), axes["y"])
                # a mirrored level turns the other way round
                C.set_props(a, axis=unreal.Vector(*ax), rpm=float(props.get("rpm", 6.0)) * self.ysign)
            elif s["kind"] == "birds" and flock_cls is not None:
                # procedural flock circling inside a cylinder (no assets)
                a = self.spawn(flock_cls, self.loc(s["loc"]), 0.0, f"Birds_{props.get('kind', 'gull')}", "Gameplay/fx")
                if a is None:
                    continue
                C.set_props(a, count=int(props.get("count", 10)), radius=float(props.get("radius", 6000.0)),
                            height=float(props.get("height", 2500.0)))
                if bird_enum is not None:
                    C.set_props(a, kind=getattr(bird_enum, str(props.get("kind", "gull")).upper(), bird_enum.GULL))

    def doors(self):
        """One ADADoor per doorway (automatic swing / slide doors, see DAWorldActors.h)."""
        cls = C.native_class("DADoor")
        enum = getattr(unreal, "DADoorMode", None)
        if cls is None:
            C.warn("DADoor class missing - doorways stay open")
            return
        n = 0
        for d in self.layout.get("doors", []):
            mesh = self.mesh(d["mesh"])
            if mesh is None:
                C.warn(f"missing door leaf {d['mesh']}")
                continue
            a = self.spawn(cls, self.loc(d["loc"]), self.yaw(d["yaw"]), f"Door_{d.get('group', 'misc')}_{n:03d}",
                           f"Island/{d.get('group', 'misc')}/doors")
            if a is None:
                continue
            # Y mirrored import (ysign -1) flips which side is outside
            swing = int(d.get("swing", 0)) * (1 if self.ysign > 0 else -1)
            C.set_props(a, leaf_mesh=mesh, width=float(d["width"]), height=float(d["height"]), double=bool(d["double"]),
                        swing_side=swing)
            if enum is not None:
                C.set_props(a, mode=enum.SLIDE if d.get("mode") == "slide" else enum.SWING)
            try:
                a.refresh_door()
            except Exception as e:  # noqa: BLE001
                C.warn(f"door refresh: {e}")
            n += 1
        C.log(f"doors: {n}")

    def player_start(self):
        ps = self.layout["player_start"]
        a = self.spawn(unreal.PlayerStart, self.loc(ps["loc"]), self.yaw(ps["yaw"]), "PlayerStart_Harbor", "Gameplay")
        return a


def clear_generated():
    removed = 0
    for a in eas().get_all_level_actors():
        try:
            if C.GENERATED_TAG in [str(t) for t in a.get_editor_property("tags")]:
                eas().destroy_actor(a)
                removed += 1
        except Exception:  # noqa: BLE001
            pass
    if removed:
        C.log(f"removed {removed} previously generated actors")


def open_or_create_map():
    C.ensure_dir(C.ROOT + "/Maps")
    if C.exists(C.MAP_PATH):
        loaded = les().load_level(C.MAP_PATH)
        if loaded is False:
            raise RuntimeError(f"could not load {C.MAP_PATH}")
        clear_generated()
        return False
    try:
        ok = les().new_level(C.MAP_PATH)
    except TypeError:
        ok = les().new_level(C.MAP_PATH, False)
    if not ok:
        raise RuntimeError(f"could not create {C.MAP_PATH}")
    return True


def set_world_settings():
    world = editor_world()
    try:
        ws = world.get_world_settings()
        gm = C.native_class("DAGameMode")
        if gm is not None:
            C.set_props(ws, default_game_mode=gm)
        C.set_props(ws, kill_z=-50000.0)
    except Exception as e:  # noqa: BLE001
        C.warn(f"world settings: {e}")


def save():
    """Save the map, raising when the editor subsystem reports failure.

    The headless CLI turns a False / None result of ``save_current_level`` into
    a build failure; without this check the build would log success while the
    replaced actors exist only in the editor's unsaved state.
    """
    result = les().save_current_level()
    if not result:
        raise RuntimeError(f"map save failed ({C.MAP_PATH}): save_current_level -> {result!r}")
