"""Build portable offline reports. All test data is rendered as text, never HTML."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write_json(path,data):
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)

def render(report_root,run):
    folder=report_root/'runs'/run['id']
    write_json(folder/'summary.json',run)
    write_json(report_root/'summary.json',run)
    runs=[]
    for path in sorted((report_root/'runs').glob('*/summary.json'),reverse=True)[:40]:
        item=json.loads(path.read_text())
        for check in item['checks']:
            check['log_url']=f"runs/{item['id']}/{check['id']}.log" if check.get('exit_code') is not None else None
        runs.append(item)
    payload=json.dumps(runs,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(ROOT/'scripts/testing/dashboard.html').read_text()
    html=template.replace('__REPORT_DATA__',payload)
    target=report_root/'index.html'
    tmp=report_root/'index.tmp'
    tmp.write_text(html,encoding='utf-8');tmp.replace(target)
    # Per-run HTML remains useful when copied with its entire report root.
