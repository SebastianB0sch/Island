# Vegetation, rocks and ground cover

The layout stage scatters the island's trees, palms, bushes, ferns, grass, flowers, rocks and logs
(`Layout.scatter` in `Tools/dai/layout.py`, helpers in `Tools/dai/groundfit.py`). About 127 000 instances
come from the scatter; the locations, the roadside and the waterside add their own planted trees, beds
and dressing on top.

## Standing on the ground

Every scattered instance is seated on the terrain triangles the player walks on (`Layout.hf`, the drawn
mesh), not on a single sample under its pivot:

* `groundfit.measure` builds the catalog prop once and keeps its **underside**: the mesh points close
  enough to the ground that a gap under them would show (rocks and logs: their lowest fifth; trees: the
  trunk and root flare; plants: where the stems leave the ground; furniture: its feet).
* `groundfit.seat` lowers the instance until no underside point is above the terrain. On a slope the
  downhill edge touches and the uphill side is buried, so nothing hovers.
* Rocks, logs and pebbles are **bedded into the slope**: they lean with a fraction of the slope
  (`Layout.LEAN`). Grass, ferns, bushes and flowers lean a little. Trees and stumps stay upright. A
  leaning instance carries Unreal's pitch and roll after its scale in `layout.json`
  (`[x, y, z, yaw, scale, pitch, roll]`). The level builder, both Fab swappers and the preview renderer
  read them.
* A boulder is kept only if its top still stands clear of the ground (`stands_out`). One too big for its
  slope is tried smaller first. A tree whose foot spans a step, or a rock that would sink out of sight, is
  skipped.

The roadside benches, planters, bins, lanterns, guard fences, lamps, signposts and the river boulders go
through the same fit (`Layout.settle`).

The trees' own pivots are where the trunk meets the ground (`"origin": "trunk"` in
`Tools/thirdparty/registry/vegetation.json`), not the centre of the crown's bounding box. Before this, the
leaning palm's foot was 3 m off its pivot, so its trunk collision stood in empty air and the foot floated
on a slope. The palm's collision column is cut to the straight lower 3 m of its trunk. The standing-room
checks (`placement.prop_bounds`: NPC spots, stroll routes, room zones) also treat a tree as its trunk
column, as the game does, so people may stand under a crown.

## Room to grow

`groundfit.Spacing` keeps trunks, boulders and crowns apart. Two trunks never overlap. Crowns may
interlock by a per-species factor (`Layout.TREES`: forest trees by half, open-grown meadow trees barely).
Trees planted by the locations, and the props along the roads, are entered first, so the forest leaves
room for them. A tree is also skipped when its trunk or crown would reach into a building's walls, roof or
fixtures (`Layout.crown_clear`). Undergrowth only keeps off trunks and rocks.

## More life

Smooth noise fields (`groundfit.value_noise`) shape the density:

* **Forest:** stands of one species (~100 m), the big trees placed first. Younger, smaller trees grow along
  the edge, with saplings in the light just outside it. Pines take over high up and in their own stands.
* **Meadows:** solitary trees, now and then a wide old ash, and groves of two to four with a few bushes at
  their feet.
* **Coast:** palms, often in leaning pairs.
* **Grass:** grows in swathes (~30 m) and tussocks. It is thicker by the roads, the buildings and the lake
  where people walk, taller on damp ground, thinner in deep shade.
* **Flowers:** drifts of one colour along paths, meadows and the forest edge.
* **Ferns:** under the canopy, thickest in the shade by the water and round the trees' feet.
* **Rocks:** outcrops on the steep ground with scree at their foot, boulders at the waterline, volcanic
  blocks, beach stones, driftwood, stumps and fallen trunks.

## Checking it

`Tools/tests/test_groundfit.py` covers the fit, the rotator conversion and the spacing. To audit a
regenerated layout, measure each scattered instance's underside against the terrain (hovering > 5 cm) and
the tree pairs (trunks overlapping, crowns closer than 0.4 × their summed radii). At the time of writing the
scatter has no hovering instance and no overlapping trunks. Before, about 50 000 grass and fern clumps,
almost every slope rock (up to 10 m in the air) and some 600 trees hovered, 15 trunk pairs overlapped and
about 900 crowns merged.
