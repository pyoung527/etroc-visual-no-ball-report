"""Execute supplied-image lifecycle against real controller, with native DOM boundary stand-ins."""
import subprocess
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / 'hybrid-bbqc'

@pytest.mark.parametrize('scenario', ['success','http','hash','decode','dimensions','close_fetch','cancel_decode','reopen','secondary'])
def test_supplied_viewer_lifecycle(scenario):
    program = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const scenario=process.argv[2],nodes=[],revoked=[],blobs=[];let gate=null,decodeGate=null,focused=null;
class E {
 constructor(tag){this.tagName=tag.toUpperCase();this.attrs={};this.events={};this.children=[];this.dataset={};this.style={};this.open=false;this.isConnected=true;nodes.push(this)}
 append(...c){this.children.push(...c)} replaceChildren(...c){this.children=c}
 setAttribute(k,v){this.attrs[k]=v} addEventListener(k,f){(this.events[k]??=[]).push(f)}
 fire(k,e={}){for(const f of this.events[k]||[])f({target:this,preventDefault(){},...e})}
 showModal(){this.open=true} close(){this.open=false;this.fire('close')} focus(){focused=this}
 getBoundingClientRect(){return {left:10,top:10,right:900,bottom:900}}
 async decode(){if(decodeGate)await decodeGate.promise;if(scenario==='decode')throw Error('decode');this.naturalWidth=scenario==='dimensions'?1:1142;this.naturalHeight=1142}
}
global.document={querySelector:()=>null,createElement:t=>new E(t),body:new E('body')};
global.addEventListener=()=>{};global.dispatchEvent=()=>{};global.CustomEvent=class{constructor(type,o){this.type=type;Object.assign(this,o)}};
global.crypto=require('node:crypto').webcrypto;
const bytes=new Uint8Array([1,2,3]);
global.fetch=async()=>{if(gate)await gate.promise;return {ok:scenario!=='http',arrayBuffer:async()=>bytes.buffer}};
global.URL={createObjectURL:b=>{blobs.push(b);return 'blob:'+blobs.length},revokeObjectURL:u=>revoked.push(u)};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};
const tick=()=>new Promise(r=>setImmediate(r)),hook=k=>nodes.find(n=>Object.hasOwn(n.attrs,k));
require(process.argv[1]+'/new-hybrids.js');
(async()=>{
 const r={etroc_serial:'W05E5-30',lgad_label:'HPK-W7-4',individual_lgad_serial_supplied:true,channel:null,source_notes:'solder bump missing: 0개 (optical inspection 기준)',image:{uri:'image.png',bytes:3,sha256:Buffer.from(await crypto.subtle.digest('SHA-256',bytes)).toString('hex')}};
 if(scenario==='secondary'){
  const opens=[];const card=NewHybridsContract.renderCard(r,{open(...args){opens.push(args)}}),button=hook('data-new-hybrid-compare');button.fire('click');
  hook('data-new-hybrid-image-button').fire('click');assert.equal(opens.length,2);assert.equal(opens[0][0],r);assert.equal(opens[0][1],button);assert.equal(opens[1][0],r);assert(!nodes.some(n=>n.attrs['data-new-hybrid-reviewed-button']!==undefined));return;
 }
 if(scenario==='hash')r.image.sha256='0'.repeat(64);
 const viewer=NewHybridsContract.createViewer(),trigger=new E('button');
 if(scenario==='close_fetch')gate=deferred();
 if(['cancel_decode','reopen'].includes(scenario))decodeGate=deferred();
 const opening=viewer.open(r,trigger);await tick();
 const dialog=hook('data-new-hybrid-dialog');assert(dialog.open);
 if(scenario==='close_fetch'){viewer.close();gate.resolve();await opening;assert.equal(blobs.length,0);assert(!dialog.open);return}
 if(decodeGate){for(let i=0;i<100&&!blobs.length;i++)await tick();assert.equal(blobs.length,1)}
 if(scenario==='cancel_decode'){dialog.fire('cancel');decodeGate.resolve();await opening;assert(!dialog.open);assert.deepEqual(revoked,['blob:1']);assert.equal(focused,trigger);return}
 if(scenario==='reopen'){const old=decodeGate;viewer.close();decodeGate=null;await viewer.open(r,trigger);old.resolve();await opening;assert(dialog.open);assert.equal(hook('data-new-hybrid-image').src,'blob:2');assert.deepEqual(revoked,['blob:1']);viewer.close();assert.deepEqual(revoked,['blob:1','blob:2']);return}
 await opening;
 if(['http','hash','decode','dimensions'].includes(scenario)){assert(hook('data-new-hybrid-xray-status').textContent.includes('unavailable'));assert(!hook('data-new-hybrid-image'));assert.equal(revoked.length,['decode','dimensions'].includes(scenario)?1:0)}
 else {assert.equal(hook('data-new-hybrid-image').src,'blob:1');assert.deepEqual(new Uint8Array(await blobs[0].arrayBuffer()),bytes);dialog.fire('click',{clientX:0,clientY:0});assert(!dialog.open);assert.equal(focused,trigger);assert.deepEqual(revoked,['blob:1'])}
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node','-e',program,str(APP),scenario],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
