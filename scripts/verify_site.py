#!/usr/bin/env python3
"""Isolated regression runner with case-level results and a portable HTML dashboard."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from testing.report import render

CATALOG=[
 ('admin-ui','管理后台界面','脚本语法、安全文本渲染和接口失败状态。','node','tests/admin/frontend.cjs','quick'),
 ('admin','管理后台运营统计','匿名渠道漏斗、认领去重、分析质量和权限。','discover','tests/admin','quick'),
 ('test-system','测试与报告系统','失败、跳过、超时、历史结果、安全展示和本地监听。','discover','tests/testing','quick'),
 ('public-pages','公开页面与 SEO','元信息、链接、资源、站点地图及公开页面。','discover','tests/web','quick'),
 ('production-proxy','正式域名代理','公开页面、Google 回调、私有报告和索引头转发。','node','tests/web/production-proxy.cjs','quick'),
 ('frontend-flow','前端操作流程','匿名上传、登录承接、重复点击和个人关键帧对比；使用 DOM/API 替身。','node','tests/web/frontend-flow.cjs','quick'),
 ('anonymous-trial','匿名试用与账户隔离','额度、并发预约、失败重试、认领、权限、媒体访问及任务生命周期。','discover','tests/trial','quick'),
 ('core','核心依赖','FastAPI、视频处理和数值计算依赖可导入。','script','test_core.py','full'),
 ('imports','模块导入','分析模块与依赖导入冒烟检查。','script','test_import.py','full'),
 ('keyframes','关键帧时序','关键帧边界、真实姿态固定数据及时间顺序回归。','file','test_keyframe_timing.py','full'),
 ('phase-detector','投篮阶段','准备、举球、出手、跟随以及下一次投篮重置。','file','test_phase_detector_optimization.py','full'),
 ('templates','参考模板','检查当前安装模板的图片、角度及曲线对比。','discover','tests/templates','full'),
 ('feedback','训练反馈','保存、反馈、复测、分享及私有媒体访问。','discover','tests/feedback','full'),
 ('landmarks','骨骼绘制','关键点绘制及膝盖位置验证；需要 MediaPipe 运行环境。','file','test_landmark_fixes.py','extended'),
 ('real-video','真实视频完整链路','视频分析、关键帧、ZIP/PDF、认领、跨账号隔离、历史和删除。','video','','extended'),
 ('live-public','运行中网站','只读检查运行中站点的页面、资源、健康检查及 SEO。','live','','live'),
]

def tap_cases(output):
    cases=[]
    for line in output.splitlines():
        match=re.match(r'^(not ok|ok) (\d+) - (.+)',line)
        if match:
            name=match[3];skip='# SKIP' in name or '# TODO' in name
            cases.append({'id':'frontend.'+match[2],'name':name,'status':'skipped' if skip else ('passed' if match[1]=='ok' else 'failed'), 'seconds':0,'detail':output if match[1]=='not ok' else ''})
        elif cases:
            duration=re.search(r'duration_ms: ([\d.]+)',line)
            if duration:cases[-1]['seconds']=round(float(duration[1])/1000,3)
    return cases

def execute(command,env,timeout):
    try:
        p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout)
        return p.returncode,p.stdout+p.stderr
    except subprocess.TimeoutExpired as exc:
        def text(v): return v.decode(errors='replace') if isinstance(v,bytes) else (v or '')
        return 124,text(exc.stdout)+text(exc.stderr)+f'\nTimed out after {timeout} seconds'
    except OSError as exc:
        return 127,str(exc)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quick',action='store_true',help='Run public pages, frontend and trial checks only')
    parser.add_argument('--extended',action='store_true',help='Also run MediaPipe drawing and the real video lifecycle')
    parser.add_argument('--video',type=Path,help='Video for extended lifecycle (implies extended)')
    parser.add_argument('--live-url',help='Read-only check of an existing local/staging server')
    parser.add_argument('--node',help='Node 18+ executable')
    parser.add_argument('--report-dir',type=Path,default=ROOT/'artifacts/verification')
    args=parser.parse_args()
    if args.quick and (args.extended or args.video):parser.error('--quick cannot be combined with extended/video')
    extended=args.extended or bool(args.video)
    node=args.node or os.environ.get('NODE_BINARY') or shutil.which('node')
    bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
    if not node and bundled.exists():node=str(bundled)
    now=datetime.now(timezone.utc)
    run_id=now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    report=args.report_dir.resolve();folder=report/'runs'/run_id;folder.mkdir(parents=True)
    revision=subprocess.run(['git','rev-parse','--short','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
    run={'id':run_id,'checked_at':now.isoformat(),'profile':'quick' if args.quick else ('extended' if extended else 'full'),
         'git_revision':revision+(' · working tree modified' if subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True).stdout.strip() else ''),'status':'running','passed':None,'checks':[]}
    for ident,name,description,kind,target,profile in CATALOG:
        enabled=profile=='quick' or (profile=='full' and not args.quick) or (profile=='extended' and extended) or (profile=='live' and bool(args.live_url))
        reason=None if enabled else '此运行未选择该检查；不计入通过。'
        run['checks'].append({'id':ident,'name':name,'description':description,'status':'pending' if enabled else 'skipped','reason':reason,'cases':[],'seconds':0,'exit_code':None})
    started=time.monotonic()
    def save():
        run['seconds']=round(time.monotonic()-started,2);render(report,run)
    save()
    try:
        with tempfile.TemporaryDirectory(prefix='formrefine-check-') as temp:
            env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONWARNINGS='ignore',SUPABASE_URL='',SUPABASE_ANON_KEY='',SUPABASE_SERVICE_KEY='',CREEM_API_KEY='',
                     TRIAL_DB_PATH=temp+'/trials.sqlite3',UPLOAD_DIR=temp+'/uploads',RESULTS_DIR=temp+'/results',FEEDBACK_DIR=temp+'/feedback',
                     MPLCONFIGDIR=temp+'/matplotlib',SEO_SITE_URL='https://formrefine.ai',SEO_INDEXABLE='true',NO_COLOR='1')
            for check,spec in zip(run['checks'],CATALOG):
                if check['status']=='skipped':continue
                ident,_,_,kind,target,_=spec
                case_path=folder/(ident+'.cases.json')
                if kind in ('discover','file'):
                    command=[sys.executable,'scripts/testing/case_runner.py','--output',str(case_path),'--'+kind,target]
                elif kind=='node':command=[node or 'node','--test','--test-reporter=tap',target]
                elif kind=='video':command=[sys.executable,'scripts/verify_trial_video.py',str((args.video or ROOT/'modelVideo/Booker-model.mp4').resolve())]
                elif kind=='live':command=[sys.executable,'scripts/verify_live_site.py',args.live_url]
                else:command=[sys.executable,target]
                check['status']='running';save();print(f'Running {ident}…',flush=True)
                start=time.monotonic();code,output=execute(command,env,240)
                (folder/(ident+'.log')).write_text(output,encoding='utf-8')
                cases=json.loads(case_path.read_text()) if case_path.exists() else (tap_cases(output) if kind=='node' else [])
                if not cases:
                    cases=[{'id':ident+'.process','name':check['name']+'（进程级检查）','status':'passed' if code==0 else 'failed','detail':output[-6000:] if code else '', 'seconds':round(time.monotonic()-start,3)}]
                # A subprocess crash after emitting some passing cases must remain visible.
                if code and not any(c['status']=='failed' for c in cases):
                    cases.append({'id':ident+'.process','name':'测试进程未正常完成','status':'failed','detail':output[-6000:]})
                failed=code!=0 or any(c['status']=='failed' for c in cases)
                check.update(cases=cases,status='failed' if failed else 'passed',passed=not failed,exit_code=code,seconds=round(time.monotonic()-start,2))
                save();print(f'{check["status"].upper()} {ident}',flush=True)
                if failed:print(output[-2500:])
        run['passed']=all(c['status'] in ('passed','skipped') for c in run['checks'])
        run['status']='passed' if run['passed'] else 'failed'
    except KeyboardInterrupt:
        run['passed']=False;run['status']='interrupted'
        for check in run['checks']:
            if check['status'] in ('pending','running'):check.update(status='skipped',reason='运行被中断，未完成。')
    except Exception as exc:
        run['passed']=False;run['status']='failed'
        for check in run['checks']:
            if check['status']=='running':
                check.update(status='failed',reason='Runner error: '+str(exc),cases=[{'id':check['id']+'.runner','name':'测试调度异常','status':'failed','detail':str(exc)}])
            elif check['status']=='pending':check.update(status='skipped',reason='调度异常后未执行。')
        print('Runner failed:',exc,file=sys.stderr)
    finally:save()
    print(f'Report: {report/"index.html"}')
    return 0 if run['passed'] else 1

if __name__=='__main__':sys.exit(main())
