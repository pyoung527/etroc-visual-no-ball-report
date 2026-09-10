"""Execute the real result viewer/controller in a small native-DOM boundary harness."""
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hybrid-bbqc"


@pytest.mark.parametrize("scenario", ["success", "zero_targets", "hash_failure", "http_failure", "decode_failure", "close_fetch", "cancel_decode", "reopen", "routing", "review_update", "refresh_button", "publication_error"])
def test_read_only_result_viewer(scenario):
    program = r'''
const assert=require('node:assert/strict'), fs=require('node:fs');
const nodes=[], scenario=process.argv[2], lifecycle=['review_update','refresh_button','publication_error'].includes(scenario);
let selected='', focused=null, fetchGate=null, decodeGate=null, calls=[], revoked=[], blobs=[];
class Element {
 constructor(tag){this.tagName=tag;this.dataset={};this.children=[];this.attrs={};this.events={};this.open=false;this.isConnected=true;this.classList={add:()=>{},toggle:()=>{}};nodes.push(this)}
 querySelector(selector){return controls[selector]??=new Element('div')}
 append(...children){this.children.push(...children);children.forEach(c=>c.parent=this)}
 replaceChildren(...children){this.children=[];this.append(...children)}
 setAttribute(k,v){this.attrs[k]=v}
 addEventListener(k,f){(this.events[k]??=[]).push(f)}
 fire(k,event={}){for(const f of this.events[k]||[])f({target:this,button:0,preventDefault(){this.defaultPrevented=true},...event})}
 closest(selector){return selector.split(',').some(s=>s.trim()===this.tagName)?this:this.parent?.closest(selector)||null}
 focus(){focused=this} showModal(){this.open=true} close(){this.open=false;this.fire('close')}
 getBoundingClientRect(){return {left:10,right:900,top:10,bottom:900}}
 async decode(){if(decodeGate)await decodeGate.promise;if(scenario==='decode_failure')throw Error('decode')}
}
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};
const tick=()=>new Promise(r=>setImmediate(r));
const controls={}, events={};
global.addEventListener=(name,fn)=>events[name]=fn;
global.document={querySelector:selector=>lifecycle?(controls[selector]??=new Element('div')):null,createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),body:new Element('body')};
global.getSelection=()=>selected;
global.crypto=require('node:crypto').webcrypto;
const bytes=new Uint8Array([1,2,3]);
global.fetch=async(url,options)=>{calls.push({url,options});if(fetchGate)await fetchGate.promise;return {ok:scenario!=='http_failure',status:503,arrayBuffer:async()=>bytes.buffer}};
global.URL={createObjectURL:blob=>{blobs.push(blob);return 'blob:'+blobs.length},revokeObjectURL:url=>revoked.push(url)};
require(process.argv[1]+'/etroc-results.js');
const c=ETROCResultsContract;
const byHook=hook=>nodes.find(n=>n.attrs[hook]!==undefined);
(async()=>{
 const hash=Buffer.from(await crypto.subtle.digest('SHA-256',bytes)).toString('hex');
 const model={etroc_serial:'W-test',acquisition_id:'acq',clean_montage_uri:'clean.jpg',clean_montage_sha256:scenario==='hash_failure'?'0'.repeat(64):hash,
 positions:Array.from({length:256},(_,position)=>({position,label:position===255&&scenario!=='zero_targets'?'RED':'GREEN',source:position===255&&scenario!=='zero_targets'?'human':'algorithm',event_id:position===255?82:null})),
 categories:{GREEN:scenario==='zero_targets'?256:255,BLUE:0,YELLOW:0,RED:scenario==='zero_targets'?0:1,PENDING:0},target_count:scenario==='zero_targets'?0:1,reviewed_target_count:scenario==='zero_targets'?0:1};
 if(scenario==='routing'){
  let opens=0;const card=c.renderCard(model,()=>opens++), trigger=card.children[0],body=card.children[1];
  assert.equal(trigger.tagName,'button');assert.equal(trigger.type,'button');assert(trigger.attrs['aria-label'].includes('reviewed'));
  trigger.fire('click');assert.equal(opens,1);
  card.fire('click',{target:body});assert.equal(opens,2);
  for(const tag of ['button','a','details','summary','input','select','textarea']){const target=new Element(tag);card.fire('click',{target});}
  selected='selected text';card.fire('click',{target:body});selected='';card.fire('click',{target:body,button:2});assert.equal(opens,2);return;
 }
 if(lifecycle){
  decodeGate=deferred();const card=c.renderCard(model);card.children[0].fire('click');
  for(let i=0;i<100&&!blobs.length;i++)await tick();assert.equal(blobs.length,1);
  const dialog=byHook('data-etroc-result-viewer');assert(dialog.open);
  if(scenario==='review_update')events['etroc-position-review-updated']();
  else if(scenario==='refresh_button')controls['[data-etroc-results-refresh]'].fire('click');
  else events['etroc-optical-unavailable']();
  assert(!dialog.open);assert.deepEqual(revoked,['blob:1']);decodeGate.resolve();await tick();
  assert.equal(byHook('data-etroc-result-viewer-image'),undefined);return;
 }
 assert.equal(typeof c.createViewer,'function','read-only viewer must be available');
 const viewer=c.createViewer(),trigger=new Element('button');
 if(scenario==='close_fetch')fetchGate=deferred();
 if(['cancel_decode','reopen'].includes(scenario))decodeGate=deferred();
 const opening=viewer.open(model,trigger);await tick();
 if(['cancel_decode','reopen'].includes(scenario)) {for(let i=0;i<100&&!blobs.length;i++)await tick();assert.equal(blobs.length,1,'reach pending decode boundary');}
 const dialog=byHook('data-etroc-result-viewer');assert.equal(dialog.tagName,'dialog');assert(dialog.open);
 if(scenario==='close_fetch'){viewer.close();fetchGate.resolve();await opening;assert.equal(blobs.length,0);assert(!dialog.open);return}
 if(scenario==='cancel_decode'){dialog.fire('cancel');decodeGate.resolve();await opening;assert(!dialog.open);assert.equal(revoked.length,1);assert.equal(focused,trigger);return}
 if(scenario==='reopen'){
  const old=decodeGate;viewer.close();decodeGate=null;await viewer.open(model,trigger);old.resolve();await opening;
  assert(dialog.open);assert.equal(byHook('data-etroc-result-viewer-image').src,'blob:2');assert.deepEqual(revoked,['blob:1']);viewer.close();assert.deepEqual(revoked,['blob:1','blob:2']);return;
 }
 await opening;
 if(['hash_failure','http_failure','decode_failure'].includes(scenario)){
  assert(byHook('data-etroc-result-viewer-status').textContent.includes('unavailable'));
  assert.equal(byHook('data-etroc-result-viewer-image'),undefined);
  assert.equal(revoked.length,scenario==='decode_failure'?1:0);
 }else{
  const image=byHook('data-etroc-result-viewer-image');assert.equal(image.src,'blob:1');assert.deepEqual(new Uint8Array(await blobs[0].arrayBuffer()),bytes);
  const groups=nodes.filter(n=>n.tagName==='g');assert.equal(groups.length,256);assert.equal(groups[255].attrs['data-position'],'255');assert.equal(groups[255].attrs['data-label'],scenario==='zero_targets'?'GREEN':'RED');
  for(const [i,g] of groups.entries()){
   const number=g.children.find(n=>n.attrs['data-etroc-location-number']!==undefined);
   assert(number,`Position ${i} needs a persistent visible number, not just a title`);
   assert.equal(number.tagName,'text');assert.equal(number.textContent,String(i));
   assert.equal(number.attrs.fill,'#fff');assert(Number(number.attrs['font-size'])>=32);
   assert.equal(number.attrs['font-weight'],'800');assert(!number.attrs.hidden);
   const x=i%16*150,y=Math.floor(i/16)*136;
   assert(Number(number.attrs.x)>=x+4);assert.equal(Number(number.attrs.y),y+32);
   const badge=g.children.find(n=>n.attrs['data-etroc-location-badge']!==undefined);
   assert(badge);assert.equal(badge.attrs.fill,'#111');
   assert.equal(Number(badge.attrs.y),y+1);assert.equal(Number(badge.attrs.height),39);
   assert(Number(badge.attrs.y)+Number(badge.attrs.height)<=y+40);
   assert(g.children.some(n=>n.tagName==='text'&&n.textContent===`${model.positions[i].label} ${model.positions[i].source==='human'?'H':'A'}`));
  }
  const scroller=nodes.find(n=>n.attrs['data-etroc-result-viewer-scroll']!==undefined);
  assert(scroller);assert.equal(scroller.attrs.tabindex,'0');assert.equal(image.parent.parent,scroller);
  assert(!scroller.children.includes(byHook('data-etroc-result-viewer-close')));
  const card=c.renderCard(model,()=>{});
  const cardSvg=card.children[0].children.find(n=>n.tagName==='svg');
  assert.deepEqual(cardSvg.children.map(g=>g.children.find(n=>n.attrs['data-etroc-location-number']!==undefined)?.textContent),Array.from({length:256},(_,i)=>String(i)));
  assert(nodes.some(n=>n.textContent==='GREEN '+model.categories.GREEN));
  dialog.fire('click',{clientX:20,clientY:20});assert(dialog.open);
  dialog.fire('click',{clientX:0,clientY:0});assert(!dialog.open);assert.equal(focused,trigger);assert.deepEqual(revoked,['blob:1']);
 }
 assert(calls.every(c=>!c.options.method||c.options.method==='GET'),'viewer never writes');
 assert(byHook('data-etroc-result-viewer-close').textContent.includes('Close'));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", program, str(APP), scenario], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
