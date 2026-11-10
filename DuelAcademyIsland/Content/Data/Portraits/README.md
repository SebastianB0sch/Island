# Duel portraits

Character busts used by the duel scoreboards, detail panels, result screen and
the key-event cut-ins. The runtime loader is `UCharacterPortraitSubsystem`.

| File | Source |
| --- | --- |
| `jaden.png`, `jaden_face.png` | Konami Duel Links Jaden render |
| `zane.png`, `zane_face.png` | Konami Duel Links Zane render |
| `chazz.png`, `chazz_face.png` | Konami Duel Links Chazz render |
| `alexis.png`, `alexis_face.png` | Konami Duel Links Alexis render |
| `bastion.png`, `bastion_face.png` | Konami Duel Links Bastion render |
| `syrus.png`, `syrus_face.png` | Konami Duel Links Syrus render |
| `player.png`, `player_face.png` | Generic Duel Links Slifer Red student ("Evan") |
| `jaden_<expression>.png` | Duel Links Jaden duel portraits |
| `player_<expression>.png` | Duel Links Evan duel portraits |
| `chumley.png`, `jasmine.png`, `mindy.png`, `crowler.png` | Project cast renders (Blender/Cycles, see below) |
| `banner.png`, `sheppard.png`, `mimicry.png`, `dorothy.png`, `fontaine.png`, `sartyr.png` | Project cast renders |
| `beauregard.png`, `brier.png`, `dimitri.png`, `gerard.png`, `blair.png`, `topher.png`, `torrey.png`, `conklin.png`, `damon.png`, `shadow_duelist.png` | Project cast renders |
| `student_m1.png`, `student_f1.png`, `student_f2.png`, `unknown_student.png` | Project cast renders (generic students) |
| `narrator.png` | UI icon (scroll and quill) |
| `ui_pda.png`, `pda_neutral.png` | UI icon (PDA; the neutral expression copy used by the `pda` speaker) |
| `pharaoh.png`, `goblin_king.png`, `jinzo.png` | UI icons for the event-only non-human opponents |
| `<id>_<expression>.png` | Expression frame: official Duel Links cut-in for the regulars, or a render from the project cast |

Expressions: `neutral`, `happy`, `laugh`, `angry`, `determined`, `shocked`,
`sad`, `nervous`, `smug`, `thoughtful`, `proud`, `stern`, `sleepy`, `hungry`,
`confused` and `apologetic`. The duel HUD uses these for attack, damage,
fusion/ritual, low-LP, and win/loss cut-ins.

All declared expressions are present for every named speaker and opponent:

* The five regulars with ported Duel Links base art (Alexis, Bastion, Chazz,
  Syrus, Zane) use official Duel Links expression cut-ins, fetched by
  `Tools/fetch_expression_portraits.py`. Jaden and the player already had
  theirs.
* Every generated character gets expression frames rendered from the same
  cel-shaded model as their base bust. The facial morph recipes live in
  `Tools/dai/anime/expressions.py`; the neutral frame uses the character's
  resting expression, and the other frames blend the target expression with a
  quarter of the resting face.
* Jasmine, Mindy, Conklin and Damon have no story-declared expressions, so
  they get the six generic duel cut-in emotions (`happy`, `angry`,
  `determined`, `shocked`, `sad`, `laugh`) for their opponent cut-ins.

A missing expression still falls back to the base bust at runtime, but
`python Tools/portrait_check.py --strict` now fails if a declared expression
frame is absent.

`*_face.png` is a square head/bust crop for compact scoreboards; the unsuffixed
file is the full render for dialogue and result panels.

## Regenerating the project-cast portraits

The missing speakers are rendered from the project's own,
cel-shaded cast models, so they match the people who stand on the island. The
renders flatten onto the same `#263541` panel colour as the existing portraits.

```bash
# Blender 5.2 as an installed application, not the bpy module:
set PYTHONHASHSEED=0
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup ^
    --python Tools/render_portraits.py -- --missing

# UI icons (narration, PDA and the three event-only opponents):
python Tools/make_ui_portraits.py

# Official expression cut-ins for the five Duel Links regulars:
python Tools/fetch_expression_portraits.py

# Expressions rendered from the project cast (add --force to redraw):
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup ^
    --python Tools/render_portraits.py -- --expressions

# Generic duel cut-ins for the opponents with no story expressions:
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup ^
    --python Tools/render_portraits.py -- --expressions --ids jasmine mindy conklin damon --duel

# Status / coverage:
python Tools/portrait_check.py --strict
```

`Tools/render_portraits.py` only renders ids that have no `<id>.png`; pass
`--force --ids chumley` to redraw one, or `--ids ...` to redraw a list. The
portrait-only looks for story speakers live in
`Tools/dai/anime/portrait_cast.py`; the regulars come from
`Tools/dai/anime/cast.py`.

The Duel Links portraits were ported from the reference UE5 project together
with the duel engine. They are fan-project reference assets: the character
renders are Konami/Shueisha property and must not be redistributed with a
public build. The island's in-world characters use this project's own
models instead, including all the generated portraits above. See
[`../../../../CREDITS.md`](../../../../CREDITS.md).
