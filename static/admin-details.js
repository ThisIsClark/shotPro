function opsLink(label, action) {
  const b=document.createElement('button');b.type='button';b.className='btn-sm';b.textContent=label;b.addEventListener('click',action);return b;
}
let opsDetailGeneration=0;
let opsMediaURLs=[];
function releaseOpsMedia(){opsMediaURLs.forEach(url=>URL.revokeObjectURL(url));opsMediaURLs=[];}
function detailPanel(title) {
  const generation=++opsDetailGeneration;
  releaseOpsMedia();document.getElementById('opsDetail')?.remove();
  const section=document.createElement('section');section.id='opsDetail';section.className='data-table-wrap';section.style.cssText='padding:24px;margin:24px 0;overflow-wrap:anywhere';
  const heading=document.createElement('h2');heading.textContent=title;
  const close=opsLink('关闭详情',()=>{opsDetailGeneration++;releaseOpsMedia();section.remove();});
  const body=document.createElement('div');body.textContent='Loading…';
  section.append(heading,close,body);document.querySelector('.main-content').prepend(section);
  section.scrollIntoView({behavior:'smooth',block:'start'});
  return {body,current:()=>generation===opsDetailGeneration};
}
function detailText(root,text){const p=document.createElement('p');p.textContent=text;root.append(p);}
function detailTable(root,title,headers,rows) {
  const h=document.createElement('h3');h.textContent=title;root.append(h);
  const wrap=document.createElement('div');wrap.style.overflowX='auto';const table=document.createElement('table');
  const head=document.createElement('tr');headers.forEach(x=>{const th=document.createElement('th');th.textContent=x;head.append(th);});table.append(head);
  for(const row of rows){const tr=document.createElement('tr');for(const value of row){const td=document.createElement('td');if(value?.nodeType)td.append(value);else td.textContent=value ?? '—';tr.append(td);}table.append(tr);}
  wrap.append(table);root.append(wrap);if(!rows.length)detailText(root,'没有记录（不代表历史上从未发生）');
}
async function openAnalysisDetail(task) {
  const panel=detailPanel('分析任务详情');
  try {
    const d=await apiFetch('/analyses/'+encodeURIComponent(task)+'/detail');if(!panel.current())return;
    const root=panel.body;root.replaceChildren();
    detailText(root,d.filename+' · '+d.id+' · '+d.state);
    if(d.owner)root.append(opsLink('查看用户 '+d.owner,()=>openUserDetail(d.owner)));
    detailText(root,'创建时间：'+new Date(d.created*1000).toLocaleString()+'；耗时：'+(d.elapsed_seconds ?? '未知')+' 秒');
    detailText(root,'失败原因：'+(d.error || '无已记录的错误'));
    detailText(root,'未检测到：'+(d.missing_phases===null?'历史数据未知':d.missing_phases.map(x=>x.label).join('、') || '无'));
    detailText(root,d.diagnostic_note);
    detailTable(root,'分析参数',['参数','值'],Object.entries(d.metadata));
    detailTable(root,'关键帧与角度',['阶段','视频秒数','帧号','角度'],(d.frames || []).map(f=>[f.phase,f.timestamp,f.frame_number,JSON.stringify(f.angles)]));
    detailText(root,'用户评价：'+(d.feedback?'有帮助 '+(d.feedback.helpful?'是':'否')+'；关键帧准确 '+(d.feedback.accurate?'是':'否'):'尚未评价'));
    if(d.media_available){
      const images=document.createElement('div');images.style.cssText='display:flex;flex-wrap:wrap;gap:12px';
      const button=opsLink('加载私有关键帧预览',async()=>{
        button.disabled=true;
        for(let i=0;i<(d.frames || []).length;i++){
          try {
            const r=await fetch('/api/v1/admin/analyses/'+encodeURIComponent(task)+'/media/'+i,{headers:{Authorization:'Bearer '+authToken}});
            if(!r.ok)throw new Error('图像不可用 ('+r.status+')');
            const blob=await r.blob();if(!panel.current())return;
            const url=URL.createObjectURL(blob);opsMediaURLs.push(url);
            const figure=document.createElement('figure');figure.style.margin='0';const img=document.createElement('img');img.src=url;img.alt=d.frames[i].phase;img.style.cssText='width:180px;max-width:100%;border-radius:8px';const caption=document.createElement('figcaption');caption.textContent=d.frames[i].phase;figure.append(img,caption);images.append(figure);
          }catch(e){if(panel.current())detailText(images,e.message);}
        }
      });root.append(button,images);
    }else detailText(root,'原报告图像已过期、删除或未保存在此实例，无法预览。');
  }catch(e){if(panel.current())panel.body.textContent='任务详情读取失败：'+e.message;}
}
async function openUserDetail(user) {
  if(!user)return;
  const panel=detailPanel('用户完整记录');
  try {
    const d=await apiFetch('/users/'+encodeURIComponent(user)+'/detail');if(!panel.current())return;
    const root=panel.body;root.replaceChildren();
    detailText(root,(d.profile?.email || '邮箱未知')+' · '+d.id);
    detailText(root,d.coverage);
    for(const [key,message] of Object.entries(d.errors))detailText(root,key+'：'+message);
    detailTable(root,'按时间排列的用户路径',['时间','事件','内容','报告'],d.timeline.map(e=>[new Date(e.created*1000).toLocaleString(),e.action,JSON.stringify(e.details),e.task && d.reports.some(r=>r.id===e.task)?opsLink('查看分析',()=>openAnalysisDetail(e.task)):e.task]));
    detailTable(root,'当前额度',['余额','累计授予'],(d.cloud.user_credits || []).map(x=>[x.credits_remaining,x.total_granted]));
    detailTable(root,'订阅',['套餐','状态','当前周期结束'],(d.cloud.user_subscriptions || []).map(x=>[x.plan,x.status,x.current_period_end]));
    detailTable(root,'支付处理记录',['Checkout','处理时间'],(d.cloud.payment_checkouts || []).map(x=>[x.checkout_id,x.processed_at]));
    detailText(root,'付款金额、退款和资金到账状态没有存于现有支付记录，不由本页推断。');
    detailTable(root,'训练反馈与复测',['报告','状态','目标','前次报告','练习记录','已发布反馈'],d.reviews.map(x=>[x.id,x.state,x.goal,x.parent?.id,JSON.stringify(x.practice),JSON.stringify(x.versions)]));
    root.append(opsLink('调整该用户额度',()=>openCreditsModal(user,d.cloud.user_credits?.[0]?.credits_remaining ?? 0)));
  }catch(e){if(panel.current())panel.body.textContent='用户详情读取失败：'+e.message;}
}
