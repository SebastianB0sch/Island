# Canon deck traceability (Gate 3)

Generated: 2026-10-31T09:27:10+00:00

This report audits every deck in `Content/Data/Canon/decks.json` against the
available game source and extraction evidence. It is the companion to
`GATE3_RECONCILIATION.md` and `TRACEABILITY.md`.

## 1. Evidence and method

| Evidence | What it proves | Limits |
| --- | --- | --- |
| ROM card tables `0xF243CC`, `0xF2A68C`, `0xF58294` | Card ids, names, stats and descriptions used to resolve every deck entry. | Card data only; not deck membership. |
| ROM text pool `0x13F6DF0` + offsets `0x14280A0` | Exam-week warning strings (indices 74 and 93); event dialogue previews. | Does not encode deck lists. |
| `game3d/src/duel/decklists.js` | Donor Jaden list and three starter lists. | Donor implementation, not independently verified against a ROM deck table. |
| Yugipedia Starter Decks page | Three starter deck lists. | Public guide; starter lists match the donor implementation. |
| Yugipedia Opponents page | Opponent roster, archetypes and signature cards. | Does not publish full opponent lists. |
| GameFAQs Character Deck List FAQ v1.4 (Tracy_Smith, 2006-03-11) | Character-specific opponent lists, counts, missing-card notes and the shared generic shell. | Player-written guide, not a ROM dump; the author marks several lists as incomplete. |
| GameFAQs Event FAQ (ishingun, v3) | Event opponents, timed-puzzle solution and E22/E23/E26 context. | No deck lists for Jinzo, Goblin King or Bastion's Seventh Deck. |

### ROM deck-table search (negative evidence)

The ROM was read in place and never copied into the repository. Two searches
were run against the verified US ROM (`0c2f6069...4afe`):

1. Raw little-endian `u16` scan for the known starter and Jaden card-id sequences
   (the `romhack/research/find_decks.py` method). No contiguous 40-card sequence
   was found for Fire, Water, Wind or Jaden.
2. Scan of every valid GBA BIOS LZ77/RLE block and search of the decompressed
   output for the same sequences. No match.

Conclusion: the ROM does not expose an obvious uncompressed 40-card deck table
at the card-id encoding used by `cards.json`. The deck lists below are therefore
guide-derived; they are not marked ROM-exact. This is why no deck is labelled
`exact` even when the guide says its character list is complete.

### Generic shell

The FAQ lists a shared 15-card Year 1 generic shell. It is
appended only where `use_generic_shell` is true. The FAQ says the shell is 15 or
16 cards; this dataset uses the 15-card Year 1 legal selection and records the
optional 16th slot as a global unresolved shell slot.

Generic shell ids: 375 (Card Destruction), 370 (Graceful Charity), 422 (Heavy Storm), 387 (Pot of Greed), 477 (Premature Burial), 428 (Snatch Steal), 497 (Call of the Haunted), 552 (Magic Cylinder), 402 (Magic Jammer), 402 (Magic Jammer), 421 (Mirror Force), 403 (Seven Tools of the Bandit), 403 (Seven Tools of the Bandit), 547 (Torrential Tribute), 348 (Jinzo)

## 2. Deck summary

| Deck id | Name | Opponent | Type | Main | Extra | Status | Unresolved | Complete | Confidence |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| `fire` | Fire Starter |  | starter | 40 | 1 | complete | 0 | True | high |
| `water` | Water Starter |  | starter | 40 | 0 | complete | 0 | True | high |
| `wind` | Wind Starter |  | starter | 40 | 0 | complete | 0 | True | high |
| `alexis_year1` | Alexis Rhodes - Year 1 | alexis | opponent | 49 | 1 | partial | 4 | False | medium |
| `banner_year1` | Lyman Banner - Year 1 | banner | opponent | 40 | 2 | partial | 2 | False | medium |
| `bastion_year1` | Bastion Misawa - Year 1 | bastion | opponent | 43 | 0 | partial | 3 | False | medium |
| `beauregard_year1` | Beauregard - Year 1 | beauregard | opponent | 52 | 0 | complete | 0 | True | high |
| `blair_year1` | Blair Flannigan - Year 1 | blair | opponent | 43 | 0 | partial | 1 | False | medium |
| `brier_year1` | Brier - Year 1 | brier | opponent | 47 | 0 | complete | 0 | True | high |
| `chazz_year1` | Chazz Princeton - Year 1 | chazz | opponent | 45 | 0 | complete | 0 | True | high |
| `chumley_year1` | Chumley Huffington - Year 1 | chumley | opponent | 50 | 1 | complete | 0 | True | high |
| `crowler_year1` | Vellian Crowler - Year 1 | crowler | opponent | 45 | 0 | partial | 4 | False | medium |
| `damon_year1` | Damon - Year 1 | damon | opponent | 50 | 1 | complete | 0 | True | high |
| `dimitri_year1` | Dimitri - Year 1 | dimitri | opponent | 51 | 4 | complete | 0 | True | high |
| `fontaine_year1` | Fonda Fontaine - Year 1 | fontaine | opponent | 45 | 0 | partial | 2 | False | medium |
| `gerard_year1` | Gerard - Year 1 | gerard | opponent | 44 | 2 | partial | 1 | False | medium |
| `jasmine_year1` | Jasmine - Year 1 | jasmine | opponent | 60 | 0 | complete | 0 | True | high |
| `mindy_year1` | Mindy - Year 1 | mindy | opponent | 28 | 0 | partial | 12 | False | medium |
| `pharaoh_year1` | Pharaoh - Year 1 | pharaoh | opponent | 39 | 0 | partial | 1 | False | medium |
| `sartyr_year1` | Sartyr - Year 1 | sartyr | opponent | 43 | 0 | complete | 0 | True | high |
| `syrus_year1` | Syrus Truesdale - Year 1 | syrus | opponent | 45 | 1 | complete | 0 | True | high |
| `torrey_year1` | Torrey - Year 1 | torrey | opponent | 48 | 0 | complete | 0 | True | high |
| `zane_year1` | Zane Truesdale - Year 1 | zane | opponent | 50 | 2 | complete | 0 | True | high |
| `shadow_duelist_year1` | The Shadow Duelist - Year 1 | shadow_duelist | opponent | 16 | 0 | partial | 24 | False | medium |
| `mimicry_year1` | Mimicry / Test Proctor - Year 1 | mimicry | opponent | 46 | 0 | partial | 0 | False | medium |
| `topher_year1` | Topher - Year 1 | topher | opponent | 17 | 0 | partial | 23 | False | medium |
| `conklin_year1` | Conklin - Year 1 | conklin | opponent | 17 | 0 | partial | 23 | False | medium |
| `sheppard_year1` | Chancellor Sheppard - Year 1 | sheppard | opponent | 48 | 3 | complete | 0 | True | high |
| `jaden_year1` | Jaden Yuki - Year 1 | jaden | opponent | 53 | 4 | complete | 0 | True | medium |
| `jinzo_spirit` | Jinzo - Spirit Deck | jinzo | event | 0 | 0 | unknown | 40 | False | low |
| `damon_exodia` | Damon - Exodia Draw (Event) | damon | event | 5 | 0 | partial | 35 | False | low |
| `yugi_deck` | Yugi Muto - Legendary Deck (Event) | dimitri | event | 39 | 2 | partial | 5 | False | medium |
| `bastion_seventh` | Bastion Misawa - Seventh Deck | bastion | event | 0 | 0 | unknown | 40 | False | low |
| `torrey_special` | Torrey - Special Player Deck | torrey | player_override | 0 | 0 | unknown | 40 | False | low |
| `chazz_ojama` | Chazz Princeton - Ojama | chazz | opponent_variant | 0 | 0 | unknown | 40 | False | low |
| `jaden_improved` | Jaden Yuki - Improved | jaden | opponent_variant | 0 | 0 | unknown | 40 | False | low |
| `bastion_magnet` | Bastion Misawa - Magnet | bastion | opponent_variant | 0 | 0 | unknown | 40 | False | low |

## 3. Per-deck audit

Each section lists the evidenced cards (source name -> canon card id and count),
then the generic shell and the explicit unresolved slots.

### `fire` - Fire Starter

- Opponent: `n/a`
- Type: `starter`; status: **complete**; complete: **True**
- Main: **40**; Extra: **1**; unresolved slots: **0**
- Confidence: **high**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Starter_Decks
- Generic shell applied: no

- No evidenced card list; the deck is an explicit unknown.

### `water` - Water Starter

- Opponent: `n/a`
- Type: `starter`; status: **complete**; complete: **True**
- Main: **40**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Starter_Decks
- Generic shell applied: no

- No evidenced card list; the deck is an explicit unknown.

### `wind` - Wind Starter

- Opponent: `n/a`
- Type: `starter`; status: **complete**; complete: **True**
- Main: **40**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Starter_Decks
- Generic shell applied: no

- No evidenced card list; the deck is an explicit unknown.

### `alexis_year1` - Alexis Rhodes - Year 1

- Opponent: `alexis`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **49**; Extra: **1**; unresolved slots: **4**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#a
- FAQ section: `a`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: 4 or so (I suspect it is a Magic Jammer, two Seven Tools of the Bandit, and a Trap Hole)'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Big Bang Shot | Big Bang Shot `#796` | 1 | False |
| spell | Cestus of Dagla | Cestus of Dagla `#669` | 1 | False |
| spell | Mage Power | Mage Power `#594` | 1 | False |
| spell | Polymerization | Polymerization `#381` | 1 | False |
| spell | Sanctuary in the Sky | The Sanctuary in the Sky `#953` | 1 | False |
| spell | Shinato's Ark | Shinato's Ark `#822` | 1 | False |
| spell | United We Stand | United We Stand `#593` | 1 | False |
| trap | Enchanted Javelin | Enchanted Javelin `#499` | 1 | False |
| trap | Numinous Healer | Numinous Healer `#463` | 3 | False |
| trap | Solar Ray | Solar Ray `#958` | 1 | False |
| monster14 | Absorbing Kid From The Sky | Absorbing Kid from the Sky `#980` | 1 | False |
| monster14 | Agido | Agido `#674` | 1 | False |
| monster14 | Dunames Dark Witch | Dunames Dark Witch `#360` | 3 | False |
| monster14 | Hysteric Fairy | Hysteric Fairy `#586` | 3 | False |
| monster14 | Kelbek | Kelbek `#672` | 1 | False |
| monster14 | Manju of the Ten Thousand Hands | Manju of the Ten Thousand Hands `#909` | 1 | False |
| monster14 | Mudora | Mudora `#668` | 1 | False |
| monster14 | Outstanding Dog Marron | Outstanding Dog Marron `#837` | 1 | False |
| monster14 | The Forgiving Maiden | The Forgiving Maiden `#588` | 1 | False |
| monster14 | Warrior of Zera | Warrior of Zera `#934` | 1 | False |
| monster14 | Zolga | Zolga `#673` | 1 | False |
| monster56 | Marie the Fallen One | Marie the Fallen One `#590` | 1 | False |
| monster56 | Soul of Purity and Light | Soul of Purity and Light `#620` | 3 | False |
| monster7 | Archlord Zerato | Archlord Zerato `#949` | 1 | False |
| monster7 | Guardian Angel Joan | Guardian Angel Joan `#908` | 1 | False |
| monster7 | Shinato, Ruler Of A Higher Plane | Shinato, King of a Higher Plane `#812` | 1 | False |

Extra Deck evidence:

- St. Joan -> St. Joan `#589` x1

**Unresolved:** 4 card slot(s). They are not silently filled; see the reason above.

### `banner_year1` - Lyman Banner - Year 1

- Opponent: `banner`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **40**; Extra: **2**; unresolved slots: **2**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#b
- FAQ section: `b`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: 2 or so (most likely Mystic Horseman and Trap Hole)'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Axe of Despair | Axe of Despair `#110` | 1 | False |
| spell | Black Pendant | Black Pendant `#117` | 2 | False |
| spell | Polymerization | Polymerization `#381` | 3 | False |
| trap | Magic Jammer | Magic Jammer `#402` | 1 | False |
| trap | Negate Attack | Negate Attack `#368` | 3 | False |
| trap | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 1 | False |
| monster14 | Aqua Madoor | Aqua Madoor `#82` | 1 | False |
| monster14 | Battle Ox | Battle Ox `#20` | 1 | False |
| monster14 | Blackland Fire Dragon | Blackland Fire Dragon `#8` | 1 | False |
| monster14 | Hane-Hane | Hane-Hane `#239` | 2 | False |
| monster14 | Fairy Dragon | Fairy Dragon `#263` | 1 | False |
| monster14 | Magician of Faith | Magician of Faith `#190` | 2 | False |
| monster14 | Man-Eater Bug | Man-Eater Bug `#221` | 2 | False |
| monster14 | Penguin Soldier | Penguin Soldier `#262` | 2 | False |
| monster56 | Curse of Dragon | Curse of Dragon `#27` | 1 | False |
| monster7 | Gaia the Fierce Knight | Gaia The Fierce Knight `#26` | 1 | False |

Extra Deck evidence:

- Gaia the Dragon Champion -> Gaia the Dragon Champion `#25` x1
- Rabid Horseman -> Rabid Horseman `#44` x1

**Unresolved:** 2 card slot(s). They are not silently filled; see the reason above.

### `bastion_year1` - Bastion Misawa - Year 1

- Opponent: `bastion`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **43**; Extra: **0**; unresolved slots: **3**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#c
- FAQ section: `c`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: As complete as I can get it'; three dorm-dependent slots (Trap Hole x3 or the parenthesised cards).
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Dark Factory of Mass Production | Dark Factory of Mass Production `#1021` | 1 | False |
| spell | Mystical Space Typhoon | Mystical Space Typhoon `#436` | 1 | False |
| spell | Swords of Revealing Light | Swords of Revealing Light `#153` | 1 | False |
| trap | Backup Soldier | Backup Soldier `#467` | 1 | False |
| trap | Negate Attack | Negate Attack `#368` | 1 | False |
| trap | Ring of Destruction | Ring of Destruction `#503` | 1 | False |
| trap | Trap Hole | Trap Hole `#380` | 3 | True |
| monster14 | Alpha the Magnet Warrior | Alpha The Magnet Warrior `#338` | 3 | False |
| monster14 | Beta the Magnet Warrior | Beta The Magnet Warrior `#351` | 3 | False |
| monster14 | Gamma the Magnet Warrior | Gamma The Magnet Warrior `#364` | 3 | False |
| monster14 | Hane-Hane | Hane-Hane `#239` | 1 | True |
| monster14 | Needle Worm | Needle Worm `#251` | 2 | False |
| monster14 | Penguin Soldier | Penguin Soldier `#262` | 2 | False |
| monster14 | Sangan | Sangan `#29` | 1 | False |
| monster14 | Sapphire Dragon | Luster Dragon `#780` | 1 | True |
| monster14 | Vorse Raider | Vorse Raider `#502` | 2 | False |
| monster14 | Vorse Raider | Vorse Raider `#502` | 1 | True |
| monster14 | White Magician Pikeru | White Magician Pikeru `#948` | 1 | False |
| monster14 | Witch of the Black Forest | Witch of the Black Forest `#257` | 1 | True |
| monster56 | Emerald Dragon | Luster Dragon `#663` | 2 | False |
| monster7 | Hyozanryu | Hyozanryu `#337` | 2 | False |
| monster7 | Valkyrion the Magnet Warrior | Valkyrion the Magna Warrior `#500` | 1 | False |

**Unresolved:** 3 card slot(s). They are not silently filled; see the reason above.

### `beauregard_year1` - Beauregard - Year 1

- Opponent: `beauregard`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **52**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#d
- FAQ section: `d`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Banner of Courage | Banner of Courage `#739` | 2 | False |
| spell | Big Bang Shot | Big Bang Shot `#796` | 2 | False |
| spell | Fairy Meteor Crush | Fairy Meteor Crush `#555` | 2 | False |
| spell | Gaia Power | Gaia Power `#455` | 2 | False |
| spell | Goblin Thief | Goblin Thief `#955` | 2 | False |
| spell | Goblin's Secret Remedy | Goblin's Secret Remedy `#145` | 1 | False |
| spell | Upstart Goblin | Upstart Goblin `#425` | 2 | False |
| trap | Magic Jammer | Magic Jammer `#402` | 1 | True |
| trap | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 1 | True |
| monster14 | Battle Ox | Battle Ox `#20` | 3 | False |
| monster14 | D.D. Trainer | D. D. Trainer `#834` | 3 | False |
| monster14 | Dancing Fairy | Dancing Fairy `#583` | 1 | False |
| monster14 | Giant Orc | Giant Orc `#758` | 3 | False |
| monster14 | Goblin Attack Force | Goblin Attack Force `#566` | 3 | False |
| monster14 | Goblin Elite Attack Force | Goblin Elite Attack Force `#1170` | 3 | False |
| monster14 | Goblin Calligrapher | Goblin Calligrapher `#1006` | 3 | False |
| monster14 | Mad Sword Beast | Mad Sword Beast `#563` | 2 | False |
| monster14 | Man-Thro' Tro' | Man-Thro' Tro' `#982` | 2 | False |
| monster14 | Witch of the Black Forest | Witch of the Black Forest `#257` | 1 | True |
| monster56 | Granmarg the Rock Monarch | Granmarg the Rock Monarch `#1077` | 1 | False |

### `blair_year1` - Blair Flannigan - Year 1

- Opponent: `blair`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **43**; Extra: **0**; unresolved slots: **1**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#e
- FAQ section: `e`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: 1, and I'm almost positive it's a Harpie Girl'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Stray Lambs | Stray Lambs `#913` | 2 | False |
| spell | Malevolent Nuzzler | Malevolent Nuzzler `#127` | 1 | False |
| spell | Toon World | Toon World `#366` | 1 | False |
| trap | Shadow of Eyes | Shadow of Eyes `#558` | 1 | False |
| trap | Skull Dice | Skull Dice `#373` | 2 | False |
| monster14 | Ancient Elf | Ancient Elf `#192` | 1 | False |
| monster14 | Dancing Fairy | Dancing Fairy `#583` | 1 | False |
| monster14 | Dark Elf | Dark Elf `#244` | 1 | False |
| monster14 | Dunames Dark Witch | Dunames Dark Witch `#360` | 2 | False |
| monster14 | Ebon Magician Curran | Ebon Magician Curran `#1181` | 1 | False |
| monster14 | Gemini Elf | Gemini Elf `#234` | 2 | False |
| monster14 | Maiden of the Aqua | Maiden of the Aqua `#513` | 1 | False |
| monster14 | Harpie Girl | Harpie Girl `#1040` | 2 | False |
| monster14 | The Unhappy Maiden | The Unhappy Maiden `#413` | 1 | False |
| monster14 | Toon Gemini Elf | Toon Gemini Elf `#711` | 2 | False |
| monster14 | Toon Mermaid | Toon Mermaid `#330` | 1 | False |
| monster14 | Water Magician | Water Magician `#191` | 1 | False |
| monster14 | White Magician Pikeru | White Magician Pikeru `#948` | 1 | False |
| monster56 | Cyber Dragon | Cyber Dragon `#1152` | 1 | False |
| monster56 | Dark Magician Girl | Dark Magician Girl `#352` | 1 | False |
| monster56 | Toon Dark Magician Girl | Toon Dark Magician Girl `#707` | 1 | False |
| monster7 | Cosmo Queen | Cosmo Queen `#314` | 1 | False |

**Unresolved:** 1 card slot(s). They are not silently filled; see the reason above.

### `brier_year1` - Brier - Year 1

- Opponent: `brier`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **47**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#f
- FAQ section: `f`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Completely done'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| trap | Coffin Seller | Coffin Seller `#718` | 2 | False |
| trap | Minor Goblin Official | Minor Goblin Official `#464` | 1 | False |
| trap | Negate Attack | Negate Attack `#368` | 1 | False |
| trap | Robbin' Goblin | Robbin' Goblin `#414` | 2 | False |
| trap | Robbin' Zombie | Robbin' Zombie `#926` | 2 | False |
| monster14 | D.D. Trainer | D. D. Trainer `#834` | 3 | False |
| monster14 | Giant Orc | Giant Orc `#758` | 2 | False |
| monster14 | Goblin Attack Force | Goblin Attack Force `#566` | 3 | False |
| monster14 | Goblin Elite Attack Force | Goblin Elite Attack Force `#1170` | 3 | False |
| monster14 | Goblin Calligrapher | Goblin Calligrapher `#1006` | 3 | False |
| monster14 | Great Angus | Great Angus `#777` | 3 | False |
| monster14 | Mad Sword Beast | Mad Sword Beast `#563` | 2 | False |
| monster14 | Needle Worm | Needle Worm `#251` | 2 | False |
| monster14 | Witch of the Black Forest | Witch of the Black Forest `#257` | 1 | True |
| monster56 | Mefist the Infernal General | Mefist the Infernal General `#839` | 2 | False |
| monster56 | Penumberal Soldier Lady | Penumbral Soldier Lady `#1017` | 1 | False |

### `chazz_year1` - Chazz Princeton - Year 1

- Opponent: `chazz`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **45**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#g
- FAQ section: `g`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Dark Factory of Mass Production | Dark Factory of Mass Production `#1021` | 2 | False |
| spell | Mystic Plasma Zone | Mystic Plasma Zone `#460` | 2 | False |
| spell | Mystical Space Typhoon | Mystical Space Typhoon `#436` | 1 | False |
| spell | Swords of Revealing Light | Swords of Revealing Light `#153` | 1 | False |
| trap | Hidden Soldier | Hidden Soldier `#716` | 2 | False |
| trap | Magic Jammer | Magic Jammer `#402` | 1 | False |
| trap | Robbin' Zombie | Robbin' Zombie `#926` | 2 | False |
| trap | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 1 | False |
| trap | Trap Hole | Trap Hole `#380` | 1 | False |
| monster14 | Blood Sucker | Blood Sucker `#1102` | 1 | False |
| monster14 | Clown Zombie | Clown Zombie `#47` | 2 | False |
| monster14 | Decayed Commander | Decayed Commander `#756` | 1 | False |
| monster14 | Master Kyonshee | Master Kyonshee `#725` | 3 | False |
| monster14 | Newdoria | Newdoria `#715` | 2 | False |
| monster14 | Zombie Tiger | Zombie Tiger `#757` | 1 | False |
| monster56 | Giga Gagagigo | Giga Gagagigo `#887` | 2 | False |
| monster56 | Mefist the Infernal General | Mefist the Infernal General `#839` | 2 | False |
| monster56 | Legendary Fiend | Legendary Fiend `#708` | 1 | False |
| monster56 | Shadow Ghoul | Shadow Ghoul `#163` | 2 | False |

### `chumley_year1` - Chumley Huffington - Year 1

- Opponent: `chumley`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **50**; Extra: **1**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#h
- FAQ section: `h`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete...whew...'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Beast Fangs | Beast Fangs `#114` | 1 | False |
| spell | Dian Keto the Cure Master | Dian Keto the Cure Master `#147` | 1 | False |
| spell | Fusion Gate | Fusion Gate `#637` | 1 | False |
| spell | Fusion Sage | Fusion Sage `#410` | 1 | False |
| spell | Gaia Power | Gaia Power `#455` | 1 | False |
| spell | Poison Fangs | Poison Fangs `#1090` | 2 | False |
| spell | Polymerization | Polymerization `#381` | 1 | False |
| monster14 | Des Kangaroo | Des Kangaroo `#855` | 3 | False |
| monster14 | Des Koala | Des Koala `#793` | 3 | False |
| monster14 | Des Wombat | Des Wombat `#1125` | 3 | False |
| monster14 | Frenzied Panda | Frenzied Panda `#78` | 2 | False |
| monster14 | Gyaku-Gire Panda | Gyaku-Gire Panda `#819` | 2 | False |
| monster14 | Hyena | Hyena `#1080` | 3 | False |
| monster14 | Kangaroo Champ | Kangaroo Champ `#1079` | 3 | False |
| monster14 | Maji-Gire Panda | Maji-Gire Panda `#1078` | 2 | False |
| monster14 | Nimble Momonga | Nimble Momonga `#448` | 3 | False |
| monster7 | Big Koala | Big Koala `#854` | 3 | False |

Extra Deck evidence:

- Master of Oz -> Master of Oz `#1019` x1

### `crowler_year1` - Vellian Crowler - Year 1

- Opponent: `crowler`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **45**; Extra: **0**; unresolved slots: **4**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#i
- FAQ section: `i`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: 4. I hate you, Crowler.'
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Limiter Removal | Limiter Removal `#556` | 1 | False |
| spell | Mystical Space Typhoon | Mystical Space Typhoon `#436` | 1 | False |
| spell | Power Bond | Power Bond `#1159` | 2 | False |
| trap | Bottomless Shifting Sand | Bottomless Shifting Sand `#703` | 3 | False |
| trap | Fairy Box | Fairy Box `#546` | 1 | False |
| trap | Magic Jammer | Magic Jammer `#402` | 1 | False |
| trap | Red Gadget - Stronghold | Red Gadget - Stronghold `#1033` | 2 | False |
| trap | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 1 | False |
| monster14 | Ancient Gear Soldier | Ancient Gear Soldier `#1113` | 3 | False |
| monster14 | Goblin Elite Attack Force | Goblin Elite Attack Force `#1170` | 2 | False |
| monster14 | Green Gadget | Green Gadget `#1032` | 1 | False |
| monster14 | Gyroid | Gyroid `#1148` | 1 | False |
| monster14 | Insect Knight | Insect Knight `#1076` | 3 | False |
| monster14 | Mighty Guard | Mighty Guard `#1038` | 1 | False |
| monster14 | Red Gadget | Red Gadget `#1034` | 1 | False |
| monster14 | Robotic Knight | Robotic Knight `#514` | 1 | False |
| monster14 | Steamroid | Steamroid `#1149` | 1 | False |
| monster14 | Yellow Gadget | Yellow Gadget `#1035` | 1 | False |
| monster56 | Ancient Gear Beast | Ancient Gear Beast `#1112` | 1 | False |
| monster56 | Machine King | Machine King `#180` | 1 | False |
| monster7 | Ancient Gear Golem | Ancient Gear Golem `#1111` | 1 | False |

**Unresolved:** 4 card slot(s). They are not silently filled; see the reason above.

### `damon_year1` - Damon - Year 1

- Opponent: `damon`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **50**; Extra: **1**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#j
- FAQ section: `j`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Polymerization | Polymerization `#381` | 2 | False |
| spell | Upstart Goblin | Upstart Goblin `#425` | 2 | False |
| trap | Jar of Greed | Jar of Greed `#591` | 3 | False |
| trap | Reckless Greed | Reckless Greed `#706` | 1 | False |
| trap | Solemn Wishes | Solemn Wishes `#553` | 2 | False |
| monster14 | Goblin Calligrapher | Goblin Calligrapher `#1006` | 3 | False |
| monster14 | Muka Muka | Muka Muka `#226` | 3 | False |
| monster14 | Opticlops | Opticlops `#646` | 2 | False |
| monster14 | Poison Draw Frog | Poison Draw Frog `#1178` | 3 | False |
| monster14 | Red Archery Girl | Red Archery Girl `#327` | 3 | False |
| monster14 | Sangan | Sangan `#29` | 1 | False |
| monster14 | Skelengel | Skelengel `#238` | 2 | False |
| monster14 | The Snake Hair | The Snake Hair `#24` | 1 | False |
| monster14 | Warrior Dai Grephyr | Warrior Dai Grepher `#650` | 2 | False |
| monster14 | White Magical Hat | White Magical Hat `#52` | 1 | False |
| monster56 | Enraged Muka Muka | Enraged Muka Muka `#1015` | 2 | False |
| monster56 | Airknight Parshath | Airknight Parshath `#511` | 2 | False |

Extra Deck evidence:

- Sanwitch -> Sanwitch `#1020` x1

### `dimitri_year1` - Dimitri - Year 1

- Opponent: `dimitri`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **51**; Extra: **4**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#k
- FAQ section: `k`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Nothing'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Graceful Dice | Graceful Dice `#372` | 2 | False |
| spell | Mystical Space Typhoon | Mystical Space Typhoon `#436` | 1 | False |
| spell | Polymerization | Polymerization `#381` | 3 | False |
| spell | Scapegoat | Scapegoat `#374` | 2 | False |
| trap | Fairy Box | Fairy Box `#546` | 2 | False |
| trap | Ring of Destruction | Ring of Destruction `#503` | 1 | False |
| trap | Skull Dice | Skull Dice `#373` | 3 | False |
| monster14 | Alligator's Sword | Alligator's Sword `#353` | 1 | False |
| monster14 | Axe Raider | Axe Raider `#38` | 1 | False |
| monster14 | Baby Dragon | Baby Dragon `#3` | 3 | False |
| monster14 | Battle Ox | Battle Ox `#20` | 1 | False |
| monster14 | Battle Warrior | Battle Warrior `#48` | 1 | False |
| monster14 | Copycat | Copycat `#365` | 2 | False |
| monster14 | Gearfried the Iron Knight | Gearfried the Iron Knight `#526` | 2 | False |
| monster14 | Lady Ninja Yae | Lady Ninja Yae `#947` | 1 | False |
| monster14 | Mystical Elf | Mystical Elf `#2` | 1 | False |
| monster14 | Obnoxious Celtic Guardian | Obnoxious Celtic Guard `#614` | 1 | False |
| monster14 | Red Eyes Black Chick | Red-Eyes B. Chick `#1007` | 1 | False |
| monster14 | Vorse Raider | Vorse Raider `#502` | 1 | False |
| monster56 | Summoned Skull | Summoned Skull `#18` | 2 | False |
| monster7 | Gaia the Fierce Knight | Gaia The Fierce Knight `#26` | 1 | False |
| monster7 | Red Eyes Black Dragon | Red-Eyes B. Dragon `#40` | 2 | False |
| monster7 | Red Eyes Darkness Dragon | Red-Eyes Darkness Dragon `#1104` | 1 | False |

Extra Deck evidence:

- Alligator's Sword Dragon -> Alligator's Sword Dragon `#501` x2
- Black Skull Dragon -> B. Skull Dragon `#85` x2

### `fontaine_year1` - Fonda Fontaine - Year 1

- Opponent: `fontaine`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **45**; Extra: **0**; unresolved slots: **2**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#l
- FAQ section: `l`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: 2 (most likely a Seven Tools and a Trap Hole)'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Cyber Shield | Cyber Shield `#123` | 2 | False |
| spell | Elegant Egotist | Elegant Egotist `#124` | 3 | False |
| spell | Harpie's Hunting Ground | Harpies' Hunting Ground `#1062` | 3 | False |
| trap | Negate Attack | Negate Attack `#368` | 2 | False |
| monster14 | Birdface | Birdface `#509` | 2 | False |
| monster14 | Eagle Eye | Eagle Eye `#1050` | 2 | False |
| monster14 | Garuda the Wind Spirit | Garuda the Wind Spirit `#624` | 1 | False |
| monster14 | Harpie Lady #1 | Harpie Lady 1 `#1045` | 1 | False |
| monster14 | Harpie Lady #2 | Harpie Lady 2 `#1046` | 1 | False |
| monster14 | Harpie Lady #3 | Harpie Lady 3 `#1047` | 1 | False |
| monster14 | Harpie Girl | Harpie Girl `#1040` | 3 | False |
| monster14 | Sonic Duck | Sonic Duck `#779` | 2 | False |
| monster14 | Takuhee | Takuhee `#258` | 3 | False |
| monster56 | Harpie Lady Sisters | Harpie Lady Sisters `#33` | 2 | False |
| monster56 | Roc from the Valley of Haze | Roc from the Valley of Haze `#1043` | 1 | False |
| monster7 | Harpie's Pet Dragon | Harpie's Pet Dragon `#168` | 1 | False |

**Unresolved:** 2 card slot(s). They are not silently filled; see the reason above.

### `gerard_year1` - Gerard - Year 1

- Opponent: `gerard`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **44**; Extra: **2**; unresolved slots: **1**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#m
- FAQ section: `m`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: At most, 1'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Contract with the Abyss | Contract with the Abyss `#844` | 1 | False |
| spell | Hamburger Recipe | Hamburger Recipe `#296` | 1 | False |
| spell | Mooyan Curry | Mooyan Curry `#143` | 1 | False |
| spell | Polymerization | Polymerization `#381` | 2 | False |
| spell | Resurrection of Chakra | Resurrection of Chakra `#302` | 1 | False |
| trap | Eatgaboon | Eatgaboon `#299` | 1 | False |
| trap | House of Adhesive Tape | House of Adhesive Tape `#298` | 1 | False |
| trap | Widespread Ruin | Widespread Ruin `#300` | 1 | False |
| monster14 | Ancient Brain | Ancient Brain `#73` | 1 | False |
| monster14 | Armaill | Armaill `#72` | 1 | False |
| monster14 | Behegon | Behegon `#243` | 1 | False |
| monster14 | Mech-Mole Zombie | Mech Mole Zombie `#76` | 1 | False |
| monster14 | M-Warrior #1 | M-Warrior #1 `#65` | 1 | False |
| monster14 | M-Warrior #2 | M-Warrior #2 `#66` | 1 | False |
| monster14 | Niwatori | Niwatori `#237` | 1 | False |
| monster14 | Rhaimundos of the Red Sword | Rhaimundos of the Red Sword `#62` | 1 | False |
| monster14 | Sea Kamen | Sea Kamen `#208` | 1 | False |
| monster14 | Tongyo | Tongyo `#240` | 1 | False |
| monster14 | Tyhone | Tyhone `#10` | 1 | False |
| monster14 | Wasteland Amazon | Wasteland Amazon `#1199` | 1 | False |
| monster14 | Wings of Wicked Flame | Wings of Wicked Flame `#49` | 1 | False |
| monster56 | Bottom Dweller | Bottom Dweller `#194` | 1 | False |
| monster56 | Garoozis | Garoozis `#35` | 1 | False |
| monster56 | Hungry Burger | Hungry Burger `#308` | 1 | False |
| monster56 | Lava Battleguard | Lava Battleguard `#245` | 1 | False |
| monster56 | Ocubeam | Ocubeam `#175` | 1 | False |
| monster56 | Swamp Battleguard | Swamp Battleguard `#9` | 1 | False |
| monster7 | Chakra | Chakra `#315` | 1 | False |

Extra Deck evidence:

- Karbonala Warrior -> Karbonala Warrior `#28` x1
- Deepsea Shark -> Deepsea Shark `#193` x1

**Unresolved:** 1 card slot(s). They are not silently filled; see the reason above.

### `jasmine_year1` - Jasmine - Year 1

- Opponent: `jasmine`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **60**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#o
- FAQ section: `o`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: ...it's complete'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Banner of Courage | Banner of Courage `#739` | 2 | False |
| spell | Legendary Sword | Legendary Sword `#107` | 2 | False |
| spell | Lightning Blade | Lightning Blade `#545` | 3 | False |
| spell | Reinforcements of the Army | Reinforcement of the Army `#653` | 2 | False |
| spell | Sogen | Sogen `#138` | 3 | False |
| spell | The Warrior Returning Alive | The Warrior Returning Alive `#654` | 2 | False |
| trap | Chain Burst | Chain Burst `#1070` | 3 | False |
| trap | Thunder of Ruler | Thunder of Ruler `#771` | 1 | False |
| monster14 | Amazon Archer | Amazon Archer `#578` | 2 | False |
| monster14 | Amazoness Fighter | Amazoness Fighter `#641` | 2 | False |
| monster14 | Amazoness Paladin | Amazoness Paladin `#781` | 2 | False |
| monster14 | Amazoness Swords Woman | Amazoness Swords Woman `#639` | 3 | False |
| monster14 | Beautiful Headhuntress | Beautiful Headhuntress `#89` | 2 | False |
| monster14 | Hibikime | Hibikime `#278` | 2 | False |
| monster14 | Lady Ninja Yae | Lady Ninja Yae `#947` | 1 | False |
| monster14 | Maurading Captain | Marauding Captain `#649` | 1 | False |
| monster14 | Princess of Tsurugi | Princess of Tsurugi `#96` | 1 | False |
| monster14 | Queen's Double | Queen's Double `#272` | 1 | False |
| monster14 | Queen's Knight | Queen's Knight `#723` | 3 | False |
| monster14 | The Unfriendly Amazon | The Unfriendly Amazon `#577` | 2 | False |
| monster14 | Wasteland Amazon | Wasteland Amazon `#1199` | 3 | False |
| monster56 | Penumbral Soldier Lady | Penumbral Soldier Lady `#1017` | 2 | False |

### `mindy_year1` - Mindy - Year 1

- Opponent: `mindy`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **28**; Extra: **0**; unresolved slots: **12**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#p
- FAQ section: `p`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: fixed cards plus a 20-card random normal-monster pool; deck is not a fixed 40-card list.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Dark Magic Curtain | Dark Magic Curtain `#377` | 1 | False |
| spell | Knight's Title | Knight's Title `#831` | 1 | False |
| monster14 | Dimension Warrior | Dimensional Warrior `#95` | 1 | False |
| monster14 | Getsu Fuhma | Getsu Fuhma `#910` | 1 | False |
| monster14 | Harpie's Brother | Harpie's Brother `#490` | 1 | False |
| monster14 | Neo the Magic Swordsman | Neo the Magic Swordsman `#416` | 1 | False |
| monster14 | Obnoxious Celtic Guardian | Obnoxious Celtic Guard `#614` | 1 | False |
| monster14 | Sand Gambler | Sand Gambler `#979` | 1 | False |
| monster14 | Sealmaster Meisei | Sealmaster Meisei `#935` | 1 | False |
| monster14 | Tactical Espionage Expert | Tactical Espionage Expert `#1051` | 1 | False |
| monster56 | Fairy King Truesdale | Fairy King Truesdale `#512` | 1 | False |
| monster7 | Dark Magician | Dark Magician `#23` | 1 | False |
| monster7 | Dark Magician Knight | Dark Magician Knight `#830` | 1 | False |

Random pool (19 evidenced normal monsters, not counted in Main):

Armaill `#72`, Bone Mouse `#242`, Enchanting Mermaid `#93`, Fire Eye `#74`, Flame Manipulator `#58`, Flying Fish `#530`, Frenzied Panda `#78`, Mystical Elf `#2`, Oppressed People `#752`, Petit Dragon `#77`, People Running About `#751`, Red Archery Girl `#327`, Ryu-Kishin `#4`, Snakeyashi `#269`, Sonic Duck `#779`, Souleater `#520`, Spherous Lady `#533`, Trakadon `#255`, United Resistance `#753`

**Unresolved:** 12 card slot(s). They are not silently filled; see the reason above.

### `pharaoh_year1` - Pharaoh - Year 1

- Opponent: `pharaoh`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **39**; Extra: **0**; unresolved slots: **1**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#q
- FAQ section: `q`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Nothing'. Known fixed cards + 15-card Year 1 generic shell = 39; the FAQ's optional 16th generic slot is not identified.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Beast Fangs | Beast Fangs `#114` | 1 | False |
| spell | Horn Of The Unicorn | Horn of the Unicorn `#120` | 1 | False |
| spell | Poison Fangs | Poison Fangs `#1090` | 1 | False |
| spell | The Big March Of Animals | The Big March of Animals `#1095` | 1 | False |
| monster14 | Bone Mouse | Bone Mouse `#242` | 1 | False |
| monster14 | Chu-Ske The Mouse Fighter | Chu-Ske the Mouse Fighter `#1075` | 1 | False |
| monster14 | Giant Rat | Giant Rat `#442` | 1 | False |
| monster14 | Giga-Tech Wolf | Giga-Tech Wolf `#183` | 1 | False |
| monster14 | Iron Blacksmith Kotetsu | Iron Blacksmith Kotetsu `#838` | 1 | False |
| monster14 | Mad Dog of Darkness | Mad Dog of Darkness `#888` | 1 | False |
| monster14 | Manju of the Ten Thousand Hands | Manju of the Ten Thousand Hands `#909` | 1 | False |
| monster14 | Mecha-Dog Marron | Mecha-Dog Marron `#1082` | 1 | False |
| monster14 | Mystical Sheep #2 | Mystical Sheep #2 `#100` | 1 | False |
| monster14 | Outstanding Dog Marron | Outstanding Dog Marron `#837` | 1 | False |
| monster14 | Panther Warrior | Panther Warrior `#342` | 1 | False |
| monster14 | Pitch-Black Warwolf | Pitch-Black Warwolf `#1054` | 1 | False |
| monster14 | Silver Fang | Silver Fang `#34` | 1 | False |
| monster14 | Skull Dog Marron | Skull Dog Marron `#1005` | 1 | False |
| monster14 | Soul Tiger | Soul Tiger `#853` | 1 | False |
| monster14 | The All-Seeing White Tiger | The All-Seeing White Tiger `#565` | 1 | False |
| monster14 | Wolf Axewielder | Wolf Axwielder `#507` | 1 | False |
| monster14 | Zombie Tiger | Zombie Tiger `#757` | 1 | False |
| monster56 | Ancient Gear Beast | Ancient Gear Beast `#1112` | 1 | False |
| monster56 | Mechanical Hound | Mechanical Hound `#1169` | 1 | False |

**Unresolved:** 1 card slot(s). They are not silently filled; see the reason above.

### `sartyr_year1` - Sartyr - Year 1

- Opponent: `sartyr`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **43**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#r
- FAQ section: `r`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Cyclon Laser | Cyclon Laser `#632` | 2 | False |
| monster14 | A-Team: Trap Disposal Unit | A-Team: Trap Disposal Unit `#1058` | 2 | False |
| monster14 | Getsu Fuhma | Getsu Fuhma `#910` | 2 | False |
| monster14 | Gradius | Gradius `#562` | 3 | False |
| monster14 | Gradius' Option | Gradius' Option `#676` | 3 | False |
| monster14 | Moai Interceptor Cannons | Moai Interceptor Cannons `#1116` | 2 | False |
| monster14 | Penguin Soldier | Penguin Soldier `#262` | 3 | False |
| monster14 | Soitsu | Soitsu `#1165` | 3 | False |
| monster14 | Space Mambo | Space Mambo `#1073` | 3 | False |
| monster14 | Tainted Wisdom | Tainted Wisdom `#67` | 2 | False |
| monster56 | Aitsu | Aitsu `#778` | 3 | False |

### `syrus_year1` - Syrus Truesdale - Year 1

- Opponent: `syrus`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **45**; Extra: **1**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#s
- FAQ section: `s`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Black Pendant | Black Pendant `#117` | 3 | False |
| spell | Fusion Gate | Fusion Gate `#637` | 2 | False |
| spell | Fusion Sage | Fusion Sage `#410` | 1 | False |
| spell | Fusion Weapon | Fusion Weapon `#1025` | 1 | False |
| spell | Limiter Removal | Limiter Removal `#556` | 2 | False |
| spell | Polymerization | Polymerization `#381` | 1 | False |
| spell | Shield Crash | Shield Crash `#964` | 1 | False |
| trap | Negate Attack | Negate Attack `#368` | 1 | False |
| monster14 | A-Team: Trap Disposal Unit | A-Team: Trap Disposal Unit `#1058` | 1 | False |
| monster14 | Bokoichi the Freightening Car | Bokoichi the Freightening Car `#1039` | 3 | False |
| monster14 | Dekoichi the Battlechained Locotmotive | Dekoichi the Battlechanted Locomotive `#1057` | 3 | False |
| monster14 | Drilloid | Drillroid `#1150` | 1 | False |
| monster14 | Cycroid | Cycroid `#1146` | 1 | False |
| monster14 | Gyroid | Gyroid `#1148` | 2 | False |
| monster14 | Harpie Girl | Harpie Girl `#1040` | 1 | False |
| monster14 | Patroid | Patroid `#1147` | 1 | False |
| monster14 | Steamroid | Steamroid `#1149` | 2 | False |
| monster56 | Big Core | Big Core `#1056` | 1 | False |
| monster56 | UFOroid | UFOroid `#1151` | 2 | False |

Extra Deck evidence:

- Steam Gyroid -> Steam Gyroid `#1155` x1

### `torrey_year1` - Torrey - Year 1

- Opponent: `torrey`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **48**; Extra: **0**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#t
- FAQ section: `t`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | The Dark Door | The Dark Door `#603` | 1 | False |
| spell | The Shallow Grave | The Shallow Grave `#476` | 2 | False |
| trap | Magic Jammer | Magic Jammer `#402` | 1 | False |
| trap | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 1 | False |
| trap | Trap Hole | Trap Hole `#380` | 2 | False |
| monster14 | Aswan Apparition | Aswan Apparition `#975` | 2 | False |
| monster14 | Dokuroyaiba | Dokuroyaiba `#571` | 1 | False |
| monster14 | Earthbound Spirit | Earthbound Spirit `#604` | 2 | False |
| monster14 | Headless Knight | Headless Knight `#600` | 2 | False |
| monster14 | Master Kyonshee | Master Kyonshee `#725` | 3 | False |
| monster14 | Mystical Elf | Mystical Elf `#2` | 1 | False |
| monster14 | Phantom Ghost | Phantom Ghost `#79` | 1 | False |
| monster14 | Souls of the Forgotten | Souls of the Forgotten `#570` | 2 | False |
| monster14 | Spirit Caller | Spirit Caller `#981` | 1 | False |
| monster14 | The Gross Ghost of Fled Dreams | The Gross Ghost of Fled Dreams `#599` | 2 | False |
| monster14 | The Portrait's Secret | The Portrait's Secret `#598` | 1 | False |
| monster14 | The Wandering Doomed | The Wandering Doomed `#247` | 2 | False |
| monster14 | Theban Nightmare | Theban Nightmare `#974` | 2 | False |
| monster56 | Magical Marionette | Magical Marionette `#786` | 2 | False |
| monster56 | The Earl of Demise | The Earl of Demise `#605` | 2 | False |

### `zane_year1` - Zane Truesdale - Year 1

- Opponent: `zane`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **50**; Extra: **2**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#v
- FAQ section: `v`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete (pain-in-the-rear)'.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Black Luster Ritual | Black Luster Ritual `#290` | 1 | False |
| spell | Dragon's Mirror | Dragon's Mirror `#1185` | 2 | False |
| spell | Fusion Gate | Fusion Gate `#637` | 1 | False |
| spell | Limiter Removal | Limiter Removal `#556` | 3 | False |
| spell | Mystical Space Typhoon | Mystical Space Typhoon `#436` | 1 | False |
| spell | Power Bond | Power Bond `#1159` | 3 | False |
| spell | Swords Of Revealing Light | Swords of Revealing Light `#153` | 1 | False |
| trap | Fairy Box | Fairy Box `#546` | 1 | False |
| trap | Ring Of Destruction | Ring of Destruction `#503` | 1 | False |
| monster14 | Battle Footballer | Battle Footballer `#816` | 3 | False |
| monster14 | Cyber Jar | Cyber Jar `#440` | 1 | False |
| monster14 | Cyber-Stein | Cyber-Stein `#186` | 1 | False |
| monster14 | Gyroid | Gyroid `#1148` | 1 | False |
| monster14 | Mataza the Zapper | Mataza the Zapper `#907` | 1 | False |
| monster14 | Mechanicalchaser | Mechanicalchaser `#184` | 3 | False |
| monster14 | Reflect Bounder | Reflect Bounder `#350` | 1 | False |
| monster14 | Steamroid | Steamroid `#1149` | 1 | False |
| monster14 | Zombyra The Dark | Zombyra the Dark `#615` | 1 | False |
| monster56 | Blowback Dragon | Blowback Dragon `#940` | 1 | False |
| monster56 | Cyber Dragon | Cyber Dragon `#1152` | 3 | False |
| monster56 | Machine King | Machine King `#180` | 1 | False |
| monster56 | UFOroid | UFOroid `#1151` | 1 | False |
| monster7 | Barrel Dragon | Barrel Dragon `#340` | 1 | False |
| monster7 | Black Luster Soldier | Black Luster Soldier `#160` | 1 | False |
| monster7 | Black Luster Soldier - Envoy Of The Beginning | Black Luster Soldier - Envoy of the Beginning `#868` | 1 | True |
| monster7 | Chaos Emperor Dragon - Envoy Of The End | Chaos Emperor Dragon - Envoy of the End `#886` | 1 | True |

Extra Deck evidence:

- Cyber End Dragon -> Cyber End Dragon `#1158` x1
- Cyber Twin Dragon -> Cyber Twin Dragon `#1157` x1
- Gatling Dragon -> Gatling Dragon `#1088` x1
- Steam Gyroid -> Steam Gyroid `#1155` x1

### `shadow_duelist_year1` - The Shadow Duelist - Year 1

- Opponent: `shadow_duelist`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **16**; Extra: **0**; unresolved slots: **24**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#w
- FAQ section: `w`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: only Archfiend Soldier remembered ('Yep...that's all I remember...'). 24 unknown slots remain after the known card and the 15-card generic shell.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| monster14 | Archfiend Soldier | Archfiend Soldier `#836` | 1 | False |

**Unresolved:** 24 card slot(s). They are not silently filled; see the reason above.

### `mimicry_year1` - Mimicry / Test Proctor - Year 1

- Opponent: `mimicry`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **46**; Extra: **0**; unresolved slots: **0**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#x
- FAQ section: `x`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: I've gotta see if I memorized this correctly...' (author unverified).
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Big Bang Shot | Big Bang Shot `#796` | 3 | False |
| spell | Shinato's Ark | Shinato's Ark `#822` | 2 | False |
| spell | Sword of the Deep-Seated | Sword of Deep-Seated `#411` | 2 | False |
| trap | Enchanted Javelin | Enchanted Javelin `#499` | 3 | False |
| trap | Numinous Healer | Numinous Healer `#463` | 3 | False |
| monster14 | Fire Princess | Fire Princess `#579` | 3 | False |
| monster14 | Granadora | Granadora `#811` | 3 | False |
| monster14 | Kiseitai | Kiseitai `#486` | 3 | False |
| monster14 | Nimble Momonga | Nimble Momonga `#448` | 3 | False |
| monster56 | Marie the Fallen One | Marie the Fallen One `#590` | 2 | False |
| monster7 | Guardian Angel Joan | Guardian Angel Joan `#908` | 2 | False |
| monster7 | Shinato, King of a Higher Plane | Shinato, King of a Higher Plane `#812` | 2 | False |

### `topher_year1` - Topher - Year 1

- Opponent: `topher`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **17**; Extra: **0**; unresolved slots: **23**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#event
- FAQ section: `event`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: Yugipedia Opponents page gives only Blast Sphere and Giant Germ; the rest of the deck is undocumented. 23 slots remain after the two signature cards and the 15-card generic shell.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| monster14 | Blast Sphere | Blast Sphere `#336` | 1 | False |
| monster14 | Giant Germ | Giant Germ `#447` | 1 | False |

**Unresolved:** 23 card slot(s). They are not silently filled; see the reason above.

### `conklin_year1` - Conklin - Year 1

- Opponent: `conklin`
- Type: `opponent`; status: **partial**; complete: **False**
- Main: **17**; Extra: **0**; unresolved slots: **23**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#event
- FAQ section: `event`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: Yugipedia Opponents page gives only UFO Turtle and Blazing Inpachi; the rest of the deck is undocumented. 23 slots remain after the two signature cards and the 15-card generic shell.
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| monster14 | UFO Turtle | UFO Turtle `#444` | 1 | False |
| monster14 | Blazing Inpachi | Blazing Inpachi `#892` | 1 | False |

**Unresolved:** 23 card slot(s). They are not silently filled; see the reason above.

### `sheppard_year1` - Chancellor Sheppard - Year 1

- Opponent: `sheppard`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **48**; Extra: **3**; unresolved slots: **0**
- Confidence: **high**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#y
- FAQ section: `y`
- Generic shell applied: yes (15-card Year 1 selection)
- Unresolved reason: FAQ v1.4: 'Missing: Complete, unless this guy's got a F.G.D., too.'
- Notes: Fixed cards and counts transcribed from the named FAQ section. Year 1 generic shell appended where use_generic_shell is true.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Burst Stream of Destruction | Burst Stream of Destruction `#951` | 2 | False |
| spell | Dragon Treasure | Dragon Treasure `#121` | 2 | False |
| spell | Dragon's Mirror | Dragon's Mirror `#1185` | 2 | False |
| spell | Megamorph | Megamorph `#282` | 2 | False |
| spell | Sebek's Blessing | Sebek's Blessing `#505` | 3 | False |
| trap | Burst Breath | Burst Breath `#662` | 1 | False |
| trap | Dragon's Rage | Dragon's Rage `#661` | 1 | False |
| trap | Ring of Destruction | Ring of Destruction `#503` | 1 | False |
| monster14 | Cyber-Stein | Cyber-Stein `#186` | 3 | False |
| monster14 | La Jinn the Mystical Genie | La Jinn the Mystical Genie of the Lamp `#165` | 3 | False |
| monster14 | Spear Dragon | Spear Dragon `#655` | 2 | False |
| monster14 | The Dragon Dwelling in the Cave | The Dragon dwelling in the Cave `#656` | 3 | False |
| monster14 | Vorse Raider | Vorse Raider `#502` | 3 | False |
| monster56 | Emerald Dragon | Luster Dragon `#663` | 2 | False |
| monster7 | Blue-Eyes White Dragon | Blue-Eyes White Dragon `#1` | 3 | False |

Extra Deck evidence:

- Blue-Eyes Ultimate Dragon -> Blue-Eyes Ultimate Dragon `#166` x3

### `jaden_year1` - Jaden Yuki - Year 1

- Opponent: `jaden`
- Type: `opponent`; status: **complete**; complete: **True**
- Main: **53**; Extra: **4**; unresolved slots: **0**
- Confidence: **medium**
- Source: game3d/src/duel/decklists.js (local donor; not committed) + https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#n
- FAQ section: `n`
- Generic shell applied: no
- Notes: Donor implementation list (game3d/src/duel/decklists.js), not independently verified against a ROM deck table. FAQ section n independently lists the same archetype; its character-specific list totals 34 cards before the generic shell and says a few cards are missing.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| donor | Cyber-Tech Alligator | Cyber-Tech Alligator `#363` | 1 | False |
| donor | Elemental Hero Avian | Elemental Hero Avian `#1106` | 1 | False |
| donor | Elemental Hero Avian | Elemental Hero Avian `#1106` | 1 | False |
| donor | Elemental Hero Burstinatrix | Elemental Hero Burstinatrix `#1107` | 1 | False |
| donor | Elemental Hero Burstinatrix | Elemental Hero Burstinatrix `#1107` | 1 | False |
| donor | Elemental Hero Clayman | Elemental Hero Clayman `#1108` | 1 | False |
| donor | Elemental Hero Clayman | Elemental Hero Clayman `#1108` | 1 | False |
| donor | Elemental Hero Sparkman | Elemental Hero Sparkman `#1109` | 1 | False |
| donor | Elemental Hero Sparkman | Elemental Hero Sparkman `#1109` | 1 | False |
| donor | Luster Dragon | Luster Dragon `#780` | 1 | False |
| donor | Luster Dragon | Luster Dragon `#780` | 1 | False |
| donor | Luster Dragon | Luster Dragon `#663` | 1 | False |
| donor | Luster Dragon | Luster Dragon `#663` | 1 | False |
| donor | Cyber Jar | Cyber Jar `#440` | 1 | False |
| donor | Elemental Hero Bubbleman | Elemental Hero Bubbleman `#1154` | 1 | False |
| donor | Elemental Hero Bubbleman | Elemental Hero Bubbleman `#1154` | 1 | False |
| donor | Hane-Hane | Hane-Hane `#239` | 1 | False |
| donor | Kaiser Glider | Kaiser Glider `#666` | 1 | False |
| donor | Man-Eater Bug | Man-Eater Bug `#221` | 1 | False |
| donor | Penguin Soldier | Penguin Soldier `#262` | 1 | False |
| donor | Spear Dragon | Spear Dragon `#655` | 1 | False |
| donor | Spear Dragon | Spear Dragon `#655` | 1 | False |
| donor | Spear Dragon | Spear Dragon `#655` | 1 | False |
| donor | Winged Kuriboh | Winged Kuriboh `#1110` | 1 | False |
| donor | Winged Kuriboh LV10 | Winged Kuriboh LV10 `#1161` | 1 | False |
| donor | Card Destruction | Card Destruction `#375` | 1 | False |
| donor | Dragon's Mirror | Dragon's Mirror `#1185` | 1 | False |
| donor | Fusion Weapon | Fusion Weapon `#1025` | 1 | False |
| donor | Fusion Weapon | Fusion Weapon `#1025` | 1 | False |
| donor | Graceful Charity | Graceful Charity `#370` | 1 | False |
| donor | Heavy Storm | Heavy Storm `#422` | 1 | False |
| donor | Mage Power | Mage Power `#594` | 1 | False |
| donor | Miracle Fusion | Miracle Fusion `#1184` | 1 | False |
| donor | Monster Reincarnation | Monster Reincarnation `#1065` | 1 | False |
| donor | Polymerization | Polymerization `#381` | 1 | False |
| donor | Pot of Greed | Pot of Greed `#387` | 1 | False |
| donor | Premature Burial | Premature Burial `#477` | 1 | False |
| donor | Skyscraper | Skyscraper `#1160` | 1 | False |
| donor | Snatch Steal | Snatch Steal `#428` | 1 | False |
| donor | Transcendent Wings | Transcendent Wings `#1162` | 1 | False |
| donor | United We Stand | United We Stand `#593` | 1 | False |
| donor | A Hero Emerges | A Hero Emerges `#921` | 1 | False |
| donor | Call of the Haunted | Call of the Haunted `#497` | 1 | False |
| donor | Hero Signal | Hero Signal `#1136` | 1 | False |
| donor | Magic Cylinder | Magic Cylinder `#552` | 1 | False |
| donor | Magic Jammer | Magic Jammer `#402` | 1 | False |
| donor | Magic Jammer | Magic Jammer `#402` | 1 | False |
| donor | Mirror Force | Mirror Force `#421` | 1 | False |
| donor | Negate Attack | Negate Attack `#368` | 1 | False |
| donor | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 1 | False |
| donor | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 1 | False |
| donor | Torrential Tribute | Torrential Tribute `#547` | 1 | False |
| donor | Trap Hole | Trap Hole `#380` | 1 | False |

Extra Deck evidence:

- Elemental Hero Flame Wingman -> Elemental Hero Flame Wingman `#1129` x1
- Elemental Hero Thunder Giant -> Elemental Hero Thunder Giant `#1130` x1
- Elemental Hero Shining Flare Wingman -> Elemental Hero Shining Flare Wingman `#1200` x1
- F.G.D. -> F.G.D. `#722` x1

### `jinzo_spirit` - Jinzo - Spirit Deck

- Opponent: `jinzo`
- Type: `event`; status: **unknown**; complete: **False**
- Main: **0**; Extra: **0**; unresolved slots: **40**
- Confidence: **low**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_8:_Jinzo
- Generic shell applied: no
- Unresolved reason: E08 identifies the opponent as the spirit of Jinzo, but no deck list is published or extracted. Do not infer a 40-card list from the ace card.

- No evidenced card list; the deck is an explicit unknown.

**Unresolved:** 40 card slot(s). They are not silently filled; see the reason above.

### `damon_exodia` - Damon - Exodia Draw (Event)

- Opponent: `damon`
- Type: `event`; status: **partial**; complete: **False**
- Main: **5**; Extra: **0**; unresolved slots: **35**
- Confidence: **low**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_22:_Draw,_draw,_draw
- Generic shell applied: no
- Unresolved reason: E22 says both sides use Damon's draw/Exodia deck, but no exact list is published. Only the five Exodia pieces are explicitly evidenced. The FAQ's complete Damon deck is a different draw deck with no Exodia pieces; the event deck therefore remains unresolved.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| monster | Right Leg of the Forbidden One | Right Leg of the Forbidden One `#13` | 1 | False |
| monster | Left Leg of the Forbidden One | Left Leg of the Forbidden One `#14` | 1 | False |
| monster | Right Arm of the Forbidden One | Right Arm of the Forbidden One `#15` | 1 | False |
| monster | Left Arm of the Forbidden One | Left Arm of the Forbidden One `#16` | 1 | False |
| monster | Exodia the Forbidden One | Exodia the Forbidden One `#17` | 1 | False |

**Unresolved:** 35 card slot(s). They are not silently filled; see the reason above.

### `yugi_deck` - Yugi Muto - Legendary Deck (Event)

- Opponent: `dimitri`
- Type: `event`; status: **partial**; complete: **False**
- Main: **39**; Extra: **2**; unresolved slots: **5**
- Confidence: **medium**
- Source: https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#u
- Generic shell applied: no
- Unresolved reason: FAQ v1.4: 'Missing: 5 or so (my guess is Gazelle x2, Magic Jammer, Swords of Revealing Light, and perhaps a Fusion Gate)'. The five cards are not encoded as facts.

| Category | Source name | Canon card | Count | Optional |
| --- | --- | --- | ---: | --- |
| spell | Dark Magic Attack | Special Hurricane `#983` | 2 | False |
| spell | Dark Magician's Tome of Black Magic | 7 `#986` | 2 | False |
| spell | Dedication through Light and Darkness | Soul Reversal `#985` | 1 | False |
| spell | Polymerization | Polymerization `#381` | 1 | False |
| spell | Sage's Stone | Order to Charge `#984` | 1 | False |
| spell | Swords of Revealing Light | Swords of Revealing Light `#153` | 2 | False |
| spell | Thousand Knives | Thousand Knives `#575` | 1 | False |
| spell | Tricky's Magic 4 | Tricky's Magic 4 `#1036` | 1 | False |
| trap | Magic Cylinder | Magic Cylinder `#552` | 3 | False |
| trap | Magic Jammer | Magic Jammer `#402` | 1 | False |
| trap | Seven Tools of the Bandit | Seven Tools of the Bandit `#403` | 2 | False |
| monster14 | Berfomet | Berfomet `#345` | 2 | False |
| monster14 | King's Knight | King's Knight `#748` | 3 | False |
| monster14 | Kuriboh | Kuriboh `#31` | 2 | False |
| monster14 | Queen's Knight | Queen's Knight `#723` | 3 | False |
| monster56 | Dark Magician Girl | Dark Magician Girl `#352` | 1 | False |
| monster56 | Jack's Knight | Jack's Knight `#749` | 3 | False |
| monster56 | The Tricky | Tricky `#1031` | 1 | False |
| monster7 | Black Luster Soldier - Envoy of the Beginning | Golem Sentry `#1086` | 1 | False |
| monster7 | Buster Blader | Buster Blader `#493` | 2 | False |
| monster7 | Dark Magician | Dark Magician `#23` | 3 | False |
| monster7 | Dark Magician of Chaos | Dark Magician of Chaos `#896` | 1 | False |

Extra Deck evidence:

- Chimera the Flying Mythical Beast -> Chimera the Flying Mythical Beast `#346` x1
- Dark Paladin -> Dark Paladin `#776` x1

**Unresolved:** 5 card slot(s). They are not silently filled; see the reason above.

### `bastion_seventh` - Bastion Misawa - Seventh Deck

- Opponent: `bastion`
- Type: `event`; status: **unknown**; complete: **False**
- Main: **0**; Extra: **0**; unresolved slots: **40**
- Confidence: **low**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_26:_The_7th_Deck + dialogue index 4230
- Generic shell applied: no
- Unresolved reason: E26/Dialogue call it a new "Seventh Deck" built to beat Jaden, but no list or archetype is documented. Do not substitute Bastion's normal Magnet deck.

- No evidenced card list; the deck is an explicit unknown.

**Unresolved:** 40 card slot(s). They are not silently filled; see the reason above.

### `torrey_special` - Torrey - Special Player Deck

- Opponent: `torrey`
- Type: `player_override`; status: **unknown**; complete: **False**
- Main: **0**; Extra: **0**; unresolved slots: **40**
- Confidence: **low**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_7:_Occult_Recommendation
- Generic shell applied: no
- Unresolved reason: E07 makes the player use a special deck made by Torrey; no list is published. E07 still references this override; it is not an opponent deck.

- No evidenced card list; the deck is an explicit unknown.

**Unresolved:** 40 card slot(s). They are not silently filled; see the reason above.

### `chazz_ojama` - Chazz Princeton - Ojama

- Opponent: `chazz`
- Type: `opponent_variant`; status: **unknown**; complete: **False**
- Main: **0**; Extra: **0**; unresolved slots: **40**
- Confidence: **low**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events
- Generic shell applied: no
- Unresolved reason: Event 15 deck; full list not published.

- No evidenced card list; the deck is an explicit unknown.

**Unresolved:** 40 card slot(s). They are not silently filled; see the reason above.

### `jaden_improved` - Jaden Yuki - Improved

- Opponent: `jaden`
- Type: `opponent_variant`; status: **unknown**; complete: **False**
- Main: **0**; Extra: **0**; unresolved slots: **40**
- Confidence: **low**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events
- Generic shell applied: no
- Unresolved reason: Event 3 upgrade; full list not published.

- No evidenced card list; the deck is an explicit unknown.

**Unresolved:** 40 card slot(s). They are not silently filled; see the reason above.

### `bastion_magnet` - Bastion Misawa - Magnet

- Opponent: `bastion`
- Type: `opponent_variant`; status: **unknown**; complete: **False**
- Main: **0**; Extra: **0**; unresolved slots: **40**
- Confidence: **low**
- Source: https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Opponents
- Generic shell applied: no
- Unresolved reason: One of six Bastion decks; only signature cards documented.

- No evidenced card list; the deck is an explicit unknown.

**Unresolved:** 40 card slot(s). They are not silently filled; see the reason above.

## 4. Event constructs and opponent reconciliation

The three bracket/partner constructs are not roster duelists. They are
represented as `tournament` or `partner_pool` objects in `events.json`;
their participants resolve to existing roster ids and year-1 decks.

| Construct | Kind | Participants | Rounds | Used by | Evidence |
| --- | --- | --- | ---: | --- | --- |
| `festival_bracket` | tournament | ranked_roster | None | E09 | E09 Interdorm Duel; exact bracket and rounds are not published. |
| `chocolate_bracket` | tournament | fontaine, alexis, jasmine, mindy, blair | 4 | E28 | E28 four-round Valentine tournament; the event requires the five female characters. |
| `walk_home_partner` | partner_pool | jaden, syrus, chumley, bastion, alexis, chazz, zane | 1 | E31 | E31 duel against the character walked home with three times; reward table names the pool. |

### Added event opponents

| Opponent id | Name | Deck | Evidence |
| --- | --- | --- | --- |
| `jinzo` | Jinzo (spirit) | jinzo_spirit | Spirit possessing Torrey; E08 opponent. |
| `goblin_king` | Goblin King / Duel Giant | timed_puzzle | E17 timed duel; the Duel Giant is Brier and Beauregard under a mask. |
| `sheppard` | Chancellor Sheppard | sheppard_year1 | E33 King of Games promotion duel; complete deck in Character Deck List FAQ v1.4 section y. |

## 5. Remaining unknowns

| Area | Remaining unknown | Evidence/why it stays open | Owner |
| --- | --- | --- | --- |
| Partial opponent decks | 15 decks / 140 slots | The FAQ marks missing cards or optional/dorm-dependent slots; each record carries an explicit `unresolved_slots` count. | A07 |
| Fully unknown decks | 6 decks / 240 slots | `jinzo_spirit`, `bastion_seventh`, `torrey_special`, `chazz_ojama`, `jaden_improved`, `bastion_magnet`; no published list. | A07 |
| Generic shell 16th slot | 1 shared slot | FAQ says 15 or 16; only the 15-card Year 1 selection is proven. | A01/A07 |
| ROM deck table | not located | Raw u16 and compressed-block scans found no contiguous deck table. | A01 |
| Exam week | exact Friday | ROM/exam calendar routine not decoded; a raw search found no 12-entry exam-date table; fallback is last Friday, marked unproven. | A02 |

