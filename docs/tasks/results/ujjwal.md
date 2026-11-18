# Ujjwal: chunking and corpus-scope ablations

## Setup

The five retrieval configurations were run in Google Colab on a Tesla T4 using
`sentence-transformers/all-mpnet-base-v2`. Each configuration ran BM25, dense,
and the dev-tuned hybrid retriever both with and without FCRA.
All confidence intervals below are 95% complaint-level bootstrap intervals
(10,000 resamples, seed 0).

## Chunking comparison without FCRA

These are held-out report-half results (`n = 65`). Chunk counts in this table
are for the regulation-only corpus. Each metric is shown as estimate
`[95% CI]`.

| Chunking | Chunks | BM25 hit@1 | BM25 hit@5 | BM25 MRR | Dense hit@1 | Dense hit@5 | Dense MRR | Hybrid hit@1 | Hybrid hit@5 | Hybrid MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `struct1400` | 2,629 | 0.062 [0.015, 0.123] | 0.185 [0.092, 0.277] | 0.130 [0.075, 0.194] | 0.231 [0.138, 0.338] | 0.585 [0.462, 0.708] | 0.375 [0.284, 0.468] | 0.231 [0.138, 0.338] | 0.585 [0.462, 0.708] | 0.375 [0.284, 0.468] |
| `struct700` | 3,776 | 0.062 [0.015, 0.123] | 0.123 [0.046, 0.200] | 0.108 [0.056, 0.169] | 0.185 [0.092, 0.277] | 0.477 [0.354, 0.600] | 0.330 [0.244, 0.421] | 0.185 [0.092, 0.277] | 0.477 [0.354, 0.600] | 0.330 [0.244, 0.421] |
| `struct2800` | 1,668 | 0.015 [0.000, 0.046] | 0.200 [0.108, 0.308] | 0.108 [0.070, 0.153] | 0.169 [0.077, 0.262] | 0.554 [0.431, 0.677] | 0.317 [0.237, 0.404] | 0.169 [0.077, 0.262] | 0.554 [0.431, 0.677] | 0.317 [0.237, 0.404] |
| `fixed200` | 1,402 | 0.046 [0.000, 0.108] | 0.108 [0.046, 0.185] | 0.116 [0.066, 0.176] | 0.138 [0.062, 0.231] | 0.415 [0.292, 0.538] | 0.274 [0.198, 0.359] | 0.123 [0.046, 0.215] | 0.431 [0.308, 0.554] | 0.272 [0.198, 0.353] |
| `section` | 136 | 0.031 [0.000, 0.077] | 0.123 [0.046, 0.200] | 0.105 [0.061, 0.159] | 0.154 [0.077, 0.246] | 0.508 [0.385, 0.631] | 0.305 [0.226, 0.391] | 0.246 [0.138, 0.354] | 0.585 [0.462, 0.708] | 0.374 [0.283, 0.472] |

## Paired differences from `struct1400`

Differences are alternative minus `struct1400` on the same 65 report-half
complaints. Negative values favor `struct1400`.

| Alternative | Retriever | Delta hit@5 [95% CI] | Delta MRR [95% CI] |
|---|---|---:|---:|
| `struct700` | BM25 | -0.062 [-0.138, 0.000] | -0.022 [-0.061, 0.010] |
| `struct700` | Dense | -0.108 [-0.200, -0.015] | -0.045 [-0.104, 0.015] |
| `struct700` | Hybrid | -0.108 [-0.200, -0.015] | -0.045 [-0.104, 0.015] |
| `struct2800` | BM25 | 0.015 [-0.077, 0.108] | -0.022 [-0.066, 0.016] |
| `struct2800` | Dense | -0.031 [-0.123, 0.062] | -0.057 [-0.107, -0.017] |
| `struct2800` | Hybrid | -0.031 [-0.123, 0.062] | -0.057 [-0.107, -0.017] |
| `fixed200` | BM25 | -0.077 [-0.154, 0.000] | -0.014 [-0.050, 0.024] |
| `fixed200` | Dense | -0.169 [-0.262, -0.077] | -0.101 [-0.175, -0.033] |
| `fixed200` | Hybrid | -0.154 [-0.246, -0.077] | -0.103 [-0.165, -0.045] |
| `section` | BM25 | -0.062 [-0.154, 0.031] | -0.025 [-0.087, 0.037] |
| `section` | Dense | -0.077 [-0.200, 0.031] | -0.069 [-0.146, 0.002] |
| `section` | Hybrid | 0.000 [-0.108, 0.108] | -0.000 [-0.081, 0.080] |

## Effect of adding FCRA to `struct1400`

This comparison is restricted to the same 47 non-FCRA, report-half complaints
so it measures corpus distraction rather than performance on FCRA complaints.
The paired differences are with FCRA minus without FCRA.

| Retriever | Corpus | hit@1 [95% CI] | hit@5 [95% CI] | MRR [95% CI] | Paired delta hit@5 [95% CI] | Paired delta MRR [95% CI] |
|---|---|---:|---:|---:|---:|---:|
| BM25 | Without FCRA | 0.085 [0.021, 0.170] | 0.255 [0.128, 0.383] | 0.180 [0.108, 0.262] | — | — |
| BM25 | With FCRA | 0.043 [0.000, 0.106] | 0.191 [0.085, 0.298] | 0.134 [0.079, 0.201] | -0.064 [-0.149, 0.000] | -0.046 [-0.080, -0.019] |
| Dense | Without FCRA | 0.319 [0.191, 0.447] | 0.809 [0.681, 0.915] | 0.518 [0.416, 0.620] | — | — |
| Dense | With FCRA | 0.170 [0.064, 0.277] | 0.638 [0.489, 0.766] | 0.378 [0.292, 0.469] | -0.170 [-0.298, -0.064] | -0.140 [-0.195, -0.089] |
| Hybrid | Without FCRA | 0.319 [0.191, 0.447] | 0.809 [0.681, 0.915] | 0.518 [0.416, 0.620] | — | — |
| Hybrid | With FCRA | 0.191 [0.085, 0.298] | 0.638 [0.489, 0.766] | 0.404 [0.314, 0.499] | -0.170 [-0.277, -0.064] | -0.114 [-0.179, -0.056] |

## Interpretation

Structure-aware `struct1400` beat the naive fixed 200-word windows for dense and hybrid retrieval: both paired hit@5 and MRR intervals excluded zero. Reducing the structural target to 700 characters lowered dense and hybrid hit@5, while increasing it to 2,800 characters lowered MRR; therefore the default size was the strongest structural setting overall, although several intervals still included zero. Whole-section chunks were statistically indistinguishable from `struct1400` for hybrid hit@5 and MRR, so the data do not establish a hybrid advantage for either of those two settings. Adding FCRA hurt retrieval on non-FCRA complaints: dense and hybrid hit@5 fell by 0.170, and their paired intervals excluded zero. The chunking conclusion uses the without-FCRA runs because `chunk_regulations.py` re-chunks FCRA while `make_fixed_chunks.py` retains the default FCRA chunks.

## Commands and run notes

The alternative chunk files were built with:

```bash
python chunking/chunk_regulations.py --max-chars 700 --out chunking/data/processed/chunks_struct700.jsonl
python chunking/chunk_regulations.py --max-chars 2800 --out chunking/data/processed/chunks_struct2800.jsonl
python scripts/make_fixed_chunks.py --words 200 --stride 150
python scripts/make_fixed_chunks.py --words 0
```

Retrieval was run directly in Colab with these commands:

```bash
python scripts/run_retrieval.py --tag struct1400 --device cuda
python scripts/run_retrieval.py --chunks chunking/data/processed/chunks_struct700.jsonl --tag struct700 --device cuda
python scripts/run_retrieval.py --chunks chunking/data/processed/chunks_struct2800.jsonl --tag struct2800 --device cuda
python scripts/run_retrieval.py --chunks chunking/data/processed/chunks_fixed200_s150.jsonl --tag fixed200 --device cuda
python scripts/run_retrieval.py --chunks chunking/data/processed/chunks_section.jsonl --tag section --device cuda
python scripts/analysis/compare_chunkings.py
```

All five runs completed successfully. The ten rank Parquets are archived in the team Drive under
`final-experiments/ujjwal/`.
