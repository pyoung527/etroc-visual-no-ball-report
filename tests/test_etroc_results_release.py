"""Release closure for the result-first ETROC entry document."""
from pathlib import Path
import re
import io
import json
import os
import types
from unittest.mock import patch

import pytest
from test_etroc_results import load_module, STATIC_ROOT

ROOT = Path(__file__).resolve().parents[1]


def test_results_script_in_release_download_checksum_and_http_closure():
    helper = (ROOT / 'hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh').read_text()
    loop = re.search(r'for file in (.+?); do\n  download', helper)
    assert loop and 'etroc-results.js' in loop.group(1).split()
    assert re.search(r"ETROC_RESULTS_JS_SHA256='[0-9a-f]{64}'", helper)
    assert '"$ETROC_RESULTS_JS_SHA256" etroc-results.js >> SHA256SUMS' in helper
    assert 'sha256sum /app/static/etroc-results.js' in helper
    assert 'test "$REMOTE_ETROC_RESULTS_JS_SHA" = "$ETROC_RESULTS_JS_SHA256"' in helper
    assert 'ETROC_RESULTS_JS_SHA256="$ETROC_RESULTS_JS_SHA256"' in helper
    assert "('etroc-results.js', os.environ['ETROC_RESULTS_JS_SHA256'])" in helper
    assert 'ETROC_RESULTS_RUNTIME_CONTRACT PASS' in helper
    assert '/api/etroc-position-reviews/results?dataset_id=ETROC_OI_2608' in helper


def test_embedded_results_probe_accepts_real_service_contract_and_rejects_partial(tmp_path):
    module = load_module()
    evidence = module.load_evidence(STATIC_ROOT)
    db = tmp_path / 'reviews.sqlite3'
    module.init_schema(db)
    payload = module.results_summary(db, evidence)
    completion = module.completion_summary(db, evidence)
    publication = json.loads((STATIC_ROOT / 'data/etroc-optical/ETROC_OI_2608/chips.json').read_text())
    helper = (ROOT / 'hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh').read_text()
    probe = 'results_url=' + helper.split('results_url=', 1)[1].split('\nPY\n', 1)[0]

    def run():
        response = io.BytesIO(json.dumps(payload).encode())
        response.status = 200
        response.headers = {'Cache-Control': 'no-store'}
        request_api = types.SimpleNamespace(Request=lambda *a, **kw: None, urlopen=lambda *a, **kw: response)
        namespace = dict(json=json, os=os, urllib=types.SimpleNamespace(request=request_api), publication=publication, completion=completion)
        with patch.dict(os.environ, {'ETROC_REVIEWER_TEST_USER': 'synthetic-qa'}):
            exec(compile(probe, 'release-results-probe', 'exec'), namespace)

    run()
    first = next(iter(payload['results'].values()))
    first['algorithm_labels'].pop()
    with pytest.raises(SystemExit, match='evidence mismatch'):
        run()

