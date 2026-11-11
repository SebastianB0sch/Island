"""Named ambient NPC roster.

The island's generic student markers used to share three looks, the display name
"Student" and the same handful of dorm lines.  This module gives every ambient
marker a stable identity instead:

  * a unique name (curated for the notable spots, generated for the rest),
  * a dorm / location-appropriate voice with three original lines,
  * a hair colour and a profile line that names the character.

The named anime cast keep the markers they own (see ``cast.assign_npcs``); only
markers still carrying ``tint == True`` are annotated here.

Assignment is deterministic.  Markers are sorted by (group, dorm, x, y), so the
same layout always produces the same roster, and rebuilding the layout never
reshuffles who stands where.
"""

from __future__ import annotations

import zlib

# --------------------------------------------------------------------------- hair
# Linear RGB.  The first ten are natural colours used for staff; students also
# draw from the anime colours at the end.
HAIR_PALETTE = (
    (0.015, 0.012, 0.010),   # black
    (0.035, 0.020, 0.012),   # near-black brown
    (0.090, 0.045, 0.020),   # dark brown
    (0.180, 0.085, 0.035),   # brown
    (0.300, 0.160, 0.070),   # chestnut
    (0.500, 0.260, 0.090),   # auburn
    (0.700, 0.300, 0.080),   # ginger
    (0.850, 0.650, 0.250),   # blond
    (0.950, 0.820, 0.500),   # platinum blond
    (0.600, 0.600, 0.620),   # silver
    (0.850, 0.850, 0.880),   # white
    (0.050, 0.080, 0.220),   # blue-black
    (0.080, 0.180, 0.500),   # navy
    (0.100, 0.350, 0.400),   # teal
    (0.100, 0.300, 0.120),   # dark green
    (0.350, 0.150, 0.500),   # purple
    (0.650, 0.200, 0.450),   # magenta
    (0.800, 0.300, 0.350),   # rose
    (0.250, 0.250, 0.280),   # charcoal
    (0.450, 0.350, 0.300),   # ash brown
)
NATURAL_HAIR_COUNT = 10

# --------------------------------------------------------------------------- voices
# Each voice is a small, original set of lines for a dorm / role / location.  A
# roster entry picks two of them; the third line is always its own profile line,
# so every NPC has at least one line nobody else says.
VOICES = {
    "slifer_underdog": (
        "Slifer Red isn't a rank, it's a promise. We just haven't kept it yet.",
        "Everyone here counts us out before the first draw. That's fine by me.",
        "You don't need a fancy dorm to have a good deck. You need nerve.",
        "One day this whole island is going to know a Slifer won the big one.",
    ),
    "slifer_slacker": (
        "Class? I thought today was the free period.",
        "The cliff walk is the best shortcut on the island. Nobody patrols it.",
        "I'll study tomorrow. Tomorrow-me is much more responsible.",
        "There's a nap spot behind the gym that nobody knows about. Until now.",
    ),
    "slifer_curry": (
        "Curry for breakfast, curry for lunch. That's balance.",
        "Professor Banner's curry has ruined every other food for me.",
        "The secret is to add the spice after the rice, not before.",
        "I've got a curry recipe that could win a duel by itself.",
    ),
    "ra_scholar": (
        "The written exam rewards preparation, not luck. Read the rulings.",
        "I keep a notebook of every card interaction I see. It's getting heavy.",
        "Ra Yellow is quiet enough to think and close enough to the arena.",
        "There is always a correct line of play. Finding it is the fun part.",
    ),
    "ra_ambitious": (
        "Promotion to Obelisk Blue is a matter of when, not if.",
        "I'm two wins away from the top of the dorm rankings.",
        "The Ra cafeteria is good, but I'm working for the Obelisk view.",
        "Every duel is an audition. I intend to be unforgettable.",
    ),
    "ra_inventor": (
        "I rebuilt my duel disk over the weekend. It only sparks a little now.",
        "My deck has a combo that nobody expects. Mostly because it's unstable.",
        "Theory is useless if you never test it. That's why I duel so much.",
        "The physics lab has a spare bench if you ever need to prototype something.",
    ),
    "obelisk_elite": (
        "Obelisk Blue is a standard, not a colour. Try to carry it properly.",
        "The academy expects excellence from us. I expect it from myself.",
        "You can learn a lot from a duelist's posture before they even draw.",
        "Winning is not enough. It has to look effortless.",
    ),
    "obelisk_duelist": (
        "The arena field is where reputations are made. I plan to make mine.",
        "I've studied every top-table match this year. Twice.",
        "A deck is a promise. Mine says I don't intend to lose.",
        "If you want a real duel, you know where to find me.",
    ),
    "obelisk_socialite": (
        "The girls' dorm tea room has a better view than the Chancellor's office.",
        "I'm hosting a study circle tonight. Duel theory, not gossip. Mostly.",
        "You should see the formal gardens when the lamps come on.",
        "There is a correct fork for every course. And a correct topic for every table.",
    ),
    "girl_duelist": (
        "Don't let the uniform fool you. I've topped my bracket three times.",
        "The girls' dorm has its own practice room. It gets crowded after class.",
        "I prefer a fast deck. Make a decision, commit to it, win.",
        "If you're looking for an easy duel, keep walking.",
    ),
    "girl_gossip": (
        "Did you hear what happened in the Obelisk dining hall last night?",
        "I know every rumour on this island. Most of them are even true.",
        "The boys' dorm is not allowed past the lake. That has never stopped anyone.",
        "You didn't hear this from me, but the abandoned dorm is not empty.",
    ),
    "staff_teacher": (
        "Duel Academy runs on punctuality. Yours could use work.",
        "The practical exam is not about luck. It is about preparation.",
        "If you have a question, ask it before the bell, not after.",
        "I've graded worse duels than yours. Not many, but some.",
    ),
    "staff_nurse": (
        "Drink water, sleep, and stop dueling on an empty stomach.",
        "The infirmary is open. The beds are not for napping. Usually.",
        "If you get hurt in a Shadow Game, come to me first. Then tell the Chancellor.",
        "Duelists forget that their bodies are part of the deck too.",
    ),
    "staff_librarian": (
        "The archives are open until dusk. Please keep your voice down.",
        "We have every duel theory text published this decade. Most of them twice.",
        "A card's text is not a suggestion. Read it carefully.",
        "The restricted shelf is restricted for a reason. Ask me why.",
    ),
    "staff_chef": (
        "The kitchen is closed until dinner. Unless you're here to help.",
        "Curry, stew, or whatever's left in the pantry. Take your pick.",
        "A good meal is the first step to a good duel.",
        "Don't touch the pots. I mean it.",
    ),
    "harbor_worker": (
        "The ferry comes in on the hour. The cargo comes in whenever it wants.",
        "I've seen storms take the whole pier apart. The lighthouse always held.",
        "You want to know what's in the warehouse? So do I.",
        "Harbor work is quiet until it isn't. Then it's very loud.",
    ),
    "gym_athlete": (
        "The court is free after the assembly. Bring a deck and proper shoes.",
        "I run the beach path every morning. The hill at the end is the real duel.",
        "Dueling and sport have the same rule: keep your feet moving.",
        "The gym has the best light in the afternoon. It makes every win look better.",
    ),
    "hotsprings_regular": (
        "The water is perfect today. Leave your deck outside the changing room.",
        "Nothing resets a bad duel like an hour in the springs.",
        "The steam hides the volcano. The rumble doesn't.",
        "I've been coming here since my first year. The rocks never move.",
    ),
    "plaza_vendor": (
        "Fresh cards, cold drinks, and absolutely no refunds.",
        "The plaza is the best place to watch the island go by.",
        "You can tell a duelist's dorm by how they walk across the fountain square.",
        "Special today: a rare card and a terrible joke, one price.",
    ),
    "society_of_light": (
        "The light shows you the path. You only have to stop resisting it.",
        "Everything is clearer in white. Even the things you would rather not see.",
        "The Society welcomes everyone. Especially the uncertain.",
        "Once you have seen the light, the old dorm colours look very small.",
    ),
    "club_artist": (
        "The art room is on the third floor. Mind the wet canvas.",
        "I'm painting the volcano from the west cliff. The light changes every hour.",
        "A duel is just a composition with a winner at the end.",
        "If you stand still long enough, I'll put you in the background.",
    ),
    "club_gamer": (
        "There's a CRT in the Slifer lounge that still works. Mostly.",
        "I've beaten every game in the club room except one. It knows what I did.",
        "The arcade cabinet by the harbor is rigged. I respect that.",
        "One more round. Then I'll study. Probably.",
    ),
    "exchange_student": (
        "I transferred in this term. The island is bigger than the brochure.",
        "Back home we dueled outdoors. The arena here is another world.",
        "I'm still learning everyone's names. There are so many of you.",
        "The ferry ride in was beautiful. The ferry ride out is not happening yet.",
    ),
    "bookworm": (
        "The library has a copy of every rulebook. I've read most of them.",
        "You can learn a lot about a duelist from the cards they never play.",
        "I'm researching the old dorm's history. The records don't agree.",
        "Quiet please. I'm on the third volume of the island archives.",
    ),
    "delinquent": (
        "You looking for something? Didn't think so.",
        "The rules are a suggestion. The rankings are not.",
        "I don't need a dorm to tell me who I am.",
        "If you want a duel, say it straight. If not, move along.",
    ),
}

GROUP_VOICES = {
    "slifer": ("slifer_underdog", "slifer_slacker", "slifer_curry"),
    "ra": ("ra_scholar", "ra_ambitious", "ra_inventor"),
    "obelisk_boys": ("obelisk_elite", "obelisk_duelist", "delinquent"),
    "obelisk_girls": ("girl_duelist", "girl_gossip", "obelisk_socialite"),
    "academy": ("bookworm", "club_artist", "club_gamer", "exchange_student",
                "obelisk_duelist", "slifer_underdog", "ra_scholar"),
    "plaza": ("plaza_vendor", "obelisk_duelist", "slifer_underdog", "exchange_student"),
    "harbor": ("harbor_worker", "exchange_student", "ra_inventor"),
    "gym": ("gym_athlete", "obelisk_duelist", "slifer_underdog"),
    "hotsprings": ("hotsprings_regular", "staff_nurse", "ra_scholar"),
    "lighthouse": ("harbor_worker", "bookworm", "obelisk_duelist"),
}
STAFF_VOICES = ("staff_teacher", "staff_nurse", "staff_librarian", "staff_chef", "society_of_light")
STAFF_VOICE_BY_TITLE = {
    "Nurse": "staff_nurse",
    "Librarian": "staff_librarian",
    "Archivist": "staff_librarian",
    "Curator": "staff_librarian",
    "Professor": "staff_teacher",
    "Dr.": "staff_teacher",
    "Instructor": "staff_teacher",
    "Counselor": "staff_teacher",
    "Coach": "staff_teacher",
    "Chef": "staff_chef",
    "Groundskeeper": "staff_teacher",
    "Warden": "staff_teacher",
}

# --------------------------------------------------------------------------- curated names
# Notable ambient characters: the first pass gives these names to matching
# markers in the listed groups.  ``voice`` selects their dialogue; ``line`` (if
# present) replaces the generated profile line.
CURATED = (
    # Slifer Red
    dict(name="Ryo Matsuda", female=False, dorm="slifer", voice="slifer_underdog",
         line="I'm Ryo. Slifer Red, third year, still climbing."),
    dict(name="Kenta Baba", female=False, dorm="slifer", voice="slifer_slacker",
         line="Kenta. If you need me, I'll be wherever the food is."),
    dict(name="Haru Nishida", female=False, dorm="slifer", voice="slifer_curry",
         line="Haru Nishida. I make the curry that makes the dorm tolerable."),
    # Ra Yellow
    dict(name="Kenji Tanabe", female=False, dorm="ra", voice="ra_scholar"),
    dict(name="Sora Ishida", female=False, dorm="ra", voice="ra_ambitious"),
    dict(name="Tatsuya Ohta", female=False, dorm="ra", voice="ra_inventor"),
    dict(name="Ren Fujita", female=False, dorm="ra", voice="ra_scholar"),
    dict(name="Daichi Morita", female=False, dorm="ra", voice="ra_ambitious"),
    dict(name="Yuto Nakajima", female=False, dorm="ra", voice="ra_inventor"),
    # Obelisk Blue boys
    dict(name="Takeshi Kuroda", female=False, dorm="obelisk", voice="obelisk_elite"),
    dict(name="Sho Arakawa", female=False, dorm="obelisk", voice="obelisk_duelist"),
    dict(name="Jin Sakamoto", female=False, dorm="obelisk", voice="obelisk_elite"),
    dict(name="Kei Tachibana", female=False, dorm="obelisk", voice="delinquent"),
    dict(name="Naoki Endo", female=False, dorm="obelisk", voice="obelisk_duelist"),
    dict(name="Haruto Kondo", female=False, dorm="obelisk", voice="obelisk_elite"),
    # Obelisk Blue girls
    dict(name="Ayaka Mizuno", female=True, dorm="obelisk", voice="girl_duelist"),
    dict(name="Rina Hoshino", female=True, dorm="obelisk", voice="girl_gossip"),
    dict(name="Momo Kikuchi", female=True, dorm="obelisk", voice="obelisk_socialite"),
    dict(name="Saki Fujimoto", female=True, dorm="obelisk", voice="girl_duelist"),
    dict(name="Yuna Shimada", female=True, dorm="obelisk", voice="girl_gossip"),
    dict(name="Hina Takeda", female=True, dorm="obelisk", voice="obelisk_socialite"),
    dict(name="Eri Nakagawa", female=True, dorm="obelisk", voice="girl_duelist"),
    dict(name="Kaori Sugiyama", female=True, dorm="obelisk", voice="girl_gossip"),
    # Plaza
    dict(name="Hiroshi Yamada", female=False, groups=("plaza",), voice="plaza_vendor"),
    dict(name="Nao Kimura", female=True, groups=("plaza",), voice="exchange_student"),
    dict(name="Goro Hayashi", female=False, groups=("plaza",), voice="slifer_underdog"),
    dict(name="Mei Sato", female=True, groups=("plaza",), voice="obelisk_duelist"),
    # Harbor
    dict(name="Kaito Mori", female=False, groups=("harbor",), voice="harbor_worker"),
    dict(name="Sae Yamamoto", female=True, groups=("harbor",), voice="harbor_worker"),
    dict(name="Genjiro Ito", female=False, groups=("harbor",), voice="harbor_worker"),
    dict(name="Aya Kobayashi", female=True, groups=("harbor",), voice="exchange_student"),
    dict(name="Toma Ishikawa", female=False, groups=("harbor",), voice="harbor_worker"),
    # Gym
    dict(name="Ryota Kato", female=False, groups=("gym",), voice="gym_athlete"),
    dict(name="Shun Maeda", female=False, groups=("gym",), voice="gym_athlete"),
    dict(name="Asuka Noguchi", female=True, groups=("gym",), voice="gym_athlete"),
    dict(name="Kaz Fujiwara", female=False, groups=("gym",), voice="gym_athlete"),
    # Hot springs
    dict(name="Chiyo Ueda", female=True, groups=("hotsprings",), voice="hotsprings_regular"),
    dict(name="Bunta Sakai", female=False, groups=("hotsprings",), voice="hotsprings_regular"),
    # Academy staff
    dict(name="Professor Hale", female=False, staff=True, dorm="white", voice="staff_teacher",
         line="Professor Hale. My office is on the second floor, next to the archives."),
    dict(name="Nurse Okafor", female=True, staff=True, dorm="white", voice="staff_nurse",
         line="Nurse Okafor. The infirmary is always open, even during duels."),
    dict(name="Librarian Ono", female=True, staff=True, dorm="white", voice="staff_librarian",
         line="Librarian Ono. The archives are quieter than the arena, and better organised."),
    dict(name="Groundskeeper Bruno", female=False, staff=True, dorm="white", voice="staff_teacher",
         line="Bruno. I keep the grounds. You keep off the flower beds."),
    # Academy students
    dict(name="Lena Voss", female=True, groups=("academy",), voice="exchange_student"),
    dict(name="Marco Ruiz", female=False, groups=("academy",), voice="exchange_student"),
    dict(name="Tsubasa Aoki", female=False, groups=("academy",), voice="club_artist"),
    dict(name="Natsumi Kudo", female=True, groups=("academy",), voice="club_artist"),
    dict(name="Junpei Ando", female=False, groups=("academy",), voice="club_gamer"),
    dict(name="Riko Shimizu", female=True, groups=("academy",), voice="bookworm"),
    dict(name="Oliver Grant", female=False, groups=("academy",), voice="bookworm"),
    dict(name="Sora Minami", female=True, groups=("academy",), voice="girl_duelist"),
)

# --------------------------------------------------------------------------- generated names
MALE_FIRST = (
    "Akira", "Arata", "Atsushi", "Daiki", "Eiji", "Fumio", "Gaku", "Haruki", "Hayato", "Hikaru",
    "Hiro", "Ichiro", "Isamu", "Jiro", "Jun", "Kai", "Kazuki", "Keita", "Koji", "Kota",
    "Masaru", "Michi", "Minoru", "Naoya", "Nobu", "Osamu", "Rai", "Riku", "Ryohei", "Satoshi",
    "Seiji", "Shin", "Shota", "Taiga", "Takumi", "Taro", "Tetsu", "Tomoya", "Toru", "Yamato",
    "Yasuo", "Yori", "Yuji", "Yuma", "Yusuke", "Zen", "Adrian", "Caleb", "Diego", "Elias",
    "Felix", "Hugo", "Ivan", "Jonas", "Leon", "Miles", "Noah", "Owen", "Theo", "Victor",
)
FEMALE_FIRST = (
    "Ami", "Arisa", "Chika", "Emi", "Fumiko", "Hana", "Haruka", "Hikari", "Honoka", "Izumi",
    "Junko", "Kaede", "Kanako", "Kasumi", "Kira", "Kotone", "Mai", "Mami", "Mayu", "Megumi",
    "Mio", "Miyu", "Nanami", "Nao", "Rei", "Rin", "Sakura", "Sayo", "Shiori", "Sumire",
    "Tomoko", "Wakana", "Yui", "Yuka", "Yumi", "Alice", "Clara", "Elena", "Freya", "Iris",
    "Julia", "Lila", "Nora", "Rose", "Sofia", "Tessa", "Vera", "Zoe",
)
LAST_NAMES = (
    "Abe", "Akiyama", "Ando", "Aoki", "Arai", "Chiba", "Doi", "Endo", "Fujii", "Fukuda",
    "Goto", "Hara", "Hasegawa", "Hattori", "Hayashi", "Hirano", "Honda", "Ikeda", "Imai", "Inoue",
    "Ishii", "Iwata", "Kanda", "Kawaguchi", "Kimura", "Kobayashi", "Kojima", "Kubo", "Kudo", "Maeda",
    "Matsumoto", "Miyazaki", "Mori", "Murata", "Nagai", "Nakamura", "Nishimura", "Noguchi", "Ogawa", "Okada",
    "Ono", "Saito", "Sakamoto", "Sasaki", "Sato", "Shibata", "Shimizu", "Suzuki", "Takahashi", "Tanaka",
    "Tsuchiya", "Ueda", "Watanabe", "Yamaguchi", "Yamamoto", "Yoshida", "Adams", "Bennett", "Carter", "Diaz",
    "Ellis", "Foster", "Grant", "Hayes", "Ibrahim", "Jensen", "Keller", "Lopez", "Moreau", "Parker",
)
STAFF_TITLES = (
    "Professor", "Dr.", "Nurse", "Coach", "Librarian", "Counselor", "Chef", "Groundskeeper",
    "Curator", "Warden", "Instructor", "Archivist",
)
HOMETOWNS = (
    "Domino City", "the mainland", "a fishing town up the coast", "the north shore",
    "a small city in the mountains", "Kaiba Land", "the southern islands", "a quiet suburb",
    "the industrial district", "a village near the sea", "the capital", "the other side of the volcano",
)
THEMES = (
    "Fusion Summoning", "beatdown", "burn damage", "stall tactics", "dragons", "machines",
    "Spellcasters", "Warriors", "Fiends", "Fairies", "Dinosaurs", "Insects", "Sea Serpents",
    "Rock monsters", "Psychic monsters", "Plants", "Zombies", "Winged Beasts", "Thunder monsters",
    "Aqua monsters",
)
CLUBS = (
    "the dueling club", "the art room", "the library", "the gaming club", "the swim team",
    "the archaeology club", "the cooking club", "the mechanics club", "the film club",
    "the astronomy club", "the music room", "the newspaper club",
)
TOPICS = (
    "card rulings", "the old dorm", "the volcano trail", "the harbor ferry", "fusion recipes",
    "the exam schedule", "the island archives", "the Society of Light", "the Grand Arena",
    "the best curry on the island", "deck building", "the lighthouse",
)


def _seed(npc):
    key = "%.1f,%.1f,%s,%s" % (
        float(npc["loc"][0]), float(npc["loc"][1]), npc.get("group", ""), npc.get("dorm", ""))
    return zlib.crc32(key.encode("utf-8"))


def _marker_key(npc):
    return (
        str(npc.get("group", "")),
        str(npc.get("dorm", "")),
        round(float(npc["loc"][0]), 1),
        round(float(npc["loc"][1]), 1),
    )


def _is_female(npc):
    return npc.get("cast") in ("student_f1", "student_f2")


def _is_staff(npc):
    return npc.get("dorm") == "white"


DORM_VOICES = {
    "slifer": ("slifer_underdog", "slifer_slacker", "slifer_curry"),
    "ra": ("ra_scholar", "ra_ambitious", "ra_inventor"),
    "obelisk": ("obelisk_elite", "obelisk_duelist", "delinquent"),
}
GIRL_VOICES = ("girl_duelist", "girl_gossip", "obelisk_socialite")


def _voice_for(npc, seed):
    if _is_staff(npc):
        return STAFF_VOICES[seed % len(STAFF_VOICES)]
    group = npc.get("group", "")
    dorm = npc.get("dorm", "")
    if group == "obelisk_girls":
        return GIRL_VOICES[seed % len(GIRL_VOICES)]
    if group == "obelisk_boys":
        return DORM_VOICES["obelisk"][seed % 3]
    if group in ("harbor", "gym", "hotsprings", "plaza"):
        # A location flavour line half the time; the student's dorm voice the rest.
        if seed % 2 == 0:
            voices = GROUP_VOICES.get(group, ())
            if voices:
                return voices[(seed // 2) % len(voices)]
    if dorm == "obelisk" and _is_female(npc):
        return GIRL_VOICES[seed % len(GIRL_VOICES)]
    if dorm in DORM_VOICES:
        return DORM_VOICES[dorm][seed % 3]
    voices = GROUP_VOICES.get(group, GROUP_VOICES["academy"])
    return voices[seed % len(voices)]


def _profile_line(name, seed, female, staff):
    if staff:
        return (
            "I'm %s. I keep this place running while the students duel." % name,
            "%s. If you need something, ask before the bell." % name,
            "I'm %s. Duel Academy has enough distractions without another one." % name,
            "%s. The staff quarters are not open to students, in case you were wondering." % name,
        )[seed % 4]
    return (
        "I'm %s. I transferred in from %s." % (name, HOMETOWNS[seed % len(HOMETOWNS)]),
        "Name's %s. My deck is built around %s." % (name, THEMES[(seed // 7) % len(THEMES)]),
        "I'm %s. You'll usually find me at %s." % (name, CLUBS[(seed // 13) % len(CLUBS)]),
        "%s. Ask me about %s if you want the long version." % (name, TOPICS[(seed // 17) % len(TOPICS)]),
    )[seed % 4]


def _lines_for(entry, seed):
    voice = VOICES.get(entry.get("voice"), VOICES["slifer_underdog"])
    first = entry.get("line") or _profile_line(
        entry["name"], seed, bool(entry.get("female")), bool(entry.get("staff")))
    lines = [first]
    for offset in range(len(voice)):
        line = voice[(seed + offset) % len(voice)]
        if line not in lines:
            lines.append(line)
        if len(lines) == 3:
            break
    return lines


def _hair_for(entry, seed):
    if entry.get("staff"):
        return HAIR_PALETTE[seed % NATURAL_HAIR_COUNT]
    return HAIR_PALETTE[seed % len(HAIR_PALETTE)]


def _generated_name(npc, counters, used):
    female = _is_female(npc)
    staff = _is_staff(npc)
    if staff:
        title = STAFF_TITLES[counters["staff"] % len(STAFF_TITLES)]
        last = LAST_NAMES[(counters["staff"] // len(STAFF_TITLES) + counters["staff"] * 3) % len(LAST_NAMES)]
        name = "%s %s" % (title, last)
    elif female:
        first = FEMALE_FIRST[counters["female"] % len(FEMALE_FIRST)]
        last = LAST_NAMES[(counters["female"] // len(FEMALE_FIRST) + counters["female"] * 5) % len(LAST_NAMES)]
        name = "%s %s" % (first, last)
    else:
        first = MALE_FIRST[counters["male"] % len(MALE_FIRST)]
        last = LAST_NAMES[(counters["male"] // len(MALE_FIRST) + counters["male"] * 7) % len(LAST_NAMES)]
        name = "%s %s" % (first, last)
    while name.casefold() in used:
        if staff:
            counters["staff"] += 1
            title = STAFF_TITLES[counters["staff"] % len(STAFF_TITLES)]
            last = LAST_NAMES[(counters["staff"] // len(STAFF_TITLES) + counters["staff"] * 3) % len(LAST_NAMES)]
            name = "%s %s" % (title, last)
        elif female:
            counters["female"] += 1
            first = FEMALE_FIRST[counters["female"] % len(FEMALE_FIRST)]
            last = LAST_NAMES[(counters["female"] // len(FEMALE_FIRST) + counters["female"] * 5) % len(LAST_NAMES)]
            name = "%s %s" % (first, last)
        else:
            counters["male"] += 1
            first = MALE_FIRST[counters["male"] % len(MALE_FIRST)]
            last = LAST_NAMES[(counters["male"] // len(MALE_FIRST) + counters["male"] * 7) % len(LAST_NAMES)]
            name = "%s %s" % (first, last)
    if staff:
        counters["staff"] += 1
    elif female:
        counters["female"] += 1
    else:
        counters["male"] += 1
    used.add(name.casefold())
    return name


def _entry_for_marker(npc, counters, used):
    seed = _seed(npc)
    staff = _is_staff(npc)
    # Staff markers all use the male base mesh in the layout; alternate the
    # roster's staff identities so the academy has both male and female staff.
    female = (seed % 2 == 0) if staff else _is_female(npc)
    name = _generated_name(npc, counters, used)
    voice = _voice_for(npc, seed)
    if staff:
        voice = STAFF_VOICE_BY_TITLE.get(name.split()[0], voice)
    return dict(
        name=name,
        female=female,
        staff=staff,
        voice=voice,
        id="ambient_%08x" % zlib.crc32(name.casefold().encode("utf-8")),
    )


def assign_uniques(npcs):
    """Annotate every generic (``tint``) marker with a unique identity.

    ``npcs`` is the list from ``layout.json``.  Markers owned by the named cast
    have ``tint == False`` and are left untouched.  The function is idempotent:
    previous roster fields on generic markers are cleared before reassignment.
    """
    generic = [n for n in npcs if n.get("tint", True)]
    for n in generic:
        n.pop("name", None)
        n.pop("lines", None)
        n.pop("hair", None)
        n.pop("roster_id", None)
        n.pop("fab_look", None)
    if not generic:
        return npcs

    markers = sorted(generic, key=_marker_key)
    # Reserve the named cast and every curated name so generated identities can
    # never collide with a curated character, even if that entry goes unused.
    used = {n["name"].casefold() for n in npcs if n.get("name")}
    used.update(entry["name"].casefold() for entry in CURATED)
    assigned = {}
    remaining = [dict(entry) for entry in CURATED]
    for entry in remaining:
        entry.setdefault("id", "curated_%08x" % zlib.crc32(entry["name"].casefold().encode("utf-8")))

    def take(entry, ignore_groups=False):
        for marker in markers:
            if id(marker) in assigned:
                continue
            # Staff markers can host either gender (the build swaps their base
            # mesh to match); student markers must match the entry's gender.
            if not entry.get("staff") and _is_female(marker) != bool(entry.get("female")):
                continue
            if _is_staff(marker) != bool(entry.get("staff")):
                continue
            if entry.get("dorm") and marker.get("dorm") != entry["dorm"]:
                continue
            groups = entry.get("groups") or ()
            if not ignore_groups and groups and marker.get("group") not in groups:
                continue
            assigned[id(marker)] = entry
            used.add(entry["name"].casefold())
            remaining.remove(entry)
            return True
        return False

    # Curated characters with a location preference claim their spot first.
    for entry in list(remaining):
        if entry.get("groups"):
            take(entry)
    # Leftovers fill any compatible marker.
    for entry in list(remaining):
        take(entry, ignore_groups=True)

    counters = dict(male=0, female=0, staff=0)
    for marker in markers:
        if id(marker) not in assigned:
            assigned[id(marker)] = _entry_for_marker(marker, counters, used)

    for marker in markers:
        entry = assigned[id(marker)]
        seed = _seed(marker)
        if entry.get("staff"):
            # Match the base mesh to the identity; cast.assign_npcs recomputes
            # the runtime scale from the final cast id.
            if entry.get("female"):
                marker["cast"] = "student_f1" if seed % 2 == 0 else "student_f2"
            else:
                marker["cast"] = "student_m1"
        marker["name"] = entry["name"]
        marker["roster_id"] = entry["id"]
        groups = entry.get("groups") or ()
        if groups and marker.get("group") not in groups:
            # A curated name that had to spill to another location keeps its
            # name but takes a voice that fits the marker's dorm / group.
            entry = dict(entry, voice=_voice_for(marker, seed), line=None)
        marker["lines"] = _lines_for(entry, seed)
        marker["hair"] = list(_hair_for(entry, seed))
    return npcs
