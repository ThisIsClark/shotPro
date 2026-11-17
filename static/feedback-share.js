(async()=>{
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const status=document.getElementById('status');
 try{
  const token=location.hash.slice(1);
  if(!token)throw Error('This feedback link is incomplete. Ask the owner for a new link.');
  const res=await fetch('/api/v1/feedback/shared',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  const r=await res.json();if(!res.ok)throw Error(r.detail);
  const v=r.review;status.textContent='Published feedback · Version '+v.version;
  document.getElementById('content').innerHTML=`<p>${esc(r.problem)}</p><video controls playsinline preload="metadata" src="${esc(r.video)}"></video><article class="fb-review"><h3>${esc(v.focus)}</h3><h4>What we observed</h4><p>${esc(v.observation)}</p><button id="evidence">View evidence at ${Number(v.evidence_seconds).toFixed(2)}s</button><h4>What to practice</h4><p>${esc(v.drill)}</p><h4>How to film your follow-up</h4><p>${esc(v.retest)}</p><h4>What we’ll check</h4><p>${esc(v.criteria)}</p><small>Feedback by ${esc(v.author)}</small></article><a class="fb-button" href="/app">Open your training account</a>`;
  document.getElementById('evidence').onclick=()=>{const video=document.querySelector('video');video.currentTime=v.evidence_seconds;video.focus();};
 }catch(e){status.textContent=e.message;}
})();
