# Code Review & Refactor Pass 2 — Workstream Brief

This pass stacks on top of the uncommitted first review pass
(`Docs/CodeReview/00-overview.md`). The first pass is the baseline: do not
revert it, reformat unrelated code, or regenerate committed data.

## Goals

- Audit the remaining high-risk follow-ups from pass 1.
- Cover runtime systems that pass 1 did not review.
- Fix high-confidence correctness, robustness, lifecycle and performance
  defects; do not stop at a findings report.
- Refactor only where the change is cohesive and behavior-preserving.
- Add or extend regression tests where the existing harness supports it.
- Preserve public APIs and serialized data formats unless a clear bug requires
  an additive change.

## Rules

- Every workstream owns a disjoint file set. Read anything, edit only your
  scope plus your report in this directory.
- Do not run UnrealBuildTool or the Unreal editor. The parent session owns the
  combined build and headless runs.
- Do not edit generated runtime data, manifests, reports, or assets.
- Do not rewrite files just to change line endings or formatting.
- Keep changes reviewable and add a short rationale in the report.
- Run `git diff --check` on your changed files and any scoped tests you can run
  without a renderer or Unreal process.

## Reports

Each workstream writes `NN-name.md` with:

1. Scope and constraints.
2. Findings table (severity, location, finding, status).
3. Changes made.
4. Verification performed.
5. Remaining risks / follow-ups.

The parent session writes `00-overview.md` after integration.
