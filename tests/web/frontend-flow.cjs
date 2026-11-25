/* Real page functions run with deterministic API/DOM doubles. No browser or network. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const html = fs.readFileSync('templates/index.html', 'utf8');
function extract(name) {
  const start = html.search(new RegExp('        (?:async )?function ' + name + '\\('));
  assert(start >= 0, 'Missing function ' + name);
  const rest = html.slice(start + 1);
  const end = rest.search(/\n        (?:async )?function /);
  // Analyze's event binding precedes the function; no other top-level statements are included.
  return html.slice(start, end < 0 ? undefined : start + 1 + end);
}
function fixture() {
  const elements = new Map();
  const el = id => {if(!elements.has(id)) elements.set(id, {value:'',checked:true,style:{},classList:{remove(){},add(){}}}); return elements.get(id);};
  const x = {selectedFile:{name:'shot.mov'}, analysisBusy:false,pendingAnalysis:false,currentUser:null,
    creditsUnlimited:false,creditsRemaining:3,opened:0,uploads:0,payments:0,
    analyzeBtn:{disabled:false},removeFile:{},fileInput:{},
    document:{getElementById:el,querySelector:()=>({value:'right'}),body:{style:{}}},
    openAuthModal(){x.opened++},showLoginButton(){x.currentUser=null},showAuthError(msg){x.authError=msg},
    fetchCredits:async()=>({credits_remaining:3}),openPaymentModal(){x.payments++},trackEvent(){},
    FormData:class {append(){}},progressContainer:{style:{}},progressFill:{style:{}},progressText:{},
    t:s=>s,getAuthHeaders:async()=>({Authorization:'Bearer test'}),
    fetch:async()=>{x.uploads++;return {ok:true,status:200,json:async()=>({task_id:'demo'})}},
    setInterval:()=>1,checkStatus(){},alert(msg){x.alertMessage=msg},console};
  vm.createContext(x);
  for (const name of ['closeAuthModal','resetUploadState','resumePendingAnalysis','startAnalysis']) vm.runInContext(extract(name), x);
  return x;
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('all executable scripts parse, including standalone feedback scripts',()=>{
  for(const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    if(!/application\/ld\+json/.test(match[1])) new vm.Script(match[2]);
  }
  for(const file of ['static/feedback.js','static/feedback-share.js','static/trial.js']) new vm.Script(fs.readFileSync(file,'utf8'));
});
test('guest can analyze without login',async()=>{
  const x=fixture();await x.startAnalysis();assert.equal(x.opened,0);assert.equal(x.uploads,1);
});
test('used guest trial opens signup and retains video',async()=>{
  const x=fixture();x.creditsRemaining=0;await x.startAnalysis();
  assert.equal(x.opened,1);assert.equal(x.uploads,0);assert(x.pendingAnalysis);assert.equal(x.payments,0);
});
test('login success preserves the pending intent; repeated auth events upload once',async()=>{
  const x=fixture();x.creditsRemaining=0;await x.startAnalysis();x.creditsRemaining=3;x.currentUser={id:'player'};x.closeAuthModal(false);
  x.resumePendingAnalysis();x.resumePendingAnalysis();await settle();assert.equal(x.uploads,1);assert(x.analysisBusy);
});
test('closing the login dialog preserves video but cancels auto-start',async()=>{
  const x=fixture();x.creditsRemaining=0;await x.startAnalysis();x.closeAuthModal();x.currentUser={id:'player'};x.resumePendingAnalysis();
  await settle();assert.equal(x.uploads,0);assert.equal(x.selectedFile.name,'shot.mov');
});
test('double clicks while credits load cannot create duplicate tasks',async()=>{
  const x=fixture();x.currentUser={};let release;x.fetchCredits=()=>new Promise(r=>release=r);
  const first=x.startAnalysis();await x.startAnalysis();release({credits_remaining:3});await first;
  assert.equal(x.uploads,1);
});
test('expired login at credit check returns to login with video intact',async()=>{
  const x=fixture();x.currentUser={};x.fetchCredits=async()=>({authExpired:true});await x.startAnalysis();
  assert.equal(x.opened,1);assert.equal(x.uploads,0);assert(!x.analysisBusy);assert(x.pendingAnalysis);
});
test('no credits opens payment without uploading',async()=>{
  const x=fixture();x.currentUser={};x.creditsRemaining=0;await x.startAnalysis();assert.equal(x.payments,1);assert.equal(x.uploads,0);assert(!x.analysisBusy);
});
test('failed credit lookup remains retryable and does not charge or upload',async()=>{
  const x=fixture();x.currentUser={};x.fetchCredits=async()=>null;await x.startAnalysis();assert(!x.analysisBusy);assert(!x.analyzeBtn.disabled);assert.equal(x.uploads,0);
});
test('401 during upload preserves video and reopens login',async()=>{
  const x=fixture();x.currentUser={};x.fetch=async()=>({ok:false,status:401});await x.startAnalysis();
  assert.equal(x.opened,1);assert(x.pendingAnalysis);assert(!x.analysisBusy);assert(x.selectedFile);
});
test('upload failure restores file controls and allows retry',async()=>{
  const x=fixture();x.currentUser={};x.fetch=async()=>{throw Error('network unavailable')};await x.startAnalysis();
  assert(!x.analysisBusy);assert(!x.fileInput.disabled);assert(!x.removeFile.disabled);assert(x.selectedFile);assert.match(x.alertMessage,/network unavailable/);
});
test('personal comparison matches phases and shows signed angle differences without a score', async()=>{
  const target={textContent:'',innerHTML:''};
  const elements={personalComparison:target,compareEarlier:{value:'before'},compareLater:{value:'after'}};
  const results=[{key_frames:[{phase:'release_frame',timestamp:1,angles:{knee_angle:150},image_url:'/results/before/release.png'}, {phase:'dip',angles:{knee_angle:90}}]},
    {key_frames:[{phase:'release_frame',timestamp:2,angles:{knee_angle:155},image_url:'/results/after/release.png'}]}];
  const x={document:{getElementById:id=>elements[id]},getAuthHeaders:async()=>({}),
    fetch:async()=>({ok:true,json:async()=>results.shift()}),console};
  vm.createContext(x);vm.runInContext(fs.readFileSync('static/trial.js','utf8'),x);
  vm.runInContext('saveTrialToAccount=async()=>true; historyEscape=v=>String(v);',x);
  await x.comparePersonalReports();
  assert.match(target.innerHTML,/\+5\.0°/);assert.match(target.innerHTML,/150\.0°/);
  assert(!target.innerHTML.includes('<h4>dip</h4>'));assert(!target.innerHTML.includes('improved'));
  elements.compareLater.value='before';await x.comparePersonalReports();
  assert.equal(target.textContent,'Choose two different reports.');
});
test('test dashboard renders histories, filters failures and searches cases without injecting HTML',()=>{
  const source=fs.readFileSync('scripts/testing/dashboard.html','utf8');
  const code=source.split('</script><script>')[1].split('</script>')[0];
  new vm.Script(code);
  class Element {
    constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.value='';this.attrs={};}
    append(...nodes){this.children.push(...nodes)}
    prepend(...nodes){this.children.unshift(...nodes)}
    replaceChildren(...nodes){this.children=[...nodes]}
    setAttribute(k,v){this.attrs[k]=v}
  }
  const elements=new Map();const get=id=>{if(!elements.has(id))elements.set(id,new Element('div'));return elements.get(id)};
  const run=(id,status)=>({id,checked_at:'2026-11-15T00:00:00Z',profile:'full',status,checks:[{id:'trial',name:'Trial',description:'quota',status,cases:[{id:'cookie',name:'refresh quota',status,detail:status==='failed'?'<script>bad()</script>':''}]}]});
  get('report-data').textContent=JSON.stringify([run('new','passed'),run('old','failed')]);get('filter').value='all';
  const context={document:{getElementById:get,createElement:tag=>new Element(tag)},console};vm.createContext(context);vm.runInContext(code,context);
  assert.equal(get('history').children.length,2);assert.equal(get('groups').children.length,1);
  assert.equal(get('visuals').children.length,3);
  assert.equal(get('visuals').children[0].children[0].children[0].textContent,'100%');
  get('filter').value='failed';get('filter').onchange();assert.equal(get('groups').children[0].textContent,'没有匹配的用例。');
  get('history').children[1].onclick();assert.equal(get('groups').children[0].tag,'details');
  assert.equal(get('visuals').children[0].children[0].children[0].textContent,'0%');
  get('search').value='missing term';get('search').oninput();assert.equal(get('groups').children[0].textContent,'没有匹配的用例。');
  get('search').value='refresh';get('search').oninput();assert.equal(get('groups').children[0].tag,'details');
  get('visuals').children[2].children[2].children[0].onclick();
  assert.equal(get('search').value,'Trial');assert.equal(get('filter').value,'all');
  get('visuals').children[1].children[1].children[1].onclick();
  assert.equal(get('visuals').children[0].children[0].children[0].textContent,'100%');
});

test('public navigation offsets follow header wrapping without replacing native anchors', () => {
  let height=83.2, observer, observed, listener;
  const properties={};const header={getBoundingClientRect:()=>({height})};
  const context=vm.createContext({
    document:{querySelector:()=>header,documentElement:{style:{setProperty:(key,value)=>properties[key]=value}}},
    window:{addEventListener:(type,fn)=>{assert.equal(type,'resize');listener=fn;}},
    ResizeObserver:class{constructor(callback){observer=callback;}observe(element){observed=element;}}
  });
  vm.runInContext(fs.readFileSync('static/public-navigation.js','utf8'),context);
  assert.equal(properties['--public-header-height'],'84px');assert.equal(observed,header);
  height=172;observer();assert.equal(properties['--public-header-height'],'172px');
  height=130;listener();assert.equal(properties['--public-header-height'],'130px');
  for(const path of ['templates/index.html','templates/guide.html'])assert.match(fs.readFileSync(path,'utf8'),/public-navigation.js/);
});

test('trend metrics use measured events and never turn missing values into zero', () => {
  const context={window:{}};vm.createContext(context);
  vm.runInContext(fs.readFileSync('static/shot-trends.js','utf8'),context);
  const metrics=context.window.ShotTrends.metrics;
  assert.equal(metrics({}).tempo,null);
  const frames=[{phase:'sync_frame_1',timestamp:0},{phase:'release_frame',timestamp:.4,angles:{elbow_angle:150}},{phase:'knee_min_frame',angles:{knee_angle:90}}];
  assert.equal(metrics({key_frames:frames}).tempo,.4);
  assert.equal(metrics({key_frames:frames}).knee,90);
  frames[1].timestamp=-1;assert.equal(metrics({key_frames:frames}).tempo,null);
  frames[1].angles.elbow_angle=null;assert.equal(metrics({key_frames:frames}).elbow,null);
});

test('history opens and scrolls even if trial claim is unavailable; guests see login', async()=>{
 const x=fixture();x.currentLang='en-US';x.saveTrialToAccount=async()=>false;
 x.renderHistoryList=()=>{x.rendered=true};x.addHistoryComparison=()=>{};
 x.window={ShotTrends:{mount:()=>{x.trends=true}}};
 x.document.getElementById('historyView').scrollIntoView=()=>{x.scrolled=true};
 vm.runInContext(extract('showHistory'),x);
 await x.showHistory();assert.equal(x.opened,1);
 x.currentUser={id:'isolated'};await x.showHistory();
 assert.equal(x.document.getElementById('historyView').style.display,'block');
 assert(x.scrolled);assert(x.rendered);assert(x.trends);
});

test('template choices show compact labels while preserving IDs and full descriptions',()=>{
 const options=[];const select={innerHTML:'',appendChild:option=>options.push(option)};
 const context={availableTemplates:[
  {id:'booker',name:'Devin Booker · Practice jumper · Side-oblique view',description:'Reference only; compare similar views.'},
  {id:'ray',name:'Ray Allen · Catch-and-shoot · Oblique view'},
  {id:'custom',name:'A'.repeat(80)}
 ],t:()=> 'No Template',document:{getElementById:()=>select,createElement:()=>({})}};
 vm.createContext(context);vm.runInContext(extract('updateTemplateSelect').split('// Upload area events')[0],context);context.updateTemplateSelect();
 assert.equal(options[0].textContent,'Devin Booker · Jumper');
 assert.equal(options[0].value,'booker');
 assert.match(options[0].title,/Side-oblique view/);assert.match(options[0].title,/Reference only/);
 assert.equal(options[1].textContent,'Ray Allen · Catch-and-shoot');
 assert.equal(options[2].textContent.length,40);
});

test('public analysis no longer offers or requests the human feedback pilot',async()=>{
 assert.doesNotMatch(html,/Feedback\.(?:open|mount)|id="retainForFeedback"|\/static\/feedback\.(?:js|css)|invitation-only pilot/);
 const x=fixture();x.currentUser={id:'test'};let uploadUrl;
 x.fetch=async url=>{uploadUrl=url;return {ok:true,json:async()=>({task_id:'demo'})}};
 await x.startAnalysis();assert(uploadUrl);assert.doesNotMatch(uploadUrl,/retain_for_feedback/);
 assert.match(html,/window\.ShotTrends\.mount\(history\)/);
});

test('history shows three charts, honest deltas, report links and gaps',()=>{
 const x={window:{}};vm.createContext(x);vm.runInContext(fs.readFileSync('static/shot-trends.js','utf8'),x);
 const row=(date,elbow)=>({created_at:date,video_filename:'<unsafe>.mov',metrics:{elbow,knee:100,tempo:.6}});
 const render=x.window.ShotTrends.render;
 const output=render([row('2026-11-01',140),row('2026-11-02',145)]);
 assert.equal((output.match(/class="trend-card"/g)||[]).length,3);
 assert.match(output,/\+5.0° vs previous report/);assert.match(output,/No change vs previous report/);
 assert.match(output,/data-trend-report="1"/);assert.match(output,/tabindex="0"/);
 assert.doesNotMatch(output,/<unsafe>/);assert.match(output,/&lt;unsafe&gt;/);
 const missing=render([row('2026-11-01',140),row('2026-11-02',null)]);
 assert.match(missing,/Needs two consecutive measurements/);assert.match(missing,/Not detected/);
 assert.doesNotMatch(missing,/[−-]140.0°/);
 const empty=render([]);assert.equal((empty.match(/No measurements yet/g)||[]).length,3);
});

test('rhythm replay uses the reported evidence interval and clears when switching reports', () => {
  const elements = new Map();
  function get(id) {
    if (!elements.has(id)) elements.set(id, {style:{}, pause(){}, load(){}, removeAttribute(name){delete this[name];}});
    return elements.get(id);
  }
  const x = {document:{getElementById:get}};
  vm.createContext(x);
  vm.runInContext(fs.readFileSync('static/shot-rhythm.js','utf8'),x);
  const card = x.renderShotRhythm({style:'two_motion', reason:'set_then_extend', replay_start:1,
    evidence_start:1.25, evidence_end:1.5, replay_url:'/results/demo/rhythm.mp4'}, 'demo');
  assert.equal(get('rhythmPoster').href,'/api/v1/export/demo/images/shot-rhythm.png');
  assert.equal(get('rhythmPoster').hidden,false);
  assert.equal(card.hidden,false);
  assert.equal(get('rhythmStyle').textContent,'Likely two-motion');
  get('rhythmVideo').duration = 1;
  get('rhythmVideo').onloadedmetadata();
  assert.equal(get('rhythmReplay').hidden,false);
  assert.equal(get('rhythmPlay').hidden,false);
  assert.equal(get('rhythmVideo').currentTime,0.25);
  let plays = 0;
  get('rhythmVideo').play = () => { plays++; return Promise.resolve(); };
  get('rhythmPlay').onclick();
  assert.equal(plays,1);
  assert.equal(get('rhythmVideo').currentTime,0);
  assert.equal(get('rhythmMarker').style.left,'25%');
  assert.equal(get('rhythmMarker').style.width,'25%');
  assert.equal(get('rhythmVideo').playbackRate,0.5);
  x.renderShotRhythm({style:'unclear',reason:'insufficient_tracking'});
  assert.equal(get('rhythmReplay').hidden,true);
  assert.equal(get('rhythmPlay').hidden,true);
  assert.match(get('rhythmReason').textContent,/shooting-hand side/);
  assert.equal(get('rhythmVideo').src,undefined);
  assert.equal(get('rhythmPoster').href,undefined);
  assert.equal(get('rhythmPoster').hidden,true);
  x.renderShotRhythm(null);
  assert.equal(card.hidden,true);
});

test('shot rhythm is the lead result for both upload entry points', () => {
  const report = html.slice(html.indexOf('id="resultsContainer"'));
  const position = report.indexOf('id="shotRhythmCard"');
  assert(position >= 0);
  for (const later of ['class="analysis-heading"', 'class="export-section"', 'id="keyFramesSection"']) {
    assert(report.indexOf(later) > position, later);
  }
  assert(!extract('displayResults').includes('location.hash'));
});
