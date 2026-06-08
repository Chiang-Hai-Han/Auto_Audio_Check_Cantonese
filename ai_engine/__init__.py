"""AI 引擎模塊 - 提供可替換的音頻分析器架構"""
from ai_engine.base import AudioMeta, ReviewResult, ReviewItem, AudioAnalyzer

QwenAudioAnalyzer = None
try:
    from ai_engine.qwen import QwenAudioAnalyzer
except Exception:
    pass
