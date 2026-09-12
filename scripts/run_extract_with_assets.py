from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import extract_with_assets as assets

base = assets.base


def iter_markdown_image_targets(text: str):
    """Yield Markdown image destinations while supporting balanced parentheses.

    The original validator reused a regex that stopped at the first `)` in a
    destination. That misread valid generated links such as
    `第三章 内存管理(3.1).docx.assets/figure.png` as a missing file named
    `第三章 内存管理(3.1`.
    """
    cursor = 0
    length = len(text)

    while cursor < length:
        image_start = text.find("![", cursor)
        if image_start < 0:
            return

        destination_start = text.find("](", image_start + 2)
        if destination_start < 0:
            return

        pos = destination_start + 2
        depth = 0
        escaped = False

        while pos < length:
            ch = text[pos]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    yield text[destination_start + 2 : pos]
                    cursor = pos + 1
                    break
                depth -= 1
            pos += 1
        else:
            return


def validate_outputs(sources: list[Path]) -> list[str]:
    errors: list[str] = []
    repo_root = base.ROOT.resolve()

    for source in sources:
        md = base.destination_for(source)
        if not md.is_file():
            errors.append(f"{source.relative_to(base.ROOT)} has no Markdown output")
            continue

        text = base.read_text(md)
        if base.useful_chars(text) < 40:
            errors.append(f"{md.relative_to(base.ROOT)} has too little readable text")

        for raw_target in iter_markdown_image_targets(text):
            target = unquote(raw_target.strip().strip("<>"))
            if target.startswith(("http://", "https://", "data:")):
                continue

            target_path = (md.parent / target).resolve()
            try:
                target_path.relative_to(repo_root)
            except ValueError:
                errors.append(
                    f"{md.relative_to(base.ROOT)} image escapes repository: {target}"
                )
                continue

            if not target_path.is_file():
                errors.append(
                    f"{md.relative_to(base.ROOT)} has missing image asset: {target}"
                )

    return errors


# extract_with_assets patches the base extractor on import. Replace only its
# image-link validator with the balanced-parenthesis-safe implementation above.
base.validate_outputs = validate_outputs


if __name__ == "__main__":
    raise SystemExit(base.main())
