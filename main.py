"""
音頻自動審核系統 - 主入口
用法: python main.py --input "C:/path/to/审核文件夹"
"""
import os
import sys
import json
import argparse
import logging

from scanner import AudioScanner
from matcher import ExcelMatcher
from reviewer import Reviewer
from reporter import Reporter
from ai_engine.base import ReviewResult, ReviewItem

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.json") -> dict:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
        logger.info(f"已載入配置: {config_path}")
    else:
        logger.warning(f"配置文件不存在: {config_path}，使用默認配置")
        config = {}
    config["_criteria_path"] = "review_criteria.md"
    return config


def make_placeholder_result(meta) -> ReviewResult:
    """為未匹配的音頻生成佔位審核結果（標記為需人工審核）"""
    result = ReviewResult(audio_meta=meta)
    result.error = "未匹配到Excel原文，需人工審核"
    result.overall_pass = False
    result.overall_verdict = "需人工審核"
    result.overall_summary = "音頻文件未能在Excel中找到對應的原文條目，請人工核對"
    for attr_name in ["content_match", "grammar", "tw_word_choice",
                       "math_terms", "tone_politeness", "intonation"]:
        item = getattr(result, attr_name)
        setattr(result, attr_name, ReviewItem(item.dimension, False, "未匹配，無法自動審核"))
    return result


def main():
    parser = argparse.ArgumentParser(description="音頻自動審核系統 - 台灣市場教育內容審核")
    parser.add_argument("--input", "-i", type=str, required=True,
                        help="待審核文件夾路徑（包含 Excel 原文和配音文件夾）")
    parser.add_argument("--config", "-c", type=str, default="config.json",
                        help="配置文件路徑（默認: config.json）")
    parser.add_argument("--dry-run", action="store_true",
                        help="僅掃描和匹配，不調用 API（測試匹配效果）")
    args = parser.parse_args()

    input_dir = args.input
    if not os.path.isdir(input_dir):
        logger.error(f"目錄不存在: {input_dir}")
        sys.exit(1)

    config = load_config(args.config)

    print("=" * 60)
    print("  音頻自動審核系統")
    print("=" * 60)
    print(f"  輸入目錄: {input_dir}")
    print(f"  API 模型: {config.get('api', {}).get('model', 'qwen-audio-turbo')}")
    if args.dry_run:
        print("  模式: Dry Run (僅掃描匹配，不調用API)")
    print("=" * 60)
    print()

    # Step 1: 掃描
    print("[1/4] 掃描音頻文件...")
    scanner = AudioScanner()
    audios = scanner.scan(input_dir)
    print(f"  找到 {len(audios)} 個 .wav 文件")
    if not audios:
        logger.warning("未找到任何音頻文件，退出")
        return

    # Step 2: 匹配
    print("[2/4] 匹配 Excel 原文...")
    matcher = ExcelMatcher(config)
    excel_path = matcher.find_excel_in_dir(input_dir)
    if not excel_path:
        logger.error(f"目錄中未找到 Excel 文件: {input_dir}")
        sys.exit(1)

    sheets_data = matcher.load_excel(excel_path)
    audios = matcher.match_audios(audios, sheets_data)

    matched = [a for a in audios if a.expected_text_from_excel]
    unmatched = [a for a in audios if not a.expected_text_from_excel]
    print(f"  成功匹配: {len(matched)}/{len(audios)} 條")
    if unmatched:
        print(f"  未匹配:   {len(unmatched)} 條 (將標記為需人工審核)")

    print("\n  匹配預覽 (前5條):")
    for a in audios[:5]:
        status = "[OK]" if a.expected_text_from_excel else "[!!]"
        print(f"    {status} {a.filename[:60]}")
        if a.expected_text_from_excel:
            print(f"        角色={a.role}{a.role_index} | 語速={a.expected_speed} | 語氣={a.expected_tone}")

    if args.dry_run:
        # dry-run 也生成預覽報告（僅含未匹配標記）
        print("\n[Dry Run] 生成預覽報告...")
        all_results = []
        for m in matched:
            r = ReviewResult(audio_meta=m)
            r.overall_summary = "Dry-Run 預覽（已匹配）"
            all_results.append(r)
        for m in unmatched:
            all_results.append(make_placeholder_result(m))
        reporter = Reporter(config)
        report_path = reporter.generate(all_results, input_dir)
        print(f"  預覽報告: {os.path.abspath(report_path)}")
        print("\n[Dry Run 完成] 僅掃描匹配，不調用 API。")
        return

    # Step 3: AI 審核
    print("\n[3/4] AI 審核中...")
    try:
        from ai_engine.qwen import QwenAudioAnalyzer
    except ImportError:
        logger.error("缺少 dashscope 套件。請先安裝: pip install dashscope")
        sys.exit(1)

    analyzer = QwenAudioAnalyzer(config)
    if not analyzer.validate_connection():
        logger.error("API 連接驗證失敗，請檢查 config.json 中的 api_key")
        sys.exit(1)

    reviewer = Reviewer(config, analyzer)
    ai_results = reviewer.review_all(matched) if matched else []

    # 合併：AI 結果 + 未匹配佔位結果
    all_results = ai_results + [make_placeholder_result(m) for m in unmatched]

    # Step 4: 報告
    print("\n[4/4] 生成報告...")
    reporter = Reporter(config)
    report_path = reporter.generate(all_results, input_dir)

    total = len(all_results)
    passed = sum(1 for r in all_results if r.all_passed and not r.error)
    with_issues = sum(1 for r in all_results if not r.all_passed and not r.error)
    failed = sum(1 for r in all_results if r.error)

    print("\n" + "=" * 60)
    print("  審核完成！")
    print("=" * 60)
    print(f"  總音頻數: {total}")
    print(f"  完全通過: {passed}")
    print(f"  有問題:   {with_issues}")
    print(f"  未匹配/失敗: {failed}")
    print(f"  報告文件: {os.path.abspath(report_path)}")
    print("=" * 60)


if __name__ == "__main__":
    main()