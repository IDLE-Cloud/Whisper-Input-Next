"""
润色处理器：把 ASR 原始文本交给 LLM 整理成通顺的书面语。

支持两种 provider：
  POLISH_PROVIDER=openai     OpenAI 兼容格式（DeepSeek、Qwen、SiliconFlow、Ollama 等）
  POLISH_PROVIDER=anthropic  Anthropic 原生 SDK（Claude 系列）
"""

import os
from ..utils.logger import logger

DEFAULT_PROMPT = (
    "你是一个文字整理助手。"
    "用户提供的是语音识别的原始文本，可能含有口语化表达、重复词、语气词（嗯、那个、就是等）、不完整句子。"
    "请将其整理成通顺、简洁的书面语。"
    "要求：\n"
    "1. 保留原意，不添加新内容\n"
    "2. 去除口误、重复、填充词\n"
    "3. 断句合理，加上合适的标点\n"
    "4. 只输出整理后的文本，不加任何解释"
)


class PolishProcessor:
    def __init__(self):
        self.api_key  = os.getenv("POLISH_API_KEY", "")
        self.provider = os.getenv("POLISH_PROVIDER", "openai").lower()
        self.model    = os.getenv("POLISH_MODEL", "")
        self.prompt   = os.getenv("POLISH_PROMPT", DEFAULT_PROMPT)

        if not self.api_key:
            raise ValueError("未配置 POLISH_API_KEY，请在 .env 中设置")

        if self.provider == "anthropic":
            self._init_anthropic()
        else:
            self._init_openai()

        logger.info(f"润色处理器已初始化 | provider={self.provider} model={self.model}")

    # ── 初始化 ────────────────────────────────────────────────────────────

    def _init_openai(self):
        from openai import OpenAI
        base_url = os.getenv("POLISH_BASE_URL", "https://api.openai.com/v1")
        if not self.model:
            self.model = "gpt-4o-mini"
        self._client = OpenAI(api_key=self.api_key, base_url=base_url)

    def _init_anthropic(self):
        try:
            import anthropic as _anthropic
        except ImportError:
            raise ImportError(
                "使用 Anthropic 润色需要安装 anthropic 包：pip install anthropic"
            )
        if not self.model:
            self.model = "claude-haiku-4-5-20251001"
        base_url = os.getenv("POLISH_BASE_URL")
        kwargs = {"api_key": self.api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = _anthropic.Anthropic(**kwargs)

    # ── 对外接口 ──────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return bool(self.api_key)

    def polish(self, raw_text: str) -> str:
        """把原始 ASR 文本润色为通顺的书面语。"""
        if not raw_text.strip():
            return raw_text

        logger.info(f"开始润色（{self.provider}），原文: {raw_text!r}")
        try:
            if self.provider == "anthropic":
                return self._polish_anthropic(raw_text)
            else:
                return self._polish_openai(raw_text)
        except Exception as e:
            logger.error(f"润色失败: {e}，返回原文")
            return raw_text

    # ── 各 provider 实现 ──────────────────────────────────────────────────

    def _polish_openai(self, text: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.prompt},
                {"role": "user",   "content": text},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"润色完成: {result!r}")
        return result

    def _polish_anthropic(self, text: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=self.prompt,
            messages=[{"role": "user", "content": text}],
        )
        result = response.content[0].text.strip()
        logger.info(f"润色完成: {result!r}")
        return result
