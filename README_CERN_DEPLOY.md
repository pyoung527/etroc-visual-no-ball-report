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
oc login --token=<CERN_OKD_TOKEN> --server=https://api.paas.okd.cern.ch
```

If this fails with `EOF` or TLS handshake errors from outside CERN, retry from the CERN network, CERN VPN, or lxplus-like environment with access to the OKD API.

## Create/select project

```bash
oc new-project etroc-solder-inspection \
  --description="ETROC solder inspection static report" \
  --display-name="ETROC solder inspection"
# or, if CERN Web Frameworks already created the namespace:
oc project etroc-solder-inspection
```

## Deploy from GitHub source

```bash
oc apply -f openshift/imagestream.yaml
oc apply -f openshift/buildconfig.yaml
oc start-build etroc-solder-inspection --follow
oc apply -f openshift/deployment.yaml
oc apply -f openshift/service.yaml
oc apply -f openshift/route.yaml
```

## Verify

```bash
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
oc annotate route etroc-solder-inspection \
  haproxy.router.openshift.io/ip_whitelist='0.0.0.0/0 ::/0' \
  --overwrite
```

Then verify from outside CERN.


## Shortening the default route URL

If the first route was created as `etroc-solder-inspection-etroc-solder-inspection.app.cern.ch`, apply the updated route manifest or patch the host directly:

```bash
oc apply -f openshift/route.yaml
# or
oc patch route etroc-solder-inspection --type=merge \
  -p '{"spec":{"host":"etroc-solder-inspection.app.cern.ch"}}'
```

Verify:

```bash
oc get route etroc-solder-inspection
curl -I https://etroc-solder-inspection.app.cern.ch/
```
