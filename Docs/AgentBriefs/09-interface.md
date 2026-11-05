# A09 — Interface

> **Read first:** `Docs/PORT_MASTERPLAN.md` (story command contract §4.3, UI ownership).
> **Role:** UI/UX, dialogue, PDA, shop/deck/exam screens, presentation.
> **Baseline branch:** `port/baseline` → work branch `port/a09-interface`.

## Mission

Make the port feel like a complete game: every screen, every line, every reward, every transition. Build the code-only Canvas UI the project already uses; do not add Blueprint/binary UI assets.

## Inputs

- Current: `DAHUD.*`, `DADuelUI.*`, `DADuelUI.h`, `DAStudentCharacter.*` input, `DAIslandSubsystem.*` messages.
- A02: profile/calendar/title/DP/save/settings APIs.
- A03: story commands + text keys.
- A06: inventory/shop/deck APIs; A07: opponent/exam/puzzle payloads.
- A01: portrait manifest, UI strings.
- Donor: `$GX_ROM\ue5\Source\DuelAcademy\DuelAcademyHUD.*` (dialogue/deck/duel screens), `CharacterPortraitSubsystem.*`.

## Owned files

- `.../DAHUD.*`, `DADuelUI.*`
- `.../DADialogueUI.*`, `DAPDAUI.*`, `DAShopUI.*`, `DADeckUI.*`, `DAExamUI.*`, `DASaveUI.*`, `DACutscene.*`
- `.../DACardArtSubsystem.*`, `DACharacterPortraitSubsystem.*`
- `Content/Data/UI/**`
- Tests: `DAUISmokeTests.cpp`, screenshot/debug modes.

Shared `DAStudentCharacter.*` input changes only via A10; request a key/modal hook.

## Deliverables

1. **Title/new game/continue**
   - Title screen, continue slots with metadata, new game name entry, erase confirm, options, credits.
   - Intro/loading fades; first-launch defaults.

2. **HUD**
   - Calendar/clock, location banner, objective, DP, title, dorm, interaction prompt, toasts, compass/minimap.
   - Fast-travel map with interior/location markers; unlock/discovery state.
   - Debug overlays for screenshots.

3. **Dialogue/cutscenes**
   - Typewriter, speaker name, portrait/expression, choices, history/log, skip/auto, click/E/Space advance.
   - Story command execution: dialogue, choice, camera, move NPC, fade, wait, banner, SFX/music, duel, reward.
   - Letterbox/fade/slow-pan; skippable; save/load mid-scene.
   - Portrait fallback for speakers without art (silhouette/monogram).

4. **PDA**
   - Tabs: Map, Calendar, Deck, Mail, Save, Options, Records, Limitation.
   - Calendar shows month/weekday/period/exam days/events; deck opens A06 UI; mail contacts/messages/duel requests; records/titles/DP; limitation list; save/load slots.
   - Keyboard/gamepad/mouse navigation; no dead ends.

5. **Shop**
   - Pack browse by category, price, unlock reason, owned count, DP balance; purchase confirm; pack-opening animation; card reveal; duplicate handling; Dorothy's Gift.

6. **Deck editor**
   - Collection list with filters/sort, deck slots, add/remove, counts, validation messages, recipes, copy/erase/rename, extra deck, banned/limited indicators.
   - Works with A06 logic; no rules duplication.

7. **Exam/puzzle UI**
   - Written question screen (10 questions, timer, answer feedback).
   - Timed puzzle board/objective/timer/retry.
   - Practical objective/progress/score breakdown; pass/fail; title/dorm promotion.
   - Result screen for normal duels: win/loss, DP breakdown, rewards, rematch/return.

8. **Presentation/accessibility**
   - Controller/keyboard/mouse; remapping? (at least display); 1080p/4K legibility; color-safe states; text speed; skip.
   - Audio hooks for UI/duel/story; no ripped audio.
   - Screenshot modes for every screen.

## Work plan

1. Build PDA shell + title/new game + save/load UI against A02 stubs.
2. Build dialogue/cutscene executor against A03 stub commands; test opening.
3. Build shop + deck editor against A06 stubs; build exam UI against A07 stubs.
4. Integrate real APIs; add result/DP/title/dorm screens.
5. Add controller/mouse paths, history/log, settings.
6. Screenshot every screen at 1080p/4K; fix layout/legibility.
7. Freeze UI API; support A10 smoke tests.

## Acceptance criteria

- [ ] Every screen reachable/closable with keyboard, gamepad, mouse; no modal deadlocks.
- [ ] Story commands execute correctly; save/load mid-scene; skip/auto.
- [ ] PDA tabs all work; calendar/mail/records/limitation accurate.
- [ ] Shop/deck/exam flows complete; validation/error states clear.
- [ ] All strings from data/keys; no hardcoded story text.
- [ ] Portraits/expressions/fallbacks work for every speaker.
- [ ] 1080p/4K screenshots pass; no UI overlaps; performance budget met.
- [ ] No gameplay rules implemented in UI; APIs consumed only.

## Non-goals

- Story content (A03), inventory/shop logic (A06), exam scoring (A07), duel rules (A04), world geometry (A08).

## Handoff report

Report: screens implemented, input paths, screenshot paths, API assumptions, known UI gaps, blockers.
