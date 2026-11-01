# 01 — Duel Engine & Rules Review

Scope: `DADuelEngine.cpp/.h`, `DADuelistAI.cpp/.h`, `DADuelRules.h`,
`DADuelRulesSelfTest.cpp`, and the new `DADuelEngineDiagnostics.cpp`.

## Summary

`DADuelEngine.cpp` was 9,250 lines and owned both runtime rules and the
AI-vs-AI diagnostics harness. The 987-line diagnostics block has been moved
into `DADuelEngineDiagnostics.cpp`, leaving the runtime unit at ~8,257 lines.
The public declarations in `DADuelEngine.h` are unchanged; only private
declarations were extended. The moved definitions are textually identical to
the originals (same messages, ordering and output strings).

The largest rules functions were reviewed for concrete defects. Fixes were
limited to cases where the existing code contradicted its own intent or card
text: a hard-coded "destroyed" result in `ResolveBattle`, a swapped
`OnBattleDamage` payload, incomplete F.G.D. battle protection, two stale
references across mutation, a range-for invalidation, and missing
post-duel guards. Two cohesive helpers were extracted
(`ApplyBattleDamage`, `ResolveReviveSpell`).

`DADuelistAI.cpp` and `DADuelRules.h` were reviewed but not changed: the AI
policy is deliberately independent of the engine, has no unsafe indexing, and
is not wired into `FDuelEngine` (the header documents that as an A04 hook).

Coverage notes for the six large functions: no unchecked fixed-zone indexing
was found (all `Monsters[]` / `Spells[]` loops are bounded, and the scenario
placement path checks its index); double-destroy is already guarded by
`DestroyMonster`'s uid re-fetch; `InflictDamage` refuses damage after
`bWinnerSet`; and the equip-target choice callback defers one-shot cleanup
through `PendingActivationCleanupUids`, so no choice/chain cleanup leak was
found in `ResolveSpell`.

## Findings

### Fixed

| Severity | Location | Finding |
|---|---|---|
| High | `DADuelEngine.cpp:3157-3169` | `ResolveBattle` hard-coded `bTargetDestroyed = true` after `DestroyMonster`. `DestroyMonster` can return early when an effect prevents destruction, so Flame Wingman / Shining Flare Wingman / Inferno / Fenrir / Yomi Ship / Winged Kuriboh follow-ups fired even when the target survived. `DestroyMonster` now returns `bool` (header `DADuelEngine.h:473`) and the result is used. |
| Medium | `DADuelEngine.cpp:3217-3252` | For damage dealt to the attacker (attacker loses the battle), the old `OnBattleDamage` call passed the attacking monster as both source and target identity: it reported `FindMonster(AttackerUid)` as the source and `FindMonster(TargetUid)` as the damaged card, while the damaged card was actually the attacker. The new `ApplyBattleDamage` helper reports `SourceUid` (the card that dealt damage) and `ReceiverCardUid` (the card that took it). No current effect script subscribes to `OnBattleDamage`, so this is a latent payload fix rather than a visible rules change. |
| Medium | `DADuelEngine.cpp:3119-3142` | F.G.D.'s protected-attribute battle clause zeroed battle damage but left `bDestroyTarget` / `bDestroyAttacker` set, so F.G.D. could still be destroyed by battle. The flags are now cleared for the protected monster only; F.G.D. can still destroy the opposing monster. |
| Medium | `DADuelEngine.cpp:3008-3014` | Sasuke Samurai called `AfterAttack(Attacker)` after `DestroyMonster`, even though the target's destruction effect (notably Yomi Ship) can destroy the attacker and free/reuse its slot. The attacker is now re-fetched by uid before `AfterAttack`. |
| Medium | `DADuelEngine.cpp:3407-3414` | `TriggerFlipEffect` called `EffectRuntime->OnFlip(Card)` and then read `Card.Uid` from the same reference. `OnFlip` may remove the card and reset/reuse the slot; the uid is now captured before the callback. |
| Medium | `DADuelEngine.cpp:3476-3493` | Magician of Faith erased a Spell from `SideRef(Side).Graveyard` inside a range-for over that array. Erasing invalidated the iteration before the `break`. The first Spell uid is now captured first, then removed. |
| Medium | `DADuelEngine.cpp:5934-5940` | `ActivateMonsterEffect` checked pending choices and locks but not `bWinnerSet`; a card with a manual effect script could still be activated after the duel ended. Added an explicit "duel is over" guard before the manual-effect branch. |
| Medium | `DADuelEngine.cpp:2761-2774` | Winged Kuriboh LV10's board wipe continued destroying monsters, and then applied burn, after a destruction-triggered effect had already ended the duel. The loop now breaks on `bWinnerSet` and the burn is skipped. |
| Low | `DADuelEngine.cpp:3032-3060` | When a damage-step effect removed the attack target, `ResolveBattle` returned without `AfterAttack`. That skipped Spear Dragon's position change and the extra-attack reset for Mermaid Knight / Gray Wing / `HasExtraAttack` monsters. `AfterAttack` is now called when the attacker survives. |
| Low | `DADuelRulesSelfTest.cpp:107-116` | The synthetic deck block indexed `Main40[0]` / `Main40[1]` even after reporting that a 40-card deck could not be built. A malformed card database could therefore crash the self-test instead of reporting a failure. Added an early report/return guard for fewer than two cards. |

### Reported, not fixed

| Severity | Location | Finding |
|---|---|---|
| Medium | `DADuelEngine.cpp:657-668` | A simultaneous double KO calls `EndDuel(EDuelOwner::Opponent, "Both duelists reached 0 Life Points.")`, while `FinalizeResultStats` sets `bDraw = true` for the same state. Result stats and ante treat it as a draw, but `Winner`, the log and the HUD see an opponent win. Fixing this requires a first-class draw result (and UI/achievement handling), so it is left as a rules/design follow-up. |
| Medium | `DADuelEngine.cpp:4720-4740` | Snatch Steal implements control transfer by removing the monster, calling `CleanupEquips`, and re-placing it with `PlaceMonster`. That destroys the opponent's equip cards attached to the stolen monster and resets `SummonedTurn` / `AttacksUsed`, which a pure control change should not do. `ReturnControl` does not call `CleanupEquips`, so the two paths are inconsistent. Fixing this cleanly needs a control-change primitive separate from remove/re-place. |
| Low | `DADuelEngine.cpp:3610-3773` | `DestroyMonster` runs battle floaters and Backfire after `EffectRuntime->OnDestroyed`; that callback can end the duel, but there is no `bWinnerSet` guard before the remaining triggers. Damage itself is guarded by `InflictDamage`, but post-duel summons/discards can still mutate the board. |
| Low | `DADuelEngine.cpp:3857-3884` | `DestroyAllMonsters` / `DestroyAllSpellTraps` iterate uid snapshots without stopping if a destruction trigger ends the duel. Same class of post-duel mutation as above. |
| Low | `DADuelEngine.cpp:5002`, `5153`, `5214` | The three manual Spell activation paths call `CheckWinner()` and return before `CleanupResolvedChainCard(Uid)` when the resolution ended the duel, so a one-shot Spell can remain face-up on the final board. Left unchanged because the final board may be intentional for the win presentation; the durable fix is to run the one-shot cleanup even when `bWinnerSet` (persistent/Field cards are already skipped by the helper). |
| Low | `DADuelistAI.cpp:341-363` | `ShouldAttack` computes `AttackWeight` from `attack_into_set_atk` and never uses it (`(void)AttackWeight`); `ScoreCardId` is also unused. The class is intentionally not wired into `FDuelEngine`, so its card scoring duplicates `FDuelEngine::AiCardValue` without sharing code. No safety issue found; left unchanged because the header documents the independent-policy design. |

## Changes made

- **New `DADuelEngineDiagnostics.cpp`**
  - Moved `FDuelEngine::CheckDuelStateInvariants`, its `SelfTest*` helpers,
    `FDuelEngine::RunSelfTest`, and the `da.DuelSelfTest` console command.
  - Kept anonymous-namespace helpers file-local.
  - Added only the includes the moved code needs.
- **`DADuelEngine.cpp`**
  - Removed the diagnostics block and seven includes that were used only by it
    (`HAL/IConsoleManager.h`, `HAL/FileManager.h`, `HAL/PlatformTime.h`,
    `Engine/World.h`, `Engine/GameInstance.h`, `Misc/CommandLine.h`,
    `Misc/Parse.h`; the rest were still used).
  - `ApplyBattleDamage`: extracted the duplicated redirect/zero/multiplier and
    `OnBattleDamage` pipeline in `ResolveBattle`.
  - `ResolveReviveSpell`: extracted the duplicated Premature Burial /
    Autonomous Action Unit revival flow.
  - `DestroyMonster`: returns `bool` indicating whether the card was actually
    destroyed and moved to the Graveyard/Banished pile.
  - `ResolveBattle`: uses the new helper, the destruction result, F.G.D.
    destruction protection, a safe Sasuke re-fetch, and `AfterAttack` on
    target-gone early returns.
  - `TriggerFlipEffect`: captured uid across `OnFlip`; safe Magician of Faith
    selection.
  - `ExecuteAttack`: stops the Winged Kuriboh LV10 wipe/burn when the duel ends.
  - `ActivateMonsterEffect`: rejects activation after the duel is over.
- **`DADuelEngine.h`**
  - Added private declarations `ApplyBattleDamage` and `ResolveReviveSpell`.
  - Changed private `DestroyMonster` to return `bool`.
  - Moved the hand limit to a private `static constexpr int32 HandLimit = 6` so
    the runtime and diagnostics translation units share one definition.
- **`DADuelRulesSelfTest.cpp`**
  - Guarded the deck-validation block against an undersized synthetic deck.
- **`DADuelistAI.*`, `DADuelRules.h`**
  - Reviewed; no changes (findings above are informational/follow-up).

## Verification

**Integration:** the combined editor build passed with no compiler warnings, and
`-DADuelSelfTest=24`, `-DADuelRulesSelfTest`, `-DAPuzzleExamSelfTest`,
`-DASaveFuzz=300 -DATwelveMonthTest` all passed. See
[00-overview.md](00-overview.md).

- `git diff --check` reports no whitespace errors (only Git's existing
  LF/CRLF advisory on this checkout).
- The moved diagnostics block was compared against `HEAD:DADuelEngine.cpp`;
  definitions, comments, log strings, ordering and the console command text are
  unchanged. The only source-level difference is that `HandLimit` now resolves
  to the shared private class constant instead of two file-local constants.
- Symbol checks confirm `DADuelEngine.cpp` no longer references `RunSelfTest`,
  `CheckDuelStateInvariants` or any moved `SelfTest*` helper, and that each
  removed include had no remaining use in that translation unit.
- No UnrealBuildTool / UnrealEditor run was performed, per the task
  instructions. The new `.cpp` is picked up automatically by the module.

## Follow-ups / risks

1. Build and run `-DADuelSelfTest=24`, `-DADuelRulesSelfTest`, and the puzzle
   gate after integration. The battle fixes can change AI-vs-AI outcomes for
   F.G.D., multi-attack monsters and destruction-prevention cases, even though
   determinism and the self-test invariants are preserved.
2. Draw semantics (double KO) remain unresolved; `ResultStats.bDraw` and
   `Winner` can disagree.
3. Snatch Steal / control-change semantics need a dedicated control-change
   primitive if equip and summon-state preservation is required.
4. `DestroyMonster` changed from `void` to `bool`. The two calls in
   `DAEffectRuntime.cpp` ignore the return value and remain source-compatible;
   future callers can now distinguish a prevented destruction.
5. Diagnostics code now lives in its own file; future self-test changes should
   go there rather than back into the runtime unit.
6. The F.G.D. protection remains a hard-coded name/attribute list, consistent
   with the engine's existing card-specific approach; it is not a general
   replacement for effect scripts.
7. `-DADuelSelfTest=N` is still parsed in `RunSelfTest`, `DAHUD.cpp` and
   `DADuelRulesSelfTest.cpp`. The moved implementation preserved that
   duplication; a single owner would avoid future drift.
