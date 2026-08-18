"""
pipeline/utils.py — Unified LLM backend.

Priority:
  1. Groq  (cloud, free tier, very fast ~2s) — tried first
  2. Gemini REST API — fallback if Groq quota hit
  3. Ollama (local) — last resort, 60s timeout to prevent hangs
"""

import json
import logging
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_OLLAMA_BASE    = "http://localhost:11434"
_OLLAMA_MODEL   = "qwen2.5:3b"
_OLLAMA_TIMEOUT = 600         # 600s max — local model takes time for large docs

_GEMINI_MODEL   = "gemini-3.6-flash"  # confirmed available on this Gemini key
_GEMINI_MIN_INTERVAL = 5.0    # rate-limiter: 12 req/min safe

_GROQ_MODEL     = "qwen/qwen3.6-27b"  # confirmed available on this Groq account


# ── Module-level quota state ───────────────────────────────────────────────────
_groq_quota_exhausted:    bool  = False
_groq_quota_reset_time:   float = 0.0

_gemini_last_call_time:   float = 0.0
_gemini_quota_exhausted:  bool  = False
_gemini_quota_reset_time: float = 0.0


# ─────────────────────────────────────────────────────────────
# Groq helpers (PRIMARY)
# ─────────────────────────────────────────────────────────────

def _call_groq(messages: list[dict], response_format=None, temperature: float = 0.1) -> str:
    """Call Groq Cloud API — fast, free tier, OpenAI-compatible."""
    global _groq_quota_exhausted, _groq_quota_reset_time

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise ValueError("GROQ_API_KEY not set")

    if _groq_quota_exhausted and time.time() < _groq_quota_reset_time:
        raise RuntimeError(f"Groq quota in cool-down for {_groq_quota_reset_time - time.time():.0f}s")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload: dict = {
        "model": _GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096,
    }
    if response_format and response_format.get("type") == "json_object":
        payload["response_format"] = {"type": "json_object"}

    r = requests.post(url, headers=headers, json=payload, timeout=60)

    if r.status_code == 429:
        _groq_quota_exhausted = True
        _groq_quota_reset_time = time.time() + 60
        raise RuntimeError("Groq 429 — quota hit, cool-down 60s")

    r.raise_for_status()
    _groq_quota_exhausted = False
    return r.json()["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────────────────────
# Gemini helpers (SECONDARY)
# ─────────────────────────────────────────────────────────────

def _call_gemini(messages: list[dict], response_format=None, temperature: float = 0.1,
                 max_retries: int = 2) -> str:
    """Call Gemini REST API with rate limiting."""
    global _gemini_last_call_time, _gemini_quota_exhausted, _gemini_quota_reset_time

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not set in .env")

    if _gemini_quota_exhausted and time.time() < _gemini_quota_reset_time:
        raise RuntimeError("Gemini quota in cool-down")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_GEMINI_MODEL}:generateContent?key={gemini_key}"
    )

    system_instruction = None
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            if not system_instruction:
                system_instruction = {"parts": [{"text": msg["content"]}]}
            else:
                system_instruction["parts"].append({"text": "\n" + msg["content"]})
        else:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    payload: dict = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if system_instruction:
        payload["systemInstruction"] = system_instruction
    if response_format and response_format.get("type") == "json_object":
        payload["generationConfig"]["responseMimeType"] = "application/json"

    for attempt in range(1, max_retries + 1):
        wait = _GEMINI_MIN_INTERVAL - (time.time() - _gemini_last_call_time)
        if wait > 0:
            time.sleep(wait)
        try:
            _gemini_last_call_time = time.time()
            r = requests.post(url, json=payload, timeout=60)

            if r.status_code == 429:
                _gemini_quota_exhausted = True
                _gemini_quota_reset_time = time.time() + 60
                raise RuntimeError("Gemini 429 quota exhausted")

            r.raise_for_status()
            data = r.json()
            if "candidates" not in data or not data["candidates"]:
                raise ValueError(f"Empty Gemini response: {data}")

            _gemini_quota_exhausted = False
            return data["candidates"][0]["content"]["parts"][0]["text"]

        except Exception as e:
            if "quota" in str(e).lower() or "429" in str(e):
                raise
            if attempt < max_retries:
                logger.warning("Gemini error (attempt %d/%d): %s — retrying", attempt, max_retries, e)
                time.sleep(5)
            else:
                raise

    raise RuntimeError("Gemini exhausted all retries")


# ─────────────────────────────────────────────────────────────
# Ollama helpers (LAST RESORT)
# ─────────────────────────────────────────────────────────────

def _ollama_available() -> bool:
    try:
        r = requests.get(f"{_OLLAMA_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _call_ollama(messages: list[dict], response_format=None, temperature: float = 0.1) -> str:
    """Call Ollama. Hard 60s timeout — never blocks for 400s again."""
    url = f"{_OLLAMA_BASE}/v1/chat/completions"
    payload: dict = {
        "model": _OLLAMA_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if response_format and response_format.get("type") == "json_object":
        payload["response_format"] = {"type": "json_object"}

    r = requests.post(url, json=payload, timeout=_OLLAMA_TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────

def generate_with_retry(
    client=None, model=None,
    messages: list[dict] = None,
    max_retries: int = 3,
    response_format=None,
    temperature: float = 0.1,
    task_type: str = "normal",
) -> str:
    """
    Primary LLM entry point.  Priority: Groq → Gemini → Ollama.

    Groq is tried first (fast, free cloud tier).
    Gemini is fallback if Groq quota hit.
    Ollama (local) is last resort — slower but always available.
    task_type is kept for API compat but no longer changes priority.
    """
    last_error: Exception | None = None

    # ── 1. Try Groq (primary — fast, free cloud) ─────────────────────────────
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and not (_groq_quota_exhausted and time.time() < _groq_quota_reset_time):
        try:
            logger.info("[LLM] Using Groq (%s) — primary", _GROQ_MODEL)
            result = _call_groq(messages, response_format=response_format, temperature=temperature)
            if response_format and response_format.get("type") == "json_object":
                text = _clean_json(result)
                json.loads(text)  # validate
                return text
            return result
        except Exception as e:
            last_error = e
            logger.warning("[LLM] Groq failed: %s — trying Gemini", e)

    # ── 2. Try Gemini (secondary) ─────────────────────────────────────────────
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key and not (_gemini_quota_exhausted and time.time() < _gemini_quota_reset_time):
        try:
            logger.info("[LLM] Using Gemini (%s) — secondary", _GEMINI_MODEL)
            result = _call_gemini(messages, response_format=response_format, temperature=temperature)
            if response_format and response_format.get("type") == "json_object":
                text = _clean_json(result)
                json.loads(text)  # validate
                return text
            return result
        except Exception as e:
            last_error = e
            logger.warning("[LLM] Gemini failed: %s — trying Ollama", e)

    # ── 3. Try Ollama (last resort — local GPU) ───────────────────────────────
    if _ollama_available():
        try:
            logger.info("[LLM] Using Ollama (%s) on GPU — last resort", _OLLAMA_MODEL)
            result = _call_ollama(messages, response_format=response_format, temperature=temperature)
            if response_format and response_format.get("type") == "json_object":
                text = _clean_json(result)
                json.loads(text)  # validate
                return text
            return result
        except Exception as e:
            last_error = e
            logger.warning("[LLM] Ollama failed: %s", e)

    raise RuntimeError(f"No LLM backend available. Last error: {last_error}")


def parse_json_response(text: str) -> dict:
    text = _clean_json(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s\nRaw: %s", e, repr(text[:400]))
        return {}


def _clean_json(text: str) -> str:
    if not text:
        return "{}"
    text = text.strip()
    if "<think>" in text and "</think>" in text:
        text = text.split("</think>")[-1].strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    return text.strip() or "{}"
