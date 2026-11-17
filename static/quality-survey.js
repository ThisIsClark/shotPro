window.mountQualitySurvey = function(task, container) {
  document.getElementById('qualitySurvey')?.remove();
  if (!task) return;
  const form=document.createElement('form');form.id='qualitySurvey';form.className='glass-card';form.style.cssText='padding:20px;margin-top:24px';
  const title=document.createElement('h3');title.textContent='Was this analysis useful?';form.append(title);
  const fields=[];
  for(const text of ['Did this help you spot something to work on?','Were the keyframes accurate?']) {
    const label=document.createElement('label');label.style.cssText='display:block;margin:12px 0';label.append(document.createTextNode(text+' '));
    const select=document.createElement('select');select.required=true;
    [['','Choose…'],['yes','Yes'],['no','No']].forEach(([value,text])=>{const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option);});
    label.append(select);form.append(label);fields.push(select);
  }
  const button=document.createElement('button');button.type='submit';button.className='btn btn-secondary';button.textContent='Send feedback';
  const status=document.createElement('p');status.setAttribute('aria-live','polite');form.append(button,status);
  form.addEventListener('submit',async e=>{
    e.preventDefault();button.disabled=true;
    try {
      const headers=await getAuthHeaders();headers['Content-Type']='application/json';
      const response=await fetch('/api/v1/trial/reports/'+encodeURIComponent(task)+'/feedback',{method:'POST',headers,body:JSON.stringify({helpful:fields[0].value==='yes',accurate:fields[1].value==='yes'})});
      if(!response.ok)throw new Error('Could not save feedback. Please try again.');
      status.textContent='Thanks — your feedback helps us improve the analysis.';
    } catch(e) { status.textContent=e.message; }
    finally {button.disabled=false;}
  });container.append(form);
};
