# API (Draft)

This API is a placeholder for the assistant runtime. The contract may change.

## Base URL

`/api/v1`

## POST /chat

Submit a user question and optional context.

Request (JSON):

```json
{
  "question": "How do I factor x^2 - 9?",
  "subject": "algebra",
  "language": "en",
  "answer_mode": "coach",
  "constraints": {
    "no_final_answer": true
  }
}
```

Response (JSON):

```json
{
  "answer": "Start by recognizing a difference of squares...",
  "citations": [
    {
      "source": "wikipedia",
      "title": "Difference of two squares",
      "url": "https://en.wikipedia.org/...",
      "license": "CC BY-SA 4.0"
    }
  ],
  "diagnostics": {
    "tool_calls": 3,
    "safety_flags": []
  }
}
```

Notes:
- `answer_mode` defaults to `coach` unless policy allows `solution_allowed`.
- `diagnostics` is optional and may be omitted in production responses.

## GET /health

Simple liveness probe.

Response (JSON):

```json
{ "status": "ok" }
```
