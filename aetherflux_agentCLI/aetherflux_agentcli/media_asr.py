"""Local video download and ASR processing for agentCLI bundles."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping
from urllib.parse import urlsplit


Runner = Callable[..., subprocess.CompletedProcess]
Transcriber = Callable[[Path, str, "ASRConfig"], Dict[str, Any]]


@dataclass
class ASRConfig:
    backend: str = "auto"
    model: str = "small"
    language: str = "zh"
    cookies_from_browser: str = ""
    browser_media_resolution: bool = True
    browser_session: str = "aetherflux-agentcli-media"
    download_timeout_seconds: int = 600
    audio_timeout_seconds: int = 300


def dependency_status() -> Dict[str, Any]:
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "mlx_whisper": _module_exists("mlx_whisper"),
        "mlx_whisper_cli": bool(_mlx_whisper_cli()),
        "faster_whisper": _module_exists("faster_whisper"),
        "whisper": _module_exists("whisper"),
    }


def select_asr_backend(preferred: str = "auto", deps: Mapping[str, Any] | None = None) -> str:
    deps = dict(deps or dependency_status())
    if preferred and preferred != "auto":
        normalized = preferred.replace("-", "_")
        if normalized == "mlx_whisper" and deps.get("mlx_whisper_cli"):
            return "mlx_whisper_cli"
        return normalized if normalized == "fake" or deps.get(normalized, False) else ""
    for backend in ("mlx_whisper", "mlx_whisper_cli", "faster_whisper", "whisper"):
        if deps.get(backend):
            return backend
    return ""


def process_video_item(
    item: Mapping[str, Any],
    output_root: str | Path,
    config: ASRConfig | None = None,
    runner: Runner = subprocess.run,
    transcriber: Transcriber | None = None,
) -> Dict[str, Any]:
    cfg = config or ASRConfig()
    item_id = _item_id(item)
    item_dir = Path(output_root) / str(item.get("platform") or "unknown") / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Any] = {
        "item_id": item_id,
        "platform": item.get("platform", ""),
        "url": item.get("url", ""),
        "download_status": "pending",
        "asr_status": "pending",
        "asr_backend": "",
        "summary": "",
        "transcript_ref": "",
        "segments_ref": "",
        "artifacts_dir": str(item_dir),
    }

    content_type = str(item.get("content_type") or "").lower()
    url = str(item.get("url") or "").strip()
    browser_media = _resolve_browser_media(url, cfg, runner) if cfg.browser_media_resolution and url else {}
    if content_type and content_type not in {"video", "mixed"}:
        image_refs = _download_images(browser_media.get("image_urls") or [], item_dir, runner)
        return _finish(
            item_dir,
            result,
            download_status="skipped",
            asr_status="skipped",
            error="not_video_content",
            image_refs=image_refs,
            browser_media=browser_media,
            information_value=classify_information_value(item, "", [], content_type=content_type),
        )

    local_existing = _find_existing_media(item)
    local_video = local_existing
    download: Dict[str, Any] = {"method": "local_file"}
    if not local_video:
        if not url:
            return _finish(item_dir, result, download_status="skipped", asr_status="skipped", error="missing_video_url")
        download = _download_browser_video(browser_media.get("video_urls") or [], item_dir, runner)
        browser_download_error = download.get("stderr", "") if not download["ok"] else ""
        if not download["ok"]:
            download = _download_video(url, item_dir, cfg, runner)
        if not download["ok"]:
            return _finish(
                item_dir,
                result,
                download_status="failed",
                asr_status="failed",
                error=download["error"],
                error_detail=download.get("stderr", ""),
                browser_download_error=browser_download_error,
                browser_media=browser_media,
                dependency_status=dependency_status(),
            )
        local_video = download["video_path"]

    audio_path = item_dir / "audio.wav"
    audio = _extract_audio(local_video, audio_path, cfg, runner)
    if not audio["ok"]:
        return _finish(item_dir, result, download_status="done", asr_status="failed", error=audio["error"], error_detail=audio.get("stderr", ""))

    backend = select_asr_backend(cfg.backend)
    result["asr_backend"] = backend
    if not backend:
        return _finish(
            item_dir,
            result,
            download_status="done",
            asr_status="failed",
            error="asr_dependency_missing",
            dependency_status=dependency_status(),
        )

    transcript = (transcriber or _run_asr)(audio_path, backend, cfg)
    transcript_text = str(transcript.get("text") or "").strip()
    segments = [dict(row) for row in transcript.get("segments", []) if isinstance(row, Mapping)]
    transcript_path = item_dir / "transcript.txt"
    segments_path = item_dir / "segments.json"
    transcript_path.write_text(transcript_text, encoding="utf-8")
    segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = summarize_transcript(item, transcript_text, segments)
    information_value = classify_information_value(item, transcript_text, segments, content_type=content_type or "video")
    return _finish(
        item_dir,
        result,
        download_status="done",
        download_method=download.get("method", "local_file") if not local_existing else "local_file",
        asr_status="done",
        summary=summary["summary"],
        transcript_ref=str(transcript_path),
        segments_ref=str(segments_path),
        video_summary=summary,
        information_value=information_value,
    )


def _resolve_browser_media(url: str, config: ASRConfig, runner: Runner) -> Dict[str, Any]:
    if not url:
        return {}
    session = config.browser_session
    try:
        runner(["opencli", "browser", session, "--window", "foreground", "open", url], check=False, capture_output=True, text=True, timeout=60)
        runner(["opencli", "browser", session, "wait", "time", "5"], check=False, capture_output=True, text=True, timeout=30)
        result = runner(["opencli", "browser", session, "eval", _browser_media_extract_js()], check=False, capture_output=True, text=True, timeout=60)
        data = _parse_json_stdout(result.stdout or "")
        if not isinstance(data, Mapping):
            return {}
        return {
            "page_url": data.get("page_url", ""),
            "text": data.get("text", ""),
            "video_urls": _unique_urls(data.get("video_urls") or []),
            "image_urls": _unique_urls(data.get("image_urls") or []),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            runner(["opencli", "browser", session, "close"], check=False, capture_output=True, text=True, timeout=30)
        except Exception:
            pass


def _browser_media_extract_js() -> str:
    return r"""
(() => {
  const valid = (url) => typeof url === "string" && /^https?:\/\//.test(url);
  const videoUrls = Array.from(document.querySelectorAll("video"))
    .flatMap((video) => [video.currentSrc, video.src, video.querySelector("source")?.src])
    .filter(valid);
  const imageUrls = Array.from(document.querySelectorAll("img"))
    .filter((img) => img.naturalWidth >= 250 || img.naturalHeight >= 250)
    .flatMap((img) => [img.currentSrc, img.src, ...(img.srcset || "").split(",").map((part) => part.trim().split(/\s+/)[0])])
    .filter(valid)
    .filter((url) => !/douyinstatic\.com\/obj\/one-solution-center-external/.test(url));
  const bgUrls = Array.from(document.querySelectorAll("[style*='background-image']"))
    .map((node) => String(node.style.backgroundImage || "").match(/url\(["']?(.*?)["']?\)/)?.[1])
    .filter(valid);
  return JSON.stringify({
    page_url: location.href,
    text: (document.body?.innerText || "").slice(0, 1000),
    video_urls: Array.from(new Set(videoUrls)),
    image_urls: Array.from(new Set([...imageUrls, ...bgUrls]))
  });
})()
""".strip()


def _download_browser_video(video_urls: List[str], item_dir: Path, runner: Runner) -> Dict[str, Any]:
    if not video_urls:
        return {"ok": False, "error": "browser_video_url_missing"}
    target = item_dir / "browser_video.mp4"
    result = _download_url(video_urls[0], target, runner, referer="https://www.douyin.com/")
    if not result["ok"]:
        return {"ok": False, "error": "browser_video_download_failed", "stderr": result.get("stderr", "")}
    return {"ok": True, "video_path": target, "method": "browser_media_url"}


def _download_images(image_urls: List[str], item_dir: Path, runner: Runner) -> List[str]:
    refs: List[str] = []
    image_dir = item_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    for index, url in enumerate(_unique_urls(image_urls), start=1):
        suffix = _guess_suffix(url, ".jpg")
        target = image_dir / f"image_{index:03d}{suffix}"
        result = _download_url(url, target, runner, referer="https://www.douyin.com/")
        if result["ok"]:
            refs.append(str(target))
    return refs


def _download_url(url: str, target: Path, runner: Runner, referer: str = "") -> Dict[str, Any]:
    if not shutil.which("curl"):
        return {"ok": False, "stderr": "curl_missing"}
    command = [
        "curl",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        "120",
        "-A",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36",
    ]
    if referer:
        command.extend(["-e", referer])
    command.extend([url, "-o", str(target)])
    result = runner(command, check=False, capture_output=True, text=True, timeout=150)
    return {"ok": result.returncode == 0 and target.exists() and target.stat().st_size > 0, "stderr": (result.stderr or "")[-800:]}


def _parse_json_stdout(stdout: str) -> Any:
    text = (stdout or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


def _unique_urls(values: Any) -> List[str]:
    seen = set()
    urls: List[str] = []
    for value in values if isinstance(values, list) else []:
        url = str(value or "").strip()
        if not url or not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _guess_suffix(url: str, default: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov"}:
        return suffix
    return default


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


def classify_information_value(
    item: Mapping[str, Any],
    transcript: str,
    segments: List[Mapping[str, Any]],
    content_type: str = "video",
) -> Dict[str, Any]:
    """Classify whether a media item contains usable intelligence signal."""
    normalized_type = (content_type or "").lower()
    if normalized_type and normalized_type not in {"video", "mixed"}:
        return {
            "status": "needs_ocr",
            "reasons": ["image_or_non_video_content"],
            "matched_terms": [],
            "matched_entities": _matched_entities(_item_text(item)),
        }

    title_body = _item_text(item)
    transcript_text = re.sub(r"\s+", "", str(transcript or ""))
    combined = f"{title_body} {transcript or ''}"
    matched_terms = _matched_terms(combined)
    matched_entities = _matched_entities(combined)
    reasons: List[str] = []

    if matched_terms:
        reasons.append("risk_or_opportunity_terms")
    if matched_entities:
        reasons.append("local_entities")

    asr_low_signal = _is_low_signal_transcript(transcript_text, segments)
    if asr_low_signal:
        reasons.append("asr_low_signal")

    hard_terms = [term for term in matched_terms if term not in _WEAK_SOCIAL_TERMS]
    has_actionable_transcript = bool(hard_terms and any(term in (transcript or "") for term in hard_terms))
    has_strong_title_body = bool(hard_terms and len(title_body) >= 12)

    if asr_low_signal and not has_actionable_transcript and not has_strong_title_body:
        status = "low_value"
    elif hard_terms or has_actionable_transcript:
        status = "useful"
    elif matched_entities and not asr_low_signal and len(transcript_text) >= 20:
        status = "review_needed"
        reasons.append("entity_without_clear_actionable_term")
    else:
        status = "low_value" if asr_low_signal else "review_needed"

    return {
        "status": status,
        "reasons": reasons or ["no_clear_signal"],
        "matched_terms": matched_terms,
        "matched_entities": matched_entities,
        "transcript_char_count": len(transcript_text),
        "segment_count": len(segments),
    }


_RISK_TERMS = [
    "避雷",
    "投诉",
    "宰客",
    "排队",
    "堵车",
    "坑",
    "踩雷",
    "不推荐",
    "别去",
    "贵",
    "涨价",
    "限流",
    "停运",
    "封路",
    "事故",
    "退票",
]
_OPPORTUNITY_TERMS = [
    "攻略",
    "路线",
    "玩法",
    "体验",
    "推荐",
    "小众",
    "民宿",
    "旅拍",
    "预约",
    "建议",
    "省钱",
    "免费",
    "新开",
    "活动",
    "优惠",
]
_WEAK_SOCIAL_TERMS = {"推荐", "体验", "旅拍"}
_LOCAL_ENTITIES = ["阳朔", "遇龙河", "漓江", "竹筏", "西街", "如意峰", "桂林", "十里画廊", "兴坪"]


def _item_text(item: Mapping[str, Any]) -> str:
    return " ".join(str(item.get(key) or "") for key in ("title", "body", "description")).strip()


def _matched_terms(text: str) -> List[str]:
    return [term for term in [*_RISK_TERMS, *_OPPORTUNITY_TERMS] if term in text]


def _matched_entities(text: str) -> List[str]:
    return [term for term in _LOCAL_ENTITIES if term in text]


def _is_low_signal_transcript(transcript_text: str, segments: List[Mapping[str, Any]]) -> bool:
    if not transcript_text:
        return True
    if len(transcript_text) < 12:
        return True
    unique_chars = set(transcript_text)
    if len(unique_chars) <= max(4, len(transcript_text) // 8):
        return True
    if _has_periodic_repetition(transcript_text):
        return True
    if _repetition_ratio(transcript_text) >= 0.45:
        return True
    segment_texts = [str(row.get("text") or "").strip() for row in segments if isinstance(row, Mapping)]
    non_empty_segments = [text for text in segment_texts if text]
    if segments and not non_empty_segments:
        return True
    return False


def _has_periodic_repetition(text: str) -> bool:
    for size in range(4, max(5, len(text) // 2 + 1)):
        if len(text) % size != 0:
            continue
        chunk = text[:size]
        if chunk * (len(text) // size) == text:
            return True
    return False


def _repetition_ratio(text: str) -> float:
    if len(text) < 16:
        return 0.0
    repeated = 0
    for size in range(2, min(12, len(text) // 2) + 1):
        chunks = [text[index : index + size] for index in range(0, len(text) - size + 1, size)]
        if not chunks:
            continue
        counts = {chunk: chunks.count(chunk) for chunk in set(chunks)}
        repeated = max(repeated, max((count - 1) * size for count in counts.values()))
    return repeated / max(1, len(text))


def _download_video(url: str, item_dir: Path, config: ASRConfig, runner: Runner) -> Dict[str, Any]:
    if not shutil.which("yt-dlp"):
        return {"ok": False, "error": "yt_dlp_missing"}
    output_template = item_dir / "video.%(ext)s"
    command = ["yt-dlp", "--no-playlist", "--write-info-json", "-o", str(output_template)]
    if config.cookies_from_browser:
        command.extend(["--cookies-from-browser", config.cookies_from_browser])
    command.append(url)
    result = runner(command, check=False, capture_output=True, text=True, timeout=config.download_timeout_seconds)
    if result.returncode != 0:
        return {"ok": False, "error": "video_download_failed", "stderr": (result.stderr or "")[-800:]}
    video_path = _find_downloaded_video(item_dir)
    if not video_path:
        return {"ok": False, "error": "downloaded_video_missing"}
    return {"ok": True, "video_path": video_path}


def _extract_audio(video_path: Path, audio_path: Path, config: ASRConfig, runner: Runner) -> Dict[str, Any]:
    if not shutil.which("ffmpeg"):
        return {"ok": False, "error": "ffmpeg_missing"}
    command = ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)]
    result = runner(command, check=False, capture_output=True, text=True, timeout=config.audio_timeout_seconds)
    return {"ok": result.returncode == 0, "error": "audio_extract_failed" if result.returncode else "", "stderr": (result.stderr or "")[-800:]}


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
    if backend == "mlx_whisper_cli":
        return _run_mlx_whisper_cli(audio_path, config)
    return {"text": "", "segments": []}


def _run_mlx_whisper_cli(audio_path: Path, config: ASRConfig) -> Dict[str, Any]:
    executable = _mlx_whisper_cli()
    if not executable:
        return {"text": "", "segments": []}
    output_dir = audio_path.parent / "mlx_whisper"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = "transcript"
    command = [
        str(executable),
        str(audio_path),
        "--model",
        f"mlx-community/whisper-{config.model}-mlx",
        "--language",
        config.language,
        "--output-dir",
        str(output_dir),
        "--output-name",
        output_name,
        "--output-format",
        "json",
        "--verbose",
        "False",
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=1800)
    data = json.loads((output_dir / f"{output_name}.json").read_text(encoding="utf-8"))
    rows = [
        {"start": round(seg.get("start", 0), 2), "end": round(seg.get("end", 0), 2), "text": str(seg.get("text", "")).strip()}
        for seg in data.get("segments", [])
    ]
    return {"text": str(data.get("text", "")).strip(), "segments": rows}


def _find_existing_media(item: Mapping[str, Any]) -> Path | None:
    media = item.get("media") if isinstance(item.get("media"), Mapping) else {}
    for value in (item.get("local_video_path"), media.get("local_video_path") if isinstance(media, Mapping) else ""):
        if value and Path(str(value)).exists():
            return Path(str(value))
    return None


def _find_downloaded_video(item_dir: Path) -> Path | None:
    blocked_suffixes = {".json", ".part", ".ytdl", ".wav", ".txt"}
    for path in sorted(item_dir.iterdir()):
        if path.is_file() and path.suffix.lower() not in blocked_suffixes and path.name != "asr_result.json":
            return path
    return None


def _item_id(item: Mapping[str, Any]) -> str:
    raw = str(item.get("item_id") or item.get("platform_item_id") or item.get("content_id") or item.get("url") or item.get("title") or "item")
    return "".join(char if char.isalnum() else "_" for char in raw)[-80:] or "item"


def _finish(item_dir: Path, result: Dict[str, Any], **updates: Any) -> Dict[str, Any]:
    result.update(updates)
    (item_dir / "asr_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _module_exists(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _mlx_whisper_cli() -> str:
    executable = shutil.which("mlx_whisper")
    if executable:
        return executable
    # V0.2.6: removed hardcoded personal path; try common user-site locations
    import site
    for base in site.getusersitepackages(), site.getusersitepackages().replace('site-packages', 'bin'):
        if base:
            candidate = Path(base).parent / 'bin' / 'mlx_whisper'
            if candidate.exists():
                return str(candidate)
    return ""
