(() => {
  'use strict';
  const DATASET = 'NEW_HYBRIDS_20260911';
  const BASE = `/data/new-hybrids/${DATASET}/`;
  const PIN = 'cc1eae6b36079f6a857e4e4acc6c9addc9ee5851aedd7715029ced47ac50285a';
  const ARCHIVE = '5a428fa82513ec707c7801eb7eb7202cf596113cae6f03b823bef6249b5d59ee';
  const CROSSWALK = Object.fromEntries([
    ['W02G4','2',[44,45,49,50,51,55,60,63,64,66,67,68,70,78,79,80,81,82]],
    ['W03F7','3',[75,76,77,78,79,80,81,83]],
    ['W05E5','5',[24,30,36,38,39,41,64,68,75]]
  ].flatMap(([wafer,prefix,suffixes]) => suffixes.map(s => [`${wafer}-${s}`,`좌우반전/${prefix}-${s}.png`])));
  const GENERIC = ['W02G4-68','W02G4-50','W02G4-64','W02G4-66','W02G4-79'];
  const exact = (o, keys) => o && typeof o === 'object' && !Array.isArray(o) && Object.keys(o).length === keys.length && keys.every(k => Object.hasOwn(o,k));
  const hash = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v => v.toString(16).padStart(2,'0')).join('');
  const digest = s => typeof s === 'string' && /^[a-f0-9]{64}$/.test(s);
  function validate(m) {
    const fail = () => { throw Error('Supplied batch publication invalid'); };
    if (!exact(m,['schema_version','dataset_id','archive_sha256','archive_bytes','original_csv_sha256','corrected_csv_sha256','corrections','excluded_etroc_serials','record_count','records']) || m.schema_version !== 1 || m.dataset_id !== DATASET || m.archive_sha256 !== ARCHIVE || m.archive_bytes !== 35022225 || !digest(m.original_csv_sha256) || !digest(m.corrected_csv_sha256) || m.record_count !== 35 || !Array.isArray(m.records) || m.records.length !== 35 || JSON.stringify(m.excluded_etroc_serials) !== '["W03F7-85"]') fail();
    if (!exact(m.corrections,['version','W05E5-30','W03F7-85']) || m.corrections.version !== '20260911-user-approved-v1' || m.corrections['W05E5-30'] !== 'LGAD ID corrected to HPK-W7-4' || m.corrections['W03F7-85'] !== 'Not bump-bonded, excluded from bonded batch; retained in pre-bonding cohort') fail();
    const seen = new Set(), lgads = new Set();
    for (const r of m.records) {
      if (!exact(r,['etroc_serial','lgad_label','individual_lgad_serial_supplied','channel','source_notes','original_fields','image']) || !Object.hasOwn(CROSSWALK,r.etroc_serial) || seen.has(r.etroc_serial) || r.channel !== null || typeof r.source_notes !== 'string' || !/^solder bump missing: [0-6]개 \(optical inspection 기준\)(; shear force test에 사용됨)?$/.test(r.source_notes)) fail();
      seen.add(r.etroc_serial);
      const generic = GENERIC.includes(r.etroc_serial);
      if (r.individual_lgad_serial_supplied !== !generic || (generic ? r.lgad_label !== 'LF-LC2-K-UBM' : !/^(HPK-W7|FBK-LF-W1[45])-[0-9]+$/.test(r.lgad_label) || lgads.has(r.lgad_label))) fail();
      lgads.add(r.lgad_label);
      if (r.etroc_serial === 'W05E5-30' && r.lgad_label !== 'HPK-W7-4') fail();
      const f = r.original_fields, i = r.image;
      if (!exact(f,['LGAD ID','ETROC ID','연결 채널','비고']) || f['ETROC ID'] !== r.etroc_serial || f['연결 채널'] !== '' || f['비고'] !== r.source_notes || f['LGAD ID'] !== (r.etroc_serial === 'W05E5-30' ? '' : r.lgad_label)) fail();
      if (!exact(i,['uri','sha256','bytes','width','height','source_member']) || !digest(i.sha256) || i.uri !== `images/${i.sha256}.png` || i.source_member !== CROSSWALK[r.etroc_serial] || i.width !== 1142 || i.height !== 1142 || !Number.isSafeInteger(i.bytes) || i.bytes < 1 || i.bytes > 4000000) fail();
    }
    return m;
  }
  async function parseVerified(bytes) {
    if (bytes.byteLength > 100000 || await hash(bytes) !== PIN) throw Error('Manifest integrity mismatch');
    return validate(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)));
  }
  const select = (records, query) => records.filter(r => `${r.etroc_serial} ${r.lgad_label}`.toLowerCase().includes(query.trim().toLowerCase()));
  function node(tag, text, className) {
    const e = document.createElement(tag); if (text !== undefined) e.textContent = text;
    if (className) e.className = className; return e;
  }
  function createViewer() {
    const dialog = node('dialog',undefined,'new-hybrids-dialog');
    const heading = node('h2'); heading.id = 'new-hybrids-dialog-title'; dialog.setAttribute('aria-labelledby',heading.id); dialog.setAttribute('data-new-hybrid-dialog','');
    const closeButton = node('button','Close supplied image'); closeButton.type = 'button'; closeButton.setAttribute('data-new-hybrid-close','');
    const status = node('p'); status.setAttribute('role','status'); status.setAttribute('data-new-hybrid-status','');
    const content = node('div'); dialog.append(heading,closeButton,status,content); document.body.append(dialog);
    let generation = 0, controller = null, trigger = null;
    const urls = new Set();
    const release = url => { if (urls.delete(url)) URL.revokeObjectURL(url); };
    function cleanup() { ++generation; controller?.abort(); controller = null; urls.forEach(release); content.replaceChildren(); }
    function close() { const old = trigger; trigger = null; cleanup(); if (dialog.open) dialog.close(); if (old?.isConnected) old.focus(); }
    closeButton.addEventListener('click',close);
    dialog.addEventListener('cancel', e => { e.preventDefault(); close(); });
    dialog.addEventListener('close', () => { if (!dialog.open) { const old = trigger; trigger = null; cleanup(); if(old?.isConnected) old.focus(); } });
    dialog.addEventListener('click', e => { const b = dialog.getBoundingClientRect(); if(e.target === dialog && (e.clientX < b.left || e.clientX > b.right || e.clientY < b.top || e.clientY > b.bottom)) close(); });
    async function open(record, opener) {
      close(); trigger = opener; const token = ++generation; controller = new AbortController();
      const current = () => token === generation && dialog.open;
      heading.textContent = `${record.etroc_serial} · ${record.lgad_label} · Supplied image`;
      status.textContent = 'Verifying supplied image…'; dialog.showModal(); closeButton.focus();
      let url = null, displayed = false;
      try {
        const response = await fetch(BASE + record.image.uri,{credentials:'same-origin',cache:'no-store',signal:controller.signal});
        if (!current()) return;
        if (!response.ok) throw Error('Image unavailable');
        const bytes = await response.arrayBuffer(); if (!current()) return;
        if (bytes.byteLength !== record.image.bytes || await hash(bytes) !== record.image.sha256) throw Error('Image integrity mismatch');
        if (!current()) return;
        url = URL.createObjectURL(new Blob([bytes],{type:'image/png'})); urls.add(url);
        const image = node('img'); image.src = url; image.alt = `${record.etroc_serial}: verified supplied image, original orientation`; image.width = 1142; image.height = 1142;
        await image.decode(); if (!current()) return;
        if (image.naturalWidth !== 1142 || image.naturalHeight !== 1142) throw Error('Image dimensions mismatch');
        image.setAttribute('data-new-hybrid-image',''); content.replaceChildren(image); displayed = true;
        status.textContent = 'Verified supplied image · original bytes and orientation · read-only. Coordinate mapping not established.';
      } catch(error) { if(current()) { content.replaceChildren(); status.textContent = 'Supplied image unavailable — integrity or decoding failed. Close and reopen to retry.'; } }
      finally { if(url && !displayed) release(url); }
    }
    return {open,close};
  }
  function renderCard(r, viewer) {
    const card = node('article',undefined,'new-hybrids-card'); card.dataset.newHybridEtroc = r.etroc_serial;
    const button = node('button',undefined,'new-hybrids-image'); button.type = 'button'; button.setAttribute('data-new-hybrid-image-button',''); button.setAttribute('aria-label',`${r.etroc_serial}: open supplied image`); button.setAttribute('aria-haspopup','dialog');
    const img = node('img'); img.src = BASE + r.image.uri; img.alt = `${r.etroc_serial} · supplied image thumbnail`; img.loading = 'lazy'; img.width = 1142; img.height = 1142;
    img.addEventListener('error',() => button.replaceChildren(node('span','Supplied image unavailable — open to retry')));
    button.append(img); button.addEventListener('click',() => { void viewer.open(r,button); });
    card.append(button,node('h3',r.etroc_serial),node('p',r.lgad_label));
    if (!r.individual_lgad_serial_supplied) card.append(node('p','Individual LGAD serial not supplied (generic label)'));
    card.append(node('p',`Connection channel: ${r.channel === null ? 'Not supplied' : r.channel}`),node('p',`Pre-bonding optical: ${r.source_notes.split(';')[0]} (supplied CSV)`));
    if (r.source_notes.includes(';')) card.append(node('p',`Supplied usage note: ${r.source_notes.split(';')[1].trim()}`));
    const reviewed = node('button','Open current reviewed pre-bonding montage'); reviewed.type = 'button'; reviewed.setAttribute('data-new-hybrid-reviewed-button','');
    const availability = node('p'); availability.setAttribute('role','status');
    reviewed.addEventListener('click',() => {
      const request = new CustomEvent('etroc-results-open-request',{cancelable:true,detail:{etroc_serial:r.etroc_serial,trigger:reviewed}});
      globalThis.dispatchEvent(request);
      availability.textContent = request.defaultPrevented ? '' : 'Current reviewed pre-bonding results unavailable. No original algorithm fallback.';
    }); card.append(reviewed,availability); return card;
  }
  globalThis.NewHybridsContract = Object.freeze({validate,parseVerified,select,createViewer,renderCard});
  const root = document.querySelector('[data-new-hybrids]'); if (!root) return;
  const status = root.querySelector('[data-new-hybrids-status]'), cards = root.querySelector('[data-new-hybrids-cards]'), search = root.querySelector('[data-new-hybrids-search]');
  (async () => {
    try {
      const response = await fetch(BASE+'manifest.json',{credentials:'same-origin',cache:'no-store'});
      if (!response.ok) throw Error('Manifest unavailable');
      const manifest = await parseVerified(await response.arrayBuffer());
      const viewer = createViewer();
      const apply = () => { const visible = select(manifest.records,search.value); cards.replaceChildren(...visible.map(r => renderCard(r,viewer))); status.textContent = `${visible.length} / 35 bonded specimens · 35 supplied images · separate from the 72 registered hybrids`; };
      search.disabled = false; search.addEventListener('input',apply); apply();
      const sources = root.querySelector('[data-new-hybrids-sources]');
      for(const [file,label] of [['source-original.csv','Original supplied CSV'],['source-corrected.csv','Corrected source CSV']]) { const a = node('a',label); a.href = BASE+file; a.download = file; sources.append(a); }
      sources.append(node('p',`${manifest.corrections['W05E5-30']}. W03F7-85: ${manifest.corrections['W03F7-85']}. Directory 좌우반전 records source provenance; images are not flipped again. No new Construction DB registrations.`));
    } catch(error) { cards.replaceChildren(); search.disabled = true; status.textContent = 'New supplied batch unavailable — publication could not be verified. Existing registered cohort is unaffected.'; }
  })();
})();
