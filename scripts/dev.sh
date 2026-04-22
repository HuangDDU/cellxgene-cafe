#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/common_env.sh
# Reuse shared helpers (.env loading, python resolution, npm proxy passthrough).
source "${SCRIPT_DIR}/common_env.sh"

# Ensure plugin frontend dependencies exist before running webpack build/watch.
ensure_plugin_client_deps() {
  local root_dir="$1"

  if [[ -d "${root_dir}/client/node_modules" ]]; then
    return
  fi

  echo "[DEV] Install plugin frontend dependencies"
  cd "${root_dir}/client"
  run_npm install
}

# Build plugin bundle for non-watch mode.
ensure_plugin_bundle() {
  local root_dir="$1"
  local build_plugin="$2"
  local bundle="${root_dir}/dist/cafe-plugin.js"

  local need_build="${build_plugin}"

  if [[ "${need_build}" != "1" && -f "${bundle}" ]]; then
    if [[ "${root_dir}/client/package.json" -nt "${bundle}" || "${root_dir}/client/webpack.config.js" -nt "${bundle}" ]]; then
      need_build="1"
    elif find "${root_dir}/client/src" -type f \( -name "*.js" -o -name "*.jsx" -o -name "*.css" \) -newer "${bundle}" -print -quit | grep -q .; then
      need_build="1"
    fi
  fi

  if [[ -f "${bundle}" && "${need_build}" != "1" ]]; then
    echo "[DEV] Reuse existing plugin bundle: ${bundle}"
    return
  fi

  if [[ "${need_build}" != "1" && ! -f "${bundle}" ]]; then
    echo "[WARN] Missing ${bundle}. Set CELLXGENE_BUILD_PLUGIN=1 to auto build it."
    return
  fi

  echo "[DEV] Build plugin frontend bundle"
  ensure_plugin_client_deps "${root_dir}"
  cd "${root_dir}/client"
  run_npm run build
}

# Start the plugin frontend dev server with HMR enabled.
start_plugin_dev_server() {
  local root_dir="$1"
  local dev_server_log_file="$2"
  local dev_server_port="$3"

  ensure_plugin_client_deps "${root_dir}"

  (
    cd "${root_dir}/client"
    CAFE_PLUGIN_DEV_SERVER_PORT="${dev_server_port}" run_npm run dev
  ) >> "${dev_server_log_file}" 2>&1 &

  echo "$!"
}

patch_backend_template_for_dev_bundle() {
  local host_template_file="$1"
  local client_port="$2"

  if [[ ! -f "${host_template_file}" ]]; then
    return
  fi

  python3 - <<'PY' "$host_template_file" "$client_port"
from pathlib import Path
import re
import sys

template_file = Path(sys.argv[1])
client_port = sys.argv[2]
content = template_file.read_text(encoding="utf-8")

replacement = (
    f'<script defer src="http://localhost:{client_port}/static/js/bundle.js"></script>'
    f'<link href="http://localhost:{client_port}/static/main.css" rel="stylesheet"></head>'
)

pattern = re.compile(
    r'<script defer src="static/main-[^"]+\.js"></script>'
    r'<script defer src="obsolete\.js"></script>'
    r'<link href="static/main-[^"]+\.css" rel="stylesheet"></head>',
    re.DOTALL,
)

updated = pattern.sub(replacement, content, count=1)
if updated != content:
    template_file.write_text(updated, encoding="utf-8")
    print(f"[DEV] Patched backend template to use dev bundle: {template_file}")
else:
    print(f"[DEV] Backend template already points to dev bundle: {template_file}")
PY
}

# Return 1 if a TCP port is occupied, else 0.
port_in_use() {
  local port="$1"
  python3 - <<'PY' "$port"
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("127.0.0.1", port))
    print("0")
except OSError:
    print("1")
finally:
    sock.close()
PY
}

# Ensure target port can be used by current dev session.
ensure_port_ready() {
  local port="$1"
  local force_kill="$2"

  if [[ "$(port_in_use "${port}")" == "0" ]]; then
    return
  fi

  if [[ "${force_kill}" == "1" ]]; then
    echo "[DEV] Port ${port} is busy. Killing existing process because CELLXGENE_FORCE_KILL_PORT=1"
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    return
  fi

  echo "[ERROR] Port ${port} is in use. Set CELLXGENE_FORCE_KILL_PORT=1 or choose another port." >&2
  exit 1
}

# Stop all processes persisted from the previous dev run.
stop_previous_processes() {
  local pid_file="$1"
  if [[ ! -f "${pid_file}" ]]; then
    return
  fi

  while read -r pid _service; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done < "${pid_file}"

  rm -f "${pid_file}"
}

dev_main() {
  load_project_env "${ROOT_DIR}/.env"

  # Runtime wiring.
  local cellxgene_source_root="${CELLXGENE_SOURCE_ROOT:-}"
  local cellxgene_dataset="${CELLXGENE_DATASET:-}"
  local server_port="${CELLXGENE_PORT:-5005}"
  local client_port="${CXG_CLIENT_PORT:-3000}"

  # Plugin build strategy.
  local plugin_hmr="${CELLXGENE_PLUGIN_HMR:-1}"
  local build_plugin="${CELLXGENE_BUILD_PLUGIN:-0}"
  local plugin_dev_port="${CELLXGENE_PLUGIN_DEV_PORT:-3001}"

  # Process lifecycle and logs.
  local force_kill_port="${CELLXGENE_FORCE_KILL_PORT:-1}"
  local backend_log_file="${ROOT_DIR}/log/dev_backend.log"
  local frontend_log_file="${ROOT_DIR}/log/dev_frontend.log"
  local plugin_dev_log_file="${ROOT_DIR}/log/dev_plugin_dev_server.log"
  local pid_file="${ROOT_DIR}/log/dev.pids"

  if [[ -z "${cellxgene_source_root}" || ! -d "${cellxgene_source_root}" ]]; then
    echo "[ERROR] CELLXGENE_SOURCE_ROOT is invalid: ${cellxgene_source_root}" >&2
    exit 1
  fi

  if [[ -z "${cellxgene_dataset}" || ! -f "${cellxgene_dataset}" ]]; then
    echo "[ERROR] CELLXGENE_DATASET is invalid: ${cellxgene_dataset}" >&2
    exit 1
  fi

  if [[ ! -f "${cellxgene_source_root}/Makefile" ]]; then
    echo "[ERROR] Not a valid cellxgene source root: ${cellxgene_source_root}" >&2
    exit 1
  fi

  local target_python
  target_python="$(resolve_target_python "cafe")"

  if [[ "${target_python}" != "python3" && ! -x "${target_python}" ]]; then
    echo "[ERROR] Invalid Python executable: ${target_python}" >&2
    exit 1
  fi

  if [[ "${target_python}" != "python3" ]]; then
    export PATH="$(cd "$(dirname "${target_python}")" && pwd):${PATH}"
  fi

  # Prevent launch failures due to stale ports.
  ensure_port_ready "${server_port}" "${force_kill_port}"
  ensure_port_ready "${client_port}" "${force_kill_port}"

  # Export variables consumed by injectors and host make targets.
  export CELLXGENE_HOST_ROOT="${cellxgene_source_root}"
  export CXG_SERVER_PORT="${server_port}"
  export CXG_CLIENT_PORT="${client_port}"
  export DATASET="${cellxgene_dataset}"

  echo "[DEV] Host source: ${cellxgene_source_root}"
  echo "[DEV] Dataset: ${cellxgene_dataset}"
  echo "[DEV] Backend port: ${server_port}"
  echo "[DEV] Frontend port: ${client_port}"
  echo "[DEV] Plugin HMR: ${plugin_hmr}"
  echo "[DEV] Plugin dev port: ${plugin_dev_port}"

  mkdir -p "${ROOT_DIR}/log"
  stop_previous_processes "${pid_file}"

  local plugin_dev_pid=""
  if [[ "${plugin_hmr}" == "1" ]]; then
    echo "[DEV] Start plugin frontend dev server (webpack-dev-server + HMR)"
    plugin_dev_pid="$(start_plugin_dev_server "${ROOT_DIR}" "${plugin_dev_log_file}" "${plugin_dev_port}")"
  else
    ensure_plugin_bundle "${ROOT_DIR}" "${build_plugin}"
  fi

  if [[ "${plugin_hmr}" == "1" ]]; then
    export CAFE_PLUGIN_BUNDLE_URL="http://localhost:${plugin_dev_port}/cafe-plugin.js"
    export CAFE_PLUGIN_HMR_ENABLED="1"
  else
    export CAFE_PLUGIN_BUNDLE_URL="static/cafe-plugin.js"
    export CAFE_PLUGIN_HMR_ENABLED="0"
  fi

  # Inject plugin hooks and force host template to load host frontend dev bundle.
  echo "[DEV] Inject backend/frontend hooks"
  cd "${ROOT_DIR}"
  python3 scripts/inject_server.py
  python3 scripts/inject_client.py
  patch_backend_template_for_dev_bundle "${cellxgene_source_root}/server/common/web/templates/index.html" "${client_port}"

  # Keep plugin backend/bridge code hot-swappable in host source tree.
  ln -sfn "${ROOT_DIR}/server/cafe_api.py" "${cellxgene_source_root}/server/cafe_api.py"
  ln -sfn "${ROOT_DIR}/server/cafe_util.py" "${cellxgene_source_root}/server/cafe_util.py"
  ln -sfn "${ROOT_DIR}/client/src/lib/cafeHostBridge.js" "${cellxgene_source_root}/client/src/cafeHostBridge.js"

  # Keep a fallback static asset path in place for non-HMR installations.
  mkdir -p "${cellxgene_source_root}/server/common/web/static"
  ln -sfn "${ROOT_DIR}/dist/cafe-plugin.js" "${cellxgene_source_root}/server/common/web/static/cafe-plugin.js"

  # Launch host backend/frontend in background.
  echo "[DEV] Launch backend and frontend (background)"

  (
    cd "${cellxgene_source_root}"
    make start-server
  ) >> "${backend_log_file}" 2>&1 &
  local server_pid=$!

  (
    cd "${cellxgene_source_root}/client"
    make start-frontend
  ) >> "${frontend_log_file}" 2>&1 &
  local frontend_pid=$!

  {
    echo "${server_pid} server"
    echo "${frontend_pid} frontend"
    if [[ -n "${plugin_dev_pid}" ]]; then
      echo "${plugin_dev_pid} plugin-dev-server"
    fi
  } > "${pid_file}"

  echo "[DEV] Started. Backend PID=${server_pid}, Frontend PID=${frontend_pid}"
  if [[ -n "${plugin_dev_pid}" ]]; then
    echo "[DEV] Plugin dev server PID=${plugin_dev_pid}"
  fi
  echo "[DEV] Backend log file: ${backend_log_file}"
  echo "[DEV] Frontend log file: ${frontend_log_file}"
  if [[ -n "${plugin_dev_pid}" ]]; then
    echo "[DEV] Plugin dev server log file: ${plugin_dev_log_file}"
  fi
  echo "[DEV] Open: http://localhost:${server_port}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  dev_main "$@"
fi