import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import streamlit as st

from preflight import run_preflight


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
PROMPT_PATH = APP_DIR / "review_criteria.md"
UI_STATE_PATH = APP_DIR / ".ui_state.json"


def load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return default.copy()
    return default.copy()


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    return load_json(CONFIG_PATH, {})


def save_config(config: dict) -> None:
    save_json(CONFIG_PATH, config)


def load_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def save_prompt(text: str) -> None:
    PROMPT_PATH.write_text(text, encoding="utf-8")


def load_ui_state() -> dict:
    return load_json(UI_STATE_PATH, {})


def save_ui_state(data: dict) -> None:
    save_json(UI_STATE_PATH, data)


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def normalize_input_dir(path_text: str) -> str:
    text = (path_text or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1].strip()
    return text


def choose_folder() -> str:
    selected = {"path": ""}

    def _open_dialog():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected["path"] = filedialog.askdirectory()
        root.destroy()

    thread = threading.Thread(target=_open_dialog)
    thread.start()
    thread.join()
    return selected["path"]


def can_start_review(preflight_result) -> bool:
    return bool(preflight_result) and preflight_result.severity in {"pass", "warn"}


def decode_output(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk", "cp950"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run_review(input_dir: str):
    command = [sys.executable, "main.py", "--input", input_dir]
    process = subprocess.Popen(
        command,
        cwd=str(APP_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    return process


st.set_page_config(
    page_title="音频自动审核 - 粤语版",
    page_icon="🎧",
    layout="wide",
)


config = load_config()
ui_state = load_ui_state()
default_prompt = load_prompt()

if "last_loaded_prompt" not in st.session_state:
    st.session_state.last_loaded_prompt = default_prompt
if "prompt_text" not in st.session_state:
    st.session_state.prompt_text = default_prompt
elif (
    st.session_state.prompt_text == st.session_state.last_loaded_prompt
    and default_prompt != st.session_state.last_loaded_prompt
):
    st.session_state.prompt_text = default_prompt
    st.session_state.last_loaded_prompt = default_prompt
if "preflight_result" not in st.session_state:
    st.session_state.preflight_result = None
if "review_output" not in st.session_state:
    st.session_state.review_output = ""
if "review_report_path" not in st.session_state:
    st.session_state.review_report_path = ""
if "input_dir" not in st.session_state:
    st.session_state.input_dir = ui_state.get("last_input_dir", "")
if "input_dir_text" not in st.session_state:
    st.session_state.input_dir_text = st.session_state.input_dir
if "pending_input_dir" not in st.session_state:
    st.session_state.pending_input_dir = ""

if st.session_state.pending_input_dir:
    st.session_state.input_dir = st.session_state.pending_input_dir
    st.session_state.input_dir_text = st.session_state.pending_input_dir
    st.session_state.pending_input_dir = ""


st.title("音频自动审核 - 粤语版")
st.caption("先检查和预整理，再进入审核，避免浪费资源。")
st.caption("by 海瀚")

left, right = st.columns([1, 1.35], gap="large")

with left:
    st.subheader("基础配置")
    st.caption("可以把文件夹路径直接拖进输入框，也可以点右侧按钮浏览选择文件夹。")

    path_col1, path_col2 = st.columns([4, 1])
    with path_col1:
        raw_input_dir = st.text_input("音频目录", placeholder=r"C:\path\to\folder", key="input_dir_text")
    with path_col2:
        st.write("")
        if st.button("浏览", use_container_width=True):
            chosen = choose_folder()
            if chosen:
                st.session_state.pending_input_dir = chosen
                st.rerun()

    input_dir = normalize_input_dir(raw_input_dir)
    st.session_state.input_dir = input_dir
    if st.session_state.input_dir_text != input_dir:
        st.session_state.input_dir_text = input_dir
    if raw_input_dir != input_dir:
        st.caption(f"已识别目录：`{input_dir}`")

    api_cfg = config.get("api", {})
    saved_key = api_cfg.get("api_key", "")
    show_edit_key = st.toggle("修改 API Key", value=False)
    if saved_key and not show_edit_key:
        st.text_input("已保存的 API Key", value=mask_key(saved_key), disabled=True)
        api_key = saved_key
    else:
        api_key = st.text_input("API Key", value=saved_key if show_edit_key else "", type="password")

    model = st.text_input("模型", value=api_cfg.get("model", "qwen3.5-omni-plus"))
    st.caption(f"当前将使用模型：`{model}`")

    st.subheader("审核提示词")
    st.caption("默认使用项目预设提示词，需要时可修改。")
    prompt_text = st.text_area("提示词内容", value=st.session_state.prompt_text, height=320)
    st.session_state.prompt_text = prompt_text

    prompt_col1, prompt_col2 = st.columns(2)
    with prompt_col1:
        if st.button("保存当前提示词", use_container_width=True):
            save_prompt(prompt_text)
            st.session_state.last_loaded_prompt = prompt_text
            st.success("提示词已保存。")
    with prompt_col2:
        if st.button("恢复默认提示词", use_container_width=True):
            original = load_prompt()
            st.session_state.prompt_text = original
            st.session_state.last_loaded_prompt = original
            st.rerun()

    if st.button("保存基础配置", use_container_width=True):
        config.setdefault("api", {})
        config["api"]["api_key"] = api_key
        config["api"]["model"] = model
        save_config(config)
        save_ui_state({"last_input_dir": input_dir})
        st.success("配置已保存。")

with right:
    st.subheader("步骤 1：检查并预整理")
    check_clicked = st.button("开始检查", type="primary", use_container_width=True)

    progress_bar = st.progress(0, text="等待开始")
    progress_text = st.empty()

    if check_clicked:
        if not input_dir or not os.path.isdir(input_dir):
            st.error("请输入有效的音频目录。")
        else:
            config.setdefault("api", {})
            config["api"]["api_key"] = api_key
            config["api"]["model"] = model
            save_config(config)
            save_prompt(st.session_state.prompt_text)
            save_ui_state({"last_input_dir": input_dir})

            def on_preflight_progress(value: float, message: str):
                progress_bar.progress(int(value * 100), text=message)
                progress_text.caption(message)

            result = run_preflight(input_dir, str(CONFIG_PATH), progress_cb=on_preflight_progress)
            st.session_state.preflight_result = result

    result = st.session_state.preflight_result
    if result:
        severity_map = {
            "pass": ("检查通过", st.success),
            "warn": ("检查有警告", st.warning),
            "block": ("检查未通过", st.error),
        }
        title, renderer = severity_map[result.severity]
        renderer(title)

        metric_cols = st.columns(4)
        metric_cols[0].metric("音频总数", result.total_audio)
        metric_cols[1].metric("成功匹配", result.matched_audio)
        metric_cols[2].metric("未匹配", result.unmatched_audio)
        metric_cols[3].metric("低置信度", result.low_confidence_count)

        prep = result.prepare_summary or {}
        st.caption(
            f"已发现 {len(result.excel_files)} 份 Excel，载入 {prep.get('loaded_files', 0)} 份，"
            f"预整理出 {prep.get('row_count', 0)} 条有效台词。"
        )

        if result.blockers:
            st.markdown("**阻断问题**")
            for item in result.blockers:
                st.write(f"- {item}")

        if result.warnings:
            st.markdown("**警告信息**")
            for item in result.warnings:
                st.write(f"- {item}")

        st.markdown("**输出文件**")
        if result.prepared_excel_path:
            st.write(f"预整理表：`{result.prepared_excel_path}`")
        if result.preview_report_path:
            st.write(f"检查预览：`{result.preview_report_path}`")

        with st.expander("查看匹配预览", expanded=result.severity != "pass"):
            st.dataframe(result.rows, use_container_width=True, hide_index=True)

    st.subheader("步骤 2：开始审核")
    review_disabled = not can_start_review(result)
    review_clicked = st.button("开始审核", disabled=review_disabled, use_container_width=True)

    if review_disabled:
        st.info("请先完成检查，并确保没有阻断问题后再开始审核。")

    if review_clicked and result:
        review_progress = st.progress(0, text="准备启动审核")
        review_status = st.empty()
        review_log = st.empty()
        review_progress.progress(5, text="正在启动主程序")
        review_status.caption("正在调用主审核流程")

        process = run_review(result.input_dir)
        log_lines = []
        report_path = ""

        while True:
            raw_line = process.stdout.readline() if process.stdout else b""
            if not raw_line and process.poll() is not None:
                break
            if not raw_line:
                continue

            line = decode_output(raw_line).rstrip("\r\n")
            log_lines.append(line)

            match = re.search(r"\[(\d+)/(\d+)\]", line)
            if match:
                current = int(match.group(1))
                total = int(match.group(2))
                percent = 15 + int((current / total) * 80) if total else 15
                review_progress.progress(min(percent, 95), text=f"审核进度 {current}/{total}")
                review_status.caption(f"正在审核：{current}/{total}")

            report_match = re.search(r"(報告文件|报告文件|報告已保存|报告已保存)[:：]\s*(.+\.xlsx)", line)
            if report_match:
                report_path = report_match.group(2).strip()

            review_log.code("\n".join(log_lines[-80:]), language="text")

        return_code = process.wait()
        review_progress.progress(100, text="审核流程已结束")
        review_status.caption("审核结束，请查看日志和报告。")

        st.session_state.review_output = "\n".join(log_lines).strip()
        st.session_state.review_report_path = report_path

        if return_code == 0:
            st.success("审核已完成。")
        else:
            st.error("审核执行失败，请查看日志。")

    if st.session_state.review_output:
        with st.expander("查看审核日志", expanded=False):
            st.code(st.session_state.review_output, language="text")

    if st.session_state.review_report_path and os.path.exists(st.session_state.review_report_path):
        st.subheader("审核报告")
        st.write(f"报告文件：`{st.session_state.review_report_path}`")
        with open(st.session_state.review_report_path, "rb") as f:
            st.download_button(
                "下载审核报告",
                data=f.read(),
                file_name=os.path.basename(st.session_state.review_report_path),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
