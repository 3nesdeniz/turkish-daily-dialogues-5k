.PHONY: generate reproduce lint format-check validate test qa clean-generated

PYTHON ?= python3

generate:
	$(PYTHON) scripts/generate_dataset.py

reproduce: generate

lint:
	ruff check scripts tests

format-check:
	ruff format --check scripts tests

validate:
	$(PYTHON) scripts/validate_dataset.py --root .

test:
	$(PYTHON) -m unittest discover -s tests -v

qa: lint format-check validate test

clean-generated:
	rm -f data/*.jsonl data/*.parquet samples/*.jsonl MANIFEST.json SHA256SUMS reports/*.json reports/*.md
