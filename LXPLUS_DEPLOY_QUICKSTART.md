# LXPLUS quick deploy for ETROC solder inspection

Use this when running from `lxplus.cern.ch`, especially if your CERN home directory is full. The deploy script keeps `oc` and `KUBECONFIG` under `/tmp/$USER/...` by default.

## One-liner

```bash
mkdir -p /tmp/$USER/etroc-okd && cd /tmp/$USER/etroc-okd
curl -fsSLO https://raw.githubusercontent.com/pyoung527/etroc-visual-no-ball-report/main/scripts/deploy_lxplus_okd.sh
chmod +x deploy_lxplus_okd.sh
./deploy_lxplus_okd.sh
```

The script will:

1. install `oc` under `/tmp/$USER/oc-client` if needed;
2. ask for the CERN OKD token without echoing it;
3. create/select project `etroc-solder-inspection`;
4. build from GitHub using the included `Containerfile`;
5. create Deployment, Service, and public HTTPS Route;
6. print `DEPLOYED_URL=...` after HTTP checks pass.

## If you want to provide the token non-interactively

```bash
export OKD_TOKEN='sha256~...'
./deploy_lxplus_okd.sh
unset OKD_TOKEN
```

Do not paste tokens into shared terminals/logs.

## Override names if needed

```bash
PROJECT_NAME=my-existing-cern-webapp-project ./deploy_lxplus_okd.sh
```
