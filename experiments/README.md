# SlideGuard Ablation Experiments

Scripts for running three ablation studies that isolate the contribution of key pipeline components.

## Ablations

| Name | What is disabled | What it measures |
|---|---|---|
| `baseline` | Nothing (full pipeline) | Reference configuration |
| `no_filtering` | Slide-type applicability filtering | Value of running criteria only on relevant slides |
| `text_only` | Multimodal input for evaluation criteria | Value of passing slide images vs text descriptions |
| `no_retry` | Structured-output retry loop (`max_retries=0`) | How often error-feedback retries rescue parse failures |

## Prerequisites

- A configured `.env` file (or equivalent environment variables) for the LLM backend.
- One or more PDF slide decks for evaluation.
- The `slideguard` package installed (e.g. `pip install -e .` from the repo root).

## Running

From the **repository root**:

```bash
# Run all four configurations on a folder of PDFs
python experiments/run_ablations.py \
    --pdf-dir path/to/pdfs/ \
    --output-dir experiments/results \
    --presentation-type scientific

# Run only specific ablations
python experiments/run_ablations.py \
    --pdf-dir path/to/pdfs/ \
    --ablations baseline,no_filtering

# Single PDF
python experiments/run_ablations.py \
    --pdf-dir path/to/presentation.pdf \
    --output-dir experiments/results
```

### Runner options

| Flag | Default | Description |
|---|---|---|
| `--pdf-dir` | *(required)* | Path to a PDF or directory of PDFs |
| `--output-dir` | `experiments/results` | Where result JSONs are written |
| `--cache-base` | `.slideguard_ablation_cache` | Per-ablation evaluation cache root |
| `--ablations` | `baseline,no_filtering,text_only,no_retry` | Comma-separated ablation list |
| `--presentation-type` | `scientific` | Presentation type for criteria selection |
| `--verbose` | off | Enable debug logging |

## Analysing results

```bash
# Basic comparison
python experiments/analyze_results.py \
    --results-dir experiments/results

# With ground-truth annotations and CSV export
python experiments/analyze_results.py \
    --results-dir experiments/results \
    --ground-truth data/annotations \
    --csv experiments/summary.csv
```

The analysis script outputs Markdown tables for:

- **Mean score** per criterion across ablations
- **Mean issue count** per slide per criterion
- **Fallback (parse-failure) rate** — percentage of evaluations that fell back to a default result
- **Detection rate** vs ground truth (when `--ground-truth` is provided)

## Output structure

```
experiments/results/
├── baseline/
│   ├── presentation_A.json
│   └── presentation_B.json
├── no_filtering/
│   ├── presentation_A.json
│   └── presentation_B.json
├── text_only/
│   └── ...
└── no_retry/
    └── ...
```

Each JSON file is a serialised `FullEvaluation` object identical to what the CLI produces.

## Implementation notes

- All ablation logic lives in `experiments/ablations/` — **no core source files are modified**.
- Each ablation uses a **separate evaluation cache directory** to prevent cross-contamination; the file cache (PDF-to-PNG conversion) is shared since the images are identical.
- The `text_only` ablation still runs service criteria (slide type classification, description generation) on images; only the evaluation criteria receive text.
