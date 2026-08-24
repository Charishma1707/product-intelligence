"""
pipeline/utils.py — Unified LLM backend.

Priority:
  1. Gemini REST API (gemini-3.6-flash) — tried first (Primary LLM)
  2. Groq Cloud API (qwen/qwen3.6-27b) — fallback if Gemini quota hit
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
# Groq helpers (SECONDARY FALLBACK)
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
# Gemini helpers (PRIMARY)
# ─────────────────────────────────────────────────────────────

def _call_gemini(messages: list[dict], response_format=None, temperature: float = 0.1,
                 max_retries: int = 3) -> str:
    """Call Gemini 3.6 Flash REST API with automatic backoff retry."""
    global _gemini_last_call_time

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY not set in .env")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-3.6-flash:generateContent?key={gemini_key}"
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

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                wait_time = attempt * 2
                logger.warning(f"Gemini 3.6 Flash 429 rate limit (attempt {attempt}/{max_retries}) — backing off for {wait_time}s...")
                time.sleep(wait_time)
                continue

            r.raise_for_status()
            data = r.json()
            if "candidates" not in data or not data["candidates"]:
                raise ValueError(f"Empty Gemini response: {data}")

            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            last_err = e
            logger.warning(f"Gemini 3.6 Flash attempt {attempt} failed: {e}")
            time.sleep(1.5)

    raise RuntimeError(f"Gemini 3.6 Flash exhausted retries. Last error: {last_err}")


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
        "options": {
            "num_gpu": 99,  # Offload all layers to GPU if available
        },
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
    Primary LLM entry point with cost-sensitive fallback cascade:
    - Simple tasks (extraction, classification, normal) -> try Ollama (local) first, escalate to Groq/Gemini if low confidence or invalid.
    - Complex tasks (copywrite, reasoning, conflict resolution) -> try Groq/Gemini first, Ollama as last resort.
    """
    last_error: Exception | None = None
    is_simple = task_type in ("normal", "simple", "extraction", "classification")

    # ── 1. Try local Ollama FIRST for simple/extraction/classification tasks (free and fast on GPU) ────
    if is_simple and _ollama_available():
        try:
            logger.info("[LLM Cascade] Attempting local Ollama (%s) first for simple task_type: %s", _OLLAMA_MODEL, task_type)
            result = _call_ollama(messages, response_format=response_format, temperature=temperature)
            
            # Simple confidence/validity check
            if response_format and response_format.get("type") == "json_object":
                text = _clean_json(result)
                parsed = json.loads(text)  # validate JSON
                
                # If it's a specifications extraction RAG call and returns null/empty value, we escalate
                if task_type == "extraction" and (
                    not parsed.get("value") or 
                    str(parsed.get("value")).strip().lower() in ("", "null", "none", "n/a")
                ):
                    raise ValueError("Ollama returned null/empty value for extraction. Escalating to cloud models.")
                return text
            return result
        except Exception as e:
            logger.warning("[LLM Cascade] Local Ollama failed/skipped: %s. Escalating to Groq...", e)
            last_error = e

    # ── 2. Cloud model cascade (Gemini PRIMARY → Groq Secondary) ─────────────────
    # Primary Cloud Provider: Gemini 3.6 Flash (high throughput, no rate limits)
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key and not (_gemini_quota_exhausted and time.time() < _gemini_quota_reset_time):
        try:
            logger.info("[LLM Cascade] Routing to Primary LLM: Gemini (%s)", _GEMINI_MODEL)
            result = _call_gemini(messages, response_format=response_format, temperature=temperature)
            if response_format and response_format.get("type") == "json_object":
                text = _clean_json(result)
                json.loads(text)  # validate
                return text
            return result
        except Exception as e:
            last_error = e
            logger.warning("[LLM Cascade] Gemini primary call failed: %s — trying Groq fallback", e)

    # Secondary Fallback Provider: Groq Cloud API
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key and not (_groq_quota_exhausted and time.time() < _groq_quota_reset_time):
        try:
            logger.info("[LLM Cascade] Routing to Secondary LLM: Groq (%s)", _GROQ_MODEL)
            result = _call_groq(messages, response_format=response_format, temperature=temperature)
            if response_format and response_format.get("type") == "json_object":
                text = _clean_json(result)
                json.loads(text)  # validate
                return text
            return result
        except Exception as e:
            last_error = e
            logger.warning("[LLM Cascade] Groq fallback failed: %s", e)

    # ── 3. Local Ollama as ultimate fallback for complex tasks ───────────────────
    if not is_simple and _ollama_available():
        try:
            logger.info("[LLM Cascade] Cloud failed. Falling back to local Ollama (%s) as last resort", _OLLAMA_MODEL)
            result = _call_ollama(messages, response_format=response_format, temperature=temperature)
            if response_format and response_format.get("type") == "json_object":
                text = _clean_json(result)
                json.loads(text)  # validate
                return text
            return result
        except Exception as e:
            last_error = e
            logger.warning("[LLM Cascade] Ollama fallback failed: %s", e)

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
