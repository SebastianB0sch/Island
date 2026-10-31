# Duel Engine Notes — Rules Architecture Pass (A04)

Status: additive scaffolding. The shipped 137-card duel remains the regression
baseline. No existing HUD call site had to change: if nothing queues a choice,
the engine behaves exactly as before. All new behaviour that can alter the
legacy flow is behind a flag whose default is the old behaviour.

## Files

| File | Purpose |
| --- | --- |
| `Public/DADuelRules.h` | Plain value types: choices, chain links, timing rules, deck validation, scenarios, ante, result stats. No UObject dependency. |
| `Public/DADuelEngine.h` / `Private/DADuelEngine.cpp` | Engine integration and public API. |
| `Public/DADuelRulesSelfTest.h` / `Private/DADuelRulesSelfTest.cpp` | `-DADuelRulesSelfTest` / `da.DuelRulesSelfTest`. |
| `Docs/DuelEngine_Notes.md` | This document. |

## Choice / targeting model

`FDuelChoiceRequest` describes one rules question:

- `Type` (`EDuelChoiceType`): card/cards/zone/yes-no/chain response/ante/generic.
- `Prompt`, `Options` (`FDuelChoiceOption`), `MinSelections`, `MaxSelections`.
- `SourceCardUid` / `SourceCardId` — the effect asking.
- `Side` — who must answer.
- `TargetZone` — hint for targeting UI.
- `DefaultOptionIds` — sensible AI/default answer.
- `bCancellable` — whether `CancelChoice` is legal.

`FDuelChoiceOption` carries `Id`, `Label`, `CardUid`, `CardId`, `Zone`,
`ZoneIndex`, `bEnabled` and `DisabledReason`. Disabled options are visible to
the UI but cannot be submitted.

### Flow

1. An effect calls `RequestChoice(Request, OnResolved)`.
2. If `Request.Side == Opponent` (and `bAutoAnswerAiChoices`, default true), the
   engine answers immediately with `DefaultOptionIds` (or the first enabled
   option up to `MinSelections`) and invokes the callback. The choice never
   reaches the queue.
3. Otherwise the request is queued. `GetPendingChoice()` / `GetPendingChoices()`
   expose it. While a choice is pending, `CanPlayerAct()` is false and
   `GetHandActions`/`GetMonsterActions`/`GetSpellTrapActions` return empty; the
   UI should present the prompt instead of the board actions.
4. The UI calls `AnswerChoice(RequestId, OptionIds, Error)` (or
   `AutoAnswerPendingChoice`). The callback runs, the queue advances, and the
   duel continues.
5. `CancelChoice` is only legal for `bCancellable` requests; the callback
   receives an empty option list to signal cancellation.

Request ids are engine-assigned when `RequestId <= 0`. Only the head of the
queue can be answered. `ClearPendingChoices()` is a debug/reset helper; the
queue is also cleared when the duel ends.

A choice is not required for existing automatic effects. Existing effects keep
their auto-targeting; A05 can opt into prompts card by card.

`RequestOptionalTrigger(Card, Prompt, bDefaultYes, Callback)` is a convenience
wrapper that queues a Yes/No prompt (`Activate` / `Do not activate`) for the
player. A05 should use it for "you may" player triggers; for opponent-side
optional triggers, build an `FDuelChoiceRequest` with `Side = Opponent`.

## Chain stack

`FDuelChainLink` fields: `LinkIndex` (1-based, engine-assigned), `CardUid`,
`CardId`, `Controller`, `Speed`, `EffectId`, `LinkType`, `Label`,
`TargetUids`, `bNegated`, `bResolved`, `bCardEffect`.

- `StartChain(Link, Error)` creates link 1. Returns `0` on failure.
- `AddChainLink(Link, Error)` appends a response. With
  `bEnforceChainSpellSpeeds` (default true), a new link must be at least as fast
  as the current top link; only Spell Speed 3 can respond to a Speed 3 link.
- `NegateChainLink(LinkIndex, Error)` flags a link. A negated link still counts
  for chain order but does not execute.
- `ResolveChain(Error)` resolves **last link first**, appends each link to
  `GetLastResolvedChain()` in resolution order, appends card uids to
  `GetResolvedChainOrder()`, then empties the open chain.
- Link resolution:
  - `bCardEffect == true` and `EffectId == 0`: look up the card and call the
    legacy `ResolveSpell` / `ResolveTrap`.
  - `EffectId != 0`: call the optional `SetChainEffectResolver` callback
    (A05 hook). Without a callback the engine only logs that the effect id
    resolved. Set `bCardEffect = false` for script-only links so the legacy
    card resolver does not also run.
  - `bCardEffect == true` non-continuous Spells/Traps are moved to the
    Graveyard after resolution. Continuous/Equip/Field cards stay.
  - A negated link is skipped but is not automatically moved to the Graveyard;
    the negating effect (A05/A09) owns that cleanup.
- `ActivateCounterTrapResponse(TrapUid, TargetLinkNumber, Error)` is the
  scaffolding entry point for a Counter Trap response: validates a set Counter
  Trap, adds a Speed 3 link and negates the target link. It does not yet run the
  counter card's own effect; A05 supplies that via `EffectId`.
- Callers must place a Spell/Trap in its zone before adding a card-effect chain
  link; `ResolveChain` resolves the printed effect but does not move a card from
  the hand to the field.

The legacy automatic Trap flow is unchanged and does not create chain links.
`SetChainEffectResolver` is cleared when a new duel starts; install it after
`Start`/`StartScenario`.

## Activation windows and timing

Public queries:

- `GetCurrentTimingWindow()` — `Main1`, `Main2`, `Battle`, or `None` (duel over).
- `GetActivationRule(Card)` / `GetActivationMode(Card)` — per-card override or
  inferred default.
- `IsActivationLegal(Card, Window, Reason)` — pure timing/type check.
- `GetSpellSpeed(Card)` — Speed 1 normal, 2 Quick-Play/Trap, 3 Counter Trap.
- `SetActivationRule(CardId, Rule)` — override mode, source zones, quick effect,
  counter-trap flag, speed and allowed windows.
- `SetEnforceActivationTiming(bool)` — default **false**. When false, the old
  activation paths do not consult the timing layer. When true,
  `CanActivateSpellCard`, `ActivateSpell`, `ActivateSetTrap`,
  `ActivateQuickPlayFromHand`, `ActivateSetSpell` and `ActivateMonsterEffect`
  consult it.
- `SetLegacyAutomaticTraps(bool)` — default **true**. Automatic trap selection
  (`PickAttackTrap`, `TriggerSummonTraps`) still resolves immediately; when the
  timing layer is enforced and this flag is false, those picks are filtered
  through `IsActivationLegal` for the response window and manual-mode cards are
  skipped.

Default timing rules:

- Normal Spell: Main 1 / Main 2 only.
- Quick-Play Spell: Main 1 / Main 2 / Battle, or as a chain response.
- Normal/Continuous Trap: Main phases or response windows.
- Counter Trap: response windows only.
- Monster effect: Main phases; a rule with `bQuickEffect` may also use Battle
  and response windows.
- Damage Step: denied unless the rule explicitly lists `DamageStep` or `Any`.

The existing activation functions still perform their own zone/legality checks
(hand vs Set, empty Spell & Trap Zone, Trap set turn). The timing layer is
additive and does not replace those checks.

Quick-Play support added in this pass:

- `SetSpellTrap` now accepts Quick-Play Spells, and `GetHandActions` offers a
  "Set Quick-Play" action.
- `ActivateQuickPlayFromHand(Uid, Error)` activates a Quick-Play Spell from the
  hand during Main 1, Main 2 or Battle (timing check applies).
- `ActivateSetSpell(Uid, Error)` activates a face-down Quick-Play Spell on the
  player's field.
- `GetSpellTrapActions` returns an activation action for a Set Quick-Play.

Card-specific activation conditions for Set Quick-Play cards are not re-run
yet; use `IsActivationLegal` plus the card's own condition code when A05 wires
the full effect layer.

## Deck validation and banned/limited list

`ValidateDeck(Main, Extra)` returns `FDuelDeckValidationResult`:

- Main Deck 40–60; Extra Deck ≤15 (2006 Fusion Deck cap; `MinMain`, `MaxMain`,
  `MaxExtra` and `MaxCopies` are part of the ruleset, but `LoadBannedListFromJson`
  clamps `max_extra` to 15 even when an older A06 file advertises 20).
- At most 3 copies per card id in each deck and ≤3 across both (or
  `MaxCopies` if the ruleset changes it).
- Extra Deck entries must be Fusion Monsters when the card database is present.
- Unknown/invalid card ids are errors.
- Banned/limited/semi-limited limits come from `FDuelBannedListRuleset`.
  Default ruleset is `default_2006_empty` (no restrictions) until A01 delivers
  the canonical list.
- `SetBannedList`, `LoadBannedListFromJson`, `LoadBannedListFromFile` inject or
  load a ruleset. Suggested future path:
  `Content/Data/Rules/banned_list.json`. A06 already ships a provisional
  `Content/Data/Rules/banned_limited.json`; pass
  `FPaths::ProjectContentDir() / TEXT("Data/Rules/banned_limited.json")` to
  `LoadBannedListFromFile` (or use `LoadDefaultBannedList`).

Supported JSON shapes:

```json
{ "ruleset_id": "gba_2006", "cards": [ { "id": 1, "limit": 0, "reason": "..." } ] }
```

```json
{ "ruleset_id": "gba_2006", "banned": [1], "limited": [2], "semi_limited": [3] }
```

Limit meaning: `0` banned, `1` limited, `2` semi-limited, `3` unlimited.

## Scenario / puzzle / exam setup

`StartScenario(FDuelScenario, Error)` resets the engine and builds both sides
from fixed data:

- LP, hand, deck, graveyard, banished, Extra Deck.
- Field entries via `FDuelScenarioCard` (`Zone`, `ZoneIndex`, `bFaceDown`,
  `bDefense`).
- Deck order: **index 0 is the top card**; the loader inserts in reverse so the
  legacy `Deck.Pop()` draw order matches the authored order.
- `bPlayerGoesFirst`, `bDrawOnFirstTurn` (default false; the fixed hand is not
  disturbed by a draw), `Seed`.
- `TurnLimit` counts **player turns**; `GetScenarioPlayerTurnsTaken()` and
  `GetScenarioTurnsRemaining()` expose it. Exceeding it loses the scenario.
- `TimeLimitSeconds` is host-driven: call `CheckScenarioTimeout(Elapsed)`; the
  engine has no wall-clock dependency.
- Objective counters: battle damage, battle-destroyed monsters, Fusion/Ritual/
  Special Summons, Spells/Traps activated. `CheckWinner` also calls
  `IsScenarioObjectiveComplete`; completing the objective wins the scenario.
- `Surrender()` ends the duel with the opponent as the winner (player-facing
  surrender).

## Ante

- `ConfigureAnte(true)` enables ante for the duel.
- `SelectAnteCard(Side, CardId, Error)` validates the card and, once the duel is
  started, requires it to be in that side's Deck.
- `FinalizeAnteSelection(Error)` requires both sides to have selected.
- On `EndDuel`, `ResolveAnteOnDuelEnd` fills `FDuelAnteState`:
  `bTransferred`, `bPlayerWon`, `WinnerCardId`, `LoserCardId`, `Note`. Draws do
  not transfer.
- `SetAnteResultHook` receives the final state. Inventory removal/insertion is
  **A06's job**; the engine only reports the transfer.

## Result statistics

`GetResultStats()` exposes `FDuelResultStats`: winner/draw, opponent id, mode,
end reason, turns, final LP, battle damage dealt/taken, effect damage dealt,
monsters destroyed/lost by battle, Fusion/Ritual/Special Summon counts,
Spells/Traps activated, cards drawn and discarded. These counters are updated
during play and finalized in `EndDuel`. `SetDuelMode` lets A07 mark story/exam/
ante modes before the result is consumed. A02 can map the stats to DP/titles
(copy `OpponentId`, `Mode`, `bWentSecond`, LP and damage fields into
`FDAProfileDuelResult`); A07 can map them to exam objectives.

## Data-driven effect runtime (A04)

`DAEffectRuntime.h/.cpp` loads `Content/Data/Effects/scripts/*.json` and executes
the A05 schema. The engine owns one runtime (`FDuelEngine::GetEffectRuntime()`);
the legacy name handlers remain the fallback.

### Loading and validation

- `LoadDefaultScripts`, `LoadScriptsFromDirectory`, `LoadScriptJsonText`.
- Triggers, operations, cost ops, selector zones, condition keys and custom
  predicates are validated while loading. Unknown data is rejected instead of
  resolving as a no-op.
- `ResetForNewDuel()` clears once-per-turn/duel counters, typed counters,
  lingering modifiers and continuous registries without reloading scripts.
- `GetLoadedCardCount`, `GetLoadedScriptCount`, `HasScript`, `GetScriptCount`,
  `GetScriptId`, `GetScriptTrigger`.

### Event mapping

The engine calls the runtime at these points; each maps to the matching schema
trigger:

| Engine point | Runtime trigger(s) |
| --- | --- |
| `Start` / `StartScenario` | `OnDuelStart` |
| `StartTurn` | `OnTurnStart`, `OnStandby`, `OnMain` |
| `Draw` | `OnDraw` |
| `OnSummon` | `OnSummon`, then `OnNormalSummon` / `OnSpecialSummon` / `OnFlipSummon` |
| `TriggerFlipEffect` | `OnFlip` |
| `PerformFusion` | `OnFusionSummon` |
| `ActivateRitual` | `OnRitualSummon` |
| Spell/Trap resolution | `OnActivate` |
| `AddChainLink` | `OnChain` |
| `ExecuteAttack` | `OnAttackDeclared` |
| battle calculation | `OnDamageCalculated` |
| monster destruction | `OnDestroy`, `OnBattleDestroy`, `OnSentToGraveyard` |
| discard / mill | `OnSentToGraveyard` |
| return to hand/deck/banished | `OnRemovedFromField` |
| `FinishPlayerTurn` / AI end phase | `OnEnd` |

Continuous/equip/field scripts are recomputed after zone, position, face-up,
counter and controller changes through `RecomputeContinuous()`. Jinzo-style
activation locks, Breaker-style ATK modifiers, Fusion Gate procedures and
Amazoness battle-damage redirection are exposed through the runtime queries.

### Supported operations

Script target selectors resolve deterministically (side, zone order, uid) and
route target/cost/optional choices through `FDuelChoiceRequest`; AI default
answers use `DefaultOptionIds`. Implemented primitives include:

- draw, discard, search, mill, banish, destroy, send-to-grave, summon,
  special-summon, set, change-position, return-to-hand/deck/extra, reveal,
  shuffle, excavate.
- ATK/DEF modifiers (including per-counter), damage/heal, add/remove counters,
  equip, take-control, fusion, ritual, negate, lock-activation, allow-fusion,
  redirect-battle-damage, prevent-battle-damage, battle-damage-zero,
  skip-phase/draw, extra-attack.
- Once-per-turn and once-per-duel guards; optional prompts; atomic cost
  validation before payment.

Known runtime limitations: roll-die/toss-coin are logged visual rolls without a
full replay record; `declare_name`/`look_at_deck`/`attack_directly`/`redirect_attack`
are recorded but not fully interactive; contact fusion and generic mixed fusion
slots are not yet implemented; condition/operation coverage is complete for the
ten example scripts but not every 1,200-card rule.

### Self-test

- `-DAEffectRuntimeSelfTest` loads the ten scripts, runs fixed duel states and
  exits.
- `da.EffectRuntimeSelfTest` runs the same checks from the console.
- Checks: script loading, Sangan search, Morphing Jar discard/draw, Breaker
  counter + continuous ATK + manual cost, Exiled Force self-tribute and
  once-per-turn, MST target prompt/destroy, Bottomless condition and
  destroy→banish, negative ATK condition, Sakuretsu attack trigger, Jinzo lock,
  Fusion Gate registration and Amazoness damage redirection.

## Compatibility flags

| Flag | Default | Effect |
| --- | --- | --- |
| `bEnforceActivationTiming` | false | Old activation paths ignore the timing layer. |
| `bLegacyAutomaticTraps` | true | Keeps automatic Trap resolution exactly as shipped. Set false together with `bEnforceActivationTiming` to filter auto traps through the timing layer. |
| `bEnforceChainSpellSpeeds` | true | New chain API enforces 2006 spell-speed ordering. |
| `bAutoAnswerAiChoices` | true | Opponent choices are answered synchronously. |
| `bAutoAnswerAllChoices` | false | Test/debug: all choices answer immediately. |

No pending choice + timing off + legacy traps on is the old 137-card behaviour.

## Self-test

- `-DADuelRulesSelfTest` — boots the game, waits for the card database, runs all
  checks, logs `PASS:`/`FAIL:` lines and exits.
- `da.DuelRulesSelfTest` — same checks from the console without exiting.
- `-DADuelSelfTest` — legacy 24-duel AI-vs-AI smoke, still handled by the HUD.
- `-DADuelSelfTest=N` — release-gate batch (1–10,000; default 24). The counted
  form is owned by `UDADuelRulesSelfTestSubsystem` because the legacy HUD switch
  only matches a bare token; no UI change is required.
- `da.DuelSelfTest [N]` — same batch from the console (1–10,000; default 24).

Checks cover: choice queue/targeting/disabled options/AI auto-answer, chain link
ordering and speed rejection, Quick-Play/Counter Trap timing, banned/limited/
copy/40–60/main-extra validation, banned-list JSON, ante selection/transfer/hook,
fixed scenario setup/turn limit/timeout, result stats, and a 2-duel smoke run of
the existing AI-vs-AI harness (must report 0 stalls).

## Release gate (Gate 3 / A04)

Command (no editor build required for the code change; run once a build exists):

```text
UnrealEditor-Cmd.exe DuelAcademyIsland/DuelAcademyIsland.uproject -game -nullrhi -nosound -unattended -nop4 -DADuelSelfTest=1000 -log -stdout -FullStdOutLogOutput
```

`Tools/integration/run_smoke.py --duel-selftest --iterations 1000` now emits the
same `-DADuelSelfTest=1000` command.

### Determinism

- Game `i` uses seed `1200 + i * 37` (0-based, same seed for every run).
- Player deck rotates `fire` → `water` → `wind`; the opponent is always the
  `jaden` database deck.
- Shuffles use `FRandomStream`; no wall clock or HUD input participates.
- Each game installs the default `Content/Data/Rules/banned_limited.json` list.

### Per-game invariants

Every step of every duel is checked (and again at the final state):

- No stall: the duel must finish before 120 turns / 240 harness steps.
- No negative Life Points (damage and costs clamp at 0).
- Zone shape: five Monster slots and five Spell & Trap slots per side; no
  invalid entries; monsters in Monster Zones, Spells/Traps in Spell & Trap
  Zones, Field Zone holds a Spell.
- Conservation: every card owned by a duelist still exists in exactly one zone
  (deck/hand/field/graveyard/banished/extra); zone control changes do not lose
  or duplicate cards.
- No duplicate card instance uids across both sides, and no dangling equipment
  or tie targets.
- Card turn stamps (`SummonedTurn`, `SetTurn`, `PositionChangedTurn`,
  `EffectUsedTurn`) are not in the future; counters/attack counters are not
  negative.
- Legal phase transitions: Main 1 → Battle → Main 2, or a new turn starting in
  Main 1; the Over phase is only reachable after a winner exists.
- No unanswered choice and no open chain after a step; any open chain is logged
  and resolved so the rest of the batch can continue.
- Banlist/copy limits are re-validated for both gate decks before each game.
- Result statistics finalize the turn count and final Life Points exactly.

### Deck legality pass

Constructed decks (starter/shop decks in `Data/decks.json`, A06 player decks in
`Data/Decks/player_decks.json`, and every `Data/Opponents/decks/*.json`) are
checked for 40–60 main, 0–15 Extra, at most three copies, the loaded banlist,
known card ids, Fusion-only Extra entries, and at least one legal win condition
(attack-capable monster, Exodia/alternate-win card, or a damage Spell/Trap).

Puzzle files are fixed scenarios, so the 40–60 construction rule does not apply.
Each `Data/Puzzles/P*.json` is checked for known ids, copy/banlist limits, Extra
size, and a legal player win condition, then actually constructed through
`StartScenario` and checked with the same state invariants.

The report is one `[DeckLegality] PASS|FAIL <id> ...` line per constructed deck
and one `[PuzzleLegality] PASS|FAIL <file>` line per puzzle. A06/A07 data is
read-only for this gate: failures are reported, never repaired in place.

Current data status (static audit; rerun the command for the authoritative
result): 6 of 36 constructed decks pass and 30 fail, mostly because many
opponent decks still run banned/limited staples (`Monster Reborn` 385 is the
most common). All 100 puzzle boards pass the scenario audit. These are A06/A07
data findings, not engine regressions.

### Expected output

Legacy/default run:

```text
Duel self-test: 24 iterations, ... 0 stalls, average turns ..., invariant failures 0, gate deck failures 0, deck audit 6/36, puzzle audit 100/100, elapsed ...s, RESULT PASS
```

Release gate:

```text
Duel self-test: 1000 iterations, ... 0 stalls, average turns ..., invariant failures 0, gate deck failures 0, deck audit 6/36, puzzle audit 100/100, elapsed ...s, RESULT PASS
```

`RESULT PASS` means the engine and invariants passed. It does not mean the
A06/A07 deck data is legal; the separate deck-audit count is the data sign-off.
A stall or any invariant failure prints `[DuelSelfTest] ...` details and returns
`RESULT FAIL`.

### Runtime budget

Target: under 10 minutes for 1,000 duels with `-nullrhi` on a desktop CPU; the
legacy 24-duel smoke should stay under 30 seconds. The summary prints elapsed
seconds so the orchestrator can gate on it. The 100-game puzzle probe constructs
one scenario per file and does not simulate puzzle solutions.

### Remaining coverage / risks

- Legacy 137-card effects still use the automatic resolver; the AI-vs-AI batch
  does not build arbitrary chain stacks. Chain/timing coverage comes from
  `-DADuelRulesSelfTest`, and script coverage from `-DAEffectRuntimeSelfTest`.
- A07 now registers `Content/Data/Opponents/decks/*.json` with
  `UCardDatabaseSubsystem::RegisterDeck`, so `FDuelEngine::Start` resolves
  opponent deck ids in addition to `Data/decks.json`. The 31 runtime decks are
  regenerated from A01 canon data by `Tools/opponents/import_canon_decks.py`.
- `banned_limited.json` now advertises `max_extra: 15`, and A06's `DADeckLogic`
  reads that value, so the deck editor and duel engine agree. A06's
  `DAEconomyTests.cpp` still has 20-card extra assertions and
  `Tools/economy/sync_canon.py` still writes 20; those A06-owned files need a
  coordinated update or a later sync run will reintroduce the old value.
- The release gate is compile-safe only in this lane; a UE build is required to
  produce the actual 1,000-duel log. No standalone/Python simulation is treated
  as proof.
- The counted switch still boots the normal GameInstance to obtain
  `UCardDatabaseSubsystem`; the duel simulation itself has no world/HUD
  dependency. A future commandlet could remove that last boot cost.
- A07's 31 runtime opponent decks are now regenerated from canon data and pass
  the constructed-deck audit (`Tools/opponents/import_canon_decks.py --check`).
  The engine still treats deck JSON as read-only; the importer is the only
  writer.

## Integration hooks and gaps

For A05:

- Use `EffectId` on chain links and install `SetChainEffectResolver` after
  `Start`. `ResolveChain` is LIFO and calls the resolver after the card's legacy
  effect when both are requested.
- Use `RequestChoice` for target selection; put the sensible AI answer in
  `DefaultOptionIds`.
- Add per-card `FDuelActivationRule` overrides for Quick Effects, Counter Traps,
  optional triggers and Damage Step exceptions.

For A07:

- Populate `FDuelScenario` from `Puzzles/` and `Exams/`; use fixed deck order
  (index 0 = top), `TurnLimit`, `TimeLimitSeconds` and objective counters.
- Use `SelectAnteCard` / `GetAnteState` for ante duels; transfer inventory via
  the hook.
- AI profiles should answer choices via `DefaultOptionIds`; the base AI does so
  automatically for opponent-side requests.

For A09:

- During a duel, check `HasPendingChoice()` before accepting board input; render
  `GetPendingChoice()` and submit `AnswerChoice`.
- `GetChainLinks()` / `GetLastResolvedChain()` drive chain visuals.
- `GetResultStats()` drives the result screen; ante state drives ante UI.
- For a Set Quick-Play action returned by `GetSpellTrapActions`, call
  `ActivateSetSpell`. For a Quick-Play hand card in Main/Battle, call
  `ActivateQuickPlayFromHand`; `ActivateSpell` still only handles Main Phase
  hand activation.

Known gaps (intentional for this pass):

- The legacy 137-card effects still auto-target; they do not yet generate
  choice requests. Converting them is the next incremental step.
- Chain links created by legacy `ActivateSpell`/`ActivateTrapInternal` are not
  mirrored into `ChainLinks`; only callers using the new chain API get a stack.
- `ActivateCounterTrapResponse` negates a link but does not execute the counter
  card's own effect (A05 owns that script).
- Choice resolution is synchronous: an effect that queues a player choice during
  the AI turn must resume from its callback; the base AI loop does not suspend
  and resume arbitrary card effects yet. Existing 137-card effects never queue
  choices, so this is a new-content risk for A05/A09, not a baseline regression.
- Optional-trigger ordering, replay/record, damage-step sub-windows, side deck
  and full 1,200-card coverage remain.
- `ActivateSetSpell`/`ActivateQuickPlayFromHand` are player-turn APIs in this
  scaffold; activating a Set Quick-Play during the opponent's turn needs the
  response-window UI from A09 plus a non-player-turn activation path.
- Damage Step timing is a single window until a full damage-step state machine
  lands.
