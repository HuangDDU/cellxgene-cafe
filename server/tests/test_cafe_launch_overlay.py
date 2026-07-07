from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cellxgene_cafe.assets import packaged_assets_root  # noqa: E402
from cellxgene_cafe.cli import build_launch_env, build_launch_argv, find_project_root, parse_launch_args  # noqa: E402
from cellxgene_cafe.overlay import _python_env_without_paths, prepare_overlay  # noqa: E402


def write_fake_cellxgene_host(root: Path) -> None:
    app_py = root / "server" / "app" / "app.py"
    app_py.parent.mkdir(parents=True)
    app_py.write_text(
        "\n".join(
            [
                "import server.common.rest as common_rest",
                "",
                "class App:",
                "    def __init__(self):",
                "        self.app.register_blueprint(resources.blueprint)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    client_template = root / "client" / "index_template.html"
    client_template.parent.mkdir(parents=True)
    client_template.write_text("<html><body><div id='cellxgene'></div></body></html>", encoding="utf-8")

    backend_template = root / "server" / "common" / "web" / "templates" / "index.html"
    backend_template.parent.mkdir(parents=True)
    backend_template.write_text("<html><body><div id='cellxgene'></div></body></html>", encoding="utf-8")


def write_fake_cafe_project(root: Path) -> None:
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    scripts.joinpath("inject_client.html").write_text(
        "<!-- CAFE-PLUGIN-INJECTION START -->"
        "<script src=\"static/cafe-plugin.js\"></script>"
        "<!-- CAFE-PLUGIN-INJECTION END -->",
        encoding="utf-8",
    )

    server = root / "server"
    server.mkdir()
    server.joinpath("cafe_api.py").write_text("cafe_bp = object()\n", encoding="utf-8")
    util = server / "cafe_util"
    util.mkdir()
    util.joinpath("__init__.py").write_text("VALUE = 1\n", encoding="utf-8")

    dist = root / "dist"
    dist.mkdir()
    dist.joinpath("cafe-plugin.js").write_text("window.CafePlugin = {};\n", encoding="utf-8")


def test_prepare_overlay_patches_only_the_overlay_copy(tmp_path: Path) -> None:
    host_root = tmp_path / "site-packages"
    project_root = tmp_path / "cellxgene-cafe"
    overlay_root = tmp_path / "overlay" / "site-packages"
    write_fake_cellxgene_host(host_root)
    write_fake_cafe_project(project_root)

    original_app = (host_root / "server" / "app" / "app.py").read_text(encoding="utf-8")

    prepared = prepare_overlay(host_root=host_root, project_root=project_root, overlay_root=overlay_root)

    assert prepared == overlay_root
    assert (host_root / "server" / "app" / "app.py").read_text(encoding="utf-8") == original_app
    overlay_app = (overlay_root / "server" / "app" / "app.py").read_text(encoding="utf-8")
    assert "from server.cafe_api import cafe_bp  # CAFE-CONNECTOR" in overlay_app
    assert "self.app.register_blueprint(cafe_bp)  # CAFE-CONNECTOR" in overlay_app
    assert (overlay_root / "server" / "cafe_api.py").read_text(encoding="utf-8") == "cafe_bp = object()\n"
    assert (overlay_root / "server" / "cafe_util" / "__init__.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (overlay_root / "server" / "common" / "web" / "static" / "cafe-plugin.js").exists()
    assert "CAFE-PLUGIN-INJECTION" in (overlay_root / "client" / "index_template.html").read_text(encoding="utf-8")


def test_prepare_overlay_fails_when_target_exists(tmp_path: Path) -> None:
    host_root = tmp_path / "site-packages"
    project_root = tmp_path / "cellxgene-cafe"
    overlay_root = tmp_path / "overlay" / "site-packages"
    write_fake_cellxgene_host(host_root)
    write_fake_cafe_project(project_root)
    overlay_root.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        prepare_overlay(host_root=host_root, project_root=project_root, overlay_root=overlay_root)


def test_launch_args_are_split_between_cafe_and_cellxgene() -> None:
    parsed, cellxgene_args = parse_launch_args(
        [
            "--cafe-host-root",
            "/tmp/native-cellxgene",
            "--cafe-dry-run",
            "dataset.h5ad",
            "--port",
            "5005",
        ]
    )

    assert parsed.cafe_host_root == "/tmp/native-cellxgene"
    assert parsed.cafe_dry_run is True
    assert cellxgene_args == ["dataset.h5ad", "--port", "5005"]


def test_launch_env_puts_overlay_first_on_pythonpath(tmp_path: Path) -> None:
    env = build_launch_env(tmp_path / "overlay", base_env={"PYTHONPATH": os.pathsep.join(["/old/one", "/old/two"])})

    assert env["PYTHONPATH"].split(os.pathsep) == [str(tmp_path / "overlay"), "/old/one", "/old/two"]


def test_host_resolution_env_removes_cafe_project_from_pythonpath(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cafe_root = tmp_path / "cellxgene-cafe"
    other_path = tmp_path / "other"
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([str(cafe_root), str(other_path)]))

    env = _python_env_without_paths([cafe_root])

    assert env["PYTHONPATH"] == str(other_path)


def test_launch_argv_runs_native_cellxgene_launch_with_passthrough_args() -> None:
    argv = build_launch_argv("cellxgene", ["dataset.h5ad", "--port", "5005"])

    assert argv == ["cellxgene", "launch", "dataset.h5ad", "--port", "5005"]


def test_pyproject_exposes_cellxgene_cafe_console_script() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '[project.scripts]' in pyproject
    assert 'cellxgene-cafe = "cellxgene_cafe.cli:main"' in pyproject


def test_packaged_assets_include_runtime_connector_files() -> None:
    assets_root = packaged_assets_root()

    assert (assets_root / "server" / "cafe_api.py").is_file()
    assert (assets_root / "server" / "cafe_util" / "__init__.py").is_file()
    assert (assets_root / "server" / "cafe_util" / "plot.py").is_file()
    assert (assets_root / "scripts" / "inject_client.html").is_file()
    assert (assets_root / "frontend" / "cafe-plugin.js").is_file()


def test_installed_cli_uses_packaged_assets_when_project_root_is_not_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CELLXGENE_CAFE_ROOT", raising=False)

    assert find_project_root() == packaged_assets_root()


def test_pyproject_includes_package_assets_without_declaring_cellxgene_dependency() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "include-package-data = true" in pyproject
    assert "[tool.setuptools.package-data]" in pyproject
    assert '"cellxgene_cafe"' in pyproject
    assert '"assets/**"' in pyproject
    project_metadata = pyproject.split("[project]", 1)[1].split("[project.scripts]", 1)[0]
    assert "dependencies" not in project_metadata


def test_packaged_assets_are_synced_with_source_runtime_assets() -> None:
    assets_root = packaged_assets_root()
    source_asset_pairs = [
        (REPO_ROOT / "server" / "cafe_api.py", assets_root / "server" / "cafe_api.py"),
        (REPO_ROOT / "scripts" / "inject_client.html", assets_root / "scripts" / "inject_client.html"),
    ]
    built_bundle = REPO_ROOT / "dist" / "cafe-plugin.js"
    if built_bundle.exists():
        source_asset_pairs.append((built_bundle, assets_root / "frontend" / "cafe-plugin.js"))
    source_asset_pairs.extend(
        (source_file, assets_root / "server" / "cafe_util" / source_file.name)
        for source_file in sorted((REPO_ROOT / "server" / "cafe_util").glob("*.py"))
    )

    for source_file, packaged_file in source_asset_pairs:
        assert packaged_file.read_bytes() == source_file.read_bytes(), packaged_file
