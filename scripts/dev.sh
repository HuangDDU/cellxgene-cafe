#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/common_env.sh
# Reuse shared helpers (.env loading, python resolution, npm proxy passthrough).
source "${SCRIPT_DIR}/common_env.sh"

# Ensure host frontend dependencies exist before launching its dev server.
ensure_host_client_deps() {
  local root_dir="$1"

  if [[ -d "${root_dir}/client/node_modules" && -f "${root_dir}/client/node_modules/chalk/package.json" ]]; then
    return
  fi

  echo "[DEV] Install host frontend dependencies"
  cd "${root_dir}/client"
  run_npm install
}

# Ensure plugin frontend dependencies exist before running webpack build/watch.
# if stuck in puppeteer downloading Chromium, try `PUPPETEER_SKIP_DOWNLOAD=true` to skip chrome download
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

# Patch backend template to load host frontend dev bundle from webpack-dev-server instead of static assets built by host Makefile.
patch_backend_template_for_dev_bundle() {
  local host_template_file="$1"
  local client_port="$2"

  if [[ ! -f "${host_template_file}" ]]; then
    return
  fi

  local search='<script defer src="static/main-[^"]+\.js"></script><script defer src="obsolete\.js"></script><link href="static/main-[^"]+\.css" rel="stylesheet"></head>'
  local replace='<script defer src="http://localhost:'"${client_port}"'/static/js/bundle.js"></script><link href="http://localhost:'"${client_port}"'/static/main.css" rel="stylesheet"></head>'

  if grep -E -q "${search}" "${host_template_file}"; then
    sed -i -E "s|${search}|${replace}|" "${host_template_file}"
    echo "[DEV] Patched backend template to use dev bundle: ${host_template_file}"
  elif ! grep -q "static/js/bundle.js" "${host_template_file}"; then
    sed -i "s|</head>|${replace}|" "${host_template_file}"
    echo "[DEV] Added dev bundle to backend template: ${host_template_file}"
  else
    echo "[DEV] Backend template already points to dev bundle: ${host_template_file}"
  fi
}

# Patch host reducers to enable Redux DevTools Extension support in host frontend dev server.
patch_host_redux_devtools() {
  local root_dir="$1"
  local host_reducers_file="${root_dir}/client/src/reducers/index.js"

  if [[ ! -f "${host_reducers_file}" ]]; then
    return
  fi

  if ! grep -q "__REDUX_DEVTOOLS_EXTENSION_COMPOSE__" "${host_reducers_file}"; then
    sed -i 's/import { createStore, applyMiddleware } from "redux";/import { createStore, applyMiddleware, compose } from "redux";/' "${host_reducers_file}"
    sed -i '/const store = createStore(Reducer,/c\const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ ? window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__({ name: "cellxgene" }) : compose;\nconst store = createStore(Reducer, composeEnhancers(applyMiddleware(thunk, annoMatrixGC)));' "${host_reducers_file}"
    echo "[DEV] Patched host Redux DevTools support: ${host_reducers_file}"
  fi
}

# Ensure target port can be used by current dev session.
ensure_port_ready() {
  local port="$1"
  local force_kill="$2"

  if fuser -n tcp "${port}" >/dev/null 2>&1; then
    if [[ "${force_kill}" == "1" ]]; then
      echo "[DEV] Port ${port} is busy. Killing existing process because CELLXGENE_FORCE_KILL_PORT=1"
      fuser -k "${port}/tcp" >/dev/null 2>&1 || true
      return
    fi

    echo "[ERROR] Port ${port} is in use. Set CELLXGENE_FORCE_KILL_PORT=1 or choose another port." >&2
    exit 1
  fi
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
  local cellxgene_conda_env="${CELLXGENE_CONDA_ENV:-cellxgene_cafe}"
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
    local default_target="${ROOT_DIR}/../cellxgene"
    local target_dir="${cellxgene_source_root:-${default_target}}"
    echo "[WARN] CELLXGENE_SOURCE_ROOT is missing or invalid: ${target_dir}" >&2
    read -r -p "Do you want to clone the latest cellxgene repository from GitHub into ${target_dir}? [y/N] " response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
      echo "[DEV] Cloning cellxgene repository..."
      git clone https://github.com/chanzuckerberg/cellxgene.git "${target_dir}"
      cellxgene_source_root="$(cd "${target_dir}" && pwd)"
    else
      echo "[ERROR] Cannot proceed without cellxgene source code. Exiting." >&2
      exit 1
    fi
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
  if [[ "${plugin_hmr}" == "1" ]]; then
    ensure_port_ready "${plugin_dev_port}" "${force_kill_port}"
  fi

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
  local backend_template="${cellxgene_source_root}/server/common/web/templates/index.html"
  if [[ ! -f "${backend_template}" ]]; then
    mkdir -p "$(dirname "${backend_template}")"
    cp "${cellxgene_source_root}/client/index_template.html" "${backend_template}"
  fi
  python3 scripts/inject_client.py
  if [[ "${plugin_hmr}" == "1" ]]; then
    sed -i -E 's|<script src="[^"]*cafe-plugin[^"]*"></script>|<script src="'"${CAFE_PLUGIN_BUNDLE_URL}"'"></script>|' \
      "${cellxgene_source_root}/client/index_template.html" \
      "${backend_template}"
  fi
  patch_backend_template_for_dev_bundle "${backend_template}" "${client_port}"
  patch_host_redux_devtools "${cellxgene_source_root}"

  # Keep plugin backend/bridge code hot-swappable in host source tree.
  cp "${ROOT_DIR}/server/cafe_api.py" "${cellxgene_source_root}/server/cafe_api.py"
  rm -rf "${cellxgene_source_root}/server/cafe_util"
  cp -r "${ROOT_DIR}/server/cafe_util" "${cellxgene_source_root}/server/cafe_util/"
  cp "${ROOT_DIR}/client/src/lib/cafeHostBridge.js" "${cellxgene_source_root}/client/src/cafeHostBridge.js"

  # Keep a fallback static asset path in place for non-HMR installations.
  mkdir -p "${cellxgene_source_root}/server/common/web/static"
  cp -sfn "${ROOT_DIR}/dist/cafe-plugin.js" "${cellxgene_source_root}/server/common/web/static/cafe-plugin.js"

  # Launch host backend/frontend in background.
  echo "[DEV] Launch backend and frontend (background)"

  ensure_host_client_deps "${cellxgene_source_root}"

  (
    cd "${cellxgene_source_root}"
    export PYTHONPATH="${cellxgene_source_root}"
    conda run --live-stream -n "${cellxgene_conda_env}" make start-server # run backend in conda environment
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
