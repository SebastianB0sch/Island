# 01 — Effect runtime semantics (pass 2)

Branch: `refactor/code-review-pass` (stacked on the uncommitted pass-1 tree).

Scope: `DuelAcademyIsland/Source/DuelAcademyIsland/{Private,Public}/DAEffectRuntime*`,
`Tools/effects/**` and this report. No card scripts, decks, manifests,
`DADuelEngine.*`, UI or other workstream files were changed.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| U1 | High | `DAEffectRuntime.cpp` `FireEvent` | Events raised while an effect was executing (`bExecuting`) were dropped. A summon/destroy/leave-field caused by an effect never fired its own trigger. | Fixed: bounded FIFO event queue, drained after the current effect; no recursive script re-entry. |
| U2 | Medium | `DAEffectRuntime.cpp` `OnDestroyed` | `on_sent_to_graveyard` fired for every destroy, including destruction replaced by banish. An explicit destroy-then-banish script also announced a Graveyard move after the card had left it. | Fixed: destination-aware notification; the queued event is skipped if the card is no longer in a Graveyard at dispatch. |
| U3 | Medium | `DAEffectRuntime.cpp` `ExecuteSendToGrave`, `PayCosts` | `send_to_graveyard` operations and costs called `MoveToGrave` with no event hook, so Foolish-Burial-style scripts never triggered Graveyard effects. | Fixed: exactly one `OnSentToGraveyard` after each successful move, with `bFromField` captured before the removal. |
| U4 | Medium | `DAEffectRuntime.cpp` `ApplyContinuousRestriction` | A whole-zone target without `count` (`all_monsters`, `all_cards`, ...) resolved through the default target count of 1, so only one monster was locked. `ApplyContinuousStat` already had the special case. | Fixed: shared `CollectWholeZoneOperationTargets`; both continuous paths use it. |
| U5 | Low | `DAEffectRuntime.cpp` `ExecuteStatModifier` | `per_counter` multiplied the amount by `Targets[0]`'s counters and applied it to every target. | Fixed: each target uses its own counter count; single-target behaviour is unchanged. |
| U6 | Low | `DAEffectRuntime.h/.cpp` | `NegatedActivationUids` and `AttackRestrictionExpiryTurn` were write-only. `bTrapEffectNegated` was also set by `ExecuteNegate` and immediately reset by the post-script `RecomputeContinuous`. | Partially fixed: removed the two write-only members and the dead `ExecuteNegate` assignment. `bTrapEffectNegated` is kept because the public trap-activation query and continuous `lock_activation` use it. |
| U7 | Low | `DAEffectRuntime.cpp` `LoadScriptsFromDirectory` | A failure part-way through the directory left earlier files loaded. | Fixed: snapshot/rollback makes the directory load all-or-nothing. |
| U8 | Low | `Tools/effects/audit.py`, `effect_data.py` | Audit hardcoded Fusion 76 / Ritual 22 totals; `_ids_from` could collect unrelated numbers (amounts, levels, counts) as card ids. | Fixed: totals are derived from `cards.json`; `_ids_from` only accepts ids from card-id fields/lists. |
| U9 | Low | `Tools/effects/effect_data.py`, `audit.py` | Two script files for the same card id were last-one-wins when building the manifest; validation ran after the manifest write. | Fixed: `script_files()` raises on duplicate card ids; audit preflights it before writing the manifest. |

## Changes

### Event queue (U1)

- `FireEvent` now normalises/captures the event, then either enqueues it (when
  another event/effect is on the stack) or dispatches it and drains the queue
  FIFO. Effects still run synchronously; a queued event never re-enters a
  script that is already executing.
- Queue limits: `MaxPendingEffectEvents = 64` and
  `MaxEffectEventsPerCascade = 128`. Overflow and cascade exhaustion log once
  and stop, so a trigger loop cannot stall a duel. The queue is cleared on
  `ResetForNewDuel` and when a duel ends.
- `FireEvent` return contract: 0 for a nested call (the event was only
  queued), otherwise the number of scripts started for the event plus its
  synchronous queued cascade. This keeps callers that test `> 0` / `== 0`
  working.
- Manual/inherent activations are not inside `FireEvent`, so
  `ContinueAfterTargets` drains the queue after restoring `bExecuting`; the
  cost-failure path drains too, so cost-generated events are not left stale.

### Graveyard notifications (U2, U3)

- `OnDestroyed` checks the card's zone after the engine move. Banish/hand/deck/
  Extra destinations do not emit `on_sent_to_graveyard`. For a normal destroy
  the event carries a "must still be in a Graveyard at dispatch" flag, which
  also suppresses the notification in explicit destroy-then-banish scripts such
  as Bottomless Trap Hole while keeping the `on_destroy` trigger. The
  Bottomless self-test now asserts that no Graveyard LP trigger fires for that
  sequence.
- `ExecuteSendToGrave` and the `send_to_graveyard` cost emit
  `OnSentToGraveyard` once, after `RemoveFromZone` + `MoveToGrave` succeed.
  `bFromField` is captured before the removal so the
  `sent_from_field_to_graveyard` predicate remains correct for hand/deck sends.

### Loading and targets (U4, U5, U7)

- `LoadScriptsFromDirectory` snapshots `ScriptsByCard` and restores it on any
  read/parse/validation failure.
- `CollectWholeZoneOperationTargets` is shared by `ApplyContinuousStat` and
  `ApplyContinuousRestriction`; an explicit `count` still wins.
- `ExecuteStatModifier` computes `per_counter` per target. The flat/dynamic
  paths and `set_atk` / `set_def` behaviour are unchanged.

### Dead state (U6)

- Removed `NegatedActivationUids` (only ever added to) and
  `AttackRestrictionExpiryTurn` (only ever assigned).
- Removed the `bTrapEffectNegated = true` write in `ExecuteNegate`; chain
  negation already uses `FDuelChainLink::bNegated`. `bTrapEffectNegated`
  remains the continuous `lock_activation` query used by
  `IsCardActivationLocked`.

### Python tooling (U8, U9)

- `audit.py` derives expected Fusion/Ritual totals from `cards.json`
  (`_expected_recipe_totals`) instead of 76/22, and preflights
  `effect_data.script_files()` before building/writing the manifest.
- `effect_data.script_files()` raises `ValueError` on duplicate card ids;
  `validate_effects.validate()` catches it as a normal validation error.
- `_ids_from` treats bare integers in explicit card lists as ids, but only
  follows card-id keys inside dictionaries. This removes false positives such
  as story reward `amount` values without changing any usage/priority lane for
  the current data.
- `test_effects.py` covers `_ids_from`, duplicate-file rejection and derived
  recipe totals.

## Verification

- `python Tools/effects/test_effects.py` -> 9 tests passed.
- `python Tools/effects/validate_effects.py` ->
  `OK: 253 effect script(s), fusion 75/76 resolved, ritual 22/22 resolved, 0 warning(s)`.
- `python Tools/effects/coverage.py --check` -> `pending=493 scripted=362 vanilla=345` (no writes).
- `python Tools/effects/report_coverage.py --check` -> exit 0 (no writes).
- `python -m py_compile` on all changed Python files -> OK.
- Duplicate-file preflight was exercised with a temporary script directory:
  `audit.main()` exited 1 and the committed manifest mtime was unchanged.
- Before/after `_ids_from` comparison over the usage data: only
  `story_rewards` loses two false-positive ids; every priority assignment is
  unchanged.
- `git diff --check` on all changed files -> clean (only Git's CRLF advisory
  warnings).
- Not compiled and not run in UE, per the pass-2 rules. The new C++ self-tests
  still need the parent session's editor build/headless run.

## Remaining risks / follow-ups

1. **C++ build/run pending.** The queue, destination check and new self-tests
   were only reviewed statically here. The parent should run the editor build
   and `-DAEffectRuntimeSelfTest`; new triggers may legitimately change board
   states in existing scripted scenarios.
2. **Queue caps.** Pathological trigger loops are bounded by 64 pending /
   128 dispatched events per cascade and then dropped with a log. That is a
   safety valve, not full YGO trigger-chain semantics.
3. **Dispatch-time Graveyard check.** A card destroyed then moved out of the
   Graveyard by the *same* effect will not fire `on_sent_to_graveyard`. This is
   intentional for destroy-then-banish implementations; it could suppress a
   trigger in an unusual destroy-then-return script.
4. **`MoveToGrave` still has no engine hook.** The effect runtime now notifies
   for its own send-to-grave operations/costs, but direct engine calls to
   `MoveToGrave` that are neither discard nor mill remain silent. If this is
   centralised later, add the notification inside `FDuelEngine::MoveToGrave`
   and remove the explicit calls in `DiscardCard`, `Mill`, `ExecuteSendToGrave`
   and `PayCosts` to avoid double events.
5. **Optional engine hook for destinations.** `OnDestroyed` infers the
   destination from the zone after the move. A cleaner long-term API is
   `OnDestroyed(Card, bByBattle, Reason, bool bToGraveyard)`, passed by
   `DestroyMonster` (`!bBanishInstead`); that needs a `DADuelEngine` change and
   was deliberately avoided.
6. **`bTrapEffectNegated`** remains meaningful only for continuous
   `lock_activation` registration. One-shot negation relies on
   `FDuelChainLink::bNegated`; this is documented rather than reworked.
7. **`report_coverage.py` historical batch numbers** (155/264/345/591, 22/22 in
   prose) are still snapshots. They were left untouched because regenerating
   `Docs/Effects/COVERAGE.md` is a report-policy change outside this
   workstream's requested fixes.
