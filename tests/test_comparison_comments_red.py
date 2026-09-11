"""Run the real comparison controller; only native DOM/network boundaries are faked."""
import ast
import subprocess
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / 'hybrid-bbqc'
SOURCE = Path(__file__).with_name('test_hybrid_comparison.py')

@pytest.mark.parametrize('scenario', ['save', 'pending', 'ambiguous', 'switch', 'draft', 'auth', 'read_error', 'mixed_status', 'length', 'red', 'zero', 'identity'])
def test_comments_and_red(scenario):
    tree = ast.parse(SOURCE.read_text())
    program = next(n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'program' for t in n.targets))
    program = program.replace("global.fetch=async url=>", "global.imageFetch=async url=>")
    boundary = r'''
let posts=0, rows=[], postGate=null, failRead=false;
global.fetch=async (url,opts={})=>{
 if(url==='/api/me')return {ok:true,status:200,json:async()=>({authenticated:scenario!=='auth',user:{display:'Tester'}})};
 if(url.startsWith('/api/comments')){
  if(opts.method==='POST'){
   posts++;if(postGate)await postGate.promise;
   if(scenario==='ambiguous')throw Error('network');
   const p=JSON.parse(opts.body);assert.equal(p.status,'note');assert.equal(opts.credentials,'same-origin');
   const receipt={...p,id:posts,author_display:'Tester',created_at:123,updated_at:123};rows.unshift(receipt);
   if(scenario==='pending')failRead=true;
   return {ok:true,status:201,json:async()=>receipt};
  }
  if(failRead||scenario==='read_error')throw Error('read');
  const target=new URLSearchParams(url.split('?')[1]).get('target');
  return {ok:true,status:200,json:async()=>rows.filter(r=>r.target===target).map(r=>({...r,can_edit:true}))};
 }
 return imageFetch(url);
};
'''
    program = program.replace("require(process.argv[1]+'/etroc-results.js');", boundary + "require(process.argv[1]+'/etroc-results.js');")
    checks = r'''
 await tick();await tick();
 const form=hook('data-comparison-comments-form'),body=hook('data-comparison-comments-body'),save=hook('data-comparison-comments-save'),message=hook('data-comparison-comments-message'),refresh=hook('data-comparison-comments-refresh');
 assert(form&&body&&save&&message&&refresh,'persistent comment controls required');
 const enter=text=>{body.value=text;body.fire('input')};
 const settle=async()=>{for(let i=0;i<12;i++)await tick()};
 if(scenario==='identity'){const targets=manifest.records.map(c.commentTarget);assert.equal(new Set(targets).size,35);for(let i=0;i<35;i++)assert.equal(targets[i],'hybrid-comparison:NEW_HYBRIDS_20260911:'+manifest.records[i].etroc_serial);viewer.close();return}
 if(scenario==='auth'){assert(save.disabled);enter('note');form.fire('submit');await settle();assert.equal(posts,0);viewer.close();return}
 if(scenario==='read_error'){assert(hook('data-comparison-comments-list').textContent.includes('unavailable'));viewer.close();return}
 if(scenario==='mixed_status'){
  const statuses=['note','review','pass','fail','follow-up'];
  rows=statuses.map((status,i)=>({id:i+1,target:c.commentTarget(r),body:`Existing ${status} comment`,status,author_display:'Tester',created_at:123+i,updated_at:123+i}));
  refresh.fire('click');await settle();
  const list=hook('data-comparison-comments-list');
  assert.equal(list.children.length,statuses.length,'all backend-supported statuses must render together');
  const renderedBodies=list.children.map(item=>item.children[1].textContent);
  assert.deepEqual(renderedBodies,statuses.slice().reverse().map(status=>`Existing ${status} comment`));
  assert(!list.textContent.includes('unavailable'));assert.equal(posts,0);viewer.close();return;
 }
 if(scenario==='red'||scenario==='zero'){
  const buttons=all('data-comparison-red-position'),outlines=all('data-comparison-red-outline');assert.deepEqual(buttons.map(b=>b.attrs['data-comparison-red-position']),['255']);assert.deepEqual(outlines.map(b=>b.attrs['data-comparison-red-outline']),['255']);
  assert.equal(outlines[0].attrs.fill,'none');assert.equal(outlines[0].attrs['vector-effect'],'non-scaling-stroke');
  buttons[0].fire('click');assert(parseFloat(hook('data-new-hybrid-optical-stage').style.width)>=1200);const scroller=all('data-comparison-scroll').find(s=>s.attrs['data-comparison-scroll']==='optical');assert.equal(scroller.scrollTop,(2040+68)*.5-600/2);assert.equal(scroller.scrollLeft,(2250+75)*.5-500/2);assert.equal(buttons[0].attrs['aria-pressed'],'true');
  const stage=hook('data-new-hybrid-optical-stage');dispatchEvent(new CustomEvent('etroc-results-invalidated'));assert.equal(stage.children.length,0);assert(!hook('data-comparison-red-summary').textContent.includes('(1)'));const before=stage.style.width;buttons[0].fire('click');assert.equal(stage.style.width,before);
  model.positions.forEach(p=>p.label='GREEN');dispatchEvent(new CustomEvent('etroc-results-ready'));await settle();assert.equal(hook('data-comparison-red-summary').textContent,'No RED-labelled locations');viewer.close();return;
 }
 enter(scenario==='length'?'x'.repeat(2001):'<img src=x onerror=alert(1)> human 한글');
 if(scenario==='draft'){const draft=body.value;viewer.close();await viewer.open({...r,etroc_serial:manifest.records[1].etroc_serial},trigger);await settle();assert.equal(body.value,'');enter('separate draft');await viewer.open(r,trigger);await settle();assert.equal(body.value,draft);assert.equal(posts,0);viewer.close();return}
 if(scenario==='length'){form.fire('submit');await settle();assert.equal(posts,0);viewer.close();return}
 if(scenario==='switch')postGate=deferred();
 form.fire('submit');form.fire('submit');await tick();assert.equal(posts,1,'duplicate submissions locked');
 if(scenario==='switch'){
  const draft=body.value;viewer.close();await viewer.open({...r,etroc_serial:manifest.records[1].etroc_serial},trigger);await settle();assert.equal(body.value,'');enter('other chip');postGate.resolve();await settle();assert.equal(body.value,'other chip');assert(!message.textContent.startsWith('Saved'));await viewer.open(r,trigger);await settle();assert.equal(body.value,'');assert.equal(rows[0].target,c.commentTarget(r));viewer.close();return;
 }
 await settle();
 if(scenario==='ambiguous'){assert(message.textContent.includes('unknown'));assert(body.value);form.fire('submit');refresh.fire('click');await settle();form.fire('submit');await settle();assert.equal(posts,1);assert(!message.textContent.startsWith('Saved'));viewer.close();return}
 if(scenario==='pending'){assert(body.value);assert(!message.textContent.startsWith('Saved'));form.fire('submit');await settle();assert.equal(posts,1);failRead=false;refresh.fire('click');await settle();}
 assert(message.textContent.startsWith('Saved'));assert.equal(body.value,'');assert.equal(posts,1);assert(rows[0].body.includes('<img'));assert(!nodes.some(n=>n.tagName==='IMG'&&n.src==='x'));
 viewer.close();await viewer.open(r,trigger);await settle();assert.equal(rows.length,1);assert.equal(body.value,'');viewer.close();return;
'''
    program = program.replace(' const dialog=hook(\'data-new-hybrid-dialog\');assert.equal', checks + '\n const dialog=hook(\'data-new-hybrid-dialog\');assert.equal')
    result = subprocess.run(['node', '-e', program, str(APP), scenario], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
