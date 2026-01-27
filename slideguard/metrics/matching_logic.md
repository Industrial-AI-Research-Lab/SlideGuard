# Matching logic (evaluation_metrics.py)

Step-by-step flow for how predicted issues are matched to ground-truth issues and labeled.

## Inputs
- Predicted evaluation: `FullEvaluation` with slide and deck evaluations containing issue texts.
- Ground truth: `GoldenYAMLSchema` with slide and deck issues.
- Optional LLM: `ControlledLLM` for semantic adjudication.

## High-level stages
1) Extract predicted issue texts per slide criterion and per deck criterion.
2) Extract ground-truth issue texts keyed by slide+criterion and by deck criterion.
3) For each slide criterion (non-service) and deck criterion:
   - Perform candidate generation (BM25 prefilter) between predicted and ground-truth lists.
   - Optionally adjudicate top candidates with LLM.
   - Normalize scores and run greedy, conflict-free assignment.
   - Emit confusion entries: matched → TP, unmatched predicted → FP, unmatched ground truth → FN.
4) Add FN entries for any remaining ground-truth issues with no predicted entry at all (by key).

## Detailed mechanics
### Candidate generation
- Tokenize each ground-truth issue (lowercase, alnum tokens) and build BM25 index:
  - Document frequency per term.
  - IDF per term: `(N - df + 0.5) / (df + 0.5)` (clamped to non-negative).
  - Average document length.
- For each predicted issue:
  - Tokenize predicted text.
  - Compute BM25 score against each ground-truth doc using k1=1.5, b=0.75, length normalization.
  - Keep top-N (default 3) scoring ground-truth indices as candidates `(pred_idx, gt_idx, score)`.

### Optional LLM adjudication
- If LLM is available, each candidate is rechecked:
  - Prompt asks if predicted issue and ground-truth issue are semantically equivalent (same concern), with examples.
  - Structured output `IssueMatchResult` with confidence.
  - If LLM says no match → score set to 0; if yes → score set to 1.
  - Calls are semaphore-limited by `_match_semaphore`.

### Score normalization
- Each candidate score is converted to `score / (score + 1)` (keeps 0..1, higher is better).

### Greedy, conflict-free assignment
- Candidates are sorted descending by normalized score.
- Threshold: 0.55 when LLM used, else 0.35.
- Iterate candidates:
  - Skip if score < threshold.
  - Skip if predicted index or ground-truth index already matched.
  - Otherwise accept and mark both as matched.
- Outputs:
  - `matches`: list of `(pred_idx, gt_idx, score)`.
  - `unmatched_pred`: predicted indices not matched.
  - `unmatched_gt`: ground-truth indices not matched.

### Confusion entry emission (slide-level)
- For each accepted match → TP with the paired predicted and ground-truth issue text.
- For each unmatched predicted → FP with that predicted issue text.
- For each unmatched ground-truth → FN with that ground-truth issue text.
- Any slide+criterion key present in ground truth but absent in predicted evaluations produces FN entries (one per ground-truth issue).

### Confusion entry emission (deck-level)
- Same matching and labeling logic as slide-level but keyed only by criterion (no slide_id).
- Deck criteria present in ground truth but missing in predicted evaluations produce FN entries (one per issue).

### Labels used
- TP: predicted=True, ground_truth=True (matched pair)
- FP: predicted=True, ground_truth=False (unmatched predicted)
- FN: predicted=False, ground_truth=True (unmatched ground truth)
- TN is never produced.

## Controls and limits
- Top-N per predicted issue (default 3) to avoid exhaustive pairing.
- Semaphore limits concurrent LLM adjudication calls.
- Threshold prevents low-similarity pairs from matching.

## Fail-safes
- If no LLM, matching falls back to BM25-only scoring and normalized threshold.
- If tokenization yields empty query, candidate search is skipped for that predicted issue.
- If no predicted or no ground-truth issues, outputs are empty match list and all items go to FP or FN accordingly.

