"""Run the real analysis pipeline on local reference videos and export reviewable results.

PYTHONPATH=. python scripts/regress_model_videos.py
No uploads, account writes, or existing analysis results are changed.
"""
import argparse
import html
import json
from pathlib import Path

from app.config import settings
from app.services.analysis_service import AnalysisService, AnalysisConfig

LABELS = dict(sync_frame_1='沉球点', sync_frame_2='手上升后',
              knee_min_frame='最低蹲点', elbow_min_frame='最紧折叠点',
              max_hold_frame='最高持球估计点', release_frame='出手估计点',
              wrist_peak_frame='手腕最高点', follow_through_frame='跟随定型点')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=Path('modelVideo'))
    parser.add_argument('--output', type=Path, default=Path('artifacts/model-video-regression'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    settings.results_dir = args.output.resolve() / 'results'
    report = []
    for index, path in enumerate(sorted(args.input.iterdir())):
        if path.suffix.lower() not in {'.mov', '.mp4', '.avi', '.webm'}:
            continue
        print(f'RUN {path.name}', flush=True)
        row = {'video': path.name}
        try:
            with AnalysisService(AnalysisConfig()) as service:
                result = service.analyze_video(path, task_id=f'video-{index}')
                row.update(result.to_dict())
                row['pose_frames'] = len(service.phase_detector.frame_history)
                row['source_frames'] = result.video_info.total_frames
                row['sample_interval'] = max(1, int(result.video_info.fps / settings.target_fps))
                row['sampled_frames'] = len(range(0, result.video_info.total_frames, row['sample_interval']))
                raw = [dict(frame_number=f.frame_number, timestamp=f.timestamp,
                            wrist_y=f.raw_wrist_y, confidence=f.confidence,
                            angles=f.raw_angles.to_dict() if f.raw_angles else None)
                       for f in service.phase_detector.frame_history]
                (settings.results_dir / result.task_id / 'raw_pose.json').write_text(json.dumps(raw, indent=2))
            keys = {f['phase']: f for f in row['key_frames']}
            checks = []
            for before, after in [('sync_frame_1', 'sync_frame_2'),
                                  ('sync_frame_1', 'release_frame'),
                                  ('max_hold_frame', 'release_frame'),
                                  ('wrist_peak_frame', 'follow_through_frame')]:
                if before in keys and after in keys and keys[before]['timestamp'] > keys[after]['timestamp']:
                    checks.append(f'{before} occurs after {after}')
            for f in row['key_frames']:
                if not (0 <= f['frame_number'] < row['source_frames']):
                    checks.append('Frame outside source video')
                if not (args.output / f['image_url'].lstrip('/')).is_file():
                    checks.append('Missing image: ' + f['image_url'])
            if 'sync_frame_1' not in keys and any(not i['skipped'] for i in row['coordination_issues']):
                checks.append('Incomplete preparation incorrectly evaluated')
            row['checks_failed'] = checks
            row['missing'] = [k for k in LABELS if k not in keys]
            print(f'RESULT {path.name}: {len(keys)}/8 keyframes; '
                  f'pose={row["pose_frames"]}/{row["sampled_frames"]}; errors={checks}', flush=True)
        except Exception as exc:
            row['error'] = repr(exc)
            print(f'ERROR {path.name}: {exc}', flush=True)
        report.append(row)
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))

    page = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全量视频回归</title>',
            '<style>body{font:16px system-ui;background:#141b22;color:#edf3f9;margin:28px}p,small{color:#b4c5d5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:12px}figure{margin:0;background:#24313c;padding:10px;border-radius:10px}img{width:100%;height:300px;object-fit:contain}figcaption{padding:10px 0}section{margin:40px 0}a{color:#91d7ff}</style>',
            '<h1>modelVideo 全量回归</h1><p>全新运行姿态检测、关键帧选取、协调性评价及标注图生成。默认右手；卡片按时间排序。结构检查通过不等于选帧准确，需人工核对。</p>']
    for r in report:
        page.append(f'<section><h2>{html.escape(r["video"])}</h2>')
        if 'error' in r:
            page.append('<p>' + html.escape(r['error']) + '</p></section>')
            continue
        page.append(f'<p>姿态返回 {r["pose_frames"]}/{r["sampled_frames"]} 帧 · 关键帧 {len(r["key_frames"])}/8 · 结构检查：{html.escape(str(r["checks_failed"]) if r["checks_failed"] else "通过")}</p>')
        if r['missing']:
            page.append('<p>未识别：' + '、'.join(LABELS[k] for k in r['missing']) + '</p>')
        for issue in r['coordination_issues']:
            page.append('<p>' + html.escape(issue['description']) + '</p>')
        page.append('<div class="grid">')
        for f in sorted(r['key_frames'], key=lambda f: f['timestamp']):
            src = html.escape(f['image_url'].lstrip('/'), quote=True)
            page.append(f'<figure><a href="{src}"><img src="{src}"></a><figcaption>{LABELS.get(f["phase"],f["phase"])}<br><small>{f["timestamp"]:.2f}s · 帧号 {f["frame_number"]}</small></figcaption></figure>')
        page.append('</div></section>')
    page.append('</html>')
    (args.output / 'index.html').write_text('\n'.join(page))
    if any('error' in r or r.get('checks_failed') for r in report):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
