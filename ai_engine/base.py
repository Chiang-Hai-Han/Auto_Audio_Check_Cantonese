"""Base types for audio review."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AudioMeta:
    wav_path: str
    folder_name: str
    filename: str
    role: str
    role_index: str
    expected_text_from_filename: str
    expected_text_from_excel: str = ""
    expected_speed: str = "常规"
    expected_tone: str = "常规"
    sheet_name: str = ""
    row_number: int = 0
    match_score: float = 0.0


@dataclass
class ReviewItem:
    dimension: str
    passed: bool
    issue: str


@dataclass
class ReviewResult:
    audio_meta: AudioMeta
    content_match: ReviewItem = field(default_factory=lambda: ReviewItem("内容匹配", True, "无"))
    grammar: ReviewItem = field(default_factory=lambda: ReviewItem("语法", True, "无"))
    tw_word_choice: ReviewItem = field(default_factory=lambda: ReviewItem("台词用词", True, "无"))
    math_terms: ReviewItem = field(default_factory=lambda: ReviewItem("数学术语", True, "无"))
    tone_politeness: ReviewItem = field(default_factory=lambda: ReviewItem("语气礼貌", True, "无"))
    intonation: ReviewItem = field(default_factory=lambda: ReviewItem("语调节奏", True, "无"))
    overall_pass: bool = True
    overall_verdict: str = "适合"
    overall_summary: str = ""
    raw_response: str = ""
    error: str = ""

    @property
    def all_passed(self) -> bool:
        return all([
            self.content_match.passed,
            self.grammar.passed,
            self.tw_word_choice.passed,
            self.math_terms.passed,
            self.tone_politeness.passed,
            self.intonation.passed,
            self.overall_pass,
        ])

    @property
    def issue_count(self) -> int:
        return sum(
            1
            for item in [
                self.content_match,
                self.grammar,
                self.tw_word_choice,
                self.math_terms,
                self.tone_politeness,
                self.intonation,
            ]
            if not item.passed
        )


class AudioAnalyzer(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def analyze(self, audio_meta: AudioMeta, prompt: str) -> ReviewResult:
        raise NotImplementedError

    @abstractmethod
    def validate_connection(self) -> bool:
        raise NotImplementedError
