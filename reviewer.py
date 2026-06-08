"""
審核流水線：組合提示詞、調用 AI 引擎、應用術語檢查
"""
import os
import time
import logging
from typing import List
from ai_engine.base import AudioMeta, ReviewResult, AudioAnalyzer

logger = logging.getLogger(__name__)


class Reviewer:
    """音頻審核流水線"""

    def __init__(self, config: dict, analyzer: AudioAnalyzer):
        self.config = config
        self.analyzer = analyzer
        self.criteria_text = ""  # 從 review_criteria.md 加載

        # 加載審核標準文檔
        criteria_path = config.get("_criteria_path", "review_criteria.md")
        if os.path.exists(criteria_path):
            with open(criteria_path, "r", encoding="utf-8") as f:
                self.criteria_text = f.read()
            logger.info(f"已載入審核標準: {criteria_path}")
        else:
            logger.warning(f"審核標準文件不存在: {criteria_path}")


    def build_prompt(self, meta: AudioMeta) -> str:
        """构建简洁审核提示词（替换模板变量）"""
        expected = meta.expected_text_from_excel or meta.expected_text_from_filename
        prompt = self.criteria_text.replace("{EXPECTED_TEXT}", expected)
        return prompt
    def review_one(self, meta: AudioMeta) -> ReviewResult:
        """審核單條音頻"""
        logger.info(f"審核中: {meta.filename}")
        prompt = self.build_prompt(meta)
        result = self.analyzer.analyze(meta, prompt)
        return result

    def review_all(self, audios: List[AudioMeta]) -> List[ReviewResult]:
        """批量審核所有音頻"""
        results = []
        total = len(audios)
        batch_delay = self.config.get("review", {}).get("request_delay", 1.0)

        for i, meta in enumerate(audios, 1):
            logger.info(f"[{i}/{total}] {meta.filename}")
            result = self.review_one(meta)
            results.append(result)

            if i < total:
                time.sleep(batch_delay)

        # 統計
        passed = sum(1 for r in results if r.all_passed and not r.error)
        with_issues = sum(1 for r in results if not r.all_passed)
        with_errors = sum(1 for r in results if r.error)
        logger.info(f"審核完成: {passed}通過, {with_issues}有問題, {with_errors}失敗")

        return results
