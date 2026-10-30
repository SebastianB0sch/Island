# Location map — A01 initial extraction

> **Status:** first-pass ROM-name extraction, for A08 reconciliation only.
> **Authoritative audited map:** [`LOCATION_MAP.md`](LOCATION_MAP.md) (A08).
> **Machine-readable data:** `DuelAcademyIsland/Content/Data/Canon/locations.json`.

A08 already produced a detailed, coordinate-bearing map from the generated
island. This file records the ROM name pool and the first-pass GBA → GX
mapping used by the canon dataset. Do not replace A08's map with this one.

The ROM names are context-specific. `Front of Dorm`, `Lobby`, `Cafeteria`,
`Your Room` and `Headmaster's Room` are reused by all three dorms and must be
resolved with the current dorm at runtime.

| GBA name | ROM offset | GX zone / interior | Zone id | Notes |
| --- | --- | --- | --- | --- |
| Duel Academy | `0x13F6FD0` | Academy plaza / main entrance | `academy_plaza` | Existing zone; add scene anchor. |
| Front of School | `0x13F704A` | Academy plaza / main entrance | `academy_plaza` | Same physical place as above. |
| Classroom | `0x13F7070` | Academy interior classroom | `academy_classroom` | New interior cell. |
| Test Room | `0x13F7066` | Academy interior exam room | `academy_test_room` | New interior cell; exam UI. |
| Duel Arena | `0x13F705A` | Grand Duel Arena | `duel_arena` | Existing walk-in arena; story duel anchors. |
| Gym | `0x13F707A` | Duel Gym & Beach | `gym` | Existing gym; practical exam anchor. |
| Shop | `0x13F707E` | Academy Card Shop | `card_shop` | Replace fan cards with 48 packs. |
| Principal's Office | `0x13F7086` | Chancellor's office | `chancellors_office` | Ending trigger; E33. |
| Dr. Crowler's Room | `0x13F7098` | Academy staff office | `crowler_office` | New interior cell. |
| Slifer Red Dorm | `0x13F7024` | Slifer Red Dorm exterior | `slifer_dorm` | Existing. |
| Ra Yellow Dorm | `0x13F701C` | Ra Yellow Dorm exterior | `ra_dorm` | Existing. |
| Obelisk Blue - Boys' Dorm | `0x13F6FDE` | Obelisk Blue Dorm exterior | `obelisk_boys_dorm` | Existing. |
| Obelisk Blue - Girls' Dorm | `0x13F6FF8` | Obelisk Blue Girls' Dorm exterior | `obelisk_girls_dorm` | Story trigger only (E19/E25). |
| Front of Dorm | `0x13F70AC` | Dorm exterior (context) | `dorm_front` | Resolve by dorm. |
| Lobby | `0x13F70B8` | Dorm lobby (context) | `dorm_lobby` | Resolve by dorm; E14 uses Obelisk. |
| Cafeteria | `0x13F70FA` | Dorm cafeteria (context) | `dorm_cafeteria` | Resolve by dorm. |
| Your Room | `0x13F70BE` | Dorm room (context) | `dorm_room` | Sleep/save; E08/E11/E21/E30. |
| Headmaster's Room | `0x13F712E` | Dorm headmaster room (context) | `dorm_headmaster` | Christmas; E02 Banner. |
| Jaden's Room | `0x13F713C` | Slifer interior bunk room | `slifer_jaden_room` | E03. |
| Zane's Room | `0x13F7194` | Obelisk interior room | `obelisk_zane_room` | E25 incident. |
| Ocean | `0x13F7034` | Beach / shore / lake overlook | `ocean` | E04b/E06/E20/E31. |
| Next to Ocean | `0x13F7148` | Beach / shore / lake overlook | `ocean` | Same physical place as above. |
| Volcano | `0x13F703C` | Volcano viewpoint / crater | `volcano` | E06 random Titan duel. |
| Near Crater | `0x13F7154` | Volcano viewpoint / crater | `volcano_crater` | Titan/Shadow Game. |
| Harbor | `0x13F7042` | Harbor & Lighthouse | `harbor` | E06/E13/E17/E24/E25/E31. |
| Abandoned Dorm | not in this pool | Abandoned Dorm | `abandoned_dorm` | Shadow Game/Titan; no plain string found in this bank. |

## Portal / anchor rules for A08

- Every row above with an interior must have a door portal and a return portal.
- `dorm_front`, `dorm_lobby`, `dorm_cafeteria`, `dorm_room`,
  `dorm_headmaster` require the current dorm as a context parameter.
- `Your Room` is a save point in every dorm; sleep advances the calendar.
- `Next to Ocean` and `Ocean` are the same destination for fast travel.
- `Front of School` and `Duel Academy` are the same destination.
- E20 requires three separate visit anchors: Ocean, Volcano, Gym.
- E33 requires a Chancellor's Office anchor.
- E32 requires a Front of School anchor with a truck prop.

## Unresolved

- The plain-text pool does not contain `Abandoned Dorm`; it may use a different
  name or a script-only label. Confirm with A08/A03.
- Interior room numbers/floors are not in the ROM text; A08 owns the layout.
