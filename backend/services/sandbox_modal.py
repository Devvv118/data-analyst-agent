"""
One sandbox is created per API request (see warmup) and reused for every task/retry of that request,
so files written by one task are still there for the next. After each script runs, new or changed
files are copied back into the local workspace/ so the rest of the pipeline works unchanged.
"""
import os
import asyncio
from pathlib import Path

import modal

APP_NAME = "data-analyst-sandbox"
SANDBOX_LIFETIME = 1200          # seconds; the sandbox destroys itself even if this server crashes
EXEC_TIMEOUT = 300               # seconds allowed for a single script
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024

_sb = None
_seen = {}   # name -> (size, modified_time) of files already in sync with the local workspace


def _image():
    # built once by Modal, then cached
    return (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install("uv")
        .run_commands("mkdir -p /workspace /code")
    )


async def start(workspace_dir: str):
    """Create the sandbox and upload everything currently in the local workspace."""
    global _sb, _seen
    await close()
    app = await modal.App.lookup.aio(APP_NAME, create_if_missing=True)
    _sb = await modal.Sandbox.create.aio(
        app=app,
        image=_image(),
        timeout=SANDBOX_LIFETIME,
        workdir="/workspace",
        cpu=1,
        memory=1024,
    )
    for name in os.listdir(workspace_dir):
        path = os.path.join(workspace_dir, name)
        if os.path.isfile(path):
            await _sb.filesystem.copy_from_local.aio(path, f"/workspace/{name}")
    _seen = {}
    await _sync_down(workspace_dir, download=False)  # remember the uploaded files as "already in sync"
    print("modal sandbox ready")


async def _sync_down(workspace_dir: str, download: bool = True):
    """Copy files that are new or changed in the sandbox's /workspace back to the local workspace."""
    for info in await _sb.filesystem.list_files.aio("/workspace"):
        if not info.is_file():
            continue
        name = os.path.basename(info.name)
        key = (info.size, info.modified_time)
        if _seen.get(name) == key:
            continue
        _seen[name] = key
        if download and info.size <= MAX_DOWNLOAD_BYTES:
            await _sb.filesystem.copy_to_local.aio(f"/workspace/{name}", os.path.join(workspace_dir, name))


async def run(script_path: str, workspace_dir: str):
    """Run one generated script in the sandbox. Returns the same dict shape as the Docker backend."""
    if _sb is None:
        raise RuntimeError("Modal sandbox was not started.")

    script = Path(script_path)
    remote = f"/code/{script.parent.name}/{script.name}"      # e.g. /code/task1/code0.py
    await _sb.filesystem.copy_from_local.aio(str(script), remote)

    try:
        proc = await _sb.exec.aio(
            "uv", "run", "--no-project", remote,
            workdir="/workspace",
            timeout=EXEC_TIMEOUT,
        )
        stdout, stderr = await asyncio.wait_for(
            asyncio.gather(proc.stdout.read.aio(), proc.stderr.read.aio()),
            timeout=EXEC_TIMEOUT + 30,
        )
        returncode = await proc.wait.aio()
    except asyncio.TimeoutError:
        return {
            "error": "timeout",
            "stdout": "",
            "stderr": f"Execution timed out after {EXEC_TIMEOUT} seconds",
            "returncode": 124,
        }

    await _sync_down(workspace_dir)

    result = {"stdout": stdout, "stderr": stderr, "returncode": returncode}
    if returncode != 0:
        result["error"] = f"Script exited with code {returncode}"
        if not stderr.strip():
            result["stderr"] = f"Script exited with code {returncode} (it may have hit the {EXEC_TIMEOUT}s time limit)."
    return result


async def close():
    global _sb
    if _sb is not None:
        try:
            await _sb.terminate.aio()
        except Exception as e:
            print(f"could not terminate modal sandbox: {e}")
        _sb = None
