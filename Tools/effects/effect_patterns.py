"""Card-text patterns that the A04 data-driven effect runtime can execute.

This module is deliberately conservative.  A card is scripted only when the
whole printed effect is covered by a pattern below; partial effects are left
`pending` with a reason.  The same module supplies the pending-reason taxonomy
used by the manifest, the coverage report and the script generator, so all
three outputs agree.

Runtime assumptions are taken from
`Docs/Effects/RUNTIME_INTERFACE.md` and the current `DAEffectRuntime.cpp`:

* `search` always moves the selected card to its owner's hand and optionally
  shuffles the owner's Deck.
* `return_to_deck` places the card on the bottom; a following `shuffle` makes
  that equivalent to "add to Deck, then shuffle".
* `special_summon` places the monster in face-up Attack Position.  Patterns
  that need Defense Position or a face-down Set are not scripted.
* `modify_atk` / `modify_def` in `continuous` scripts only apply to the card
  that owns the script, so team/field-wide continuous boosts are not scripted.
* Generic tribute/discard costs currently resolve deterministically in A04;
  the data still declares the correct target filter.

Only standard-library Python is used.  Import this module from the generator,
the manifest builder, the coverage tool and the validator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

CARD_TYPES = {
    "Normal Monster",
    "Effect Monster",
    "Fusion Monster",
    "Ritual Monster",
    "Spell",
    "Trap",
}

# ---------------------------------------------------------------------------
# DSL helpers
# ---------------------------------------------------------------------------


def _clean(value: dict) -> dict:
    return {key: item for key, item in value.items() if item is not None}


def condition(**kwargs) -> dict:
    return _clean(kwargs)


def all_of(*items: dict | None) -> dict:
    return {"all": [item for item in items if item]}


def any_of(*items: dict | None) -> dict:
    return {"any": [item for item in items if item]}


def target(
    zone: str,
    count: int | str | dict | None = 1,
    filt: dict | None = None,
    chooser: str | None = None,
    optional: bool | None = None,
    reveal: bool | None = None,
) -> dict:
    payload: dict = {"zone": zone}
    if count is not None:
        payload["count"] = count
    if filt:
        payload["filter"] = filt
    if chooser:
        payload["chooser"] = chooser
    if optional is not None:
        payload["optional"] = optional
    if reveal is not None:
        payload["reveal"] = reveal
    return payload


def op(name: str, **kwargs) -> dict:
    return _clean({"op": name, **kwargs})


def discard_cost(count: int = 1) -> dict:
    """A hand-discard cost with an explicit, deterministic source zone."""
    return op("discard", target={"zone": "self_hand", "count": count})


def script(
    script_id: str,
    trigger: str,
    operations: list[dict],
    *,
    condition_payload: dict | None = None,
    cost: list[dict] | None = None,
    target_payload: dict | None = None,
    duration: str = "instant",
    optional: bool = False,
    spell_speed: int = 1,
    once_per_turn: bool = False,
    source_text: str = "",
    notes: list[str] | None = None,
) -> dict:
    payload: dict = {
        "id": script_id,
        "trigger": trigger,
        "operations": operations,
        "duration": duration,
        "optional": optional,
        "spell_speed": spell_speed,
        "once_per_turn": once_per_turn,
    }
    if condition_payload:
        payload["condition"] = condition_payload
    if cost:
        payload["cost"] = cost
    if target_payload:
        payload["target"] = target_payload
    if source_text:
        payload["source_text"] = source_text
    if notes:
        payload["notes"] = notes
    return payload


def _payload(card: dict, tier: int, scripts: list[dict], notes: list[str]) -> dict:
    card_type = card.get("card_type")
    subtype = card.get("subtype")
    card_id = int(card["id"])
    self_event_triggers = {
        "on_summon",
        "on_normal_summon",
        "on_special_summon",
        "on_flip_summon",
        "on_battle_destroy",
        "on_sent_to_graveyard",
        "on_position_change",
        "on_tribute_summon",
    }
    for item in scripts:
        minimum = 1
        if card_type == "Trap":
            minimum = 3 if subtype == "Counter" else 2
        elif subtype == "Quick-Play":
            minimum = 2
        item["spell_speed"] = max(int(item.get("spell_speed", 1)), minimum)
        # FireEvent scans every field card for these triggers.  The current
        # runtime has no "source == event card" condition, so add a same-name
        # guard for monster self-triggers.  It is harmless once A04 gates the
        # event bus by source UID.
        if card_type in {"Effect Monster", "Fusion Monster", "Ritual Monster"} and item["trigger"] in self_event_triggers:
            existing = item.get("condition")
            if not existing:
                item["condition"] = {"name": card["name"]}
            elif "all" in existing and isinstance(existing["all"], list):
                if not any(child.get("name") == card["name"] for child in existing["all"] if isinstance(child, dict)):
                    existing["all"].append({"name": card["name"]})
            elif existing.get("name") != card["name"]:
                item["condition"] = {"all": [existing, {"name": card["name"]}]}
        # Keep script ids globally unique so logs, prompts and review reports
        # can identify one script without needing the card id as context.
        if not item["id"].startswith(f"{card_id}_"):
            item["id"] = f"{card_id}_{item['id']}"
    return {
        "schema_version": 1,
        "card_id": card_id,
        "name": card["name"],
        "card_type": card_type,
        "tier": tier,
        "status": "scripted",
        "source_text": card.get("description") or "",
        "notes": notes,
        "scripts": scripts,
    }


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

_QUOTE_TABLE = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "\u00f0": "",
        "\u00ae": "",
        "\u00a2": "",
    }
)


def normalize(text: str | None) -> str:
    """Collapse whitespace and repair the handful of broken high-bit chars."""
    value = (text or "").translate(_QUOTE_TABLE)
    value = value.replace("\u00f0\u00ae", "").replace("\u00f0", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _sentence(text: str, index: int = 0) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return parts[index] if index < len(parts) else text


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    pattern: re.Pattern[str]
    build: Callable[[dict, int, re.Match[str], str], tuple[list[dict], list[str]] | None]
    notes: str


RECIPES: list[Recipe] = []


def recipe(recipe_id: str, pattern: str, notes: str):
    def decorator(builder):
        RECIPES.append(
            Recipe(recipe_id, re.compile(pattern, re.IGNORECASE), builder, notes)
        )
        return builder

    return decorator


# --- Spells and Traps: direct LP / damage / draw ---------------------------


@recipe(
    "spell_gain_lp",
    r"Increases? your Life Points by (\d+) points?",
    "Normal Spell that only gains Life Points.",
)
def _spell_gain_lp(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "gain_life_points",
                "on_activate",
                [op("gain_lp", amount=amount, player="self", reason=card["name"])],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Single-clause Life Point gain."],
    )


@recipe(
    "spell_gain_lp_both",
    r"(?:Increases? the Life Points of both players by|Increase both your and your opponent's Life Points by) (\d+) points?",
    "Normal Spell that gains Life Points for both players.",
)
def _spell_gain_lp_both(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "gain_life_points_both",
                "on_activate",
                [op("gain_lp", amount=amount, player="both", reason=card["name"])],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Symmetric Life Point gain."],
    )


@recipe(
    "spell_damage_opponent",
    r"(?:Infl(?:i|ic)ts? \d+ points? of Direct Damage to your opponent's Life Points|Decrease your opponent's Life Points by \d+ points)",
    "Single-clause effect damage to the opponent.",
)
def _spell_damage_opponent(card, tier, match, text):
    amount = int(re.search(r"(\d+)", text).group(1))
    return (
        [
            script(
                "damage_opponent",
                "on_activate",
                [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Single-clause burn."],
    )


@recipe(
    "tremendous_fire",
    r"Inflicts? 1000 points of Direct Damage to your opponent's Life Points and 500 points of Direct Damage to your Life Points",
    "Fixed two-sided burn (Tremendous Fire).",
)
def _tremendous_fire(card, tier, match, text):
    return (
        [
            script(
                "tremendous_fire",
                "on_activate",
                [
                    op("inflict_damage", amount=1000, player="opponent", reason=card["name"]),
                    op("inflict_damage", amount=500, player="self", reason=card["name"]),
                ],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Two fixed damage operations; opponent first, then self."],
    )


@recipe(
    "goblin_thief",
    r"Inflict 500 points of damage to your opponent's Life Points and increase your Life Points by 500 points",
    "Fixed damage plus fixed Life Point gain (Goblin Thief).",
)
def _goblin_thief(card, tier, match, text):
    return (
        [
            script(
                "goblin_thief",
                "on_activate",
                [
                    op("inflict_damage", amount=500, player="opponent", reason=card["name"]),
                    op("gain_lp", amount=500, player="self", reason=card["name"]),
                ],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Fixed burn plus fixed heal."],
    )


@recipe(
    "draw_fixed",
    r"Draw (\d+) cards? from your Deck",
    "Draw a fixed number of cards.",
)
def _draw_fixed(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "draw_cards",
                "on_activate",
                [op("draw", count=amount, player="self", reason=card["name"])],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Fixed draw."],
    )


# --- Spells and Traps: destruction -----------------------------------------


@recipe(
    "destroy_all_typed",
    r"Destroys? all (?:face-up )?([A-Za-z-]+)-Type monsters on the field",
    "Destroy every monster of one Type.",
)
def _destroy_all_typed(card, tier, match, text):
    monster_type = match.group(1)
    face_up = bool(re.search(r"face-up", text, re.I))
    filt = condition(monster_type=monster_type, card_type="Monster")
    if face_up:
        filt = all_of(filt, condition(face_up=True))
    return (
        [
            script(
                "destroy_type",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target("all_monsters", "all", filt),
                spell_speed=1,
                source_text=text,
            )
        ],
        [f"All {monster_type} monsters are destroyed."],
    )


@recipe(
    "destroy_opponent_monsters",
    r"Destroys? all of your opponent's monsters on the field",
    "Destroy all opponent monsters.",
)
def _destroy_opponent_monsters(card, tier, match, text):
    return (
        [
            script(
                "destroy_opponent_monsters",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target("opponent_monster", "all"),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Board wipe against the opponent."],
    )


@recipe(
    "destroy_all_monsters",
    r"Destroys? all monsters on the field",
    "Destroy every monster.",
)
def _destroy_all_monsters(card, tier, match, text):
    return (
        [
            script(
                "destroy_all_monsters",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target("all_monsters", "all"),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Symmetric monster wipe."],
    )


@recipe(
    "destroy_opponent_spell_traps",
    r"Destroys? all of your opponent's Spell and Trap Cards on the field",
    "Destroy all opponent Spell/Trap cards.",
)
def _destroy_opponent_spell_traps(card, tier, match, text):
    return (
        [
            script(
                "destroy_opponent_spell_traps",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target("opponent_spell_trap", "all"),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Symmetric Spell/Trap wipe against the opponent."],
    )


@recipe(
    "destroy_one_faceup_trap",
    r"Destroys? 1 face-up Trap Card on the field",
    "Destroy one face-up Trap Card.",
)
def _destroy_one_faceup_trap(card, tier, match, text):
    return (
        [
            script(
                "destroy_trap",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target(
                    "any_spell_trap", 1, all_of(condition(card_type="Trap"), condition(face_up=True))
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Targets a face-up Trap."],
    )


@recipe(
    "destroy_one_defense_monster",
    r"Select 1 Monster in Defense Position on the Field and destroy it",
    "Destroy one Defense Position monster.",
)
def _destroy_one_defense_monster(card, tier, match, text):
    return (
        [
            script(
                "destroy_defense_monster",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target(
                    "any_monster", 1, all_of(condition(position="defense"), condition(face_up=True))
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Targets a face-up Defense Position monster."],
    )


# --- Spells and Traps: position changes ------------------------------------


@recipe(
    "position_opponent_attack_to_defense",
    r"Select 1 of your opponent's face-up Attack Position monsters and shift it to Defense Position",
    "Change one opponent Attack Position monster to Defense.",
)
def _position_opponent_attack_to_defense(card, tier, match, text):
    return (
        [
            script(
                "change_to_defense",
                "on_activate",
                [op("change_position", target="$target", position="defense")],
                target_payload=target(
                    "opponent_monster", 1, all_of(condition(position="attack"), condition(face_up=True))
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["No damage calculation is involved."],
    )


@recipe(
    "position_all_faceup_defense",
    r"All face-up monsters on the field are changed to Defense Position",
    "Change every face-up monster to Defense.",
)
def _position_all_faceup_defense(card, tier, match, text):
    return (
        [
            script(
                "change_all_to_defense",
                "on_activate",
                [op("change_position", target="$target", position="defense")],
                target_payload=target("all_monsters", "all", condition(face_up=True)),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Symmetric position change."],
    )


@recipe(
    "position_own_faceup_defense",
    r"All monsters on your side of the field are changed to face-up Defense Position",
    "Change all own monsters to face-up Defense.",
)
def _position_own_faceup_defense(card, tier, match, text):
    return (
        [
            script(
                "change_own_to_defense",
                "on_activate",
                [op("change_position", target="$target", position="defense")],
                target_payload=target("self_monster", "all"),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Own monsters only."],
    )


# --- Spells and Traps: fixed ATK/DEF modifiers -----------------------------


def _stat_script(card, text, stat: str, amount: int, source: str, *, quick: bool = False):
    return script(
        stat,
        "on_activate",
        [op(f"modify_{stat}", target="$target", amount=amount, mode="flat")],
        target_payload=target("any_monster", 1),
        duration="until_end_of_turn",
        spell_speed=2 if quick else 1,
        source_text=source,
    )


@recipe(
    "modify_one_monster_atk",
    r"(?:Increase 1 monster's ATK by (\d+) points during the turn this card is activated|Increase 1 selected monster's ATK by (\d+) points during the turn this card is activated)",
    "Fixed ATK boost until end of turn.",
)
def _modify_one_monster_atk(card, tier, match, text):
    amount = int(match.group(1) or match.group(2))
    return (
        [
            script(
                "boost_atk",
                "on_activate",
                [op("modify_atk", target="$target", amount=amount, mode="flat")],
                target_payload=target("any_monster", 1),
                duration="until_end_of_turn",
                spell_speed=2 if card.get("subtype") == "Quick-Play" else 1,
                source_text=text,
            )
        ],
        ["Single-target ATK boost until the end of the turn."],
    )


@recipe(
    "modify_one_monster_def",
    r"Increase 1 face-up monster's DEF by (\d+) points until the end of this turn",
    "Fixed DEF boost until end of turn.",
)
def _modify_one_monster_def(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "boost_def",
                "on_activate",
                [op("modify_def", target="$target", amount=amount, mode="flat")],
                target_payload=target(
                    "any_monster", 1, all_of(condition(face_up=True))
                ),
                duration="until_end_of_turn",
                spell_speed=2 if card.get("subtype") == "Quick-Play" else 1,
                source_text=text,
            )
        ],
        ["Single-target DEF boost until the end of the turn."],
    )


@recipe(
    "trap_boost_atk",
    r"Increase 1 selected monster's ATK by (\d+) points during the turn this card is activated",
    "Fixed ATK boost from a Normal Trap.",
)
def _trap_boost_atk(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "boost_atk",
                "on_activate",
                [op("modify_atk", target="$target", amount=amount, mode="flat")],
                target_payload=target("any_monster", 1),
                duration="until_end_of_turn",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Single-target ATK boost until the end of the turn."],
    )


@recipe(
    "trap_boost_def",
    r"Increase a selected monster's DEF by (\d+) points during the turn this card is activated",
    "Fixed DEF boost from a Normal Trap.",
)
def _trap_boost_def(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "boost_def",
                "on_activate",
                [op("modify_def", target="$target", amount=amount, mode="flat")],
                target_payload=target("any_monster", 1),
                duration="until_end_of_turn",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Single-target DEF boost until the end of the turn."],
    )


@recipe(
    "trap_reduce_def",
    r"Decrease 1 selected monster's DEF by (\d+) points during the turn this card is activated",
    "Fixed DEF reduction from a Normal Trap.",
)
def _trap_reduce_def(card, tier, match, text):
    amount = -int(match.group(1))
    return (
        [
            script(
                "reduce_def",
                "on_activate",
                [op("modify_def", target="$target", amount=amount, mode="flat")],
                target_payload=target("any_monster", 1),
                duration="until_end_of_turn",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Single-target DEF reduction until the end of the turn."],
    )


@recipe(
    "trap_reduce_attacker_atk",
    r"This card can only be activated in the Battle Phase. Select 1 attacking monster and decrease the selected monster's ATK by (\d+) points during the turn this card is activated",
    "Battle-phase ATK reduction on the attacker.",
)
def _trap_reduce_attacker_atk(card, tier, match, text):
    amount = -int(match.group(1))
    return (
        [
            script(
                "weaken_attacker",
                "on_attack_declared",
                [op("modify_atk", target="$target", amount=amount, mode="flat")],
                target_payload=target("attacking_monster", 1),
                duration="until_end_of_turn",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Selects the attacking monster and reduces ATK until the end of the turn."],
    )


# --- Spells and Traps: search / hand manipulation --------------------------


@recipe(
    "search_field_spell",
    r"Add 1 Field Spell Card from your Deck to your hand. Then shuffle your Deck",
    "Search a Field Spell.",
)
def _search_field_spell(card, tier, match, text):
    return (
        [
            script(
                "search_field_spell",
                "on_activate",
                [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
                target_payload=target(
                    "self_deck", 1, all_of(condition(card_type="Spell"), condition(subtype="Field"))
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Searches a Field Spell into the hand and shuffles."],
    )


@recipe(
    "search_named_card",
    r"(?:Add|Take) 1 \"([^\"]+)\" (?:card )?from your Deck(?: to your hand)?(?: and add it(?: to)? your hand)?(?:\. )?(?:The Deck is then shuffled|Then shuffle your Deck)?",
    "Search a card with a fixed name.",
)
def _search_named_card(card, tier, match, text):
    name = match.group(1)
    return (
        [
            script(
                "search_named",
                "on_activate",
                [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
                target_payload=target("self_deck", 1, condition(name=name)),
                spell_speed=1,
                source_text=text,
            )
        ],
        [f"Searches '{name}' from the Deck."],
    )


@recipe(
    "search_warrior_level4",
    r"Move 1 Level 4 or lower Warrior-Type monster from your Deck to your hand. Your Deck is then shuffled",
    "Search a Level 4 or lower Warrior.",
)
def _search_warrior_level4(card, tier, match, text):
    return (
        [
            script(
                "search_warrior",
                "on_activate",
                [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
                target_payload=target(
                    "self_deck",
                    1,
                    all_of(
                        condition(card_type="Monster"),
                        condition(monster_type="Warrior"),
                        condition(level_max=4),
                    ),
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Searches a Level 4 or lower Warrior."],
    )


@recipe(
    "return_two_hand_to_deck",
    r"Return 2 cards from your hand to your Deck. Then shuffle your Deck",
    "Return two hand cards to the Deck.",
)
def _return_two_hand_to_deck(card, tier, match, text):
    return (
        [
            script(
                "return_hand_to_deck",
                "on_activate",
                [
                    op("return_to_deck", target="$target", shuffle=True),
                    op("shuffle", player="self"),
                ],
                target_payload=target("self_hand", 2),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Bottom placement followed by a shuffle is equivalent to the printed effect."],
    )


@recipe(
    "opponent_hand_to_deck",
    r"Look at your opponent's hand, then select 1 card and return it to his/her Deck. The Deck is then shuffled",
    "Return one opponent hand card to the Deck.",
)
def _opponent_hand_to_deck(card, tier, match, text):
    return (
        [
            script(
                "return_opponent_hand_card",
                "on_activate",
                [
                    op("return_to_deck", target="$target", shuffle=True),
                    op("shuffle", player="opponent"),
                ],
                target_payload=target("opponent_hand", 1, chooser="controller"),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["The hand is revealed by the target prompt; the card goes to the bottom and the Deck is shuffled."],
    )


@recipe(
    "pay_lp_discard_opponent_hand",
    r"Pay 1000 Life Points to look at your opponent's hand. Select 1 card and discard it to the Graveyard",
    "Pay 1000 LP, then discard one opponent hand card.",
)
def _pay_lp_discard_opponent_hand(card, tier, match, text):
    return (
        [
            script(
                "confiscation",
                "on_activate",
                [op("discard", target="$target", reason=card["name"])],
                cost=[op("pay_lp", amount=1000)],
                target_payload=target("opponent_hand", 1),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Cost is paid before the hand is revealed."],
    )


@recipe(
    "discard_up_to_three_monsters",
    r"You can discard up to 3 Monster Cards from your hand to the Graveyard",
    "Discard up to three monsters.",
)
def _discard_up_to_three_monsters(card, tier, match, text):
    return (
        [
            script(
                "discard_up_to_three_monsters",
                "on_activate",
                [op("discard", target="$target", player="self", reason=card["name"])],
                target_payload=target(
                    "self_hand", {"min": 0, "max": 3}, condition(card_type="Monster"), optional=True
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Up to three monsters; zero is legal."],
    )


@recipe(
    "pay_lp_banish_machine",
    r"Pay 1000 Life Points. Remove from play all Machine-Type monsters on your opponent's side of the field and in their Graveyard",
    "Pay 1000 LP; banish opponent Machines on the field and in the Graveyard.",
)
def _pay_lp_banish_machine(card, tier, match, text):
    return (
        [
            script(
                "system_down",
                "on_activate",
                [
                    op("banish", target={"zone": "opponent_monster", "count": "all", "filter": condition(monster_type="Machine")}),
                    op(
                        "banish",
                        target={
                            "zone": "opponent_graveyard",
                            "count": "all",
                            "filter": all_of(condition(card_type="Monster"), condition(monster_type="Machine")),
                        },
                    ),
                ],
                cost=[op("pay_lp", amount=1000)],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Two inline all-candidate selectors, one per zone."],
    )


# --- Spells and Traps: discard costs ---------------------------------------


def _discard_cost(card, text, operations: list[dict], target_payload=None):
    return script(
        "discard_cost_effect",
        "on_activate",
        operations,
        cost=[discard_cost(1)],
        target_payload=target_payload,
        spell_speed=1,
        source_text=text,
    )


@recipe(
    "discard_destroy_all_faceup_opponent_monsters",
    r"Discard 1 card from your hand. Destroy all face-up monsters on your opponent's side of the field",
    "Discard one card; destroy all face-up opponent monsters.",
)
def _discard_destroy_faceup_opp(card, tier, match, text):
    s = _discard_cost(
        card,
        text,
        [op("destroy", target="$target", reason=card["name"])],
        target("opponent_monster", "all", condition(face_up=True)),
    )
    return [s], ["Discard cost, then a one-sided face-up monster wipe."]


@recipe(
    "discard_destroy_continuous_traps",
    r"Discard 1 card from your hand. Destroy all face-up Continuous Trap Cards on the field",
    "Discard one card; destroy face-up Continuous Traps.",
)
def _discard_destroy_continuous_traps(card, tier, match, text):
    s = _discard_cost(
        card,
        text,
        [op("destroy", target="$target", reason=card["name"])],
        target(
            "all_spell_traps",
            "all",
            all_of(condition(card_type="Trap"), condition(subtype="Continuous"), condition(face_up=True)),
        ),
    )
    return [s], ["Discard cost, then all face-up Continuous Traps are destroyed."]


@recipe(
    "discard_destroy_continuous_spells",
    r"Discard 1 card from your hand. Destroy all face-up Continuous Spell Cards on the field",
    "Discard one card; destroy face-up Continuous Spells.",
)
def _discard_destroy_continuous_spells(card, tier, match, text):
    s = _discard_cost(
        card,
        text,
        [op("destroy", target="$target", reason=card["name"])],
        target(
            "all_spell_traps",
            "all",
            all_of(condition(card_type="Spell"), condition(subtype="Continuous"), condition(face_up=True)),
        ),
    )
    return [s], ["Discard cost, then all face-up Continuous Spells are destroyed."]


@recipe(
    "discard_destroy_one_card",
    r"Discard 1 card from your hand to the Graveyard to destroy 1 card on the field",
    "Discard one card; destroy one card.",
)
def _discard_destroy_one_card(card, tier, match, text):
    s = _discard_cost(
        card,
        text,
        [op("destroy", target="$target", reason=card["name"])],
        target("all_cards", 1),
    )
    return [s], ["Discard cost, then one field card is destroyed."]


@recipe(
    "discard_return_monster_to_hand",
    r"Discard 1 card from your hand. Return 1 monster on the field to the top of the owner's Deck",
    "Discard one card; return a monster to the top of the Deck.",
)
def _discard_return_monster_to_hand(card, tier, match, text):
    # The printed card says top of the Deck; the runtime only supports bottom
    # placement, so this recipe intentionally does not build a payload.
    return None


@recipe(
    "final_destiny",
    r"Discard 5 cards from your hand to destroy all the cards on the field",
    "Discard five cards; destroy the whole field.",
)
def _final_destiny(card, tier, match, text):
    return (
        [
            script(
                "final_destiny",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                cost=[discard_cost(5)],
                target_payload=target("all_cards", "all"),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Five-card discard cost, then every field card is destroyed."],
    )


# --- Spells and Traps: graveyard manipulation ------------------------------


@recipe(
    "banish_two_opponent_grave_monsters",
    r"Select 2 Monster Cards from your opponent's Graveyard. These Monster Cards are removed from play for the remainder of the Duel",
    "Banish two monsters from the opponent Graveyard.",
)
def _banish_two_opponent_grave_monsters(card, tier, match, text):
    return (
        [
            script(
                "banish_grave_monsters",
                "on_activate",
                [op("banish", target="$target", reason=card["name"])],
                target_payload=target(
                    "opponent_graveyard", 2, condition(card_type="Monster")
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Two monster cards from the opponent Graveyard are banished."],
    )


@recipe(
    "banish_one_opponent_grave_card",
    r"Select 1 card from your opponent's Graveyard and remove it from play",
    "Banish one card from the opponent Graveyard.",
)
def _banish_one_opponent_grave_card(card, tier, match, text):
    return (
        [
            script(
                "banish_grave_card",
                "on_activate",
                [op("banish", target="$target", reason=card["name"])],
                target_payload=target("opponent_graveyard", 1),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["One opponent Graveyard card is banished."],
    )


@recipe(
    "banish_up_to_five_grave_cards",
    r"Select up to 5 cards from either you or your opponent's Graveyard and remove them from the current Duel",
    "Banish up to five cards from either Graveyard.",
)
def _banish_up_to_five_grave_cards(card, tier, match, text):
    return (
        [
            script(
                "soul_release",
                "on_activate",
                [op("banish", target="$target", reason=card["name"])],
                target_payload=target("graveyard", {"min": 0, "max": 5}, optional=True),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Both Graveyards are candidates; zero to five cards."],
    )


@recipe(
    "send_deck_monster_to_grave",
    r"Select one Monster from your Deck and send it to the Graveyard. Afterward, shuffle your Deck",
    "Send a chosen monster from the Deck to the Graveyard.",
)
def _send_deck_monster_to_grave(card, tier, match, text):
    return (
        [
            script(
                "foolish_burial",
                "on_activate",
                [
                    op("send_to_graveyard", target="$target", reason=card["name"]),
                    op("shuffle", player="self"),
                ],
                target_payload=target("self_deck", 1, condition(card_type="Monster")),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Uses the runtime's selected-card send-to-Graveyard operation."],
    )


# --- Spells and Traps: attack-response traps -------------------------------


@recipe(
    "calamity_of_the_wicked",
    r"Can be activated when your opponent's Monster attacks. Destroys all Spell and Trap cards on the Field",
    "Attack-response trap that destroys all Spell/Trap cards.",
)
def _calamity_of_the_wicked(card, tier, match, text):
    return (
        [
            script(
                "calamity",
                "on_attack_declared",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=condition(controller="opponent"),
                target_payload=target("all_spell_traps", "all"),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Triggers on the opponent's attack declaration."],
    )


@recipe(
    "dark_mirror_force",
    r"You can only activate this card when your opponent's monster declares an attack. Remove all monsters in Defense Position on your opponent's side of the field from play",
    "Attack-response trap that banishes all opponent Defense Position monsters.",
)
def _dark_mirror_force(card, tier, match, text):
    return (
        [
            script(
                "dark_mirror_force",
                "on_attack_declared",
                [op("banish", target="$target", reason=card["name"])],
                condition_payload=condition(controller="opponent"),
                target_payload=target(
                    "opponent_monster",
                    "all",
                    all_of(condition(position="defense"), condition(face_up=True)),
                ),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Triggers on the opponent's attack declaration."],
    )


@recipe(
    "destruction_ring",
    r"Destroy 1 face-up monster on your side of the field to inflict 1000 points of damage to both players' Life Points",
    "Destroy an own monster and burn both players.",
)
def _destruction_ring(card, tier, match, text):
    return (
        [
            script(
                "destruction_ring",
                "on_activate",
                [
                    op("destroy", target="$target", reason=card["name"]),
                    op("inflict_damage", amount=1000, player="both", reason=card["name"]),
                ],
                target_payload=target(
                    "self_monster", 1, all_of(condition(face_up=True))
                ),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Destroy first, then both players take 1000."],
    )


@recipe(
    "assault_on_ghq",
    r"Select 1 monster on your side of the field to activate this card. Destroy the selected card and send 2 cards from the top of your opponent's Deck to the Graveyard",
    "Destroy an own monster and mill two opponent cards.",
)
def _assault_on_ghq(card, tier, match, text):
    return (
        [
            script(
                "assault_on_ghq",
                "on_activate",
                [
                    op("destroy", target="$target", reason=card["name"]),
                    op("mill", count=2, player="opponent", reason=card["name"]),
                ],
                target_payload=target("self_monster", 1),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Destroy then mill; both are fixed operations."],
    )


# --- Spells and Traps: continuous locks ------------------------------------


@recipe(
    "royal_decree",
    r"As long as this card remains face-up on the field, negate the effects of all Trap Cards except this card on the field",
    "Continuous Trap that negates Trap effects while face-up.",
)
def _royal_decree(card, tier, match, text):
    return (
        [
            script(
                "royal_decree_lock",
                "continuous",
                [
                    op(
                        "lock_activation",
                        target={
                            "zone": "all_spell_traps",
                            "count": "all",
                            "filter": condition(card_type="Trap"),
                        },
                        mode="trap_activation_and_effects",
                    )
                ],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_spell_trap"
                ),
                duration="while_face_up",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Uses the same trap lock primitive as Jinzo."],
    )


# ---------------------------------------------------------------------------
# Monster recipes
# ---------------------------------------------------------------------------


def _monster_condition(**kwargs) -> dict:
    base = {"controller": "self", "face_up": True, "zone": "self_monster"}
    base.update(kwargs)
    return base


@recipe(
    "flip_fixed_damage",
    r"FLIP: Inflict (\d+) points of Direct Damage to your opponent's Life Points",
    "FLIP effect with fixed burn.",
)
def _flip_fixed_damage(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "flip_damage",
                "on_flip",
                [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
                condition_payload=_monster_condition(),
                source_text=text,
            )
        ],
        ["FLIP burn."],
    )


@recipe(
    "flip_destroy_defense_monster",
    r"FLIP: Destroy 1 Defense Position monster on the field",
    "FLIP effect that destroys one Defense Position monster.",
)
def _flip_destroy_defense_monster(card, tier, match, text):
    return (
        [
            script(
                "flip_destroy_defense",
                "on_flip",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target(
                    "any_monster", 1, all_of(condition(position="defense"), condition(face_up=True))
                ),
                source_text=text,
            )
        ],
        ["Targets a face-up Defense Position monster."],
    )


@recipe(
    "flip_destroy_any_monster",
    r"FLIP: Destroys? 1 monster on the field \(regardless of position\)",
    "FLIP effect that destroys one monster.",
)
def _flip_destroy_any_monster(card, tier, match, text):
    return (
        [
            script(
                "flip_destroy_monster",
                "on_flip",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target("any_monster", 1),
                source_text=text,
            )
        ],
        ["Any monster, regardless of position."],
    )


@recipe(
    "flip_draw_one",
    r"FLIP: You can draw 1 card from your deck",
    "Optional FLIP draw.",
)
def _flip_draw_one(card, tier, match, text):
    return (
        [
            script(
                "flip_draw",
                "on_flip",
                [op("draw", count=1, player="self", reason=card["name"])],
                condition_payload=_monster_condition(),
                optional=True,
                source_text=text,
            )
        ],
        ["Optional FLIP draw."],
    )


@recipe(
    "flip_destroy_level4_opponents",
    r"FLIP: Destroys all face-up Level 4 monsters on your opponent's side of the field",
    "FLIP effect that destroys all face-up Level 4 opponent monsters.",
)
def _flip_destroy_level4_opponents(card, tier, match, text):
    return (
        [
            script(
                "flip_destroy_level_four",
                "on_flip",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target(
                    "opponent_monster",
                    "all",
                    all_of(condition(face_up=True), condition(level_min=4), condition(level_max=4)),
                ),
                source_text=text,
            )
        ],
        ["Level 4 is checked through the effective level."],
    )


@recipe(
    "flip_trap_grave_to_hand",
    r"FLIP: Select 1 Trap Card from your Graveyard and return it to your hand",
    "FLIP effect that returns a Trap from the Graveyard.",
)
def _flip_trap_grave_to_hand(card, tier, match, text):
    return (
        [
            script(
                "flip_trap_to_hand",
                "on_flip",
                [op("return_to_hand", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target("self_graveyard", 1, condition(card_type="Trap")),
                source_text=text,
            )
        ],
        ["Trap card only."],
    )


@recipe(
    "flip_opponent_monster_to_hand",
    r"FLIP: Select 1 Monster Card on your opponent's side of the field \(regardless of position\) and return it to its owner's hand",
    "FLIP effect that bounces one opponent monster.",
)
def _flip_opponent_monster_to_hand(card, tier, match, text):
    return (
        [
            script(
                "flip_bounce_monster",
                "on_flip",
                [op("return_to_hand", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target("opponent_monster", 1),
                source_text=text,
            )
        ],
        ["Any opponent monster, regardless of position."],
    )


@recipe(
    "flip_grave_card_to_deck",
    r"FLIP: Select 1 card from your Graveyard and add it to your Deck. Then shuffle your Deck",
    "FLIP effect that recycles one Graveyard card.",
)
def _flip_grave_card_to_deck(card, tier, match, text):
    return (
        [
            script(
                "flip_recycle_grave",
                "on_flip",
                [
                    op("return_to_deck", target="$target", reason=card["name"]),
                    op("shuffle", player="self"),
                ],
                condition_payload=_monster_condition(),
                target_payload=target("self_graveyard", 1),
                source_text=text,
            )
        ],
        ["Bottom placement followed by a shuffle."],
    )


@recipe(
    "flip_return_up_to_three",
    r"FLIP: You can return up to (\d+) monsters on the field to the owner's hand",
    "FLIP effect that bounces up to three monsters.",
)
def _flip_return_up_to_three(card, tier, match, text):
    count = int(match.group(1))
    return (
        [
            script(
                "flip_bounce_monsters",
                "on_flip",
                [op("return_to_hand", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target("any_monster", {"min": 0, "max": count}, optional=True),
                optional=True,
                source_text=text,
            )
        ],
        ["Zero to three monsters; the controller chooses."],
    )


@recipe(
    "flip_banish_grave_monster",
    r"FLIP: Select 1 Monster Card from you or your opponent's Graveyard. Remove it from play",
    "FLIP effect that banishes one monster from either Graveyard.",
)
def _flip_banish_grave_monster(card, tier, match, text):
    return (
        [
            script(
                "flip_banish_grave_monster",
                "on_flip",
                [op("banish", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target("graveyard", 1, condition(card_type="Monster")),
                source_text=text,
            )
        ],
        ["Either Graveyard is eligible."],
    )


@recipe(
    "flip_summon_normal_from_grave",
    r"FLIP: You can Special Summon 1 Level 3 or lower Normal Monster from your Graveyard to your side of the field",
    "FLIP effect that revives a Level 3 or lower Normal Monster.",
)
def _flip_summon_normal_from_grave(card, tier, match, text):
    return (
        [
            script(
                "flip_revive_normal",
                "on_flip",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=_monster_condition(),
                target_payload=target(
                    "self_graveyard",
                    1,
                    all_of(
                        condition(card_type="Normal Monster"),
                        condition(level_max=3),
                    ),
                ),
                optional=True,
                source_text=text,
            )
        ],
        ["Revived in face-up Attack Position (the runtime's fixed special-summon position)."],
    )


@recipe(
    "flip_destroy_spell_or_trap",
    r"FLIP: Destroys? 1 (Spell|Trap) Card on the field",
    "FLIP effect that destroys one Spell or Trap.",
)
def _flip_destroy_spell_or_trap(card, tier, match, text):
    card_type = match.group(1)
    return (
        [
            script(
                f"flip_destroy_{card_type.lower()}",
                "on_flip",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target("any_spell_trap", 1, condition(card_type=card_type)),
                source_text=text,
            )
        ],
        [f"Only {card_type} cards can be selected (face-down cards are known to the engine)."],
    )


@recipe(
    "flip_search_equip_spell",
    r"FLIP: Select 1 Equip Spell Card from your Deck and add it to your hand",
    "FLIP effect that searches an Equip Spell.",
)
def _flip_search_equip_spell(card, tier, match, text):
    return (
        [
            script(
                "flip_search_equip",
                "on_flip",
                [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
                condition_payload=_monster_condition(),
                target_payload=target(
                    "self_deck",
                    1,
                    all_of(condition(card_type="Spell"), condition(subtype="Equip")),
                ),
                optional=True,
                source_text=text,
            )
        ],
        ["Searches an Equip Spell and shuffles."],
    )


@recipe(
    "flip_flip_monster_down_except_self",
    r'FLIP: Flip 1 face-up monster on the field into face-down Defense Position. You cannot select "([^"]+)"',
    "FLIP effect that turns one other monster face-down.",
)
def _flip_flip_monster_down_except_self(card, tier, match, text):
    excluded = match.group(1)
    return (
        [
            script(
                "flip_turn_monster_down",
                "on_flip",
                [op("change_position", target="$target", position="face_down")],
                condition_payload=_monster_condition(),
                target_payload=target(
                    "any_monster",
                    1,
                    all_of(condition(face_up=True), {"not": condition(name=excluded)}),
                ),
                source_text=text,
            )
        ],
        [f"Excludes '{excluded}' via a negated name filter."],
    )


# --- Monster: hand / LP costs ----------------------------------------------


@recipe(
    "flip_pay_lp_damage",
    r"FLIP: You can inflict (\d+) points of Direct Damage to your opponent's Life Points at the cost of (\d+) of your own Life Points",
    "FLIP effect that pays Life Points for fixed burn.",
)
def _flip_pay_lp_damage(card, tier, match, text):
    damage, cost = int(match.group(1)), int(match.group(2))
    return (
        [
            script(
                "flip_pay_life_for_damage",
                "on_flip",
                [op("inflict_damage", amount=damage, player="opponent", reason=card["name"])],
                condition_payload=_monster_condition(),
                cost=[op("pay_lp", amount=cost)],
                optional=True,
                source_text=text,
            )
        ],
        ["Life Point payment is a cost, so it is checked before damage."],
    )


@recipe(
    "manual_flip_down",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase",
    "Ignition effect that sets itself face-down once per turn.",
)
def _manual_flip_down(card, tier, match, text):
    return (
        [
            script(
                "manual_set_self",
                "manual",
                [op("change_position", target="$self", position="face_down")],
                condition_payload=condition(
                    controller="self",
                    face_up=True,
                    zone="self_monster",
                    custom="ignition_main_phase",
                ),
                once_per_turn=True,
                source_text=text,
            )
        ],
        ["One ignition script; the runtime enforces once-per-turn."],
    )


@recipe(
    "simple_normal_summon_no_traps",
    r"When this card is Normal Summoned successfully, no Trap Cards can be activated",
    "Normal-summon Trap lock.",
)
def _simple_normal_summon_no_traps(card, tier, match, text):
    # The printed lock is not a one-shot; modelling it as a continuous lock
    # would incorrectly apply before the summon.  Leave it pending.
    return None


@recipe(
    "battle_damage_zero_self",
    r"Battle Damage to this card's controller that he/she takes from a battle involving this card becomes 0",
    "Continuous battle-damage protection for this card's controller.",
)
def _battle_damage_zero_self(card, tier, match, text):
    return (
        [
            script(
                "battle_damage_zero",
                "continuous",
                [op("battle_damage_zero", target="$self")],
                condition_payload=_monster_condition(),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Card-specific battle-damage zero."],
    )


@recipe(
    "continuous_self_atk_empty_hand",
    r"While you have no cards in your hand, increase the ATK of this card by (\d+) points",
    "Continuous self ATK boost while the hand is empty.",
)
def _continuous_self_atk_empty_hand(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "attack_boost_empty_hand",
                "continuous",
                [op("modify_atk", target="$self", amount=amount, mode="flat")],
                condition_payload=_monster_condition(hand_max=0),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Continuous self boost; the condition is re-evaluated by the runtime."],
    )


@recipe(
    "standby_damage",
    r"During each of your Standby Phases, inflict (\d+) points of damage to your opponent's Life Points",
    "Standby Phase fixed burn.",
)
def _standby_damage(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "standby_damage",
                "on_standby",
                [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
                condition_payload=_monster_condition(turn="self"),
                source_text=text,
            )
        ],
        ["Fires only on the controller's Standby Phase."],
    )


@recipe(
    "standby_heal",
    r"(?:As long as this card remains face-up on your side of the field, )?increase your Life Points by (\d+) points during each of your Standby Phases",
    "Standby Phase fixed Life Point gain.",
)
def _standby_heal(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "standby_heal",
                "on_standby",
                [op("gain_lp", amount=amount, player="self", reason=card["name"])],
                condition_payload=_monster_condition(turn="self"),
                source_text=text,
            )
        ],
        ["Fires only on the controller's Standby Phase."],
    )


@recipe(
    "standby_atk_gain_self",
    r"During each Standby Phase on your turn, this card's ATK is raised by (\d+) points",
    "Standby Phase permanent self ATK gain.",
)
def _standby_atk_gain_self(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "standby_attack_gain",
                "on_standby",
                [op("modify_atk", target="$self", amount=amount, mode="flat")],
                condition_payload=_monster_condition(turn="self"),
                duration="permanent",
                source_text=text,
            )
        ],
        ["Lingering ATK gain on the controller's Standby Phase."],
    )


@recipe(
    "standby_tribute_self_destroy_two",
    r"Offer this card as a Tribute during your Standby Phase if face-up to destroy 2 face-up monsters with an ATK of 1000 or less",
    "Standby Phase optional self-tribute removal.",
)
def _standby_tribute_self_destroy_two(card, tier, match, text):
    return (
        [
            script(
                "standby_tribute_destroy",
                "on_standby",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(turn="self"),
                cost=[op("tribute", target="$self")],
                target_payload=target(
                    "all_monsters",
                    2,
                    all_of(
                        condition(face_up=True),
                        condition(atk_max=1000),
                        {"not": condition(name=card["name"])},
                    ),
                ),
                optional=True,
                source_text=text,
            )
        ],
        ["Self-tribute cost; targets two other face-up monsters with ATK <= 1000."],
    )


# --- Monster: battle-destruction recruiters --------------------------------


def _recruit_payload(card, tier, text, filter_payload, *, optional=True, note=""):
    return (
        [
            script(
                "battle_recruit",
                "on_battle_destroy",
                [
                    op("special_summon", target="$target", position="attack"),
                    op("shuffle", player="self"),
                ],
                target_payload=target("self_deck", 1, filter_payload),
                optional=optional,
                source_text=text,
            )
        ],
        [note] if note else [],
    )


def _recruit_attribute(card, tier, match, text):
    attribute = match.group(1).upper()
    limit = int(match.group(2))
    return _recruit_payload(
        card,
        tier,
        text,
        all_of(condition(card_type="Monster"), condition(attribute=attribute), condition(atk_max=limit)),
        note=f"Recruits a {attribute} monster with ATK <= {limit} in face-up Attack Position.",
    )


RECIPES.append(
    Recipe(
        "battle_recruit_attribute",
        re.compile(
            r"When this card is sent to the Graveyard as a result of battle, you can (?:Special Summon|select) 1 "
            r"(DARK|LIGHT|EARTH|WATER|FIRE|WIND) monster with an ATK of (\d+) or less "
            r"(?:in face-up Attack Position from your Deck(?: and Special Summon it to the field in face-up Attack Position"
            r" \(no Tribute is required for monsters of Level 5 or more\))?)"
            r"\.? (?:Then shuffle your Deck|The Deck is then shuffled)",
            re.IGNORECASE,
        ),
        _recruit_attribute,
        "Battle-destruction recruiter filtered by Attribute and ATK.",
    )
)

def _recruit_type(card, tier, match, text):
    monster_type = match.group(1)
    limit = int(match.group(2))
    return _recruit_payload(
        card,
        tier,
        text,
        all_of(
            condition(card_type="Monster"),
            condition(monster_type=monster_type),
            condition(atk_max=limit),
        ),
        note=f"Recruits a {monster_type} monster with ATK <= {limit} in face-up Attack Position.",
    )


RECIPES.append(
    Recipe(
        "battle_recruit_type",
        re.compile(
            r"When this card (?:is sent to the Graveyard as a result of battle|is destroyed and sent to the Graveyard as a result of battle), "
            r"you (?:can|may) (?:select|Special Summon) 1 (Dragon|Insect|Machine)-Type monster with an ATK of (\d+) or less "
            r"(?:to your side of the field )?from your Deck\.? (?:Then shuffle your Deck|The Deck is then shuffled)",
            re.IGNORECASE,
        ),
        _recruit_type,
        "Battle-destruction recruiter filtered by Type and ATK.",
    )
)


@recipe(
    "battle_recruit_earth_warrior",
    r"When this card is destroyed in battle and sent to the Graveyard, you may Special Summon an EARTH Warrior type Monster with (\d+) ATK or less from the Deck to be placed face up on your field. Shuffle your Deck afterwards",
    "Battle-destruction recruiter for an EARTH Warrior.",
)
def _battle_recruit_earth_warrior(card, tier, match, text):
    limit = int(match.group(1))
    return _recruit_payload(
        card,
        tier,
        text,
        all_of(
            condition(card_type="Monster"),
            condition(attribute="EARTH"),
            condition(monster_type="Warrior"),
            condition(atk_max=limit),
        ),
        note=f"Recruits an EARTH Warrior with ATK <= {limit}.",
    )


@recipe(
    "battle_recruit_hyena",
    r'When this card is sent to the Graveyard as a result of battle, you can Special Summon any "([^"]+)"\(s\) from your Deck to the field. Then shuffle your Deck',
    "Battle-destruction recruiter for every copy of a named card.",
)
def _battle_recruit_hyena(card, tier, match, text):
    name = match.group(1)
    return (
        [
            script(
                "battle_recruit_all_named",
                "on_battle_destroy",
                [
                    op("special_summon", target="$target", position="attack"),
                    op("shuffle", player="self"),
                ],
                target_payload=target("self_deck", "all", condition(name=name)),
                optional=True,
                source_text=text,
            )
        ],
        [f"Recruits every '{name}' from the Deck."],
    )


# --- Monster: Graveyard triggers -------------------------------------------


@recipe(
    "grave_self_heal",
    r"When this card is sent to the Graveyard, increase your Life Points by (\d+) points",
    "Graveyard trigger with fixed Life Point gain.",
)
def _grave_self_heal(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "grave_gain_life",
                "on_sent_to_graveyard",
                [op("gain_lp", amount=amount, player="self", reason=card["name"])],
                source_text=text,
            )
        ],
        ["Fires when this card reaches the Graveyard from any zone."],
    )


@recipe(
    "grave_opponent_heal",
    r"When this card is sent to the Graveyard, increase your opponent's Life Points by (\d+) points",
    "Graveyard trigger that heals the opponent.",
)
def _grave_opponent_heal(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "grave_heal_opponent",
                "on_sent_to_graveyard",
                [op("gain_lp", amount=amount, player="opponent", reason=card["name"])],
                source_text=text,
            )
        ],
        ["Fires when this card reaches the Graveyard from any zone."],
    )


@recipe(
    "grave_recycle_deck",
    r"When this card is sent to your Graveyard, it is returned to your Deck. Then shuffle your Deck",
    "Graveyard trigger that shuffles itself back into the Deck.",
)
def _grave_recycle_deck(card, tier, match, text):
    return (
        [
            script(
                "grave_recycle_self",
                "on_sent_to_graveyard",
                [
                    op("return_to_deck", target="$self", reason=card["name"]),
                    op("shuffle", player="self"),
                ],
                source_text=text,
            )
        ],
        ["Bottom placement followed by a shuffle."],
    )


@recipe(
    "hand_to_grave_recycle",
    r"When this card is sent directly from your hand to the Graveyard, add this card to the Deck and shuffle it",
    "Hand-to-Graveyard trigger that recycles itself.",
)
def _hand_to_grave_recycle(card, tier, match, text):
    # The runtime cannot distinguish "directly from the hand" from a card
    # sent from the field, so this effect is intentionally left pending.
    return None


@recipe(
    "sent_from_field_search_def",
    r"When this card is sent from the field to the Graveyard, move 1 monster with a DEF of (\d+) or less from your Deck to your hand. Your Deck is then shuffled",
    "Sent-from-field search filtered by DEF.",
)
def _sent_from_field_search_def(card, tier, match, text):
    limit = int(match.group(1))
    return (
        [
            script(
                "sent_search_def",
                "on_sent_to_graveyard",
                [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
                condition_payload=all_of(
                    condition(controller="self"),
                    condition(zone="self_monster"),
                    condition(custom="sent_from_field_to_graveyard"),
                ),
                target_payload=target(
                    "self_deck",
                    1,
                    all_of(condition(card_type="Monster"), condition(def_max=limit)),
                ),
                optional=True,
                source_text=text,
            )
        ],
        [f"Searches a monster with DEF <= {limit}."],
    )


@recipe(
    "sent_from_field_summon_insect_hand",
    r"When this card on your side of the field is sent to the Graveyard, you can Special Summon 1 Insect-Type Monster from your hand",
    "Sent-from-field trigger that summons an Insect from the hand.",
)
def _sent_from_field_summon_insect_hand(card, tier, match, text):
    return (
        [
            script(
                "sent_summon_insect",
                "on_sent_to_graveyard",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=all_of(
                    condition(controller="self"),
                    condition(zone="self_monster"),
                    condition(custom="sent_from_field_to_graveyard"),
                ),
                target_payload=target(
                    "self_hand",
                    1,
                    all_of(condition(card_type="Monster"), condition(monster_type="Insect")),
                ),
                optional=True,
                source_text=text,
            )
        ],
        ["The Insect is summoned in face-up Attack Position."],
    )


@recipe(
    "battle_grave_return_two_opponent",
    r"When this card is destroyed and sent to the Graveyard as a result of battle, select 2 cards from your opponent's Graveyard and return them to your opponent's Deck. Your opponent then shuffles his/her Deck",
    "Battle-destruction trigger that recycles two opponent Graveyard cards.",
)
def _battle_grave_return_two_opponent(card, tier, match, text):
    return (
        [
            script(
                "battle_recycle_opponent_grave",
                "on_battle_destroy",
                [
                    op("return_to_deck", target="$target", reason=card["name"]),
                    op("shuffle", player="opponent"),
                ],
                target_payload=target("opponent_graveyard", 2),
                source_text=text,
            )
        ],
        ["Two cards are placed on the bottom and the opponent's Deck is shuffled."],
    )


@recipe(
    "battle_destroy_one_monster",
    r"When this card is sent to the Graveyard as a result of battle, select 1 monster on the field and destroy it",
    "Battle-destruction trigger that destroys one monster.",
)
def _battle_destroy_one_monster(card, tier, match, text):
    return (
        [
            script(
                "battle_destroy_monster",
                "on_battle_destroy",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target("any_monster", 1),
                source_text=text,
            )
        ],
        ["Any monster on the field is a legal target."],
    )


@recipe(
    "battle_destroy_damage_fixed",
    r"When this card is (?:destroyed and sent to the Graveyard|sent to the Graveyard) as a result of battle, inflict (\d+) points of damage to your opponent's Life Points",
    "Battle-destruction trigger with fixed burn.",
)
def _battle_destroy_damage_fixed(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "battle_destroy_damage",
                "on_battle_destroy",
                [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
                source_text=text,
            )
        ],
        ["Fires when this card is destroyed by battle."],
    )


@recipe(
    "battle_destroy_destroy_all_spell_traps",
    r"(?:This card can only be Special Summoned by removing 1 EARTH monster in your Graveyard from play. )?When this card is destroyed and sent to the Graveyard as a result of battle, destroy all Spell and Trap Cards on the field",
    "Battle-destruction trigger that destroys all Spell/Trap cards.",
)
def _battle_destroy_destroy_all_spell_traps(card, tier, match, text):
    return (
        [
            script(
                "battle_destroy_spell_traps",
                "on_battle_destroy",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target("all_spell_traps", "all"),
                source_text=text,
            )
        ],
        ["The summoning condition is rules text; the script covers the destruction trigger."],
    )


@recipe(
    "battle_destroy_summon_troop_dragon",
    r"When this card is destroyed and sent to the Graveyard, take 1 \"([^\"]+)\" from your Deck and Special Summon it to the field in face-up Attack or Defense Position. The Deck is then shuffled",
    "Battle/Graveyard trigger that recruits a named card in a chosen position.",
)
def _battle_destroy_summon_troop_dragon(card, tier, match, text):
    # Position choice (Attack or Defense) is not available in the current
    # special_summon operation.
    return None


@recipe(
    "normal_summon_special_hand_named",
    r"When (?:this monster|this card) is Normal Summoned successfully, you can Special Summon 1 \"([^\"]+)\" from your hand",
    "Normal-summon trigger that summons a named card from the hand.",
)
def _normal_summon_special_hand_named(card, tier, match, text):
    name = match.group(1)
    return (
        [
            script(
                "normal_summon_special_named",
                "on_normal_summon",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=condition(controller="self", zone="self_monster"),
                target_payload=target("self_hand", 1, condition(name=name)),
                optional=True,
                source_text=text,
            )
        ],
        [f"Special Summons '{name}' from the hand in Attack Position."],
    )


@recipe(
    "normal_or_flip_summon_any_number_named",
    r"When this card is Normal Summoned or Flip Summoned successfully, you can Special Summon any number of \"([^\"]+)\"\(s\) from your hand",
    "Normal/Flip summon trigger that summons every copy from the hand.",
)
def _normal_or_flip_summon_any_number_named(card, tier, match, text):
    name = match.group(1)

    def make(trigger: str):
        return script(
            f"{trigger}_special_all_named",
            trigger,
            [op("special_summon", target="$target", position="attack")],
            condition_payload=condition(controller="self", zone="self_monster"),
            target_payload=target(
                "self_hand", {"min": 0, "max": 10}, condition(name=name), optional=True
            ),
            optional=True,
            source_text=text,
        )

    return ([make("on_normal_summon"), make("on_flip_summon")], [f"Summons any number of '{name}'."])


@recipe(
    "normal_or_flip_summon_search_ritual",
    r"When this card is (?:Normal Summoned or Flip Summoned|summoned to the field \(excluding Special Summon\)), you (?:can|may) (?:select|move) 1 Ritual (Monster|Spell) Card(?: or 1 Ritual (?:Monster|Spell) Card)? from your Deck and add it to your hand",
    "Normal/Flip summon trigger that searches a Ritual card.",
)
def _normal_or_flip_summon_search_ritual(card, tier, match, text):
    first = match.group(1)
    if "or 1 Ritual" in text:
        filter_payload = any_of(
            condition(card_type="Ritual Monster"),
            all_of(condition(card_type="Spell"), condition(subtype="Ritual")),
        )
    elif first == "Monster":
        filter_payload = condition(card_type="Ritual Monster")
    else:
        filter_payload = all_of(condition(card_type="Spell"), condition(subtype="Ritual"))

    def make(trigger: str):
        return script(
            f"{trigger}_search_ritual",
            trigger,
            [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
            condition_payload=condition(controller="self", zone="self_monster"),
            target_payload=target("self_deck", 1, filter_payload),
            optional=True,
            source_text=text,
        )

    return ([make("on_normal_summon"), make("on_flip_summon")], ["Searches a Ritual card from the Deck."])


@recipe(
    "normal_or_flip_summon_search_named",
    r"When this card is summoned \(excluding Special Summon\), you can add 1 \"([^\"]+)\" from your Deck to your hand",
    "Normal/Flip summon trigger that searches a named card.",
)
def _normal_or_flip_summon_search_named(card, tier, match, text):
    name = match.group(1)

    def make(trigger: str):
        return script(
            f"{trigger}_search_named",
            trigger,
            [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
            condition_payload=condition(controller="self", zone="self_monster"),
            target_payload=target("self_deck", 1, condition(name=name)),
            optional=True,
            source_text=text,
        )

    return ([make("on_normal_summon"), make("on_flip_summon")], [f"Searches '{name}'."])


@recipe(
    "any_summon_search_named",
    r"When this card is Summoned or Special Summoned successfully, you may add one \"([^\"]+)\" card from your Deck to your Hand",
    "Any-summon trigger that searches a named Gadget.",
)
def _any_summon_search_named(card, tier, match, text):
    name = match.group(1)
    return (
        [
            script(
                "summon_search_named",
                "on_summon",
                [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
                condition_payload=condition(controller="self", zone="self_monster"),
                target_payload=target("self_deck", 1, condition(name=name)),
                optional=True,
                source_text=text,
            )
        ],
        [f"Searches '{name}' from the Deck."],
    )


@recipe(
    "normal_or_flip_summon_destroy_dragon",
    r"When this card is Summoned \(excluding Special Summon\), destroy 1 face-up Dragon-Type monster on the field",
    "Normal/Flip summon trigger that destroys a face-up Dragon.",
)
def _normal_or_flip_summon_destroy_dragon(card, tier, match, text):
    def make(trigger: str):
        return script(
            f"{trigger}_destroy_dragon",
            trigger,
            [op("destroy", target="$target", reason=card["name"])],
            condition_payload=condition(controller="self", zone="self_monster"),
            target_payload=target(
                "any_monster", 1, all_of(condition(face_up=True), condition(monster_type="Dragon"))
            ),
            source_text=text,
        )

    return ([make("on_normal_summon"), make("on_flip_summon")], ["Destroys a face-up Dragon."])


@recipe(
    "summon_trigger_fixed_damage",
    r"When this monster is Normal Summoned, Flip Summoned, or Special Summoned, inflict (\d+) points of Direct Damage to your opponent's Life Points",
    "Any-summon trigger with fixed burn.",
)
def _summon_trigger_fixed_damage(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "summon_damage",
                "on_summon",
                [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
                condition_payload=condition(controller="self", zone="self_monster"),
                source_text=text,
            )
        ],
        ["Fires on Normal, Flip and Special Summon."],
    )


@recipe(
    "special_summon_draw_one",
    r"When this card is Special Summoned, the controller of this card draws 1 card",
    "Special-summon trigger that draws one card.",
)
def _special_summon_draw_one(card, tier, match, text):
    return (
        [
            script(
                "special_summon_draw",
                "on_special_summon",
                [op("draw", count=1, player="self", reason=card["name"])],
                condition_payload=condition(controller="self", zone="self_monster"),
                source_text=text,
            )
        ],
        ["Fires only on Special Summon."],
    )


@recipe(
    "tribute_self_summon_named_hand",
    r"Tribute this card to Special Summon 1 \"([^\"]+)\" from your hand",
    "Ignition effect with a self-tribute cost.",
)
def _tribute_self_summon_named_hand(card, tier, match, text):
    name = match.group(1)
    return (
        [
            script(
                "tribute_self_summon_named",
                "manual",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[op("tribute", target="$self")],
                target_payload=target("self_hand", 1, condition(name=name)),
                source_text=text,
            )
        ],
        [f"Tributing the source is the cost for summoning '{name}'."],
    )


@recipe(
    "send_self_summon_named_hand",
    r"Send this face-up card on your side of the field to the Graveyard to Special Summon 1 \"([^\"]+)\" from your hand",
    "Ignition effect with a send-self-to-Graveyard cost.",
)
def _send_self_summon_named_hand(card, tier, match, text):
    name = match.group(1)
    return (
        [
            script(
                "send_self_summon_named",
                "manual",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[op("send_to_graveyard", target="$self")],
                target_payload=target("self_hand", 1, condition(name=name)),
                source_text=text,
            )
        ],
        [f"Sending the source to the Graveyard is the cost for summoning '{name}'."],
    )


@recipe(
    "tribute_monsters_burn",
    r"Offer (\d+) monsters? on your side of the field as a Tribute to inflict (\d+) points of Direct Damage to your opponent's Life Points(?:\. Monsters used for a Tribute Summon or that are offered as Tributes due to other cards' effects are excluded)?",
    "Ignition effect that tributes monsters for fixed burn.",
)
def _tribute_monsters_burn(card, tier, match, text):
    if card.get("card_type") not in {"Effect Monster", "Fusion Monster", "Ritual Monster"}:
        return None
    tributes, damage = int(match.group(1)), int(match.group(2))
    return (
        [
            script(
                "tribute_burn",
                "manual",
                [op("inflict_damage", amount=damage, player="opponent", reason=card["name"])],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[op("tribute", target={"zone": "self_monster", "count": tributes})],
                source_text=text,
            )
        ],
        [f"Tributes {tributes} monster(s) as a cost for {damage} damage."],
    )


@recipe(
    "tribute_typed_monster_burn",
    r"Offer 1 ([A-Za-z-]+)-Type monster on your side of the field as a Tribute to inflict (\d+) points of damage to your opponent's Life Points",
    "Ignition effect that tributes a typed monster for fixed burn.",
)
def _tribute_typed_monster_burn(card, tier, match, text):
    monster_type, damage = match.group(1), int(match.group(2))
    return (
        [
            script(
                "tribute_typed_burn",
                "manual",
                [op("inflict_damage", amount=damage, player="opponent", reason=card["name"])],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[
                    op(
                        "tribute",
                        target={
                            "zone": "self_monster",
                            "count": 1,
                            "filter": condition(monster_type=monster_type),
                        },
                    )
                ],
                source_text=text,
            )
        ],
        [f"Tributing a {monster_type} monster is the cost for {damage} damage."],
    )


@recipe(
    "tribute_normal_monster_burn",
    r"Offer 1 Normal Monster \(except a Token\) on your side of the field as a Tribute to inflict (\d+) points of damage to your opponent's Life Points",
    "Ignition effect that tributes a Normal Monster for fixed burn.",
)
def _tribute_normal_monster_burn(card, tier, match, text):
    damage = int(match.group(1))
    return (
        [
            script(
                "tribute_normal_burn",
                "manual",
                [op("inflict_damage", amount=damage, player="opponent", reason=card["name"])],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[
                    op(
                        "tribute",
                        target={
                            "zone": "self_monster",
                            "count": 1,
                            "filter": condition(card_type="Normal Monster"),
                        },
                    )
                ],
                source_text=text,
            )
        ],
        [f"Tributing a Normal Monster is the cost for {damage} damage."],
    )


@recipe(
    "tribute_two_heal",
    r"Offer 2 monsters on your side of the field as a Tribute to increase your Life Points by (\d+) points(?:\. Monsters used for a Tribute Summon or that are offered as Tributes due to other cards' effects are excluded)?",
    "Ignition effect that tributes two monsters for fixed healing.",
)
def _tribute_two_heal(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "tribute_heal",
                "manual",
                [op("gain_lp", amount=amount, player="self", reason=card["name"])],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[op("tribute", target={"zone": "self_monster", "count": 2})],
                source_text=text,
            )
        ],
        [f"Two tributes are the cost for {amount} Life Points."],
    )


@recipe(
    "pay_lp_return_named_grave",
    r"At the cost of (\d+) Life Points, you can return \"([^\"]+)\" from the Graveyard to your hand",
    "Ignition effect that pays Life Points to return a named card.",
)
def _pay_lp_return_named_grave(card, tier, match, text):
    cost, name = int(match.group(1)), match.group(2)
    return (
        [
            script(
                "pay_life_return_named",
                "manual",
                [op("return_to_hand", target="$target", reason=card["name"])],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[op("pay_lp", amount=cost)],
                target_payload=target("self_graveyard", 1, condition(name=name)),
                source_text=text,
            )
        ],
        [f"Pays {cost} LP to return '{name}'."],
    )


@recipe(
    "pay_lp_summon_fusion",
    r"At the cost of (\d+) of your own Life Points, you can Special Summon 1 Fusion Monster from your Fusion Deck in face-up Attack Position",
    "Ignition effect that pays Life Points to summon a Fusion Monster.",
)
def _pay_lp_summon_fusion(card, tier, match, text):
    cost = int(match.group(1))
    return (
        [
            script(
                "pay_life_summon_fusion",
                "manual",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[op("pay_lp", amount=cost)],
                target_payload=target("self_extra", 1, condition(card_type="Fusion Monster")),
                source_text=text,
            )
        ],
        [f"Pays {cost} LP and summons a Fusion Monster from the Extra Deck."],
    )


@recipe(
    "ddm_summon_banished",
    r"Discard 1 Spell Card from your hand. Special Summon 1 of your monsters that is currently removed from play. You can only activate this effect once per turn, during your Main Phase",
    "Ignition effect that discards a Spell to revive a banished monster.",
)
def _ddm_summon_banished(card, tier, match, text):
    return (
        [
            script(
                "discard_spell_revive_banished",
                "manual",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[
                    op(
                        "discard",
                        target={
                            "zone": "self_hand",
                            "count": 1,
                            "filter": condition(card_type="Spell"),
                        },
                    )
                ],
                target_payload=target("self_banished", 1, condition(card_type="Monster")),
                once_per_turn=True,
                source_text=text,
            )
        ],
        ["Discarding a Spell is the cost; the banished monster returns in Attack Position."],
    )


@recipe(
    "spell_counter_library",
    r"Each time you or your opponent activates 1 Spell Card, put 1 Spell Counter on this card \(max\. 3\). Remove 3 Spell Counters from this card to draw 1 card from your Deck",
    "Spell-counter engine with a manual counter-removal draw.",
)
def _spell_counter_library(card, tier, match, text):
    # on_chain scripts are considered even while the monster is face-down.
    return None


@recipe(
    "spell_counter_marionette",
    r"Each time you or your opponent activates 1 Spell Card, put 1 Spell Counter on this card. Increase the ATK of this card by 200 points for each Spell Counter on this card. Also, remove 2 Spell Counters from this card to destroy 1 monster on the field",
    "Spell-counter monster with a continuous ATK bonus and manual removal.",
)
def _spell_counter_marionette(card, tier, match, text):
    # on_chain scripts are considered even while the monster is face-down.
    return None


@recipe(
    "normal_summon_counter_trap",
    r"When this card is Summoned successfully, place 1 Spell Counter on it \(maximum of 1\). Remove the Spell Counter to destroy one face-up Trap Card in the Field",
    "Normal-summon counter placement plus a manual trap removal.",
)
def _normal_summon_counter_trap(card, tier, match, text):
    return (
        [
            script(
                "summon_place_counter",
                "on_summon",
                [op("add_counter", target="$self", counter="spell", amount=1, max=1)],
                condition_payload=condition(controller="self", zone="self_monster"),
                source_text="When this card is Summoned successfully, place 1 Spell Counter on it (maximum of 1).",
            ),
            script(
                "spend_counter_destroy_trap",
                "manual",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=condition(
                    controller="self",
                    face_up=True,
                    zone="self_monster",
                    has_counter={"counter": "spell", "min": 1},
                    custom="ignition_main_phase",
                ),
                cost=[op("remove_counter", target="$self", counter="spell", count=1)],
                target_payload=target(
                    "any_spell_trap", 1, all_of(condition(card_type="Trap"), condition(face_up=True))
                ),
                source_text="Remove the Spell Counter to destroy one face-up Trap Card.",
            ),
        ],
        ["Counter placement and a manual counter-removal trap removal."],
    )


# --- Trap: fixed-cost attack / hand effects --------------------------------


@recipe(
    "trap_raigeki_break",
    r"Discard 1 card from your hand to the Graveyard to destroy 1 card on the field",
    "Trap that discards one card to destroy one field card.",
)
def _trap_raigeki_break(card, tier, match, text):
    return (
        [
            script(
                "discard_destroy_one",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                cost=[discard_cost(1)],
                target_payload=target("all_cards", 1),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Discard cost, then one field card is destroyed."],
    )


@recipe(
    "trap_rising_energy",
    r"Discard 1 card from your hand. Increase the ATK of 1 face-up monster on the field by 1500 points until the End Phase of this turn",
    "Trap that discards one card for a large temporary ATK boost.",
)
def _trap_rising_energy(card, tier, match, text):
    return (
        [
            script(
                "discard_boost_attack",
                "on_activate",
                [op("modify_atk", target="$target", amount=1500, mode="flat")],
                cost=[discard_cost(1)],
                target_payload=target("any_monster", 1, condition(face_up=True)),
                duration="until_end_of_turn",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Discard cost, then a temporary ATK boost."],
    )


@recipe(
    "offerings_to_the_doomed",
    r"Destroys 1 face-up monster. Skip your next Draw Phase",
    "Spell that destroys one face-up monster and skips the next draw.",
)
def _offerings_to_the_doomed(card, tier, match, text):
    return (
        [
            script(
                "destroy_and_skip_draw",
                "on_activate",
                [
                    op("destroy", target="$target", reason=card["name"]),
                    op("skip_phase", player="self", mode="draw"),
                ],
                target_payload=target("any_monster", 1, condition(face_up=True)),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["The runtime's skip_phase currently implements the next Draw Phase skip."],
    )


# --- Spell: selected-card graveyard sends ----------------------------------


@recipe(
    "rock_bombardment",
    r"Select 1 Rock-Type monster in your Deck and send it to the Graveyard. Inflict (\d+) points of damage to your opponent's Life Points. The Deck is then shuffled",
    "Trap that sends a Rock monster from the Deck to the Graveyard and burns.",
)
def _rock_bombardment(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "send_rock_and_burn",
                "on_activate",
                [
                    op("send_to_graveyard", target="$target", reason=card["name"]),
                    op("inflict_damage", amount=amount, player="opponent", reason=card["name"]),
                    op("shuffle", player="self"),
                ],
                target_payload=target(
                    "self_deck",
                    1,
                    all_of(condition(card_type="Monster"), condition(monster_type="Rock")),
                ),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Selected Deck card is sent to the Graveyard, then the Deck is shuffled."],
    )


@recipe(
    "graveyard_to_hand_two_normal",
    r"Select 2 Normal Monsters from your Graveyard and add them to your hand",
    "Spell that returns two Normal Monsters from the Graveyard.",
)
def _graveyard_to_hand_two_normal(card, tier, match, text):
    return (
        [
            script(
                "return_two_normal_monsters",
                "on_activate",
                [op("return_to_hand", target="$target", reason=card["name"])],
                target_payload=target(
                    "self_graveyard", 2, condition(card_type="Normal Monster")
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Exactly two Normal Monsters."],
    )


@recipe(
    "graveyard_to_hand_warrior",
    r"Select 1 Warrior-Type monster in your Graveyard and return it to your hand",
    "Spell that returns one Warrior from the Graveyard.",
)
def _graveyard_to_hand_warrior(card, tier, match, text):
    return (
        [
            script(
                "return_warrior",
                "on_activate",
                [op("return_to_hand", target="$target", reason=card["name"])],
                target_payload=target(
                    "self_graveyard",
                    1,
                    all_of(condition(card_type="Monster"), condition(monster_type="Warrior")),
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["One Warrior-Type monster."],
    )


@recipe(
    "graveyard_to_deck_two_spells",
    r"Select 2 Spell Cards from your Graveyard and add them to your Deck. Your Deck is then shuffled",
    "Trap that recycles two Spells.",
)
def _graveyard_to_deck_two_spells(card, tier, match, text):
    return (
        [
            script(
                "recycle_two_spells",
                "on_activate",
                [
                    op("return_to_deck", target="$target", reason=card["name"]),
                    op("shuffle", player="self"),
                ],
                target_payload=target("self_graveyard", 2, condition(card_type="Spell")),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Two Spells go to the bottom and the Deck is shuffled."],
    )


@recipe(
    "graveyard_to_deck_two_light",
    r"Select 2 LIGHT monsters from your Graveyard and add them to your Deck. Then shuffle your Deck",
    "Trap that recycles two LIGHT monsters.",
)
def _graveyard_to_deck_two_light(card, tier, match, text):
    return (
        [
            script(
                "recycle_two_light_monsters",
                "on_activate",
                [
                    op("return_to_deck", target="$target", reason=card["name"]),
                    op("shuffle", player="self"),
                ],
                target_payload=target(
                    "self_graveyard",
                    2,
                    all_of(condition(card_type="Monster"), condition(attribute="LIGHT")),
                ),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Two LIGHT monsters go to the bottom and the Deck is shuffled."],
    )


@recipe(
    "spell_reproduction",
    r"Send 2 Spell Cards from your hand to the Graveyard. Select 1 Spell Card from your Graveyard and add it to your hand",
    "Spell that trades two hand Spells for one Graveyard Spell.",
)
def _spell_reproduction(card, tier, match, text):
    return (
        [
            script(
                "recycle_spell",
                "on_activate",
                [op("return_to_hand", target="$target", reason=card["name"])],
                cost=[
                    op(
                        "discard",
                        target={
                            "zone": "self_hand",
                            "count": 2,
                            "filter": condition(card_type="Spell"),
                        },
                    )
                ],
                target_payload=target("self_graveyard", 1, condition(card_type="Spell")),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Two hand Spells are the cost; one Graveyard Spell returns to the hand."],
    )


# ---------------------------------------------------------------------------
# Monster: manual flip-down plus a Flip Summon trigger
# ---------------------------------------------------------------------------


def _manual_flip_scripts(card, text, flip_script: dict) -> tuple[list[dict], list[str]]:
    manual = script(
        "manual_set_self",
        "manual",
        [op("change_position", target="$self", position="face_down")],
        condition_payload=condition(
            controller="self",
            face_up=True,
            zone="self_monster",
            custom="ignition_main_phase",
        ),
        once_per_turn=True,
        source_text=_sentence(text, 0),
    )
    return [manual, flip_script], ["One ignition set-self script plus one Flip Summon trigger."]


@recipe(
    "manual_flip_guardian_statue",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase. When this card is Flip Summoned successfully, return 1 monster on your opponent's side of the field to the owner's hand",
    "Manual set-self plus Flip Summon bounce.",
)
def _manual_flip_guardian_statue(card, tier, match, text):
    return _manual_flip_scripts(
        card,
        text,
        script(
            "flip_summon_bounce",
            "on_flip_summon",
            [op("return_to_hand", target="$target", reason=card["name"])],
            condition_payload=_monster_condition(),
            target_payload=target("opponent_monster", 1),
            source_text=_sentence(text, 1),
        ),
    )


@recipe(
    "manual_flip_golem_sentry",
    r"You can flip this card into face-down Defense Position once per turn\. When this card is Flip Summoned successfully, return 1 monster on your opponent's side of the field to the owner's hand",
    "Manual set-self plus Flip Summon bounce.",
)
def _manual_flip_golem_sentry(card, tier, match, text):
    return _manual_flip_guardian_statue(card, tier, match, text)


@recipe(
    "manual_flip_medusa_worm",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase. When this card is Flip Summoned successfully, destroy 1 monster on your opponent's side of the field",
    "Manual set-self plus Flip Summon destruction.",
)
def _manual_flip_medusa_worm(card, tier, match, text):
    return _manual_flip_scripts(
        card,
        text,
        script(
            "flip_summon_destroy",
            "on_flip_summon",
            [op("destroy", target="$target", reason=card["name"])],
            condition_payload=_monster_condition(),
            target_payload=target("opponent_monster", 1),
            source_text=_sentence(text, 1),
        ),
    )


@recipe(
    "manual_flip_des_lacooda",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase. When this card is Flip Summoned, you draw 1 card from your Deck",
    "Manual set-self plus Flip Summon draw.",
)
def _manual_flip_des_lacooda(card, tier, match, text):
    return _manual_flip_scripts(
        card,
        text,
        script(
            "flip_summon_draw",
            "on_flip_summon",
            [op("draw", count=1, player="self", reason=card["name"])],
            condition_payload=_monster_condition(),
            source_text=_sentence(text, 1),
        ),
    )


@recipe(
    "manual_flip_stealth_bird",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase. When this card is Flip Summoned successfully, inflict (\d+) points of damage to your opponent's Life Points",
    "Manual set-self plus Flip Summon burn.",
)
def _manual_flip_stealth_bird(card, tier, match, text):
    amount = int(match.group(1))
    return _manual_flip_scripts(
        card,
        text,
        script(
            "flip_summon_damage",
            "on_flip_summon",
            [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
            condition_payload=_monster_condition(),
            source_text=_sentence(text, 1),
        ),
    )


@recipe(
    "manual_flip_swarm_locusts",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase. When this card is Flip Summoned, destroy 1 Spell or Trap Card on your opponent's side of the field",
    "Manual set-self plus Flip Summon Spell/Trap removal.",
)
def _manual_flip_swarm_locusts(card, tier, match, text):
    return _manual_flip_scripts(
        card,
        text,
        script(
            "flip_summon_destroy_spell_trap",
            "on_flip_summon",
            [op("destroy", target="$target", reason=card["name"])],
            condition_payload=_monster_condition(),
            target_payload=target("opponent_spell_trap", 1),
            source_text=_sentence(text, 1),
        ),
    )


@recipe(
    "manual_flip_swarm_scarabs",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase. When this card is Flip Summoned, destroy 1 monster on your opponent's side of the field",
    "Manual set-self plus Flip Summon destruction.",
)
def _manual_flip_swarm_scarabs(card, tier, match, text):
    return _manual_flip_medusa_worm(card, tier, match, text)


@recipe(
    "manual_flip_guardian_sphinx",
    r"You can flip this card into face-down Defense Position once per turn during your Main Phase. When this card is Flip Summoned, return all monsters on your opponent's side of the field to the owner's hand",
    "Manual set-self plus Flip Summon mass bounce.",
)
def _manual_flip_guardian_sphinx(card, tier, match, text):
    return _manual_flip_scripts(
        card,
        text,
        script(
            "flip_summon_bounce_all",
            "on_flip_summon",
            [op("return_to_hand", target="$target", reason=card["name"])],
            condition_payload=_monster_condition(),
            target_payload=target("opponent_monster", "all"),
            source_text=_sentence(text, 1),
        ),
    )


RECIPES.append(
    Recipe(
        "battle_recruit_light_select",
        re.compile(
            r"When this card is sent to the Graveyard as a result of battle, you can select 1 (LIGHT) monster with an ATK of "
            r"(\d+) or less from your Deck and Special Summon it to the field in face-up Attack Position "
            r"\(no Tribute is required for monsters of Level 5 or more\)\. The Deck is then shuffled",
            re.IGNORECASE,
        ),
        _recruit_attribute,
        "Battle-destruction recruiter with the older 'select from Deck and Special Summon' wording.",
    )
)


@recipe(
    "summon_search_ritual_move",
    r"When this card is summoned to the field \(excluding Special Summon\), you may move 1 Ritual (Monster|Spell) Card from your Deck to your hand. The Deck is then shuffled",
    "Normal/Flip summon trigger that moves a Ritual card to the hand.",
)
def _summon_search_ritual_move(card, tier, match, text):
    kind = match.group(1)
    filter_payload = (
        condition(card_type="Ritual Monster")
        if kind == "Monster"
        else all_of(condition(card_type="Spell"), condition(subtype="Ritual"))
    )

    def make(trigger: str):
        return script(
            f"{trigger}_search_ritual",
            trigger,
            [op("search", target="$target", destination="hand", reveal=True, shuffle=True)],
            condition_payload=condition(controller="self", zone="self_monster"),
            target_payload=target("self_deck", 1, filter_payload),
            optional=True,
            source_text=text,
        )

    return ([make("on_normal_summon"), make("on_flip_summon")], ["Searches a Ritual card from the Deck."])


@recipe(
    "hidden_book_of_spell",
    r"(?:You can only activate this card during your turn\. )?Select 2 Spell Cards from your Graveyard and add them to your Deck. Your Deck is then shuffled",
    "Trap that recycles two Spells, optionally gated to the controller's turn.",
)
def _hidden_book_of_spell(card, tier, match, text):
    return (
        [
            script(
                "recycle_two_spells",
                "on_activate",
                [
                    op("return_to_deck", target="$target", reason=card["name"]),
                    op("shuffle", player="self"),
                ],
                target_payload=target("self_graveyard", 2, condition(card_type="Spell")),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Two Spells go to the bottom and the Deck is shuffled."],
    )


@recipe(
    "curse_of_aging",
    r"Discard 1 card from your hand. Decrease the ATK and DEF of all monsters on your opponent's side of the field by (\d+) points until the end of the turn this card is activated",
    "Trap that weakens every opponent monster for the turn.",
)
def _curse_of_aging(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "discard_weaken_opponent_monsters",
                "on_activate",
                [
                    op("modify_atk", target="$target", amount=-amount, mode="flat"),
                    op("modify_def", target="$target", amount=-amount, mode="flat"),
                ],
                cost=[discard_cost(1)],
                target_payload=target("opponent_monster", "all"),
                duration="until_end_of_turn",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Discard cost, then every opponent monster loses ATK and DEF until the end of the turn."],
    )


@recipe(
    "mispolymerization",
    r"You can only activate this card when a Fusion Monster is Special Summoned. Return all face-up Fusion Monsters on the field to their respective Fusion Decks",
    "Trap that returns all face-up Fusion Monsters to the Extra Deck.",
)
def _mispolymerization(card, tier, match, text):
    return (
        [
            script(
                "return_fusion_monsters",
                "on_summon",
                [op("return_to_extra", target="$target", reason=card["name"])],
                condition_payload=condition(
                    controller="any", summon_type="special", card_type="Fusion Monster"
                ),
                target_payload=target(
                    "all_monsters",
                    "all",
                    all_of(condition(card_type="Fusion Monster"), condition(face_up=True)),
                ),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Uses the set-trap-safe on_summon response path and requires a Special Summon event."],
    )


@recipe(
    "spirit_of_the_pharaoh",
    r"This card cannot be Normal Summoned or Set\. This card cannot be Special Summoned except by the effect of \"The First Sarcophagus\"\. When this card is Special Summoned successfully, you can Special Summon up to (\d+) Level 2 or lower Zombie-Type Normal Monsters from your Graveyard",
    "Special-summon trigger that revives low-Level Zombie Normal Monsters.",
)
def _spirit_of_the_pharaoh(card, tier, match, text):
    limit = int(match.group(1))
    return (
        [
            script(
                "revive_zombie_normals",
                "on_special_summon",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=condition(controller="self", zone="self_monster"),
                target_payload=target(
                    "self_graveyard",
                    {"min": 0, "max": limit},
                    all_of(
                        condition(card_type="Normal Monster"),
                        condition(monster_type="Zombie"),
                        condition(level_max=2),
                    ),
                    optional=True,
                ),
                optional=True,
                source_text=text,
            )
        ],
        ["The summoning restriction is rules text; the script covers the on-summon revival."],
    )


@recipe(
    "dark_magician_knight",
    r"This card cannot be Normal Summoned or Set\. This card cannot be Special Summoned except by the effect of \"Knight's Title\"\. If this card is Special Summoned successfully, select 1 card on the field and destroy it",
    "Special-summon trigger that destroys one field card.",
)
def _dark_magician_knight(card, tier, match, text):
    return (
        [
            script(
                "special_summon_destroy",
                "on_special_summon",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=condition(controller="self", zone="self_monster"),
                target_payload=target("all_cards", 1),
                source_text=text,
            )
        ],
        ["The summoning restriction is rules text; the script covers the on-summon destruction."],
    )


@recipe(
    "ultra_evolution_pill",
    r"Offer 1 Reptile-Type monster on your side of the field as a Tribute\. Special Summon 1 Dinosaur-Type Monster from your hand",
    "Spell that tributes a Reptile to summon a Dinosaur from the hand.",
)
def _ultra_evolution_pill(card, tier, match, text):
    return (
        [
            script(
                "tribute_reptile_summon_dinosaur",
                "on_activate",
                [op("special_summon", target="$target", position="attack")],
                cost=[
                    op(
                        "tribute",
                        target={
                            "zone": "self_monster",
                            "count": 1,
                            "filter": condition(monster_type="Reptile"),
                        },
                    )
                ],
                target_payload=target(
                    "self_hand",
                    1,
                    all_of(condition(card_type="Monster"), condition(monster_type="Dinosaur")),
                ),
                spell_speed=1,
                source_text=text,
            )
        ],
        ["The Reptile tribute is the cost; the Dinosaur is summoned in Attack Position."],
    )


# --- Additional exact, single-effect patterns ------------------------------


def _flip_destroy_typed_spell_trap(card, tier, text, card_type: str):
    return (
        [
            script(
                f"flip_destroy_{card_type.lower()}",
                "on_flip",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=_monster_condition(),
                target_payload=target("any_spell_trap", 1, condition(card_type=card_type)),
                source_text=text,
            )
        ],
        [f"The engine knows the printed type, so only a {card_type} is selectable."],
    )


RECIPES.append(
    Recipe(
        "flip_destroy_trap_reveal",
        re.compile(
            r"FLIP: Destroys 1 Trap Card on the field\. If this card's target is face-down, flip it face-up\. "
            r"If the card is a Trap Card, it is destroyed\. If not, it is returned to its face-down position\. "
            r"The flipped card is not activated",
            re.IGNORECASE,
        ),
        lambda card, tier, match, text: _flip_destroy_typed_spell_trap(card, tier, text, "Trap"),
        "FLIP Trap removal; the reveal/return clause is handled by the type filter.",
    )
)

RECIPES.append(
    Recipe(
        "flip_destroy_spell_reveal",
        re.compile(
            r"FLIP: Destroys 1 Spell Card on the field\. If this card's target is face-down, flip it face-up\. "
            r"If the card is a Spell Card, it is destroyed\. If not, it is returned to its face-down position\. "
            r"The flipped card is not activated",
            re.IGNORECASE,
        ),
        lambda card, tier, match, text: _flip_destroy_typed_spell_trap(card, tier, text, "Spell"),
        "FLIP Spell removal; the reveal/return clause is handled by the type filter.",
    )
)

RECIPES.append(
    Recipe(
        "flip_destroy_trap_reveal_select",
        re.compile(
            r"FLIP: Select 1 Trap Card on the field and destroy it\. If the selected card is Set, pick up and see the card\. "
            r"If it is a Trap Card, it is destroyed\. If it is a Spell Card, return it to its original position",
            re.IGNORECASE,
        ),
        lambda card, tier, match, text: _flip_destroy_typed_spell_trap(card, tier, text, "Trap"),
        "FLIP Trap removal; the reveal/return clause is handled by the type filter.",
    )
)


@recipe(
    "battle_damage_zero_self_all",
    r"All Battle Damage to this card's controller that he/she takes from a battle involving this monster becomes 0",
    "Continuous battle-damage protection for this card's controller.",
)
def _battle_damage_zero_self_all(card, tier, match, text):
    return (
        [
            script(
                "battle_damage_zero",
                "continuous",
                [op("battle_damage_zero", target="$self")],
                condition_payload=_monster_condition(),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Card-specific battle-damage zero."],
    )


@recipe(
    "byser_shock",
    r"When this card is Normal Summoned, Flip Summoned, or Special Summoned, return all Set cards on the field to their owner's respective hands",
    "Any-summon trigger that bounces every Set card.",
)
def _byser_shock(card, tier, match, text):
    return (
        [
            script(
                "return_set_cards",
                "on_summon",
                [op("return_to_hand", target="$target", reason=card["name"])],
                condition_payload=condition(controller="self", zone="self_monster"),
                target_payload=target("all_cards", "all", condition(face_up=False)),
                source_text=text,
            )
        ],
        ["Set monsters and Set Spell/Trap cards are both face-down field cards."],
    )


@recipe(
    "disarmament",
    r"Destroy all Equip Spell Cards on the field",
    "Destroy every Equip Spell.",
)
def _disarmament(card, tier, match, text):
    return (
        [
            script(
                "destroy_equip_spells",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target(
                    "all_spell_traps",
                    "all",
                    all_of(condition(card_type="Spell"), condition(subtype="Equip")),
                ),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["All Equip Spells on the field are destroyed."],
    )


@recipe(
    "compulsory_evacuation_device",
    r"Return 1 monster on the field to its owner's hand",
    "Return one monster to its owner's hand.",
)
def _compulsory_evacuation_device(card, tier, match, text):
    return (
        [
            script(
                "bounce_monster",
                "on_activate",
                [op("return_to_hand", target="$target", reason=card["name"])],
                target_payload=target("any_monster", 1),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["One monster, regardless of position."],
    )


@recipe(
    "mokey_mokey_king",
    r'"Mokey Mokey" \+ "Mokey Mokey" \+ "Mokey Mokey" When this card is removed from the field, you can Special Summon as many "Mokey Mokey" as possible from your Graveyard',
    "Leaves the field and revives every Mokey Mokey.",
)
def _mokey_mokey_king(card, tier, match, text):
    # The runtime checks IsSourceAvailable via FindCard, but OnCardLeftField is
    # raised after RemoveFromZone and before the card reaches its destination.
    return None


@recipe(
    "the_creator",
    r"Select 1 monster from your Graveyard\. Send 1 card from your hand to the Graveyard and Special Summon the selected monster\. You can only use this effect once per turn\. This card cannot be Special Summoned from the Graveyard",
    "Once-per-turn ignition revival with a hand discard.",
)
def _the_creator(card, tier, match, text):
    return (
        [
            script(
                "discard_revive_monster",
                "manual",
                [op("special_summon", target="$target", position="attack")],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[discard_cost(1)],
                target_payload=target("self_graveyard", 1, condition(card_type="Monster")),
                once_per_turn=True,
                source_text=text,
            )
        ],
        ["The discard is a cost; the Graveyard monster returns in Attack Position."],
    )


@recipe(
    "gale_dogra",
    r"At the cost of (\d+) Life Points, you can discard 1 monster from your Fusion Deck to the Graveyard",
    "Ignition effect that pays Life Points to send an Extra Deck monster to the Graveyard.",
)
def _gale_dogra(card, tier, match, text):
    cost = int(match.group(1))
    return (
        [
            script(
                "pay_life_send_extra_monster",
                "manual",
                [op("send_to_graveyard", target="$target", reason=card["name"])],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                cost=[op("pay_lp", amount=cost)],
                target_payload=target("self_extra", 1, condition(card_type="Monster")),
                source_text=text,
            )
        ],
        [f"Pays {cost} LP and sends one Extra Deck monster to the Graveyard."],
    )


def _spell_destroy_typed(card, tier, text, card_type: str):
    return (
        [
            script(
                f"destroy_{card_type.lower()}",
                "on_activate",
                [op("destroy", target="$target", reason=card["name"])],
                target_payload=target("any_spell_trap", 1, condition(card_type=card_type)),
                spell_speed=1,
                source_text=text,
            )
        ],
        [f"The engine knows the printed type, so only a {card_type} is selectable."],
    )


RECIPES.append(
    Recipe(
        "de_spell",
        re.compile(
            r"Destroys 1 Spell Card on the field\. If this card's target is face-down, flip it face-up\. "
            r"If the card is a Spell Card, it is destroyed\. If not, it is returned to its face-down position\. "
            r"The flipped card is not activated",
            re.IGNORECASE,
        ),
        lambda card, tier, match, text: _spell_destroy_typed(card, tier, text, "Spell"),
        "Spell removal; the reveal/return clause is handled by the type filter.",
    )
)

RECIPES.append(
    Recipe(
        "battle_recruit_type_from_deck",
        re.compile(
            r"When this card is destroyed as a result of battle and sent to the Graveyard, you can Special Summon from your Deck "
            r"1 (Dragon|Insect|Machine)-Type monster with an ATK of (\d+) or less in face-up Attack Position\. Then shuffle your Deck",
            re.IGNORECASE,
        ),
        _recruit_type,
        "Battle-destruction recruiter with the 'Special Summon from your Deck 1 ...' wording.",
    )
)


# ---------------------------------------------------------------------------
# Gate 3.1 recipes: A04 primitive expansion
# ---------------------------------------------------------------------------


def _equip_target(**filter_kwargs) -> dict:
    filt = condition(**filter_kwargs) if filter_kwargs else None
    return target("any_monster", 1, filt)


def _equip_scripts(
    card,
    target_filter: dict | None,
    stat_operations: list[dict],
    *,
    condition_payload: dict | None = None,
    extra_scripts: list[dict] | None = None,
    notes: list[str] | None = None,
) -> tuple[list[dict], list[str]]:
    condition_value = condition_payload or condition(controller="self", face_up=True)
    scripts = [
        script(
            "equip_activate",
            "on_activate",
            [op("equip", target="$target")],
            target_payload=target("any_monster", 1, target_filter),
            spell_speed=1,
            source_text="Equip this card to a legal monster.",
        ),
        script(
            "equip_continuous",
            "equip_continuous",
            stat_operations,
            condition_payload=condition_value,
            duration="while_face_up",
            source_text="Apply the equipped monster's continuous bonus.",
        ),
    ]
    if extra_scripts:
        scripts.extend(extra_scripts)
    return scripts, notes or ["Attach on activation, then apply continuous effects to the equipped monster."]


def _type_list_filter(types: list[str]) -> dict:
    return any_of(*[condition(monster_type=monster_type) for monster_type in types])


def _parse_type_list(raw: str) -> list[str]:
    cleaned = raw.replace(" and ", ", ")
    return [part.strip() for part in cleaned.split(",") if part.strip()]


@recipe(
    "equip_simple_type_atk_def",
    r"A[n]? ([A-Za-z][A-Za-z -]*?)-Type monster equipped with this card increases its ATK and DEF by (\d+) points",
    "Equip Spell with a Type-restricted ATK/DEF bonus.",
)
def _equip_simple_type_atk_def(card, tier, match, text):
    monster_type, amount = match.group(1), int(match.group(2))
    return _equip_scripts(
        card,
        condition(monster_type=monster_type),
        [
            op("modify_atk", target="$self", amount=amount, mode="flat"),
            op("modify_def", target="$self", amount=amount, mode="flat"),
        ],
        condition_payload=condition(controller="self", face_up=True, monster_type=monster_type),
        notes=[f"Only a {monster_type} monster can be equipped; +{amount} ATK/DEF."],
    )


@recipe(
    "equip_simple_type_atk",
    r"A[n]? ([A-Za-z][A-Za-z -]*?)-Type monster equipped with this card increases its ATK by (\d+) points",
    "Equip Spell with a Type-restricted ATK bonus.",
)
def _equip_simple_type_atk(card, tier, match, text):
    monster_type, amount = match.group(1), int(match.group(2))
    return _equip_scripts(
        card,
        condition(monster_type=monster_type),
        [op("modify_atk", target="$self", amount=amount, mode="flat")],
        condition_payload=condition(controller="self", face_up=True, monster_type=monster_type),
        notes=[f"Only a {monster_type} monster can be equipped; +{amount} ATK."],
    )


@recipe(
    "equip_simple_attribute_atk_def",
    r"A[n]? (LIGHT|DARK|EARTH|WATER|FIRE|WIND) monster equipped with this card increases its ATK by (\d+) points and decreases its DEF by (\d+) points",
    "Equip Spell with an Attribute-restricted ATK gain and DEF loss.",
)
def _equip_simple_attribute_atk_def(card, tier, match, text):
    attribute, atk, dfn = match.group(1), int(match.group(2)), -int(match.group(3))
    return _equip_scripts(
        card,
        condition(attribute=attribute),
        [
            op("modify_atk", target="$self", amount=atk, mode="flat"),
            op("modify_def", target="$self", amount=dfn, mode="flat"),
        ],
        condition_payload=condition(controller="self", face_up=True, attribute=attribute),
        notes=[f"Only a {attribute} monster can be equipped; +{atk} ATK / {dfn} DEF."],
    )


@recipe(
    "equip_simple_any_atk_def",
    r"A[n]? (?:Monster Card|monster) equipped with this card increases its ATK and DEF by (\d+) points",
    "Equip Spell with an unrestricted ATK/DEF bonus.",
)
def _equip_simple_any_atk_def(card, tier, match, text):
    amount = int(match.group(1))
    return _equip_scripts(
        card,
        None,
        [
            op("modify_atk", target="$self", amount=amount, mode="flat"),
            op("modify_def", target="$self", amount=amount, mode="flat"),
        ],
        notes=[f"Any monster can be equipped; +{amount} ATK/DEF."],
    )


@recipe(
    "equip_simple_any_atk",
    r"A[n]? monster equipped with this card increases its ATK by (\d+) points",
    "Equip Spell with an unrestricted ATK bonus.",
)
def _equip_simple_any_atk(card, tier, match, text):
    amount = int(match.group(1))
    return _equip_scripts(
        card,
        None,
        [op("modify_atk", target="$self", amount=amount, mode="flat")],
        notes=[f"Any monster can be equipped; +{amount} ATK."],
    )


@recipe(
    "equip_simple_any_def",
    r"A[n]? monster equipped with this card increases its DEF by (\d+) points",
    "Equip Spell with an unrestricted DEF bonus.",
)
def _equip_simple_any_def(card, tier, match, text):
    amount = int(match.group(1))
    return _equip_scripts(
        card,
        None,
        [op("modify_def", target="$self", amount=amount, mode="flat")],
        notes=[f"Any monster can be equipped; +{amount} DEF."],
    )


@recipe(
    "equip_fairy_meteor_crush",
    r"When a monster equipped with this card attacks with an ATK that is higher than the DEF of a Defense Position monster, inflict the difference as Battle Damage to your opponent's Life Points",
    "Equip Spell that grants piercing.",
)
def _equip_fairy_meteor_crush(card, tier, match, text):
    return _equip_scripts(
        card,
        None,
        [op("piercing", target="$equipped")],
        notes=["The equipped monster gains piercing."],
    )


@recipe(
    "equip_lightning_blade",
    r"This card can only be equipped to Warrior-Type monsters\. Increases the ATK of the equipped monster by (\d+) points and decreases the ATK of all WATER monsters on the field by (\d+) points",
    "Warrior-only Equip that also weakens every WATER monster.",
)
def _equip_lightning_blade(card, tier, match, text):
    atk, water = int(match.group(1)), -int(match.group(2))
    return _equip_scripts(
        card,
        condition(monster_type="Warrior"),
        [
            op("modify_atk", target="$self", amount=atk, mode="flat"),
            op(
                "modify_atk",
                target={
                    "zone": "all_monsters",
                    "count": "all",
                    "filter": condition(attribute="WATER"),
                },
                amount=water,
                mode="flat",
            ),
        ],
        condition_payload=condition(controller="self", face_up=True, monster_type="Warrior"),
        notes=[f"+{atk} ATK to the equipped Warrior; {water} ATK to all WATER monsters on the field."],
    )


@recipe(
    "equip_cyclon_laser",
    r"This card can only be used to equip \"Gradius\"\. Increases the ATK of \"Gradius\" by (\d+) points\. When \"Gradius\" attacks with an ATK that is higher than the DEF of your opponent's Defense Position monster, inflict the difference as Battle Damage to your opponent's Life Points",
    "Gradius-only Equip with an ATK bonus and piercing.",
)
def _equip_cyclon_laser(card, tier, match, text):
    amount = int(match.group(1))
    return _equip_scripts(
        card,
        condition(name="Gradius"),
        [
            op("modify_atk", target="$self", amount=amount, mode="flat"),
            op("piercing", target="$equipped"),
        ],
        condition_payload=condition(controller="self", face_up=True, name="Gradius"),
        notes=[f"Only Gradius can be equipped; +{amount} ATK and piercing."],
    )


@recipe(
    "equip_dark_magician_tome",
    r'Only "Dark Magician" or "Dark Magician Girl" may equip this\. The Monster that equips this will gain (\d+) ATK Points\. When this card is sent to the Graveyard, you recover (\d+) Life Points',
    "Dark Magician-only Equip with an ATK bonus and Graveyard Life Point gain.",
)
def _equip_dark_magician_tome(card, tier, match, text):
    atk, heal = int(match.group(1)), int(match.group(2))
    return _equip_scripts(
        card,
        any_of(condition(name="Dark Magician"), condition(name="Dark Magician Girl")),
        [op("modify_atk", target="$self", amount=atk, mode="flat")],
        condition_payload=all_of(
            condition(controller="self", face_up=True),
            any_of(condition(name="Dark Magician"), condition(name="Dark Magician Girl")),
        ),
        extra_scripts=[
            script(
                "grave_recover_life",
                "on_sent_to_graveyard",
                [op("gain_lp", amount=heal, player="self", reason=card["name"])],
                source_text="When this card is sent to the Graveyard, you recover Life Points.",
            )
        ],
        notes=[f"Only Dark Magician/Dark Magician Girl; +{atk} ATK, then gain {heal} LP when sent to the Graveyard."],
    )


@recipe(
    "equip_ritual_weapon",
    r"This card can only be equipped to a Ritual Monster of Level 6 or less\. Increase the ATK and DEF of the equipped monster by (\d+) points",
    "Ritual-only Equip with an ATK/DEF bonus.",
)
def _equip_ritual_weapon(card, tier, match, text):
    amount = int(match.group(1))
    return _equip_scripts(
        card,
        all_of(condition(card_type="Ritual Monster"), condition(level_max=6)),
        [
            op("modify_atk", target="$self", amount=amount, mode="flat"),
            op("modify_def", target="$self", amount=amount, mode="flat"),
        ],
        condition_payload=all_of(
            condition(controller="self", face_up=True),
            condition(card_type="Ritual Monster"),
            condition(level_max=6),
        ),
        notes=[f"Only a Level 6 or lower Ritual Monster; +{amount} ATK/DEF."],
    )


@recipe(
    "equip_fuhma_shuriken",
    r'This card can only be used to equip a monster that includes "Ninja" in its card name\. A monster equipped with this card increases its ATK by (\d+) points\. When this card is sent from the field to the Graveyard, inflict (\d+) points of damage to your opponent\'s Life Points',
    "Ninja-only Equip with an ATK bonus and Graveyard burn.",
)
def _equip_fuhma_shuriken(card, tier, match, text):
    atk, damage = int(match.group(1)), int(match.group(2))
    return _equip_scripts(
        card,
        condition(name_contains="Ninja"),
        [op("modify_atk", target="$self", amount=atk, mode="flat")],
        condition_payload=condition(controller="self", face_up=True, name_contains="Ninja"),
        extra_scripts=[
            script(
                "grave_damage",
                "on_sent_to_graveyard",
                [op("inflict_damage", amount=damage, player="opponent", reason=card["name"])],
                condition_payload=condition(custom="sent_from_field_to_graveyard"),
                source_text="When this card is sent from the field to the Graveyard, inflict damage.",
            )
        ],
        notes=[f"Ninja-only; +{atk} ATK, then {damage} damage when sent to the Graveyard."],
    )


@recipe(
    "equip_horn_of_the_unicorn",
    r"A monster equipped with this card increases its ATK and DEF by (\d+) points\. When this card is sent from the field to the Graveyard, it returns to the top of your Deck",
    "Equip stat bonus plus top-of-Deck recycling.",
)
def _equip_horn_of_the_unicorn(card, tier, match, text):
    amount = int(match.group(1))
    return _equip_scripts(
        card,
        None,
        [
            op("modify_atk", target="$self", amount=amount, mode="flat"),
            op("modify_def", target="$self", amount=amount, mode="flat"),
        ],
        extra_scripts=[
            script(
                "grave_return_top",
                "on_sent_to_graveyard",
                [op("return_to_deck", target="$self", destination="deck_top", reason=card["name"])],
                condition_payload=condition(custom="sent_from_field_to_graveyard"),
                source_text="When this card is sent from the field to the Graveyard, return it to the top of the Deck.",
            )
        ],
        notes=[f"+{amount} ATK/DEF; returns to the top of the Deck from the Graveyard."],
    )


@recipe(
    "equip_sword_deep_seated",
    r"A Monster Card equipped with this card increases its ATK and DEF by (\d+) points\. When this card is sent to the Graveyard, place it on top of your Deck",
    "Equip stat bonus plus top-of-Deck recycling.",
)
def _equip_sword_deep_seated(card, tier, match, text):
    amount = int(match.group(1))
    return _equip_scripts(
        card,
        None,
        [
            op("modify_atk", target="$self", amount=amount, mode="flat"),
            op("modify_def", target="$self", amount=amount, mode="flat"),
        ],
        extra_scripts=[
            script(
                "grave_return_top",
                "on_sent_to_graveyard",
                [op("return_to_deck", target="$self", destination="deck_top", reason=card["name"])],
                source_text="When this card is sent to the Graveyard, place it on top of your Deck.",
            )
        ],
        notes=[f"+{amount} ATK/DEF; returns to the top of the Deck from the Graveyard."],
    )


@recipe(
    "equip_horn_of_light",
    r"A monster equipped with this card increases its DEF by (\d+) points\. When this card is sent from the field to the Graveyard, you can pay (\d+) Life Points to place it on top of your Deck",
    "Equip DEF bonus with an optional top-of-Deck return cost.",
)
def _equip_horn_of_light(card, tier, match, text):
    dfn, cost = int(match.group(1)), int(match.group(2))
    return _equip_scripts(
        card,
        None,
        [op("modify_def", target="$self", amount=dfn, mode="flat")],
        extra_scripts=[
            script(
                "grave_return_top",
                "on_sent_to_graveyard",
                [op("return_to_deck", target="$self", destination="deck_top", reason=card["name"])],
                condition_payload=condition(custom="sent_from_field_to_graveyard"),
                cost=[op("pay_lp", amount=cost)],
                optional=True,
                source_text="Pay Life Points to place this card on top of your Deck.",
            )
        ],
        notes=[f"+{dfn} DEF; optionally pay {cost} LP to return it to the top of the Deck."],
    )


@recipe(
    "equip_malevolent_nuzzler",
    r"A monster equipped with this card increases its ATK by (\d+) points\. When this card is sent from the field to the Graveyard, if you pay (\d+) Life Points, this card returns to the top of your Deck",
    "Equip ATK bonus with an optional top-of-Deck return cost.",
)
def _equip_malevolent_nuzzler(card, tier, match, text):
    atk, cost = int(match.group(1)), int(match.group(2))
    return _equip_scripts(
        card,
        None,
        [op("modify_atk", target="$self", amount=atk, mode="flat")],
        extra_scripts=[
            script(
                "grave_return_top",
                "on_sent_to_graveyard",
                [op("return_to_deck", target="$self", destination="deck_top", reason=card["name"])],
                condition_payload=condition(custom="sent_from_field_to_graveyard"),
                cost=[op("pay_lp", amount=cost)],
                optional=True,
                source_text="Pay Life Points to return this card to the top of the Deck.",
            )
        ],
        notes=[f"+{atk} ATK; optionally pay {cost} LP to return it to the top of the Deck."],
    )


@recipe(
    "equip_axe_of_despair",
    r"A monster equipped with this card increases its ATK by (\d+) points\. When this card is sent from the field to the Graveyard, if you offer 1 monster on your side of the field as a Tribute, this card returns to the top of your Deck",
    "Equip ATK bonus with an optional tribute-to-recycle clause.",
)
def _equip_axe_of_despair(card, tier, match, text):
    atk = int(match.group(1))
    return _equip_scripts(
        card,
        None,
        [op("modify_atk", target="$self", amount=atk, mode="flat")],
        extra_scripts=[
            script(
                "grave_return_top",
                "on_sent_to_graveyard",
                [op("return_to_deck", target="$self", destination="deck_top", reason=card["name"])],
                condition_payload=condition(custom="sent_from_field_to_graveyard"),
                cost=[op("tribute", target={"zone": "self_monster", "count": 1})],
                optional=True,
                source_text="Tribute a monster to return this card to the top of the Deck.",
            )
        ],
        notes=[f"+{atk} ATK; optionally tribute a monster to return it to the top of the Deck."],
    )


# --- Field Spell stat patterns ---------------------------------------------


def _field_stat_script(card, operations: list[dict], note: str) -> tuple[list[dict], list[str]]:
    return (
        [
            script(
                "field_stat",
                "field_continuous",
                operations,
                condition_payload=condition(controller="self", face_up=True, zone="self_field"),
                duration="while_face_up",
                source_text=note,
            )
        ],
        [note],
    )


@recipe(
    "field_type_list_atk_def",
    r"Increases? the ATK and DEF of all ([A-Za-z][A-Za-z ,-]*?)-Type monsters by (\d+) points",
    "Field Spell that boosts a list of Monster Types.",
)
def _field_type_list_atk_def(card, tier, match, text):
    types = _parse_type_list(match.group(1))
    amount = int(match.group(2))
    filter_payload = _type_list_filter(types)
    operations = [
        op("modify_atk", target={"zone": "all_monsters", "count": "all", "filter": filter_payload}, amount=amount, mode="flat"),
        op("modify_def", target={"zone": "all_monsters", "count": "all", "filter": filter_payload}, amount=amount, mode="flat"),
    ]
    return _field_stat_script(card, operations, f"+{amount} ATK/DEF to {', '.join(types)} monsters.")


@recipe(
    "field_attribute_atk_def",
    r"Increases? the ATK of all (LIGHT|DARK|EARTH|WATER|FIRE|WIND) monsters by (\d+) points and decreases? their DEF by (\d+) points",
    "Field Spell that boosts one Attribute and lowers its DEF.",
)
def _field_attribute_atk_def(card, tier, match, text):
    attribute, atk, dfn = match.group(1), int(match.group(2)), -int(match.group(3))
    filter_payload = condition(attribute=attribute)
    operations = [
        op("modify_atk", target={"zone": "all_monsters", "count": "all", "filter": filter_payload}, amount=atk, mode="flat"),
        op("modify_def", target={"zone": "all_monsters", "count": "all", "filter": filter_payload}, amount=dfn, mode="flat"),
    ]
    return _field_stat_script(card, operations, f"+{atk} ATK / {dfn} DEF to {attribute} monsters.")


@recipe(
    "field_defense_def",
    r"Increases the DEF of all Defense Position monsters by (\d+) points",
    "Field Spell that boosts every Defense Position monster's DEF.",
)
def _field_defense_def(card, tier, match, text):
    amount = int(match.group(1))
    operations = [
        op(
            "modify_def",
            target={
                "zone": "all_monsters",
                "count": "all",
                "filter": all_of(condition(position="defense"), condition(face_up=True)),
            },
            amount=amount,
            mode="flat",
        )
    ]
    return _field_stat_script(card, operations, f"+{amount} DEF to face-up Defense Position monsters.")


@recipe(
    "field_yami",
    r"Increases the ATK and DEF of all Fiend and Spellcaster-Type monsters by (\d+) points\. Also decreases the ATK and DEF of all Fairy-Type monsters by (\d+) points",
    "Yami's Type-specific buff and Fairy debuff.",
)
def _field_yami(card, tier, match, text):
    buff, debuff = int(match.group(1)), -int(match.group(2))
    buff_filter = any_of(condition(monster_type="Fiend"), condition(monster_type="Spellcaster"))
    fairy_filter = condition(monster_type="Fairy")
    operations = [
        op("modify_atk", target={"zone": "all_monsters", "count": "all", "filter": buff_filter}, amount=buff, mode="flat"),
        op("modify_def", target={"zone": "all_monsters", "count": "all", "filter": buff_filter}, amount=buff, mode="flat"),
        op("modify_atk", target={"zone": "all_monsters", "count": "all", "filter": fairy_filter}, amount=debuff, mode="flat"),
        op("modify_def", target={"zone": "all_monsters", "count": "all", "filter": fairy_filter}, amount=debuff, mode="flat"),
    ]
    return _field_stat_script(card, operations, f"+{buff}/-{-debuff} ATK/DEF for Fiend, Spellcaster and Fairy monsters.")


# --- Story-reachable monsters: dynamic stats -------------------------------


@recipe(
    "machine_king",
    r"Increase the ATK of this card by (\d+) points for each face-up Machine-Type monster on the field",
    "Continuous ATK equal to 100 per face-up Machine on the field.",
)
def _machine_king(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "machine_count_atk",
                "continuous",
                [
                    op(
                        "modify_atk",
                        target="$self",
                        amount=amount,
                        mode="per_card",
                        count_zone="all_monsters",
                        count_filter=all_of(condition(face_up=True), condition(monster_type="Machine")),
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Counts every face-up Machine on either side, including this card."],
    )


@recipe(
    "dark_magician_girl",
    r"Increase the ATK of this monster by (\d+) points for each \"Dark Magician\" or \"Magician of Black Chaos\" in either player's Graveyard",
    "Continuous ATK per Dark Magician / Magician of Black Chaos in either Graveyard.",
)
def _dark_magician_girl(card, tier, match, text):
    amount = int(match.group(1))
    name_filter = any_of(condition(name="Dark Magician"), condition(name="Magician of Black Chaos"))
    return (
        [
            script(
                "grave_name_atk",
                "continuous",
                [
                    op(
                        "modify_atk",
                        target="$self",
                        amount=amount,
                        mode="per_card",
                        count_zone="graveyard",
                        count_filter=name_filter,
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Both Graveyards are counted."],
    )


@recipe(
    "arsenal_bug",
    r"If there are no face-up Insect-Type monsters \(except this monster\) on your side of the field, both the ATK and DEF of this monster become (\d+) points",
    "Continuous stat replacement while no other Insect is face-up.",
)
def _arsenal_bug(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "insect_condition_stats",
                "continuous",
                [
                    op("modify_atk", target="$self", amount=amount, mode="set_atk"),
                    op("modify_def", target="$self", amount=amount, mode="set_def"),
                ],
                condition_payload=all_of(
                    condition(controller="self", face_up=True, zone="self_monster"),
                    condition(
                        count_zone="self_monster",
                        count_filter=all_of(condition(face_up=True), condition(monster_type="Insect")),
                        count_max=1,
                    ),
                ),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["The count includes Arsenal Bug itself, so count_max=1 means no other face-up Insect."],
    )


@recipe(
    "amazoness_paladin",
    r'Increase the ATK of this monster by (\d+) points for each monster on your side of the field that includes "Amazoness" in its card name, or is named "Amazon Archer"',
    "Continuous ATK per Amazoness / Amazon Archer on your field.",
)
def _amazoness_paladin(card, tier, match, text):
    amount = int(match.group(1))
    name_filter = any_of(condition(name_contains="Amazoness"), condition(name="Amazon Archer"))
    return (
        [
            script(
                "amazoness_count_atk",
                "continuous",
                [
                    op(
                        "modify_atk",
                        target="$self",
                        amount=amount,
                        mode="per_card",
                        count_zone="self_monster",
                        count_filter=name_filter,
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Counts itself because its name contains Amazoness."],
    )


@recipe(
    "des_koala",
    r"FLIP: Inflict (\d+) points of Direct Damage to your opponent's Life Points for each card in your opponent's hand",
    "FLIP burn per opponent hand card.",
)
def _des_koala(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "flip_hand_burn",
                "on_flip",
                [
                    op(
                        "inflict_damage",
                        amount=amount,
                        player="opponent",
                        mode="per_card",
                        count_zone="opponent_hand",
                        reason=card["name"],
                    )
                ],
                condition_payload=_monster_condition(),
                source_text=text,
            )
        ],
        ["Counts the opponent's hand at resolution."],
    )


@recipe(
    "chaos_necromancer",
    r"The ATK of this card becomes the number of Monster Cards in your Graveyard x (\d+) points",
    "Continuous ATK equal to 300 per monster in your Graveyard (base ATK is 0).",
)
def _chaos_necromancer(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "grave_monster_atk",
                "continuous",
                [
                    op(
                        "modify_atk",
                        target="$self",
                        amount=amount,
                        mode="per_card",
                        count_zone="self_graveyard",
                        count_filter=condition(card_type="Monster"),
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Base ATK is 0, so the dynamic addition is equivalent to setting the ATK."],
    )


@recipe(
    "lost_guardian",
    r"The original DEF of this card becomes the number of your Rock-Type monsters that are removed from play x (\d+) points",
    "Continuous DEF equal to 700 per banished Rock monster (base DEF is 0).",
)
def _lost_guardian(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "banished_rock_def",
                "continuous",
                [
                    op(
                        "modify_def",
                        target="$self",
                        amount=amount,
                        mode="per_card",
                        count_zone="self_banished",
                        count_filter=condition(monster_type="Rock"),
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Base DEF is 0, so the dynamic addition is equivalent to setting the DEF."],
    )


@recipe(
    "tyranno_infinity",
    r"The original ATK of this card becomes the number of your Dinosaur-Type monsters that are removed from play x (\d+) points",
    "Continuous ATK equal to 1000 per banished Dinosaur (base ATK is 0).",
)
def _tyranno_infinity(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "banished_dinosaur_atk",
                "continuous",
                [
                    op(
                        "modify_atk",
                        target="$self",
                        amount=amount,
                        mode="per_card",
                        count_zone="self_banished",
                        count_filter=condition(monster_type="Dinosaur"),
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Base ATK is 0, so the dynamic addition is equivalent to setting the ATK."],
    )


@recipe(
    "big_march_of_animals",
    r"Until the End Phase, increase the ATK of all face-up Beast-Type monsters on your side of the field by (\d+) points for each Beast-Type monster on your side of the field",
    "Team ATK boost per Beast on your field until End Phase.",
)
def _big_march_of_animals(card, tier, match, text):
    amount = int(match.group(1))
    beast = all_of(condition(face_up=True), condition(monster_type="Beast"))
    return (
        [
            script(
                "beast_team_boost",
                "on_activate",
                [
                    op(
                        "modify_atk",
                        target="$target",
                        amount=amount,
                        mode="per_card",
                        count_zone="self_monster",
                        count_filter=beast,
                    )
                ],
                target_payload=target("self_monster", "all", beast),
                duration="until_end_of_turn",
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Each face-up Beast on your side receives the same per-Beast bonus."],
    )


@recipe(
    "secret_barrel",
    r"Inflict Direct Damage to your opponent's Life Points equal to the total number of cards on your opponent's side of the field and in your opponent's hand x (\d+) points",
    "Trap burn per opponent field/hand card.",
)
def _secret_barrel(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "opponent_cards_burn",
                "on_activate",
                [
                    op(
                        "inflict_damage",
                        amount=amount,
                        player="opponent",
                        mode="per_card",
                        count_zone="opponent_all",
                        reason=card["name"],
                    )
                ],
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Counts opponent monsters, Spell/Traps, Field Spell and hand."],
    )


@recipe(
    "good_goblin_housekeeping",
    r"Draw a number of cards from your Deck equal to the number of \"Good Goblin Housekeeping\" cards in your Graveyard .*?1, select 1 card from your hand, and return it to the bottom of your Deck",
    "Draw per Good Goblin Housekeeping in the Graveyard plus one, then bottom one hand card.",
)
def _good_goblin_housekeeping(card, tier, match, text):
    # draw does not implement dynamic modes; only fixed counts are executed.
    return None


# --- Story-reachable monsters: battle / attack primitives ------------------


@recipe(
    "airknight_parshath",
    r"When this card attacks with an ATK higher than the DEF of your opponent's Defense Position monster, inflict the difference as Battle Damage to your opponent's Life Points\. When this card inflicts Battle Damage to your opponent's Life Points, draw 1 card from your Deck",
    "Piercing plus draw on battle damage.",
)
def _airknight_parshath(card, tier, match, text):
    return (
        [
            script(
                "piercing",
                "continuous",
                [op("piercing", target="$self")],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text="This card inflicts piercing Battle Damage.",
            ),
            script(
                "battle_damage_draw",
                "on_battle_damage",
                [op("draw", count=1, player="self", reason=card["name"])],
                condition_payload=all_of(
                    condition(custom="battle_involving_self"),
                    condition(is_turn_player=True),
                ),
                source_text="When this card inflicts Battle Damage, draw 1 card.",
            ),
        ],
        ["Piercing is continuous; the draw is an after-battle-damage trigger."],
    )


@recipe(
    "mad_sword_beast",
    r"When this card attacks with an ATK that is higher than the DEF of your opponent's Defense Position monster, inflict the difference as Battle Damage to your opponent's Life Points",
    "Continuous piercing.",
)
def _mad_sword_beast(card, tier, match, text):
    return (
        [
            script(
                "piercing",
                "continuous",
                [op("piercing", target="$self")],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Continuous piercing permission."],
    )


@recipe(
    "dark_driceratops",
    r"When this card attacks with an ATK that is higher than the DEF of your opponent's Defense Position monster, inflict the difference as Battle Damage to your opponent's Life Points",
    "Continuous piercing.",
)
def _dark_driceratops(card, tier, match, text):
    return _mad_sword_beast(card, tier, match, text)


@recipe(
    "cyber_end_dragon",
    r'"Cyber Dragon" \+ "Cyber Dragon" \+ "Cyber Dragon" A Fusion Summon of this card can only be conducted with the above Fusion Material Monsters\. During battle between this card and a Defense Position monster whose DEF is lower than the ATK of this card, inflict the difference as Battle Damage to your opponent\'s Life Points',
    "Cyber End Dragon's continuous piercing.",
)
def _cyber_end_dragon(card, tier, match, text):
    return (
        [
            script(
                "piercing",
                "continuous",
                [op("piercing", target="$self")],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text="During battle with a Defense Position monster, inflict piercing Battle Damage.",
            )
        ],
        ["The Fusion Summon recipe is rules data; the script covers the printed battle effect."],
    )


@recipe(
    "cyber_twin_dragon",
    r'"Cyber Dragon" \+ "Cyber Dragon" A Fusion Summon of this card can only be conducted with the above Fusion Material Monsters\. This card can attack twice during the same Battle Phase',
    "Cyber Twin Dragon's second attack.",
)
def _cyber_twin_dragon(card, tier, match, text):
    return (
        [
            script(
                "extra_attack",
                "continuous",
                [op("extra_attack", target="$self", count=1)],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text="This card can attack twice during the same Battle Phase.",
            )
        ],
        ["Extra attack is registered continuously; the Fusion Summon recipe is rules data."],
    )


@recipe(
    "atomic_firefly",
    r"When this face-up card on the field is destroyed as a result of battle, the player who destroyed it takes (\d+) points of damage",
    "Battle-destruction trigger that burns the opponent.",
)
def _atomic_firefly(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "battle_destroy_burn",
                "on_battle_destroy",
                [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
                source_text=text,
            )
        ],
        ["The battle destroyer is the opponent in a legal battle."],
    )


@recipe(
    "millennium_scorpion",
    r"Each time this card destroys 1 monster on your opponent's side of the field and sends it to the Graveyard as a result of battle, increase the ATK of this card by (\d+) points",
    "Attacker-destroy trigger that permanently gains ATK.",
)
def _millennium_scorpion(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "destroy_gain_atk",
                "on_battle_destroy_by_attacker",
                [op("modify_atk", target="$self", amount=amount, mode="flat")],
                condition_payload=condition(custom="battle_involving_self"),
                duration="permanent",
                source_text=text,
            )
        ],
        ["Uses the attacker-side battle-destroy hook."],
    )


@recipe(
    "holy_knight_ishzark",
    r"A Monster destroyed by this card in battle is removed from play",
    "Attacker-destroy trigger that banishes the destroyed monster.",
)
def _holy_knight_ishzark(card, tier, match, text):
    return (
        [
            script(
                "banish_destroyed_monster",
                "on_battle_destroy_by_attacker",
                [op("banish", target="$trigger", reason=card["name"])],
                condition_payload=condition(custom="battle_involving_self"),
                source_text=text,
            )
        ],
        ["The destroyed monster is in the Graveyard when the attacker hook resolves; banish it from there."],
    )


@recipe(
    "black_tyranno",
    r"If the only cards on your opponent's side of the field are Defense Position Monster Cards, this card can attack your opponent's Life Points directly",
    "Continuous direct-attack permission when the opponent has only Defense Position monsters.",
)
def _black_tyranno(card, tier, match, text):
    return (
        [
            script(
                "conditional_direct_attack",
                "continuous",
                [op("attack_directly", target="$self")],
                condition_payload=all_of(
                    condition(controller="self", face_up=True, zone="self_monster"),
                    condition(
                        count_zone="opponent_monster",
                        count_filter=all_of(condition(position="attack"), condition(face_up=True)),
                        count_max=0,
                    ),
                    condition(count_zone="opponent_spell_trap", count_max=0),
                ),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["No face-up Attack Position monster and no opponent Spell/Trap means direct attack is legal."],
    )


@recipe(
    "insect_barrier",
    r"All Insect-Type monsters on your opponent's side of the field cannot attack as long as this card remains face-up on the field",
    "Continuous attack lock on the opponent's Insects.",
)
def _insect_barrier(card, tier, match, text):
    return (
        [
            script(
                "opponent_insect_lock",
                "continuous",
                [
                    op(
                        "attack_lock",
                        target={
                            "zone": "opponent_monster",
                            "count": "all",
                            "filter": condition(monster_type="Insect"),
                        },
                        mode="cannot_attack",
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_spell_trap"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["The lock is registered continuously while this card is face-up."],
    )


@recipe(
    "the_dark_door",
    r"Both players can only attack with 1 monster during their respective Battle Phases",
    "Continuous one-attacker limit for both players.",
)
def _the_dark_door(card, tier, match, text):
    return (
        [
            script(
                "one_attacker_lock",
                "continuous",
                [op("attack_lock", mode="only_one_attacker", player="both", side_wide=True)],
                condition_payload=condition(controller="self", face_up=True, zone="self_spell_trap"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Both sides are capped at one attacker."],
    )


@recipe(
    "threatening_roar",
    r"Your opponent cannot declare an attack during this turn",
    "Normal Trap that forbids attacks for the turn.",
)
def _threatening_roar(card, tier, match, text):
    return (
        [
            script(
                "attack_lock_turn",
                "on_activate",
                [op("attack_lock", mode="cannot_attack", player="opponent", side_wide=True)],
                duration="until_end_of_turn",
                spell_speed=2,
                source_text=text,
            )
        ],
        ["Side-wide attack lock for the opponent until the end of the turn."],
    )


@recipe(
    "barrel_dragon",
    r"Toss a coin 3 times\. If 2 out of 3 results are Heads, destroy 1 monster on your opponent's side of the field\. This card's effect can only be used during your own turn, once per turn",
    "Once-per-turn coin effect that destroys one opponent monster on two or more Heads.",
)
def _barrel_dragon(card, tier, match, text):
    return (
        [
            script(
                "coin_destroy_monster",
                "manual",
                [
                    op(
                        "toss_coin",
                        count=3,
                        success_min=2,
                        success_max=3,
                        success_operations=[op("destroy", target="$target", reason=card["name"])],
                    )
                ],
                condition_payload=all_of(
                    condition(controller="self", face_up=True, zone="self_monster"),
                    condition(custom="ignition_main_phase"),
                    condition(is_turn_player=True),
                ),
                target_payload=target("opponent_monster", 1),
                once_per_turn=True,
                source_text=text,
            )
        ],
        ["The target is selected before the coin toss; only a successful result destroys it."],
    )


@recipe(
    "goblin_attack_force",
    r"When this card attacks, it is changed to Defense Position at the end of the Battle Phase\. This position cannot be changed during your next turn",
    "End-of-Battle-Phase Defense change.",
)
def _goblin_attack_force(card, tier, match, text):
    return (
        [
            script(
                "battle_end_defense",
                "continuous",
                [op("battle_position_lock", target="$self", mode="defense_at_end")],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text="This card changes to Defense Position at the end of the Battle Phase.",
            )
        ],
        ["Defense change is registered continuously; the next-turn change lock is not separately represented."],
    )


@recipe(
    "goblin_elite_attack_force",
    r"If this card attacks, it is changed to Defense Position at the end of the Battle Phase\. This card's battle position cannot be changed until the end of your next turn, except with a card effect",
    "End-of-Battle-Phase Defense change.",
)
def _goblin_elite_attack_force(card, tier, match, text):
    return _goblin_attack_force(card, tier, match, text)


@recipe(
    "indomitable_fighter_lei_lei",
    r"If this card attacks, it is changed to Defense Position at the end of the Battle Phase\. This card's battle position cannot be changed until the end of your next turn, except with a card effect",
    "End-of-Battle-Phase Defense change.",
)
def _indomitable_fighter_lei_lei(card, tier, match, text):
    return _goblin_attack_force(card, tier, match, text)


@recipe(
    "granmarg_rock_monarch",
    r"When this card is Tribute Summoned successfully, destroy 1 face-down card on the field",
    "Tribute-Summon trigger that destroys one Set card.",
)
def _granmarg_rock_monarch(card, tier, match, text):
    return (
        [
            script(
                "tribute_summon_destroy_set",
                "on_tribute_summon",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=condition(controller="self", zone="self_monster"),
                target_payload=target("all_cards", 1, condition(face_up=False)),
                source_text=text,
            )
        ],
        ["Triggers only on a Normal Summon with at least one tribute."],
    )


@recipe(
    "maji_gire_panda",
    r"As long as this card remains face-up on the field, each time a Beast-Type monster\(s\) on the field is destroyed, increase the ATK of this card by (\d+) points",
    "Continuous trigger that grows when a Beast is destroyed.",
)
def _maji_gire_panda(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "beast_destroyed_gain_atk",
                "on_destroy",
                [op("modify_atk", target="$self", amount=amount, mode="flat")],
                condition_payload=condition(monster_type="Beast"),
                duration="permanent",
                source_text=text,
            )
        ],
        ["The destroyed Beast is the event subject; this card's script gains the ATK."],
    )


@recipe(
    "kangaroo_champ",
    r"A monster that battles with this card is changed to Defense Position after damage calculation",
    "Change the battling monster to Defense Position after damage calculation.",
)
def _kangaroo_champ(card, tier, match, text):
    # on_damage_calculated is still field-scanned for other card ids; there is
    # no condition that proves this source is the attacker or the attack target.
    return None


@recipe(
    "blade_rabbit",
    r"When this card is changed from Attack Position to face-up Defense Position, destroy 1 monster on your opponent's side of the field",
    "Position-change trigger that destroys one opponent monster.",
)
def _blade_rabbit(card, tier, match, text):
    return (
        [
            script(
                "position_change_destroy",
                "on_position_change",
                [op("destroy", target="$target", reason=card["name"])],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", position="defense"
                ),
                target_payload=target("opponent_monster", 1),
                source_text=text,
            )
        ],
        ["A change to face-up Defense Position is distinguished from a Set by face_up=true."],
    )


@recipe(
    "master_monk",
    r"This card cannot be Normal Summoned or Set\. This card cannot be Special Summoned except by Tributing 1 \"Monk Fighter\" on your side of the field\. This card can attack twice during the same turn",
    "Inherent summon by tributing Monk Fighter plus a second attack.",
)
def _master_monk(card, tier, match, text):
    return (
        [
            script(
                "inherent_summon",
                "inherent_summon",
                [op("inherent_special_summon", target="$self", position="attack")],
                cost=[
                    op(
                        "tribute",
                        target={
                            "zone": "self_monster",
                            "count": 1,
                            "filter": condition(name="Monk Fighter"),
                        },
                    )
                ],
                source_text="Special Summon this card by Tributing 1 Monk Fighter.",
            ),
            script(
                "extra_attack",
                "continuous",
                [op("extra_attack", target="$self", count=1)],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text="This card can attack twice during the same turn.",
            ),
        ],
        ["Inherent summon plus continuous extra attack."],
    )


@recipe(
    "cyber_dragon",
    r"If there is a monster on your opponent's side of the field and there are no monsters on your side of the field, you can Special Summon this card from your hand",
    "Inherent Special Summon from the hand when the opponent has a monster and your field is empty.",
)
def _cyber_dragon(card, tier, match, text):
    return (
        [
            script(
                "inherent_summon",
                "inherent_summon",
                [op("inherent_special_summon", target="$self", position="attack")],
                condition_payload=all_of(
                    condition(zone="self_hand"),
                    condition(count_zone="opponent_monster", count_min=1),
                    condition(count_zone="self_monster", count_max=0),
                ),
                source_text=text,
            )
        ],
        ["The condition counts both sides at activation time."],
    )


@recipe(
    "chaos_sorcerer",
    r"This card can only be Special Summoned by removing 1 LIGHT and 1 DARK monster in your Graveyard from play\. Once during each of your turns, you can remove 1 face-up monster on the field from play\. If you activate this effect, this card cannot attack during this turn",
    "Chaos Sorcerer's inherent banish-summon and once-per-turn banish ignition.",
)
def _chaos_sorcerer(card, tier, match, text):
    return (
        [
            script(
                "inherent_summon",
                "inherent_summon",
                [op("inherent_special_summon", target="$self", position="attack")],
                condition_payload=all_of(
                    condition(zone="self_hand"),
                    condition(
                        count_zone="self_graveyard",
                        count_filter=condition(attribute="LIGHT"),
                        count_min=1,
                    ),
                    condition(
                        count_zone="self_graveyard",
                        count_filter=condition(attribute="DARK"),
                        count_min=1,
                    ),
                ),
                cost=[
                    op(
                        "banish",
                        target={
                            "zone": "self_graveyard",
                            "count": 1,
                            "filter": condition(attribute="LIGHT"),
                        },
                    ),
                    op(
                        "banish",
                        target={
                            "zone": "self_graveyard",
                            "count": 1,
                            "filter": condition(attribute="DARK"),
                        },
                    ),
                ],
                source_text="Special Summon by banishing 1 LIGHT and 1 DARK monster from the Graveyard.",
            ),
            script(
                "banish_monster",
                "manual",
                [
                    op("banish", target="$target", reason=card["name"]),
                    op("attack_lock", target="$self", mode="cannot_attack"),
                ],
                condition_payload=condition(
                    controller="self", face_up=True, zone="self_monster", custom="ignition_main_phase"
                ),
                target_payload=target("any_monster", 1, condition(face_up=True)),
                duration="until_end_of_turn",
                once_per_turn=True,
                source_text="Remove 1 face-up monster from play; this card cannot attack this turn.",
            ),
        ],
        ["The banish and the attack lock resolve in the same manual script."],
    )


@recipe(
    "steamroid",
    r"If this card attacks your opponent's monster, increase the ATK of this card by (\d+) points during the Damage Step only\. If this card is attacked by your opponent's monster, decrease the ATK of this card by (\d+) points during the Damage Step only",
    "Damage Step ATK change based on whether Steamroid is attacking or defending.",
)
def _steamroid(card, tier, match, text):
    # on_damage_step is still field-scanned for different card ids; there is
    # no condition that proves this source is the attacker/target.
    return None


@recipe(
    "megarock_dragon",
    r"This card cannot be Normal Summoned or Set\. This card cannot be Special Summoned except by removing from play a Rock-Type monster\(s\) in your Graveyard\. The original ATK and DEF of this card become the number of Rock-Type monsters you removed from play when you Special Summoned this card x (\d+) points",
    "Inherent Rock-summon plus dynamic ATK/DEF from banished Rocks.",
)
def _megarock_dragon(card, tier, match, text):
    # The printed procedure banishes any number of Rocks; a single fixed cost
    # would change the resulting ATK/DEF.
    return None


@recipe(
    "muka_muka",
    r"Increase the ATK and DEF of this card by (\d+) points for every card in your hand",
    "Continuous ATK/DEF per card in hand.",
)
def _muka_muka(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "hand_scaled_stats",
                "continuous",
                [
                    op("modify_atk", target="$self", amount=amount, mode="per_hand"),
                    op("modify_def", target="$self", amount=amount, mode="per_hand"),
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Both stats scale with the controller's hand size."],
    )


@recipe(
    "team_type_stat",
    r"As long as this card remains face-up on the field, increase the ATK and DEF of all ([A-Za-z-]+)-Type monsters on your side of the field by (\d+) points",
    "Continuous team-wide Type stat boost.",
)
def _team_type_stat(card, tier, match, text):
    monster_type, amount = match.group(1), int(match.group(2))
    filter_payload = all_of(condition(controller="self"), condition(monster_type=monster_type))
    return (
        [
            script(
                "team_type_stat",
                "continuous",
                [
                    op("modify_atk", target={"zone": "all_monsters", "count": "all", "filter": filter_payload}, amount=amount, mode="flat"),
                    op("modify_def", target={"zone": "all_monsters", "count": "all", "filter": filter_payload}, amount=amount, mode="flat"),
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        [f"+{amount} ATK/DEF to friendly {monster_type} monsters."],
    )


@recipe(
    "mudora",
    r"The ATK of this card increases by (\d+) points for every Fairy-Type monster in your Graveyard",
    "Continuous ATK per Fairy in the Graveyard.",
)
def _mudora(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "grave_fairy_atk",
                "continuous",
                [
                    op(
                        "modify_atk",
                        target="$self",
                        amount=amount,
                        mode="per_card",
                        count_zone="self_graveyard",
                        count_filter=condition(monster_type="Fairy"),
                    )
                ],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Counts Fairy-Type monsters in the controller's Graveyard."],
    )


@recipe(
    "giant_germ",
    r"When this card is sent to the Graveyard as a result of battle, inflict (\d+) points of Direct Damage to your opponent's Life Points\. You can also take cards of the same name from your Deck and Special Summon them to the field in face-up Attack Position\. The Deck is then shuffled",
    "Battle-destruction burn plus same-name recruit.",
)
def _giant_germ(card, tier, match, text):
    amount = int(match.group(1))

    def recruit(trigger: str):
        return script(
            "battle_recruit_same_name",
            trigger,
            [
                op("special_summon", target="$target", position="attack"),
                op("shuffle", player="self"),
            ],
            target_payload=target("self_deck", "all", condition(name=card["name"])),
            optional=True,
            source_text="Recruit all cards of the same name in face-up Attack Position.",
        )

    return (
        [
            script(
                "battle_destroy_burn",
                "on_battle_destroy",
                [op("inflict_damage", amount=amount, player="opponent", reason=card["name"])],
                source_text="When this card is sent to the Graveyard by battle, inflict damage.",
            ),
            recruit("on_battle_destroy"),
        ],
        ["Burn is mandatory; the same-name recruit is optional."],
    )


@recipe(
    "nimble_momonga",
    r"When this card is sent to the Graveyard as a result of battle, increase your Life Points by (\d+) points\. You can also take cards of the same name from your Deck and Special Summon them to the field in face-down Defense Position\. The Deck is then shuffled",
    "Battle-destruction heal plus same-name face-down recruit.",
)
def _nimble_momonga(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "battle_destroy_heal",
                "on_battle_destroy",
                [op("gain_lp", amount=amount, player="self", reason=card["name"])],
                source_text="When this card is sent to the Graveyard by battle, gain Life Points.",
            ),
            script(
                "battle_recruit_same_name",
                "on_battle_destroy",
                [
                    op("special_summon", target="$target", position="face_down"),
                    op("shuffle", player="self"),
                ],
                target_payload=target("self_deck", "all", condition(name=card["name"])),
                optional=True,
                source_text="Recruit all cards of the same name in face-down Defense Position.",
            ),
        ],
        ["Heal is mandatory; the same-name recruit is optional and uses face-down Defense."],
    )


@recipe(
    "alligators_sword_dragon",
    r'"Baby Dragon" \+ "Alligator\'s Sword" You can Inflict Direct Damage to your opponent\'s Life Points with this card if the only Attributes of Monster Cards on your opponent\'s side of the field are EARTH, WATER, or FIRE',
    "Conditional direct attack when the opponent has no LIGHT/DARK/WIND monsters.",
)
def _alligators_sword_dragon(card, tier, match, text):
    return (
        [
            script(
                "conditional_direct_attack",
                "continuous",
                [op("attack_directly", target="$self")],
                condition_payload=all_of(
                    condition(controller="self", face_up=True, zone="self_monster"),
                    condition(
                        count_zone="opponent_monster",
                        count_filter=any_of(
                            condition(attribute="LIGHT"),
                            condition(attribute="DARK"),
                            condition(attribute="WIND"),
                        ),
                        count_max=0,
                    ),
                ),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["No LIGHT, DARK or WIND monster on the opponent's side means the direct attack is legal."],
    )


@recipe(
    "zombyra_the_dark",
    r"This card cannot attack a player directly\. Each time this card destroys a monster in battle, decrease the ATK of this card by (\d+) points",
    "Cannot attack directly; loses ATK whenever it destroys a monster.",
)
def _zombyra_the_dark(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "cannot_attack_directly",
                "continuous",
                [op("attack_lock", target="$self", mode="cannot_attack_directly")],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text="This card cannot attack a player directly.",
            ),
            script(
                "destroy_lose_atk",
                "on_battle_destroy_by_attacker",
                [op("modify_atk", target="$self", amount=-amount, mode="flat")],
                condition_payload=condition(custom="battle_involving_self"),
                duration="permanent",
                source_text="Each time this card destroys a monster in battle, it loses ATK.",
            ),
        ],
        ["Direct-attack lock plus the attacker-destroy ATK loss."],
    )


@recipe(
    "lesser_fiend",
    r"As long as this monster remains face-up on the field, monsters destroyed by this monster in battle are removed from play instead of being sent to the Graveyard",
    "Battle-destroyed monsters are banished.",
)
def _lesser_fiend(card, tier, match, text):
    return (
        [
            script(
                "banish_destroyed_monster",
                "on_battle_destroy_by_attacker",
                [op("banish", target="$trigger", reason=card["name"])],
                condition_payload=condition(custom="battle_involving_self"),
                source_text=text,
            )
        ],
        ["Banish the destroyed monster from the Graveyard destination."],
    )


@recipe(
    "giant_orc",
    r"When this card attacks, it is changed to Defense Position at the end of the Battle Phase\. This position cannot be changed until the end of your next turn",
    "End-of-Battle-Phase Defense change.",
)
def _giant_orc(card, tier, match, text):
    return _goblin_attack_force(card, tier, match, text)


@recipe(
    "backup_soldier",
    r"You can activate this card when there are 5 or more Monster Cards in your Graveyard\. Select up to 3 Monster Cards with an ATK of 1500 points or less \(except Effect Monster Cards\) from your Graveyard and add them to your hand",
    "Trap that returns up to three low-ATK Normal Monsters from the Graveyard.",
)
def _backup_soldier(card, tier, match, text):
    return (
        [
            script(
                "return_three_normal_monsters",
                "on_activate",
                [op("return_to_hand", target="$target", reason=card["name"])],
                condition_payload=condition(
                    count_zone="self_graveyard",
                    count_filter=condition(card_type="Monster"),
                    count_min=5,
                ),
                target_payload=target(
                    "self_graveyard",
                    {"min": 0, "max": 3},
                    all_of(
                        condition(card_type="Normal Monster"),
                        condition(atk_max=1500),
                    ),
                    optional=True,
                ),
                spell_speed=2,
                source_text=text,
            )
        ],
        ["The condition counts monsters, not all Graveyard cards."],
    )


@recipe(
    "direct_attack_monster",
    r"(?:This monster|This card) may attack your opponent's Life Points directly",
    "Continuous direct-attack permission.",
)
def _direct_attack_monster(card, tier, match, text):
    return (
        [
            script(
                "attack_directly",
                "continuous",
                [op("attack_directly", target="$self")],
                condition_payload=condition(controller="self", face_up=True, zone="self_monster"),
                duration="while_face_up",
                source_text=text,
            )
        ],
        ["Continuous direct-attack permission."],
    )


@recipe(
    "banner_of_courage",
    r"During your Battle Phase only, increase the ATK of all monsters on your side of the field by (\d+) points",
    "Continuous Spell that boosts the controller's monsters during their Battle Phase.",
)
def _banner_of_courage(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "battle_phase_team_boost",
                "on_battle_start",
                [op("modify_atk", target="$target", amount=amount, mode="flat")],
                condition_payload=condition(
                    controller="self",
                    face_up=True,
                    zone="self_spell_trap",
                    is_turn_player=True,
                ),
                target_payload=target(
                    "all_monsters", "all", condition(controller="self")
                ),
                duration="until_end_of_battle_phase",
                source_text=text,
            )
        ],
        ["Applies at the controller's Battle Phase start and expires with the Battle Phase."],
    )


@recipe(
    "soul_of_purity_and_light",
    r"This card can only be Special Summoned by removing 2 LIGHT monsters in your Graveyard from play\. As long as this card remains face-up on the field, decrease the ATK of all monsters on your opponent's side of the field by (\d+) points during his/her Battle Phase",
    "Banish-two-LIGHT inherent summon plus an opponent Battle Phase ATK debuff.",
)
def _soul_of_purity_and_light(card, tier, match, text):
    amount = int(match.group(1))
    return (
        [
            script(
                "inherent_summon",
                "inherent_summon",
                [op("inherent_special_summon", target="$self", position="attack")],
                condition_payload=all_of(
                    condition(zone="self_hand"),
                    condition(
                        count_zone="self_graveyard",
                        count_filter=condition(attribute="LIGHT"),
                        count_min=2,
                    ),
                ),
                cost=[
                    op(
                        "banish",
                        target={
                            "zone": "self_graveyard",
                            "count": 2,
                            "filter": condition(attribute="LIGHT"),
                        },
                    )
                ],
                source_text="Special Summon by banishing 2 LIGHT monsters from the Graveyard.",
            ),
            script(
                "opponent_battle_debuff",
                "on_battle_start",
                [op("modify_atk", target="$target", amount=-amount, mode="flat")],
                condition_payload=condition(
                    controller="self",
                    face_up=True,
                    zone="self_monster",
                    is_turn_player=False,
                ),
                target_payload=target("opponent_monster", "all"),
                duration="until_end_of_battle_phase",
                source_text="During the opponent's Battle Phase, their monsters lose ATK.",
            ),
        ],
        ["The inherent summon and the opponent Battle Phase debuff are separate scripts."],
    )


@recipe(
    "wroughtweiler",
    r"When this card is destroyed as a result of battle and sent to the Graveyard, add from your Graveyard to your hand 1 card that includes \"Elemental Hero\" in its card name, and 1 \"Polymerization\"",
    "Battle-destruction recovery of one Elemental HERO card and Polymerization.",
)
def _wroughtweiler(card, tier, match, text):
    return (
        [
            script(
                "recover_hero_and_polymerization",
                "on_battle_destroy",
                [
                    op(
                        "search",
                        target={
                            "zone": "self_graveyard",
                            "count": 1,
                            "filter": condition(name_contains="Elemental Hero"),
                        },
                        destination="hand",
                        reveal=True,
                        shuffle=False,
                    ),
                    op(
                        "search",
                        target={
                            "zone": "self_graveyard",
                            "count": 1,
                            "filter": condition(name="Polymerization"),
                        },
                        destination="hand",
                        reveal=True,
                        shuffle=False,
                    ),
                ],
                source_text=text,
            )
        ],
        ["Two explicit Graveyard searches; the deterministic selector takes the first matching card."],
    )


@recipe(
    "the_shallow_grave",
    r"Each player takes 1 Monster Card from his/her respective Graveyard and Special Summons them on the field in face-down Defense Position",
    "Each player revives one monster face-down.",
)
def _the_shallow_grave(card, tier, match, text):
    return (
        [
            script(
                "both_players_revive_facedown",
                "on_activate",
                [
                    op(
                        "special_summon",
                        target={"zone": "self_graveyard", "count": 1, "filter": condition(card_type="Monster")},
                        position="face_down",
                    ),
                    op(
                        "special_summon",
                        target={"zone": "opponent_graveyard", "count": 1, "filter": condition(card_type="Monster")},
                        position="face_down",
                    ),
                ],
                spell_speed=1,
                source_text=text,
            )
        ],
        ["Both players' Graveyards are selected with one monster each and Set face-down."],
    )


# ---------------------------------------------------------------------------
# Pending-reason taxonomy
# ---------------------------------------------------------------------------

PENDING_REASONS = {
    "vanilla_summoning_condition": (
        "vanilla",
        "printed text is only a summoning restriction/procedure; no effect to script",
    ),
    "runtime_attack_directly": (
        "pending",
        "direct attacks / attack restrictions are not executable by the current runtime",
    ),
    "runtime_extra_attack": (
        "pending",
        "extra attacks are not applied by the current continuous runtime",
    ),
    "runtime_piercing": (
        "pending",
        "piercing battle damage is not an operation in the current runtime",
    ),
    "runtime_dynamic_stat": (
        "pending",
        "ATK/DEF depends on a dynamic count (cards, counters, Levels, Graveyards) the runtime cannot evaluate",
    ),
    "runtime_team_stat": (
        "pending",
        "continuous ATK/DEF changes to other cards or the whole field are not applied by the current runtime",
    ),
    "runtime_equip_stat": (
        "pending",
        "equip stat bonuses are not applied by the current runtime (the engine hardcodes a small list)",
    ),
    "runtime_field_stat": (
        "pending",
        "field-spell stat changes are not applied by the current runtime (the engine hardcodes a small list)",
    ),
    "runtime_destruction_replacement": (
        "pending",
        "battle/effect destruction replacement or immunity is not implemented",
    ),
    "runtime_battle_position_lock": (
        "pending",
        "end-of-Battle-Phase position changes and position-change locks are not implemented",
    ),
    "runtime_delayed": (
        "pending",
        "turn-counted or End-Phase-delayed effects are not implemented",
    ),
    "runtime_token_summon": (
        "pending",
        "token creation and token destruction are not implemented",
    ),
    "runtime_copy_name_stat": (
        "pending",
        "copying names, Attributes, Types or original ATK/DEF is not implemented",
    ),
    "runtime_union_equip": (
        "pending",
        "Union-monster equip/unequip handling is not implemented",
    ),
    "runtime_toon": (
        "pending",
        "Toon World restrictions and direct-attack rules are not implemented",
    ),
    "runtime_spirit": (
        "pending",
        "Spirit Monster end-phase return is not implemented",
    ),
    "runtime_top_of_deck": (
        "pending",
        "the runtime returns cards to the bottom of the Deck; 'top of Deck' cannot be expressed",
    ),
    "runtime_hand_size": (
        "pending",
        "drawing/returning until a hand size is reached is not implemented",
    ),
    "runtime_condition_count": (
        "pending",
        "the activation condition needs a zone/count predicate the runtime does not expose",
    ),
    "runtime_named_field_check": (
        "pending",
        "the activation condition needs a named card on the field, which the runtime cannot check",
    ),
    "runtime_negate_activation": (
        "pending",
        "negating an opponent's activation from a set Counter Trap is not wired to a safe trigger",
    ),
    "runtime_random_outcome": (
        "pending",
        "coin/die outcomes are recorded but cannot branch the effect",
    ),
    "runtime_target_priority": (
        "pending",
        "targeting the highest ATK/DEF or all cards with the same name is not expressible",
    ),
    "runtime_continuous_trigger": (
        "pending",
        "a face-up continuous card's trigger cannot be gated on its own face-up state",
    ),
    "runtime_special_summon_position": (
        "pending",
        "special_summon is fixed to face-up Attack Position; this card needs Defense or face-down",
    ),
    "runtime_send_to_grave_schema": (
        "pending",
        "selected-card Deck-to-Graveyard send is not exposed by the current schema",
    ),
    "multi_clause": (
        "pending",
        "multiple clauses remain; at least one clause is outside the current runtime",
    ),
    "runtime_manual_spell": (
        "pending",
        "continuous spells with manual ignition effects have no activation path",
    ),
    "runtime_battle_damage_trigger": (
        "pending",
        "no 'after battle damage' trigger hook",
    ),
    "runtime_attacker_destroy_trigger": (
        "pending",
        "no 'this card destroyed a monster by battle' trigger hook",
    ),
    "runtime_position_change_trigger": (
        "pending",
        "position-change triggers are not emitted",
    ),
    "runtime_damage_step": (
        "pending",
        "Damage Step-only windows are not exposed",
    ),
    "runtime_trap_monster": (
        "pending",
        "Trap Cards that become monsters are not implemented",
    ),
    "runtime_generic_ritual": (
        "pending",
        "generic ritual-spell procedures are not in rituals.json",
    ),
    "runtime_named_activation": (
        "pending",
        "no trigger for a specific named card's activation",
    ),
    "runtime_hand_activation": (
        "pending",
        "monster effects cannot be activated from the hand",
    ),
    "runtime_inherent_special_summon": (
        "pending",
        "the engine does not implement this inherent special-summon procedure",
    ),
    "runtime_activation_cost_only": (
        "pending",
        "only an activation cost is printed; no effect operation to script",
    ),
    "runtime_attack_lock": (
        "pending",
        "attack-declaration locks are not implemented",
    ),
    "runtime_control_duration": (
        "pending",
        "temporary control with a return duration is not implemented",
    ),
    "runtime_destruction_destination": (
        "pending",
        "replacing the destruction destination is not implemented",
    ),
    "runtime_fusion_procedure": (
        "pending",
        "fusion procedure/material selection is not a script operation",
    ),
    "runtime_conditional_stat": (
        "pending",
        "conditional/original stat replacement is not implemented",
    ),
    "runtime_battle_graveyard_tracking": (
        "pending",
        "tracking monsters destroyed earlier in the turn is not implemented",
    ),
    "runtime_tribute_summon_trigger": (
        "pending",
        "Tribute Summon is not exposed as a distinct trigger/condition",
    ),
    "runtime_placement_restriction": (
        "pending",
        "placement restrictions are not implemented",
    ),
    "runtime_position_toggle": (
        "pending",
        "toggling battle positions is not implemented",
    ),
    "runtime_damage_prevention": (
        "pending",
        "damage-prevention scopes are not implemented",
    ),
    "runtime_equipped_filter": (
        "pending",
        "filters/effects based on equipped cards are not implemented",
    ),
    "runtime_summon_stat_condition": (
        "pending",
        "summon-time stat conditions are not expressible",
    ),
    "runtime_counter_distribution": (
        "pending",
        "multi-card counter distribution/removal is not implemented",
    ),
    "runtime_zone_choice": (
        "pending",
        "choosing between hand/Deck/Graveyard for the same effect is not expressible",
    ),
    "runtime_gy_summon_trigger": (
        "pending",
        "no trigger for a Special Summon specifically from the Graveyard",
    ),
    "runtime_draw_phase": (
        "pending",
        "Draw Phase-specific triggers are not implemented",
    ),
    "runtime_mode_choice": (
        "pending",
        "selecting one of several effect modes is not implemented",
    ),
    "runtime_hand_reveal": (
        "pending",
        "persistent hand reveal is not implemented",
    ),
    "runtime_skip_phase": (
        "pending",
        "skipping a named phase is not implemented",
    ),
    "runtime_attacker_info": (
        "pending",
        "the runtime does not expose the attacker/destroyer for this trigger",
    ),
    "runtime_damage_type": (
        "pending",
        "changing the damage type is not implemented",
    ),
    "runtime_upkeep_cost": (
        "pending",
        "Standby upkeep with a destroy-if-unpaid branch is not implemented",
    ),
    "runtime_grave_trigger": (
        "pending",
        "effects that trigger/apply while the card is in the Graveyard are not implemented",
    ),
    "runtime_opponent_lp_condition": (
        "pending",
        "conditions on the opponent's Life Points are not expressible",
    ),
    "runtime_source_role": (
        "pending",
        "the runtime cannot prove this source is the attacker or the attack target",
    ),
    "runtime_dynamic_target_atk": (
        "pending",
        "damage based on another card's ATK is not expressible",
    ),
    "runtime_win_condition": (
        "pending",
        "alternate win conditions are not implemented",
    ),
    "runtime_equipped_count": (
        "pending",
        "per-equipped-card scaling is not implemented",
    ),
    "runtime_dynamic_draw": (
        "pending",
        "draw count cannot use a dynamic mode",
    ),
    "runtime_global_grave_banish": (
        "pending",
        "global Graveyard-to-banished replacement is not implemented",
    ),
    "runtime_spell_counter_trigger": (
        "pending",
        "no field-scanning Spell-activation trigger for other cards",
    ),
    "runtime_trigger_scope": (
        "pending",
        "the needed global game-event trigger is not implemented",
    ),
    "runtime_lookup_set": (
        "pending",
        "looking at/reordering a Set card is not implemented",
    ),
    "runtime_zone_lock": (
        "pending",
        "locked Monster/Spell/Trap Zones are not implemented",
    ),
    "runtime_special_summoned_filter": (
        "pending",
        "filtering monsters by Special Summon provenance is not implemented",
    ),
    "runtime_attack_cost": (
        "pending",
        "attack costs/restrictions are not implemented",
    ),
    "runtime_control_lock": (
        "pending",
        "control-change locks are not implemented",
    ),
    "runtime_battle_phase_control": (
        "pending",
        "skipping/ending a Battle Phase is not implemented",
    ),
    "runtime_deck_reorder": (
        "pending",
        "deck/hand reordering and top-placement are not implemented",
    ),
    "runtime_declare": (
        "pending",
        "name/Type/Attribute declaration is not implemented",
    ),
    "runtime_name_contains": (
        "pending",
        "substring card-name filters are not expressible",
    ),
    "runtime_flip_negation": (
        "pending",
        "flip-effect negation/suppression is not implemented",
    ),
    "runtime_battle_damage_modifier": (
        "pending",
        "battle-damage arithmetic modifiers are not implemented",
    ),
    "runtime_attack_negation": (
        "pending",
        "attack negation is not implemented",
    ),
    "runtime_summon_lock": (
        "pending",
        "summon locks are not implemented",
    ),
    "runtime_activation_lock": (
        "pending",
        "card-type activation locks beyond the Trap lock are not implemented",
    ),
    "runtime_graveyard_effect": (
        "pending",
        "effects that activate from the Graveyard are not implemented",
    ),
    "runtime_standby_side": (
        "pending",
        "the runtime cannot gate a Standby trigger to one player's turn",
    ),
    "runtime_chain_face_up": (
        "pending",
        "the on_chain trigger cannot require the source to be face-up",
    ),
    "runtime_removed_from_field": (
        "pending",
        "the leave-field trigger cannot find its source after removal",
    ),
    "runtime_special_summon_position": (
        "pending",
        "special_summon is fixed to face-up Attack Position",
    ),
    "vanilla_ritual_procedure": (
        "vanilla",
        "specific Ritual Spell procedure is owned by rituals.json",
    ),
    "unclassified": (
        "pending",
        "effect text is not covered by a supported template",
    ),
    "runtime_unimplemented_effect": (
        "pending",
        "the effect needs a trigger/operation combination that is not implemented",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SUMMON_ONLY_SENTENCES = [
    re.compile(r"This card cannot be Normal Summoned(?: or Set)?\.", re.IGNORECASE),
    re.compile(r"This card cannot be Special Summoned\.", re.IGNORECASE),
    re.compile(r"This card cannot be Special Summoned except by .+?\.", re.IGNORECASE),
    re.compile(r"This card can only be Special Summoned (?:by|from|with) .+?\.", re.IGNORECASE),
    re.compile(r"This card can only be placed on the field .+?\.", re.IGNORECASE),
    re.compile(r"This card cannot be summoned unless .+?\.", re.IGNORECASE),
    re.compile(r"Your Deck is then shuffled\.", re.IGNORECASE),
    re.compile(r"The Deck is then shuffled\.", re.IGNORECASE),
]


_SUMMON_ONLY_WHOLE = [
    re.compile(
        r"This card can only be Special Summoned .+?\. (?:Your|The) Deck is then shuffled\.",
        re.IGNORECASE,
    ),
]


def summoning_condition_only(card: dict) -> bool:
    """True when the printed text is only a summon/placement restriction.

    Such a card has no effect the runtime can execute.  It is classified
    `vanilla` (no effect text), not `scripted`.
    """
    if card.get("card_type") not in {"Effect Monster", "Fusion Monster", "Ritual Monster"}:
        return False
    text = normalize(card.get("description"))
    if not text:
        return False
    if any(pattern.fullmatch(text) for pattern in _SUMMON_ONLY_WHOLE):
        return True
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not parts:
        return False
    return all(
        any(pattern.fullmatch(part) for pattern in _SUMMON_ONLY_SENTENCES)
        for part in parts
    )


_REASON_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "runtime_toon",
        re.compile(r"\bToon\b|Toon World", re.IGNORECASE),
        "Toon World summon/attack/destruction rules are not implemented",
    ),
    (
        "runtime_union_equip",
        re.compile(r"Union Monster|equip it to|unequip the Union", re.IGNORECASE),
        "Union equip/unequip is not implemented",
    ),
    (
        "runtime_inherent_special_summon",
        re.compile(
            r"you can Special Summon this card from your hand|"
            r"can be Special Summoned from your Hand by discarding|"
            r"you can Summon this card in face-up Attack Position without offering|"
            r"treat the Normal Summon of this card as a Special Summon",
            re.IGNORECASE,
        ),
        "the engine does not implement this inherent special-summon procedure",
    ),
    (
        "runtime_activation_cost_only",
        re.compile(r"^This card is activated by paying \d+ of your Life Points\.$", re.IGNORECASE),
        "the printed text is only an activation cost; there is no effect operation to script",
    ),
    (
        "runtime_attack_lock",
        re.compile(
            r"cannot declare an attack|cannot attack during this turn|"
            r"can only attack with 1 monster|monsters? .* cannot attack",
            re.IGNORECASE,
        ),
        "attack-declaration locks are not implemented",
    ),
    (
        "runtime_control_duration",
        re.compile(
            r"take control of .* until|control 1 opposing monster.* until|"
            r"control of this card cannot switch",
            re.IGNORECASE,
        ),
        "temporary control with a return duration is not implemented",
    ),
    (
        "runtime_destruction_destination",
        re.compile(
            r"destroyed by this card .* removed from play|"
            r"destroyed by this monster .* removed from play|"
            r"monster destroyed by this card .* removed from play",
            re.IGNORECASE,
        ),
        "replacing the destruction destination (banish instead of Graveyard) is not implemented",
    ),
    (
        "runtime_fusion_procedure",
        re.compile(
            r"Fusion[- ]Material Monsters?",
            re.IGNORECASE,
        ),
        "fusion procedure/material selection is not exposed as a script operation",
    ),
    (
        "runtime_conditional_stat",
        re.compile(
            r"both the ATK and DEF of this monster become|ATK and DEF of this monster become|"
            r"original ATK and DEF of this card become",
            re.IGNORECASE,
        ),
        "conditional/original stat replacement is not implemented",
    ),
    (
        "runtime_battle_graveyard_tracking",
        re.compile(
            r"destroyed in battle during this turn|monsters? destroyed in battle this turn|"
            r"destroyed.* during this turn",
            re.IGNORECASE,
        ),
        "tracking monsters destroyed earlier in the turn is not implemented",
    ),
    (
        "runtime_upkeep_cost",
        re.compile(
            r"must pay .* (?:during|at) each of your Standby Phases|"
            r"Pay \d+ Life Points (?:during|at) each of your Standby Phases|"
            r"During your Standby Phase, pay \d+ Life Points",
            re.IGNORECASE,
        ),
        "Standby upkeep with a destroy-if-unpaid branch is not implemented",
    ),
    (
        "runtime_grave_trigger",
        re.compile(
            r"exists in your Graveyard|is in the Graveyard and you have no cards in your Hand",
            re.IGNORECASE,
        ),
        "effects that trigger/apply while the card is in the Graveyard are not implemented",
    ),
    (
        "runtime_opponent_lp_condition",
        re.compile(
            r"opponent's Life Points are 3000 or less|"
            r"opponent's Life Points are at least \d+ points higher|"
            r"difference is 7000 points or more",
            re.IGNORECASE,
        ),
        "conditions on the opponent's Life Points are not expressible",
    ),
    (
        "runtime_source_role",
        re.compile(
            r"if this card attacks|if this card is attacked|when this card is attacked|"
            r"attacked by a monster on your opponent's side of the field",
            re.IGNORECASE,
        ),
        "the runtime cannot prove this source is the attacker or the attack target",
    ),
    (
        "runtime_dynamic_target_atk",
        re.compile(
            r"damage equal to the .*ATK of the (?:attacking|destroyed)|"
            r"inflict .* equal to the ATK of the attacking|"
            r"equal to the ATK of the destroyed",
            re.IGNORECASE,
        ),
        "damage based on another card's ATK is not expressible",
    ),
    (
        "runtime_win_condition",
        re.compile(r"automatic victory|you win the Duel", re.IGNORECASE),
        "alternate win conditions are not implemented",
    ),
    (
        "runtime_equipped_count",
        re.compile(r"for each card equipped|for each Equip Card equipped", re.IGNORECASE),
        "per-equipped-card scaling is not implemented",
    ),
    (
        "runtime_dynamic_draw",
        re.compile(r"Draw a number of cards.*equal to", re.IGNORECASE),
        "draw count cannot use a dynamic mode",
    ),
    (
        "runtime_global_grave_banish",
        re.compile(r"any card sent to the Graveyard is removed from play", re.IGNORECASE),
        "global Graveyard-to-banished replacement is not implemented",
    ),
    (
        "runtime_spell_counter_trigger",
        re.compile(r"Each time you or your opponent activates 1 Spell Card", re.IGNORECASE),
        "there is no field-scanning 'a Spell was activated' trigger for other cards",
    ),
    (
        "runtime_trigger_scope",
        re.compile(
            r"Each time (?:you draw|you increase your own Life Points|a card is removed from play|"
            r"your opponent's Monster Cards are sent|a player equips|"
            r"a Beast-Type monster inflicts|1 of your monsters inflicts)",
            re.IGNORECASE,
        ),
        "the needed global game-event trigger is not implemented",
    ),
    (
        "runtime_lookup_set",
        re.compile(r"look at 1 Set card", re.IGNORECASE),
        "looking at/reordering a Set card is not implemented",
    ),
    (
        "runtime_standby_side",
        re.compile(r"Standby Phase", re.IGNORECASE),
        "the runtime cannot gate a Standby trigger to one player's turn",
    ),
    (
        "runtime_chain_face_up",
        re.compile(r"Each time .*activates 1 Spell Card", re.IGNORECASE),
        "the on_chain trigger cannot require the source to be face-up",
    ),
    (
        "runtime_removed_from_field",
        re.compile(r"removed from the field|removed from your side of the field", re.IGNORECASE),
        "the leave-field trigger is evaluated after the card leaves its zone and cannot find its source",
    ),
    (
        "runtime_special_summon_position",
        re.compile(
            r"Special Summon.*(?:Defense Position|face-down Defense Position)|"
            r"(?:Defense Position|face-down Defense Position).*Special Summon",
            re.IGNORECASE,
        ),
        "special_summon is fixed to face-up Attack Position",
    ),
    (
        "runtime_token_summon",
        re.compile(r"\bToken\b", re.IGNORECASE),
        "token creation/removal is not implemented",
    ),
    (
        "runtime_spirit",
        re.compile(r"returns to the owner's hand during the End Phase", re.IGNORECASE),
        "Spirit Monster end-phase return is not implemented",
    ),
    (
        "runtime_copy_name_stat",
        re.compile(
            r"name is treated as|adopts the original ATK and DEF|take on the ATK and DEF|"
            r"ATK and DEF of 1 opponent's monster|original ATK of this card becomes|"
            r"original ATK and DEF of this card become",
            re.IGNORECASE,
        ),
        "copy/name/original-stat replacement is not implemented",
    ),
    (
        "runtime_attack_directly",
        re.compile(
            r"attack your opponent's Life Points directly|attack directly|"
            r"may attack your opponent's Life Points directly|can attack your opponent's Life Points directly",
            re.IGNORECASE,
        ),
        "direct-attack permission/restriction is not executable",
    ),
    (
        "runtime_extra_attack",
        re.compile(r"attack twice|attack once again|can attack twice", re.IGNORECASE),
        "extra attacks are not applied by the continuous runtime",
    ),
    (
        "runtime_piercing",
        re.compile(r"inflict the difference as Battle Damage", re.IGNORECASE),
        "piercing battle damage is not an operation",
    ),
    (
        "runtime_random_outcome",
        re.compile(r"toss a coin|roll (?:a |1 )?(?:six-sided )?die|roll a die", re.IGNORECASE),
        "coin/die results are recorded but cannot branch the effect",
    ),
    (
        "runtime_negate_activation",
        re.compile(r"negate the activation|negate the effect|negates the activation", re.IGNORECASE),
        "activation/effect negation needs a safe response trigger the runtime does not expose",
    ),
    (
        "runtime_destruction_replacement",
        re.compile(
            r"would be destroyed|cannot be destroyed|not destroyed as a result of battle|"
            r"is not destroyed",
            re.IGNORECASE,
        ),
        "destruction replacement/immunity is not implemented",
    ),
    (
        "runtime_battle_position_lock",
        re.compile(
            r"end of the Battle Phase|battle position cannot be changed|"
            r"position cannot be changed|changed to Defense Position at the end of the Battle Phase",
            re.IGNORECASE,
        ),
        "end-of-battle position changes and position locks are not implemented",
    ),
    (
        "runtime_delayed",
        re.compile(
            r"End Phase of the|fifth turn|next 2 turns|for 3 turns|after 20 turns|"
            r"until the End Phase of this turn|for the rest of the Duel",
            re.IGNORECASE,
        ),
        "turn-counted / delayed effects are not implemented",
    ),
    (
        "runtime_top_of_deck",
        re.compile(
            r"top of (?:your|the owner's|his/her|their|the) Deck",
            re.IGNORECASE,
        ),
        "the runtime only returns cards to the bottom of the Deck",
    ),
    (
        "runtime_hand_size",
        re.compile(
            r"until (?:they|he/she|you) (?:have|has)|until your hand has|hand has \d+ cards|"
            r"same number of cards|draw cards until",
            re.IGNORECASE,
        ),
        "hand-size-based draw/return is not implemented",
    ),
    (
        "runtime_target_priority",
        re.compile(
            r"highest ATK|highest DEF|same name|all Monster Cards of the same name|"
            r"all monsters of the same name",
            re.IGNORECASE,
        ),
        "highest-stat / same-name targeting is not expressible",
    ),
    (
        "runtime_battle_damage_trigger",
        re.compile(
            r"inflicts? (?:Battle Damage|damage) to your opponent|inflicts? battle damage|"
            r"when this card inflicts|each time you inflict battle damage|"
            r"inflicts? damage to your opponent",
            re.IGNORECASE,
        ),
        "there is no 'after battle damage' trigger hook in the runtime",
    ),
    (
        "runtime_attacker_destroy_trigger",
        re.compile(
            r"destroys? (?:a|1|an|your opponent's) monster.*(?:as a result of battle|in battle)|"
            r"destroys? .* by battle|destroys? a Monster in battle",
            re.IGNORECASE,
        ),
        "there is no 'this card destroyed a monster by battle' trigger hook",
    ),
    (
        "runtime_position_change_trigger",
        re.compile(
            r"changed from (?:Attack|Defense) Position to (?:face-up )?(?:Attack|Defense) Position",
            re.IGNORECASE,
        ),
        "position-change triggers are not emitted by the runtime",
    ),
    (
        "runtime_damage_step",
        re.compile(
            r"during the Damage Step|during damage calculation|after Damage Calculation|"
            r"only during damage calculation",
            re.IGNORECASE,
        ),
        "Damage Step-only windows are not exposed as a script trigger",
    ),
    (
        "runtime_trap_monster",
        re.compile(
            r"becomes a Monster Card|also treated as a Trap Card|treated as a Trap Card",
            re.IGNORECASE,
        ),
        "Trap Cards that become monsters are not implemented",
    ),
    (
        "runtime_generic_ritual",
        re.compile(r"This card is used to Ritual Summon any ", re.IGNORECASE),
        "generic ritual-spell procedures are not in rituals.json",
    ),
    (
        "runtime_named_activation",
        re.compile(
            r"when .* activates \"[^\"]+\"|when your opponent plays \"[^\"]+\"|"
            r"when .* is activated",
            re.IGNORECASE,
        ),
        "there is no trigger for a specific named card's activation",
    ),
    (
        "runtime_hand_activation",
        re.compile(r"^Discard this card from your hand", re.IGNORECASE),
        "monster effects cannot be activated from the hand",
    ),
    (
        "runtime_attack_cost",
        re.compile(
            r"cannot attack unless|requires? a cost of \d+ .* to attack|"
            r"cost of \d+ .* to attack",
            re.IGNORECASE,
        ),
        "attack costs/restrictions are not implemented",
    ),
    (
        "runtime_control_lock",
        re.compile(r"control of this card cannot switch", re.IGNORECASE),
        "control-change locks are not implemented",
    ),
    (
        "runtime_battle_phase_control",
        re.compile(
            r"Battle Phase for that turn ends|skips? .* Battle Phase|"
            r"cannot perform .* Battle Phase",
            re.IGNORECASE,
        ),
        "skipping/ending a Battle Phase is not implemented",
    ),
    (
        "runtime_deck_reorder",
        re.compile(
            r"arrange them|return the cards to the Deck in the same order|"
            r"return those cards to the top|return it to its original position",
            re.IGNORECASE,
        ),
        "deck/hand reordering and top-placement are not implemented",
    ),
    (
        "runtime_declare",
        re.compile(r"declare (?:1|one) (?:Type|Attribute)|declare a card name", re.IGNORECASE),
        "name/Type/Attribute declaration is not implemented",
    ),
    (
        "runtime_name_contains",
        re.compile(r"includes \"[^\"]+\" in its card name", re.IGNORECASE),
        "substring card-name filters are not expressible",
    ),
    (
        "runtime_flip_negation",
        re.compile(r"Flip Effects? (?:are not activated|.*negat)", re.IGNORECASE),
        "flip-effect negation/suppression is not implemented",
    ),
    (
        "runtime_battle_damage_modifier",
        re.compile(
            r"Battle Damage.*(?:doubled|halved|becomes 0|decreased to 0)|"
            r"damage (?:is )?doubled|damage (?:is )?halved",
            re.IGNORECASE,
        ),
        "battle-damage arithmetic modifiers are not implemented",
    ),
    (
        "runtime_attack_negation",
        re.compile(r"negate the attack", re.IGNORECASE),
        "attack negation is not implemented",
    ),
    (
        "runtime_summon_lock",
        re.compile(
            r"cannot Normal Summon|cannot Special Summon|neither player can Summon|"
            r"no monsters can be Special Summoned",
            re.IGNORECASE,
        ),
        "summon locks are not implemented",
    ),
    (
        "runtime_activation_lock",
        re.compile(
            r"Trap Cards cannot be activated|Spell Cards cannot be activated|"
            r"cannot activate (?:a |any )?(?:Quick-Play )?Spell|"
            r"cannot activate (?:a |any )?Trap",
            re.IGNORECASE,
        ),
        "card-type activation locks beyond the Trap lock are not implemented",
    ),
    (
        "runtime_graveyard_effect",
        re.compile(r"if this card is in the Graveyard|as long as this card exists in your Graveyard", re.IGNORECASE),
        "effects that activate from the Graveyard are not implemented",
    ),
    (
        "runtime_tribute_summon_trigger",
        re.compile(
            r"Tribute Summoned successfully|successful Tribute Summon|Tribute Summon or Set|"
            r"offered as a Tribute for a successful Tribute Summon",
            re.IGNORECASE,
        ),
        "Tribute Summon is not exposed as a distinct trigger/condition",
    ),
    (
        "runtime_placement_restriction",
        re.compile(r"can only be placed on the field", re.IGNORECASE),
        "placement restrictions are not implemented",
    ),
    (
        "runtime_position_toggle",
        re.compile(
            r"change its battle position|change the battle positions|"
            r"changed to Defense Position after damage calculation",
            re.IGNORECASE,
        ),
        "toggling battle positions (rather than setting one) is not implemented",
    ),
    (
        "runtime_damage_prevention",
        re.compile(
            r"damage .* (?:decreased|reduced) to 0|damage .* becomes 0",
            re.IGNORECASE,
        ),
        "battle/effect damage prevention scopes are not implemented",
    ),
    (
        "runtime_equipped_filter",
        re.compile(
            r"monsters equipped with Equip Cards|equipped with an Equip Card|"
            r"equipped to this monster",
            re.IGNORECASE,
        ),
        "filters/effects based on equipped cards are not implemented",
    ),
    (
        "runtime_summon_stat_condition",
        re.compile(
            r"monster summoned by your opponent.*(?:ATK|DEF).*500 or less",
            re.IGNORECASE,
        ),
        "summon-time stat conditions are not expressible",
    ),
    (
        "runtime_counter_distribution",
        re.compile(
            r"counter on each|remove all Spell Counters|put 3 counters on this card",
            re.IGNORECASE,
        ),
        "multi-card counter distribution/removal is not implemented",
    ),
    (
        "runtime_zone_choice",
        re.compile(
            r"from your hand, Deck, or Graveyard|from your hand or your Deck|"
            r"from your hand or Deck|from your Deck or your Graveyard|"
            r"from your hand or your Fusion Deck|from your hand, Deck or Graveyard",
            re.IGNORECASE,
        ),
        "choosing between hand/Deck/Graveyard for the same effect is not expressible",
    ),
    (
        "runtime_gy_summon_trigger",
        re.compile(r"Special Summoned from the Graveyard", re.IGNORECASE),
        "there is no trigger for a Special Summon specifically from the Graveyard",
    ),
    (
        "runtime_draw_phase",
        re.compile(r"During your Draw Phase|in the Draw Phase", re.IGNORECASE),
        "Draw Phase-specific triggers are not implemented",
    ),
    (
        "runtime_mode_choice",
        re.compile(
            r"Select and activate 1 of the following effects|Select one of the following effects|"
            r"following effects:",
            re.IGNORECASE,
        ),
        "selecting one of several effect modes is not implemented",
    ),
    (
        "runtime_hand_reveal",
        re.compile(
            r"show (?:their|his/her) (?:opponent their )?hand|must show .* hand|reveal .* hand",
            re.IGNORECASE,
        ),
        "persistent hand reveal is not implemented",
    ),
    (
        "runtime_skip_phase",
        re.compile(r"skips? (?:the |his/her |your )?[A-Z][A-Za-z ]*Phase", re.IGNORECASE),
        "skipping a named phase is not implemented",
    ),
    (
        "runtime_attacker_info",
        re.compile(
            r"player who destroyed it takes|destroyed as a result of battle, the player",
            re.IGNORECASE,
        ),
        "the runtime does not expose the attacker/destroyer for this trigger",
    ),
    (
        "runtime_damage_type",
        re.compile(r"treated as the Effect Damage", re.IGNORECASE),
        "changing the damage type is not implemented",
    ),
    (
        "runtime_condition_count",
        re.compile(
            r"when there (?:are|is) \d+|if there are \d+ or more|when you have \d+|"
            r"player whose hand contains|when \d+ or more of your cards are removed",
            re.IGNORECASE,
        ),
        "the activation condition needs a zone/count predicate",
    ),
    (
        "runtime_named_field_check",
        re.compile(
            r"face-up \"[^\"]+\" on your side of the field|when \"[^\"]+\" is on the field|"
            r"if \"[^\"]+\" is on your side of the field|while \"[^\"]+\" is on (?:your side of )?the field|"
            r"there is a face-up \"[^\"]+\"|"
            r"\"[^\"]+\"(?:, \"[^\"]+\")* and \"[^\"]+\" are face-up on your side of the field|"
            r"with \"[^\"]+\" on your (?:side of the )?[Ff]ield",
            re.IGNORECASE,
        ),
        "the condition needs a named card on the field",
    ),
    (
        "runtime_continuous_trigger",
        re.compile(
            r"As long as this card remains face-up.*(?:each time|when |if )|"
            r"Each time .* (?:inflict|draw|increase|decrease|send|discard)",
            re.IGNORECASE,
        ),
        "a face-up continuous card's trigger cannot be gated on its own face-up state",
    ),
    (
        "runtime_dynamic_stat",
        re.compile(
            r"for each|for every|equal to the number of|equal to half|"
            r"equal to the .* ATK|damage equal to|"
            r"\bx\s*\d|\bmultiplied by|number of .* x",
            re.IGNORECASE,
        ),
        "ATK/DEF/damage scales with a dynamic count",
    ),
]


_RITUAL_PROCEDURE = re.compile(
    r'This card is used to (?:Ritual )?[Ss]ummon "[^"]+"\. '
    r"You must also (?:offer|Tribute) monsters whose total (?:Level Stars?|Levels?) equal \d+ or more"
    r"(?: (?:as a Tribute )?from the field or your hand(?: as a Tribute)?)\.",
    re.IGNORECASE,
)


def ritual_procedure_only(card: dict) -> bool:
    """True for a specific Ritual Spell whose text is only its procedure.

    These cards have no standalone effect: `rituals.json` owns the monster /
    spell / level relationship.  Generic ritual spells ("any DARK monster" or
    "any EARTH monster") are not covered by `rituals.json` and stay pending.
    """
    if card.get("card_type") != "Spell":
        return False
    return bool(_RITUAL_PROCEDURE.fullmatch(normalize(card.get("description"))))


def classify_pending(card: dict) -> tuple[str, str, str]:
    """Return (status, reason_code, detail) for a non-scripted card."""
    if summoning_condition_only(card):
        return (
            "vanilla",
            "vanilla_summoning_condition",
            "printed text is only a summoning restriction/procedure; no effect to script",
        )
    if ritual_procedure_only(card):
        return (
            "vanilla",
            "vanilla_ritual_procedure",
            "ritual procedure is data in rituals.json; no standalone effect to script",
        )

    text = normalize(card.get("description"))
    subtype = card.get("subtype") or ""

    if re.search(r"\bToken\b", text, re.IGNORECASE):
        return (
            "pending",
            "runtime_token_summon",
            "token creation and token destruction are not implemented",
        )
    if re.search(
        r"must pay .* (?:during|at) each of your Standby Phases|"
        r"Pay \d+ Life Points (?:during|at) each of your Standby Phases|"
        r"During your Standby Phase, pay \d+ Life Points",
        text,
        re.IGNORECASE,
    ):
        return (
            "pending",
            "runtime_upkeep_cost",
            "Standby upkeep with a destroy-if-unpaid branch is not implemented",
        )
    if re.search(r"Monster Card Zones?.*cannot be used|selected zones cannot be used", text, re.IGNORECASE):
        return (
            "pending",
            "runtime_zone_lock",
            "locked Monster/Spell/Trap Zones are not implemented",
        )
    if re.search(r"destroy all Special Summoned monsters", text, re.IGNORECASE):
        return (
            "pending",
            "runtime_special_summoned_filter",
            "filtering monsters by Special Summon provenance is not implemented",
        )

    if (
        card.get("card_type") == "Spell"
        and subtype == "Continuous"
        and re.search(r"Offer 1 monster|Tribute 1", text, re.IGNORECASE)
    ):
        return (
            "pending",
            "runtime_manual_spell",
            "the runtime has no manual activation path for a Continuous Spell's ignition effect",
        )

    if subtype == "Equip" and re.search(r"\bATK\b|\bDEF\b", text, re.IGNORECASE):
        return (
            "pending",
            "runtime_equip_stat",
            "equip stat bonuses are not applied by the runtime (only a hardcoded engine list works)",
        )
    if subtype == "Field" and re.search(r"\bATK\b|\bDEF\b", text, re.IGNORECASE):
        return (
            "pending",
            "runtime_field_stat",
            "field-spell stat changes are not applied by the runtime (only a hardcoded engine list works)",
        )

    for code, pattern, detail in _REASON_RULES:
        if pattern.search(text):
            # Dynamic-stat wording often appears in an otherwise continuous
            # card; keep the more specific code when it is the first hit.
            return ("pending", code, detail)

    if subtype == "Equip":
        return (
            "pending",
            "runtime_equip_stat",
            "equip stat bonuses are not applied by the runtime (only a hardcoded engine list works)",
        )
    if subtype == "Field":
        return (
            "pending",
            "runtime_field_stat",
            "field-spell stat changes are not applied by the runtime (only a hardcoded engine list works)",
        )
    if re.search(r"As long as this card remains face-up", text, re.IGNORECASE):
        return (
            "pending",
            "runtime_team_stat",
            "continuous changes to other cards / the field are not applied by the runtime",
        )

    sentence_count = len([part for part in re.split(r"(?<=[.!?])\s+", text) if part])
    if sentence_count > 1:
        return (
            "pending",
            "multi_clause",
            "multiple clauses remain; at least one clause is outside the current runtime",
        )
    return (
        "pending",
        "runtime_unimplemented_effect",
        "the effect needs a trigger/operation combination that is not implemented",
    )


def build_payload(card: dict, tier: int) -> dict | None:
    """Return a valid script payload for *card*, or None if unsupported."""
    text = normalize(card.get("description"))
    if not text:
        return None
    candidates = [text]
    if text.endswith("."):
        candidates.append(text[:-1].rstrip())
    for recipe in RECIPES:
        for candidate in candidates:
            match = recipe.pattern.fullmatch(candidate)
            if not match:
                continue
            result = recipe.build(card, tier, match, text)
            if result is None:
                return None
            scripts, notes = result
            if not scripts:
                return None
            return _payload(card, tier, scripts, notes)
    return None


