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
        zone=(200.0, 165.0, 50.0), spawn=(-143.0, 704.0, 0.0)),   # the lake walk by the sign
    "waterfall": dict(
        name="Volcano Falls", subtitle="Lake Waterfall",
        desc="Snowmelt? No - spring water, warmed by the volcano, tumbling into the lake.",
        pos=(345.0, 905.0), yaw=0.0, height=74.0, pad=(30.0, 25.0), color=(0.6, 0.85, 0.95),
        zone=(70.0, 60.0, 80.0), spawn=(278.0, 765.0, 0.0)),
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
    "millbrook": dict(
        name="Millbrook", subtitle="Mill Hamlet on the Academy River",
        desc="A water mill, a stone bridge and a handful of cottages where the forest path crosses the river.",
        pos=(378.0, 14.0), yaw=0.0, height=None, pad=(44.0, 32.0), color=(0.80, 0.62, 0.38),
        zone=(75.0, 65.0, 40.0), spawn=(338.0, 30.0, 0.0)),
    "willow_pond": dict(
        name="Willow Pond", subtitle="Pondside Village",
        desc="Thatched cottages, a market square and a jetty on the pond the river fills before the sea.",
        pos=(138.0, -548.0), yaw=0.0, height=None, pad=(38.0, 32.0), color=(0.55, 0.78, 0.50),
        zone=(120.0, 95.0, 40.0), spawn=(118.0, -556.0, 0.0)),
    "fishers_cove": dict(
        name="Fisher's Cove", subtitle="Fishing Hamlet at the River Mouth",
        desc="Net sheds, drying racks and boats pulled up where the Academy River meets the sea.",
        pos=(566.0, -912.0), yaw=0.0, height=None, pad=(40.0, 28.0), color=(0.45, 0.62, 0.78),
        zone=(80.0, 65.0, 40.0), spawn=(540.0, -902.0, 0.0)),
    "cliffs": dict(
        name="West Cliffs", subtitle="Sunset Point",
        desc="Sheer cliffs and sea stacks. The sunsets here are legendary.",
        pos=(-1150.0, 150.0), yaw=0.0, height=0.0, pad=(0.0, 0.0), color=(0.75, 0.6, 0.5),
        zone=(160.0, 260.0, 120.0), spawn=(-1080.0, 120.0, 0.0)),
}

# Locations that are flattened building pads (others are natural features)
PAD_LOCATIONS = ["academy", "plaza", "harbor", "lighthouse", "slifer", "ra", "obelisk_boys",
                 "obelisk_girls", "abandoned", "gym", "hotsprings", "waterfall",
                 "millbrook", "willow_pond", "fishers_cove"]
VILLAGES = ["millbrook", "willow_pond", "fishers_cove"]

LAKE_LEVEL = 30.0
LAKE_CENTER = (130.0, 780.0)
LAKE_RADII = (190.0, 150.0)
LAKE_ROT = 20.0
VOLCANO_CENTER = (720.0, 700.0)
VOLCANO_PEAK = 360.0          # height the cone adds on top of the plateau
VOLCANO_RADIUS = 650.0
CRATER_RADIUS = 95.0
VOLCANO_VIEW = (850.0, 690.0)  # viewpoint at the end of the volcano trail (foot of the summit stair)
VOLCANO_VIEW_YAW = math.degrees(math.atan2(700.0 - 690.0, 720.0 - 850.0))   # facing the crater
CRATER_DEPTH = 40.0           # floor is this far below the rim (rim is measured)
HARBOR_RECT = (60.0, -1066.0, 235.0, 60.0)   # cx, cy, half-x, half-y of the flat quay
# x0, x1, y0, y1 dredged flat to HARBOR_DEPTH: right up to the quay face (the south edge of HARBOR_RECT), whose
# wall reaches 1 m below that bed; the pier's piles stand on it
HARBOR_BASIN = (-250.0, 420.0, -1420.0, -1126.0)
HARBOR_DEPTH = -12.0
SEA_STACKS = [(-1300.0, 60.0, 22.0, 34.0), (-1265.0, -95.0, 16.0, 26.0), (-1350.0, 210.0, 26.0, 42.0),
              (-1215.0, -455.0, 14.0, 22.0), (-990.0, 1010.0, 20.0, 30.0), (420.0, 1390.0, 18.0, 28.0)]

# Arms of the lake. pts: (x, y, half width of the water) in world metres, or (location key, local x, local y,
# half width) in that location's frame, from the head of the arm out into the open lake. The terrain stage
# cuts each like the lake itself - `depth` m deep along the middle, banks rising `bank` m per unit of the
# lake's normalised radius (terrain.inlet_q) - and the water raster, the lake mesh, the minimap and the
# engine's water query (water.json "inlets") all see it. landing: (point, z) where a path meets a jetty's
# landing and the height of the landing's deck there (the ground is levelled just under it).
LAKE_INLETS = [
    # The girls' dorm jetty stood on dry ground in a hollow 70 m from the water; the lake now reaches up to it
    # along the axis of the garden walk (jetty root at local (0, -100), deck towards -Y, piles down to 27.0).
    dict(id="girls_jetty", name="Jetty Inlet", depth=2.2, bank=40.0,
         landing=(("obelisk_girls", 0.0, -91.0), 31.8),
         pts=[("obelisk_girls", 0.0, -104.0, 8.0), ("obelisk_girls", 0.0, -126.0, 12.0),
              ("obelisk_girls", -3.0, -152.0, 14.0), ("obelisk_girls", 2.0, -180.0, 18.0),
              ("obelisk_girls", 0.0, -208.0, 26.0), ("obelisk_girls", 0.0, -232.0, 32.0)]),
]


def _local(key, lx, ly):
    """World (x, y) of a point given in a location's own frame (for the tables below)."""
    (ox, oy), a = LOCATIONS[key]["pos"], math.radians(LOCATIONS[key].get("yaw", 0.0))
    return ox + lx * math.cos(a) - ly * math.sin(a), oy + lx * math.sin(a) + ly * math.cos(a)

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
    # Girls' dorm garden walk (it ends between two lantern pillars at the edge of the pad) -> the jetty landing
    dict(id="girls_jetty", width=4.0, surface="paved", lamps=False, pts=[
        _local("obelisk_girls", 0.0, -62.5), _local("obelisk_girls", 0.0, -91.0)]),
    # Lake shore walk to waterfall viewpoint
    dict(id="lake_walk", width=4.0, surface="dirt", lamps=False, pts=[
        (-150.0, 700.0), (-30.0, 640.0), (110.0, 600.0), (230.0, 640.0), (285.0, 715.0),
        (282.0, 772.0)]),
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
    # Hot springs -> volcano trail -> viewpoint under the crater rim (the summit stair climbs the last 30 m).
    # Constant-grade switchbacks across the east flank: ~1.3 km of trail for the 220 m climb at 19 %, each leg
    # following the slope at a fixed angle off the contour (a straight line would be 57 % steep; the old seven
    # straight legs needed 32 % and still left 40-68 % pitches where a leg cut across a gully).
    dict(id="volcano_trail", width=4.0, surface="dirt", lamps=False, grade=0.21, smooth=2, flat=3.0, pts=[
        (1082.0, 360.0), (1092.0, 440.0), (1106.0, 533.5), (1113.8, 562.4), (1112.8, 625.3), (1117.1, 654.8),
        (1099.9, 693.0), (1078.6, 725.6), (1086.6, 699.9), (1086.6, 682.0), (1062.6, 637.2), (1055.8, 605.0),
        (1047.1, 589.4), (1000.1, 557.5), (967.9, 526.4), (950.3, 525.3), (903.9, 504.2), (874.7, 498.1),
        (915.6, 528.4), (929.8, 551.1), (933.1, 568.7), (926.3, 591.5), (925.9, 612.5), (936.7, 661.9),
        (927.4, 687.2), (904.3, 714.3), (909.7, 682.3), (888.8, 649.7), (880.0, 627.5), (833.8, 594.5),
        (817.9, 572.8), (826.0, 604.7), (852.5, 654.9), (854.2, 675.7), (850.0, 690.0)]),
    # Abandoned dorm -> over the creek and back, square to it both times and clear of its bends -> round the
    # foot of the volcano -> lake east shore. (The old straight
    # line climbed 130 m up the volcano's flank and the grade limit carved it into a 60 m deep trench.)
    dict(id="forest_trail", width=4.0, surface="dirt", lamps=False, grade=0.16, pts=[
        (930.0, 0.0), (930.0, 44.0), (902.0, 96.0), (826.0, 110.0), (772.0, 108.0), (743.0, 100.0), (725.0, 38.0),
        (690.0, 48.0), (640.0, 80.0), (596.0, 100.0), (556.0, 110.0), (508.0, 126.0),
        (404.0, 208.0), (380.0, 252.0), (348.0, 288.0), (286.0, 412.0), (280.0, 440.0), (214.0, 564.0),
        (228.0, 604.0), (240.0, 654.0)]),
    # Harbor quay -> breakwater -> lighthouse  (boardwalk is part of the harbor mesh, we just pave)
    dict(id="breakwater", width=8.0, surface="paved", lamps=True, fixed_z=4.0, dike=True, pts=[
        (180.0, -1080.0), (230.0, -1140.0), (270.0, -1195.0), (295.0, -1222.0)]),
    # Plaza -> heliport
    dict(id="to_heliport", width=6.0, surface="paved", lamps=True, pts=[
        (-70.0, -850.0), (-110.0, -930.0), (-115.0, -1018.0)]),
    # Obelisk boys -> cliffs viewpoint
    dict(id="to_cliffs", width=4.0, surface="dirt", lamps=False, pts=[
        (-650.0, 450.0), (-800.0, 360.0), (-940.0, 250.0), (-1060.0, 150.0)]),
    # Main road -> Willow Pond village square -> the jetty
    dict(id="pond_lane", width=5.0, surface="paved", lamps=True, pts=[
        (44.0, -536.0), (70.0, -532.0), (88.0, -508.0), (96.0, -482.0), (122.0, -472.0), (140.0, -490.0),
        (140.0, -516.0), (142.0, -540.0), (158.0, -548.0), (172.0, -544.0)]),
    # Gym road -> Fisher's Cove
    dict(id="cove_lane", width=4.0, surface="dirt", lamps=True, pts=[
        (458.0, -856.0), (500.0, -884.0), (540.0, -902.0), (566.0, -910.0)]),
    # Millbrook: the mill lane along the river's east bank, off the forest path
    dict(id="mill_lane", width=4.0, surface="dirt", lamps=True, pts=[
        (340.0, 30.0), (372.0, 18.0), (404.0, 10.0)]),
]

# Grade limits (rise / run) of the path profiles: roads are ironed to these between their fixed ends.
ROAD_GRADE = {"paved": 0.09, "dirt": 0.12, "boardwalk": 0.09}

# The last stretch to the door. The paths above are graded between the edges of the grounds they join (a
# pad is level, there is nothing to grade on it) - which left several of them ending in a lawn, short of the
# building's own paving. These carry them on across the grounds: no earthworks, the same surface as the path
# (a paved road's ribbon simply runs further, a dirt path is trodden further into the splat).
#   start / end : waypoints before the path's first / after its last point, in walking order. A waypoint is a
#                 world (x, y), or (location key, local x, local y) in that location's own frame - so the
#                 road keeps meeting the walkway if the building is moved or turned.
#   start_edge / end_edge : the two corners of a built slab the paving butts against (paved across, level
#                 with it); without one the path ends on the ground and thins out into whatever is there.
PATH_EXTENSIONS = {
    # the Academy's forecourt apron (painted paving, 128 x 92 m either side of (0, 140)): three roads stopped
    # at the edge of the lawn round it
    "to_obelisk": dict(start=[(-124.0, 60.0)],
                       # ... and at the Obelisk dorm 12 m outside the garden gate: on to the gate walk
                       end=[("obelisk_boys", 0.0, -88.0), ("obelisk_boys", 0.0, -83.7)],
                       end_edge=(("obelisk_boys", -5.0, -83.7), ("obelisk_boys", 5.0, -83.7))),
    "to_girls": dict(start=[(-60.0, 228.0)]),
    "to_abandoned": dict(start=[(124.0, 60.0)]),
    # Ra Yellow: the dorm's entrance walk ends 18 m from where the road did
    "to_ra": dict(end=[("ra", 0.0, -46.0)], end_edge=(("ra", -2.0, -46.0), ("ra", 2.0, -46.0))),
    # the cliff trail starts at the side walk of the Obelisk dorm, not 40 m out in its lawn
    "to_cliffs": dict(start=[("obelisk_boys", -44.0, -10.0)]),
    # the hot springs: up to the gate and its stepping stones
    "to_springs": dict(end=[("hotsprings", 0.0, -28.6)]),
    # the girls' dorm: from the garden walk (5.2 m) onto the jetty's stone landing (4 m)
    "girls_jetty": dict(start_edge=(("obelisk_girls", -2.6, -62.5), ("obelisk_girls", 2.6, -62.5)),
                        end_edge=(("obelisk_girls", -2.0, -91.0), ("obelisk_girls", 2.0, -91.0))),
}

# --------------------------------------------------------------------------- waterways
# Centre lines run downstream. width = water half-width (m) at that point (linear in between), depth = water
# depth mid-stream. The water level follows the ground it is cut into: never above the terrain, never rising
# (see terrain.py river_profile). "pond" marks points whose width is a pool, not a channel.
RIVERS = [
    dict(id="academy_river", name="Academy River", source="lake", depth=1.0, pts=[
        (106.0, 652.0, 3.2), (108.0, 618.0, 3.2), (114.0, 560.0, 3.0), (118.0, 508.0, 3.0), (136.0, 458.0, 3.2),
        (130.0, 420.0, 3.4), (142.0, 362.0, 3.4), (176.0, 316.0, 3.6), (222.0, 268.0, 3.6), (262.0, 196.0, 3.8),
        (292.0, 124.0, 4.0), (302.0, 60.0, 4.2), (288.0, -20.0, 4.2), (300.0, -100.0, 4.2), (326.0, -170.0, 4.4),
        (318.0, -250.0, 4.4), (296.0, -330.0, 4.6), (304.0, -410.0, 4.6), (286.0, -462.0, 6.0),
        (258.0, -526.0, 44.0), (272.0, -572.0, 34.0), (322.0, -632.0, 6.5), (396.0, -688.0, 5.5),
        (452.0, -718.0, 5.5), (492.0, -770.0, 5.5), (524.0, -828.0, 5.5), (596.0, -842.0, 6.5),
        (676.0, -876.0, 9.0), (730.0, -902.0, 12.0)]),
    dict(id="forest_creek", name="Forest Creek", source="spring", depth=0.6, pts=[
        (646.0, 160.0, 2.4), (630.0, 126.0, 1.6), (652.0, 100.0, 1.6), (704.0, 78.0, 1.8), (764.0, 60.0, 1.8),
        (832.0, 66.0, 2.0), (900.0, 60.0, 2.0), (950.0, 36.0, 2.2), (996.0, 12.0, 2.2), (1060.0, -50.0, 2.4),
        (1108.0, -102.0, 2.6), (1148.0, -140.0, 3.5), (1176.0, -164.0, 5.0)]),
]
POND_MIN_HALF_WIDTH = 15.0      # a river point at least this wide is a pool (deeper, calm, lily pads)

# Extra named spots (not zones) used by layout.
HELIPORT = (-115.0, -1060.0)
BEACH_SEGMENT = [(380.0, -1000.0), (620.0, -880.0), (860.0, -720.0), (1030.0, -520.0), (1160.0, -300.0)]


def deg(a):
    return math.radians(a)


def loc(key):
    return LOCATIONS[key]


def world_point(pt):
    """World (x, y) of a waypoint: (x, y) as it is, or (location key, local x, local y)."""
    if len(pt) == 2:
        return float(pt[0]), float(pt[1])
    return _local(*pt)


def lake_inlets():
    """LAKE_INLETS in world metres: [dict(id, name, depth, bank, pts [(x, y)], half [m], landing ((x, y), z))]."""
    out = []
    for rec in LAKE_INLETS:
        pts = [world_point(p[:-1]) for p in rec["pts"]]
        land = rec.get("landing")
        out.append(dict(id=rec["id"], name=rec["name"], depth=float(rec["depth"]), bank=float(rec["bank"]),
                        pts=pts, half=[float(p[-1]) for p in rec["pts"]],
                        landing=(world_point(land[0]), float(land[1])) if land else None))
    return out


def path_extension(path_id):
    """PATH_EXTENSIONS[path_id] in world coordinates: dict(start=[(x, y)], end=[(x, y)], start_edge, end_edge)."""
    ext = PATH_EXTENSIONS.get(path_id, {})
    out = dict(start=[world_point(q) for q in ext.get("start", [])], end=[world_point(q) for q in ext.get("end", [])])
    for k in ("start_edge", "end_edge"):
        if ext.get(k):
            out[k] = [world_point(q) for q in ext[k]]
    return out
