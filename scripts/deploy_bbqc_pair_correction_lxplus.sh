#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

APP="etl-hybrid-bbqc"
PROJECT="etroc-solder-inspection"
CLUSTER="paas"
EXPECTED_COMMIT="d18535b60bfac9224a221b6e629f07bc4524a985"
OLD_PAIR="W04F2-81__FBK_LF-W14_34"
NEW_PAIR="W04F2-81__FBK_LF-W14_35"
PRESERVED_PAIR="W04F2-34__FBK_LF-W14_34"
OLD_TARGET="hybrid:${OLD_PAIR}"
NEW_TARGET="hybrid:${NEW_PAIR}"
RAW_BASE="https://raw.githubusercontent.com/pyoung527/etroc-visual-no-ball-report/${EXPECTED_COMMIT}"
SSO_PLUGIN_COMMIT="d049ae2182f795c4f5dec15dfb8dbef8971518da"
WORK_ROOT="/tmp/${USER}/bbqc-pair-correction-${EXPECTED_COMMIT:0:12}"
BIN_DIR="${WORK_ROOT}/bin"
VENV_DIR="${WORK_ROOT}/venv"
CONTEXT_DIR="${WORK_ROOT}/context"
ARCHIVE="${WORK_ROOT}/overlay-build.tar.gz"
export KUBECONFIG="${WORK_ROOT}/kubeconfig"
export PIP_NO_CACHE_DIR=1

log() { printf '\n[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
cleanup() {
  rm -f "$KUBECONFIG" "$ARCHIVE"
  rm -rf "$CONTEXT_DIR" "$VENV_DIR" "$BIN_DIR"
}
trap cleanup EXIT

mkdir -p "$BIN_DIR" "$CONTEXT_DIR/hybrid-bbqc" \
  "$CONTEXT_DIR/overlay/hybrids" \
  "$CONTEXT_DIR/overlay/data" \
  "$CONTEXT_DIR/overlay/assets/nw_scans"
chmod 700 "$WORK_ROOT" "$BIN_DIR" "$CONTEXT_DIR"

for cmd in curl tar python3 sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || fail "required command not found: $cmd"
done

if command -v oc >/dev/null 2>&1; then
  OC="$(command -v oc)"
else
  log "Installing the OpenShift client under ${BIN_DIR}"
  curl -fsSL --retry 3 \
    "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz" \
    -o "${WORK_ROOT}/openshift-client-linux.tar.gz"
  tar -xzf "${WORK_ROOT}/openshift-client-linux.tar.gz" -C "$BIN_DIR" oc
  rm -f "${WORK_ROOT}/openshift-client-linux.tar.gz"
  OC="${BIN_DIR}/oc"
fi
export PATH="${BIN_DIR}:${PATH}"
log "OpenShift client: $($OC version --client 2>/dev/null | head -n 1)"

if ! "$OC" whoami >/dev/null 2>&1; then
  log "No OKD session. Installing CERN's official oc-sso-login plugin in /tmp"
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet requests dnspython
  curl -fsSL --retry 3 \
    "https://gitlab.cern.ch/paas-tools/oc-sso-login/-/raw/${SSO_PLUGIN_COMMIT}/oc-sso-login.py" \
    -o "${BIN_DIR}/oc-sso_login"
  [[ "$(sha256sum "${BIN_DIR}/oc-sso_login" | cut -d' ' -f1)" == \
    "67b6eebc40f8b36e44124bfcec3fc526e29f93830fa203d0c8feeedfd99e9ca3" ]] || \
    fail "SHA-256 mismatch for CERN oc-sso-login plugin"
  chmod 700 "${BIN_DIR}/oc-sso_login"
  export PATH="${VENV_DIR}/bin:${BIN_DIR}:${PATH}"
  log "Follow the Device Authorization URL/code printed below on the phone"
  "$OC" sso-login "$CLUSTER"
fi

IDENTITY="$($OC whoami)"
SERVER="$($OC whoami --show-server)"
[[ -n "$IDENTITY" && "$IDENTITY" != "system:anonymous" ]] || \
  fail "invalid OKD identity: ${IDENTITY:-empty}"
[[ "$SERVER" == "https://api.paas.okd.cern.ch" ]] || \
  fail "unexpected OKD server: ${SERVER}"
log "Authenticated identity=${IDENTITY} server=${SERVER}"

"$OC" get project "$PROJECT" >/dev/null
"$OC" project "$PROJECT" >/dev/null
[[ "$($OC project -q)" == "$PROJECT" ]] || fail "failed to select project ${PROJECT}"
for resource in "buildconfig/${APP}" "deployment/${APP}" "pvc/${APP}-comments" "imagestream/${APP}"; do
  "$OC" get "$resource" >/dev/null || fail "missing production resource: $resource"
done
log "Production scope verified: project=${PROJECT} app=${APP}"

select_ready_pod() {
  "$OC" get pods -l "app=${APP}" -o json | python3 -c '
import json,sys
items=json.load(sys.stdin).get("items",[])
def ready(p):
    if p.get("metadata",{}).get("deletionTimestamp"):
        return False
    if p.get("status",{}).get("phase") != "Running":
        return False
    cs={x.get("name"):x for x in p.get("status",{}).get("containerStatuses",[])}
    return cs.get("web",{}).get("ready") and cs.get("oauth2-proxy",{}).get("ready")
items=[p for p in items if ready(p)]
items.sort(key=lambda p:p.get("metadata",{}).get("creationTimestamp",""))
if not items: raise SystemExit(1)
print(items[-1]["metadata"]["name"])
'
}

CURRENT_POD="$(select_ready_pod)" || fail "no ready production pod found"
BASE_IMAGE_ID="$($OC get pod "$CURRENT_POD" -o json | python3 -c '
import json,sys
p=json.load(sys.stdin)
for c in p.get("status",{}).get("containerStatuses",[]):
    if c.get("name")=="web":
        print(c.get("imageID","")); break
')"
BASE_IMAGE_ID="${BASE_IMAGE_ID#docker-pullable://}"
BASE_IMAGE_ID="${BASE_IMAGE_ID#docker://}"
[[ "$BASE_IMAGE_ID" == *@sha256:* ]] || fail "could not resolve immutable current web imageID"
OLD_REVISION="$($OC get deployment "$APP" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')"
log "Current pod=${CURRENT_POD} revision=${OLD_REVISION} base_image=${BASE_IMAGE_ID##*@}"

fetch_verified() {
  local source_path="$1" destination="$2" expected_hash="$3"
  mkdir -p "$(dirname "$destination")"
  curl -fsSL --retry 3 "${RAW_BASE}/${source_path}" -o "$destination"
  local actual_hash
  actual_hash="$(sha256sum "$destination" | cut -d' ' -f1)"
  [[ "$actual_hash" == "$expected_hash" ]] || fail "SHA-256 mismatch for ${source_path}"
}

log "Fetching the five correction artifacts pinned to ${EXPECTED_COMMIT}"
fetch_verified "hybrid-bbqc/index.html" \
  "$CONTEXT_DIR/overlay/index.html" \
  "2c8efcb41500c6e28e05c51d930270f062f319d158fb36121e49ee5b8f1613ae"
fetch_verified "hybrid-bbqc/hybrids/${OLD_PAIR}.html" \
  "$CONTEXT_DIR/overlay/hybrids/${OLD_PAIR}.html" \
  "9cebb629c8f3414418be9c7074bfcbe17676500d96c12ce0f84ff88cb7975984"
fetch_verified "hybrid-bbqc/hybrids/${NEW_PAIR}.html" \
  "$CONTEXT_DIR/overlay/hybrids/${NEW_PAIR}.html" \
  "1870e5c59803977131e123dbeef1fbfc619e71c8c050bc8f70967664f2a8a223"
fetch_verified "hybrid-bbqc/data/comment_concordance_snapshot.json" \
  "$CONTEXT_DIR/overlay/data/comment_concordance_snapshot.json" \
  "5f5a46716bffdfd7d9242b9ef0f7a716f19e78e19feeeae5ed962e393ab8dd2e"
fetch_verified "assets/nw_scans/nw_scan_manifest.json" \
  "$CONTEXT_DIR/overlay/assets/nw_scans/nw_scan_manifest.json" \
  "4e75b08f5d4ee7eba4689efc2b12706de2243520f35cc60888a27bd1a6c346e8"

cat > "$CONTEXT_DIR/hybrid-bbqc/Containerfile" <<EOF
FROM ${BASE_IMAGE_ID}
USER root
COPY overlay/ /app/static/
RUN chown -R app:app /app/static
USER app
EOF

tar -C "$CONTEXT_DIR" -czf "$ARCHIVE" .
log "Overlay build context ready: $(du -h "$ARCHIVE" | cut -f1)"

log "Starting Binary Build from the immutable current production image"
"$OC" start-build "$APP" --from-archive="$ARCHIVE" --follow --wait
BUILD_NAME="$($OC get builds -l "buildconfig=${APP}" -o json | python3 -c '
import json,sys
items=json.load(sys.stdin).get("items",[])
items.sort(key=lambda x:x.get("metadata",{}).get("creationTimestamp",""))
if not items: raise SystemExit(1)
print(items[-1]["metadata"]["name"])
')"
BUILD_PHASE="$($OC get build "$BUILD_NAME" -o jsonpath='{.status.phase}')"
[[ "$BUILD_PHASE" == "Complete" ]] || fail "build ${BUILD_NAME} phase=${BUILD_PHASE}"
NEW_DIGEST="$($OC get imagestreamtag "${APP}:latest" -o jsonpath='{.image.metadata.name}')"
[[ "$NEW_DIGEST" == sha256:* ]] || fail "invalid output digest: ${NEW_DIGEST}"
[[ "${BASE_IMAGE_ID##*@}" != "$NEW_DIGEST" ]] || fail "build did not produce a new image digest"
log "Build complete: ${BUILD_NAME} digest=${NEW_DIGEST}"

log "Restarting production deployment to pull the new image"
"$OC" rollout restart "deployment/${APP}"
"$OC" rollout status "deployment/${APP}" --timeout=300s
NEW_POD="$(select_ready_pod)" || fail "no ready pod after rollout"
NEW_REVISION="$($OC get deployment "$APP" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}')"
NEW_IMAGE_ID="$($OC get pod "$NEW_POD" -o json | python3 -c '
import json,sys
p=json.load(sys.stdin)
for c in p.get("status",{}).get("containerStatuses",[]):
    if c.get("name")=="web":
        print(c.get("imageID","")); break
')"
[[ "$NEW_IMAGE_ID" == *"${NEW_DIGEST}" ]] || \
  fail "new pod imageID does not match build digest"
log "Rollout complete: revision=${OLD_REVISION}->${NEW_REVISION} pod=${NEW_POD}"

log "Verifying corrected static artifacts inside the new pod"
"$OC" exec -i "$NEW_POD" -c web -- \
  env OLD_PAIR="$OLD_PAIR" NEW_PAIR="$NEW_PAIR" PRESERVED_PAIR="$PRESERVED_PAIR" \
      OLD_TARGET="$OLD_TARGET" NEW_TARGET="$NEW_TARGET" \
  python - <<'PY'
import json, os
from pathlib import Path
root=Path('/app/static')
old=os.environ['OLD_PAIR']; new=os.environ['NEW_PAIR']; preserved=os.environ['PRESERVED_PAIR']
old_target=os.environ['OLD_TARGET']; new_target=os.environ['NEW_TARGET']
index=(root/'index.html').read_text()
assert new in index
assert preserved in index
assert old not in index
new_page=(root/'hybrids'/f'{new}.html').read_text()
assert new in new_page and f'data-comments-target="{new_target}"' in new_page
old_page=(root/'hybrids'/f'{old}.html').read_text()
assert new in old_page and ('location.replace' in old_page or 'http-equiv="refresh"' in old_page)
snapshot=json.loads((root/'data/comment_concordance_snapshot.json').read_text())
records=snapshot['records']
targets=[r.get('target') for r in records]
assert len(records)==72 and targets.count(new_target)==1 and old_target not in targets and f'hybrid:{preserved}' in targets
manifest=json.loads((root/'assets/nw_scans/nw_scan_manifest.json').read_text())
assert manifest['W04F2-81']['lgad']=='FBK_LF-W14_35'
assert manifest['W04F2-34']['lgad']=='FBK_LF-W14_34'
print('STATIC_CORRECTION PASS records=72 new=1 old=0 preserved=1')
PY

log "Creating an online SQLite backup and migrating only the corrected comment target"
"$OC" exec -i "$NEW_POD" -c web -- \
  env OLD_TARGET="$OLD_TARGET" NEW_TARGET="$NEW_TARGET" \
  python - <<'PY'
import os, sqlite3, time
from pathlib import Path
old=os.environ['OLD_TARGET']; new=os.environ['NEW_TARGET']
db_path=Path('/data/comments.sqlite3')
backup_dir=Path('/data/backups'); backup_dir.mkdir(parents=True,exist_ok=True)
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
backup_path=backup_dir/f'comments.sqlite3.before-W04F2-81-{stamp}.bak'
cols='id,target,body,status,author,author_display,created_at,updated_at,deleted'
with sqlite3.connect(db_path) as src:
    assert src.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    with sqlite3.connect(backup_path) as dst:
        src.backup(dst)
with sqlite3.connect(backup_path) as bak:
    assert bak.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
with sqlite3.connect(db_path) as db:
    db.execute('BEGIN IMMEDIATE')
    before=db.execute(f'SELECT {cols} FROM comments WHERE target IN (?,?) ORDER BY id',(old,new)).fetchall()
    old_ids=[r[0] for r in before if r[1]==old]
    metadata={r[0]:(r[2],r[3],r[4],r[5],r[6],r[7],r[8]) for r in before}
    if old_ids:
        placeholders=','.join('?' for _ in old_ids)
        db.execute(f'UPDATE comments SET target=? WHERE id IN ({placeholders})',(new,*old_ids))
    db.commit()
    after=db.execute(f'SELECT {cols} FROM comments WHERE target IN (?,?) ORDER BY id',(old,new)).fetchall()
    assert not any(r[1]==old for r in after)
    after_by_id={r[0]:r for r in after}
    for row_id, expected in metadata.items():
        row=after_by_id[row_id]
        assert row[1]==new
        assert (row[2],row[3],row[4],row[5],row[6],row[7],row[8])==expected
    active_total=db.execute('SELECT COUNT(*) FROM comments WHERE deleted=0').fetchone()[0]
    active_targets=db.execute('SELECT COUNT(DISTINCT target) FROM comments WHERE deleted=0').fetchone()[0]
    new_count=db.execute('SELECT COUNT(*) FROM comments WHERE target=? AND deleted=0',(new,)).fetchone()[0]
print(f'DB_MIGRATION PASS moved={len(old_ids)} new_active={new_count} active_total={active_total} active_targets={active_targets} backup={backup_path}')
PY

log "Verifying deployment state and the comments API"
"$OC" exec -i "$NEW_POD" -c web -- env NEW_TARGET="$NEW_TARGET" python - <<'PY'
import json, os, urllib.parse, urllib.request
base='http://127.0.0.1:8080'
health=json.load(urllib.request.urlopen(base+'/api/health',timeout=10))
assert health.get('ok') is True
target=os.environ['NEW_TARGET']
url=base+'/api/comments/summary?target='+urllib.parse.quote(target)
summary=json.load(urllib.request.urlopen(url,timeout=10))
assert target in summary
assert summary[target]['count'] >= 1
print(f'API_VERIFICATION PASS health=200 target={target} comments={summary[target]["count"]}')
PY

"$OC" get deployment "$APP" -o json | python3 -c '
import json,sys
d=json.load(sys.stdin); s=d.get("status",{}); desired=d.get("spec",{}).get("replicas")
vals=(desired,s.get("readyReplicas",0),s.get("updatedReplicas",0),s.get("availableReplicas",0))
assert vals==(1,1,1,1), vals
print("DEPLOYMENT_STATE PASS desired/ready/updated/available=1/1/1/1")
'

ROUTE_HOST="$($OC get route "$APP" -o jsonpath='{.spec.host}')"
HEADERS="${WORK_ROOT}/route-headers.txt"
curl -sS --max-time 20 -D "$HEADERS" -o /dev/null "https://${ROUTE_HOST}/"
python3 - "$HEADERS" <<'PY'
import sys
text=open(sys.argv[1],errors='replace').read().lower()
assert ('http/1.1 302' in text or 'http/2 302' in text) and 'auth.cern.ch' in text
print('ROUTE_GATE PASS status=302 redirect_host=auth.cern.ch')
PY
rm -f "$HEADERS"

printf '\nDEPLOYMENT_COMPLETE\n'
printf 'commit=%s\n' "$EXPECTED_COMMIT"
printf 'identity=%s\n' "$IDENTITY"
printf 'project=%s\n' "$PROJECT"
printf 'build=%s\n' "$BUILD_NAME"
printf 'digest=%s\n' "$NEW_DIGEST"
printf 'revision=%s->%s\n' "$OLD_REVISION" "$NEW_REVISION"
printf 'pod=%s\n' "$NEW_POD"
printf 'url=https://%s/\n' "$ROUTE_HOST"
