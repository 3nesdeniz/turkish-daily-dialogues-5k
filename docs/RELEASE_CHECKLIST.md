# Release checklist

- [x] Source scenario changes are intentional and reviewed in Turkish.
- [x] All 105 topic × split samples have been read end to end.
- [x] All 105 topic × turn-count samples have been read end to end.
- [x] Each topic-level `relationship` descriptor remains true for every core/addon combination.
- [x] `make reproduce` succeeds in a clean environment.
- [x] `make validate` reports `PASS` and verifies Parquet parity.
- [x] `make test` passes.
- [x] `shasum -a 256 -c SHA256SUMS` passes.
- [x] `MANIFEST.json`, `reports/validation.json`, and `reports/QA_REPORT.md` match the release.
- [x] README counts, limitations, version, and provenance remain accurate.
- [x] `CHANGELOG.md` includes the release.
- [x] `CITATION.cff` and license metadata are valid.
- [x] No repository, Hugging Face, DOI, download, or human-review claim is made before it is true.
- [ ] The Hugging Face Viewer renders all three configured Parquet splits after publication.
