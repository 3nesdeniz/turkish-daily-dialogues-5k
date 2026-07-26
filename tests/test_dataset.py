from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from scripts.generate_dataset import (
    SCENARIO_FAMILIES_PER_TOPIC,
    TEST_FAMILIES_PER_TOPIC,
    TOPICS,
    TRAIN_FAMILIES_PER_TOPIC,
    VALIDATION_FAMILIES_PER_TOPIC,
    attach,
    build,
    generate_records,
    records_for_topic,
    render_dialogue,
    scenario_family_count,
    scenario_family_index,
    select_split,
)
from scripts.validate_dataset import EXPECTED_SPLITS, normalize_text, validate

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = generate_records()

    def test_exact_count_and_balanced_topic_coverage(self) -> None:
        self.assertEqual(len(self.records), 5_000)
        topic_counts = Counter(row["topic"] for row in self.records)
        self.assertEqual(len(topic_counts), 35)
        self.assertLessEqual(max(topic_counts.values()) - min(topic_counts.values()), 1)

    def test_split_counts_and_topic_coverage(self) -> None:
        self.assertEqual(Counter(row["split"] for row in self.records), Counter(EXPECTED_SPLITS))
        topic_splits = {(row["topic"], row["split"]) for row in self.records}
        self.assertEqual(len(topic_splits), 35 * 3)

    def test_scenario_families_do_not_cross_splits(self) -> None:
        family_splits: dict[tuple[str, int], set[str]] = defaultdict(set)
        for topic_index, spec in enumerate(TOPICS):
            for row_index in range(records_for_topic(topic_index)):
                row = self.records[sum(records_for_topic(i) for i in range(topic_index)) + row_index]
                family = scenario_family_index(spec, row_index)
                self.assertEqual(row["source"]["scenario_family"], family)
                family_splits[(row["topic"], family)].add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in family_splits.values()))

    def test_scenario_family_allocation_contract(self) -> None:
        expected = Counter(
            {
                "train": TRAIN_FAMILIES_PER_TOPIC,
                "validation": VALIDATION_FAMILIES_PER_TOPIC,
                "test": TEST_FAMILIES_PER_TOPIC,
            }
        )
        for topic_index, spec in enumerate(TOPICS):
            self.assertEqual(scenario_family_count(spec), SCENARIO_FAMILIES_PER_TOPIC)
            actual = Counter(select_split(topic_index, family) for family in range(SCENARIO_FAMILIES_PER_TOPIC))
            self.assertEqual(actual, expected, spec.slug)

    def test_schema_invariants(self) -> None:
        ids = set()
        seeds = set()
        for row in self.records:
            ids.add(row["conversation_id"])
            seeds.add(row["source"]["record_seed"])
            self.assertEqual(row["language"], "tr")
            self.assertIs(row["synthetic"], True)
            self.assertIn(row["turn_count"], {4, 6, 8})
            self.assertEqual(row["turn_count"], len(row["messages"]))
            self.assertEqual([m["role"] for m in row["messages"]], ["user", "assistant"] * (len(row["messages"]) // 2))
            self.assertTrue(all(m["content"].strip() == m["content"] for m in row["messages"]))
        self.assertEqual(len(ids), 5_000)
        self.assertEqual(len(seeds), 5_000)

    def test_relationship_metadata_is_topic_safe(self) -> None:
        """Topic-wide composition must never rotate in an incompatible role pair."""
        by_slug = {spec.slug: spec for spec in TOPICS}
        self.assertTrue(all(len(spec.relationships) == 1 for spec in TOPICS))
        for row in self.records:
            slug = row["conversation_id"].removeprefix("trdd5k-").rsplit("-", 1)[0]
            self.assertEqual(row["relationship"], by_slug[slug].relationships[0])

    def test_addon_pairs_keep_user_assistant_semantics(self) -> None:
        for topic_index, spec in enumerate(TOPICS):
            addon_map = dict(spec.addons)
            for row_index in range(records_for_topic(topic_index)):
                messages = render_dialogue(spec, topic_index, row_index)
                contents = [message["content"] for message in messages]
                for index, content in enumerate(contents):
                    if content not in addon_map:
                        continue
                    self.assertEqual(index % 2, 0, (spec.slug, row_index, index, content))
                    self.assertLess(index + 1, len(contents), (spec.slug, row_index, index))
                    self.assertTrue(
                        contents[index + 1].startswith(addon_map[content]),
                        (spec.slug, row_index, index, contents[index + 1]),
                    )

    def test_ordered_addon_families_use_self_contained_core_opening_pair(self) -> None:
        for topic_index, spec in enumerate(TOPICS):
            first_core_pairs = {core[:2] for core in spec.cores}
            second_core_pairs = {core[2:] for core in spec.cores}
            for row_index in range(records_for_topic(topic_index)):
                family = scenario_family_index(spec, row_index)
                messages = render_dialogue(spec, topic_index, row_index)
                if family < len(spec.cores) or len(messages) < 6:
                    continue
                extension = tuple(message["content"] for message in messages[4:6])
                self.assertIn(extension, first_core_pairs, (spec.slug, row_index, extension))
                self.assertNotIn(extension, second_core_pairs - first_core_pairs, (spec.slug, row_index, extension))

    def test_statement_openers_do_not_claim_to_ask_a_question(self) -> None:
        question_only_cues = (
            "bir şey soracağım",
            "kısa bir sorum var",
            "birkaç küçük soru",
            "birkaç şey soracağım",
            "ilk sorum",
            "birkaç sorum",
            "sorularımı",
            "ilk sorumu",
            "öğrenebilir miyim",
        )
        for row in self.records:
            first = row["messages"][0]["content"]
            if first.endswith("?"):
                continue
            normalized = normalize_text(first)
            self.assertFalse(
                any(normalize_text(cue) in normalized for cue in question_only_cues),
                (row["conversation_id"], first),
            )

    def test_generated_markers_do_not_repeat_source_discourse_markers(self) -> None:
        doubled_initial = re.compile(r"^(tamam|peki|bu arada|anladım)\s+\1\b")
        connector = r"(?:tamam|peki|anladım|bu arada|o hâlde|o zaman|bu durumda|öyleyse|buna göre)"
        stacked_initial = re.compile(rf"^{connector}\s+{connector}\b")
        stacked_consequence = re.compile(r"^(o hâlde|bu durumda|öyleyse|buna göre)\b.*\bo zaman\b")
        for row in self.records:
            for message in row["messages"]:
                normalized = normalize_text(message["content"])
                self.assertIsNone(doubled_initial.search(normalized), (row["conversation_id"], message["content"]))
                self.assertIsNone(stacked_initial.search(normalized), (row["conversation_id"], message["content"]))
                self.assertIsNone(stacked_consequence.search(normalized), (row["conversation_id"], message["content"]))

    def test_marker_compatibility_regressions(self) -> None:
        self.assertEqual(attach("", "Bugün erken çıkalım."), "Bugün erken çıkalım.")
        self.assertEqual(attach("Tamam, ", "Tamam, yemlikleri ben yıkarım."), "Tamam, yemlikleri ben yıkarım.")
        self.assertEqual(attach("Peki, ", "Peki, yarın uygun musun?"), "Peki, yarın uygun musun?")
        self.assertEqual(attach("Bu arada, ", "Bu arada, ekmeği aldın mı?"), "Bu arada, ekmeği aldın mı?")
        self.assertEqual(attach("Bu arada, ", "Tamam, yemlikleri ben yıkarım."), "Tamam, yemlikleri ben yıkarım.")
        self.assertEqual(attach("Anladım; ", "Anladım, öğleden sonra gelirim."), "Anladım, öğleden sonra gelirim.")
        self.assertEqual(attach("O hâlde ", "Ölçüyü küçültüp yapalım o zaman."), "Ölçüyü küçültüp yapalım o zaman.")
        self.assertEqual(attach("Bu durumda ", "O zaman kısa anlatayım."), "O zaman kısa anlatayım.")

    def test_no_normalized_exact_dialogue_duplicates(self) -> None:
        normalized = {
            normalize_text(" ".join(message["content"] for message in row["messages"])) for row in self.records
        }
        self.assertEqual(len(normalized), 5_000)

    def test_turkish_capital_i_normalizes_as_one_token(self) -> None:
        self.assertEqual(normalize_text("İstasyon girişindeki cihaz"), "istasyon girişindeki cihaz")

    def test_jsonl_generation_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            build(first, ("jsonl",))
            build(second, ("jsonl",))
            for relative in (
                "data/all.jsonl",
                "data/train.jsonl",
                "data/validation.jsonl",
                "data/test.jsonl",
                "samples/topic-split-samples.jsonl",
                "samples/topic-turn-samples.jsonl",
                "MANIFEST.json",
                "SHA256SUMS",
            ):
                self.assertEqual(digest(first / relative), digest(second / relative), relative)


class ReleaseArtifactTests(unittest.TestCase):
    def test_full_release_validator(self) -> None:
        report = validate(ROOT, write_report=False)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["duplicates"]["near_duplicate_pairs"], 0)
        self.assertEqual(report["duplicates"]["cross_split_near_duplicate_pairs"], 0)
        self.assertEqual(report["content"]["pii_pattern_hits"], 0)
        self.assertEqual(report["content"]["unsafe_phrase_hits"], 0)
        self.assertEqual(report["parquet"]["status"], "passed")

    def test_manifest_is_machine_readable(self) -> None:
        manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["record_count"], 5_000)
        self.assertEqual(manifest["topic_count"], len(TOPICS))
        self.assertFalse(manifest["generated_with"]["network_required"])
        self.assertFalse(manifest["generated_with"]["runtime_model_inference"])
        self.assertTrue(manifest["generated_with"]["ai_assisted_authoring"])
        self.assertEqual(
            manifest["split_strategy"],
            {
                "unit": "scenario_family",
                "families_per_topic": 38,
                "train_families_per_topic": 30,
                "validation_families_per_topic": 4,
                "test_families_per_topic": 4,
            },
        )

    def test_documented_split_contract_matches_code(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        methodology = (ROOT / "docs" / "GENERATION_METHODOLOGY.md").read_text(encoding="utf-8")
        self.assertIn("38 families: 30 assigned to train, 4 to validation, and 4 to test", readme)
        self.assertIn("30 complete families are assigned to train, 4 to validation, and 4 to test", methodology)
        for document in (readme, methodology):
            self.assertIn("3,950", document)
            self.assertIn("525", document)

    def test_qa_report_uses_exact_record_split_ratio(self) -> None:
        report = (ROOT / "reports" / "QA_REPORT.md").read_text(encoding="utf-8")
        self.assertIn("record ratio is 79/10.5/10.5", report)
        self.assertNotIn("75/12.5/12.5", report)


if __name__ == "__main__":
    unittest.main()
