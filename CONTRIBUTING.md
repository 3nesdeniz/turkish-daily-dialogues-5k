# Contributing

Thank you for helping improve Turkish Daily Dialogues 5K.

## Content changes

Generated files under `data/` and `samples/` must not be edited directly. Correct the source scenario library or rendering logic in `scripts/generate_dataset.py`, regenerate every artifact, and run the full QA suite.

For a language correction, include:

- the affected `conversation_id` or source scenario;
- why the wording is unnatural, ambiguous, unsafe, or incorrectly labelled;
- a suggested Turkish replacement and expected register;
- confirmation that the proposal is original and contains no private or copyrighted conversation text.

Do not submit real chat logs, names, phone numbers, account identifiers, addresses, medical details, or other personal data.

## Development workflow

```bash
python -m pip install --require-hashes -r requirements-dev.lock
make reproduce
make validate
make test
```

Review generated changes rather than assuming successful generation means good language. Read at minimum all changed topic/split and topic/turn-count samples and inspect `reports/QA_REPORT.md`.

## Pull-request expectations

- Keep provenance claims accurate.
- Explain distribution or split changes quantitatively.
- Add or update a focused regression test for generator/validator defects.
- Update `CHANGELOG.md` for user-visible data or schema changes.
- Never weaken a validation threshold solely to make a failing release pass.
