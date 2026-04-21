#!/usr/bin/env bash

load_project_env() {
  local env_file="$1"
  if [[ ! -f "${env_file}" ]]; then
    return
  fi

  set -a
  # shellcheck disable=SC1090
  source "${env_file}"
  set +a
}

resolve_target_python() {
  local default_env_name="${1:-cellxgene_cafe}"
  local env_name="${CELLXGENE_CONDA_ENV:-${default_env_name}}"

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

run_npm() {
  local -a env_args=()

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