# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi",
#   "uvicorn",
#   "python-dotenv",
#   "google",
#   "python-multipart",
#   "httpx",
#   "beautifulsoup4",
#   "playwright",
#   "pandas",
#   "asyncio",
#   "httpx",
#   "tiktoken",
#   "pydantic",
#   "aiofiles",
#   "pillow",
#   "numpy",
#   "scipy",
#   "matplotlib",
#   "lxml",
#   "duckdb",
#   "networkx",
#   "seaborn",
#   "datetime",
# ]
# ///

import os
import sys
import json
import time
import uuid
import asyncio
import subprocess
import contextlib
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from dotenv import load_dotenv
from pathlib import Path
from services.llm_utils import daily_budget_exceeded, LLMError

from services.pipelines_utils import (
    setup,
    write_code,
    execute_code,
    debug_code,
    get_metadata,
    final_check,
    cleanup_sandbox,
    use_modal,
    SANDBOX_IMAGE
)

# ---- startup messages (printed here, replayed by the frontend via GET /boot) ----

START_TIME = time.time()
BOOT_LOG = []

def boot(msg: str, level: str = "info"):
    BOOT_LOG.append({"t": round(time.time() - START_TIME, 3), "level": level, "msg": msg})
    print(f"[boot {time.strftime('%H:%M:%S')}] {msg}", flush=True)

boot(f"data-analyst-agent starting - python {sys.version.split()[0]}")

if load_dotenv():
    boot(".env loaded", "ok")
else:
    boot(".env not found - using the process environment", "warn")

if not os.getenv("GEMINI_KEY"):
    boot("GEMINI_KEY missing - task breakdown will fail", "warn")
if not os.getenv("AIPIPE_TOKEN"):
    boot("AIPIPE_TOKEN missing - every request will be refused", "warn")

boot(f"sandbox backend: {'modal' if use_modal() else 'docker'}", "ok")

_prompts = list(Path("prompts").glob("*.txt"))
if _prompts:
    boot(f"{len(_prompts)} prompt templates loaded", "ok")
else:
    boot("prompts/ not found - start the server from the backend folder", "error")

app = FastAPI(title="Data Analyst Agent")
boot("FastAPI app created", "ok")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
boot("CORS middleware enabled", "ok")

@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    return JSONResponse(
        status_code=503,
        content={
            "error": True,
            "message": exc.message,
            "model": exc.model,
            "type": exc.type
        }
    )

def _noop(level, msg):
    pass

async def run_code(file_path):
    # The docker backend blocks on subprocess.run(); run it in a thread so the server
    # (and the live progress stream) stays responsive while generated code executes.
    if use_modal():
        return await execute_code(file_path)
    return await asyncio.to_thread(asyncio.run, execute_code(file_path))

def _stderr_tail(text, lines=4):
    return [l.strip()[:200] for l in (text or "").strip().splitlines()[-lines:] if l.strip()]

async def analyze(all_metadata, emit=_noop):
    try:
        with open("tasks.json", "r", encoding="utf-8") as resp_file:
            tasks = json.load(resp_file)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="tasks.json not found.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error decoding tasks.json.")

    total = len(tasks["tasks"])
    emit("ok", f"{total} task(s) planned")
    for t in tasks["tasks"]:
        emit("plan", f"task {t.get('id')}: {t.get('name', '')}")

    for task in tasks["tasks"]:

        task_started = time.time()
        emit("step", f"task {task['id']}/{total} - {task.get('name', '')}")
        
        metadata = []

        if task["files_for_reference"]:

            metadata = [
                {key: value}
                for key, value in all_metadata.items()
                if key in task["files_for_reference"]
            ]

            task["files_for_reference"] = [
                key
                for x in metadata
                for key, value in x.items()
                if value != "file does not exist"
            ]

        response = await write_code(task, metadata)
        code0 = f"codes/task{task['id']}/code0.py"
        emit("ok", f"code0.py written ({_line_count(code0)} lines)")

        started = time.time()
        response = await run_code(f"codes/task{task['id']}/code0.py")

        if response["returncode"] == 0:
            emit("ok", f"code0.py ran clean in {time.time() - started:.1f}s")

        if response["returncode"] != 0:
            emit("warn", f"code0.py failed (exit {response['returncode']})")
            for l in _stderr_tail(response["stderr"]):
                emit("stderr", l)
            i = 0
            with open(f"codes/task{task['id']}/error{i}.txt", "w", encoding="utf-8") as error_file:
                error_file.write(response["stderr"])
            while response["returncode"] != 0 and i < 2:
                i += 1
                emit("info", f"retry {i}/2 - asking the model to fix the code")
                response = await debug_code(task, f"codes/task{task['id']}/code{i-1}.py", response["stderr"], i, metadata)
                started = time.time()
                response = await run_code(f"codes/task{task['id']}/code{i}.py")
                if response["returncode"] != 0:
                    emit("warn", f"code{i}.py failed (exit {response['returncode']})")
                    for l in _stderr_tail(response["stderr"]):
                        emit("stderr", l)
                    with open(f"codes/task{task['id']}/error{i}.txt", "w", encoding="utf-8") as error_file:
                        error_file.write(response["stderr"])
                else:
                    emit("ok", f"code{i}.py ran clean in {time.time() - started:.1f}s")

            # if response["returncode"] != 0:
            #     return "Task processed unsuccessfully"  # FOR TESTING PURPOSES ONLY
            if response["returncode"] != 0:
                emit("warn", f"task {task['id']} still failing after 2 retries - moving on")

        if task["output_file_name"]:
            metadata = await get_metadata(task["output_file_name"])
            all_metadata[task["output_file_name"]] = metadata
            emit("ok", f"task {task['id']} done in {time.time() - task_started:.1f}s -> {task['output_file_name']}")
        else:
            emit("ok", f"task {task['id']} done in {time.time() - task_started:.1f}s")

    return all_metadata,tasks["tasks"][-1]["output_file_name"]

def _line_count(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0

# API Endpoints

@app.get("/")
async def root():
    return {"Server": "Healthy"}

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")

global_lock = asyncio.Lock()

@app.post("/api")
async def api(request: Request):
    async with global_lock:

        if await daily_budget_exceeded():
            raise LLMError({
                "error": True,
                "message": "Daily AI budget has been reached",
                "code": 429,
                "type": "DailyBudgetExceeded",
                "model": "gpt-4o-mini"
            })
            
        try:
            form = await request.form()
            all_metadata = await setup(form)
            all_metadata,final_file = await analyze(all_metadata)
            print(all_metadata)
            return await final_check(final_file,form)
        finally:
            await cleanup_sandbox()

# ---- live progress: GET /boot and POST /api/stream ----------------------------

def _run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""

def check_sandbox():
    """Live checks of whatever will execute the generated code."""
    if use_modal():
        have = bool(os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET")) \
            or (Path.home() / ".modal.toml").exists()
        if have:
            return [{"level": "ok", "msg": "modal credentials found"}]
        return [{"level": "error", "msg": "modal credentials missing - set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET"}]

    code, version = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if code != 0:
        return [{"level": "error", "msg": "docker is not reachable - is Docker running?"}]
    checks = [{"level": "ok", "msg": f"docker daemon reachable (v{version})"}]
    code, _ = _run(["docker", "image", "inspect", SANDBOX_IMAGE])
    if code == 0:
        checks.append({"level": "ok", "msg": f"sandbox image '{SANDBOX_IMAGE}' found"})
    else:
        checks.append({"level": "error", "msg": f"sandbox image missing - run: docker build -t {SANDBOX_IMAGE} sandbox/"})
    return checks

@app.get("/boot")
async def boot_status():
    checks = await asyncio.to_thread(check_sandbox)
    return {
        "boot": BOOT_LOG,
        "checks": checks,
        "ok": all(c["level"] != "error" for c in checks),
        "uptime": round(time.time() - START_TIME, 1),
    }

def _secrets():
    keys = ("GEMINI_KEY", "AIPIPE_TOKEN", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")
    return [v for v in (os.getenv(k) for k in keys) if v and len(v) >= 8]

def _clean(text: str) -> str:
    for secret in _secrets():
        text = text.replace(secret, "***")
    return text

class _Tee:
    """Forwards each line printed by the pipeline (services/*) to the stream, and still prints it."""
    SKIP = ("today_cost",)   # don't expose spend

    def __init__(self, real, emit):
        self.real, self.emit, self.buf = real, emit, ""

    def write(self, text):
        self.real.write(text)
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            line = line.strip()
            if line and not line.startswith(self.SKIP):
                self.emit("agent", line[:240])
        return len(text)

    def flush(self):
        self.real.flush()

    def __getattr__(self, name):
        return getattr(self.real, name)

@contextlib.contextmanager
def tee_prints(emit):
    real = sys.stdout
    sys.stdout = _Tee(real, emit)
    try:
        yield
    finally:
        sys.stdout = real

@app.post("/api/stream")
async def api_stream(request: Request):
    # Same work as /api, but every step is sent as it happens (one JSON object per line).
    form = await request.form()
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    rid = uuid.uuid4().hex[:6]
    t0 = time.time()

    def put(event):
        event["t"] = round(time.time() - t0, 3)
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def emit(level, msg):
        msg = _clean(msg)
        if level not in ("agent",):   # agent lines are already echoed by the tee
            print(f"[run {rid}] {msg}", file=sys.__stdout__, flush=True)
        put({"type": "log", "level": level, "msg": msg})

    def fail(status, msg):
        print(f"[run {rid}] ERROR {status}: {msg}", file=sys.__stdout__, flush=True)
        put({"type": "error", "status": status, "msg": _clean(msg)})

    async def pipeline():
        try:
            n_files = sum(1 for v in dict(form).values() if not isinstance(v, str))
            emit("info", f"request {rid} received - {n_files} data file(s)")

            if global_lock.locked():
                emit("warn", "another analysis is running - waiting for it to finish ...")
            async with global_lock:
                try:
                    emit("info", "checking daily AI budget ...")
                    if await daily_budget_exceeded():
                        fail(429, "Daily AI budget has been reached")
                        return
                    emit("ok", "budget ok")

                    checks = await asyncio.to_thread(check_sandbox)
                    for c in checks:
                        emit(c["level"], c["msg"])
                    if any(c["level"] == "error" for c in checks):
                        fail(503, "sandbox is not available")
                        return

                    with tee_prints(emit):
                        all_metadata = await setup(form)
                        emit("ok", f"setup finished - {len(all_metadata)} data file(s) summarised")
                        all_metadata, final_file = await analyze(all_metadata, emit)
                        emit("info", f"final check on {final_file} ...")
                        output = await final_check(final_file, form)

                    emit("ok", f"done in {time.time() - t0:.1f}s")
                    put({"type": "result", "output": output})
                finally:
                    await cleanup_sandbox()
        except LLMError as e:
            fail(503, e.message)
        except HTTPException as e:
            fail(e.status_code, str(e.detail))
        except ValueError as e:
            fail(400, str(e))
        except Exception:
            traceback.print_exc()
            fail(500, "internal error - see the server logs")
        finally:
            put({"type": "end"})

    task = asyncio.create_task(pipeline())

    async def lines():
        try:
            while True:
                event = await queue.get()
                if event["type"] == "end":
                    break
                yield json.dumps(event) + "\n"
        finally:
            if not task.done():
                task.cancel()   # client left / pressed ^C: stop spending tokens, release the lock

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

boot("ready - waiting for requests", "ok")

# local testing

if __name__ == "__main__":
    import uvicorn
    import json
    print("Starting server at http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
