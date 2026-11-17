/* Private report metrics; no score or improvement is inferred from a change. */
(() => {
  const definitions = [['elbow','Release elbow angle','°'], ['knee','Deepest knee angle','°'], ['tempo','Dip-to-release time','s']];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function metrics(result) {
    const frames = result.key_frames || [];
    const get = phase => frames.find(f => f.phase === phase);
    const dip=get('sync_frame_1'), release=get('release_frame');
    const finite = v => typeof v === 'number' && Number.isFinite(v) ? v : null;
    const start=finite(dip?.timestamp), end=finite(release?.timestamp);
    return {tempo:start!==null && end!==null && end>start ? end-start : null,
      knee:finite(get('knee_min_frame')?.angles?.knee_angle), elbow:finite(release?.angles?.elbow_angle)};
  }
  let generation=0;
  async function mount(items) {
    const ticket=++generation;
    const panel=document.createElement('section');panel.className='shot-trends';
    panel.innerHTML='<h3>Your shooting trends</h3><p>Loading recent measurements…</p>';
    document.getElementById('historyContent').prepend(panel);
    const recent=items.filter(x=>x.status==='completed').sort((a,b)=>new Date(b.created_at)-new Date(a.created_at)).slice(0,10).reverse();
    let headers; try { headers=await getAuthHeaders(); } catch { panel.querySelector('p').textContent='Could not load trends. Reopen History to try again.'; return; }
    const rows=await Promise.all(recent.map(async item=>{try{const r=await fetch(`/api/v1/videos/tasks/${encodeURIComponent(item.task_id)}/result`,{headers});if(!r.ok)throw Error();return {...item,metrics:metrics(await r.json())};}catch{return {...item,metrics:{},unavailable:true};}}));
    if(ticket!==generation || !panel.isConnected)return;
    panel.innerHTML=render(rows);
    const open = event => {
      const point=event.target.closest('[data-trend-report]');
      if (!point || !panel.contains(point)) return;
      if (event.type==='keydown' && !['Enter',' '].includes(event.key)) return;
      if (event.type==='keydown') event.preventDefault();
      const row=rows[Number(point.dataset.trendReport)];
      if(row) viewHistoryDetail(row.task_id);
    };
    panel.addEventListener('click',open);
    panel.addEventListener('keydown',open);
  }
  function render(rows) {
    const format=(value,key)=>Number.isFinite(value)?value.toFixed(key==='tempo'?2:1):'—';
    const cards=definitions.map(([key,label,unit])=>{
      const values=rows.map(r=>r.metrics[key]);
      const latest=values.at(-1), previous=values.at(-2);
      const diff=Number.isFinite(latest)&&Number.isFinite(previous)?latest-previous:null;
      const change=diff===null?'Needs two consecutive measurements':Math.abs(diff)<(key==='tempo'?.005:.05)?'No change vs previous report':`${diff>0?'+':'−'}${format(Math.abs(diff),key)}${unit} vs previous report`;
      // Stable angle scale avoids exaggerating small changes. Timing starts at zero.
      const ceiling=key==='tempo'?Math.max(1,Math.ceil(Math.max(0,...values.filter(Number.isFinite))*2)/2):180;
      const x=i=>48+i*264/Math.max(1,rows.length-1), y=v=>148-120*Math.min(ceiling,Math.max(0,v))/ceiling;
      const ticks=[0,ceiling/2,ceiling].map(v=>`<line x1="48" y1="${y(v)}" x2="312" y2="${y(v)}" class="trend-gridline"/><text x="40" y="${y(v)+4}" text-anchor="end">${format(v,key)}</text>`).join('');
      const marks=values.map((v,i)=>{
        if(!Number.isFinite(v))return '';
        const line=i&&Number.isFinite(values[i-1])?`<line x1="${x(i-1)}" y1="${y(values[i-1])}" x2="${x(i)}" y2="${y(v)}" class="trend-line"/>`:'';
        const title=`${rows[i].created_at.slice(0,10)} · ${rows[i].video_filename}: ${format(v,key)}${unit}. Open analysis`;
        return `${line}<g role="button" tabindex="0" data-trend-report="${i}" aria-label="${esc(title)}" class="trend-point"><title>${esc(title)}</title><circle cx="${x(i)}" cy="${y(v)}" r="14" fill="transparent"/><circle cx="${x(i)}" cy="${y(v)}" r="${i===rows.length-1?6:4}" class="trend-dot"/></g>`;
      }).join('');
      const valid=values.filter(Number.isFinite).length;
      return `<article class="trend-card"><h4>${label}</h4><div class="trend-value">${format(latest,key)}<span>${unit}</span></div><div class="trend-change">${change}</div>${valid?`<svg viewBox="0 0 340 185" role="group" aria-label="${label}, oldest to newest">${ticks}${marks}<text x="48" y="176">${esc(rows[0].created_at.slice(5,10))}</text><text x="312" y="176" text-anchor="end">${esc(rows.at(-1).created_at.slice(5,10))}</text></svg>`:'<div class="trend-empty">No measurements yet</div>'}<p class="trend-caption">${valid<2?'Add another comparable analysis to see a trend.':'Oldest → newest · Click a point to open its analysis.'}</p></article>`;
    }).join('');
    return `<h3>See how your shot changes</h3><p>Three views of your latest ${rows.length} completed analyses. Large values show your latest report; changes compare it with the previous report.</p><div class="trend-cards">${cards}</div><p class="trend-context">Change is not a score. Compare the same camera angle, distance and shot type. Timing is measured in the video; do not compare slow-motion with real-time clips.</p><details class="trend-details"><summary>View all measurements and reports</summary><div class="trend-table-wrap"><table><thead><tr><th>Report</th>${definitions.map(([,label,unit])=>`<th>${label} (${unit})</th>`).join('')}</tr></thead><tbody>${rows.map((r,i)=>`<tr><td><button type="button" data-trend-report="${i}">${esc(r.created_at.slice(0,10))} · ${esc(r.video_filename)}</button></td>${definitions.map(([key])=>`<td>${Number.isFinite(r.metrics[key])?format(r.metrics[key],key):r.unavailable?'Report unavailable':'Not detected'}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`;
  }
  window.ShotTrends={metrics,mount,render};
})();
