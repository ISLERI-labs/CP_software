import ctypes
from ctypes import wintypes
import os
import sys
import time
import socket
import subprocess
import threading
import urllib.request
from pathlib import Path

import webview

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

API_HOST = "127.0.0.1"
API_PORT = 8000
UI_HOST = "127.0.0.1"
UI_PORT = 8501

API_URL = f"http://{API_HOST}:{API_PORT}/telemetry"
UI_URL = f"http://{UI_HOST}:{UI_PORT}"

APPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
LOG_DIR = APPDATA / "CerePhyte" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

processes = []
log_files = []
shutdown_lock = threading.Lock()
shutting_down = False


def port_is_free(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) != 0


def wait_for_url(url, process, timeout=45):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"A CerePhyte service exited unexpectedly. "
                f"Check the logs in {LOG_DIR}"
            )

        try:
            request = urllib.request.Request(
                url, headers={"Cache-Control": "no-cache"}
            )
            with urllib.request.urlopen(request, timeout=1.0):
                return
        except Exception:
            time.sleep(0.25)

    raise TimeoutError(f"Service did not become ready: {url}")


def start_process(name, args):
    log_path = LOG_DIR / f"{name}.log"
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    log_files.append(log_file)

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    process = subprocess.Popen(
        args,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
    )

    processes.append(process)
    return process


def stop_process_tree(process):
    if process.poll() is not None:
        return

    # Stop only this application's process tree.
    try:
        subprocess.run(
            [
                "taskkill",
                "/PID", str(process.pid),
                "/T", "/F",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.terminate()
        except OSError:
            pass

    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            pass


def shutdown():
    global shutting_down

    with shutdown_lock:
        if shutting_down:
            return
        shutting_down = True

    # Reverse order: dashboard first, then API.
    for process in reversed(processes):
        stop_process_tree(process)

    for log_file in log_files:
        try:
            log_file.close()
        except OSError:
            pass



def set_windows_icon():
    if sys.platform != "win32":
        return

    icon_path = ROOT / "images" / "isleri.ico"
    if not icon_path.is_file():
        print(f"Icon not found: {icon_path}", file=sys.stderr)
        return

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    WM_SETICON = 0x0080
    ICON_BIG = 1
    ICON_SMALL = 0

    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadImageW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]

    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.SendMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]

    icon = user32.LoadImageW(
        None, str(icon_path), IMAGE_ICON, 0, 0, LR_LOADFROMFILE
    )

    if not icon:
        print(
            f"Could not load icon. Windows error: {ctypes.get_last_error()}",
            file=sys.stderr,
        )
        return

    try:
        native_handle = webview.windows[0].native.Handle
        hwnd_value = native_handle.ToInt64()
        hwnd = wintypes.HWND(hwnd_value)

        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, icon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, icon)
        print("CerePhyte window icon applied.")
    except Exception as exc:
        print(f"Could not apply window icon: {exc}", file=sys.stderr)


def main():
    if not (ROOT / "app.py").is_file():
        raise FileNotFoundError(f"Missing dashboard: {ROOT / 'app.py'}")

    if not (ROOT / "main.py").is_file():
        raise FileNotFoundError(f"Missing API: {ROOT / 'main.py'}")

    # Do not accidentally connect to an unrelated service on these ports.
    for port in (API_PORT, UI_PORT):
        if not port_is_free("127.0.0.1", port):
            raise RuntimeError(
                f"Port {port} is already in use. "
                "Close the conflicting application and try again."
            )

    try:
        api = start_process(
            "fastapi",
            [
                PYTHON, "-m", "uvicorn", "main:app",
                "--host", API_HOST,
                "--port", str(API_PORT),
                "--no-access-log",
            ],
        )

        wait_for_url(API_URL, api)

        dashboard = start_process(
            "streamlit",
            [
                PYTHON, "-m", "streamlit", "run", "app.py",
                "--server.address", UI_HOST,
                "--server.port", str(UI_PORT),
                "--server.headless", "true",
                "--server.fileWatcherType", "none",
                "--browser.gatherUsageStats", "false",
            ],
        )

        wait_for_url(UI_URL, dashboard)

        window = webview.create_window(
            "CerePhyte | ISLERI",
            UI_URL,
            width=1440,
            height=900,
            min_size=(1000, 650),
            background_color="#101522",
        )

        window.events.closed += shutdown
        window.events.shown += set_windows_icon
        webview.start()

    finally:
        shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        shutdown()
        print(f"CerePhyte could not start: {exc}", file=sys.stderr)
        print(f"Diagnostic logs: {LOG_DIR}", file=sys.stderr)
        input("Press Enter to exit...")
