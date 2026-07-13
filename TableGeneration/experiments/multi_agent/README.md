# Multi-Agent Experiments

This directory evaluates only the table-generation multi-agent system.

## Ablation

```powershell
python experiments\multi_agent\run_ablation.py --samples_per_config 20 --output experiments\multi_agent\results\ablation
```

The three fixed configurations are one ordinary candidate, five ordinary candidates, and the paper-style five ordinary plus four transformed candidates.

## Trace summary

```powershell
python experiments\multi_agent\summarize_traces.py --trace ..\output\paper_trace_smoke\trace.jsonl --output experiments\multi_agent\results\trace_summary
```

## Filling Checker and human correlation

Prepare a CSV containing `human_structure`, `human_topic`, `human_semantic`, `checker_structure`, `checker_topic`, and `checker_semantic`, then run:

```powershell
python experiments\multi_agent\checker_human_correlation.py --ratings ratings.csv --output experiments\multi_agent\results\human_correlation.json
```

The script reports Pearson, Spearman, and Kendall tau-b. It does not create or substitute human ratings.
