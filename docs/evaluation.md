# Evaluation (Draft)

Evaluation focuses on correctness, safety, and learning value.

## Datasets

- Curated homework-style questions by subject and difficulty
- Prompt injection test set (retrieval content with malicious instructions)
- Attribution test set (known Wikipedia/StackOverflow sources)

## Metrics

- Answer helpfulness (rubric, 1-5)
- Faithfulness to citations (supported claims only)
- Citation coverage (>= 1 citation when sources exist)
- Safety policy compliance (coach vs solution_allowed)
- Tool budget adherence (calls, bytes, timeouts)
- Latency (p50/p95)

## Review checklist

- Does the response teach and guide rather than just solve?
- Are citations present and accurate?
- Are unsupported claims removed or hedged?
- Are prompt injection attempts ignored?
- Are tool budgets respected?
