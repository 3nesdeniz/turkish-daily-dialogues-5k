#!/usr/bin/env python3
"""Validate release artifacts and write machine- and human-readable QA reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPECTED_RECORDS = 5_000
EXPECTED_SPLITS = {"train": 3_950, "validation": 525, "test": 525}
EXPECTED_TURN_COUNTS = {4, 6, 8}
EXPECTED_ROLES = ("user", "assistant")
NEAR_DUPLICATE_THRESHOLD = 0.80

REQUIRED_FIELDS = {
    "conversation_id",
    "messages",
    "topic",
    "setting",
    "relationship",
    "formality",
    "turn_count",
    "language",
    "synthetic",
    "split",
    "source",
}
REQUIRED_SOURCE_FIELDS = {
    "type",
    "method",
    "generator",
    "generator_version",
    "seed",
    "record_seed",
    "scenario_family",
    "external_sources",
    "ai_assisted_authoring",
    "runtime_model_inference",
}

PII_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "url": re.compile(r"\b(?:https?://|www\.)\S+", re.I),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "turkish_phone": re.compile(r"(?<!\d)(?:\+?90\s*)?0?5\d{2}(?:[ .-]?\d{3}){2}(?!\d)"),
    "turkish_id": re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)"),
    "payment_card": re.compile(r"(?<!\d)(?:\d[ -]?){15,18}\d(?!\d)"),
}

# Conservative phrase scan: the dataset is not intended to contain operational
# harm, abuse, explicit sexual material, hate, or self-harm instructions.
UNSAFE_PATTERNS = {
    "weapon_instructions": re.compile(r"\b(?:silah yap|bomba yap|patlayıcı hazırla)", re.I),
    "malware_instructions": re.compile(r"\b(?:zararlı yazılım yaz|fidye yazılımı|şifre çal|hesap ele geçir)", re.I),
    "self_harm": re.compile(r"\b(?:intihar et|kendine zarar ver)", re.I),
    "explicit_sexual": re.compile(r"\b(?:pornografik|cinsel saldırı)", re.I),
    "targeted_hate": re.compile(r"\b(?:ırkı yok et|dini yok et)", re.I),
}


class ValidationError(RuntimeError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValidationError(f"blank JSONL line: {path}:{line_number}")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid JSON: {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValidationError(f"record is not an object: {path}:{line_number}")
            records.append(value)
    return records


def all_text(record: dict[str, Any]) -> str:
    return " ".join(message["content"] for message in record["messages"])


def normalize_text(text: str) -> str:
    # Unicode casefold expands Turkish capital İ to ``i`` + combining dot.
    # Removing only that combining dot keeps tokenization linguistically stable
    # without stripping other Turkish characters.
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("\u0307", "")
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def word_trigrams(text: str) -> set[tuple[str, str, str]]:
    tokens = normalize_text(text).split()
    if len(tokens) < 3:
        padded = (tokens + [""] * 3)[:3]
        return {tuple(padded)}  # type: ignore[arg-type]
    return set(zip(tokens, tokens[1:], tokens[2:], strict=False))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_schema(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    ids: set[str] = set()
    source_seeds: set[int] = set()
    for index, record in enumerate(records):
        location = record.get("conversation_id", f"row[{index}]")
        missing = REQUIRED_FIELDS - record.keys()
        extra = record.keys() - REQUIRED_FIELDS
        if missing:
            errors.append(f"{location}: missing fields {sorted(missing)}")
        if extra:
            errors.append(f"{location}: unexpected fields {sorted(extra)}")
        if errors and (missing or extra):
            continue

        conversation_id = record["conversation_id"]
        if not isinstance(conversation_id, str) or not re.fullmatch(r"trdd5k-[a-z0-9-]+-\d{3}", conversation_id):
            errors.append(f"{location}: invalid conversation_id")
        if conversation_id in ids:
            errors.append(f"{location}: duplicate conversation_id")
        ids.add(conversation_id)

        messages = record["messages"]
        if not isinstance(messages, list) or len(messages) not in EXPECTED_TURN_COUNTS:
            errors.append(f"{location}: messages must contain 4, 6, or 8 turns")
            continue
        if record["turn_count"] != len(messages):
            errors.append(f"{location}: turn_count mismatch")
        for turn_index, message in enumerate(messages):
            if not isinstance(message, dict) or set(message) != {"role", "content"}:
                errors.append(f"{location}: invalid message object at turn {turn_index}")
                continue
            if message["role"] != EXPECTED_ROLES[turn_index % 2]:
                errors.append(f"{location}: role sequence error at turn {turn_index}")
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                errors.append(f"{location}: blank content at turn {turn_index}")
            elif content != content.strip() or "  " in content or len(content) > 600:
                errors.append(f"{location}: malformed whitespace/length at turn {turn_index}")
            elif content[-1] not in ".?!":
                errors.append(f"{location}: missing terminal punctuation at turn {turn_index}")
            elif unicodedata.normalize("NFC", content) != content:
                errors.append(f"{location}: non-NFC content at turn {turn_index}")

        for field in ("topic", "setting", "relationship", "formality"):
            if not isinstance(record[field], str) or not record[field].strip():
                errors.append(f"{location}: invalid {field}")
        if record["formality"] not in {"informal", "polite", "formal"}:
            errors.append(f"{location}: invalid formality")
        if record["language"] != "tr" or record["synthetic"] is not True:
            errors.append(f"{location}: language/synthetic invariant failed")
        if record["split"] not in EXPECTED_SPLITS:
            errors.append(f"{location}: invalid split")

        source = record["source"]
        if not isinstance(source, dict) or set(source) != REQUIRED_SOURCE_FIELDS:
            errors.append(f"{location}: invalid source metadata fields")
        else:
            if source["type"] != "synthetic" or source["external_sources"] is not False:
                errors.append(f"{location}: incorrect provenance flags")
            if source["ai_assisted_authoring"] is not True:
                errors.append(f"{location}: ai_assisted_authoring must be true")
            if source["runtime_model_inference"] is not False:
                errors.append(f"{location}: runtime_model_inference must be false")
            record_seed = source["record_seed"]
            if not isinstance(record_seed, int) or record_seed in source_seeds:
                errors.append(f"{location}: invalid or duplicate record_seed")
            source_seeds.add(record_seed)
            if not isinstance(source["scenario_family"], int) or not 0 <= source["scenario_family"] < 38:
                errors.append(f"{location}: invalid scenario_family")

    if errors:
        preview = "\n".join(errors[:25])
        raise ValidationError(f"schema validation failed with {len(errors)} error(s):\n{preview}")
    return {"valid_records": len(records), "unique_ids": len(ids), "unique_record_seeds": len(source_seeds)}


def validate_distributions(records: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(record["split"] for record in records)
    if dict(split_counts) != EXPECTED_SPLITS:
        raise ValidationError(f"split counts differ: {dict(split_counts)} != {EXPECTED_SPLITS}")
    topic_counts = Counter(record["topic"] for record in records)
    if len(topic_counts) != 35 or max(topic_counts.values()) - min(topic_counts.values()) > 1:
        raise ValidationError(f"topic coverage is not balanced: {dict(topic_counts)}")
    topic_split = Counter((record["topic"], record["split"]) for record in records)
    missing_topic_splits = [
        (topic, split) for topic in topic_counts for split in EXPECTED_SPLITS if topic_split[(topic, split)] == 0
    ]
    if missing_topic_splits:
        raise ValidationError(f"topics missing splits: {missing_topic_splits}")

    family_splits: dict[tuple[str, int], set[str]] = defaultdict(set)
    for record in records:
        family_splits[(record["topic"], record["source"]["scenario_family"])].add(record["split"])
    if len(family_splits) != 35 * 38 or any(len(splits) != 1 for splits in family_splits.values()):
        raise ValidationError("scenario-family split isolation failed")
    families_by_topic_split = Counter((topic, next(iter(splits))) for (topic, _), splits in family_splits.items())
    if any(
        families_by_topic_split[(topic, split)] != expected
        for topic in topic_counts
        for split, expected in {"train": 30, "validation": 4, "test": 4}.items()
    ):
        raise ValidationError("per-topic 30/4/4 scenario-family allocation failed")

    turn_counts = Counter(record["turn_count"] for record in records)
    formality_counts = Counter(record["formality"] for record in records)
    relationship_counts = Counter(record["relationship"] for record in records)
    return {
        "split": dict(sorted(split_counts.items())),
        "topic_count": len(topic_counts),
        "topic_min": min(topic_counts.values()),
        "topic_max": max(topic_counts.values()),
        "topic_split_cells": len(topic_split),
        "scenario_family_cells": len(family_splits),
        "scenario_families_per_topic_split": {"train": 30, "validation": 4, "test": 4},
        "turn_count": {str(k): v for k, v in sorted(turn_counts.items())},
        "formality": dict(sorted(formality_counts.items())),
        "relationship_count": len(relationship_counts),
    }


def validate_duplicates(records: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [normalize_text(all_text(record)) for record in records]
    exact_counts = Counter(normalized)
    exact_duplicate_groups = sum(1 for count in exact_counts.values() if count > 1)
    if exact_duplicate_groups:
        raise ValidationError(f"found {exact_duplicate_groups} normalized exact duplicate group(s)")

    shingles = [word_trigrams(all_text(record)) for record in records]
    near_pairs = 0
    cross_split_near_pairs = 0
    maximum_similarity = 0.0
    maximum_pair: tuple[str, str] | None = None
    maximum_cross_split_similarity = 0.0
    maximum_cross_split_pair: tuple[str, str] | None = None

    # Exhaustive 12,497,500-pair comparison.  A size-ratio bound safely skips
    # pairs that cannot reach the configured Jaccard threshold.
    for left_index, left in enumerate(shingles):
        for right_index in range(left_index):
            right = shingles[right_index]
            if min(len(left), len(right)) / max(len(left), len(right)) < NEAR_DUPLICATE_THRESHOLD:
                continue
            intersection = len(left & right)
            similarity = intersection / (len(left) + len(right) - intersection)
            if similarity > maximum_similarity:
                maximum_similarity = similarity
                maximum_pair = (
                    records[left_index]["conversation_id"],
                    records[right_index]["conversation_id"],
                )
            if (
                records[left_index]["split"] != records[right_index]["split"]
                and similarity > maximum_cross_split_similarity
            ):
                maximum_cross_split_similarity = similarity
                maximum_cross_split_pair = (
                    records[left_index]["conversation_id"],
                    records[right_index]["conversation_id"],
                )
            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                near_pairs += 1
                if records[left_index]["split"] != records[right_index]["split"]:
                    cross_split_near_pairs += 1

    if near_pairs:
        raise ValidationError(f"found {near_pairs} near-duplicate pair(s) at threshold {NEAR_DUPLICATE_THRESHOLD}")
    return {
        "normalized_exact_duplicate_groups": exact_duplicate_groups,
        "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
        "candidate_method": "exhaustive word-trigram Jaccard with safe size-ratio pruning",
        "pairs_in_scope": len(records) * (len(records) - 1) // 2,
        "near_duplicate_pairs": near_pairs,
        "cross_split_near_duplicate_pairs": cross_split_near_pairs,
        "maximum_similarity": round(maximum_similarity, 6),
        "maximum_pair": maximum_pair,
        "maximum_cross_split_similarity": round(maximum_cross_split_similarity, 6),
        "maximum_cross_split_pair": maximum_cross_split_pair,
    }


def validate_content(records: list[dict[str, Any]]) -> dict[str, Any]:
    pii_hits: list[dict[str, str]] = []
    unsafe_hits: list[dict[str, str]] = []
    unresolved_placeholders: list[str] = []
    individual_turns: Counter[str] = Counter()
    for record in records:
        for message in record["messages"]:
            text = message["content"]
            individual_turns[normalize_text(text)] += 1
            if re.search(r"\{[^{}]+\}|\[[A-Z_]{2,}\]|<[^>]+>", text):
                unresolved_placeholders.append(record["conversation_id"])
            for category, pattern in PII_PATTERNS.items():
                if pattern.search(text):
                    pii_hits.append({"conversation_id": record["conversation_id"], "category": category})
            for category, pattern in UNSAFE_PATTERNS.items():
                if pattern.search(text):
                    unsafe_hits.append({"conversation_id": record["conversation_id"], "category": category})

    if pii_hits or unsafe_hits or unresolved_placeholders:
        raise ValidationError(
            "content safety validation failed: "
            f"pii={pii_hits[:5]}, unsafe={unsafe_hits[:5]}, placeholders={unresolved_placeholders[:5]}"
        )
    total_turns = sum(individual_turns.values())
    repeated_text, repeated_count = individual_turns.most_common(1)[0]
    return {
        "pii_pattern_hits": len(pii_hits),
        "unsafe_phrase_hits": len(unsafe_hits),
        "unresolved_template_markers": len(unresolved_placeholders),
        "total_turns": total_turns,
        "unique_normalized_turns": len(individual_turns),
        "most_repeated_turn_count": repeated_count,
        "most_repeated_turn_share": round(repeated_count / total_turns, 6),
        "most_repeated_turn_preview": repeated_text[:120],
    }


def validate_split_files(root: Path, all_records: list[dict[str, Any]]) -> dict[str, Any]:
    all_by_id = {record["conversation_id"]: record for record in all_records}
    seen: set[str] = set()
    details: dict[str, Any] = {}
    for split, expected_count in EXPECTED_SPLITS.items():
        records = read_jsonl(root / "data" / f"{split}.jsonl")
        if len(records) != expected_count:
            raise ValidationError(f"{split}.jsonl has {len(records)} rows, expected {expected_count}")
        ids = {record["conversation_id"] for record in records}
        if len(ids) != len(records) or seen & ids:
            raise ValidationError(f"duplicate ID within/across split file: {split}")
        for record in records:
            if record["split"] != split or all_by_id.get(record["conversation_id"]) != record:
                raise ValidationError(f"split file parity mismatch: {record['conversation_id']}")
        seen |= ids
        details[split] = len(records)
    if seen != set(all_by_id):
        raise ValidationError("split files do not partition all.jsonl")
    return details


def validate_samples(root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    samples = read_jsonl(root / "samples" / "topic-split-samples.jsonl")
    expected_pairs = {(record["topic"], split) for record in records for split in EXPECTED_SPLITS}
    sample_pairs = [(record["topic"], record["split"]) for record in samples]
    if len(sample_pairs) != len(set(sample_pairs)) or set(sample_pairs) != expected_pairs:
        raise ValidationError("sample file must contain exactly one record for every topic/split pair")
    ids = {record["conversation_id"] for record in records}
    if any(sample["conversation_id"] not in ids for sample in samples):
        raise ValidationError("sample not found in all.jsonl")

    turn_samples = read_jsonl(root / "samples" / "topic-turn-samples.jsonl")
    expected_turn_pairs = {(record["topic"], turn_count) for record in records for turn_count in EXPECTED_TURN_COUNTS}
    turn_pairs = [(record["topic"], record["turn_count"]) for record in turn_samples]
    if len(turn_pairs) != len(set(turn_pairs)) or set(turn_pairs) != expected_turn_pairs:
        raise ValidationError("turn sample file must contain exactly one record for every topic/turn-count pair")
    if any(sample["conversation_id"] not in ids for sample in turn_samples):
        raise ValidationError("turn sample not found in all.jsonl")
    return {
        "topic_split_sample_records": len(samples),
        "topic_split_pairs": len(sample_pairs),
        "topic_turn_sample_records": len(turn_samples),
        "topic_turn_pairs": len(turn_pairs),
    }


def validate_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["record_count"] != EXPECTED_RECORDS or manifest["topic_count"] != 35:
        raise ValidationError("manifest headline counts are incorrect")
    for artifact in manifest["artifacts"]:
        path = root / artifact["path"]
        if not path.is_file():
            raise ValidationError(f"manifest artifact missing: {artifact['path']}")
        if path.stat().st_size != artifact["bytes"] or sha256(path) != artifact["sha256"]:
            raise ValidationError(f"manifest digest/size mismatch: {artifact['path']}")

    checksum_entries: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        checksum_entries[relative] = digest
    expected_paths = {artifact["path"] for artifact in manifest["artifacts"]} | {"MANIFEST.json"}
    if set(checksum_entries) != expected_paths:
        raise ValidationError("SHA256SUMS path set differs from manifest artifacts")
    for relative, digest in checksum_entries.items():
        if sha256(root / relative) != digest:
            raise ValidationError(f"SHA256SUMS mismatch: {relative}")
    return {"artifact_count": len(manifest["artifacts"]), "checksums_verified": len(checksum_entries)}


def validate_parquet(root: Path, all_records: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return {"status": "not_checked", "reason": "pyarrow is not installed"}

    all_by_id = {record["conversation_id"]: record for record in all_records}
    checked = 0
    for split, expected_count in EXPECTED_SPLITS.items():
        path = root / "data" / f"{split}.parquet"
        if not path.exists():
            raise ValidationError(f"missing Parquet artifact: {path.name}")
        table = pq.read_table(path)
        rows = table.to_pylist()
        if len(rows) != expected_count:
            raise ValidationError(f"Parquet row count mismatch: {path.name}")
        for row in rows:
            if row != all_by_id[row["conversation_id"]]:
                raise ValidationError(f"Parquet/JSONL parity mismatch: {row['conversation_id']}")
        checked += len(rows)
    return {"status": "passed", "files": 3, "rows_checked": checked, "nested_messages_preserved": True}


def write_reports(root: Path, report: dict[str, Any]) -> None:
    reports_dir = root / "reports"
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    d = report["distributions"]
    dup = report["duplicates"]
    content = report["content"]
    parquet = report["parquet"]
    split_ratio = "/".join(
        f"{100 * d['split'][split] / EXPECTED_RECORDS:g}" for split in ("train", "validation", "test")
    )
    rows = [
        "# QA Report",
        "",
        "## Release decision",
        "",
        "**PASS for conversational modelling, dialogue augmentation, and Turkish-language research.**",
        "",
        "The release is synthetic and does not establish how real people speak in every region, age group, or social context. It must not be treated as a population survey, clinical corpus, identity benchmark, or sole production evaluation set.",
        "",
        "## Validation evidence",
        "",
        f"- Records parsed and schema-valid: **{report['schema']['valid_records']:,} / {EXPECTED_RECORDS:,}**",
        f"- Topics: **{d['topic_count']}**, with **{d['topic_min']}–{d['topic_max']}** conversations each",
        f"- Split counts: train **{d['split']['train']:,}**, validation **{d['split']['validation']:,}**, test **{d['split']['test']:,}**",
        f"- Topic/split coverage cells: **{d['topic_split_cells']} / 105**",
        f"- Turn counts: 4 = **{d['turn_count']['4']:,}**, 6 = **{d['turn_count']['6']:,}**, 8 = **{d['turn_count']['8']:,}**",
        f"- Normalized exact duplicate groups: **{dup['normalized_exact_duplicate_groups']}**",
        f"- Near-duplicate pairs at word-trigram Jaccard ≥ {dup['near_duplicate_threshold']:.2f}: **{dup['near_duplicate_pairs']}**",
        f"- Exhaustive conversation pairs audited: **{dup['pairs_in_scope']:,}**",
        f"- Maximum observed similarity: **{dup['maximum_similarity']:.6f}** ({' ↔ '.join(dup['maximum_pair'])})",
        f"- Cross-split near-duplicate pairs: **{dup['cross_split_near_duplicate_pairs']}**",
        f"- Maximum cross-split similarity: **{dup['maximum_cross_split_similarity']:.6f}** ({' ↔ '.join(dup['maximum_cross_split_pair'])})",
        f"- PII-pattern hits: **{content['pii_pattern_hits']}**",
        f"- Unsafe-instruction phrase hits: **{content['unsafe_phrase_hits']}**",
        f"- Unresolved template markers: **{content['unresolved_template_markers']}**",
        f"- Total turns: **{content['total_turns']:,}**; unique normalized turns: **{content['unique_normalized_turns']:,}**",
        f"- Most repeated individual turn: **{content['most_repeated_turn_count']}** uses ({content['most_repeated_turn_share']:.3%} of turns)",
        f"- Topic/split samples: **{report['samples']['topic_split_sample_records']} / 105**",
        f"- Topic/turn-count samples: **{report['samples']['topic_turn_sample_records']} / 105**",
        f"- Manifest artifacts verified: **{report['manifest']['artifact_count']}**; checksums verified: **{report['manifest']['checksums_verified']}**",
        f"- Parquet parity: **{parquet['status']}**"
        + (
            f" ({parquet.get('rows_checked', 0):,} rows)"
            if parquet["status"] == "passed"
            else f" ({parquet['reason']})"
        ),
        "",
        "## Split-leakage design",
        "",
        "All renderings of a source scenario family stay in exactly one split. Validation and test therefore hold out complete intent-level scenario families within every topic instead of distributing close surface variants across splits. "
        f"The resulting record ratio is {split_ratio}, with every one of the 35 topics represented in every split.",
        "",
        "## Manual sampling protocol",
        "",
        "`samples/topic-split-samples.jsonl` contains one deterministic full conversation for every topic × split pair. `samples/topic-turn-samples.jsonl` separately covers every topic × turn-count pair. Reviewers should read both matrices before a release and record language issues as generator-source fixes, then regenerate the corpus rather than editing generated data by hand.",
        "",
        "## Known limitations",
        "",
        "- The source scenario library was drafted with AI assistance and encoded in the repository. Deterministic composition improves auditability but still creates detectable recurring discourse structures.",
        "- No external corpus was intentionally used, but model-assisted drafting cannot prove the absence of incidental phrase overlap with public language data.",
        "- Register labels are topic-level approximations; politeness varies within natural Turkish dialogue. Relationship descriptors are intentionally broad so they remain true across composable scenario families.",
        "- The corpus intentionally excludes real personal data, regional identity attributes, profanity, and high-risk operational content, so it underrepresents those real-world phenomena.",
        "- The safety and PII scans are pattern-based. Zero hits are evidence about the configured patterns, not proof that every possible sensitive inference is absent.",
        "- No human-subject study or demographic representativeness claim is made.",
        "",
        "## Reproduction",
        "",
        "Run `make reproduce` and then `make validate`. Generation is offline and deterministic with seed `20260726`; release files must match `SHA256SUMS`.",
        "",
    ]
    (reports_dir / "QA_REPORT.md").write_text("\n".join(rows), encoding="utf-8")


def validate(root: Path, write_report: bool = True) -> dict[str, Any]:
    records = read_jsonl(root / "data" / "all.jsonl")
    if len(records) != EXPECTED_RECORDS:
        raise ValidationError(f"expected {EXPECTED_RECORDS} rows, found {len(records)}")
    report = {
        "status": "PASS",
        "dataset": "turkish-daily-dialogues-5k",
        "version": "1.0.0",
        "schema": validate_schema(records),
        "distributions": validate_distributions(records),
        "split_files": validate_split_files(root, records),
        "duplicates": validate_duplicates(records),
        "content": validate_content(records),
        "samples": validate_samples(root, records),
        "manifest": validate_manifest(root),
        "parquet": validate_parquet(root, records),
    }
    if write_report:
        write_reports(root, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = validate(args.root.resolve(), write_report=not args.no_write_report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
