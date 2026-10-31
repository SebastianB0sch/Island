# Effect runtime interface (A05 → A04)

Status: **A04 implementation in progress; A05 consumes the implemented subset.**
A04 owns `DAEffectRuntime.*` and `DADuelEngine.*`; A05 owns the JSON scripts
described here. This document remains the contract for the primitives the
scripts in `Content/Data/Effects/` need. Nothing in this file authorises a C++
edit by A05.

## 1. Contract summary

The runtime consumes one `EffectScript` per card:

```text
CardEffectScript
  card_id, name, card_type, tier, status, source_text
  scripts[]
    id, trigger, condition?, cost[], target?, operations[], duration?,
    optional, spell_speed, once_per_turn, source_text
```

Scripts are pure data. They contain no pointers, no UObject references and no
callback names that are not in the registries below. The runtime must reject an
unknown trigger, condition key, selector zone, cost op or operation instead of
silently resolving it as a no-op.

The six things the runtime must provide:

1. **Selector resolver** — turn a `target` into a deterministic list of card
   references, with a prompt when the choice is not forced.
2. **Condition evaluator** — evaluate `condition` against the current duel
   state, including continuous recalculation while a source is face-up.
3. **Cost payer** — validate and pay a cost atomically before activation; a
   failed cost must leave the state unchanged.
4. **Operation executor** — execute the ordered `operations` with event hooks
   and visual events, aborting safely if the duel ends mid-chain.
5. **Event bus** — deliver the hook list in §5 with the correct timing and
   chain state.
6. **Prompt bridge** — expose target/optional/cost/order choices as data for
   A09; the runtime must also have an AI policy for the same prompts.

## 2. Card and zone queries

The current engine already has private helpers for most of these. A04 should
promote a stable, script-safe subset to `DAEffectRuntime`, rather than letting
scripts call `FDuelEngine` internals.

| Primitive | Contract |
| --- | --- |
| `FindCard(uid)` | Resolve a live card reference; returns null if it left its zone. |
| `FindCards(zone, filter)` | Iterate a zone in deterministic order (zone index, then uid). |
| `ControllerOf(card)` | Current controller, not original owner. |
| `OwnerOf(card)` | Original owner, for return-to-owner and owner checks. |
| `IsFaceUp(card)` | False for face-down monsters and set Spells/Traps. |
| `PositionOf(card)` | Attack / Defense / face-down; no "unknown" state. |
| `EffectiveAtk(card)` / `EffectiveDef(card)` | Applies equip, field, continuous and counter modifiers in a documented order. |
| `EffectiveLevel(card)` | Applies level modifiers (A Legendary Ocean, etc.). |
| `CardType(card)` / `Subtype(card)` / `Attribute(card)` / `MonsterType(card)` | Raw card data. |
| `CounterCount(card, counter)` | Counter lookup by typed name (`spell`, `bushido`, ...). |
| `ZoneOf(card)` | Hand/Deck/Graveyard/Banished/Extra/Monster/SpellTrap/Field. |
| `CountZone(zone, filter)` | Count for conditions such as "3 or more". |
| `HasFieldSpell(side, name)` | Face-up Field Spell check. |
| `IsTurnPlayer(side)` / `Phase()` / `TurnNumber()` | Timing predicates. |
| `Lp(side)` / `HandCount(side)` / `DeckCount(side)` | Player state for conditions. |

Determinism: all multi-card selectors must define a stable order. When the
player or AI chooses, the prompt must receive the same ordered candidate list.

## 3. Movement and summon primitives

These operations must update the same zone/visual/log bookkeeping as the
existing engine helpers (`Draw`, `MoveToGrave`, `MoveToBanished`,
`PlaceMonster`, `PlaceSpellTrap`, `RemoveFromZone`, `ShuffleSide`).

| Primitive | Notes |
| --- | --- |
| `Draw(side, count, reason)` | Deck-out is a loss condition; emit draw events. |
| `Discard(card, reason)` | From hand only; triggers discard hooks. |
| `Mill(side, count, reason)` | Deck to Graveyard. |
| `Banish(card, reason)` | Any zone to Banished; preserve face-up/position metadata where relevant. |
| `ReturnToHand(card)` / `ReturnToDeck(card, top/bottom/shuffle)` | Owner-aware. |
| `ReturnToExtra(card)` | Fusion/Synchro-style Extra Deck return. |
| `Destroy(card, byBattle, reason)` | Runs destruction replacement/negation and `on_destroy`. |
| `SendToGraveyard(card, reason)` | Non-destruction send; must not trigger destruction effects. Exposed by `schema.json` as `send_to_graveyard` (the runtime also accepts `send_to_grave`). |
| `Search(side, filter, destination, reveal, shuffle)` | Deck search with reveal and mandatory shuffle. |
| `Excavate(side, count, filter, destination)` | Pick up, reveal, split into summoned/sent-to-grave groups. Used by Cyber Jar. |
| `Reveal(card)` / `RevealAndReturn(card)` | Visual event and opponent information. |
| `NormalSummon(card, tributes)` | Tribute count and normal-summon lock checks. |
| `FlipSummon(card)` | Position and flip-effect timing. |
| `SpecialSummon(card, position, source, reason)` | Must respect `CanBeSpecialSummonedByEffect` and summon locks. |
| `FusionSummon(result, materials, fusionType)` | Validates recipe, sends/banishes materials, places result. |
| `RitualSummon(monster, spell, tributes)` | Validates level sum and ritual spell. |
| `ContactFusion(result, materials)` | Banish materials from the field, no Polymerization. Missing today. |
| `SetSpellTrap(card)` / `SetMonster(card)` | Set is not a flip summon. |
| `ChangePosition(card, position)` | Once-per-turn and position-change locks. |
| `Equip(spell, target)` / `AttachEquip` | Tracks `EquippedToUid`; cleans up when either leaves. |
| `TakeControl(card, newController, duration)` | Return control at the stated duration. |
| `Copy(card, source)` / `CopyName` / `CopyStats` | For copy effects. |
| `CreateToken(side, tokenSpec)` | Token stats/type/attribute/level and "token" marker. |

## 4. Effect, combat and player primitives

| Primitive | Notes |
| --- | --- |
| `Activate(card, chainLink)` | Checks spell speed, ignition/timing, once-per-turn and activation locks. |
| `NegateActivation(card)` / `NegateEffect(card)` | Distinguish activation negation from effect negation. |
| `PayCost(costList)` | Atomic; abort activation if any cost is illegal. |
| `InflictDamage(side, amount, reason)` / `GainLp` / `PayLp` | Damage vs. cost vs. LP gain are separate events. |
| `ModifyAtk(card, amount, duration, source)` / `ModifyDef` | Continuous and lingering variants; recompute effective stats. |
| `AddCounter(card, counter, amount, max)` / `RemoveCounter` | Max and removal legality. |
| `LockActivation(filter, mode)` | Jinzo-style continuous lock; recomputed on zone changes. |
| `AllowFusion(fusionType, banishMaterials)` | Fusion Gate-style procedure registration. |
| `SkipPhase(side, phase)` / `SkipDraw` | Used by Fenrir-style effects. |
| `ExtraAttack(card, count)` / `AttackDirectly(card)` | Battle-phase state. |
| `RedirectAttack(attacker, newTarget)` | Attack replay and damage-step timing. |
| `RedirectBattleDamage(card, to)` | Amazoness Swords Woman; damage receiver changes, not the battle result. |
| `PreventBattleDamage(side, scope)` / `BattleDamageZero(card)` | Winged Kuriboh / Dark Flare Knight. |
| `RollDie(count)` / `TossCoin(count)` | Seeded RNG; result recorded in the replay log. |
| `Shuffle(side)` / `RevealTop(side, count)` | Deterministic with the duel seed. |
| `DeclareName(prompt)` / `LookAtDeck` | Prompt data for A09. |
| `EndDuel(winner, reason)` | Guard every operation loop against a winner being set mid-effect. |

## 5. Event hooks

The runtime must emit these hooks with a payload containing the source card,
controller, event card(s), previous/next zone and chain link. Hooks are ordered:
turn-player effects first, then non-turn-player, then mandatory before optional.

| Hook | Fires when | Example consumers |
| --- | --- | --- |
| `OnDuelStart` | After both decks are shuffled and hands drawn. | Opening continuous effects. |
| `OnTurnStart` / `OnTurnEnd` | Before draw / after end-phase resolution. | Once-per-turn resets, lingering expiry. |
| `OnDraw` | Each card drawn (including draw-phase draw). | Draw triggers, "when you draw". |
| `OnStandby` | Standby Phase after turn-start triggers. | Maintenance costs, counters. |
| `OnMain` | Main Phase 1 / 2 entry. | Ignition availability. |
| `OnBattleStart` | Battle Phase entry. | Battle-phase locks. |
| `OnAttackDeclared` | Attacker chosen, before target selection resolves. | Sakuretsu Armor, Mirror Force timing. |
| `OnAttackTarget` | Target chosen, before damage calculation. | Redirect/negate attack. |
| `OnDamageCalculated` | After ATK/DEF comparison, before damage applied. | Damage modifiers, battle protection. |
| `OnBattleDestroy` | A monster is destroyed by battle. | Flame Wingman burn, recruit effects. |
| `OnDestroy` | Any destruction (battle or effect). | "When destroyed" triggers, floating effects. |
| `OnSentToGraveyard` | Any card sent to Graveyard (including discard/mill). | Sangan, Witch of the Black Forest. |
| `OnRemovedFromField` | Card leaves the field for any destination. | Mokey Mokey King, leave-field triggers. |
| `OnSummon` | Normal, Flip, Special, Fusion or Ritual Summon succeeds. | Bottomless Trap Hole, summon locks. |
| `OnNormalSummon` | Normal Summon only (not Set). | Breaker, "when Normal Summoned". |
| `OnFlipSummon` | Flip Summon only. | Flip-summon traps. |
| `OnFlip` | A face-down monster is flipped face-up by any means. | Man-Eater Bug, Morphing Jar. |
| `OnSpecialSummon` | Special Summon only. | Summon-response traps. |
| `OnFusionSummon` / `OnRitualSummon` | After the summon procedure succeeds. | Fusion/ritual support. |
| `OnActivate` | A Spell/Trap/effect activation is declared. | Counter traps, spell counters. |
| `OnChain` | A chain link is added. | Chain-building and spell-speed checks. |
| `OnEnd` | End Phase triggers. | End-phase burn, temporary control return. |

Continuous effects are not one-shot hooks: they register a predicate and are
recomputed whenever the relevant zone, position, face-up state, counter or
controller changes. The runtime must expose `RecomputeContinuous()` and call it
after every state mutation.

**Gate 3 source-UID rule (implemented).** `FireEvent` always considers the
event's `SourceCard` first. For source-bound triggers (`on_summon`,
`on_normal_summon`, `on_special_summon`, `on_flip_summon`, `on_flip`,
`on_fusion_summon`, `on_ritual_summon`, `on_activate`, `on_chain`,
`on_attack_declared`, `on_attack_target`, `on_damage_calculated`,
`on_battle_destroy`, `on_destroy`, `on_sent_to_graveyard`,
`on_removed_from_field`), another copy of the same card id does not fire merely
because it shares the card name or id: the script on the source instance is the
only copy that runs. Two copies of the same card therefore do not both trigger
when only one is summoned/destroyed.

Field-wide response scans are preserved for different cards: Spell/Trap cards
on the field are still considered for summon, destroy, leave-field and attack
responses (for example Bottomless Trap Hole on `on_summon` and Sakuretsu Armor
on `on_attack_declared`). `on_activate` and `on_chain` are strictly source-only
because they identify the card whose activation/link is being processed.

**Gate 3 follow-up self-binding.** `on_battle_destroy`,
`on_sent_to_graveyard`, `on_tribute_summon`, `on_position_change`,
`on_battle_destroy_by_attacker` and `on_battle_damage` are now self-only by
default, and Monster `on_summon`/summon variants are self-only too.  A script
must set `"field_scan": true` or `"event_source_is_self": false` to react to
another card's event.  This keeps equip/Graveyard/recruiter triggers from
firing when a different card leaves the field.  Continuous and replacement
effects continue to use `RecomputeContinuous()` and the field-wide timing
scans.

## 6. Selector and prompt contract

A selector is data:

```json
{
  "zone": "any_monster",
  "count": 1,
  "filter": { "face_up": true, "atk_max": 1500 },
  "chooser": "controller",
  "optional": true,
  "reveal": false
}
```

The resolver returns:

```text
TargetResolution
  candidates[]        ordered card refs that passed the filter
  min, max            selection bounds ("all" => candidates.size())
  chooser             controller / opponent / random
  promptKey           stable key for A09 localization and replay
  optional            can the player decline?
```

Prompt kinds the runtime must emit for A09 and the AI:

- `SelectTargets` (min/max, ordered candidates, filter description)
- `SelectOption` (optional yes/no, mode choices)
- `SelectCost` (which card to discard/tribute, or payment order)
- `SelectPosition` (Attack/Defense/face-down)
- `SelectZone` (Ojama King-style zone selection)
- `SelectOrder` (simultaneous trigger ordering)
- `SelectName` (DeclareName / copy effects)
- `SelectEffect` (which optional trigger to activate)

Every prompt must be derivable from the serialized state plus the script, so
save/load and replay can resume at the same prompt.

## 7. Fusion and ritual requirements

### Fusion

- Load `fusions.json` with `result`, `materials`, `fusionTypes`,
  `materialsType`, `anyCount`, `confidence`, `source`, `status`.
- Validate the recipe before summoning; reject wrong materials, duplicate
  materials beyond the printed count, and Fusion Monsters that are not in the
  player's Extra Deck.
- Support generic recipes (`materialsType` + `anyCount`), starting with F.G.D.
  (`Dragon` ×5).
- Add mixed specific/generic material slots for UFOroid Fighter
  (`UFOroid` + 1 Warrior-Type). Until then, recipe 1156 remains
  `status: unresolved` and must not be selectable.
- Add contact fusion (745/747/774/775): banish the named materials from the
  field, no Polymerization, then place the result.
- Recognise `Polymerization`, `Miracle Fusion`, `Dragon's Mirror`, `Power Bond`
  and `Fusion Gate`. The current engine resolves only the first three; the data
  marks the other two as `engineReady: false`-equivalent through notes.

### Ritual

- Load `rituals.json`; each entry has `monster`, `ritual_spell`,
  `level_requirement` and `materials.mode = "level_sum"`.
- Validate that the Ritual Spell is in hand/field, the monster is in hand, and
  the tributes' total Level is at least `level_requirement`.
- Send the Ritual Spell and tributes to the Graveyard, then Special Summon the
  Ritual Monster as a Ritual Summon.
- The current engine only implements Legendary Flame Lord + Incandescent
  Ordeal; generic ritual handling is a required A04 primitive.

## 8. Current engine gaps blocking the example scripts

These are already represented in the example scripts and need runtime support:

| Script | Missing contract |
| --- | --- |
| 29 Sangan | `on_sent_to_graveyard` reason `sent_from_field_to_graveyard`; search + reveal + shuffle. |
| 348 Jinzo | Continuous `lock_activation` over all Trap Cards, including set Traps. |
| 651 Exiled Force | Ignition prompt; tribute-self cost; field-wide target. |
| 639 Amazoness Swords Woman | Battle-damage redirection after damage calculation. |
| 436 Mystical Space Typhoon | Quick-Play spell-speed 2 activation from hand/set. |
| 849 Sakuretsu Armor | `on_attack_declared` trap window and attacking-monster selector. |
| 686 Bottomless Trap Hole | `on_summon` covering Normal/Flip/Special, ATK filter and destroy→banish chain. |
| 259 Morphing Jar | FLIP trigger, all-hands discard, both-player draw, correct ordering. |
| 787 Breaker | Counters, `modify_atk` per counter, counter-removal cost. |
| 637 Fusion Gate | Field-spell continuous `allow_fusion` with banish materials. |

## 9. Gate 3 runtime follow-up (A04)

The following primitives are implemented by `DAEffectRuntime.*` and are the
contract for the next A05 generation pass.  They are additive: the legacy
137-card handlers and all existing scripts keep running unchanged.

### 9.1 New event hooks

| Trigger | Payload / timing |
| --- | --- |
| `on_attack_target` | Fired after `on_attack_declared`, before traps and damage. `$attacker` / `$attack_target` are available. |
| `on_damage_step` | Start of the Damage Step, before `on_damage_calculated`. |
| `on_battle_damage` | After battle damage is actually applied. `DamageReceiver`, `DamageAmount`, `bDirectAttack`, `$attacker` and `$attack_target` are set. |
| `on_battle_destroy_by_attacker` | The source monster destroyed the event monster by battle. `$trigger` is the destroyed monster. |
| `on_position_change` | Source changes battle position; `PreviousPosition` is carried on the event. |
| `on_tribute_summon` | Normal Summon with one or more tributes; `tribute_min` can gate the trigger. |
| `inherent_summon` | Manual inherent Special Summon from the hand, activated through `ActivateInherentSummon`. |

`on_removed_from_field` now runs from the last known card snapshot after the
source has left its zone.  `on_standby` can be gated to one player's turn with
`"turn": "self"` or `"turn": "opponent"`.

### 9.2 Selectors and conditions

New condition keys: `turn`, `phase`, `name_contains`, `name_on_field`,
`count_zone`, `count_zones`, `count_filter`, `count_min`, `count_max`,
`equipped_min`, `tribute_min`, `graveyard_min`, `banished_min`, `deck_min`,
`extra_min`, `monster_min`, `spell_trap_min`, `damage_step`, `attack_direct`,
`has_attacked`, `is_turn_player`, `event_source_is_self` and `field_scan`.

New target zones: `deck_top`, `equipped_monster`, `self_all`,
`opponent_all` and `all_cards_and_hands`.  For `equip_continuous` scripts the
condition subject and a `$self` stat target are the **equipped monster**, not
the Equip Spell itself; `$equipped` is an explicit alias.  A missing stat
target on `field_continuous` applies to every face-up monster, and a target
object (`{"zone": "all_monsters", "filter": ...}`) applies team-wide.

### 9.3 Stat, damage and counter operations

| Op | Fields | Behaviour |
| --- | --- | --- |
| `modify_atk` / `modify_def` | `amount`, `mode`, `counter`, `count_zone`, `count_zones`, `count_filter`, `multiplier`, `divisor` | Modes: `flat`, `per_counter`, `per_card`/`count`, `per_level`, `per_atk`/`atk`, `per_def`/`def`, `half_atk`, `half_def`, `per_hand`, `per_graveyard`, `per_banished`, `per_deck`, `per_extra`, `per_monster`, `per_spell_trap`, `set_atk`, `set_def`. |
| `inflict_damage` / `gain_lp` | same dynamic fields | Damage/LP amount can use any of the dynamic modes. |
| `battle_damage_modifier` | `mode`: `zero`, `half`, `double` | Applied to battle damage dealt/received by the target. |
| `piercing` | `target` | Continuous or lingering piercing permission. |
| `extra_attack` / `attack_directly` | `target`, optional `count` | Battle-phase permissions; extra attacks also work through continuous scripts. |

Continuous stats are recalculated from the current board on every
`RecomputeContinuous()` and removed when their source or equipped target
leaves.  Equip Spell stat scripts take precedence over the legacy hardcoded
equip list, so a card is never counted twice.

### 9.4 Attack, battle and destruction controls

| Op | Fields | Behaviour |
| --- | --- | --- |
| `attack_lock` / `must_attack` | `target`, `mode`, `player`, `amount`, `side_wide` | `cannot_attack`, `cannot_attack_directly`, `must_attack`, `max_attackers`/`only_one_attacker`. `until_end_of_turn` locks also cover monsters summoned later in the turn. |
| `negate_attack` | none | Sets the one-shot attack-negation flag consumed by the engine after `on_attack_target`. |
| `battle_position_lock` | `target`, `mode` | `cannot_change` or `defense_at_end` (applied by `OnBattleEnd`). |
| `destruction_replacement` / `destroy_replace` | `target`, `mode` | `cannot_be_destroyed`, `cannot_be_destroyed_by_battle`, `banish_instead`. Effect-destruction still works when only battle immunity is registered. |
| `summon_lock` | `player`, `mode` | `normal`, `special`, `both`, `normal_only`, `special_only`. |
| `spirit_return` | `target` | Registers a Spirit Monster that returns to the hand in its controller's End Phase. |
| `union_equip` / `union_unequip` | `target`, `position` | Moves a Union monster between the Monster Zone and a Spell/Trap slot while preserving `EquippedToUid`. |

### 9.5 Position, Deck and random outcomes

- `special_summon` / `summon` accept `"position": "attack" | "defense" |
  "face_down"`; face-down Defense is a Set, not a Flip Summon.
- `return_to_deck` accepts `"destination": "deck_top"` or
  `"position": "top"`.  `deck_top` is the card the next `Draw` takes.
- `roll_die` / `toss_coin` use the duel's seeded `FRandomStream`.  `count`,
  `success_min`, `success_max` and `threshold` control the result, and
  `success_operations` / `failure_operations` contain nested operation arrays.
  `GetLastRandomResult()` / `GetLastRandomResults()` expose the recorded
  outcome for replay tests.
- `negate` / `negate_activation` mark the addressed chain link (or the
  `Event.ChainLink` target of a Counter Trap response) negated.
- `inherent_special_summon` performs the source card's printed inherent
  procedure without applying `CanBeSpecialSummonedByEffect`.

### 9.6 Activation persistence

`FDuelEngine` decides whether an activated Spell/Trap remains on the field
from the card's printed subtype first: `Equip`, `Field` and `Continuous` cards
stay face-up.  The loaded data script is the second source of truth:
`equip_continuous` and `field_continuous` triggers, or a `continuous` /
`on_activate` script with `duration: while_face_up|permanent`, also keep the
card registered.  The old name lists remain only as a fallback for the shipped
137-card handlers.

Field Spells are placed in the Field Zone and immediately trigger
`RecomputeContinuous()`.  Equip Spells stay face-up until their `on_activate`
script attaches them, then `AttachEquip` updates `EquippedToUid` and
recalculates.  Continuous Spells/Traps are recalculated when they are flipped
face-up on activation.  Destruction, target loss and counter-negation always
remove the card through `DestroySpellTrap`/`MoveToGrave` and clear its
registered continuous state.  Engine fallback stat tables are skipped when a
card has an `equip_continuous`/`field_continuous` stat script, so stats are
never applied twice.

### 9.7 Source binding for self triggers

`on_battle_destroy`, `on_sent_to_graveyard`, `on_tribute_summon`,
`on_position_change`, `on_battle_destroy_by_attacker` and `on_battle_damage`
are self-only by default: a script only runs when the event's source UID is
its own UID.  `on_summon`/`on_normal_summon`/`on_special_summon`/
`on_flip_summon` use the same rule for Monster sources, while Spell/Trap
responses (Bottomless Trap Hole, Mispolymerization) keep the field-wide scan.

A script can opt into another card's event explicitly:

```json
"condition": { "field_scan": true }
```

or equivalently `"event_source_is_self": false`.  `event_source_is_self: true`
makes the self binding explicit and is useful for documentation.  The same-ID
copy guard remains: two copies of one card never both fire for one event.
Zone conditions are evaluated against the event-time source zone snapshot, so
an earlier operation in the same event cannot make a later script appear to be
in a different zone.

### 9.8 Runtime self-test

`-DAEffectRuntimeSelfTest` and `da.EffectRuntimeSelfTest` now run **124**
checks, including a load regression for all **253** script files / **312**
script entries and focused single/continuous/cleanup cases for every
primitive above, plus explicit two-copy/other-card source-binding cases.

## 10. Non-goals and boundaries

- A05 does not add C++ methods, edit `DADuelEngine.*`, or change the duel UI.
- A05 does not choose AI policy; it only supplies prompt data and condition
  semantics.
- A04 owns chain/timing, damage-step structure, replay determinism and the
  public `DAEffectRuntime` API.
- Any new primitive must be added to `schema.json`, `OP_SPECS`/`COST_SPECS` in
  `Tools/effects/validate_effects.py`, this document, and A04's runtime in the
  same change.
