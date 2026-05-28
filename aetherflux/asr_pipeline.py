"""Local-first ASR-oriented video processing helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping


Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class ASRConfig:
    backend: str = "auto"
    model: str = "small"
    language: str = "zh"
    enable_keyframes: bool = False


def dependency_status() -> Dict[str, Any]:
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "mlx_whisper": _module_exists("mlx_whisper"),
        "faster_whisper": _module_exists("faster_whisper"),
        "whisper": _module_exists("whisper"),
    }


def select_asr_backend(preferred: str = "auto") -> str:
    deps = dependency_status()
    if preferred != "auto":
        return preferred if deps.get(preferred.replace("-", "_"), False) else ""
    for backend in ("mlx_whisper", "faster_whisper", "whisper"):
        if deps.get(backend):
            return backend
    return ""


def process_video_item(
    item: Mapping[str, Any],
    output_root: str | Path,
    config: ASRConfig | None = None,
    runner: Runner = subprocess.run,
) -> Dict[str, Any]:
    cfg = config or ASRConfig()
    item_id = _item_id(item)
    item_dir = Path(output_root) / str(item.get("platform") or "unknown") / item_id
    item_dir.mkdir(parents=True, exist_ok=True)

    video_path = _find_existing_media(item)
    result: Dict[str, Any] = {
        "item_id": item_id,
        "platform": item.get("platform", ""),
        "url": item.get("url", ""),
        "deep_process_status": "started",
        "asr_status": "pending",
        "asr_backend": "",
        "transcript_full": "",
        "transcript_segments": [],
        "video_summary": {},
        "decision_hints": [],
        "artifacts_dir": str(item_dir),
    }
    if not video_path:
        result.update(
            {
                "deep_process_status": "failed",
                "asr_status": "failed",
                "error": "video_download_not_available",
                "video_summary": summarize_transcript(item, "", []),
            }
        )
        _write_result(item_dir, result)
        return result

    audio_path = item_dir / "audio.wav"
    ffmpeg = _extract_audio(video_path, audio_path, runner=runner)
    if not ffmpeg["ok"]:
        result.update({"deep_process_status": "failed", "asr_status": "failed", "error": ffmpeg["error"]})
        _write_result(item_dir, result)
        return result

    backend = select_asr_backend(cfg.backend)
    result["asr_backend"] = backend
    if not backend:
        result.update(
            {
                "deep_process_status": "failed",
                "asr_status": "failed",
                "error": "asr_dependency_missing",
                "dependency_status": dependency_status(),
                "video_summary": summarize_transcript(item, "", []),
            }
        )
        _write_result(item_dir, result)
        return result

    transcript = _run_asr(audio_path, backend, cfg)
    result.update(
        {
            "deep_process_status": "done",
            "asr_status": "done",
            "transcript_full": transcript["text"],
            "transcript_segments": transcript["segments"],
            "video_summary": summarize_transcript(item, transcript["text"], transcript["segments"]),
        }
    )
    _write_result(item_dir, result)
    return result


def summarize_transcript(item: Mapping[str, Any], transcript: str, segments: List[Mapping[str, Any]]) -> Dict[str, Any]:
    text = f"{item.get('title') or ''} {item.get('body') or ''} {transcript}".strip()
    risk_terms = ["避雷", "投诉", "宰客", "排队", "堵车", "坑", "贵"]
    opportunity_terms = ["攻略", "路线", "玩法", "体验", "推荐", "小众", "民宿", "旅拍"]
    return {
        "title": item.get("title", ""),
        "summary": text[:500],
        "segment_count": len(segments),
        "risk_terms": [term for term in risk_terms if term in text],
        "opportunity_terms": [term for term in opportunity_terms if term in text],
    }


def _extract_audio(video_path: Path, audio_path: Path, runner: Runner) -> Dict[str, Any]:
    if not shutil.which("ffmpeg"):
        return {"ok": False, "error": "ffmpeg_missing"}
    command = ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)]
    result = runner(command, check=False, capture_output=True, text=True, timeout=300)
    return {"ok": result.returncode == 0, "error": result.stderr[-500:] if result.returncode else ""}


def _run_asr(audio_path: Path, backend: str, config: ASRConfig) -> Dict[str, Any]:
    if backend == "faster_whisper":
        from faster_whisper import WhisperModel  # type: ignore

        model = WhisperModel(config.model, device="auto", compute_type="int8")
        segments, _info = model.transcribe(str(audio_path), language=config.language)
        rows = [{"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()} for seg in segments]
        return {"text": " ".join(row["text"] for row in rows).strip(), "segments": rows}
    if backend == "whisper":
        import whisper  # type: ignore

        model = whisper.load_model(config.model)
        data = model.transcribe(str(audio_path), language=config.language)
        rows = [
            {"start": round(seg.get("start", 0), 2), "end": round(seg.get("end", 0), 2), "text": str(seg.get("text", "")).strip()}
            for seg in data.get("segments", [])
        ]
        return {"text": str(data.get("text", "")).strip(), "segments": rows}
    if backend == "mlx_whisper":
        import mlx_whisper  # type: ignore

        data = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=f"mlx-community/whisper-{config.model}-mlx", language=config.language)
        rows = [
            {"start": round(seg.get("start", 0), 2), "end": round(seg.get("end", 0), 2), "text": str(seg.get("text", "")).strip()}
            for seg in data.get("segments", [])
        ]
        return {"text": str(data.get("text", "")).strip(), "segments": rows}
    return {"text": "", "segments": []}


def _find_existing_media(item: Mapping[str, Any]) -> Path | None:
    media = item.get("media") if isinstance(item.get("media"), Mapping) else {}
    for value in (item.get("local_video_path"), media.get("local_video_path") if isinstance(media, Mapping) else ""):
        if value and Path(str(value)).exists():
            return Path(str(value))
    return None


def _item_id(item: Mapping[str, Any]) -> str:
    raw = str(item.get("platform_item_id") or item.get("content_id") or item.get("url") or item.get("title") or "item")
    return "".join(char if char.isalnum() else "_" for char in raw)[-80:] or "item"


def _write_result(item_dir: Path, result: Mapping[str, Any]) -> None:
    (item_dir / "asr_result.json").write_text(json.dumps(dict(result), ensure_ascii=False, indent=2), encoding="utf-8")


def _module_exists(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False
