# Canon traceability matrix

Generated: 2026-10-31T09:24:44+00:00

One row per runtime ID. `Source` is a ROM offset, a public-guide URL, or an explicit inference.
`Confidence` is `exact` only for byte-verified ROM data; everything guide-derived is marked.

## Coverage summary

| Type | Count | Source of truth | Confidence | Used by |
| --- | ---: | --- | --- | --- |
| Cards | 1200 | ROM 0xF243CC / 0xF2A68C / 0xF58294 | exact | A05, A06 |
| Packs | 48 | Yugipedia set pages + ROM pack names | high price/pool, low odds | A06 |
| Events | 35 | Yugipedia Events + ROM dialogue | high/medium | A03 |
| Opponents | 28 (25 named + 3 event) | Yugipedia Opponents + ROM name pool | medium | A07 |
| Decks | 37 (16 complete) | starter guide + Character Deck FAQ v1.4 + donor Jaden | high starters, mixed opponents | A06, A07 |
| Puzzles | 100 | Yugipedia puzzle pages | high solution, unknown setup | A07 |
| Titles | 14 | ROM 0x146C858 + guides | mixed | A02 |
| Banned/Limited | 63 | Yugipedia Banned List | high | A04, A06 |
| Written exam templates | 89 | ROM 0x1430F2C | high templates, low keys | A07 |
| Dialogue strings | 4527 | ROM 0x13F6DF0 / table 0x14280A0 | high offsets, local-only text | A03, A09 |
| Dialogue keys | 4527 | `DLG_XXXX` over the same index | high key stability | A03, A09 |

## Cards

| ID | Name | Type | Attribute | Level | ATK | DEF | Source | Confidence |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | Blue-Eyes White Dragon | Normal Monster | LIGHT | 8 | 3000 | 2500 | ROM 0xF243D0 | exact |
| 2 | Mystical Elf | Normal Monster | LIGHT | 4 | 800 | 2000 | ROM 0xF243D4 | exact |
| 3 | Baby Dragon | Normal Monster | WIND | 3 | 1200 | 700 | ROM 0xF243D8 | exact |
| 4 | Ryu-Kishin | Normal Monster | DARK | 3 | 1000 | 500 | ROM 0xF243DC | exact |
| 5 | Feral Imp | Normal Monster | DARK | 4 | 1300 | 1400 | ROM 0xF243E0 | exact |
| 6 | Winged Dragon,Guardian of the Fortress #1 | Normal Monster | WIND | 4 | 1400 | 1200 | ROM 0xF243E4 | exact |
| 7 | Shadow Specter | Normal Monster | DARK | 1 | 500 | 200 | ROM 0xF243E8 | exact |
| 8 | Blackland Fire Dragon | Normal Monster | DARK | 4 | 1500 | 800 | ROM 0xF243EC | exact |
| 9 | Swamp Battleguard | Effect Monster | EARTH | 5 | 1800 | 1500 | ROM 0xF243F0 | exact |
| 10 | Tyhone | Normal Monster | WIND | 4 | 1200 | 1400 | ROM 0xF243F4 | exact |
| 11 | Flame Swordsman | Fusion Monster | FIRE | 5 | 1800 | 1600 | ROM 0xF243F8 | exact |
| 12 | Time Wizard | Effect Monster | LIGHT | 2 | 500 | 400 | ROM 0xF243FC | exact |
| 13 | Right Leg of the Forbidden One | Normal Monster | DARK | 1 | 200 | 300 | ROM 0xF24400 | exact |
| 14 | Left Leg of the Forbidden One | Normal Monster | DARK | 1 | 200 | 300 | ROM 0xF24404 | exact |
| 15 | Right Arm of the Forbidden One | Normal Monster | DARK | 1 | 200 | 300 | ROM 0xF24408 | exact |
| 16 | Left Arm of the Forbidden One | Normal Monster | DARK | 1 | 200 | 300 | ROM 0xF2440C | exact |
| 17 | Exodia the Forbidden One | Effect Monster | DARK | 3 | 1000 | 1000 | ROM 0xF24410 | exact |
| 18 | Summoned Skull | Normal Monster | DARK | 6 | 2500 | 1200 | ROM 0xF24414 | exact |
| 19 | Skull Servant | Normal Monster | DARK | 1 | 300 | 200 | ROM 0xF24418 | exact |
| 20 | Battle Ox | Normal Monster | EARTH | 4 | 1700 | 1000 | ROM 0xF2441C | exact |
| 21 | Zombie Warrior | Fusion Monster | DARK | 3 | 1200 | 900 | ROM 0xF24420 | exact |
| 22 | Two-Headed King Rex | Normal Monster | EARTH | 4 | 1600 | 1200 | ROM 0xF24424 | exact |
| 23 | Dark Magician | Normal Monster | DARK | 7 | 2500 | 2100 | ROM 0xF24428 | exact |
| 24 | The Snake Hair | Normal Monster | DARK | 4 | 1500 | 1200 | ROM 0xF2442C | exact |
| 25 | Gaia the Dragon Champion | Fusion Monster | WIND | 7 | 2600 | 2100 | ROM 0xF24430 | exact |
| 26 | Gaia The Fierce Knight | Normal Monster | EARTH | 7 | 2300 | 2100 | ROM 0xF24434 | exact |
| 27 | Curse of Dragon | Normal Monster | DARK | 5 | 2000 | 1500 | ROM 0xF24438 | exact |
| 28 | Karbonala Warrior | Fusion Monster | EARTH | 4 | 1500 | 1200 | ROM 0xF2443C | exact |
| 29 | Sangan | Effect Monster | DARK | 3 | 1000 | 600 | ROM 0xF24440 | exact |
| 30 | Hercules Beetle | Normal Monster | EARTH | 5 | 1500 | 2000 | ROM 0xF24444 | exact |
| 31 | Kuriboh | Effect Monster | DARK | 1 | 300 | 200 | ROM 0xF24448 | exact |
| 32 | Harpie Lady | Normal Monster | WIND | 4 | 1300 | 1400 | ROM 0xF2444C | exact |
| 33 | Harpie Lady Sisters | Effect Monster | WIND | 6 | 1950 | 2100 | ROM 0xF24450 | exact |
| 34 | Silver Fang | Normal Monster | EARTH | 3 | 1200 | 800 | ROM 0xF24454 | exact |
| 35 | Garoozis | Normal Monster | FIRE | 5 | 1800 | 1500 | ROM 0xF24458 | exact |
| 36 | Thousand Dragon | Fusion Monster | WIND | 7 | 2400 | 2000 | ROM 0xF2445C | exact |
| 37 | Giant Soldier of Stone | Normal Monster | EARTH | 3 | 1300 | 2000 | ROM 0xF24460 | exact |
| 38 | Axe Raider | Normal Monster | EARTH | 4 | 1700 | 1150 | ROM 0xF24464 | exact |
| 39 | Crawling Dragon #2 | Normal Monster | EARTH | 4 | 1600 | 1200 | ROM 0xF24468 | exact |
| 40 | Red-Eyes B. Dragon | Normal Monster | DARK | 7 | 2400 | 2000 | ROM 0xF2446C | exact |
| 41 | Barox | Fusion Monster | DARK | 5 | 1380 | 1530 | ROM 0xF24470 | exact |
| 42 | Catapult Turtle | Effect Monster | WATER | 5 | 1000 | 2000 | ROM 0xF24474 | exact |
| 43 | Mystic Horseman | Normal Monster | EARTH | 4 | 1300 | 1550 | ROM 0xF24478 | exact |
| 44 | Rabid Horseman | Fusion Monster | EARTH | 6 | 2000 | 1700 | ROM 0xF2447C | exact |
| 45 | Crass Clown | Effect Monster | DARK | 4 | 1350 | 1400 | ROM 0xF24480 | exact |
| 46 | Dragon Zombie | Normal Monster | DARK | 3 | 1600 | 0 | ROM 0xF24484 | exact |
| 47 | Clown Zombie | Normal Monster | DARK | 2 | 1350 | 0 | ROM 0xF24488 | exact |
| 48 | Battle Warrior | Normal Monster | EARTH | 3 | 700 | 1000 | ROM 0xF2448C | exact |
| 49 | Wings of Wicked Flame | Normal Monster | FIRE | 2 | 700 | 600 | ROM 0xF24490 | exact |
| 50 | Mask of Darkness | Effect Monster | DARK | 2 | 900 | 400 | ROM 0xF24494 | exact |
| 51 | Curtain of the Dark Ones | Normal Monster | DARK | 2 | 600 | 500 | ROM 0xF24498 | exact |
| 52 | White Magical Hat | Effect Monster | LIGHT | 3 | 1000 | 700 | ROM 0xF2449C | exact |
| 53 | Kamionwizard | Fusion Monster | DARK | 4 | 1300 | 1100 | ROM 0xF244A0 | exact |
| 54 | Dream Clown | Effect Monster | EARTH | 3 | 1200 | 900 | ROM 0xF244A4 | exact |
| 55 | Faith Bird | Normal Monster | WIND | 4 | 1500 | 1100 | ROM 0xF244A8 | exact |
| 56 | Charubin the Fire Knight | Fusion Monster | FIRE | 3 | 1100 | 800 | ROM 0xF244AC | exact |
| 57 | Fiend's Hand | Normal Monster | DARK | 2 | 600 | 600 | ROM 0xF244B0 | exact |
| 58 | Flame Manipulator | Normal Monster | FIRE | 3 | 900 | 1000 | ROM 0xF244B4 | exact |
| 59 | Temple of Skulls | Normal Monster | DARK | 4 | 900 | 1300 | ROM 0xF244B8 | exact |
| 60 | Monster Egg | Normal Monster | EARTH | 3 | 600 | 900 | ROM 0xF244BC | exact |
| 61 | Lord of the Lamp | Normal Monster | DARK | 4 | 1400 | 1200 | ROM 0xF244C0 | exact |
| 62 | Rhaimundos of the Red Sword | Normal Monster | EARTH | 4 | 1200 | 1300 | ROM 0xF244C4 | exact |
| 63 | Fire Reaper | Normal Monster | DARK | 2 | 700 | 500 | ROM 0xF244C8 | exact |
| 64 | Firegrass | Normal Monster | EARTH | 2 | 700 | 600 | ROM 0xF244CC | exact |
| 65 | M-Warrior #1 | Normal Monster | EARTH | 3 | 1000 | 500 | ROM 0xF244D0 | exact |
| 66 | M-Warrior #2 | Normal Monster | EARTH | 3 | 500 | 1000 | ROM 0xF244D4 | exact |
| 67 | Tainted Wisdom | Effect Monster | DARK | 3 | 1250 | 800 | ROM 0xF244D8 | exact |
| 68 | Mysterious Puppeteer | Effect Monster | EARTH | 4 | 1000 | 1500 | ROM 0xF244DC | exact |
| 69 | Darkfire Dragon | Fusion Monster | DARK | 4 | 1500 | 1250 | ROM 0xF244E0 | exact |
| 70 | Spirit of the Harp | Normal Monster | LIGHT | 4 | 800 | 2000 | ROM 0xF244E4 | exact |
| 71 | Big Eye | Effect Monster | DARK | 4 | 1200 | 1000 | ROM 0xF244E8 | exact |
| 72 | Armaill | Normal Monster | EARTH | 3 | 700 | 1300 | ROM 0xF244EC | exact |
| 73 | Ancient Brain | Normal Monster | DARK | 3 | 1000 | 700 | ROM 0xF244F0 | exact |
| 74 | Fire Eye | Normal Monster | FIRE | 2 | 800 | 600 | ROM 0xF244F4 | exact |
| 75 | Fusionist | Fusion Monster | EARTH | 3 | 900 | 700 | ROM 0xF244F8 | exact |
| 76 | Mech Mole Zombie | Normal Monster | DARK | 2 | 500 | 400 | ROM 0xF244FC | exact |
| 77 | Petit Dragon | Normal Monster | WIND | 2 | 600 | 700 | ROM 0xF24500 | exact |
| 78 | Frenzied Panda | Normal Monster | EARTH | 4 | 1200 | 1000 | ROM 0xF24504 | exact |
| 79 | Phantom Ghost | Normal Monster | DARK | 2 | 600 | 800 | ROM 0xF24508 | exact |
| 80 | Petit Angel | Normal Monster | LIGHT | 3 | 600 | 900 | ROM 0xF2450C | exact |
| 81 | Hinotama Soul | Normal Monster | FIRE | 2 | 600 | 500 | ROM 0xF24510 | exact |
| 82 | Aqua Madoor | Normal Monster | WATER | 4 | 1200 | 2000 | ROM 0xF24514 | exact |
| 83 | Flame Ghost | Fusion Monster | DARK | 3 | 1000 | 800 | ROM 0xF24518 | exact |
| 84 | Doriado | Normal Monster | EARTH | 4 | 1200 | 1400 | ROM 0xF2451C | exact |
| 85 | B. Skull Dragon | Fusion Monster | DARK | 9 | 3200 | 2500 | ROM 0xF24520 | exact |
| 86 | Roaring Ocean Snake | Fusion Monster | WATER | 6 | 2100 | 1800 | ROM 0xF24524 | exact |
| 87 | Trap Master | Effect Monster | EARTH | 3 | 500 | 1100 | ROM 0xF24528 | exact |
| 88 | Rare Fish | Fusion Monster | WATER | 4 | 1500 | 1200 | ROM 0xF2452C | exact |
| 89 | Beautiful Headhuntress | Normal Monster | EARTH | 4 | 1600 | 800 | ROM 0xF24530 | exact |
| 90 | Wodan the Resident of the Forest | Effect Monster | EARTH | 3 | 900 | 1200 | ROM 0xF24534 | exact |
| 91 | Guardian of the Labyrinth | Normal Monster | EARTH | 4 | 1000 | 1200 | ROM 0xF24538 | exact |
| 92 | Dissolverock | Normal Monster | EARTH | 3 | 900 | 1000 | ROM 0xF2453C | exact |
| 93 | Enchanting Mermaid | Normal Monster | WATER | 3 | 1200 | 900 | ROM 0xF24540 | exact |
| 94 | Prevent Rat | Normal Monster | EARTH | 4 | 500 | 2000 | ROM 0xF24544 | exact |
| 95 | Dimensional Warrior | Effect Monster | EARTH | 4 | 1200 | 1000 | ROM 0xF24548 | exact |
| 96 | Princess of Tsurugi | Effect Monster | WIND | 3 | 900 | 700 | ROM 0xF2454C | exact |
| 97 | Mavelus | Fusion Monster | WIND | 4 | 1300 | 900 | ROM 0xF24550 | exact |
| 98 | Ground Attacker Bugroth | Normal Monster | EARTH | 4 | 1500 | 1000 | ROM 0xF24554 | exact |
| 99 | Protector of the Throne | Normal Monster | EARTH | 4 | 800 | 1500 | ROM 0xF24558 | exact |
| 100 | Mystical Sheep #2 | Normal Monster | EARTH | 3 | 800 | 1000 | ROM 0xF2455C | exact |
| 101 | Dark Artist | Effect Monster | DARK | 3 | 600 | 1400 | ROM 0xF24560 | exact |
| 102 | Fireyarou | Normal Monster | FIRE | 4 | 1300 | 1000 | ROM 0xF24564 | exact |
| 103 | Masaki the Legendary Swordsman | Normal Monster | EARTH | 4 | 1100 | 1100 | ROM 0xF24568 | exact |
| 104 | Dragoness the Wicked Knight | Fusion Monster | WIND | 3 | 1200 | 900 | ROM 0xF2456C | exact |
| 105 | One-Eyed Shield Dragon | Normal Monster | WIND | 3 | 700 | 1300 | ROM 0xF24570 | exact |
| 106 | Sonic Maid | Normal Monster | EARTH | 3 | 1200 | 900 | ROM 0xF24574 | exact |
| 107 | Legendary Sword | Spell | NONE | 0 | 0 | 0 | ROM 0xF24578 | exact |
| 108 | Sword of Dark Destruction | Spell | NONE | 0 | 0 | 0 | ROM 0xF2457C | exact |
| 109 | Dark Energy | Spell | NONE | 0 | 0 | 0 | ROM 0xF24580 | exact |
| 110 | Axe of Despair | Spell | NONE | 0 | 0 | 0 | ROM 0xF24584 | exact |
| 111 | Laser Cannon Armor | Spell | NONE | 0 | 0 | 0 | ROM 0xF24588 | exact |
| 112 | Insect Armor with Laser Cannon | Spell | NONE | 0 | 0 | 0 | ROM 0xF2458C | exact |
| 113 | Elf's Light | Spell | NONE | 0 | 0 | 0 | ROM 0xF24590 | exact |
| 114 | Beast Fangs | Spell | NONE | 0 | 0 | 0 | ROM 0xF24594 | exact |
| 115 | Steel Shell | Spell | NONE | 0 | 0 | 0 | ROM 0xF24598 | exact |
| 116 | Vile Germs | Spell | NONE | 0 | 0 | 0 | ROM 0xF2459C | exact |
| 117 | Black Pendant | Spell | NONE | 0 | 0 | 0 | ROM 0xF245A0 | exact |
| 118 | Silver Bow and Arrow | Spell | NONE | 0 | 0 | 0 | ROM 0xF245A4 | exact |
| 119 | Horn of Light | Spell | NONE | 0 | 0 | 0 | ROM 0xF245A8 | exact |
| 120 | Horn of the Unicorn | Spell | NONE | 0 | 0 | 0 | ROM 0xF245AC | exact |
| 121 | Dragon Treasure | Spell | NONE | 0 | 0 | 0 | ROM 0xF245B0 | exact |
| 122 | Electro-Whip | Spell | NONE | 0 | 0 | 0 | ROM 0xF245B4 | exact |
| 123 | Cyber Shield | Spell | NONE | 0 | 0 | 0 | ROM 0xF245B8 | exact |
| 124 | Elegant Egotist | Spell | NONE | 0 | 0 | 0 | ROM 0xF245BC | exact |
| 125 | Mystical Moon | Spell | NONE | 0 | 0 | 0 | ROM 0xF245C0 | exact |
| 126 | Stop Defense | Spell | NONE | 0 | 0 | 0 | ROM 0xF245C4 | exact |
| 127 | Malevolent Nuzzler | Spell | NONE | 0 | 0 | 0 | ROM 0xF245C8 | exact |
| 128 | Violet Crystal | Spell | NONE | 0 | 0 | 0 | ROM 0xF245CC | exact |
| 129 | Book of Secret Arts | Spell | NONE | 0 | 0 | 0 | ROM 0xF245D0 | exact |
| 130 | Invigoration | Spell | NONE | 0 | 0 | 0 | ROM 0xF245D4 | exact |
| 131 | Machine Conversion Factory | Spell | NONE | 0 | 0 | 0 | ROM 0xF245D8 | exact |
| 132 | Raise Body Heat | Spell | NONE | 0 | 0 | 0 | ROM 0xF245DC | exact |
| 133 | Follow Wind | Spell | NONE | 0 | 0 | 0 | ROM 0xF245E0 | exact |
| 134 | Power of Kaishin | Spell | NONE | 0 | 0 | 0 | ROM 0xF245E4 | exact |
| 135 | Forest | Spell | NONE | 0 | 0 | 0 | ROM 0xF245E8 | exact |
| 136 | Wasteland | Spell | NONE | 0 | 0 | 0 | ROM 0xF245EC | exact |
| 137 | Mountain | Spell | NONE | 0 | 0 | 0 | ROM 0xF245F0 | exact |
| 138 | Sogen | Spell | NONE | 0 | 0 | 0 | ROM 0xF245F4 | exact |
| 139 | Umi | Spell | NONE | 0 | 0 | 0 | ROM 0xF245F8 | exact |
| 140 | Yami | Spell | NONE | 0 | 0 | 0 | ROM 0xF245FC | exact |
| 141 | Dark Hole | Spell | NONE | 0 | 0 | 0 | ROM 0xF24600 | exact |
| 142 | Raigeki | Spell | NONE | 0 | 0 | 0 | ROM 0xF24604 | exact |
| 143 | Mooyan Curry | Spell | NONE | 0 | 0 | 0 | ROM 0xF24608 | exact |
| 144 | Red Medicine | Spell | NONE | 0 | 0 | 0 | ROM 0xF2460C | exact |
| 145 | Goblin's Secret Remedy | Spell | NONE | 0 | 0 | 0 | ROM 0xF24610 | exact |
| 146 | Soul of the Pure | Spell | NONE | 0 | 0 | 0 | ROM 0xF24614 | exact |
| 147 | Dian Keto the Cure Master | Spell | NONE | 0 | 0 | 0 | ROM 0xF24618 | exact |
| 148 | Sparks | Spell | NONE | 0 | 0 | 0 | ROM 0xF2461C | exact |
| 149 | Hinotama | Spell | NONE | 0 | 0 | 0 | ROM 0xF24620 | exact |
| 150 | Final Flame | Spell | NONE | 0 | 0 | 0 | ROM 0xF24624 | exact |
| 151 | Ookazi | Spell | NONE | 0 | 0 | 0 | ROM 0xF24628 | exact |
| 152 | Tremendous Fire | Spell | NONE | 0 | 0 | 0 | ROM 0xF2462C | exact |
| 153 | Swords of Revealing Light | Spell | NONE | 0 | 0 | 0 | ROM 0xF24630 | exact |
| 154 | Spellbinding Circle | Trap | NONE | 0 | 0 | 0 | ROM 0xF24634 | exact |
| 155 | Dark-Piercing Light | Spell | NONE | 0 | 0 | 0 | ROM 0xF24638 | exact |
| 156 | Super War-Lion | Ritual Monster | EARTH | 7 | 2300 | 2100 | ROM 0xF2463C | exact |
| 157 | Yamadron | Normal Monster | FIRE | 5 | 1600 | 1800 | ROM 0xF24640 | exact |
| 158 | Zera The Mant | Ritual Monster | DARK | 8 | 2800 | 2300 | ROM 0xF24644 | exact |
| 159 | Millennium Shield | Normal Monster | EARTH | 5 | 0 | 3000 | ROM 0xF24648 | exact |
| 160 | Black Luster Soldier | Ritual Monster | EARTH | 8 | 3000 | 2500 | ROM 0xF2464C | exact |
| 161 | Fiend's Mirror | Ritual Monster | DARK | 6 | 2100 | 1800 | ROM 0xF24650 | exact |
| 162 | Jirai Gumo | Effect Monster | EARTH | 4 | 2200 | 100 | ROM 0xF24654 | exact |
| 163 | Shadow Ghoul | Effect Monster | DARK | 5 | 1600 | 1300 | ROM 0xF24658 | exact |
| 164 | Labyrinth Tank | Fusion Monster | DARK | 7 | 2400 | 2400 | ROM 0xF2465C | exact |
| 165 | La Jinn the Mystical Genie of the Lamp | Normal Monster | DARK | 4 | 1800 | 1000 | ROM 0xF24660 | exact |
| 166 | Blue-Eyes Ultimate Dragon | Fusion Monster | LIGHT | 12 | 4500 | 3800 | ROM 0xF24664 | exact |
| 167 | Bickuribox | Fusion Monster | DARK | 7 | 2300 | 2000 | ROM 0xF24668 | exact |
| 168 | Harpie's Pet Dragon | Effect Monster | WIND | 7 | 2000 | 2500 | ROM 0xF2466C | exact |
| 169 | Mystic Lamp | Effect Monster | DARK | 1 | 400 | 300 | ROM 0xF24670 | exact |
| 170 | Giltia the D. Knight | Fusion Monster | LIGHT | 5 | 1850 | 1500 | ROM 0xF24674 | exact |
| 171 | Launcher Spider | Normal Monster | FIRE | 7 | 2200 | 2500 | ROM 0xF24678 | exact |
| 172 | Zoa | Normal Monster | DARK | 7 | 2600 | 1900 | ROM 0xF2467C | exact |
| 173 | Metalzoa | Effect Monster | DARK | 8 | 3000 | 2300 | ROM 0xF24680 | exact |
| 174 | Zone Eater | Effect Monster | WATER | 1 | 250 | 200 | ROM 0xF24684 | exact |
| 175 | Ocubeam | Normal Monster | LIGHT | 5 | 1550 | 1650 | ROM 0xF24688 | exact |
| 176 | Leghul | Effect Monster | EARTH | 1 | 300 | 350 | ROM 0xF2468C | exact |
| 177 | Ooguchi | Effect Monster | WATER | 1 | 300 | 250 | ROM 0xF24690 | exact |
| 178 | Swordsman from a Foreign Land | Effect Monster | EARTH | 1 | 250 | 250 | ROM 0xF24694 | exact |
| 179 | Monster Eye | Effect Monster | DARK | 1 | 250 | 350 | ROM 0xF24698 | exact |
| 180 | Machine King | Effect Monster | EARTH | 6 | 2200 | 2000 | ROM 0xF2469C | exact |
| 181 | Metal Dragon | Fusion Monster | WIND | 6 | 1850 | 1700 | ROM 0xF246A0 | exact |
| 182 | Mechanical Spider | Effect Monster | EARTH | 2 | 400 | 500 | ROM 0xF246A4 | exact |
| 183 | Giga-Tech Wolf | Normal Monster | FIRE | 4 | 1200 | 1400 | ROM 0xF246A8 | exact |
| 184 | Mechanicalchaser | Normal Monster | DARK | 4 | 1850 | 800 | ROM 0xF246AC | exact |
| 185 | Blast Juggler | Effect Monster | FIRE | 3 | 800 | 900 | ROM 0xF246B0 | exact |
| 186 | Cyber-Stein | Effect Monster | DARK | 2 | 700 | 500 | ROM 0xF246B4 | exact |
| 187 | Jinzo #7 | Effect Monster | DARK | 2 | 500 | 400 | ROM 0xF246B8 | exact |
| 188 | Thunder Dragon | Effect Monster | LIGHT | 5 | 1600 | 1500 | ROM 0xF246BC | exact |
| 189 | Kaiser Dragon | Fusion Monster | LIGHT | 7 | 2300 | 2000 | ROM 0xF246C0 | exact |
| 190 | Magician of Faith | Effect Monster | LIGHT | 1 | 300 | 400 | ROM 0xF246C4 | exact |
| 191 | Water Magician | Normal Monster | WATER | 4 | 1400 | 1000 | ROM 0xF246C8 | exact |
| 192 | Ancient Elf | Normal Monster | LIGHT | 4 | 1450 | 1200 | ROM 0xF246CC | exact |
| 193 | Deepsea Shark | Fusion Monster | WATER | 5 | 1900 | 1600 | ROM 0xF246D0 | exact |
| 194 | Bottom Dweller | Normal Monster | WATER | 5 | 1650 | 1700 | ROM 0xF246D4 | exact |
| 195 | 7 Colored Fish | Normal Monster | WATER | 4 | 1800 | 800 | ROM 0xF246D8 | exact |
| 196 | Aqua Dragon | Fusion Monster | WATER | 6 | 2250 | 1900 | ROM 0xF246DC | exact |
| 197 | Guardian of the Sea | Normal Monster | WATER | 4 | 1300 | 1000 | ROM 0xF246E0 | exact |
| 198 | Giant Red Seasnake | Normal Monster | WATER | 4 | 1800 | 800 | ROM 0xF246E4 | exact |
| 199 | Millennium Golem | Normal Monster | EARTH | 6 | 2000 | 2200 | ROM 0xF246E8 | exact |
| 200 | Destroyer Golem | Normal Monster | EARTH | 4 | 1500 | 1000 | ROM 0xF246EC | exact |
| 201 | Kaminari Attack | Fusion Monster | WIND | 5 | 1900 | 1400 | ROM 0xF246F0 | exact |
| 202 | Punished Eagle | Fusion Monster | WIND | 6 | 2100 | 1800 | ROM 0xF246F4 | exact |
| 203 | Skull Red Bird | Normal Monster | WIND | 4 | 1550 | 1200 | ROM 0xF246F8 | exact |
| 204 | Crimson Sunbird | Fusion Monster | FIRE | 6 | 2300 | 1800 | ROM 0xF246FC | exact |
| 205 | Armed Ninja | Effect Monster | EARTH | 1 | 300 | 300 | ROM 0xF24700 | exact |
| 206 | Soul Hunter | Fusion Monster | DARK | 6 | 2200 | 1800 | ROM 0xF24704 | exact |
| 207 | Vermillion Sparrow | Fusion Monster | FIRE | 5 | 1900 | 1500 | ROM 0xF24708 | exact |
| 208 | Sea Kamen | Normal Monster | WATER | 4 | 1100 | 1300 | ROM 0xF2470C | exact |
| 209 | Sinister Serpent | Effect Monster | WATER | 1 | 300 | 250 | ROM 0xF24710 | exact |
| 210 | Insect Soldiers of the Sky | Effect Monster | WIND | 3 | 1000 | 800 | ROM 0xF24714 | exact |
| 211 | Cockroach Knight | Effect Monster | EARTH | 3 | 800 | 900 | ROM 0xF24718 | exact |
| 212 | Kuwagata ò¤ | Normal Monster | EARTH | 4 | 1250 | 1000 | ROM 0xF2471C | exact |
| 213 | Pragtical | Fusion Monster | EARTH | 5 | 1900 | 1500 | ROM 0xF24720 | exact |
| 214 | Flower Wolf | Fusion Monster | EARTH | 5 | 1800 | 1400 | ROM 0xF24724 | exact |
| 215 | Rainbow Flower | Effect Monster | EARTH | 2 | 400 | 500 | ROM 0xF24728 | exact |
| 216 | Needle Ball | Effect Monster | DARK | 2 | 750 | 700 | ROM 0xF2472C | exact |
| 217 | Hoshiningen | Effect Monster | LIGHT | 2 | 500 | 700 | ROM 0xF24730 | exact |
| 218 | Maha Vailo | Effect Monster | LIGHT | 4 | 1550 | 1400 | ROM 0xF24734 | exact |
| 219 | Musician King | Fusion Monster | LIGHT | 5 | 1750 | 1500 | ROM 0xF24738 | exact |
| 220 | Dragon Seeker | Effect Monster | DARK | 6 | 2000 | 2100 | ROM 0xF2473C | exact |
| 221 | Man-Eater Bug | Effect Monster | EARTH | 2 | 450 | 600 | ROM 0xF24740 | exact |
| 222 | Gale Dogra | Effect Monster | EARTH | 2 | 650 | 600 | ROM 0xF24744 | exact |
| 223 | Cyber Saurus | Fusion Monster | EARTH | 5 | 1800 | 1400 | ROM 0xF24748 | exact |
| 224 | Bracchio-raidus | Fusion Monster | WATER | 6 | 2200 | 2000 | ROM 0xF2474C | exact |
| 225 | Cannon Soldier | Effect Monster | DARK | 4 | 1400 | 1300 | ROM 0xF24750 | exact |
| 226 | Muka Muka | Effect Monster | EARTH | 2 | 600 | 300 | ROM 0xF24754 | exact |
| 227 | Fire Kraken | Normal Monster | FIRE | 4 | 1600 | 1500 | ROM 0xF24758 | exact |
| 228 | Skullbird | Fusion Monster | WIND | 6 | 1900 | 1700 | ROM 0xF2475C | exact |
| 229 | The Bistro Butcher | Effect Monster | DARK | 4 | 1800 | 1000 | ROM 0xF24760 | exact |
| 230 | Star Boy | Effect Monster | WATER | 2 | 550 | 500 | ROM 0xF24764 | exact |
| 231 | Milus Radiant | Effect Monster | EARTH | 1 | 300 | 250 | ROM 0xF24768 | exact |
| 232 | Flame Cerebrus | Normal Monster | FIRE | 6 | 2100 | 1800 | ROM 0xF2476C | exact |
| 233 | Mystical Sand | Fusion Monster | EARTH | 6 | 2100 | 1700 | ROM 0xF24770 | exact |
| 234 | Gemini Elf | Normal Monster | EARTH | 4 | 1900 | 900 | ROM 0xF24774 | exact |
| 235 | Kwagar Hercules | Fusion Monster | EARTH | 6 | 1900 | 1700 | ROM 0xF24778 | exact |
| 236 | Mega Thunderball | Normal Monster | WIND | 2 | 750 | 600 | ROM 0xF2477C | exact |
| 237 | Niwatori | Normal Monster | EARTH | 3 | 900 | 800 | ROM 0xF24780 | exact |
| 238 | Skelengel | Effect Monster | LIGHT | 2 | 900 | 400 | ROM 0xF24784 | exact |
| 239 | Hane-Hane | Effect Monster | EARTH | 2 | 450 | 500 | ROM 0xF24788 | exact |
| 240 | Tongyo | Normal Monster | WATER | 4 | 1350 | 800 | ROM 0xF2478C | exact |
| 241 | Skelgon | Fusion Monster | DARK | 6 | 1700 | 1900 | ROM 0xF24790 | exact |
| 242 | Bone Mouse | Normal Monster | DARK | 1 | 400 | 300 | ROM 0xF24794 | exact |
| 243 | Behegon | Normal Monster | WATER | 4 | 1350 | 1000 | ROM 0xF24798 | exact |
| 244 | Dark Elf | Effect Monster | DARK | 4 | 2000 | 800 | ROM 0xF2479C | exact |
| 245 | Lava Battleguard | Effect Monster | EARTH | 5 | 1550 | 1800 | ROM 0xF247A0 | exact |
| 246 | Tyhone #2 | Normal Monster | FIRE | 6 | 1700 | 1900 | ROM 0xF247A4 | exact |
| 247 | The Wandering Doomed | Normal Monster | DARK | 2 | 800 | 600 | ROM 0xF247A8 | exact |
| 248 | Steel Ogre Grotto #1 | Normal Monster | EARTH | 5 | 1400 | 1800 | ROM 0xF247AC | exact |
| 249 | Invader from Another Dimension | Normal Monster | DARK | 4 | 950 | 1400 | ROM 0xF247B0 | exact |
| 250 | Lesser Dragon | Normal Monster | WIND | 4 | 1200 | 1000 | ROM 0xF247B4 | exact |
| 251 | Needle Worm | Effect Monster | EARTH | 2 | 750 | 600 | ROM 0xF247B8 | exact |
| 252 | Great Mammoth of Goldfine | Fusion Monster | DARK | 6 | 2200 | 1800 | ROM 0xF247BC | exact |
| 253 | Man-eating Black Shark | Fusion Monster | WATER | 5 | 2100 | 1300 | ROM 0xF247C0 | exact |
| 254 | Darkworld Thorns | Normal Monster | EARTH | 3 | 1200 | 900 | ROM 0xF247C4 | exact |
| 255 | Trakadon | Normal Monster | EARTH | 3 | 1300 | 800 | ROM 0xF247C8 | exact |
| 256 | Empress Judge | Fusion Monster | EARTH | 6 | 2100 | 1700 | ROM 0xF247CC | exact |
| 257 | Witch of the Black Forest | Effect Monster | DARK | 4 | 1100 | 1200 | ROM 0xF247D0 | exact |
| 258 | Takuhee | Normal Monster | WIND | 4 | 1450 | 1000 | ROM 0xF247D4 | exact |
| 259 | Morphing Jar | Effect Monster | EARTH | 2 | 700 | 600 | ROM 0xF247D8 | exact |
| 260 | Rose Spectre of Dunn | Fusion Monster | DARK | 6 | 2000 | 1800 | ROM 0xF247DC | exact |
| 261 | Little Chimera | Effect Monster | FIRE | 2 | 600 | 550 | ROM 0xF247E0 | exact |
| 262 | Penguin Soldier | Effect Monster | WATER | 2 | 750 | 500 | ROM 0xF247E4 | exact |
| 263 | Fairy Dragon | Normal Monster | WIND | 4 | 1100 | 1200 | ROM 0xF247E8 | exact |
| 264 | Bladefly | Effect Monster | WIND | 2 | 600 | 700 | ROM 0xF247EC | exact |
| 265 | Lady of Faith | Normal Monster | LIGHT | 3 | 1100 | 800 | ROM 0xF247F0 | exact |
| 266 | Twin-Headed Thunder Dragon | Fusion Monster | LIGHT | 7 | 2800 | 2100 | ROM 0xF247F4 | exact |
| 267 | Marine Beast | Fusion Monster | WATER | 5 | 1700 | 1600 | ROM 0xF247F8 | exact |
| 268 | Warrior of Tradition | Fusion Monster | EARTH | 6 | 1900 | 1700 | ROM 0xF247FC | exact |
| 269 | Snakeyashi | Normal Monster | EARTH | 4 | 1000 | 1200 | ROM 0xF24800 | exact |
| 270 | Amazon of the Seas | Normal Monster | WATER | 4 | 1300 | 1400 | ROM 0xF24804 | exact |
| 271 | Witch's Apprentice | Effect Monster | DARK | 2 | 550 | 500 | ROM 0xF24808 | exact |
| 272 | Queen's Double | Effect Monster | EARTH | 1 | 350 | 300 | ROM 0xF2480C | exact |
| 273 | Blue-Winged Crown | Normal Monster | WIND | 4 | 1600 | 1200 | ROM 0xF24810 | exact |
| 274 | Amphibious Bugroth | Fusion Monster | WATER | 5 | 1850 | 1300 | ROM 0xF24814 | exact |
| 275 | Flame Viper | Normal Monster | EARTH | 2 | 400 | 450 | ROM 0xF24818 | exact |
| 276 | Gruesome Goo | Normal Monster | WATER | 3 | 1300 | 700 | ROM 0xF2481C | exact |
| 277 | Hyosube | Normal Monster | WATER | 4 | 1500 | 900 | ROM 0xF24820 | exact |
| 278 | Hibikime | Normal Monster | EARTH | 4 | 1450 | 1000 | ROM 0xF24824 | exact |
| 279 | Warrior Elimination | Spell | NONE | 0 | 0 | 0 | ROM 0xF24828 | exact |
| 280 | Salamandra | Spell | NONE | 0 | 0 | 0 | ROM 0xF2482C | exact |
| 281 | Eternal Rest | Spell | NONE | 0 | 0 | 0 | ROM 0xF24830 | exact |
| 282 | Megamorph | Spell | NONE | 0 | 0 | 0 | ROM 0xF24834 | exact |
| 283 | Metalmorph | Trap | NONE | 0 | 0 | 0 | ROM 0xF24838 | exact |
| 284 | Acid Rain | Spell | NONE | 0 | 0 | 0 | ROM 0xF2483C | exact |
| 285 | Eradicating Aerosol | Spell | NONE | 0 | 0 | 0 | ROM 0xF24840 | exact |
| 286 | Breath of Light | Spell | NONE | 0 | 0 | 0 | ROM 0xF24844 | exact |
| 287 | Eternal Draught | Spell | NONE | 0 | 0 | 0 | ROM 0xF24848 | exact |
| 288 | Bright Castle | Spell | NONE | 0 | 0 | 0 | ROM 0xF2484C | exact |
| 289 | Shadow Spell | Trap | NONE | 0 | 0 | 0 | ROM 0xF24850 | exact |
| 290 | Black Luster Ritual | Spell | NONE | 0 | 0 | 0 | ROM 0xF24854 | exact |
| 291 | Zera Ritual | Spell | NONE | 0 | 0 | 0 | ROM 0xF24858 | exact |
| 292 | Harpie's Feather Duster | Spell | NONE | 0 | 0 | 0 | ROM 0xF2485C | exact |
| 293 | War-Lion Ritual | Spell | NONE | 0 | 0 | 0 | ROM 0xF24860 | exact |
| 294 | Beastly Mirror Ritual | Spell | NONE | 0 | 0 | 0 | ROM 0xF24864 | exact |
| 295 | Commencement Dance | Spell | NONE | 0 | 0 | 0 | ROM 0xF24868 | exact |
| 296 | Hamburger Recipe | Spell | NONE | 0 | 0 | 0 | ROM 0xF2486C | exact |
| 297 | Novox's Prayer | Spell | NONE | 0 | 0 | 0 | ROM 0xF24870 | exact |
| 298 | House of Adhesive Tape | Trap | NONE | 0 | 0 | 0 | ROM 0xF24874 | exact |
| 299 | Eatgaboon | Trap | NONE | 0 | 0 | 0 | ROM 0xF24878 | exact |
| 300 | Widespread Ruin | Trap | NONE | 0 | 0 | 0 | ROM 0xF2487C | exact |
| 301 | Turtle Oath | Spell | NONE | 0 | 0 | 0 | ROM 0xF24880 | exact |
| 302 | Resurrection of Chakra | Spell | NONE | 0 | 0 | 0 | ROM 0xF24884 | exact |
| 303 | Javelin Beetle Pact | Spell | NONE | 0 | 0 | 0 | ROM 0xF24888 | exact |
| 304 | Garma Sword Oath | Spell | NONE | 0 | 0 | 0 | ROM 0xF2488C | exact |
| 305 | Revival of Dokurorider | Spell | NONE | 0 | 0 | 0 | ROM 0xF24890 | exact |
| 306 | Fortress Whale's Oath | Spell | NONE | 0 | 0 | 0 | ROM 0xF24894 | exact |
| 307 | Performance of Sword | Ritual Monster | EARTH | 6 | 1950 | 1850 | ROM 0xF24898 | exact |
| 308 | Hungry Burger | Ritual Monster | DARK | 6 | 2000 | 1850 | ROM 0xF2489C | exact |
| 309 | Sengenjin | Normal Monster | EARTH | 8 | 2750 | 2500 | ROM 0xF248A0 | exact |
| 310 | Skull Guardian | Ritual Monster | LIGHT | 7 | 2050 | 2500 | ROM 0xF248A4 | exact |
| 311 | Tri-Horned Dragon | Normal Monster | DARK | 8 | 2850 | 2350 | ROM 0xF248A8 | exact |
| 312 | Serpent Night Dragon | Normal Monster | DARK | 7 | 2350 | 2400 | ROM 0xF248AC | exact |
| 313 | Skull Knight | Fusion Monster | DARK | 7 | 2650 | 2250 | ROM 0xF248B0 | exact |
| 314 | Cosmo Queen | Normal Monster | DARK | 8 | 2900 | 2450 | ROM 0xF248B4 | exact |
| 315 | Chakra | Ritual Monster | DARK | 7 | 2450 | 2000 | ROM 0xF248B8 | exact |
| 316 | Crab Turtle | Ritual Monster | WATER | 8 | 2550 | 2500 | ROM 0xF248BC | exact |
| 317 | Mikazukinoyaiba | Normal Monster | DARK | 7 | 2200 | 2350 | ROM 0xF248C0 | exact |
| 318 | Meteor Dragon | Normal Monster | EARTH | 6 | 1800 | 2000 | ROM 0xF248C4 | exact |
| 319 | Meteor B. Dragon | Fusion Monster | FIRE | 8 | 3500 | 2000 | ROM 0xF248C8 | exact |
| 320 | Firewing Pegasus | Normal Monster | FIRE | 6 | 2250 | 1800 | ROM 0xF248CC | exact |
| 321 | Garma Sword | Ritual Monster | DARK | 7 | 2550 | 2150 | ROM 0xF248D0 | exact |
| 322 | Javelin Beetle | Ritual Monster | EARTH | 8 | 2450 | 2550 | ROM 0xF248D4 | exact |
| 323 | Fortress Whale | Ritual Monster | WATER | 7 | 2350 | 2150 | ROM 0xF248D8 | exact |
| 324 | Dokurorider | Ritual Monster | DARK | 6 | 1900 | 1850 | ROM 0xF248DC | exact |
| 325 | Dark Magic Ritual | Spell | NONE | 0 | 0 | 0 | ROM 0xF248E0 | exact |
| 326 | Magician of Black Chaos | Ritual Monster | DARK | 8 | 2800 | 2600 | ROM 0xF248E4 | exact |
| 327 | Red Archery Girl | Normal Monster | WATER | 4 | 1400 | 1500 | ROM 0xF248E8 | exact |
| 328 | Ryu-Ran | Normal Monster | FIRE | 7 | 2200 | 2600 | ROM 0xF248EC | exact |
| 329 | Manga Ryu-Ran | Effect Monster | FIRE | 7 | 2200 | 2600 | ROM 0xF248F0 | exact |
| 330 | Toon Mermaid | Effect Monster | WATER | 4 | 1400 | 1500 | ROM 0xF248F4 | exact |
| 331 | Toon Summoned Skull | Effect Monster | DARK | 6 | 2500 | 1200 | ROM 0xF248F8 | exact |
| 332 | Relinquished | Ritual Monster | DARK | 1 | 0 | 0 | ROM 0xF248FC | exact |
| 333 | Thousand-Eyes Idol | Normal Monster | DARK | 1 | 0 | 0 | ROM 0xF24900 | exact |
| 334 | Thousand-Eyes Restrict | Fusion Monster | DARK | 1 | 0 | 0 | ROM 0xF24904 | exact |
| 335 | Steel Ogre Grotto #2 | Normal Monster | EARTH | 6 | 1900 | 2200 | ROM 0xF24908 | exact |
| 336 | Blast Sphere | Effect Monster | DARK | 4 | 1400 | 1400 | ROM 0xF2490C | exact |
| 337 | Hyozanryu | Normal Monster | LIGHT | 7 | 2100 | 2800 | ROM 0xF24910 | exact |
| 338 | Alpha The Magnet Warrior | Normal Monster | EARTH | 4 | 1400 | 1700 | ROM 0xF24914 | exact |
| 339 | Red-Eyes Black Metal Dragon | Effect Monster | DARK | 8 | 2800 | 2400 | ROM 0xF24918 | exact |
| 340 | Barrel Dragon | Effect Monster | DARK | 7 | 2600 | 2200 | ROM 0xF2491C | exact |
| 341 | Hannibal Necromancer | Effect Monster | DARK | 4 | 1400 | 1800 | ROM 0xF24920 | exact |
| 342 | Panther Warrior | Effect Monster | EARTH | 4 | 2000 | 1600 | ROM 0xF24924 | exact |
| 343 | Gazelle the King of Mythical Beasts | Normal Monster | EARTH | 4 | 1500 | 1200 | ROM 0xF24928 | exact |
| 344 | Stone Statue of the Aztecs | Effect Monster | EARTH | 4 | 300 | 2000 | ROM 0xF2492C | exact |
| 345 | Berfomet | Effect Monster | DARK | 5 | 1400 | 1800 | ROM 0xF24930 | exact |
| 346 | Chimera the Flying Mythical Beast | Fusion Monster | WIND | 6 | 2100 | 1800 | ROM 0xF24934 | exact |
| 347 | Gear Golem the Moving Fortress | Effect Monster | EARTH | 4 | 800 | 2200 | ROM 0xF24938 | exact |
| 348 | Jinzo | Effect Monster | DARK | 6 | 2400 | 1500 | ROM 0xF2493C | exact |
| 349 | The Fiend Megacyber | Effect Monster | DARK | 6 | 2200 | 1200 | ROM 0xF24940 | exact |
| 350 | Reflect Bounder | Effect Monster | LIGHT | 4 | 1700 | 1000 | ROM 0xF24944 | exact |
| 351 | Beta The Magnet Warrior | Normal Monster | EARTH | 4 | 1700 | 1600 | ROM 0xF24948 | exact |
| 352 | Dark Magician Girl | Effect Monster | DARK | 6 | 2000 | 1700 | ROM 0xF2494C | exact |
| 353 | Alligator's Sword | Normal Monster | EARTH | 4 | 1500 | 1200 | ROM 0xF24950 | exact |
| 354 | Insect Queen | Effect Monster | EARTH | 7 | 2200 | 2400 | ROM 0xF24954 | exact |
| 355 | Skull-Mark Ladybug | Effect Monster | EARTH | 4 | 500 | 1500 | ROM 0xF24958 | exact |
| 356 | Pinch Hopper | Effect Monster | EARTH | 4 | 1000 | 1200 | ROM 0xF2495C | exact |
| 357 | Blue-Eyes Toon Dragon | Effect Monster | LIGHT | 8 | 3000 | 2500 | ROM 0xF24960 | exact |
| 358 | Satellite Cannon | Effect Monster | LIGHT | 5 | 0 | 0 | ROM 0xF24964 | exact |
| 359 | The Last Warrior from Another Planet | Fusion Monster | EARTH | 7 | 2350 | 2300 | ROM 0xF24968 | exact |
| 360 | Dunames Dark Witch | Normal Monster | LIGHT | 4 | 1800 | 1050 | ROM 0xF2496C | exact |
| 361 | Total Defense Shogun | Effect Monster | DARK | 6 | 1550 | 2500 | ROM 0xF24970 | exact |
| 362 | Beast of Talwar | Normal Monster | DARK | 6 | 2400 | 2150 | ROM 0xF24974 | exact |
| 363 | Cyber-Tech Alligator | Normal Monster | WIND | 5 | 2500 | 1600 | ROM 0xF24978 | exact |
| 364 | Gamma The Magnet Warrior | Normal Monster | EARTH | 4 | 1500 | 1800 | ROM 0xF2497C | exact |
| 365 | Copycat | Effect Monster | LIGHT | 1 | 0 | 0 | ROM 0xF24980 | exact |
| 366 | Toon World | Spell | NONE | 0 | 0 | 0 | ROM 0xF24984 | exact |
| 367 | Black Illusion Ritual | Spell | NONE | 0 | 0 | 0 | ROM 0xF24988 | exact |
| 368 | Negate Attack | Trap | NONE | 0 | 0 | 0 | ROM 0xF2498C | exact |
| 369 | Multiply | Spell | NONE | 0 | 0 | 0 | ROM 0xF24990 | exact |
| 370 | Graceful Charity | Spell | NONE | 0 | 0 | 0 | ROM 0xF24994 | exact |
| 371 | Chain Destruction | Trap | NONE | 0 | 0 | 0 | ROM 0xF24998 | exact |
| 372 | Graceful Dice | Spell | NONE | 0 | 0 | 0 | ROM 0xF2499C | exact |
| 373 | Skull Dice | Trap | NONE | 0 | 0 | 0 | ROM 0xF249A0 | exact |
| 374 | Scapegoat | Spell | NONE | 0 | 0 | 0 | ROM 0xF249A4 | exact |
| 375 | Card Destruction | Spell | NONE | 0 | 0 | 0 | ROM 0xF249A8 | exact |
| 376 | Tragedy | Trap | NONE | 0 | 0 | 0 | ROM 0xF249AC | exact |
| 377 | Dark Magic Curtain | Spell | NONE | 0 | 0 | 0 | ROM 0xF249B0 | exact |
| 378 | Insect Barrier | Spell | NONE | 0 | 0 | 0 | ROM 0xF249B4 | exact |
| 379 | Fissure | Spell | NONE | 0 | 0 | 0 | ROM 0xF249B8 | exact |
| 380 | Trap Hole | Trap | NONE | 0 | 0 | 0 | ROM 0xF249BC | exact |
| 381 | Polymerization | Spell | NONE | 0 | 0 | 0 | ROM 0xF249C0 | exact |
| 382 | Remove Trap | Spell | NONE | 0 | 0 | 0 | ROM 0xF249C4 | exact |
| 383 | Blue Medicine | Spell | NONE | 0 | 0 | 0 | ROM 0xF249C8 | exact |
| 384 | Raimei | Spell | NONE | 0 | 0 | 0 | ROM 0xF249CC | exact |
| 385 | Monster Reborn | Spell | NONE | 0 | 0 | 0 | ROM 0xF249D0 | exact |
| 386 | De-Spell | Spell | NONE | 0 | 0 | 0 | ROM 0xF249D4 | exact |
| 387 | Pot of Greed | Spell | NONE | 0 | 0 | 0 | ROM 0xF249D8 | exact |
| 388 | Gravedigger Ghoul | Spell | NONE | 0 | 0 | 0 | ROM 0xF249DC | exact |
| 389 | Burning Spear | Spell | NONE | 0 | 0 | 0 | ROM 0xF249E0 | exact |
| 390 | Gust Fan | Spell | NONE | 0 | 0 | 0 | ROM 0xF249E4 | exact |
| 391 | Reinforcements | Trap | NONE | 0 | 0 | 0 | ROM 0xF249E8 | exact |
| 392 | Castle Walls | Trap | NONE | 0 | 0 | 0 | ROM 0xF249EC | exact |
| 393 | Ancient Telescope | Spell | NONE | 0 | 0 | 0 | ROM 0xF249F0 | exact |
| 394 | White Hole | Trap | NONE | 0 | 0 | 0 | ROM 0xF249F4 | exact |
| 395 | Call of the Grave | Trap | NONE | 0 | 0 | 0 | ROM 0xF249F8 | exact |
| 396 | Anti Raigeki | Trap | NONE | 0 | 0 | 0 | ROM 0xF249FC | exact |
| 397 | Tribute to the Doomed | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A00 | exact |
| 398 | Soul Release | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A04 | exact |
| 399 | The Cheerful Coffin | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A08 | exact |
| 400 | Call of the Dark | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A0C | exact |
| 401 | Change of Heart | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A10 | exact |
| 402 | Magic Jammer | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A14 | exact |
| 403 | Seven Tools of the Bandit | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A18 | exact |
| 404 | Just Desserts | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A1C | exact |
| 405 | Royal Decree | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A20 | exact |
| 406 | Last Day of Witch | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A24 | exact |
| 407 | Exile of the Wicked | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A28 | exact |
| 408 | Magical Thorn | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A2C | exact |
| 409 | Restructer Revolution | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A30 | exact |
| 410 | Fusion Sage | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A34 | exact |
| 411 | Sword of Deep-Seated | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A38 | exact |
| 412 | Block Attack | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A3C | exact |
| 413 | The Unhappy Maiden | Effect Monster | LIGHT | 1 | 0 | 100 | ROM 0xF24A40 | exact |
| 414 | Robbin' Goblin | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A44 | exact |
| 415 | Wall of Illusion | Effect Monster | DARK | 4 | 1000 | 1850 | ROM 0xF24A48 | exact |
| 416 | Neo the Magic Swordsman | Normal Monster | LIGHT | 4 | 1700 | 1000 | ROM 0xF24A4C | exact |
| 417 | Baron of the Fiend Sword | Normal Monster | DARK | 4 | 1550 | 800 | ROM 0xF24A50 | exact |
| 418 | Man-Eating Treasure Chest | Normal Monster | DARK | 4 | 1600 | 1000 | ROM 0xF24A54 | exact |
| 419 | Sorcerer of the Doomed | Normal Monster | DARK | 4 | 1450 | 1200 | ROM 0xF24A58 | exact |
| 420 | Waboku | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A5C | exact |
| 421 | Mirror Force | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A60 | exact |
| 422 | Heavy Storm | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A64 | exact |
| 423 | Gryphon Wing | Trap | NONE | 0 | 0 | 0 | ROM 0xF24A68 | exact |
| 424 | Gravekeeper's Servant | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A6C | exact |
| 425 | Upstart Goblin | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A70 | exact |
| 426 | Toll | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A74 | exact |
| 427 | Final Destiny | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A78 | exact |
| 428 | Snatch Steal | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A7C | exact |
| 429 | Chorus of Sanctuary | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A80 | exact |
| 430 | Confiscation | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A84 | exact |
| 431 | Delinquent Duo | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A88 | exact |
| 432 | Rush Recklessly | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A8C | exact |
| 433 | The Reliable Guardian | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A90 | exact |
| 434 | The Forceful Sentry | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A94 | exact |
| 435 | Chain Energy | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A98 | exact |
| 436 | Mystical Space Typhoon | Spell | NONE | 0 | 0 | 0 | ROM 0xF24A9C | exact |
| 437 | Giant Trunade | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AA0 | exact |
| 438 | Painful Choice | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AA4 | exact |
| 439 | Snake Fang | Trap | NONE | 0 | 0 | 0 | ROM 0xF24AA8 | exact |
| 440 | Cyber Jar | Effect Monster | DARK | 3 | 900 | 900 | ROM 0xF24AAC | exact |
| 441 | Banisher of the Light | Effect Monster | LIGHT | 3 | 100 | 2000 | ROM 0xF24AB0 | exact |
| 442 | Giant Rat | Effect Monster | EARTH | 4 | 1400 | 1450 | ROM 0xF24AB4 | exact |
| 443 | Senju of the Thousand Hands | Effect Monster | LIGHT | 4 | 1400 | 1000 | ROM 0xF24AB8 | exact |
| 444 | UFO Turtle | Effect Monster | FIRE | 4 | 1400 | 1200 | ROM 0xF24ABC | exact |
| 445 | Flash Assailant | Effect Monster | DARK | 4 | 2000 | 2000 | ROM 0xF24AC0 | exact |
| 446 | Karate Man | Effect Monster | EARTH | 3 | 1000 | 1000 | ROM 0xF24AC4 | exact |
| 447 | Giant Germ | Effect Monster | DARK | 2 | 1000 | 100 | ROM 0xF24AC8 | exact |
| 448 | Nimble Momonga | Effect Monster | EARTH | 2 | 1000 | 100 | ROM 0xF24ACC | exact |
| 449 | Shining Angel | Effect Monster | LIGHT | 4 | 1400 | 800 | ROM 0xF24AD0 | exact |
| 450 | Mother Grizzly | Effect Monster | WATER | 4 | 1400 | 1000 | ROM 0xF24AD4 | exact |
| 451 | Flying Kamakiri #1 | Effect Monster | WIND | 4 | 1400 | 900 | ROM 0xF24AD8 | exact |
| 452 | Ceremonial Bell | Effect Monster | LIGHT | 3 | 0 | 1850 | ROM 0xF24ADC | exact |
| 453 | Sonic Bird | Effect Monster | WIND | 4 | 1400 | 1000 | ROM 0xF24AE0 | exact |
| 454 | Mystic Tomato | Effect Monster | DARK | 4 | 1400 | 1100 | ROM 0xF24AE4 | exact |
| 455 | Gaia Power | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AE8 | exact |
| 456 | Umiiruka | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AEC | exact |
| 457 | Molten Destruction | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AF0 | exact |
| 458 | Rising Air Current | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AF4 | exact |
| 459 | Luminous Spark | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AF8 | exact |
| 460 | Mystic Plasma Zone | Spell | NONE | 0 | 0 | 0 | ROM 0xF24AFC | exact |
| 461 | Messenger of Peace | Spell | NONE | 0 | 0 | 0 | ROM 0xF24B00 | exact |
| 462 | Michizure | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B04 | exact |
| 463 | Numinous Healer | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B08 | exact |
| 464 | Minor Goblin Official | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B0C | exact |
| 465 | Gamble | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B10 | exact |
| 466 | DNA Surgery | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B14 | exact |
| 467 | Backup Soldier | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B18 | exact |
| 468 | Attack and Receive | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B1C | exact |
| 469 | Ceasefire | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B20 | exact |
| 470 | Light of Intervention | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B24 | exact |
| 471 | Respect Play | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B28 | exact |
| 472 | Imperial Order | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B2C | exact |
| 473 | Skull Invitation | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B30 | exact |
| 474 | Nobleman of Crossout | Spell | NONE | 0 | 0 | 0 | ROM 0xF24B34 | exact |
| 475 | Nobleman of Extermination | Spell | NONE | 0 | 0 | 0 | ROM 0xF24B38 | exact |
| 476 | The Shallow Grave | Spell | NONE | 0 | 0 | 0 | ROM 0xF24B3C | exact |
| 477 | Premature Burial | Spell | NONE | 0 | 0 | 0 | ROM 0xF24B40 | exact |
| 478 | Inspection | Spell | NONE | 0 | 0 | 0 | ROM 0xF24B44 | exact |
| 479 | Morphing Jar #2 | Effect Monster | EARTH | 3 | 800 | 700 | ROM 0xF24B48 | exact |
| 480 | Bubonic Vermin | Effect Monster | EARTH | 3 | 900 | 600 | ROM 0xF24B4C | exact |
| 481 | Flame Champion | Normal Monster | FIRE | 5 | 1900 | 1300 | ROM 0xF24B50 | exact |
| 482 | Twin-Headed Fire Dragon | Normal Monster | FIRE | 6 | 2200 | 1700 | ROM 0xF24B54 | exact |
| 483 | Darkfire Soldier #1 | Normal Monster | FIRE | 4 | 1700 | 1150 | ROM 0xF24B58 | exact |
| 484 | Mr. Volcano | Normal Monster | FIRE | 5 | 2100 | 1300 | ROM 0xF24B5C | exact |
| 485 | Darkfire Soldier #2 | Normal Monster | FIRE | 4 | 1700 | 1100 | ROM 0xF24B60 | exact |
| 486 | Kiseitai | Effect Monster | DARK | 2 | 300 | 800 | ROM 0xF24B64 | exact |
| 487 | Cyber Falcon | Normal Monster | WIND | 4 | 1400 | 1200 | ROM 0xF24B68 | exact |
| 488 | Dark Bat | Normal Monster | WIND | 3 | 1000 | 1000 | ROM 0xF24B6C | exact |
| 489 | Flying Kamakiri #2 | Normal Monster | WIND | 4 | 1500 | 800 | ROM 0xF24B70 | exact |
| 490 | Harpie's Brother | Normal Monster | WIND | 4 | 1800 | 600 | ROM 0xF24B74 | exact |
| 491 | Oni Tank T-34 | Normal Monster | EARTH | 4 | 1400 | 1700 | ROM 0xF24B78 | exact |
| 492 | Overdrive | Normal Monster | EARTH | 4 | 1600 | 1500 | ROM 0xF24B7C | exact |
| 493 | Buster Blader | Effect Monster | EARTH | 7 | 2600 | 2300 | ROM 0xF24B80 | exact |
| 494 | Time Seal | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B84 | exact |
| 495 | Gift of The Mystical Elf | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B88 | exact |
| 496 | Dust Tornado | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B8C | exact |
| 497 | Call of the Haunted | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B90 | exact |
| 498 | Solomon's Lawbook | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B94 | exact |
| 499 | Enchanted Javelin | Trap | NONE | 0 | 0 | 0 | ROM 0xF24B98 | exact |
| 500 | Valkyrion the Magna Warrior | Effect Monster | EARTH | 8 | 3500 | 3850 | ROM 0xF24B9C | exact |
| 501 | Alligator's Sword Dragon | Fusion Monster | WIND | 5 | 1700 | 1500 | ROM 0xF24BA0 | exact |
| 502 | Vorse Raider | Normal Monster | DARK | 4 | 1900 | 1200 | ROM 0xF24BA4 | exact |
| 503 | Ring of Destruction | Trap | NONE | 0 | 0 | 0 | ROM 0xF24BA8 | exact |
| 504 | Aqua Chorus | Trap | NONE | 0 | 0 | 0 | ROM 0xF24BAC | exact |
| 505 | Sebek's Blessing | Spell | NONE | 0 | 0 | 0 | ROM 0xF24BB0 | exact |
| 506 | Luminous Soldier | Effect Monster | LIGHT | 5 | 2100 | 1400 | ROM 0xF24BB4 | exact |
| 507 | Wolf Axwielder | Normal Monster | EARTH | 4 | 1650 | 1000 | ROM 0xF24BB8 | exact |
| 508 | The Illusory Gentleman | Normal Monster | DARK | 4 | 1500 | 1600 | ROM 0xF24BBC | exact |
| 509 | Birdface | Effect Monster | WIND | 4 | 1600 | 1600 | ROM 0xF24BC0 | exact |
| 510 | Kryuel | Effect Monster | DARK | 4 | 1000 | 1700 | ROM 0xF24BC4 | exact |
| 511 | Airknight Parshath | Effect Monster | LIGHT | 5 | 1900 | 1400 | ROM 0xF24BC8 | exact |
| 512 | Fairy King Truesdale | Effect Monster | WATER | 6 | 2200 | 1500 | ROM 0xF24BCC | exact |
| 513 | Maiden of the Aqua | Effect Monster | WATER | 4 | 700 | 2000 | ROM 0xF24BD0 | exact |
| 514 | Robotic Knight | Normal Monster | FIRE | 4 | 1600 | 1800 | ROM 0xF24BD4 | exact |
| 515 | Molten Behemoth | Normal Monster | FIRE | 5 | 1000 | 2200 | ROM 0xF24BD8 | exact |
| 516 | Injection Fairy Lily | Effect Monster | EARTH | 3 | 400 | 1500 | ROM 0xF24BDC | exact |
| 517 | Woodland Sprite | Effect Monster | EARTH | 3 | 900 | 400 | ROM 0xF24BE0 | exact |
| 518 | Arsenal Bug | Effect Monster | EARTH | 3 | 2000 | 2000 | ROM 0xF24BE4 | exact |
| 519 | Kinetic Soldier | Effect Monster | EARTH | 3 | 1350 | 1800 | ROM 0xF24BE8 | exact |
| 520 | Souleater | Normal Monster | EARTH | 4 | 1200 | 0 | ROM 0xF24BEC | exact |
| 521 | Slate Warrior | Effect Monster | WIND | 4 | 1900 | 400 | ROM 0xF24BF0 | exact |
| 522 | Shapesnatch | Normal Monster | DARK | 5 | 1200 | 1700 | ROM 0xF24BF4 | exact |
| 523 | Servant of Catabolism | Effect Monster | LIGHT | 3 | 700 | 500 | ROM 0xF24BF8 | exact |
| 524 | Boneheimer | Normal Monster | WATER | 3 | 850 | 400 | ROM 0xF24BFC | exact |
| 525 | Flame Dancer | Normal Monster | FIRE | 2 | 550 | 450 | ROM 0xF24C00 | exact |
| 526 | Gearfried the Iron Knight | Effect Monster | EARTH | 4 | 1800 | 1600 | ROM 0xF24C04 | exact |
| 527 | Humanoid Slime | Normal Monster | WATER | 4 | 800 | 2000 | ROM 0xF24C08 | exact |
| 528 | Worm Drake | Normal Monster | EARTH | 4 | 1400 | 1500 | ROM 0xF24C0C | exact |
| 529 | Humanoid Worm Drake | Fusion Monster | WATER | 7 | 2200 | 2000 | ROM 0xF24C10 | exact |
| 530 | Flying Fish | Normal Monster | WIND | 4 | 800 | 500 | ROM 0xF24C14 | exact |
| 531 | Amphibian Beast | Normal Monster | WATER | 6 | 2400 | 2000 | ROM 0xF24C18 | exact |
| 532 | Lightning Conger | Normal Monster | WATER | 3 | 350 | 750 | ROM 0xF24C1C | exact |
| 533 | Spherous Lady | Normal Monster | EARTH | 3 | 400 | 1400 | ROM 0xF24C20 | exact |
| 534 | Shining Abyss | Normal Monster | LIGHT | 4 | 1600 | 1800 | ROM 0xF24C24 | exact |
| 535 | Gadget Soldier | Normal Monster | FIRE | 6 | 1800 | 2000 | ROM 0xF24C28 | exact |
| 536 | Grand Tiki Elder | Normal Monster | DARK | 4 | 1500 | 800 | ROM 0xF24C2C | exact |
| 537 | The Masked Beast | Ritual Monster | DARK | 8 | 3200 | 1800 | ROM 0xF24C30 | exact |
| 538 | Melchid the Four-Face Beast | Normal Monster | DARK | 4 | 1500 | 1200 | ROM 0xF24C34 | exact |
| 539 | Mask of Weakness | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C38 | exact |
| 540 | Curse of the Masked Beast | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C3C | exact |
| 541 | Mask of Dispel | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C40 | exact |
| 542 | Mask of Restrict | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C44 | exact |
| 543 | Mask of the Accursed | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C48 | exact |
| 544 | Mask of Brutality | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C4C | exact |
| 545 | Lightning Blade | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C50 | exact |
| 546 | Fairy Box | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C54 | exact |
| 547 | Torrential Tribute | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C58 | exact |
| 548 | Multiplication of Ants | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C5C | exact |
| 549 | Nightmare's Steelcage | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C60 | exact |
| 550 | Infinite Cards | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C64 | exact |
| 551 | Card of Safe Return | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C68 | exact |
| 552 | Magic Cylinder | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C6C | exact |
| 553 | Solemn Wishes | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C70 | exact |
| 554 | Burning Land | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C74 | exact |
| 555 | Fairy Meteor Crush | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C78 | exact |
| 556 | Limiter Removal | Spell | NONE | 0 | 0 | 0 | ROM 0xF24C7C | exact |
| 557 | Gravity Bind | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C80 | exact |
| 558 | Shadow of Eyes | Trap | NONE | 0 | 0 | 0 | ROM 0xF24C84 | exact |
| 559 | Girochin Kuwagata | Normal Monster | WIND | 4 | 1700 | 1000 | ROM 0xF24C88 | exact |
| 560 | Hayabusa Knight | Effect Monster | EARTH | 3 | 1000 | 700 | ROM 0xF24C8C | exact |
| 561 | 4-Starred Ladybug of Doom | Effect Monster | WIND | 3 | 800 | 1200 | ROM 0xF24C90 | exact |
| 562 | Gradius | Normal Monster | LIGHT | 4 | 1200 | 800 | ROM 0xF24C94 | exact |
| 563 | Mad Sword Beast | Effect Monster | EARTH | 4 | 1400 | 1200 | ROM 0xF24C98 | exact |
| 564 | Skull Mariner | Normal Monster | WATER | 4 | 1600 | 900 | ROM 0xF24C9C | exact |
| 565 | The All-Seeing White Tiger | Normal Monster | WIND | 3 | 1300 | 500 | ROM 0xF24CA0 | exact |
| 566 | Goblin Attack Force | Effect Monster | EARTH | 4 | 2300 | 0 | ROM 0xF24CA4 | exact |
| 567 | Island Turtle | Normal Monster | WATER | 4 | 1100 | 2000 | ROM 0xF24CA8 | exact |
| 568 | Wingweaver | Normal Monster | LIGHT | 7 | 2750 | 2400 | ROM 0xF24CAC | exact |
| 569 | Science Soldier | Normal Monster | DARK | 3 | 800 | 800 | ROM 0xF24CB0 | exact |
| 570 | Souls of the Forgotten | Normal Monster | DARK | 2 | 900 | 200 | ROM 0xF24CB4 | exact |
| 571 | Dokuroyaiba | Normal Monster | FIRE | 3 | 1000 | 400 | ROM 0xF24CB8 | exact |
| 572 | Rain of Mercy | Spell | NONE | 0 | 0 | 0 | ROM 0xF24CBC | exact |
| 573 | Yellow Luster Shield | Spell | NONE | 0 | 0 | 0 | ROM 0xF24CC0 | exact |
| 574 | Spring of Rebirth | Spell | NONE | 0 | 0 | 0 | ROM 0xF24CC4 | exact |
| 575 | Thousand Knives | Spell | NONE | 0 | 0 | 0 | ROM 0xF24CC8 | exact |
| 576 | Ground Collapse | Spell | NONE | 0 | 0 | 0 | ROM 0xF24CCC | exact |
| 577 | The Unfriendly Amazon | Effect Monster | EARTH | 4 | 2000 | 1000 | ROM 0xF24CD0 | exact |
| 578 | Amazon Archer | Effect Monster | EARTH | 4 | 1400 | 1000 | ROM 0xF24CD4 | exact |
| 579 | Fire Princess | Effect Monster | FIRE | 4 | 1300 | 1500 | ROM 0xF24CD8 | exact |
| 580 | Lady Assailant of Flames | Effect Monster | FIRE | 4 | 1500 | 1000 | ROM 0xF24CDC | exact |
| 581 | Fire Sorcerer | Effect Monster | FIRE | 4 | 1000 | 1500 | ROM 0xF24CE0 | exact |
| 582 | Spirit of the Breeze | Effect Monster | WIND | 3 | 0 | 1800 | ROM 0xF24CE4 | exact |
| 583 | Dancing Fairy | Effect Monster | WIND | 4 | 1700 | 1000 | ROM 0xF24CE8 | exact |
| 584 | Empress Mantis | Normal Monster | WIND | 6 | 2200 | 1400 | ROM 0xF24CEC | exact |
| 585 | Cure Mermaid | Effect Monster | WATER | 4 | 1500 | 800 | ROM 0xF24CF0 | exact |
| 586 | Hysteric Fairy | Effect Monster | LIGHT | 4 | 1800 | 500 | ROM 0xF24CF4 | exact |
| 587 | Bio-Mage | Normal Monster | LIGHT | 3 | 1150 | 1000 | ROM 0xF24CF8 | exact |
| 588 | The Forgiving Maiden | Effect Monster | LIGHT | 4 | 850 | 2000 | ROM 0xF24CFC | exact |
| 589 | St. Joan | Fusion Monster | LIGHT | 7 | 2800 | 2000 | ROM 0xF24D00 | exact |
| 590 | Marie the Fallen One | Effect Monster | DARK | 5 | 1700 | 1200 | ROM 0xF24D04 | exact |
| 591 | Jar of Greed | Trap | NONE | 0 | 0 | 0 | ROM 0xF24D08 | exact |
| 592 | Scroll of Bewitchment | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D0C | exact |
| 593 | United We Stand | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D10 | exact |
| 594 | Mage Power | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D14 | exact |
| 595 | Offerings to the Doomed | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D18 | exact |
| 596 | Meteor of Destruction | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D1C | exact |
| 597 | Lightning Vortex | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D20 | exact |
| 598 | The Portrait's Secret | Normal Monster | EARTH | 4 | 1200 | 1500 | ROM 0xF24D24 | exact |
| 599 | The Gross Ghost of Fled Dreams | Normal Monster | DARK | 4 | 1300 | 1800 | ROM 0xF24D28 | exact |
| 600 | Headless Knight | Normal Monster | EARTH | 4 | 1450 | 1700 | ROM 0xF24D2C | exact |
| 601 | Dark Magician's Tome of Black Magic | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D30 | exact |
| 602 | Destiny Board | Trap | NONE | 0 | 0 | 0 | ROM 0xF24D34 | exact |
| 603 | The Dark Door | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D38 | exact |
| 604 | Earthbound Spirit | Normal Monster | EARTH | 4 | 500 | 2000 | ROM 0xF24D3C | exact |
| 605 | The Earl of Demise | Normal Monster | DARK | 5 | 2000 | 700 | ROM 0xF24D40 | exact |
| 606 | Dark Sage | Effect Monster | DARK | 9 | 2800 | 3200 | ROM 0xF24D44 | exact |
| 607 | Cathedral of Nobles | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D48 | exact |
| 608 | Embodiment of Apophis | Trap | NONE | 0 | 0 | 0 | ROM 0xF24D4C | exact |
| 609 | Foolish Burial | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D50 | exact |
| 610 | Makiu | Spell | NONE | 0 | 0 | 0 | ROM 0xF24D54 | exact |
| 611 | Cyber Harpie Lady | Effect Monster | WIND | 4 | 1800 | 1300 | ROM 0xF24D58 | exact |
| 612 | Mystical Beast Serket | Effect Monster | EARTH | 6 | 2500 | 2000 | ROM 0xF24D5C | exact |
| 613 | Swift Gaia the Fierce Knight | Effect Monster | DARK | 7 | 2300 | 2100 | ROM 0xF24D60 | exact |
| 614 | Obnoxious Celtic Guard | Effect Monster | EARTH | 4 | 1400 | 1200 | ROM 0xF24D64 | exact |
| 615 | Zombyra the Dark | Effect Monster | DARK | 4 | 2100 | 500 | ROM 0xF24D68 | exact |
| 616 | Jowgen the Spiritualist | Effect Monster | LIGHT | 3 | 200 | 1300 | ROM 0xF24D6C | exact |
| 617 | Kycoo the Ghost Destroyer | Effect Monster | DARK | 4 | 1800 | 700 | ROM 0xF24D70 | exact |
| 618 | Summoner of Illusions | Effect Monster | LIGHT | 3 | 800 | 900 | ROM 0xF24D74 | exact |
| 619 | Bazoo the Soul-Eater | Effect Monster | EARTH | 4 | 1600 | 900 | ROM 0xF24D78 | exact |
| 620 | Soul of Purity and Light | Effect Monster | LIGHT | 6 | 2000 | 1800 | ROM 0xF24D7C | exact |
| 621 | Spirit of Flames | Effect Monster | FIRE | 4 | 1700 | 1000 | ROM 0xF24D80 | exact |
| 622 | Aqua Spirit | Effect Monster | WATER | 4 | 1600 | 1200 | ROM 0xF24D84 | exact |
| 623 | The Rock Spirit | Effect Monster | EARTH | 4 | 1700 | 1000 | ROM 0xF24D88 | exact |
| 624 | Garuda the Wind Spirit | Effect Monster | WIND | 4 | 1600 | 1200 | ROM 0xF24D8C | exact |
| 625 | Gilasaurus | Effect Monster | EARTH | 3 | 1400 | 400 | ROM 0xF24D90 | exact |
| 626 | Supply | Effect Monster | EARTH | 4 | 1300 | 800 | ROM 0xF24D94 | exact |
| 627 | Maryokutai | Effect Monster | WATER | 3 | 900 | 900 | ROM 0xF24D98 | exact |
| 628 | Royal Command | Trap | NONE | 0 | 0 | 0 | ROM 0xF24D9C | exact |
| 629 | Graverobber's Retribution | Trap | NONE | 0 | 0 | 0 | ROM 0xF24DA0 | exact |
| 630 | Deal of Phantom | Trap | NONE | 0 | 0 | 0 | ROM 0xF24DA4 | exact |
| 631 | Blind Destruction | Trap | NONE | 0 | 0 | 0 | ROM 0xF24DA8 | exact |
| 632 | Cyclon Laser | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DAC | exact |
| 633 | Spirit Message "I" | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DB0 | exact |
| 634 | Spirit Message "N" | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DB4 | exact |
| 635 | Spirit Message "A" | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DB8 | exact |
| 636 | Spirit Message "L" | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DBC | exact |
| 637 | Fusion Gate | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DC0 | exact |
| 638 | Miracle Dig | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DC4 | exact |
| 639 | Amazoness Swords Woman | Effect Monster | EARTH | 4 | 1500 | 1600 | ROM 0xF24DC8 | exact |
| 640 | Enchanted Arrow | Spell | NONE | 0 | 0 | 0 | ROM 0xF24DCC | exact |
| 641 | Amazoness Fighter | Effect Monster | EARTH | 4 | 1500 | 1300 | ROM 0xF24DD0 | exact |
| 642 | Nightmare Wheel | Trap | NONE | 0 | 0 | 0 | ROM 0xF24DD4 | exact |
| 643 | Byser Shock | Effect Monster | DARK | 5 | 800 | 600 | ROM 0xF24DD8 | exact |
| 644 | Lesser Fiend | Effect Monster | DARK | 5 | 2100 | 1000 | ROM 0xF24DDC | exact |
| 645 | Ryu-Kishin Clown | Effect Monster | DARK | 2 | 800 | 500 | ROM 0xF24DE0 | exact |
| 646 | Opticlops | Normal Monster | DARK | 4 | 1800 | 1700 | ROM 0xF24DE4 | exact |
| 647 | Fatal Abacus | Trap | NONE | 0 | 0 | 0 | ROM 0xF24DE8 | exact |
| 648 | Throwstone Unit | Effect Monster | EARTH | 4 | 900 | 2000 | ROM 0xF24DEC | exact |
| 649 | Marauding Captain | Effect Monster | EARTH | 3 | 1200 | 400 | ROM 0xF24DF0 | exact |
| 650 | Warrior Dai Grepher | Normal Monster | EARTH | 4 | 1700 | 1600 | ROM 0xF24DF4 | exact |
| 651 | Exiled Force | Effect Monster | EARTH | 4 | 1000 | 1000 | ROM 0xF24DF8 | exact |
| 652 | The Hunter with 7 Weapons | Effect Monster | EARTH | 3 | 1000 | 600 | ROM 0xF24DFC | exact |
| 653 | Reinforcement of the Army | Spell | NONE | 0 | 0 | 0 | ROM 0xF24E00 | exact |
| 654 | The Warrior Returning Alive | Spell | NONE | 0 | 0 | 0 | ROM 0xF24E04 | exact |
| 655 | Spear Dragon | Effect Monster | WIND | 4 | 1900 | 0 | ROM 0xF24E08 | exact |
| 656 | The Dragon dwelling in the Cave | Normal Monster | WIND | 4 | 1300 | 2000 | ROM 0xF24E0C | exact |
| 657 | Lizard Soldier | Normal Monster | WIND | 3 | 1100 | 800 | ROM 0xF24E10 | exact |
| 658 | Cave Dragon | Effect Monster | WIND | 4 | 2000 | 100 | ROM 0xF24E14 | exact |
| 659 | Gray Wing | Effect Monster | WIND | 3 | 1300 | 700 | ROM 0xF24E18 | exact |
| 660 | Troop Dragon | Effect Monster | WIND | 2 | 700 | 800 | ROM 0xF24E1C | exact |
| 661 | Dragon's Rage | Trap | NONE | 0 | 0 | 0 | ROM 0xF24E20 | exact |
| 662 | Burst Breath | Trap | NONE | 0 | 0 | 0 | ROM 0xF24E24 | exact |
| 663 | Luster Dragon | Normal Monster | WIND | 6 | 2400 | 1400 | ROM 0xF24E28 | exact |
| 664 | Emergency Provisions | Spell | NONE | 0 | 0 | 0 | ROM 0xF24E2C | exact |
| 665 | Keldo | Effect Monster | EARTH | 4 | 1200 | 1600 | ROM 0xF24E30 | exact |
| 666 | Kaiser Glider | Effect Monster | LIGHT | 6 | 2400 | 2200 | ROM 0xF24E34 | exact |
| 667 | Spell Reproduction | Spell | NONE | 0 | 0 | 0 | ROM 0xF24E38 | exact |
| 668 | Mudora | Effect Monster | EARTH | 4 | 1500 | 1800 | ROM 0xF24E3C | exact |
| 669 | Cestus of Dagla | Spell | NONE | 0 | 0 | 0 | ROM 0xF24E40 | exact |
| 670 | Des Feral Imp | Effect Monster | DARK | 4 | 1600 | 1800 | ROM 0xF24E44 | exact |
| 671 | Reversal of Graves | Trap | NONE | 0 | 0 | 0 | ROM 0xF24E48 | exact |
| 672 | Kelbek | Effect Monster | EARTH | 4 | 1500 | 1800 | ROM 0xF24E4C | exact |
| 673 | Zolga | Effect Monster | EARTH | 4 | 1700 | 1200 | ROM 0xF24E50 | exact |
| 674 | Agido | Effect Monster | EARTH | 4 | 1500 | 1300 | ROM 0xF24E54 | exact |
| 675 | Fiber Jar | Effect Monster | EARTH | 3 | 500 | 500 | ROM 0xF24E58 | exact |
| 676 | Gradius' Option | Effect Monster | LIGHT | 1 | 0 | 0 | ROM 0xF24E5C | exact |
| 677 | Inaba White Rabbit | Effect Monster | EARTH | 3 | 700 | 500 | ROM 0xF24E60 | exact |
| 678 | Yata-Garasu | Effect Monster | WIND | 2 | 200 | 100 | ROM 0xF24E64 | exact |
| 679 | Susa Soldier | Effect Monster | EARTH | 4 | 2000 | 1600 | ROM 0xF24E68 | exact |
| 680 | Yamata Dragon | Effect Monster | FIRE | 7 | 2600 | 3100 | ROM 0xF24E6C | exact |
| 681 | Great Long Nose | Effect Monster | DARK | 5 | 1900 | 1700 | ROM 0xF24E70 | exact |
| 682 | Hino-Kagu-Tsuchi | Effect Monster | FIRE | 8 | 2800 | 2900 | ROM 0xF24E74 | exact |
| 683 | Fushi No Tori | Effect Monster | FIRE | 4 | 1200 | 0 | ROM 0xF24E78 | exact |
| 684 | A Legendary Ocean | Spell | NONE | 0 | 0 | 0 | ROM 0xF24E7C | exact |
| 685 | Disappear | Trap | NONE | 0 | 0 | 0 | ROM 0xF24E80 | exact |
| 686 | Bottomless Trap Hole | Trap | NONE | 0 | 0 | 0 | ROM 0xF24E84 | exact |
| 687 | Fiend Comedian | Trap | NONE | 0 | 0 | 0 | ROM 0xF24E88 | exact |
| 688 | Gora Turtle | Effect Monster | WATER | 3 | 1100 | 1100 | ROM 0xF24E8C | exact |
| 689 | Sasuke Samurai | Effect Monster | WIND | 2 | 500 | 800 | ROM 0xF24E90 | exact |
| 690 | Poison Mummy | Effect Monster | EARTH | 4 | 1000 | 1800 | ROM 0xF24E94 | exact |
| 691 | Dark Dust Spirit | Effect Monster | EARTH | 6 | 2200 | 1800 | ROM 0xF24E98 | exact |
| 692 | Swarm of Scarabs | Effect Monster | DARK | 3 | 500 | 1000 | ROM 0xF24E9C | exact |
| 693 | Swarm of Locusts | Effect Monster | DARK | 3 | 1000 | 500 | ROM 0xF24EA0 | exact |
| 694 | Giant Axe Mummy | Effect Monster | EARTH | 5 | 1700 | 2000 | ROM 0xF24EA4 | exact |
| 695 | 8-Claws Scorpion | Effect Monster | DARK | 2 | 300 | 200 | ROM 0xF24EA8 | exact |
| 696 | Guardian Sphinx | Effect Monster | EARTH | 5 | 1700 | 2400 | ROM 0xF24EAC | exact |
| 697 | Pyramid Turtle | Effect Monster | EARTH | 4 | 1200 | 1400 | ROM 0xF24EB0 | exact |
| 698 | Dice Jar | Effect Monster | LIGHT | 3 | 200 | 300 | ROM 0xF24EB4 | exact |
| 699 | Don Zaloog | Effect Monster | DARK | 4 | 1400 | 1500 | ROM 0xF24EB8 | exact |
| 700 | Des Lacooda | Effect Monster | EARTH | 3 | 500 | 600 | ROM 0xF24EBC | exact |
| 701 | Book of Taiyou | Spell | NONE | 0 | 0 | 0 | ROM 0xF24EC0 | exact |
| 702 | Book of Moon | Spell | NONE | 0 | 0 | 0 | ROM 0xF24EC4 | exact |
| 703 | Bottomless Shifting Sand | Trap | NONE | 0 | 0 | 0 | ROM 0xF24EC8 | exact |
| 704 | Statue of the Wicked | Trap | NONE | 0 | 0 | 0 | ROM 0xF24ECC | exact |
| 705 | Needle Wall | Trap | NONE | 0 | 0 | 0 | ROM 0xF24ED0 | exact |
| 706 | Reckless Greed | Trap | NONE | 0 | 0 | 0 | ROM 0xF24ED4 | exact |
| 707 | Toon Dark Magician Girl | Effect Monster | DARK | 6 | 2000 | 1700 | ROM 0xF24ED8 | exact |
| 708 | Legendary Fiend | Effect Monster | DARK | 6 | 1500 | 1800 | ROM 0xF24EDC | exact |
| 709 | Toon Table of Contents | Spell | NONE | 0 | 0 | 0 | ROM 0xF24EE0 | exact |
| 710 | Toon Masked Sorcerer | Effect Monster | DARK | 4 | 900 | 1400 | ROM 0xF24EE4 | exact |
| 711 | Toon Gemini Elf | Effect Monster | EARTH | 4 | 1900 | 900 | ROM 0xF24EE8 | exact |
| 712 | Toon Cannon Soldier | Effect Monster | DARK | 4 | 1400 | 1300 | ROM 0xF24EEC | exact |
| 713 | Toon Goblin Attack Force | Effect Monster | EARTH | 4 | 2300 | 0 | ROM 0xF24EF0 | exact |
| 714 | Card of Sanctity | Spell | NONE | 0 | 0 | 0 | ROM 0xF24EF4 | exact |
| 715 | Newdoria | Effect Monster | DARK | 4 | 1200 | 800 | ROM 0xF24EF8 | exact |
| 716 | Hidden Soldier | Trap | NONE | 0 | 0 | 0 | ROM 0xF24EFC | exact |
| 717 | Gil Garth | Normal Monster | DARK | 4 | 1800 | 1200 | ROM 0xF24F00 | exact |
| 718 | Coffin Seller | Trap | NONE | 0 | 0 | 0 | ROM 0xF24F04 | exact |
| 719 | Calamity of the Wicked | Trap | NONE | 0 | 0 | 0 | ROM 0xF24F08 | exact |
| 720 | Lava Golem | Effect Monster | FIRE | 8 | 3000 | 2500 | ROM 0xF24F0C | exact |
| 721 | Master of Dragon Soldier | Fusion Monster | LIGHT | 12 | 5000 | 5000 | ROM 0xF24F10 | exact |
| 722 | F.G.D. | Fusion Monster | DARK | 12 | 5000 | 5000 | ROM 0xF24F14 | exact |
| 723 | Queen's Knight | Normal Monster | LIGHT | 4 | 1500 | 1600 | ROM 0xF24F18 | exact |
| 724 | X-Head Cannon | Normal Monster | LIGHT | 4 | 1800 | 1500 | ROM 0xF24F1C | exact |
| 725 | Master Kyonshee | Normal Monster | EARTH | 4 | 1750 | 1000 | ROM 0xF24F20 | exact |
| 726 | Kabazauls | Normal Monster | WATER | 4 | 1700 | 1500 | ROM 0xF24F24 | exact |
| 727 | Inpachi | Normal Monster | EARTH | 4 | 1600 | 1900 | ROM 0xF24F28 | exact |
| 728 | Gravekeeper's Spy | Effect Monster | DARK | 4 | 1200 | 2000 | ROM 0xF24F2C | exact |
| 729 | Gravekeeper's Curse | Effect Monster | DARK | 3 | 800 | 800 | ROM 0xF24F30 | exact |
| 730 | Gravekeeper's Guard | Effect Monster | DARK | 4 | 1000 | 1900 | ROM 0xF24F34 | exact |
| 731 | Gravekeeper's Spear Soldier | Effect Monster | DARK | 4 | 1500 | 1000 | ROM 0xF24F38 | exact |
| 732 | Gravekeeper's Vassal | Effect Monster | DARK | 3 | 700 | 500 | ROM 0xF24F3C | exact |
| 733 | Gravekeeper's Cannonholder | Effect Monster | DARK | 4 | 1400 | 1200 | ROM 0xF24F40 | exact |
| 734 | Yomi Ship | Effect Monster | WATER | 3 | 800 | 1400 | ROM 0xF24F44 | exact |
| 735 | Cobra Jar | Effect Monster | EARTH | 2 | 600 | 300 | ROM 0xF24F48 | exact |
| 736 | Dark Room of Nightmare | Spell | NONE | 0 | 0 | 0 | ROM 0xF24F4C | exact |
| 737 | Dark Snake Syndrome | Spell | NONE | 0 | 0 | 0 | ROM 0xF24F50 | exact |
| 738 | Terraforming | Spell | NONE | 0 | 0 | 0 | ROM 0xF24F54 | exact |
| 739 | Banner of Courage | Spell | NONE | 0 | 0 | 0 | ROM 0xF24F58 | exact |
| 740 | Metamorphosis | Spell | NONE | 0 | 0 | 0 | ROM 0xF24F5C | exact |
| 741 | Curse of Aging | Trap | NONE | 0 | 0 | 0 | ROM 0xF24F60 | exact |
| 742 | Raigeki Break | Trap | NONE | 0 | 0 | 0 | ROM 0xF24F64 | exact |
| 743 | Non Aggression Area | Trap | NONE | 0 | 0 | 0 | ROM 0xF24F68 | exact |
| 744 | Y-Dragon Head | Effect Monster | LIGHT | 4 | 1500 | 1600 | ROM 0xF24F6C | exact |
| 745 | XY-Dragon Cannon | Fusion Monster | LIGHT | 6 | 2200 | 1900 | ROM 0xF24F70 | exact |
| 746 | Z-Metal Tank | Effect Monster | LIGHT | 4 | 1500 | 1300 | ROM 0xF24F74 | exact |
| 747 | XYZ-Dragon Cannon | Fusion Monster | LIGHT | 8 | 2800 | 2600 | ROM 0xF24F78 | exact |
| 748 | King's Knight | Effect Monster | LIGHT | 4 | 1600 | 1400 | ROM 0xF24F7C | exact |
| 749 | Jack's Knight | Normal Monster | LIGHT | 5 | 1900 | 1000 | ROM 0xF24F80 | exact |
| 750 | Drillago | Effect Monster | DARK | 4 | 1600 | 1100 | ROM 0xF24F84 | exact |
| 751 | People Running About | Normal Monster | FIRE | 2 | 600 | 600 | ROM 0xF24F88 | exact |
| 752 | Oppressed People | Normal Monster | WATER | 1 | 400 | 2000 | ROM 0xF24F8C | exact |
| 753 | United Resistance | Normal Monster | WIND | 3 | 1000 | 400 | ROM 0xF24F90 | exact |
| 754 | Dark Blade | Normal Monster | DARK | 4 | 1800 | 1500 | ROM 0xF24F94 | exact |
| 755 | Pitch-Dark Dragon | Effect Monster | DARK | 3 | 900 | 600 | ROM 0xF24F98 | exact |
| 756 | Decayed Commander | Effect Monster | EARTH | 4 | 1000 | 1500 | ROM 0xF24F9C | exact |
| 757 | Zombie Tiger | Effect Monster | EARTH | 3 | 1400 | 1600 | ROM 0xF24FA0 | exact |
| 758 | Giant Orc | Effect Monster | DARK | 4 | 2200 | 0 | ROM 0xF24FA4 | exact |
| 759 | Vampire Orchis | Effect Monster | EARTH | 4 | 1700 | 1000 | ROM 0xF24FA8 | exact |
| 760 | Des Dendle | Effect Monster | EARTH | 4 | 300 | 2000 | ROM 0xF24FAC | exact |
| 761 | D.D. Crazy Beast | Effect Monster | EARTH | 3 | 1400 | 1400 | ROM 0xF24FB0 | exact |
| 762 | Spell Canceller | Effect Monster | WIND | 5 | 1800 | 1600 | ROM 0xF24FB4 | exact |
| 763 | Paladin of White Dragon | Ritual Monster | LIGHT | 4 | 1900 | 1200 | ROM 0xF24FB8 | exact |
| 764 | White Dragon Ritual | Spell | NONE | 0 | 0 | 0 | ROM 0xF24FBC | exact |
| 765 | Demotion | Spell | NONE | 0 | 0 | 0 | ROM 0xF24FC0 | exact |
| 766 | Autonomous Action Unit | Spell | NONE | 0 | 0 | 0 | ROM 0xF24FC4 | exact |
| 767 | Poison of the Old Man | Spell | NONE | 0 | 0 | 0 | ROM 0xF24FC8 | exact |
| 768 | Kishido Spirit | Spell | NONE | 0 | 0 | 0 | ROM 0xF24FCC | exact |
| 769 | Wave-Motion Cannon | Spell | NONE | 0 | 0 | 0 | ROM 0xF24FD0 | exact |
| 770 | Huge Revolution | Trap | NONE | 0 | 0 | 0 | ROM 0xF24FD4 | exact |
| 771 | Thunder of Ruler | Trap | NONE | 0 | 0 | 0 | ROM 0xF24FD8 | exact |
| 772 | Meteorain | Trap | NONE | 0 | 0 | 0 | ROM 0xF24FDC | exact |
| 773 | Secret Barrel | Trap | NONE | 0 | 0 | 0 | ROM 0xF24FE0 | exact |
| 774 | XZ-Tank Cannon | Fusion Monster | LIGHT | 6 | 2400 | 2100 | ROM 0xF24FE4 | exact |
| 775 | YZ-Tank Dragon | Fusion Monster | LIGHT | 6 | 2100 | 2200 | ROM 0xF24FE8 | exact |
| 776 | Dark Paladin | Fusion Monster | DARK | 8 | 2900 | 2400 | ROM 0xF24FEC | exact |
| 777 | Great Angus | Normal Monster | FIRE | 4 | 1800 | 600 | ROM 0xF24FF0 | exact |
| 778 | Aitsu | Normal Monster | FIRE | 5 | 100 | 100 | ROM 0xF24FF4 | exact |
| 779 | Sonic Duck | Normal Monster | WIND | 3 | 1700 | 700 | ROM 0xF24FF8 | exact |
| 780 | Luster Dragon | Normal Monster | WIND | 4 | 1900 | 1600 | ROM 0xF24FFC | exact |
| 781 | Amazoness Paladin | Effect Monster | EARTH | 4 | 1700 | 300 | ROM 0xF25000 | exact |
| 782 | Skilled White Magician | Effect Monster | LIGHT | 4 | 1700 | 1900 | ROM 0xF25004 | exact |
| 783 | Skilled Dark Magician | Effect Monster | DARK | 4 | 1900 | 1700 | ROM 0xF25008 | exact |
| 784 | Apprentice Magician | Effect Monster | DARK | 2 | 400 | 800 | ROM 0xF2500C | exact |
| 785 | Old Vindictive Magician | Effect Monster | DARK | 2 | 450 | 600 | ROM 0xF25010 | exact |
| 786 | Magical Marionette | Effect Monster | DARK | 5 | 2000 | 1000 | ROM 0xF25014 | exact |
| 787 | Breaker the Magical Warrior | Effect Monster | DARK | 4 | 1600 | 1000 | ROM 0xF25018 | exact |
| 788 | Magical Plant Mandragola | Effect Monster | DARK | 2 | 500 | 200 | ROM 0xF2501C | exact |
| 789 | Magical Scientist | Effect Monster | DARK | 1 | 300 | 300 | ROM 0xF25020 | exact |
| 790 | Royal Magical Library | Effect Monster | LIGHT | 4 | 0 | 2000 | ROM 0xF25024 | exact |
| 791 | Armor Exe | Effect Monster | LIGHT | 4 | 2400 | 1400 | ROM 0xF25028 | exact |
| 792 | Tribe-Infecting Virus | Effect Monster | WATER | 4 | 1600 | 1000 | ROM 0xF2502C | exact |
| 793 | Des Koala | Effect Monster | DARK | 3 | 1100 | 1800 | ROM 0xF25030 | exact |
| 794 | Koitsu | Effect Monster | WATER | 10 | 200 | 100 | ROM 0xF25034 | exact |
| 795 | Pitch-Black Power Stone | Trap | NONE | 0 | 0 | 0 | ROM 0xF25038 | exact |
| 796 | Big Bang Shot | Spell | NONE | 0 | 0 | 0 | ROM 0xF2503C | exact |
| 797 | Mass Driver | Spell | NONE | 0 | 0 | 0 | ROM 0xF25040 | exact |
| 798 | Senri Eye | Spell | NONE | 0 | 0 | 0 | ROM 0xF25044 | exact |
| 799 | Emblem of Dragon Destroyer | Spell | NONE | 0 | 0 | 0 | ROM 0xF25048 | exact |
| 800 | Jar Robber | Spell | NONE | 0 | 0 | 0 | ROM 0xF2504C | exact |
| 801 | Mega Ton Magical Cannon | Spell | NONE | 0 | 0 | 0 | ROM 0xF25050 | exact |
| 802 | Continuous Destruction Punch | Spell | NONE | 0 | 0 | 0 | ROM 0xF25054 | exact |
| 803 | Exhausting Spell | Trap | NONE | 0 | 0 | 0 | ROM 0xF25058 | exact |
| 804 | Hidden Book of Spell | Trap | NONE | 0 | 0 | 0 | ROM 0xF2505C | exact |
| 805 | Miracle Restoring | Trap | NONE | 0 | 0 | 0 | ROM 0xF25060 | exact |
| 806 | Disarmament | Trap | NONE | 0 | 0 | 0 | ROM 0xF25064 | exact |
| 807 | Anti-Spell | Trap | NONE | 0 | 0 | 0 | ROM 0xF25068 | exact |
| 808 | The Spell Absorbing Life | Trap | NONE | 0 | 0 | 0 | ROM 0xF2506C | exact |
| 809 | Metal Reflect Slime | Trap | NONE | 0 | 0 | 0 | ROM 0xF25070 | exact |
| 810 | Bowganian | Effect Monster | DARK | 3 | 1300 | 1000 | ROM 0xF25074 | exact |
| 811 | Granadora | Effect Monster | WATER | 4 | 1900 | 700 | ROM 0xF25078 | exact |
| 812 | Shinato, King of a Higher Plane | Ritual Monster | LIGHT | 8 | 3300 | 3000 | ROM 0xF2507C | exact |
| 813 | Dark Flare Knight | Fusion Monster | DARK | 6 | 2200 | 800 | ROM 0xF25080 | exact |
| 814 | Mirage Knight | Effect Monster | LIGHT | 8 | 2800 | 2000 | ROM 0xF25084 | exact |
| 815 | Exodia Necross | Effect Monster | DARK | 4 | 1800 | 0 | ROM 0xF25088 | exact |
| 816 | Battle Footballer | Normal Monster | FIRE | 4 | 1000 | 2100 | ROM 0xF2508C | exact |
| 817 | Nin-Ken Dog | Normal Monster | WIND | 4 | 1800 | 1000 | ROM 0xF25090 | exact |
| 818 | Acrobat Monkey | Normal Monster | EARTH | 3 | 1000 | 1800 | ROM 0xF25094 | exact |
| 819 | Gyaku-Gire Panda | Effect Monster | EARTH | 3 | 800 | 1600 | ROM 0xF25098 | exact |
| 820 | D. D. Warrior Lady | Effect Monster | LIGHT | 4 | 1500 | 1600 | ROM 0xF2509C | exact |
| 821 | Thousand Needles | Effect Monster | EARTH | 4 | 1000 | 1800 | ROM 0xF250A0 | exact |
| 822 | Shinato's Ark | Spell | NONE | 0 | 0 | 0 | ROM 0xF250A4 | exact |
| 823 | Contract with Exodia | Spell | NONE | 0 | 0 | 0 | ROM 0xF250A8 | exact |
| 824 | Precious Cards from Beyond | Spell | NONE | 0 | 0 | 0 | ROM 0xF250AC | exact |
| 825 | Rod of the Mind's Eye | Spell | NONE | 0 | 0 | 0 | ROM 0xF250B0 | exact |
| 826 | Token Thanksgiving | Spell | NONE | 0 | 0 | 0 | ROM 0xF250B4 | exact |
| 827 | Morale Boost | Spell | NONE | 0 | 0 | 0 | ROM 0xF250B8 | exact |
| 828 | Ojama Trio | Trap | NONE | 0 | 0 | 0 | ROM 0xF250BC | exact |
| 829 | Really Eternal Rest | Trap | NONE | 0 | 0 | 0 | ROM 0xF250C0 | exact |
| 830 | Dark Magician Knight | Effect Monster | DARK | 7 | 2500 | 2100 | ROM 0xF250C4 | exact |
| 831 | Knight's Title | Spell | NONE | 0 | 0 | 0 | ROM 0xF250C8 | exact |
| 832 | Sage's Stone | Spell | NONE | 0 | 0 | 0 | ROM 0xF250CC | exact |
| 833 | Gagagigo | Normal Monster | WATER | 4 | 1850 | 1000 | ROM 0xF250D0 | exact |
| 834 | D. D. Trainer | Normal Monster | DARK | 1 | 100 | 2000 | ROM 0xF250D4 | exact |
| 835 | Ojama Green | Normal Monster | LIGHT | 2 | 0 | 1000 | ROM 0xF250D8 | exact |
| 836 | Archfiend Soldier | Normal Monster | DARK | 4 | 1900 | 1500 | ROM 0xF250DC | exact |
| 837 | Outstanding Dog Marron | Effect Monster | LIGHT | 1 | 100 | 100 | ROM 0xF250E0 | exact |
| 838 | Iron Blacksmith Kotetsu | Effect Monster | FIRE | 2 | 500 | 500 | ROM 0xF250E4 | exact |
| 839 | Mefist the Infernal General | Effect Monster | DARK | 5 | 1800 | 1700 | ROM 0xF250E8 | exact |
| 840 | Tsukuyomi | Effect Monster | DARK | 4 | 1100 | 1400 | ROM 0xF250EC | exact |
| 841 | Legendary Flame Lord | Ritual Monster | FIRE | 7 | 2400 | 2000 | ROM 0xF250F0 | exact |
| 842 | Dark Master - Zorc | Ritual Monster | DARK | 8 | 2700 | 1500 | ROM 0xF250F4 | exact |
| 843 | Incandescent Ordeal | Spell | NONE | 0 | 0 | 0 | ROM 0xF250F8 | exact |
| 844 | Contract with the Abyss | Spell | NONE | 0 | 0 | 0 | ROM 0xF250FC | exact |
| 845 | Contract with the Dark Master | Spell | NONE | 0 | 0 | 0 | ROM 0xF25100 | exact |
| 846 | Final Countdown | Spell | NONE | 0 | 0 | 0 | ROM 0xF25104 | exact |
| 847 | Altar for Tribute | Trap | NONE | 0 | 0 | 0 | ROM 0xF25108 | exact |
| 848 | Frozen Soul | Trap | NONE | 0 | 0 | 0 | ROM 0xF2510C | exact |
| 849 | Sakuretsu Armor | Trap | NONE | 0 | 0 | 0 | ROM 0xF25110 | exact |
| 850 | Ray of Hope | Trap | NONE | 0 | 0 | 0 | ROM 0xF25114 | exact |
| 851 | Ojama Yellow | Normal Monster | LIGHT | 2 | 0 | 1000 | ROM 0xF25118 | exact |
| 852 | Ojama Black | Normal Monster | LIGHT | 2 | 0 | 1000 | ROM 0xF2511C | exact |
| 853 | Soul Tiger | Normal Monster | EARTH | 4 | 0 | 2100 | ROM 0xF25120 | exact |
| 854 | Big Koala | Normal Monster | EARTH | 7 | 2700 | 2000 | ROM 0xF25124 | exact |
| 855 | Des Kangaroo | Effect Monster | DARK | 4 | 1500 | 1700 | ROM 0xF25128 | exact |
| 856 | Crimson Ninja | Effect Monster | EARTH | 1 | 300 | 300 | ROM 0xF2512C | exact |
| 857 | Gale Lizard | Effect Monster | WATER | 4 | 1400 | 700 | ROM 0xF25130 | exact |
| 858 | Spirit of the Pot of Greed | Effect Monster | LIGHT | 1 | 100 | 100 | ROM 0xF25134 | exact |
| 859 | Sasuke Samurai #3 | Effect Monster | LIGHT | 3 | 1000 | 1000 | ROM 0xF25138 | exact |
| 860 | Witch Doctor of Chaos | Effect Monster | DARK | 2 | 500 | 500 | ROM 0xF2513C | exact |
| 861 | Chaos Necromancer | Effect Monster | DARK | 1 | 0 | 0 | ROM 0xF25140 | exact |
| 862 | Inferno | Effect Monster | FIRE | 4 | 1100 | 1900 | ROM 0xF25144 | exact |
| 863 | Fenrir | Effect Monster | WATER | 4 | 1400 | 1200 | ROM 0xF25148 | exact |
| 864 | Gigantes | Effect Monster | EARTH | 4 | 1900 | 1300 | ROM 0xF2514C | exact |
| 865 | Silpheed | Effect Monster | WIND | 4 | 1700 | 700 | ROM 0xF25150 | exact |
| 866 | Chaos Sorcerer | Effect Monster | DARK | 6 | 2300 | 2000 | ROM 0xF25154 | exact |
| 867 | Gren Maju Da Eiza | Effect Monster | FIRE | 3 | 0 | 0 | ROM 0xF25158 | exact |
| 868 | Black Luster Soldier - Envoy of the Beginning | Effect Monster | LIGHT | 8 | 3000 | 2500 | ROM 0xF2515C | exact |
| 869 | Fuhma Shuriken | Spell | NONE | 0 | 0 | 0 | ROM 0xF25160 | exact |
| 870 | Heart of the Underdog | Spell | NONE | 0 | 0 | 0 | ROM 0xF25164 | exact |
| 871 | Ojama Delta Hurricane!! | Spell | NONE | 0 | 0 | 0 | ROM 0xF25168 | exact |
| 872 | Chaos End | Spell | NONE | 0 | 0 | 0 | ROM 0xF2516C | exact |
| 873 | Chaos Greed | Spell | NONE | 0 | 0 | 0 | ROM 0xF25170 | exact |
| 874 | D. D. Borderline | Spell | NONE | 0 | 0 | 0 | ROM 0xF25174 | exact |
| 875 | Recycle | Spell | NONE | 0 | 0 | 0 | ROM 0xF25178 | exact |
| 876 | Primal Seed | Spell | NONE | 0 | 0 | 0 | ROM 0xF2517C | exact |
| 877 | Thunder Crash | Spell | NONE | 0 | 0 | 0 | ROM 0xF25180 | exact |
| 878 | Dimension Distortion | Spell | NONE | 0 | 0 | 0 | ROM 0xF25184 | exact |
| 879 | Reload | Spell | NONE | 0 | 0 | 0 | ROM 0xF25188 | exact |
| 880 | Soul Absorption | Spell | NONE | 0 | 0 | 0 | ROM 0xF2518C | exact |
| 881 | Blasting the Ruins | Trap | NONE | 0 | 0 | 0 | ROM 0xF25190 | exact |
| 882 | Tower of Babel | Trap | NONE | 0 | 0 | 0 | ROM 0xF25194 | exact |
| 883 | Chain Disappearance | Trap | NONE | 0 | 0 | 0 | ROM 0xF25198 | exact |
| 884 | Zero Gravity | Trap | NONE | 0 | 0 | 0 | ROM 0xF2519C | exact |
| 885 | Dark Mirror Force | Trap | NONE | 0 | 0 | 0 | ROM 0xF251A0 | exact |
| 886 | Chaos Emperor Dragon - Envoy of the End | Effect Monster | DARK | 8 | 3000 | 2500 | ROM 0xF251A4 | exact |
| 887 | Giga Gagagigo | Normal Monster | WATER | 5 | 2450 | 1500 | ROM 0xF251A8 | exact |
| 888 | Mad Dog of Darkness | Normal Monster | DARK | 4 | 1900 | 1400 | ROM 0xF251AC | exact |
| 889 | Neo Bug | Normal Monster | EARTH | 4 | 1800 | 1700 | ROM 0xF251B0 | exact |
| 890 | Sea Serpent Warrior of Darkness | Normal Monster | WATER | 4 | 1800 | 1500 | ROM 0xF251B4 | exact |
| 891 | Terrorking Salmon | Normal Monster | WATER | 5 | 2400 | 1000 | ROM 0xF251B8 | exact |
| 892 | Blazing Inpachi | Normal Monster | FIRE | 4 | 1850 | 0 | ROM 0xF251BC | exact |
| 893 | Burning Algae | Effect Monster | FIRE | 3 | 500 | 1500 | ROM 0xF251C0 | exact |
| 894 | The Thing in the Crater | Effect Monster | FIRE | 4 | 1000 | 1200 | ROM 0xF251C4 | exact |
| 895 | Molten Zombie | Effect Monster | FIRE | 4 | 1600 | 400 | ROM 0xF251C8 | exact |
| 896 | Dark Magician of Chaos | Effect Monster | DARK | 8 | 2800 | 2600 | ROM 0xF251CC | exact |
| 897 | Stealth Bird | Effect Monster | DARK | 3 | 700 | 1700 | ROM 0xF251D0 | exact |
| 898 | Sacred Crane | Effect Monster | LIGHT | 4 | 1600 | 400 | ROM 0xF251D4 | exact |
| 899 | Enraged Battle Ox | Effect Monster | EARTH | 4 | 1700 | 1000 | ROM 0xF251D8 | exact |
| 900 | Don Turtle | Effect Monster | WATER | 3 | 1100 | 1200 | ROM 0xF251DC | exact |
| 901 | Balloon Lizard | Effect Monster | EARTH | 4 | 500 | 1900 | ROM 0xF251E0 | exact |
| 902 | Dark Driceratops | Effect Monster | EARTH | 6 | 2400 | 1500 | ROM 0xF251E4 | exact |
| 903 | Black Tyranno | Effect Monster | EARTH | 7 | 2600 | 1800 | ROM 0xF251E8 | exact |
| 904 | Anti-Aircraft Flower | Effect Monster | EARTH | 3 | 0 | 1600 | ROM 0xF251EC | exact |
| 905 | Amphibious Bugroth MK-3 | Effect Monster | WATER | 4 | 1500 | 1300 | ROM 0xF251F0 | exact |
| 906 | Levia-Dragon - Daedalus | Effect Monster | WATER | 7 | 2600 | 1500 | ROM 0xF251F4 | exact |
| 907 | Mataza the Zapper | Effect Monster | DARK | 3 | 1300 | 800 | ROM 0xF251F8 | exact |
| 908 | Guardian Angel Joan | Effect Monster | LIGHT | 7 | 2800 | 2000 | ROM 0xF251FC | exact |
| 909 | Manju of the Ten Thousand Hands | Effect Monster | LIGHT | 4 | 1400 | 1000 | ROM 0xF25200 | exact |
| 910 | Getsu Fuhma | Effect Monster | DARK | 4 | 1700 | 1200 | ROM 0xF25204 | exact |
| 911 | Ryu Kokki | Effect Monster | DARK | 6 | 2400 | 2000 | ROM 0xF25208 | exact |
| 912 | Gryphon's Feather Duster | Spell | NONE | 0 | 0 | 0 | ROM 0xF2520C | exact |
| 913 | Stray Lambs | Spell | NONE | 0 | 0 | 0 | ROM 0xF25210 | exact |
| 914 | Smashing Ground | Spell | NONE | 0 | 0 | 0 | ROM 0xF25214 | exact |
| 915 | Dedication through Light and Darkness | Spell | NONE | 0 | 0 | 0 | ROM 0xF25218 | exact |
| 916 | Salvage | Spell | NONE | 0 | 0 | 0 | ROM 0xF2521C | exact |
| 917 | Ultra Evolution Pill | Spell | NONE | 0 | 0 | 0 | ROM 0xF25220 | exact |
| 918 | Earth Chant | Spell | NONE | 0 | 0 | 0 | ROM 0xF25224 | exact |
| 919 | Destruction Ring | Trap | NONE | 0 | 0 | 0 | ROM 0xF25228 | exact |
| 920 | Compulsory Evacuation Device | Trap | NONE | 0 | 0 | 0 | ROM 0xF2522C | exact |
| 921 | A Hero Emerges | Trap | NONE | 0 | 0 | 0 | ROM 0xF25230 | exact |
| 922 | Self-Destruct Button | Trap | NONE | 0 | 0 | 0 | ROM 0xF25234 | exact |
| 923 | Curse of Darkness | Trap | NONE | 0 | 0 | 0 | ROM 0xF25238 | exact |
| 924 | Begone, Knave! | Trap | NONE | 0 | 0 | 0 | ROM 0xF2523C | exact |
| 925 | DNA Transplant | Trap | NONE | 0 | 0 | 0 | ROM 0xF25240 | exact |
| 926 | Robbin' Zombie | Trap | NONE | 0 | 0 | 0 | ROM 0xF25244 | exact |
| 927 | Trap Jammer | Trap | NONE | 0 | 0 | 0 | ROM 0xF25248 | exact |
| 928 | Invader of Darkness | Effect Monster | DARK | 8 | 2900 | 2500 | ROM 0xF2524C | exact |
| 929 | Inferno Hammer | Effect Monster | DARK | 6 | 2400 | 0 | ROM 0xF25250 | exact |
| 930 | Emes the Infinity | Effect Monster | LIGHT | 7 | 2500 | 2000 | ROM 0xF25254 | exact |
| 931 | D. D. Assailant | Effect Monster | EARTH | 4 | 1700 | 1600 | ROM 0xF25258 | exact |
| 932 | Dangerous Machine TYPE-6 | Spell | NONE | 0 | 0 | 0 | ROM 0xF2525C | exact |
| 933 | Gogiga Gagagigo | Normal Monster | WATER | 8 | 2950 | 2800 | ROM 0xF25260 | exact |
| 934 | Warrior of Zera | Normal Monster | EARTH | 4 | 1600 | 1600 | ROM 0xF25264 | exact |
| 935 | Sealmaster Meisei | Normal Monster | DARK | 3 | 1100 | 900 | ROM 0xF25268 | exact |
| 936 | Mystical Shine Ball | Normal Monster | LIGHT | 2 | 500 | 500 | ROM 0xF2526C | exact |
| 937 | Metal Armored Bug | Normal Monster | EARTH | 8 | 2800 | 1500 | ROM 0xF25270 | exact |
| 938 | KA-2 Des Scissors | Effect Monster | DARK | 4 | 1000 | 1000 | ROM 0xF25274 | exact |
| 939 | Needle Burrower | Effect Monster | DARK | 5 | 1700 | 1700 | ROM 0xF25278 | exact |
| 940 | Blowback Dragon | Effect Monster | DARK | 6 | 2300 | 1200 | ROM 0xF2527C | exact |
| 941 | Zaborg the Thunder Monarch | Effect Monster | LIGHT | 5 | 2400 | 1000 | ROM 0xF25280 | exact |
| 942 | Atomic Firefly | Effect Monster | LIGHT | 1 | 100 | 200 | ROM 0xF25284 | exact |
| 943 | Mermaid Knight | Effect Monster | WATER | 4 | 1500 | 700 | ROM 0xF25288 | exact |
| 944 | Piranha Army | Effect Monster | WATER | 2 | 800 | 200 | ROM 0xF2528C | exact |
| 945 | Two Thousand Needles | Effect Monster | EARTH | 5 | 2000 | 1800 | ROM 0xF25290 | exact |
| 946 | Disc Fighter | Effect Monster | EARTH | 4 | 1000 | 1000 | ROM 0xF25294 | exact |
| 947 | Lady Ninja Yae | Effect Monster | WIND | 3 | 1100 | 200 | ROM 0xF25298 | exact |
| 948 | White Magician Pikeru | Effect Monster | LIGHT | 2 | 1200 | 0 | ROM 0xF2529C | exact |
| 949 | Archlord Zerato | Effect Monster | LIGHT | 8 | 2800 | 2300 | ROM 0xF252A0 | exact |
| 950 | Mystik Wok | Spell | NONE | 0 | 0 | 0 | ROM 0xF252A4 | exact |
| 951 | Burst Stream of Destruction | Spell | NONE | 0 | 0 | 0 | ROM 0xF252A8 | exact |
| 952 | Monster Gate | Spell | NONE | 0 | 0 | 0 | ROM 0xF252AC | exact |
| 953 | The Sanctuary in the Sky | Spell | NONE | 0 | 0 | 0 | ROM 0xF252B0 | exact |
| 954 | Earthquake | Spell | NONE | 0 | 0 | 0 | ROM 0xF252B4 | exact |
| 955 | Goblin Thief | Spell | NONE | 0 | 0 | 0 | ROM 0xF252B8 | exact |
| 956 | Backfire | Trap | NONE | 0 | 0 | 0 | ROM 0xF252BC | exact |
| 957 | Light of Judgment | Trap | NONE | 0 | 0 | 0 | ROM 0xF252C0 | exact |
| 958 | Solar Ray | Trap | NONE | 0 | 0 | 0 | ROM 0xF252C4 | exact |
| 959 | Ninjitsu Art of Transformation | Trap | NONE | 0 | 0 | 0 | ROM 0xF252C8 | exact |
| 960 | Beckoning Light | Trap | NONE | 0 | 0 | 0 | ROM 0xF252CC | exact |
| 961 | Draining Shield | Trap | NONE | 0 | 0 | 0 | ROM 0xF252D0 | exact |
| 962 | Armor Break | Trap | NONE | 0 | 0 | 0 | ROM 0xF252D4 | exact |
| 963 | Marshmallon | Effect Monster | LIGHT | 3 | 300 | 500 | ROM 0xF252D8 | exact |
| 964 | Shield Crash | Spell | NONE | 0 | 0 | 0 | ROM 0xF252DC | exact |
| 965 | Return Zombie | Effect Monster | DARK | 4 | 1000 | 1600 | ROM 0xF252E0 | exact |
| 966 | Corpse of Yata-Garasu | Trap | NONE | 0 | 0 | 0 | ROM 0xF252E4 | exact |
| 967 | Mokey Mokey | Normal Monster | LIGHT | 1 | 300 | 100 | ROM 0xF252E8 | exact |
| 968 | Gigobyte | Normal Monster | WATER | 1 | 350 | 300 | ROM 0xF252EC | exact |
| 969 | Kozaky | Normal Monster | DARK | 1 | 400 | 400 | ROM 0xF252F0 | exact |
| 970 | Fiend Scorpion | Normal Monster | EARTH | 2 | 900 | 200 | ROM 0xF252F4 | exact |
| 971 | Pharaoh's Servant | Normal Monster | DARK | 2 | 900 | 0 | ROM 0xF252F8 | exact |
| 972 | Pharaonic Protector | Normal Monster | EARTH | 2 | 900 | 0 | ROM 0xF252FC | exact |
| 973 | Spirit of the Pharaoh | Effect Monster | LIGHT | 6 | 2500 | 2000 | ROM 0xF25300 | exact |
| 974 | Theban Nightmare | Effect Monster | LIGHT | 4 | 1500 | 500 | ROM 0xF25304 | exact |
| 975 | Aswan Apparition | Effect Monster | DARK | 3 | 500 | 500 | ROM 0xF25308 | exact |
| 976 | Protector of the Sanctuary | Effect Monster | EARTH | 4 | 1100 | 1900 | ROM 0xF2530C | exact |
| 977 | Nubian Guard | Effect Monster | FIRE | 2 | 500 | 500 | ROM 0xF25310 | exact |
| 978 | Desertapir | Effect Monster | EARTH | 3 | 900 | 300 | ROM 0xF25314 | exact |
| 979 | Sand Gambler | Effect Monster | LIGHT | 3 | 300 | 1600 | ROM 0xF25318 | exact |
| 980 | Absorbing Kid from the Sky | Effect Monster | LIGHT | 4 | 1300 | 1000 | ROM 0xF2531C | exact |
| 981 | Spirit Caller | Effect Monster | LIGHT | 3 | 1000 | 1000 | ROM 0xF25320 | exact |
| 982 | Man-Thro' Tro' | Effect Monster | EARTH | 4 | 1000 | 1000 | ROM 0xF25324 | exact |
| 983 | Special Hurricane | Spell | NONE | 0 | 0 | 0 | ROM 0xF25328 | exact |
| 984 | Order to Charge | Spell | NONE | 0 | 0 | 0 | ROM 0xF2532C | exact |
| 985 | Soul Reversal | Spell | NONE | 0 | 0 | 0 | ROM 0xF25330 | exact |
| 986 | 7 | Spell | NONE | 0 | 0 | 0 | ROM 0xF25334 | exact |
| 987 | The Law of the Normal | Spell | NONE | 0 | 0 | 0 | ROM 0xF25338 | exact |
| 988 | Dark Magic Attack | Spell | NONE | 0 | 0 | 0 | ROM 0xF2533C | exact |
| 989 | The Third Sarcophagus | Spell | NONE | 0 | 0 | 0 | ROM 0xF25340 | exact |
| 990 | The Second Sarcophagus | Spell | NONE | 0 | 0 | 0 | ROM 0xF25344 | exact |
| 991 | The First Sarcophagus | Trap | NONE | 0 | 0 | 0 | ROM 0xF25348 | exact |
| 992 | Desert Sunlight | Trap | NONE | 0 | 0 | 0 | ROM 0xF2534C | exact |
| 993 | Des Counterblow | Trap | NONE | 0 | 0 | 0 | ROM 0xF25350 | exact |
| 994 | Labyrinth of Nightmare | Trap | NONE | 0 | 0 | 0 | ROM 0xF25354 | exact |
| 995 | Soul Resurrection | Trap | NONE | 0 | 0 | 0 | ROM 0xF25358 | exact |
| 996 | Pyramid of Light | Trap | NONE | 0 | 0 | 0 | ROM 0xF2535C | exact |
| 997 | Rare Metal Dragon | Effect Monster | DARK | 4 | 2400 | 1200 | ROM 0xF25360 | exact |
| 998 | Peten the Dark Clown | Effect Monster | DARK | 3 | 500 | 1200 | ROM 0xF25364 | exact |
| 999 | Andro Sphinx | Effect Monster | LIGHT | 10 | 3000 | 2500 | ROM 0xF25368 | exact |
| 1000 | Sphinx Teleia | Effect Monster | LIGHT | 10 | 2500 | 3000 | ROM 0xF2536C | exact |
| 1001 | Theinen the Great Sphinx | Effect Monster | LIGHT | 10 | 3500 | 3000 | ROM 0xF25370 | exact |
| 1002 | Inferno Tempest | Spell | NONE | 0 | 0 | 0 | ROM 0xF25374 | exact |
| 1003 | Charcoal Inpachi | Normal Monster | FIRE | 1 | 100 | 2100 | ROM 0xF25378 | exact |
| 1004 | Neo Aqua Madoor | Normal Monster | WATER | 6 | 1200 | 3000 | ROM 0xF2537C | exact |
| 1005 | Skull Dog Marron | Normal Monster | EARTH | 4 | 1350 | 2000 | ROM 0xF25380 | exact |
| 1006 | Goblin Calligrapher | Normal Monster | DARK | 1 | 400 | 400 | ROM 0xF25384 | exact |
| 1007 | Red-Eyes B. Chick | Effect Monster | DARK | 1 | 800 | 500 | ROM 0xF25388 | exact |
| 1008 | Ninja Grandmaster Sasuke | Effect Monster | LIGHT | 4 | 1800 | 1000 | ROM 0xF2538C | exact |
| 1009 | Ultimate Baseball Kid | Effect Monster | FIRE | 3 | 500 | 1000 | ROM 0xF25390 | exact |
| 1010 | Mobius the Frost Monarch | Effect Monster | WATER | 6 | 2400 | 1000 | ROM 0xF25394 | exact |
| 1011 | Element Dragon | Effect Monster | LIGHT | 4 | 1500 | 1200 | ROM 0xF25398 | exact |
| 1012 | Howling Insect | Effect Monster | EARTH | 3 | 1200 | 1300 | ROM 0xF2539C | exact |
| 1013 | Masked Dragon | Effect Monster | FIRE | 3 | 1400 | 1100 | ROM 0xF253A0 | exact |
| 1014 | Mind on Air | Effect Monster | DARK | 6 | 1000 | 1600 | ROM 0xF253A4 | exact |
| 1015 | Enraged Muka Muka | Effect Monster | EARTH | 5 | 1200 | 600 | ROM 0xF253A8 | exact |
| 1016 | Hade-Hane | Effect Monster | EARTH | 5 | 900 | 1000 | ROM 0xF253AC | exact |
| 1017 | Penumbral Soldier Lady | Effect Monster | DARK | 6 | 2100 | 1400 | ROM 0xF253B0 | exact |
| 1018 | Ojama King | Fusion Monster | LIGHT | 6 | 0 | 3000 | ROM 0xF253B4 | exact |
| 1019 | Master of Oz | Fusion Monster | EARTH | 9 | 4200 | 3700 | ROM 0xF253B8 | exact |
| 1020 | Sanwitch | Fusion Monster | DARK | 6 | 2100 | 1800 | ROM 0xF253BC | exact |
| 1021 | Dark Factory of Mass Production | Spell | NONE | 0 | 0 | 0 | ROM 0xF253C0 | exact |
| 1022 | Hammer Shot | Spell | NONE | 0 | 0 | 0 | ROM 0xF253C4 | exact |
| 1023 | Mind Wipe | Spell | NONE | 0 | 0 | 0 | ROM 0xF253C8 | exact |
| 1024 | Inferno Fire Blast | Spell | NONE | 0 | 0 | 0 | ROM 0xF253CC | exact |
| 1025 | Fusion Weapon | Spell | NONE | 0 | 0 | 0 | ROM 0xF253D0 | exact |
| 1026 | Ritual Weapon | Spell | NONE | 0 | 0 | 0 | ROM 0xF253D4 | exact |
| 1027 | Spirit Barrier | Trap | NONE | 0 | 0 | 0 | ROM 0xF253D8 | exact |
| 1028 | Ninjitsu Art of Decoy | Trap | NONE | 0 | 0 | 0 | ROM 0xF253DC | exact |
| 1029 | Heavy Slump | Trap | NONE | 0 | 0 | 0 | ROM 0xF253E0 | exact |
| 1030 | Cemetary Bomb | Trap | NONE | 0 | 0 | 0 | ROM 0xF253E4 | exact |
| 1031 | Tricky | Effect Monster | WIND | 5 | 2000 | 1200 | ROM 0xF253E8 | exact |
| 1032 | Green Gadget | Effect Monster | EARTH | 4 | 1400 | 600 | ROM 0xF253EC | exact |
| 1033 | Red Gadget - Stronghold | Trap | NONE | 0 | 0 | 0 | ROM 0xF253F0 | exact |
| 1034 | Red Gadget | Effect Monster | EARTH | 4 | 1300 | 1500 | ROM 0xF253F4 | exact |
| 1035 | Yellow Gadget | Effect Monster | EARTH | 4 | 1200 | 1200 | ROM 0xF253F8 | exact |
| 1036 | Tricky's Magic 4 | Spell | NONE | 0 | 0 | 0 | ROM 0xF253FC | exact |
| 1037 | Woodborg Inpachi | Normal Monster | FIRE | 5 | 500 | 2500 | ROM 0xF25400 | exact |
| 1038 | Mighty Guard | Normal Monster | EARTH | 4 | 500 | 1200 | ROM 0xF25404 | exact |
| 1039 | Bokoichi the Freightening Car | Normal Monster | DARK | 2 | 500 | 500 | ROM 0xF25408 | exact |
| 1040 | Harpie Girl | Normal Monster | WIND | 2 | 500 | 500 | ROM 0xF2540C | exact |
| 1041 | The Creator | Effect Monster | LIGHT | 8 | 2300 | 3000 | ROM 0xF25410 | exact |
| 1042 | The Creator Incarnate | Effect Monster | LIGHT | 4 | 1600 | 1500 | ROM 0xF25414 | exact |
| 1043 | Roc from the Valley of Haze | Effect Monster | WIND | 6 | 2400 | 1400 | ROM 0xF25418 | exact |
| 1044 | Sasuke Samurai #4 | Effect Monster | WIND | 4 | 1200 | 1200 | ROM 0xF2541C | exact |
| 1045 | Harpie Lady 1 | Effect Monster | WIND | 4 | 1300 | 1400 | ROM 0xF25420 | exact |
| 1046 | Harpie Lady 2 | Effect Monster | WIND | 4 | 1300 | 1400 | ROM 0xF25424 | exact |
| 1047 | Harpie Lady 3 | Effect Monster | WIND | 4 | 1300 | 1400 | ROM 0xF25428 | exact |
| 1048 | Raging Flame Sprite | Effect Monster | FIRE | 3 | 100 | 200 | ROM 0xF2542C | exact |
| 1049 | Thestalos the Firestorm Monarch | Effect Monster | FIRE | 6 | 2400 | 1000 | ROM 0xF25430 | exact |
| 1050 | Eagle Eye | Effect Monster | WIND | 3 | 1300 | 1200 | ROM 0xF25434 | exact |
| 1051 | Tactical Espionage Expert | Effect Monster | EARTH | 3 | 1300 | 1200 | ROM 0xF25438 | exact |
| 1052 | Invasion of Flames | Effect Monster | FIRE | 3 | 1300 | 1200 | ROM 0xF2543C | exact |
| 1053 | Creeping Doom Manta | Effect Monster | WATER | 3 | 1300 | 1200 | ROM 0xF25440 | exact |
| 1054 | Pitch-Black Warwolf | Effect Monster | DARK | 4 | 1600 | 600 | ROM 0xF25444 | exact |
| 1055 | Mirage Dragon | Effect Monster | LIGHT | 4 | 1600 | 600 | ROM 0xF25448 | exact |
| 1056 | Big Core | Effect Monster | DARK | 6 | 2300 | 1100 | ROM 0xF2544C | exact |
| 1057 | Dekoichi the Battlechanted Locomotive | Effect Monster | DARK | 4 | 1400 | 1000 | ROM 0xF25450 | exact |
| 1058 | A-Team: Trap Disposal Unit | Effect Monster | FIRE | 2 | 300 | 400 | ROM 0xF25454 | exact |
| 1059 | Homunculus the Alchemic Being | Effect Monster | LIGHT | 4 | 1800 | 1600 | ROM 0xF25458 | exact |
| 1060 | Dark Blade the Dragon Knight | Fusion Monster | DARK | 6 | 2200 | 1500 | ROM 0xF2545C | exact |
| 1061 | Mokey Mokey King | Fusion Monster | LIGHT | 6 | 300 | 100 | ROM 0xF25460 | exact |
| 1062 | Harpies' Hunting Ground | Spell | NONE | 0 | 0 | 0 | ROM 0xF25464 | exact |
| 1063 | Mokey Mokey Smackdown | Spell | NONE | 0 | 0 | 0 | ROM 0xF25468 | exact |
| 1064 | Back to Square One | Spell | NONE | 0 | 0 | 0 | ROM 0xF2546C | exact |
| 1065 | Monster Reincarnation | Spell | NONE | 0 | 0 | 0 | ROM 0xF25470 | exact |
| 1066 | Malice Dispersion | Spell | NONE | 0 | 0 | 0 | ROM 0xF25474 | exact |
| 1067 | Divine Wrath | Trap | NONE | 0 | 0 | 0 | ROM 0xF25478 | exact |
| 1068 | Fruits of Kozaky's Studies | Trap | NONE | 0 | 0 | 0 | ROM 0xF2547C | exact |
| 1069 | Fuh-Rin-Ka-Zan | Trap | NONE | 0 | 0 | 0 | ROM 0xF25480 | exact |
| 1070 | Chain Burst | Trap | NONE | 0 | 0 | 0 | ROM 0xF25484 | exact |
| 1071 | Spell Purification | Trap | NONE | 0 | 0 | 0 | ROM 0xF25488 | exact |
| 1072 | Castle Gate | Effect Monster | EARTH | 6 | 0 | 2400 | ROM 0xF2548C | exact |
| 1073 | Space Mambo | Normal Monster | WATER | 4 | 1700 | 1000 | ROM 0xF25490 | exact |
| 1074 | Divine Dragon Ragnarok | Normal Monster | LIGHT | 4 | 1500 | 1000 | ROM 0xF25494 | exact |
| 1075 | Chu-Ske the Mouse Fighter | Normal Monster | EARTH | 3 | 1200 | 0 | ROM 0xF25498 | exact |
| 1076 | Insect Knight | Normal Monster | EARTH | 4 | 1900 | 1500 | ROM 0xF2549C | exact |
| 1077 | Granmarg the Rock Monarch | Effect Monster | EARTH | 6 | 2400 | 1000 | ROM 0xF254A0 | exact |
| 1078 | Maji-Gire Panda | Effect Monster | EARTH | 4 | 1000 | 800 | ROM 0xF254A4 | exact |
| 1079 | Kangaroo Champ | Effect Monster | EARTH | 4 | 800 | 700 | ROM 0xF254A8 | exact |
| 1080 | Hyena | Effect Monster | EARTH | 3 | 1000 | 300 | ROM 0xF254AC | exact |
| 1081 | Blade Rabbit | Effect Monster | EARTH | 2 | 400 | 300 | ROM 0xF254B0 | exact |
| 1082 | Mecha-Dog Marron | Effect Monster | LIGHT | 4 | 1000 | 1000 | ROM 0xF254B4 | exact |
| 1083 | Blast Magician | Effect Monster | FIRE | 4 | 1400 | 1700 | ROM 0xF254B8 | exact |
| 1084 | Gearfried the Swordmaster | Effect Monster | LIGHT | 7 | 2600 | 2200 | ROM 0xF254BC | exact |
| 1085 | Shadowslayer | Effect Monster | DARK | 4 | 1400 | 200 | ROM 0xF254C0 | exact |
| 1086 | Golem Sentry | Effect Monster | EARTH | 4 | 800 | 1800 | ROM 0xF254C4 | exact |
| 1087 | Abare Ushioni | Effect Monster | EARTH | 4 | 1200 | 1200 | ROM 0xF254C8 | exact |
| 1088 | Gatling Dragon | Fusion Monster | DARK | 8 | 2600 | 1200 | ROM 0xF254CC | exact |
| 1089 | A Feather of the Phoenix | Spell | NONE | 0 | 0 | 0 | ROM 0xF254D0 | exact |
| 1090 | Poison Fangs | Spell | NONE | 0 | 0 | 0 | ROM 0xF254D4 | exact |
| 1091 | Spiral Spear Strike | Spell | NONE | 0 | 0 | 0 | ROM 0xF254D8 | exact |
| 1092 | Release Restraint | Spell | NONE | 0 | 0 | 0 | ROM 0xF254DC | exact |
| 1093 | Fulfillment of the Contract | Spell | NONE | 0 | 0 | 0 | ROM 0xF254E0 | exact |
| 1094 | Re-Fusion | Spell | NONE | 0 | 0 | 0 | ROM 0xF254E4 | exact |
| 1095 | The Big March of Animals | Spell | NONE | 0 | 0 | 0 | ROM 0xF254E8 | exact |
| 1096 | Threatening Roar | Trap | NONE | 0 | 0 | 0 | ROM 0xF254EC | exact |
| 1097 | Phoenix Wing Wind Blast | Trap | NONE | 0 | 0 | 0 | ROM 0xF254F0 | exact |
| 1098 | Good Goblin Housekeeping | Trap | NONE | 0 | 0 | 0 | ROM 0xF254F4 | exact |
| 1099 | Assault on GHQ | Trap | NONE | 0 | 0 | 0 | ROM 0xF254F8 | exact |
| 1100 | D.D. Dynamite | Trap | NONE | 0 | 0 | 0 | ROM 0xF254FC | exact |
| 1101 | Elemental Burst | Trap | NONE | 0 | 0 | 0 | ROM 0xF25500 | exact |
| 1102 | Blood Sucker | Effect Monster | DARK | 4 | 1300 | 1500 | ROM 0xF25504 | exact |
| 1103 | Overpowering Eye | Spell | NONE | 0 | 0 | 0 | ROM 0xF25508 | exact |
| 1104 | Red-Eyes Darkness Dragon | Effect Monster | DARK | 9 | 2400 | 2000 | ROM 0xF2550C | exact |
| 1105 | Kaibaman | Effect Monster | LIGHT | 3 | 200 | 700 | ROM 0xF25510 | exact |
| 1106 | Elemental Hero Avian | Normal Monster | WIND | 3 | 1000 | 1000 | ROM 0xF25514 | exact |
| 1107 | Elemental Hero Burstinatrix | Normal Monster | FIRE | 3 | 1200 | 800 | ROM 0xF25518 | exact |
| 1108 | Elemental Hero Clayman | Normal Monster | EARTH | 4 | 800 | 2000 | ROM 0xF2551C | exact |
| 1109 | Elemental Hero Sparkman | Normal Monster | LIGHT | 4 | 1600 | 1400 | ROM 0xF25520 | exact |
| 1110 | Winged Kuriboh | Effect Monster | LIGHT | 1 | 300 | 200 | ROM 0xF25524 | exact |
| 1111 | Ancient Gear Golem | Effect Monster | EARTH | 8 | 3000 | 3000 | ROM 0xF25528 | exact |
| 1112 | Ancient Gear Beast | Effect Monster | EARTH | 6 | 2000 | 2000 | ROM 0xF2552C | exact |
| 1113 | Ancient Gear Soldier | Effect Monster | EARTH | 4 | 1300 | 1300 | ROM 0xF25530 | exact |
| 1114 | Millennium Scorpion | Effect Monster | EARTH | 5 | 2000 | 1800 | ROM 0xF25534 | exact |
| 1115 | Lost Guardian | Effect Monster | EARTH | 4 | 100 | 0 | ROM 0xF25538 | exact |
| 1116 | Moai Interceptor Cannons | Effect Monster | EARTH | 4 | 1100 | 2000 | ROM 0xF2553C | exact |
| 1117 | Megarock Dragon | Effect Monster | EARTH | 7 | 0 | 0 | ROM 0xF25540 | exact |
| 1118 | Mine Golem | Effect Monster | EARTH | 3 | 1000 | 1900 | ROM 0xF25544 | exact |
| 1119 | Monk Fighter | Effect Monster | EARTH | 3 | 1300 | 1000 | ROM 0xF25548 | exact |
| 1120 | Master Monk | Effect Monster | EARTH | 5 | 1900 | 1000 | ROM 0xF2554C | exact |
| 1121 | Guardian Statue | Effect Monster | EARTH | 4 | 800 | 1400 | ROM 0xF25550 | exact |
| 1122 | Medusa Worm | Effect Monster | EARTH | 2 | 500 | 600 | ROM 0xF25554 | exact |
| 1123 | White Ninja | Effect Monster | LIGHT | 4 | 1500 | 800 | ROM 0xF25558 | exact |
| 1124 | Batteryman AA | Effect Monster | LIGHT | 3 | 0 | 0 | ROM 0xF2555C | exact |
| 1125 | Des Wombat | Effect Monster | EARTH | 3 | 1600 | 300 | ROM 0xF25560 | exact |
| 1126 | King of the Skull Servants | Effect Monster | DARK | 1 | 0 | 0 | ROM 0xF25564 | exact |
| 1127 | Reshef the Dark Being | Ritual Monster | LIGHT | 8 | 2500 | 1500 | ROM 0xF25568 | exact |
| 1128 | Elemental Mistress Doriado | Ritual Monster | LIGHT | 3 | 1200 | 1400 | ROM 0xF2556C | exact |
| 1129 | Elemental Hero Flame Wingman | Fusion Monster | WIND | 6 | 2100 | 1200 | ROM 0xF25570 | exact |
| 1130 | Elemental Hero Thunder Giant | Fusion Monster | LIGHT | 6 | 2400 | 1500 | ROM 0xF25574 | exact |
| 1131 | Battery Charger | Spell | NONE | 0 | 0 | 0 | ROM 0xF25578 | exact |
| 1132 | Kaminote Blow | Spell | NONE | 0 | 0 | 0 | ROM 0xF2557C | exact |
| 1133 | Doriado's Blessing | Spell | NONE | 0 | 0 | 0 | ROM 0xF25580 | exact |
| 1134 | Final Ritual of the Ancients | Spell | NONE | 0 | 0 | 0 | ROM 0xF25584 | exact |
| 1135 | Legendary Black Belt | Spell | NONE | 0 | 0 | 0 | ROM 0xF25588 | exact |
| 1136 | Hero Signal | Trap | NONE | 0 | 0 | 0 | ROM 0xF2558C | exact |
| 1137 | Minefield Eruption | Trap | NONE | 0 | 0 | 0 | ROM 0xF25590 | exact |
| 1138 | Kozaky's Self-Destruct Button | Trap | NONE | 0 | 0 | 0 | ROM 0xF25594 | exact |
| 1139 | Mispolymerization | Trap | NONE | 0 | 0 | 0 | ROM 0xF25598 | exact |
| 1140 | Rock Bombardment | Trap | NONE | 0 | 0 | 0 | ROM 0xF2559C | exact |
| 1141 | Token Feastevil | Trap | NONE | 0 | 0 | 0 | ROM 0xF255A0 | exact |
| 1142 | Spell-Stopping Statute | Trap | NONE | 0 | 0 | 0 | ROM 0xF255A4 | exact |
| 1143 | Royal Surrender | Trap | NONE | 0 | 0 | 0 | ROM 0xF255A8 | exact |
| 1144 | Holy Knight Ishzark | Effect Monster | LIGHT | 6 | 2300 | 1800 | ROM 0xF255AC | exact |
| 1145 | Ocean Dragon Lord - Neo-Daedalus | Effect Monster | WATER | 8 | 2900 | 1600 | ROM 0xF255B0 | exact |
| 1146 | Cycroid | Normal Monster | EARTH | 3 | 800 | 1000 | ROM 0xF255B4 | exact |
| 1147 | Patroid | Effect Monster | EARTH | 4 | 1200 | 1200 | ROM 0xF255B8 | exact |
| 1148 | Gyroid | Effect Monster | WIND | 3 | 1000 | 1000 | ROM 0xF255BC | exact |
| 1149 | Steamroid | Effect Monster | EARTH | 4 | 1800 | 1800 | ROM 0xF255C0 | exact |
| 1150 | Drillroid | Effect Monster | EARTH | 4 | 1600 | 1600 | ROM 0xF255C4 | exact |
| 1151 | UFOroid | Effect Monster | LIGHT | 6 | 1200 | 1200 | ROM 0xF255C8 | exact |
| 1152 | Cyber Dragon | Effect Monster | LIGHT | 5 | 2100 | 1600 | ROM 0xF255CC | exact |
| 1153 | Wroughtweiler | Effect Monster | EARTH | 3 | 800 | 1200 | ROM 0xF255D0 | exact |
| 1154 | Elemental Hero Bubbleman | Effect Monster | WATER | 4 | 800 | 1200 | ROM 0xF255D4 | exact |
| 1155 | Steam Gyroid | Fusion Monster | EARTH | 6 | 2200 | 1600 | ROM 0xF255D8 | exact |
| 1156 | UFOroid Fighter | Fusion Monster | LIGHT | 10 | 0 | 0 | ROM 0xF255DC | exact |
| 1157 | Cyber Twin Dragon | Fusion Monster | LIGHT | 8 | 2800 | 2100 | ROM 0xF255E0 | exact |
| 1158 | Cyber End Dragon | Fusion Monster | LIGHT | 10 | 4000 | 2800 | ROM 0xF255E4 | exact |
| 1159 | Power Bond | Spell | NONE | 0 | 0 | 0 | ROM 0xF255E8 | exact |
| 1160 | Skyscraper | Spell | NONE | 0 | 0 | 0 | ROM 0xF255EC | exact |
| 1161 | Winged Kuriboh LV10 | Effect Monster | LIGHT | 10 | 300 | 200 | ROM 0xF255F0 | exact |
| 1162 | Transcendent Wings | Spell | NONE | 0 | 0 | 0 | ROM 0xF255F4 | exact |
| 1163 | Bubble Shuffle | Spell | NONE | 0 | 0 | 0 | ROM 0xF255F8 | exact |
| 1164 | Spark Gun | Spell | NONE | 0 | 0 | 0 | ROM 0xF255FC | exact |
| 1165 | Soitsu | Normal Monster | WIND | 3 | 0 | 0 | ROM 0xF25600 | exact |
| 1166 | Mad Lobster | Normal Monster | WATER | 3 | 1700 | 1000 | ROM 0xF25604 | exact |
| 1167 | Jerry Beans Man | Normal Monster | EARTH | 3 | 1750 | 0 | ROM 0xF25608 | exact |
| 1168 | Cybernetic Cyclopean | Effect Monster | EARTH | 4 | 1400 | 200 | ROM 0xF2560C | exact |
| 1169 | Mechanical Hound | Effect Monster | EARTH | 7 | 2800 | 1500 | ROM 0xF25610 | exact |
| 1170 | Goblin Elite Attack Force | Effect Monster | EARTH | 4 | 2200 | 1500 | ROM 0xF25614 | exact |
| 1171 | B.E.S. Crystal Core | Effect Monster | WATER | 5 | 2100 | 1000 | ROM 0xF25618 | exact |
| 1172 | Giant Kozaky | Effect Monster | DARK | 4 | 2500 | 2400 | ROM 0xF2561C | exact |
| 1173 | Indomitable Fighter Lei Lei | Effect Monster | EARTH | 4 | 2300 | 0 | ROM 0xF25620 | exact |
| 1174 | Protective Soul Ailin | Effect Monster | LIGHT | 1 | 0 | 0 | ROM 0xF25624 | exact |
| 1175 | Doitsu | Effect Monster | EARTH | 4 | 100 | 200 | ROM 0xF25628 | exact |
| 1176 | Des Frog | Effect Monster | WATER | 5 | 1900 | 0 | ROM 0xF2562C | exact |
| 1177 | T.A.D.P.O.L.E. | Effect Monster | WATER | 1 | 0 | 0 | ROM 0xF25630 | exact |
| 1178 | Poison Draw Frog | Effect Monster | WATER | 2 | 100 | 100 | ROM 0xF25634 | exact |
| 1179 | Tyranno Infinity | Effect Monster | EARTH | 4 | 0 | 0 | ROM 0xF25638 | exact |
| 1180 | Batteryman C | Effect Monster | LIGHT | 2 | 0 | 0 | ROM 0xF2563C | exact |
| 1181 | Ebon Magician Curran | Effect Monster | DARK | 2 | 1200 | 0 | ROM 0xF25640 | exact |
| 1182 | D.D.M. - Different Dimension Master | Effect Monster | LIGHT | 5 | 1700 | 1500 | ROM 0xF25644 | exact |
| 1183 | Fusion Recovery | Spell | NONE | 0 | 0 | 0 | ROM 0xF25648 | exact |
| 1184 | Miracle Fusion | Spell | NONE | 0 | 0 | 0 | ROM 0xF2564C | exact |
| 1185 | Dragon's Mirror | Spell | NONE | 0 | 0 | 0 | ROM 0xF25650 | exact |
| 1186 | System Down | Spell | NONE | 0 | 0 | 0 | ROM 0xF25654 | exact |
| 1187 | Des Croaking | Spell | NONE | 0 | 0 | 0 | ROM 0xF25658 | exact |
| 1188 | Pot of Generosity | Spell | NONE | 0 | 0 | 0 | ROM 0xF2565C | exact |
| 1189 | Fire Darts | Trap | NONE | 0 | 0 | 0 | ROM 0xF25660 | exact |
| 1190 | Spiritual Earth Art - Kurogane | Trap | NONE | 0 | 0 | 0 | ROM 0xF25664 | exact |
| 1191 | Spiritual Water Art - Aoi | Trap | NONE | 0 | 0 | 0 | ROM 0xF25668 | exact |
| 1192 | Spiritual Fire Art - Kurenai | Trap | NONE | 0 | 0 | 0 | ROM 0xF2566C | exact |
| 1193 | Spiritual Wind Art - Miyabi | Trap | NONE | 0 | 0 | 0 | ROM 0xF25670 | exact |
| 1194 | A Rival Appears! | Trap | NONE | 0 | 0 | 0 | ROM 0xF25674 | exact |
| 1195 | Magical Explosion | Trap | NONE | 0 | 0 | 0 | ROM 0xF25678 | exact |
| 1196 | Rising Energy | Trap | NONE | 0 | 0 | 0 | ROM 0xF2567C | exact |
| 1197 | D.D. Trap Hole | Trap | NONE | 0 | 0 | 0 | ROM 0xF25680 | exact |
| 1198 | Conscription | Trap | NONE | 0 | 0 | 0 | ROM 0xF25684 | exact |
| 1199 | Wasteland Amazon | Effect Monster | EARTH | 4 | 1100 | 1200 | ROM 0xF25688 | exact |
| 1200 | Elemental Hero Shining Flare Wingman | Fusion Monster | LIGHT | 8 | 2500 | 2100 | ROM 0xF2568C | exact |

## Packs

| ID | Name | Price | Cards/pack | Pool | Unlock | Source | Confidence |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| basic_1a | Basic 1-A | 100 | 5 | 40 | default | [guide](https://yugipedia.com/wiki/Basic_1-A) | high |
| basic_1b | Basic 1-B | 100 | 5 | 40 | default | [guide](https://yugipedia.com/wiki/Basic_1-B) | high |
| basic_2a | Basic 2-A | 120 | 5 | 40 | default | [guide](https://yugipedia.com/wiki/Basic_2-A) | high |
| basic_2b | Basic 2-B | 120 | 5 | 40 | default | [guide](https://yugipedia.com/wiki/Basic_2-B) | high |
| basic_3a | Basic 3-A | 150 | 5 | 40 | for purchase during the last week of October | [guide](https://yugipedia.com/wiki/Basic_3-A) | high |
| basic_3b | Basic 3-B | 150 | 5 | 40 | for purchase during the last week of November | [guide](https://yugipedia.com/wiki/Basic_3-B) | high |
| basic_4a | Basic 4-A | 150 | 5 | 40 | for purchase on January 23rd of the second year | [guide](https://yugipedia.com/wiki/Basic_4-A) | high |
| basic_4b | Basic 4-B | 150 | 5 | 40 | for purchase on February 20th of the second year | [guide](https://yugipedia.com/wiki/Basic_4-B) | high |
| basic_1c | Basic 1-C | 150 | 5 | 40 | for purchase during March 20th | [guide](https://yugipedia.com/wiki/Basic_1-C) | high |
| basic_2c | Basic 2-C | 150 | 5 | 40 | for purchase on April 24th of the second year | [guide](https://yugipedia.com/wiki/Basic_2-C) | high |
| basic_3c | Basic 3-C | 150 | 5 | 40 | for purchase on May 22nd | [guide](https://yugipedia.com/wiki/Basic_3-C) | high |
| basic_4c | Basic 4-C | 150 | 5 | 40 | for purchase during the last week of June | [guide](https://yugipedia.com/wiki/Basic_4-C) | high |
| effect_monsters | Effect Monsters | 150 | 7 | 50 | Read "Effect Monster" Tutorial (1-2) | [guide](https://yugipedia.com/wiki/Effect_Monsters_(GX1-BP)) | high |
| various_fields | Various Fields | 150 | 3 | 20 | Read "Field Spell" Tutorial (7-7) | [guide](https://yugipedia.com/wiki/Various_Fields_(GX1-BP)) | high |
| equipments | Equipments | 100 | 3 | 55 | Read "Equip Spell" Tutorial (7-3) | [guide](https://yugipedia.com/wiki/Equipments_(GX1-BP)) | high |
| fusions | Fusions | 100 | 5 | 61 | Read "Fusion Monster" Tutorial (1-4) | [guide](https://yugipedia.com/wiki/Fusions_(GX1-BP)) | high |
| rituals | Rituals | 100 | 5 | 51 | Read "Ritual Monster" Tutorial (1-3) | [guide](https://yugipedia.com/wiki/Rituals_(GX1-BP)) | high |
| continuous_effects | Continuous Effects | 100 | 5 | 80 | "Continuous Spell" (7-4) and "Continuous Trap" Tutorials (7-11) | [guide](https://yugipedia.com/wiki/Continuous_Effects_(GX1-BP)) | high |
| spell_collection_1 | Spell Collection 1 | 100 | 5 | 33 | Read "Spell" Tutorial (1-5) | [guide](https://yugipedia.com/wiki/Spell_Collection_1_(GX1-BP)) | high |
| spell_collection_2 | Spell Collection 2 | 100 | 5 | 33 | Read "Spell" Tutorial (1-5) | [guide](https://yugipedia.com/wiki/Spell_Collection_2_(GX1-BP)) | high |
| trap_collection_1 | Trap Collection 1 | 100 | 5 | 28 | Read "Trap" Tutorial (1-6) | [guide](https://yugipedia.com/wiki/Trap_Collection_1_(GX1-BP)) | high |
| trap_collection_2 | Trap Collection 2 | 100 | 5 | 28 | Read "Trap" Tutorial (1-6) | [guide](https://yugipedia.com/wiki/Trap_Collection_2_(GX1-BP)) | high |
| spell_special_1 | Spell Special 1 | 150 | 3 | 33 | Get 90% Collection Rate on "Spell Collection 1" Pack | [guide](https://yugipedia.com/wiki/Spell_Special_1_(GX1-BP)) | high |
| spell_special_2 | Spell Special 2 | 150 | 3 | 33 | Get 90% Collection Rate on "Spell Collection 2" Pack | [guide](https://yugipedia.com/wiki/Spell_Special_2_(GX1-BP)) | high |
| trap_special_1 | Trap Special 1 | 150 | 3 | 28 | Get 90% Collection Rate on "Trap Collection 1" Pack | [guide](https://yugipedia.com/wiki/Trap_Special_1_(GX1-BP)) | high |
| trap_special_2 | Trap Special 2 | 150 | 3 | 28 | Get 90% Collection Rate on "Trap Collection 2" Pack | [guide](https://yugipedia.com/wiki/Trap_Special_2_(GX1-BP)) | high |
| expert_1 | Expert I | 200 | 5 | 72 | "Excellent Duelist" Rank | [guide](https://yugipedia.com/wiki/Expert_I_(GX1-BP)) | high |
| expert_2 | Expert II | 200 | 5 | 72 | "Excellent Duelist" Rank | [guide](https://yugipedia.com/wiki/Expert_II_(GX1-BP)) | high |
| expert_3 | Expert III | 200 | 5 | 72 | "Excellent Duelist" Rank | [guide](https://yugipedia.com/wiki/Expert_III_(GX1-BP)) | high |
| expert_4 | Expert IV | 200 | 5 | 72 | "Excellent Duelist" Rank | [guide](https://yugipedia.com/wiki/Expert_IV_(GX1-BP)) | high |
| power_destructions | Power Destructions | 250 | 3 | 53 | Change dorms at least once | [guide](https://yugipedia.com/wiki/Power_Destructions_(GX1-BP)) | high |
| effect_monsters_special | Effect Monsters Special | 150 | 3 | 36 | Housed in each dorm at least once | [guide](https://yugipedia.com/wiki/Effect_Monsters_Special_(GX1-BP)) | high |
| master_fusions | Master Fusions | 200 | 3 | 36 | Get 90% Collection Rate on "Fusions" Pack | [guide](https://yugipedia.com/wiki/Master_Fusions_(GX1-BP)) | high |
| the_hero | The HERO | 400 | 3 | 26 | "New Hero Summoning!" Event (Be on Slifer Red Dorm + Beat Syrus 10 times + Beat Jaden 5 times) | [guide](https://yugipedia.com/wiki/The_HERO_(GX1-BP)) | high |
| live_vehicles | Live Vehicles | 400 | 3 | 12 | Beat Syrus 10 times | [guide](https://yugipedia.com/wiki/Live_Vehicles_(GX1-BP)) | high |
| be_quick | Be Quick | 700 | 3 | 19 | Read "Combos" Tutorial (11-1~4) | [guide](https://yugipedia.com/wiki/Be_Quick_(GX1-BP)) | high |
| special_ways | Special Ways | 400 | 3 | 53 | Duel with Sartyr once | [guide](https://yugipedia.com/wiki/Special_Ways_(GX1-BP)) | high |
| dorothys_gift | Dorothy's Gift | 1000 | 7 | 0 | Get 90% Collection Rate | [guide](https://yugipedia.com/wiki/Dorothy's_Gift_(GX1-BP)) | high |
| residents_of_the_sea | Residents of the Sea | 200 | 5 | 89 | Duel at the Harbor once | [guide](https://yugipedia.com/wiki/Residents_of_the_Sea_(GX1-BP)) | high |
| invitation_to_the_dark | Invitation to the Dark | 200 | 5 | 177 | Clear "Shadow Demon Deck" Event | [guide](https://yugipedia.com/wiki/Invitation_to_the_Dark_(GX1-BP)) | high |
| pyrogen | Pyrogen | 200 | 5 | 77 | for purchase by finishing a Duel at the Volcano | [guide](https://yugipedia.com/wiki/Pyrogen) | high |
| fairy_dance | Fairy Dance | 200 | 5 | 49 | for purchase by beating the event A Suspicious Person!? | [guide](https://yugipedia.com/wiki/Fairy_Dance) | high |
| insects_nest | Insect's Nest | 200 | 5 | 38 | Clear "Draw! Draw! Draw!" Event (In order to do this, you have to be at the "Talented Duelist" Rank + Beat Damon 5 times + already unlocked "Invitation to the Dark" Pack) | [guide](https://yugipedia.com/wiki/Insect's_Nest_(GX1-BP)) | high |
| dragons_in_flight | Dragons in Flight | 200 | 5 | 59 | Beat Bastion 10 times | [guide](https://yugipedia.com/wiki/Dragons_in_Flight_(GX1-BP)) | high |
| beasts_in_fight | Beasts in Fight | 200 | 5 | 74 | Indoor Duel" Event (Be in Slifer Red Dorm + Stay in your room for 3 weeks) | [guide](https://yugipedia.com/wiki/Beasts_in_Fight_(GX1-BP)) | high |
| the_warriors | The Warriors | 200 | 5 | 112 | Duel with Gerard once | [guide](https://yugipedia.com/wiki/The_Warriors_(GX1-BP)) | high |
| the_machines | The Machines | 200 | 5 | 81 | Clear "An Old Memory" Event (Be "Average Duelist" Rank + On Saturday Morning, Duel with Syrus + On Saturday Night, go to the Harbor | [guide](https://yugipedia.com/wiki/The_Machines_(GX1-BP)) | high |
| spellcasters_dance | Spellcaster's Dance | 200 | 5 | 91 | Clear "VS Yugi Deck" Event (Dimitri available for more than a month + Unlocked "The Machines" Pack + Unlocked "Insect's Next" Pack) | [guide](https://yugipedia.com/wiki/Spellcaster's_Dance_(GX1-BP)) | high |

## Events

| ID | Title | When | Where | Confidence | Source | Dialogue candidates |
| --- | --- | --- | --- | --- | --- | ---: |
| E01 | School Registration | date={'year': 1, 'month': 10, 'day': 1}, weekday=Sunday, note=Opening ceremony; first free-roam day is Saturday, October 7. | Gym; Slifer Red cafeteria; Shop; Classroom | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E02 | Pharaoh's True Power | weekday=Saturday | Lyman Banner's Room | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E03 | A New Hero Summoned | weekday=Weekdays, automatic=True | Jaden's Room | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 0 |
| E04 | Old Memories, Part 1 | weekday=Sunday, period=AM | Anywhere | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 0 |
| E04b | Old Memories, Part 2 | weekday=Sunday, period=Night, automatic=True | Next to Ocean | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E05 | The Power of the Kaiser | weekday=Weekdays, automatic=True | Anywhere | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E06 | Dark Fiend Deck | weekday=Weekdays, period=PM, automatic=True | Harbor; Ocean | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 5 |
| E07 | Occult Recommendation | weekday=Weekdays, automatic=True | Classroom | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E08 | Jinzo | period=PM, after_event=E07, automatic=True | Your Room | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E09 | Duel Festival | weekday=Friday, rule=third Friday of November | Classroom; Duel Arena | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E10 | Merry Christmas | date={'year': 1, 'month': 12, 'day': 25} | Headmaster's Room (current dorm) | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E11 | New Year's Duel | date={'year': 2, 'month': 1, 'day': 1} | Your Room | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E12 | Pride of the Elite | weekday=Weekdays, automatic=True | Front of Obelisk Blue Boys' Dorm | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 2 |
| E13 | Battle against Chazz | weekday=Weekdays, automatic=True | Classroom; Duel Arena; Harbor | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E14 | Revenge of the Obelisk Blues | weekday=Weekdays, period=PM, automatic=True | Obelisk Blue Boys' Lobby; Duel Arena | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 2 |
| E15 | Chazz Reborn | weekday=Weekdays, automatic=True | Chancellor's Office; Duel Arena | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 0 |
| E16 | Brier and Beauregard | weekday=Saturday, period=PM | Duel Arena | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 4 |
| E17 | The Goblin King | weekday=Weekdays, period=PM/Night, automatic=True | Classroom; Front of Duel Academy; Harbor | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 0 |
| E18 | Who Are You? | note=Talk to Sartyr once, wait 60 days, then talk again. | Your Room; Next to Ocean; Ra Yellow Cafeteria; Duel Arena | medium | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 3 |
| E19 | A Suspicious Character | weekday=Saturday, period=Night | Classroom; Front of Obelisk Blue Girls' Dorm | medium | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 3 |
| E20 | A Shadow Game | weekday=Weekend, period=PM | Ocean; Volcano; Gym | medium | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E21 | Suspicious Classmate | weekday=Weekdays, period=PM, automatic=True | Your Room | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 3 |
| E22 | Draw, Draw, Draw | weekday=Weekdays, period=PM, automatic=True | Shop; Front of Obelisk Blue Boys' Dorm | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 1 |
| E23 | Yugi's Legendary Deck | weekday=Weekdays, period=PM, automatic=True | Your Room; Next to Ocean | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E24 | Missing Hero | weekday=Saturday | Harbor | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E25 | The Power of a Maiden's Love | weekday=Saturday, period=PM | Front of Obelisk Blue Boys' Dorm; Your Room; Harbor | medium | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 6 |
| E26 | The 7th Deck | weekday=Saturday | Classroom | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 3 |
| E27 | The Truth Behind Gerard | automatic=True | Front of Slifer Red Dorm | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 0 |
| E28 | Battle for the Chocolate! | date={'year': 2, 'month': 2, 'day': 14} | Classroom; Duel Arena | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E28b | Reversal Valentine's Day | date={'year': 2, 'month': 3, 'day': 14} | Obelisk Blue Girls' Dorm | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E29 | Helping the Dropout | weekday=Saturday, period=PM | Gym | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E30 | A Friend's Concern | weekday=Weekdays, automatic=True | Your Room (Slifer Red) | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |
| E31 | The Walk Home | weekday=Weekdays, period=PM, automatic=True | Front of Duel Academy; Next to Ocean | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 5 |
| E32 | Help Miss Dorothy | weekday=Friday, exam_day=True, chance=2/5 | Front of Duel Academy | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 3 |
| E33 | The Duel King | weekday=Saturday, post_game=True | Chancellor's Office | high | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) | 8 |

## Opponents

| ID | Name | Dorm | Archetype | Signature cards | Confidence |
| --- | --- | --- | --- | ---: | --- |
| alexis | Alexis Rhodes | Obelisk Blue | Fairy | 16 | medium |
| banner | Lyman Banner | Slifer Red | Retro | 4 | medium |
| bastion | Bastion Misawa | Ra Yellow | Magnet | 10 | medium |
| beauregard | Beauregard | Ra Yellow | Goblin | 11 | medium |
| blair | Blair Flannigan | Slifer Red | Maiden | 7 | medium |
| brier | Brier | Ra Yellow | Goblin | 7 | medium |
| chazz | Chazz Princeton | Obelisk Blue | Dark | 7 | medium |
| chumley | Chumley Huffington | Slifer Red | Burn Beast | 4 | medium |
| conklin | Conklin | Obelisk Blue | basic Fire | 2 | medium |
| crowler | Vellian Crowler | Obelisk Blue | Ancient Gear | 10 | medium |
| damon | Damon | Obelisk Blue | Draw | 13 | medium |
| dimitri | Dimitri | Ra Yellow | unclassified | 14 | medium |
| fontaine | Fonda Fontaine | Obelisk Blue | Winged Beast | 12 | medium |
| gerard | Gerard | Slifer Red | unclassified | 5 | medium |
| jaden | Jaden Yuki | Slifer Red | Beatdown Elemental Hero/Dragon | 14 | medium |
| jasmine | Jasmine | Obelisk Blue | Warrior | 7 | medium |
| mimicry | Mimicry | Others | Cure/Burn/Piercing | 11 | medium |
| mindy | Mindy | Obelisk Blue | Beatdown | 8 | medium |
| pharaoh | Pharaoh | Slifer Red | unclassified | 2 | medium |
| sartyr | Sartyr | Ra Yellow | Knowledge | 10 | medium |
| shadow_duelist | The Shadow Duelist | Others | Archfiend | 16 | medium |
| syrus | Syrus Truesdale | Slifer Red | Vehicroid | 5 | medium |
| topher | Topher | Obelisk Blue | Burn | 2 | medium |
| torrey | Torrey | Obelisk Blue | Fiend | 5 | medium |
| zane | Zane Truesdale | Obelisk Blue | Cyber Dragon / Fusion | 18 | medium |
| goblin_king | Goblin King / Duel Giant | Event |  | 1 | medium |
| jinzo | Jinzo (spirit) | Event |  | 1 | medium |
| sheppard | Chancellor Sheppard | Staff |  | 3 | high |

## Decks

| ID | Name | Type | Main | Extra | Status | Unresolved slots | Complete | Confidence | Source |
| --- | --- | --- | ---: | ---: | --- | ---: | --- | --- | --- |
| fire | Fire Starter | starter | 40 | 1 | complete | 0 | True | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Starter_Decks) |
| water | Water Starter | starter | 40 | 0 | complete | 0 | True | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Starter_Decks) |
| wind | Wind Starter | starter | 40 | 0 | complete | 0 | True | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Starter_Decks) |
| alexis_year1 | Alexis Rhodes - Year 1 | opponent | 49 | 1 | partial | 4 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#a) |
| banner_year1 | Lyman Banner - Year 1 | opponent | 40 | 2 | partial | 2 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#b) |
| bastion_year1 | Bastion Misawa - Year 1 | opponent | 43 | 0 | partial | 3 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#c) |
| beauregard_year1 | Beauregard - Year 1 | opponent | 52 | 0 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#d) |
| blair_year1 | Blair Flannigan - Year 1 | opponent | 43 | 0 | partial | 1 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#e) |
| brier_year1 | Brier - Year 1 | opponent | 47 | 0 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#f) |
| chazz_year1 | Chazz Princeton - Year 1 | opponent | 45 | 0 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#g) |
| chumley_year1 | Chumley Huffington - Year 1 | opponent | 50 | 1 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#h) |
| crowler_year1 | Vellian Crowler - Year 1 | opponent | 45 | 0 | partial | 4 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#i) |
| damon_year1 | Damon - Year 1 | opponent | 50 | 1 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#j) |
| dimitri_year1 | Dimitri - Year 1 | opponent | 51 | 4 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#k) |
| fontaine_year1 | Fonda Fontaine - Year 1 | opponent | 45 | 0 | partial | 2 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#l) |
| gerard_year1 | Gerard - Year 1 | opponent | 44 | 2 | partial | 1 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#m) |
| jasmine_year1 | Jasmine - Year 1 | opponent | 60 | 0 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#o) |
| mindy_year1 | Mindy - Year 1 | opponent | 28 | 0 | partial | 12 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#p) |
| pharaoh_year1 | Pharaoh - Year 1 | opponent | 39 | 0 | partial | 1 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#q) |
| sartyr_year1 | Sartyr - Year 1 | opponent | 43 | 0 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#r) |
| syrus_year1 | Syrus Truesdale - Year 1 | opponent | 45 | 1 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#s) |
| torrey_year1 | Torrey - Year 1 | opponent | 48 | 0 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#t) |
| zane_year1 | Zane Truesdale - Year 1 | opponent | 50 | 2 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#v) |
| shadow_duelist_year1 | The Shadow Duelist - Year 1 | opponent | 16 | 0 | partial | 24 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#w) |
| mimicry_year1 | Mimicry / Test Proctor - Year 1 | opponent | 46 | 0 | partial | 0 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#x) |
| topher_year1 | Topher - Year 1 | opponent | 17 | 0 | partial | 23 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#event) |
| conklin_year1 | Conklin - Year 1 | opponent | 17 | 0 | partial | 23 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#event) |
| sheppard_year1 | Chancellor Sheppard - Year 1 | opponent | 48 | 3 | complete | 0 | True | high | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#y) |
| jaden_year1 | Jaden Yuki - Year 1 | opponent | 53 | 4 | complete | 0 | True | medium | game3d/src/duel/decklists.js (local donor; not committed) + https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#n |
| jinzo_spirit | Jinzo - Spirit Deck | event | 0 | 0 | unknown | 40 | False | low | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_8:_Jinzo) |
| damon_exodia | Damon - Exodia Draw (Event) | event | 5 | 0 | partial | 35 | False | low | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_22:_Draw,_draw,_draw) |
| yugi_deck | Yugi Muto - Legendary Deck (Event) | event | 39 | 2 | partial | 5 | False | medium | [guide](https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382#u) |
| bastion_seventh | Bastion Misawa - Seventh Deck | event | 0 | 0 | unknown | 40 | False | low | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_26:_The_7th_Deck + dialogue index 4230) |
| torrey_special | Torrey - Special Player Deck | player_override | 0 | 0 | unknown | 40 | False | low | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_7:_Occult_Recommendation) |
| chazz_ojama | Chazz Princeton - Ojama | opponent_variant | 0 | 0 | unknown | 40 | False | low | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) |
| jaden_improved | Jaden Yuki - Improved | opponent_variant | 0 | 0 | unknown | 40 | False | low | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events) |
| bastion_magnet | Bastion Misawa - Magnet | opponent_variant | 0 | 0 | unknown | 40 | False | low | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Opponents) |

### Event constructs

| ID | Kind | Participants | Rounds | Source |
| --- | --- | --- | ---: | --- |
| festival_bracket | tournament | ranked_roster | None | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_9:_Duel_Festival) |
| chocolate_bracket | tournament | fontaine, alexis, jasmine, mindy, blair | 4 | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_28:_Battle_for_the_Chocolate!) |
| walk_home_partner | partner_pool | jaden, syrus, chumley, bastion, alexis, chazz, zane | 1 | [Events](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events#Event_31:_The_Walk_Home) |

## Puzzles

| ID | Level | Solution steps | Setup | Confidence | Source |
| --- | ---: | ---: | --- | --- | --- |
| P001 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_001) |
| P002 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_002) |
| P003 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_003) |
| P004 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_004) |
| P005 | 1 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_005) |
| P006 | 1 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_006) |
| P007 | 1 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_007) |
| P008 | 1 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_008) |
| P009 | 1 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_009) |
| P010 | 1 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_010) |
| P011 | 1 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_011) |
| P012 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_012) |
| P013 | 1 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_013) |
| P014 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_014) |
| P015 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_015) |
| P016 | 1 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_016) |
| P017 | 1 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_017) |
| P018 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_018) |
| P019 | 1 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_019) |
| P020 | 1 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_020) |
| P021 | 2 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_021) |
| P022 | 2 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_022) |
| P023 | 2 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_023) |
| P024 | 2 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_024) |
| P025 | 2 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_025) |
| P026 | 2 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_026) |
| P027 | 2 | 9 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_027) |
| P028 | 2 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_028) |
| P029 | 2 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_029) |
| P030 | 2 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_030) |
| P031 | 2 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_031) |
| P032 | 2 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_032) |
| P033 | 2 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_033) |
| P034 | 2 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_034) |
| P035 | 2 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_035) |
| P036 | 2 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_036) |
| P037 | 2 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_037) |
| P038 | 2 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_038) |
| P039 | 2 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_039) |
| P040 | 2 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_040) |
| P041 | 3 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_041) |
| P042 | 3 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_042) |
| P043 | 3 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_043) |
| P044 | 3 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_044) |
| P045 | 3 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_045) |
| P046 | 3 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_046) |
| P047 | 3 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_047) |
| P048 | 3 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_048) |
| P049 | 3 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_049) |
| P050 | 3 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_050) |
| P051 | 3 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_051) |
| P052 | 3 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_052) |
| P053 | 3 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_053) |
| P054 | 3 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_054) |
| P055 | 3 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_055) |
| P056 | 3 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_056) |
| P057 | 3 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_057) |
| P058 | 3 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_058) |
| P059 | 3 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_059) |
| P060 | 3 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_060) |
| P061 | 4 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_061) |
| P062 | 4 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_062) |
| P063 | 4 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_063) |
| P064 | 4 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_064) |
| P065 | 4 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_065) |
| P066 | 4 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_066) |
| P067 | 4 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_067) |
| P068 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_068) |
| P069 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_069) |
| P070 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_070) |
| P071 | 4 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_071) |
| P072 | 4 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_072) |
| P073 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_073) |
| P074 | 4 | 14 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_074) |
| P075 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_075) |
| P076 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_076) |
| P077 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_077) |
| P078 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_078) |
| P079 | 4 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_079) |
| P080 | 4 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_080) |
| P081 | 5 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_081) |
| P082 | 5 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_082) |
| P083 | 5 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_083) |
| P084 | 5 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_084) |
| P085 | 5 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_085) |
| P086 | 5 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_086) |
| P087 | 5 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_087) |
| P088 | 5 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_088) |
| P089 | 5 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_089) |
| P090 | 5 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_090) |
| P091 | 5 | 8 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_091) |
| P092 | 5 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_092) |
| P093 | 5 | 9 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_093) |
| P094 | 5 | 3 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_094) |
| P095 | 5 | 4 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_095) |
| P096 | 5 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_096) |
| P097 | 5 | 10 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_097) |
| P098 | 5 | 6 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_098) |
| P099 | 5 | 7 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_099) |
| P100 | 5 | 5 | unknown | high | [guide](https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_100) |

## Titles

| ID | Name | Permanent | Conditions | Confidence |
| --- | --- | --- | --- | --- |
| dropout_boy | Dropout Boy | False | [{'type': 'fail_exam'}] | high |
| apprentice_duelist | Apprentice Duelist | True | [{'type': 'start'}, {'type': 'recover_from_dropout', 'event': 'E29'}] | high |
| novice_duelist | Novice Duelist | True | [{'type': 'wins_total', 'count': 5}] | low |
| average_duelist | Average Duelist | True | [{'type': 'wins_total', 'count': 10}] | high |
| fiery_duelist | Fiery Duelist | True | [{'type': 'wins_total', 'count': 30}] | high |
| calm_duelist | Calm Duelist | True | [{'type': 'wins_total', 'count': 30}, {'type': 'timed_clears', 'count': 25}] | medium |
| superior_duelist | Superior Duelist | True | [{'type': 'wins_total', 'count': 50}, {'type': 'timed_clears', 'count': 50}] | high |
| shrewd_duelist | Shrewd Duelist | True | [{'type': 'wins_total', 'count': 100}] | high |
| honored_duelist | Honored Duelist | True | [{'type': 'wins_total', 'count': 100}, {'type': 'written_correct', 'count': 40}] | medium |
| elite_duelist | Elite Duelist | True | [{'type': 'wins_total', 'count': 100}, {'type': 'timed_clears', 'count': 100}] | medium |
| celebrity_duelist | Celebrity Duelist | True | [{'type': 'wins_total', 'count': 150}] | low |
| prince_of_games | Prince of Games | True | [{'type': 'collection', 'count': 1200}, {'type': 'written_correct_percent', 'percent': 40}] | medium |
| king_of_games | King of Games | True | [{'type': 'wins_total', 'count': 200}, {'type': 'wins_against_each', 'count': 10, 'duelists': 20}, {'type': 'written_correct_percent', 'percent': 60}, {'type': 'after_ending'}] | high |
| occult_duelist | Occult Duelist | False | [{'type': 'event', 'event': 'E07'}] | high |

## Banned / Limited

| Card ID | Name | Year 1 | Year 2 | Year 3 |
| ---: | --- | --- | --- | --- |
| 13 | Right Leg of the Forbidden One | Limited | Limited | Limited |
| 14 | Left Leg of the Forbidden One | Limited | Limited | Limited |
| 15 | Right Arm of the Forbidden One | Limited | Limited | Limited |
| 16 | Left Arm of the Forbidden One | Limited | Limited | Limited |
| 17 | Exodia the Forbidden One | Limited | Limited | Limited |
| 29 | Sangan | Limited | Limited | Limited |
| 141 | Dark Hole | Forbidden | Limited | Forbidden |
| 142 | Raigeki | Forbidden | Forbidden | Limited |
| 153 | Swords of Revealing Light | Limited | Limited | Limited |
| 209 | Sinister Serpent | Limited | Limited | Limited |
| 257 | Witch of the Black Forest | Forbidden | Limited | Forbidden |
| 259 | Morphing Jar | Limited | Limited | Limited |
| 292 | Harpie's Feather Duster | Forbidden | Limited | Forbidden |
| 348 | Jinzo | Limited | Limited | Limited |
| 350 | Reflect Bounder | Limited | Limited | Limited |
| 370 | Graceful Charity | Limited | Limited | Limited |
| 375 | Card Destruction | Limited | Limited | Limited |
| 385 | Monster Reborn | Forbidden | Limited | Forbidden |
| 387 | Pot of Greed | Limited | Forbidden | Limited |
| 401 | Change of Heart | Forbidden | Limited | Forbidden |
| 405 | Royal Decree | Unlimited | Limited | Unlimited |
| 421 | Mirror Force | Limited | Limited | Limited |
| 422 | Heavy Storm | Limited | Forbidden | Limited |
| 425 | Upstart Goblin | Semi-Limited | Semi-Limited | Limited |
| 428 | Snatch Steal | Limited | Forbidden | Limited |
| 430 | Confiscation | Forbidden | Limited | Forbidden |
| 431 | Delinquent Duo | Limited | Forbidden | Limited |
| 434 | The Forceful Sentry | Forbidden | Limited | Forbidden |
| 436 | Mystical Space Typhoon | Limited | Limited | Limited |
| 438 | Painful Choice | Forbidden | Limited | Forbidden |
| 440 | Cyber Jar | Limited | Limited | Limited |
| 469 | Ceasefire | Limited | Limited | Limited |
| 472 | Imperial Order | Forbidden | Limited | Forbidden |
| 474 | Nobleman of Crossout | Semi-Limited | Semi-Limited | Semi-Limited |
| 477 | Premature Burial | Limited | Forbidden | Limited |
| 497 | Call of the Haunted | Limited | Limited | Limited |
| 503 | Ring of Destruction | Limited | Limited | Limited |
| 516 | Injection Fairy Lily | Limited | Limited | Limited |
| 547 | Torrential Tribute | Limited | Limited | Limited |
| 552 | Magic Cylinder | Limited | Limited | Limited |
| 557 | Gravity Bind | Semi-Limited | Limited | Semi-Limited |
| 593 | United We Stand | Limited | Limited | Limited |
| 594 | Mage Power | Limited | Limited | Limited |
| 597 | Lightning Vortex | Limited | Limited | Limited |
| 649 | Marauding Captain | Semi-Limited | Semi-Limited | Semi-Limited |
| 651 | Exiled Force | Limited | Limited | Limited |
| 653 | Reinforcement of the Army | Semi-Limited | Semi-Limited | Semi-Limited |
| 664 | Emergency Provisions | Semi-Limited | Semi-Limited | Semi-Limited |
| 671 | Reversal of Graves | Limited | Limited | Limited |
| 675 | Fiber Jar | Forbidden | Limited | Forbidden |
| 678 | Yata-Garasu | Forbidden | Limited | Forbidden |
| 706 | Reckless Greed | Limited | Limited | Limited |
| 762 | Spell Canceller | Unlimited | Limited | Unlimited |
| 787 | Breaker the Magical Warrior | Limited | Limited | Limited |
| 789 | Magical Scientist | Forbidden | Limited | Forbidden |
| 792 | Tribe-Infecting Virus | Limited | Forbidden | Limited |
| 820 | D. D. Warrior Lady | Limited | Limited | Limited |
| 868 | Black Luster Soldier - Envoy of the Beginning | Limited | Forbidden | Limited |
| 886 | Chaos Emperor Dragon - Envoy of the End | Forbidden | Limited | Limited |
| 896 | Dark Magician of Chaos | Limited | Limited | Limited |
| 963 | Marshmallon | Limited | Limited | Limited |
| 976 | Protector of the Sanctuary | Limited | Limited | Limited |
| 1098 | Good Goblin Housekeeping | Semi-Limited | Semi-Limited | Semi-Limited |

## Exams and text

| ID | Type | Source | Confidence |
| --- | --- | --- | --- |
| written_exam_bank | question templates | ROM 0x1430F2C | high templates / low keys |
| practical_exam_1..7 | practical definitions | ROM 0x146C23E | high |
| dialogue_index | 4,527 strings | ROM 0x13F6DF0 / 0x14280A0 | high offsets, local-only text |
| name_table | 26 full / 26 short names | ROM 0x146CB14 / 0x146CC32 | exact |

