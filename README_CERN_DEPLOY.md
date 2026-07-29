# CERN OKD deployment: ETROC solder inspection report

Static report app for the ETROC solder/visual no-ball inspection output.

## Proposed names

- OKD project/namespace: `etroc-solder-inspection`
- OKD app/resources: `etroc-solder-inspection`
- Human-facing app name: `ETROC-solder-inspection`
- Public exposure: OpenShift `Route`, public, edge TLS, HTTP redirected to HTTPS

Kubernetes/OKD resource names are lowercase DNS labels, so the requested `ETROC-solder-inspection` is normalized to `etroc-solder-inspection` for resource names.

## One-time login

```bash
set -Eeuo pipefail
oc login --token=<CERN_OKD_TOKEN> --server=https://api.paas.okd.cern.ch
```

If this fails with `EOF` or TLS handshake errors from outside CERN, retry from the CERN network, CERN VPN, or lxplus-like environment with access to the OKD API.

## Create/select project

```bash
set -Eeuo pipefail
if oc project etroc-solder-inspection >/dev/null 2>&1; then
  echo 'Using existing project etroc-solder-inspection'
else
  oc new-project etroc-solder-inspection \
    --description="ETROC solder inspection static report" \
    --display-name="ETROC solder inspection"
fi
```

## Deploy from GitHub source

```bash
set -Eeuo pipefail
oc apply -f openshift/imagestream.yaml
oc apply -f openshift/buildconfig.yaml
oc start-build etroc-solder-inspection --follow
oc apply -f openshift/deployment.yaml
oc apply -f openshift/service.yaml
oc apply -f openshift/route.yaml
```

## Verify

```bash
set -Eeuo pipefail
oc rollout status deployment/etroc-solder-inspection
oc get pods,svc,route
ROUTE_URL="https://$(oc get route etroc-solder-inspection -o jsonpath='{.spec.host}')"
echo "$ROUTE_URL"
curl -I "$ROUTE_URL/"
curl -I "$ROUTE_URL/assets/images/visual_no_ball_chip_card_table_corrected.png"
curl -I "$ROUTE_URL/assets/montages/W03F7_DATA1_chip_87.jpg"
```

## Custom CERN hostname

The included `openshift/route.yaml` now requests the cleaner host `etroc-solder-inspection.app.cern.ch` instead of the default `<route>-<project>.app.cern.ch` pattern. If CERN Web Frameworks later allocates a `*.web.cern.ch` hostname, replace `spec.host` in `openshift/route.yaml` or configure the host through the CERN Web Frameworks UI, depending on the service workflow.

## Public route exposure

The route manifest explicitly sets:

```yaml
haproxy.router.openshift.io/ip_whitelist: "0.0.0.0/0 ::/0"
```

CERN OKD may otherwise default routes to CERN-network-only CIDRs. If external users see `Empty reply from server` while lxplus receives `HTTP/1.1 200 OK`, re-apply the route or run:

```bash
set -Eeuo pipefail
oc annotate route etroc-solder-inspection \
  haproxy.router.openshift.io/ip_whitelist='0.0.0.0/0 ::/0' \
  --overwrite
```

Then verify from outside CERN.


## Shortening the default route URL

If the first route was created as `etroc-solder-inspection-etroc-solder-inspection.app.cern.ch`, apply the updated route manifest or patch the host directly:

```bash
set -Eeuo pipefail
oc apply -f openshift/route.yaml
# or
oc patch route etroc-solder-inspection --type=merge \
  -p '{"spec":{"host":"etroc-solder-inspection.app.cern.ch"}}'
```

Verify:

```bash
set -Eeuo pipefail
oc get route etroc-solder-inspection
curl -I https://etroc-solder-inspection.app.cern.ch/
```

## BBQC–ETL hybrid registry bridge

The BBQC comments service now initializes an idempotent bridge in the existing
`/data/comments.sqlite3` PVC:

- `hybrid_registry`: stable BBQC identity and nullable ETL Hybrid ID/serial.
- `hybrid_target_aliases`: canonical and redirected `hybrid:<pair_key>` targets.
- `comments.hybrid_registry_id`: stable comment-to-hybrid reference; the legacy
  `comments.target` column and all current comment API shapes remain supported.

At startup the service seeds canonical pairs from `index.html`, imports redirect
pages as aliases, and backfills `comments.hybrid_registry_id` without rewriting
legacy `comments.target` values. Pair corrections reuse a registry row through
exact-pair, redirect, or unambiguous ETROC/LGAD evidence, preserving its ID and
ETL binding. Startup fails before registry mutation if no canonical pairs are
found, if a child is duplicated, or if correction evidence is ambiguous.

The backend listens only on `127.0.0.1:8080`; the Service exposes oauth2-proxy.
Only `X-Forwarded-Email` passed upstream by oauth2-proxy is trusted, and mutations
require the exact `APP_ORIGIN`. The Deployment uses `Recreate`, so old and new
SQLite writers do not overlap.

### Pre-rollout database backup and release capture

Confirm the account/project, record the running image digest and comment count,
then create and verify an online SQLite backup:

```bash
set -Eeuo pipefail
PROJECT="etroc-solder-inspection"
REPO_ROOT="$(git rev-parse --show-toplevel)"
test -f "$REPO_ROOT/hybrid-bbqc/openshift/select_single_app_pod.py"
test -f "$REPO_ROOT/hybrid-bbqc/openshift/validate_pvc_controllers.py"
normalize_api_server() {
  python -c 'import sys, urllib.parse
u=urllib.parse.urlsplit(sys.argv[1])
assert u.scheme == "https" and u.hostname == "api.paas.okd.cern.ch"
assert u.port in (None, 443) and not u.username and not u.password
assert not u.path.rstrip("/") and not u.query and not u.fragment
print("https://api.paas.okd.cern.ch:443")' "$1"
}
API_SERVER="$(normalize_api_server "$(oc whoami --show-server)")"
test "$API_SERVER" = "https://api.paas.okd.cern.ch:443"
OC_USER="$(oc whoami)"
test "$OC_USER" = "ypark"
oc project "$PROJECT"
verify_context() {
  test "$(normalize_api_server "$(oc whoami --show-server)")" = "$API_SERVER"
  test "$(oc whoami)" = "$OC_USER"
  test "$(oc project -q)" = "$PROJECT"
  if test -n "${DEPLOYMENT_UID:-}"; then
    test "$(oc -n "$PROJECT" get deployment/etl-hybrid-bbqc -o jsonpath='{.metadata.uid}')" = "$DEPLOYMENT_UID"
  fi
}
select_single_app_pod() {
  local tmpdir selected
  tmpdir="$(mktemp -d)"
  if ! oc -n "$PROJECT" get pods -o json > "$tmpdir/pods.json" \
    || ! oc -n "$PROJECT" get replicasets.apps -o json > "$tmpdir/replicasets.json"; then
    rm -rf "$tmpdir"
    return 1
  fi
  if ! selected="$(python "$REPO_ROOT/hybrid-bbqc/openshift/select_single_app_pod.py" \
    --pods "$tmpdir/pods.json" --replicasets "$tmpdir/replicasets.json" \
    --deployment etl-hybrid-bbqc --deployment-uid "$DEPLOYMENT_UID" \
    --pvc etl-hybrid-bbqc-comments \
    --container web --container oauth2-proxy \
    --pvc-container web --pvc-mount-path /data)"; then
    rm -rf "$tmpdir"
    return 1
  fi
  rm -rf "$tmpdir"
  printf '%s\n' "$selected"
}
verify_context
oc -n "$PROJECT" rollout status deployment/etl-hybrid-bbqc --timeout=300s
DEPLOYMENT_UID="$(oc -n "$PROJECT" get deployment/etl-hybrid-bbqc -o jsonpath='{.metadata.uid}')"
[[ "$DEPLOYMENT_UID" =~ ^[A-Za-z0-9._:-]+$ ]]
verify_context
POD="$(select_single_app_pod)"
RAW_OLD_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
OLD_WEB_IMAGE="${RAW_OLD_WEB_IMAGE#docker-pullable://}"
case "$OLD_WEB_IMAGE" in *@sha256:*) ;; *) echo 'old imageID is missing or not digest-pinned' >&2; exit 1;; esac
RAW_OLD_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
OLD_PROXY_IMAGE="${RAW_OLD_PROXY_IMAGE#docker-pullable://}"
case "$OLD_PROXY_IMAGE" in *@sha256:*) ;; *) echo 'old proxy imageID is missing or not digest-pinned' >&2; exit 1;; esac
BEFORE_COMMENTS="$(oc -n "$PROJECT" exec "$POD" -c web -- python -c \
  "import sqlite3; print(sqlite3.connect('/data/comments.sqlite3').execute('SELECT COUNT(*) FROM comments').fetchone()[0])")"
[[ "$BEFORE_COMMENTS" =~ ^[0-9]+$ ]]
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/data/comments.sqlite3.before-registry-${STAMP}.bak"
BACKUP_DIR="${HOME}/bbqc-backups"
install -d -m 700 "$BACKUP_DIR"
LOCAL_BACKUP="${BACKUP_DIR}/$(basename "$BACKUP")"
RELEASE_STATE="${BACKUP_DIR}/current-release.env"
OLD_DEPLOYMENT_FILE="${BACKUP_DIR}/deployment-before-registry-${STAMP}.json"
umask 077
export OLD_WEB_IMAGE OLD_PROXY_IMAGE DEPLOYMENT_UID
oc -n "$PROJECT" get deployment/etl-hybrid-bbqc -o json | python -c '
import json, os, sys
source=json.load(sys.stdin)
assert source["metadata"]["uid"] == os.environ["DEPLOYMENT_UID"]
metadata={key: source["metadata"][key] for key in ("name","namespace","labels","annotations")
          if key in source["metadata"]}
desired={"apiVersion": source["apiVersion"], "kind": "Deployment",
         "metadata": metadata, "spec": source["spec"]}
images={"web": os.environ["OLD_WEB_IMAGE"],
        "oauth2-proxy": os.environ["OLD_PROXY_IMAGE"]}
found=set()
for container in desired["spec"]["template"]["spec"]["containers"]:
    if container["name"] in images:
        container["image"]=images[container["name"]]
        found.add(container["name"])
assert found == set(images), found
json.dump(desired, sys.stdout, indent=2, sort_keys=True)
' > "$OLD_DEPLOYMENT_FILE"
OLD_DEPLOYMENT_SHA256="$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)"
[[ "$OLD_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
{
  declare -p PROJECT REPO_ROOT API_SERVER OC_USER DEPLOYMENT_UID OLD_WEB_IMAGE OLD_PROXY_IMAGE BEFORE_COMMENTS
  declare -p STAMP BACKUP LOCAL_BACKUP OLD_DEPLOYMENT_FILE OLD_DEPLOYMENT_SHA256
  declare -f normalize_api_server verify_context select_single_app_pod
} > "$RELEASE_STATE"
printf 'API_SERVER=%s\nOC_USER=%s\nPROJECT=%s\nOLD_WEB_IMAGE=%s\nOLD_PROXY_IMAGE=%s\nOLD_DEPLOYMENT_FILE=%s\nBEFORE_COMMENTS=%s\nBACKUP=%s\nLOCAL_BACKUP=%s\n' \
  "$API_SERVER" "$OC_USER" "$PROJECT" "$OLD_WEB_IMAGE" "$OLD_PROXY_IMAGE" \
  "$OLD_DEPLOYMENT_FILE" "$BEFORE_COMMENTS" "$BACKUP" "$LOCAL_BACKUP"

oc -n "$PROJECT" exec -i "$POD" -c web -- env BACKUP="$BACKUP" BEFORE_COMMENTS="$BEFORE_COMMENTS" python - <<'PY'
import os, sqlite3
source = sqlite3.connect('/data/comments.sqlite3')
target = sqlite3.connect(os.environ['BACKUP'])
with target:
    source.backup(target)
integrity = target.execute('PRAGMA integrity_check').fetchone()[0]
comments = target.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
target.close(); source.close()
assert integrity == 'ok', integrity
assert comments == int(os.environ['BEFORE_COMMENTS']), (comments, os.environ['BEFORE_COMMENTS'])
print({'backup': os.environ['BACKUP'], 'integrity': integrity, 'comments': comments})
PY
oc -n "$PROJECT" cp "$POD:$BACKUP" "$LOCAL_BACKUP" -c web
export LOCAL_BACKUP BEFORE_COMMENTS
python - <<'PY'
import os, sqlite3
path = os.environ['LOCAL_BACKUP']
with sqlite3.connect(path) as db:
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
    comments = db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
assert integrity == 'ok', integrity
assert comments == int(os.environ['BEFORE_COMMENTS']), (comments, os.environ['BEFORE_COMMENTS'])
print({'local_backup': path, 'integrity': integrity, 'comments': comments})
PY
BACKUP_SHA256="$(sha256sum "$LOCAL_BACKUP" | cut -d' ' -f1)"
[[ "$BACKUP_SHA256" =~ ^[0-9a-f]{64}$ ]]
declare -p BACKUP_SHA256 >> "$RELEASE_STATE"
printf '%s  %s\n' "$BACKUP_SHA256" "$LOCAL_BACKUP" > "${LOCAL_BACKUP}.sha256"
```

Do not deploy the mutable `:latest` reference. After the build succeeds, resolve
the ImageStreamTag to a digest and render a pinned deployment manifest:

```bash
set -Eeuo pipefail
source "${HOME}/bbqc-backups/current-release.env"
verify_context
cd "$REPO_ROOT"
test -z "$(git status --porcelain --untracked-files=all -- hybrid-bbqc assets)"
SOURCE_REVISION="$(git rev-parse HEAD)"
[[ "$SOURCE_REVISION" =~ ^[0-9a-f]{40}$ ]]
oc -n "$PROJECT" apply --dry-run=server -f hybrid-bbqc/openshift/imagestream.yaml
oc -n "$PROJECT" apply --dry-run=server -f hybrid-bbqc/openshift/buildconfig.yaml
oc -n "$PROJECT" apply -f hybrid-bbqc/openshift/imagestream.yaml
oc -n "$PROJECT" apply -f hybrid-bbqc/openshift/buildconfig.yaml
BUILD_CONTEXT="$(mktemp -d)"
trap 'rm -rf "$BUILD_CONTEXT"' EXIT
cp -a hybrid-bbqc assets "$BUILD_CONTEXT/"
BUILD_CONTEXT_SHA256="$(tar --sort=name --mtime='UTC 1970-01-01' \
  --owner=0 --group=0 --numeric-owner -cf - -C "$BUILD_CONTEXT" \
  hybrid-bbqc assets | sha256sum | cut -d' ' -f1)"
[[ "$BUILD_CONTEXT_SHA256" =~ ^[0-9a-f]{64}$ ]]
BUILD_NAME="$(oc -n "$PROJECT" start-build etl-hybrid-bbqc \
  --from-dir="$BUILD_CONTEXT" -o name)"
oc -n "$PROJECT" logs -f "$BUILD_NAME"
oc -n "$PROJECT" wait --for=condition=Complete "$BUILD_NAME" --timeout=900s
test "$(oc -n "$PROJECT" get "$BUILD_NAME" -o jsonpath='{.status.phase}')" = "Complete"
NEW_WEB_IMAGE="$(oc -n "$PROJECT" get istag etl-hybrid-bbqc:latest \
  -o jsonpath='{.image.dockerImageReference}')"
case "$NEW_WEB_IMAGE" in *@sha256:*) ;; *) echo 'image is not digest-pinned' >&2; exit 1;; esac
declare -p SOURCE_REVISION BUILD_CONTEXT_SHA256 BUILD_NAME NEW_WEB_IMAGE \
  >> "${HOME}/bbqc-backups/current-release.env"
export NEW_WEB_IMAGE
rm -f /tmp/etl-hybrid-bbqc-deployment-pinned.yaml
python - <<'PY'
import os
from pathlib import Path
src = Path('hybrid-bbqc/openshift/deployment.yaml').read_text()
tag = 'image-registry.openshift-image-registry.svc:5000/etroc-solder-inspection/etl-hybrid-bbqc:latest'
assert src.count(tag) == 1
rendered = src.replace(tag, os.environ['NEW_WEB_IMAGE'])
assert rendered.count('@sha256:') >= 2  # web and oauth2-proxy
Path('/tmp/etl-hybrid-bbqc-deployment-pinned.yaml').write_text(rendered)
PY
test -s /tmp/etl-hybrid-bbqc-deployment-pinned.yaml
oc -n "$PROJECT" apply --dry-run=server -f /tmp/etl-hybrid-bbqc-deployment-pinned.yaml
oc -n "$PROJECT" apply -f /tmp/etl-hybrid-bbqc-deployment-pinned.yaml
oc -n "$PROJECT" annotate deployment/etl-hybrid-bbqc --overwrite \
  "bbqc.cern.ch/source-revision=$SOURCE_REVISION" \
  "bbqc.cern.ch/build-context-sha256=$BUILD_CONTEXT_SHA256" \
  "bbqc.cern.ch/build-name=$BUILD_NAME"
oc -n "$PROJECT" rollout status deployment/etl-hybrid-bbqc --timeout=300s
```

### Post-rollout database verification

The current static dashboard contains exactly 72 active pairs. Verify schema,
coverage, comments, foreign keys, and SQLite integrity:

```bash
set -Eeuo pipefail
source "${HOME}/bbqc-backups/current-release.env"
verify_context
POD="$(select_single_app_pod)"
oc -n "$PROJECT" exec -i "$POD" -c web -- env BEFORE_COMMENTS="$BEFORE_COMMENTS" python - <<'PY'
import os, sqlite3
p='/data/comments.sqlite3'
with sqlite3.connect(p) as db:
    active = db.execute('SELECT COUNT(*) FROM hybrid_registry WHERE active=1').fetchone()[0]
    canonical = db.execute('SELECT COUNT(*) FROM hybrid_target_aliases WHERE is_canonical=1').fetchone()[0]
    aliases = db.execute('SELECT COUNT(*) FROM hybrid_target_aliases').fetchone()[0]
    comments = db.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
    unresolved = db.execute("""
      SELECT COUNT(*) FROM comments
      WHERE target LIKE 'hybrid:%' AND hybrid_registry_id IS NULL
    """).fetchone()[0]
    duplicate_children = db.execute('''
      SELECT COUNT(*) FROM (
        SELECT etroc_serial FROM hybrid_registry WHERE active=1 GROUP BY etroc_serial HAVING COUNT(*)>1
        UNION ALL
        SELECT lgad_serial FROM hybrid_registry WHERE active=1 GROUP BY lgad_serial HAVING COUNT(*)>1
      )
    ''').fetchone()[0]
    foreign_key_errors = db.execute('PRAGMA foreign_key_check').fetchall()
    integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
result = {
  'active': active, 'canonical': canonical, 'aliases': aliases,
  'comments': comments, 'unresolved_hybrid_comments': unresolved,
  'duplicate_children': duplicate_children,
  'foreign_key_errors': len(foreign_key_errors), 'integrity': integrity,
}
print(result)
assert active == 72 and canonical == 72 and aliases >= 72
assert comments >= int(os.environ['BEFORE_COMMENTS'])
assert unresolved == 0 and duplicate_children == 0
assert not foreign_key_errors and integrity == 'ok'
PY
```

Verify the deployed image digest and logs:

```bash
set -Eeuo pipefail
source "${HOME}/bbqc-backups/current-release.env"
verify_context
POD="$(select_single_app_pod)"
RAW_POD_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
POD_WEB_IMAGE="${RAW_POD_WEB_IMAGE#docker-pullable://}"
test "$POD_WEB_IMAGE" = "$NEW_WEB_IMAGE"
EXPECTED_PROXY_IMAGE="$(oc -n "$PROJECT" get deployment/etl-hybrid-bbqc -o jsonpath='{.spec.template.spec.containers[?(@.name=="oauth2-proxy")].image}')"
RAW_POD_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
POD_PROXY_IMAGE="${RAW_POD_PROXY_IMAGE#docker-pullable://}"
case "$EXPECTED_PROXY_IMAGE" in *@sha256:*) ;; *) exit 1;; esac
test "$POD_PROXY_IMAGE" = "$EXPECTED_PROXY_IMAGE"
READY="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{range .status.containerStatuses[*]}{.name}={.ready}{"\n"}{end}')"
printf '%s\n' "$READY"
grep -qx 'web=true' <<< "$READY"
grep -qx 'oauth2-proxy=true' <<< "$READY"
WEB_LOG="$(oc -n "$PROJECT" logs "$POD" -c web --tail=200)"
printf '%s\n' "$WEB_LOG"
grep -Fq 'BBQC_STARTUP_OK' <<< "$WEB_LOG"
if grep -Eiq 'Traceback|unhandled exception|migration failed' <<< "$WEB_LOG"; then
  echo 'web log contains a blocking error' >&2
  exit 1
fi
PROXY_LOG="$(oc -n "$PROJECT" logs "$POD" -c oauth2-proxy --tail=200)"
printf '%s\n' "$PROXY_LOG"
if grep -Eiq '(^|[^[:alpha:]])(panic|fatal)([^[:alpha:]]|$)' <<< "$PROXY_LOG"; then
  echo 'oauth2-proxy log contains panic/fatal' >&2
  exit 1
fi
```

Externally, an unauthenticated request should redirect to CERN SSO. Then open
the authenticated endpoints in a browser and confirm `count: 72` and the CERN
identity shown by `/api/me`:

- [Health endpoint](https://etl-hybrid-bbqc.app.cern.ch/api/health)
- [Registry endpoint](https://etl-hybrid-bbqc.app.cern.ch/api/hybrids)
- [Identity endpoint](https://etl-hybrid-bbqc.app.cern.ch/api/me)

```bash
set -Eeuo pipefail
HEADERS="$(mktemp)"
trap 'rm -f "$HEADERS"' EXIT
HTTP_STATUS="$(curl -sS -D "$HEADERS" -o /dev/null -w '%{http_code}' \
  -H 'X-Forwarded-Email: ypark@cern.ch' \
  https://etl-hybrid-bbqc.app.cern.ch/api/health)"
test "$HTTP_STATUS" = "302"
LOCATION="$(awk 'tolower($1)=="location:" {gsub("\r", "", $2); print $2}' "$HEADERS" | tail -n1)"
case "$LOCATION" in https://auth.cern.ch/*) ;; *) echo "unexpected SSO redirect: $LOCATION" >&2; exit 1;; esac
printf 'SSO_PROXY_GATE PASS status=%s location=%s\n' "$HTTP_STATUS" "$LOCATION"
```

The release is not complete until an authenticated CERN browser session confirms
`/api/me` reports Young's expected identity and `/api/hybrids` reports
`count: 72`.

### ETL binding API

Registry reads are available at:

```text
GET /api/hybrids?pair_key=<ETROC__LGAD>
```

Binding requires CERN SSO, an identity listed in `COMMENTS_ADMIN_USERS`, exact
`Origin: https://etl-hybrid-bbqc.app.cern.ch`, and JSON content. All identity
fields are required; a partial request cannot clear a binding and there is no
implicit unbind operation. The first successful binding is immutable: repeating
the same ETL ID/serial is idempotent, while replacing it requires a separately
designed audited correction workflow and is rejected by this endpoint.

```text
POST /api/hybrids/bind
Origin: https://etl-hybrid-bbqc.app.cern.ch
Content-Type: application/json

{
  "pair_key": "W04F2-81__FBK_LF-W14_35",
  "etl_hybrid_id": 12345,
  "etl_hybrid_serial": "<ETL-approved serial>",
  "sync_status": "matched",
  "source_revision": "<import batch or ETL revision>"
}
```

The endpoint records an already-created ETL identity; it does not create or
modify ETL components. Do not exercise it with placeholder identifiers.

### Rollback

Do not use `oc rollout undo` against mutable source tags. Restore the captured
complete Deployment spec with both runtime images pinned to their pre-rollout
digests. Preserved legacy `comments.target` values keep pre-migration comments
visible to the previous application:

```bash
set -Eeuo pipefail
source "${HOME}/bbqc-backups/current-release.env"
verify_context
: "${OLD_DEPLOYMENT_FILE:?}" "${OLD_DEPLOYMENT_SHA256:?}"
case "$OLD_WEB_IMAGE" in *@sha256:*) ;; *) exit 1;; esac
case "$OLD_PROXY_IMAGE" in *@sha256:*) ;; *) exit 1;; esac
[[ "$OLD_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
test -r "$OLD_DEPLOYMENT_FILE"
test "$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)" = "$OLD_DEPLOYMENT_SHA256"
CURRENT_DEPLOYMENT="$(mktemp)"
ROLLBACK_DEPLOYMENT="$(mktemp)"
ACTUAL_DEPLOYMENT="$(mktemp)"
trap 'rm -f "$CURRENT_DEPLOYMENT" "$ROLLBACK_DEPLOYMENT" "$ACTUAL_DEPLOYMENT"' EXIT
oc -n "$PROJECT" get deployment/etl-hybrid-bbqc -o json > "$CURRENT_DEPLOYMENT"
export OLD_DEPLOYMENT_FILE CURRENT_DEPLOYMENT ROLLBACK_DEPLOYMENT
python -c '
import json, os
old=json.load(open(os.environ["OLD_DEPLOYMENT_FILE"]))
current=json.load(open(os.environ["CURRENT_DEPLOYMENT"]))
old["metadata"]["resourceVersion"]=current["metadata"]["resourceVersion"]
json.dump(old, open(os.environ["ROLLBACK_DEPLOYMENT"], "w"), indent=2, sort_keys=True)
'
oc -n "$PROJECT" replace --dry-run=server -f "$ROLLBACK_DEPLOYMENT"
oc -n "$PROJECT" replace -f "$ROLLBACK_DEPLOYMENT"
oc -n "$PROJECT" rollout status deployment/etl-hybrid-bbqc --timeout=300s
verify_context
oc -n "$PROJECT" get deployment/etl-hybrid-bbqc -o json > "$ACTUAL_DEPLOYMENT"
export ACTUAL_DEPLOYMENT
python -c '
import json, os
expected=json.load(open(os.environ["OLD_DEPLOYMENT_FILE"]))
actual=json.load(open(os.environ["ACTUAL_DEPLOYMENT"]))
assert actual["spec"] == expected["spec"], "rollback Deployment spec differs from snapshot"
print("ROLLBACK_SPEC_PASS")
'
POD="$(select_single_app_pod)"
RAW_ROLLBACK_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
RAW_ROLLBACK_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
ROLLBACK_WEB_IMAGE="${RAW_ROLLBACK_WEB_IMAGE#docker-pullable://}"
ROLLBACK_PROXY_IMAGE="${RAW_ROLLBACK_PROXY_IMAGE#docker-pullable://}"
test "$ROLLBACK_WEB_IMAGE" = "$OLD_WEB_IMAGE"
test "$ROLLBACK_PROXY_IMAGE" = "$OLD_PROXY_IMAGE"
printf 'ROLLBACK_RUNTIME_PASS pod=%s web=%s proxy=%s\n' \
  "$POD" "$ROLLBACK_WEB_IMAGE" "$ROLLBACK_PROXY_IMAGE"
```

New comments or bindings created after rollout remain in the forward-compatible
schema. If exact pre-rollout database state is required, stop all writers and
restore the verified backup with a temporary PVC-mounted pod. Preserve the
failed database first:

```bash
set -Eeuo pipefail
source "${HOME}/bbqc-backups/current-release.env"
verify_context
: "${PROJECT:?}" "${OLD_WEB_IMAGE:?}" "${BACKUP:?}" "${LOCAL_BACKUP:?}"
: "${BACKUP_SHA256:?}" "${STAMP:?}" "${BEFORE_COMMENTS:?}"
: "${OLD_PROXY_IMAGE:?}" "${OLD_DEPLOYMENT_FILE:?}" "${OLD_DEPLOYMENT_SHA256:?}"
case "$OLD_WEB_IMAGE" in *@sha256:*) ;; *) exit 1;; esac
case "$OLD_PROXY_IMAGE" in *@sha256:*) ;; *) exit 1;; esac
[[ "$BACKUP_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$OLD_DEPLOYMENT_SHA256" =~ ^[0-9a-f]{64}$ ]]
[[ "$BEFORE_COMMENTS" =~ ^[0-9]+$ ]]
[[ "$STAMP" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]
[[ "$BACKUP" = /data/*.bak ]]
[[ "$LOCAL_BACKUP" = "${HOME}/bbqc-backups/"*.bak ]]
test -r "$LOCAL_BACKUP"
test "$(sha256sum "$LOCAL_BACKUP" | cut -d' ' -f1)" = "$BACKUP_SHA256"
test -r "$OLD_DEPLOYMENT_FILE"
test "$(sha256sum "$OLD_DEPLOYMENT_FILE" | cut -d' ' -f1)" = "$OLD_DEPLOYMENT_SHA256"
export OLD_DEPLOYMENT_FILE
oc -n "$PROJECT" get deployment/etl-hybrid-bbqc -o json | python -c '
import json, os, sys
expected=json.load(open(os.environ["OLD_DEPLOYMENT_FILE"]))
actual=json.load(sys.stdin)
assert actual["spec"] == expected["spec"], "complete Deployment rollback required"
'
POD="$(select_single_app_pod)"
RAW_ROLLBACK_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
RAW_ROLLBACK_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
test "${RAW_ROLLBACK_WEB_IMAGE#docker-pullable://}" = "$OLD_WEB_IMAGE"
test "${RAW_ROLLBACK_PROXY_IMAGE#docker-pullable://}" = "$OLD_PROXY_IMAGE"
oc -n "$PROJECT" delete pod etl-hybrid-bbqc-db-restore --ignore-not-found
oc -n "$PROJECT" wait --for=delete pod/etl-hybrid-bbqc-db-restore --timeout=120s || \
  test -z "$(oc -n "$PROJECT" get pod etl-hybrid-bbqc-db-restore --ignore-not-found -o name)"

CONTROLLER_RESOURCES="deployments.apps,statefulsets.apps,daemonsets.apps,jobs.batch,cronjobs.batch,replicationcontrollers,replicasets.apps,horizontalpodautoscalers.autoscaling"
OPENSHIFT_CONTROLLER_RESOURCES="$(oc api-resources --namespaced=true --api-group=apps.openshift.io -o name)"
if grep -qx 'deploymentconfigs.apps.openshift.io' <<< "$OPENSHIFT_CONTROLLER_RESOURCES"; then
  CONTROLLER_RESOURCES="${CONTROLLER_RESOURCES},deploymentconfigs.apps.openshift.io"
fi
oc -n "$PROJECT" get "$CONTROLLER_RESOURCES" -o json | \
  python "$REPO_ROOT/hybrid-bbqc/openshift/validate_pvc_controllers.py" \
    --pvc etl-hybrid-bbqc-comments --deployment etl-hybrid-bbqc \
    --deployment-uid "$DEPLOYMENT_UID"
POD="$(select_single_app_pod)"
printf 'pre-scale exact UID-chain pod=%s deployment_uid=%s\n' "$POD" "$DEPLOYMENT_UID"

oc -n "$PROJECT" scale deployment/etl-hybrid-bbqc --replicas=0
oc -n "$PROJECT" wait --for=delete pod -l app=etl-hybrid-bbqc --timeout=180s
oc -n "$PROJECT" get deployments.apps,replicasets.apps -o json | \
  python "$REPO_ROOT/hybrid-bbqc/openshift/validate_pvc_controllers.py" \
    --pvc etl-hybrid-bbqc-comments --deployment etl-hybrid-bbqc \
    --deployment-uid "$DEPLOYMENT_UID" --require-scaled-zero
oc -n "$PROJECT" get pods -o json | env PVC=etl-hybrid-bbqc-comments python -c '
import json, os, sys
consumers=[]
for pod in json.load(sys.stdin)["items"]:
    if any(v.get("persistentVolumeClaim", {}).get("claimName") == os.environ["PVC"]
           for v in pod["spec"].get("volumes", [])):
        consumers.append(pod["metadata"]["name"])
assert not consumers, consumers
print({"quiescent PVC consumers": consumers})
'
cat <<YAML | oc -n "$PROJECT" create -f -
apiVersion: v1
kind: Pod
metadata:
  name: etl-hybrid-bbqc-db-restore
spec:
  restartPolicy: Never
  containers:
    - name: restore
      image: ${OLD_WEB_IMAGE}
      command: ["sleep", "3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: etl-hybrid-bbqc-comments
YAML
oc -n "$PROJECT" wait --for=condition=Ready pod/etl-hybrid-bbqc-db-restore --timeout=120s
oc -n "$PROJECT" get pods -o json | env PVC=etl-hybrid-bbqc-comments python -c '
import json, os, sys
consumers=[]
for pod in json.load(sys.stdin)["items"]:
    if any(v.get("persistentVolumeClaim", {}).get("claimName") == os.environ["PVC"]
           for v in pod["spec"].get("volumes", [])):
        consumers.append(pod["metadata"]["name"])
assert consumers == ["etl-hybrid-bbqc-db-restore"], consumers
print({"restore PVC consumers": consumers})
'
if ! oc -n "$PROJECT" exec etl-hybrid-bbqc-db-restore -c restore -- test -f "$BACKUP"; then
  oc -n "$PROJECT" cp "$LOCAL_BACKUP" "etl-hybrid-bbqc-db-restore:$BACKUP" -c restore
fi
REMOTE_BACKUP_SHA256="$(oc -n "$PROJECT" exec etl-hybrid-bbqc-db-restore -c restore -- \
  sha256sum "$BACKUP" | cut -d' ' -f1)"
if test "$REMOTE_BACKUP_SHA256" != "$BACKUP_SHA256"; then
  echo 'PVC backup checksum mismatch; replacing it with verified off-cluster copy' >&2
  oc -n "$PROJECT" cp "$LOCAL_BACKUP" "etl-hybrid-bbqc-db-restore:$BACKUP" -c restore
  REMOTE_BACKUP_SHA256="$(oc -n "$PROJECT" exec etl-hybrid-bbqc-db-restore -c restore -- \
    sha256sum "$BACKUP" | cut -d' ' -f1)"
fi
test "$REMOTE_BACKUP_SHA256" = "$BACKUP_SHA256"
oc -n "$PROJECT" exec -i etl-hybrid-bbqc-db-restore -c restore -- \
  env BACKUP="$BACKUP" STAMP="$STAMP" BEFORE_COMMENTS="$BEFORE_COMMENTS" python - <<'PY'
import os, sqlite3
live='/data/comments.sqlite3'
failed=f"{live}.failed-{os.environ['STAMP']}"
failed_result=None
if os.path.exists(live):
    failed_source=sqlite3.connect(live)
    failed_target=sqlite3.connect(failed)
    with failed_target:
        failed_source.backup(failed_target)
    failed_integrity=failed_target.execute('PRAGMA integrity_check').fetchone()[0]
    failed_target.close(); failed_source.close()
    assert failed_integrity == 'ok', failed_integrity
    failed_result=failed
source=sqlite3.connect(os.environ['BACKUP'])
source_integrity=source.execute('PRAGMA integrity_check').fetchone()[0]
source_comments=source.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
assert source_integrity == 'ok', source_integrity
assert source_comments == int(os.environ['BEFORE_COMMENTS'])
for suffix in ('', '-wal', '-shm', '-journal'):
    try: os.remove(live + suffix)
    except FileNotFoundError: pass
target=sqlite3.connect(live)
with target:
    source.backup(target)
integrity=target.execute('PRAGMA integrity_check').fetchone()[0]
comments=target.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
source.close(); target.close()
assert integrity == 'ok', integrity
assert comments == int(os.environ['BEFORE_COMMENTS']), (comments, os.environ['BEFORE_COMMENTS'])
print({'preserved_failed_db': failed_result, 'restored': os.environ['BACKUP'],
       'integrity': integrity, 'comments': comments})
PY
oc -n "$PROJECT" delete pod etl-hybrid-bbqc-db-restore
oc -n "$PROJECT" scale deployment/etl-hybrid-bbqc --replicas=1
oc -n "$PROJECT" rollout status deployment/etl-hybrid-bbqc --timeout=300s
POD="$(select_single_app_pod)"
RAW_RUNTIME_WEB_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="web")].imageID}')"
RAW_RUNTIME_PROXY_IMAGE="$(oc -n "$PROJECT" get pod "$POD" -o jsonpath='{.status.containerStatuses[?(@.name=="oauth2-proxy")].imageID}')"
RUNTIME_WEB_IMAGE="${RAW_RUNTIME_WEB_IMAGE#docker-pullable://}"
RUNTIME_PROXY_IMAGE="${RAW_RUNTIME_PROXY_IMAGE#docker-pullable://}"
test "$RUNTIME_WEB_IMAGE" = "$OLD_WEB_IMAGE"
test "$RUNTIME_PROXY_IMAGE" = "$OLD_PROXY_IMAGE"
```
