const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
class Element {
  constructor(){this.nodeType=1;this.children=[];this.dataset={};this.style={};this.textContent='';}
  addEventListener(){}
  append(...items){this.children.push(...items);}
  prepend(...items){this.children.unshift(...items);}
  replaceChildren(...items){this.children=items;this.textContent='';}
  set innerHTML(_){throw new Error('Unsafe HTML rendering');}
}
test('Admin scripts parse and operations renders malicious-looking names as text',async()=>{
  const html=fs.readFileSync('templates/admin.html','utf8');
  for(const [,source] of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(source);
  const root=new Element(); const sample='<img src=x onerror=alert(1)>';
  const data={total:1,completed:1,failed:0,processing:0,anonymous_started:1,saved_trials:0,repeat_accounts:0,average_seconds:null,measured_durations:0,
    feedback:{responses:0,helpful:0,accurate:0},funnel:[{label:'Visitors',count:1}],channels:[{source:sample,visitors:1,started:1,completed:1,saved:0}],recent:[{id:'test',filename:sample,type:'Trial',state:'completed',frames:null,error:null}],credit_changes:[]};
  const context=vm.createContext({document:{getElementById:id=>id==='opsContent'?root:{value:'7'},createElement:()=>new Element()},apiFetch:async()=>data});
  vm.runInContext(fs.readFileSync('static/admin-details.js','utf8'),context);
  vm.runInContext(fs.readFileSync('static/admin-operations.js','utf8'),context);await context.loadOperations();
  const texts=[];function walk(e){texts.push(e.textContent);e.children.forEach(walk);}walk(root);
  assert.ok(texts.includes(sample));assert.ok(texts.includes('匿名试用转化'));assert.ok(!texts.some(x=>String(x).includes('读取失败')));
});
test('Operations API failure is visible instead of rendered as zeros',async()=>{
  const root=new Element();
  const context=vm.createContext({document:{getElementById:id=>id==='opsContent'?root:{value:'7'}},apiFetch:async()=>{throw new Error('503');}});
  vm.runInContext(fs.readFileSync('static/admin-details.js','utf8'),context);
  vm.runInContext(fs.readFileSync('static/admin-operations.js','utf8'),context);await context.loadOperations();
  assert.match(root.textContent,/读取失败/);
});
test('Quality survey and tracking scripts parse',()=>{
  for(const path of ['static/quality-survey.js','static/operations-tracking.js'])new vm.Script(fs.readFileSync(path,'utf8'));
});
test('P1 user detail renders timeline, cloud failure and review history safely',async()=>{
  const main=new Element();
  Element.prototype.scrollIntoView=function(){};
  const calls=[];
  const data={id:'u',profile:{email:'<img onerror=x>'},coverage:'90 days',errors:{cloud:'Unavailable'},reports:[{id:'shot'}],timeline:[{created:1,action:'analysis',details:{filename:'<script>x</script>'},task:'shot'}],cloud:{},reviews:[{id:'retest',state:'waiting',goal:'range',parent:{id:'shot'},practice:{sessions:3},versions:[]}]};
  const context=vm.createContext({document:{getElementById:()=>null,querySelector:()=>main,createElement:()=>new Element()},apiFetch:async path=>{calls.push(path);return data;}});
  vm.runInContext(fs.readFileSync('static/admin-details.js','utf8'),context);
  await context.openUserDetail('u');
  const texts=[];function walk(e){texts.push(String(e.textContent));e.children.forEach(walk);}walk(main);
  assert.equal(calls[0],'/users/u/detail');assert.ok(texts.some(x=>x.includes('<img onerror=x>')));
  assert.ok(texts.includes('cloud：Unavailable'));assert.ok(texts.includes('训练反馈与复测'));assert.ok(texts.includes('retest'));
  assert.ok(!texts.some(x=>x.includes('读取失败')));
});
test('P0 detail distinguishes unknown phases and expired media',async()=>{
  const main=new Element();Element.prototype.scrollIntoView=function(){};
  const data={id:'shot',filename:'shot.mov',state:'failed',created:1,elapsed_seconds:null,owner:null,error:'No pose',missing_phases:null,diagnostic_note:'Unknown history',metadata:{},frames:null,feedback:null,media_available:false};
  const context=vm.createContext({document:{getElementById:()=>null,querySelector:()=>main,createElement:()=>new Element()},apiFetch:async()=>data});
  vm.runInContext(fs.readFileSync('static/admin-details.js','utf8'),context);await context.openAnalysisDetail('shot');
  const texts=[];function walk(e){texts.push(String(e.textContent));e.children.forEach(walk);}walk(main);
  assert.ok(texts.includes('未检测到：历史数据未知'));assert.ok(texts.includes('失败原因：No pose'));assert.ok(texts.some(x=>x.includes('无法预览')));
});
