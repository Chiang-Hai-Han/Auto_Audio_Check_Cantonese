"""Start Streamlit and kill the whole process tree when this launcher exits."""
import atexit
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
child_process = None


def kill_process_tree() -> None:
    global child_process
    if child_process is None:
        return
    if child_process.poll() is not None:
        return
    subprocess.run(
        ["taskkill", "/PID", str(child_process.pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def main() -> int:
    global child_process
    command = [sys.executable, "-m", "streamlit", "run", "app.py"]
    child_process = subprocess.Popen(command, cwd=str(APP_DIR))
    atexit.register(kill_process_tree)

    print("前端已启动。关闭这个窗口时，会自动结束相关进程。")
    print("如果浏览器没自动打开，请访问输出里的本地地址。")

    try:
        return child_process.wait()
    except KeyboardInterrupt:
        kill_process_tree()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
