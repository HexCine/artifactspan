# ArtifactSpan

**[Start here: visual guide EN/RU](https://github.com/HexCine/artifactspan/releases/download/v0.1.2/start.html)** · [Русский: первый запуск](docs/QUICKSTART.ru.md)

Download `start.html` and open it in your browser for installation, a failing demo,
a passing comparison and next steps. Examples are synthetic and run locally.

[![CI](https://github.com/HexCine/artifactspan/actions/workflows/ci.yml/badge.svg)](https://github.com/HexCine/artifactspan/actions/workflows/ci.yml)

Find artifact-name collisions and missing producer ordering in GitHub Actions
**before a workflow runs**. Expand a static matrix, see the names each job would
upload, and check whether named downloads follow their producers.

A workflow can be valid YAML and pass ordinary input checks while every matrix
leg uploads `build`, or a consumer downloads `build-linux` without waiting for
the build job. ArtifactSpan focuses on that gap. Use it alongside actionlint.

Python 3.11+, PyYAML 6, MIT. Version 0.1.2 is an early release.
No GitHub token, network requests, shell execution, repository edits or uploads.

## Download a release

[Release v0.1.2](https://github.com/HexCine/artifactspan/releases/tag/v0.1.2) includes a wheel, source
archives, checksums and a verification record. With Python 3.11+, install the
downloaded wheel using `python -m pip install artifactspan-0.1.2-py3-none-any.whl`.
Runtime dependencies listed below are resolved by pip when needed.
For source development, clone this repository and follow the existing install steps.

## Install and try

From this repository in a virtual environment:

```sh
python -m pip install .
artifactspan examples/collision.yml
artifactspan examples/fixed.yml --format json
artifactspan examples/fixed.yml --format sarif
```

The collision example exits 1 with the two concrete producer locations. The
fixed example exits 0 and shows two upload-to-download edges. An additional
example, `examples/unknown.yml`, exits 2 because its matrix is computed at runtime.
Reports go to stdout; malformed input errors go to stderr. Redirect only to a
new report file, never onto the input workflow.

## Checks

| Finding | Meaning |
|---|---|
| `duplicate_upload` | More than one producer instance uses the same immutable artifact name |
| `concurrent_overwrite` | Unordered producers use a name with overwrite=true; replacement can race |
| `overwrite_during_download` | A replacement can occur concurrently with a consumer |
| `invalid_artifact_name` | Expanded name is empty or contains a forbidden character, such as a shard's `/` |
| `missing_producer` | Named download has no direct producer in the modeled workflow |
| `producer_not_ordered` | A producer exists, but neither earlier in this job instance nor in transitive needs |

`overwrite: true` permits a sequential replacement when the writer is ordered
after the prior writer. It does not establish ordering between matrix legs or
between a reader and another writer. `max-parallel: 1` does not make duplicate
immutable artifact names valid.

JSON includes `events`, `edges`, `findings`, `unknowns`, matrix coordinates,
source lines and `schema_version: 1`. SARIF 2.1.0 can be consumed by CI/code
scanning; the tool only emits a file and does not publish it.

## What is modeled

* Direct `actions/upload-artifact` v4–v7 and `actions/download-artifact` v4–v8.
* A single workflow/run attempt with otherwise successful jobs and available files.
* Literal matrix axes (up to 256 combinations), include/exclude and nested object
  properties referenced using `matrix.target.os`.
* Literal names, `matrix.*`, `github.job`, and shared symbolic `github.run_id`,
  `github.run_number`, `github.run_attempt`. Symbolic run values remain visibly
  marked as `__ARTIFACTSPAN_...__` in reports, not fabricated actual run IDs.
* Default upload name `artifact`, literal overwrite booleans, transitive `needs`
  and step order **within the same matrix instance**.
* Literal true/false conditions and success(). Other conditions are uncertain;
  possible conditional collisions are unknowns, not definite findings.

Pinned SHAs and custom refs are not guessed. After reviewing an exact action
revision, explicitly assert that it uses v4+ immutable artifact semantics:

```sh
artifactspan workflow.yml --modern-ref actions/upload-artifact@REVIEWED_SHA
```

Repeat the flag for other exact `uses` values. This is your declaration, not
remote verification by ArtifactSpan; it does not broaden supported inputs.
Prefer pinning actions in real CI and recording reviewed refs in the command.
Quote version strings such as `"3.10"`. Floating-point interpolation and integers
outside JavaScript's exact integer range are unknown rather than guessed.

## Honest handling of unknowns

Dynamic matrices/expressions, env/vars/inputs/steps contexts, local composite
actions, reusable workflows, download patterns/all/IDs/other runs, merge actions,
dynamic overwrite and `archive: false` are not resolved. They appear explicitly
as unknowns. Unknown producers prevent a false claim that a download has none.
YAML aliases, duplicate keys and oversized files are rejected.

| Exit | Meaning |
|---|---|
| 0 | No findings or unknowns within the supported model |
| 1 | Findings, with the supported analysis complete |
| 2 | Invalid/unsupported input or at least one unknown; inspect JSON for any known findings too |

Unknowns take precedence over findings in the exit code. This avoids a misleading
green result from a partial analysis. `complete` refers only to this declared
model, not to all possible runtime behavior.

## Boundaries

This is not a GitHub Actions emulator or proof that CI succeeds. It cannot know
whether a build creates files, whether an upload succeeds, backend outages,
artifact expiry, file collisions **inside** merged archives, cancellation, or
artifacts retained from prior run attempts. Third-party actions and shell scripts
may upload artifacts invisibly to this direct-action model. Other workflow
syntax should be checked by actionlint. No automatic fixes are applied.

Limits: 2 MiB YAML, nesting depth 50, 50,000 parser events, 256 jobs, 500 steps per
job, 256 matrix combinations/job, 2,048 expanded artifact steps, 100,000 producer
pairs. Bounds are defensive, not an OS resource sandbox. Matrix names/values can
contain private project details; review reports before sharing.

## Why another tool?

The reviewed actionlint checks validate workflow structure, expressions and
action inputs. Reviewed ghalint/sisakulint rules focus on policy/security and
other semantic checks. We did not find this artifact name/order analysis in
their documented rules. That is a bounded research result, not a claim that no
equivalent software exists anywhere. The useful rules may ultimately fit better
upstream; see [research and alternatives](docs/RESEARCH.ru.md).

## Development

```sh
python -m unittest discover -s tests -v
python -m pip install build
python -m build
```

See [CONTRIBUTING](CONTRIBUTING.md), [SECURITY](SECURITY.md),
[release instructions](docs/RELEASING.md) and [30-day plan](docs/ROADMAP.md).

Artifact inputs follow `actions/core` whitespace trimming and boolean parsing. A statically skipped required job skips ordinary dependent jobs; uncertain dependency conditions remain uncertain. See the [toolkit input implementation](https://github.com/actions/toolkit/blob/main/packages/core/src/core.ts) and [GitHub needs semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idneeds).
