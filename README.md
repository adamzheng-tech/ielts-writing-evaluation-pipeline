# IELTS Writing Evaluation Pipeline

A Python/FastAPI prototype that returns four dimension scores and writing feedback for one IELTS essay. It sends concurrent requests to an OpenAI-compatible API and stores results in SQLite. Scores are **uncalibrated estimates, not official IELTS results**.

## What works

- Task 2: a real text request has returned four validated dimension results and been saved to SQLite.
- Task 1: accepts JPEG, PNG or WebP prompt images in the client and API; a live image request has not yet been verified.
- Task 1 uses *Task Achievement*; Task 2 uses *Task Response*. Both also use *Coherence and Cohesion*, *Lexical Resource*, and *Grammatical Range and Accuracy*.

The model currently receives brief criteria summaries, not the complete band-by-band IELTS descriptors. This prototype has not been calibrated against examiner-scored essays.

## Run locally

Requires Python 3.10+ and an API key for an endpoint and model compatible with the project's Chat Completions requests. The selected model must support image input for Task 1.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your own key, base URL and model. Never commit `.env`.

In one terminal, start the server:

```bash
uvicorn api:app --reload
```

In another terminal, from the project directory:

```bash
source .venv/bin/activate
python3 client.py --input examples/task2.md
```

The Markdown client reads `student_id` and `task_type` from front matter, `# Prompt Text` and `# Essay Text` from the body, and optional `![[image.png]]` references under `# Prompt Image`. See `examples/task2.md`. The health endpoint is `http://127.0.0.1:8000/health`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

These local tests use fake model calls. Passing tests does not confirm provider availability, Task 1 image support, or scoring accuracy.

## Next steps

- Verify a real Task 1 image request and make model timeouts configurable.
- Add versioned, band-specific scoring descriptors and calibrate estimates against examiner-scored essays.
- Strengthen response validation, error handling and parser tests.
