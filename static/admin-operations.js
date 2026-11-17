async function loadOperations() {
  const root = document.getElementById('opsContent');
  root.textContent = 'Loading…';
  try {
    const d = await apiFetch('/operations?days='+document.getElementById('opsDays').value);
    const cards = [['分析任务',d.total],['成功',d.completed],['失败',d.failed],['处理中',d.processing],['匿名试用',d.anonymous_started],['已保存的试用',d.saved_trials],['重复分析账户',d.repeat_accounts],['平均完成秒数',d.average_seconds ?? '—'],['用户评价数',d.feedback.responses],['认为有帮助',d.feedback.helpful],['认为关键帧准确',d.feedback.accurate]];
    root.replaceChildren();
    const grid = document.createElement('div'); grid.className='stats-grid';
    cards.forEach(([label,value]) => { const card=document.createElement('div'); card.className='stat-card'; const l=document.createElement('div');l.textContent=label;const v=document.createElement('div');v.className='value';v.textContent=value;card.append(l,v);grid.append(card); });
    root.append(grid);
    const note=document.createElement('p');note.textContent='按所选期间创建的任务统计；重复账户指期间内至少两次成功分析。平均耗时仅含已采集的 '+d.measured_durations+' 次成功任务。历史缺失耗时和关键帧数据以 — 显示。';root.append(note);
    function table(title,headers,rows) {
      const h=document.createElement('h2');h.textContent=title;root.append(h);
      const wrap=document.createElement('div');wrap.style.overflowX='auto';
      const t=document.createElement('table');const head=document.createElement('tr');
      headers.forEach(x=>{const c=document.createElement('th');c.textContent=x;head.append(c);});t.append(head);
      rows.forEach(row=>{const tr=document.createElement('tr');row.forEach(x=>{const td=document.createElement('td');if(x && typeof x==='object' && x.nodeType) td.append(x); else td.textContent=x ?? '—';tr.append(td);});t.append(tr);});
      if(!rows.length){const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=headers.length;td.textContent='暂无数据';tr.append(td);t.append(tr);}
      wrap.append(t);root.append(wrap);
    }
    table('匿名试用转化', ['步骤','去重访客数'], d.funnel.map(x=>[x.label,x.count]));
    const explanation=document.createElement('p');explanation.textContent='同一浏览器在本期间首次被记录的来源；只有访问后创建的试用进入漏斗。保存表示认领报告，不等于新注册。清除 Cookie 或跨设备会被视为不同访客；本地开发访问不上报。';root.append(explanation);
    table('渠道表现', ['来源','访客','开始试用','完成试用','保存到账户'],d.channels.map(x=>[x.source,x.visitors,x.started,x.completed,x.saved]));
    table('最近 100 个分析任务', ['任务 ID','视频','类型','状态','关键帧数','失败原因'],d.recent.map(x=>[opsLink(x.id,()=>openAnalysisDetail(x.id)),x.filename,x.type,x.state,x.frames,x.error]));
    if (d.journey) {
      table('完整体验路径（同一访客按顺序）', ['步骤','访客数','上一步转化率'], d.journey.map(x=>[x.label,x.count,x.conversion===null?'—':x.conversion+'%']));
      const note=document.createElement('p');note.textContent='结果查看后：提交注册 '+d.registration_submitted+'；经认证服务确认的新注册 '+d.registered_after_view+'；保存后查看前后对比 '+d.comparison_accounts+'。注册是独立分支，老用户无需重新注册。历史未记录的步骤不推断为已发生。';root.append(note);
      for (const [label,key] of [['来源细分','sources'],['落地页细分','landings'],['推广活动细分','campaigns']]) {
        table(label,['分组',...d.journey.map(x=>x.label)],d[key].map(x=>[x.name,...x.counts]));
      }
      table('未检测到的关键帧（'+d.quality_measured+' 个已采集任务）',['关键帧','任务数'],d.missing_summary.map(x=>[x.label,x.count]));
      const caution=document.createElement('p');caution.textContent='未检测到某帧不等于用户动作错误；可能是片段不完整、遮挡或检测证据不足。历史数据未知时不会计为缺失。';root.append(caution);
      table('异常任务（共 '+d.anomaly_count+' 个，展示最近 100 个）',['任务','视频','状态','缺失帧','用户'],d.anomalies.map(x=>[opsLink(x.id,()=>openAnalysisDetail(x.id)),x.filename,x.stalled?'长时间处理中':x.state,x.missing?.join(', ') || '—',x.owner?opsLink(x.owner,()=>openUserDetail(x.owner)):'匿名']));
      table('期间内分析用户',['用户','分析次数'],d.accounts.map(x=>[opsLink(x.id,()=>openUserDetail(x.id)),x.analyses]));
    }
    table('最近 100 次额度调整', ['时间','操作人','用户','调整前','调整后','原因'],d.credit_changes.map(x=>[new Date(x.created*1000).toLocaleString(),x.actor,x.target,x.before_balance,x.after_balance,x.reason]));
  } catch(e) { root.textContent='运营数据读取失败，请稍后刷新。'+e.message; }
}
