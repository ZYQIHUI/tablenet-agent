# Mini Structure Fidelity Experiment

- Created at: 2026-07-09T16:07:45
- Metric: span-level structure score, exact match, parsed structure validity.
- Direct baseline: deterministic offline HTML baseline for LLM-direct style errors.

| Method | Case | Samples | Exact Match | Structure Valid | Avg Structure Score | Avg Error Count |
|---|---|---:|---:|---:|---:|---:|
| agent_tool | simple_with_content | 7 | 7 | 7 | 1.0 | 0.0 |
| agent_tool | simple_without_content | 7 | 7 | 7 | 1.0 | 0.0 |
| agent_tool | complex_with_content | 7 | 7 | 7 | 1.0 | 0.0 |
| agent_tool | complex_without_content | 7 | 7 | 7 | 1.0 | 0.0 |
| llm_direct | simple_with_content | 7 | 7 | 7 | 1.0 | 0.0 |
| llm_direct | simple_without_content | 7 | 7 | 7 | 1.0 | 0.0 |
| llm_direct | complex_with_content | 7 | 0 | 0 | 0.8552 | 3.1429 |
| llm_direct | complex_without_content | 7 | 3 | 3 | 0.9367 | 1.4286 |
