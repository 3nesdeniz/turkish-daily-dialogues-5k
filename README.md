---
pretty_name: Turkish Daily Dialogues 5K
language:
  - tr
license: cc-by-4.0
size_categories:
  - 1K<n<10K
task_categories:
  - text-generation
tags:
  - conversational
  - dialogue
  - turkish
  - synthetic
  - multi-turn
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train.parquet
      - split: validation
        path: data/validation.parquet
      - split: test
        path: data/test.parquet
---

# Turkish Daily Dialogues 5K

[![Validate dataset](https://github.com/3nesdeniz/turkish-daily-dialogues-5k/actions/workflows/validate.yml/badge.svg)](https://github.com/3nesdeniz/turkish-daily-dialogues-5k/actions/workflows/validate.yml)
[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-dataset-FFD21E)](https://huggingface.co/datasets/3nesdeniz/turkish-daily-dialogues-5k)
[![License: CC BY 4.0](https://img.shields.io/badge/license-CC%20BY%204.0-blue)](LICENSE)

Exactly 5,000 synthetic, multi-turn Turkish conversations covering ordinary daily-life situations. The corpus is designed as a small, auditable baseline for dialogue modelling, instruction-format experiments, augmentation research, and Turkish-language evaluation—not as a substitute for conversations written by real people.

> **Provenance in one sentence:** the Turkish source scenario library was drafted with AI assistance specifically for this project, then expanded by a deterministic offline generator; no scraped dialogue corpus, personal conversation, external text collection, runtime model call, or real personal information is used intentionally.

## Türkçe özet

Bu veri seti; market alışverişi, ulaşım, aile planları, iş günü, sağlık randevusu organizasyonu, kargo, teknoloji desteği ve benzeri 35 günlük yaşam başlığında tam 5.000 sentetik Türkçe konuşma içerir. Her kayıt 4, 6 veya 8 dönüşlüdür. Kaynak senaryo kütüphanesi yapay zekâ desteğiyle bu proje için hazırlanmış, veri dosyaları ise ağ bağlantısı ya da model çağrısı yapmayan deterministik bir betikle üretilmiştir. Veri seti gerçek kişilerin konuşmalarını veya kişisel bilgilerini içerme amacı taşımaz.

## Dataset snapshot

| Property | Value |
|---|---:|
| Conversations | 5,000 |
| Topics | 35 |
| Train | 3,950 |
| Validation | 525 |
| Test | 525 |
| Turns | 4 / 6 / 8 |
| Language | Turkish (`tr`) |
| Provenance | Synthetic, AI-assisted source authoring |
| Runtime generation | Deterministic, offline, no model inference |
| Real PII intentionally included | None |
| License | CC BY 4.0 |

The split is deliberately **scenario-family grouped** rather than row-random. Each topic has 38 families: 30 assigned to train, 4 to validation, and 4 to test. All renderings derived from the same family stay in one split, while every topic appears in all three splits. The resulting record ratio is 79/10.5/10.5.

## Intended uses

- Turkish conversational-format prototyping and supervised fine-tuning experiments
- Dialogue augmentation and data-pipeline tests
- Turn-taking, formatting, and metadata experiments
- Small-scale language-quality or robustness baselines
- Educational examples for deterministic synthetic-data engineering

### Out-of-scope uses

- Demographic, dialect, cultural, or population-level conclusions
- Clinical, legal, financial, emergency, or other high-stakes decisions
- Identity inference, profiling, surveillance, or evaluation of protected groups
- Claiming the data reflects authentic private conversations
- Using this dataset alone as proof that a production assistant is safe or fluent

## Data structure

Each JSONL row and Parquet record has the following shape:

```json
{
  "conversation_id": "trdd5k-market-alisverisi-001",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "topic": "Market alışverişi",
  "setting": "mahalle marketi",
  "relationship": "müşteri-market çalışanı",
  "formality": "polite",
  "turn_count": 4,
  "language": "tr",
  "synthetic": true,
  "split": "train",
  "source": {
    "type": "synthetic",
    "method": "ai-assisted-scenario-library-deterministic-composition",
    "generator": "scripts/generate_dataset.py",
    "generator_version": "1.0.0",
    "seed": 20260726,
    "record_seed": 20260726,
    "scenario_family": 0,
    "external_sources": false,
    "ai_assisted_authoring": true,
    "runtime_model_inference": false
  }
}
```

`user` and `assistant` are compatibility labels for alternating speakers. They do not mean every dialogue depicts a human talking to an AI assistant, and they do not encode preference or correctness labels.

See [docs/SCHEMA.md](docs/SCHEMA.md) for constraints. The sample files cover every topic × split and every topic × turn-count cell.

## Load with 🤗 Datasets

From the Hugging Face Hub:

```python
from datasets import load_dataset

dataset = load_dataset("3nesdeniz/turkish-daily-dialogues-5k")
print(dataset)
print(dataset["train"][0]["messages"])
```

From a local checkout without relying on Hub metadata:

```python
from datasets import load_dataset

dataset = load_dataset(
    "parquet",
    data_files={
        "train": "data/train.parquet",
        "validation": "data/validation.parquet",
        "test": "data/test.parquet",
    },
)
```

JSONL files are also supplied for transparent inspection and language-agnostic tooling.

## Generation and reproducibility

The repository is the source of truth. Do not edit generated rows manually.

```bash
python -m pip install --require-hashes -r requirements-dev.lock
make reproduce
make lint
make format-check
make validate
make test
shasum -a 256 -c SHA256SUMS
```

- Fixed seed: `20260726`
- Generator version: `1.0.0`
- Network required during generation: no
- Runtime model inference: no
- Locale or runtime-clock dependency: no
- JSON serialization: UTF-8, newline-delimited, stable field insertion order
- Python formatter/linter: Ruff `0.16.0` (version enforced in `pyproject.toml`)

The source dialogues, composition rules, split logic, and Parquet schema live in [scripts/generate_dataset.py](scripts/generate_dataset.py). The full methodology is documented in [docs/GENERATION_METHODOLOGY.md](docs/GENERATION_METHODOLOGY.md).

## Quality assurance

The release validator checks:

- exact record count, schema, types, roles, turn counts, NFC text, and punctuation;
- unique IDs and record seeds;
- all 35 topics in every split;
- JSONL split partition parity and nested Parquet parity;
- normalized exact duplicates and exhaustive word-trigram near-duplicate comparisons;
- cross-split leakage at the configured similarity threshold;
- unresolved template markers and repeated-turn concentration;
- common email, URL, IP, phone, Turkish ID, and payment-card patterns;
- conservative unsafe-instruction phrase patterns;
- manifest sizes/digests and `SHA256SUMS`;
- one deterministic sample for each topic × split and topic × turn-count cell.

The current evidence and known limitations are in [reports/QA_REPORT.md](reports/QA_REPORT.md); machine-readable results are in [reports/validation.json](reports/validation.json). Pattern scans are not proof that every conceivable sensitive inference is absent.

## Ethical and provenance notes

- The text was created for this dataset; no external dialogue source is intentionally copied or scraped.
- AI assistance was used when drafting the checked-in Turkish scenario library. This fact is recorded in every row.
- Deterministic expansion does not call an AI model and can be reproduced offline.
- No real names, emails, phone numbers, addresses, account identifiers, or private conversations are intentionally included.
- Model-assisted drafting cannot prove zero incidental phrase overlap with public language data; users should not describe the corpus as human-authored.
- Logistic health conversations explicitly defer medical judgment to qualified professionals.
- Security-conscious everyday lines are defensive and do not provide operational abuse instructions.

## Limitations

- Synthetic dialogue is smoother and more cooperative than many real conversations.
- Recurring discourse structures remain detectable even though full-dialogue near duplicates are screened.
- Regional varieties, code-switching, speech disfluencies, slang, profanity, accessibility needs, and age-related language are underrepresented.
- `formality` and `relationship` are broad topic metadata, not independently human-annotated labels; relationship descriptors are intentionally composition-safe rather than fine-grained role annotations.
- The dataset has not undergone a representative human-subject evaluation.
- The current release should be treated as a transparent synthetic baseline, not a universal Turkish dialogue benchmark.

## Maintenance and contributions

Please read [CONTRIBUTING.md](CONTRIBUTING.md). Language fixes belong in the source scenario library, followed by full regeneration and QA. Do not patch only `data/*.jsonl` or `data/*.parquet`.

Potential privacy, provenance, or harmful-content problems can be reported through the repository’s issue tracker. Include only the `conversation_id`; do not post sensitive personal material.

## License and citation

The dataset, documentation, and generation material are released under [CC BY 4.0](LICENSE). Attribution should include the dataset title, version, author, and repository or Hub URL once published.

```bibtex
@dataset{deniz_2026_turkish_daily_dialogues_5k,
  author  = {Deniz, Enes},
  title   = {Turkish Daily Dialogues 5K},
  year    = {2026},
  version = {1.0.0},
  note    = {Synthetic Turkish multi-turn dialogue dataset},
  url     = {https://huggingface.co/datasets/3nesdeniz/turkish-daily-dialogues-5k}
}
```

See [CITATION.cff](CITATION.cff) for citation-manager metadata.
