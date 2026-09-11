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
      translateNotes(r.source_notes);
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
  function translateNotes(source) {
    const match = /^solder bump missing: (0|1|2|6)개 \(optical inspection 기준\)(; shear force test에 사용됨)?$/.exec(source);
    if (!match || (match[1] === '6' && !match[2]) || (match[2] && !['2','6'].includes(match[1]))) throw Error('Supplied note translation unavailable');
    return `Missing solder bumps: ${match[1]} (based on optical inspection).${match[2] ? ' Used for shear force testing.' : ''}`;
  }
  function commentTarget(record) {
    if (!record || !Object.hasOwn(CROSSWALK,record.etroc_serial)) throw Error('Unknown supplied pair');
    return `hybrid-comparison:${DATASET}:${record.etroc_serial}`;
  }
  function createComments() {
    const root=node('section',undefined,'new-hybrids-comments'); root.setAttribute('data-comparison-comments','');
    const hook=(tag,key,text)=>{const e=node(tag,text);e.setAttribute(`data-comparison-comments-${key}`,'');return e;};
    const list=hook('div','list'),form=hook('form','form'),body=hook('textarea','body'),save=hook('button','save','Save comment'),message=hook('p','message'),refresh=hook('button','refresh','Refresh comments'),auth=node('p');
    body.value='';body.maxLength=2000;body.rows=3;body.setAttribute('aria-label','Comment (maximum 2000 characters)');save.type='submit';refresh.type='button';message.setAttribute('role','status');
    form.append(body,save);root.append(node('h3','Comments'),node('p','Latest comments (up to 100)'),auth,list,form,message,refresh,node('p','Unsaved drafts remain only while this page stays open. The server trims outer whitespace.'));
    const states=new Map();let activeTarget=null,authGeneration=0;
    const state=t=>{if(!states.has(t))states.set(t,{draft:'',rows:null,read:0,loading:false,auth:false,authText:'Checking sign-in…',phase:'idle',receipt:null,submitted:null,message:''});return states.get(t);};
    const validRow=(r,t)=>r&&Number.isSafeInteger(r.id)&&r.id>0&&r.target===t&&typeof r.body==='string'&&r.body.length>0&&Array.from(r.body).length<=2000&&['note','review','pass','fail','follow-up'].includes(r.status)&&typeof r.author_display==='string'&&Number.isSafeInteger(r.created_at)&&Number.isSafeInteger(r.updated_at);
    function render(t) {
      if(t!==activeTarget)return;const s=state(t);body.value=s.draft;auth.textContent=s.authText;message.textContent=s.message;
      body.disabled=!s.auth||s.phase!=='idle';save.disabled=body.disabled||!s.draft.trim()||Array.from(s.draft).length>2000;refresh.disabled=s.loading||s.phase==='posting';
      list.textContent='';list.replaceChildren();
      if(s.rows===null)list.textContent=s.loading?'Loading comments…':'Comments unavailable — refresh to retry.';
      else if(!s.rows.length)list.textContent='No comments yet.';
      else for(const r of s.rows){const item=node('article');item.append(node('p',`${r.author_display} · ${new Date(r.created_at*1000).toLocaleString()} · ${r.status}`),node('p',r.body));list.append(item);}
    }
    async function read(t) {
      const s=state(t),version=++s.read;s.loading=true;render(t);
      try {
        const response=await fetch(`/api/comments?target=${encodeURIComponent(t)}`,{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error('read');const rows=await response.json();
        if(!Array.isArray(rows)||rows.length>100||!rows.every(r=>validRow(r,t)&&typeof r.can_edit==='boolean')||new Set(rows.map(r=>r.id)).size!==rows.length)throw Error('shape');
        if(version!==s.read)return;s.rows=rows.sort((a,b)=>b.created_at-a.created_at||b.id-a.id);
        if(s.receipt){const receipt=s.receipt;const found=rows.some(r=>['id','target','body','status','author_display','created_at','updated_at'].every(k=>r[k]===receipt[k]));
          if(found){if(s.draft===s.submitted)s.draft='';s.receipt=null;s.submitted=null;s.phase='idle';s.message='Saved — verified in comments.';}
          else s.message='Save receipt received, but read-back not verified. Refresh comments; do not resubmit.';
        }
      }catch(error){if(version===s.read){s.rows=null;if(s.receipt)s.message='Save receipt received; read-back unavailable. Refresh comments; do not resubmit.';}}
      finally{if(version===s.read){s.loading=false;render(t);}}
    }
    async function loadAuth(t){const s=state(t),version=++authGeneration;s.auth=false;s.authText='Checking sign-in…';render(t);try{const r=await fetch('/api/me',{credentials:'same-origin',cache:'no-store'});if(!r.ok)throw Error('auth');const me=await r.json();if(version!==authGeneration)return;s.auth=me.authenticated===true&&me.user&&typeof(me.user.display||me.user.user)==='string';s.authText=s.auth?`Signed in as ${me.user.display||me.user.user}`:'Sign in with CERN SSO to add comments.';}catch(error){if(version!==authGeneration)return;s.auth=false;s.authText='Sign-in unavailable — writing disabled.';}render(t);}
    body.addEventListener('input',()=>{if(activeTarget){state(activeTarget).draft=body.value;render(activeTarget);}});
    refresh.addEventListener('click',()=>{if(activeTarget){void read(activeTarget);void loadAuth(activeTarget);}});
    form.addEventListener('submit',async event=>{
      event.preventDefault();const t=activeTarget;if(!t)return;const s=state(t);
      if(!s.auth||s.phase!=='idle'||!s.draft.trim()||Array.from(s.draft).length>2000)return;
      const draft=s.draft,expected=draft.trim();s.phase='posting';s.submitted=draft;s.message='Saving…';++s.read;s.loading=false;render(t);
      try{
        const response=await fetch('/api/comments',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:t,body:draft,status:'note'})});
        if([400,401,403,404,413,422,429].includes(response.status)){s.phase='idle';s.message='Comment rejected; draft retained. Check sign-in and comment length before trying again.';if([401,403].includes(response.status)){s.auth=false;s.authText='Sign in with CERN SSO to add comments.';}render(t);return;}
        if(response.status!==201)throw Error('unknown');const receipt=await response.json();
        if(!validRow(receipt,t)||receipt.body!==expected||receipt.status!=='note')throw Error('receipt');
        s.receipt=receipt;s.phase='receipt';s.message='Receipt received — verifying comments…';render(t);await read(t);
      }catch(error){s.phase='unknown';s.message='Save status unknown; refresh/check comments before resubmitting. No automatic retry. This draft is locked to prevent duplicates; reload only after checking the thread.';render(t);}
    });
    return {root,open(record){activeTarget=commentTarget(record);render(activeTarget);void loadAuth(activeTarget);void read(activeTarget);},close(){activeTarget=null;++authGeneration;}};
  }
  function createViewer() {
    const dialog = node('dialog',undefined,'new-hybrids-dialog');
    const heading = node('h2'); heading.id = 'new-hybrids-dialog-title'; dialog.setAttribute('aria-labelledby',heading.id); dialog.setAttribute('data-new-hybrid-dialog','');
    const closeButton = node('button','Close'); closeButton.type = 'button'; closeButton.setAttribute('data-new-hybrid-close','');
    const header = node('header',undefined,'new-hybrids-dialog-header'); header.append(heading,closeButton);
    const notes = node('p',undefined,'new-hybrids-comparison-notes');
    const status = node('p'); status.setAttribute('role','status'); status.setAttribute('data-new-hybrid-status','');
    const content = node('div',undefined,'new-hybrids-comparison');
    const body=node('div',undefined,'new-hybrids-comparison-body');body.setAttribute('data-comparison-body','');
    const comments=createComments();body.append(notes,status,content,comments.root);dialog.append(header,body);document.body.append(dialog);
    let generation = 0, trigger = null, active = null;
    const urls = new Set();
    const release = url => { if (urls.delete(url)) URL.revokeObjectURL(url); };
    const summary = () => { status.textContent = panes.every(p => p.ready) ? 'Both images verified · independent coordinates, no grid correspondence implied. H = human; A = algorithm; ? = pending.' : 'Comparison incomplete — each pane reports its verification state.'; };
    function pane(kind,title,width,height) {
      const root = node('section',undefined,'new-hybrids-pane'); root.setAttribute('data-comparison-pane',kind);
      const label = node('h3',title), state = node('p'); state.setAttribute('role','status'); state.setAttribute('data-comparison-status',kind); state.setAttribute(`data-new-hybrid-${kind}-status`,'');
      const controls = node('div',undefined,'new-hybrids-zoom');
      const scroll = node('div',undefined,'new-hybrids-pane-scroll'); scroll.setAttribute('tabindex','0'); scroll.setAttribute('role','region'); scroll.setAttribute('aria-label',`${title}: independently scrollable image`); scroll.setAttribute('data-comparison-scroll',kind);
      const stage = node('div',undefined,'new-hybrids-pane-stage'); stage.setAttribute(`data-new-hybrid-${kind}-stage`,''); stage.setAttribute(`data-new-hybrid-${kind}-content`,''); scroll.append(stage);
      const p = {kind,root,state,scroll,stage,width,height,version:0,controller:null,url:null,ready:false,scale:1,overview:true};
      function scale(value,overview=false) { p.overview=overview; p.scale=Math.max(.02,Math.min(4,value)); stage.style.width=`${width*p.scale}px`; stage.style.height=`${height*p.scale}px`; zoom.textContent=overview?'Fit overview':`Detail ${Math.round(p.scale*100)}%`; }
      p.detail = () => scale(Math.max(.5,p.scale));
      p.fit = () => scale(Math.min((scroll.clientWidth || 300)/width,(scroll.clientHeight || 300)/height),true);
      const zoom = node('span','Fit overview'); zoom.setAttribute('aria-live','polite');
      for (const [key,text,action] of [['fit','Fit',p.fit],['detail','Detail',()=>scale(Math.max(.5,p.scale))],['minus','−',()=>{if(!p.overview&&p.scale>.5)scale(Math.max(.5,p.scale/1.5));}],['plus','+',()=>scale(Math.max(.5,p.scale*1.5))]]) {
        const button = node('button',text); button.type='button'; button.setAttribute('aria-label',`${title}: ${text}`); button.setAttribute(`data-comparison-${key}`,kind); button.setAttribute(`data-new-hybrid-${kind}-${key}`,''); button.addEventListener('click',action); controls.append(button);
      }
      controls.append(zoom); root.append(label,controls,state,scroll); content.append(root); return p;
    }
    const xray = pane('xray','X-ray',1142,1142), optical = pane('optical','Current reviewed pre-bonding montage',2400,2176), panes=[xray,optical];
    const redRoot=node('div',undefined,'new-hybrids-red'),redSummary=node('p','RED locations unavailable'),redList=node('div');redSummary.setAttribute('data-comparison-red-summary','');redRoot.append(redSummary,redList);optical.root.append(redRoot);
    function redOverlay(model) {
      const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 2400 2176');svg.setAttribute('class','new-hybrids-red-overlay');svg.setAttribute('aria-hidden','true');
      const reds=model.positions.filter(p=>p.label==='RED'),token=generation,version=optical.version;let selected=null;const buttons=[];
      redSummary.textContent=reds.length?`RED locations (${reds.length}) · label, not a formal QC failure`:'No RED-labelled locations';redList.replaceChildren();
      for(const p of reds){const x=p.position%16*150,y=Math.floor(p.position/16)*136;
        let outline;
        for(const [color,width] of [['#fff',9],['#c40020',4]]){const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');for(const [k,v] of Object.entries({x:x+4,y:y+4,width:142,height:128,fill:'none',stroke:color,'stroke-width':width,'vector-effect':'non-scaling-stroke'}))rect.setAttribute(k,v);if(color!=='#fff'){rect.setAttribute('data-comparison-red-outline',p.position);outline=rect;}svg.append(rect);}
        const button=node('button',String(p.position));button.type='button';button.setAttribute('data-comparison-red-position',p.position);button.setAttribute('aria-label',`Show RED location ${p.position}`);button.setAttribute('aria-pressed','false');buttons.push(button);
        button.addEventListener('click',()=>{if(token!==generation||version!==optical.version||!optical.ready||!dialog.open)return;
          if(selected){selected.setAttribute('stroke','#c40020');selected.setAttribute('stroke-dasharray','none');}selected=outline;outline.setAttribute('stroke','#820014');outline.setAttribute('stroke-dasharray','8 3');buttons.forEach(b=>b.setAttribute('aria-pressed',b===button?'true':'false'));
          optical.detail();optical.scroll.scrollLeft=Math.max(0,(x+75)*optical.scale-optical.scroll.clientWidth/2);optical.scroll.scrollTop=Math.max(0,(y+68)*optical.scale-optical.scroll.clientHeight/2);
        });redList.append(button);
      }return svg;
    }
    function invalidate(p,message) { ++p.version; p.controller?.abort(); p.controller=null; release(p.url); p.url=null; p.ready=false; p.stage.replaceChildren(); if(p===optical){redList.replaceChildren();redSummary.textContent='RED locations unavailable';}p.state.textContent=message; summary(); }
    function cleanup() { ++generation; active=null;comments.close(); panes.forEach(p=>invalidate(p,'Not loaded')); }
    function close() { const old=trigger; trigger=null; cleanup(); if(dialog.open)dialog.close(); if(old?.isConnected)old.focus(); }
    closeButton.addEventListener('click',close);
    dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
    dialog.addEventListener('close',()=>{if(!dialog.open){const old=trigger;trigger=null;cleanup();if(old?.isConnected)old.focus();}});
    dialog.addEventListener('click',e=>{const b=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom))close();});
    async function load(p,spec,model=null) {
      invalidate(p,`Verifying ${p.kind === 'xray' ? 'supplied X-ray' : 'current clean montage'}…`);
      const token=generation,version=p.version,serial=active.etroc_serial; p.controller=new AbortController();
      const current=()=>token===generation&&version===p.version&&dialog.open;
      let url=null,displayed=false;
      try {
        const response=await fetch(spec.uri,{credentials:'same-origin',cache:'no-store',signal:p.controller.signal}); if(!current())return;
        if(!response.ok)throw Error('Image unavailable');
        const bytes=await response.arrayBuffer(); if(!current())return;
        if((spec.bytes!==undefined&&bytes.byteLength!==spec.bytes)||await hash(bytes)!==spec.sha256)throw Error('Image integrity mismatch');
        if(!current())return;
        url=URL.createObjectURL(new Blob([bytes],{type:model?'image/jpeg':'image/png'})); urls.add(url); p.url=url;
        const image=node('img'); image.src=url; image.width=p.width; image.height=p.height; image.alt=`${serial}: verified ${model?'current clean montage with effective labels':'supplied X-ray, original orientation'}`;
        await image.decode(); if(!current())return;
        if(image.naturalWidth!==p.width||image.naturalHeight!==p.height)throw Error('Image dimensions mismatch');
        image.setAttribute('data-comparison-image',p.kind); image.setAttribute(model?'data-new-hybrid-optical-image':'data-new-hybrid-image','');
        p.stage.replaceChildren(image,...(model?[globalThis.ETROCResultsContract.renderOverlay(model),redOverlay(model)]:[])); displayed=true;p.ready=true;p.fit();
        p.state.textContent=model?'Verified clean montage · 256 effective positions (0–255). Fit overview / Detail for readable numbers.':'Verified supplied X-ray · original bytes and orientation.';summary();
      } catch(error) { if(current()){p.stage.replaceChildren();p.ready=false;p.state.textContent=`${model?'Current reviewed montage':'Supplied X-ray'} unavailable — integrity or decoding failed. Close and reopen to retry.`;summary();} }
      finally {if(url&&!displayed){release(url);if(p.url===url)p.url=null;}}
    }
    function loadOptical() {
      invalidate(optical,'Current reviewed montage unavailable until current results are validated. No original algorithm fallback.');
      if(!active||!dialog.open)return Promise.resolve();
      let model=null;
      globalThis.dispatchEvent(new CustomEvent('etroc-results-model-request',{detail:{etroc_serial:active.etroc_serial,receive:value=>{model=value;}}}));
      if(!model||model.etroc_serial!==active.etroc_serial||model.positions?.length!==256)return Promise.resolve();
      return load(optical,{uri:`/data/etroc-optical/ETROC_OI_2608/${model.clean_montage_uri}`,sha256:model.clean_montage_sha256},model);
    }
    globalThis.addEventListener('etroc-results-invalidated',()=>invalidate(optical,'Current reviewed montage unavailable — results refreshing or publication invalid.'));
    globalThis.addEventListener('etroc-results-ready',()=>{if(active&&dialog.open)void loadOptical();});
    globalThis.addEventListener('resize',()=>{if(dialog.open)panes.forEach(p=>{if(p.overview)p.fit();});});
    async function open(record,opener) {
      close();trigger=opener;active=record;
      heading.textContent=`${record.etroc_serial} · ${record.lgad_label}`;
      try {notes.textContent=`Supplied pre-bonding optical note: ${translateNotes(record.source_notes)}`;} catch(error){notes.textContent='Supplied pre-bonding optical note unavailable — unrecognized source grammar.';}
      dialog.showModal();closeButton.focus();comments.open(record);
      await Promise.all([load(xray,{...record.image,uri:BASE+record.image.uri}),loadOptical()]);
    }
    return {open,close};
  }
  function renderCard(r, viewer) {
    const card = node('article',undefined,'new-hybrids-card'); card.dataset.newHybridEtroc = r.etroc_serial;
    const button = node('button',undefined,'new-hybrids-image'); button.type = 'button'; button.setAttribute('data-new-hybrid-image-button',''); button.setAttribute('aria-label',`${r.etroc_serial}: compare X-ray and montage`); button.setAttribute('aria-haspopup','dialog');
    const img = node('img'); img.src = BASE + r.image.uri; img.alt = `${r.etroc_serial} · supplied image thumbnail`; img.loading = 'lazy'; img.width = 1142; img.height = 1142;
    img.addEventListener('error',() => button.replaceChildren(node('span','Supplied image unavailable — open to retry')));
    button.append(img); button.addEventListener('click',() => { void viewer.open(r,button); });
    card.append(button,node('h3',r.etroc_serial),node('p',r.lgad_label));
    if (!r.individual_lgad_serial_supplied) card.append(node('p','Individual LGAD serial not supplied (generic label)'));
    card.append(node('p',`Connection channel: ${r.channel === null ? 'Not supplied' : r.channel}`),node('p',`Supplied pre-bonding optical note: ${translateNotes(r.source_notes)}`));
    const compare = node('button','Compare X-ray and montage'); compare.type='button'; compare.setAttribute('data-new-hybrid-compare',''); compare.setAttribute('aria-haspopup','dialog');
    compare.addEventListener('click',()=>{void viewer.open(r,compare);}); card.append(compare); return card;
  }
  globalThis.NewHybridsContract = Object.freeze({validate,parseVerified,select,translateNotes,commentTarget,createViewer,renderCard});
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
      sources.append(node('p',`${manifest.corrections['W05E5-30']}. W03F7-85: ${manifest.corrections['W03F7-85']}. Source directory indicates left-right-mirrored images; no additional flip is applied. Downloads preserve original source-language provenance. No new Construction DB registrations.`));
    } catch(error) { cards.replaceChildren(); search.disabled = true; status.textContent = 'New supplied batch unavailable — publication could not be verified. Existing registered cohort is unaffected.'; }
  })();
})();
