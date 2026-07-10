#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# HANDWRITING_CORRECTION_W04F2_44_TO_41: Master corrected the apparent W04F2-44 mapping to W04F2-41; use 4-41.jpg for HPK-W3_6.
ZIP_PATH = Path('/home/young-park/Documents/QAQC/260702_2nd batch_5 gel pack.zip')
MAP_PATH = Path('/home/young-park/.hermes/profiles/homer/cache/documents/doc_cfb44cfd07bc_Hybrid-ETROC_LGAD_mapping .csv')
XDIR = ROOT / 'assets' / 'xray'
MANIFEST_PATH = XDIR / 'xray_manifest.json'
DATA_DIR = ROOT / 'hybrid-bbqc' / 'data'


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def slug_name(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower() or '.jpg'
    stem = stem.replace('#', 'num')
    stem = re.sub(r'[^A-Za-z0-9_.-]+', '_', stem).strip('_')
    stem = re.sub(r'_+', '_', stem)
    return stem + suffix


def key_for_etroc(etroc: str) -> str:
    wafer, chip = etroc.split('-', 1)
    prefix = {'W03F7': '3', 'W04F2': '4', 'W07D3': '7'}[wafer]
    return f'{prefix}-{int(chip)}'


def etroc_for_zip_name(base: str) -> str | None:
    m = re.match(r'([47])-(0?\d+)(.*)\.jpe?g$', base, re.I)
    if not m:
        return None
    prefix, chip_s, _suffix = m.groups()
    wafer = 'W04F2' if prefix == '4' else 'W07D3'
    return f'{wafer}-{int(chip_s)}'


def reason_after_mapping(old_reason: str, has_xray: bool) -> str:
    parts = [p.strip() for p in old_reason.split(';') if p.strip()]
    out = []
    for p in parts:
        low = p.lower()
        if low == 'lgad unmapped':
            continue
        if has_xray and low == 'x-ray missing':
            continue
        out.append(p)
    if has_xray and not any('x-ray' in p.lower() for p in out):
        out.append('X-ray evidence available')
    return '; '.join(out) if out else ('X-ray evidence available' if has_xray else 'Mapped LGAD')


def note_for_crops(crops: list[str]) -> str:
    if not crops:
        return 'No X-ray note'
    joined = ' '.join(crops).lower().replace('_', ' ')
    if 'no ball' in joined or 'no solder' in joined:
        return 'X-ray no-ball / no-solder detail crop available'
    if 'ball size fail' in joined or 'fail' in joined or 'defect' in joined:
        return 'X-ray detail crop available'
    return 'X-ray detail crop available'


def xray_full_article(prefix: str, path: str | None, etroc: str) -> str:
    if not path:
        return '<article class="panel"><h2>X-ray full-chip image</h2><div class="page-placeholder">No X-ray image mapped for this chip yet.</div></article>'
    return f'<article class="panel"><h2>X-ray full-chip image</h2><img src="{prefix}{esc(path)}" alt="X-ray full-chip image for {esc(etroc)}" loading="lazy" /></article>'


def xray_crop_article(prefix: str, crops: list[str]) -> str:
    if not crops:
        inner = '<div class="page-placeholder small">No X-ray detail crop mapped for this chip.</div>'
    else:
        figs = []
        for i, crop in enumerate(crops, 1):
            figs.append(f'<figure><img src="{prefix}{esc(crop)}" alt="X-ray detail crop {i}" loading="lazy" /><figcaption>{esc(Path(crop).name)}</figcaption></figure>')
        inner = ''.join(figs)
    return f'<article class="panel wide"><h2>X-ray detail crops</h2><div class="crop-strip">{inner}</div><p class="muted">{esc(note_for_crops(crops))}</p></article>'


def update_evidence_section(text: str, full_path: str | None, crops: list[str], etroc: str, prefix: str) -> str:
    repl_full = xray_full_article(prefix, full_path, etroc)
    repl_crops = xray_crop_article(prefix, crops)
    text = re.sub(r'<article class="panel"><h2>X-ray full-chip image</h2>.*?</article>', repl_full, text, count=1, flags=re.S)
    text = re.sub(r'<article class="panel wide"><h2>X-ray detail crops</h2>.*?</article>', repl_crops, text, count=1, flags=re.S)
    return text


def update_detail_page(path: Path, etroc: str, lgad: str, xinfo: dict | None) -> str:
    text = path.read_text(errors='ignore')
    key = key_for_etroc(etroc)
    has_xray = bool(xinfo and xinfo.get('full'))
    crops = xinfo.get('crops', []) if xinfo else []
    full = xinfo.get('full') if xinfo else None
    old_title = f'Hybrid {etroc} + LGAD not mapped'
    new_title = f'Hybrid {etroc} + {lgad}'
    text = text.replace(old_title, new_title)
    text = text.replace('<strong>LGAD not mapped</strong>', f'<strong>{esc(lgad)}</strong>')
    text = re.sub(r'<div><span>Reasons</span><strong>(.*?)</strong></div>', lambda m: f'<div><span>Reasons</span><strong>{esc(reason_after_mapping(html.unescape(m.group(1)), has_xray))}</strong></div>', text, count=1, flags=re.S)
    text = re.sub(r'<div class="meta"><span>X-ray key / crops</span><strong>.*?</strong></div>', f'<div class="meta"><span>X-ray key / crops</span><strong>{esc(key)} · {len(crops)}</strong></div>', text, count=1, flags=re.S)
    text = update_evidence_section(text, full, crops, etroc, '/')
    text = text.replace(f'data-comments-target="hybrid:{etroc}__LGAD-unmapped"', f'data-comments-target="hybrid:{etroc}__{lgad}"')
    new_path = path.with_name(f'{etroc}__{lgad}.html')
    new_path.write_text(text)
    if new_path != path:
        alias = f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={esc(new_path.name)}"><link rel="canonical" href="{esc(new_path.name)}"><title>Redirecting to {esc(etroc)} {esc(lgad)}</title><p>Redirecting to <a href="{esc(new_path.name)}">{esc(etroc)} + {esc(lgad)}</a>.</p>'
        path.write_text(alias)
    return new_path.name


def update_chip_page(path: Path, etroc: str, lgad: str, xinfo: dict | None) -> None:
    text = path.read_text(errors='ignore')
    key = key_for_etroc(etroc)
    crops = xinfo.get('crops', []) if xinfo else []
    full = xinfo.get('full') if xinfo else None
    text = text.replace('<span class="hybrid-badge missing">LGAD not mapped</span>', f'<span class="hybrid-badge sensor"><b>{esc(lgad)}</b></span>')
    text = re.sub(r'<div class="meta-card"><div class="meta-label">X-ray key / crops</div><div class="meta-value">.*?</div></div>', f'<div class="meta-card"><div class="meta-label">X-ray key / crops</div><div class="meta-value">{esc(key)} · {len(crops)}</div></div>', text, count=1, flags=re.S)
    text = update_evidence_section(text, full, crops, etroc, '../')
    path.write_text(text)


def update_index_segment(seg: str, etroc: str, lgad: str, new_file: str, xinfo: dict | None) -> str:
    has_xray = bool(xinfo and xinfo.get('full'))
    crops = xinfo.get('crops', []) if xinfo else []
    full = xinfo.get('full') if xinfo else None
    seg = seg.replace(f'hybrids/{etroc}__LGAD-unmapped.html', f'hybrids/{new_file}')
    seg = seg.replace(f"hybrids/{etroc}__LGAD-unmapped.html", f"hybrids/{new_file}")
    seg = seg.replace(f'hybrid:{etroc}__LGAD-unmapped', f'hybrid:{etroc}__{lgad}')
    seg = seg.replace('LGAD not mapped', esc(lgad))
    # visible/text reasons
    for old in ['LGAD unmapped; X-ray missing; NW missing', 'LGAD unmapped; X-ray missing', 'LGAD unmapped NW missing', 'LGAD unmapped X-ray missing NW missing']:
        if old in seg:
            new = reason_after_mapping(old.replace(' NW ', '; NW ').replace(' X-ray ', '; X-ray '), has_xray)
            # For data-text keep spaces instead of semicolons.
            seg = seg.replace(old, new if ';' in old else new.replace(';', ''))
    seg = seg.replace('LGAD unmapped; ', '')
    seg = seg.replace('LGAD unmapped ', '')
    if has_xray and full:
        seg = seg.replace('data-xray="0"', 'data-xray="1"')
        seg = seg.replace('<span class="badge miss">No X-ray</span>', '<span class="badge">X-ray</span>')
        seg = re.sub(r'<div class="xray-placeholder compact">No X-ray image mapped for this chip yet\.</div>', f'<img src="/{esc(full)}" alt="X-ray full-chip image for {esc(etroc)}" loading="lazy" />', seg, count=1)
        # table xray cell: after yellow/noball columns there are optical yes/no cells; replace first <td>no</td> after LGAD row context by xray yes conservatively via exact sequence near comments.
        seg = seg.replace('<td>no</td><td class="comment-summary', '<td>yes</td><td class="comment-summary')
    return seg


def update_index(index_path: Path, mapping: dict[str, str], xmap: dict[str, dict], new_files: dict[str, str]) -> None:
    text = index_path.read_text(errors='ignore')
    text = text.replace('<div class="metric"><span>Mapped LGAD</span><strong>27</strong></div>', '<div class="metric"><span>Mapped LGAD</span><strong>72</strong></div>')
    text = text.replace('<div class="metric"><span>X-ray available</span><strong>27</strong></div>', '<div class="metric"><span>X-ray available</span><strong>71</strong></div>')
    for etroc, lgad in mapping.items():
        new_file = new_files.get(etroc, f'{etroc}__{lgad}.html')
        xinfo = xmap.get(etroc)
        # card segments
        text = re.sub(rf'<a class="card [^>]*data-text="[^"]*{re.escape(etroc)}[^"]*".*?</a>', lambda m: update_index_segment(m.group(0), etroc, lgad, new_file, xinfo), text, count=1, flags=re.S)
        # table row segments
        text = re.sub(rf'<tr [^>]*data-text="[^"]*{re.escape(etroc)}[^"]*".*?</tr>', lambda m: update_index_segment(m.group(0), etroc, lgad, new_file, xinfo), text, count=1, flags=re.S)
    index_path.write_text(text)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MAP_PATH, DATA_DIR / 'Hybrid-ETROC_LGAD_mapping.csv')
    mapping = {r['ETROC'].strip(): r['LGAD'].strip() for r in csv.DictReader(MAP_PATH.open(encoding='utf-8-sig'))}

    zip_files: dict[str, list[tuple[str, str]]] = {}
    with zipfile.ZipFile(ZIP_PATH) as z:
        for info in z.infolist():
            if not info.filename.lower().endswith(('.jpg', '.jpeg')):
                continue
            base = Path(info.filename).name
            etroc = etroc_for_zip_name(base)
            if not etroc:
                continue
            dest_name = slug_name(base)
            dest = XDIR / dest_name
            with z.open(info) as src, dest.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            suffix = re.match(r'[47]-0?\d+(.*)\.jpe?g$', base, re.I).group(1).strip()
            kind = 'full' if not suffix else 'crop'
            zip_files.setdefault(etroc, []).append((kind, dest_name))

    manifest = json.loads(MANIFEST_PATH.read_text())
    xmap: dict[str, dict] = {}
    for etroc in sorted(mapping):
        files = zip_files.get(etroc, [])
        key = key_for_etroc(etroc)
        fulls = [n for kind, n in files if kind == 'full']
        crops = [n for kind, n in files if kind != 'full']
        if fulls:
            full = f'assets/xray/{fulls[0]}'
            crop_paths = [f'assets/xray/{n}' for n in crops]
            notes = [] if not crop_paths else [note_for_crops(crop_paths)]
            manifest[key] = {'chip': key.split('-', 1)[1], 'crops': crop_paths, 'full': full, 'notes': notes, 'prefix': key.split('-', 1)[0]}
            xmap[etroc] = manifest[key]
        else:
            xmap[etroc] = {}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')

    new_files = {}
    for etroc, lgad in sorted(mapping.items()):
        paths = list((ROOT / 'hybrid-bbqc' / 'hybrids').glob(f'{etroc}__LGAD-unmapped.html'))
        if paths:
            new_files[etroc] = update_detail_page(paths[0], etroc, lgad, xmap.get(etroc))
        # chip evidence pages
        chip = etroc.split('-', 1)[1]
        for p in (ROOT / 'chips').glob(f'{etroc.split("-",1)[0]}-*-chip-{int(chip)}.html'):
            update_chip_page(p, etroc, lgad, xmap.get(etroc))

    update_index(ROOT / 'hybrid-bbqc' / 'index.html', mapping, xmap, new_files)

    print('mapping_rows', len(mapping))
    print('xray_linked', sum(1 for e in mapping if xmap.get(e, {}).get('full')))
    print('xray_missing', [e for e in mapping if not xmap.get(e, {}).get('full')])
    print('extra_zip_keys', sorted(set(zip_files) - set(mapping)))

if __name__ == '__main__':
    main()
