# 02 — Effect runtime

Branch: `refactor/code-review-pass`

Scope: `DAEffectRuntime.cpp/.h`, `DAEffectRuntimeSelfTest.cpp/.h`,
`Tools/effects/**/*.py` and this report. No card scripts, decks, manifest
content or out-of-scope C++ were changed. `effect_patterns.py`'s generated
recipe table was not rewritten.

## Summary

The runtime is data-driven and the shipped 253 scripts load and validate
cleanly. The main risks found were around script reload, prompt failure,
removals from the field leaving Equip/Union attachments and stale per-card
state, and the loader accepting malformed JSON shapes that it then silently
ignored. Those are fixed with small, same-file changes.

The dispatcher covers every operation accepted by the loader; none falls
through to the final unsupported-operation error (three diagnostic ops,
`declare_name` / `look_at_deck` / `redirect_attack`, intentionally log and
return without a state change). The remaining high-impact issue is
architectural: `FireEvent` suppresses nested events for the whole duration of
an effect (`bExecuting`), so summon/destruction triggers caused by an effect's
own operations never fire. That needs an event queue and is listed as a
follow-up rather than patched in this pass.

Deduplication was limited to helpers that were byte-for-byte equivalent:
target-object resolution, operation target fallback, zone counting,
destruction-replacement registration and the equip/field stat-script scan.
`ExecuteOperation`, `ApplyContinuousStat`, `ApplyContinuousRestriction` and
`ExecuteAttackLock` were **not** mechanically reshaped; their branches differ
in target and side semantics, so forcing a shared helper would change
behaviour.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| F1 | Medium | `DAEffectRuntime.cpp:723` (`LoadScriptJsonText`) | Loading the same card file (or any script id) twice appended a second copy to `ScriptsByCard`, so every matching trigger fired twice. | Fixed: reject duplicate ids per card before appending. |
| F2 | Medium | `DAEffectRuntime.cpp:2144` (`TryStartScript`) | `RequestOptionalTrigger` can return 0 (duel ended / no options), but the result was ignored and the script was still counted as started. | Fixed: treat request failure as not started and undo the prompt count. |
| F3 | Medium | `DAEffectRuntime.cpp:3084` (`ExecuteSet`) | `RemoveFromZone` succeeded, then a failed `PlaceMonster` / `PlaceSpellTrap` dropped the card from the game. | Fixed: failed placement sends the card to the Graveyard, matching `ExecuteSummon`. |
| F4 | Medium | `DAEffectRuntime.cpp:2616-2667` (`PayCosts`), `2980`, `3015`, `3260` (`ExecuteBanish` / `SendToGrave` / `Return`) | Removing a card from the field via an operation or cost did not call `CleanupEquips`, and Graveyard moves did not clear per-card runtime state. Attached Equips/Unions could survive their host; counters/modifiers stayed keyed to the removed uid. `return_to_extra` also bypassed the engine move path, so no leave-field trigger ran. | Fixed: cleanup/state clear on field removals; Extra Deck returns route through `MoveToDeckBottom`. |
| F5 | Medium | `DAEffectRuntime.cpp:569,600,692,410` (`LoadScriptJsonText`, `ValidateOperationJsonArray`) | Malformed `condition` / `target` / `cost` fields were silently treated as absent; unknown `$target` references and non-array random branches were accepted; invalid `once_per_turn` values were ignored. | Fixed: reject non-object/non-array shapes, unknown target refs and invalid once-per-turn values. |
| F6 | Medium | `DAEffectRuntime.cpp:3733` (`ExecuteAttackLock`) | A turn-scoped `attack_lock` on specific UIDs wrote the permanent `CannotAttackUids` set (only cleared when the card leaves the field) and also blocked the whole side. Chaos Sorcerer's "cannot attack this turn" became permanent. | Fixed: new `CannotAttackUidsThisTurn`, reset at turn start; side-wide locks still use the side set. |
| F7 | Low | `Tools/effects/validate_effects.py:326,359,500,580,686,810` | The validator raised `TypeError` on unhashable/mistyped script ids, manifest ids, fusion results or ritual monsters; target `count` min/max compared unchecked types; `count_filter` was never recursively checked although the runtime validates it. | Fixed: type guards and recursive `count_filter` validation. |
| F8 | Low | `DAEffectRuntime.cpp:2800,2841,3540,3784,4845` | Target-object parsing was duplicated in cost and operation resolution; zone counting was duplicated in conditions and dynamic amounts; equip/field stat scans were identical apart from the trigger. | Fixed: extracted five helpers with identical behaviour. |
| U1 | High | `DAEffectRuntime.cpp:1362` (`FireEvent`) | Any event raised while `bExecuting` is true is dropped. Summons, destruction, damage and leave-field events caused by an effect's operations therefore do not fire their own trigger scripts. This is the largest remaining semantic gap. | Not fixed — requires a queued event bus; out of scope for a minimal patch. |
| U2 | Medium | `DAEffectRuntime.cpp:1304` (`OnDestroyed`) | `on_sent_to_graveyard` is fired unconditionally for every destroy, including destruction replaced by banish. `Bottomless Trap Hole`'s destroy-then-banish sequence also emits a Graveyard event before the banish operation. | Not fixed — needs a destination-aware destruction notification. |
| U3 | Medium | `DAEffectRuntime.cpp:3006`, `2623` | `send_to_grave` / send-to-graveyard cost call `MoveToGrave`, which has no event hook, so `on_sent_to_graveyard` does not fire (unlike discard/mill, which call `OnSentToGraveyard` explicitly). Scripts such as Foolish Burial will not trigger Graveyard effects. | Not fixed — needs an explicit event after the move; report to engine owner. |
| U4 | Medium | `DAEffectRuntime.cpp:4130` (`ApplyContinuousRestriction`) | A continuous target object without `count` goes through `ResolveOperationTargets`, whose default count is 1, so `{"zone":"all_monsters"}` locks only one monster. `ApplyContinuousStat` has a whole-zone special case for the same shape. | Not fixed — no shipped script uses the shape; unify when the target helper is next touched. |
| U5 | Low | `DAEffectRuntime.cpp:3136` (`ExecuteStatModifier`) | `per_counter` computes the amount from `Targets[0]` and applies it to every target. Single-target scripts (Breaker) are correct; multi-target scripts would be wrong. | Not fixed — latent. |
| U6 | Low | `DAEffectRuntime.cpp:3475-3494`, `3668`, `4385` | `NegatedActivationUids` and `AttackRestrictionExpiryTurn` are write-only; `bTrapEffectNegated` is set by `ExecuteNegate` then cleared by the `RecomputeContinuous` at the end of the same script, so that flag is effectively transient. Chain negation itself relies on `FDuelChainLink::bNegated` and is correct. | Not fixed — dead state; remove or wire up deliberately. |
| U7 | Low | `DAEffectRuntime.cpp:479` (`LoadScriptsFromDirectory`) | A failure part-way through the directory leaves earlier scripts loaded while returning false. The engine constructor discards the runtime, but a public reload sees mixed state. | Not fixed — needs an all-or-nothing load transaction. |
| U8 | Low | `Tools/effects/audit.py:117,119`; `report_coverage.py:209-213`; `effect_data.py:213-226,308-312` | Audit hardcodes 76 Fusion / 22 Ritual totals; the coverage report hardcodes historical batch counts and runtime caveats; `_ids_from` can treat numeric non-card values inside arbitrary dicts as card ids. Current data does not trigger these, but they will drift silently. | Reported, not changed (content/report policy). |
| U9 | Low | `Tools/effects/effect_data.py:593` (`script_files`) | Two files with the same `card_id` last-one-wins for the manifest. `validate_effects.py` catches the duplicate, but the manifest is built before validation in `audit.py`. | Reported, not changed. |

## Changes

### Loading and validation

- `LoadScriptJsonText`: rejects duplicate script ids per card. This also makes
  a second `LoadDefaultScripts` / hot reload idempotent instead of doubling
  every trigger.
- `LoadScriptJsonText`: `condition`, `target`, `cost` and `once_per_turn` now
  reject the wrong JSON shape instead of being ignored.
- `ValidateConditionJson`: `all` / `any` entries must be objects.
- `ValidateOperationJsonArray`: string target references must be a known
  `$self/$target/$cost/$trigger/$attacker/$attack_target/$equipped`; random
  branch fields must be arrays if present.
- Cost targets use the same reference check.

### Execution

- `TryStartScript`: a failed optional-trigger request returns false.
- `ExecuteSet`: failed placement sends the card to the Graveyard instead of
  deleting it.
- `ExecuteAttackLock`: turn-scoped per-card locks use a new
  `CannotAttackUidsThisTurn` set instead of the permanent uid set or the whole
  side; the set resets at turn start and when the card leaves the field.
- `PayCosts` (tribute, send-to-graveyard, banish, return-to-hand/deck) and
  `ExecuteBanish`, `ExecuteSendToGrave`, `ExecuteReturn`, `ExecuteRitual`:
  call `CleanupEquips` / `ClearCardState` where the engine move path does not
  do it.
- `ExecuteReturn` `return_to_extra`: routed through `MoveToDeckBottom` so the
  card reaches the owner's Extra Deck with normal bookkeeping and leave-field
  trigger ordering.

### Deduplication

- `ResolveTargetObjectUids`: shared object-target/count/filter resolution for
  operations and costs.
- `ResolveOperationTargetsOrDefault`: shared "resolve, else source" fallback
  used by eight operations.
- `CountMatchingZoneCards`: shared by condition counts and dynamic amounts.
- `RegisterDestructionReplacement`: shared by the immediate operation and
  `RecomputeContinuous`.
- `HasContinuousStatScript`: shared by `HasEquipStatScript` and
  `HasFieldStatScript`.

No public API was changed. `DAEffectRuntimeSelfTest` and its header were
reviewed but needed no change.

### Python tooling

- `validate_effects.py` now type-guards script ids, manifest ids, fusion
  results, ritual monster ids and target count bounds; it also recurses into
  `count_filter` like the C++ loader does. Valid data output is unchanged.
- `coverage.py`, `report_coverage.py`, `build_manifest.py`,
  `effect_data.py` and `effect_patterns.py` were reviewed. No behavioural
  change was needed for the current data; the drift risks are listed in U8/U9.
- `test_effects.py` now builds the manifest with `write=False`, so running the
  regression suite no longer rewrites the committed
  `card_effect_manifest.json` as a side effect. CI runs the suite.

## Verification

**Integration:** the combined editor build passed, and
`-DAEffectRuntimeSelfTest` passed 147/147 plus the full duel/puzzle/exam suites.
See [00-overview.md](00-overview.md).

- `python Tools/effects/validate_effects.py`
  -> `OK: 253 effect script(s), fusion 75/76 resolved, ritual 22/22 resolved, 0 warning(s)`
- `python Tools/effects/audit.py`
  -> `AUDIT PASSED`; Tier 0 100%, Tier 1 100%, Tier 2 53.2% (informational),
  Tier 3 100%, Fusion 98.7% resolved, Ritual 100%, overall 707/1200 (58.9%).
  Audit rewrote `card_effect_manifest.json`; that generated diff was reverted
  with `git checkout --` per the review rules. `Docs/Effects/COVERAGE.md` was
  rewritten identically (no diff).
- `python Tools/effects/test_effects.py`
  -> 6 tests passed.
- `python Tools/effects/coverage.py --check`
  -> pending=493, scripted=362, vanilla=345 (no writes).
- `python Tools/effects/report_coverage.py --check`
  -> exit 0 (no writes).
- `git diff --check` on the scoped C++/Python files
  -> clean; only Git's LF/CRLF advisory warnings.
- Not built or run in UE per the review instructions. No UnrealBuildTool or
  editor invocation was performed.

## Follow-ups

1. Queue nested effect events instead of dropping them in `FireEvent` (U1).
   This is the main behaviour gap for effect-driven summons/destruction.
2. Make destruction notifications destination-aware and fire
   `on_sent_to_graveyard` only for actual Graveyard moves (U2, U3).
3. Unify whole-zone target handling between `ApplyContinuousStat` and
   `ApplyContinuousRestriction` (U4), and make `per_counter` per-target (U5).
4. Remove or use the write-only chain/attack-expiry state (U6).
5. Make `LoadScriptsFromDirectory` transactional (U7).
6. Make audit totals derive from `cards.json` instead of hardcoded 76/22, and
   make the coverage report compute its historical/batch numbers or mark them
   as snapshots (U8). Make `_ids_from` only collect ids under card-id keys.
7. Add a validator check for duplicate script files before manifest build, or
   make `script_files` fail loudly (U9).
