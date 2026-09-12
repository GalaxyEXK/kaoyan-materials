from __future__ import annotations

from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import time
from urllib.parse import quote, unquote
import zipfile

import requests

import extract_to_md as base

# V2 deliberately makes all legacy/v1 outputs stale once, so every document can
# acquire a persistent visual sidecar instead of losing its MinerU image crops.
base.MINERU_PROFILE = "mineru-vlm-assets-v2"
base.FALLBACK_DOCX_PROFILE = "fallback-pandoc-assets-v2"
base.FALLBACK_PDF_PROFILE = "fallback-pdftotext-v2"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".jp2"}
HTML_IMAGE_SRC_RE = re.compile(r"<img\b[^>]*?\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)


def assets_dir_for(source: Path) -> Path:
    rel = source.relative_to(base.ROOT)
    return base.OUT_ROOT / (rel.as_posix() + ".assets")


def figures_manifest_for(source: Path) -> Path:
    rel = source.relative_to(base.ROOT)
    return base.OUT_ROOT / (rel.as_posix() + ".figures.md")


def output_is_current(source: Path, dest: Path, digest: str) -> bool:
    # Never downgrade the existing archive if the MinerU secret is temporarily unavailable.
    if not os.getenv("MINERU_API_TOKEN", "").strip():
        return ORIGINAL_OUTPUT_IS_CURRENT(source, dest, digest)
    if not dest.exists():
        return False
    meta = base.read_metadata(dest)
    if meta.get("source_sha256") != digest:
        return False
    return meta.get("extractor_profile", "") in {
        base.MINERU_PROFILE,
        base.FALLBACK_DOCX_PROFILE,
        base.FALLBACK_PDF_PROFILE,
    }


def clean_previous_visuals(source: Path) -> None:
    asset_dir = assets_dir_for(source)
    if asset_dir.exists():
        shutil.rmtree(asset_dir)
    manifest = figures_manifest_for(source)
    if manifest.exists():
        manifest.unlink()


def unique_asset_path(asset_dir: Path, name: str, raw: bytes) -> Path:
    candidate = asset_dir / (Path(name).name or "figure.bin")
    if not candidate.exists() or candidate.read_bytes() == raw:
        return candidate
    digest = hashlib.sha256(raw).hexdigest()[:10]
    return asset_dir / f"{candidate.stem}-{digest}{candidate.suffix}"


def archive_member_for_target(names: set[str], markdown_member: str, target: str) -> str | None:
    target = unquote(target.strip().strip("<>"))
    if target.startswith(("http://", "https://", "data:")):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    base_dir = str(PurePosixPath(markdown_member).parent)
    normalized = posixpath.normpath(posixpath.join(base_dir, target)).lstrip("./")
    for candidate in (normalized, target.lstrip("./")):
        if candidate in names:
            return candidate
    basename = PurePosixPath(target).name
    matches = [name for name in names if PurePosixPath(name).name == basename]
    return matches[0] if len(matches) == 1 else None


def load_content_list(archive: zipfile.ZipFile) -> list[dict]:
    candidates = [
        name for name in archive.namelist()
        if name.lower().endswith("content_list.json") and not name.endswith("/")
    ]
    if not candidates:
        return []
    try:
        data = json.loads(archive.read(sorted(candidates, key=len)[0]).decode("utf-8", errors="replace"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def visual_records(content_list: list[dict]) -> list[dict]:
    return [
        item for item in content_list
        if isinstance(item, dict)
        and item.get("type") in {"image", "chart"}
        and item.get("sub_type") != "seal"
    ]


def write_figures_manifest(source: Path, records: list[dict], asset_map: dict[str, str]) -> int:
    manifest = figures_manifest_for(source)
    lines = [
        f"# {source.name} — 图像索引",
        "",
        "> 由 MinerU 结构化结果生成。题目若依赖树形、拓扑、流程、曲线、区域、时序或其他空间关系，应核对这里的原图，不要只依据 OCR 文本推断。",
        "",
    ]
    count = 0
    for item in records:
        img_path = str(item.get("img_path") or "").strip()
        repo_target = asset_map.get(img_path)
        if not repo_target:
            basename = PurePosixPath(img_path).name
            matches = [value for key, value in asset_map.items() if PurePosixPath(key).name == basename]
            repo_target = matches[0] if len(set(matches)) == 1 else None
        if not repo_target:
            continue
        count += 1
        lines.extend([f"## 图 {count}", "", f"![图 {count}]({repo_target})", ""])
        meta = []
        if isinstance(item.get("page_idx"), int):
            meta.append(f"原文页码：{item['page_idx'] + 1}")
        if item.get("bbox"):
            meta.append(f"bbox：`{json.dumps(item['bbox'], ensure_ascii=False)}`")
        if item.get("sub_type"):
            meta.append(f"类型：`{item['sub_type']}`")
        if meta:
            lines.extend(["；".join(meta), ""])
        caption = item.get("image_caption") or item.get("chart_caption") or []
        if caption:
            if not isinstance(caption, list):
                caption = [caption]
            lines.extend(["**图注：** " + " ".join(str(x) for x in caption), ""])
        if item.get("content"):
            lines.extend(["**MinerU 结构化内容：**", "", str(item["content"]), ""])
    if count:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    elif manifest.exists():
        manifest.unlink()
    return count


def extract_mineru_package(zip_url: str, source: Path) -> tuple[str, int]:
    response = requests.get(zip_url, timeout=300)
    response.raise_for_status()
    clean_previous_visuals(source)
    asset_dir = assets_dir_for(source)

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        candidates = [name for name in names if name.lower().endswith("full.md")]
        if not candidates:
            candidates = [name for name in names if name.lower().endswith(".md")]
        if not candidates:
            raise RuntimeError("MinerU result ZIP contains no Markdown file")
        markdown_member = sorted(candidates, key=lambda n: (0 if n.lower().endswith("full.md") else 1, len(n)))[0]
        markdown = archive.read(markdown_member).decode("utf-8", errors="replace")
        records = visual_records(load_content_list(archive))

        wanted = [m.group(2) for m in base.IMAGE_RE.finditer(markdown)]
        wanted += [m.group(1) for m in HTML_IMAGE_SRC_RE.finditer(markdown)]
        wanted += [str(item.get("img_path") or "") for item in records]
        members: set[str] = set()
        for target in wanted:
            if target:
                member = archive_member_for_target(names, markdown_member, target)
                if member:
                    members.add(member)
        if not members:
            members = {name for name in names if PurePosixPath(name).suffix.lower() in IMAGE_EXTENSIONS}

        asset_map: dict[str, str] = {}
        if members:
            asset_dir.mkdir(parents=True, exist_ok=True)
        for member in sorted(members):
            raw = archive.read(member)
            dest = unique_asset_path(asset_dir, member, raw)
            dest.write_bytes(raw)
            link = dest.relative_to(base.destination_for(source).parent).as_posix()
            asset_map[member] = link
            asset_map[f"images/{PurePosixPath(member).name}"] = link

        def replace_markdown_image(match: re.Match[str]) -> str:
            alt, target = match.group(1), match.group(2)
            member = archive_member_for_target(names, markdown_member, target)
            if member and member in asset_map:
                return f"![{alt}]({asset_map[member]})"
            return f"> ⚠️ 图像资源未能从 MinerU 结果包保存：`{target}`"

        markdown = base.IMAGE_RE.sub(replace_markdown_image, markdown)

        def replace_html_image(match: re.Match[str]) -> str:
            target = match.group(1)
            member = archive_member_for_target(names, markdown_member, target)
            if member and member in asset_map:
                return f"![MinerU 图像]({asset_map[member]})"
            return f"> ⚠️ 图像资源未能从 MinerU 结果包保存：`{target}`"

        markdown = HTML_IMAGE_SRC_RE.sub(replace_html_image, markdown)
        for item in records:
            img_path = str(item.get("img_path") or "")
            member = archive_member_for_target(names, markdown_member, img_path)
            if member and member in asset_map:
                asset_map[img_path] = asset_map[member]
        figure_count = write_figures_manifest(source, records, asset_map)

    if base.useful_chars(markdown) < 40:
        raise RuntimeError("MinerU Markdown result is unexpectedly empty")
    return markdown.strip(), figure_count


def poll_batch(
    batch_id: str,
    mapping: dict[str, Path],
    digests: dict[Path, str],
    token: str,
) -> tuple[set[Path], dict[Path, str]]:
    deadline = time.monotonic() + base.TIMEOUT_SECONDS
    completed: set[Path] = set()
    failures: dict[Path, str] = {}
    while time.monotonic() < deadline:
        response = requests.get(
            f"{base.API_BASE}/extract-results/batch/{batch_id}",
            headers=base.auth_headers(token), timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("code") != 0:
            raise RuntimeError(result.get("msg") or "MinerU batch status request failed")
        items = (result.get("data") or {}).get("extract_result") or []
        states: list[str] = []
        for item in items:
            source = mapping.get(item.get("data_id"))
            if source is None:
                file_name = item.get("file_name")
                matches = [path for path in mapping.values() if path.name == file_name]
                source = matches[0] if len(matches) == 1 else None
            if source is None:
                continue
            state = str(item.get("state") or "")
            states.append(state)
            if state == "done" and source not in completed:
                zip_url = item.get("full_zip_url")
                if not zip_url:
                    failures[source] = "done result did not contain full_zip_url"
                else:
                    try:
                        markdown, figures = extract_mineru_package(zip_url, source)
                        base.write_output(source, digests[source], base.MINERU_PROFILE, markdown)
                        print(f"[mineru done] {source.relative_to(base.ROOT).as_posix()} figures={figures}", flush=True)
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
        time.sleep(base.POLL_SECONDS)
    for source in mapping.values():
        if source not in completed:
            failures[source] = f"timeout after {base.TIMEOUT_SECONDS}s"
    return completed, failures


def validate_outputs(sources: list[Path]) -> list[str]:
    errors: list[str] = []
    for source in sources:
        md = base.destination_for(source)
        if not md.is_file():
            errors.append(f"{source.relative_to(base.ROOT)} has no Markdown output")
            continue
        text = base.read_text(md)
        if base.useful_chars(text) < 40:
            errors.append(f"{md.relative_to(base.ROOT)} has too little readable text")
        for match in base.IMAGE_RE.finditer(text):
            target = unquote(match.group(2).strip().strip("<>"))
            if target.startswith(("http://", "https://", "data:")):
                continue
            target_path = (md.parent / target).resolve()
            try:
                target_path.relative_to(base.ROOT.resolve())
            except ValueError:
                errors.append(f"{md.relative_to(base.ROOT)} image escapes repository: {target}")
                continue
            if not target_path.is_file():
                errors.append(f"{md.relative_to(base.ROOT)} has missing image asset: {target}")
    return errors


def write_gpt_index() -> int:
    count = ORIGINAL_WRITE_GPT_INDEX()
    text = base.INDEX_PATH.read_text(encoding="utf-8")
    old_rules = (
        "4. 回答时标明使用的仓库笔记路径；OCR、公式或表格可疑时明确提示需要核对原文件。"
    )
    new_rules = (
        "4. 若候选笔记存在对应的 `*.figures.md` 图像索引，且问题依赖树形、拓扑、流程、曲线、区域、时序或其他空间关系，必须继续核对对应原图；不得仅凭 OCR 文本补猜图形关系。\n"
        "5. 当前客户端若无法读取图片像素，应明确说明需要核对原图并让用户上传相关图片，不能把 OCR/图注当成完整视觉信息。\n"
        "6. 回答时标明使用的仓库笔记路径；OCR、公式或表格可疑时明确提示需要核对原文件。"
    )
    text = text.replace(old_rules, new_rules)

    manifests = {}
    for manifest in base.OUT_ROOT.rglob("*.figures.md"):
        main_rel = manifest.relative_to(base.ROOT).as_posix().removesuffix(".figures.md") + ".md"
        manifests[quote(main_rel, safe="/")] = quote(manifest.relative_to(base.ROOT).as_posix(), safe="/")
    lines = []
    for line in text.splitlines():
        for main_target, figures_target in manifests.items():
            if f"]({main_target})" in line and "[图像索引]" not in line:
                line += f" — [图像索引]({figures_target})"
                break
        lines.append(line)
    base.INDEX_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return count


ORIGINAL_OUTPUT_IS_CURRENT = base.output_is_current
ORIGINAL_WRITE_GPT_INDEX = base.write_gpt_index
base.output_is_current = output_is_current
base.poll_batch = poll_batch
base.validate_outputs = validate_outputs
base.write_gpt_index = write_gpt_index

if __name__ == "__main__":
    raise SystemExit(base.main())
