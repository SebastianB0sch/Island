"""
Island-wide configuration: world extents, location coordinates, path network.

Coordinate convention (Blender, metres):  +X = east, +Y = north, +Z = up.
Every building asset is modelled with its FRONT facing -Y (south) at yaw 0.
`yaw` values below are counter-clockwise degrees about +Z (Blender convention).

The Unreal side converts Blender -> UE as  (x, y, z) m  ->  (x, -y, z) * 100 cm,
yaw_ue = -yaw.  (The UE build script verifies the axis convention against the
imported terrain bounds, so this only has to be correct here.)
"""

import math
import os

# --------------------------------------------------------------------------- paths
TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(TOOLS_DIR)
UE_PROJECT_DIR = os.path.join(REPO_DIR, "DuelAcademyIsland")
OUT_DIR = os.path.join(UE_PROJECT_DIR, "SourceAssets")
OUT_MESHES = os.path.join(OUT_DIR, "Meshes")
OUT_TEXTURES = os.path.join(OUT_DIR, "Textures")
OUT_AUDIO = os.path.join(OUT_DIR, "Audio")
OUT_DATA = os.path.join(OUT_DIR, "Data")
OUT_HEIGHTMAP = os.path.join(OUT_DIR, "Heightmap")
DOCS_DIR = os.path.join(REPO_DIR, "Docs")
RENDER_DIR = os.path.join(DOCS_DIR, "renders")
CACHE_DIR = os.path.join(TOOLS_DIR, ".cache")

# --------------------------------------------------------------------------- world
WORLD_SIZE = 3072.0            # terrain domain edge length in metres (square, centred on origin)
HALF = WORLD_SIZE / 2.0
FIELD_RES = 2017               # heightfield samples per side (UE Landscape friendly, ~1.52 m spacing)
MESH_QUADS = 1008              # terrain mesh quads per side (~3.05 m spacing)
CHUNKS = 8                     # terrain mesh chunks per side (126 quads each)
SPLAT_RES = 4096               # splat / colour map resolution (0.75 m per texel)
SEA_LEVEL = 0.0
SEA_FLOOR = -48.0
OCEAN_RADIUS = 16000.0         # ocean plane radius (m)
SEED = 1996                    # GX aired 2004, Duel Monsters 1996 - any int works

# Default heightmap scale for the optional UE Landscape import (documented in README)
HEIGHT_MIN = -64.0
HEIGHT_MAX = 448.0             # 512 m of range in 16 bit -> 0.78 cm precision

# --------------------------------------------------------------------------- locations
# kind: building pads are flattened to `height` inside an ellipse (rx, ry) rotated by yaw.
LOCATIONS = {
    "academy": dict(
        name="Duel Academy", subtitle="Main Academy Building",
        desc="The heart of the island. Classrooms, the card shop and the grand Duel Arena.",
        pos=(0.0, 150.0), yaw=0.0, height=34.0, pad=(175.0, 135.0), color=(0.95, 0.75, 0.2),
        zone=(200.0, 170.0, 70.0), spawn=(0.0, -40.0, 0.0)),
    "plaza": dict(
        name="Academy Plaza", subtitle="Front Courtyard",
        desc="The fountain courtyard where every freshman takes their first step on campus.",
        pos=(0.0, -10.0), yaw=0.0, height=34.0, pad=(95.0, 50.0), color=(0.9, 0.9, 0.9),
        zone=(95.0, 50.0, 50.0), spawn=(0.0, -40.0, 0.0)),
    "harbor": dict(
        name="Duel Academy Harbor", subtitle="Docks, Warehouse & Heliport",
        desc="Where the ferry from the mainland arrives. The lighthouse keeps watch at the breakwater.",
        pos=(60.0, -1075.0), yaw=0.0, height=3.0, pad=(290.0, 70.0), color=(0.55, 0.75, 0.95),
        zone=(330.0, 170.0, 60.0), spawn=(40.0, -1040.0, 0.0)),
    "lighthouse": dict(
        name="Lighthouse", subtitle="Harbor Breakwater",
        desc="A quiet place to think. Some say the Kaiser comes here to watch the sea.",
        pos=(300.0, -1235.0), yaw=0.0, height=4.0, pad=(18.0, 18.0), color=(0.95, 0.95, 0.95),
        zone=(45.0, 45.0, 60.0), spawn=(255.0, -1195.0, 0.0)),
    "slifer": dict(
        name="Slifer Red Dorm", subtitle="Osiris Red Dormitory",
        desc="Humble, creaky and right on the cliff edge - the best ocean view on the island.",
        pos=(-1065.0, -262.0), yaw=-90.0, height=None, pad=(32.0, 52.0), color=(0.85, 0.1, 0.08),
        zone=(70.0, 85.0, 50.0), spawn=(-1010.0, -262.0, 0.0)),
    "ra": dict(
        name="Ra Yellow Dorm", subtitle="Ra Yellow Dormitory",
        desc="Comfortable rooms, a proper cafeteria, and walls covered in someone's equations.",
        pos=(-690.0, -660.0), yaw=140.0, height=22.0, pad=(75.0, 60.0), color=(0.98, 0.8, 0.15),
        zone=(95.0, 85.0, 50.0), spawn=(-630.0, -600.0, 0.0)),
    "obelisk_boys": dict(
        name="Obelisk Blue Dorm", subtitle="Boys' Dormitory",
        desc="A palace for the elite. Marble columns, fountains and a five-star kitchen.",
        pos=(-600.0, 520.0), yaw=50.0, height=44.0, pad=(110.0, 95.0), color=(0.15, 0.35, 0.9),
        zone=(130.0, 120.0, 60.0), spawn=(-500.0, 440.0, 0.0)),
    "obelisk_girls": dict(
        name="Obelisk Blue Girls' Dorm", subtitle="Lakeside Dormitory",
        desc="An elegant lakeside mansion. Boys caught near the lake answer to the Queen of Obelisk Blue.",
        pos=(-215.0, 905.0), yaw=65.0, height=34.0, pad=(80.0, 70.0), color=(0.55, 0.7, 1.0),
        zone=(110.0, 95.0, 50.0), spawn=(-120.0, 840.0, 0.0)),
    "lake": dict(
        name="Academy Lake", subtitle="Girls' Dorm Lakeshore",
        desc="Calm water fed by the volcano falls. Rowing boats wait at the jetty.",
        pos=(130.0, 780.0), yaw=0.0, height=30.0, pad=(185.0, 150.0), color=(0.35, 0.65, 0.85),
        zone=(200.0, 165.0, 50.0), spawn=(-40.0, 760.0, 0.0)),
    "waterfall": dict(
        name="Volcano Falls", subtitle="Lake Waterfall",
        desc="Snowmelt? No - spring water, warmed by the volcano, tumbling into the lake.",
        pos=(345.0, 905.0), yaw=0.0, height=74.0, pad=(30.0, 25.0), color=(0.6, 0.85, 0.95),
        zone=(70.0, 60.0, 80.0), spawn=(270.0, 840.0, 0.0)),
    "volcano": dict(
        name="Duel Academy Volcano", subtitle="Still Active",
        desc="The island's smoking heart. The crater glows at night.",
        pos=(720.0, 700.0), yaw=0.0, height=None, pad=(0.0, 0.0), color=(0.95, 0.35, 0.1),
        zone=(420.0, 420.0, 260.0), spawn=(905.0, 640.0, 0.0)),
    "abandoned": dict(
        name="Abandoned Dorm", subtitle="Off Limits",
        desc="The old Special Dorm. Students who stayed here vanished. Nobody comes here anymore...",
        pos=(930.0, -60.0), yaw=-90.0, height=50.0, pad=(60.0, 55.0), color=(0.5, 0.2, 0.6),
        zone=(85.0, 80.0, 50.0), spawn=(855.0, -60.0, 0.0)),
    "gym": dict(
        name="Duel Gym", subtitle="Beachside Gymnasium",
        desc="Sports hall and practice duel courts beyond the beach.",
        pos=(690.0, -720.0), yaw=-67.0, height=7.0, pad=(80.0, 70.0), color=(0.3, 0.8, 0.6),
        zone=(95.0, 85.0, 40.0), spawn=(620.0, -660.0, 0.0)),
    "beach": dict(
        name="South-East Beach", subtitle="White Sand Shore",
        desc="Warm sand and bright water. Perfect for a beach duel.",
        pos=(860.0, -560.0), yaw=0.0, height=2.0, pad=(0.0, 0.0), color=(0.98, 0.9, 0.6),
        zone=(260.0, 230.0, 40.0), spawn=(820.0, -560.0, 0.0)),
    "hotsprings": dict(
        name="Hot Springs", subtitle="Volcanic Onsen",
        desc="Steaming pools heated by the volcano. Relax after a long day of duels.",
        pos=(1080.0, 330.0), yaw=-37.0, height=24.0, pad=(50.0, 45.0), color=(0.9, 0.55, 0.45),
        zone=(65.0, 60.0, 40.0), spawn=(1035.0, 300.0, 0.0)),
    "forest": dict(
        name="Duel Academy Forest", subtitle="Deep Woods",
        desc="Dense jungle between the academy and the volcano. Easy to get lost in at night.",
        pos=(560.0, 230.0), yaw=0.0, height=0.0, pad=(0.0, 0.0), color=(0.2, 0.6, 0.25),
        zone=(260.0, 240.0, 120.0), spawn=(450.0, 10.0, 0.0)),
    "cliffs": dict(
        name="West Cliffs", subtitle="Sunset Point",
        desc="Sheer cliffs and sea stacks. The sunsets here are legendary.",
        pos=(-1150.0, 150.0), yaw=0.0, height=0.0, pad=(0.0, 0.0), color=(0.75, 0.6, 0.5),
        zone=(160.0, 260.0, 120.0), spawn=(-1080.0, 120.0, 0.0)),
}

# Locations that are flattened building pads (others are natural features)
PAD_LOCATIONS = ["academy", "plaza", "harbor", "lighthouse", "slifer", "ra", "obelisk_boys",
                 "obelisk_girls", "abandoned", "gym", "hotsprings", "waterfall"]

LAKE_LEVEL = 30.0
LAKE_CENTER = (130.0, 780.0)
LAKE_RADII = (190.0, 150.0)
LAKE_ROT = 20.0
VOLCANO_CENTER = (720.0, 700.0)
VOLCANO_PEAK = 360.0          # height the cone adds on top of the plateau
VOLCANO_RADIUS = 650.0
CRATER_RADIUS = 95.0
CRATER_DEPTH = 40.0           # floor is this far below the rim (rim is measured)
HARBOR_RECT = (60.0, -1066.0, 235.0, 60.0)   # cx, cy, half-x, half-y of the flat quay
HARBOR_BASIN = (-250.0, 420.0, -1420.0, -1136.0)  # x0, x1, y0, y1 dredged to -12 m
SEA_STACKS = [(-1300.0, 60.0, 22.0, 34.0), (-1265.0, -95.0, 16.0, 26.0), (-1350.0, 210.0, 26.0, 42.0),
              (-1215.0, -455.0, 14.0, 22.0), (-990.0, 1010.0, 20.0, 30.0), (420.0, 1390.0, 18.0, 28.0)]

# --------------------------------------------------------------------------- paths
# Each path: list of XY waypoints, width (m), surface ('paved' | 'dirt' | 'boardwalk'), lamps?
PATHS = [
    # Harbor -> winding main road -> plaza
    dict(id="main_road", width=12.0, surface="paved", lamps=True, pts=[
        (40.0, -1035.0), (20.0, -960.0), (-60.0, -860.0), (-90.0, -760.0), (-40.0, -650.0),
        (40.0, -560.0), (60.0, -450.0), (10.0, -340.0), (-20.0, -230.0), (0.0, -130.0), (0.0, -55.0)]),
    # Plaza -> Slifer Red
    dict(id="to_slifer", width=6.0, surface="dirt", lamps=True, pts=[
        (-90.0, -30.0), (-230.0, -95.0), (-390.0, -150.0), (-560.0, -205.0), (-720.0, -240.0),
        (-860.0, -255.0), (-960.0, -262.0), (-1030.0, -262.0)]),
    # Slifer path -> Ra Yellow
    dict(id="to_ra", width=7.0, surface="paved", lamps=True, pts=[
        (-480.0, -180.0), (-520.0, -300.0), (-560.0, -420.0), (-610.0, -530.0), (-650.0, -610.0)]),
    # Academy west side -> Obelisk Blue boys
    dict(id="to_obelisk", width=9.0, surface="paved", lamps=True, pts=[
        (-170.0, 60.0), (-260.0, 170.0), (-360.0, 290.0), (-450.0, 390.0), (-530.0, 455.0)]),
    # Academy north -> lake -> girls dorm
    dict(id="to_girls", width=7.0, surface="paved", lamps=True, pts=[
        (-60.0, 290.0), (-90.0, 420.0), (-120.0, 560.0), (-150.0, 700.0), (-170.0, 820.0),
        (-190.0, 860.0)]),
    # Lake shore walk to waterfall viewpoint
    dict(id="lake_walk", width=4.0, surface="dirt", lamps=False, pts=[
        (-150.0, 700.0), (-30.0, 640.0), (110.0, 600.0), (230.0, 640.0), (300.0, 730.0),
        (290.0, 830.0)]),
    # Academy east -> forest -> abandoned dorm
    dict(id="to_abandoned", width=5.0, surface="dirt", lamps=False, pts=[
        (175.0, 60.0), (300.0, 40.0), (430.0, 0.0), (560.0, -30.0), (700.0, -60.0), (800.0, -62.0),
        (875.0, -60.0)]),
    # Harbor -> beach -> gym
    dict(id="to_gym", width=8.0, surface="paved", lamps=True, pts=[
        (180.0, -1030.0), (300.0, -960.0), (420.0, -880.0), (540.0, -800.0), (630.0, -745.0)]),
    # Gym -> east coast -> hot springs
    dict(id="to_springs", width=5.0, surface="dirt", lamps=False, pts=[
        (720.0, -650.0), (820.0, -520.0), (930.0, -380.0), (1010.0, -200.0), (1040.0, 0.0),
        (1050.0, 160.0), (1050.0, 290.0)]),
    # Hot springs -> volcano trail -> crater rim
    dict(id="volcano_trail", width=4.0, surface="dirt", lamps=False, pts=[
        (1040.0, 380.0), (990.0, 470.0), (1010.0, 560.0), (940.0, 600.0), (900.0, 650.0),
        (870.0, 680.0), (850.0, 690.0)]),
    # Abandoned dorm -> forest -> lake east shore
    dict(id="forest_trail", width=4.0, surface="dirt", lamps=False, pts=[
        (930.0, 0.0), (850.0, 160.0), (700.0, 330.0), (560.0, 480.0), (420.0, 600.0), (300.0, 680.0)]),
    # Harbor quay -> breakwater -> lighthouse  (boardwalk is part of the harbor mesh, we just pave)
    dict(id="breakwater", width=8.0, surface="paved", lamps=True, fixed_z=4.0, dike=True, pts=[
        (180.0, -1080.0), (230.0, -1140.0), (270.0, -1195.0), (295.0, -1222.0)]),
    # Plaza -> heliport
    dict(id="to_heliport", width=6.0, surface="paved", lamps=True, pts=[
        (-70.0, -850.0), (-110.0, -930.0), (-115.0, -1018.0)]),
    # Obelisk boys -> cliffs viewpoint
    dict(id="to_cliffs", width=4.0, surface="dirt", lamps=False, pts=[
        (-650.0, 450.0), (-800.0, 360.0), (-940.0, 250.0), (-1060.0, 150.0)]),
]

# Extra named spots (not zones) used by layout.
HELIPORT = (-115.0, -1060.0)
BEACH_SEGMENT = [(380.0, -1000.0), (620.0, -880.0), (860.0, -720.0), (1030.0, -520.0), (1160.0, -300.0)]


def deg(a):
    return math.radians(a)


def loc(key):
    return LOCATIONS[key]
