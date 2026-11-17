"""Stage a reviewed local clip, then optionally publish into the local template library.

Usage: venv/bin/python scripts/import_reference_template.py manifest.json [--publish]
The manifest records source, exact cut, viewpoint and playback limitations.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.analysis_service import AnalysisService, AnalysisConfig
from app.models.template import TemplateManager, TemplateKeyFrame
from app.services.comparison_service import compare_curves


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    template_id = manifest['id']
    if not template_id.startswith('template_') or not all(c.isalnum() or c == '_' for c in template_id):
        raise ValueError('Unsafe template id')
    stage_root = ROOT / 'artifacts' / 'template-sources' / 'staged'
    stage = stage_root / template_id
    clip = ROOT / manifest['clip']
    if not args.publish:
        result = AnalysisService(AnalysisConfig(
            shooting_hand=manifest.get('shooting_hand', 'right'),
            generate_evaluation=False, generate_annotated_video=False,
            output_dir=stage_root,
        )).analyze_video(clip, task_id=template_id)
        (stage / 'result.json').write_text(json.dumps(result.to_dict(), indent=2))
        frames = [dict(phase=k.phase.value, frame_number=k.frame_number,
                       timestamp=k.timestamp, image_path=Path(k.image_path).name,
                       angles=k.angles.to_dict() if k.angles else None) for k in result.key_frames]
        (stage / 'frames.json').write_text(json.dumps(frames, indent=2))
    frames = json.loads((stage / 'frames.json').read_text())
    data = json.loads((stage / 'frame_data.json').read_text())
    assert len(data) >= 15, 'Not enough detected frames'
    assert {'release_frame', 'knee_min_frame'}.issubset({k['phase'] for k in frames}), 'Missing core keyframes'
    for k in frames:
        assert (stage / k['image_path']).is_file(), 'Missing keyframe image'
    phases = {}
    for row in data:
        phase = row.get('phase')
        if not phase or phase == 'unknown': continue
        phases.setdefault(phase, dict(start_frame=row['frame_number'], start_time=row['timestamp']))
        phases[phase].update(end_frame=row['frame_number'], end_time=row['timestamp'])
    curves = {'angles': data, 'phases': phases}
    comparison = compare_curves(data, curves)
    assert comparison and comparison.get('joints'), 'Curve comparison failed'
    report = dict(id=template_id, keyframe_count=len(frames), detected_frames=len(data),
                  phases=list(phases), curve_comparison='passed', published=False)
    if args.publish:
        assert manifest.get('visually_reviewed') is True, 'Review clip and detected keyframes before publishing'
        manager = TemplateManager(ROOT / 'templates')
        assert manager.get_template(template_id) is None, 'Template already exists; refusing overwrite'
        dest = manager.get_template_dir(template_id)
        dest.mkdir(parents=True, exist_ok=False)
        stored = []
        for k in frames:
            filename = k['phase'] + '.jpg'
            shutil.copy2(stage / k['image_path'], dest / filename)
            stored.append(TemplateKeyFrame(k['phase'], k['frame_number'], k['timestamp'],
                f'templates/{template_id}/{filename}', k['angles']))
        (dest / 'angles.json').write_text(json.dumps(data))
        (dest / 'phases.json').write_text(json.dumps(phases))
        (dest / 'source.json').write_text(json.dumps(manifest, indent=2))
        manager.create_template(template_id, manifest['name'], stored, manifest['description'],
            video_info={'filename': clip.name, 'shooting_hand': manifest.get('shooting_hand','right'),
                        'source_url':manifest['source_url'], 'view':manifest['view'],
                        'playback':manifest['playback'], 'source_start':manifest['start'],
                        'source_end':manifest['end']}, has_curve_data=True)
        assert manager.get_template_curves(template_id)
        report['published'] = True
    (stage / 'validation.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
