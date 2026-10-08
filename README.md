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
        ├─ 5. Execute       Run the script in an isolated sandbox: local Docker or a Modal Sandbox (`uv run` inside)
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
├── render.yaml                  # Render blueprint (deploys with the Modal sandbox)
├── static/
│   └── index.html               # Small browser page (type questions, attach files)
├── sandbox/
│   └── Dockerfile               # Image for the local Docker sandbox
├── services/
│   ├── llm_utils.py             # Gemini + OpenAI (via AI Pipe) clients with fallback
│   ├── pipelines_utils.py       # Setup, code generation, execution, debugging, final check
│   ├── sandbox_modal.py         # Modal Sandbox backend (used when SANDBOX_BACKEND=modal)
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
- One sandbox backend for generated code:
  - [Docker](https://docs.docker.com/get-docker/) for running locally (default), or
  - a free [Modal](https://modal.com) account for deployment (Render cannot run Docker containers)
- A Gemini API key
- An [AI Pipe](https://aipipe.org) token (used for the GPT-4o-mini calls)

## Setup

```bash
git clone 
cd data-analyst-agent

# Install dependencies
uv pip install -r requirements.txt
# or: pip install -r requirements.txt
```

Build the sandbox image (one time):

```bash
docker build -t data-analyst-sandbox sandbox/
```

Create a `.env` file in the project root:

```env
GEMINI_KEY=your_gemini_api_key
AIPIPE_TOKEN=your_aipipe_token
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

Multipart form upload. Provide the analysis request either as a `questions.txt` file (the first file in the form) or typed into a `questions` text field, plus any data files the questions refer to. If `questions` is filled in, every uploaded file is treated as a data file.

```bash
curl -X POST http://localhost:8000/api \
  -F "questions.txt=@questions.txt" \
  -F "data.csv=@data.csv"
```

Typing the questions instead of uploading a file:

```bash
curl -X POST http://localhost:8000/api \
  -F "questions=How many rows are in data.csv? Respond with a JSON array of strings." \
  -F "data.csv=@data.csv"
```

Or open **http://localhost:8000/ui** for a simple page with a text box for the questions and an optional file picker.

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

## Sandboxing

All LLM-generated code runs in an isolated sandbox instead of on the host. Pick the backend with the `SANDBOX_BACKEND` environment variable:

| `SANDBOX_BACKEND` | Where code runs | Use for |
|---|---|---|
| `docker` (default) | A throwaway local Docker container | Running on your own machine |
| `modal` | A [Modal Sandbox](https://modal.com/docs/guide/sandbox) (remote, gVisor-isolated) | Deploying on Render or anywhere without Docker |

### Docker backend

- Only two things are mounted: `workspace/` (uploaded data + task outputs, read/write) and the script's folder (read-only). `.env`, `main.py` and the rest of the project are not visible, and no environment variables are passed in, so API keys are not exposed.
- Non-root user, all capabilities dropped, `no-new-privileges`, read-only root filesystem.
- Limits: 1 GB RAM, 1 CPU, 256 processes, 300 s timeout (the container is killed on timeout).
- Package downloads are cached in a Docker volume (`sandbox-uv-cache`) so repeated runs are fast.

### Modal backend

- One sandbox is created per request and shared by all tasks and retries of that request, so a task can read files written by an earlier task. It is terminated when the request ends (success or failure) and has a hard lifetime of 20 minutes in case the server dies.
- Uploaded files are copied into the sandbox's `/workspace`. After each script, new or changed files are copied back to the local `workspace/`, so the rest of the pipeline is unchanged.
- The sandbox gets no secrets and no environment variables. Your Gemini/AI Pipe keys and the Modal token never enter it.
- Limits: 1 CPU, 1 GB RAM, 300 s per script.
- Dependencies are installed with `uv run` inside the sandbox on every request, which adds a few seconds.
- Setup: `pip install modal`, create a token at modal.com (or run `modal token new` locally), and set `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`. The first request builds the sandbox image, which takes about a minute; later ones reuse it.
- Cost: Modal's free Starter plan includes $30 of compute credits per month, billed per second (sandboxes are priced higher than regular functions, so check their pricing page). `DAILY_LIMIT` in `services/llm_utils.py` caps LLM usage per day.

In both backends, network access is left on because tasks often scrape websites.

## Deploying on Render (with Modal)

1. Push the project to GitHub (keep `.env` out of the repo).
2. In Render, create a new **Blueprint** from the repo (it reads `render.yaml`), or a Web Service with the same settings:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Set these environment variables in Render:
   - `GEMINI_KEY`, `AIPIPE_TOKEN`
   - `SANDBOX_BACKEND=modal`
   - `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`
4. Open `https://<your-service>.onrender.com/ui`.

The Render service itself never executes generated code. It only calls Modal. Note that Render's free instances spin down when idle, so the first request after a pause is slow.

## Generated artifacts

During a run the agent writes these to the working directory (all git-ignored):

- `questions.txt` – the uploaded question file
- `tasks.json` – the task breakdown
- `workspace/` – uploaded data files and each task's output files (reset on every request)
- `codes/taskN/code{i}.py` – each generated script and its debug revisions
- `codes/taskN/error{i}.txt` – stderr from failed attempts

## Current status / known limitations
- Generated code is sandboxed (Docker or Modal), but the sandbox still has outbound network access, so it could send out the data you uploaded. Demo-grade, not hardened.
- Files returned from the sandbox are untrusted content and are parsed locally (pandas etc.) to build summaries.
- With the Modal backend, only files directly in `/workspace` are copied back (no subfolders), up to 50 MB each.
- CORS is configured to allow all origins.
- Debugging is capped at 2 retries per task.

## License

MIT – see [LICENSE](LICENSE).
