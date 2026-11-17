/* One workspace over the existing analysis page; all mutations use bearer auth. */
(() => {
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const tr = (en, zh) => typeof currentLang !== 'undefined' && currentLang === 'zh-CN' ? zh : en;
  const labels = {quicker_release:'Quicker release',range:'More range',consistency:'More consistency',other:'Other',stationary:'Stationary',catch_and_shoot:'Catch and shoot',off_dribble:'Off the dribble'};
  let dialog, body, current, admin=false, dirty=false, captured=[], lastFocus, viewGeneration=0, busy=false;
  const formField = (name,label,value='',type='textarea',required=false) => `<label for="fb-${name}">${esc(label)}</label>${type==='textarea'?`<textarea id="fb-${name}" name="${name}" maxlength="3000" ${required?'required':''}>${esc(value)}</textarea>`:`<input id="fb-${name}" name="${name}" type="${type}" value="${esc(value)}" ${required?'required':''}>`}`;
  const select = (name,label,options,value) => `<label for="fb-${name}">${esc(label)}</label><select id="fb-${name}" name="${name}">${options.map(([v,l])=>`<option value="${v}" ${v===value?'selected':''}>${esc(l)}</option>`).join('')}</select>`;
  async function api(path='', options={}) {
    const headers = {...(typeof getAuthHeaders==='function'?await getAuthHeaders():{}), ...options.headers};
    if (options.body && !(options.body instanceof FormData)) { headers['Content-Type']='application/json'; options.body=JSON.stringify(options.body); }
    const res = await fetch('/api/v1/feedback'+path,{...options,headers});
    const data = await res.json();
    if (!res.ok) {const error=new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));error.status=res.status;throw error;}
    return data;
  }
  function message(text) { const el=document.getElementById('fbMessage'); if(el) el.textContent=text; }
  function init() {
    if(dialog) return;
    dialog=document.createElement('dialog'); dialog.className='fb fb-dialog'; dialog.setAttribute('aria-labelledby','fbTitle');
    dialog.innerHTML=`<div class="fb-head"><h2 id="fbTitle">${tr('Feedback & follow-up','人工反馈与复测')}</h2><div class="fb-actions"><button data-action="list">${tr('Training history','训练记录')}</button><button data-action="close">${tr('Close','关闭')}</button></div></div><div class="fb-body"><p id="fbMessage" role="status" aria-live="polite"></p><div id="fbContent"></div></div>`;
    document.body.append(dialog); body=dialog.querySelector('#fbContent');
    dialog.addEventListener('close',()=>{viewGeneration++;dialog.querySelectorAll('video').forEach(v=>v.pause());});
    dialog.addEventListener('cancel',e=>{if(busy||!leave())e.preventDefault();else dirty=false;});
    dialog.addEventListener('input',e=>{if(e.target.closest('#fbReview'))dirty=true; if(e.target.dataset.frameLabel!==undefined){captured[Number(e.target.dataset.frameLabel)].phase=e.target.value;dirty=true;} if(e.target.closest('#fbFollowup'))savePractice();});
    dialog.addEventListener('change',e=>{if(e.target.closest('#fbFollowup'))savePractice();});
    dialog.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(b&&!busy)act(b);});
    dialog.addEventListener('submit',e=>{e.preventDefault();if(!busy)submit(e.target);});
    window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
  }
  function leave(){return !dirty || confirm(tr('Discard unsaved feedback edits?','放弃未保存的反馈修改？'));}
  async function open(taskId) {
    init(); if(!leave())return; dirty=false;
    if(!dialog.open){lastFocus=document.activeElement;dialog.showModal();}
    const ticket=++viewGeneration;
    body.textContent=tr('Loading…','加载中…');message('');
    try {await api('/media-session',{method:'POST'}); const list=await api();if(ticket!==viewGeneration||!dialog.open)return;admin=list.admin; if(taskId)await detail(taskId,ticket);else renderList(list);}
    catch(e){if(ticket!==viewGeneration||!dialog.open)return;body.innerHTML=e.status===401?`<p>${tr('Sign in again to access your training records.','请重新登录后查看训练记录。')}</p><button class="primary" data-action="login">${tr('Sign in','登录')}</button>`:'<p>Could not load Training. Your saved records have not changed.</p><button data-action="list">Try again</button>';message(e.message);}
  }
  function renderList(data) {
    current=null;
    const groups=new Map();for(const r of data.items){const g=groups.get(r.thread_id)||{latest:r,count:0};g.count++;groups.set(r.thread_id,g);}
    const rows=[...groups.values()];
    body.innerHTML=`<h3>${tr('Your feedback and follow-ups','从这里开始下一次训练')}</h3><p class="fb-muted">${tr('Use this workspace after requesting human feedback: check your review, practice the suggested adjustment, then submit a follow-up. This is an invitation-only pilot, not an automatic training plan. For ordinary reports and trends, open History.','从分析结果申请反馈，练习一个调整，再上传复测。')}</p><small>Pilot ID: ${esc(data.subject)}</small>${admin?`<details><summary>Manage pilot access</summary><form id="fbGrant">${formField('owner','Pilot ID','','text',true)}${formField('count','Initial feedback invitations',1,'number',true)}<button class="primary">Save access</button></form><p class="fb-muted">Each initial feedback includes one follow-up. This does not change analysis credits.</p></details>`:''}<div>${rows.length?rows.map(({latest:r,count})=>`<div class="fb-row"><div><strong>${esc(r.goal?labels[r.goal]:r.filename)}</strong><small>${count} video${count===1?'':'s'} · ${esc(r.state)} · ${new Date(r.created_at*1000).toLocaleDateString()}</small></div><button data-action="detail" data-id="${r.id}">${tr('Open','打开')}</button></div>`).join(''):`<p class="fb-notice">${tr('No saved videos yet. Analyze a video with “Keep video for feedback” selected, then request feedback from the result.','暂无记录。上传时选择保留视频，分析完成后从结果申请反馈。')}</p>`}</div>`;
  }
  function video(r,label='Current video') {return `<h4>${esc(label)}</h4><video controls playsinline preload="metadata" src="${esc(r.video)}" data-video="${r.id}"></video><div class="fb-actions"><button data-action="speed" data-id="${r.id}">0.5× / 1×</button></div>`;}
  function reviewCard(r,v=r.review) {
    if(!v)return `<p class="fb-notice">${tr('Human feedback is awaiting review. Automatic observations are available below.','人工反馈等待处理中，下方可查看自动观察。')}</p>`;
    return `<article class="fb-review"><small>${esc(labels[r.goal]||r.goal)} · Feedback ${v.version}</small><h3>${esc(v.focus)}</h3><h4>What we observed</h4><p>${esc(v.observation)}</p><button data-action="seek" data-id="${r.id}" data-time="${v.evidence_seconds}">View evidence at ${Number(v.evidence_seconds).toFixed(2)}s</button><h4>What to practice</h4><p>${esc(v.drill)}</p><h4>How to film your follow-up</h4><p>${esc(v.retest)}</p><h4>What we’ll check</h4><p>${esc(v.criteria)}</p><small>Feedback by ${esc(v.author)} · ${new Date(v.published_at*1000).toLocaleDateString()}</small></article>`;
  }
  function frameStrip(r,frames,editable=false) {
    return `<div class="fb-frames">${frames.map((f,i)=>`<div class="fb-frame"><img alt="${esc(f.phase)} at ${Number(f.timestamp).toFixed(2)} seconds" src="/api/v1/feedback/media/${r.id}/${encodeURIComponent(f.asset)}"><small>${esc(f.phase)} · ${Number(f.timestamp).toFixed(2)}s</small>${editable?`<label>Frame label<input type="text" maxlength="80" data-frame-label="${i}" value="${esc(f.phase)}"></label><button type="button" data-action="remove-frame" data-index="${i}">Remove</button>`:`<button data-action="seek" data-id="${r.id}" data-time="${f.timestamp}">View moment</button>`}</div>`).join('')}</div>`;
  }
  async function detail(id,ticket=++viewGeneration) {
    const loaded=await api('/tasks/'+id);if(ticket!==viewGeneration||!dialog.open)return;current=loaded;dirty=false; const r=current;
    body.innerHTML=`<div class="fb-actions"><strong>${esc(r.filename)}</strong><small>${esc(r.state)} · Automatic analysis: ${esc(r.analysis_state)}</small><button data-action="refresh">Refresh status</button></div><p>${esc(r.problem)}</p>${r.error?`<p class="fb-notice">${esc(r.error)}</p>`:''}${r.state==='available'?requestForm(r):''}<div class="fb-grid"><div>${video(r)}${r.review?frameStrip(r,r.review.frames||[]):''}<details><summary>Automatic observations & keyframes</summary><p class="fb-muted">These are measurements and candidate observations, not confirmed training advice.</p>${frameStrip(r,r.keyframes)}${(r.result?.observations||[]).map(x=>`<p>${esc(x.skipped?'Not enough evidence to assess this movement.':x.description_en)}</p>`).join('')||'<p>No automatic observations available.</p>'}</details></div><div>${r.state!=='available'?reviewCard(r):'<p class="fb-notice">Your original video is saved. Choose one goal and request feedback.</p>'}${r.review?`<div class="fb-actions">${r.followup_id?`<button class="primary" data-action="detail" data-id="${r.followup_id}">View submitted follow-up</button>`:!r.parent||admin?'<button class="primary" data-action="followup">Submit a follow-up</button>':'<p>Your included follow-up is complete. Contact your reviewer for another round.</p>'}<button data-action="share">Create share link</button>${r.share_active?'<button data-action="revoke">Revoke share links</button>':''}</div><p class="fb-muted">Sharing lets anyone with the link view this video and published feedback.</p><div id="fbShareLink"></div>`:''}</div></div>${r.previous?`<section class="fb-compare"><h3>Compare with your previous video</h3><p class="fb-muted">Compare the same movement, not matching timestamps. Videos play independently.</p><div class="fb-grid"><div>${video(r.previous,'Previous video')}${frameStrip(r.previous,r.previous.review?.frames||r.previous.keyframes)}</div><div><h4>Practice record</h4><p>${esc(r.practice.completion)} · ${esc(r.practice.feeling)}</p><p>${esc(r.practice.notes)}</p>${r.practice.attempts?`<p>User-reported: ${r.practice.makes}/${r.practice.attempts} makes. This alone does not establish improvement.</p>`:''}${r.practice.conditions_changed?`<p class="fb-notice">Conditions changed: ${esc(r.practice.conditions_note)}</p>`:''}${reviewCard(r.previous)}</div></div></section>`:''}<div id="fbFollowupSlot"></div>${admin&&r.state!=='available'?editor(r):''}<details><summary>Training timeline</summary>${(r.timeline||[]).sort((a,b)=>a.created_at-b.created_at).map(x=>`<div class="fb-row"><span>${esc(x.filename)} · ${esc(x.state)}</span><button data-action="detail" data-id="${x.id}">Open</button></div>`).join('')}</details><details><summary>Manage saved videos</summary><p>Deleting this training thread removes its private videos and feedback links. Legacy analysis exports are managed separately.</p><button data-action="delete">Delete training thread</button></details>`;
    captured=r.draft?.frames ? [...r.draft.frames] : [...r.keyframes];
    document.getElementById('fbEditorFrames')?.replaceChildren();renderEditorFrames();
    for(const [name,max] of Object.entries({focus:1000,criteria:1000,retest:2000,author:100,problem:1000})) {const field=document.getElementById('fb-'+name);if(field)field.maxLength=max;}
    message('');
  }
  function requestForm(r){return `<form id="fbRequest"><h3>Get a clear next step</h3><p class="fb-muted">Human feedback is available to invited participants. Includes one follow-up; no extra analysis credit is charged for this request.</p>${select('goal','What would you like to improve?',Object.entries(labels).slice(0,4),r.goal)}${select('context','Video setting',['stationary','catch_and_shoot','off_dribble','other'].map(k=>[k,labels[k]]),r.context)}${formField('problem','What feels difficult about your shot?',r.problem,'textarea',true)}<div class="fb-actions"><button class="primary">Request feedback</button></div></form>`;}
  function editor(r) {const d=r.draft||{};return `<details ${!r.review?'open':''}><summary>Reviewer workspace</summary><div class="fb-grid"><div id="fbReviewVideo" class="fb-sticky">${video(r,'Review video')}</div><form id="fbReview"><h3>One focus for the next practice</h3><p class="fb-muted">Verify the video before giving advice. Your edits remain private until published.</p>${['observation','focus','drill','retest','criteria','author'].map(n=>formField(n,({observation:'What is visible in the video?',focus:'One training focus',drill:'Specific drill and amount',retest:'Follow-up filming instructions',criteria:'What will you check?',author:'Your display name and role'})[n],d[n]||'',n==='author'?'text':'textarea')).join('')}${formField('evidence_seconds','Evidence time (seconds)',d.evidence_seconds||0,'number')}<div class="fb-actions"><button type="button" data-action="use-time">Use current playback time</button><button type="button" data-action="frame">Capture keyframe at this time</button></div><div id="fbEditorFrames"></div><div class="fb-actions"><button class="primary" type="submit">Save draft</button><button type="button" data-action="publish">Publish saved feedback</button>${r.analysis_state==='failed'?'<button type="button" data-action="retry">Retry automatic analysis</button>':''}</div></form></div></details>`;}
  function renderEditorFrames(){captured.sort((a,b)=>a.timestamp-b.timestamp);const el=document.getElementById('fbEditorFrames');if(el)el.innerHTML=frameStrip(current,captured,true);const input=document.getElementById('fb-evidence_seconds');if(input){input.step='0.01';input.min=0;input.max=current.duration;}}
  function practiceKey(){return 'feedback-practice-'+current.id;}
  function savePractice(){const f=document.getElementById('fbFollowup');if(!f)return;const entries=Object.fromEntries(new FormData(f));delete entries.file;sessionStorage.setItem(practiceKey(),JSON.stringify(entries));}
  function followupForm(){
    const slot=document.getElementById('fbFollowupSlot');let d={};try{d=JSON.parse(sessionStorage.getItem(practiceKey())||'{}');}catch{}
    slot.innerHTML=`<form id="fbFollowup" class="fb-review"><h3>Submit your follow-up</h3><p>${esc(current.review.retest)}</p><small>Included with this feedback. No ordinary analysis credits are used.</small>${select('completion','Did you complete the practice?',[['done','Completed'],['partial','Partly'],['not_done','Not yet']],d.completion)}${select('feeling','How did it feel?',[['unsure','Not sure'],['smoother','Smoother'],['same','About the same'],['harder','More difficult']],d.feeling)}${formField('notes','What did you notice?',d.notes)}<div class="fb-grid"><div>${formField('makes','Makes (optional)',d.makes||'','number')}</div><div>${formField('attempts','Attempts (optional)',d.attempts||'','number')}</div></div>${select('conditions_changed','Were the filming or shooting conditions different?',[['false','No'],['true','Yes']],d.conditions_changed)}${formField('conditions_note','If different, describe the changes',d.conditions_note)}<label for="fb-file">Follow-up video (up to 10 seconds)</label><input id="fb-file" name="file" type="file" accept="video/*" required><div class="fb-actions"><button class="primary">Upload follow-up</button></div></form>`;
    slot.scrollIntoView({behavior:'smooth'});
  }
  async function act(b){const action=b.dataset.action;if(['close','list','detail','refresh'].includes(action)&&!leave())return;
    busy=true;b.disabled=true;message('');
    try {
      if(action==='close'){dirty=false;dialog.close();lastFocus?.focus();}
      else if(action==='login'){dirty=false;dialog.close();if(typeof openAuthModal==='function')openAuthModal();}
      else if(action==='list'){dirty=false;await open();}
      else if(action==='detail'){dirty=false;await detail(b.dataset.id);}
      else if(action==='refresh'){await detail(current.id);}
      else if(action==='speed'){const v=b.closest('.fb-actions').previousElementSibling;v.playbackRate=v.playbackRate===1?.5:1;b.textContent=v.playbackRate+'×';}
      else if(action==='seek'){const v=body.querySelector(`video[data-video="${b.dataset.id}"]`);v.currentTime=Number(b.dataset.time);v.scrollIntoView({block:'center'});v.focus();}
      else if(action==='use-time'){document.getElementById('fb-evidence_seconds').value=document.querySelector('#fbReviewVideo video').currentTime.toFixed(2);dirty=true;}
      else if(action==='frame'){const f=await api(`/tasks/${current.id}/frame`,{method:'POST',body:{seconds:Number(document.getElementById('fb-evidence_seconds').value)}});captured.push(f);dirty=true;renderEditorFrames();}
      else if(action==='remove-frame'){captured.splice(Number(b.dataset.index),1);dirty=true;renderEditorFrames();}
      else if(action==='publish'){if(dirty)throw Error('Save your draft before publishing.');await api(`/tasks/${current.id}/publish`,{method:'POST',body:{revision:current.revision}});await detail(current.id);message('Feedback published.');}
      else if(action==='followup'){followupForm();}
      else if(action==='share'){const result=await api(`/tasks/${current.id}/shares`,{method:'POST'});const url=location.origin+result.url;const el=document.getElementById('fbShareLink');el.innerHTML=`<p>Anyone with this link can view this feedback and video.</p><a class="fb-share-link" href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a><div class="fb-actions"><button data-action="revoke">Revoke share links</button></div>`;}
      else if(action==='revoke'){await api(`/tasks/${current.id}/shares`,{method:'DELETE'});await detail(current.id);message('Share links revoked.');}
      else if(action==='retry'){await api(`/tasks/${current.id}/retry`,{method:'POST'});message('Analysis queued. Refresh status shortly.');}
      else if(action==='delete'){if(!confirm('Delete this entire training thread, its private videos and feedback?'))return;await api(`/tasks/${current.id}`,{method:'DELETE'});dirty=false;await open();}
    }catch(e){message(e.message);}finally{busy=false;b.disabled=false;}
  }
  async function submit(f){busy=true;const button=f.querySelector('button[type=submit],button.primary');button.disabled=true;message('');
    try{const data=Object.fromEntries(new FormData(f));
      if(f.id==='fbFollowup')savePractice();
      f.querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=true);
      if(f.id==='fbRequest'){await api(`/tasks/${current.id}/request`,{method:'POST',body:data});await detail(current.id);message('Feedback requested. Check Training for updates.');}
      else if(f.id==='fbGrant'){await api('/grants',{method:'POST',body:{owner:data.owner,count:Number(data.count)}});message('Pilot access saved.');}
      else if(f.id==='fbReview'){data.revision=current.revision;data.evidence_seconds=Number(data.evidence_seconds);data.frames=captured;const r=await api(`/tasks/${current.id}/draft`,{method:'PUT',body:data});current.revision=r.revision;current.draft=r.draft;dirty=false;message('Draft saved. Publish when ready.');}
      else if(f.id==='fbFollowup'){
        const practice={completion:data.completion,feeling:data.feeling,notes:data.notes,conditions_changed:data.conditions_changed==='true',conditions_note:data.conditions_note,makes:data.makes===''?null:Number(data.makes),attempts:data.attempts===''?null:Number(data.attempts)};
        const fd=new FormData();fd.append('file',data.file);fd.append('practice',JSON.stringify(practice));fd.append('version',current.review.version);
        const keyName='feedback-upload-key-'+current.id;let key=sessionStorage.getItem(keyName);if(!key){key=crypto.randomUUID();sessionStorage.setItem(keyName,key);}fd.append('key',key);
        message('Uploading your follow-up…');const r=await api(`/tasks/${current.id}/followup`,{method:'POST',body:fd});sessionStorage.removeItem(practiceKey());await detail(r.id);message('Follow-up received. Your reviewer can now compare both videos.');
      }
    }catch(e){message(e.message);}finally{busy=false;f.querySelectorAll('input,textarea,select,button').forEach(el=>el.disabled=false);button.disabled=false;}
  }
  async function mount(taskId){
    let entry=document.getElementById('feedbackEntry');if(!entry){entry=document.createElement('section');entry.id='feedbackEntry';entry.className='fb fb-entry';document.getElementById('resultsContainer').prepend(entry);}
    entry.dataset.task=taskId;
    entry.innerHTML=`<h3>${tr('Human feedback & follow-up','知道下一次该练什么')}</h3><p>${tr('Invitation-only pilot: a reviewer checks your video, suggests one practice focus, and reviews a follow-up. Automatic analysis does not include human feedback.','为这份分析增加人工建议与复测，当前向受邀体验用户开放。')}</p><button class="primary" id="fbOpenResult">${tr('View feedback options','获取训练建议')}</button>`;
    document.getElementById('fbOpenResult').onclick=async()=>{
      try{await api('/tasks/'+taskId);await open(taskId);}
      catch(e){if(e.status!==404){init();await open(taskId);return;}
        init();if(!dialog.open)dialog.showModal();message('');body.innerHTML=`<h3>Attach the original video</h3><p>This older analysis no longer has a saved original. Upload the same clip to make human review possible. No analysis credits are charged.</p><form id="fbRestore"><label for="fb-original">Original video</label><input id="fb-original" type="file" accept="video/*" required><div class="fb-actions"><button class="primary">Save video</button></div></form>`;
        const f=document.getElementById('fbRestore');f.onsubmit=async ev=>{ev.preventDefault();ev.stopPropagation();const b=f.querySelector('button');b.disabled=true;try{const fd=new FormData();fd.append('file',document.getElementById('fb-original').files[0]);await api(`/tasks/${taskId}/restore-video`,{method:'POST',body:fd});await open(taskId);}catch(err){message(err.message);}finally{b.disabled=false;}};
      }
    };
    try{const r=await api('/tasks/'+taskId);if(entry.dataset.task!==taskId)return;if(r.review){entry.querySelector('h3').textContent=r.review.focus;entry.querySelector('p').textContent=r.review.drill;entry.querySelector('button').textContent=tr('View feedback & follow up','查看反馈与提交复测');}else if(r.state!=='available'){entry.querySelector('p').textContent=tr('Your feedback is awaiting review. Open Training to check progress.','反馈等待处理中，可在训练记录中查看进展。');}}catch{}
  }
  window.Feedback={open,mount};
})();
