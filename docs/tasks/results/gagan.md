
# H5: Retrieval-Confidence-Based Detection of Out-of-Scope CFPB Complaints

## 1. Objective

H5 evaluates whether retrieval-confidence signals can identify CFPB consumer complaints that fall outside the regulatory coverage of our corpus.

The target label is `NONE`, indicating that a complaint has no applicable regulation in the annotated corpus.

We evaluate:

- Individual BM25 and MPNet dense-retrieval confidence signals.
- Logistic regression combining retrieval-confidence features.
- The effect of excluding FCRA text from the retrieval corpus.
- Error costs associated with incorrectly flagging covered complaints as `NONE`.

The goal is to determine whether retrieval-based abstention is feasible, rather than automatically forcing a regulation match for every complaint.

## 2. Experimental Setup

### Dataset

The evaluation uses 198 annotated CFPB complaints:

| Label | Count |
|---|---:|
| Covered by corpus | 127 |
| `NONE` | 71 |
| **Total** | **198** |

The data was divided into development and held-out report splits:

| Split | Total | `NONE` |
|---|---:|---:|
| Development | 107 | 45 |
| Held-out report | 91 | 26 |

The held-out report split therefore contains 65 covered complaints and 26 `NONE` complaints.

### Retrieval and Features

The experiment uses BM25 and dense retrieval with the following embedding model:

`sentence-transformers/all-mpnet-base-v2`

Nine features were considered:

1. BM25 top score
2. BM25 score margin
3. BM25 normalized top score
4. BM25 top-five mean score
5. Dense top score
6. Dense score margin
7. Dense normalized top score
8. Dense top-five mean score
9. Complaint length (`n_words`)

Hybrid retrieval is not part of the H5 feature-based classifier evaluation.

### Model and Evaluation

A logistic regression classifier was trained using standardized features.

The classification threshold was tuned on the development split and applied to the held-out report split.

Reported metrics include:

- Area under the ROC curve (AUROC).
- 95% bootstrap confidence intervals.
- Precision, recall, and F1 for the `NONE` class.
- Confusion-matrix counts.
- Repeated 5-fold cross-validation with 20 repetitions.

The held-out report metrics are the primary evaluation results.

Results computed using all annotated examples are not treated as independent held-out performance because they include development examples.

### CARC Execution

Experiments were run on USC CARC Discovery.

The successful retrieval feature-generation job was:

- **SLURM job ID:** `13755073`

Earlier troubleshooting jobs were:

- `13753571`: GPU-node execution failure.
- `13753837`: GPU-node execution failure.
- `13754110`: dependency incompatibility.

The successful H5 run originally used:

- `torch==2.5.1+cu121`
- `transformers==4.50.0`
- `sentence-transformers==5.1.2`

These are the original experiment environment versions, not the team's subsequently updated CARC environment.

## 3. Primary H5 Results

### 3.1 Single-Signal AUROC

The table reports held-out AUROC for `NONE` detection. Confidence intervals are 95% bootstrap intervals.

| Signal | With FCRA AUROC [95% CI] | Without FCRA AUROC [95% CI] |
|---|---|---|
| BM25 top score | 0.376 [0.244, 0.516] | 0.370 [0.240, 0.505] |
| BM25 margin | 0.464 [0.325, 0.593] | 0.501 [0.354, 0.647] |
| BM25 normalized top score | 0.594 [0.460, 0.718] | 0.556 [0.421, 0.680] |
| BM25 top-five mean | 0.372 [0.244, 0.512] | 0.368 [0.240, 0.504] |
| Dense top score | 0.660 [0.539, 0.786] | 0.617 [0.488, 0.743] |
| Dense margin | 0.457 [0.335, 0.583] | 0.463 [0.344, 0.591] |
| Dense normalized top score | 0.544 [0.400, 0.689] | 0.563 [0.428, 0.694] |
| Dense top-five mean | **0.666 [0.545, 0.793]** | **0.624 [0.500, 0.751]** |
| Complaint length (longer = NONE) | 0.623 [0.486, 0.755] | 0.623 [0.486, 0.755] |

The best individual retrieval-confidence signal with FCRA included was the dense top-five mean, with a held-out AUROC of 0.666.

The raw BM25 top score performed poorly as a standalone signal, with AUROC 0.376.

These results show that individual confidence signals vary substantially in their ability to distinguish covered complaints from `NONE` complaints.

### 3.2 Combined Logistic Regression

| Metric | With FCRA | Without FCRA |
|---|---:|---:|
| Held-out AUROC | **0.740** | 0.632 |
| 95% bootstrap CI | [0.625, 0.851] | [0.510, 0.755] |
| Repeated CV mean AUROC | 0.732 | 0.686 |
| Repeated CV AUROC SD | 0.076 | 0.080 |
| Held-out precision | 0.440 | 0.328 |
| Held-out recall | 0.846 | 0.808 |
| Held-out F1 | 0.579 | 0.467 |
| Development-tuned threshold | 0.386 | 0.272 |
| Held-out evaluation count | 91 | 91 |
| Held-out `NONE` count | 26 | 26 |

With FCRA included, the logistic regression classifier achieved a held-out AUROC of 0.740.

The observed AUROC exceeded the strongest individual retrieval signal (dense top-five mean, AUROC 0.666). However, the paired uncertainty analysis in Section 4 shows that this difference is not statistically established.

Repeated cross-validation produced a mean AUROC of 0.732 with a standard deviation of 0.076 in the with-FCRA configuration.

### 3.3 Held-Out Confusion Matrix

`NONE` is treated as the positive class.

| Outcome | With FCRA | Without FCRA |
|---|---:|---:|
| True positives (`NONE` correctly flagged) | 22 | 21 |
| False negatives (`NONE` missed) | 4 | 5 |
| False positives (covered complaints flagged as `NONE`) | 28 | 43 |
| True negatives (covered complaints correctly retained) | 37 | 22 |

With FCRA included, the classifier correctly flagged 22 of the 26 `NONE` complaints, yielding 84.6% recall.

However, it also incorrectly flagged 28 covered complaints.

#### Operational Error Cost

For the with-FCRA configuration:

- Correct `NONE` flags: 22
- Incorrect flags on covered complaints: 28
- Incorrect flags per correct `NONE` flag: **28 / 22 = 1.27**

Thus, for every correct `NONE` referral, the classifier generated approximately **1.27 incorrect referrals**.

Here, a referral means a complaint flagged for `NONE` handling or further review. It does not imply that the complaint was automatically rejected in a deployed system.

This high false-positive burden is a major practical limitation, even though the model achieves high recall.

## 4. Exploratory Model Comparisons

**Status: Exploratory, performed after examining held-out report-half results.**

The comparisons in Sections 4–7 were supplied through the team's follow-up recheck and were not produced by the original H5 scripts. They should not be interpreted as prespecified confirmatory tests.

### 4.1 Feature Ablation

The team's exploratory recheck reported the following held-out AUROC values:

| Model configuration | Held-out AUROC |
|---|---:|
| Dense features only | 0.661 |
| Dense features + `n_words` | 0.727 |
| All features | **0.740** |
| All features excluding `n_words` | 0.739 |

Dense features alone achieved AUROC 0.661.

Adding complaint length to the dense feature set increased observed AUROC to 0.727.

Using all features achieved 0.740, while removing complaint length from the full feature set yielded 0.739.

The near-equal full-model AUROCs do not demonstrate that complaint length is unimportant. Its contribution depends on the other features included.

### 4.2 Complaint Length and BM25 Correlation

The team's exploratory analysis found a correlation of:

**Corr(BM25 top score, `n_words`) = 0.986**

This is a very strong association.

Consequently, the small standardized coefficient on `n_words` in the full logistic regression model cannot be interpreted as evidence that the classifier does not rely on complaint length.

Because BM25 top score and complaint length are highly correlated, their effects can overlap in the combined model.

The ablation results and this feature correlation are more informative than interpreting the complaint-length coefficient in isolation.

### 4.3 Combined Model vs. Best Single Signal

The best individual retrieval-confidence signal was dense top-five mean:

- Dense top-five mean AUROC: 0.666
- Full logistic regression AUROC: 0.740
- Observed AUROC difference: **0.074**
- Paired 95% CI for the difference: **[-0.005, 0.167]**

Although the combined classifier performed better numerically, the paired confidence interval includes zero.

Therefore, **the improvement over the best single signal is not statistically established** by this evaluation.

The main conclusion is that the combined classifier is promising, not that it has conclusively outperformed the strongest individual confidence signal.

## 5. Exploratory FCRA Ablation Analysis

**Status: Exploratory, performed after examining held-out report-half results.**

### 5.1 Observed Performance Change

The primary H5 results reported:

| Configuration | Held-out AUROC |
|---|---:|
| With FCRA | 0.740 |
| Without FCRA | 0.632 |
| Observed difference | **0.108** |

The team's follow-up paired analysis found:

| Comparison population | AUROC difference [95% paired CI] |
|---|---|
| All 91 report-half complaints | 0.108 [0.018, 0.202] |
| Excluding FCRA complaints | 0.085 [-0.012, 0.189] |

On all 91 held-out complaints, the paired interval was above zero.

However, after excluding FCRA complaints, the paired confidence interval includes zero.

Therefore, the evidence for an FCRA-related performance difference depends on which complaint population is evaluated.

### 5.2 Important Coverage Caveat

In the no-FCRA retrieval experiment, FCRA regulation text was removed from the retrieval corpus, but the evaluation still counted **18 FCRA complaints as covered**.

Among the 43 false positives in the no-FCRA run, **11 were FCRA complaints**.

This matters because complaints whose relevant regulation text was deliberately excluded from retrieval were still evaluated as though they were covered by the corpus.

As a result, the increased false-positive count in the no-FCRA condition cannot be attributed solely to a general deterioration in the abstention classifier.

Part of the apparent degradation is associated with the changed corpus coverage and the evaluation-label definition.

### 5.3 Evaluation Excluding FCRA Complaints

The team's exploratory recheck reported an **AUROC of 0.688** when FCRA complaints were excluded from the no-FCRA evaluation.

This is different from the unfiltered no-FCRA AUROC of 0.632.

The difference reinforces the importance of evaluating the detector against a consistent definition of which regulations are actually covered.

Together, these findings show that the FCRA ablation must be interpreted as a corpus-coverage and evaluation-design sensitivity analysis, rather than a clean measure of model degradation.

## 6. Exploratory Error Breakdown by Regulation

**Status: Exploratory, performed after examining held-out report-half results.**

The team's follow-up error review identified the following incorrect `NONE` flag rates among covered complaints in the with-FCRA held-out evaluation:

| Regulation | Incorrectly flagged | Total | Flag rate |
|---|---:|---:|---:|
| Regulation Z | 13 | 15 | 86.7% |
| Regulation E | 7 | 13 | 53.8% |
| Regulation F | 4 | 15 | 26.7% |
| Regulation V | 1 | 4 | 25.0% |
| FCRA | 3 | 18 | 16.7% |
| **Total** | **28** | **65** | **43.1%** |

All 28 false positives from the with-FCRA held-out confusion matrix are accounted for by this breakdown.

The highest observed false-positive flag rate was for Regulation Z, where 13 of 15 covered complaints were incorrectly classified as `NONE`.

Regulation E also showed a high false-positive rate, with 7 of 13 complaints flagged.

These rates indicate that the detector's errors are not evenly distributed across regulations.

They are descriptive subgroup findings based on small sample sizes, not definitive evidence that the classifier will behave similarly on a larger population.

## 7. Exploratory Coefficient Interpretation

**Status: Exploratory interpretation after examining held-out results.**

The original logistic regression produced the following standardized coefficients:

| Feature | With FCRA | Without FCRA |
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

With FCRA included, dense top-five mean and dense top score had relatively large negative coefficients.

These signs are consistent with lower dense-retrieval confidence increasing the predicted probability of `NONE`, holding the other model inputs fixed.

However, standardized coefficients must be interpreted with care because the model includes correlated features.

In particular, BM25 top score and complaint length have an observed correlation of 0.986.

Therefore:

- Individual coefficients should not be treated as causal feature importance.
- A small coefficient does not establish that a feature contributes little to prediction.
- The exploratory ablations in Section 4 provide additional context for feature contributions.

## 8. Limitations

### Evaluation Sample Size

Only 91 complaints were in the held-out report split, including 26 `NONE` examples.

The resulting confidence intervals are relatively wide, limiting the precision of performance estimates.

### False-Positive Referrals

The with-FCRA classifier produced 28 incorrect `NONE` referrals for 22 correct referrals.

This ratio of 1.27 incorrect referrals per correct referral makes direct automatic abstention risky without additional validation or review.

### Dependence on Regulation Coverage

Removing FCRA text changed which regulations were available to retrieval, while FCRA complaints remained labeled as covered.

The apparent performance drop therefore mixes retrieval corpus coverage effects with abstention behavior.

### Correlated Features

BM25 top score was strongly correlated with complaint length.

Individual logistic regression coefficients should not be interpreted as independent measures of feature importance.

### Limited Evidence of Improvement Over Strongest Baseline

The paired AUROC difference between the full logistic regression and dense top-five mean was 0.074, with confidence interval [-0.005, 0.167].

Because the interval crosses zero, superiority over the best single signal is not established.

### Post-Hoc Analyses

The ablations, paired comparisons, length correlation, and regulation-level breakdowns in Sections 4–7 were supplied through the team's exploratory recheck after examination of the held-out results.

These findings are useful for interpretation and follow-up planning but should not be presented as prespecified confirmatory evidence.

## 9. Conclusion

H5 demonstrates that retrieval-confidence features contain useful information for identifying CFPB complaints outside the regulation corpus.

With FCRA included, the logistic regression classifier achieved:

- **Held-out AUROC:** 0.740
- **95% CI:** [0.625, 0.851]
- **`NONE` recall:** 0.846
- **`NONE` precision:** 0.440
- **`NONE` F1:** 0.579

The result is encouraging, but the detector made 28 incorrect `NONE` referrals for 22 correct referrals.

Moreover, the observed AUROC gain over the best individual signal was not statistically established in the paired exploratory comparison.

The FCRA ablation also demonstrates that the meaning of `NONE` must remain consistent with the regulations actually available in the retrieval corpus.

**Overall, H5 supports retrieval-confidence-based `NONE` detection as a promising research direction, but does not establish a production-ready automatic abstention mechanism.**

## 10. Reproducibility and Artifacts

### Original Experiment Environment

The successful H5 run used:

```text
torch==2.5.1+cu121
transformers==4.50.0
sentence-transformers==5.1.2
```

The CARC environment was later updated to the team's `final-experiments` commit `e5ac79a` using `carc/setup_env.sh`.

Updated environment versions:

```text
torch==2.14.1+cu126
transformers==5.19.0
sentence-transformers==6.2.0
```

The updated package versions should not be mistaken for the versions that originally generated the H5 results.

### Retrieval Feature Generation

```bash
sbatch carc/retrieval.sbatch
```

Successful CARC job ID: `13755073`.

### H5 With FCRA

```bash
python scripts/run_abstention.py \
  --features outputs/retrieval/features_mpnet.parquet \
  --tag mpnet
```

### H5 Without FCRA

```bash
python scripts/run_abstention.py \
  --features outputs/retrieval/features_mpnet_no_fcra.parquet \
  --tag mpnet_no_fcra
```

### H5 Result Files

The H5 PR contains:

- `docs/tasks/results/gagan.md`
- `results/abstention_mpnet.json`
- `results/abstention_mpnet_no_fcra.json`

The retrieval benchmark artifact `results/retrieval_mpnet.json` is owned by Ishani and is intentionally excluded from this H5 PR.

The Parquet feature files are generated artifacts and are not committed to the repository.

### Provenance of Additional Analyses

The original H5 result JSON files provide the primary model evaluation metrics and confidence intervals.

The model ablations, paired AUROC comparisons, feature correlation, adjusted FCRA analysis, and regulation-level flag rates in Sections 4–7 were provided through the team's post-hoc recheck, not the original H5 scripts.
