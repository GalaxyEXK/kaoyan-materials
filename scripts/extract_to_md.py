from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "_extracted"

SUPPORTED = {".docx", ".pdf"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def old_hash(md_path: Path):
    if not md_path.exists():
        return None

    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")[:2000]
        m = re.search(
            r'^source_sha256:\s*"?([0-9a-f]{64})"?\s*$',
            text,
            re.MULTILINE,
        )
        return m.group(1) if m else None
    except Exception:
        return None


def run_command(cmd):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(stderr)

    return result.stdout.decode("utf-8", errors="replace")


def convert_docx(src: Path) -> str:
    # Pandoc 对真正的 Word Equation / OMML 数学公式
    # 通常能够转换为 Markdown 中的 TeX 数学表达式。
    return run_command([
        "pandoc",
        str(src),
        "--from=docx",
        "--to=markdown+tex_math_dollars",
        "--wrap=none",
    ])


def convert_pdf(src: Path) -> str:
    # V1：提取 PDF 自带文本层。
    text = run_command([
        "pdftotext",
        "-layout",
        str(src),
        "-"
    ])

    # pdftotext 用分页符区分页，这里改成 Markdown 分隔符。
    text = text.replace("\f", "\n\n---\n\n")

    if len(text.strip()) < 100:
        return (
            "> ⚠️ 此 PDF 没有提取到足够的文本。"
            "它可能是扫描版 PDF，需要 OCR。\n\n"
            + text
        )

    return text


def output_path(src: Path) -> Path:
    rel = src.relative_to(ROOT)

    # 保留原扩展名，避免同目录的 xxx.pdf 和 xxx.docx 冲突。
    # 例如：
    # 原文件：数学/高数/test.docx
    # 输出：_extracted/数学/高数/test.docx.md
    return OUT_ROOT / rel.parent / f"{rel.name}.md"


def build_markdown(src: Path, body: str, file_hash: str) -> str:
    rel = src.relative_to(ROOT).as_posix()

    metadata = (
        "---\n"
        "generated_by: extract_to_md.py\n"
        f"source: {json.dumps(rel, ensure_ascii=False)}\n"
        f'source_sha256: "{file_hash}"\n'
        "---\n\n"
    )

    title = f"# {src.name}\n\n"

    return metadata + title + body.strip() + "\n"


def should_ignore(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)

    return (
        ".git" in parts
        or "_extracted" in parts
        or ".github" in parts
    )


def main():
    sources = []

    for path in ROOT.rglob("*"):
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED
            and not should_ignore(path)
        ):
            sources.append(path)

    print(f"Found {len(sources)} supported files.")

    converted = 0
    skipped = 0
    failed = 0

    for src in sorted(sources):
        rel = src.relative_to(ROOT)
        out = output_path(src)

        current_hash = sha256_file(src)

        if old_hash(out) == current_hash:
            print(f"[SKIP] {rel}")
            skipped += 1
            continue

        print(f"[CONVERT] {rel}")

        try:
            if src.suffix.lower() == ".docx":
                body = convert_docx(src)
            elif src.suffix.lower() == ".pdf":
                body = convert_pdf(src)
            else:
                continue

            out.parent.mkdir(parents=True, exist_ok=True)

            md = build_markdown(src, body, current_hash)
            out.write_text(md, encoding="utf-8")

            converted += 1

        except Exception as e:
            print(f"[ERROR] {rel}: {e}", file=sys.stderr)
            failed += 1

    print()
    print(f"Converted: {converted}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")

    # 个别坏文件不要导致整个批处理完全失败
    if failed:
        print(
            "Some files failed. Other successfully converted files "
            "will still be committed."
        )


if __name__ == "__main__":
    main()
