# Effect runtime interface (A05 → A04)

Status: **contract request**, not implemented. A04 owns `DAEffectRuntime.*` and
`DADuelEngine.*`; A05 owns the JSON scripts described here. This document is the
minimum API the scripts in `Content/Data/Effects/` need. Nothing in this file
authorises a C++ edit by A05.

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
| `SendToGraveyard(card, reason)` | Non-destruction send; must not trigger destruction effects. |
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

## 9. Non-goals and boundaries

- A05 does not add C++ methods, edit `DADuelEngine.*`, or change the duel UI.
- A05 does not choose AI policy; it only supplies prompt data and condition
  semantics.
- A04 owns chain/timing, damage-step structure, replay determinism and the
  public `DAEffectRuntime` API.
- Any new primitive must be added to `schema.json`, `OP_SPECS`/`COST_SPECS` in
  `Tools/effects/validate_effects.py`, this document, and A04's runtime in the
  same change.
