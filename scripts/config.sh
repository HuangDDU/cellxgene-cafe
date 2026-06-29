#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=scripts/common_env.sh
source "${SCRIPT_DIR}/common_env.sh"

config_main() {
  load_project_env "${ROOT_DIR}/.env"

  local target_python host_dir
  target_python="$(resolve_target_python "cellxgene_cafe")"
  host_dir="$(resolve_host_dir "${target_python}")"

  if [[ ! -d "${host_dir}/server" ]]; then
    echo "[ERROR] Cannot locate cellxgene server directory in target host: ${host_dir}" >&2
    exit 1
  fi

  export CELLXGENE_HOST_ROOT="${host_dir}"

  echo "[1/5] Install plugin frontend dependencies"
  cd "${ROOT_DIR}/client"
  run_npm install

  echo "[2/5] Build plugin bundle"
  run_npm run build

  echo "[3/5] Copy backend connector files"
  cp "${ROOT_DIR}/server/cafe_api.py" "${host_dir}/server/cafe_api.py"
  rm -rf "${host_dir}/server/cafe_util"
  cp -r "${ROOT_DIR}/server/cafe_util" "${host_dir}/server/cafe_util/"

  echo "[4/5] Copy frontend bundle"
  mkdir -p "${host_dir}/server/common/web/static"
  cp "${ROOT_DIR}/dist/cafe-plugin.js" "${host_dir}/server/common/web/static/cafe-plugin.js"

  echo "[5/5] Inject host hooks"
  cd "${ROOT_DIR}"
  python3 scripts/inject_server.py
  python3 scripts/inject_client.py

  echo "Done. Now start cellxgene as usual."
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  config_main "$@"
fi