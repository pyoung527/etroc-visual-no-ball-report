"""Execute the exact embedded release closure verifier, without auth or deployment."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'hybrid-bbqc/openshift/deploy_dashboard_overlay_lxplus.sh'
REL = 'data/new-hybrids/NEW_HYBRIDS_20260911'

def verifier():
    script = SCRIPT.read_text()
    assert 'new_hybrids_verifier() {' in script, 'release closure verifier is missing'
    return script.split("new_hybrids_verifier() {\n  cat <<'NEW_HYBRIDS_PY'\n", 1)[1].split('\nNEW_HYBRIDS_PY', 1)[0]

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def fixture(root):
    bundle = root / REL
    bundle.mkdir(parents=True)
    assets = {'source-original.csv': b'original', 'source-corrected.csv': b'corrected'}
    records = []
    for i in range(35):
        raw = b'\x89PNG\r\n\x1a\n' + str(i).encode()
        digest = sha(raw)
        uri = f'images/{digest}.png'
        assets[uri] = raw
        records.append({'etroc_serial': f'W02G4-{i}', 'image': {'uri': uri, 'sha256': digest}})
    assets['manifest.json'] = json.dumps({'dataset_id': 'NEW_HYBRIDS_20260911', 'records': records}).encode()
    for name, raw in assets.items():
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    sums = ''.join(f'{sha(raw)}  {name}\n' for name, raw in sorted(assets.items()))
    (bundle / 'SHA256SUMS').write_text(sums)
    for name in ('new-hybrids.js', 'new-hybrids.css'):
        (root / name).write_bytes(name.encode())
    return [sha((root / 'new-hybrids.js').read_bytes()), sha((root / 'new-hybrids.css').read_bytes()), sha(assets['manifest.json']), sha(sums.encode())]

def run(root, pins, mode='files'):
    return subprocess.run([sys.executable, '-I', '-', str(root), mode, *pins], input=verifier(), capture_output=True, text=True)

def test_valid_exact_closure(tmp_path):
    result = run(tmp_path, fixture(tmp_path))
    assert result.returncode == 0, result.stderr

@pytest.mark.parametrize('case', ['traversal', 'absolute', 'duplicate', 'malformed', 'missing', 'extra', 'wrong_image_hash', 'extra_file', 'symlink', 'unpinned', 'manifest_mismatch'])
def test_rejects_unsafe_or_incomplete_closure(tmp_path, case):
    pins = fixture(tmp_path)
    bundle = tmp_path / REL
    sums = bundle / 'SHA256SUMS'
    lines = sums.read_text().splitlines()
    if case == 'traversal': lines[0] = 'a'*64 + '  ../escape.csv'
    elif case == 'absolute': lines[0] = 'a'*64 + '  /tmp/escape.csv'
    elif case == 'duplicate': lines[-1] = lines[0]
    elif case == 'malformed': lines[0] = 'not-a-checksum  source-original.csv'
    elif case == 'missing': lines.pop()
    elif case == 'extra': lines.append('a'*64 + '  extra.csv')
    elif case == 'wrong_image_hash':
        i = next(i for i, line in enumerate(lines) if 'images/' in line)
        lines[i] = 'a'*64 + lines[i][64:]
    elif case == 'extra_file': (bundle / 'unlisted.csv').write_text('unexpected')
    elif case == 'symlink':
        p = bundle / 'source-original.csv'; p.unlink(); p.symlink_to(bundle / 'source-corrected.csv')
    elif case == 'unpinned': pins[0] = 'UNPINNED'
    elif case == 'manifest_mismatch':
        p = bundle / 'manifest.json'; doc = json.loads(p.read_bytes()); doc['records'].pop(); p.write_text(json.dumps(doc))
        pins[2] = sha(p.read_bytes())
        lines = [pins[2] + line[64:] if line.endswith('  manifest.json') else line for line in lines]
    sums.write_text('\n'.join(lines) + '\n')
    pins[3] = sha(sums.read_bytes())
    result = run(tmp_path, pins)
    assert result.returncode != 0, case

@pytest.mark.parametrize('corrupt', [False, True])
def test_runtime_http_reads_entire_bundle(tmp_path, corrupt):
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    pins = fixture(tmp_path)
    if corrupt:
        (tmp_path / REL / 'source-corrected.csv').write_bytes(b'tampered')
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        program = verifier().replace('http://127.0.0.1:8080', f'http://127.0.0.1:{server.server_port}')
        result = subprocess.run([sys.executable, '-I', '-', str(tmp_path), 'http', *pins], input=program, capture_output=True, text=True)
        assert (result.returncode != 0) == corrupt, result.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

def test_current_builder_bundle_closure_when_available():
    root = ROOT / 'hybrid-bbqc'
    paths = [root / 'new-hybrids.js', root / 'new-hybrids.css', root / REL / 'manifest.json', root / REL / 'SHA256SUMS']
    if not all(p.is_file() for p in paths):
        pytest.skip('parallel builder has not frozen all new Hybrid artifacts')
    result = run(root, [sha(p.read_bytes()) for p in paths])
    assert result.returncode == 0, result.stderr

def test_release_closure_runs_before_auth_and_at_all_boundaries():
    script = SCRIPT.read_text()
    main = script[script.index('trap cleanup EXIT'):]
    assert main.index('prepare_new_hybrids') < main.index('ensure_authenticated')
    assert 'verify_new_hybrids_context' in main
    assert 'verify_new_hybrids_runtime "$CANDIDATE_PROBE_POD"' in main
    assert 'verify_new_hybrids_runtime "$POD" web' in main
    assert "if len(lines) != 181:" in script

def test_network_downloads_have_bounded_retry_without_relaxing_hashes(tmp_path):
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    pins = fixture(tmp_path)
    counts = {'attempts': 0}
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(tmp_path), **kwargs)
        def log_message(self, format, *args):
            pass
        def do_GET(self):
            if self.path.endswith('/source-original.csv'):
                counts['attempts'] += 1
                if counts['attempts'] <= 2:
                    self.send_error(502)
                    return
            super().do_GET()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        program = verifier().replace('http://127.0.0.1:8080', f'http://127.0.0.1:{server.server_port}')
        result = subprocess.run([sys.executable, '-I', '-', str(tmp_path), 'http', *pins], input=program, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        assert counts['attempts'] == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_final_available_files_match_pins_or_explicit_unpinned():
    script = SCRIPT.read_text()
    pairs = {'NEW_HYBRIDS_JS_SHA256': 'new-hybrids.js', 'NEW_HYBRIDS_CSS_SHA256': 'new-hybrids.css', 'NEW_HYBRIDS_MANIFEST_SHA256': REL + '/manifest.json', 'NEW_HYBRIDS_SUMS_SHA256': REL + '/SHA256SUMS'}
    for variable, relative in pairs.items():
        pin = re.search(rf"^{variable}='([^']+)'$", script, re.M).group(1)
        assert pin == 'UNPINNED' or re.fullmatch('[0-9a-f]{64}', pin)
        path = ROOT / 'hybrid-bbqc' / relative
        if pin != 'UNPINNED':
            assert path.is_file(), relative
            assert sha(path.read_bytes()) == pin, relative
