# QA Report

## Release decision

**PASS for conversational modelling, dialogue augmentation, and Turkish-language research.**

The release is synthetic and does not establish how real people speak in every region, age group, or social context. It must not be treated as a population survey, clinical corpus, identity benchmark, or sole production evaluation set.

## Validation evidence

- Records parsed and schema-valid: **5,000 / 5,000**
- Topics: **35**, with **142–143** conversations each
- Split counts: train **3,950**, validation **525**, test **525**
- Topic/split coverage cells: **105 / 105**
- Turn counts: 4 = **1,000**, 6 = **2,000**, 8 = **2,000**
- Normalized exact duplicate groups: **0**
- Near-duplicate pairs at word-trigram Jaccard ≥ 0.80: **0**
- Exhaustive conversation pairs audited: **12,497,500**
- Maximum observed similarity: **0.736842** (trdd5k-toplu-tasima-114 ↔ trdd5k-toplu-tasima-098)
- Cross-split near-duplicate pairs: **0**
- Maximum cross-split similarity: **0.724138** (trdd5k-tamir-ve-servis-130 ↔ trdd5k-tamir-ve-servis-025)
- PII-pattern hits: **0**
- Unsafe-instruction phrase hits: **0**
- Unresolved template markers: **0**
- Total turns: **32,000**; unique normalized turns: **5,291**
- Most repeated individual turn: **57** uses (0.178% of turns)
- Topic/split samples: **105 / 105**
- Topic/turn-count samples: **105 / 105**
- Manifest artifacts verified: **9**; checksums verified: **10**
- Parquet parity: **passed** (5,000 rows)

## Split-leakage design

All renderings of a source scenario family stay in exactly one split. Validation and test therefore hold out complete intent-level scenario families within every topic instead of distributing close surface variants across splits. The resulting record ratio is 79/10.5/10.5, with every one of the 35 topics represented in every split.

## Manual sampling protocol

`samples/topic-split-samples.jsonl` contains one deterministic full conversation for every topic × split pair. `samples/topic-turn-samples.jsonl` separately covers every topic × turn-count pair. Reviewers should read both matrices before a release and record language issues as generator-source fixes, then regenerate the corpus rather than editing generated data by hand.

## Known limitations

- The source scenario library was drafted with AI assistance and encoded in the repository. Deterministic composition improves auditability but still creates detectable recurring discourse structures.
- No external corpus was intentionally used, but model-assisted drafting cannot prove the absence of incidental phrase overlap with public language data.
- Register labels are topic-level approximations; politeness varies within natural Turkish dialogue. Relationship descriptors are intentionally broad so they remain true across composable scenario families.
- The corpus intentionally excludes real personal data, regional identity attributes, profanity, and high-risk operational content, so it underrepresents those real-world phenomena.
- The safety and PII scans are pattern-based. Zero hits are evidence about the configured patterns, not proof that every possible sensitive inference is absent.
- No human-subject study or demographic representativeness claim is made.

## Reproduction

Run `make reproduce` and then `make validate`. Generation is offline and deterministic with seed `20260726`; release files must match `SHA256SUMS`.
