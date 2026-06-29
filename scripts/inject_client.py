import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
HOST_DIR = Path(os.environ.get("CELLXGENE_HOST_ROOT", str(BASE_DIR.parent / "cellxgene"))).resolve()
TARGET_FILES = [
  HOST_DIR / "client/index_template.html",
  HOST_DIR / "server/common/web/templates/index.html",
]

INJECTION_HTML = (Path(__file__).resolve().parent / "inject_client.html").read_text(encoding="utf-8")

INJECTION_BLOCK_PATTERN = re.compile(
  r"<!-- CAFE-PLUGIN-INJECTION START -->.*?<!-- CAFE-PLUGIN-INJECTION END -->",
  re.DOTALL,
)


def inject_html(target_file: Path) -> None:
    if not target_file.exists():
        print(f"Skip missing file: {target_file}")
        return

    content = target_file.read_text(encoding="utf-8")
    if "CAFE-PLUGIN-INJECTION" in content:
      updated = INJECTION_BLOCK_PATTERN.sub(lambda _match: INJECTION_HTML.strip(), content, count=1)
      if updated != content:
        target_file.write_text(updated, encoding="utf-8")
        print(f"Updated injection: {target_file}")
      else:
        print(f"Injection marker found but unchanged: {target_file}")
      return

    if "</body>" not in content:
        raise RuntimeError(f"Cannot find </body> in {target_file}")

    updated = content.replace("</body>", f"{INJECTION_HTML}\n</body>", 1)
    target_file.write_text(updated, encoding="utf-8")
    print(f"Injected: {target_file}")


def main() -> None:
    for target in TARGET_FILES:
        inject_html(target)


if __name__ == "__main__":
    main()
