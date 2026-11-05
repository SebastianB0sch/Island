# 01 — Duel / effect Graveyard semantics (pass 3)

Branch: `refactor/code-review-pass` (stacked on the uncommitted pass-1/pass-2 tree).

Scope: the owned duel/effect files only —
`DADuelEngine.{h,cpp}`, `DADuelEngineDiagnostics.cpp`, `DADuelistAI.{h,cpp}`,
`DADuelRulesSelfTest.cpp`, `DAEffectRuntime.{h,cpp}`,
`DAEffectRuntimeSelfTest.cpp`, and this report.  No card scripts, manifests,
generated effects, UI, save/story or build files were edited.  Pass-1/pass-2
work was not reverted or reformatted.  No Unreal process was launched.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P3-01-H1 | High | `FDuelEngine::MoveToGrave` / `DiscardCard` / `Mill` / `ExecuteSendToGrave` / `PayCosts` | Direct engine Graveyard moves (tributes, fusion material, cleanup, returned cards, and the many legacy handlers) were silent, while discard, mill, effect sends and costs each notified separately. A centralisation had to avoid double events. | Fixed: `MoveToGrave` is now the authoritative notifying path; `MoveToGraveRaw` is the placement-only primitive used by destruction; all former explicit `OnSentToGraveyard` calls were removed. |
| P3-01-M1 | Medium | `FDAEffectRuntime::OnDestroyed` | The Graveyard destination was inferred from the card's zone *after* the move. `on_destroy` and the Graveyard event therefore shared one implicit decision and were fragile for destroy-then-rezone effects. | Fixed: additive `bToGraveyard = true` parameter supplied by `DestroyMonster` (`!bBanishInstead`) and `DestroySpellTrap` (`true`). `on_destroy`/`on_battle_destroy` always fire; the Graveyard event only fires when the engine says the card went there. |
| P3-01-M2 | Medium | `FDuelEngine::InflictDamage` / `InflictBattleDamage` / `IsScenarioObjectiveComplete` | Damage statistics and `RequiredBattleDamage` used the requested amount, so 100 LP left could satisfy a 2000-damage objective through overkill. | Fixed: statistics use the actual LP loss (`min(LP, Amount)`); the visual/log still show the requested amount. Regression tests cover both effect and battle overkill and a 200-damage objective. |
| P3-01-M3 | Medium | `ResolveSpell` `Card Destruction` | The both-decks-short branch called `EndDuelAsDraw` before moving either hand to the Graveyard, leaving the final hands unresolved and no Graveyard triggers. | Fixed: both hands are discarded first, then the draw result is applied if the duel is still running. Test asserts final hands/decks are empty and both Graveyards contain the discarded cards. |
| P3-01-L1 | Low | `DADuelEngine.h` | `PickSummonTrap` was declared but had no definition or caller. | Removed. |
| P3-01-L2 | Low | `FDuelEngine::Draw` | If an `OnDraw` trigger ended the duel, the rest of a multi-card draw still executed. | Fixed: bail out of the batch after `OnDraw` when the result is final. |
| P3-01-L3 | Low | `FDuelEngine::ResolveBattle` | Lethal battle damage still allowed FLIP effects and destruction follow-ups (Flame Wingman/Inferno/Yomi Ship) to run after the result was decided. | Fixed: winner guards after damage, after destruction follow-up damage, and before the second monster's destruction. |
| P3-01-L4 | Low | `DestroyMonster` / `DestroySpellTrap` / `CleanupEquips` | A destruction callback during equip cleanup or an attached-monster destruction could end the duel while the outer destruction kept moving cards and firing triggers. | Fixed: entry winner guards plus silent destination placement when a callback already ended the duel; equip cleanup stops at `bWinnerSet`. |
| P3-01-L5 | Low | `DADuelEngine::GetWinner` | `GetWinner()` cannot express "no winner"; on a draw it keeps the legacy opponent value. | Fixed additively: `TryGetWinner(EDuelOwner&)` returns false for unfinished/drawn duels. Used in the new tests and the diagnostics batch. `GetWinner()` remains for compatibility and is documented. |
| P3-01-L6 | Low | `DADuelistAI` | `ScoreCardId` was a dead private method and `Random` was write-only; the policy is deterministic but that was not covered. | Removed both dead members; `Configure(Profile, Seed)` keeps its signature with an explicit `(void)InSeed`. Added a repeated-decision determinism check. |
| P3-01-L7 | Low | `ActivateSpell` / `ActivateQuickPlayFromHand` / `ActivateSetSpell` / `ActivateSetTrap` | `OnActivate` was fired even when the preceding resolution had already ended the duel, allowing post-result activation scripts. | Fixed: `OnActivate` is gated by `!bWinnerSet`. |

## Changes

### Central Graveyard path (H1)

- `FDuelEngine::MoveToGrave(Card, Reason = ..., bFromField = false)` now:
  1. normalises and places the card through `MoveToGraveRaw`,
  2. recomputes continuous effects,
  3. calls `FDAEffectRuntime::OnSentToGraveyard` exactly once.
- `MoveToGraveRaw` is placement-only (no event) and is used by the two
  destruction paths, whose `OnDestroyed` call owns `on_destroy`,
  `on_battle_destroy` and the Graveyard event.
- Removed the explicit `OnSentToGraveyard` calls from `DiscardCard`, `Mill`,
  `PayCosts` (tribute + send cost) and `ExecuteSendToGrave`.  `OnSentToGraveyard`
  now also clears the card's runtime state, matching the old effect-send path.
- Every engine call site now supplies a reason and the correct `bFromField`
  value where known: tribute/cost/fusion material from the field are true;
  discard/mill/activation-failure/deck sends are false; effect sends capture
  the zone before removal.  This preserves `sent_from_field_to_graveyard`
  behaviour for Sangan-style scripts while keeping discard/mill distinct.
- Legacy direct moves are no longer silent, so a card tributed or cleaned up
  by an old handler now fires its Graveyard script once.

### Destruction destination (M1)

- `OnDestroyed(Card, bByBattle, Reason, bToGraveyard = true)` is additive.  The
  engine passes the explicit destination it already computed.  The queued
  dispatch check still suppresses the Graveyard event when a script moves the
  card out of the Graveyard later in the same chain.
- `DestroyMonster` and `DestroySpellTrap` use `MoveToGraveRaw` before the
  callback, so there is no second Graveyard event.

### Damage accounting (M2)

- `InflictDamage` returns the actual LP loss and adds that to
  `EffectDamageDealt`.  `InflictBattleDamage` records the same actual loss in
  `BattleDamageDealt`/`BattleDamageTaken` before calling `InflictDamage` so
  the values are present when `EndDuel` finalizes the result.
- `RequiredBattleDamage` therefore measures real damage.  The two existing
  puzzle/exam flow checks continue to use the same counters.

### Card Destruction completion (M3)

- `Card Destruction` now shares one `DiscardHandToGrave` lambda.  In the
  both-short branch it discards both hands, then calls `EndDuelAsDraw` if no
  Graveyard trigger already ended the duel.  Normal branches still discard
  and draw per side, with winner guards after both operations.

### Compatibility and cleanup (L1–L7)

- Removed `PickSummonTrap` (declaration only).
- `TryGetWinner` added; `GetWinner` documentation now says it is only
  meaningful when `!IsDraw()`.
- Draw, battle-damage and destruction callbacks now stop at `bWinnerSet`; the
  final board is still left in a legal zone.
- One-shot activation scripts are not fired after another callback finalized
  the duel.
- AI: removed `ScoreCardId`/`Random`; the existing first-past-the-post tie
  break in snapshot order is the deterministic contract.

## Verification

Commands actually run (no Unreal process was started):

```
python Tools/effects/test_effects.py
  -> Ran 9 tests ... OK
python Tools/effects/validate_effects.py
  -> OK: 253 effect script(s), fusion 75/76 resolved, ritual 22/22 resolved, 0 warning(s)
python Tools/puzzles/validate.py
  -> PASS summary: 145 checks, 0 failures, 1 warnings (pre-existing duplicate-name warning)
python Tools/effects/coverage.py --check
  -> pending=493 scripted=362 vanilla=345
python Tools/effects/report_coverage.py --check
  -> exit 0, coverage report matches the committed manifest
git diff --check -- <all changed C++ files>
  -> no whitespace errors (only Git's LF/CRLF advisory)
```

Additional static checks:

- Delimiter/brace scan with strings and comments stripped: balanced `{}`, `()`
  and `[]` in every changed C++ file.
- Source scan confirms every `MoveToGrave(...)` call in the engine and effect
  runtime supplies a reason and from-field flag; only `MoveToGraveRaw` is
  placement-only.
- Python effect schemas/data were not changed; the Python suite is unchanged
  and green.
- `Tools/puzzles/validate.py` refreshes `Content/Data/Canon/manifest.json` as a
  side effect of the canon checks.  That generated file was restored to HEAD
  immediately; it is not part of this workstream's diff.

## API / serialization impact

- Additive public API: `FDuelEngine::TryGetWinner(EDuelOwner&)`,
  `FDAEffectRuntime::OnDestroyed(..., bool bToGraveyard = true)`.
- Private-only signature changes: `FDuelEngine::MoveToGrave` gained reason and
  from-field parameters; `MoveToGraveRaw` was added; `InflictDamage` now
  returns the actual loss.  All are private/friend-only.
- Removed private dead API: `FDuelEngine::PickSummonTrap`,
  `FDAIDuelistAI::ScoreCardId`, `FDAIDuelistAI::Random`.
- No saved/serialized structure changed.  `FDuelResultStats` and
  `FDuelScenario` fields keep their names and types; only the *values* of
  damage counters become actual LP loss.
- `GetWinner()`/`GetWinnerName()` behaviour on a draw is unchanged for
  compatibility; new code should use `IsDraw()` or `TryGetWinner()`.

## Remaining risks / cross-workstream follow-ups

1. **Build/headless run pending.** All C++ was reviewed statically only.  The
   parent must run the editor build and at least
   `-DADuelRulesSelfTest`, `-DAEffectRuntimeSelfTest`, `-DADuelSelfTest=24`
   and `-DAPuzzleExamSelfTest`.  Centralising the Graveyard hook intentionally
   makes legacy direct moves fire scripts; AI-vs-AI win splits can move even
   though determinism is preserved.
2. **From-field classification is call-site data.** New engine moves must pass
   the correct reason/from-field flag; the default is `false`.  The annotated
   paths cover every current call in `DADuelEngine.cpp` and
   `DAEffectRuntime.cpp`, but future call sites need review.
3. **Destroy-then-rezone edge case remains intentional.** A destruction moved
   out of the Graveyard by the same effect suppresses `on_sent_to_graveyard`
   at dispatch time (documented pass-2 behaviour).  `on_destroy` still fires.
4. **Card Destruction precedence.** If a hand card's own Graveyard trigger ends
   the duel while the both-short branch is resolving the discards, that real
   trigger result wins over the deck-out draw.  With inert cards the branch is
   a draw and the final zones are complete.
5. **Damage counter drift.** Profile/exam aggregates that previously benefited
   from overkill will now see actual damage.  This is the requested contract,
   but historical balance/report snapshots may shift.
6. **Out-of-scope consumer migration.** `DAPuzzleRuntime.cpp` and
   `DAPuzzleSelfTest.cpp` still call `GetWinner()`; they only compare against
   `Player`, so a draw remains a loss and is safe.  They should migrate to
   `TryGetWinner()`/`IsDraw()` in a later pass.  `DADuelUI.cpp` already reads
   `ResultStats.bDraw`.
7. **Post-result board writes.** Late moves still place cards in a legal zone
   and recompute continuous state, but `TryStartScript` blocks new scripts once
   `bWinnerSet` is true.  This keeps invariants without replaying triggers.
