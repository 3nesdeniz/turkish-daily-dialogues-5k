# Schema reference

All release formats share one logical schema.

| Field | Type | Constraint |
|---|---|---|
| `conversation_id` | string | Unique; `trdd5k-<topic-slug>-<3 digits>` |
| `messages` | list of structs | Exactly 4, 6, or 8 non-empty turns |
| `messages[].role` | string | Alternates `user`, `assistant`; starts with `user` |
| `messages[].content` | string | UTF-8 NFC Turkish text with terminal punctuation |
| `topic` | string | One of 35 daily-life topic labels |
| `setting` | string | Generic setting; never a real address |
| `relationship` | string | Broad topic-level speaker relationship, chosen to remain valid for every composable scenario in that topic |
| `formality` | string | `informal`, `polite`, or `formal` |
| `turn_count` | int | Equal to `len(messages)` |
| `language` | string | Always `tr` |
| `synthetic` | boolean | Always `true` |
| `split` | string | `train`, `validation`, or `test` |
| `source` | struct | Required provenance and reproducibility metadata |

## Source metadata

| Field | Type | Meaning |
|---|---|---|
| `type` | string | Always `synthetic` |
| `method` | string | Authoring/composition method identifier |
| `generator` | string | Repository-relative generator path |
| `generator_version` | string | Generator semantic version |
| `seed` | int | Dataset-wide deterministic seed |
| `record_seed` | int | Unique deterministic seed for the row |
| `scenario_family` | int | Integer 0–37; source family used for group-aware splitting |
| `external_sources` | boolean | `false`; no external corpus is intentionally used |
| `ai_assisted_authoring` | boolean | `true`; source scenarios were drafted with AI assistance |
| `runtime_model_inference` | boolean | `false`; regeneration makes no model call |

The logical nested types are retained in Parquet. JSONL represents the same structures as JSON objects and arrays.
