#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

resolve_target_python() {
	local env_name="${CELLXGENE_CONDA_ENV:-cellxgene_cafe}"

	if [[ -n "${CELLXGENE_PYTHON:-}" ]]; then
		echo "${CELLXGENE_PYTHON}"
		return
	fi

	local env_python="/root/miniconda3/envs/${env_name}/bin/python"
	if [[ -x "${env_python}" ]]; then
		echo "${env_python}"
		return
	fi

	if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
		echo "${CONDA_PREFIX}/bin/python"
		return
	fi

	echo "python3"
}

resolve_host_dir() {
	local py_bin="$1"
	(
		cd /tmp
		"${py_bin}" - <<'PY'
import importlib.util
import pathlib
import sys

spec = importlib.util.find_spec("server.app.app")
if spec is None or spec.origin is None:
		print("[ERROR] Unable to resolve module: server.app.app", file=sys.stderr)
		raise SystemExit(2)

app_py = pathlib.Path(spec.origin).resolve()
print(app_py.parents[2])
PY
	)
}

TARGET_PYTHON="$(resolve_target_python)"
HOST_DIR="$(resolve_host_dir "${TARGET_PYTHON}")"

if [[ ! -d "${HOST_DIR}/server" ]]; then
	echo "[ERROR] Cannot locate cellxgene server directory in target host: ${HOST_DIR}" >&2
	exit 1
fi

export CELLXGENE_HOST_ROOT="${HOST_DIR}"

run_npm() {
	local -a env_args=()

	# Prefer lowercase proxy vars when both lowercase and uppercase exist.
	if [[ -n "${http_proxy:-}" ]]; then
		env_args+=("HTTP_PROXY=${http_proxy}" "http_proxy=${http_proxy}")
	fi
	if [[ -n "${https_proxy:-}" ]]; then
		env_args+=("HTTPS_PROXY=${https_proxy}" "https_proxy=${https_proxy}")
	fi
	if [[ -n "${no_proxy:-}" ]]; then
		env_args+=("NO_PROXY=${no_proxy}" "no_proxy=${no_proxy}")
	fi

	env "${env_args[@]}" npm "$@"
}

echo "[1/5] Install plugin frontend dependencies"
cd "$ROOT_DIR/client"
run_npm install

echo "[2/5] Build plugin bundle"
run_npm run build

echo "[3/5] Copy backend connector files"
cp "$ROOT_DIR/server/cafe_api.py" "$HOST_DIR/server/cafe_api.py"
cp "$ROOT_DIR/server/cafe_util.py" "$HOST_DIR/server/cafe_util.py"

echo "[4/5] Copy frontend bundle"
mkdir -p "$HOST_DIR/server/common/web/static"
cp "$ROOT_DIR/dist/cafe-plugin.js" "$HOST_DIR/server/common/web/static/cafe-plugin.js"

echo "[5/5] Inject host hooks"
cd "$ROOT_DIR"
python3 scripts/inject_server.py
python3 scripts/inject_client.py

echo "Done. Now start cellxgene as usual."
