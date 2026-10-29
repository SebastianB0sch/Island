"""Assemble /Game/DuelAcademy/Maps/DuelAcademyIsland from Data/layout.json."""

import math

import unreal

from . import common as C

EAS = None


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
        m = self.meshes.get(name)
        if m is None:
            for folder in ("Props", "Terrain", "Water", "Roads", "Characters"):
                m = C.load(f"{C.MESH_DIR}/{folder}/{name}")
                if m:
                    break
        return m

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
        C.set_props(m, sun=env.get("sun"), moon=env.get("moon"), sky_light=env.get("sky"), height_fog=env.get("fog"),
                    parameter_collection=mpc, hour=float(self.layout["environment"]["start_hour"]),
                    day_length_minutes=float(self.layout["environment"]["day_minutes"]), map_texture=map_tex,
                    map_min=unreal.Vector2D(w["map"]["min"][0], w["map"]["min"][1]),
                    map_max=unreal.Vector2D(w["map"]["max"][0], w["map"]["max"][1]),
                    sea_level=float(w["sea_level"]), lake_center=self.loc(lake["center"]),
                    lake_radii=unreal.Vector2D(lake["radii"][0], lake["radii"][1]),
                    lake_yaw=self.yaw(lake["rot"]), lake_level=float(w["lake_level"]))
        if self.ysign < 0:
            # the map texture's north edge is now at +Y
            C.set_props(m, map_min=unreal.Vector2D(w["map"]["min"][0], w["map"]["max"][1]),
                        map_max=unreal.Vector2D(w["map"]["max"][0], w["map"]["min"][1]))
        return m

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
        for name, g in self.layout["instances"].items():
            mesh = self.mesh(name)
            if mesh is None:
                C.warn(f"missing instanced mesh {name}")
                continue
            items = g["items"]
            if slow:
                slow.enter_progress_frame(1, f"Scattering {name} ({len(items)})")
            xforms = []
            for x, y, z, yaw, s in items:
                xforms.append(unreal.Transform(unreal.Vector(x, y * self.ysign, z), C.rot(yaw=yaw * self.ysign),
                                               unreal.Vector(s, s, s)))
            folder = "Island/vegetation" if any(k in name for k in ("Tree", "Palm", "Bush", "Fern", "Grass", "Flower", "Rock")) else "Island/props"
            if cls is not None:
                a = self.spawn(cls, unreal.Vector(0, 0, 0), 0.0, f"Scatter_{name.replace('SM_', '')}", folder)
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
            a = self.spawn(cls, self.loc(z["center"]), 0.0, f"Zone_{z['id']}", "Gameplay/zones")
            C.set_props(a, location_id=z["id"], display_name=z["name"], subtitle=z["subtitle"], description=z["desc"],
                        theme_color=C.lc(z["color"]), zone_extent=C.vec(z["extent"]), sort_order=i,
                        spawn_location=self.loc(z["spawn"]["loc"]), spawn_yaw=self.yaw(z["spawn"]["yaw"]))
            box = a.get_component_by_class(unreal.BoxComponent)
            if box:
                box.set_box_extent(C.vec(z["extent"]), False)

    def interactables(self):
        cls = C.native_class("DAInteractable")
        if cls is None:
            return
        kinds = {"sign": "SIGN", "card_shop": "CARD_SHOP", "duel_field": "DUEL_FIELD", "info": "INFO"}
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
            a = self.spawn(cls, self.loc(e["loc"]), 0.0, f"Emitter_{e['kind']}", "Gameplay/fx")
            C.set_props(a, kind=getattr(enum, e["kind"].upper(), enum.STEAM), effect_scale=float(e["scale"]),
                        rate=float(e.get("rate", 1.0)))

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
            if c:
                # anime cast member (see Tools/dai/anime): mesh, skeleton group, name and dialogue
                C.set_props(a, cast_mesh=c["name"], anim_group=c["group"], dorm_tint=bool(n.get("tint", True)),
                            body_scale=float(n.get("scale", c.get("scale", 1.0))))
                if n.get("name"):
                    C.set_props(a, display_name=n["name"], lines=list(n.get("lines", [])))

    def specials(self):
        beam_cls = C.native_class("DALighthouseBeam")
        for s in self.layout["specials"]:
            if s["kind"] == "lighthouse_beam" and beam_cls is not None:
                a = self.spawn(beam_cls, self.loc(s["loc"]), self.yaw(s["yaw"]), "LighthouseBeam", "Gameplay/fx")
                if "beam_length" in s["props"]:
                    C.set_props(a, beam_length=float(s["props"]["beam_length"]))

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
        les().load_level(C.MAP_PATH)
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
    les().save_current_level()
