# Test fixtures

Small, deterministic JSON inputs used by integration tests. Keep each fixture
focused on one scenario and document the expected result next to it.

Planned fixtures (owners):

- `save_pre_exam.json` (A02) - calendar/DP/exam state before a Friday exam.
- `save_mid_scene.json` (A02/A03) - `story.command_index` resume state.
- `duel_request_story.json` (A04) - `FDuelRequest` in story mode.
- `duel_result_win.json` (A04) - `FDuelResult` with DP statistics.
- `pack_opening_seed_42.json` (A06) - deterministic 5-card pull.
- `event_choice_accept.json` (A03) - choice outcome and flags.
- `puzzle_solution_P001.json` (A07) - scripted one-turn solution.

Fixtures must not contain timestamps that change per run, and must not contain
ROM/save data or ripped assets. Add a validator assertion when you add one.
