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
import json
import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path
from services.llm_utils import daily_budget_exceeded, LLMError

from services.pipelines_utils import (
    setup,
    write_code,
    execute_code,
    debug_code,
    get_metadata,
    final_check,
    cleanup_sandbox
)

app = FastAPI(title="Data Analyst Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

async def analyze(all_metadata):
    try:
        with open("tasks.json", "r", encoding="utf-8") as resp_file:
            tasks = json.load(resp_file)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="tasks.json not found.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Error decoding tasks.json.")


    for task in tasks["tasks"]:
        
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

        response = await execute_code(f"codes/task{task['id']}/code0.py")

        if response["returncode"] != 0:
            i = 0
            with open(f"codes/task{task['id']}/error{i}.txt", "w", encoding="utf-8") as error_file:
                error_file.write(response["stderr"])
            while response["returncode"] != 0 and i < 2:
                i += 1
                response = await debug_code(task, f"codes/task{task['id']}/code{i-1}.py", response["stderr"], i, metadata)
                response = await execute_code(f"codes/task{task['id']}/code{i}.py")
                if response["returncode"] != 0:
                    with open(f"codes/task{task['id']}/error{i}.txt", "w", encoding="utf-8") as error_file:
                        error_file.write(response["stderr"])

            # if response["returncode"] != 0:
            #     return "Task processed unsuccessfully"  # FOR TESTING PURPOSES ONLY

        if task["output_file_name"]:
            metadata = await get_metadata(task["output_file_name"])
            all_metadata[task["output_file_name"]] = metadata

    return all_metadata,tasks["tasks"][-1]["output_file_name"]

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

# local testing

if __name__ == "__main__":
    import uvicorn
    import json
    print("Starting server at http://0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
