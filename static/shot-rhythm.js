// The playback is a private extract. Evidence times refer to the original upload.
function renderShotRhythm(rhythm, taskId) {
    const card = document.getElementById('shotRhythmCard');
    const replay = document.getElementById('rhythmReplay');
    const video = document.getElementById('rhythmVideo');
    const play = document.getElementById('rhythmPlay');
    const poster = document.getElementById('rhythmPoster');
    poster.hidden = true;
    poster.removeAttribute('href');
    const time = document.getElementById('rhythmTime');
    const marker = document.getElementById('rhythmMarker');
    const labels = {one_motion: 'Likely one-motion', two_motion: 'Likely two-motion', unclear: 'Unclear'};
    const reasons = {
        overlapping_lift: 'Your elbow opens while your upper arm is still rising into the release.',
        set_then_extend: 'Your upper arm settles near the set point before the main elbow extension.',
        insufficient_tracking: 'Your shooting arm could not be tracked through enough consecutive frames. Try filming from your shooting-hand side.',
        partial_motion: 'Record the full lift through the release so both movements can be compared.',
        mixed_timing: 'The lift and extension show mixed timing in this shot.'
    };
    video.onloadedmetadata = null;
    video.onerror = null;
    play.onclick = null;
    play.hidden = true;
    video.pause();
    video.removeAttribute('src');
    video.load();
    marker.hidden = true;
    card.hidden = !rhythm || !Object.hasOwn(labels, rhythm.style);
    if (card.hidden) return null;
    document.getElementById('rhythmStyle').textContent = labels[rhythm.style];
    document.getElementById('rhythmReason').textContent = reasons[rhythm.reason] || reasons.mixed_timing;
    const hasTimes = Number.isFinite(rhythm.evidence_start) && Number.isFinite(rhythm.evidence_end);
    time.textContent = hasTimes ? `Evidence in your video · ${rhythm.evidence_start.toFixed(2)}–${rhythm.evidence_end.toFixed(2)} s` : '';
    const evidenceTime = time.textContent;
    replay.hidden = !rhythm.replay_url;
    play.hidden = replay.hidden;
    if (!replay.hidden && taskId && rhythm.style !== 'unclear') {
        poster.hidden = false;
        poster.href = `/api/v1/export/${encodeURIComponent(taskId)}/images/shot-rhythm.png`;
    }
    if (!replay.hidden) {
        video.src = rhythm.replay_url;
        video.defaultPlaybackRate = 0.5;
        video.onloadedmetadata = () => {
            video.playbackRate = 0.5;
            if (!hasTimes || !Number.isFinite(video.duration) || video.duration <= 0) return;
            video.currentTime = Math.max(0, Math.min(video.duration, rhythm.evidence_start - rhythm.replay_start));
            marker.style.left = 100 * (rhythm.evidence_start - rhythm.replay_start) / video.duration + '%';
            marker.style.width = 100 * (rhythm.evidence_end - rhythm.evidence_start) / video.duration + '%';
            marker.hidden = false;
        };
        play.onclick = () => {
            video.currentTime = 0;
            video.playbackRate = 0.5;
            video.play().catch(() => {
                if (!replay.hidden && video.paused) video.focus();
            });
        };
        video.onerror = () => {
            replay.hidden = true;
            play.hidden = true;
            time.textContent = [evidenceTime, 'Replay unavailable.'].filter(Boolean).join(' · ');
        };
    }
    return card;
}
