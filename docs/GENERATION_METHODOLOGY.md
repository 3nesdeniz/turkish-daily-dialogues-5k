# Generation methodology

## Objective

Produce exactly 5,000 auditable Turkish daily-life conversations with broad scenario coverage, explicit synthetic provenance, deterministic rebuilds, and split boundaries that do not leak close variants of the same source scenario.

## Source material and provenance

The source scenario library is embedded in `scripts/generate_dataset.py`. It contains 35 topics, each with eight authored four-turn cores and six topic-specific two-turn exchange pairs. The generator derives 30 additional ordered-pair families from those six exchanges, producing exactly 38 scenario families per topic. The library was drafted with AI assistance specifically for this project and reviewed structurally while implementing the generator. No scraped corpus, private conversation log, web page, book, subtitle file, benchmark, or third-party dialogue dataset is an intentional source.

This distinction is encoded in every record:

- `synthetic: true`
- `source.external_sources: false`
- `source.ai_assisted_authoring: true`
- `source.runtime_model_inference: false`

The source disclosure does not claim that model-assisted drafting can guarantee zero incidental phrase overlap with all public language data.

## Deterministic composition

1. The target count (5,000), topic library, generator version, and seed (`20260726`) are constants.
2. Records are distributed across 35 topics as evenly as integer arithmetic allows: 142 or 143 conversations per topic.
3. A record selects one of 38 topic-specific scenario families: one of eight authored cores or one of 30 ordered combinations of two distinct topic exchanges.
4. Authored-core families extend with unused topic exchanges. Ordered-pair families extend first with the self-contained opening exchange of one authored core and, for 8 turns, one unused topic exchange. This prevents the same small addon set from reappearing in a different order without inserting context-dependent second-half replies.
5. Every added exchange is appended as an intact `user` → `assistant` pair; the four-turn base is never interrupted.
6. Formality- and length-specific opening variants, separated for question-led and statement-led dialogues, plus question/statement-compatible discourse markers create limited surface variation without generic padding sentences.
7. Role labels alternate deterministically between `user` and `assistant`.
8. JSONL is written as UTF-8 with one compact JSON object per line. Parquet preserves nested message/source structures and uses Zstandard compression.

Each topic uses one deliberately broad `relationship` descriptor that remains semantically true across every core/addon recombination. This avoids assigning service-worker, peer, or family labels by row rotation when the rendered dialogue does not support that specific role pair.

The generator does not read environment locale, current time, network data, or random operating-system entropy. Split, register, length, and extension choices are arithmetic functions of the fixed dataset seed, topic index, scenario-family index, and rendering index. A stable integer `record_seed` is stored in every row for traceability.

## Split strategy

Splitting happens at the source scenario-family level. For each topic, 30 complete families are assigned to train, 4 to validation, and 4 to test. A deterministic topic-dependent permutation rotates which family indices are held out.

Consequences:

- every topic exists in every split;
- all renderings from one source scenario stay in exactly one split;
- the release ratio is 3,950 train / 525 validation / 525 test;
- validation and test probe unseen scenario intents within known topics rather than minor wording changes from train.

The split is therefore intentionally not row-random. At the family level it is 30/4/4 per topic; at the record level it is 79/10.5/10.5.

## Quality controls

`scripts/validate_dataset.py` performs release-level validation over the checked-in artifacts. Important boundaries include:

- all 5,000 rows are parsed and checked against the complete schema;
- all 12,497,500 conversation pairs are considered by the word-trigram Jaccard audit, with only a mathematically safe length-ratio prune;
- the near-duplicate threshold is 0.80;
- cross-split near-duplicate pairs are counted separately;
- common structured PII forms and a conservative list of operationally unsafe phrases are scanned;
- individual-turn frequency is measured to expose recurring template material;
- JSONL split files and nested Parquet files must reproduce the canonical `all.jsonl` rows;
- one complete sample for every topic × split and topic × turn-count cell is materialized for manual review;
- relationship metadata is constrained to one composition-safe descriptor per topic;
- artifact sizes and SHA-256 digests are verified.

## Regeneration policy

Generated files are derivatives, not editing targets. Make a source-level change and run:

```bash
make reproduce
make validate
make test
```

A content change is release-significant because it can alter row hashes, near-duplicate statistics, samples, and Parquet bytes. Update `CHANGELOG.md` and the version when publishing such a change.

## Human review boundary

Automated checks can catch structural defects, duplication, configured sensitive patterns, and distribution mistakes. They cannot establish cultural representativeness, universal naturalness, or absence of every sensitive inference. Before public publication, a Turkish-speaking maintainer should read both 105-record sample matrices and record corrections as source-library changes.
