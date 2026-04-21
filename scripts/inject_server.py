import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
HOST_DIR = Path(os.environ.get("CELLXGENE_HOST_ROOT", str(BASE_DIR.parent / "cellxgene"))).resolve()
TARGET_FILE = HOST_DIR / "server/app/app.py"
IMPORT_SENTINEL = "from server.cafe_api import cafe_bp  # CAFE-CONNECTOR"
REGISTER_SENTINEL = "        self.app.register_blueprint(cafe_bp)  # CAFE-CONNECTOR"


def inject_blueprint() -> None:
    if not TARGET_FILE.exists():
        raise FileNotFoundError(f"Target file not found: {TARGET_FILE}")

    content = TARGET_FILE.read_text(encoding="utf-8")

    if IMPORT_SENTINEL in content and REGISTER_SENTINEL in content:
        print("Backend already injected.")
        return

    if IMPORT_SENTINEL not in content:
        anchor = "import server.common.rest as common_rest\n" # follow the last import
        if anchor not in content:
            raise RuntimeError("Cannot find import anchor in app.py")
        content = content.replace(anchor, f"{anchor}{IMPORT_SENTINEL}\n", 1)

    if REGISTER_SENTINEL not in content:
        anchor = "        self.app.register_blueprint(resources.blueprint)\n" # follow the last blueprint registration
        if anchor not in content:
            raise RuntimeError("Cannot find blueprint registration anchor in app.py")
        content = content.replace(anchor, f"{anchor}{REGISTER_SENTINEL}\n", 1)

    TARGET_FILE.write_text(content, encoding="utf-8")
    print("Backend injection complete.")


if __name__ == "__main__":
    inject_blueprint()
