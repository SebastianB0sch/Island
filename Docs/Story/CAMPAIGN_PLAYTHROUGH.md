# Full Campaign Playthrough Harness (E02–E33)

> **Owner:** A03 (Director).
> **Files:** `Source/DuelAcademyIsland/Public/DAStoryPlaythroughTest.h`,
> `Source/DuelAcademyIsland/Private/DAStoryPlaythroughTest.cpp`, plus the test
> hooks added to `DAStorySubsystem.h/.cpp`.
> **Scope:** in-engine runtime proof, not another data audit. `-DAFullStorySelfTest`
> still owns static reachability; this harness plays the real scene queues.

---

## 1. What it proves

`UDAStorySubsystem::RunStoryPlaythroughTest()` runs inside the normal
`UGameInstance` with the normal `UDAProfileSubsystem`, `UDACalendarSubsystem`,
`UDAInventorySubsystem` and `UDATitleSystem` instances. It:

1. snapshots the live profile/calendar/story/inventory, then starts a fresh
   profile and plays the real opening (`E01` + `E01b`) through the scene queue;
2. sets A02's calendar to Saturday, October 7, Year 1 and walks **365 days**
   (AM/PM/Night) through the school year;
3. attempts every canonical event in `order` order whenever its trigger and
   requirements are valid, and records the exact requirement that blocks it
   (including events whose canon date is beyond the first 365 days);
4. forces only the data-declared gates that a single natural save cannot satisfy
   (exclusive dorm gates, the `Dropout Boy` title, and the three flags that no
   current lane produces), then replays every remaining event through the real
   queue;
5. for each event calls `StartEvent`, drives `Advance()` / `Choose(0)` through
   every dialogue/choice command, resolves every duel with
   `NotifyDuelResult(true, false)`, and waits for `End`;
6. verifies flags, DP, cards, titles, dorm, emails, pack grants and duel
   requests after each event;
7. restores the snapshot, so the live save is not overwritten.

The harness is deterministic: option 0 is always chosen, every story duel is a
win, and no random roll is used.

---

## 2. Switches

```powershell
# Auto-run once the world/story are loaded, then exit.
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  /Game/DuelAcademy/Maps/DuelAcademyIsland `
  -game -nullrhi -DAStoryPlaythroughTest
```

The harness does not need a HUD. It forces the manual-audience path, so it also
works in a windowed `-game` run.

Console command (same suite, on demand):

```text
da.StoryPlaythroughTest
```

Do **not** combine `-DAStoryPlaythroughTest` with `-DAOpeningTest`,
`-DAStorySelfTest`, `-DAFullStorySelfTest`, `-DADuelSelfTest` or UI screenshot
switches in the same process. The harness snapshots/restores the live save, but
it is still a single-run test switch.

---

## 3. Coverage table

“Gate” is the authored requirement shape; the natural 365-day pass may not
satisfy exclusive dorm gates in one save, so those events are replayed in the
forced runtime pass.

| Event | Title | Scene | Duels | Dialogue | Trigger | Gate |
| --- | --- | --- | ---: | ---: | --- | --- |
| `E01` | School Registration | `full.E01` | 0 | 3 | new_game | - (opening.json owns runtime) |
| `E02` | Pharaoh's True Power | `full.E02` | 1 | 2 | talk | dorm; counter |
| `E03` | A New Hero Summoned | `full.E03` | 1 | 2 | event | dorm; counter |
| `E04` | Old Memories, Part 1 | `full.E04` | 1 | 2 | talk | counter; flag |
| `E04b` | Old Memories, Part 2 | `full.E04b` | 1 | 2 | event | event; weekday; period |
| `E05` | The Power of the Kaiser | `full.E05` | 1 | 2 | event | event; counter; dorm |
| `E06` | Dark Fiend Deck | `full.E06` | 1 | 2 | event | counter; any(dorm); counter |
| `E07` | Occult Recommendation | `full.E07` | 1 | 2 | event | event; card |
| `E08` | Jinzo | `full.E08` | 1 | 2 | event | event |
| `E09` | Duel Festival | `full.E09` | 1 | 2 | date | - |
| `E10` | Merry Christmas | `full.E10` | 0 | 2 | date | counter; flag |
| `E11` | New Year's Duel | `full.E11` | 1 | 2 | date | - |
| `E12` | Pride of the Elite | `full.E12` | 3 | 2 | weekday | counter; dorm |
| `E13` | Battle against Chazz | `full.E13` | 1 | 2 | event | any(dorm); counter |
| `E14` | Revenge of the Obelisk Blues | `full.E14` | 1 | 2 | event | event |
| `E15` | Chazz Reborn | `full.E15` | 1 | 2 | event | event; counter |
| `E16` | Brier and Beauregard | `full.E16` | 2 | 2 | talk | dorm; counter |
| `E17` | The Goblin King | `full.E17` | 2 | 2 | event | event; counter; dorm |
| `E18` | Who Are You? | `full.E18` | 0 | 3 | talk | dorm |
| `E19` | A Suspicious Character | `full.E19` | 3 | 2 | talk | event; weekday; period |
| `E20` | A Shadow Game | `full.E20` | 3 | 2 | talk | event; period |
| `E21` | Suspicious Classmate | `full.E21` | 0 | 3 | event | met flags |
| `E22` | Draw, Draw, Draw | `full.E22` | 1 | 2 | event | counter; dorm; event |
| `E23` | Yugi's Legendary Deck | `full.E23` | 1 | 2 | event | event; any(dorm) |
| `E24` | Missing Hero | `full.E24` | 1 | 2 | talk | dorm; event; counter |
| `E25` | The Power of a Maiden's Love | `full.E25` | 1 | 2 | event | event; counter; period |
| `E26` | The 7th Deck | `full.E26` | 1 | 2 | event | event |
| `E27` | The Truth Behind Gerard | `full.E27` | 0 | 3 | event | flag |
| `E28` | Battle for the Chocolate! | `full.E28` | 4 | 1 | date | met flags |
| `E28b` | Reversal Valentine's Day | `full.E28b` | 0 | 3 | date | event |
| `E29` | Helping the Dropout | `full.E29` | 1 | 2 | talk | title `Dropout Boy`; dorm |
| `E30` | A Friend's Concern | `full.E30` | 1 | 2 | flag | dorm |
| `E31` | The Walk Home | `full.E31` | 1 | 2 | flag | flag |
| `E32` | Help Miss Dorothy | `full.E32` | 0 | 2 | weekday | exam_day |
| `E33` | The Duel King | `full.E33` | 0 | 3 | flag | counter; flag |

Totals: **35 events / 44 full-campaign scenes / 89 dialogue keys / 39 full-campaign duel
commands / 6 email contacts / 6 email duel requests**. The playthrough also
resolves the opening `E01` tutorial duel, so its aggregate story-duel count is
40/40 (39 full-campaign + 1 tutorial).

---

## 4. Runtime defects found and fixed

These were found while making the campaign actually run, not just validate:

1. **Automation could not drive UI-blocked commands.**
   Headless mode skipped dialogue and choices, so `Advance()`/`Choose()` were
   never exercised. Added an internal manual-audience path used only by the
   harness: dialogue blocks, `Advance()` resumes; choice blocks, `Choose(0)`
   applies; duel blocks, `NotifyDuelResult()` resolves. The old UI and headless
   paths are unchanged.
2. **Text-entry automation soft-locked.**
   `Advance()` did not clear `bPendingTextInput`, so a headless/automation run
   could stop on the opening name-entry line. `Advance()` now confirms the
   current profile name and clears the pending text-input flag, matching
   `HandleDialogueClosed`. The live UI now has a real text field; the harness
   stays headless and confirms the default.
3. **Duel commands could only be resolved by polling the HUD.**
   A manual duel now stays pending until `NotifyDuelResult(true, false)` is
   called. Sequential duels (E12, E16, E17, E19, E20, E28) continue correctly
   when no `on_win`/`on_lose`/`on_draw` scene is authored.
4. **Missing scenes silently completed events.**
   `StartScene()` used to call `FinishEvent(true)`, which could mark an event
   complete even when its scene was absent. It now fails the event and increments
   the harness diagnostic counter.
5. **Choice next-key lookup could silently restart a scene.**
   `FindCommandIndexForKey()` returned `0` for an unknown key. It now returns
   `INDEX_NONE`, logs the missing key and falls back to the top of the target
   scene, so a typo is visible instead of looking like a valid transition.
6. **Pack rewards were log-only.**
   `grant_pack` outcomes and `pack`/`pack_grant` rewards now queue an unopened
   pack grant in story state (`GetPendingPackGrants()` /
   `ConsumePendingPackGrant()`), with save/load support. A06 does not expose an
   unopened-pack inventory yet, so this is the handoff point rather than an
   invented economy rule.
7. **Email unlock/read/duel-request hooks were data-only.**
   `CompleteEvent()` now applies `emails.json` `unlocked_by` contacts, creates
   the authored pending `duel_requests` through
   `UDAProfileSubsystem::AddDuelRequest`, and unlocks the matching A07 opponent
   id through `UnlockDuel`. The harness checks unlock, read (`MarkEmailRead`),
   pending request and consume/restore state.
8. **Auto-start raced explicit event starts.**
   The harness suppresses `TryStartNextAvailableEvent()` while it is driving one
   event at a time. Normal gameplay is unchanged.
9. **Card grants had no provider fallback.**
   If A06 inventory is unavailable, story card grants now fall back to the
   profile `card_<id>` counter used by the event graph, instead of disappearing.
10. **Calendar rollover was only assumed.**
   The harness uses `AdvanceDay()`/`AdvancePeriod()` for 365 days and asserts all
   12 month indexes were visited. No A02 code was edited.
11. **Date windows use the school-year calendar.**
   E11/E28/E28b are January/February/March of **school Year 1** (October–September).
   A02's `Year` is the school year, so they are inside the natural 365-day pass.
   An earlier harness revision simulated January–September as literal Year 2 and
   falsely reported them as blocked; the audit now walks one school year.

---

## 5. Remaining blockers / notes

| Blocker | Detail |
| --- | --- |
| **World flags now have producers** | `NotifyRoomStay` (room-bed interactable, weekends only), `NotifyWalkHome` (harbor walk-home interactable) and the year-2 post-game gate write `stayed_in_room_three_weekends`, `walk_home_partner_3` and `post_game`. The harness still simulates them for deterministic coverage. |
| **Exclusive dorm gates** | E02/E03/E12/E24/E29/E30 require Slifer, E16/E17/E18 require Ra, E05/E22 require Obelisk, and E13 writes Obelisk. A single natural save cannot hold two dorms at once, so the natural pass reports the exact dorm blocker and the forced pass sets the requested dorm through A02 `SetDorm`. The campaign still needs an authored dorm-change/reassignment path or a canonical event ordering decision. |
| **E29 fail state** | `Dropout Boy` is produced by A02/`UDATitleSystem::ApplyExamOutcome(0)`, and `FDAExamUI` now calls it on a failed exam. The harness also invokes it directly for determinism. |
| **Unopened packs** | Story state holds the grant; A06/A09 must consume `GetPendingPackGrants()` / `ConsumePendingPackGrant()` to show/open the pack. |
| **Duel result callback** | `FDADuelUI` now records the profile/opponent result and calls `NotifyDuelResult` after the result screen closes. The harness calls the same hook directly. |
| **Name entry UI** | `FDADialogueUI` now implements the 1–8 character text field; automation and the harness still confirm the default name. |
| **Exact dialogue text** | `dialogue/full_campaign.json` remains port-scaffold paraphrase, not exact canon text. |
| **Placeholder content** | E04 one-turn setup, E09 bracket, E17 timed puzzle and E28 bracket order remain scaffold rules; E20 is now a three-location chain and E29 now uses remaining-LP DP. |

---

## 6. Expected log lines

A successful `-DAStoryPlaythroughTest` run ends with stable aggregate lines.
Per-event lines include the title and command counts and may differ only in those
details.

```text
StoryPlaythroughTest: PASS full campaign loaded
StoryPlaythroughTest: PASS 35 canonical events
StoryPlaythroughTest: PASS every canonical event has a loaded scene
StoryPlaythroughTest: PASS every dialogue/choice key resolves
StoryPlaythroughTest: PASS every scene command is supported
StoryPlaythroughTest: PASS every duel command names an opponent
StoryPlaythroughTest: PASS every outcome reward id resolves
StoryPlaythroughTest: PASS opening E01/E01b completed
StoryPlaythroughTest: INFO simulated external progress: 220 wins, 60 timed clears, 130 written answers (... counters set)
StoryPlaythroughTest: INFO natural 365-day timeline: .../35 events completed
StoryPlaythroughTest: INFO natural blocker E05 @ ...: dorm is slifer, expected obelisk
StoryPlaythroughTest: INFO natural blocker E16 @ ...: dorm is slifer, expected ra
StoryPlaythroughTest: INFO forced gates E05: dorm Obelisk Blue
StoryPlaythroughTest: INFO forced gates E16: dorm Ra Yellow
StoryPlaythroughTest: PASS event E02 (Pharaoh's True Power): duels 1/1, dialogue 2, choices 0, outcomes 3
...
StoryPlaythroughTest: PASS event E33 (The Duel King): duels 1/1, dialogue 4, choices 0, outcomes 1
StoryPlaythroughTest: PASS all 35 events started
StoryPlaythroughTest: PASS all 35 events completed
StoryPlaythroughTest: PASS 39/39 full-campaign duel commands resolved
StoryPlaythroughTest: PASS all story duels resolved (40/40 including the E01 tutorial)
StoryPlaythroughTest: PASS no missing scenes
StoryPlaythroughTest: PASS no missing dialogue/choice keys
StoryPlaythroughTest: PASS no unknown command types
StoryPlaythroughTest: PASS no unknown outcome types
StoryPlaythroughTest: PASS 6 email contacts unlocked
StoryPlaythroughTest: PASS email read state applied
StoryPlaythroughTest: PASS 6 email duel requests pending
StoryPlaythroughTest: PASS email duel requests unlocked for A07
StoryPlaythroughTest: PASS duel request consume/restore
StoryPlaythroughTest: PASS E10 pack grant recorded
StoryPlaythroughTest: PASS E32 pack grant recorded
StoryPlaythroughTest: PASS pending pack consume API
StoryPlaythroughTest: PASS opening flags preserved
StoryPlaythroughTest: PASS E33 King of Games title applied
StoryPlaythroughTest: PASS calendar advanced a full school year
StoryPlaythroughTest: PASS calendar visited all 12 months
StoryPlaythroughTest: SUMMARY PASS: 35/35 events started, 35/35 events completed, 40/40 story duels resolved (39/39 full campaign), 6/6 email contacts, ... pending packs, 28/28 checks passed, 0 checks failed, 0 event failures
StoryPlaythroughTest: PASS in 0.xxx s
```

A failure produces `FAIL event <id>` with the event failure/effect failures and
`SUMMARY FAIL`; the harness returns `false` and the console command logs
`StoryPlaythroughTest: FAIL`.

---

## 7. Relationship to the existing tests

| Switch | Purpose | Expected |
| --- | --- | --- |
| `-DAStorySelfTest` | Opening/E01 slice | **14/14 PASS** |
| `-DAFullStorySelfTest` | 35-event data/reachability audit | **20/20 PASS**, 35/35 reachable with progress |
| `-DAStoryPlaythroughTest` | In-engine E02–E33 runtime playthrough | **35/35 events**, **39/39 full-campaign duels** (+ E01 tutorial), 28/28 checks, 0 missing |

The playthrough harness is deliberately separate from the two existing suites so
a failure in full-campaign runtime cannot be masked by the static audit, and the
opening behaviour remains untouched.
