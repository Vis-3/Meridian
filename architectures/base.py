"""
Meridian — Abstract base class for all RAG architectures.

Every architecture subclass must implement retrieve() and generate().
The run() method wires them together and enforces the shared response schema.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

log = logging.getLogger(__name__)

_NUMERICAL_TYPES = {"numerical_reasoning", "simple_factual"}
_COMPARATIVE_TYPES = {"comparative"}


class BaseArchitecture(ABC):
    """Base class for all Meridian RAG architectures."""

    name: str = "base"  # override in each subclass

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def retrieve(self, question: str, **kwargs) -> list[dict]:
        """
        Retrieve relevant chunks for a question.

        Returns a list of chunk dicts, each containing at minimum:
          { "chunk_id", "text", "score", "company", "fiscal_year",
            "section", "document_type" }
        """

    @abstractmethod
    def generate(self, question: str, chunks: list[dict]) -> dict:
        """
        Generate an answer grounded in chunks.

        Returns the llm.generator.generate() dict:
          { "answer", "citations", "tokens_used",
            "estimated_cost_usd", "latency_ms", "model" }
        """

    # ------------------------------------------------------------------
    # Shared runner — produces the canonical response schema
    # ------------------------------------------------------------------

    def run(
        self,
        question_id: str,
        question: str,
        keyword_hit_rate: Optional[float] = None,
        question_type: Optional[str] = None,
        companies: Optional[list] = None,
        years: Optional[list] = None,
        **retrieve_kwargs,
    ) -> dict:
        """
        Execute retrieve → generate and return the full response schema.

        Args:
            question_id:      Unique identifier for this question.
            question:         The natural-language question.
            keyword_hit_rate: Pre-computed KHR for risk_qualitative questions.
            question_type:    If provided, enables facts lookup pre-step.
            companies:        Company filter hints (forwarded to facts lookup).
            years:            Fiscal year filter hints (forwarded to facts lookup).
            **retrieve_kwargs: Forwarded to retrieve() (filters, top_k, etc.).
        """
        t0 = time.perf_counter()

        # ── Facts lookup pre-step ────────────────────────────────────────
        # For numerical/factual questions, try to inject a verified facts.py
        # chunk at the top of the context before hitting Qdrant.
        facts_chunk = None
        if question_type in _NUMERICAL_TYPES and (companies or years):
            try:
                from retrieval.facts_lookup import lookup_numerical
                facts_chunk = lookup_numerical(question, companies or [], years or [])
                if facts_chunk:
                    log.debug("[facts_lookup] hit for %s: %s", question_id, facts_chunk["chunk_id"])
            except Exception as e:
                log.debug("[facts_lookup] error: %s", e)

        elif question_type in _COMPARATIVE_TYPES:
            try:
                from retrieval.facts_lookup import lookup_comparative
                facts_chunk = lookup_comparative(question, years or [])
                if facts_chunk:
                    log.debug("[facts_lookup] comparative hit for %s", question_id)
            except Exception as e:
                log.debug("[facts_lookup] error: %s", e)

        # ── Normal retrieval ─────────────────────────────────────────────
        chunks = self.retrieve(question, **retrieve_kwargs)

        # Prepend facts chunk so LLM sees it first (highest priority)
        if facts_chunk:
            chunks = [facts_chunk] + [c for c in chunks if c.get("chunk_id") != facts_chunk["chunk_id"]]

        # ── Context compression ──────────────────────────────────────────
        # For numerical/factual questions, strip non-numerical sentences
        # from each chunk to reduce LLM context noise.
        if question_type in _NUMERICAL_TYPES:
            try:
                from retrieval.compression import compress_chunks
                chunks = compress_chunks(chunks, question_type, question)
            except Exception as e:
                log.debug("[compression] error: %s", e)

        # ── Generation — use numerical prompt when facts chunk injected ──
        if facts_chunk is not None and question_type in _NUMERICAL_TYPES:
            from llm.generator import generate as _llm_generate
            from llm.prompts import GENERATION_SYSTEM_NUMERICAL
            llm_out = _llm_generate(question, chunks, system_prompt=GENERATION_SYSTEM_NUMERICAL)
        else:
            llm_out = self.generate(question, chunks)

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        citations = [
            {
                "chunk_id": c.get("chunk_id", ""),
                "text":     c.get("text", ""),
                "score":    c.get("score", 0.0),
                "company":  c.get("company", ""),
                "year":     c.get("fiscal_year"),
                "section":  c.get("section", ""),
            }
            for c in chunks
        ]

        return {
            "question_id":        question_id,
            "architecture_name":  self.name,
            "question":           question,
            "answer":             llm_out.get("answer", ""),
            "citations":          citations,
            # RAGAS metrics — placeholders until evaluation runs
            "faithfulness":       0.0,
            "answer_relevancy":   0.0,
            "context_precision":  0.0,
            "context_recall":     0.0,
            "answer_correctness": 0.0,
            "latency_ms":         latency_ms,
            "tokens_used":        llm_out.get("tokens_used", 0),
            "estimated_cost_usd": llm_out.get("estimated_cost_usd", 0.0),
            "keyword_hit_rate":   keyword_hit_rate,
        }
