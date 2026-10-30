# A10 — Gatekeeper

> **Read first:** `Docs/PORT_MASTERPLAN.md` (all sections, especially gates and §7).
> **Role:** integration, QA, release.
> **Baseline branch:** `port/baseline`; your work branch `port/a10-integration`.
> **You are the tech lead/gatekeeper, not a content lane.**

## Mission

Keep ten lanes shippable: freeze contracts, merge safely, build the test harness, prove the 12-month campaign, package the build and audit the release.

## Inputs

- All agent branches/worktrees.
- `Docs/PORT_MASTERPLAN.md`, `Docs/AgentBriefs/*`.
- Current build scripts/config: `DuelAcademyIsland/Build/**`, `Config/*.ini`, `DuelAcademyIsland.Build.cs`.
- Donor CI/tests: `C:\dev\argh\.github/workflows/ci.yml`, `tests/`, `game3d/tests/`.

## Owned files

- `Tools/validate/**`, `Tools/integration/**`
- `.github/workflows/**`
- `DuelAcademyIsland/Build/**`, build wrappers (`Build.bat` etc.)
- `Docs/PORT_STATUS.md`, `Docs/Contracts/**` (with lane owners)
- `Content/Data/Integration/**` (golden saves, fixtures, reports)
- Shared-file changes: `DAGameMode.*`, `DATypes.h`, `DAIslandSubsystem.*`, `DAStudentCharacter.*`, `Config/*.ini`, `.uproject`, `Build.cs`, target files.

## Responsibilities

1. **Baseline and branches**
   - Protect the current dirty WIP: commit/stash on `port/baseline`; verify build + current Jaden self-test.
   - Create `port/a01`…`port/a10` worktrees; enforce one-writer-per-file.
   - Maintain `Docs/Contracts/README.md`, `CHANGELOG.md`, API freeze notes.

2. **Contracts**
   - Freeze `FStoryCommand`, `FDuelRequest`, `FDuelResult`, save schema, data schemas, subsystem APIs.
   - Review lane RFCs; reject changes that bypass contracts.
   - Keep contract headers compiling for all lanes.

3. **Validation harness**
   - `Tools/validate/validate_all.py`: cards, decks, packs, events, puzzles, exams, schedules, effects, anchors.
   - Unreal automation: profile/calendar/save/story/rules/economy/opponents/puzzles/exams/world/UI smoke.
   - Self-tests: `-DADuelSelfTest` 1,000 duels; `-DAStorySelfTest` 12 months; `-DAPuzzleSelfTest` 100; `-DASaveSelfTest` fuzz/migration.
   - Golden saves/fixtures in `Content/Data/Integration/`.

4. **Integration**
   - Merge in gate order (§6); run the full suite after each merge.
   - Resolve cross-lane API mismatches; file bugs to owners.
   - Maintain `Docs/PORT_STATUS.md` (what works, what is blocked, test counts, known issues).

5. **Playthrough/QA**
   - Scripted opening → 12 months → credits; save/load at every beat.
   - Manual checklist §7.3; controller/mouse/keyboard; performance.
   - Crash/log triage; no P0/P1 at release.

6. **Release**
   - Clean-checkout build + package; verify `Content/Data` staging.
   - Legal/asset audit; no ROM/save/ripped assets; credits.
   - README/controls/known issues; tag.

## Acceptance criteria

- [ ] Baseline builds; current Jaden duel passes before parallel work starts.
- [ ] Contracts frozen and documented; all lanes compile against them.
- [ ] `validate_all.py` + UE automation green.
- [ ] 1,000 AI duels no stalls; 100/100 puzzles; 12-month simulation passes.
- [ ] Full playthrough passes; save fuzz/migration/corruption tests pass.
- [ ] Performance budgets met; packaged build launches/saves/loads.
- [ ] No P0/P1; legal audit clean; docs/credits updated.

## Non-goals

- Writing content/effects/UI/world (lane owners). You integrate and test; you may make minimal glue fixes and must notify the owner.

## Handoff/report format

Every gate: status, merged branches, test counts, failures, owners, next actions. Keep `Docs/PORT_STATUS.md` current.
