import os
import asyncio
import shutil
import subprocess
import uuid
import aiofiles
from pathlib import Path
import json
from PIL import Image


from services.get_metadata import summarize_csv, summarize_json, summarize_text, summarize_html
from services.llm_utils import (
    call_llm,
    call_gpt,
    LLMError
)

SANDBOX_IMAGE = "data-analyst-sandbox"  # built from sandbox/Dockerfile
SANDBOX_TIMEOUT = 300
WORKSPACE = "workspace"

def use_modal() -> bool:
    """SANDBOX_BACKEND=modal runs generated code in a Modal sandbox; default is the local Docker sandbox."""
    return os.getenv("SANDBOX_BACKEND", "docker").lower() == "modal"

async def cleanup_sandbox():
    """Called at the end of every request (even failed ones) so no remote sandbox is left running."""
    if use_modal():
        from services import sandbox_modal
        await sandbox_modal.close()

def workspace_path(name: str):
    """Resolve `name` inside WORKSPACE; return None if it would escape the folder (e.g. '../.env')."""
    root = os.path.abspath(WORKSPACE)
    path = os.path.abspath(os.path.join(root, name))
    try:
        return path if os.path.commonpath([root, path]) == root else None
    except ValueError:
        return None

async def setup(files):
    
    if not files:
        raise ValueError("At least one file is required.")
    typed = files.get("questions")
    if isinstance(typed, str) and typed.strip():
        # questions typed into the "questions" form field; every uploaded file is a data file
        questions_txt = typed
        file_names = [x for x, v in dict(files).items() if not isinstance(v, str)]
    else:
        file_names = [x for x,_ in (dict(files)).items()]
        if not file_names or isinstance(files[file_names[0]], str):
            raise ValueError("Questions are required: upload questions.txt or fill in the 'questions' field.")
        file = files[file_names[0]]
        questions_txt = (await file.read()).decode("utf-8")
    with open("questions.txt", "w", encoding="utf-8") as f:
        f.write(questions_txt)

    task_breakdown_file = os.path.join("prompts", "task_breakdown.txt")
    async with aiofiles.open(task_breakdown_file, "r", encoding="utf-8") as f:
        task_breakdown_prompt = (await f.read()).strip()

    combined_prompt = f"{task_breakdown_prompt}\nTask to analyze:\n{questions_txt}"

    print("calling gemini to create tasks")
    gemini_task = asyncio.create_task(call_llm(combined_prompt, "gemini"))

    all_metadata = await warmup(files, file_names)

    gemini_response = await gemini_task

    with open("tasks.json", "w", encoding="utf-8") as resp_file:
            resp_file.write('\n'.join(gemini_response.splitlines()[1:-1]))

    return all_metadata

async def warmup(files,file_names):

    all_metadata = {}

    loop = asyncio.get_running_loop()

    if os.path.exists("codes"):
        await loop.run_in_executor(None, shutil.rmtree, "codes")

    await loop.run_in_executor(None, shutil.rmtree, WORKSPACE, True)
    os.makedirs(WORKSPACE, exist_ok=True)

    for file in file_names:
        if "questions.txt" == file:
            continue
        safe_name = os.path.basename(file.replace("\\", "/"))  # strip any directory parts ("../x" -> "x")
        if safe_name in ("", ".", ".."):
            continue
        async with aiofiles.open(os.path.join(WORKSPACE, safe_name), "wb") as out_file:
            content = await files[file].read()
            await out_file.write(content)
            await out_file.seek(0)

            all_metadata[safe_name] = await get_metadata(safe_name)

    if use_modal():
        from services import sandbox_modal
        await sandbox_modal.start(WORKSPACE)

    print("all files set up")
    return all_metadata

def get_image_base64(image_path):
    import base64
    import mimetypes
    try:
        # Guess the correct MIME type from the file extension
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None:
            mime_type = "application/octet-stream"

        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode("utf-8")

        # Return full data URI
        return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        return str(e)
    
async def summarize_image(path):

    try:
        with Image.open(path) as img:
            summary = {
                "type": "image",
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "info": img.info,
            }


        with open("prompts/get_image_prompt.txt", "r", encoding="utf-8") as f:
            get_image_prompt = f.read()

        image_prompt = await call_llm(f"{get_image_prompt}", "gemini")
        image_base64 = get_image_base64(path)
        image_data = await call_gpt(image_prompt, image_base64)

        if "error" in image_data:
            raise RuntimeError(image_data["message"])

        summary["description"] = image_data["content"]

        return json.dumps(summary, indent=2, default=str)

    except Exception as e:
        return json.dumps({
            "error": str(e)
        }, indent=2)

async def get_metadata(file_name:str):

    _, ext = os.path.splitext(file_name)

    ext = ext.lower()

    path = workspace_path(file_name)

    if path and os.path.exists(path):
        if ext == ".csv":
            metadata = summarize_csv(path)
        elif ext == ".json":
            metadata = summarize_json(path)
        elif ext in [".txt", ".md"]:
            metadata = summarize_text(path)
        elif ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"]:
            metadata = await summarize_image(path)
        elif ext.lower() in [".html", ".htm"]:
            metadata = summarize_html(path)
        else:
            metadata = "file contents unknown"
    else:
        metadata = "file does not exist"

    return metadata

async def write_code(task,metadata=None):
    writing_prompt_file = os.path.join("prompts", "writing_code.txt")

    with open(writing_prompt_file, "r") as f:
        writing_prompt = f.read()

    if metadata:
        prompt = f"{writing_prompt}\n{task}\nFile structures:{metadata}"

    else:
        prompt = f"{writing_prompt}\n{task}"

    print(f"writing code for task {task['id']}")
    response = await call_llm(prompt, "gpt")

    code = await include_dependencies(response)

    code = quick_format(code)

    file_path = f"codes/task{task['id']}/code0.py"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as code_file:
        code_file.write(code)

    return {
        "file_path": file_path,
    }

async def include_dependencies(response):

    promp_file = os.path.join("prompts", "include_dependencies.txt")

    with open(promp_file, "r") as f:
        prompt = f.read()

    print(f"including deps")
    response = await call_llm(f"{prompt}\n{response}", "gpt")

    return response

async def execute_code(file_path: str):
    if use_modal():
        from services import sandbox_modal
        print(f"running {file_path} in modal sandbox")
        return await sandbox_modal.run(file_path, WORKSPACE)

    print(f"running {file_path} in docker sandbox")
    os.makedirs(WORKSPACE, exist_ok=True)
    code_dir = Path(file_path).resolve().parent
    container_name = f"sandbox-{uuid.uuid4().hex[:8]}"

    cmd = [
        "docker", "run", "--rm", "--name", container_name,
        # resource limits
        "--memory", "1g", "--cpus", "1", "--pids-limit", "256",
        # lock the container down
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:rw,exec,size=256m",
        # only these are visible inside: the data workspace (rw), the script (ro), uv's package cache
        "--mount", f"type=bind,src={Path(WORKSPACE).resolve()},dst=/workspace",
        "--mount", f"type=bind,src={code_dir},dst=/code,readonly",
        "--mount", "type=volume,src=sandbox-uv-cache,dst=/uv-cache",
    ]
    if hasattr(os, "getuid"):  # keep files in workspace/ owned by the host user
        cmd += ["--user", f"{os.getuid()}:{os.getgid()}"]
    cmd += [SANDBOX_IMAGE, "uv", "run", "--no-project", f"/code/{Path(file_path).name}"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=SANDBOX_TIMEOUT
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.CalledProcessError as e:
        if e.returncode == 125:  # docker itself failed (daemon down, image missing...), not the script
            raise RuntimeError(f"Docker sandbox failed to start: {e.stderr}")
        return {
            "error": str(e),
            "stdout": e.stdout,
            "stderr": e.stderr,
            "returncode": e.returncode
        }

    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", container_name], capture_output=True)
        return {
            "error": "timeout",
            "stdout": "",
            "stderr": f"Execution timed out after {SANDBOX_TIMEOUT} seconds",
            "returncode": 124
        }

    except FileNotFoundError:
        raise RuntimeError("Docker is not installed or not on PATH.")

async def explain_error(code_file_path:str, error: str):
    explain_error_file = os.path.join("prompts", "explain_error.txt")

    with open(code_file_path, "r", encoding="utf-8") as code_file:
        code = code_file.read()

    with open(explain_error_file, "r", encoding="utf-8") as f:
        explain_error_prompt = f.read().strip()

    prompt = f"{explain_error_prompt}\nCode:\n{code}\nError:\n{error}"

    print(f"suggesting fix")
    response = await call_llm(prompt, "gpt")

    return response
    
async def debug_code(task, code_file_path: str, error: str, i: int = 1, metadata=None):

    debug_prompt_path = os.path.join("prompts", "debug_code.txt")
    output_file_path = os.path.join("codes", f"task{task['id']}", f"code{i}.py")

    with open(code_file_path, "r", encoding="utf-8") as code_file:
        code = code_file.read()

    with open(debug_prompt_path, "r", encoding="utf-8") as debug_file:
        debug_prompt = debug_file.read().strip()

    error_explained = await explain_error(code_file_path, error)

    if metadata:
        prompt = f"{debug_prompt}\nCode:\n{code}\nError:\n{error}\nTask:\n{task}\nFile structures:{metadata}\nSuggested fix:{error_explained}"

    else:
        prompt = f"{debug_prompt}\nCode:\n{code}\nError:\n{error}\nTask:\n{task}\nSuggested fix:{error_explained}"


    print(f"debugging code for task {task['id']}")
    if "ImportError:" in error or "ModuleNotFoundError:" in error:
        code = await debug_dependencies(code,error.strip().split("\n")[-1])
    else:
        response = await call_llm(prompt, "gpt")
        code = await include_dependencies(response)

    code = quick_format(code)

    with open(output_file_path, "w", encoding="utf-8") as code_file:
        code_file.write(code)

    return {"message": f"Debugged code saved to {output_file_path}"}

async def debug_dependencies(response,error):

    promp_file = os.path.join("prompts", "debug_dependencies.txt")

    with open(promp_file, "r") as f:
        prompt = f.read()

    response = await call_llm(f"{prompt}\n{response}\n{error}", "gpt")

    return response

async def debug_new(task, code_file_path:str, error: str, i: int = 1):
    
    debug_file = os.path.join("prompts", "debug_new.txt")
    output_file_path = os.path.join("codes", f"task{task['id']}", f"code{i}.py")

    with open(code_file_path, "r", encoding="utf-8") as code_file:
        code = code_file.read()

    with open(debug_file, "r", encoding="utf-8") as f:
        debug_prompt = f.read().strip()

    response = await call_llm(f"{debug_prompt}\nCode:\n{code}\nError:\n{error}","gpt")

    with open(output_file_path, "w", encoding="utf-8") as code_file:
        code = '\n'.join(response.splitlines()[1:-1])
        code_file.write(code)

    return {"message": f"Debugged code saved to {output_file_path}"}


async def read_form_value(value):
    """Text of a form value: plain text as-is, uploads re-read from the start; binary files become a placeholder."""
    if isinstance(value, str):
        return value
    await value.seek(0)  # setup/warmup already read this upload once
    raw = await value.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary file, {len(raw)} bytes>"

async def final_check(output_file,files):
    print("cooking final result")
    output_path = workspace_path(output_file)
    if not output_file.lower().endswith(".txt") or not output_path or not os.path.exists(output_path):
        print("op file is not a json")
        with open("prompts/generate_dummy.txt", "r", encoding="utf-8") as f:
            prompt = f.read().strip()

        file_names = [x for x,_ in (dict(files)).items()]
        file_contents = {file: await read_form_value(files[file]) for file in file_names}

        response = await call_llm(f"{prompt}\nFiles with their contents:\n{file_contents}", "gemini")

        final_text = response.strip()

    else:
        with open(output_path, "r", encoding="utf-8") as f:
            final_text = f.read()

    return final_text

def quick_format(code):
    if code.startswith("```"):
        code = '\n'.join(code.splitlines()[1:])
    if code.endswith("```"):
        code = '\n'.join(code.splitlines()[:-1])
    
    return code