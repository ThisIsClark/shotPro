// Establish cookie via the existing trial bootstrap; never compete to initialize it.
(() => {
  const excluded = () => ['localhost','127.0.0.1'].includes(location.hostname) || localStorage.getItem('skip_tracking') === '1';
  const engine = document.body.hasAttribute('data-engine-auth');
  const endpoint = engine ? '/api/v1/videos/telemetry' : '/api/v1/audit';
  let sent = false;
  window.recordOperationsVisit = async function() {
    try {
      if (excluded() || sent) return;
      sent=true;
      const params=new URLSearchParams(location.search);
      let source=params.get('utm_source');
      if (!source && document.referrer) {
        const ref=new URL(document.referrer);
        if (ref.host!==location.host) source=ref.hostname;
      }
      const r=await fetch(endpoint + '/visit',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({source:(source || 'direct').slice(0,80), landing:location.pathname.slice(0,200),campaign:(params.get('utm_campaign') || '').slice(0,100)}),keepalive:true});
      if(!r.ok)sent=false;
    } catch (_) {sent=false;}
  };
  window.recordJourney = async function(action, task, earlier) {
    try {
      if(excluded())return;
      const headers=typeof getAuthHeaders==='function'?await getAuthHeaders():{};
      headers['Content-Type']='application/json';
      await fetch(endpoint + '/journey',{method:'POST',headers,body:JSON.stringify({action,task,earlier}),keepalive:true});
    } catch (_) { /* Analytics never blocks the product. */ }
  };
  if(engine) {
    document.addEventListener('DOMContentLoaded', window.recordOperationsVisit);
  } else if(window.opsVisitorReady)window.recordOperationsVisit();
  if(location.pathname.startsWith('/guides')) {
    if(!excluded())fetch('/api/v1/trial/status').then(r=>{if(r.ok)window.recordOperationsVisit();}).catch(()=>{});
  }
})();
