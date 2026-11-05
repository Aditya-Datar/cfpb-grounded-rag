
# H5: Detecting Out-of-Scope CFPB Complaints (NONE)

## 1. Objective

Evaluate whether retrieval-confidence signals can distinguish consumer complaints that are not covered by the regulations in our corpus (`NONE`) from in-scope complaints.

We compare individual BM25 and dense-retrieval confidence signals against a logistic regression classifier combining multiple retrieval features. We also investigate whether removing the Fair Credit Reporting Act (FCRA) from the corpus affects NONE detection.

## 2. Experimental Setup

- **Dataset:** 198 annotated CFPB complaints (127 in-scope, 71 NONE).
- **Development split:** 107 complaints, including 45 NONE.
- **Held-out report split:** 91 complaints, including 26 NONE.
- **Retrieval methods:** BM25, MPNet dense retrieval, and hybrid retrieval.
- **Embedding model:** `sentence-transformers/all-mpnet-base-v2`.
- **Corpus configurations:** With FCRA and without FCRA.
- **Features:** BM25 and dense top scores, score margins, normalized top scores, top-five mean scores, and complaint length (`n_words`).
- **Classifier:** Logistic regression with standardized features, trained on the development split.
- **Threshold:** Selected on the development split to maximize F1 and applied unchanged to the report split.
- **Evaluation:** Held-out AUROC with 95% bootstrap confidence intervals, precision, recall, F1, and repeated 5-fold cross-validation (20 repetitions).

The earlier BM25 top-score baseline was approximately **0.43 AUROC**. For direct comparisons, we use BM25 results from the same held-out split as the current experiments.

## 3. Results

### 3.1 Individual Confidence Signals

Held-out AUROC for detecting `NONE`:

| Feature | With FCRA | Without FCRA |
|---|---:|---:|
| BM25 top score | 0.376 | 0.370 |
| BM25 margin | 0.464 | 0.501 |
| BM25 normalized top score | 0.594 | 0.556 |
| BM25 top-five mean | 0.372 | 0.368 |
| Dense top score | 0.660 | 0.617 |
| Dense margin | 0.457 | 0.463 |
| Dense normalized top score | 0.544 | 0.563 |
| Dense top-five mean | **0.666** | **0.624** |
| Complaint length (longer = NONE) | 0.623 | 0.623 |

Dense-retrieval confidence generally provided stronger discrimination than the raw BM25 top score. The best individual retrieval signal with FCRA was the dense top-five mean (AUROC 0.666).

### 3.2 Combined Logistic Regression

| Metric | With FCRA | Without FCRA |
|---|---:|---:|
| Held-out AUROC | **0.740** | 0.632 |
| 95% bootstrap CI | [0.625, 0.851] | [0.510, 0.755] |
| Repeated CV AUROC (mean ± SD) | **0.732 ± 0.076** | 0.686 ± 0.080 |
| Held-out precision | **0.440** | 0.328 |
| Held-out recall | **0.846** | 0.808 |
| Held-out F1 | **0.579** | 0.467 |
| Dev-tuned decision threshold | 0.386 | 0.272 |

The combined logistic regression achieved the highest held-out AUROC (0.740) with FCRA included, outperforming the BM25 top-score signal (0.376) on the same report split.

Excluding FCRA reduced the logistic regression AUROC from 0.740 to 0.632, an observed difference of 0.108. This suggests that corpus coverage influences NONE detection, although a paired significance test would be needed to establish the reliability of this difference.

### 3.3 Held-Out Error Analysis

`NONE` is treated as the positive class.

| Outcome | With FCRA | Without FCRA |
|---|---:|---:|
| True positives (NONE correctly identified) | 22 | 21 |
| False negatives (NONE missed) | 4 | 5 |
| False positives (covered complaints incorrectly classified as NONE) | 28 | 43 |
| True negatives (covered complaints correctly retained) | 37 | 22 |

With FCRA included, the classifier correctly identified **22 of 26 NONE complaints**, achieving 84.6% recall.

However, it also incorrectly rejected **28 of 65 covered complaints**. Removing FCRA increased the false positives to 43, reducing precision from 0.440 to 0.328.

These results indicate that NONE detection is feasible, but false-positive abstentions remain a substantial limitation.

## 4. Feature Coefficient Analysis

The logistic regression uses standardized input features.

| Feature | With FCRA coefficient | Without FCRA coefficient |
|---|---:|---:|
| BM25 top score | +0.181 | +0.149 |
| BM25 margin | +0.170 | +0.012 |
| BM25 normalized top score | -0.385 | -0.161 |
| BM25 top-five mean | -0.152 | -0.048 |
| Dense top score | -0.472 | -0.416 |
| Dense margin | +0.086 | -0.557 |
| Dense normalized top score | -0.176 | -0.000 |
| Dense top-five mean | -0.555 | -0.406 |
| Complaint length (`n_words`) | +0.044 | +0.025 |

With FCRA, the largest-magnitude coefficients were associated with dense top-five mean, dense top score, and BM25 normalized top score.

The negative dense-confidence coefficients are consistent with lower retrieval confidence increasing the predicted probability of `NONE`.

Complaint length had a comparatively small coefficient (+0.044), suggesting that the model was not primarily relying on narrative length.

However, coefficient magnitudes should be interpreted cautiously because several retrieval-confidence features may be correlated.

## 5. Hypothesis Assessment

**H5: Retrieval-confidence features can help identify complaints outside the covered regulations without always forcing a regulatory match.**

The results provide evidence supporting H5 as a feasibility finding:

- Logistic regression achieved **0.740 held-out AUROC**, compared with 0.376 for the BM25 top-score signal on the same split.
- Repeated cross-validation yielded **0.732 ± 0.076 AUROC** with FCRA included.
- Dense-retrieval confidence contributed more strongly than complaint length based on the standardized coefficients.
- Removing FCRA reduced held-out AUROC to 0.632 and increased false-positive abstentions.

However, the held-out precision of 0.440 shows that the detector still incorrectly identifies many covered complaints as NONE.

Therefore, H5 is **supported as evidence of useful discrimination**, but not as a demonstration of reliable production-ready abstention.

## 6. Limitations

1. **Evaluation size:** The held-out report split contains 91 complaints, including only 26 NONE examples. The confidence intervals reflect substantial uncertainty.
2. **False-positive abstentions:** With FCRA, 28 of 65 covered complaints were incorrectly rejected.
3. **Corpus sensitivity:** Removing FCRA reduced performance, suggesting that results depend partly on regulatory corpus coverage.
4. **Feature correlation:** Standardized coefficients offer useful interpretation but cannot establish independent feature importance.
5. **Threshold sensitivity:** Precision and recall depend on the threshold chosen on the development split.
6. **Statistical comparison:** Differences between retrieval configurations have not been evaluated with paired confidence intervals or hypothesis tests.

The `all` AUROC reported in the output JSON includes training examples and is not used as the primary test result. Only the held-out `report_half` metrics are presented as final evaluation results.

## 7. Conclusion

Combining BM25 and MPNet dense-retrieval confidence features substantially improved NONE discrimination compared with a single BM25 top-score baseline.

The best configuration, logistic regression with FCRA included, achieved **0.740 held-out AUROC (95% CI: [0.625, 0.851])**, with 0.846 recall and 0.440 precision.

Although the findings support retrieval-confidence-based NONE detection, the high false-positive rate indicates that additional threshold calibration and validation are needed before using the detector for automatic abstention.

## 8. Reproducibility

The experiments were executed on USC CARC using the `final-experiments` codebase and H5 working branch `exp/gagan`.

### Generate retrieval features

```bash
sbatch carc/retrieval.sbatch
```

### Run H5 with FCRA

```bash
python scripts/run_abstention.py \
  --features outputs/retrieval/features_mpnet.parquet \
  --tag mpnet
```

### Run H5 without FCRA

```bash
python scripts/run_abstention.py \
  --features outputs/retrieval/features_mpnet_no_fcra.parquet \
  --tag mpnet_no_fcra
```

### Result Artifacts

- `results/abstention_mpnet.json`
- `results/abstention_mpnet_no_fcra.json`
- `results/retrieval_mpnet.json`

The feature Parquet files are generated experiment artifacts and are not intended to be committed to GitHub.
