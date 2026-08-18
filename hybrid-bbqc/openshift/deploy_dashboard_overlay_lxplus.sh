#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
unset PYTHONHOME PYTHONINSPECT PYTHONOPTIMIZE PYTHONPATH

SOURCE_REVISION='17f0132629095866531f5f903f6b55c240b40d70'
RAW_ROOT="https://raw.githubusercontent.com/pyoung527/etroc-visual-no-ball-report/${SOURCE_REVISION}"
INDEX_SHA256='e473694530c58cda95ccd270abe9c2dea11b8db61f8684b7671292628500faa9'
CSS_SHA256='5f9d7e3bab4ac732d6e7800f2c2a70fe75184db6f00a6e41da2d677e1d1a5b8f'
JS_SHA256='317e358631a8cea15ea4dabe6369ab1f5480454baf6e7ddcfae66d9c1b3d1644'
ETROC_CSS_SHA256='028bb4d38f70740aa18fed096de79772ec5104012f27576b5e194de7796b7ca2'
ETROC_JS_SHA256='98059cd915fb72b6228b96acbfe98646d45d5011ee1ac8491f957255b79f5cad'
LGAD_STATS_JS_SHA256='e3cfb2eff6b8391cdae80b19cf75740bb5680c12434402594eb894ce36796a02'
ETROC_MANIFEST_SHA256='96de00c344aabb3152a0d44323cc52c26e1e930dad63f25ae1d59fb4be5d3f9e'
ETROC_DATASET_REL='data/etroc-optical/ETROC_OI_2608'
SELECTOR_SHA256='54e53acf4853fab3d804101568cfd4276272c45e15cc59e8bb5bb3befb91cc86'
VALIDATOR_SHA256='ecec82614fdc8c6524c722fd5809886d8fbe1e7799d6b04a0da2f50cfdd1f9f8'
SSO_SOURCE_REVISION='d049ae2182f795c4f5dec15dfb8dbef8971518da'
SSO_SOURCE_SHA256='67b6eebc40f8b36e44124bfcec3fc526e29f93830fa203d0c8feeedfd99e9ca3'
SSO_PATCHED_SHA256='179d62436395bd82aa67a1cc4a902ec6e17a12e07d53c1a71f1298079a4b041c'
API_SERVER='https://api.paas.okd.cern.ch'
EXPECTED_API_SERVER='https://api.paas.okd.cern.ch:443'
EXPECTED_USER='ypark'
PROJECT='etroc-solder-inspection'
DEPLOYMENT='etl-hybrid-bbqc'
BUILDCONFIG='etl-hybrid-bbqc'
PVC='etl-hybrid-bbqc-comments'
EXPECTED_TOP_LEVEL=$'hybrid-bbqc\noverlay'
BACKUP_DIR="${HOME}/bbqc-backups"
CURRENT_RELEASE_STATE="${BACKUP_DIR}/current-release.env"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/bbqc-dashboard-release.XXXXXXXX")"
BUILD_CONTEXT="${WORK_DIR}/context"
SELECTOR="${WORK_DIR}/select_single_app_pod.py"
VALIDATOR="${WORK_DIR}/validate_build_provenance.py"
ROLLOUT_MUTATED=0
RELEASE_STATE=''
OLD_DEPLOYMENT_FILE=''
CAPTURED_DEPLOYMENT_FILE=''
CAPTURED_DEPLOYMENT_SHA256=''
FORWARD_DEPLOYMENT_FILE=''
FORWARD_DEPLOYMENT_SHA256=''
OLD_WEB_IMAGE=''
OLD_PROXY_IMAGE=''
DEPLOYMENT_UID=''
DEPLOYMENT_RESOURCE_VERSION=''
BUILDCONFIG_FILE=''
BUILDCONFIG_SHA256=''
BUILDCONFIG_UID=''
BUILDCONFIG_RESOURCE_VERSION=''
BUILD_OUTPUT_DIGEST=''
NEW_WEB_IMAGE=''

cleanup() {
  rm -rf "$WORK_DIR"
}

normalize_api_server() {
  python3 -I - "$1" <<'PY'
import sys
from urllib.parse import urlsplit
u = urlsplit(sys.argv[1])
if u.scheme != 'https' or u.hostname != 'api.paas.okd.cern.ch':
    raise SystemExit('unexpected API scheme or host')
if u.port not in (None, 443) or u.username or u.password:
    raise SystemExit('unexpected API authority')
if u.path.rstrip('/') or u.query or u.fragment:
    raise SystemExit('unexpected API path, query, or fragment')
print('https://api.paas.okd.cern.ch:443')
PY
}

download() {
  local url="$1" destination="$2"
  curl --fail --silent --show-error --location \
    --retry 5 --retry-delay 2 --retry-max-time 180 \
    --connect-timeout 20 --max-time 300 \
    "$url" --output "$destination"
}

verify_context() {
  test "$(normalize_api_server "$(oc whoami --show-server)")" = "$EXPECTED_API_SERVER"
  test "$(oc whoami)" = "$EXPECTED_USER"
  test "$(oc project -q)" = "$PROJECT"
  if test -n "${DEPLOYMENT_UID:-}"; then
    test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.uid}')" = "$DEPLOYMENT_UID"
  fi
}

bootstrap_sso_plugin() {
  local install_root source wrapper requirements
  install_root="${WORK_DIR}/oc-sso-login"
  source="${install_root}/oc-sso-login.py"
  wrapper="${WORK_DIR}/bin/oc-sso_login"
  requirements="${install_root}/requirements.lock"
  install -d -m 700 "$install_root" "${WORK_DIR}/bin"
  python3 -I -m venv "${install_root}/venv"
  printf '%s\n' \
      'certifi==2024.8.30 --hash=sha256:922820b53db7a7257ffbda3f597266d435245903d80737e34f8a45ff3e3230d8' \
      'charset-normalizer @ https://files.pythonhosted.org/packages/bf/9b/08c0432272d77b04803958a4598a51e2a4b51c06640af8b8f0f908c18bf2/charset_normalizer-3.4.0-py3-none-any.whl --hash=sha256:fe9f97feb71aa9896b81973a7bbada8c49501dc73e58a10fcef6663af95e5079' \
      'dnspython==2.7.0 --hash=sha256:b4c34b7d10b51bcc3a5071e7b8dee77939f1e878477eeecc965e9835f63c6c86' \
      'idna==3.10 --hash=sha256:946d195a0d259cbba61165e88e65941f16e9b36ea6ddb97f00452bae8b1287d3' \
      'requests==2.32.3 --hash=sha256:70761cfe03c773ceb22aa2f671b4757976145175cdfca038c02654d061d6dcc6' \
      'urllib3==2.2.3 --hash=sha256:ca899ca043dcb1bafa3e262d73aa25c465bfb49e0bd9dd5d59f1d0acba2f8fac' \
    > "$requirements"
  "${install_root}/venv/bin/python" -m pip install --disable-pip-version-check \
    --only-binary=:all: --require-hashes --requirement "$requirements"
  download \
    "https://gitlab.cern.ch/paas-tools/oc-sso-login/-/raw/${SSO_SOURCE_REVISION}/oc-sso-login.py" \
    "$source"
  printf '%s  %s\n' "$SSO_SOURCE_SHA256" "$source" | sha256sum -c -
  python3 -I - "$source" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1])
text=path.read_text(encoding='utf-8')
old='''        if res.returncode != 0:
            print(cmd)
            print(res.stdout, res.stderr)
            raise Exception(f"oc login returned exit code {res.returncode}")'''
new='''        if res.returncode != 0:
            print_stderr(f"oc login failed with exit code {res.returncode}; command and output omitted because they may contain a bearer token")
            raise Exception(f"oc login returned exit code {res.returncode}")'''
if text.count(old) != 1:
    raise SystemExit('unexpected oc-sso-login failure block; refusing to patch')
path.write_text(text.replace(old, new), encoding='utf-8')
PY
  printf '%s  %s\n' "$SSO_PATCHED_SHA256" "$source" | sha256sum -c -
  chmod 500 "$source"
  printf '%s\n' '#!/usr/bin/env bash' \
    "exec env -u PYTHONHOME -u PYTHONINSPECT -u PYTHONOPTIMIZE -u PYTHONPATH \"${install_root}/venv/bin/python\" -I \"${source}\" \"\$@\"" > "$wrapper"
  chmod 700 "$wrapper"
}

ensure_authenticated() {
  if oc whoami >/dev/null 2>&1; then
    return
  fi
  bootstrap_sso_plugin
  export PATH="${WORK_DIR}/bin:${PATH}"
  printf '%s\n' 'Complete the CERN device authorization shown below in your browser.'
  oc sso-login --server="$API_SERVER"
}

select_single_app_pod() {
  local tmpdir selected
  tmpdir="$(mktemp -d "${WORK_DIR}/pod-selection.XXXXXXXX")"
  oc -n "$PROJECT" get pods -o json > "${tmpdir}/pods.json"
  oc -n "$PROJECT" get replicasets.apps -o json > "${tmpdir}/replicasets.json"
  selected="$(python3 -I "$SELECTOR" \
    --pods "${tmpdir}/pods.json" --replicasets "${tmpdir}/replicasets.json" \
    --deployment "$DEPLOYMENT" --deployment-uid "$DEPLOYMENT_UID" \
    --pvc "$PVC" --container web --container oauth2-proxy \
    --pvc-container web --pvc-mount-path /data)"
  rm -rf "$tmpdir"
  printf '%s\n' "$selected"
}

rollback_deployment() {
  local current rendered pod raw_web raw_proxy web proxy
  set -Eeuo pipefail
  verify_context
  test -r "$OLD_DEPLOYMENT_FILE"
  test -r "$FORWARD_DEPLOYMENT_FILE"
  test "$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)" = "$OLD_DEPLOYMENT_SHA256"
  test "$(sha256sum "$FORWARD_DEPLOYMENT_FILE" | cut -d' ' -f1)" = "$FORWARD_DEPLOYMENT_SHA256"
  current="${WORK_DIR}/deployment-current.json"
  rendered="${WORK_DIR}/deployment-rollback.json"
  oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$current"
  DEPLOYMENT_UID="$DEPLOYMENT_UID" OLD_DEPLOYMENT_FILE="$OLD_DEPLOYMENT_FILE" FORWARD_DEPLOYMENT_FILE="$FORWARD_DEPLOYMENT_FILE" \
    CURRENT_DEPLOYMENT="$current" ROLLBACK_DEPLOYMENT="$rendered" python3 -I - <<'PY'
import json, os
old = json.load(open(os.environ['OLD_DEPLOYMENT_FILE'], encoding='utf-8'))
forward = json.load(open(os.environ['FORWARD_DEPLOYMENT_FILE'], encoding='utf-8'))
current = json.load(open(os.environ['CURRENT_DEPLOYMENT'], encoding='utf-8'))
expected_uid = os.environ['DEPLOYMENT_UID']
if current['metadata'].get('uid') != expected_uid:
    raise SystemExit('rollback target UID changed')
if old['metadata']['name'] != current['metadata']['name'] or old['metadata']['namespace'] != current['metadata']['namespace']:
    raise SystemExit('rollback target identity changed')
if current['spec'] != forward['spec']:
    raise SystemExit('current Deployment spec differs from this release; refusing rollback overwrite')
if current['metadata'].get('labels', {}) != forward['metadata'].get('labels', {}):
    raise SystemExit('current Deployment metadata labels differs from this release')
for key in ('finalizers', 'ownerReferences'):
    if current['metadata'].get(key, []) != forward['metadata'].get(key, []):
        raise SystemExit(f'current Deployment metadata {key} differs from this release')
def operator_annotations(value):
    result=dict(value or {})
    result.pop('deployment.kubernetes.io/revision', None)
    result.pop('kubectl.kubernetes.io/last-applied-configuration', None)
    return result
if operator_annotations(current['metadata'].get('annotations')) != operator_annotations(forward['metadata'].get('annotations')):
    raise SystemExit('current Deployment metadata annotations differs from this release')
old['metadata']['resourceVersion'] = current['metadata']['resourceVersion']
json.dump(old, open(os.environ['ROLLBACK_DEPLOYMENT'], 'w', encoding='utf-8'), indent=2, sort_keys=True)
PY
  oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$rendered" >/dev/null
  oc -n "$PROJECT" replace --save-config=false -f "$rendered"
  oc -n "$PROJECT" rollout status deployment/"$DEPLOYMENT" --timeout=300s
  pod="$(select_single_app_pod)"
  raw_web="$(oc -n "$PROJECT" get pod "$pod" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
  raw_proxy="$(oc -n "$PROJECT" get pod "$pod" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
  web="${raw_web#docker-pullable://}"
  proxy="${raw_proxy#docker-pullable://}"
  test "$web" = "$OLD_WEB_IMAGE"
  test "$proxy" = "$OLD_PROXY_IMAGE"
  printf 'ROLLBACK PASS web=%s proxy=%s\n' "$web" "$proxy"
}

attempt_rollback() {
  local rollback_status
  printf '%s\n' 'Attempting complete Deployment rollback to captured immutable images.' >&2
  set +e
  (
    set -Eeuo pipefail
    rollback_deployment
  )
  rollback_status=$?
  set -e
  if test "$rollback_status" -ne 0; then
    printf 'AUTOMATIC ROLLBACK FAILED status=%s; keep evidence and contact the operator.\n' "$rollback_status" >&2
  fi
}

on_error() {
  local line="$1" status="$2"
  trap - ERR HUP INT TERM
  printf 'DEPLOYMENT FAILED line=%s status=%s\n' "$line" "$status" >&2
  if test -n "$RELEASE_STATE"; then
    printf 'Release evidence: %s\n' "$RELEASE_STATE" >&2
  fi
  if test "$ROLLOUT_MUTATED" = 1; then
    attempt_rollback
  fi
  exit "$status"
}

on_signal() {
  local signal="$1" status="$2"
  trap - ERR HUP INT TERM
  printf 'DEPLOYMENT INTERRUPTED signal=%s status=%s\n' "$signal" "$status" >&2
  if test -n "$RELEASE_STATE"; then
    printf 'Release evidence: %s\n' "$RELEASE_STATE" >&2
  fi
  if test "$ROLLOUT_MUTATED" = 1; then
    attempt_rollback
  fi
  exit "$status"
}

trap cleanup EXIT
trap 'on_error "$LINENO" "$?"' ERR
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

for command in oc curl python3 sha256sum tar; do
  command -v "$command" >/dev/null
 done
ensure_authenticated
oc project "$PROJECT" >/dev/null
verify_context

test "$(oc auth can-i create builds/build.openshift.io -n "$PROJECT")" = yes
test "$(oc auth can-i update deployments.apps -n "$PROJECT")" = yes
test "$(oc auth can-i get pods -n "$PROJECT")" = yes
test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.spec.strategy.type}')" = Recreate
test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.spec.replicas}')" = 1
test "$(oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o jsonpath='{.spec.source.type}')" = Binary
test "$(oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o jsonpath='{.spec.strategy.dockerStrategy.dockerfilePath}')" = hybrid-bbqc/Containerfile
oc -n "$PROJECT" rollout status deployment/"$DEPLOYMENT" --timeout=300s
DEPLOYMENT_UID="$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.uid}')"
[[ "$DEPLOYMENT_UID" =~ ^[A-Za-z0-9._:-]+$ ]]
verify_context

download "${RAW_ROOT}/hybrid-bbqc/openshift/select_single_app_pod.py" "$SELECTOR"
printf '%s  %s\n' "$SELECTOR_SHA256" "$SELECTOR" | sha256sum -c -
download "${RAW_ROOT}/hybrid-bbqc/openshift/validate_build_provenance.py" "$VALIDATOR"
printf '%s  %s\n' "$VALIDATOR_SHA256" "$VALIDATOR" | sha256sum -c -
POD="$(select_single_app_pod)"
RAW_OLD_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
OLD_WEB_IMAGE="${RAW_OLD_WEB_IMAGE#docker-pullable://}"
case "$OLD_WEB_IMAGE" in *@sha256:*) ;; *) printf '%s\n' 'Current web image is not immutable.' >&2; false;; esac
RAW_OLD_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
OLD_PROXY_IMAGE="${RAW_OLD_PROXY_IMAGE#docker-pullable://}"
case "$OLD_PROXY_IMAGE" in *@sha256:*) ;; *) printf '%s\n' 'Current proxy image is not immutable.' >&2; false;; esac

BEFORE_COMMENTS="$(oc -n "$PROJECT" exec "$POD" -c web -- python -c \
  "import sqlite3; print(sqlite3.connect('/data/comments.sqlite3').execute('SELECT COUNT(*) FROM comments').fetchone()[0])")"
[[ "$BEFORE_COMMENTS" =~ ^[0-9]+$ ]]
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/data/comments.sqlite3.before-dashboard-${STAMP}.bak"
install -d -m 700 "$BACKUP_DIR"
LOCAL_BACKUP="${BACKUP_DIR}/$(basename "$BACKUP")"
RELEASE_STATE="${BACKUP_DIR}/dashboard-release-${STAMP}.env"
OLD_DEPLOYMENT_FILE="${BACKUP_DIR}/deployment-before-dashboard-${STAMP}.json"
CAPTURED_DEPLOYMENT_FILE="${BACKUP_DIR}/deployment-captured-dashboard-${STAMP}.json"
FORWARD_DEPLOYMENT_FILE="${BACKUP_DIR}/deployment-forward-dashboard-${STAMP}.json"
BUILDCONFIG_FILE="${BACKUP_DIR}/buildconfig-captured-dashboard-${STAMP}.json"
oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$CAPTURED_DEPLOYMENT_FILE"
oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o json > "$BUILDCONFIG_FILE"
CAPTURED_DEPLOYMENT_SHA256="$(sha256sum "$CAPTURED_DEPLOYMENT_FILE" | cut -d' ' -f1)"
BUILDCONFIG_SHA256="$(sha256sum "$BUILDCONFIG_FILE" | cut -d' ' -f1)"
[[ "$CAPTURED_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$BUILDCONFIG_SHA256" =~ ^[0-9a-f]{64}$ ]]
DEPLOYMENT_RESOURCE_VERSION="$(python3 -I - "$CAPTURED_DEPLOYMENT_FILE" <<'PY'
import json, sys
source=json.load(open(sys.argv[1], encoding='utf-8'))
uid=source.get('metadata', {}).get('uid')
resource_version=source.get('metadata', {}).get('resourceVersion')
if not isinstance(uid, str) or not uid:
    raise SystemExit('captured Deployment UID is missing')
if not isinstance(resource_version, str) or not resource_version:
    raise SystemExit('captured Deployment resourceVersion is missing')
if source.get('metadata', {}).get('deletionTimestamp') is not None:
    raise SystemExit('captured Deployment is being deleted')
trigger=source.get('metadata', {}).get('annotations', {}).get('image.openshift.io/triggers')
if trigger:
    try:
        parsed=json.loads(trigger)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'invalid Deployment image trigger annotation: {exc}') from exc
    if parsed:
        raise SystemExit('Deployment image triggers are not allowed for digest-pinned release')
print(resource_version)
PY
)"
test "$(python3 -I - "$CAPTURED_DEPLOYMENT_FILE" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['metadata']['uid'])
PY
)" = "$DEPLOYMENT_UID"
read -r BUILDCONFIG_UID BUILDCONFIG_RESOURCE_VERSION < <(python3 -I - "$BUILDCONFIG_FILE" <<'PY'
import json, sys
source=json.load(open(sys.argv[1], encoding='utf-8'))
metadata=source.get('metadata', {})
spec=source.get('spec', {})
uid=metadata.get('uid')
resource_version=metadata.get('resourceVersion')
if not isinstance(uid, str) or not uid or not isinstance(resource_version, str) or not resource_version:
    raise SystemExit('captured BuildConfig identity is incomplete')
if metadata.get('name') != 'etl-hybrid-bbqc' or metadata.get('namespace') != 'etroc-solder-inspection':
    raise SystemExit('captured BuildConfig target identity changed')
if spec.get('source', {}).get('type') != 'Binary':
    raise SystemExit('captured BuildConfig source is not Binary')
if spec.get('strategy', {}).get('dockerStrategy', {}).get('dockerfilePath') != 'hybrid-bbqc/Containerfile':
    raise SystemExit('captured BuildConfig Dockerfile path changed')
output=spec.get('output', {}).get('to', {})
if output.get('kind') != 'ImageStreamTag' or output.get('name') != 'etl-hybrid-bbqc:latest':
    raise SystemExit('captured BuildConfig output target changed')
print(uid, resource_version)
PY
)
[[ "$BUILDCONFIG_UID" =~ ^[A-Za-z0-9._:-]+$ ]]
[[ "$BUILDCONFIG_RESOURCE_VERSION" =~ ^[A-Za-z0-9._:-]+$ ]]

export OLD_WEB_IMAGE OLD_PROXY_IMAGE DEPLOYMENT_UID CAPTURED_DEPLOYMENT_FILE
python3 -I - <<'PY' > "$OLD_DEPLOYMENT_FILE"
import json, os, sys
source=json.load(open(os.environ['CAPTURED_DEPLOYMENT_FILE'], encoding='utf-8'))
if source.get('metadata', {}).get('uid') != os.environ['DEPLOYMENT_UID']:
    raise SystemExit('captured Deployment UID changed')
metadata={key: source['metadata'][key] for key in ('name','namespace','labels','annotations','finalizers','ownerReferences') if key in source['metadata']}
desired={'apiVersion': source['apiVersion'], 'kind': 'Deployment', 'metadata': metadata, 'spec': source['spec']}
images={'web': os.environ['OLD_WEB_IMAGE'], 'oauth2-proxy': os.environ['OLD_PROXY_IMAGE']}
found=set()
for container in desired['spec']['template']['spec']['containers']:
    if container['name'] in images:
        container['image']=images[container['name']]
        found.add(container['name'])
if found != set(images):
    raise SystemExit(f'captured containers do not match expected set: {sorted(found)}')
json.dump(desired, sys.stdout, indent=2, sort_keys=True)
PY
OLD_DEPLOYMENT_SHA256="$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)"
[[ "$OLD_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]

oc -n "$PROJECT" exec -i "$POD" -c web -- env BACKUP="$BACKUP" BEFORE_COMMENTS="$BEFORE_COMMENTS" python - <<'PY'
import os, sqlite3
source = sqlite3.connect('/data/comments.sqlite3')
target = sqlite3.connect(os.environ['BACKUP'])
with target:
    source.backup(target)
integrity = target.execute('PRAGMA integrity_check').fetchone()[0]
comments = target.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
target.close(); source.close()
if integrity != 'ok':
    raise SystemExit(f'remote backup integrity check failed: {integrity}')
if comments != int(os.environ['BEFORE_COMMENTS']):
    raise SystemExit(f'remote backup comment count changed: {comments}')
print({'integrity': integrity, 'comments': comments})
PY
oc -n "$PROJECT" cp "$POD:$BACKUP" "$LOCAL_BACKUP" -c web
export LOCAL_BACKUP BEFORE_COMMENTS
python3 -I - <<'PY'
import os, sqlite3
with sqlite3.connect(os.environ['LOCAL_BACKUP']) as db:
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    comments = db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
if integrity != 'ok':
    raise SystemExit(f'local backup integrity check failed: {integrity}')
if comments != int(os.environ['BEFORE_COMMENTS']):
    raise SystemExit(f'local backup comment count changed: {comments}')
print({'local_backup': os.environ['LOCAL_BACKUP'], 'integrity': integrity, 'comments': comments})
PY
BACKUP_SCHEMA_SHA256="$(python3 -I - "$LOCAL_BACKUP" <<'PY'
import hashlib, json, sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    rows=db.execute("SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name,tbl_name,sql").fetchall()
payload=json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
print(hashlib.sha256(payload).hexdigest())
PY
)"
[[ "$BACKUP_SCHEMA_SHA256" =~ ^[0-9a-f]{64}$ ]]
BACKUP_SHA256="$(sha256sum "$LOCAL_BACKUP" | cut -d' ' -f1)"
[[ "$BACKUP_SHA256" =~ ^[0-9a-f]{64}$ ]]
printf '%s  %s\n' "$BACKUP_SHA256" "$LOCAL_BACKUP" > "${LOCAL_BACKUP}.sha256"

mkdir -p "${BUILD_CONTEXT}/hybrid-bbqc" "${BUILD_CONTEXT}/overlay" "${BUILD_CONTEXT}/overlay/${ETROC_DATASET_REL}"
for file in index.html dashboard.css dashboard.js etroc-optical.css etroc-optical.js lgad-optical-stats.js; do
  download "${RAW_ROOT}/hybrid-bbqc/${file}" "${BUILD_CONTEXT}/overlay/${file}"
done
DATASET_DIR="${BUILD_CONTEXT}/overlay/${ETROC_DATASET_REL}"
download "${RAW_ROOT}/hybrid-bbqc/${ETROC_DATASET_REL}/SHA256SUMS" "${DATASET_DIR}/SHA256SUMS"
printf '%s  %s\n' "$ETROC_MANIFEST_SHA256" "${DATASET_DIR}/SHA256SUMS" | sha256sum -c -
python3 -I - "${DATASET_DIR}/SHA256SUMS" <<'PY'
from pathlib import PurePosixPath
import re, sys
lines=open(sys.argv[1], encoding='ascii').read().splitlines()
if len(lines) != 73:
    raise SystemExit(f'unexpected ETROC dataset manifest cardinality: {len(lines)}')
seen=set()
for line in lines:
    if not re.fullmatch(r'[0-9a-f]{64}  (chips\.json|(?:montages|previews)/(?:W02G4|W03F7|W05E5)-[0-9]+\.jpg)', line):
        raise SystemExit(f'unsafe ETROC dataset manifest entry: {line!r}')
    relative=line[66:]
    path=PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or relative in seen:
        raise SystemExit(f'unsafe or duplicate ETROC dataset path: {relative!r}')
    seen.add(relative)
if sum(path.startswith('montages/') for path in seen) != 36 or sum(path.startswith('previews/') for path in seen) != 36 or 'chips.json' not in seen:
    raise SystemExit('unexpected ETROC dataset asset roles')
PY
while read -r digest relative; do
  destination="${DATASET_DIR}/${relative}"
  mkdir -p "$(dirname "$destination")"
  download "${RAW_ROOT}/hybrid-bbqc/${ETROC_DATASET_REL}/${relative}" "$destination"
done < "${DATASET_DIR}/SHA256SUMS"
(
  cd "${BUILD_CONTEXT}/overlay"
  printf '%s  %s\n' "$INDEX_SHA256" index.html > SHA256SUMS
  printf '%s  %s\n' "$CSS_SHA256" dashboard.css >> SHA256SUMS
  printf '%s  %s\n' "$JS_SHA256" dashboard.js >> SHA256SUMS
  printf '%s  %s\n' "$ETROC_CSS_SHA256" etroc-optical.css >> SHA256SUMS
  printf '%s  %s\n' "$ETROC_JS_SHA256" etroc-optical.js >> SHA256SUMS
  printf '%s  %s\n' "$LGAD_STATS_JS_SHA256" lgad-optical-stats.js >> SHA256SUMS
  printf '%s  %s\n' "$ETROC_MANIFEST_SHA256" "${ETROC_DATASET_REL}/SHA256SUMS" >> SHA256SUMS
  sha256sum -c SHA256SUMS
  cd "$ETROC_DATASET_REL"
  sha256sum -c SHA256SUMS
)
printf '%s\n' \
  "FROM ${OLD_WEB_IMAGE}" \
  'USER root' \
  'COPY overlay/ /app/static/' \
  'RUN chown -R root:root /app/static && chmod -R u=rwX,go=rX /app/static' \
  'USER app' > "${BUILD_CONTEXT}/hybrid-bbqc/Containerfile"
ACTUAL_TOP_LEVEL="$(python3 -I - "$BUILD_CONTEXT" <<'PY'
from pathlib import Path
import sys
print('\n'.join(sorted(path.name for path in Path(sys.argv[1]).iterdir())))
PY
)"
test "$ACTUAL_TOP_LEVEL" = "$EXPECTED_TOP_LEVEL"
BUILD_CONTEXT_SHA256="$(tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -cf - -C "$BUILD_CONTEXT" hybrid-bbqc overlay | sha256sum | cut -d' ' -f1)"
[[ "$BUILD_CONTEXT_SHA256" =~ ^[0-9a-f]{64}$ ]]

{
  declare -p SOURCE_REVISION ETROC_DATASET_REL ETROC_MANIFEST_SHA256 API_SERVER EXPECTED_API_SERVER EXPECTED_USER PROJECT DEPLOYMENT BUILDCONFIG PVC
  declare -p DEPLOYMENT_UID OLD_WEB_IMAGE OLD_PROXY_IMAGE BEFORE_COMMENTS STAMP BACKUP LOCAL_BACKUP BACKUP_SHA256 BACKUP_SCHEMA_SHA256
  declare -p DEPLOYMENT_RESOURCE_VERSION CAPTURED_DEPLOYMENT_FILE CAPTURED_DEPLOYMENT_SHA256
  declare -p BUILDCONFIG_FILE BUILDCONFIG_SHA256 BUILDCONFIG_UID BUILDCONFIG_RESOURCE_VERSION
  declare -p OLD_DEPLOYMENT_FILE OLD_DEPLOYMENT_SHA256 FORWARD_DEPLOYMENT_FILE BUILD_CONTEXT_SHA256
} > "$RELEASE_STATE"
chmod 600 "$RELEASE_STATE"

verify_context
test "$(oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o jsonpath='{.metadata.uid}')" = "$BUILDCONFIG_UID"
test "$(oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o jsonpath='{.metadata.resourceVersion}')" = "$BUILDCONFIG_RESOURCE_VERSION"
test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$DEPLOYMENT_RESOURCE_VERSION"
BUILD_NAME="$(oc -n "$PROJECT" start-build "$BUILDCONFIG" --from-dir="$BUILD_CONTEXT" -o name)"
oc -n "$PROJECT" logs -f "$BUILD_NAME"
oc -n "$PROJECT" wait --for=condition=Complete "$BUILD_NAME" --timeout=900s
test "$(oc -n "$PROJECT" get "$BUILD_NAME" -o jsonpath='{.status.phase}')" = Complete
test "$(oc -n "$PROJECT" get "$BUILD_NAME" -o jsonpath='{.metadata.annotations.openshift\.io/build-config\.name}')" = "$BUILDCONFIG"
test "$(oc -n "$PROJECT" get "$BUILD_NAME" -o jsonpath='{.metadata.ownerReferences[?(@.kind=="BuildConfig")].uid}')" = "$BUILDCONFIG_UID"
test "$(oc -n "$PROJECT" get "$BUILD_NAME" -o jsonpath='{.spec.output.to.kind}')" = ImageStreamTag
test "$(oc -n "$PROJECT" get "$BUILD_NAME" -o jsonpath='{.spec.output.to.name}')" = etl-hybrid-bbqc:latest
test "$(oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o jsonpath='{.metadata.uid}')" = "$BUILDCONFIG_UID"
CURRENT_BUILDCONFIG_FILE="${WORK_DIR}/buildconfig-current.json"
BUILD_FILE="${WORK_DIR}/build-current.json"
oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o json > "$CURRENT_BUILDCONFIG_FILE"
oc -n "$PROJECT" get "$BUILD_NAME" -o json > "$BUILD_FILE"
python3 -I "$VALIDATOR" \
  --captured "$BUILDCONFIG_FILE" --current "$CURRENT_BUILDCONFIG_FILE" \
  --build "$BUILD_FILE" --name "$BUILDCONFIG" --namespace "$PROJECT"
test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$DEPLOYMENT_RESOURCE_VERSION"
BUILD_OUTPUT_DIGEST="$(python3 -I - "$BUILD_FILE" <<'PY'
import json, re, sys
build=json.load(open(sys.argv[1], encoding='utf-8'))
digest=build.get('status', {}).get('output', {}).get('to', {}).get('imageDigest')
if not isinstance(digest, str) or re.fullmatch(r'sha256:[0-9a-f]{64}', digest) is None:
    raise SystemExit('validated Build output image digest is invalid')
print(digest)
PY
)"
[[ "$BUILD_OUTPUT_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]
NEW_WEB_IMAGE="$(oc -n "$PROJECT" get "isimage/etl-hybrid-bbqc@${BUILD_OUTPUT_DIGEST}" -o jsonpath='{.image.dockerImageReference}')"
case "$NEW_WEB_IMAGE" in *@"$BUILD_OUTPUT_DIGEST") ;; *) printf '%s\n' 'Build-specific output image is not immutable.' >&2; false;; esac
test "$NEW_WEB_IMAGE" != "$OLD_WEB_IMAGE"
declare -p BUILD_NAME BUILD_OUTPUT_DIGEST NEW_WEB_IMAGE >> "$RELEASE_STATE"

verify_context
test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$DEPLOYMENT_RESOURCE_VERSION"
export NEW_WEB_IMAGE SOURCE_REVISION BUILD_CONTEXT_SHA256 BUILD_NAME DEPLOYMENT_RESOURCE_VERSION
python3 -I - <<'PY' > "$FORWARD_DEPLOYMENT_FILE"
import json, os, sys
source=json.load(open(os.environ['CAPTURED_DEPLOYMENT_FILE'], encoding='utf-8'))
metadata=source.get('metadata', {})
if metadata.get('uid') != os.environ['DEPLOYMENT_UID']:
    raise SystemExit('captured Deployment UID changed before rollout')
if metadata.get('resourceVersion') != os.environ['DEPLOYMENT_RESOURCE_VERSION']:
    raise SystemExit('captured Deployment resourceVersion changed before rollout')
desired_metadata={key: metadata[key] for key in ('name','namespace','labels','annotations','finalizers','ownerReferences','resourceVersion') if key in metadata}
desired_metadata.setdefault('annotations', {}).pop('kubectl.kubernetes.io/last-applied-configuration', None)
desired_metadata['annotations'].update({
    'bbqc.cern.ch/source-revision': os.environ['SOURCE_REVISION'],
    'bbqc.cern.ch/build-context-sha256': os.environ['BUILD_CONTEXT_SHA256'],
    'bbqc.cern.ch/build-name': os.environ['BUILD_NAME'],
    'bbqc.cern.ch/release-mode': 'immutable-overlay',
})
desired={'apiVersion': source['apiVersion'], 'kind': 'Deployment', 'metadata': desired_metadata, 'spec': source['spec']}
images={'web': os.environ['NEW_WEB_IMAGE'], 'oauth2-proxy': os.environ['OLD_PROXY_IMAGE']}
found=set()
for container in desired['spec']['template']['spec']['containers']:
    if container['name'] in images:
        container['image']=images[container['name']]
        found.add(container['name'])
if found != set(images):
    raise SystemExit(f'forward containers do not match expected set: {sorted(found)}')
json.dump(desired, sys.stdout, indent=2, sort_keys=True)
PY
FORWARD_DEPLOYMENT_SHA256="$(sha256sum "$FORWARD_DEPLOYMENT_FILE" | cut -d' ' -f1)"
[[ "$FORWARD_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
declare -p FORWARD_DEPLOYMENT_SHA256 >> "$RELEASE_STATE"
oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$FORWARD_DEPLOYMENT_FILE" >/dev/null
ROLLOUT_MUTATED=1
oc -n "$PROJECT" replace --save-config=false -f "$FORWARD_DEPLOYMENT_FILE"
oc -n "$PROJECT" rollout status deployment/"$DEPLOYMENT" --timeout=300s
verify_context
POD="$(select_single_app_pod)"
RAW_POD_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
POD_WEB_IMAGE="${RAW_POD_WEB_IMAGE#docker-pullable://}"
test "$POD_WEB_IMAGE" = "$NEW_WEB_IMAGE"
RAW_POD_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
POD_PROXY_IMAGE="${RAW_POD_PROXY_IMAGE#docker-pullable://}"
test "$POD_PROXY_IMAGE" = "$OLD_PROXY_IMAGE"

REMOTE_INDEX_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/index.html | cut -d' ' -f1)"
REMOTE_CSS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/dashboard.css | cut -d' ' -f1)"
REMOTE_JS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/dashboard.js | cut -d' ' -f1)"
REMOTE_ETROC_CSS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/etroc-optical.css | cut -d' ' -f1)"
REMOTE_ETROC_JS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/etroc-optical.js | cut -d' ' -f1)"
REMOTE_LGAD_STATS_JS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/lgad-optical-stats.js | cut -d' ' -f1)"
REMOTE_ETROC_MANIFEST_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum "/app/static/${ETROC_DATASET_REL}/SHA256SUMS" | cut -d' ' -f1)"
test "$REMOTE_INDEX_SHA" = "$INDEX_SHA256"
test "$REMOTE_CSS_SHA" = "$CSS_SHA256"
test "$REMOTE_JS_SHA" = "$JS_SHA256"
test "$REMOTE_ETROC_CSS_SHA" = "$ETROC_CSS_SHA256"
test "$REMOTE_ETROC_JS_SHA" = "$ETROC_JS_SHA256"
test "$REMOTE_LGAD_STATS_JS_SHA" = "$LGAD_STATS_JS_SHA256"
test "$REMOTE_ETROC_MANIFEST_SHA" = "$ETROC_MANIFEST_SHA256"
oc -n "$PROJECT" exec "$POD" -c web -- sh -c \
  "cd '/app/static/${ETROC_DATASET_REL}' && sha256sum -c SHA256SUMS"
oc -n "$PROJECT" exec -i "$POD" -c web -- env ETROC_DATASET_REL="$ETROC_DATASET_REL" python - <<'PY'
import json, os
from collections import Counter
from pathlib import Path
root=Path('/app/static') / os.environ['ETROC_DATASET_REL']
payload=json.loads((root / 'chips.json').read_text(encoding='utf-8'))
records=payload.get('records')
if payload.get('dataset_id') != 'ETROC_OI_2608' or payload.get('publication_status') != 'exploratory_review_pending':
    raise SystemExit('runtime ETROC dataset identity/status mismatch')
if not isinstance(records, list) or len(records) != 36 or payload.get('position_record_count') != 9216:
    raise SystemExit('runtime ETROC dataset cardinality mismatch')
if Counter(row['wafer'] for row in records) != Counter({'W02G4': 18, 'W03F7': 9, 'W05E5': 9}):
    raise SystemExit('runtime ETROC wafer cardinality mismatch')
assets=[root / row[key] for row in records for key in ('montage_uri','preview_uri')]
if len(set(assets)) != 72 or any(not path.is_file() or path.stat().st_size == 0 for path in assets):
    raise SystemExit('runtime ETROC asset inventory mismatch')
print({'dataset_id': payload['dataset_id'], 'records': len(records), 'assets': len(assets), 'positions': payload['position_record_count']})
PY

oc -n "$PROJECT" exec -i "$POD" -c web -- env \
  INDEX_SHA256="$INDEX_SHA256" ETROC_CSS_SHA256="$ETROC_CSS_SHA256" \
  ETROC_JS_SHA256="$ETROC_JS_SHA256" LGAD_STATS_JS_SHA256="$LGAD_STATS_JS_SHA256" python - <<'PY'
import hashlib, json, os
import urllib.request

base = 'http://127.0.0.1:8080/'

def fetch(path):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        if response.status != 200:
            raise SystemExit(f'runtime HTTP asset returned {response.status}: {path}')
        data = response.read()
    if not data:
        raise SystemExit(f'runtime HTTP asset is empty: {path}')
    return data

for path, expected_sha256 in (
    ('', os.environ['INDEX_SHA256']),
    ('etroc-optical.js', os.environ['ETROC_JS_SHA256']),
    ('etroc-optical.css', os.environ['ETROC_CSS_SHA256']),
    ('lgad-optical-stats.js', os.environ['LGAD_STATS_JS_SHA256']),
):
    actual = hashlib.sha256(fetch(path)).hexdigest()
    if actual != expected_sha256:
        raise SystemExit(f'runtime HTTP asset checksum mismatch: {path} {actual}')

chips_path = 'data/etroc-optical/ETROC_OI_2608/chips.json'
payload = json.loads(fetch(chips_path))
if payload.get('dataset_id') != 'ETROC_OI_2608' or len(payload.get('records', [])) != 36:
    raise SystemExit('runtime HTTP ETROC payload identity/cardinality mismatch')

for path in (
    'data/etroc-optical/ETROC_OI_2608/previews/W02G4-44.jpg',
    'data/etroc-optical/ETROC_OI_2608/montages/W02G4-44.jpg',
):
    image = fetch(path)
    if not image.startswith(b'\xff\xd8') or not image.endswith(b'\xff\xd9'):
        raise SystemExit(f'runtime HTTP JPEG contract failed: {path}')

print(f"RUNTIME_HTTP_ASSETS PASS dataset_id={payload['dataset_id']} records={len(payload['records'])}")
PY

oc -n "$PROJECT" exec -i "$POD" -c web -- env BEFORE_COMMENTS="$BEFORE_COMMENTS" BACKUP_SCHEMA_SHA256="$BACKUP_SCHEMA_SHA256" python - <<'PY'
import hashlib, json, os, sqlite3
with sqlite3.connect('/data/comments.sqlite3') as db:
    schema_rows = db.execute("SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name,tbl_name,sql").fetchall()
    comments = db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
    foreign_key_errors = db.execute('PRAGMA foreign_key_check').fetchall()
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
schema_payload = json.dumps(schema_rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
runtime_schema_sha256 = hashlib.sha256(schema_payload).hexdigest()
if runtime_schema_sha256 != os.environ['BACKUP_SCHEMA_SHA256']:
    raise SystemExit(f'runtime database schema changed: {runtime_schema_sha256}')
if comments < int(os.environ['BEFORE_COMMENTS']):
    raise SystemExit(f'comment count regressed: {comments}')
if foreign_key_errors:
    raise SystemExit(f'foreign key errors: {foreign_key_errors}')
if integrity != 'ok':
    raise SystemExit(f'runtime database integrity check failed: {integrity}')
print({'schema_sha256': runtime_schema_sha256, 'comments': comments, 'integrity': integrity})
PY
READY="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{range .status.containerStatuses[*]}{.name}={.ready}{"\n"}{end}')"
grep -qx 'web=true' <<< "$READY"
grep -qx 'oauth2-proxy=true' <<< "$READY"
RESTARTS="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{range .status.containerStatuses[*]}{.name}={.restartCount}{"\n"}{end}')"
grep -qx 'web=0' <<< "$RESTARTS"
grep -qx 'oauth2-proxy=0' <<< "$RESTARTS"
WEB_LOG="$(oc -n "$PROJECT" logs "$POD" -c web --tail=200)"
grep -Eq 'BBQC_STARTUP_OK|Serving /app/static with comments API on :8080;' <<< "$WEB_LOG"
if grep -Eiq 'Traceback|unhandled exception|migration failed' <<< "$WEB_LOG"; then
  printf '%s\n' 'Blocking web log error detected.' >&2
  false
fi
PROXY_LOG="$(oc -n "$PROJECT" logs "$POD" -c oauth2-proxy --tail=200)"
if grep -Eiq '(^|[[:space:]])(fatal|panic)([[:space:]:]|$)|level=(error|fatal)' <<< "$PROXY_LOG"; then
  printf '%s\n' 'Blocking oauth2-proxy log error detected.' >&2
  false
fi

HEADERS="${WORK_DIR}/route-headers"
HTTP_STATUS="$(curl --silent --show-error --dump-header "$HEADERS" --output /dev/null --write-out '%{http_code}' \
  https://etl-hybrid-bbqc.app.cern.ch/api/health)"
test "$HTTP_STATUS" = 302
LOCATION="$(python3 -I - "$HEADERS" <<'PY'
import sys
for line in open(sys.argv[1], encoding='iso-8859-1'):
    if line.lower().startswith('location:'):
        location=line.split(':',1)[1].strip()
print(location)
PY
)"
case "$LOCATION" in https://auth.cern.ch/*) ;; *) printf 'Unexpected SSO redirect: %s\n' "$LOCATION" >&2; false;; esac
printf 'SSO_PROXY_GATE PASS status=%s location=%s\n' "$HTTP_STATUS" "$LOCATION"
ln -sfn "$(basename "$RELEASE_STATE")" "$CURRENT_RELEASE_STATE"
ROLLOUT_MUTATED=0
printf 'DEPLOYMENT PASS source=%s build=%s image=%s comments_before=%s release_state=%s\n' \
  "$SOURCE_REVISION" "$BUILD_NAME" "$NEW_WEB_IMAGE" "$BEFORE_COMMENTS" "$RELEASE_STATE"
