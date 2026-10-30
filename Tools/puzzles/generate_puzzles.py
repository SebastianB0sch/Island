#!/usr/bin/env python3
"""Generate Duel Academy timed puzzles P021-P100.

The generator is deliberately small and deterministic: ten tactical templates,
two variants per level, levels 2-5. P001-P020 are left untouched.

    python Tools/puzzles/generate_puzzles.py
    python Tools/puzzles/generate_puzzles.py --canon path/to/Canon/puzzles.json
    python Tools/puzzles/generate_puzzles.py --no-canon

The generated setups are port-authored and engine-focused. They do not claim
canon fidelity; when A01's Canon/puzzles.json is present its solution is kept
as reference metadata only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

ROOT_DEFAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TEMPLATES = [
    "direct_attack",
    "tribute_summon",
    "fusion_summon",
    "ritual_summon",
    "spell_removal",
    "trap_negation",
    "position_switch",
    "piercing",
    "burn",
    "special_summon",
]

TIME_BY_LEVEL = {2: 45, 3: 60, 4: 75, 5: 90}


def load_cards(root: str) -> dict[int, dict]:
    with open(os.path.join(root, "DuelAcademyIsland", "Content", "Data", "cards.json"), encoding="utf-8") as handle:
        return {card["id"]: card for card in json.load(handle)}


def mon(card_id: int, position: str = "attack", face_up: bool = True) -> dict:
    return {"card_id": card_id, "position": position, "face_up": face_up}


def st(card_id: int, face_up: bool = False, set_turn: int = 0) -> dict:
    return {"card_id": card_id, "face_up": face_up, "set_turn": set_turn}


def side(lp: int, hand: list[int] | None = None, field: list[dict] | None = None,
         spell_traps: list[dict] | None = None, graveyard: list[int] | None = None,
         deck: list[int] | None = None, extra: list[int] | None = None) -> dict:
    return {
        "lp": lp,
        "hand": list(hand or []),
        "field": list(field or []),
        "spell_traps": list(spell_traps or []),
        "graveyard": list(graveyard or []),
        "deck": list(deck or []),
        "extra": list(extra or []),
    }


def atk_action(card_id: int, target: str | int = "direct") -> dict:
    return {"action": "attack", "attacker_card_id": card_id, "target": target}


def summon_action(card_id: int, tributes: list[int] | None = None) -> dict:
    action = {"action": "normal_summon", "card_id": card_id}
    if tributes:
        action["tribute_card_ids"] = tributes
    return action


def spell_action(card_id: int) -> dict:
    return {"action": "activate_spell", "card_id": card_id}


def trap_action(card_id: int) -> dict:
    return {"action": "activate_trap", "card_id": card_id}


def change_action(card_id: int, position: str = "attack") -> dict:
    return {"action": "change_position", "card_id": card_id, "position": position}


# --------------------------------------------------------------------------
# Template builders: return (player, opponent, solution, notes)
# --------------------------------------------------------------------------

def t_direct(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [([234], 1900), ([780], 1900)],
        3: [([40], 2400), ([363], 2500)],
        4: [([1], 3000), ([18, 234], 4400)],
        5: [([1, 40], 5400), ([1, 363], 5500)],
    }
    ids, lp = table[level][variant]
    player = side(8000, field=[mon(cid) for cid in ids])
    opponent = side(lp)
    solution = [atk_action(cid) for cid in ids]
    names = ", ".join(cards[cid]["name"] for cid in ids)
    return player, opponent, solution, f"Direct attack with {names} for exactly {lp} damage."


def t_tribute(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [
            dict(field=[2], hand=[363], tributes=[2], attacker=363, lp=2500),
            dict(field=[2], hand=[18], tributes=[2], attacker=18, lp=2500),
        ],
        3: [
            dict(field=[2, 165], hand=[40], tributes=[2, 165], attacker=40, lp=2400),
            dict(field=[2, 165], hand=[23], tributes=[2, 165], attacker=23, lp=2500),
        ],
        4: [
            dict(field=[2, 165], hand=[1], tributes=[2, 165], attacker=1, lp=3000),
            dict(field=[2, 165], hand=[1111], tributes=[2, 165], attacker=1111, lp=3000),
        ],
        5: [
            dict(field=[2, 165, 40], hand=[1], tributes=[2, 165], attacker=1, lp=5400, extra=[40]),
            dict(field=[2, 165, 363], hand=[1], tributes=[2, 165], attacker=1, lp=5500, extra=[363]),
        ],
    }
    spec = table[level][variant]
    player = side(8000, hand=spec["hand"], field=[mon(cid) for cid in spec["field"]])
    opponent = side(spec["lp"])
    solution = [summon_action(spec["attacker"], spec["tributes"]), atk_action(spec["attacker"])]
    solution += [atk_action(cid) for cid in spec.get("extra", [])]
    notes = (f"Tribute {', '.join(cards[cid]['name'] for cid in spec['tributes'])} for "
             f"{cards[spec['attacker']]['name']}, then attack for exactly {spec['lp']}.")
    return player, opponent, solution, notes


def t_fusion(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [
            dict(hand=[381, 1106, 1107], extra=[1129], field=[], lp=2100, fusion=1129, spell=381),
            dict(hand=[381, 40, 318], extra=[319], field=[], lp=3500, fusion=319, spell=381),
        ],
        3: [
            dict(hand=[1184], grave=[1106, 1107], extra=[1129], field=[], lp=2100, fusion=1129, spell=1184),
            dict(hand=[381, 1106, 1107], extra=[1129], field=[234], lp=4000, fusion=1129, spell=381),
        ],
        4: [
            dict(hand=[381, 40, 318], extra=[319], field=[1], lp=6500, fusion=319, spell=381),
            dict(hand=[1184], grave=[1106, 1107], extra=[1129], field=[1], lp=5100, fusion=1129, spell=1184),
        ],
        5: [
            dict(hand=[381, 1106, 1107], extra=[1129], field=[1, 40], lp=7500, fusion=1129, spell=381),
            dict(hand=[1184], grave=[1106, 1107], extra=[1129], field=[1, 363], lp=7600, fusion=1129, spell=1184),
        ],
    }
    spec = table[level][variant]
    player = side(8000, hand=spec["hand"], field=[mon(cid) for cid in spec["field"]],
                  graveyard=spec.get("grave", []), extra=spec["extra"])
    opponent = side(spec["lp"])
    solution = [spell_action(spec["spell"]), atk_action(spec["fusion"])]
    solution += [atk_action(cid) for cid in spec["field"]]
    notes = (f"Fusion Summon {cards[spec['fusion']]['name']} with {cards[spec['spell']]['name']}, "
             f"then attack for exactly {spec['lp']}.")
    return player, opponent, solution, notes


def t_ritual(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [
            dict(hand=[843, 841, 2, 165], field=[], lp=2400),
            dict(hand=[843, 841, 234, 195], field=[], lp=2400),
        ],
        3: [
            dict(hand=[843, 841, 2, 165], field=[234], lp=4300),
            dict(hand=[843, 841, 234, 195], field=[363], lp=4900),
        ],
        4: [
            dict(hand=[843, 841, 2, 165], field=[1], lp=5400),
            dict(hand=[843, 841, 234, 195], field=[40], lp=4800),
        ],
        5: [
            dict(hand=[843, 841, 2, 165], field=[1, 40], lp=7800),
            dict(hand=[843, 841, 234, 195], field=[1, 363], lp=7900),
        ],
    }
    spec = table[level][variant]
    player = side(8000, hand=spec["hand"], field=[mon(cid) for cid in spec["field"]])
    opponent = side(spec["lp"])
    solution = [spell_action(843), atk_action(841)]
    solution += [atk_action(cid) for cid in spec["field"]]
    notes = "Ritual Summon Legendary Flame Lord with Incandescent Ordeal, then attack for exact LP."
    return player, opponent, solution, notes


def t_removal(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [
            dict(kind="fissure", field=[234], hand=[379], opp_field=[1], lp=1900),
            dict(kind="fissure", field=[40], hand=[379], opp_field=[363], lp=2400),
        ],
        3: [
            dict(kind="tribute", field=[40], hand=[397, 2], opp_field=[1], lp=2400),
            dict(kind="snatch", field=[40], hand=[428], opp_field=[1], lp=5400),
        ],
        4: [
            dict(kind="heavy", field=[1], hand=[422], opp_spells=[421], lp=3000),
            dict(kind="tribute", field=[1], hand=[397, 2], opp_field=[1111], lp=3000),
        ],
        5: [
            dict(kind="snatch", field=[40], hand=[428], opp_field=[1], lp=5400),
            dict(kind="heavy", field=[1, 40], hand=[422], opp_spells=[421, 547], lp=5400),
        ],
    }
    spec = table[level][variant]
    player = side(8000, hand=spec["hand"], field=[mon(cid) for cid in spec["field"]])
    opponent = side(spec["lp"], field=[mon(cid) for cid in spec.get("opp_field", [])],
                    spell_traps=[st(cid) for cid in spec.get("opp_spells", [])])
    kind = spec["kind"]
    if kind == "fissure":
        solution = [spell_action(379), atk_action(spec["field"][0])]
        notes = f"Fissure removes the only opposing monster; {cards[spec['field'][0]]['name']} attacks directly."
    elif kind == "tribute":
        solution = [spell_action(397), atk_action(spec["field"][0])]
        notes = "Tribute to the Doomed discards the spare card and destroys the opposing monster."
    elif kind == "snatch":
        solution = [spell_action(428), atk_action(1), atk_action(spec["field"][0])]
        notes = "Snatch Steal takes Blue-Eyes; both monsters attack directly for exact LP."
    else:
        solution = [spell_action(422)] + [atk_action(cid) for cid in spec["field"]]
        notes = "Heavy Storm clears the set backrow, then the direct attacks finish the duel."
    return player, opponent, solution, notes


def t_trap(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [([234], 1900), ([780], 1900)],
        3: [([40], 2400), ([363], 2500)],
        4: [([1], 3000), ([18, 234], 4400)],
        5: [([1, 40], 5400), ([1, 363], 5500)],
    }
    ids, lp = table[level][variant]
    player = side(8000, field=[mon(cid) for cid in ids], spell_traps=[st(403)])
    opponent = side(lp, spell_traps=[st(421)])
    solution = [atk_action(cid) for cid in ids]
    notes = ("Seven Tools of the Bandit is already Set; the engine auto-negates Mirror Force "
             "when the lethal direct attack is declared.")
    return player, opponent, solution, notes


def t_position(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [([234], 1900), ([780], 1900)],
        3: [([40], 2400), ([363], 2500)],
        4: [([1], 3000), ([18], 2500)],
        5: [([1, 40], 5400), ([1, 363], 5500)],
    }
    ids, lp = table[level][variant]
    player = side(8000, field=[mon(cid, "defense") for cid in ids])
    opponent = side(lp)
    solution = [change_action(cid, "attack") for cid in ids]
    solution += [atk_action(cid) for cid in ids]
    notes = "Both monsters begin in Defense Position; change to Attack, then attack directly."
    return player, opponent, solution, notes


def t_piercing(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [
            dict(field=[655], opp=[165], hand=[], lp=900),
            dict(field=[655], opp=[2], hand=[117], lp=400),
        ],
        3: [
            dict(field=[655], opp=[37], hand=[117], lp=400),
            dict(field=[655], opp=[2], hand=[593], lp=700),
        ],
        4: [
            dict(field=[655], opp=[37], hand=[117, 593], lp=1200),
            dict(field=[655], opp=[37], hand=[117, 594], lp=1400),
        ],
        5: [
            dict(field=[655], opp=[37], hand=[117, 593, 594], lp=2700),
            dict(field=[655, 2], opp=[2], hand=[117, 593, 594], lp=3500),
        ],
    }
    spec = table[level][variant]
    player = side(8000, hand=spec["hand"], field=[mon(cid) for cid in spec["field"]])
    opponent = side(spec["lp"], field=[mon(cid, "defense") for cid in spec["opp"]])
    solution = [spell_action(cid) for cid in spec["hand"]]
    solution.append(atk_action(655, spec["opp"][0]))
    notes = ("Spear Dragon's built-in piercing damage, boosted by the equipped cards, "
             "deals exact battle damage to the Defense Position monster.")
    return player, opponent, solution, notes


def t_burn(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [
            dict(hand=[148], field=[], traps=[], lp=200, solution=[spell_action(148)]),
            dict(hand=[], field=[11], traps=[1192], lp=1800, solution=[trap_action(1192)]),
        ],
        3: [
            dict(hand=[148], field=[234], traps=[], lp=2100, solution=[spell_action(148), atk_action(234)]),
            dict(hand=[], field=[11, 234], traps=[1192], lp=3700, solution=[trap_action(1192), atk_action(234)]),
        ],
        4: [
            dict(hand=[], field=[11, 1], traps=[1192], lp=4800, solution=[trap_action(1192), atk_action(1)]),
            dict(hand=[], field=[11, 363], traps=[1192], lp=4300, solution=[trap_action(1192), atk_action(363)]),
        ],
        5: [
            dict(hand=[], field=[11, 1, 363], traps=[1192], lp=7300, solution=[trap_action(1192), atk_action(1), atk_action(363)]),
            dict(hand=[148], field=[11, 1], traps=[1192], lp=5000, solution=[spell_action(148), trap_action(1192), atk_action(1)]),
        ],
    }
    spec = table[level][variant]
    player = side(8000, hand=spec["hand"], field=[mon(cid) for cid in spec["field"]],
                  spell_traps=[st(cid) for cid in spec["traps"]])
    opponent = side(spec["lp"])
    notes = "Burn with Sparks / Spiritual Fire Art - Kurenai, then attack for the remaining LP."
    return player, opponent, spec["solution"], notes


def t_special(level: int, variant: int, cards: dict[int, dict]):
    table = {
        2: [
            dict(hand=[477], field=[], grave=[1], opp_grave=[], player_lp=8000, lp=3000, revived=1),
            dict(hand=[477], field=[], grave=[363], opp_grave=[], player_lp=8000, lp=2500, revived=363),
        ],
        3: [
            dict(hand=[766], field=[], grave=[], opp_grave=[363], player_lp=3000, lp=2500, revived=363),
            dict(hand=[477], field=[234], grave=[1], opp_grave=[], player_lp=8000, lp=4900, revived=1),
        ],
        4: [
            dict(hand=[477], field=[40], grave=[1], opp_grave=[], player_lp=8000, lp=5400, revived=1),
            dict(hand=[766], field=[234], grave=[], opp_grave=[1], player_lp=3000, lp=4900, revived=1),
        ],
        5: [
            dict(hand=[477], field=[40, 363], grave=[1], opp_grave=[], player_lp=8000, lp=7900, revived=1),
            dict(hand=[766], field=[40, 234], grave=[], opp_grave=[1], player_lp=3000, lp=7300, revived=1),
        ],
    }
    spec = table[level][variant]
    spell = spec["hand"][0]
    player = side(spec["player_lp"], hand=spec["hand"], field=[mon(cid) for cid in spec["field"]],
                  graveyard=spec["grave"])
    opponent = side(spec["lp"], graveyard=spec["opp_grave"])
    solution = [spell_action(spell), atk_action(spec["revived"])]
    solution += [atk_action(cid) for cid in spec["field"]]
    notes = ("Premature Burial / Autonomous Action Unit revives a monster, then all available "
             "attackers deal exact damage.")
    return player, opponent, solution, notes


BUILDERS = {
    "direct_attack": t_direct,
    "tribute_summon": t_tribute,
    "fusion_summon": t_fusion,
    "ritual_summon": t_ritual,
    "spell_removal": t_removal,
    "trap_negation": t_trap,
    "position_switch": t_position,
    "piercing": t_piercing,
    "burn": t_burn,
    "special_summon": t_special,
}


def build_puzzle(pid: str, level: int, template: str, variant: int,
                 cards: dict[int, dict], canon: dict | None) -> dict:
    player, opponent, solution, notes = BUILDERS[template](level, variant, cards)
    puzzle = {
        "schema_version": 1,
        "id": pid,
        "level": level,
        "title": f"{template.replace('_', ' ').title()} L{level}-{variant + 1}",
        "template": template,
        "opponent": "mimicry",
        "seed": 2000 + int(pid[1:]),
        "turn_limit": 1,
        "time_limit": TIME_BY_LEVEL[level] + (5 if template in {"fusion_summon", "ritual_summon", "piercing"} else 0),
        "objective": "win_this_turn",
        "player": player,
        "opponent_state": opponent,
        "solution": solution,
        "reward": {"dp": 100 + level * 20, "cards": []},
        "engine_ready": True,
        "confidence": "low",
        "source": ("Port-authored setup from Tools/puzzles/generate_puzzles.py "
                   f"template '{template}', level {level}, variant {variant + 1}. "
                   "The line uses engine-supported cards but is not a GBA fixed-board reconstruction."),
        "notes": notes,
    }
    if canon and pid in canon:
        c = canon[pid]
        puzzle["canon_reference"] = {
            "source": "DuelAcademyIsland/Content/Data/Canon/puzzles.json (A01 extraction)",
            "source_url": c.get("source"),
            "setup_status": "canon setup unavailable; this file uses a port-authored template",
            "solution_card_ids": c.get("solution_card_ids", []),
            "solution_card_names": c.get("solution_card_names", []),
            "solution_steps": [step.get("text", "") for step in c.get("solution_steps", [])],
            "confidence": c.get("confidence", {}),
            "note": "Canonical solution metadata only; the generated board/time/reward are not canon.",
        }
    return puzzle


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate P021-P100 for Duel Academy.")
    parser.add_argument("--root", default=ROOT_DEFAULT)
    parser.add_argument("--canon", default="", help="Optional Canon/puzzles.json path")
    parser.add_argument("--no-canon", action="store_true", help="Do not attach canon reference metadata")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    cards = load_cards(root)
    puzzle_dir = os.path.join(root, "DuelAcademyIsland", "Content", "Data", "Puzzles")
    os.makedirs(puzzle_dir, exist_ok=True)

    canon = None
    canon_path = args.canon or os.path.join(root, "DuelAcademyIsland", "Content", "Data", "Canon", "puzzles.json")
    if not args.no_canon and os.path.exists(canon_path):
        with open(canon_path, encoding="utf-8") as handle:
            canon = {p["id"]: p for p in json.load(handle).get("puzzles", [])}

    next_id = 21
    count = 0
    for level in (2, 3, 4, 5):
        for template in TEMPLATES:
            for variant in (0, 1):
                pid = f"P{next_id:03d}"
                puzzle = build_puzzle(pid, level, template, variant, cards, canon)
                # Reject missing card ids immediately; the full validator does more.
                referenced = set(puzzle["player"]["hand"] + puzzle["player"]["graveyard"] + puzzle["player"]["extra"])
                referenced |= set(puzzle["opponent_state"]["graveyard"])
                referenced |= {entry["card_id"] for entry in puzzle["player"]["field"] + puzzle["player"]["spell_traps"]}
                referenced |= {entry["card_id"] for entry in puzzle["opponent_state"]["field"] + puzzle["opponent_state"]["spell_traps"]}
                for cid in referenced:
                    if cid not in cards:
                        raise SystemExit(f"{pid}: unknown card id {cid}")
                with open(os.path.join(puzzle_dir, pid + ".json"), "w", encoding="utf-8") as handle:
                    json.dump(puzzle, handle, indent=2)
                    handle.write("\n")
                count += 1
                next_id += 1

    print(f"wrote {count} puzzles P021-P100 ({len(TEMPLATES)} templates x 2 variants x 4 levels)")
    if canon:
        print(f"attached canon reference metadata from {canon_path}")
    else:
        print("no canon reference metadata attached")
    return 0


if __name__ == "__main__":
    sys.exit(main())
