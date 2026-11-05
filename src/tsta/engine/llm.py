"""LLM client with OpenAI-compatible API interface.

Supports OpenAI, 豆包 (Doubao), and any other OpenAI-compatible provider.
"""

import os
from dataclasses import dataclass

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: float = 60.0


class LLMClient:
    """OpenAI-compatible LLM client for generating node answers.

    The client is lazily initialized — no API key is required at construction time.
    """

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response from the LLM."""
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> str:
        """Multi-turn free-form chat, preserving full conversation history.

        ``messages`` is a list of ``{"role": ..., "content": ...}`` dicts
        (roles: "user" / "assistant"). An optional system prompt is prepended.
        """
        msgs: list[dict] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=msgs,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""

    def generate_answer(
        self,
        question: str,
        parent_question: str | None = None,
        parent_answer: str | None = None,
        knowledge_base: str | None = None,
    ) -> str:
        """Generate an answer using the anti-hallucination prompt template.

        This implements Algorithm 1, lines 14-19 from the TSTA paper:
        answers are strictly constrained to parent content + KB.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question, parent_question, parent_answer, knowledge_base
        )
        return self.generate(system_prompt, user_prompt)

    def _build_system_prompt(self) -> str:
        return """You are a Tree-Structured Thinking Agent (TSTA) designed for AI-assisted self-education.

Core rules:
1. Answer ONLY based on the parent node content and knowledge base provided below.
2. Do NOT introduce information from outside the given context.
3. If the parent context / KB lacks sufficient information, say so honestly.
4. Keep answers concise, accurate, and educational.
5. Structure complex answers with clear organization to aid learning.
6. When appropriate, suggest potential follow-up questions the learner might explore.

Your goal is to help the learner build a structured, traceable knowledge tree."""

    def _build_user_prompt(
        self,
        question: str,
        parent_question: str | None = None,
        parent_answer: str | None = None,
        knowledge_base: str | None = None,
    ) -> str:
        parts = []

        if parent_question:
            parts.append(f"Parent question (previous knowledge): {parent_question}")
        if parent_answer:
            parts.append(f"Parent answer (previous explanation): {parent_answer}")
        if knowledge_base:
            parts.append(f"Knowledge base (reference material): {knowledge_base}")

        parts.append(f"Current question (new inquiry): {question}")
        parts.append(
            "\nProvide a concise, accurate answer based ONLY on the above context."
        )

        return "\n".join(parts)
