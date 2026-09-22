# Scope and first 30 days

## User and stack

A maintainer edits a GitHub Actions workflow with matrix builds and named
artifacts. Run one local command before CI to see conflicting producer instances
or downloads that do not wait for their producers.

Python 3.11 + PyYAML keeps the core small and supports local installation and
testing on three OS families. Go could offer a standalone binary and alignment
with actionlint, but would increase the initial implementation cost. TypeScript
would fit Actions tooling but still needs a YAML parser and runtime. No AI API,
database, account or server is required. Project and PyYAML use MIT licenses.

## Release 0.1 acceptance

1. Expand literal matrices with include/exclude and identify concrete names.
2. Detect duplicate/invalid names and concurrent overwrites.
3. Check named downloads against same-job order and transitive needs.
4. Emit text, JSON and SARIF with source locations; incomplete analysis exits 2.
5. Install a distributable wheel, run documented examples, and pass meaningful
   matrix/order/input/CLI tests in a clean environment.

Dynamic expression evaluation, reusable workflow traversal, cross-run downloads,
archive content merging and executing workflows are outside this release.
An unknown result is useful evidence of a scope boundary, not success.

## Days 1–7: validate the pain

After choosing a repository and reviewing the bundle, publish an honest alpha
with the collision/fixed examples. Review current issue timelines before any
outreach. Seek three voluntary maintainer trials through relevant discussions
where project announcements are welcome. Do not post unsolicited repeated
messages or claim the tool solves backend bugs. No outreach has been performed.

Record: workflow complexity, findings confirmed by its maintainer, unknown
reasons, installation friction and time until a useful result. Ask permission
before retaining private workflows. Prefer minimized, synthetic reproductions.

## Days 8–14: measure precision

Aim for at least ten diverse consenting/public workflow reviews, including
examples expected to pass. Record false positives and scope failures separately.
A finding must map to a reproducible artifact failure or ordering hazard; raw
finding counts are not a measure of value. Discuss whether a focused upstream
actionlint rule is preferable to maintaining a separate tool.

## Days 15–21: implement only a demonstrated need

Choose one improvement from observed blockers: constrained pattern matching,
reviewed ref mapping, or reusable workflow input propagation. Do not implement a
general GitHub expression engine. Add regression cases from confirmed reports
and document when a requested feature would produce unreliable conclusions.

## Days 22–30: keep or consolidate

Seek one real, voluntary CI integration and evidence that a maintainer reran the
tool after their first trial. These are internal learning targets, not official
requirements of a support program. If nobody returns or upstream covers the
rules, consolidate the work upstream instead of adding more features.

Publish a small release only after checking all configured CI platforms, package
metadata, installation and changelog. Keep issue responses and accepted fixes as
evidence of maintenance. Stars/downloads alone do not demonstrate useful use;
never manufacture adoption or formal contributions.

## Ongoing cost and risks

Runtime costs are local CPU only. Hosted CI depends on the chosen hosting plan;
no account or paid infrastructure was provisioned. Budget roughly a few hours
weekly for reports and action-version changes during the trial, then reassess.
The highest maintenance risk is semantic drift of GitHub Actions and artifact
versions. Unsupported new refs should remain explicit unknowns until reviewed.
