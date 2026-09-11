"""Executable comparison contract; native DOM/decode boundary stand-ins only."""
import subprocess
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / 'hybrid-bbqc'

@pytest.mark.parametrize('scenario', ['notes', 'paired', 'optical_hash', 'optical_decode', 'optical_dimensions', 'xray_hash', 'invalidate', 'stale', 'zoom', 'minus', 'keyboard'])
def test_comparison(scenario):
    program = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const scenario=process.argv[2],nodes=[],revoked=[],blobs=[],events={};let focused,decodeGate;
class E {
 constructor(tag){this.tagName=tag.toUpperCase();this.attrs={};this.events={};this.children=[];this.dataset={};this.style={};this.classList={add(){}};this.open=false;this.isConnected=true;this.clientWidth=500;this.clientHeight=600;nodes.push(this)}
 append(...c){this.children.push(...c)} replaceChildren(...c){this.children=c}
 setAttribute(k,v){this.attrs[k]=String(v)} addEventListener(k,f){(this.events[k]??=[]).push(f)}
 fire(k,e={}){for(const f of this.events[k]||[])f({target:this,preventDefault(){},...e})}
 showModal(){this.open=true} close(){this.open=false;this.fire('close')} focus(){focused=this}
 getBoundingClientRect(){return {left:10,top:10,right:900,bottom:900}}
 async decode(){if(decodeGate)await decodeGate.promise;if(scenario==='optical_decode'&&this.width===2400)throw Error('bad decode');this.naturalWidth=scenario==='optical_dimensions'&&this.width===2400?1:this.width;this.naturalHeight=this.height}
}
global.document={querySelector:()=>null,createElement:t=>new E(t),createElementNS:(_,t)=>new E(t),body:new E('body')};
global.CustomEvent=class {constructor(type,o={}){this.type=type;Object.assign(this,o);this.defaultPrevented=false}preventDefault(){this.defaultPrevented=true}};
global.addEventListener=(k,f)=>(events[k]??=[]).push(f);global.dispatchEvent=e=>{for(const f of events[e.type]||[])f(e);return !e.defaultPrevented};
global.crypto=require('node:crypto').webcrypto;
const bytes=new Uint8Array([1,2,3]),optical=new Uint8Array([4,5,6]);
global.fetch=async url=>({ok:true,arrayBuffer:async()=>(url.includes('etroc-optical')?optical:bytes).buffer});
global.URL={createObjectURL:b=>{blobs.push(b);return 'blob:'+blobs.length},revokeObjectURL:u=>revoked.push(u)};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}},tick=()=>new Promise(r=>setImmediate(r));
const hook=k=>nodes.find(n=>Object.hasOwn(n.attrs,k)),all=k=>nodes.filter(n=>Object.hasOwn(n.attrs,k));
require(process.argv[1]+'/etroc-results.js');require(process.argv[1]+'/new-hybrids.js');
(async()=>{
 const c=NewHybridsContract,manifest=JSON.parse(fs.readFileSync(process.argv[1]+'/data/new-hybrids/NEW_HYBRIDS_20260911/manifest.json'));
 if(scenario==='notes'){
  assert.equal(manifest.records.length,35);const variants=new Set();
  for(const r of manifest.records){variants.add(r.source_notes);const out=c.translateNotes(r.source_notes);assert(!/[가-힣]/.test(out));assert(out.includes('Missing solder bumps: '+r.source_notes.match(/missing: (\d+)/)[1]+' (based on optical inspection).'));assert.equal(out.includes('Used for shear force testing.'),r.source_notes.includes(';'));}
  assert.equal(variants.size,5);for(const s of ['unknown','solder bump missing: 3개 (optical inspection 기준)','solder bump missing: 0개 (optical inspection 기준); planned'])assert.throws(()=>c.translateNotes(s));return;
 }
 const sha=async b=>Buffer.from(await crypto.subtle.digest('SHA-256',b)).toString('hex');
 const r={...manifest.records[0],image:{uri:'image.png',bytes:3,sha256:await sha(bytes),width:1142,height:1142}};
 let model={etroc_serial:r.etroc_serial,clean_montage_uri:'clean.jpg',clean_montage_sha256:await sha(optical),positions:Array.from({length:256},(_,position)=>({position,label:position===255?'RED':'GREEN',source:position===255?'human':'algorithm',event_id:position===255?42:null}))};
 if(scenario==='optical_hash')model.clean_montage_sha256='0'.repeat(64);if(scenario==='xray_hash')r.image.sha256='0'.repeat(64);
 global.addEventListener('etroc-results-model-request',e=>{if(model)e.detail.receive(structuredClone(model))});
 const viewer=c.createViewer(),trigger=new E('button');
 if(scenario==='stale')decodeGate=deferred();
 const opening=viewer.open(r,trigger);
 if(scenario==='stale'){for(let i=0;i<100&&blobs.length<2;i++)await tick();viewer.close();const gate=decodeGate;decodeGate=null;await viewer.open(r,trigger);gate.resolve();await opening;assert.equal(new Set(revoked).size,2);assert.equal(hook('data-new-hybrid-dialog').open,true);viewer.close();assert.equal(new Set(revoked).size,4);return}
 await opening;
 const dialog=hook('data-new-hybrid-dialog');assert.equal(nodes.filter(n=>n.tagName==='DIALOG'&&n.open).length,1);
 const x=hook('data-new-hybrid-image'),o=hook('data-new-hybrid-optical-image');
 if(scenario.startsWith('optical_')){assert(x);assert(!o);assert(hook('data-new-hybrid-optical-status').textContent.includes('unavailable'));assert(hook('data-new-hybrid-status').textContent.includes('incomplete'));viewer.close();return}
 if(scenario==='xray_hash'){assert(!x);assert(o);assert(hook('data-new-hybrid-status').textContent.includes('incomplete'));viewer.close();return}
 assert(x&&o);assert.equal(all('data-position').length,256);assert.equal(all('data-position')[255].attrs['data-label'],'RED');assert.equal(all('data-position')[255].attrs['data-source'],'human');
 for(const img of [x,o]){const blob=blobs[Number(img.src.split(':')[1])-1];assert.deepEqual(new Uint8Array(await blob.arrayBuffer()),img===x?bytes:optical)}
 assert(hook('data-new-hybrid-dialog-title')||nodes.some(n=>n.id==='new-hybrids-dialog-title'&&n.textContent.includes(r.etroc_serial)));
 if(scenario==='invalidate'){model=null;dispatchEvent(new CustomEvent('etroc-results-invalidated'));assert.equal(hook('data-new-hybrid-optical-content').children.length,0);assert.equal(hook('data-new-hybrid-xray-content').children.length,1);assert(revoked.includes(o.src));model={etroc_serial:r.etroc_serial,clean_montage_uri:'new.jpg',clean_montage_sha256:await sha(optical),positions:Array.from({length:256},(_,position)=>({position,label:'BLUE',source:'algorithm'}))};dispatchEvent(new CustomEvent('etroc-results-ready'));for(let i=0;i<100&&all('data-position').length<512;i++)await tick();assert.equal(all('data-position').at(-1).attrs['data-label'],'BLUE');}
 if(scenario==='zoom'){const detail=hook('data-new-hybrid-optical-detail'),fit=hook('data-new-hybrid-optical-fit');detail.fire('click');assert(parseFloat(hook('data-new-hybrid-optical-stage').style.width)>=1200);fit.fire('click');assert(parseFloat(hook('data-new-hybrid-optical-stage').style.width)<=500);}
 if(scenario==='minus'){for(const kind of ['xray','optical']){const stage=hook(`data-new-hybrid-${kind}-stage`),before=parseFloat(stage.style.width);hook(`data-new-hybrid-${kind}-minus`).fire('click');assert(parseFloat(stage.style.width)<=before,'Minus must never increase magnification');}}
 if(scenario==='keyboard'){dialog.fire('cancel');assert(!dialog.open);assert.equal(focused,trigger)}
 viewer.close();assert.equal(new Set(revoked).size,blobs.length);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', program, str(APP), scenario], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_current_results_bridge_is_cloned_and_invalidates_synchronously(tmp_path):
    import json
    from test_etroc_results import load_module, STATIC_ROOT, seed_reviews
    module = load_module()
    evidence = module.load_evidence(STATIC_ROOT)
    db = tmp_path / 'isolated.sqlite3'
    module.init_schema(db)
    seed_reviews(module, db, evidence)
    fixture = tmp_path / 'results.json'
    fixture.write_text(json.dumps(module.results_summary(db, evidence)))
    program = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const events={},controls={};
class E {constructor(){this.children=[];this.dataset={};this.value='';this.events={};this.classList={add(){},toggle(){}}}querySelector(s){return controls[s]??=new E()}append(...x){this.children.push(...x)}replaceChildren(...x){this.children=x}setAttribute(){}addEventListener(k,f){this.events[k]=f}}
global.addEventListener=(k,f)=>(events[k]??=[]).push(f);global.dispatchEvent=e=>{for(const f of events[e.type]||[])f(e)};
global.document={querySelector:()=>null};require(process.argv[1]+'/etroc-optical.js');
const records=ETROCOpticalContract.validate(JSON.parse(fs.readFileSync(process.argv[1]+'/data/etroc-optical/ETROC_OI_2608/chips.json')));
global.document={querySelector:s=>controls[s]??=new E(),createElement:()=>new E(),createElementNS:()=>new E()};
let payload=JSON.parse(fs.readFileSync(process.argv[2])),gate=null;
global.fetch=async()=>{if(gate)await gate;return {ok:true,json:async()=>structuredClone(payload)}};
require(process.argv[1]+'/etroc-results.js');
const emit=(type,detail)=>dispatchEvent({type,detail});
const request=serial=>{let model=null;emit('etroc-results-model-request',{etroc_serial:serial,receive:m=>model=m});return model};
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const serial=records.find(r=>r.position_review_target_count>0).etroc_serial;
 assert.equal(request(serial),null);
 emit('etroc-optical-publication',{records,publicationSha256:payload.publication_sha256});
 for(let i=0;i<100&&!request(serial);i++)await tick();
 const model=request(serial);assert(model);const human=model.positions.find(p=>p.source==='human');assert(human);
 model.positions[human.position].label='MUTATED';model.clean_montage_uri='BAD';assert.equal(request(serial).positions[human.position].label,'GREEN');assert.notEqual(request(serial).clean_montage_uri,'BAD');
 assert.equal(request('W03F7-85-extra'),null);
 let invalid=0;addEventListener('etroc-results-invalidated',()=>{invalid++;assert.equal(request(serial),null)});
 for(const type of ['etroc-position-review-updated','refresh','etroc-optical-loading','etroc-optical-unavailable']){
  let resolve;gate=new Promise(r=>resolve=r);
  if(type==='refresh')controls['[data-etroc-results-refresh]'].events.click();else emit(type);
  assert.equal(request(serial),null);assert(invalid>0);
  resolve();gate=null;await tick();
  emit('etroc-optical-publication',{records,publicationSha256:payload.publication_sha256});for(let i=0;i<100&&!request(serial);i++)await tick();assert(request(serial));
 }
 payload.results[model.acquisition_id].human_labels[human.position].label='RED';
 emit('etroc-position-review-updated');assert.equal(request(serial),null);for(let i=0;i<100&&!request(serial);i++)await tick();assert.equal(request(serial).positions[human.position].label,'RED');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', program, str(APP), str(fixture)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
