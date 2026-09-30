"""Stage-2 verifier: a vision-language model reviews the flagged keyframes.

Backends (config configs/vlm.yaml or env ATOS_VLM_BACKEND):
  mock       - offline stand-in: independent image analysis of the keyframes (no API key needed)
  anthropic  - Claude vision via Messages API   (env ANTHROPIC_API_KEY)
  gemini     - Gemini vision via REST           (env GEMINI_API_KEY)
The VLM reply is parsed and validated against the strict VLMVerdict schema. Invalid / timeout / missing key ->
VLMUnavailable -> deterministic vlm_fallback handler (the system never trusts unvalidated model text).
"""
import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import cv2
import httpx
from pydantic import ValidationError

from config import cfg
from pipeline.candidate_engine import overlap_ratio, rect_gap_px
from pipeline.detector import ColorDetector
from schemas.vlm import VLMResult, VLMVerdict

PROMPT = """You are a traffic-incident verification assistant looking at three CCTV keyframes
(BEFORE, IMPACT, AFTER) of a suspected road accident. Base your answer ONLY on what is visible.
If you are unsure, lower the confidence. Do not invent details.
Return ONLY a JSON object with exactly these keys:
{"is_accident": bool, "confidence": float 0-1, "vehicles_visible": int, "collision_visible": bool,
 "vehicles_stationary_after": bool, "reasons": [1-4 short strings]}"""


class VLMUnavailable(Exception):
    pass


def _b64(p: Path) -> str:
    return base64.b64encode(Path(p).read_bytes()).decode()


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in VLM reply")
    return json.loads(m.group(0))


def _imgs(evidence_dir: str):
    d = Path(evidence_dir)
    names = ["before_raw.jpg", "impact_raw.jpg", "after_raw.jpg"]
    return [d / n for n in names if (d / n).exists()]


class _Mock:
    name = "mock"

    def __init__(self):
        self.det = ColorDetector()

    def run(self, evidence_dir: str) -> dict:
        ims = {n: cv2.imread(str(Path(evidence_dir) / f"{n}_raw.jpg")) for n in ("before", "impact", "after")}
        if ims["after"] is None or ims["impact"] is None:
            raise VLMUnavailable("keyframes missing")
        boxes = {k: [d.bbox for d in self.det.detect(v)] for k, v in ims.items() if v is not None}

        def contact_pairs(bs, tol=0.02):
            return [(a, b) for i, a in enumerate(bs) for b in bs[i + 1:] if overlap_ratio(a, b) > tol]

        after_pairs = contact_pairs(boxes["after"])
        impact_pairs = contact_pairs(boxes["impact"])
        before_pairs = contact_pairs(boxes.get("before", []))
        transition = bool(after_pairs) and not before_pairs          # vehicles were apart, now in overlap
        stationary = False
        if after_pairs and boxes["impact"]:
            # wreck persists: an overlapping pair in AFTER is within ~2 m of where a box was in IMPACT
            a, b = after_pairs[0]
            cx = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
            stationary = any(abs((q[0] + q[2]) / 2 - cx[0]) < 40 and abs((q[1] + q[3]) / 2 - cx[1]) < 40 for q in boxes["impact"])
        collision = bool(after_pairs or impact_pairs)
        conf = 0.10 + 0.35 * bool(after_pairs) + 0.20 * bool(impact_pairs) + 0.20 * transition + 0.15 * stationary
        reasons = []
        reasons.append("vehicle boxes overlap in the AFTER frame" if after_pairs else "no overlapping vehicles in the AFTER frame")
        if transition:
            reasons.append("vehicles were apart in BEFORE and overlap afterwards (contact event)")
        if stationary:
            reasons.append("overlapping vehicles remain in place after impact")
        return {"is_accident": conf >= 0.5, "confidence": round(min(conf, 0.99), 2), "vehicles_visible": len(boxes["after"]),
                "collision_visible": collision, "vehicles_stationary_after": stationary, "reasons": reasons}


class _Anthropic:
    name = "anthropic"

    def run(self, evidence_dir: str) -> dict:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise VLMUnavailable("ANTHROPIC_API_KEY not set")
        c = cfg("vlm")
        content = []
        for p in _imgs(evidence_dir):
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(p)}})
        content.append({"type": "text", "text": PROMPT})
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=c["timeout_s"],
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json={"model": c["anthropic_model"], "max_tokens": 400, "messages": [{"role": "user", "content": content}]})
        r.raise_for_status()
        return _extract_json(r.json()["content"][0]["text"])


class _Gemini:
    name = "gemini"

    def run(self, evidence_dir: str) -> dict:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise VLMUnavailable("GEMINI_API_KEY not set")
        c = cfg("vlm")
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": _b64(p)}} for p in _imgs(evidence_dir)]
        parts.append({"text": PROMPT})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{c['gemini_model']}:generateContent?key={key}"
        r = httpx.post(url, timeout=c["timeout_s"], json={"contents": [{"parts": parts}],
                                                          "generationConfig": {"responseMimeType": "application/json"}})
        r.raise_for_status()
        return _extract_json(r.json()["candidates"][0]["content"]["parts"][0]["text"])


_BACKENDS = {"mock": _Mock, "anthropic": _Anthropic, "gemini": _Gemini}
_cache = {}


def get_backend(name: Optional[str] = None):
    name = name or os.environ.get("ATOS_VLM_BACKEND") or cfg("vlm")["backend"]
    if name not in _cache:
        _cache[name] = _BACKENDS[name]()
    return _cache[name]


def verify(evidence_dir: str, backend: Optional[str] = None) -> VLMResult:
    b = get_backend(backend)
    retries = cfg("vlm")["max_retries"]
    last = None
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            raw = b.run(evidence_dir)
            verdict = VLMVerdict(**raw)                      # strict schema validation
            return VLMResult(verdict=verdict, backend=b.name, latency_ms=(time.perf_counter() - t0) * 1000)
        except VLMUnavailable:
            raise
        except (ValidationError, ValueError, KeyError, httpx.HTTPError) as e:
            last = e
    raise VLMUnavailable(f"VLM output invalid or request failed after {retries + 1} attempts: {type(last).__name__}")
