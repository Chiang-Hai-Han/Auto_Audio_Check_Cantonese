"""Scan wav files and parse metadata from filenames."""
import logging
import os
import re
from typing import List

from ai_engine.base import AudioMeta

logger = logging.getLogger(__name__)


class AudioScanner:
    def __init__(self):
        self.hyphen_pattern = re.compile(r"^(?P<prefix>[^-]+)-(?P<text>.+)\.wav$", re.IGNORECASE)
        self.direct_pattern = re.compile(r"^(?P<prefix>.+?)(?P<text>[^\\/]*)\.wav$", re.IGNORECASE)

    @staticmethod
    def _split_prefix(prefix: str) -> tuple[str, str]:
        prefix = prefix.strip()

        leading = re.match(r"^(?P<index>\d+)(?P<role>.+)$", prefix)
        if leading:
            return leading.group("role").strip(), leading.group("index").zfill(2)

        trailing = re.match(r"^(?P<role>.+?)(?P<index>\d+)$", prefix)
        if trailing:
            return trailing.group("role").strip(), trailing.group("index").zfill(2)

        return prefix, ""

    def _parse_filename(self, filename: str) -> tuple[str, str, str]:
        clean_name = filename
        if clean_name.lower().endswith(".folderdownload"):
            clean_name = clean_name[:-len(".folderdownload")]

        match = self.hyphen_pattern.match(clean_name)
        if match:
            role, idx = self._split_prefix(match.group("prefix"))
            return role, idx, match.group("text").strip()

        base = os.path.splitext(clean_name)[0]
        match = self.direct_pattern.match(clean_name)
        if match:
            prefix = match.group("prefix")
            role, idx = self._split_prefix(prefix)
            text = base[len(prefix):].strip()
            if role and text:
                return role, idx, text

        return "", "", ""

    def scan(self, root_dir: str) -> List[AudioMeta]:
        if not os.path.isdir(root_dir):
            raise ValueError(f"目录不存在: {root_dir}")

        results: List[AudioMeta] = []
        wav_count = 0

        for dirpath, _, filenames in os.walk(root_dir):
            for fname in filenames:
                lower_name = fname.lower()
                if not lower_name.endswith(".wav") and ".wav.folderdownload" not in lower_name:
                    continue
                if ".wav.folderdownload" in lower_name and not lower_name.endswith(".wav"):
                    continue

                wav_count += 1
                full_path = os.path.join(dirpath, fname)
                folder_name = os.path.basename(dirpath)

                role, idx, text = self._parse_filename(fname)
                if not role or not text:
                    logger.warning(f"文件名格式不符，跳过解析: {fname}")

                results.append(
                    AudioMeta(
                        wav_path=full_path,
                        folder_name=folder_name,
                        filename=fname,
                        role=role,
                        role_index=idx,
                        expected_text_from_filename=text,
                    )
                )

        logger.info(f"扫描完成：共找到 {wav_count} 个 .wav 文件")
        return results
