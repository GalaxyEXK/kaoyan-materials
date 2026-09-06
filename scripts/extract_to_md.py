from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "_extracted"

MINERU_PROFILE = "mineru-vlm-v1"
FALLBACK_DOCX_PROFILE = "fallback-pandoc-v1"
FALLBACK_PDF_PROFILE = "fallback-pdftotext-v1"

SUPPORTED = {".docx", ".pdf"}
SKIP_DIRS = {".git", ".github", "_extracted", "__pycache__"}
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)(?:\{[^}\n]*\})?")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

API_BASE = "https://mineru.net/api/v4"
BATCH_SIZE = max(1, min(50, int(os.getenv("MINERU_BATCH_SIZE", "10"))))
POLL_SECONDS = max(3, int(os.getenv("MINERU_POLL_SECONDS", "10")))
TIMEOUT_SECONDS = max(60, int(os.getenv("MINERU_TIMEOUT_SECONDS", "3600")))
MAX_FILES = max(0, int(os.getenv("MINERU_MAX_FILES", "0")))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def destination_for(source: Path) -> Path:
    rel = source.relative_to(ROOT)
    return OUT_ROOT / (rel.as_posix() + ".md")


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def metadata_block(source: Path, digest: str, profile: str) -> str:
    rel = source.relative_to(ROOT).as_posix()
    return (
        "---\n"
        "generated_by: extract_to_md.py\n"
        f"source: {yaml_string(rel)}\n"
        f'source_sha256: "{digest}"\n'
        f'extractor_profile: "{profile}"\n'
        "---\n\n"
    )


def read_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}

    meta: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        value = value.strip()
        try:
            parsed = json.loads(value)
            if isinstance(parsed, str):
                value = parsed
        except Exception:
            value = value.strip("\"'")
        meta[key.strip()] = value
    return meta


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def useful_chars(text: str) -> int:
    text = FRONT_MATTER_RE.sub("", text, count=1)
    text = IMAGE_RE.sub("", text)
    text = HTML_IMAGE_RE.sub("", text)
    return len(re.sub(r"\s+", "", text))


def output_is_current(source: Path, dest: Path, digest: str) -> bool:
    if not dest.exists():
        return False

    meta = read_metadata(dest)
    if meta.get("source_sha256") != digest:
        return False

    profile = meta.get("extractor_profile", "")
    if profile in {MINERU_PROFILE, FALLBACK_DOCX_PROFILE, FALLBACK_PDF_PROFILE}:
        return True

    text = read_text(dest)

    # Existing PDFs with a matching source hash are kept as-is to avoid a costly
    # one-time cloud migration of the whole PDF archive. New/changed PDFs use MinerU.
    if source.suffix.lower() == ".pdf":
        return useful_chars(text) >= 200

    # Existing DOCX outputs are only migrated when they are clearly not GPT-readable:
    # e.g. they mainly contain unresolved Pandoc image links or almost no text.
    has_images = IMAGE_RE.search(text) is not None or HTML_IMAGE_RE.search(text) is not None
    return not has_images and useful_chars(text) >= 120


def run(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )


def strip_local_images(markdown: str) -> str:
    def repl(match: re.Match[str]) -> str:
        alt = match.group(1).strip()
        return f"\n> [图像内容已由 MinerU 解析：{alt}]\n" if alt else "\n"

    markdown = IMAGE_RE.sub(repl, markdown)
    markdown = HTML_IMAGE_RE.sub("", markdown)
    return markdown.strip()


def write_output(source: Path, digest: str, profile: str, body: str) -> None:
    dest = destination_for(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    title = f"# {source.name}\n\n"
    dest.write_text(
        metadata_block(source, digest, profile) + title + body.strip() + "\n",
        encoding="utf-8",
    )


def fallback_docx(source: Path, digest: str) -> str:
    if not shutil.which("pandoc"):
        raise RuntimeError("pandoc is not installed")

    result = run(
        [
            "pandoc",
            str(source.resolve()),
            "-t",
            "gfm",
            "--wrap=none",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"pandoc exit {result.returncode}")

    body = strip_local_images(result.stdout)
    if useful_chars(body) < 40:
        body = (
            "> ⚠️ MinerU 解析失败，Pandoc 也没有提取到足够正文。"
            "该文件可能主要由图片组成，建议稍后重新触发 MinerU。\n"
        )
    return body


def fallback_pdf(source: Path, digest: str) -> str:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext is not installed")

    result = run(["pdftotext", "-layout", str(source.resolve()), "-"])
    text = result.stdout if result.returncode == 0 else ""
    if useful_chars(text) < 200:
        return (
            "> ⚠️ MinerU 解析失败，本地 PDF 文本层也不足。"
            "这很可能是扫描版 PDF，建议稍后重新触发 MinerU。\n"
        )
    return text.replace("\f", "\n\n---\n\n").strip()


def fallback_one(source: Path, digest: str, reason: str) -> None:
    rel = source.relative_to(ROOT).as_posix()
    print(f"::warning::MinerU failed for {rel}; using local fallback: {reason}", flush=True)
    if source.suffix.lower() == ".docx":
        body = fallback_docx(source, digest)
        profile = FALLBACK_DOCX_PROFILE
    else:
        body = fallback_pdf(source, digest)
        profile = FALLBACK_PDF_PROFILE
    write_output(source, digest, profile, body)


def data_id_for(source: Path, digest: str) -> str:
    rel = source.relative_to(ROOT).as_posix()
    path_hash = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:12]
    return f"d_{digest[:20]}_{path_hash}"


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }


def request_upload_urls(
    sources: list[Path], digests: dict[Path, str], token: str
) -> tuple[str, list[str], dict[str, Path]]:
    entries = []
    mapping: dict[str, Path] = {}

    for source in sources:
        data_id = data_id_for(source, digests[source])
        mapping[data_id] = source
        entries.append(
            {
                "name": source.name,
                "data_id": data_id,
                "is_ocr": True,
            }
        )

    payload = {
        "files": entries,
        "model_version": "vlm",
        "language": "ch",
        "enable_formula": True,
        "enable_table": True,
    }
    response = requests.post(
        f"{API_BASE}/file-urls/batch",
        headers=auth_headers(token),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 0:
        raise RuntimeError(result.get("msg") or "MinerU upload-url request failed")

    data = result.get("data") or {}
    batch_id = data.get("batch_id")
    urls = data.get("file_urls") or []
    if not batch_id or len(urls) != len(sources):
        raise RuntimeError("MinerU returned an invalid batch_id/file_urls response")

    return batch_id, urls, mapping


def upload_sources(sources: list[Path], urls: list[str]) -> None:
    for source, upload_url in zip(sources, urls):
        rel = source.relative_to(ROOT).as_posix()
        print(f"[mineru upload] {rel}", flush=True)
        with source.open("rb") as f:
            response = requests.put(upload_url, data=f, timeout=600)
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"upload failed for {rel}: HTTP {response.status_code}"
            )


def download_full_markdown(zip_url: str) -> str:
    response = requests.get(zip_url, timeout=300)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if name.lower().endswith("full.md") and not name.endswith("/")
        ]
        if not candidates:
            candidates = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".md") and not name.endswith("/")
            ]
        if not candidates:
            raise RuntimeError("MinerU result ZIP contains no Markdown file")

        chosen = sorted(
            candidates,
            key=lambda n: (0 if n.lower().endswith("full.md") else 1, len(n)),
        )[0]
        raw = archive.read(chosen)

    text = raw.decode("utf-8", errors="replace")
    text = strip_local_images(text)
    if useful_chars(text) < 40:
        raise RuntimeError("MinerU Markdown result is unexpectedly empty")
    return text


def poll_batch(
    batch_id: str,
    mapping: dict[str, Path],
    digests: dict[Path, str],
    token: str,
) -> tuple[set[Path], dict[Path, str]]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    completed: set[Path] = set()
    failures: dict[Path, str] = {}

    while time.monotonic() < deadline:
        response = requests.get(
            f"{API_BASE}/extract-results/batch/{batch_id}",
            headers=auth_headers(token),
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("code") != 0:
            raise RuntimeError(result.get("msg") or "MinerU batch status request failed")

        data = result.get("data") or {}
        items = data.get("extract_result") or []

        states: list[str] = []
        for item in items:
            data_id = item.get("data_id")
            source = mapping.get(data_id)

            if source is None:
                file_name = item.get("file_name")
                matches = [p for p in mapping.values() if p.name == file_name]
                if len(matches) == 1:
                    source = matches[0]
            if source is None:
                continue

            state = str(item.get("state") or "")
            states.append(state)

            if state == "done" and source not in completed:
                zip_url = item.get("full_zip_url")
                if not zip_url:
                    failures[source] = "done result did not contain full_zip_url"
                    completed.add(source)
                    continue
                try:
                    markdown = download_full_markdown(zip_url)
                    write_output(source, digests[source], MINERU_PROFILE, markdown)
                    print(
                        f"[mineru done] {source.relative_to(ROOT).as_posix()}",
                        flush=True,
                    )
                except Exception as exc:
                    failures[source] = str(exc)
                completed.add(source)

            elif state == "failed" and source not in completed:
                failures[source] = item.get("err_msg") or "MinerU reported failed"
                completed.add(source)

        if len(completed) >= len(mapping):
            return completed, failures

        waiting = len(mapping) - len(completed)
        summary = ",".join(sorted(set(states))) if states else "waiting-file"
        print(f"[mineru wait] batch={batch_id} pending={waiting} states={summary}", flush=True)
        time.sleep(POLL_SECONDS)

    for source in mapping.values():
        if source not in completed:
            failures[source] = f"timeout after {TIMEOUT_SECONDS}s"
    return completed, failures


def process_batch(
    sources: list[Path], digests: dict[Path, str], token: str
) -> tuple[int, int]:
    if not sources:
        return 0, 0

    try:
        batch_id, urls, mapping = request_upload_urls(sources, digests, token)
        print(f"[mineru batch] {batch_id} files={len(sources)}", flush=True)
        upload_sources(sources, urls)
        _, failures = poll_batch(batch_id, mapping, digests, token)
    except Exception as exc:
        failures = {source: str(exc) for source in sources}

    mineru_ok = len(sources) - len(failures)
    fallback_ok = 0

    for source, reason in failures.items():
        try:
            fallback_one(source, digests[source], reason)
            fallback_ok += 1
        except Exception as exc:
            rel = source.relative_to(ROOT).as_posix()
            print(f"::error::{rel}: MinerU and fallback both failed: {exc}", flush=True)

    return mineru_ok, fallback_ok


def source_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.name.startswith("~$"):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.as_posix().lower())


def validate_outputs() -> list[str]:
    errors: list[str] = []
    for md in OUT_ROOT.rglob("*.md"):
        meta = read_metadata(md)
        profile = meta.get("extractor_profile", "")
        if profile != MINERU_PROFILE:
            continue
        text = read_text(md)
        match = IMAGE_RE.search(text)
        if match:
            errors.append(
                f"{md.relative_to(ROOT)} contains unresolved image link: {match.group(0)}"
            )
        if useful_chars(text) < 40:
            errors.append(f"{md.relative_to(ROOT)} has too little readable text")
    return errors


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    token = os.getenv("MINERU_API_TOKEN", "").strip()
    if not token:
        print(
            "::warning::MINERU_API_TOKEN is missing; pending files will use local fallback.",
            flush=True,
        )

    digests: dict[Path, str] = {}
    pending: list[Path] = []
    scanned = 0
    skipped = 0

    for source in source_files():
        scanned += 1
        digest = sha256_file(source)
        digests[source] = digest
        dest = destination_for(source)

        if output_is_current(source, dest, digest):
            skipped += 1
            continue

        pending.append(source)

    if MAX_FILES:
        pending = pending[:MAX_FILES]

    print(
        f"Plan: sources={scanned}, skipped={skipped}, pending={len(pending)}, "
        f"mineru={'enabled' if token else 'disabled'}",
        flush=True,
    )

    mineru_ok = 0
    fallback_ok = 0
    hard_failures = 0

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start : start + BATCH_SIZE]

        if token:
            ok, fallback = process_batch(batch, digests, token)
            mineru_ok += ok
            fallback_ok += fallback
            hard_failures += len(batch) - ok - fallback
        else:
            for source in batch:
                try:
                    fallback_one(source, digests[source], "MINERU_API_TOKEN missing")
                    fallback_ok += 1
                except Exception as exc:
                    hard_failures += 1
                    rel = source.relative_to(ROOT).as_posix()
                    print(f"::error::{rel}: fallback failed: {exc}", flush=True)

    validation_errors = validate_outputs()
    for item in validation_errors:
        print(f"::error::{item}", flush=True)

    print(
        "\nSummary: "
        f"sources={scanned}, skipped={skipped}, pending_processed={len(pending)}, "
        f"mineru_ok={mineru_ok}, fallback_ok={fallback_ok}, "
        f"hard_failures={hard_failures}, validation_errors={len(validation_errors)}"
    )

    return 1 if hard_failures or validation_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
