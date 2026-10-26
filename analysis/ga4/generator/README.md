# ec_demo generator assessment

See [decision report](../../../docs/reports/phase-3.3-ga4-generator-assessment.md).
This is synthetic local output, separate from Google's public sample dataset.
No BigQuery or production database is needed. Only aggregates are retained here;
raw generated JSONL/CSVs remain in `/tmp/ec-demo-evaluation-output` and may expire.

The evaluated upstream revision is pinned in `run-manifest.json`. `evaluated-config.yaml`
copies the evaluated configuration with an isolated output directory. The evaluator
uses the existing project DuckDB dependency, a temporary in-memory database with a
1 GB limit and two threads, and a streamed compact projection of JSONL. It never
opens `ecommerce.duckdb` or ClickHouse. Snapshot dates are intentionally fixed for
the evaluated January–March 2025 experiment, not inferred from arbitrary inputs.

Reproduce in fresh temporary locations (requires authorized network/package access):

```bash
git clone https://github.com/ajaxbarcelonacruyff/ec_demo.git /tmp/ec_demo-assessment
git -C /tmp/ec_demo-assessment checkout 4f5c09c6965e76662d31bc8e3a9ef68e74599bb0
python3 -m venv /tmp/ec-demo-eval-venv
/tmp/ec-demo-eval-venv/bin/pip install 'pyyaml==6.0.3'
/tmp/ec-demo-eval-venv/bin/python /tmp/ec_demo-assessment/generate.py \
  --config analysis/ga4/generator/evaluated-config.yaml
.venv/bin/python analysis/ga4/generator/evaluate.py \
  --input /tmp/ec-demo-evaluation-output \
  --output analysis/ga4/generator/results-seed-42.json
.venv/bin/python -m pytest /tmp/ec_demo-assessment/tests -q
.venv/bin/python -m pytest analysis/ga4/generator/test_evaluate.py -q
.venv/bin/ruff check analysis/ga4/generator
.venv/bin/ruff format --check analysis/ga4/generator
```

Use a fresh output directory when changing dates: the upstream generator does not
clear older daily files. Do not run `bigquery_load.py`. The generator needs only
PyYAML; its BigQuery dependency is unnecessary for generation and was not installed.
UUID transaction values vary across reruns despite the seed; compare aggregate
metrics rather than claiming byte-identical outputs. No upstream code is vendored
or modified. Upstream tests check invariants; they do not establish real-world validity.
