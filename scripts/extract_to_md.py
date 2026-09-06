from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "_extracted"

DOCX_PROFILE = "docx-inline-ocr-v1"
PDF_PROFILE = "pdf-text-only-v1"

SUPPORTED = {".docx", ".pdf"}
SKIP_DIRS = {".git", ".github", "_extracted", "__pycache__"}
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)(?:\{[^}\n]*\})?")
FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


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


def output_is_current(source: Path, dest: Path, digest: str) -> bool:
    if not dest.exists():
        return False

    meta = read_metadata(dest)
    if meta.get("source_sha256") != digest:
        return False

    # Existing PDFs are intentionally grandfathered in. This prevents a one-time
    # migration from reprocessing a large archive of PDFs.
    if source.suffix.lower() == ".pdf":
        return True

    if meta.get("extractor_profile") != DOCX_PROFILE:
        return False

    try:
        body = dest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return IMAGE_RE.search(body) is None


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
        env=env,
    )


def normalize_ocr(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.splitlines()]

    compact: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            compact.append(line.strip())
            blank = False
        elif compact and not blank:
            compact.append("")
            blank = True

    while compact and not compact[-1]:
        compact.pop()
    return "\n".join(compact).strip()


def tesseract_image(path: Path) -> str:
    if not shutil.which("tesseract"):
        return ""

    env = os.environ.copy()
    env.setdefault("OMP_THREAD_LIMIT", "1")

    attempts = [
        ["tesseract", str(path), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
        ["tesseract", str(path), "stdout", "-l", "eng", "--psm", "6"],
    ]
    for args in attempts:
        result = run(args, timeout=120, env=env)
        if result.returncode == 0:
            text = normalize_ocr(result.stdout)
            if text:
                return text
    return ""


def quote_ocr(text: str, source_label: str) -> str:
    safe_label = source_label.replace("--", "—")
    if not text:
        return (
            f"<!-- source-image: {safe_label} -->\n\n"
            "> **图片 OCR：** 未识别到可用文字。\n"
        )

    quoted = "\n".join("> " + line if line else ">" for line in text.splitlines())
    return (
        f"<!-- source-image: {safe_label} -->\n\n"
        "> **图片 OCR：**\n>\n"
        f"{quoted}\n"
    )


def resolve_image_target(raw_target: str, base_dirs: list[Path]) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = unquote(target)

    # Pandoc media paths generated by this script do not contain a title suffix.
    # If a quoted title somehow appears, prefer the path before it.
    if ' "' in target:
        target = target.split(' "', 1)[0]

    raw_path = Path(target)
    if raw_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None

    candidates = [raw_path] if raw_path.is_absolute() else [base / raw_path for base in base_dirs]
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:
            pass
        if candidate.exists():
            return candidate

    return None


def inline_docx_ocr(markdown: str, base_dirs: list[Path]) -> tuple[str, int, int]:
    matches = list(IMAGE_RE.finditer(markdown))
    if not matches:
        return markdown, 0, 0

    unique: dict[Path, str] = {}
    labels: dict[Path, str] = {}
    unresolved = 0

    for match in matches:
        raw_target = match.group(2)
        image_path = resolve_image_target(raw_target, base_dirs)
        if image_path is None or not image_path.exists():
            unresolved += 1
            continue
        unique.setdefault(image_path, "")
        labels.setdefault(image_path, raw_target)

    workers = max(1, min(4, os.cpu_count() or 2))
    if unique:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(tesseract_image, path): path for path in unique}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    unique[path] = future.result()
                except Exception:
                    unique[path] = ""

    recognized = sum(1 for text in unique.values() if text)

    def replace(match: re.Match[str]) -> str:
        raw_target = match.group(2)
        image_path = resolve_image_target(raw_target, base_dirs)
        if image_path is None or not image_path.exists():
            return quote_ocr("", raw_target)
        return quote_ocr(unique.get(image_path, ""), labels.get(image_path, raw_target))

    return IMAGE_RE.sub(replace, markdown), recognized, unresolved


def convert_docx(source: Path, dest: Path, digest: str) -> tuple[int, int]:
    if not shutil.which("pandoc"):
        raise RuntimeError("pandoc is not installed")

    dest.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="kaoyan-docx-") as temp_name:
        temp_dir = Path(temp_name)
        media_root = temp_dir / "assets"

        result = run(
            [
                "pandoc",
                str(source.resolve()),
                "-t",
                "gfm",
                "--wrap=none",
                f"--extract-media={media_root}",
            ],
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "pandoc failed: " + (result.stderr.strip() or f"exit {result.returncode}")
            )

        markdown, recognized, unresolved = inline_docx_ocr(
            result.stdout,
            [ROOT, temp_dir, media_root],
        )

        # Never leave broken image links in GPT-facing Markdown.
        markdown = IMAGE_RE.sub(
            lambda m: quote_ocr("", m.group(2)),
            markdown,
        )

    title = f"# {source.name}\n\n"
    dest.write_text(
        metadata_block(source, digest, DOCX_PROFILE) + title + markdown.strip() + "\n",
        encoding="utf-8",
    )
    return recognized, unresolved


def convert_pdf(source: Path, dest: Path, digest: str) -> bool:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext is not installed")

    dest.parent.mkdir(parents=True, exist_ok=True)
    result = run(["pdftotext", "-layout", str(source.resolve()), "-"], timeout=600)

    text = normalize_ocr(result.stdout) if result.returncode == 0 else ""
    useful_chars = len(re.sub(r"\s+", "", text))

    title = f"# {source.name}\n\n"
    if useful_chars < 200:
        body = (
            "> ⚠️ **扫描型 PDF：轻量模式未自动 OCR。**\n>\n"
            "> 为避免 GitHub Actions 因逐页 OCR 跑数小时而超时，这类 PDF "
            "只做标记。需要时可以单独处理该文件。\n"
        )
        has_text = False
    else:
        body = text.replace("\f", "\n\n---\n\n").strip() + "\n"
        has_text = True

    dest.write_text(
        metadata_block(source, digest, PDF_PROFILE) + title + body,
        encoding="utf-8",
    )
    return has_text


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


def validate_gpt_outputs() -> list[str]:
    errors: list[str] = []
    for md in OUT_ROOT.rglob("*.docx.md"):
        meta = read_metadata(md)
        if meta.get("extractor_profile") != DOCX_PROFILE:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        match = IMAGE_RE.search(text)
        if match:
            errors.append(f"{md.relative_to(ROOT)} still contains image reference: {match.group(0)}")
    return errors


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    scanned = 0
    skipped = 0
    converted_docx = 0
    converted_pdf = 0
    pdf_scan_markers = 0
    ocr_images = 0
    warnings: list[str] = []

    for source in source_files():
        scanned += 1
        dest = destination_for(source)
        digest = sha256_file(source)

        if output_is_current(source, dest, digest):
            skipped += 1
            continue

        rel = source.relative_to(ROOT).as_posix()
        print(f"[convert] {rel}", flush=True)

        try:
            if source.suffix.lower() == ".docx":
                recognized, unresolved = convert_docx(source, dest, digest)
                converted_docx += 1
                ocr_images += recognized
                if unresolved:
                    warnings.append(f"{rel}: {unresolved} image reference(s) could not be resolved")
            else:
                has_text = convert_pdf(source, dest, digest)
                converted_pdf += 1
                if not has_text:
                    pdf_scan_markers += 1
        except Exception as exc:
            warnings.append(f"{rel}: {exc}")
            print(f"::warning::{rel}: {exc}", flush=True)

    validation_errors = validate_gpt_outputs()
    for item in validation_errors:
        print(f"::error::{item}", flush=True)

    print(
        "\nSummary: "
        f"sources={scanned}, skipped={skipped}, "
        f"docx_converted={converted_docx}, pdf_converted={converted_pdf}, "
        f"ocr_images_with_text={ocr_images}, scan_pdf_markers={pdf_scan_markers}, "
        f"warnings={len(warnings)}, validation_errors={len(validation_errors)}"
    )

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    return 1 if validation_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
