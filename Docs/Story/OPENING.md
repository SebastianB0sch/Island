# Opening Vertical Slice — Story Spec

> **Status:** data complete; A10's full validator reports **0 errors** against the current tree.
> **Owner:** A03 (Director). **Branch:** `port/baseline`.
> **Scope:** new game through the first free-roam day and the first optional Jaden free duel.
>
> **Source note (updated):** A01's canon extraction landed during this pass. `Content/Data/Canon/text/dialogue_index.json` now confirms the opening registration and dorm entries (around `0x13FE2DE`–`0x13FE8BA`), including the Slifer Red assignment, Banner/Pharaoh, and the **Apprentice Duelist** title. The full extracted text is **local-only** (`full_text_committed: false`), so the runtime prose here remains original/paraphrased for this port. Stable keys are ready for a later text swap if the owner clears the exact script.

---

## 1. Files and counts

| File | Contents |
| --- | --- |
| `DuelAcademyIsland/Content/Data/Story/opening.json` | Manifest: new-game setup, calendar, beats, events, flags, counters, rewards, save points, objectives, tutorial/optional-duel config, anchor inventory, canon questions. |
| `DuelAcademyIsland/Content/Data/Story/scenes/opening.json` | **21 scenes** with location/anchor/cast and story command queues. |
| `DuelAcademyIsland/Content/Data/Story/dialogue/opening.json` | **86 dialogue lines**, 10 speakers, portraits/expressions, 5 choice nodes, 1 text-input node. |
| `DuelAcademyIsland/Content/Data/Story/schedules/opening.json` | **7 NPC schedules**, 42 base entries, 17 date/event overrides. |
| `Docs/Story/OPENING.md` | This spec. |

**Counts**

- **Beats:** 8 (B01–B08).
- **Events:** 3 — `E01` (canon Event 1: School Registration), `E01b` (port-internal first free-roam checkpoint), `FJ01` (port-internal optional first Jaden free duel).
- **Scenes:** 21.
- **Dialogue lines:** 86. **Choice nodes:** 5. **Text-input nodes:** 1.
- **Duels:** 2 — Syrus tutorial practice (`syrus_roids`, free mode + `tutorial: true`, 4,000 LP); Jaden optional free duel (`jaden`, free mode, 8,000 LP).
- **Schedule NPCs:** 7 — Banner, Jaden, Syrus, Chumley, Sheppard, Mimicry, Dorothy.
- **Required anchors:** 31 — **25 already exist in A08's `World/anchors.json`**, **6 are A08 requests**.
- **Flags:** 33. **Counters:** 10. **Rewards:** 5 (3,000 DP; three starter-deck grants; three email contacts).
- **Save points:** 9.

**Canon-ID discipline:** `E02`–`E33` are reserved for the numbered story events. The opening is canon **E01**; `E01b` and `FJ01` are explicitly `canon_event: false`.

**Layout note:** the assignment asks for one `scenes/opening.json`, one `dialogue/opening.json` and one `schedules/opening.json`. A10's canonical layout is one file per scene plus `Story/events.json`, `Story/dialogue.json`, `Story/schedules.json`. The validator explicitly supports this bundle/legacy shape (warnings, not errors); A03 should merge/split into the canonical files when the full 33-event graph is built.

---

## 2. Timeline and canon basis

| In-game time | Content | Source | Confidence |
| --- | --- | --- | --- |
| Sunday, October 1, AM | New-game deck choice, arrival, Sheppard's speech, registration/name entry, Slifer dorm, Banner's 3,000 DP, Syrus tutorial. | A01 dialogue index opening entries; Yugipedia Event 1; masterplan | High |
| October 2–6 | Orientation week montage (not playable in this slice). | Port-original transition | High |
| Saturday, October 7, 8:00 AM | First free-roam day; card shop open; manual save unlocked. | Yugipedia "first moves Saturday, October 7"; masterplan/save schema; A02 calendar start | High |
| Saturday, October 7, AM+ | Optional first Jaden free duel outside the Slifer dorm. | Jaden is a free-duel opponent from the start; framing port-original | High |

**A01-confirmed facts**

- Registration: "Congratulations on your acceptance to Duel Academy. To make things official, write your name on this document." After the name, the player is assigned to **Slifer Red** based on the entrance exam and sent to the dorm (`0x13FE2DE`–`0x13FE34E`).
- Dorm intro: Banner, Pharaoh, Jaden, Syrus and Chumley introduce themselves; Banner explains the three levels, monthly exams, titles and King of Games (`0x13FE3F6`–`0x13FE70C`).
- Starting title: **Apprentice Duelist** (`0x13FE6AA`).
- The exact text is local-only and is **not** copied into runtime JSON.

**Why the prologue is October 1 and free roam is October 7:** the public guide lists Event 1 on Sunday, October 1 but says the first free moves are Saturday, October 7. The masterplan/save schema start at October 7 AM. The port plays the prologue on October 1, montages the orientation week, then starts the calendar at October 7 AM. See Q1.

**Shop date:** Mimicry and Banner both say the card shop opens "next Saturday" on October 1, which is October 7. The shop is open on the first free-roam day so Gate 1 can include a pack purchase. See Q4.

**Source/confidence by beat**

| Beat | Title | Source | Confidence |
| --- | --- | --- | --- |
| B01 | New Game / Arrival + starter deck setup | mixed | High |
| B02 | Sheppard's Speech | guide + A01 index | High |
| B03 | Registration and Name Entry | guide + A01 index | High |
| B04 | Slifer Red Dorm Meeting | guide + A01 index | High |
| B05 | Banner's 3,000 DP, Dorms, Titles and the Card Shop | guide + A01 index | High |
| B06 | Syrus's Tutorial | guide + A01 index | Medium (exact tutorial steps not documented) |
| B07 | First Free-Roam Day | mixed | High |
| B08 | Optional First Jaden Free Duel | mixed | High |

---

## 3. Beat-by-beat flow

### B01 — New Game / Arrival + starter deck setup (`E01`, scene `opening.b01_new_game`)

- **New-game setup (before E01):** the player chooses one of the three starter decks — **Fire**, **Water** or **Wind**. The choice grants the matching existing deck (`fire`/`water`/`wind`), sets it active, and sets `starter_deck_chosen` + the matching `starter_deck_*` flag. This is a port presentation of the GBA's three-deck start; it is **not** part of Mimicry's registration dialogue.
- **Location:** `plaza`; anchors `academy_front_steps`, `academy_front_camera`.
- **Cast:** player.
- **Flow:** title/new-game → deck select → fade in on the ferry plaza → chapter card `DUEL ACADEMY — FRESHMAN ORIENTATION — SUNDAY, OCTOBER 1` → four lines establishing the island and the bell → objective card "Attend the opening assembly in the Duel Gym" → walk to the gym.
- **Commands used:** `music`, `fade`, `camera`, `banner`, `wait`, `dialogue`, `play_sfx`, `end`.
- **Canon note:** the GBA opens with Sheppard's speech; the plaza arrival is a 3D-port framing beat so the island reads before the cutscene.

### B02 — Sheppard's Speech (`E01`, scene `opening.b02_sheppard_speech`)

- **Location:** `gym`; anchors `gym_assembly_stage`, `gym_assembly_camera`, `gym_assembly_crowd`, `gym_assembly_student_02`, `gym_assembly_student_03`, `gym_assembly_staff` (requested).
- **Cast:** Sheppard, Jaden, Syrus, Chumley, player.
- **Flow:** fade to the gym → `DUEL GYM — OPENING CEREMONY` → Sheppard takes the podium → welcomes the students and describes a broad dueling education (rules, card lore, strategy, history) → "a duel, like life, is not over until the very end" → Jaden cheers for Slifer Red, Syrus shushes him, Chumley asks to be woken when the dueling starts → registration at the academy reception desk with Mimicry → player answers → applause → objective card "REGISTRATION — Academy Lobby" → join the registration queue.
- **Canon note:** A01's index has Sheppard's opening address around `0x13Fxxx` (entries 1118–1121: welcome, broad study, "a duel is not over until the very end," deck variety). The speech text is a port paraphrase.

### B03 — Registration and Name Entry (`E01`, scenes `opening.b03_registration`, `opening.b03_name_entry`, `opening.b03_name_accepted`)

- **Location:** `academy`; anchors `academy_registration_desk`, `academy_registration_player`.
- **Cast:** Mimicry, player.
- **Flow:**
  1. Mimicry introduces himself as the practical-dueling instructor and exam coordinator.
  2. He asks the player to spell their name one letter at a time.
  3. **Name entry** opens the text-input variant of the Choice command: 1–8 characters, A–Z and 0–9, `END` confirms, `DELETE` erases. The value is stored at `profile.name`.
  4. Mimicry reads back `{player_name_spelled}` and asks for confirmation. **Yes** continues; **No** reopens name entry.
  5. Mimicry hands over the student PDA (map, calendar, deck, mail, save), confirms **Slifer Red** from the entrance exam, and sends the player to Professor Banner.
  6. Mimicry says the card shop opens next Saturday.
- **Commands used:** `camera`, `move_npc`, `music`, `banner`, `dialogue`, `choice`, `set_flag`, `play_sfx`, `end`.
- **Canon note:** A01 confirms registration writes the name and then assigns Slifer Red. The GBA's three-deck choice is a separate new-game setup, not Mimicry's dialogue.
- **Save point:** `autosave_registered` after registration.

### B04 — Slifer Red Dorm Meeting (`E01`, scene `opening.b04_dorm_welcome`)

- **Location:** `slifer`; anchors `slifer_front_gate`, `slifer_front_camera`, `slifer_dorm_front_jaden`, `slifer_dorm_front_syrus`, `slifer_dorm_front_chumley` (the last three are A08 requests).
- **Cast:** Jaden, Syrus, Chumley, player.
- **Flow:** fade to the west cliff → `SLIFER RED DORM — West Cliff, Home of the Red` → narrator establishes the creaky red building → Jaden, Syrus and Chumley introduce themselves → player gives their name → Jaden leads everyone inside for Banner's welcome and the starting DP.
- **Canon note:** A01 confirms the dorm introductions and the Jaden/Syrus/Chumley lines' content. The exterior greeting is a port staging choice; the cafeteria scene follows immediately.

### B05 — Banner's 3,000 DP, Dorms, Titles and the Card Shop (`E01`, scene `opening.b05_banner_dp`)

- **Location:** `slifer`; anchors `slifer_cafeteria_table`, `slifer_cafeteria_counter`, `slifer_cafeteria_seat_01`, `slifer_cafeteria_seat_02`, `slifer_cafeteria_seat_03` (requested).
- **Cast:** Banner, Jaden, Syrus, Chumley, player.
- **Flow:** cafeteria card → Banner introduces himself and **Pharaoh** → explains the three levels, the monthly exam and the duelist-title ladder up to King of Games → Jaden declares he will be King of Games → **reward `opening_starting_dp` = 3,000 DP** → player reacts → Banner explains DP: earned by dueling, spent on booster packs at the card shop (100–200 DP per pack) → Syrus says the shop opens next Saturday → Chumley plans to spend it on a Master Fusions pack or lunch → Banner warns against blowing it all on one pack → Jaden disagrees → Banner unlocks the three dorm-mate email contacts → Syrus offers the duel tutorial → Banner tells Syrus not to let the player leave until they know a summon from a set.
- **Canon note:** A01 entries 1206–1218 confirm Banner, Pharaoh, the dorm/title explanation and the Apprentice Duelist rank. The 3,000 DP grant, shop opening and email unlock come from Yugipedia Event 1 / the masterplan.
- **Save point:** `autosave_banner_dp`.

### B06 — Syrus's Tutorial (`E01`, scenes `opening.b06_tutorial`, `opening.b06_tutorial_phases`, `opening.b06_tutorial_duel`, `opening.b06_tutorial_win`, `opening.b06_tutorial_lose`, `opening.b06_tutorial_continue`)

- **Location:** `slifer`; anchors `slifer_cafeteria_table` (rules), `slifer_yard_practice` (practice duel, A08 request).
- **Cast:** Syrus, player.
- **Rules taught:** 40–60 card deck; 8,000 LP; draw one per turn; one Normal Summon/Set per turn; Level 4 or lower no tribute, Level 5–6 one tribute, Level 7+ two; Attack vs Defense position; destroyed monsters go to the Graveyard; Spell Cards resolve, Trap Cards must be Set first; win by reducing LP to zero or deck-out.
- **Choice:** "I'm ready" starts the practice duel; "Can you explain the phases again?" opens a short phases refresher and returns to the prompt.
- **Practice duel:** **free mode with `tutorial: true`** (the frozen duel-mode enum has no `tutorial` value), opponent Syrus, deck **`syrus_roids`**, player deck `selected_starter`, **4,000 LP each**, 10-turn limit, no DP, no win counter, loss is a valid outcome. Objectives for optional UI tracking: normal summon, set a Spell/Trap, destroy a monster by battle.
- **Win path:** Syrus congratulates the player; flags `tutorial_complete`, `tutorial_duel_played`, `tutorial_duel_won`.
- **Loss path:** Syrus reassures the player; choice "Run it back" restarts the practice duel, "I'm good — let's keep going" continues; flags `tutorial_complete`, `tutorial_duel_played`, `tutorial_duel_lost`.
- **Canon note:** A01 entries 1230–1232 show an offer to explain the controls; the exact tutorial steps and a practice duel are not documented. The practice duel is a port-original adaptation.
- **Save points:** `autosave_tutorial_start`, `autosave_tutorial_win` / `autosave_tutorial_loss`.

### B07 — First Free-Roam Day (`E01b`, scenes `opening.b07_first_free_roam`, `opening.b07_save`, `opening.b07_free_roam`)

- **Location:** `slifer`; anchor `slifer_player_room_bed`.
- **Cast:** player; PDA; Dorothy via message.
- **Flow:** one-week montage line → `SATURDAY, OCTOBER 7 — 8:00 AM — FIRST FREE DAY` → player notes the shop opens today → PDA sets the objective "Explore Duel Academy. The Card Shop is open. Save your progress." → Dorothy's shop message (open, basic packs 100 DP) → narrator establishes the free-roam island → flags `first_free_roam`, `shop_unlocked`, `save_unlocked`, `jaden_first_duel_available` → **save prompt**: "Save now" runs the PDA save demonstration, "Later" drops straight to free roam.
- **PDA save:** `A_Save`, wait, `SAVED — Progress saved to slot 1`. Manual save unlocks here; prior saves are autosaves.
- **Canon note:** first free moves on Saturday, October 7; shop opening announced as "next Saturday" during the October 1 prologue.
- **Save points:** `autosave_first_free_roam`, `manual_save_first_free_roam`.

### B08 — Optional First Jaden Free Duel (`FJ01`, scenes `opening.b08_jaden_intro`, `opening.b08_jaden_decline`, `opening.b08_jaden_duel_setup`, `opening.b08_jaden_win`, `opening.b08_jaden_lose`)

- **Location:** `slifer`; anchors `slifer_dorm_front_jaden` (requested), `slifer_front_camera`.
- **Cast:** Jaden, player.
- **Flow:** Jaden asks how the tutorial went → player says they are getting the hang of it → Jaden offers a no-pressure free duel → **choice** "Let's duel!" or "Not right now."
  - **Decline:** Jaden says he will be around; event ends with `complete_event: false`, so it remains available. Flag `jaden_first_duel_available` stays true.
  - **Accept:** `OPTIONAL FREE DUEL — JADEN YUKI, ELEMENTAL HERO` → Jaden: "Get your game on!" → duel `mode: free`, opponent Jaden, deck `jaden`, player's active deck, 8,000 LP, DP by the normal formula, counts as a win.
  - **Win:** Jaden is shocked and impressed; player thanks him; Jaden asks for a rematch. Flags `jaden_first_duel_done`, `jaden_first_duel_won`; counters `duels_total +1`, `wins_jaden +1`, `wins_total +1`.
  - **Loss:** Jaden encourages the player; flags `jaden_first_duel_done`, `jaden_first_duel_lost`; counter `duels_total +1`. No story block, no forced retry.
- **Clear separation from the tutorial:** different event (`FJ01`), different mode (free), different banner, different deck, DP formula on, win counter on, optional and loss-tolerant. The tutorial is free mode **with `tutorial: true`**, no DP, no win counter, 4,000 LP.
- **After completion:** `jaden_first_duel_available = false`, `jaden_free_duel_unlocked = true`; repeatable Jaden free duels are A07's free-duel system, not this event.
- **Save points:** `autosave_jaden_first_win` / `autosave_jaden_first_loss` (autosave + manual allowed).

---

## 4. Required speakers, portraits and expressions

The dialogue file's `lines` table is the source of truth. Counts are per line.

| Speaker id | Display name | Lines | Portraits used | Asset status at time of writing | Fallback |
| --- | --- | ---: | --- | --- | --- |
| `player` | `{player_name}` | 15 | `player_neutral` (3), `player_happy` (6), `player_shocked` (1), `player_sad` (1), `player_determined` (4) | Existing in `Content/Data/Portraits` | `player_neutral` |
| `jaden` | Jaden Yuki | 13 | `jaden_happy` (5), `jaden_laugh` (5), `jaden_determined` (2), `jaden_shocked` (1) | Existing; neutral/angry/sad also available | `jaden_neutral` |
| `syrus` | Syrus Truesdale | 19 | `syrus_neutral` (8), `syrus_nervous` (4), `syrus_happy` (6), `syrus_determined` (1) | Base `syrus.png` and `syrus_face.png` exist; **expression frames required** | `syrus` |
| `banner` | Lyman Banner | 10 | `banner_happy` (4), `banner_neutral` (3), `banner_thoughtful` (2), `banner_stern` (1) | **Required** | `portrait_fallback_teacher` |
| `mimicry` | Professor Mimicry | 9 | `mimicry_neutral` (4), `mimicry_smug` (3), `mimicry_happy` (1), `mimicry_thoughtful` (1) | **Required** | `portrait_fallback_teacher` |
| `sheppard` | Chancellor Sheppard | 7 | `sheppard_neutral` (3), `sheppard_proud` (2), `sheppard_stern` (1), `sheppard_happy` (1) | **Required** | `portrait_fallback_chancellor` |
| `narrator` | — | 6 | `none` | UI text, no portrait | none |
| `chumley` | Chumley Huffington | 3 | `chumley_sleepy` (1), `chumley_happy` (1), `chumley_hungry` (1) | **Required** | `portrait_fallback_student` |
| `pda` | PDA | 3 | `ui_pda` | **UI frame required** | `ui_pda` |
| `dorothy` | Miss Dorothy | 1 | `dorothy_happy` (1) | **Required** | `portrait_fallback_shopkeeper` |

**Minimum new portrait work for the slice**

- Syrus: `syrus_neutral`, `syrus_nervous`, `syrus_happy`, `syrus_determined` (or a documented tint/zoom fallback from the base render).
- Banner: `banner_neutral`, `banner_happy`, `banner_thoughtful`, `banner_stern`.
- Mimicry: `mimicry_neutral`, `mimicry_smug`, `mimicry_happy`, `mimicry_thoughtful`.
- Sheppard: `sheppard_neutral`, `sheppard_proud`, `sheppard_stern`, `sheppard_happy`.
- Chumley: `chumley_neutral`, `chumley_happy`, `chumley_sleepy`, `chumley_hungry`.
- Dorothy: `dorothy_neutral`, `dorothy_happy`.
- PDA: `ui_pda`.

Deliberate generic fallbacks (`portrait_fallback_teacher`, `_chancellor`, `_student`, `_shopkeeper`, `ui_pda`) are acceptable for a data-complete slice but should be replaced before Gate 1 sign-off for presentation quality. A09 owns these assets and the portrait/expression fallback rules.

**Speakers deliberately not in this slice:** Alexis, Crowler, Zane, Chazz, Bastion, Pharaoh (Pharaoh is mentioned by Banner, not a speaking portrait). The guide's Event 1 also mentions meeting Alexis and Crowler in the classroom; that is deferred (Q9).

---

## 5. Required locations, anchors and NPC marks

Locations use the existing island zone ids. The data now uses A08's **current anchor ids** where they exist; the six missing ids are explicit A08 requests. The full machine-readable inventory is `opening.json.required_anchors`.

### Plaza

| Anchor | Status | Purpose |
| --- | --- | --- |
| `academy_front_steps` | A08 | B01 player arrival mark |
| `academy_front_camera` | A08 | B01 establishing camera; Sheppard weekend walk |

### Gym

| Anchor | Status | Purpose |
| --- | --- | --- |
| `gym_assembly_stage` | A08 | B02 Sheppard podium; Sheppard Oct 1 override |
| `gym_assembly_camera` | A08 | B02 establishing camera |
| `gym_assembly_crowd` | A08 | B02 crowd camera/Chumley mark |
| `gym_assembly_student_02` | A08 | B02 Jaden mark; Oct 1 schedule |
| `gym_assembly_student_03` | A08 | B02 Syrus mark; Oct 1 schedule |
| `gym_assembly_staff` | **REQUEST** | Banner's Oct 1 staff mark at the assembly |
| `gym_practice_field_a` | A08 | Mimicry weekday/weekend PM practical |

### Academy (interior)

| Anchor | Status | Purpose |
| --- | --- | --- |
| `academy_registration_desk` | A08 | B03 Mimicry registration mark |
| `academy_registration_player` | A08 | B03 player registration mark |
| `academy_card_shop_keeper` | A08 | Dorothy shop counter/stockroom schedule |
| `academy_card_shop_player` | A08 | Syrus weekday PM card-shop browsing |
| `academy_test_room_proctor` | A08 | Mimicry weekday/weekend AM exam prep |
| `chancellor_office_desk` | A08 | Sheppard schedule |

### Slifer Red (exterior + interiors)

| Anchor | Status | Purpose |
| --- | --- | --- |
| `slifer_front_gate` | A08 | B04 dorm-front scene mark |
| `slifer_front_camera` | A08 | B04/B08 establishing camera |
| `slifer_dorm_front_jaden` | **REQUEST** | B04 + B08 Jaden mark; FJ01 talk anchor |
| `slifer_dorm_front_syrus` | **REQUEST** | B04 Syrus mark |
| `slifer_dorm_front_chumley` | **REQUEST** | B04 Chumley mark |
| `slifer_cafeteria_table` | A08 | B05/B06 player table camera |
| `slifer_cafeteria_counter` | A08 | B05 Banner mark; Banner schedule |
| `slifer_cafeteria_seat_01` | A08 | B05 Jaden mark; Jaden schedule |
| `slifer_cafeteria_seat_02` | A08 | B05 Syrus mark; Syrus schedule |
| `slifer_cafeteria_seat_03` | **REQUEST** | B05 Chumley mark; Chumley schedule |
| `slifer_jaden_room_jaden` | A08 | Jaden night schedule |
| `slifer_jaden_room_syrus` | A08 | Syrus night schedule |
| `slifer_jaden_room_chumley` | A08 | Chumley night schedule |
| `slifer_banner_room_desk` | A08 | Banner PM office schedule |
| `slifer_yard_practice` | **REQUEST** | B06 practice duel; Jaden/Syrus weekend PM |
| `slifer_player_room_bed` | A08 | B07 wake/save scene |

**A08 requests (6):**

1. `gym_assembly_staff` — Banner's staff mark at the opening assembly.
2. `slifer_cafeteria_seat_03` — Chumley's cafeteria seat.
3. `slifer_dorm_front_jaden` — Jaden mark outside the dorm, used by B04 and FJ01.
4. `slifer_dorm_front_syrus` — Syrus mark outside the dorm.
5. `slifer_dorm_front_chumley` — Chumley mark outside the dorm.
6. `slifer_yard_practice` — practice-duel mark in the Slifer yard.

**Interior/portal work implied for A08**

- Gym: walk-in interior exists; add the registration/podium/crowd/staff marks and the practical-court mark.
- Slifer Red: the dining hall geometry exists; add a formal cafeteria interior cell/portal if needed, plus the player room (exists), the Jaden/Syrus/Chumley room (exists), Banner's room (exists), and the six requested marks.
- Academy: lobby, registration desk, card shop, test room and chancellor's office exist; the registration desk is in the **academy lobby** (A08's implementation), so B03 plays there rather than in the gym. This is the only intentional spatial adaptation from the guide's "gym lobby" wording.
- Plaza: existing zone; the arrival uses the academy front steps/camera.

### NPC marks by character

| NPC | Marks |
| --- | --- |
| Sheppard | `gym_assembly_stage`, `chancellor_office_desk`, `academy_front_steps` |
| Mimicry | `academy_registration_desk`, `academy_test_room_proctor`, `gym_practice_field_a`, `academy_registration_desk` (night) |
| Banner | `gym_assembly_staff` (request), `slifer_cafeteria_counter`, `slifer_banner_room_desk` |
| Jaden | `gym_assembly_student_02`, `slifer_dorm_front_jaden` (request), `slifer_cafeteria_seat_01`, `slifer_jaden_room_jaden`, `slifer_yard_practice` (request) |
| Syrus | `gym_assembly_student_03`, `slifer_dorm_front_syrus` (request), `slifer_cafeteria_seat_02`, `slifer_jaden_room_syrus`, `slifer_yard_practice` (request) |
| Chumley | `gym_assembly_crowd`, `slifer_dorm_front_chumley` (request), `slifer_cafeteria_seat_03` (request), `slifer_jaden_room_chumley` |
| Dorothy | `academy_card_shop_keeper` |

---

## 6. Required rewards, flags and counters

### Rewards (idempotent by `reward_id`)

| Reward id | Type | Amount/ids | Applied at | Source |
| --- | --- | --- | --- | --- |
| `opening_starting_dp` | DP | 3,000 | B05, after Banner's line | Guide/masterplan |
| `opening_email_contacts` | Email unlock | `jaden`, `syrus`, `chumley` | B05, after Banner's mail line | Guide |
| `opening_starter_deck_fire` | Deck grant | `fire`, set active | New-game setup | Guide |
| `opening_starter_deck_water` | Deck grant | `water`, set active | New-game setup | Guide |
| `opening_starter_deck_wind` | Deck grant | `wind`, set active | New-game setup | Guide |

No cards or packs are granted in the opening. The tutorial duel awards no DP and does not increment wins. The Jaden duel awards DP by the normal A02 formula and counts as a win.

### Flags (33)

**Progression:** `new_game_started`, `sheppard_speech_seen`, `registered`, `name_confirmed`, `starter_deck_chosen`, `starter_deck_fire`, `starter_deck_water`, `starter_deck_wind`, `met_mimicry`, `met_banner`, `met_jaden`, `met_syrus`, `met_chumley`, `banner_dp_granted`, `emails_unlocked`, `shop_announced`, `tutorial_complete`, `tutorial_duel_played`, `tutorial_duel_won`, `tutorial_duel_lost`.

**Free roam:** `first_free_roam`, `shop_unlocked`, `save_unlocked`, `fast_travel_unlocked`, `opening_complete`.

**Optional Jaden:** `jaden_first_duel_available`, `jaden_first_duel_done`, `jaden_first_duel_won`, `jaden_first_duel_lost`, `jaden_free_duel_unlocked`.

**Event bookkeeping:** `event_01_cleared`, `event_01b_cleared`, `event_fj01_cleared`.

All default to `false` except none; `jaden_first_duel_available` is set true by `E01b` and by the decline path. The data file declares every flag with its default.

### Counters (10)

| Counter | Default | Changed in this slice |
| --- | ---: | --- |
| `wins_total` | 0 | +1 on a Jaden win |
| `wins_jaden` | 0 | +1 on a Jaden win |
| `wins_syrus` | 0 | No (tutorial does not count) |
| `wins_chumley` | 0 | No |
| `duels_total` | 0 | +1 when the Jaden duel is played (win or loss) |
| `tutorial_duels_played` | 0 | +1 after the tutorial completes |
| `tutorial_duels_won` | 0 | +1 only on a tutorial win |
| `dp_earned_total` | 0 | A02 formula; Banner's 3,000 is a grant, not earned |
| `timed_clears` | 0 | No |
| `written_correct` | 0 | No |

---

## 7. Save/load points

| Save id | Scene | Trigger | Autosave | Manual |
| --- | --- | --- | --- | --- |
| `autosave_registered` | `opening.b03_name_accepted` | Registration complete | Yes | No |
| `autosave_banner_dp` | `opening.b05_banner_dp` | After Banner's 3,000 DP grant | Yes | No |
| `autosave_tutorial_start` | `opening.b06_tutorial` | Before the practice duel | Yes | No |
| `autosave_tutorial_win` | `opening.b06_tutorial_win` | Tutorial win | Yes | No |
| `autosave_tutorial_loss` | `opening.b06_tutorial_continue` | Tutorial loss, continue | Yes | No |
| `autosave_first_free_roam` | `opening.b07_first_free_roam` | First free-roam day begins | Yes | No |
| `manual_save_first_free_roam` | `opening.b07_save` | Player chooses "Save now" | No | Yes |
| `autosave_jaden_first_win` | `opening.b08_jaden_win` | Jaden duel won | Yes | Yes |
| `autosave_jaden_first_loss` | `opening.b08_jaden_lose` | Jaden duel lost | Yes | Yes |

**Mid-scene save requirements**

- Serialize `scene_id`, command index and current dialogue key. A choice prompt must serialize the pending choice id.
- A duel command must serialize the duel seed and mode so reload resumes the same practice/free duel.
- Reward ids must be recorded in the save so a reload after the reward command cannot duplicate the 3,000 DP, email unlock or deck grant.
- Before B07, saving is autosave-only. After B07, the PDA manual save is enabled.
- Save/load at every scene boundary, after every reward command, and in the middle of the name-entry/choice prompts.

---

## 8. Acceptance test steps for the vertical slice

### Manual playthrough

1. **New game:** start a fresh profile. Confirm the new-game setup offers Fire, Water and Wind; choose one. Confirm the matching deck is granted and active, and the other two are not.
2. **Arrival:** confirm B01 enters, the chapter card reads Sunday, October 1, and the objective points to the gym.
3. **Speech:** complete B02. Confirm Sheppard, Jaden, Syrus and Chumley appear at their gym marks and the registration objective appears.
4. **Name entry:** enter a 1-character name and an 8-character name in separate runs. Confirm `END` accepts, `DELETE` erases, empty input is rejected, and the confirm prompt reads back the spelled name.
5. **Name rejection loop:** choose "No — let me spell it again," enter a different name, and confirm it. Verify no duplicate registration effects.
6. **Registration:** confirm Mimicry sends the player to **Slifer Red**, mentions the card shop opening next Saturday, and the `autosave_registered` point fires.
7. **Dorm:** confirm the Slifer exterior greeting, then Banner's cafeteria introduction, including Pharaoh, the dorm/title explanation and Jaden's King of Games line.
8. **3,000 DP:** confirm exactly 3,000 DP is added once; check the HUD/profile value before and after. Confirm the email contacts Jaden, Syrus and Chumley are unlocked once.
9. **Shop explanation:** confirm the "next Saturday" line appears and the shop is not purchasable during the prologue.
10. **Tutorial:** run the rules dialogue. Use "explain the phases" once and confirm it loops back. Then win the practice duel; confirm no DP and no `wins_syrus` increment.
11. **Tutorial loss:** replay and lose. Confirm "Run it back" restarts the practice duel; "Keep going" completes the tutorial without a penalty. Confirm no softlock.
12. **Time skip:** after the tutorial, confirm the calendar advances to Saturday, October 7, 8:00 AM, and B07 plays.
13. **First free roam:** confirm the shop is open, the PDA objective is set, manual save is available, and the player regains control.
14. **Save/load:** save from the B07 prompt; reload; confirm the profile, DP, deck, flags and date survive. Repeat from an autosave.
15. **Jaden decline:** talk to Jaden, decline. Confirm the event does not complete and Jaden can be talked to again.
16. **Jaden win:** accept and win. Confirm DP is awarded by formula, `wins_jaden`/`wins_total`/`duels_total` increment once, and `jaden_first_duel_done` is set.
17. **Jaden loss:** in a separate run, accept and lose. Confirm the event completes, `duels_total` increments, `wins_jaden` does not, and free roam resumes.
18. **Repeatable free duel:** after FJ01, confirm Jaden remains available for repeatable free duels through A07's system and the one-time event does not replay.
19. **No duplicates:** replay B05/B08 from saves around the reward/result commands; confirm DP, emails, deck and counters are never duplicated.

### Automated / data checks

- A10 `Tools/validate/validate_all.py`: currently **0 errors** for this data. The remaining warnings are the intentional bundle/legacy schema drift; the event-coverage gap is expected because only the opening event is authored.
- `story_tests`: all event ids unique; every event scene id exists; every scene `end.next_scene`, choice `next_scene`, duel `on_win/on_lose/on_draw` resolves; no orphan dialogue lines; every speaker/portrait exists or has a declared fallback.
- `event_graph`: E01 reachable from `new_game`; E01b reachable at 10/7 AM after E01; FJ01 reachable by talking to Jaden after E01b; decline does not complete FJ01.
- `save_tests`: save/load at each save point; reward-id idempotency; mid-scene/mid-choice restore; no duplicate DP/email/deck.
- `world_tests`: every anchor in `opening.json.required_anchors` exists; six A08 requests must be filled before this check passes.
- `ui_smoke`: new-game deck select, name entry, dialogue, choice, banner, tutorial banner, duel result, PDA save and free-roam HUD open/close with keyboard, gamepad and mouse.
- `playthrough`: new game → B08 completes without debug commands; both tutorial outcomes and both Jaden outcomes pass.

**Gate 1 pass condition:** a player can complete B01–B07, save, reload, buy a pack, and win or lose the Jaden duel, with no dead ends and no duplicate rewards.

---

## 9. Dependencies and blockers

| Lane | Needed for this slice | Status/risk |
| --- | --- | --- |
| **A08** | 31 anchors; 25 exist, **6 requests**: `gym_assembly_staff`, `slifer_cafeteria_seat_03`, `slifer_dorm_front_jaden`, `slifer_dorm_front_syrus`, `slifer_dorm_front_chumley`, `slifer_yard_practice`. | **Primary spatial blocker**; the six requests are small marks, not new geometry. |
| **A09** | New-game deck select; name-entry UI; dialogue/choice/portrait UI; banners; PDA save; tutorial/duel banners; portraits for Banner, Sheppard, Mimicry, Chumley, Dorothy, Syrus expressions and the PDA frame. | **Primary presentation blocker**; data has fallbacks but the slice needs at least neutral portraits for the five new speakers. |
| **A07** | `syrus_roids` deck (exists), tutorial `tutorial: true` handling, Jaden free-duel integration, repeatable Jaden free duels after FJ01. | `syrus_roids` and `jaden` decks exist in A07's `Opponents/decks/`; A07 must honor tutorial metadata and the 4,000 LP/10-turn override. |
| **A04** | Duel request support for `starting_lp`, `turn_limit`, `tutorial: true`, `on_win/on_lose/on_draw`, `award_dp: none`, `counts_as_win: false`. | Extends the duel request contract; coordinate through A10. |
| **A02** | Calendar advance 10/1 → 10/7 AM; 3,000 DP grant; email unlock; flags/counters; manual save unlock; default title `apprentice_duelist`. | A02's `Profile/calendar.json` already starts at day 7 AM; `titles.json` defaults to `apprentice_duelist`. |
| **A06** | Existing `fire`/`water`/`wind` decks; shop unlock on 10/7; pack purchase at Gate 1. | Decks exist; the 48-pack catalogue is A06's current lane. |
| **A01** | Canon index now confirms registration/dorm/title facts; exact script remains local-only. | Resolved for this slice; keep exact text out of runtime JSON. |
| **A10** | Contract note for the legacy bundle and tutorial metadata; eventual split into canonical `Story/events.json`, `Story/dialogue.json`, `Story/schedules.json`, one scene per file. | Validator currently passes with schema-drift warnings; split before the full 33-event graph. |

### Contract notes used by this data

- The bundle uses A10's supported **legacy** shape: `scenes{}` with lowercase command types, `events` in `opening.json`, `dialogue` as a `lines` table, `schedules` as `npcs{}` with `periods[]`.
- Each command carries `command_id`, `args`, `duration`, `skippable`; Dialogue/Choice also carry `text_key`, `speaker`, `portrait`.
- New-game deck selection is a setup step, not a story scene; the three deck rewards are declared in `opening.json.rewards`.
- Event `scene` is the entry scene id; `scene_file` points at `scenes/opening.json`. The validator's legacy path accepts this.
- Tutorial duel uses `mode: "free"` + `tutorial: true` because the frozen duel-mode enum has no `tutorial` value.
- `Choice` options carry `next_scene` + `next_key`; scene bundles are the unit of loading.
- `End` carries `next_scene`, `enter_free_roam`, `complete_event`; `complete_event: false` leaves FJ01 available after a decline.
- Rewards are idempotent by `reward_id`; save records applied ids.

---

## 10. Open canon questions

| id | Question | Port decision | Owner |
| --- | --- | --- | --- |
| Q1 | Does the prologue play on Sunday, October 1, or does play start on Saturday, October 7? | Play the prologue on October 1, montage the week, start free roam October 7 AM. | A01/A02 |
| Q2 | What is the new student's starting title? | **Resolved by A01:** `apprentice_duelist` / "Apprentice Duelist". | A01/A02 |
| Q3 | Do the target's Fire/Water/Wind lists replace the GBA's canonical starter decks? | Use the existing target decks for the slice; reconcile later. | A01/A06 |
| Q4 | Is the card shop open on October 7 or only announced then? | Open it October 7 so Gate 1 can buy a pack. | A01/A06 |
| Q5 | What characters/length does the GBA name entry allow? | 1–8 characters, A–Z and 0–9, END/DELETE. | A01/A09 |
| Q6 | Does the Syrus tutorial include a practice duel? | Rules dialogue plus a short 4,000 LP no-stakes practice duel; A01 confirms only a controls explanation. | A01/A07 |
| Q7 | Is there a one-time first Jaden duel? | One-time optional intro; repeatable free duels after. | A01/A07 |
| Q8 | Where are the exact GBA dialogue lines? | **Resolved for reference:** A01's index has them, but the full text is local-only; runtime prose stays port-original. | A01/A03 |
| Q9 | Where is the Alexis/Crowler classroom introduction? | Deferred out of this slice; add as the first post-slice event. | A03 |

---

## 11. Runtime notes for the story subsystem

1. **The scene command list is authoritative.** Dialogue line `next` fields are validation/trace metadata and match the intended linear reading; they do not override the scene queue.
2. **Choice nodes:** a `choice` command with no input presents the referenced line's prompt and `choices`. Each option jumps to `next_scene` + `next_key`. If `next_key` is omitted, start the target scene at its first command.
3. **Input nodes:** a `choice` command with `input` captures text, stores it at `input.store_as`, and advances to the next command in the same scene. Name entry uses this variant.
4. **Duels:** a `duel` command starts the requested mode and jumps to `on_win`, `on_lose` or `on_draw` on result. `player_deck: "selected_starter"` resolves to the deck chosen in new-game setup; `"active"` resolves to the player's active deck.
5. **Rewards:** scene `reward` commands apply immediately; event `outcomes` reference the same `reward_id` for audit. Apply once per id.
6. **Placeholders:** `{player_name}` is the confirmed profile name; `{player_name_spelled}` is the same name with spaces between letters for Mimicry's read-back.
7. **Event ids:** `E01` is canon Event 1. `E01b` and `FJ01` are port-internal. Do not assign `E02`–`E33` to opening beats.
8. **`banner` command:** a UI title card, unrelated to the character Lyman Banner.
9. **Free roam:** `end.enter_free_roam = true` returns control to the player; `end.complete_event = false` leaves the event available (Jaden decline).
10. **Save/load:** serialize scene id, command index, current dialogue key, pending choice id, duel seed/mode, and applied reward ids.
11. **Contract merge:** this bundle is intentionally A10-legacy. Before the full 33-event graph, split `scenes/opening.json` into one file per scene, move `events` into `Story/events.json`, `lines` into `Story/dialogue.json`, and `npcs` into `Story/schedules.json`.

---

## 12. File manifest

| Path | Status |
| --- | --- |
| `DuelAcademyIsland/Content/Data/Story/opening.json` | Written |
| `DuelAcademyIsland/Content/Data/Story/scenes/opening.json` | Written |
| `DuelAcademyIsland/Content/Data/Story/dialogue/opening.json` | Written |
| `DuelAcademyIsland/Content/Data/Story/schedules/opening.json` | Written |
| `Docs/Story/OPENING.md` | Written |

No C++, UI, world, save or other lane files were modified in the data pass. Nothing was committed.

**Runtime layer:** see [`RUNTIME.md`](RUNTIME.md) for `UDAStorySubsystem` / `FDAEventGraph`, the `-DAOpeningTest` runner, console commands, save/load behavior and integration hooks.
