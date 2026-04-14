import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
HOST_DIR = Path(os.environ.get("CELLXGENE_HOST_ROOT", str(BASE_DIR.parent / "cellxgene"))).resolve()
TARGET_FILES = [
  HOST_DIR / "client/index_template.html",
  HOST_DIR / "server/common/web/templates/index.html",
]

INJECTION_HTML = """
<!-- CAFE-PLUGIN-INJECTION START -->
<link href="https://cdn.jsdelivr.net/npm/jspanel4@4.16.1/dist/jspanel.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/jspanel4@4.16.1/dist/jspanel.min.js"></script>
<script src="static/cafe-plugin.js"></script>
<script>
(function () {
  const launcherId = "cafe-plugin-launcher";
  const panelId = "cafe-plugin-panel";
  const rootId = "cafe-plugin-root";

  function mountCafePlugin() {
    if (window.CafePlugin && typeof window.CafePlugin.mount === "function") {
      window.CafePlugin.mount(rootId);
    } else if (window.mountCafeApp) {
      window.mountCafeApp(rootId);
    } else {
      console.error("CAFE plugin bundle loaded but mount function is missing.");
    }
  }

  function openPanel() {
    if (!window.jsPanel) {
      console.error("jsPanel is not loaded.");
      return;
    }

    const existing = document.getElementById(panelId);
    if (existing && existing.jspanel) {
      existing.jspanel.front();
      return;
    }

    window.jsPanel.create({
      id: panelId,
      headerTitle: "CAFE Plugins",
      theme: "primary",
      contentSize: "780 640",
      position: "center-top 0 64",
      content: '<div id="' + rootId + '" style="height:100%;overflow:auto;"></div>',
      callback: mountCafePlugin,
      onclosed: function () {
        if (window.CafePlugin && typeof window.CafePlugin.unmount === "function") {
          window.CafePlugin.unmount(rootId);
        }
      }
    });
  }

  function ensureLauncherButton() {
    if (document.getElementById(launcherId)) {
      return;
    }

    const button = document.createElement("button");
    button.id = launcherId;
    button.type = "button";
    button.textContent = "Cafe Plugins";
    button.style.position = "fixed";
    button.style.right = "14px";
    button.style.bottom = "16px";
    button.style.zIndex = "9999";
    button.style.padding = "6px 10px";
    button.style.border = "1px solid #6a8fb2";
    button.style.borderRadius = "4px";
    button.style.background = "#2f6f9f";
    button.style.color = "#fff";
    button.style.cursor = "pointer";
    button.title = "Open CAFE plugin window";
    button.addEventListener("click", openPanel);
    document.body.appendChild(button);
  }

  window.openCafePluginPanel = openPanel;
  window.addEventListener("load", function () {
    setTimeout(ensureLauncherButton, 700);
  });
})();
</script>
<!-- CAFE-PLUGIN-INJECTION END -->
"""

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
      updated = INJECTION_BLOCK_PATTERN.sub(INJECTION_HTML.strip(), content, count=1)
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
