#!/usr/bin/env bash
set -euo pipefail

APP_NAME="etroc-solder-inspection"
PROJECT_NAME="${PROJECT_NAME:-etroc-solder-inspection}"
DISPLAY_NAME="ETROC solder inspection"
DESCRIPTION="ETROC solder inspection static report"
SERVER="${OKD_SERVER:-https://api.paas.okd.cern.ch}"
REPO_URL="${REPO_URL:-https://github.com/pyoung527/etroc-visual-no-ball-report.git}"
WORK_ROOT="${WORK_ROOT:-/tmp/${USER}/etroc-solder-inspection-okd}"
OC_DIR="${OC_DIR:-/tmp/${USER}/oc-client}"
OC_BIN="${OC_BIN:-${OC_DIR}/oc}"

log() { printf '\n[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

mkdir -p "$WORK_ROOT" "$OC_DIR"
chmod 700 "$WORK_ROOT" "$OC_DIR" || true

log "Using work root: $WORK_ROOT"
log "Using project: $PROJECT_NAME"

if command -v oc >/dev/null 2>&1; then
  OC="$(command -v oc)"
elif [[ -x "$OC_BIN" ]]; then
  OC="$OC_BIN"
else
  log "oc not found; installing OpenShift client under $OC_DIR"
  curl -fsSL "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz" -o "$WORK_ROOT/openshift-client-linux.tar.gz"
  tar -xzf "$WORK_ROOT/openshift-client-linux.tar.gz" -C "$OC_DIR" oc kubectl
  OC="$OC_BIN"
fi

log "oc client version"
"$OC" version --client

# Avoid writing kube config into the full lxplus home directory.
export KUBECONFIG="${KUBECONFIG:-$WORK_ROOT/kubeconfig}"

if ! "$OC" whoami >/dev/null 2>&1; then
  if [[ -z "${OKD_TOKEN:-}" ]]; then
    echo
    echo "Paste CERN OKD token. Input is hidden; token will not be echoed."
    read -r -s -p "OKD token: " OKD_TOKEN
    echo
  fi
  log "Logging in to $SERVER"
  "$OC" login --token="$OKD_TOKEN" --server="$SERVER"
else
  log "Already logged in as $("$OC" whoami)"
fi

log "Creating/selecting project"
if "$OC" get project "$PROJECT_NAME" >/dev/null 2>&1; then
  "$OC" project "$PROJECT_NAME"
else
  "$OC" new-project "$PROJECT_NAME" --description="$DESCRIPTION" --display-name="$DISPLAY_NAME"
fi

REPO_DIR="$WORK_ROOT/repo"
if [[ -d "$REPO_DIR/.git" ]]; then
  log "Updating existing repo clone"
  git -C "$REPO_DIR" fetch origin main
  git -C "$REPO_DIR" reset --hard origin/main
else
  log "Cloning repo"
  git clone --depth 1 "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"

log "Applying OKD resources"
"$OC" apply -f openshift/imagestream.yaml
"$OC" apply -f openshift/buildconfig.yaml

log "Starting build from GitHub source"
"$OC" start-build "$APP_NAME" --follow --wait

"$OC" apply -f openshift/deployment.yaml
"$OC" apply -f openshift/service.yaml
"$OC" apply -f openshift/route.yaml

log "Waiting for rollout"
"$OC" rollout status "deployment/${APP_NAME}" --timeout=180s

log "Current resources"
"$OC" get pods,svc,route -l "app=${APP_NAME}"

ROUTE_HOST="$("$OC" get route "$APP_NAME" -o jsonpath='{.spec.host}')"
ROUTE_URL="https://${ROUTE_HOST}"
log "Route URL: $ROUTE_URL"

log "HTTP checks"
curl -fsSI "$ROUTE_URL/" | sed -n '1,12p'
curl -fsSI "$ROUTE_URL/assets/images/visual_no_ball_chip_card_table_corrected.png" | sed -n '1,8p'
curl -fsSI "$ROUTE_URL/assets/montages/W03F7_DATA1_chip_87.jpg" | sed -n '1,8p'

echo
printf 'DEPLOYED_URL=%s\n' "$ROUTE_URL"
printf 'KUBECONFIG=%s\n' "$KUBECONFIG"
