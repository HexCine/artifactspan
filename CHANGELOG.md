# Changelog

## 0.1.2 — 2026-09-22

- Add a responsive, offline EN/RU first-run guide with copyable demo commands.
- Add a Russian quickstart, expected outcomes and troubleshooting links in the README.


## 0.1.1 — 2026-09-22 (first GitHub release)

- Normalize artifact names with the same whitespace set as actions/core; padded producer names now collide and padded downloads resolve.
- Treat empty named downloads as unresolved download-all operations and match toolkit boolean input parsing.
- Propagate skipped and uncertain job dependencies without discarding explicit unknown conditions such as always().
- Emit valid absolute file URIs for Windows/POSIX SARIF locations; report the actual package version.
- Add regression coverage and test built wheels in fresh CI environments.



## 0.1.0 - unreleased



Static artifact inventory, matrix expansion, collision and ordering findings, explicit unknowns, JSON and SARIF reports.
