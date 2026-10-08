# Data Analyst Agent - terminal frontend

React + Vite + Tailwind 4, same terminal theme as the portfolio. Talks to `backend/main.py` only.

## Run

```bash
# 1. backend (terminal 1) - start it from inside backend/ (it reads prompts/ and writes codes/ relative to there)
cd backend
pip install -r requirements.txt
docker build -t data-analyst-sandbox sandbox/    # one time (or set SANDBOX_BACKEND=modal)
cp .env.example .env                              # fill in GEMINI_KEY and AIPIPE_TOKEN
python main.py                                    # http://localhost:8000

# 2. frontend (terminal 2)
cd frontend
npm install
npm run dev                                       # http://localhost:5173
```

Point the UI at another backend with `VITE_API_URL` (see `.env.example`).

## What it does

1. On load it calls `GET /boot`: the startup messages `main.py` printed, plus live sandbox checks
   (Docker daemon + sandbox image, or Modal credentials).
2. You type the **questions** and optionally attach **data files** (picker or drag-and-drop). `ctrl+enter` runs.
3. `POST /api/stream` streams one JSON line per step: setup, task plan, code written, sandbox run,
   errors and retries, final check. `^C` interrupts the run and stops the backend work.
4. The answer is rendered from the returned JSON: lists/objects as rows, base64 chart images inline,
   plus a collapsible raw-JSON view.

The original `POST /api` endpoint and the `/ui` page still work unchanged.
