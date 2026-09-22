# Local release validation

Date: 2026-09-21. This is an unpublished alpha, not a production certification.

| Check | Observed result |
|---|---|
| Windows / Python 3.11.15 | 40 unittest tests passed |
| Windows / Python 3.14.5 | 40 unittest tests passed |
| Fresh Python 3.14 environment, installed wheel | 40 tests passed; import confirmed from site-packages |
| Installed console command, text/JSON/SARIF | collision exits 1, fixed exits 0, unknown exits 2 in all three formats |
| Fixed example | Two producer-consumer edges, no findings/unknowns |
| Missing file and --version | Exit 2 for missing file; version 0.1.0 |
| Package build | sdist built; wheel built from sdist |
| twine check | Wheel and sdist metadata passed |
| Public issue #692 fixture | Five invalid names found; fixture parsed, never executed |
| actionlint 1.7.12 comparison | Both collision and fixed examples exit 0; ArtifactSpan differentiates them |

Unit tests cover matrix products/include/exclude, type distinctions, nested
properties, numeric uncertainty, same-job and transitive ordering, matrix-leg
independence, sequential/concurrent overwrites, reader/writer races, conditional
uncertainty, opaque producers, version declarations, malformed graphs, duplicate
YAML keys, unsafe tags/aliases, dates, source lines and CLI exit behavior.

Machine-readable demo evidence is under examples/reports. The release folder
also contains the clean-install check results. These checks establish local
behavior and packaging, not external adoption or full GitHub runtime equivalence.

Not run: hosted GitHub workflows, Linux/macOS runners, live artifact uploads,
SARIF ingestion by GitHub code scanning, or a large representative workflow
corpus. The CI configuration includes all three OS families with Python 3.11
and 3.14, but its existence is not a claim those jobs have passed.

The clean distribution includes allowlisted source, tests, docs, examples and
CI configuration. It excludes virtual environments, caches, downloaded upstream
binaries, complete third-party workflow fixtures, local paths and research scratch.
Automated token/private-path patterns supplement manual review; no scanner can
prove the absence of all possible sensitive data.
