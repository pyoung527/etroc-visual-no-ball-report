"""Deterministic, byte-preserving publication of the approved supplied batch."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile

from PIL import Image

DATASET = 'NEW_HYBRIDS_20260911'
ARCHIVE_SHA256 = '5a428fa82513ec707c7801eb7eb7202cf596113cae6f03b823bef6249b5d59ee'
SOURCE = Path('/home/young-park/.hermes/profiles/schuman/downloads/onedrive-new-hybrids/new_hybrids.zip')
OUTPUT = Path(__file__).resolve().parents[1] / 'hybrid-bbqc/data/new-hybrids' / DATASET
FIELDS = ['LGAD ID', 'ETROC ID', '연결 채널', '비고']
CROSSWALK = {f'{wafer}-{suffix}': f'좌우반전/{prefix}-{suffix}.png'
             for wafer, prefix, suffixes in [
                 ('W02G4', '2', [44,45,49,50,51,55,60,63,64,66,67,68,70,78,79,80,81,82]),
                 ('W03F7', '3', [75,76,77,78,79,80,81,83]),
                 ('W05E5', '5', [24,30,36,38,39,41,64,68,75])]
             for suffix in suffixes}
GENERIC = {'W02G4-68','W02G4-50','W02G4-64','W02G4-66','W02G4-79'}
CORRECTIONS = {'version': '20260911-user-approved-v1', 'W05E5-30': 'LGAD ID corrected to HPK-W7-4',
               'W03F7-85': 'Not bump-bonded, excluded from bonded batch; retained in pre-bonding cohort'}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def validate_archive(raw, expected_sha=ARCHIVE_SHA256):
    if sha(raw) != expected_sha:
        raise ValueError('archive SHA256 mismatch')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = z.infolist()
            names = [i.filename for i in members]
            expected = {'좌우반전/', 'lgad_etroc_pairs.csv', *CROSSWALK.values()}
            if len(names) != len(set(names)) or set(names) != expected:
                raise ValueError('archive member closure mismatch')
            for i in members:
                if i.flag_bits & 1 or stat.S_ISLNK(i.external_attr >> 16) or i.file_size > 4_000_000:
                    raise ValueError('unsafe archive member')
            payloads = {i.filename: z.read(i) for i in members if not i.is_dir()}
        original = payloads['lgad_etroc_pairs.csv']
        reader = csv.DictReader(io.StringIO(original.decode('utf-8-sig')))
        if reader.fieldnames != FIELDS:
            raise ValueError('CSV fields mismatch')
        rows = list(reader)
        if len(rows) != 36 or {r['ETROC ID'] for r in rows} != {*CROSSWALK, 'W03F7-85'}:
            raise ValueError('CSV row identity mismatch')
        lgads = set()
        for row in rows:
            if set(row) != set(FIELDS) or any(not isinstance(v, str) for v in row.values()) or row['연결 채널'] != '':
                raise ValueError('CSV row fields mismatch')
            etroc, lgad = row['ETROC ID'], row['LGAD ID']
            if not re.fullmatch(r'solder bump missing: [0-6]개 \(optical inspection 기준\)(; shear force test에 사용됨)?', row['비고']):
                raise ValueError('CSV note mismatch')
            if etroc in GENERIC:
                if lgad != 'LF-LC2-K-UBM': raise ValueError('generic label mismatch')
            elif etroc in {'W03F7-85','W05E5-30'}:
                if lgad != '': raise ValueError('correction precondition mismatch')
            elif not re.fullmatch(r'(HPK-W7|FBK-LF-W1[45])-[0-9]+', lgad) or lgad in lgads:
                raise ValueError('LGAD identity mismatch')
            lgads.add(lgad)
        for member in CROSSWALK.values():
            with Image.open(io.BytesIO(payloads[member])) as im:
                if im.format != 'PNG' or im.size != (1142,1142): raise ValueError('PNG dimensions or format mismatch')
                im.verify()
            with Image.open(io.BytesIO(payloads[member])) as im: im.load()
        return rows, payloads
    except (zipfile.BadZipFile, RuntimeError, OSError, UnicodeError, csv.Error) as error:
        raise ValueError('invalid archive payload') from error

def build(source=SOURCE, output=OUTPUT):
    raw = Path(source).read_bytes()
    rows, payloads = validate_archive(raw)
    files = {'source-original.csv': payloads['lgad_etroc_pairs.csv']}
    corrected = []
    records = []
    for row in rows:
        etroc = row['ETROC ID']
        new = dict(row)
        if etroc == 'W05E5-30': new['LGAD ID'] = 'HPK-W7-4'
        if etroc == 'W03F7-85': new['비고'] += '; ' + CORRECTIONS[etroc]
        corrected.append(new)
        if etroc not in CROSSWALK: continue
        member = CROSSWALK[etroc]
        image = payloads[member]
        digest = sha(image)
        uri = f'images/{digest}.png'
        files[uri] = image
        records.append({'etroc_serial': etroc, 'lgad_label': new['LGAD ID'], 'individual_lgad_serial_supplied': etroc not in GENERIC,
                        'channel': None, 'source_notes': row['비고'], 'original_fields': row,
                        'image': {'uri': uri, 'sha256': digest, 'bytes': len(image), 'width': 1142, 'height': 1142, 'source_member': member}})
    csv_out = io.StringIO(newline='')
    writer = csv.DictWriter(csv_out, fieldnames=FIELDS, lineterminator='\r\n')
    writer.writeheader(); writer.writerows(corrected)
    files['source-corrected.csv'] = csv_out.getvalue().encode('utf-8-sig')
    manifest = {'schema_version': 1, 'dataset_id': DATASET, 'archive_sha256': sha(raw), 'archive_bytes': len(raw),
                'original_csv_sha256': sha(files['source-original.csv']), 'corrected_csv_sha256': sha(files['source-corrected.csv']),
                'corrections': CORRECTIONS, 'excluded_etroc_serials': ['W03F7-85'], 'record_count': 35,
                'records': sorted(records, key=lambda r: r['etroc_serial'])}
    files['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    files['SHA256SUMS'] = ''.join(f'{sha(b)}  {name}\n' for name,b in sorted(files.items())).encode()
    output = Path(output)
    if output.exists():
        existing = {str(f.relative_to(output)): f.read_bytes() for f in output.rglob('*') if f.is_file()}
        if existing != files: raise ValueError('stale output or asset closure mismatch; use a fresh output directory')
        return manifest
    output.mkdir(parents=True)
    for name, data in files.items():
        path = output / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.source, args.output)
    print(f'{DATASET}: 35 records; manifest SHA256 {sha((args.output / "manifest.json").read_bytes())}')
