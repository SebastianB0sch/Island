# Code Review & Refactor Pass 3 — Workstream Brief

This pass stacks on the uncommitted pass-1 and pass-2 tree on
`refactor/code-review-pass`. That tree is the baseline: do not revert, reformat,
or regenerate unrelated work.

## Why this pass

Pass 2 closed the largest defects but left a set of explicitly documented
follow-ups and several areas that were only audited at the surface. Pass 3
targets those follow-ups plus the remaining unowned vertical slices (timed
puzzles, world persistence, economy runtime, asset-pipeline transactionality,
and the build/test harness itself).

## Goals

- Convert deferred correctness work into implemented, tested changes where the
  contract is clear.
- Review runtime paths that pass 1/2 only spot-checked.
- Add regression coverage through the existing Unreal self-tests, automation
  tests and Python `unittest` suites.
- Keep public APIs and serialized formats stable unless an additive change or a
  high-confidence bug fix is required.
- Leave an explicit, honest list of remaining risks; do not hide incomplete
  work behind a green gate.

## Rules

- Every workstream owns a disjoint file set. Read anything, but edit only your
  scope plus `Docs/CodeReview/Pass3/NN-name.md`.
- Do not run UnrealBuildTool, UnrealEditor, Blender, or any Unreal process. The
  parent session owns the combined build and headless suite.
- Do not edit generated runtime data, manifests, reports, committed assets or
  golden saves unless the workstream scope explicitly says so.
- Do not rewrite files just to change line endings or formatting.
- Keep changes reviewable. Small, cohesive refactors are welcome; speculative
  rewrites are not.
- Use existing helpers and conventions. Add a helper rather than duplicating a
  block when the new call site is in your scope.
- Run `git diff --check` on changed files and every scoped test/validator that
  does not require a renderer or Unreal process.
- If a fix requires a file outside your scope, do not edit it. Describe the
  exact required change in your report so the parent can integrate it.

## Reports

Each workstream writes `NN-name.md` with:

1. Scope and constraints.
2. Findings table: id, severity, location, finding, status.
3. Changes made, with rationale and API/serialization impact.
4. Verification performed, including commands and exact results.
5. Remaining risks and cross-workstream follow-ups.

The parent session writes `00-overview.md` after integration.
