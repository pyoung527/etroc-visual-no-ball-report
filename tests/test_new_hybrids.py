import hashlib
import importlib.util
import io
import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/build_new_hybrids.py'
SOURCE = Path('/home/young-park/.hermes/profiles/schuman/downloads/onedrive-new-hybrids/new_hybrids.zip')
OUT = ROOT / 'hybrid-bbqc/data/new-hybrids/NEW_HYBRIDS_20260911'

def builder():
    assert TOOL.exists(), 'deterministic supplied-batch builder is missing'
    spec = importlib.util.spec_from_file_location('new_hybrids', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_publication_preserves_corrected_separate_cohort(tmp_path):
    m = builder()
    m.build(SOURCE, tmp_path / 'batch')
    p = tmp_path / 'batch'
    manifest = json.loads((p / 'manifest.json').read_bytes())
    records = manifest['records']
    assert len(records) == 35
    assert len({r['etroc_serial'] for r in records}) == 35
    by = {r['etroc_serial']: r for r in records}
    assert by['W05E5-30']['lgad_label'] == 'HPK-W7-4'
    assert 'W03F7-85' not in by
    assert sum(r['lgad_label'] == 'LF-LC2-K-UBM' for r in records) == 5
    assert all(r['channel'] is None for r in records)
    with zipfile.ZipFile(SOURCE) as z:
        assert (p / 'source-original.csv').read_bytes() == z.read('lgad_etroc_pairs.csv')
        for r in records:
            image = r['image']
            raw = (p / image['uri']).read_bytes()
            assert raw == z.read(image['source_member'])
            assert hashlib.sha256(raw).hexdigest() == image['sha256']
    first = {f.relative_to(p): f.read_bytes() for f in p.rglob('*') if f.is_file()}
    m.build(SOURCE, p)
    assert first == {f.relative_to(p): f.read_bytes() for f in p.rglob('*') if f.is_file()}
    (p / 'stale.txt').write_text('stale')
    with pytest.raises(ValueError, match='stale|closure'):
        m.build(SOURCE, p)

@pytest.mark.parametrize('case', ['traversal','duplicate_member','symlink','encrypted','missing','extra','corrupt','dimensions','duplicate_row','invalid_id','generic','hash'])
def test_archive_rejects_invalid_input(case):
    m = builder()
    with zipfile.ZipFile(SOURCE) as z:
        entries = [(i, z.read(i)) for i in z.infolist()]
    if case == 'hash':
        with pytest.raises(ValueError): m.validate_archive(b'bad')
        return
    image_index = next(i for i,(n,b) in enumerate(entries) if n.filename.endswith('.png'))
    info, data = entries[image_index]
    if case == 'traversal': entries.append((zipfile.ZipInfo('../escape'), b'x'))
    elif case == 'duplicate_member': entries.append((info, data))
    elif case == 'symlink':
        info.external_attr = (0o120777 << 16); entries[image_index] = (info, data)
    elif case == 'missing': entries.pop(image_index)
    elif case == 'extra': entries.append((zipfile.ZipInfo('extra.png'), data))
    elif case == 'corrupt': entries[image_index] = (info, b'not png')
    elif case == 'dimensions':
        b = io.BytesIO(); Image.new('RGB', (10,10)).save(b, format='PNG'); entries[image_index] = (info,b.getvalue())
    elif case in ('duplicate_row','invalid_id','generic'):
        i = next(i for i,(n,b) in enumerate(entries) if n.filename.endswith('.csv'))
        n,b = entries[i]
        if case == 'duplicate_row': b += b'\r\n' + b.splitlines()[1]
        elif case == 'invalid_id': b = b.replace(b'W02G4-68',b'W99XX-68')
        else: b = b.replace(b'HPK-W7-15', b'LF-LC2-K-UBM')
        entries[i] = (n,b)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for n,b in entries: z.writestr(n,b)
    raw = buf.getvalue()
    if case == 'encrypted':
        raw = bytearray(raw)
        start = raw.index(b'PK\x01\x02'); raw[start+8] |= 1
        raw = bytes(raw)
    with pytest.raises(ValueError):
        m.validate_archive(raw, hashlib.sha256(raw).hexdigest())

def test_frontend_contract_executable():
    js = ROOT / 'hybrid-bbqc/new-hybrids.js'
    assert js.exists(), 'supplied-batch frontend missing'
    program = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
global.document={querySelector:()=>null};global.crypto=require('node:crypto').webcrypto;
require(process.argv[1]);const c=NewHybridsContract;
(async()=>{const raw=fs.readFileSync(process.argv[2]);const m=await c.parseVerified(raw);
assert.equal(m.records.length,35);assert.equal(c.select(m.records,'hpk-w7-4')[0].etroc_serial,'W05E5-30');
assert.equal(c.select(m.records,'W03F7-85').length,0);
for(const change of [m=>m.records.pop(),m=>m.records[0].extra=1,m=>m.records[0].image.uri='../x',m=>m.records[1]=m.records[0],m=>m.records[0].channel=0]){
const bad=JSON.parse(JSON.stringify(m));change(bad);assert.throws(()=>c.validate(bad));}
await assert.rejects(()=>c.parseVerified(Buffer.from('{}')));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node','-e',program,str(js),str(OUT/'manifest.json')],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
