from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from threading import Lock
from urllib.parse import unquote
import zipfile


EXTRACTOR_VERSION = "2.0"
SUPPORTED = {".docx", ".pdf"}
RASTER_IMAGES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
MIN_PDF_PAGE_CHARS = 40
IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?P<target>[^)]+)\)(?:\{[^}\n]*\})?")


@dataclass
class ConversionResult:
    source: str
    output: str
    status: str = "ok"
    repaired_docx: bool = False
    asset_dir: str = ""
    media_files: int = 0
    images_with_ocr: int = 0
    ocr_characters: int = 0
    pdf_pages_ocr: int = 0
    warnings: list[str] = field(default_factory=list)


class OcrEngine:
    def __init__(self, enabled: bool, workers: int):
        self.enabled = enabled
        self.workers = max(1, workers)
        self.language = ""
        self.warning = ""
        self._cache: dict[str, str] = {}
        self._lock = Lock()

        if not enabled:
            return

        try:
            stdout, _ = run_command(["tesseract", "--list-langs"])
        except RuntimeError as exc:
            self.enabled = False
            self.warning = f"OCR disabled: {exc}"
            return

        languages = set(stdout.splitlines())
        if "chi_sim" in languages and "eng" in languages:
            self.language = "chi_sim+eng"
        elif "eng" in languages:
            self.language = "eng"
            self.warning = "chi_sim is unavailable; OCR is limited to English."
        else:
            self.enabled = False
            self.warning = "OCR disabled: neither chi_sim nor eng is installed."

    def read(self, image: Path, cache_key: str | None = None) -> str:
        if not self.enabled:
            return ""

        key = cache_key or sha256_file(image)
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            stdout, _ = run_command(
                [
                    "tesseract",
                    str(image),
                    "stdout",
                    "-l",
                    self.language,
                    "--psm",
                    "6",
                ],
                timeout=300,
            )
            text = clean_ocr_text(stdout)
        except RuntimeError:
            text = ""

        with self._lock:
            self._cache[key] = text
        return text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 900,
    accepted_codes: tuple[int, ...] = (0,),
) -> tuple[str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Command failed: {command[0]}: {exc}") from exc

    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode not in accepted_codes:
        message = stderr.strip() or stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{command[0]}: {message}")
    return stdout, stderr


def metadata_value(markdown: Path, key: str) -> str | None:
    if not markdown.exists():
        return None
    try:
        head = markdown.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return None
    match = re.search(rf"^{re.escape(key)}:\s*\"?([^\"\n]+)\"?\s*$", head, re.MULTILINE)
    return match.group(1) if match else None


def output_path(root: Path, out_root: Path, source: Path) -> Path:
    relative = source.relative_to(root)
    return out_root / relative.parent / f"{relative.name}.md"


def asset_path(markdown: Path) -> Path:
    # Pandoc does not escape spaces/parentheses in media paths reliably.
    # A short path-derived ID keeps every document isolated and Markdown-safe.
    digest = hashlib.sha256(markdown.name.encode("utf-8")).hexdigest()[:16]
    return markdown.parent / f"_assets_{digest}"


def local_image_path(markdown: Path, target: str) -> Path | None:
    target = target.strip().strip("<>")
    if target.startswith(("http://", "https://", "data:")):
        return None
    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    return (markdown.parent / target).resolve()


def broken_image_references(markdown: Path) -> list[str]:
    try:
        text = markdown.read_text(encoding="utf-8")
    except OSError as exc:
        return [str(exc)]

    broken: list[str] = []
    for match in IMAGE_RE.finditer(text):
        target = match.group("target")
        local = local_image_path(markdown, target)
        if local is not None and not local.is_file():
            broken.append(target)
    return sorted(set(broken))


def output_is_current(markdown: Path, source_hash: str) -> bool:
    return (
        metadata_value(markdown, "source_sha256") == source_hash
        and metadata_value(markdown, "extractor_version") == EXTRACTOR_VERSION
        and not broken_image_references(markdown)
    )


def discover_sources(root: Path, out_root: Path) -> list[Path]:
    sources: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        relative_parts = set(path.relative_to(root).parts)
        if ".git" in relative_parts or ".github" in relative_parts or out_root.name in relative_parts:
            continue
        sources.append(path)
    return sorted(sources)


def clean_ocr_text(text: str) -> str:
    text = text.replace("\x0c", "").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text if len(re.sub(r"\s+", "", text)) >= 2 else ""


def ocr_block(text: str) -> str:
    lines = text.splitlines() or [text]
    quoted = "\n".join("> " + line if line else ">" for line in lines)
    return (
        "\n\n<!-- image-ocr:start -->\n"
        "> **图片 OCR（自动识别，可能含误差）：**\n>\n"
        f"{quoted}\n"
        "<!-- image-ocr:end -->"
    )


def add_image_ocr(
    body: str,
    markdown: Path,
    ocr: OcrEngine,
) -> tuple[str, int, int, list[str]]:
    references: dict[str, Path] = {}
    unsupported: list[str] = []
    for match in IMAGE_RE.finditer(body):
        target = match.group("target")
        image = local_image_path(markdown, target)
        if image is None or not image.is_file():
            continue
        if image.suffix.lower() in RASTER_IMAGES:
            references[target] = image
        else:
            unsupported.append(image.name)

    results: dict[str, str] = {}
    if ocr.enabled and references:
        with ThreadPoolExecutor(max_workers=ocr.workers) as executor:
            futures = {executor.submit(ocr.read, image): target for target, image in references.items()}
            for future in as_completed(futures):
                target = futures[future]
                results[target] = future.result()

    def replace(match: re.Match[str]) -> str:
        text = results.get(match.group("target"), "")
        return match.group(0) + ocr_block(text) if text else match.group(0)

    body = IMAGE_RE.sub(replace, body)
    ocr_texts = [text for text in results.values() if text]
    warnings: list[str] = []
    if unsupported:
        warnings.append("OCR skipped unsupported image formats: " + ", ".join(sorted(set(unsupported))[:10]))
    return body, len(ocr_texts), sum(len(text) for text in ocr_texts), warnings


def repack_docx(source: Path, destination: Path) -> None:
    unpacked = destination.parent / "unpacked"
    unpacked.mkdir(parents=True, exist_ok=True)
    run_command(
        ["unzip", "-qq", str(source), "-d", str(unpacked)],
        accepted_codes=(0, 1),
    )
    if not (unpacked / "word" / "document.xml").is_file():
        raise RuntimeError("DOCX repair failed: word/document.xml is missing")

    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        strict_timestamps=False,
    ) as archive:
        for path in sorted(unpacked.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(unpacked).as_posix())


def convert_docx(
    source: Path,
    markdown: Path,
    ocr: OcrEngine,
) -> tuple[str, bool, int, int, int, list[str]]:
    markdown.parent.mkdir(parents=True, exist_ok=True)
    assets = asset_path(markdown)
    shutil.rmtree(assets, ignore_errors=True)

    def pandoc(document: Path) -> str:
        stdout, _ = run_command(
            [
                "pandoc",
                str(document.resolve()),
                "--from=docx",
                "--to=markdown+tex_math_dollars",
                "--wrap=none",
                f"--extract-media={assets.name}",
            ],
            cwd=markdown.parent,
        )
        return stdout

    repaired = False
    try:
        body = pandoc(source)
    except RuntimeError as original_error:
        shutil.rmtree(assets, ignore_errors=True)
        try:
            with tempfile.TemporaryDirectory(prefix="docx-repair-") as temporary:
                repaired_docx = Path(temporary) / "repaired.docx"
                repack_docx(source, repaired_docx)
                body = pandoc(repaired_docx)
            repaired = True
        except RuntimeError as repair_error:
            raise RuntimeError(f"{original_error}; repair fallback: {repair_error}") from repair_error

    media = [path for path in assets.rglob("*") if path.is_file()] if assets.exists() else []
    body, ocr_count, ocr_chars, warnings = add_image_ocr(body, markdown, ocr)
    return body, repaired, len(media), ocr_count, ocr_chars, warnings


def pdf_page_count(source: Path) -> int:
    stdout, _ = run_command(["pdfinfo", str(source)])
    match = re.search(r"^Pages:\s+(\d+)\s*$", stdout, re.MULTILINE)
    return int(match.group(1)) if match else 1


def convert_pdf(
    source: Path,
    source_hash: str,
    ocr: OcrEngine,
) -> tuple[str, int, int, list[str]]:
    stdout, _ = run_command(["pdftotext", "-layout", str(source), "-"])
    pages = stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()

    page_count = pdf_page_count(source)
    pages.extend([""] * max(0, page_count - len(pages)))
    pages = pages[:page_count]
    low_text_pages = [
        number
        for number, text in enumerate(pages, start=1)
        if len(re.sub(r"\s+", "", text)) < MIN_PDF_PAGE_CHARS
    ]

    warnings: list[str] = []
    ocr_pages = 0
    ocr_chars = 0
    if low_text_pages and not ocr.enabled:
        warnings.append(f"{len(low_text_pages)} PDF page(s) have too little text and OCR is unavailable.")
    elif low_text_pages:
        with tempfile.TemporaryDirectory(prefix="pdf-ocr-") as temporary:
            temp_root = Path(temporary)
            for page_number in low_text_pages:
                prefix = temp_root / f"page-{page_number:04d}"
                run_command(
                    [
                        "pdftoppm",
                        "-f",
                        str(page_number),
                        "-l",
                        str(page_number),
                        "-r",
                        "220",
                        "-png",
                        "-singlefile",
                        str(source),
                        str(prefix),
                    ],
                    timeout=600,
                )
                image = prefix.with_suffix(".png")
                text = ocr.read(image, cache_key=f"pdf:{source_hash}:{page_number}")
                if text:
                    pages[page_number - 1] = f"<!-- 第 {page_number} 页使用 OCR 回退 -->\n{text}"
                    ocr_pages += 1
                    ocr_chars += len(text)
                elif not pages[page_number - 1].strip():
                    warnings.append(f"PDF page {page_number} produced no text, including OCR.")

    body = "\n\n---\n\n".join(page.strip() for page in pages)
    if len(re.sub(r"\s+", "", body)) < 100:
        warnings.append("The PDF still contains very little readable text after extraction.")
    return body, ocr_pages, ocr_chars, warnings


def build_markdown(
    source: Path,
    root: Path,
    body: str,
    source_hash: str,
    result: ConversionResult,
    ocr: OcrEngine,
) -> str:
    relative = source.relative_to(root).as_posix()
    status = "needs_review" if result.warnings else "ok"
    result.status = status
    metadata = (
        "---\n"
        "generated_by: extract_to_md.py\n"
        f'extractor_version: "{EXTRACTOR_VERSION}"\n'
        f"source: {json.dumps(relative, ensure_ascii=False)}\n"
        f'source_sha256: "{source_hash}"\n'
        f"status: {status}\n"
        f"ocr_language: {json.dumps(ocr.language or 'disabled')}\n"
        f"repaired_docx: {str(result.repaired_docx).lower()}\n"
        f"asset_dir: {json.dumps(result.asset_dir)}\n"
        f"media_files: {result.media_files}\n"
        f"images_with_ocr: {result.images_with_ocr}\n"
        f"ocr_characters: {result.ocr_characters}\n"
        f"pdf_pages_ocr: {result.pdf_pages_ocr}\n"
        "---\n\n"
    )
    warning_text = ""
    if result.warnings:
        warning_text = "> ⚠️ 自动提取提示：" + "；".join(result.warnings) + "\n\n"
    return metadata + f"# {source.name}\n\n" + warning_text + body.strip() + "\n"


def convert_one(
    source: Path,
    root: Path,
    out_root: Path,
    source_hash: str,
    ocr: OcrEngine,
) -> ConversionResult:
    markdown = output_path(root, out_root, source)
    relative_source = source.relative_to(root).as_posix()
    relative_output = markdown.relative_to(root).as_posix()
    result = ConversionResult(source=relative_source, output=relative_output)

    if source.suffix.lower() == ".docx":
        body, repaired, media_count, ocr_count, ocr_chars, warnings = convert_docx(source, markdown, ocr)
        result.repaired_docx = repaired
        result.asset_dir = asset_path(markdown).name if media_count else ""
        result.media_files = media_count
        result.images_with_ocr = ocr_count
        result.ocr_characters = ocr_chars
        result.warnings.extend(warnings)
        if media_count and not ocr.enabled:
            result.warnings.append("Embedded images were exported, but OCR is unavailable.")
    else:
        body, ocr_pages, ocr_chars, warnings = convert_pdf(source, source_hash, ocr)
        result.pdf_pages_ocr = ocr_pages
        result.ocr_characters = ocr_chars
        result.warnings.extend(warnings)

    if ocr.warning:
        result.warnings.append(ocr.warning)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(build_markdown(source, root, body, source_hash, result, ocr), encoding="utf-8")
    return result


def prune_stale_outputs(root: Path, out_root: Path, expected: set[Path]) -> list[str]:
    removed: list[str] = []
    if not out_root.exists():
        return removed
    for markdown in out_root.rglob("*.md"):
        if not markdown.name.lower().endswith((".docx.md", ".pdf.md")):
            continue
        if markdown in expected or metadata_value(markdown, "generated_by") != "extract_to_md.py":
            continue
        removed.append(markdown.relative_to(root).as_posix())
        markdown.unlink()
        shutil.rmtree(asset_path(markdown), ignore_errors=True)
    return removed


def validate_outputs(sources: list[Path], root: Path, out_root: Path) -> list[str]:
    errors: list[str] = []
    for source in sources:
        markdown = output_path(root, out_root, source)
        relative = source.relative_to(root).as_posix()
        if not markdown.is_file():
            errors.append(f"Missing Markdown: {relative}")
            continue
        if metadata_value(markdown, "source_sha256") != sha256_file(source):
            errors.append(f"Stale or malformed metadata: {relative}")
        broken = broken_image_references(markdown)
        if broken:
            errors.append(f"Broken image references ({len(broken)}): {relative}")
    return errors


def metadata_integer(markdown: Path, key: str) -> int:
    value = metadata_value(markdown, key)
    try:
        return int(value) if value is not None else 0
    except ValueError:
        return 0


def build_inventory(sources: list[Path], root: Path, out_root: Path) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for source in sources:
        markdown = output_path(root, out_root, source)
        inventory.append(
            {
                "source": source.relative_to(root).as_posix(),
                "output": markdown.relative_to(root).as_posix(),
                "status": metadata_value(markdown, "status") or "missing",
                "repaired_docx": metadata_value(markdown, "repaired_docx") == "true",
                "asset_dir": metadata_value(markdown, "asset_dir") or "",
                "media_files": metadata_integer(markdown, "media_files"),
                "images_with_ocr": metadata_integer(markdown, "images_with_ocr"),
                "ocr_characters": metadata_integer(markdown, "ocr_characters"),
                "pdf_pages_ocr": metadata_integer(markdown, "pdf_pages_ocr"),
            }
        )
    return inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract DOCX/PDF notes into GPT-readable Markdown.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--force", action="store_true", help="Regenerate even current outputs.")
    parser.add_argument("--no-ocr", action="store_true", help="Disable Tesseract OCR.")
    parser.add_argument("--only", action="append", default=[], help="Process one source path relative to root.")
    parser.add_argument("--ocr-workers", type=int, default=max(1, min(2, os.cpu_count() or 1)))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    out_root = root / "_extracted"
    all_sources = discover_sources(root, out_root)
    full_run = not args.only

    if args.only:
        selected = {(root / item).resolve() for item in args.only}
        sources = [path for path in all_sources if path.resolve() in selected]
        missing_selection = selected - {path.resolve() for path in sources}
        if missing_selection:
            for path in sorted(missing_selection):
                print(f"[ERROR] Requested source not found: {path}", file=sys.stderr)
            return 2
    else:
        sources = all_sources

    ocr = OcrEngine(enabled=not args.no_ocr, workers=args.ocr_workers)
    print(f"Found {len(all_sources)} supported files; processing {len(sources)}.")
    print(f"OCR: {ocr.language or 'disabled'}")

    converted: list[ConversionResult] = []
    skipped: list[str] = []
    failures: list[dict[str, str]] = []

    for source in sources:
        relative = source.relative_to(root).as_posix()
        markdown = output_path(root, out_root, source)
        source_hash = sha256_file(source)
        if not args.force and output_is_current(markdown, source_hash):
            print(f"[SKIP] {relative}")
            skipped.append(relative)
            continue

        print(f"[CONVERT] {relative}")
        try:
            converted.append(convert_one(source, root, out_root, source_hash, ocr))
        except Exception as exc:
            print(f"[ERROR] {relative}: {exc}", file=sys.stderr)
            failures.append({"source": relative, "error": str(exc)})

    expected = {output_path(root, out_root, source) for source in all_sources}
    removed = prune_stale_outputs(root, out_root, expected) if full_run else []
    validation_errors = validate_outputs(all_sources if full_run else sources, root, out_root)
    inventory = build_inventory(all_sources, root, out_root)

    report = {
        "extractor_version": EXTRACTOR_VERSION,
        "source_files": len(all_sources),
        "processed_files": len(sources),
        "converted": len(converted),
        "skipped": len(skipped),
        "failed": len(failures),
        "needs_review": sum(item["status"] == "needs_review" for item in inventory),
        "removed_stale_outputs": removed,
        "ocr_language": ocr.language or "disabled",
        "run_results": [asdict(item) for item in converted],
        "inventory": inventory,
        "failures": failures,
        "validation_errors": validation_errors,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_conversion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"Converted: {len(converted)}")
    print(f"Skipped:   {len(skipped)}")
    print(f"Failed:    {len(failures)}")
    print(f"Validation errors: {len(validation_errors)}")
    if failures or validation_errors:
        print("Extraction is incomplete; refusing to report success.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
