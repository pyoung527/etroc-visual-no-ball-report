#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
unset PYTHONHOME PYTHONINSPECT PYTHONOPTIMIZE PYTHONPATH
CANDIDATE_HOST_PYTHON='/usr/bin/python3.12'

SOURCE_REVISION='742be964df275a63ebd541d453d346f86034c19b'
RAW_ROOT="https://raw.githubusercontent.com/pyoung527/etroc-visual-no-ball-report/${SOURCE_REVISION}"
INDEX_SHA256='f2c97ef0ea2bd3eaf974ede7c5a1cccd1922e1846fda0039a29ef2a51e7ae90b'
CSS_SHA256='5f9d7e3bab4ac732d6e7800f2c2a70fe75184db6f00a6e41da2d677e1d1a5b8f'
JS_SHA256='317e358631a8cea15ea4dabe6369ab1f5480454baf6e7ddcfae66d9c1b3d1644'
ETROC_CSS_SHA256='8fb6b8dbfc2e02bb6c03c055689a5c7e2568d1633e6792c0f1d3930af667d40a'
ETROC_JS_SHA256='37c4d11b74bc3f4c706f74ab377d4c3e307c2cf1aae2795ce70b3695f252f496'
ETROC_REVIEW_JS_SHA256='13472e47c1f54f3efceb24662f6015a3d15441fc339788ffce2fb8a8117eaa1b'
ETROC_RESULTS_JS_SHA256='f97bd33202bf26b9c69ce2c4aa3299ca9a655a0f4ba2772fd5341f1c91b3db6c'
LGAD_STATS_JS_SHA256='e3cfb2eff6b8391cdae80b19cf75740bb5680c12434402594eb894ce36796a02'
ETROC_MANIFEST_SHA256='4860c04dbd5c2fd4a750150443dcab7385aa71067d68f86b1cf6b30f3f62b50b'
SERVER_PY_SHA256='d6bb2e7f7c1b82e1f3743e972fecbb53e493b8f4be6623dde57ae4e7379baa36'
ETROC_REVIEWS_PY_SHA256='1bbe25926481d38350e9138d509bf7fdc68b09874ce88d5bcc2ee534e15a1fa3'
ETROC_POSITION_REVIEWS_PY_SHA256='592714d659b85f3e38dd36bea69de891afd0929bf1326d03654c72c09460bdb2'
DEPLOYMENT_MANIFEST_SHA256='45a3a2266bcb4d18dcdb9949e5b55a00ed85f4f1e7494cebb87500b84bdbae30'
SERVICE_MANIFEST_SHA256='84b99d048fcf52d5dfbe9ee919287b36197429818228682fccbcc4ad4e5dcf5c'
ROUTE_MANIFEST_SHA256='23b1dbfa7cd930754ebc70eef3c853e164e55c43dbb8e05e5d0affad71ec8f43'
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
ETROC_REVIEWER_USERS='ypark,ypark@cern.ch,young.park@cern.ch'
ETROC_REVIEWER_USERS_NORMALIZED=''
ETROC_REVIEWER_USERS_COUNT=''
ETROC_REVIEWER_USERS_SHA256=''
EXPECTED_TOP_LEVEL=$'hybrid-bbqc\noverlay\nruntime'
BACKUP_DIR="${BBQC_BACKUP_DIR:-${HOME}/bbqc-backups}"
CURRENT_RELEASE_STATE="${BACKUP_DIR}/current-release.env"
PVC_BACKUP_SAFETY_KIB=102400
STORAGE_CHECKSUMS_KIB=64
STORAGE_RELEASE_EVIDENCE_KIB=20480
STORAGE_SAFETY_MARGIN_KIB=102400
MAX_RELEASE_ARTIFACT_SETS=20
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/bbqc-dashboard-release.XXXXXXXX")"
BUILD_CONTEXT="${WORK_DIR}/context"
CANDIDATE_DB="${WORK_DIR}/comments-candidate.sqlite3"
CANDIDATE_HTTP_ACQUISITION_FILE="${WORK_DIR}/candidate-http-acquisition-id"
OLD_RUNTIME_DIR="${WORK_DIR}/previous-runtime"
OLD_RUNTIME_SERVER="${OLD_RUNTIME_DIR}/server.py"
OLD_RUNTIME_ETROC_REVIEWS="${OLD_RUNTIME_DIR}/etroc_reviews.py"
OLD_RUNTIME_ETROC_POSITION_REVIEWS="${OLD_RUNTIME_DIR}/etroc_position_reviews.py"
MANIFESTS_DIR="${WORK_DIR}/manifests"
SERVICE_MANIFEST_FILE="${MANIFESTS_DIR}/service.yaml"
ROUTE_MANIFEST_FILE="${MANIFESTS_DIR}/route.yaml"
BASELINE_DEPLOYMENT_FILE="${WORK_DIR}/baseline-deployment.json"
BASELINE_SERVICE_FILE="${WORK_DIR}/baseline-service.json"
BASELINE_ROUTE_FILE="${WORK_DIR}/baseline-route.json"
SELECTOR="${WORK_DIR}/select_single_app_pod.py"
VALIDATOR="${WORK_DIR}/validate_build_provenance.py"
ROLLOUT_MUTATED=0
RELEASE_STATE=''
OLD_DEPLOYMENT_FILE=''
CAPTURED_DEPLOYMENT_FILE=''
CAPTURED_DEPLOYMENT_SHA256=''
CAPTURED_SERVICE_FILE=''
CAPTURED_SERVICE_SHA256=''
CAPTURED_ROUTE_FILE=''
CAPTURED_ROUTE_SHA256=''
FORWARD_DEPLOYMENT_FILE=''
FORWARD_DEPLOYMENT_SHA256=''
FORWARD_SERVICE_FILE=''
FORWARD_SERVICE_SHA256=''
FORWARD_ROUTE_FILE=''
FORWARD_ROUTE_SHA256=''
OLD_SERVICE_FILE=''
OLD_SERVICE_SHA256=''
OLD_ROUTE_FILE=''
OLD_ROUTE_SHA256=''
OLD_WEB_IMAGE=''
OLD_RELEASE_ANNOTATIONS_JSON='{}'
OLD_RUNTIME_SERVER_SHA256=''
OLD_PROXY_IMAGE=''
DEPLOYMENT_UID=''
DEPLOYMENT_RESOURCE_VERSION=''
SERVICE_UID=''
SERVICE_RESOURCE_VERSION=''
ROUTE_UID=''
ROUTE_RESOURCE_VERSION=''
BUILDCONFIG_FILE=''
BUILDCONFIG_SHA256=''
BUILDCONFIG_UID=''
BUILDCONFIG_RESOURCE_VERSION=''
BUILD_OUTPUT_DIGEST=''
NEW_WEB_IMAGE=''
ETROC_EVENT_SNAPSHOT_BEFORE=''
ETROC_EVENT_SNAPSHOT_BACKUP=''
ETROC_EVENT_SNAPSHOT_POST_ROLLOUT=''
POSITION_EVENT_SNAPSHOT_BEFORE=''
POSITION_EVENT_SNAPSHOT_BACKUP=''
POSITION_EVENT_SNAPSHOT_POST_ROLLOUT=''
CANDIDATE_PROBE_POD=''
CANDIDATE_PROBE_POD_UID=''
CANDIDATE_PROBE_POD_OWNED=0
CANDIDATE_PROBE_CREATE_RESPONSE="${WORK_DIR}/candidate-probe-create.json"
DURABLE_STORAGE_TYPE=''
DURABLE_STORAGE_CAPACITY_KIB=''
DURABLE_STORAGE_USED_KIB=''
DURABLE_STORAGE_FREE_KIB=''

cleanup() {
  if ! cleanup_candidate_probe_pod; then
    printf '%s\n' 'WARNING candidate probe cleanup did not complete' >&2
  fi
  rm -rf "$WORK_DIR"
}

cleanup_candidate_probe_pod() {
  local current_uid delete_options encoded_project encoded_pod status
  if test "$CANDIDATE_PROBE_POD_OWNED" != 1; then
    return 0
  fi
  if test -z "$CANDIDATE_PROBE_POD" || test -z "$CANDIDATE_PROBE_POD_UID"; then
    printf '%s\n' 'WARNING candidate probe ownership lacks an exact UID; refusing deletion' >&2
    return 1
  fi
  set +e
  current_uid="$(oc -n "$PROJECT" get pod/"$CANDIDATE_PROBE_POD" -o jsonpath='{.metadata.uid}' 2>/dev/null)"
  status=$?
  set -e
  if test "$status" -ne 0; then
    printf '%s\n' 'WARNING candidate probe is no longer resolvable; no deletion attempted' >&2
    return 1
  fi
  if test "$current_uid" != "$CANDIDATE_PROBE_POD_UID"; then
    printf '%s\n' 'WARNING candidate probe UID changed; refusing deletion' >&2
    return 1
  fi
  read -r encoded_project encoded_pod < <(python3 -I - "$PROJECT" "$CANDIDATE_PROBE_POD" <<'PY'
import re, sys
from urllib.parse import quote
for value in sys.argv[1:]:
    if re.fullmatch(r'[a-z0-9]([-a-z0-9.]*[a-z0-9])?', value) is None:
        raise SystemExit('unsafe Kubernetes resource name')
print(*(quote(value, safe='') for value in sys.argv[1:]))
PY
)
  delete_options="${WORK_DIR}/candidate-probe-delete-options.json"
  CANDIDATE_PROBE_POD_UID="$CANDIDATE_PROBE_POD_UID" python3 -I - > "$delete_options" <<'PY'
import json, os
json.dump({'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': os.environ['CANDIDATE_PROBE_POD_UID']}}, __import__('sys').stdout)
PY
  set +e
  oc -n "$PROJECT" delete --raw="/api/v1/namespaces/${encoded_project}/pods/${encoded_pod}" -f "$delete_options"
  status=$?
  set -e
  if test "$status" -ne 0; then
    printf '%s\n' 'WARNING candidate probe deletion failed; copied database may remain until manually removed' >&2
    return 1
  fi
  CANDIDATE_PROBE_POD_OWNED=0
}

verify_candidate_probe_identity() {
  local current_uid
  if test "$CANDIDATE_PROBE_POD_OWNED" != 1 || test -z "$CANDIDATE_PROBE_POD" || test -z "$CANDIDATE_PROBE_POD_UID"; then
    printf '%s\n' 'candidate probe exact ownership is unavailable' >&2
    return 1
  fi
  if ! current_uid="$(oc -n "$PROJECT" get pod/"$CANDIDATE_PROBE_POD" -o jsonpath='{.metadata.uid}')"; then
    printf '%s\n' 'candidate probe is no longer resolvable' >&2
    return 1
  fi
  if test "$current_uid" != "$CANDIDATE_PROBE_POD_UID"; then
    printf '%s\n' 'candidate probe UID changed; refusing name-based operation' >&2
    return 1
  fi
}

extract_previous_runtime_server() {
  local internal_prefix='image-registry.openshift-image-registry.svc:5000/etroc-solder-inspection/etl-hybrid-bbqc@sha256:'
  local image_digest public_image registry_auth
  test -n "$OLD_WEB_IMAGE" || return 1
  [[ "$OLD_WEB_IMAGE" =~ ^image-registry\.openshift-image-registry\.svc:5000/etroc-solder-inspection/etl-hybrid-bbqc@sha256:[0-9a-f]{64}$ ]] || return 1
  image_digest="${OLD_WEB_IMAGE#"$internal_prefix"}"
  [[ "$image_digest" =~ ^[0-9a-f]{64}$ ]] || return 1
  public_image="registry.paas.cern.ch/etroc-solder-inspection/etl-hybrid-bbqc@sha256:${image_digest}"
  registry_auth="${WORK_DIR}/registry-auth.json"
  trap 'rm -f -- "$registry_auth"' RETURN
  mkdir -m 700 "$OLD_RUNTIME_DIR" || return 1
  (umask 077; oc registry login --to="$registry_auth" >/dev/null) || return 1
  if ! REGISTRY_AUTH="$registry_auth" python3 -I - <<'PY'
import os, stat
from pathlib import Path

auth = Path(os.environ['REGISTRY_AUTH'])
status = auth.lstat()
if stat.S_ISLNK(status.st_mode) or not stat.S_ISREG(status.st_mode) or status.st_nlink != 1:
    raise SystemExit('registry auth file is not a regular non-symlink file')
if status.st_uid != os.geteuid() or status.st_mode & 0o077:
    raise SystemExit('registry auth file ownership or mode is unsafe')
if status.st_size == 0:
    raise SystemExit('registry auth file is empty')
PY
  then
    return 1
  fi
  oc image extract --registry-config="$registry_auth" "$public_image" \
    --path "/app/static/server.py:${OLD_RUNTIME_DIR}" \
    --path "/app/static/etroc_reviews.py:${OLD_RUNTIME_DIR}" \
    --path "/app/static/etroc_position_reviews.py:${OLD_RUNTIME_DIR}" || return 1
  rm -f -- "$registry_auth"
  trap - RETURN
  if ! OLD_RUNTIME_SERVER_SHA256="$(OLD_RUNTIME_DIR="$OLD_RUNTIME_DIR" OLD_RUNTIME_SERVER="$OLD_RUNTIME_SERVER" OLD_RUNTIME_ETROC_REVIEWS="$OLD_RUNTIME_ETROC_REVIEWS" OLD_RUNTIME_ETROC_POSITION_REVIEWS="$OLD_RUNTIME_ETROC_POSITION_REVIEWS" python3 -I - <<'PY'
import os, stat
from pathlib import Path

root = Path(os.environ['OLD_RUNTIME_DIR'])
source = Path(os.environ['OLD_RUNTIME_SERVER'])
dependency = Path(os.environ['OLD_RUNTIME_ETROC_REVIEWS'])
position_dependency = Path(os.environ['OLD_RUNTIME_ETROC_POSITION_REVIEWS'])
root_status = root.lstat()
if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(root_status.st_mode):
    raise SystemExit('previous runtime extraction directory is unsafe')
if root_status.st_uid != os.geteuid() or root_status.st_mode & 0o077:
    raise SystemExit('previous runtime extraction directory ownership or mode is unsafe')
entries = set(root.iterdir())
if entries != {source, dependency, position_dependency}:
    raise SystemExit('previous runtime extraction produced unexpected files')
for candidate in (source, dependency, position_dependency):
    candidate_status = candidate.lstat()
    if stat.S_ISLNK(candidate_status.st_mode) or not stat.S_ISREG(candidate_status.st_mode) or candidate_status.st_nlink != 1:
        raise SystemExit('previous runtime source is not a regular non-symlink file')
    if candidate_status.st_uid != os.geteuid() or candidate_status.st_mode & 0o022:
        raise SystemExit('previous runtime source ownership or mode is unsafe')
    candidate_contents = candidate.read_bytes()
    if not candidate_contents:
        raise SystemExit('previous runtime source is empty')
    try:
        compile(candidate_contents.decode('utf-8'), str(candidate), 'exec')
    except (SyntaxError, UnicodeDecodeError) as error:
        raise SystemExit(f'previous runtime source is malformed: {error}') from error
contents = source.read_bytes()
import hashlib
print(hashlib.sha256(contents).hexdigest())
PY
)"; then
    return 1
  fi
  [[ "$OLD_RUNTIME_SERVER_SHA256" =~ ^[0-9a-f]{64}$ ]] || return 1
  printf 'OLD_RUNTIME_SERVER_EXTRACT PASS image=%s sha256=%s\n' "$OLD_WEB_IMAGE" "$OLD_RUNTIME_SERVER_SHA256"
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

verify_candidate_host_python() {
  local candidate_python_version
  test -x "$CANDIDATE_HOST_PYTHON"
  candidate_python_version="$("$CANDIDATE_HOST_PYTHON" -I -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
  test "$candidate_python_version" = 3.12.14
  "$CANDIDATE_HOST_PYTHON" -I -c 'from dataclasses import make_dataclass; make_dataclass("Probe", [("value", int)], frozen=True, slots=True)'
  printf 'CANDIDATE_HOST_PYTHON PASS path=%s version=%s\n' "$CANDIDATE_HOST_PYTHON" "$candidate_python_version"
}

download() {
  local url="$1" destination="$2"
  curl --fail --silent --show-error --location \
    --retry 5 --retry-delay 2 --retry-max-time 180 \
    --connect-timeout 20 --max-time 300 \
    "$url" --output "$destination"
}

validate_backup_directory() {
  BACKUP_DIR="$1" WORK_DIR="$WORK_DIR" python3 -I - <<'PY'
import os, pwd, stat
from pathlib import PurePath

raw = os.environ['BACKUP_DIR']
if not raw or any(ord(character) < 32 or ord(character) == 127 for character in raw):
    raise SystemExit('unsafe backup directory path')
path = PurePath(raw)
if not path.is_absolute() or raw.startswith('//') or raw != os.path.normpath(raw) or any(part in ('.', '..') for part in path.parts):
    raise SystemExit('backup directory path must be canonical and absolute')
work_dir = os.environ['WORK_DIR']
if raw in ('/tmp', '/var/tmp') or (work_dir and (raw == work_dir or raw.startswith(work_dir + '/'))):
    raise SystemExit('unsafe backup directory path')
username = pwd.getpwuid(os.geteuid()).pw_name
home = PurePath(pwd.getpwnam(username).pw_dir)
if os.environ.get('HOME') != str(home) or not home.is_absolute() or os.path.realpath(home) != str(home):
    raise SystemExit('canonical HOME is invalid')
eos_root = PurePath('/eos', f'home-{username[0]}', username)
if not any(path != root and root in path.parents for root in (home, eos_root)):
    raise SystemExit('backup directory must be below the current user home or EOS root')

def directory_status(candidate: PurePath) -> os.stat_result:
    try:
        entry = os.lstat(candidate)
    except FileNotFoundError:
        raise SystemExit('backup directory parent is missing') from None
    if stat.S_ISLNK(entry.st_mode) or not stat.S_ISDIR(entry.st_mode):
        raise SystemExit('backup directory contains an unsafe path component')
    if entry.st_uid not in (0, os.geteuid()) or entry.st_mode & 0o022:
        raise SystemExit('backup directory path component ownership or mode is unsafe')
    return entry

for index in range(1, len(path.parts) - 1):
    directory_status(PurePath(*path.parts[:index + 1]))
parent = path.parent
parent_status = directory_status(parent)
if parent_status.st_uid != os.geteuid() or parent_status.st_mode & 0o022 or not os.access(parent, os.W_OK | os.X_OK):
    raise SystemExit('backup directory parent ownership or mode is unsafe')
try:
    final_status = os.lstat(path)
except FileNotFoundError:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    final_status = os.lstat(path)
if stat.S_ISLNK(final_status.st_mode) or not stat.S_ISDIR(final_status.st_mode):
    raise SystemExit('backup directory is not a directory')
if final_status.st_uid != os.geteuid() or final_status.st_mode & 0o077 or not os.access(path, os.W_OK | os.X_OK):
    raise SystemExit('backup directory ownership or mode is unsafe')
if os.path.realpath(path) != raw:
    raise SystemExit('backup directory is not canonical')
PY
}

measure_durable_storage() {
  local measurement storage_type storage_capacity_kib storage_used_kib storage_free_kib trailing
  if [[ "$BACKUP_DIR" == /afs/* ]]; then
    if ! measurement="$(fs lq "$BACKUP_DIR" 2>/dev/null)"; then
      printf '%s\n' 'invalid durable storage measurement: AFS quota lookup failed' >&2
      return 1
    fi
    if ! measurement="$(printf '%s' "$measurement" | python3 -I -c '
import re, sys
rows=[]
for line in sys.stdin:
    match=re.fullmatch(r"\s*\S+\s+(\d+)\s+(\d+)\s+\d+%\s+\S+\s*", line)
    if match is not None:
        rows.append(match.groups())
if len(rows) != 1:
    raise SystemExit("invalid durable storage measurement: malformed fs lq output")
quota, used = map(int, rows[0])
if quota == 0 or quota > 9223372036854775807 or used > quota:
    raise SystemExit("invalid durable storage measurement: invalid fs lq capacity or used KiB")
print(quota, used, quota - used)
')"; then
      return 1
    fi
    read -r storage_capacity_kib storage_used_kib storage_free_kib trailing <<< "$measurement"
    if test -z "${storage_capacity_kib:-}" || test -z "${storage_used_kib:-}" || test -z "${storage_free_kib:-}" || test -n "${trailing:-}"; then
      printf '%s\n' 'invalid durable storage measurement: malformed fs lq output' >&2
      return 1
    fi
    storage_type=afs
  else
    if ! measurement="$(df -Pk "$BACKUP_DIR" | python3 -I -c '
import re, sys
rows=[]
for line in sys.stdin:
    match=re.fullmatch(r"\S+\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+%\s+\S+(?:\s+.*)?\s*", line)
    if match is not None:
        rows.append(match.groups())
if len(rows) != 1:
    raise SystemExit("invalid durable storage measurement: malformed df output")
capacity, used, available = map(int, rows[0])
if capacity == 0 or capacity > 9223372036854775807 or used > capacity or available > capacity - used:
    raise SystemExit("invalid durable storage measurement: invalid df capacity, used, or available KiB")
print(capacity, used, min(capacity - used, available))
')"; then
      return 1
    fi
    read -r storage_capacity_kib storage_used_kib storage_free_kib trailing <<< "$measurement"
    if test -z "${storage_capacity_kib:-}" || test -z "${storage_used_kib:-}" || test -z "${storage_free_kib:-}" || test -n "${trailing:-}"; then
      printf '%s\n' 'invalid durable storage measurement: malformed df output' >&2
      return 1
    fi
    storage_type=df
  fi
  printf '%s %s %s %s\n' "$storage_type" "$storage_capacity_kib" "$storage_used_kib" "$storage_free_kib"
}

validate_dashboard_headroom() {
  DB_BYTES="$1" PVC_AVAILABLE_KIB="$2" STORAGE_TYPE="$3" STORAGE_CAPACITY_KIB="$4" STORAGE_USED_KIB="$5" STORAGE_FREE_KIB="$6" \
    RETAINED_ARTIFACT_SETS="$7" PVC_BACKUP_SAFETY_KIB="$PVC_BACKUP_SAFETY_KIB" \
    STORAGE_CHECKSUMS_KIB="$STORAGE_CHECKSUMS_KIB" STORAGE_RELEASE_EVIDENCE_KIB="$STORAGE_RELEASE_EVIDENCE_KIB" \
    STORAGE_SAFETY_MARGIN_KIB="$STORAGE_SAFETY_MARGIN_KIB" MAX_RELEASE_ARTIFACT_SETS="$MAX_RELEASE_ARTIFACT_SETS" \
    python3 -I - <<'PY'
import os, re, sys

maximum = 9223372036854775807
values = {}
if os.environ['STORAGE_TYPE'] not in ('afs', 'df'):
    raise SystemExit('invalid durable storage measurement: unsupported storage type')
for name in ('DB_BYTES', 'PVC_AVAILABLE_KIB', 'STORAGE_CAPACITY_KIB', 'STORAGE_USED_KIB', 'STORAGE_FREE_KIB', 'RETAINED_ARTIFACT_SETS',
             'PVC_BACKUP_SAFETY_KIB', 'STORAGE_CHECKSUMS_KIB', 'STORAGE_RELEASE_EVIDENCE_KIB',
             'STORAGE_SAFETY_MARGIN_KIB', 'MAX_RELEASE_ARTIFACT_SETS'):
    raw = os.environ[name]
    if re.fullmatch(r'(?:0|[1-9][0-9]{0,18})', raw) is None:
        raise SystemExit(f'invalid numeric headroom measurement: {name}')
    value = int(raw)
    if value > maximum:
        raise SystemExit(f'invalid numeric headroom measurement: {name}')
    values[name] = value
if values['DB_BYTES'] == 0 or values['STORAGE_CAPACITY_KIB'] == 0:
    raise SystemExit('invalid numeric headroom measurement: zero database size or durable storage capacity')
if values['STORAGE_USED_KIB'] > values['STORAGE_CAPACITY_KIB']:
    raise SystemExit('invalid numeric headroom measurement: durable storage used KiB exceeds capacity KiB')
storage_calculated_free_kib = values['STORAGE_CAPACITY_KIB'] - values['STORAGE_USED_KIB']
if values['STORAGE_FREE_KIB'] > storage_calculated_free_kib:
    raise SystemExit('invalid durable storage measurement: reported free KiB exceeds capacity minus used KiB')
if values['RETAINED_ARTIFACT_SETS'] >= values['MAX_RELEASE_ARTIFACT_SETS']:
    raise SystemExit(
        'dashboard release artifact retention cap reached; manual archive/cleanup is required; no evidence was deleted'
    )
db_kib = (values['DB_BYTES'] + 1023) // 1024
pvc_required_kib = db_kib + values['PVC_BACKUP_SAFETY_KIB']
storage_required_kib = db_kib + values['STORAGE_CHECKSUMS_KIB'] + values['STORAGE_RELEASE_EVIDENCE_KIB'] + values['STORAGE_SAFETY_MARGIN_KIB']
if any(value > maximum for value in (db_kib, pvc_required_kib, storage_calculated_free_kib, storage_required_kib)):
    raise SystemExit('invalid numeric headroom measurement: computed value exceeds supported range')
if values['PVC_AVAILABLE_KIB'] < pvc_required_kib:
    raise SystemExit('PVC backup headroom is insufficient; no production backup was started')
if values['STORAGE_FREE_KIB'] < storage_required_kib:
    raise SystemExit('durable storage release-evidence headroom is insufficient; no backup or release artifact was written')
print(
    'DASHBOARD_HEADROOM PASS '
    f"db_bytes={values['DB_BYTES']} db_kib={db_kib} "
    f"pvc_available_kib={values['PVC_AVAILABLE_KIB']} pvc_required_kib={pvc_required_kib} "
    f"storage_type={os.environ['STORAGE_TYPE']} storage_capacity_kib={values['STORAGE_CAPACITY_KIB']} storage_used_kib={values['STORAGE_USED_KIB']} "
    f"storage_free_kib={values['STORAGE_FREE_KIB']} storage_required_kib={storage_required_kib} "
    f"retained_artifact_sets={values['RETAINED_ARTIFACT_SETS']}"
)
PY
}

measure_dashboard_headroom() {
  local db_bytes pvc_available_kib retained_artifact_sets remote_measurement trailing
  remote_measurement="$(oc -n "$PROJECT" exec -i "$POD" -c web -- python - <<'PY'
import os, stat
database = '/data/comments.sqlite3'
total = 0
for path in (database, database + '-wal', database + '-shm'):
    try:
        entry = os.lstat(path)
    except FileNotFoundError:
        if path == database:
            raise SystemExit('production database is missing')
        continue
    if stat.S_ISLNK(entry.st_mode) or not stat.S_ISREG(entry.st_mode) or entry.st_size < 0:
        raise SystemExit('production SQLite live file is unsafe')
    total += entry.st_size
    if total > 9223372036854775807:
        raise SystemExit('production SQLite live footprint is too large')
if total <= 0:
    raise SystemExit('production database is empty')
available_kib = os.statvfs('/data').f_bavail * os.statvfs('/data').f_frsize // 1024
print(total, available_kib)
PY
)"
  remote_measurement="$(printf '%s' "$remote_measurement" | python3 -I -c '
import re, sys
match=re.fullmatch(r"([0-9]+) ([0-9]+)", sys.stdin.read())
if match is None:
    raise SystemExit("invalid numeric headroom measurement: malformed web-container DB/PVC output")
print(*match.groups())
')"
  read -r db_bytes pvc_available_kib <<< "$remote_measurement"
  read -r DURABLE_STORAGE_TYPE DURABLE_STORAGE_CAPACITY_KIB DURABLE_STORAGE_USED_KIB DURABLE_STORAGE_FREE_KIB trailing < <(measure_durable_storage)
  if test -z "${DURABLE_STORAGE_TYPE:-}" || test -z "${DURABLE_STORAGE_CAPACITY_KIB:-}" || test -z "${DURABLE_STORAGE_USED_KIB:-}" || test -z "${DURABLE_STORAGE_FREE_KIB:-}" || test -n "${trailing:-}"; then
    printf '%s\n' 'invalid durable storage measurement' >&2
    return 1
  fi
  retained_artifact_sets=0
  if test -d "$BACKUP_DIR"; then
    retained_artifact_sets="$(BACKUP_DIR="$BACKUP_DIR" python3 -I - <<'PY'
import os, re
from pathlib import Path
root=Path(os.environ['BACKUP_DIR'])
known=(
    r'dashboard-release-(?P<stamp>\d{8}T\d{6}Z)\.env',
    r'comments\.sqlite3\.before-dashboard-(?P<stamp>\d{8}T\d{6}Z)\.bak',
    r'comments\.sqlite3\.before-dashboard-(?P<stamp>\d{8}T\d{6}Z)\.bak\.sha256',
    r'(?:deployment|service|route)-(?:before|captured|forward)-dashboard-(?P<stamp>\d{8}T\d{6}Z)\.json',
    r'buildconfig-captured-dashboard-(?P<stamp>\d{8}T\d{6}Z)\.json',
)
operational=(
    r'deploy-dashboard-[0-9a-f]{40}\.sh',
    r'bbqc-etroc-\d{8}T\d{6}Z\.log',
)
stamps=set()
for entry in root.iterdir():
    if not entry.is_file() or entry.is_symlink():
        continue
    match=next((re.fullmatch(pattern, entry.name) for pattern in known if re.fullmatch(pattern, entry.name)), None)
    if match is not None:
        stamps.add(match['stamp'])
    elif any(re.fullmatch(pattern, entry.name) for pattern in operational):
        continue
    elif 'dashboard' in entry.name or entry.name.startswith('comments.sqlite3.before-dashboard-'):
        raise SystemExit('unknown dashboard release artifact; refusing retention estimate')
print(len(stamps))
PY
)"
  fi
  validate_dashboard_headroom "$db_bytes" "$pvc_available_kib" "$DURABLE_STORAGE_TYPE" "$DURABLE_STORAGE_CAPACITY_KIB" "$DURABLE_STORAGE_USED_KIB" "$DURABLE_STORAGE_FREE_KIB" "$retained_artifact_sets"
}

verify_context() {
  test "$(normalize_api_server "$(oc whoami --show-server)")" = "$EXPECTED_API_SERVER"
  test "$(oc whoami)" = "$EXPECTED_USER"
  test "$(oc project -q)" = "$PROJECT"
  if test -n "${DEPLOYMENT_UID:-}"; then
    test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.uid}')" = "$DEPLOYMENT_UID"
  fi
}

normalize_etroc_reviewer_users() {
  python3 -I - "$1" <<'PY'
import hashlib, re, sys
values={item.strip().lower() for item in sys.argv[1].split(',') if item.strip()}
if not values or any(re.fullmatch(r'[a-z0-9][a-z0-9._@-]{0,127}', item) is None for item in values):
    raise SystemExit('ETROC_REVIEWER_USERS must contain at least one normalized identity')
normalized=','.join(sorted(values))
print(normalized, len(values), hashlib.sha256(normalized.encode('utf-8')).hexdigest())
PY
}

validate_oauth2_proxy_topology_files() {
  local deployment_file services_file routes_file expected_proxy_image expected_mode expected_web_image
  deployment_file="$1"
  services_file="$2"
  routes_file="$3"
  expected_proxy_image="${4:-}"
  expected_mode="${5:-target}"
  expected_web_image="${6:-}"
EXPECTED_PROXY_IMAGE="$expected_proxy_image" EXPECTED_TOPOLOGY_MODE="$expected_mode" EXPECTED_WEB_IMAGE="$expected_web_image" python3 -I - "$deployment_file" "$services_file" "$routes_file" <<'PY'
import json, os, re, sys
deployment, services_source, routes_source = (json.load(open(path, encoding='utf-8')) for path in sys.argv[1:])
if deployment.get('kind') != 'Deployment':
    raise SystemExit('BBQC proxy Deployment topology is malformed')
services = services_source.get('items') if isinstance(services_source.get('items'), list) else [services_source] if services_source.get('kind') == 'Service' else None
routes = routes_source.get('items') if isinstance(routes_source.get('items'), list) else [routes_source] if routes_source.get('kind') == 'Route' else None
if services is None or routes is None:
    raise SystemExit('BBQC proxy Service or Route topology is malformed')
container_items = deployment.get('spec', {}).get('template', {}).get('spec', {}).get('containers')
if not isinstance(container_items, list) or any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in container_items):
    raise SystemExit('BBQC proxy topology containers are malformed')
containers = {item['name']: item for item in container_items}
if len(containers) != len(container_items):
    raise SystemExit('BBQC proxy topology containers are duplicated')
web, proxy = containers.get('web'), containers.get('oauth2-proxy')
if not isinstance(web, dict) or not isinstance(proxy, dict):
    raise SystemExit('BBQC proxy topology containers are incomplete')
web_env_items = web.get('env', [])
if not isinstance(web_env_items, list) or any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in web_env_items):
    raise SystemExit('web environment topology is malformed')
web_env = {item['name']: item.get('value') for item in web_env_items}
if len(web_env) != len(web_env_items) or web_env.get('HOST') != '127.0.0.1':
    raise SystemExit('web loopback topology mismatch')
app_origins = [item for item in web_env_items if item['name'] == 'APP_ORIGIN']
web_image = web.get('image')
if not isinstance(web_image, str) or re.fullmatch(r'.+@sha256:[0-9a-f]{64}', web_image) is None:
    raise SystemExit('web image is not digest pinned')
if os.environ['EXPECTED_WEB_IMAGE'] and web_image != os.environ['EXPECTED_WEB_IMAGE']:
    raise SystemExit('web image differs from live immutable image')
if proxy.get('ports') != [{'name': 'oauth', 'containerPort': 4180, 'protocol': 'TCP'}]:
    raise SystemExit('oauth2-proxy listen ports mismatch')
image = proxy.get('image')
if not isinstance(image, str) or re.fullmatch(r'.+@sha256:[0-9a-f]{64}', image) is None:
    raise SystemExit('oauth2-proxy image is not digest pinned')
if os.environ['EXPECTED_PROXY_IMAGE'] and image != os.environ['EXPECTED_PROXY_IMAGE']:
    raise SystemExit('oauth2-proxy image differs from captured reviewed digest')
legacy_args = [
    '--provider=oidc', '--http-address=0.0.0.0:4180', '--upstream=http://127.0.0.1:8080',
    '--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback', '--email-domain=*',
    '--reverse-proxy=true', '--pass-host-header=true', '--pass-user-headers=true',
    '--set-xauthrequest=true', '--skip-provider-button=true', '--cookie-secure=true',
    '--cookie-samesite=lax',
]
target_args = [
    '--provider=oidc', '--http-address=0.0.0.0:4180', '--upstream=http://127.0.0.1:8080',
    '--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback', '--email-domain=*',
    '--reverse-proxy=true', '--pass-host-header=true', '--pass-user-headers=true',
    '--skip-auth-strip-headers=false', '--skip-provider-button=true', '--cookie-secure=true',
    '--cookie-samesite=lax',
]
if proxy.get('args') not in (legacy_args, target_args):
    raise SystemExit('exact oauth2-proxy args mismatch')
expected_service = 'etl-hybrid-bbqc'
template_labels = deployment.get('spec', {}).get('template', {}).get('metadata', {}).get('labels', {})
if not isinstance(template_labels, dict) or not template_labels:
    raise SystemExit('live pod-template labels are incomplete')
selected_services = []
for service in services:
    selector = service.get('spec', {}).get('selector', {})
    ports = service.get('spec', {}).get('ports', [])
    selects_live_pod = isinstance(selector, dict) and bool(selector) and all(template_labels.get(key) == value for key, value in selector.items())
    if not selects_live_pod:
        continue
    selected_services.append(service)
    name = service.get('metadata', {}).get('name')
    if name != expected_service:
        raise SystemExit('additional Service selects live web pod')
if len(selected_services) != 1 or selected_services[0].get('metadata', {}).get('name') != expected_service:
    raise SystemExit('oauth2-proxy Service topology mismatch')
ports = selected_services[0].get('spec', {}).get('ports', [])
matching_routes = []
for route in routes:
    route_spec = route.get('spec', {})
    target = route_spec.get('to', {})
    if target.get('kind') == 'Service' and target.get('name') == expected_service:
        matching_routes.append(route)
if len(matching_routes) != 1 or matching_routes[0].get('metadata', {}).get('name') != expected_service:
    raise SystemExit('additional Route targets a Service selecting live pod')
route_spec = matching_routes[0].get('spec', {})
if route_spec.get('host') != 'etl-hybrid-bbqc.app.cern.ch':
    raise SystemExit('route host topology mismatch')
canonical_to = {'kind': 'Service', 'name': expected_service}
server_defaulted_to = {'kind': 'Service', 'name': expected_service, 'weight': 100}
if route_spec.get('to') not in (canonical_to, server_defaulted_to) or 'alternateBackends' in route_spec or route_spec.get('wildcardPolicy', 'None') != 'None' or set(route_spec) - {'host', 'to', 'port', 'tls', 'wildcardPolicy'} or route_spec.get('port') != {'targetPort': 'oauth'}:
    raise SystemExit('BBQC Route must target only the oauth2-proxy Service')
if route_spec.get('tls') != {'termination': 'edge', 'insecureEdgeTerminationPolicy': 'Redirect'}:
    raise SystemExit('BBQC Route TLS topology mismatch')
legacy = not app_origins and proxy.get('args') == legacy_args and ports == [{'name': 'oauth', 'protocol': 'TCP', 'port': 8080, 'targetPort': 'oauth'}]
target = app_origins == [{'name': 'APP_ORIGIN', 'value': 'https://etl-hybrid-bbqc.app.cern.ch'}] and proxy.get('args') == target_args and ports == [{'name': 'oauth', 'protocol': 'TCP', 'port': 4180, 'targetPort': 'oauth'}]
if legacy == target:
    raise SystemExit('BBQC proxy topology is neither exact legacy nor exact target')
mode = 'legacy' if legacy else 'target'
expected = os.environ['EXPECTED_TOPOLOGY_MODE']
if expected not in {'either', mode}:
    raise SystemExit(f'BBQC proxy topology mode mismatch: expected {expected}, got {mode}')
print(mode)
PY
}

validate_oauth2_proxy_topology() {
  local phase expected_proxy_image expected_mode expected_web_image deployment_file services_file routes_file
  phase="$1"
  expected_proxy_image="${2:-}"
  expected_mode="${3:-target}"
  expected_web_image="${4:-}"
  deployment_file="${WORK_DIR}/topology-${phase}-deployment.json"
  services_file="${WORK_DIR}/topology-${phase}-services.json"
  routes_file="${WORK_DIR}/topology-${phase}-routes.json"
  oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$deployment_file"
  oc -n "$PROJECT" get services -o json > "$services_file"
  oc -n "$PROJECT" get routes -o json > "$routes_file"
  validate_oauth2_proxy_topology_files "$deployment_file" "$services_file" "$routes_file" "$expected_proxy_image" "$expected_mode" "$expected_web_image"
}

validate_captured_oauth2_proxy_topology() {
  local deployment_file service_file route_file expected_proxy_image expected_mode expected_web_image
  deployment_file="$1"
  service_file="$2"
  route_file="$3"
  expected_proxy_image="$4"
  expected_mode="${5:-either}"
  expected_web_image="$6"
  validate_oauth2_proxy_topology_files "$deployment_file" "$service_file" "$route_file" "$expected_proxy_image" "$expected_mode" "$expected_web_image"
}

validate_manifest_topology() {
  local phase deployment_manifest service_manifest route_manifest expected_mode deployment_file service_file route_file
  phase="$1"
  deployment_manifest="$2"
  service_manifest="$3"
  route_manifest="$4"
  expected_mode="${5:-target}"
  deployment_file="${WORK_DIR}/rendered-${phase}-deployment.json"
  service_file="${WORK_DIR}/rendered-${phase}-service.json"
  route_file="${WORK_DIR}/rendered-${phase}-route.json"
  oc create --dry-run=client -o json -f "$deployment_manifest" > "$deployment_file"
  oc create --dry-run=client -o json -f "$service_manifest" > "$service_file"
  oc create --dry-run=client -o json -f "$route_manifest" > "$route_file"
  EXPECTED_TOPOLOGY_MODE="$expected_mode" python3 -I - "$deployment_file" "$service_file" "$route_file" <<'PY'
import json, os, re, sys
deployment, service, route = (json.load(open(path, encoding='utf-8')) for path in sys.argv[1:])
if [deployment.get('kind'), service.get('kind'), route.get('kind')] != ['Deployment', 'Service', 'Route']:
    raise SystemExit('unexpected canonical manifest kinds')
if any('items' in item for item in (deployment, service, route)):
    raise SystemExit('canonical manifest contains multiple objects')
name='etl-hybrid-bbqc'
if any(item.get('metadata', {}).get('name') != name for item in (deployment, service, route)):
    raise SystemExit('canonical manifest names do not match')
containers={item.get('name'): item for item in deployment.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])}
web, proxy=containers.get('web'), containers.get('oauth2-proxy')
if not isinstance(web, dict) or not isinstance(proxy, dict):
    raise SystemExit('canonical Deployment proxy topology is incomplete')
web_env_items=web.get('env', [])
if not isinstance(web_env_items, list) or any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in web_env_items):
    raise SystemExit('canonical Deployment web environment topology is malformed')
web_env={item['name']: item.get('value') for item in web_env_items}
if len(web_env) != len(web_env_items) or web_env.get('HOST') != '127.0.0.1':
    raise SystemExit('canonical Deployment web loopback topology mismatch')
app_origins=[item for item in web_env_items if item['name'] == 'APP_ORIGIN']
if proxy.get('ports') != [{'name': 'oauth', 'containerPort': 4180, 'protocol': 'TCP'}]:
    raise SystemExit('canonical Deployment oauth2-proxy listen ports mismatch')
if service.get('spec', {}).get('selector') != {'app': name}:
    raise SystemExit('canonical Service selector mismatch')
route_spec=route.get('spec', {})
if route_spec.get('host') != 'etl-hybrid-bbqc.app.cern.ch':
    raise SystemExit('canonical Route host mismatch')
canonical_to={'kind': 'Service', 'name': name}
server_defaulted_to={'kind': 'Service', 'name': name, 'weight': 100}
if route_spec.get('to') not in (canonical_to, server_defaulted_to) or 'alternateBackends' in route_spec or route_spec.get('wildcardPolicy', 'None') != 'None' or set(route_spec) - {'host', 'to', 'port', 'tls', 'wildcardPolicy'} or route_spec.get('port') != {'targetPort': 'oauth'}:
    raise SystemExit('canonical Route must target only the oauth Service port')
if route_spec.get('tls') != {'termination': 'edge', 'insecureEdgeTerminationPolicy': 'Redirect'}:
    raise SystemExit('canonical Route TLS topology mismatch')
legacy_args=['--provider=oidc','--http-address=0.0.0.0:4180','--upstream=http://127.0.0.1:8080','--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback','--email-domain=*','--reverse-proxy=true','--pass-host-header=true','--pass-user-headers=true','--set-xauthrequest=true','--skip-provider-button=true','--cookie-secure=true','--cookie-samesite=lax']
target_args=['--provider=oidc','--http-address=0.0.0.0:4180','--upstream=http://127.0.0.1:8080','--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback','--email-domain=*','--reverse-proxy=true','--pass-host-header=true','--pass-user-headers=true','--skip-auth-strip-headers=false','--skip-provider-button=true','--cookie-secure=true','--cookie-samesite=lax']
if proxy.get('args') not in (legacy_args, target_args):
    raise SystemExit('exact oauth2-proxy args mismatch')
legacy=not app_origins and proxy.get('args') == legacy_args and service.get('spec', {}).get('ports') == [{'name': 'oauth', 'protocol': 'TCP', 'port': 8080, 'targetPort': 'oauth'}]
target=app_origins == [{'name': 'APP_ORIGIN', 'value': 'https://etl-hybrid-bbqc.app.cern.ch'}] and proxy.get('args') == target_args and service.get('spec', {}).get('ports') == [{'name': 'oauth', 'protocol': 'TCP', 'port': 4180, 'targetPort': 'oauth'}]
if legacy == target:
    raise SystemExit('rendered proxy topology is neither exact legacy nor exact target')
mode='legacy' if legacy else 'target'
if os.environ['EXPECTED_TOPOLOGY_MODE'] != mode:
    raise SystemExit(f'rendered proxy topology mode mismatch: expected {os.environ["EXPECTED_TOPOLOGY_MODE"]}, got {mode}')
print(f'BBQC_RENDERED_OAUTH2_PROXY_TOPOLOGY PASS mode={mode}')
PY
}

snapshot_etroc_review_events() {
  python3 -I - "$1" <<'PY'
import json, sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='etroc_review_events'").fetchone()
    if not exists:
        print('{"present":false}')
    else:
        rows = db.execute('SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,state,note,author,author_display,created_at,mutation_id,supersedes_event_id FROM etroc_review_events ORDER BY id').fetchall()
        print(json.dumps({'present': True, 'count': len(rows), 'identity_chain': rows}, separators=(',', ':')))
PY
}

snapshot_position_review_events() {
  python3 -I - "$1" <<'PY'
import json, sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='position_review_events'").fetchone()
    if not exists:
        print('{"present":false}')
    else:
        columns = {row[1] for row in db.execute('PRAGMA table_info(position_review_events)')}
        value_field = 'label' if 'label' in columns else 'state' if 'state' in columns else None
        if value_field is None:
            raise SystemExit('unsupported position review event value field')
        rows = db.execute(f'SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,position,source_image_sha256,geometry_version,{value_field},note,author,author_display,created_at,mutation_id,supersedes_event_id FROM position_review_events ORDER BY id').fetchall()
        print(json.dumps({'present': True, 'count': len(rows), 'identity_chain': rows}, separators=(',', ':')))
PY
}

assert_etroc_snapshot() {
  ETROC_SNAPSHOT_BEFORE="$1" ETROC_SNAPSHOT_AFTER="$2" python3 -I - <<'PY'
import json, os
before=json.loads(os.environ['ETROC_SNAPSHOT_BEFORE'])
after=json.loads(os.environ['ETROC_SNAPSHOT_AFTER'])
if before == after:
    raise SystemExit(0)
if before == {'present': False} and after == {'present': True, 'count': 0, 'identity_chain': []}:
    raise SystemExit(0)
raise SystemExit('ETROC event identity chain changed')
PY
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

validate_previous_release_annotations() {
  CAPTURED_DEPLOYMENT_FILE="$CAPTURED_DEPLOYMENT_FILE" CAPTURED_BUILDCONFIG_FILE="$BUILDCONFIG_FILE" OLD_WEB_IMAGE="$OLD_WEB_IMAGE" \
    PROJECT="$PROJECT" BUILDCONFIG="$BUILDCONFIG" BUILDCONFIG_UID="$BUILDCONFIG_UID" DEPLOYMENT_UID="$DEPLOYMENT_UID" python3 -I - <<'PY'
import json, os, re, subprocess
from datetime import datetime

captured=json.load(open(os.environ['CAPTURED_DEPLOYMENT_FILE'], encoding='utf-8'))
annotations=captured.get('metadata', {}).get('annotations', {})
if not isinstance(annotations, dict):
    raise SystemExit('captured Deployment annotations are invalid')
annotations=dict(annotations)
annotations.pop('deployment.kubernetes.io/revision', None)
annotations.pop('kubectl.kubernetes.io/last-applied-configuration', None)
if not annotations:
    print('{}')
    raise SystemExit(0)
metadata=captured.get('metadata', {})
if metadata.get('uid') != os.environ['DEPLOYMENT_UID']:
    raise SystemExit('previous release Deployment UID differs from captured identity')
web_images=[item.get('image') for item in captured.get('spec', {}).get('template', {}).get('spec', {}).get('containers', []) if item.get('name') == 'web']
if web_images != [os.environ['OLD_WEB_IMAGE']]:
    raise SystemExit('previous release Deployment immutable web image differs from captured digest')
keys={
    'bbqc.cern.ch/source-revision',
    'bbqc.cern.ch/build-context-sha256',
    'bbqc.cern.ch/build-name',
    'bbqc.cern.ch/release-mode',
}
if set(annotations) != keys:
    raise SystemExit('previous release annotations contain unknown or incomplete keys')
if re.fullmatch(r'[0-9a-f]{40}', annotations['bbqc.cern.ch/source-revision']) is None:
    raise SystemExit('previous release source revision is invalid')
if re.fullmatch(r'[0-9a-f]{64}', annotations['bbqc.cern.ch/build-context-sha256']) is None:
    raise SystemExit('previous release build context digest is invalid')
if annotations['bbqc.cern.ch/release-mode'] != 'immutable-overlay':
    raise SystemExit('previous release mode is invalid')
buildconfig=os.environ['BUILDCONFIG']
match=re.fullmatch(r'build\.build\.openshift\.io/(' + re.escape(buildconfig) + r'-(0|[1-9][0-9]*))', annotations['bbqc.cern.ch/build-name'])
if match is None:
    raise SystemExit('previous release Build reference is invalid')
build_name=match.group(1)
build_number=build_name.rsplit('-', 1)[1]
old_image=os.environ['OLD_WEB_IMAGE']
old_digest=old_image.rsplit('@', 1)[1] if '@' in old_image else ''
if re.fullmatch(r'sha256:[0-9a-f]{64}', old_digest) is None:
    raise SystemExit('deployed old image digest is invalid')
result=subprocess.run(
    ['oc', '-n', os.environ['PROJECT'], 'get', 'build/' + build_name, '--ignore-not-found', '-o', 'json'],
    check=False, capture_output=True, text=True,
)
if result.returncode != 0:
    raise SystemExit('previous release Build lookup failed')
if result.stdout.strip():
    build=json.loads(result.stdout)
    metadata=build.get('metadata', {})
    status=build.get('status', {})
    if metadata.get('name') != build_name or metadata.get('namespace') != os.environ['PROJECT']:
        raise SystemExit('previous release Build identity changed')
    expected_owner=[{
        'apiVersion': 'build.openshift.io/v1',
        'controller': True,
        'kind': 'BuildConfig',
        'name': buildconfig,
        'uid': os.environ['BUILDCONFIG_UID'],
    }]
    if metadata.get('ownerReferences') != expected_owner:
        raise SystemExit('previous release Build controller ownerReference is invalid')
    if metadata.get('labels', {}).get('buildconfig') != buildconfig or metadata.get('annotations', {}).get('openshift.io/build-config.name') != buildconfig or metadata.get('annotations', {}).get('openshift.io/build.number') != build_number:
        raise SystemExit('previous release Build ownership is invalid')
    if status.get('phase') != 'Complete':
        raise SystemExit('previous release Build is not complete')
    # Required provenance contract: status.output.to.imageDigest
    build_digest=status.get('output', {}).get('to', {}).get('imageDigest')
    if re.fullmatch(r'sha256:[0-9a-f]{64}', build_digest or '') is None or build_digest != old_digest:
        raise SystemExit('previous release Build digest differs from deployed old image')
else:
    captured_buildconfig=json.load(open(os.environ['CAPTURED_BUILDCONFIG_FILE'], encoding='utf-8'))
    bc_metadata=captured_buildconfig.get('metadata', {})
    bc_spec=captured_buildconfig.get('spec', {})
    bc_status=captured_buildconfig.get('status', {})
    history_limit=bc_spec.get('successfulBuildsHistoryLimit')
    last_version=bc_status.get('lastVersion')
    if bc_metadata.get('name') != buildconfig or bc_metadata.get('namespace') != os.environ['PROJECT'] or bc_metadata.get('uid') != os.environ['BUILDCONFIG_UID']:
        raise SystemExit('captured BuildConfig identity changed during prune validation')
    if not isinstance(history_limit, int) or isinstance(history_limit, bool) or history_limit < 1 or not isinstance(last_version, int) or isinstance(last_version, bool):
        raise SystemExit('BuildConfig successful-build retention is not explicit')
    def parse_timestamp(value, label):
        if not isinstance(value, str):
            raise SystemExit(label + ' timestamp is invalid')
        try:
            parsed=datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise SystemExit(label + ' timestamp is invalid') from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise SystemExit(label + ' timestamp is invalid')
        return parsed
    buildconfig_created=parse_timestamp(bc_metadata.get('creationTimestamp'), 'BuildConfig creation')
    builds_result=subprocess.run(
        ['oc', '-n', os.environ['PROJECT'], 'get', 'builds', '-l', 'buildconfig=' + buildconfig, '-o', 'json'],
        check=False, capture_output=True, text=True,
    )
    if builds_result.returncode != 0:
        raise SystemExit('retained Build inventory lookup failed')
    retained_builds=json.loads(builds_result.stdout)
    historical_number=int(build_number)
    newer_completed=[]
    expected_retained_owner=[{
        'apiVersion': 'build.openshift.io/v1',
        'controller': True,
        'kind': 'BuildConfig',
        'name': buildconfig,
        'uid': os.environ['BUILDCONFIG_UID'],
    }]
    for retained in retained_builds.get('items', []):
        retained_metadata=retained.get('metadata', {})
        retained_status=retained.get('status', {})
        retained_annotations=retained_metadata.get('annotations', {})
        number_text=retained_annotations.get('openshift.io/build.number')
        if retained_status.get('phase') != 'Complete':
            continue
        if not isinstance(number_text, str) or re.fullmatch(r'(0|[1-9][0-9]*)', number_text) is None:
            raise SystemExit('retained successful Build number is invalid')
        number=int(number_text)
        if number <= historical_number:
            raise SystemExit('retained successful Build is not newer than historical release')
        if retained_metadata.get('name') != buildconfig + '-' + number_text or retained_metadata.get('namespace') != os.environ['PROJECT'] or retained_metadata.get('ownerReferences') != expected_retained_owner:
            raise SystemExit('retained successful Build identity or owner is invalid')
        if retained_metadata.get('labels', {}).get('buildconfig') != buildconfig or retained_annotations.get('openshift.io/build-config.name') != buildconfig:
            raise SystemExit('retained successful Build ownership is invalid')
        retained_completed=parse_timestamp(retained_status.get('completionTimestamp'), 'retained successful Build completion')
        newer_completed.append((number, retained_completed))
    newer_numbers={number for number, _completed in newer_completed}
    ordered_newer_numbers=sorted(newer_numbers)
    if (len(ordered_newer_numbers) < history_limit
            or ordered_newer_numbers != list(range(ordered_newer_numbers[0], ordered_newer_numbers[-1] + 1))
            or ordered_newer_numbers[0] <= historical_number
            or ordered_newer_numbers[-1] > last_version):
        raise SystemExit('missing previous release Build is not explained by successful-Build retention')
    isi_name=buildconfig + '@' + old_digest
    isi_result=subprocess.run(
        ['oc', '-n', os.environ['PROJECT'], 'get', 'imagestreamimage/' + isi_name, '-o', 'json'],
        check=False, capture_output=True, text=True,
    )
    if isi_result.returncode != 0:
        raise SystemExit('previous release ImageStreamImage is unavailable')
    isi=json.loads(isi_result.stdout)
    isi_metadata=isi.get('metadata', {})
    image=isi.get('image', {})
    image_metadata=image.get('metadata', {})
    image_labels=image.get('dockerImageMetadata', {}).get('Config', {}).get('Labels', {})
    required_image_labels={
        'io.openshift.build.name': build_name,
        'io.openshift.build.namespace': os.environ['PROJECT'],
    }
    openshift_build_labels={key: value for key, value in image_labels.items() if key.startswith('io.openshift.build.')}
    image_annotations=image_metadata.get('annotations', {})
    if isi_metadata.get('name') != isi_name or isi_metadata.get('namespace') != os.environ['PROJECT'] or image_metadata.get('name') != old_digest or image.get('dockerImageReference') != old_image:
        raise SystemExit('previous release ImageStreamImage identity differs from deployed old image')
    image_created=parse_timestamp(image_metadata.get('creationTimestamp'), 'previous release image creation')
    if image_created <= buildconfig_created:
        raise SystemExit('previous release image predates current BuildConfig UID')
    earliest_retained_completed=min(completed for _number, completed in newer_completed)
    if image_created >= earliest_retained_completed:
        raise SystemExit('previous release image creation is inconsistent with retained Build completion sequence')
    if openshift_build_labels != required_image_labels or image_annotations.get('openshift.io/image.managed') != 'true' or image_annotations.get('image.openshift.io/manifestBlobStored') != 'true':
        raise SystemExit('previous release ImageStreamImage provenance is invalid')
    stream_result=subprocess.run(
        ['oc', '-n', os.environ['PROJECT'], 'get', 'imagestream/' + buildconfig, '-o', 'json'],
        check=False, capture_output=True, text=True,
    )
    if stream_result.returncode != 0:
        raise SystemExit('previous release ImageStream is unavailable')
    stream=json.loads(stream_result.stdout)
    stream_metadata=stream.get('metadata', {})
    tag_items=[item for tag in stream.get('status', {}).get('tags', []) if tag.get('tag') == 'latest' for item in tag.get('items', [])]
    matching_items=[item for item in tag_items if item.get('image') == old_digest and item.get('dockerImageReference') == old_image]
    if stream_metadata.get('name') != buildconfig or stream_metadata.get('namespace') != os.environ['PROJECT'] or len(matching_items) != 1:
        raise SystemExit('previous release image is absent or duplicated in ImageStream history')
    history_created=parse_timestamp(matching_items[0].get('created'), 'ImageStream history creation')
    if history_created != image_created:
        raise SystemExit('ImageStream history creation differs from immutable image metadata')
print(json.dumps(annotations, sort_keys=True, separators=(',', ':')))
PY
}

render_forward_object() {
  local kind="$1" baseline_file="$2" captured_file="$3" forward_file="$4"
  RELEASE_KIND="$kind" BASELINE_OBJECT_FILE="$baseline_file" CAPTURED_OBJECT_FILE="$captured_file" \
    NEW_WEB_IMAGE="$NEW_WEB_IMAGE" OLD_WEB_IMAGE="$OLD_WEB_IMAGE" OLD_PROXY_IMAGE="$OLD_PROXY_IMAGE" \
    OLD_TOPOLOGY_MODE="$OLD_TOPOLOGY_MODE" OLD_RELEASE_ANNOTATIONS_JSON="$OLD_RELEASE_ANNOTATIONS_JSON" \
    SOURCE_REVISION="$SOURCE_REVISION" BUILD_CONTEXT_SHA256="$BUILD_CONTEXT_SHA256" BUILD_NAME="$BUILD_NAME" \
    ETROC_REVIEWER_USERS_NORMALIZED="$ETROC_REVIEWER_USERS_NORMALIZED" python3 -I - <<'PY' > "$forward_file"
import copy, json, os, re, sys
from datetime import datetime
baseline=json.load(open(os.environ['BASELINE_OBJECT_FILE'], encoding='utf-8'))
captured=json.load(open(os.environ['CAPTURED_OBJECT_FILE'], encoding='utf-8'))
kind=os.environ['RELEASE_KIND']
validated_previous_release_annotations=json.loads(os.environ.get('OLD_RELEASE_ANNOTATIONS_JSON', '{}'))
if not isinstance(validated_previous_release_annotations, dict):
    raise SystemExit('validated previous release annotations are invalid')
if baseline.get('kind') != kind or captured.get('kind') != kind:
    raise SystemExit('baseline/captured object kind mismatch')
baseline_metadata=baseline.get('metadata', {})
captured_metadata=captured.get('metadata', {})
if baseline_metadata.get('name') != captured_metadata.get('name') or captured_metadata.get('namespace') != 'etroc-solder-inspection':
    raise SystemExit(f'captured {kind} identity differs from pinned baseline')
if baseline_metadata.get('labels', {}) != captured_metadata.get('labels', {}):
    raise SystemExit(f'captured {kind} labels differ from pinned baseline')
def normalized_annotations(metadata):
    annotations=metadata.get('annotations', {})
    if not isinstance(annotations, dict):
        raise SystemExit(f'captured {kind} annotations are invalid')
    result=copy.deepcopy(annotations)
    result.pop('kubectl.kubernetes.io/last-applied-configuration', None)
    if kind == 'Deployment':
        result.pop('deployment.kubernetes.io/revision', None)
    for key, expected_value in validated_previous_release_annotations.items():
        if key in result:
            if result[key] != expected_value:
                raise SystemExit('captured previous release annotation changed after validation')
            result.pop(key)
    return result
if kind == 'Route':
    captured_route_annotations=captured_metadata.get('annotations', {})
    whitelist_key='haproxy.router.openshift.io/ip_whitelist'
    external_dns_key='external-dns.alpha.kubernetes.io/target'
    whitelist=captured_route_annotations.get(whitelist_key)
    external_dns_target=captured_route_annotations.get(external_dns_key)
    pinned_route_annotations=baseline_metadata.get('annotations', {})
    needs_reviewed_live_delta=(
        (whitelist is not None and whitelist_key not in pinned_route_annotations)
        or (external_dns_target is not None and external_dns_key not in pinned_route_annotations)
    )
    if needs_reviewed_live_delta:
        if whitelist != '0.0.0.0/0 ::/0' or not isinstance(external_dns_target, str):
            raise SystemExit('captured Route reviewed annotations are incomplete or invalid')
        topology_mode=os.environ['OLD_TOPOLOGY_MODE']
        if topology_mode == 'legacy':
            last_applied=captured_route_annotations.get('kubectl.kubernetes.io/last-applied-configuration')
            try:
                last_applied_object=json.loads(last_applied)
            except (TypeError, ValueError):
                raise SystemExit('captured Route whitelist lacks legacy apply evidence') from None
            if last_applied_object.get('metadata', {}).get('annotations', {}).get(whitelist_key) != whitelist:
                raise SystemExit('captured Route whitelist differs from legacy apply evidence')
        elif topology_mode != 'target':
            raise SystemExit('captured topology mode is invalid')
        ingress=captured.get('status', {}).get('ingress')
        if not isinstance(ingress, list) or len(ingress) != 1:
            raise SystemExit('captured Route admitted ingress topology is invalid')
        admitted=ingress[0]
        conditions=admitted.get('conditions')
        if not isinstance(conditions, list) or len(conditions) != 1 or conditions[0].get('type') != 'Admitted' or conditions[0].get('status') != 'True':
            raise SystemExit('captured Route is not uniquely admitted')
        router_name=admitted.get('routerName')
        match=re.fullmatch(r'apps-shard-([1-9][0-9]*)', router_name or '')
        if match is None:
            raise SystemExit('captured Route admitted router name is invalid')
        shard=match.group(1)
        expected_dns_target=f'paas-apps-shard-{shard}.cern.ch'
        expected_canonical=f'router-apps-shard-{shard}.{expected_dns_target}'
        if (external_dns_target != expected_dns_target
                or admitted.get('routerCanonicalHostname') != expected_canonical
                or admitted.get('host') != captured.get('spec', {}).get('host')
                or admitted.get('wildcardPolicy') != captured.get('spec', {}).get('wildcardPolicy')):
            raise SystemExit('captured Route external DNS target differs from admitted router shard')
        baseline_metadata.setdefault('annotations', {})[whitelist_key]=whitelist
        baseline_metadata.setdefault('annotations', {})[external_dns_key]=external_dns_target
baseline_annotations=normalized_annotations(baseline_metadata)
if normalized_annotations(captured_metadata) != baseline_annotations:
    raise SystemExit(f'captured {kind} annotations differ from pinned baseline')
baseline_spec=copy.deepcopy(baseline.get('spec'))
captured_spec=copy.deepcopy(captured.get('spec'))
old_topology_mode=os.environ['OLD_TOPOLOGY_MODE']
if old_topology_mode not in {'legacy', 'target'}:
    raise SystemExit('captured topology mode is invalid')
legacy_args=[
    '--provider=oidc', '--http-address=0.0.0.0:4180', '--upstream=http://127.0.0.1:8080',
    '--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback', '--email-domain=*',
    '--reverse-proxy=true', '--pass-host-header=true', '--pass-user-headers=true',
    '--set-xauthrequest=true', '--skip-provider-button=true', '--cookie-secure=true',
    '--cookie-samesite=lax',
]
target_args=[
    '--provider=oidc', '--http-address=0.0.0.0:4180', '--upstream=http://127.0.0.1:8080',
    '--redirect-url=https://etl-hybrid-bbqc.app.cern.ch/oauth2/callback', '--email-domain=*',
    '--reverse-proxy=true', '--pass-host-header=true', '--pass-user-headers=true',
    '--skip-auth-strip-headers=false', '--skip-provider-button=true', '--cookie-secure=true',
    '--cookie-samesite=lax',
]
if kind == 'Deployment':
    baseline_template=baseline_spec.get('template', {})
    captured_template=captured_spec.get('template', {})
    baseline_pod_spec=baseline_template.get('spec', {})
    captured_pod_spec=captured_template.get('spec', {})
    baseline_containers={item.get('name'): item for item in baseline_pod_spec.get('containers', [])}
    captured_containers={item.get('name'): item for item in captured_pod_spec.get('containers', [])}
    if set(baseline_containers) != set(captured_containers) or captured_containers.get('web', {}).get('image') != os.environ['OLD_WEB_IMAGE'] or captured_containers.get('oauth2-proxy', {}).get('image') != os.environ['OLD_PROXY_IMAGE']:
        raise SystemExit('captured Deployment image identity differs from reviewed pre-release digests')

    def preserve_optional_defaults(baseline_parent, captured_parent, expected, label):
        for field, value in expected.items():
            if field not in baseline_parent and field in captured_parent:
                if captured_parent[field] != value:
                    raise SystemExit(f'captured Deployment {label} default {field} is unexpected')
                baseline_parent[field]=copy.deepcopy(value)

    preserve_optional_defaults(baseline_spec, captured_spec, {
        'progressDeadlineSeconds': 600, 'revisionHistoryLimit': 10,
    }, 'spec')
    baseline_template_metadata=baseline_template.get('metadata', {})
    captured_template_metadata=captured_template.get('metadata', {})
    if 'annotations' not in baseline_template_metadata and 'annotations' in captured_template_metadata:
        restart_annotations=captured_template_metadata['annotations']
        restarted_at=restart_annotations.get('kubectl.kubernetes.io/restartedAt') if isinstance(restart_annotations, dict) else None
        if set(restart_annotations or {}) != {'kubectl.kubernetes.io/restartedAt'} or not isinstance(restarted_at, str) or re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})', restarted_at) is None:
            raise SystemExit('captured Deployment restart annotation is invalid')
        offset_match=re.search(r'([+-])(\d{2}):(\d{2})$', restarted_at)
        if offset_match is not None and (int(offset_match.group(2)) > 23 or int(offset_match.group(3)) > 59):
            raise SystemExit('captured Deployment restart annotation is invalid')
        try:
            parsed_restarted_at=datetime.fromisoformat(restarted_at.replace('Z', '+00:00'))
        except ValueError:
            raise SystemExit('captured Deployment restart annotation is invalid') from None
        if parsed_restarted_at.tzinfo is None or parsed_restarted_at.utcoffset() is None:
            raise SystemExit('captured Deployment restart annotation is invalid')
        baseline_template.setdefault('metadata', {})['annotations']=copy.deepcopy(restart_annotations)
    preserve_optional_defaults(baseline_pod_spec, captured_pod_spec, {
        'dnsPolicy': 'ClusterFirst', 'restartPolicy': 'Always', 'schedulerName': 'default-scheduler',
        'securityContext': {}, 'terminationGracePeriodSeconds': 30,
    }, 'pod spec')
    probe_defaults={
        ('web', 'startupProbe'): {'successThreshold': 1},
        ('web', 'readinessProbe'): {'failureThreshold': 3, 'successThreshold': 1, 'timeoutSeconds': 1},
        ('web', 'livenessProbe'): {'failureThreshold': 3, 'successThreshold': 1, 'timeoutSeconds': 1},
        ('oauth2-proxy', 'readinessProbe'): {'failureThreshold': 3, 'successThreshold': 1, 'timeoutSeconds': 1},
        ('oauth2-proxy', 'livenessProbe'): {'failureThreshold': 3, 'successThreshold': 1, 'timeoutSeconds': 1},
    }
    for container_name, baseline_container in baseline_containers.items():
        captured_container=captured_containers[container_name]
        preserve_optional_defaults(baseline_container, captured_container, {
            'terminationMessagePath': '/dev/termination-log', 'terminationMessagePolicy': 'File',
        }, f'{container_name} container')
        baseline_ports=baseline_container.get('ports', [])
        captured_ports=captured_container.get('ports', [])
        if len(baseline_ports) == len(captured_ports):
            for baseline_port, captured_port in zip(baseline_ports, captured_ports):
                preserve_optional_defaults(baseline_port, captured_port, {'protocol': 'TCP'}, f'{container_name} port')
        for probe_name in ('startupProbe', 'readinessProbe', 'livenessProbe'):
            baseline_probe=baseline_container.get(probe_name)
            captured_probe=captured_container.get(probe_name)
            if isinstance(baseline_probe, dict) and isinstance(captured_probe, dict):
                if old_topology_mode == 'legacy' and container_name == 'web' and probe_name in {'readinessProbe', 'livenessProbe'} and 'timeoutSeconds' not in baseline_probe:
                    if captured_probe.get('timeoutSeconds') != 3:
                        raise SystemExit(f'captured legacy Deployment web {probe_name} timeout is not the reviewed delta')
                    captured_probe.pop('timeoutSeconds')
                preserve_optional_defaults(baseline_probe, captured_probe, probe_defaults.get((container_name, probe_name), {}), f'{container_name} {probe_name}')
                baseline_http=baseline_probe.get('httpGet')
                captured_http=captured_probe.get('httpGet')
                if isinstance(baseline_http, dict) and isinstance(captured_http, dict):
                    preserve_optional_defaults(baseline_http, captured_http, {'scheme': 'HTTP'}, f'{container_name} {probe_name} httpGet')

    captured_containers['web']['image']=baseline_containers['web']['image']
    captured_containers['oauth2-proxy']['image']=baseline_containers['oauth2-proxy']['image']
    if old_topology_mode == 'legacy':
        baseline_web=baseline_containers.get('web')
        captured_web=captured_containers.get('web')
        baseline_proxy=baseline_containers.get('oauth2-proxy')
        captured_proxy=captured_containers.get('oauth2-proxy')
        if not all(isinstance(item, dict) for item in (baseline_web, captured_web, baseline_proxy, captured_proxy)):
            raise SystemExit('captured Deployment topology containers are malformed')
        baseline_env=baseline_web.get('env')
        captured_env=captured_web.get('env')
        if not isinstance(baseline_env, list) or not isinstance(captured_env, list) or any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in baseline_env + captured_env):
            raise SystemExit('captured Deployment web environment is malformed')
        reviewed_missing_names={'COMMENTS_ADMIN_USERS', 'ETROC_REVIEWER_USERS', 'APP_ORIGIN'}
        reviewed_missing=[(index, item) for index, item in enumerate(baseline_env) if item['name'] in reviewed_missing_names]
        if len(reviewed_missing) != len(reviewed_missing_names) or {item['name'] for _index, item in reviewed_missing} != reviewed_missing_names:
            raise SystemExit('pinned Deployment reviewed target environment is incomplete or duplicated')
        if any(item['name'] in reviewed_missing_names for item in captured_env):
            raise SystemExit('captured legacy Deployment reviewed target environment is already present')
        for index, item in reviewed_missing:
            captured_env.insert(index, copy.deepcopy(item))
        if captured_proxy.get('args') != legacy_args or baseline_proxy.get('args') != target_args:
            raise SystemExit('captured legacy Deployment proxy args are not the reviewed delta')
        captured_proxy['args']=copy.deepcopy(baseline_proxy['args'])
    elif old_topology_mode == 'target':
        baseline_env=baseline_containers.get('web', {}).get('env')
        captured_env=captured_containers.get('web', {}).get('env')
        if baseline_env is None and captured_env is None:
            pass
        elif not isinstance(baseline_env, list) or not isinstance(captured_env, list):
            raise SystemExit('captured target Deployment web environment is malformed')
        else:
            def env_map(items):
                if any(not isinstance(item, dict) or not isinstance(item.get('name'), str) for item in items):
                    raise SystemExit('captured target Deployment web environment is malformed')
                mapped={item['name']: item for item in items}
                if len(mapped) != len(items):
                    raise SystemExit('captured target Deployment web environment contains duplicate names')
                return mapped
            captured_map=env_map(captured_env)
            baseline_map=env_map(baseline_env)
            if captured_map != baseline_map:
                captured_reviewer=captured_map.pop('ETROC_REVIEWER_USERS', None)
                baseline_reviewer=baseline_map.pop('ETROC_REVIEWER_USERS', None)
                requested_reviewer=os.environ['ETROC_REVIEWER_USERS_NORMALIZED']
                def normalized_reviewer(entry):
                    if not isinstance(entry, dict) or set(entry) != {'name', 'value'} or entry.get('name') != 'ETROC_REVIEWER_USERS' or not isinstance(entry.get('value'), str):
                        raise SystemExit('captured target Deployment reviewer environment is malformed')
                    values=entry['value'].split(',')
                    if not values or any(not value or value != value.strip() or value.lower() != value for value in values) or len(set(values)) != len(values):
                        raise SystemExit('captured target Deployment reviewer environment is malformed')
                    return ','.join(sorted(values))
                captured_reviewer_normalized = normalized_reviewer(captured_reviewer)
                if (captured_map != baseline_map
                        or normalized_reviewer(baseline_reviewer) != requested_reviewer
                        or captured_reviewer_normalized not in {requested_reviewer, 'ypark,ypark@cern.ch'}):
                    raise SystemExit('captured target Deployment web environment differs from pinned baseline')
                captured_env[:]=copy.deepcopy(baseline_env)
            else:
                captured_containers['web']['env']=copy.deepcopy(baseline_env)
if kind == 'Service':
    for field in ('clusterIP', 'clusterIPs', 'ipFamilies', 'ipFamilyPolicy', 'healthCheckNodePort'):
        if field in captured_spec:
            baseline_spec[field]=captured_spec[field]
    for field, expected in (('internalTrafficPolicy', 'Cluster'), ('sessionAffinity', 'None'), ('type', 'ClusterIP')):
        if field in captured_spec and field not in baseline_spec:
            if captured_spec[field] != expected:
                raise SystemExit('captured Service server default is not the reviewed value')
            baseline_spec[field]=expected
    if old_topology_mode == 'legacy':
        legacy_ports=[{'name': 'oauth', 'protocol': 'TCP', 'port': 8080, 'targetPort': 'oauth'}]
        target_ports=[{'name': 'oauth', 'protocol': 'TCP', 'port': 4180, 'targetPort': 'oauth'}]
        if captured_spec.get('ports') != legacy_ports or baseline_spec.get('ports') != target_ports:
            raise SystemExit('captured legacy Service port is not the reviewed delta')
        captured_spec['ports']=copy.deepcopy(baseline_spec['ports'])
if kind == 'Route' and baseline_spec.get('to') == {'kind': 'Service', 'name': 'etl-hybrid-bbqc'} and captured_spec.get('to') == {'kind': 'Service', 'name': 'etl-hybrid-bbqc', 'weight': 100}:
    captured_spec['to']=copy.deepcopy(baseline_spec['to'])
if kind == 'Route' and 'wildcardPolicy' not in baseline_spec and captured_spec.get('wildcardPolicy') == 'None':
    captured_spec.pop('wildcardPolicy')
if captured_spec != baseline_spec:
    raise SystemExit(f'captured {kind} spec differs from pinned baseline')
uid=captured_metadata.get('uid')
resource_version=captured_metadata.get('resourceVersion')
if not isinstance(uid, str) or not uid or not isinstance(resource_version, str) or not resource_version:
    raise SystemExit(f'captured {kind} UID/resourceVersion is incomplete')
metadata={
    'name': baseline_metadata['name'], 'namespace': captured_metadata['namespace'], 'uid': uid,
    'resourceVersion': resource_version, 'labels': copy.deepcopy(baseline_metadata.get('labels', {})),
    'annotations': {
        **baseline_annotations,
        'bbqc.cern.ch/source-revision': os.environ['SOURCE_REVISION'],
        'bbqc.cern.ch/build-context-sha256': os.environ['BUILD_CONTEXT_SHA256'],
        'bbqc.cern.ch/build-name': os.environ['BUILD_NAME'],
        'bbqc.cern.ch/release-mode': 'immutable-overlay',
    },
}
for key in ('finalizers', 'ownerReferences'):
    if key in captured_metadata:
        metadata[key]=copy.deepcopy(captured_metadata[key])
desired={'apiVersion': baseline['apiVersion'], 'kind': kind, 'metadata': metadata, 'spec': baseline_spec}
if kind == 'Deployment':
    images={'web': os.environ['NEW_WEB_IMAGE'], 'oauth2-proxy': os.environ['OLD_PROXY_IMAGE']}
    found=set()
    for container in desired['spec']['template']['spec']['containers']:
        if container['name'] in images:
            container['image']=images[container['name']]
            found.add(container['name'])
        if container['name'] == 'web':
            env=container.setdefault('env', [])
            env[:]=[entry for entry in env if entry.get('name') != 'ETROC_REVIEWER_USERS']
            env.append({'name': 'ETROC_REVIEWER_USERS', 'value': os.environ['ETROC_REVIEWER_USERS_NORMALIZED']})
    if found != set(images):
        raise SystemExit(f'forward containers do not match expected set: {sorted(found)}')
json.dump(desired, sys.stdout, indent=2, sort_keys=True)
PY
}

render_captured_rollback_object() {
  local captured_file="$1" rollback_file="$2"
  CAPTURED_OBJECT_FILE="$captured_file" ROLLBACK_OBJECT_FILE="$rollback_file" python3 -I - <<'PY'
import copy, json, os
captured=json.load(open(os.environ['CAPTURED_OBJECT_FILE'], encoding='utf-8'))
metadata=captured.get('metadata', {})
keep={key: copy.deepcopy(metadata[key]) for key in ('name','namespace','uid','labels','annotations','finalizers','ownerReferences') if key in metadata}
desired={'apiVersion': captured['apiVersion'], 'kind': captured['kind'], 'metadata': keep, 'spec': copy.deepcopy(captured['spec'])}
json.dump(desired, open(os.environ['ROLLBACK_OBJECT_FILE'], 'w', encoding='utf-8'), indent=2, sort_keys=True)
PY
}

prepare_rollback_object() {
  local captured_file="$1" forward_file="$2" current_file="$3" rendered_file="$4" expected_uid="$5" action_file="$6"
  EXPECTED_UID="$expected_uid" OLD_DEPLOYMENT_FILE="$captured_file" CAPTURED_OBJECT_FILE="$captured_file" FORWARD_OBJECT_FILE="$forward_file" \
    CURRENT_DEPLOYMENT="$current_file" ROLLBACK_DEPLOYMENT="$rendered_file" ROLLBACK_ACTION_FILE="$action_file" python3 -I - <<'PY'
import copy, json, os
old = json.load(open(os.environ.get('CAPTURED_OBJECT_FILE') or os.environ['OLD_DEPLOYMENT_FILE'], encoding='utf-8'))
forward = json.load(open(os.environ.get('FORWARD_OBJECT_FILE') or os.environ['FORWARD_DEPLOYMENT_FILE'], encoding='utf-8'))
current = json.load(open(os.environ['CURRENT_DEPLOYMENT'], encoding='utf-8'))
kind=forward.get('kind')
if kind not in {'Deployment', 'Service', 'Route'} or old.get('kind') != kind or current.get('kind') != kind:
    raise SystemExit('rollback object kind changed')
expected_uid = os.environ['EXPECTED_UID']
old_metadata, forward_metadata, current_metadata = (item.get('metadata', {}) for item in (old, forward, current))
if current_metadata.get('uid') != expected_uid:
    raise SystemExit('rollback target UID changed')
for key in ('name', 'namespace', 'uid'):
    if old_metadata.get(key) != forward_metadata.get(key) or old_metadata.get(key) != current_metadata.get(key):
        raise SystemExit('rollback target identity changed')
resource_version=current_metadata.get('resourceVersion')
if not isinstance(resource_version, str) or not resource_version:
    raise SystemExit('rollback target resourceVersion is missing')
def annotations(value):
    result=copy.deepcopy(value or {})
    result.pop('kubectl.kubernetes.io/last-applied-configuration', None)
    if kind == 'Deployment':
        result.pop('deployment.kubernetes.io/revision', None)
    return result
def release_owned(candidate, reference):
    candidate_metadata=candidate.get('metadata', {})
    reference_metadata=reference.get('metadata', {})
    return (
        candidate.get('spec') == reference.get('spec')
        and candidate_metadata.get('labels', {}) == reference_metadata.get('labels', {})
        and candidate_metadata.get('finalizers', []) == reference_metadata.get('finalizers', [])
        and candidate_metadata.get('ownerReferences', []) == reference_metadata.get('ownerReferences', [])
        and annotations(candidate_metadata.get('annotations')) == annotations(reference_metadata.get('annotations'))
    )
if release_owned(current, forward):
    desired=copy.deepcopy(old)
    desired.setdefault('metadata', {})['resourceVersion']=resource_version
    json.dump(desired, open(os.environ['ROLLBACK_DEPLOYMENT'], 'w', encoding='utf-8'), indent=2, sort_keys=True)
    action='restore'
elif release_owned(current, old):
    action='unchanged'
else:
    raise SystemExit(f'rollback current {kind} is foreign/concurrent drift; refusing rollback overwrite')
open(os.environ['ROLLBACK_ACTION_FILE'], 'w', encoding='utf-8').write(action + '\n')
PY
}

verify_rollback_object() {
  local old_file="$1" current_file="$2"
  ROLLBACK_OLD_FILE="$old_file" ROLLBACK_CURRENT_FILE="$current_file" python3 -I - <<'PY'
import copy, json, os
old=json.load(open(os.environ['ROLLBACK_OLD_FILE'], encoding='utf-8'))
current=json.load(open(os.environ['ROLLBACK_CURRENT_FILE'], encoding='utf-8'))
if old.get('kind') != current.get('kind'):
    raise SystemExit('post-rollback object kind changed')
for key in ('name', 'namespace', 'uid'):
    if old.get('metadata', {}).get(key) != current.get('metadata', {}).get(key):
        raise SystemExit('post-rollback object identity changed')
if old.get('spec') != current.get('spec') or old.get('metadata', {}).get('labels', {}) != current.get('metadata', {}).get('labels', {}):
    raise SystemExit('post-rollback captured spec or labels mismatch')
for key in ('finalizers', 'ownerReferences'):
    if old.get('metadata', {}).get(key, []) != current.get('metadata', {}).get(key, []):
        raise SystemExit(f'post-rollback captured metadata {key} mismatch')
def annotations(value, kind):
    result=copy.deepcopy(value or {})
    result.pop('kubectl.kubernetes.io/last-applied-configuration', None)
    if kind == 'Deployment':
        result.pop('deployment.kubernetes.io/revision', None)
    return result
if annotations(old.get('metadata', {}).get('annotations'), old['kind']) != annotations(current.get('metadata', {}).get('annotations'), current['kind']):
    raise SystemExit('post-rollback captured annotations mismatch')
PY
}

rollback_deployment() {
  local deployment_current service_current route_current deployment_rendered service_rendered route_rendered deployment_action service_action route_action deployment_topology service_topology route_topology pod raw_web raw_proxy web proxy rollback_failures=0
  set -Eeuo pipefail
  verify_context
  test -r "$OLD_DEPLOYMENT_FILE"
  test -r "$OLD_SERVICE_FILE"
  test -r "$OLD_ROUTE_FILE"
  test -r "$FORWARD_DEPLOYMENT_FILE"
  test -r "$FORWARD_SERVICE_FILE"
  test -r "$FORWARD_ROUTE_FILE"
  test "$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)" = "$OLD_DEPLOYMENT_SHA256"
  test "$(sha256sum "$OLD_SERVICE_FILE" | cut -d' ' -f1)" = "$OLD_SERVICE_SHA256"
  test "$(sha256sum "$OLD_ROUTE_FILE" | cut -d' ' -f1)" = "$OLD_ROUTE_SHA256"
  test "$(sha256sum "$FORWARD_DEPLOYMENT_FILE" | cut -d' ' -f1)" = "$FORWARD_DEPLOYMENT_SHA256"
  test "$(sha256sum "$FORWARD_SERVICE_FILE" | cut -d' ' -f1)" = "$FORWARD_SERVICE_SHA256"
  test "$(sha256sum "$FORWARD_ROUTE_FILE" | cut -d' ' -f1)" = "$FORWARD_ROUTE_SHA256"
  deployment_current="${WORK_DIR}/deployment-current.json"
  service_current="${WORK_DIR}/service-current.json"
  route_current="${WORK_DIR}/route-current.json"
  deployment_rendered="${WORK_DIR}/deployment-rollback.json"
  service_rendered="${WORK_DIR}/service-rollback.json"
  route_rendered="${WORK_DIR}/route-rollback.json"
  deployment_action="${WORK_DIR}/deployment-rollback.action"
  service_action="${WORK_DIR}/service-rollback.action"
  route_action="${WORK_DIR}/route-rollback.action"
  oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$deployment_current"
  oc -n "$PROJECT" get service/"$DEPLOYMENT" -o json > "$service_current"
  oc -n "$PROJECT" get route/"$DEPLOYMENT" -o json > "$route_current"
  prepare_rollback_object "$OLD_DEPLOYMENT_FILE" "$FORWARD_DEPLOYMENT_FILE" "$deployment_current" "$deployment_rendered" "$DEPLOYMENT_UID" "$deployment_action"
  prepare_rollback_object "$OLD_SERVICE_FILE" "$FORWARD_SERVICE_FILE" "$service_current" "$service_rendered" "$SERVICE_UID" "$service_action"
  prepare_rollback_object "$OLD_ROUTE_FILE" "$FORWARD_ROUTE_FILE" "$route_current" "$route_rendered" "$ROUTE_UID" "$route_action"
  deployment_topology="$OLD_DEPLOYMENT_FILE"
  service_topology="$OLD_SERVICE_FILE"
  route_topology="$OLD_ROUTE_FILE"
  if test "$(cat "$deployment_action")" = restore; then
    if ! oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$deployment_rendered" >/dev/null; then rollback_failures=$((rollback_failures + 1)); fi
    deployment_topology="$deployment_rendered"
  fi
  if test "$(cat "$service_action")" = restore; then
    if ! oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$service_rendered" >/dev/null; then rollback_failures=$((rollback_failures + 1)); fi
    service_topology="$service_rendered"
  fi
  if test "$(cat "$route_action")" = restore; then
    if ! oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$route_rendered" >/dev/null; then rollback_failures=$((rollback_failures + 1)); fi
    route_topology="$route_rendered"
  fi
  if test "$(cat "$deployment_action")" = restore; then
    if ! oc -n "$PROJECT" replace --save-config=false -f "$deployment_rendered"; then rollback_failures=$((rollback_failures + 1)); fi
    if ! oc -n "$PROJECT" rollout status deployment/"$DEPLOYMENT" --timeout=300s; then rollback_failures=$((rollback_failures + 1)); fi
  fi
  if test "$(cat "$service_action")" = restore; then
    if ! oc -n "$PROJECT" replace --save-config=false -f "$service_rendered"; then rollback_failures=$((rollback_failures + 1)); fi
  fi
  if test "$(cat "$route_action")" = restore; then
    if ! oc -n "$PROJECT" replace --save-config=false -f "$route_rendered"; then rollback_failures=$((rollback_failures + 1)); fi
  fi
  if ! validate_manifest_topology rollback "$deployment_topology" "$service_topology" "$route_topology" "$OLD_TOPOLOGY_MODE"; then rollback_failures=$((rollback_failures + 1)); fi
  if ! validate_oauth2_proxy_topology rollback "$OLD_PROXY_IMAGE" "$OLD_TOPOLOGY_MODE" "$OLD_WEB_IMAGE"; then rollback_failures=$((rollback_failures + 1)); fi
  if ! oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$deployment_current"; then rollback_failures=$((rollback_failures + 1)); fi
  if ! oc -n "$PROJECT" get service/"$DEPLOYMENT" -o json > "$service_current"; then rollback_failures=$((rollback_failures + 1)); fi
  if ! oc -n "$PROJECT" get route/"$DEPLOYMENT" -o json > "$route_current"; then rollback_failures=$((rollback_failures + 1)); fi
  if test -s "$deployment_current" && ! verify_rollback_object "$OLD_DEPLOYMENT_FILE" "$deployment_current"; then rollback_failures=$((rollback_failures + 1)); fi
  if test -s "$service_current" && ! verify_rollback_object "$OLD_SERVICE_FILE" "$service_current"; then rollback_failures=$((rollback_failures + 1)); fi
  if test -s "$route_current" && ! verify_rollback_object "$OLD_ROUTE_FILE" "$route_current"; then rollback_failures=$((rollback_failures + 1)); fi
  if test "$rollback_failures" -ne 0; then
    printf 'rollback restore failures=%s; exact old state was not proven\n' "$rollback_failures" >&2
    return 1
  fi
  pod="$(select_single_app_pod)"
  raw_web="$(oc -n "$PROJECT" get pod "$pod" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
  raw_proxy="$(oc -n "$PROJECT" get pod "$pod" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
  web="${raw_web#docker-pullable://}"
  proxy="${raw_proxy#docker-pullable://}"
  test "$web" = "$OLD_WEB_IMAGE"
  test "$proxy" = "$OLD_PROXY_IMAGE"
  comments="$(oc -n "$PROJECT" exec "$pod" -c web -- python -c "import sqlite3; print(sqlite3.connect('/data/comments.sqlite3').execute('SELECT COUNT(*) FROM comments').fetchone()[0])")"
  test "$comments" = "$BEFORE_COMMENTS"
  ETROC_EVENT_SNAPSHOT_ROLLBACK="$(oc -n "$PROJECT" exec -i "$pod" -c web -- python - <<'PY'
import json, sqlite3
with sqlite3.connect('/data/comments.sqlite3') as db:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='etroc_review_events'").fetchone()
    if not exists:
        print('{"present":false}')
    else:
        rows = db.execute('SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,state,note,author,author_display,created_at,mutation_id,supersedes_event_id FROM etroc_review_events ORDER BY id').fetchall()
        print(json.dumps({'present': True, 'count': len(rows), 'identity_chain': rows}, separators=(',', ':')))
PY
)"
  assert_etroc_snapshot "$ETROC_EVENT_SNAPSHOT_BEFORE" "$ETROC_EVENT_SNAPSHOT_ROLLBACK"
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

for command in oc curl python3 sha256sum tar fs find wc; do
  command -v "$command" >/dev/null
 done
verify_candidate_host_python
ensure_authenticated
oc project "$PROJECT" >/dev/null
verify_context

read -r ETROC_REVIEWER_USERS_NORMALIZED ETROC_REVIEWER_USERS_COUNT ETROC_REVIEWER_USERS_SHA256 < <(
  normalize_etroc_reviewer_users "$ETROC_REVIEWER_USERS"
)
[[ "$ETROC_REVIEWER_USERS_COUNT" =~ ^[1-9][0-9]*$ ]]
[[ "$ETROC_REVIEWER_USERS_SHA256" =~ ^[0-9a-f]{64}$ ]]
printf 'ETROC_REVIEWER_ALLOWLIST PASS count=%s sha256=%s\n' \
  "$ETROC_REVIEWER_USERS_COUNT" "$ETROC_REVIEWER_USERS_SHA256"

mkdir -p "$MANIFESTS_DIR"
for manifest in deployment.yaml service.yaml route.yaml; do
  download "${RAW_ROOT}/hybrid-bbqc/openshift/${manifest}" "${MANIFESTS_DIR}/${manifest}"
done
printf '%s  %s\n' "$DEPLOYMENT_MANIFEST_SHA256" "${MANIFESTS_DIR}/deployment.yaml" > "${MANIFESTS_DIR}/SHA256SUMS"
printf '%s  %s\n' "$SERVICE_MANIFEST_SHA256" "$SERVICE_MANIFEST_FILE" >> "${MANIFESTS_DIR}/SHA256SUMS"
printf '%s  %s\n' "$ROUTE_MANIFEST_SHA256" "$ROUTE_MANIFEST_FILE" >> "${MANIFESTS_DIR}/SHA256SUMS"
sha256sum -c "${MANIFESTS_DIR}/SHA256SUMS"
validate_manifest_topology source-baseline \
  "${MANIFESTS_DIR}/deployment.yaml" "$SERVICE_MANIFEST_FILE" "$ROUTE_MANIFEST_FILE"
oc create --dry-run=client -o json -f "${MANIFESTS_DIR}/deployment.yaml" > "$BASELINE_DEPLOYMENT_FILE"
oc create --dry-run=client -o json -f "$SERVICE_MANIFEST_FILE" > "$BASELINE_SERVICE_FILE"
oc create --dry-run=client -o json -f "$ROUTE_MANIFEST_FILE" > "$BASELINE_ROUTE_FILE"

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
validate_oauth2_proxy_topology preflight '' either

download "${RAW_ROOT}/hybrid-bbqc/openshift/select_single_app_pod.py" "$SELECTOR"
printf '%s  %s\n' "$SELECTOR_SHA256" "$SELECTOR" | sha256sum -c -
download "${RAW_ROOT}/hybrid-bbqc/openshift/validate_build_provenance.py" "$VALIDATOR"
printf '%s  %s\n' "$VALIDATOR_SHA256" "$VALIDATOR" | sha256sum -c -
POD="$(select_single_app_pod)"
RAW_OLD_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
OLD_WEB_IMAGE="${RAW_OLD_WEB_IMAGE#docker-pullable://}"
case "$OLD_WEB_IMAGE" in *@sha256:*) ;; *) printf '%s\n' 'Current web image is not immutable.' >&2; false;; esac
extract_previous_runtime_server
RAW_OLD_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
OLD_PROXY_IMAGE="${RAW_OLD_PROXY_IMAGE#docker-pullable://}"
case "$OLD_PROXY_IMAGE" in *@sha256:*) ;; *) printf '%s\n' 'Current proxy image is not immutable.' >&2; false;; esac
BEFORE_COMMENTS="$(oc -n "$PROJECT" exec "$POD" -c web -- python -c \
  "import sqlite3; print(sqlite3.connect('/data/comments.sqlite3').execute('SELECT COUNT(*) FROM comments').fetchone()[0])")"
[[ "$BEFORE_COMMENTS" =~ ^[0-9]+$ ]]
ETROC_EVENT_SNAPSHOT_BEFORE="$(oc -n "$PROJECT" exec -i "$POD" -c web -- python - <<'PY'
import json, sqlite3
with sqlite3.connect('/data/comments.sqlite3') as db:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='etroc_review_events'").fetchone()
    if not exists:
        print('{"present":false}')
    else:
        rows = db.execute('SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,state,note,author,author_display,created_at,mutation_id,supersedes_event_id FROM etroc_review_events ORDER BY id').fetchall()
        print(json.dumps({'present': True, 'count': len(rows), 'identity_chain': rows}, separators=(',', ':')))
PY
)"
POSITION_EVENT_SNAPSHOT_BEFORE="$(oc -n "$PROJECT" exec -i "$POD" -c web -- python - <<'PY'
import json, sqlite3
with sqlite3.connect('/data/comments.sqlite3') as db:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='position_review_events'").fetchone()
    if not exists:
        print('{"present":false}')
    else:
        columns = {row[1] for row in db.execute('PRAGMA table_info(position_review_events)')}
        value_field = 'label' if 'label' in columns else 'state' if 'state' in columns else None
        if value_field is None:
            raise SystemExit('unsupported position review event value field')
        rows = db.execute(f'SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,position,source_image_sha256,geometry_version,{value_field},note,author,author_display,created_at,mutation_id,supersedes_event_id FROM position_review_events ORDER BY id').fetchall()
        print(json.dumps({'present': True, 'count': len(rows), 'identity_chain': rows}, separators=(',', ':')))
PY
)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/data/comments.sqlite3.before-dashboard-${STAMP}.bak"
validate_backup_directory "$BACKUP_DIR"
measure_dashboard_headroom
LOCAL_BACKUP="${BACKUP_DIR}/$(basename "$BACKUP")"
RELEASE_STATE="${BACKUP_DIR}/dashboard-release-${STAMP}.env"
OLD_DEPLOYMENT_FILE="${BACKUP_DIR}/deployment-before-dashboard-${STAMP}.json"
CAPTURED_DEPLOYMENT_FILE="${BACKUP_DIR}/deployment-captured-dashboard-${STAMP}.json"
FORWARD_DEPLOYMENT_FILE="${BACKUP_DIR}/deployment-forward-dashboard-${STAMP}.json"
OLD_SERVICE_FILE="${BACKUP_DIR}/service-before-dashboard-${STAMP}.json"
CAPTURED_SERVICE_FILE="${BACKUP_DIR}/service-captured-dashboard-${STAMP}.json"
FORWARD_SERVICE_FILE="${BACKUP_DIR}/service-forward-dashboard-${STAMP}.json"
OLD_ROUTE_FILE="${BACKUP_DIR}/route-before-dashboard-${STAMP}.json"
CAPTURED_ROUTE_FILE="${BACKUP_DIR}/route-captured-dashboard-${STAMP}.json"
FORWARD_ROUTE_FILE="${BACKUP_DIR}/route-forward-dashboard-${STAMP}.json"
BUILDCONFIG_FILE="${BACKUP_DIR}/buildconfig-captured-dashboard-${STAMP}.json"
oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o json > "$CAPTURED_DEPLOYMENT_FILE"
oc -n "$PROJECT" get service/"$DEPLOYMENT" -o json > "$CAPTURED_SERVICE_FILE"
oc -n "$PROJECT" get route/"$DEPLOYMENT" -o json > "$CAPTURED_ROUTE_FILE"
oc -n "$PROJECT" get buildconfig/"$BUILDCONFIG" -o json > "$BUILDCONFIG_FILE"
CAPTURED_DEPLOYMENT_SHA256="$(sha256sum "$CAPTURED_DEPLOYMENT_FILE" | cut -d' ' -f1)"
CAPTURED_SERVICE_SHA256="$(sha256sum "$CAPTURED_SERVICE_FILE" | cut -d' ' -f1)"
CAPTURED_ROUTE_SHA256="$(sha256sum "$CAPTURED_ROUTE_FILE" | cut -d' ' -f1)"
BUILDCONFIG_SHA256="$(sha256sum "$BUILDCONFIG_FILE" | cut -d' ' -f1)"
[[ "$CAPTURED_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$CAPTURED_SERVICE_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$CAPTURED_ROUTE_SHA256" =~ ^[0-9a-f]{64}$ ]]
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
read -r SERVICE_UID SERVICE_RESOURCE_VERSION ROUTE_UID ROUTE_RESOURCE_VERSION < <(python3 -I - "$CAPTURED_SERVICE_FILE" "$CAPTURED_ROUTE_FILE" <<'PY'
import json, sys
service, route=(json.load(open(path, encoding='utf-8')) for path in sys.argv[1:])
for expected_kind, source in (('Service', service), ('Route', route)):
    metadata=source.get('metadata', {})
    if source.get('kind') != expected_kind or metadata.get('name') != 'etl-hybrid-bbqc' or metadata.get('namespace') != 'etroc-solder-inspection':
        raise SystemExit(f'captured {expected_kind} target identity changed')
    if not isinstance(metadata.get('uid'), str) or not metadata['uid'] or not isinstance(metadata.get('resourceVersion'), str) or not metadata['resourceVersion']:
        raise SystemExit(f'captured {expected_kind} UID/resourceVersion is incomplete')
    if metadata.get('deletionTimestamp') is not None:
        raise SystemExit(f'captured {expected_kind} is being deleted')
print(service['metadata']['uid'], service['metadata']['resourceVersion'], route['metadata']['uid'], route['metadata']['resourceVersion'])
PY
)
[[ "$SERVICE_UID" =~ ^[A-Za-z0-9._:-]+$ ]]
[[ "$SERVICE_RESOURCE_VERSION" =~ ^[A-Za-z0-9._:-]+$ ]]
[[ "$ROUTE_UID" =~ ^[A-Za-z0-9._:-]+$ ]]
[[ "$ROUTE_RESOURCE_VERSION" =~ ^[A-Za-z0-9._:-]+$ ]]
OLD_TOPOLOGY_MODE="$(validate_captured_oauth2_proxy_topology "$CAPTURED_DEPLOYMENT_FILE" "$CAPTURED_SERVICE_FILE" "$CAPTURED_ROUTE_FILE" "$OLD_PROXY_IMAGE" either "$OLD_WEB_IMAGE")"
case "$OLD_TOPOLOGY_MODE" in legacy|target) ;; *) printf 'Unexpected captured topology mode: %s\n' "$OLD_TOPOLOGY_MODE" >&2; false;; esac
validate_oauth2_proxy_topology captured-bind "$OLD_PROXY_IMAGE" "$OLD_TOPOLOGY_MODE" "$OLD_WEB_IMAGE" >/dev/null
test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$DEPLOYMENT_RESOURCE_VERSION"
test "$(oc -n "$PROJECT" get service/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$SERVICE_RESOURCE_VERSION"
test "$(oc -n "$PROJECT" get route/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$ROUTE_RESOURCE_VERSION"
printf 'OLD_TOPOLOGY_MODE=%s\n' "$OLD_TOPOLOGY_MODE"
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
if spec.get('successfulBuildsHistoryLimit') != 5 or spec.get('failedBuildsHistoryLimit') != 5:
    raise SystemExit('captured BuildConfig history retention differs from pinned limits')
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
OLD_RELEASE_ANNOTATIONS_JSON="$(validate_previous_release_annotations)"
printf '%s\n' 'PREVIOUS_RELEASE_PROVENANCE PASS'

render_captured_rollback_object "$CAPTURED_DEPLOYMENT_FILE" "$OLD_DEPLOYMENT_FILE"
render_captured_rollback_object "$CAPTURED_SERVICE_FILE" "$OLD_SERVICE_FILE"
render_captured_rollback_object "$CAPTURED_ROUTE_FILE" "$OLD_ROUTE_FILE"
OLD_DEPLOYMENT_SHA256="$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)"
OLD_SERVICE_SHA256="$(sha256sum "$OLD_SERVICE_FILE" | cut -d' ' -f1)"
OLD_ROUTE_SHA256="$(sha256sum "$OLD_ROUTE_FILE" | cut -d' ' -f1)"
[[ "$OLD_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$OLD_SERVICE_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$OLD_ROUTE_SHA256" =~ ^[0-9a-f]{64}$ ]]

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
BACKUP_HYBRID_SCHEMA_SHA256="$(python3 -I - "$LOCAL_BACKUP" <<'PY'
import hashlib, json, sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    rows=db.execute("SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE 'etroc_review_%' AND name NOT LIKE 'idx_etroc_review_%' AND name NOT LIKE 'position_review_%' AND name NOT LIKE 'idx_position_review_%' ORDER BY type,name,tbl_name,sql").fetchall()
print(hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest())
PY
)"
[[ "$BACKUP_HYBRID_SCHEMA_SHA256" =~ ^[0-9a-f]{64}$ ]]
BACKUP_SHA256="$(sha256sum "$LOCAL_BACKUP" | cut -d' ' -f1)"
[[ "$BACKUP_SHA256" =~ ^[0-9a-f]{64}$ ]]
printf '%s  %s\n' "$BACKUP_SHA256" "$LOCAL_BACKUP" > "${LOCAL_BACKUP}.sha256"
ETROC_EVENT_SNAPSHOT_BACKUP="$(snapshot_etroc_review_events "$LOCAL_BACKUP")"
POSITION_EVENT_SNAPSHOT_BACKUP="$(snapshot_position_review_events "$LOCAL_BACKUP")"
assert_etroc_snapshot "$ETROC_EVENT_SNAPSHOT_BEFORE" "$ETROC_EVENT_SNAPSHOT_BACKUP"
assert_etroc_snapshot "$POSITION_EVENT_SNAPSHOT_BEFORE" "$POSITION_EVENT_SNAPSHOT_BACKUP"

mkdir -p "${BUILD_CONTEXT}/hybrid-bbqc" "${BUILD_CONTEXT}/overlay" "${BUILD_CONTEXT}/runtime" "${BUILD_CONTEXT}/overlay/${ETROC_DATASET_REL}"
for file in index.html dashboard.css dashboard.js etroc-optical.css etroc-optical.js etroc-review.js etroc-results.js lgad-optical-stats.js; do
  download "${RAW_ROOT}/hybrid-bbqc/${file}" "${BUILD_CONTEXT}/overlay/${file}"
done
download "${RAW_ROOT}/hybrid-bbqc/server.py" "${BUILD_CONTEXT}/runtime/server.py"
download "${RAW_ROOT}/hybrid-bbqc/etroc_reviews.py" "${BUILD_CONTEXT}/runtime/etroc_reviews.py"
download "${RAW_ROOT}/hybrid-bbqc/etroc_position_reviews.py" "${BUILD_CONTEXT}/runtime/etroc_position_reviews.py"
DATASET_DIR="${BUILD_CONTEXT}/overlay/${ETROC_DATASET_REL}"
download "${RAW_ROOT}/hybrid-bbqc/${ETROC_DATASET_REL}/SHA256SUMS" "${DATASET_DIR}/SHA256SUMS"
printf '%s  %s\n' "$ETROC_MANIFEST_SHA256" "${DATASET_DIR}/SHA256SUMS" | sha256sum -c -
python3 -I - "${DATASET_DIR}/SHA256SUMS" <<'PY'
from pathlib import PurePosixPath
import re, sys
lines=open(sys.argv[1], encoding='ascii').read().splitlines()
if len(lines) != 181:
    raise SystemExit(f'unexpected ETROC dataset manifest cardinality: {len(lines)}')
seen=set()
for line in lines:
    if not re.fullmatch(r'[0-9a-f]{64}  (chips\.json|montages/sha256/[0-9a-f]{64}\.jpg|clean-montages/sha256/[0-9a-f]{64}\.jpg|positions/sha256/[0-9a-f]{64}\.json|heights/sha256/[0-9a-f]{64}\.json|previews/(?:W02G4|W03F7|W05E5)-[0-9]+\.jpg)', line):
        raise SystemExit(f'unsafe ETROC dataset manifest entry: {line!r}')
    relative=line[66:]
    path=PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or relative in seen:
        raise SystemExit(f'unsafe or duplicate ETROC dataset path: {relative!r}')
    seen.add(relative)
if (sum(path.startswith('montages/') for path in seen) != 36
        or sum(path.startswith('montages/sha256/') for path in seen) != 36
        or sum(path.startswith('clean-montages/sha256/') for path in seen) != 36
        or sum(path.startswith('positions/sha256/') for path in seen) != 36
        or sum(path.startswith('heights/sha256/') for path in seen) != 36
        or sum(path.startswith('previews/') for path in seen) != 36
        or 'chips.json' not in seen):
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
  printf '%s  %s\n' "$ETROC_REVIEW_JS_SHA256" etroc-review.js >> SHA256SUMS
  printf '%s  %s\n' "$ETROC_RESULTS_JS_SHA256" etroc-results.js >> SHA256SUMS
  printf '%s  %s\n' "$LGAD_STATS_JS_SHA256" lgad-optical-stats.js >> SHA256SUMS
  printf '%s  %s\n' "$ETROC_MANIFEST_SHA256" "${ETROC_DATASET_REL}/SHA256SUMS" >> SHA256SUMS
  sha256sum -c SHA256SUMS
  cd "$ETROC_DATASET_REL"
  sha256sum -c SHA256SUMS
)
(
  cd "${BUILD_CONTEXT}/runtime"
  printf '%s  %s\n' "$SERVER_PY_SHA256" server.py > SHA256SUMS
  printf '%s  %s\n' "$ETROC_REVIEWS_PY_SHA256" etroc_reviews.py >> SHA256SUMS
  printf '%s  %s\n' "$ETROC_POSITION_REVIEWS_PY_SHA256" etroc_position_reviews.py >> SHA256SUMS
  sha256sum -c SHA256SUMS
)
printf '%s\n' \
  "FROM ${OLD_WEB_IMAGE}" \
  'USER root' \
  'COPY overlay/ /app/static/' \
  'COPY runtime/ /app/static/' \
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
  -cf - -C "$BUILD_CONTEXT" hybrid-bbqc overlay runtime | sha256sum | cut -d' ' -f1)"
[[ "$BUILD_CONTEXT_SHA256" =~ ^[0-9a-f]{64}$ ]]

cp "$LOCAL_BACKUP" "$CANDIDATE_DB"
CANDIDATE_DB="$CANDIDATE_DB" CANDIDATE_HTTP_ACQUISITION_FILE="$CANDIDATE_HTTP_ACQUISITION_FILE" CANDIDATE_RUNTIME="${BUILD_CONTEXT}/runtime" CANDIDATE_STATIC_ROOT="${BUILD_CONTEXT}/overlay" BEFORE_COMMENTS="$BEFORE_COMMENTS" BACKUP_HYBRID_SCHEMA_SHA256="$BACKUP_HYBRID_SCHEMA_SHA256" "$CANDIDATE_HOST_PYTHON" -I - <<'PY'
import hashlib, json, os, sqlite3, sys, uuid
from pathlib import Path

candidate = Path(os.environ['CANDIDATE_DB'])
sys.path.insert(0, os.environ['CANDIDATE_RUNTIME'])
import etroc_position_reviews
import etroc_reviews

with sqlite3.connect(candidate) as db:
    before_comments = db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
if before_comments != int(os.environ['BEFORE_COMMENTS']):
    raise SystemExit(f'candidate comment count changed before migration: {before_comments}')
etroc_reviews.init_schema(candidate)
etroc_position_reviews.init_schema(candidate)
with sqlite3.connect(candidate) as db:
    db.execute('PRAGMA foreign_keys=ON')
    etroc_reviews.validate_schema(db)
    etroc_position_reviews.validate_schema(db)
    objects = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'etroc_review_%' OR name LIKE 'idx_etroc_review_%'")}
    position_objects = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'position_review_%' OR name LIKE 'idx_position_review_%'")}
    version = db.execute('SELECT singleton,version FROM etroc_review_schema').fetchall()
    position_version = db.execute('SELECT singleton,version FROM position_review_schema').fetchall()
    foreign_key_errors = db.execute('PRAGMA foreign_key_check').fetchall()
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    hybrid_rows=db.execute("SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE 'etroc_review_%' AND name NOT LIKE 'idx_etroc_review_%' AND name NOT LIKE 'position_review_%' AND name NOT LIKE 'idx_position_review_%' ORDER BY type,name,tbl_name,sql").fetchall()
candidate_hybrid_schema_sha256=hashlib.sha256(json.dumps(hybrid_rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
expected_objects = {
    'etroc_review_schema', 'etroc_review_events', 'idx_etroc_review_one_root',
    'idx_etroc_review_one_successor', 'idx_etroc_review_author_mutation',
    'idx_etroc_review_current_lookup', 'etroc_review_no_update',
    'etroc_review_no_delete', 'etroc_review_same_evidence_successor',
}
expected_position_objects = {
    'position_review_schema', 'position_review_events',
    'idx_position_review_one_root', 'idx_position_review_one_successor',
    'idx_position_review_author_mutation', 'idx_position_review_current_lookup',
    'position_review_no_update', 'position_review_no_delete',
    'position_review_same_evidence_successor',
}
if (objects != expected_objects or position_objects != expected_position_objects
        or version != [(1, 1)] or position_version != [(1, 2)]
        or foreign_key_errors or integrity != 'ok'):
    raise SystemExit('candidate ETROC schema/integrity verification failed')
if candidate_hybrid_schema_sha256 != os.environ['BACKUP_HYBRID_SCHEMA_SHA256']:
    raise SystemExit('existing Hybrid schema changed during ETROC migration')
etroc_reviews.init_schema(candidate)
etroc_position_reviews.init_schema(candidate)
with sqlite3.connect(candidate) as db:
    etroc_reviews.validate_schema(db)
    etroc_position_reviews.validate_schema(db)
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('candidate ETROC migration is not idempotent')
    db.execute('CREATE INDEX etroc_review_unapproved_attachment ON etroc_review_events(author)')
    try:
        etroc_reviews.validate_schema(db)
    except ValueError:
        pass
    else:
        raise SystemExit('arbitrary ETROC attached object bypassed schema validation')
    db.execute('DROP INDEX etroc_review_unapproved_attachment')
    etroc_reviews.validate_schema(db)
    etroc_position_reviews.validate_schema(db)
    db.execute('CREATE INDEX position_review_unapproved_attachment ON position_review_events(author)')
    try:
        etroc_position_reviews.validate_schema(db)
    except ValueError:
        pass
    else:
        raise SystemExit('arbitrary ETROC position attached object bypassed schema validation')
    db.execute('DROP INDEX position_review_unapproved_attachment')
    etroc_position_reviews.validate_schema(db)
evidence=etroc_reviews.load_evidence(Path(os.environ['CANDIDATE_STATIC_ROOT']))
record=evidence.by_acquisition[sorted(evidence.by_acquisition)[0]]
with sqlite3.connect(candidate) as db:
    db.execute('DROP TRIGGER etroc_review_no_delete')
    db.execute('DELETE FROM etroc_review_events WHERE acquisition_id=?', (record.acquisition_id,))
    db.execute(etroc_reviews.DDL[7])
etroc_reviews.init_schema(candidate)
with sqlite3.connect(candidate) as db:
    etroc_reviews.validate_schema(db)
    etroc_position_reviews.validate_schema(db)
    empty_history_events = db.execute('SELECT COUNT(*) FROM etroc_review_events').fetchone()[0]

event_fields=(*etroc_reviews.KEY_FIELDS, 'state', 'note', 'mutation_id')
request1={field: getattr(record, field) for field in etroc_reviews.KEY_FIELDS}
request1.update({'state': 'reviewed_no_optical_concern', 'note': 'disposable local empty-history event', 'expected_current_event_id': None, 'mutation_id': str(uuid.uuid4())})
created1=etroc_reviews.append(candidate, evidence, request1, 'candidate@cern.ch', 'candidate@cern.ch')
if created1.status != 201 or created1.payload.get('ok') is not True or created1.payload.get('idempotent_replay') is not False:
    raise SystemExit('local empty-history append response is invalid')
event1=created1.payload.get('event')
current1=created1.payload.get('current')
if not isinstance(event1, dict) or any(event1.get(field) != request1[field] for field in event_fields) or event1.get('author') != 'candidate@cern.ch' or event1.get('author_display') != 'candidate@cern.ch' or not isinstance(event1.get('created_at'), int) or event1['created_at'] <= 0 or event1.get('supersedes_event_id') is not None or not isinstance(event1.get('event_id'), int) or event1['event_id'] <= 0 or not isinstance(current1, dict) or current1.get('current_event_id') != event1['event_id']:
    raise SystemExit('local empty-history exact append readback mismatch')
history1=etroc_reviews.history(candidate, evidence, record.acquisition_id)
audit1=etroc_reviews.audit(candidate, record.acquisition_id, evidence)
audit_record_key={field: getattr(record, field) for field in etroc_reviews.KEY_FIELDS}
matching1=[chain for chain in audit1.payload.get('chains', []) if chain.get('evidence') == audit_record_key]
if history1.status != 200 or audit1.status != 200 or history1.payload.get('evidence') != record.as_dict() or history1.payload.get('current') != event1 or history1.payload.get('history') != [event1] or len(matching1) != 1 or matching1[0].get('current_event') != event1 or matching1[0].get('history') != [event1]:
    raise SystemExit('local empty-history history/audit exactness mismatch')
replay1=etroc_reviews.append(candidate, evidence, request1, 'candidate@cern.ch', 'candidate@cern.ch')
stale1=etroc_reviews.append(candidate, evidence, {**request1, 'mutation_id': str(uuid.uuid4())}, 'candidate@cern.ch', 'candidate@cern.ch')
with sqlite3.connect(candidate) as db:
    after_empty_replay_events = db.execute('SELECT COUNT(*) FROM etroc_review_events').fetchone()[0]
if replay1.status != 200 or replay1.payload.get('idempotent_replay') is not True or replay1.payload.get('event') != event1 or replay1.payload.get('current') != current1 or stale1.status != 409 or stale1.payload.get('error', {}).get('code') != 'stale_current' or after_empty_replay_events != empty_history_events + 1:
    raise SystemExit('local empty-history replay/stale conflict changed event count')

request2={field: getattr(record, field) for field in etroc_reviews.KEY_FIELDS}
request2.update({'state': 'follow_up_required', 'note': 'disposable local existing-history supersession', 'expected_current_event_id': event1['event_id'], 'mutation_id': str(uuid.uuid4())})
created2=etroc_reviews.append(candidate, evidence, request2, 'candidate@cern.ch', 'candidate@cern.ch')
if created2.status != 201 or created2.payload.get('ok') is not True or created2.payload.get('idempotent_replay') is not False:
    raise SystemExit('local existing-history supersession response is invalid')
event2=created2.payload.get('event')
current2=created2.payload.get('current')
if not isinstance(event2, dict) or any(event2.get(field) != request2[field] for field in event_fields) or event2.get('author') != 'candidate@cern.ch' or event2.get('author_display') != 'candidate@cern.ch' or not isinstance(event2.get('created_at'), int) or event2['created_at'] <= 0 or event2.get('supersedes_event_id') != event1['event_id'] or not isinstance(event2.get('event_id'), int) or event2['event_id'] <= event1['event_id'] or not isinstance(current2, dict) or current2.get('current_event_id') != event2['event_id']:
    raise SystemExit('local existing-history exact append readback mismatch')
history2=etroc_reviews.history(candidate, evidence, record.acquisition_id)
audit2=etroc_reviews.audit(candidate, record.acquisition_id, evidence)
matching2=[chain for chain in audit2.payload.get('chains', []) if chain.get('evidence') == audit_record_key]
existing_history_checks={
    'history_status': history2.status == 200,
    'audit_status': audit2.status == 200,
    'history_evidence': history2.payload.get('evidence') == record.as_dict(),
    'history_current': history2.payload.get('current') == event2,
    'history_chain': history2.payload.get('history') == [event2, event1],
    'audit_chain_count': len(matching2) == 1,
    'audit_current': len(matching2) == 1 and matching2[0].get('current_event') == event2,
    'audit_history': len(matching2) == 1 and matching2[0].get('history') == [event2, event1],
}
failed=','.join(name for name, passed in existing_history_checks.items() if not passed)
if failed:
    raise SystemExit(f'local existing-history history/audit exactness mismatch failed={failed}')
replay2=etroc_reviews.append(candidate, evidence, request2, 'candidate@cern.ch', 'candidate@cern.ch')
stale2=etroc_reviews.append(candidate, evidence, {**request2, 'mutation_id': str(uuid.uuid4())}, 'candidate@cern.ch', 'candidate@cern.ch')
with sqlite3.connect(candidate) as db:
    after_existing_replay_events = db.execute('SELECT COUNT(*) FROM etroc_review_events').fetchone()[0]
if replay2.status != 200 or replay2.payload.get('idempotent_replay') is not True or replay2.payload.get('event') != event2 or replay2.payload.get('current') != current2 or stale2.status != 409 or stale2.payload.get('error', {}).get('code') != 'stale_current' or after_existing_replay_events != empty_history_events + 2:
    raise SystemExit('local existing-history replay/stale conflict changed event count; local deterministic mutation count is not +2')

with sqlite3.connect(candidate) as db:
    db.execute('DROP TRIGGER etroc_review_no_delete')
    db.execute('DELETE FROM etroc_review_events WHERE acquisition_id=?', (record.acquisition_id,))
    db.execute(etroc_reviews.DDL[7])
etroc_reviews.init_schema(candidate)
seed_request={field: getattr(record, field) for field in etroc_reviews.KEY_FIELDS}
seed_request.update({'state': 'reviewed_no_optical_concern', 'note': 'disposable HTTP existing-history seed', 'expected_current_event_id': None, 'mutation_id': str(uuid.uuid4())})
seed=etroc_reviews.append(candidate, evidence, seed_request, 'candidate@cern.ch', 'candidate@cern.ch')
seed_event=seed.payload.get('event')
if seed.status != 201 or not isinstance(seed_event, dict) or seed_event.get('supersedes_event_id') is not None:
    raise SystemExit('candidate HTTP seed event is invalid')
Path(os.environ['CANDIDATE_HTTP_ACQUISITION_FILE']).write_text(record.acquisition_id + '\n', encoding='utf-8')
with sqlite3.connect(candidate) as db:
    if db.execute('SELECT COUNT(*) FROM comments').fetchone()[0] != before_comments:
        raise SystemExit('candidate migrated DB Hybrid comments changed during mutation verification')
    etroc_reviews.validate_schema(db)
    etroc_position_reviews.validate_schema(db)
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('candidate deterministic mutation schema/integrity verification failed')
print('CANDIDATE_ETROC_SCHEMA PASS')
PY
COMMENTS_DB="$CANDIDATE_DB" OLD_RUNTIME_SERVER="$OLD_RUNTIME_SERVER" CANDIDATE_STATIC_ROOT="${BUILD_CONTEXT}/overlay" "$CANDIDATE_HOST_PYTHON" -I - <<'PY'
import http.client, importlib.util, json, os, sys, threading, uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

source = Path(os.environ['OLD_RUNTIME_SERVER'])
sys.path.insert(0, str(source.parent))
candidate_static_root = Path(os.environ['CANDIDATE_STATIC_ROOT']).resolve()
if not candidate_static_root.is_dir() or not (candidate_static_root / 'index.html').is_file():
    raise SystemExit('candidate static root is unavailable for previous-binary compatibility')
spec = importlib.util.spec_from_file_location('previous_binary_server', source)
if spec is None or spec.loader is None:
    raise SystemExit('previous-binary comments server is unavailable')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
server.ROOT = candidate_static_root
server.init_db(static_root=candidate_static_root)
httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
thread = threading.Thread(target=httpd.serve_forever, daemon=True)
thread.start()
target = f'legacy-compat:{uuid.uuid4().hex}'
headers = {
    'Content-Type': 'application/json', 'Origin': server.APP_ORIGIN,
    server.IDENTITY_HEADER: 'ypark@cern.ch',
}
try:
    connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
    connection.request('POST', '/api/comments', body=json.dumps({'target': target, 'body': 'previous-binary comments compatibility', 'status': 'note'}), headers=headers)
    created = connection.getresponse()
    created_body = json.loads(created.read())
    connection.close()
    if created.status != 201 or created_body.get('target') != target:
        raise SystemExit('previous-binary comments write failed on additive schema')
    connection = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=10)
    connection.request('GET', f'/api/comments?target={target}', headers={server.IDENTITY_HEADER: 'ypark@cern.ch'})
    listed = connection.getresponse()
    comments = json.loads(listed.read())
    connection.close()
    if listed.status != 200 or not any(comment.get('id') == created_body.get('id') for comment in comments):
        raise SystemExit('previous-binary comments read failed on additive schema')
finally:
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)
print('CANDIDATE_LEGACY_COMMENTS_COMPAT PASS')
PY

{
  declare -p SOURCE_REVISION ETROC_DATASET_REL ETROC_MANIFEST_SHA256 API_SERVER EXPECTED_API_SERVER EXPECTED_USER PROJECT DEPLOYMENT BUILDCONFIG PVC
  declare -p DEPLOYMENT_MANIFEST_SHA256 SERVICE_MANIFEST_SHA256 ROUTE_MANIFEST_SHA256
  declare -p ETROC_REVIEWER_USERS_COUNT ETROC_REVIEWER_USERS_SHA256
  declare -p DEPLOYMENT_UID SERVICE_UID ROUTE_UID OLD_WEB_IMAGE OLD_RUNTIME_SERVER_SHA256 OLD_PROXY_IMAGE OLD_TOPOLOGY_MODE BEFORE_COMMENTS STAMP BACKUP BACKUP_DIR DURABLE_STORAGE_TYPE DURABLE_STORAGE_CAPACITY_KIB DURABLE_STORAGE_USED_KIB DURABLE_STORAGE_FREE_KIB LOCAL_BACKUP BACKUP_SHA256 BACKUP_SCHEMA_SHA256 BACKUP_HYBRID_SCHEMA_SHA256
  declare -p DEPLOYMENT_RESOURCE_VERSION SERVICE_RESOURCE_VERSION ROUTE_RESOURCE_VERSION CAPTURED_DEPLOYMENT_FILE CAPTURED_DEPLOYMENT_SHA256 CAPTURED_SERVICE_FILE CAPTURED_SERVICE_SHA256 CAPTURED_ROUTE_FILE CAPTURED_ROUTE_SHA256
  declare -p BUILDCONFIG_FILE BUILDCONFIG_SHA256 BUILDCONFIG_UID BUILDCONFIG_RESOURCE_VERSION
  declare -p OLD_DEPLOYMENT_FILE OLD_DEPLOYMENT_SHA256 OLD_SERVICE_FILE OLD_SERVICE_SHA256 OLD_ROUTE_FILE OLD_ROUTE_SHA256 FORWARD_DEPLOYMENT_FILE FORWARD_SERVICE_FILE FORWARD_ROUTE_FILE BUILD_CONTEXT_SHA256
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

CANDIDATE_PROBE_POD="${DEPLOYMENT}-candidate-startup-probe-${RANDOM}${RANDOM}"
ETROC_REVIEWER_TEST_USER="${ETROC_REVIEWER_USERS_NORMALIZED%%,*}"
if ! oc -n "$PROJECT" run "$CANDIDATE_PROBE_POD" --restart=Never --image="$NEW_WEB_IMAGE" --output=json \
  --overrides='{"spec":{"volumes":[{"name":"data","emptyDir":{}}],"containers":[{"name":"'"$CANDIDATE_PROBE_POD"'","image":"'"$NEW_WEB_IMAGE"'","command":["sleep","300"],"volumeMounts":[{"name":"data","mountPath":"/data"}],"env":[{"name":"HOST","value":"127.0.0.1"},{"name":"ETROC_REVIEWER_USERS","value":"'"$ETROC_REVIEWER_USERS_NORMALIZED"'"},{"name":"POD_UID","valueFrom":{"fieldRef":{"apiVersion":"v1","fieldPath":"metadata.uid"}}}]}]}}' \
  --command -- sleep 300 > "$CANDIDATE_PROBE_CREATE_RESPONSE"; then
  printf '%s\n' 'candidate probe creation failed; refusing same-name pod reconciliation' >&2
  false
fi
CANDIDATE_PROBE_POD_UID="$(CANDIDATE_PROBE_CREATE_RESPONSE="$CANDIDATE_PROBE_CREATE_RESPONSE" CANDIDATE_PROBE_POD="$CANDIDATE_PROBE_POD" PROJECT="$PROJECT" python3 -I - <<'PY'
import json, os, re
pod=json.load(open(os.environ['CANDIDATE_PROBE_CREATE_RESPONSE'], encoding='utf-8'))
metadata=pod.get('metadata', {})
if pod.get('apiVersion') != 'v1' or pod.get('kind') != 'Pod':
    raise SystemExit('candidate probe create response is not a Pod')
if metadata.get('name') != os.environ['CANDIDATE_PROBE_POD'] or metadata.get('namespace') != os.environ['PROJECT']:
    raise SystemExit('candidate probe create response identity mismatch')
uid=metadata.get('uid')
if not isinstance(uid, str) or re.fullmatch(r'[A-Za-z0-9._:-]+', uid) is None:
    raise SystemExit('candidate probe create response UID is invalid')
print(uid)
PY
)"
CANDIDATE_PROBE_POD_OWNED=1
CANDIDATE_PROBE_CREATE_RESPONSE="$CANDIDATE_PROBE_CREATE_RESPONSE" CANDIDATE_PROBE_POD="$CANDIDATE_PROBE_POD" PROJECT="$PROJECT" NEW_WEB_IMAGE="$NEW_WEB_IMAGE" ETROC_REVIEWER_USERS_NORMALIZED="$ETROC_REVIEWER_USERS_NORMALIZED" python3 -I - <<'PY'
import json, os
pod=json.load(open(os.environ['CANDIDATE_PROBE_CREATE_RESPONSE'], encoding='utf-8'))
metadata=pod.get('metadata', {})
spec=pod.get('spec', {})
containers=spec.get('containers')
if pod.get('apiVersion') != 'v1' or pod.get('kind') != 'Pod':
    raise SystemExit('candidate probe create response is not a Pod')
if metadata.get('name') != os.environ['CANDIDATE_PROBE_POD'] or metadata.get('namespace') != os.environ['PROJECT']:
    raise SystemExit('candidate probe create response identity mismatch')
if spec.get('restartPolicy') != 'Never' or not isinstance(containers, list) or len(containers) != 1:
    raise SystemExit('candidate probe create response spec mismatch')
container=containers[0]
expected_env=[
    {'name': 'HOST', 'value': '127.0.0.1'},
    {'name': 'ETROC_REVIEWER_USERS', 'value': os.environ['ETROC_REVIEWER_USERS_NORMALIZED']},
    {'name': 'POD_UID', 'valueFrom': {'fieldRef': {'apiVersion': 'v1', 'fieldPath': 'metadata.uid'}}},
]
if container.get('name') != os.environ['CANDIDATE_PROBE_POD'] or container.get('image') != os.environ['NEW_WEB_IMAGE'] or container.get('env') != expected_env:
    raise SystemExit('candidate probe create response container mismatch')
if container.get('command') != ['sleep', '300'] or container.get('volumeMounts') != [{'name': 'data', 'mountPath': '/data'}] or spec.get('volumes') != [{'name': 'data', 'emptyDir': {}}]:
    raise SystemExit('candidate probe create response spec mismatch')
PY
verify_candidate_probe_identity
oc -n "$PROJECT" wait --for=condition=Ready pod/"$CANDIDATE_PROBE_POD" --timeout=120s
verify_candidate_probe_identity
test "$(oc -n "$PROJECT" exec "$CANDIDATE_PROBE_POD" -- env EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID" sh -ec 'test "$POD_UID" = "$EXPECTED_POD_UID"; exec python --version' 2>&1)" = "Python 3.12.13"
verify_candidate_probe_identity
oc -n "$PROJECT" exec -i "$CANDIDATE_PROBE_POD" -- env EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID" sh -ec 'test "$POD_UID" = "$EXPECTED_POD_UID"; umask 077; cat > /data/comments.sqlite3' < "$CANDIDATE_DB"
verify_candidate_probe_identity
oc -n "$PROJECT" exec -i "$CANDIDATE_PROBE_POD" -- env EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID" sh -ec 'test "$POD_UID" = "$EXPECTED_POD_UID"; umask 077; cat > /tmp/candidate-http-acquisition-id' < "$CANDIDATE_HTTP_ACQUISITION_FILE"
verify_candidate_probe_identity
oc -n "$PROJECT" exec "$CANDIDATE_PROBE_POD" -- env EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID" sh -ec 'test "$POD_UID" = "$EXPECTED_POD_UID"; python /app/static/server.py >/tmp/candidate-entrypoint.log 2>&1 &'
for candidate_attempt in $(seq 1 24); do
  verify_candidate_probe_identity
  if oc -n "$PROJECT" exec -i "$CANDIDATE_PROBE_POD" -- env EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID" ETROC_REVIEWER_TEST_USER="$ETROC_REVIEWER_TEST_USER" CANDIDATE_HTTP_ACQUISITION_FILE=/tmp/candidate-http-acquisition-id python - <<'PY'
import hashlib, json, os, sqlite3, urllib.error, uuid
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

if os.environ.get('POD_UID') != os.environ.get('EXPECTED_POD_UID'):
    raise SystemExit('candidate probe self UID mismatch')
base='http://127.0.0.1:8080'
headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']}
def read_json(path, request_headers=headers):
    with urlopen(Request(base + path, headers=request_headers), timeout=5) as response:
        if response.status != 200 or response.headers.get('Cache-Control') != 'no-store':
            raise SystemExit('candidate review read response is invalid')
        return json.loads(response.read())

with sqlite3.connect('/data/comments.sqlite3') as db:
    before_comments=db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
    before_events=db.execute('SELECT COUNT(*) FROM etroc_review_events').fetchone()[0]
summary=read_json('/api/etroc-reviews?dataset_id=ETROC_OI_2608')
if summary.get('record_count') != 36 or not isinstance(summary.get('evidence'), dict) or len(summary['evidence']) != 36:
    raise SystemExit('candidate evidence loader did not return exact cohort')
acquisition_id=Path(os.environ['CANDIDATE_HTTP_ACQUISITION_FILE']).read_text(encoding='utf-8').strip()
if not acquisition_id or acquisition_id not in summary['evidence']:
    raise SystemExit('candidate HTTP acquisition seed is invalid')
record=summary['evidence'][acquisition_id]
with urlopen('http://127.0.0.1:8080/' + record['montage_uri'], timeout=5) as response:
    montage=response.read()
if hashlib.sha256(montage).hexdigest() != record['montage_sha256']:
    raise SystemExit('candidate served montage bytes mismatch')
before_history=read_json('/api/etroc-reviews/history?acquisition_id=' + quote(acquisition_id, safe=''))
prior_event=before_history.get('current')
prior_event_id=prior_event.get('event_id') if isinstance(prior_event, dict) else None
if before_history.get('evidence') != record or before_history.get('history') != [prior_event] or not isinstance(prior_event_id, int):
    raise SystemExit('candidate HTTP existing-history seed readback is invalid')
payload={field: record[field] for field in ('dataset_id','etroc_serial','acquisition_id','analysis_run_id','montage_sha256')}
payload.update({'state': 'follow_up_required', 'note': 'disposable candidate HTTP existing-history supersession', 'expected_current_event_id': prior_event_id, 'mutation_id': str(uuid.uuid4())})
encoded=json.dumps(payload, separators=(',', ':')).encode()
append_headers={**headers, 'Content-Type': 'application/json', 'Origin': 'https://etl-hybrid-bbqc.app.cern.ch'}
def append(body):
    try:
        with urlopen(Request(base + '/api/etroc-reviews', data=body, headers=append_headers, method='POST'), timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())

created_status, created=append(encoded)
if created_status != 201 or created.get('ok') is not True or created.get('idempotent_replay') is not False:
    raise SystemExit('candidate HTTP existing-history supersession response is invalid')
event=created.get('event')
current=created.get('current')
event_fields=('dataset_id','etroc_serial','acquisition_id','analysis_run_id','montage_sha256','state','note','mutation_id')
if not isinstance(event, dict) or any(event.get(field) != payload[field] for field in event_fields) or event.get('supersedes_event_id') != prior_event_id or not isinstance(event.get('event_id'), int) or event['event_id'] <= prior_event_id or not isinstance(event.get('author'), str) or not event['author'] or not isinstance(event.get('author_display'), str) or not event['author_display'] or not isinstance(current, dict) or current.get('current_event_id') != event['event_id']:
    raise SystemExit('candidate HTTP existing-history exact readback mismatch')
replay_status, replay=append(encoded)
if replay_status != 200 or replay.get('ok') is not True or replay.get('idempotent_replay') is not True or replay.get('event') != event or replay.get('current') != current:
    raise SystemExit('candidate idempotent replay mismatch')
stale={**payload, 'mutation_id': str(uuid.uuid4())}
stale_status, stale_response=append(json.dumps(stale, separators=(',', ':')).encode())
if stale_status != 409 or stale_response.get('error', {}).get('code') != 'stale_current':
    raise SystemExit('candidate stale_current conflict was not returned')
history=read_json('/api/etroc-reviews/history?acquisition_id=' + quote(acquisition_id, safe=''))
audit=read_json('/api/etroc-reviews/audit?acquisition_id=' + quote(acquisition_id, safe=''))
if history.get('evidence') != record or history.get('current') != event or history.get('history') != [event, prior_event]:
    raise SystemExit('candidate history/audit exactness mismatch')
matching=[chain for chain in audit.get('chains', []) if chain.get('evidence') == {field: payload[field] for field in ('dataset_id','etroc_serial','acquisition_id','analysis_run_id','montage_sha256')}]
if audit.get('acquisition_id') != acquisition_id or len(matching) != 1 or matching[0].get('current_publication') is not True or matching[0].get('current_event') != event or matching[0].get('history') != history['history']:
    raise SystemExit('candidate history/audit exactness mismatch')
with sqlite3.connect('/data/comments.sqlite3') as db:
    after_comments=db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
    after_events=db.execute('SELECT COUNT(*) FROM etroc_review_events').fetchone()[0]
if after_comments != before_comments:
    raise SystemExit('candidate Hybrid comments changed during review mutation verification')
if after_events != before_events + 1:
    raise SystemExit('candidate HTTP replay/stale conflict changed event count; candidate HTTP mutation count is not +1')
print('CANDIDATE_REVIEW_MUTATION PASS')
PY
  then
    break
  fi
  test "$candidate_attempt" -lt 24
  sleep 5
done
verify_candidate_probe_identity
grep -q 'BBQC_STARTUP_OK' <<< "$(oc -n "$PROJECT" exec "$CANDIDATE_PROBE_POD" -- env EXPECTED_POD_UID="$CANDIDATE_PROBE_POD_UID" sh -ec 'test "$POD_UID" = "$EXPECTED_POD_UID"; cat /tmp/candidate-entrypoint.log')"
cleanup_candidate_probe_pod
printf 'CANDIDATE_IMAGE_STARTUP PASS image=%s\n' "$NEW_WEB_IMAGE"

verify_context
validate_oauth2_proxy_topology pre-mutation "$OLD_PROXY_IMAGE" "$OLD_TOPOLOGY_MODE" "$OLD_WEB_IMAGE" >/dev/null
test "$(oc -n "$PROJECT" get deployment/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$DEPLOYMENT_RESOURCE_VERSION"
test "$(oc -n "$PROJECT" get service/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$SERVICE_RESOURCE_VERSION"
test "$(oc -n "$PROJECT" get route/"$DEPLOYMENT" -o jsonpath='{.metadata.resourceVersion}')" = "$ROUTE_RESOURCE_VERSION"
render_forward_object Deployment "$BASELINE_DEPLOYMENT_FILE" "$CAPTURED_DEPLOYMENT_FILE" "$FORWARD_DEPLOYMENT_FILE"
render_forward_object Service "$BASELINE_SERVICE_FILE" "$CAPTURED_SERVICE_FILE" "$FORWARD_SERVICE_FILE"
render_forward_object Route "$BASELINE_ROUTE_FILE" "$CAPTURED_ROUTE_FILE" "$FORWARD_ROUTE_FILE"
FORWARD_DEPLOYMENT_SHA256="$(sha256sum "$FORWARD_DEPLOYMENT_FILE" | cut -d' ' -f1)"
FORWARD_SERVICE_SHA256="$(sha256sum "$FORWARD_SERVICE_FILE" | cut -d' ' -f1)"
FORWARD_ROUTE_SHA256="$(sha256sum "$FORWARD_ROUTE_FILE" | cut -d' ' -f1)"
[[ "$FORWARD_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$FORWARD_SERVICE_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$FORWARD_ROUTE_SHA256" =~ ^[0-9a-f]{64}$ ]]
declare -p FORWARD_DEPLOYMENT_SHA256 FORWARD_SERVICE_SHA256 FORWARD_ROUTE_SHA256 >> "$RELEASE_STATE"
validate_manifest_topology rendered-pre-rollout \
  "$FORWARD_DEPLOYMENT_FILE" "$FORWARD_SERVICE_FILE" "$FORWARD_ROUTE_FILE"
oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$FORWARD_DEPLOYMENT_FILE" >/dev/null
oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$FORWARD_SERVICE_FILE" >/dev/null
oc -n "$PROJECT" replace --save-config=false --dry-run=server -f "$FORWARD_ROUTE_FILE" >/dev/null
ROLLOUT_MUTATED=1
oc -n "$PROJECT" replace --save-config=false -f "$FORWARD_SERVICE_FILE"
oc -n "$PROJECT" replace --save-config=false -f "$FORWARD_ROUTE_FILE"
oc -n "$PROJECT" replace --save-config=false -f "$FORWARD_DEPLOYMENT_FILE"
oc -n "$PROJECT" rollout status deployment/"$DEPLOYMENT" --timeout=300s
verify_context
validate_oauth2_proxy_topology post-rollout "$OLD_PROXY_IMAGE" target "$NEW_WEB_IMAGE" >/dev/null
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
REMOTE_ETROC_REVIEW_JS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/etroc-review.js | cut -d' ' -f1)"
REMOTE_ETROC_RESULTS_JS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/etroc-results.js | cut -d' ' -f1)"
REMOTE_LGAD_STATS_JS_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/lgad-optical-stats.js | cut -d' ' -f1)"
REMOTE_SERVER_PY_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/server.py | cut -d' ' -f1)"
REMOTE_ETROC_REVIEWS_PY_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/etroc_reviews.py | cut -d' ' -f1)"
REMOTE_ETROC_POSITION_REVIEWS_PY_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum /app/static/etroc_position_reviews.py | cut -d' ' -f1)"
REMOTE_ETROC_MANIFEST_SHA="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum "/app/static/${ETROC_DATASET_REL}/SHA256SUMS" | cut -d' ' -f1)"
test "$REMOTE_INDEX_SHA" = "$INDEX_SHA256"
test "$REMOTE_CSS_SHA" = "$CSS_SHA256"
test "$REMOTE_JS_SHA" = "$JS_SHA256"
test "$REMOTE_ETROC_CSS_SHA" = "$ETROC_CSS_SHA256"
test "$REMOTE_ETROC_JS_SHA" = "$ETROC_JS_SHA256"
test "$REMOTE_ETROC_REVIEW_JS_SHA" = "$ETROC_REVIEW_JS_SHA256"
test "$REMOTE_ETROC_RESULTS_JS_SHA" = "$ETROC_RESULTS_JS_SHA256"
test "$REMOTE_LGAD_STATS_JS_SHA" = "$LGAD_STATS_JS_SHA256"
test "$REMOTE_SERVER_PY_SHA" = "$SERVER_PY_SHA256"
test "$REMOTE_ETROC_REVIEWS_PY_SHA" = "$ETROC_REVIEWS_PY_SHA256"
test "$REMOTE_ETROC_POSITION_REVIEWS_PY_SHA" = "$ETROC_POSITION_REVIEWS_PY_SHA256"
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
if (not isinstance(records, list) or len(records) != 36
        or payload.get('position_record_count') != 9216
        or payload.get('position_review_target_count') != 82
        or payload.get('position_geometry_version') != 'etroc-grid-16x16-v1'):
    raise SystemExit('runtime ETROC dataset cardinality mismatch')
if Counter(row['wafer'] for row in records) != Counter({'W02G4': 18, 'W03F7': 9, 'W05E5': 9}):
    raise SystemExit('runtime ETROC wafer cardinality mismatch')
assets=[root / row[key] for row in records for key in ('montage_uri','preview_uri','clean_montage_uri','position_publication_uri','height_publication_uri')]
if len(set(assets)) != 180 or any(not path.is_file() or path.stat().st_size == 0 for path in assets):
    raise SystemExit('runtime ETROC asset inventory mismatch')
print({'dataset_id': payload['dataset_id'], 'records': len(records), 'assets': len(assets), 'positions': payload['position_record_count']})
PY

CHIPS_PUBLICATION_SHA256="$(oc -n "$PROJECT" exec "$POD" -c web -- sha256sum "/app/static/${ETROC_DATASET_REL}/chips.json" | cut -d' ' -f1)"
[[ "$CHIPS_PUBLICATION_SHA256" =~ ^[0-9a-f]{64}$ ]]
oc -n "$PROJECT" exec -i "$POD" -c web -- env \
  ETROC_DATASET_REL="$ETROC_DATASET_REL" CHIPS_PUBLICATION_SHA256="$CHIPS_PUBLICATION_SHA256" python - <<'PY'
import hashlib, json, os, urllib.error
from pathlib import Path, PurePosixPath
root=Path('/app/static') / os.environ['ETROC_DATASET_REL']
payload=json.loads((root / 'chips.json').read_text(encoding='utf-8'))
if hashlib.sha256((root / 'chips.json').read_bytes()).hexdigest() != os.environ['CHIPS_PUBLICATION_SHA256']:
    raise SystemExit('runtime chips.json publication hash mismatch')
records=payload.get('records')
dataset_id=payload.get('dataset_id')
if not isinstance(records, list) or len(records) != 36:
    raise SystemExit('runtime ETROC review evidence cardinality mismatch')
evidence={}
keys=set()
for record in records:
    acquisition_id=record.get('acquisition_id')
    key=(dataset_id,) + tuple(record.get(field) for field in ('etroc_serial','acquisition_id','analysis_run_id','montage_sha256'))
    if acquisition_id in evidence:
        raise SystemExit('duplicate ETROC acquisition_id')
    if key in keys or not all(isinstance(value, str) and value for value in key):
        raise SystemExit('duplicate canonical ETROC evidence key')
    keys.add(key)
    montage_sha256=record['montage_sha256']
    uri=record.get('montage_uri')
    path=PurePosixPath(uri) if isinstance(uri, str) else None
    if path is None or path.parts[:2] != ('montages', 'sha256') or path.name != f'{montage_sha256}.jpg':
        raise SystemExit('runtime content-addressed montage URI mismatch')
    path_digest=path.stem
    if path_digest != montage_sha256:
        raise SystemExit('runtime content-addressed montage digest mismatch')
    montage_path=root / path
    if not montage_path.is_file() or hashlib.sha256(montage_path.read_bytes()).hexdigest() != montage_sha256:
        raise SystemExit('runtime content-addressed montage bytes mismatch')
    evidence[acquisition_id]=key
if len(evidence) != 36:
    raise SystemExit('runtime ETROC review evidence map cardinality mismatch')
print({'publication_sha256': os.environ['CHIPS_PUBLICATION_SHA256'], 'evidence': len(evidence)})
PY

oc -n "$PROJECT" exec -i "$POD" -c web -- env \
  INDEX_SHA256="$INDEX_SHA256" ETROC_CSS_SHA256="$ETROC_CSS_SHA256" \
  ETROC_JS_SHA256="$ETROC_JS_SHA256" ETROC_REVIEW_JS_SHA256="$ETROC_REVIEW_JS_SHA256" \
  ETROC_RESULTS_JS_SHA256="$ETROC_RESULTS_JS_SHA256" \
  LGAD_STATS_JS_SHA256="$LGAD_STATS_JS_SHA256" python - <<'PY'
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
    ('etroc-review.js', os.environ['ETROC_REVIEW_JS_SHA256']),
    ('etroc-results.js', os.environ['ETROC_RESULTS_JS_SHA256']),
    ('lgad-optical-stats.js', os.environ['LGAD_STATS_JS_SHA256']),
):
    actual = hashlib.sha256(fetch(path)).hexdigest()
    if actual != expected_sha256:
        raise SystemExit(f'runtime HTTP asset checksum mismatch: {path} {actual}')

chips_path = 'data/etroc-optical/ETROC_OI_2608/chips.json'
payload = json.loads(fetch(chips_path))
if payload.get('dataset_id') != 'ETROC_OI_2608' or len(payload.get('records', [])) != 36:
    raise SystemExit('runtime HTTP ETROC payload identity/cardinality mismatch')

record = payload['records'][0]
dataset_root = 'data/etroc-optical/ETROC_OI_2608'
for path in (f"{dataset_root}/{record['preview_uri']}", f"{dataset_root}/{record['montage_uri']}", f"{dataset_root}/{record['clean_montage_uri']}"):
    image = fetch(path)
    if not image.startswith(b'\xff\xd8') or not image.endswith(b'\xff\xd9'):
        raise SystemExit(f'runtime HTTP JPEG contract failed: {path}')
position_publication=fetch(f"{dataset_root}/{record['position_publication_uri']}")
if hashlib.sha256(position_publication).hexdigest() != record['position_publication_sha256'] or len(json.loads(position_publication).get('positions', [])) != 256:
    raise SystemExit('runtime HTTP position publication contract failed')
height_publication=fetch(f"{dataset_root}/{record['height_publication_uri']}")
height_document=json.loads(height_publication)
if (hashlib.sha256(height_publication).hexdigest() != record['height_publication_sha256']
        or len(height_document.get('measurements', [])) != 256 or height_document.get('height_contract', {}).get('unit') != 'mm'):
    raise SystemExit('runtime HTTP height publication contract failed')
if not record['montage_uri'].startswith('montages/sha256/'):
    raise SystemExit('runtime HTTP content-addressed montage URI mismatch')
montage = fetch(f"{dataset_root}/{record['montage_uri']}")
if hashlib.sha256(montage).hexdigest() != record['montage_sha256']:
    raise SystemExit('runtime HTTP montage bytes mismatch')

print(f"RUNTIME_HTTP_ASSETS PASS dataset_id={payload['dataset_id']} records={len(payload['records'])}")
PY

ETROC_REVIEWER_TEST_USER="${ETROC_REVIEWER_USERS_NORMALIZED%%,*}"
oc -n "$PROJECT" exec -i "$POD" -c web -- env ETROC_REVIEWER_USERS="$ETROC_REVIEWER_USERS_NORMALIZED" \
  CHIPS_PUBLICATION_SHA256="$CHIPS_PUBLICATION_SHA256" \
  ETROC_REVIEWER_TEST_USER="$ETROC_REVIEWER_TEST_USER" python - <<'PY'
import hashlib, json, os
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import urllib.request
base='http://127.0.0.1:8080/'
request=urllib.request.Request(
    base + '/api/etroc-reviews?dataset_id=ETROC_OI_2608',
    headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']},
)
with urllib.request.urlopen(request, timeout=10) as response:
    if response.status != 200 or response.headers.get('Cache-Control') != 'no-store':
        raise SystemExit('ETROC review runtime response headers/status mismatch')
    summary=json.loads(response.read())
evidence=summary.get('evidence')
if summary.get('dataset_id') != 'ETROC_OI_2608' or summary.get('record_count') != 36:
    raise SystemExit('ETROC review runtime dataset/cardinality mismatch')
if summary.get('publication_sha256') != os.environ['CHIPS_PUBLICATION_SHA256']:
    raise SystemExit('ETROC review runtime publication hash mismatch')
if not isinstance(evidence, dict) or len(evidence) != 36:
    raise SystemExit('ETROC review runtime evidence map mismatch')
root=Path('/app/static/data/etroc-optical/ETROC_OI_2608')
raw=(root / 'chips.json').read_bytes()
if hashlib.sha256(raw).hexdigest() != os.environ['CHIPS_PUBLICATION_SHA256']:
    raise SystemExit('locally validated publication hash mismatch')
publication=json.loads(raw)
publication_dataset_id=publication.get('dataset_id')
expected_evidence={}
for record in publication.get('records', []):
    key=record.get('acquisition_id')
    digest=record.get('montage_sha256')
    uri=record.get('montage_uri')
    path=PurePosixPath(uri) if isinstance(uri, str) else None
    if not isinstance(key, str) or not isinstance(digest, str) or path is None or path != PurePosixPath('montages/sha256') / f'{digest}.jpg':
        raise SystemExit('locally validated publication evidence is invalid')
    expected_evidence[key]={
        'dataset_id': publication_dataset_id,
        **{field: record.get(field) for field in ('etroc_serial','acquisition_id','analysis_run_id','montage_sha256')},
    }
    expected_evidence[key]['montage_uri']=(PurePosixPath('data/etroc-optical/ETROC_OI_2608') / path).as_posix()
if len(expected_evidence) != 36:
    raise SystemExit('locally validated publication evidence cardinality mismatch')
if set(evidence) != set(expected_evidence):
    raise SystemExit('API evidence keyset mismatch')
for acquisition_id, expected in expected_evidence.items():
    actual=evidence.get(acquisition_id)
    if actual != expected:
        raise SystemExit('API evidence identity/URI mismatch')
acquisition_id=sorted(expected_evidence)[0]
history_request=urllib.request.Request(
    base + '/api/etroc-reviews/history?acquisition_id=' + quote(acquisition_id, safe=''),
    headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']},
)
with urllib.request.urlopen(history_request, timeout=10) as response:
    if response.status != 200 or response.headers.get('Cache-Control') != 'no-store':
        raise SystemExit('ETROC review history runtime response headers/status mismatch')
    history=json.loads(response.read())
audit_request=urllib.request.Request(
    base + '/api/etroc-reviews/audit?acquisition_id=' + quote(acquisition_id, safe=''),
    headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']},
)
try:
    with urllib.request.urlopen(audit_request, timeout=10) as response:
        if response.status != 200 or response.headers.get('Cache-Control') != 'no-store':
            raise SystemExit('ETROC review audit runtime response headers/status mismatch')
        audit=json.loads(response.read())
except urllib.error.HTTPError as error:
    if error.code != 404 or json.loads(error.read()).get('error', {}).get('code') != 'audit_not_found':
        raise
    audit={'acquisition_id': acquisition_id, 'chains': []}
if history.get('evidence') != expected_evidence[acquisition_id] or not isinstance(history.get('history'), list) or not isinstance(history.get('current'), (dict, type(None))) or audit.get('acquisition_id') != acquisition_id or not isinstance(audit.get('chains'), list):
    raise SystemExit('ETROC review history/audit read-only schema mismatch')
if summary.get('viewer', {}).get('can_append_review') is not True:
    raise SystemExit('internal proxy-derived allowlisted identity was not accepted')
print(f"ETROC_REVIEW_RUNTIME_CONTRACT PASS records={len(evidence)}")
PY

oc -n "$PROJECT" exec -i "$POD" -c web -- env ETROC_REVIEWER_TEST_USER="$ETROC_REVIEWER_TEST_USER" python - <<'PY'
import json, os, urllib.parse, urllib.request
from pathlib import Path
publication=json.loads(Path('/app/static/data/etroc-optical/ETROC_OI_2608/chips.json').read_text(encoding='utf-8'))
record=next(item for item in publication['records'] if item['position_review_target_count'] > 0)
url='http://127.0.0.1:8080/api/etroc-position-reviews?dataset_id=ETROC_OI_2608&acquisition_id=' + urllib.parse.quote(record['acquisition_id'], safe='')
request=urllib.request.Request(url, headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']})
with urllib.request.urlopen(request, timeout=10) as response:
    if response.status != 200 or response.headers.get('Cache-Control') != 'no-store':
        raise SystemExit('ETROC position review runtime response mismatch')
    summary=json.loads(response.read())
if (summary.get('position_count') != 256 or summary.get('target_count') != record['position_review_target_count']
        or summary.get('position_publication_sha256') != record['position_publication_sha256']
        or summary.get('height_publication_sha256') != record['height_publication_sha256']
        or len(summary.get('height_evidence', {})) != 256
        or summary.get('reviewed_target_count') != len(summary.get('reviews', {}))
        or summary.get('completion_status') not in {'review_pending','review_complete'}
        or len(summary.get('evidence', {})) != 256 or not isinstance(summary.get('reviews'), dict)):
    raise SystemExit('ETROC position review runtime evidence mismatch')
print(f"ETROC_POSITION_REVIEW_RUNTIME_CONTRACT PASS positions={len(summary['evidence'])} targets={summary['target_count']}")
completion_url='http://127.0.0.1:8080/api/etroc-position-reviews/completion?dataset_id=ETROC_OI_2608'
completion_request=urllib.request.Request(completion_url, headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']})
with urllib.request.urlopen(completion_request, timeout=10) as response:
    completion=json.loads(response.read())
if (completion.get('record_count') != 36 or completion.get('target_count') != 82
        or len(completion.get('completion', {})) != 36
        or completion['completion'].get(record['acquisition_id'], {}).get('reviewed_target_count') != summary['reviewed_target_count']
        or completion['completion'].get(record['acquisition_id'], {}).get('status') != summary['completion_status']):
    raise SystemExit('ETROC completion runtime evidence mismatch')
print(f"ETROC_COMPLETION_RUNTIME_CONTRACT PASS records={completion['record_count']} reviewed_targets={completion['reviewed_target_count']}")
results_url='http://127.0.0.1:8080/api/etroc-position-reviews/results?dataset_id=ETROC_OI_2608'
results_request=urllib.request.Request(results_url, headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']})
with urllib.request.urlopen(results_request, timeout=10) as response:
    if response.status != 200 or response.headers.get('Cache-Control') != 'no-store':
        raise SystemExit('ETROC results runtime response mismatch')
    results=json.loads(response.read())
expected_ids={item['acquisition_id'] for item in publication['records']}
if (results.get('record_count') != 36 or results.get('position_count') != 9216
        or results.get('target_count') != 82
        or set(results.get('results', {})) != expected_ids
        or results.get('reviewed_target_count') != completion['reviewed_target_count']):
    raise SystemExit('ETROC results runtime cohort mismatch')
for item in publication['records']:
    result=results['results'][item['acquisition_id']]
    if (len(result.get('algorithm_labels', [])) != 256
            or result.get('position_publication_sha256') != item['position_publication_sha256']
            or result.get('target_count') != item['position_review_target_count']
            or len(result.get('human_labels', {})) != result.get('reviewed_target_count')
            or result.get('algorithm_labels', []).count('NEED_INSPECT') != result.get('target_count')
            or any(label not in {'GREEN','BLUE','YELLOW','RED','NEED_INSPECT'} for label in result.get('algorithm_labels', []))
            or any(label.get('label') not in {'GREEN','BLUE','YELLOW','RED'} for label in result.get('human_labels', {}).values())):
        raise SystemExit('ETROC results runtime evidence mismatch')
print(f"ETROC_RESULTS_RUNTIME_CONTRACT PASS records={results['record_count']} positions={results['position_count']}")
PY

oc -n "$PROJECT" exec -i "$POD" -c web -- env BEFORE_COMMENTS="$BEFORE_COMMENTS" BACKUP_SCHEMA_SHA256="$BACKUP_SCHEMA_SHA256" BACKUP_HYBRID_SCHEMA_SHA256="$BACKUP_HYBRID_SCHEMA_SHA256" python - <<'PY'
import hashlib, json, os, sqlite3, sys
sys.path.insert(0, '/app/static')
import etroc_position_reviews
import etroc_reviews
with sqlite3.connect('/data/comments.sqlite3') as db:
    db.execute('PRAGMA foreign_keys=ON')
    schema_rows = db.execute("SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name,tbl_name,sql").fetchall()
    hybrid_rows = db.execute("SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE 'etroc_review_%' AND name NOT LIKE 'idx_etroc_review_%' AND name NOT LIKE 'position_review_%' AND name NOT LIKE 'idx_position_review_%' ORDER BY type,name,tbl_name,sql").fetchall()
    comments = db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
    foreign_key_errors = db.execute('PRAGMA foreign_key_check').fetchall()
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    attached_objects = db.execute("SELECT type,name,tbl_name FROM sqlite_master WHERE name IN ('etroc_review_schema','etroc_review_events') OR tbl_name IN ('etroc_review_schema','etroc_review_events') ORDER BY type,name").fetchall()
    position_attached_objects = db.execute("SELECT type,name,tbl_name FROM sqlite_master WHERE name IN ('position_review_schema','position_review_events') OR tbl_name IN ('position_review_schema','position_review_events') ORDER BY type,name").fetchall()
    review_objects = {row[1] for row in attached_objects}
    position_review_objects = {row[1] for row in position_attached_objects}
    review_version = db.execute('SELECT singleton,version FROM etroc_review_schema').fetchall()
    position_review_version = db.execute('SELECT singleton,version FROM position_review_schema').fetchall()
    columns = [(row[1], row[2].upper(), row[3]) for row in db.execute('PRAGMA table_info(etroc_review_events)')]
    indexes = {row[1]: (row[2], row[3], row[4], tuple(index_row[2] for index_row in db.execute(f'PRAGMA index_info("{row[1]}")'))) for row in db.execute('PRAGMA index_list(etroc_review_events)')}
    foreign_keys = [tuple(row) for row in db.execute('PRAGMA foreign_key_list(etroc_review_events)')]
    etroc_reviews.validate_schema(db)
    etroc_position_reviews.validate_schema(db)
schema_payload = json.dumps(schema_rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
runtime_schema_sha256 = hashlib.sha256(schema_payload).hexdigest()
runtime_hybrid_schema_sha256 = hashlib.sha256(json.dumps(hybrid_rows, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
expected_review_objects = {
    'etroc_review_schema', 'etroc_review_events', 'idx_etroc_review_one_root',
    'idx_etroc_review_one_successor', 'idx_etroc_review_author_mutation',
    'idx_etroc_review_current_lookup', 'etroc_review_no_update',
    'etroc_review_no_delete', 'etroc_review_same_evidence_successor',
}
expected_position_review_objects = {
    'position_review_schema', 'position_review_events',
    'idx_position_review_one_root', 'idx_position_review_one_successor',
    'idx_position_review_author_mutation', 'idx_position_review_current_lookup',
    'position_review_no_update', 'position_review_no_delete',
    'position_review_same_evidence_successor',
}
if (review_objects != expected_review_objects
        or position_review_objects != expected_position_review_objects
        or len(review_version) != 1 or review_version[0][:2] != (1, 1)
        or len(position_review_version) != 1 or position_review_version[0][:2] != (1, 2)):
    raise SystemExit('ETROC review schema/startup probe failed')
if any(name not in expected_review_objects for _kind, name, _table in attached_objects):
    raise SystemExit('arbitrary ETROC attached object')
if any(name not in expected_position_review_objects for _kind, name, _table in position_attached_objects):
    raise SystemExit('arbitrary ETROC position attached object')
expected_columns = [
    ('id', 'INTEGER', 0), ('dataset_id', 'TEXT', 1), ('etroc_serial', 'TEXT', 1),
    ('acquisition_id', 'TEXT', 1), ('analysis_run_id', 'TEXT', 1), ('montage_sha256', 'TEXT', 1),
    ('state', 'TEXT', 1), ('note', 'TEXT', 1), ('author', 'TEXT', 1), ('author_display', 'TEXT', 1),
    ('created_at', 'INTEGER', 1), ('mutation_id', 'TEXT', 1), ('supersedes_event_id', 'INTEGER', 0),
]
expected_indexes = {
    'idx_etroc_review_one_root': (1, 'c', 1, ('dataset_id','etroc_serial','acquisition_id','analysis_run_id','montage_sha256')),
    'idx_etroc_review_one_successor': (1, 'c', 1, ('supersedes_event_id',)),
    'idx_etroc_review_author_mutation': (1, 'c', 0, ('author','mutation_id')),
    'idx_etroc_review_current_lookup': (0, 'c', 0, ('dataset_id','etroc_serial','acquisition_id','analysis_run_id','montage_sha256','id')),
}
expected_foreign_keys = [(0, 0, 'etroc_review_events', 'supersedes_event_id', 'id', 'NO ACTION', 'RESTRICT', 'NONE')]
if columns != expected_columns or indexes != expected_indexes or foreign_keys != expected_foreign_keys:
    raise SystemExit('ETROC review schema columns/indexes/index_info/FK actions mismatch')
if runtime_hybrid_schema_sha256 != os.environ['BACKUP_HYBRID_SCHEMA_SHA256']:
    raise SystemExit('existing Hybrid schema changed after rollout')
if comments < int(os.environ['BEFORE_COMMENTS']):
    raise SystemExit(f'comment count regressed: {comments}')
if foreign_key_errors:
    raise SystemExit(f'foreign key errors: {foreign_key_errors}')
if integrity != 'ok':
    raise SystemExit(f'runtime database integrity check failed: {integrity}')
print({'schema_sha256': runtime_schema_sha256, 'comments': comments, 'integrity': integrity, 'review_objects': len(review_objects), 'schema': 'POST_ROLLOUT_ETROC_SCHEMA PASS'})
PY
ETROC_EVENT_SNAPSHOT_POST_ROLLOUT="$(oc -n "$PROJECT" exec -i "$POD" -c web -- python - <<'PY'
import json, sqlite3
with sqlite3.connect('/data/comments.sqlite3') as db:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='etroc_review_events'").fetchone()
    if not exists:
        print('{"present":false}')
    else:
        rows = db.execute('SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,montage_sha256,state,note,author,author_display,created_at,mutation_id,supersedes_event_id FROM etroc_review_events ORDER BY id').fetchall()
        print(json.dumps({'present': True, 'count': len(rows), 'identity_chain': rows}, separators=(',', ':')))
PY
)"
POSITION_EVENT_SNAPSHOT_POST_ROLLOUT="$(oc -n "$PROJECT" exec -i "$POD" -c web -- python - <<'PY'
import json, sqlite3
with sqlite3.connect('/data/comments.sqlite3') as db:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='position_review_events'").fetchone()
    if not exists:
        print('{"present":false}')
    else:
        columns = {row[1] for row in db.execute('PRAGMA table_info(position_review_events)')}
        value_field = 'label' if 'label' in columns else 'state' if 'state' in columns else None
        if value_field is None:
            raise SystemExit('unsupported position review event value field')
        rows = db.execute(f'SELECT id,dataset_id,etroc_serial,acquisition_id,analysis_run_id,labelled_montage_sha256,clean_montage_sha256,position_publication_sha256,position,source_image_sha256,geometry_version,{value_field},note,author,author_display,created_at,mutation_id,supersedes_event_id FROM position_review_events ORDER BY id').fetchall()
        print(json.dumps({'present': True, 'count': len(rows), 'identity_chain': rows}, separators=(',', ':')))
PY
)"
assert_etroc_snapshot "$ETROC_EVENT_SNAPSHOT_BEFORE" "$ETROC_EVENT_SNAPSHOT_POST_ROLLOUT"
assert_etroc_snapshot "$POSITION_EVENT_SNAPSHOT_BEFORE" "$POSITION_EVENT_SNAPSHOT_POST_ROLLOUT"
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
SPOOF_STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --header "X-Forwarded-Email: ${ETROC_REVIEWER_TEST_USER}" \
  'https://etl-hybrid-bbqc.app.cern.ch/api/etroc-reviews?dataset_id=ETROC_OI_2608')"
if test "$SPOOF_STATUS" != 302; then
  printf '%s\n' 'external trusted-header spoof was accepted' >&2
  false
fi
INTERNAL_STATUS="$(oc -n "$PROJECT" exec -i "$POD" -c web -- env ETROC_REVIEWER_TEST_USER="$ETROC_REVIEWER_TEST_USER" python - <<'PY'
import os
import urllib.request
request=urllib.request.Request(
    'http://127.0.0.1:8080/api/etroc-reviews?dataset_id=ETROC_OI_2608',
    headers={'X-Forwarded-Email': os.environ['ETROC_REVIEWER_TEST_USER']},
)
with urllib.request.urlopen(request, timeout=10) as response:
    print(response.status)
PY
)"
test "$INTERNAL_STATUS" = 200
printf 'ETROC_PROXY_IDENTITY_GATE PASS spoof=%s internal=%s\n' "$SPOOF_STATUS" "$INTERNAL_STATUS"
printf '%s\n' 'AUTHENTICATED_BROWSER_QA PENDING: verify CERN SSO session behavior separately.'
printf '%s\n' 'FORWARD_RELEASE_COMMITTED after mandatory read-only post-rollout gates' >> "$RELEASE_STATE"
ln -sfn "$(basename "$RELEASE_STATE")" "$CURRENT_RELEASE_STATE"
ROLLOUT_MUTATED=0
printf 'DEPLOYMENT PASS source=%s build=%s image=%s comments_before=%s release_state=%s\n' \
  "$SOURCE_REVISION" "$BUILD_NAME" "$NEW_WEB_IMAGE" "$BEFORE_COMMENTS" "$RELEASE_STATE"
