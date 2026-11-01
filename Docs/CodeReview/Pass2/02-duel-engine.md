# 02 — Duel engine, rules and AI (pass 2)

Branch: `refactor/code-review-pass` (stacked on the uncommitted pass-1 tree).
Baseline: [01-duel-engine.md](../01-duel-engine.md). This pass did not revert or
reformat the first-pass changes.

Scope: `DuelAcademyIsland/Source/DuelAcademyIsland/{Private,Public}/DADuelEngine*`
(including `DADuelEngineDiagnostics.cpp`), `DADuelistAI.*`, `DADuelRules.h`,
`DADuelRulesSelfTest.*` and this report.
No UI, effect-runtime, story/save or data files were edited.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| D1 | High | `DADuelEngine.cpp` `CheckWinner` / `EndDuel` / `FinalizeResultStats` | A simultaneous double KO called `EndDuel(Opponent, ...)` while result statistics set `bDraw = true` from the LP values. `Winner`, the log, the HUD's `GetWinner()` and the stats disagreed. | Fixed: first-class `bDraw` outcome, `EndDuelAsDraw`, `IsDraw()`; all end paths now agree. |
| D2 | Medium | `ResolveSpell` `Card Destruction` | The two "draw the discarded count" steps ran sequentially. With both decks empty the first processed player lost before the opponent's draw was considered, so a simultaneous deck-out became an opponent win. | Fixed: both deck sizes are checked before either draw; both short is a draw, one short is still a loss. |
| D3 | Medium | `EndDuel` | The duel could finish with an open chain (`HasWinner()` true while `IsChainOpen()` true), and pending-choice bookkeeping was only partially cleared. | Fixed: shared `FinishDuelBookkeeping` clears choices, deferred cleanup, the chain stack, discard and AI-pending flags. |
| D4 | Medium | `ResolveChain` negated branch | A negated face-up one-shot Spell/Trap was logged and skipped, but never left the field. It could remain face-up for the rest of the duel (and the post-duel board). | Fixed: `CleanupResolvedChainCard` also runs for negated card links. |
| D5 | Medium | `CleanupResolvedChainCard` | Early returns (card already gone, or persistent) skipped `FlushPendingActivationCleanup`, stranding cards deferred behind an earlier choice. | Fixed: every return path flushes. |
| D6 | Medium | `RequestChoice` auto-answer path | AI answers bypass `AnswerChoice`, so the post-choice cleanup that a manual answer triggers never ran. | Fixed: flush after the auto-answer resolver. |
| D7 | Medium | `DestroyMonster` | After `EffectRuntime->OnDestroyed` ended the duel, the remaining battle floaters, Backfire/Silpheed/Kaiser Glider/Poison Draw Frog triggers and `CheckWinner` could still mutate the board. | Fixed: `bWinnerSet` guards after each callback group; the card is already in its destination pile when it returns. |
| D8 | Medium | `DestroyAllMonsters`, `DestroyAllSpellTraps`, Mirror Force, Cyber Jar, Special Hurricane | Uid-snapshot loops continued destroying cards after a destruction trigger ended the duel. | Fixed: loops stop at `bWinnerSet`. |
| D9 | Medium | `StartTurn`, `Draw`, `FinishPlayerTurn`, `DiscardFromHand`, `RunOpponentTurn`, direct-attack branch | Several effect-runtime callbacks and post-attack steps continued after a callback had ended the duel. | Fixed: explicit post-callback guards; `Draw` itself refuses to mutate a finished duel. |
| D10 | Low | `ActivateSpell`, `ActivateQuickPlayFromHand`, `ActivateSetSpell`, `ActivateTrapInternal`, `AiActivateSpellCard` | The resolved one-shot card was left on the final board when its own effect ended the duel, because the cleanup ran after an early `bWinnerSet` return. | Fixed: one-shot cleanup runs even when the duel ended; persistent/Field cards are still skipped. |
| D11 | Low | `ActivateCounterTrapResponse` | The trap pointer taken before `AddChainLink` was used afterwards; `EffectRuntime->OnChain` can mutate the board during `AddChainLink`. | Fixed: re-fetch by uid after the chain callback. |
| D12 | Low | `GetAttackTargets`, `AiPlayBattlePhase` | Both omitted `EffectRuntime->CanAttackDirectly` even though `ExecuteAttack` accepts effect-granted direct attacks. The UI could not offer a legal direct attack and the AI ignored it. | Fixed: the same direct-attack predicate is used in all three places. The UI now receives monster targets plus a direct option instead of direct-only. |
| D13 | Low | `DADuelistAI::ShouldAttack` | The policy accepted a direct attack without checking `bCanAttackDirectly`, never checked that the attacker/target ids belong to the snapshot, and computed an unused `attack_into_set_atk` threshold. | Fixed: battle phase, opponent LP, attacker membership, target membership and direct legality are checked; dead locals removed. |
| D14 | Low | `DADuelSelfTestArgs` / `RunSelfTest` / `UDADuelRulesSelfTestSubsystem` | `-DADuelSelfTest=N` was parsed and clamped twice (diagnostics and the rules subsystem). | Fixed: one owner, `DADuelSelfTestArgs::ParseRequestedIterations`. |
| D15 | Low | `AiAttackWith` | The helper hard-coded `EDuelOwner::Opponent`; it is currently unused, so any future caller of a player-side attacker would attack on the wrong side. | Fixed: uses `Attacker.Controller`. |
| D16 | Low | Scenario start | A scenario authored with a duelist at 0 LP started with an active board; nothing called `CheckWinner` until the next damage event. | Fixed: `StartScenario` runs `CheckWinner` after the first turn starts. Existing puzzle validation already rejects 0 LP. |
| D17 | Low | `GetSpellSpeed` | Scripted `FDuelActivationRule.bCounterTrap` / `bQuickEffect` overrides were honoured by `IsActivationLegal` but not by the spell-speed query, so a scripted Counter Trap could report Speed 2 and fail to respond to a Speed 3 link. | Fixed: the query uses the same rule flags as the legality check; regression checks added. |

### Reported, not fixed

| Severity | Location | Finding |
|---|---|---|
| Low | `ResolveSpell` / `InflictDamage` | Battle/effect damage statistics count the requested amount, not the LP actually removed when LP clamps at 0. `FDuelScenario::RequiredBattleDamage` can therefore be met by overkill. Changing this could change authored puzzle pass/fail, so it is left for a data-aware pass. |
| Low | `CheckWinner` | Scenario objective completion is checked before LP, so completing an objective and reaching 0 LP on the same action is a win. This is the intended puzzle rule; documented rather than changed. |
| Low | `GetWinner` | `EDuelOwner` has no "none" value. On a draw the engine keeps the conservative `Opponent` value for pre-existing consumers; `IsDraw()` and `ResultStats.bDraw` are authoritative. |
| Low | `ResolveChain` | When a link ends the duel, unresolved links are dropped without entries in `LastResolvedChain`; the duel is over, so they must not resolve. |
| Low | `AiPlayBattlePhase` | When a direct attack is legal (empty board, Bugroth + Umi, or an effect), the AI takes it without scoring monster targets. This is the pre-existing policy and is left intact to avoid changing the AI-vs-AI balance; effect-granted direct attacks now follow the same rule as Bugroth/Umi. |
| Low | `PickSummonTrap` | Declared in the header but has no definition or caller. Left untouched to keep this diff focused. |
| Low | `DADuelistAI` | The class is still not wired into `FDuelEngine` (documented A04 hook); engine AI remains `AiPlay*`. `GetThreshold` is now unused internally but remains public API. |

## Changes

### Result semantics (D1, D2, D16)

- `FDuelEngine` now has a private `bDraw` and public `IsDraw()`. `IsOver()` /
  `HasWinner()` still mean "the duel finished"; `GetWinner()` is documented as
  meaningful only when `!IsDraw()`.
- `EndDuel` clears `bDraw`; `EndDuelAsDraw` sets it together with Phase `Over`,
  result statistics, the ante outcome and end-of-duel cleanup.
- `FinalizeResultStats` derives `bDraw` from the authoritative flag instead of
  re-testing LP, and derives `bPlayerWon` from `!bDraw && Winner == Player`.
- `CheckWinner` routes a double KO to `EndDuelAsDraw`; the draw log no longer
  claims a winner. The draw still emits a `Win` visual event with text `DRAW`
  because the current HUD uses that event to open its result cut-in and reads
  `ResultStats.bDraw` to render "DUEL DRAW". `GetWinnerName()` is empty on a draw.
- `Card Destruction` checks both required draw counts first. Both short ->
  draw; one short -> the existing single-sided loss path. Other multi-card draw
  effects are single-player and unchanged.
- `StartScenario` runs `CheckWinner` after the first turn starts so a 0-LP
  scenario does not stay active.

**UI interface (not edited here):** consume `FDuelEngine::IsDraw()` (or
`GetResultStats().bDraw`) for the result screen and story/profile hooks.
`GetWinner()` on a draw currently returns `Opponent` for compatibility; do not
interpret it as a winner. `DADuelUI.cpp` in the working tree already reads
`ResultStats.bDraw` at the result transition; this pass only adds the direct
engine query. The draw `Win` visual event uses `Side = Player` so the existing
banner/cut-in path runs; if the HUD adds draw audio, it should choose a neutral
cue from `IsDraw()` rather than the per-side win/loss cue.

### End-of-duel lifecycle (D3, D7–D10)

- `FinishDuelBookkeeping` is shared by both end paths: clears pending choices
  (which flushes deferred activation cleanup), clears the chain stack, and
  resets the discard/AI-pending flags.
- `DestroyMonster` returns immediately after a destruction callback ends the
  duel. Batch destroy helpers and the special destructive loops stop on
  `bWinnerSet`.
- `StartTurn` checks after `OnTurnStart`, `OnStandby` and `OnMain`; `Draw`
  refuses to act after the result is final; `FinishPlayerTurn`,
  `DiscardFromHand` and the opponent end phase check after every effect hook.
- The direct-attack and resolved-battle paths no longer run `AfterAttack` on a
  finished duel.
- One-shot Spell/Trap cleanup runs after a duel-ending resolution. The helper
  already skips persistent and Field cards.

### Chain / choices (D4-D6, D11, D17)

- `ResolveChain` cleans up negated one-shot card links.
- `CleanupResolvedChainCard` flushes deferred cleanup on all early returns.
- `RequestChoice` flushes after an auto-answered resolver, matching
  `AnswerChoice`.
- `ActivateCounterTrapResponse` re-fetches the trap after `AddChainLink`.
- `GetSpellSpeed` now derives Counter Trap / Quick-Play speed from the same
  activation-rule flags that `IsActivationLegal` uses, instead of only the
  printed subtype.

### AI (D12, D13, D15)

- `GetAttackTargets`, `AiPlayBattlePhase` and `ExecuteAttack` now use the same
  direct-attack predicate (empty board, Bugroth + Umi, or
  `EffectRuntime::CanAttackDirectly`).
- `GetAttackTargets` exposes both the direct option and monster targets when a
  direct attack is legal but monsters are present.
- `DADuelistAI::ShouldAttack` validates battle phase, opponent LP, attacker and
  target membership, and direct-attack legality. Behaviour for a normal legal
  attack is unchanged (same weight thresholds).
- `AiAttackWith` uses the attacker's controller instead of a hard-coded side.

### Self-test argument ownership (D14)

- `DADuelSelfTestArgs::ParseRequestedIterations(Default, Max, OutRequested)` in
  `DADuelRulesSelfTest.h/.cpp` owns the `-DADuelSelfTest=N` parse and clamp.
  `FDuelEngine::RunSelfTest` and `UDADuelRulesSelfTestSubsystem::Initialize`
  both call it; the subsystem still uses `FParse::Param` for the bare
  `-DADuelRulesSelfTest` switch and the HUD still owns the bare
  `-DADuelSelfTest` token.

### Diagnostics / tests

- `CheckDuelStateInvariants` now verifies `ResultStats.bDraw` against `bDraw`,
  rejects `bPlayerWon` on a draw, and rejects a disagreement between
  `bPlayerWon` and the winning side on a normal result.
- `RunSelfTest` counts draws separately and prints `%d draws` before
  `%d stalls` (the `run_smoke.py` stalls parser still reads the last token
  before "stalls").
- `DADuelRulesSelfTest` additions:
  - double KO via Sparks -> `IsOver`, `IsDraw`, stats, empty winner name,
    no pending choice, no open chain;
  - `Card Destruction` with both decks empty -> draw;
  - single empty deck -> loss, not draw;
  - one-sided `Card Destruction` deck-out -> loss, not draw;
  - negated one-shot Spell chain link leaves the field;
  - scripted Counter Trap / Quick-Play rules report Speed 3 / Speed 2;
  - `ShouldAttack` rejects illegal direct/attacker/target ids and accepts legal
    cases;
  - normal `DebugFinishDuel` win remains `!bDraw`.

## Verification

- Reviewed the modified functions against the pass-1 baseline and the current
  `DADuelUI.cpp` result path (read-only; no UI edits).
- `git diff --check` on every modified tracked file reports no whitespace
  errors (only Git's LF/CRLF advisory). The untracked
  `DADuelEngineDiagnostics.cpp` was checked with
  `git diff --no-index --check -- NUL <file>`; no whitespace errors.
- A delimiter scan (strings/comments stripped) reports balanced `{}`, `()` and
  `[]` in all modified `.cpp` files.
- No UnrealBuildTool / UnrealEditor run was performed, per the pass-2 rules;
  the new self-tests were not executed. The parent session owns the combined
  build and headless runs.

Suggested parent commands:

```
-DADuelRulesSelfTest
-DADuelSelfTest=24
-DAPuzzleExamSelfTest
```

`-DADuelRulesSelfTest` will report a higher pass count than the pass-1 docs
because of the new checks; `run_smoke.py` only requires `failed == 0`, not an
exact total.

## Remaining risks / follow-ups

1. **Build/run pending.** All C++ changes are statically reviewed only. The new
   `DADuelRulesSelfTest` blocks depend on `Sparks`, `Card Destruction` and a
   normal-Spell scenario placement; all three exist in the committed card data.
2. **AI outcome drift.** Effect-granted direct attacks are now visible to both
   the UI and the AI; those cards can change AI-vs-AI decisions compared with
   pass 1. Determinism should be preserved (same seed, same card order), but the
   1,000-duel win split can move. The self-test invariant checks are the gate,
   not the old split.
3. **Draw compatibility.** `GetWinner()` still returns a side on a draw for
   pre-existing consumers. `DAPuzzleRuntime` treats that as a loss, which is
   safe; `DADuelUI` now reads `ResultStats.bDraw`. Any new consumer must use
   `IsDraw()`.
4. **Overkill damage accounting** remains (see findings). It can inflate
   `BattleDamageDealt` and scenario damage objectives. A data-aware fix should
   re-run the puzzle audit.
5. **Post-duel presentation triggers** are intentionally suppressed once the
   result is final. If a card animation relies on a final destruction floater,
   the HUD may show a slightly shorter effect reel.
6. **`Card Destruction` pre-check** is a snapshot taken before discarding. The
   legacy path has no discard-triggered deck changes, so the check is exact for
   current scripts; a future on-discard trigger that shuffles/draws could
   require re-checking after the discard. The both-short branch ends the duel
   before moving the hands to the Graveyard; the result is correct, but the
   final zone contents differ from a full resolution.
7. **Diagnostics coupling.** `DADuelEngineDiagnostics.cpp` now includes
   `DADuelRulesSelfTest.h` to share the launch-argument parser. Both are in the
   same module and the header has no engine dependency; if the diagnostics
   file is ever split into a test-only module, move the parser with it.
8. **Dead declarations.** `PickSummonTrap` is still declared but undefined;
   removing it was left out to keep this diff scoped.
