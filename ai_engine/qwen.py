"""
Qwen3.5 Omni 音频分析器（DashScope 原生 API）
"""
import json
import logging
import os
import dashscope
from ai_engine.base import AudioAnalyzer, AudioMeta, ReviewResult, ReviewItem

logger = logging.getLogger(__name__)


class QwenAudioAnalyzer(AudioAnalyzer):
    """基於 Qwen3.5 Omni 模型的音频审核实现（DashScope 原生接口）"""

    def __init__(self, config: dict):
        super().__init__(config)
        api_key = config.get("api", {}).get("api_key", "")
        if api_key and api_key != "your-dashscope-api-key-here":
            dashscope.api_key = api_key
        self.model = config.get("api", {}).get("model", "qwen3.5-omni-plus")

    def validate_connection(self) -> bool:
        if not dashscope.api_key:
            logger.error("DashScope API Key 未设置")
            return False
        return True

    def analyze(self, audio_meta: AudioMeta, prompt: str) -> ReviewResult:
        result = ReviewResult(audio_meta=audio_meta)

        try:
            messages = [{
                "role": "user",
                "content": [
                    {"audio": audio_meta.wav_path},
                    {"text": prompt}
                ]
            }]

            file_size = os.path.getsize(audio_meta.wav_path) if os.path.exists(audio_meta.wav_path) else 0
            logger.info(f">>> API REQUEST [{audio_meta.filename}] file={file_size}bytes model={self.model}")
            logger.info(f">>> PROMPT [{audio_meta.filename}]: {prompt[:300]}...")

            response = dashscope.MultiModalConversation.call(
                api_key=dashscope.api_key,
                model=self.model,
                messages=messages,
                result_format="message"
            )

            logger.info(f">>> API STATUS [{audio_meta.filename}]: status_code={response.status_code}")

            if response.status_code != 200:
                result.error = f"API 错误: {response.code} - {response.message}"
                logger.error(f">>> API ERROR [{audio_meta.filename}]: code={response.code} msg={response.message}")
                return result

            output_text = response["output"]["choices"][0]["message"]["content"][0]["text"]
            result.raw_response = output_text
            logger.info(f">>> API RESPONSE [{audio_meta.filename}]: {output_text[:500]}")
            self._parse_response(result, output_text)

        except Exception as e:
            logger.error(f"审核失败 [{audio_meta.filename}]: {e}")
            result.error = str(e)

        return result

    @staticmethod
    def _bool(val):
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("無", "无", "false", "否", "需修改", "不通過", "不通", "錯", "no", "n"):
                return False
            if s in ("是", "通過", "通过", "true", "ok", "pass", "適合", "适合", "yes", "y"):
                return True
        return bool(val)

    def _parse_response(self, result: ReviewResult, raw: str):
        try:
            text = raw.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if len(lines) > 2:
                    text = "\n".join(lines[1:-1])

            data = json.loads(text)
            logger.info(f">>> PARSED JSON: {json.dumps(data, ensure_ascii=False)[:500]}")
            if "transcription" in data:
                logger.info(f">>> TRANSCRIPTION: {data['transcription'][:200]}")

            cp = self._bool(data.get("content_ok", True))
            ci = data.get("content_detail", "無") or "無"
            pp = self._bool(data.get("pronunciation_ok", True))
            pi = data.get("pronunciation_detail", "無") or "無"
            ip_ = self._bool(data.get("intonation_ok", True))
            ii = data.get("intonation_detail", "無") or "無"

            result.content_match = ReviewItem("内容匹配", cp, ci)
            result.intonation = ReviewItem("语调节奏", ip_, ii)
            result.pronunciation = ReviewItem("发音准确性", pp, pi)
            result.overall_pass = cp and pp and ip_
            result.overall_verdict = data.get("verdict", "通过") or "通过"
            result.overall_summary = data.get("summary", "") or ""

            logger.info(f">>> RESULT [{result.audio_meta.filename}]: content={cp} pronunciation={pp} intonation={ip_} overall={result.overall_pass}")

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f">>> JSON 解析失败 [{result.audio_meta.filename}]: {e}")
            logger.warning(f">>> RAW: {raw[:500]}")
            result.error = f"JSON 解析失败: {e}"
            result.overall_summary = raw[:500]
