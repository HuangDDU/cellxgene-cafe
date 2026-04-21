#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/common_env.sh
source "${SCRIPT_DIR}/common_env.sh"

ensure_plugin_bundle() {
  local root_dir="$1"
  local build_plugin="$2"
  local bundle="${root_dir}/dist/cafe-plugin.js"

  if [[ -f "${bundle}" && "${build_plugin}" != "1" ]]; then
    return
  fi

  if [[ "${build_plugin}" != "1" && ! -f "${bundle}" ]]; then
    echo "[WARN] Missing ${bundle}. Set CELLXGENE_BUILD_PLUGIN=1 to auto build it."
    return
  fi

  echo "[DEV] Build plugin frontend bundle"
  cd "${root_dir}/client"
  if [[ ! -d node_modules ]]; then
    run_npm install
  fi
  run_npm run build
}

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

  local cellxgene_source_root="${CELLXGENE_SOURCE_ROOT:-}"
  local cellxgene_dataset="${CELLXGENE_DATASET:-}"
  local server_port="${CELLXGENE_PORT:-5005}"
  local client_port="${CXG_CLIENT_PORT:-3000}"
  local build_plugin="${CELLXGENE_BUILD_PLUGIN:-0}"
  local force_kill_port="${CELLXGENE_FORCE_KILL_PORT:-1}"
  local backend_log_file="${ROOT_DIR}/log/dev_backend.log"
  local frontend_log_file="${ROOT_DIR}/log/dev_frontend.log"
  local pid_file="${ROOT_DIR}/dev.pids"

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

  ensure_port_ready "${server_port}" "${force_kill_port}"
  ensure_port_ready "${client_port}" "${force_kill_port}"

  export CELLXGENE_HOST_ROOT="${cellxgene_source_root}"
  export CXG_SERVER_PORT="${server_port}"
  export CXG_CLIENT_PORT="${client_port}"
  export DATASET="${cellxgene_dataset}"

  echo "[DEV] Host source: ${cellxgene_source_root}"
  echo "[DEV] Dataset: ${cellxgene_dataset}"
  echo "[DEV] Backend port: ${server_port}"
  echo "[DEV] Frontend port: ${client_port}"

  ensure_plugin_bundle "${ROOT_DIR}" "${build_plugin}"

  echo "[DEV] Inject backend/frontend hooks"
  cd "${ROOT_DIR}"
  python3 scripts/inject_server.py
  python3 scripts/inject_client.py

  # Keep plugin backend hot-swappable in source tree.
  ln -sfn "${ROOT_DIR}/server/cafe_api.py" "${cellxgene_source_root}/server/cafe_api.py"
  ln -sfn "${ROOT_DIR}/server/cafe_util.py" "${cellxgene_source_root}/server/cafe_util.py"

  if [[ -f "${ROOT_DIR}/dist/cafe-plugin.js" ]]; then
    mkdir -p "${cellxgene_source_root}/server/common/web/static"
    ln -sfn "${ROOT_DIR}/dist/cafe-plugin.js" "${cellxgene_source_root}/server/common/web/static/cafe-plugin.js"
  fi

  mkdir -p "${ROOT_DIR}/log"
  stop_previous_processes "${pid_file}"

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

  cat > "${pid_file}" <<EOF
${server_pid} server
${frontend_pid} frontend
EOF

  echo "[DEV] Started. Backend PID=${server_pid}, Frontend PID=${frontend_pid}"
  echo "[DEV] Backend log file: ${backend_log_file}"
  echo "[DEV] Frontend log file: ${frontend_log_file}"
  echo "[DEV] Open: http://localhost:${server_port}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  dev_main "$@"
fi