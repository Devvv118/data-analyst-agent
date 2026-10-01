# Data Analyst Agent

An LLM-powered agent, served over a FastAPI endpoint, that takes a natural-language data-analysis question (plus optional data files), breaks it into smaller tasks, writes and runs Python code for each task, automatically debugs failures, and returns the answers as JSON.

## How it works

```
POST /api  (questions.txt + optional data files)
   │
   ├─ 1. Setup          Save uploads, summarize each file (CSV / JSON / text / HTML / image)
   ├─ 2. Task breakdown Gemini splits the question into ordered, self-contained tasks (tasks.json)
   │
   └─ For each task:
        ├─ 3. Modify task   Rewrite the task description using the real file structures
        ├─ 4. Write code    GPT generates a Python script (codes/taskN/code0.py)
        ├─ 5. Execute       Run the script in an isolated `uv run` environment
        ├─ 6. Debug loop    On failure: explain the error, regenerate code (up to 2 retries)
        └─ 7. Metadata      Summarize the task's output file so later tasks can use it
   │
   └─ 8. Final check    Validate/format the answer JSON (e.g. base64 image data URIs);
                        fall back to a best-effort Gemini answer if no result file exists
```

Each step is driven by a prompt template in [`prompts/`](prompts/), so behavior can be tuned without touching the code.

## Project structure

```
data-analyst-agent/
├── main.py                      # FastAPI app, /api endpoint, task orchestration loop
├── requirements.txt             # Python dependencies
├── services/
│   ├── llm_utils.py             # Gemini + OpenAI (via AI Pipe) clients with fallback
│   ├── pipelines_utils.py       # Setup, code generation, execution, debugging, final check
│   └── get_metadata.py          # File summarizers (csv, json, txt, html, image)
└── prompts/                     # Prompt templates for each pipeline stage
    ├── task_breakdown.txt
    ├── modify_task.txt
    ├── writing_code.txt
    ├── include_dependencies.txt
    ├── debug_code.txt
    ├── debug_dependencies.txt
    ├── debug_new.txt
    ├── explain_error.txt
    ├── get_image_prompt.txt
    ├── generate_dummy.txt
    └── final_check.txt
```

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (generated scripts are executed with `uv run`)
- A Gemini API key
- An [AI Pipe](https://aipipe.org) token (used for the GPT-4o-mini calls)

## Setup

```bash
git clone <your-repo-url>
cd data-analyst-agent

# Install dependencies
uv pip install -r requirements.txt
# or: pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GEMINI_KEY=your_gemini_api_key
AIPIPE_TOKEN=your_aipipe_token
```

If generated code needs to scrape dynamic pages, you may also need Playwright (listed in the `main.py` script header but not in `requirements.txt`):

```bash
pip install playwright && playwright install
```

## Running

```bash
python main.py
```

The server starts at `http://0.0.0.0:8000`.

Health check:

```bash
curl http://localhost:8000/
# {"Server":"Healthy"}
```

## API

### `POST /api`

Multipart form upload. Include a `questions.txt` file with the analysis request, plus any data files the questions refer to.

```bash
curl -X POST http://localhost:8000/api \
  -F "questions.txt=@questions.txt" \
  -F "data.csv=@data.csv"
```

**Example `questions.txt`:**

```
Scrape the list of highest grossing films from Wikipedia:
https://en.wikipedia.org/wiki/List_of_highest-grossing_films

Respond with a JSON array of strings containing the answers.
1. How many $2 bn movies were released before 2020?
2. Which is the earliest film that grossed over $1.5 bn?
```

**Response:** a JSON document in the format requested by the questions. Requests are processed one at a time (a global lock serializes runs, since intermediate files are written to the working directory).

## Models and fallbacks

| Purpose | Primary | Fallback |
| --- | --- | --- |
| Task breakdown, task rewriting | Gemini 2.5 Flash | GPT-4o-mini |
| Code writing, debugging, dependency fixes | GPT-4o-mini (via AI Pipe) | Gemini |
| Best-effort final answer | Gemini 2.5 Pro | — |

## Generated artifacts

During a run the agent writes these to the working directory (all git-ignored):

- `questions.txt` – the uploaded question file
- `tasks.json` – the task breakdown
- `codes/taskN/code{i}.py` – each generated script and its debug revisions
- `codes/taskN/error{i}.txt` – stderr from failed attempts

## Current status / known limitations

- In `main.py`, the `/api` handler currently has the `setup(...)` and `analyze(...)` calls **commented out** and goes straight to `final_check("final_answers.json", form)`. To run the full pipeline, uncomment those two lines.
- Generated code is executed locally via subprocess with no sandboxing. Run this in a container or otherwise isolated environment, and do not expose it publicly as-is.
- CORS is configured to allow all origins.
- Debugging is capped at 2 retries per task.

## License

MIT – see [LICENSE](LICENSE).
