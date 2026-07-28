import os
import signal
import subprocess
import sys
import time
import requests

from core.config import (
    CONTEXT_SIZE,
    LLAMA_CACHE_RAM_MB,
    LLAMA_CACHE_TYPE_K,
    LLAMA_CACHE_TYPE_V,
    LLAMA_FLASH_ATTN,
    LLAMA_GPU_LAYERS,
    LLAMA_SERVER,
    LLAMA_THREADS,
    MODEL_API_KEY,
    MODEL_API_KEY_FILE,
    MODEL_PATH,
    MODEL_REQUEST_HEADERS,
    PROMPT_CACHE_DIR,
    SERVER_HOST,
    SERVER_ALIAS,
    SERVER_LOG_FILE,
    SERVER_PORT,
    SERVER_URL,
)


_log_handle = None

# Tracked separately from start_server()'s return value so a Ctrl+C
# during the "Waiting for model to load..." loop -- before
# start_server() has returned anything to the caller -- can still
# find and kill the subprocess it just spawned, instead of leaking it.
_current_process = None
_OWNED_PID_ENV = "TORMENT_NEXUS_OWNED_SERVER_PID"
STARTUP_TIMEOUT = 300


def is_alive(timeout=2):
    """Is a llama-server already answering on our port?"""
    try:
        r = requests.get(
            SERVER_URL + "/v1/models",
            headers=MODEL_REQUEST_HEADERS,
            timeout=timeout,
        )
        return r.status_code == 200
    except Exception:
        return False


def accepts_unauthenticated_requests(timeout=2):
    """True only when a reachable model endpoint is missing API protection."""
    try:
        response = requests.get(
            SERVER_URL + "/v1/models",
            timeout=timeout,
        )
        return response.status_code == 200
    except Exception:
        return False


def active_server_model_id(timeout=2):
    """Return the authenticated server's advertised model id, if available."""
    try:
        response = requests.get(
            SERVER_URL + "/v1/models",
            headers=MODEL_REQUEST_HEADERS,
            timeout=timeout,
        )

        if response.status_code != 200:
            return None

        models = response.json().get("data", [])

        if not models or not isinstance(models[0], dict):
            return None

        model_id = models[0].get("id")
        return str(model_id) if model_id else None
    except Exception:
        return None


def start_server():
    """
    Launch llama-server, or reuse one that is already running.

    The reuse path is what makes self-editing restarts bearable. When
    the assistant reloads itself after an edit it leaves the model
    server up, so coming back takes a second instead of a full model
    load. It also stops a second server being spawned to fight over
    the same port.
    """
    global _log_handle, _current_process

    if is_alive():
        if accepts_unauthenticated_requests():
            raise RuntimeError(
                "An unauthenticated llama-server is already using "
                f"{SERVER_URL}. Stop that older server and launch TORMENT_NEXUS "
                "again so it can start the protected model endpoint."
            )

        if SERVER_ALIAS:
            active_alias = active_server_model_id()

            if active_alias != SERVER_ALIAS:
                found = active_alias or "no profile alias"
                raise RuntimeError(
                    "A different authenticated llama-server is already using "
                    f"{SERVER_URL}. Expected profile '{SERVER_ALIAS}', found "
                    f"'{found}'. Exit the other TORMENT_NEXUS profile before "
                    "starting this one."
                )

        print("Reusing the model server already running.")
        return None

    if not os.path.isfile(LLAMA_SERVER):
        raise RuntimeError(
            "llama-server was not found.\n"
            f"Expected: {LLAMA_SERVER}\n"
            "Build llama.cpp first, or set TORMENT_NEXUS_LLAMA_SERVER."
        )

    if not os.path.isfile(MODEL_PATH):
        raise RuntimeError(
            "The GGUF model was not found.\n"
            f"Expected: {MODEL_PATH}\n"
            "Set TORMENT_NEXUS_MODEL_PATH if it is stored elsewhere."
        )

    folder = os.path.dirname(SERVER_LOG_FILE)

    if folder:
        os.makedirs(folder, exist_ok=True)

    os.makedirs(PROMPT_CACHE_DIR, exist_ok=True)

    _log_handle = open(SERVER_LOG_FILE, "w", encoding="utf-8")

    print("Starting local AI server...")

    arguments = [
        LLAMA_SERVER,
        "-m", MODEL_PATH,
            # 8GB is the target RAM ceiling (Pi 5), even though this is
            # currently running on the Windows dev machine -- shared
            # with the OS, this Python process, and the memory
            # pipeline, not just the model. 4096 keeps the KV cache
            # modest. Raise it if you see comfortable headroom once
            # it's actually on the Pi; drop to 2048 if you see OOM
            # kills or heavy swapping instead.
            "-c", str(CONTEXT_SIZE),
            # This is a single-user assistant. One slot keeps the
            # stable persona prefix cached between turns instead of
            # cold-starting four separate slot caches, and prevents
            # background memory work from competing with chat.
        "-np", "1",
        "--host", str(SERVER_HOST),
        "--port", str(SERVER_PORT),
        "--cache-prompt",
        "--cache-ram", str(LLAMA_CACHE_RAM_MB),
        "--slot-save-path", PROMPT_CACHE_DIR,
    ]

    if MODEL_API_KEY_FILE:
        arguments.extend(("--api-key-file", MODEL_API_KEY_FILE))
    else:
        arguments.extend(("--api-key", MODEL_API_KEY))

    if LLAMA_THREADS is not None:
        arguments.extend(("-t", str(LLAMA_THREADS)))

    if LLAMA_GPU_LAYERS is not None:
        arguments.extend(("-ngl", str(LLAMA_GPU_LAYERS)))

    if LLAMA_FLASH_ATTN is not None:
        arguments.extend(("-fa", LLAMA_FLASH_ATTN))

    if LLAMA_CACHE_TYPE_K is not None:
        arguments.extend(("-ctk", LLAMA_CACHE_TYPE_K))

    if LLAMA_CACHE_TYPE_V is not None:
        arguments.extend(("-ctv", LLAMA_CACHE_TYPE_V))

    if SERVER_ALIAS:
        arguments.extend(("--alias", SERVER_ALIAS))

    try:
        process = subprocess.Popen(
            arguments,
            stdout=_log_handle,
            stderr=subprocess.STDOUT,
        )
    except Exception as error:
        if _log_handle:
            _log_handle.close()
            _log_handle = None

        raise RuntimeError(
            f"Could not launch llama-server at {LLAMA_SERVER}: {error}"
        ) from error

    _current_process = process
    # execv() keeps the environment but not Python's Popen object.
    # Preserve ownership so the reloaded assistant can still stop the
    # server cleanly when the user exits.
    os.environ[_OWNED_PID_ENV] = str(process.pid)

    print("Waiting for model to load...")

    dots = 0
    started_at = time.monotonic()

    while True:
        if is_alive(timeout=3):
            break

        exit_code = process.poll()

        if exit_code is not None:
            sys.stdout.write("\r" + " " * 20 + "\r")
            sys.stdout.flush()
            tail = _log_tail()
            stop_server(process)
            raise RuntimeError(
                f"llama-server exited during startup (code {exit_code}).\n"
                f"Log ({SERVER_LOG_FILE}):\n{tail}"
            )

        if time.monotonic() - started_at >= STARTUP_TIMEOUT:
            stop_server(process)
            raise RuntimeError(
                f"llama-server did not become ready within "
                f"{STARTUP_TIMEOUT} seconds.\n"
                f"Log ({SERVER_LOG_FILE}):\n{_log_tail()}"
            )

        dots = (dots + 1) % 4
        sys.stdout.write("\rLoading" + ("." * dots) + "   ")
        sys.stdout.flush()

        time.sleep(2)

    sys.stdout.write("\r" + " " * 20 + "\r")
    sys.stdout.flush()

    return process


def _log_tail(lines=15):
    """Best-effort read of the last few lines of the server log."""
    try:
        with open(SERVER_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().splitlines()
        return "\n".join(content[-lines:]) if content else "(log is empty)"
    except Exception as e:
        return f"(could not read log: {e})"


def stop_server(process=None):
    """
    Only stops a server this process started. A reused one is left
    alone -- something else owns it.

    Falls back to the process start_server() is currently launching
    when the caller doesn't have one yet -- see _current_process.
    """
    global _log_handle, _current_process

    target = process or _current_process

    if target:
        try:
            target.terminate()
            target.wait(timeout=5)
        except subprocess.TimeoutExpired:
            target.kill()
            try:
                target.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        except (OSError, ProcessLookupError):
            pass
    else:
        # After a self-editing execv reload, the server is still ours
        # but its Popen object no longer exists in this interpreter.
        owned_pid = os.environ.get(_OWNED_PID_ENV)

        if owned_pid:
            try:
                os.kill(int(owned_pid), signal.SIGTERM)
            except (OSError, ValueError, ProcessLookupError):
                pass

    _current_process = None
    os.environ.pop(_OWNED_PID_ENV, None)

    if _log_handle:
        try:
            _log_handle.close()
        except Exception:
            pass

        _log_handle = None
