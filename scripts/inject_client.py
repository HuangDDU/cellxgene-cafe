import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
HOST_DIR = Path(os.environ.get("CELLXGENE_HOST_ROOT", str(BASE_DIR.parent / "cellxgene"))).resolve()
INJECTION_TEMPLATE_FILE = BASE_DIR / "scripts/inject_client.html"
TARGET_FILES = [
    HOST_DIR / "client/index_template.html",
    HOST_DIR / "client/index.html",
    HOST_DIR / "server/common/web/templates/index.html",
]

INJECTION_BLOCK_PATTERN = re.compile(
    r"<!-- CAFE-PLUGIN-INJECTION START -->.*?<!-- CAFE-PLUGIN-INJECTION END -->",
    re.DOTALL,
)


def load_injection_html() -> str:
    if not INJECTION_TEMPLATE_FILE.exists():
        raise FileNotFoundError(f"Injection template not found: {INJECTION_TEMPLATE_FILE}")

    injection_html = INJECTION_TEMPLATE_FILE.read_text(encoding="utf-8").strip()
    if not injection_html:
        raise RuntimeError(f"Injection template is empty: {INJECTION_TEMPLATE_FILE}")

    if (
        "CAFE-PLUGIN-INJECTION START" not in injection_html
        or "CAFE-PLUGIN-INJECTION END" not in injection_html
    ):
        raise RuntimeError(
            "Injection template must include CAFE-PLUGIN-INJECTION START/END markers"
        )

    return injection_html


def inject_html(target_file: Path, injection_html: str) -> None:
    if not target_file.exists():
        print(f"Skip missing file: {target_file}")
        return

    content = target_file.read_text(encoding="utf-8")
    if "CAFE-PLUGIN-INJECTION" in content:
        updated = INJECTION_BLOCK_PATTERN.sub(injection_html, content, count=1)
        if updated != content:
            target_file.write_text(updated, encoding="utf-8")
            print(f"Updated injection: {target_file}")
        else:
            print(f"Injection marker found but unchanged: {target_file}")
        return

    if "</body>" not in content:
        raise RuntimeError(f"Cannot find </body> in {target_file}")

    updated = content.replace("</body>", f"{injection_html}\n</body>", 1)
    target_file.write_text(updated, encoding="utf-8")
    print(f"Injected: {target_file}")


def main() -> None:
    injection_html = load_injection_html()
    for target in TARGET_FILES:
        inject_html(target, injection_html)


if __name__ == "__main__":
    main()
