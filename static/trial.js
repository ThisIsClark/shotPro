/* Anonymous trial handoff and personal before/after report comparison. */
async function saveTrialToAccount() {
    try {
        const response = await fetch('/api/v1/trial/claim', {method: 'POST', headers: await getAuthHeaders()});
        if (!response.ok) throw new Error('Could not save this report. Sign in again and retry.');
        const data = await response.json();
        window.opsVisitorReady = true;
        window.recordOperationsVisit?.();
        const hint = document.getElementById('oneUploadHint');
        if (data.claimed.length) hint.textContent = 'Your trial report is saved in History. Your account credits are unchanged.';
        document.querySelectorAll('.login-guidance').forEach(el => el.remove());
        return true;
    } catch (error) {
        document.getElementById('oneUploadHint').textContent = error.message;
        return false;
    }
}
function historyEscape(value) {
    const el = document.createElement('span'); el.textContent = String(value ?? ''); return el.innerHTML;
}
function addHistoryComparison(items) {
    const completed = items.filter(x => x.status === 'completed');
    if (completed.length < 2) return;
    const options = completed.map(x => `<option value="${historyEscape(x.task_id)}">${historyEscape(x.video_filename)} · ${historyEscape(x.created_at.slice(0,16))}</option>`).join('');
    const panel = document.createElement('section'); panel.className = 'personal-comparison';
    panel.innerHTML = `<h3>Compare with your earlier shot</h3><p>Use similar camera angles, shooting distance and shot type. A change in angle does not by itself mean improvement.</p><div class="comparison-controls"><label>Earlier report<select id="compareEarlier">${options}</select></label><label>Later report<select id="compareLater">${options}</select></label><button type="button" id="compareReports">Compare keyframes</button></div><div id="personalComparison" aria-live="polite"></div>`;
    document.getElementById('historyContent').prepend(panel);
    document.getElementById('compareEarlier').selectedIndex = 1;
    document.getElementById('compareReports').onclick = comparePersonalReports;
}
async function comparePersonalReports() {
    const target = document.getElementById('personalComparison');
    const a = document.getElementById('compareEarlier').value, b = document.getElementById('compareLater').value;
    if (a === b) { target.textContent = 'Choose two different reports.'; return; }
    target.textContent = 'Loading comparison…';
    try {
        if (!await saveTrialToAccount()) throw new Error('Please sign in again.');
        const headers = await getAuthHeaders();
        const results = await Promise.all([a,b].map(async id => {
            const r = await fetch(`/api/v1/videos/tasks/${encodeURIComponent(id)}/result`, {headers});
            if (!r.ok) throw new Error('Could not load both reports. Refresh History and try again.');
            return r.json();
        }));
        const frames = r => r.key_frames || [];
        const right = new Map(frames(results[1]).map(f => [f.phase, f]));
        const pairs = frames(results[0]).filter(f => right.has(f.phase)).sort((x,y) => (x.timestamp || 0)-(y.timestamp || 0));
        const image = f => {
            const url = f.image_url || f.image_path || '';
            if (!url.startsWith('/results/') && !url.startsWith('https://')) return '';
            return `<img src="${historyEscape(url)}" alt="${historyEscape(f.phase)}" loading="lazy">`;
        };
        target.innerHTML = pairs.map(f => {
            const g = right.get(f.phase);
            const angles = Object.keys(f.angles || {}).filter(k => Number.isFinite(f.angles[k]) && Number.isFinite(g.angles?.[k]));
            return `<article><h4>${historyEscape(f.phase.replaceAll('_',' '))}</h4><div class="comparison-pair"><div><p>Earlier</p>${image(f)}</div><div><p>Later</p>${image(g)}</div></div><table><thead><tr><th>Angle</th><th>Earlier</th><th>Later</th><th>Change</th></tr></thead><tbody>${angles.map(k => {const d=g.angles[k]-f.angles[k];return `<tr><td>${historyEscape(k)}</td><td>${f.angles[k].toFixed(1)}°</td><td>${g.angles[k].toFixed(1)}°</td><td>${d>0?'+':''}${d.toFixed(1)}°</td></tr>`;}).join('')}</tbody></table></article>`;
        }).join('') || 'These reports have no matching keyframes to compare.';
        if (pairs.length) window.recordJourney?.('comparison_viewed', b, a);
    } catch (e) { target.textContent = e.message; }
}
function showTrialResume(data) {
    let button = document.getElementById('resumeTrial');
    if (!data.task_id) { if (button) button.remove(); return; }
    if (!button) {
        button = document.createElement('button'); button.id = 'resumeTrial'; button.type = 'button';
        button.className = 'action-btn';
        document.getElementById('oneUploadHint').after(button);
    }
    button.textContent = data.state === 'completed' ? 'View your trial report' : 'Check your analysis';
    button.onclick = async () => {
        if (data.state === 'completed') await viewHistoryDetail(data.task_id);
        else {
            currentTaskId = data.task_id;
            progressContainer.style.display = 'block';
            clearInterval(pollInterval); pollInterval = setInterval(checkStatus, 1000);
            await checkStatus();
        }
    };
}
