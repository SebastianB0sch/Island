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

Expressions: `neutral`, `happy`, `angry`, `shocked`, `sad`, `laugh`, and
`determined` (an alias of the angry frame). The duel HUD uses these for
attack, damage, fusion/ritual, low-LP, and win/loss cut-ins.

`*_face.png` is a square head/bust crop for compact scoreboards; the unsuffixed
file is the full render for dialogue and result panels.

These portraits were ported from the reference UE5 project together with the
duel engine. They are fan-project reference assets: the character renders are
Konami/Shueisha property and must not be redistributed with a public build.
The island's in-world characters use this project's VRoid-derived models
instead. See [`../../../../CREDITS.md`](../../../../CREDITS.md).
