from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import cv2
from PIL import ImageDraw
from app.services.rhythm_poster import rhythm_poster

from app.services.analysis_service import AnalysisConfig, AnalysisService


class PlayerClips(unittest.TestCase):
    def check_clip(self, player, expected):
        path = Path('modelVideo') / f'{player}-model.mp4'
        if not path.exists():
            self.skipTest(f'Local video fixture unavailable: {path}')
        with TemporaryDirectory() as folder, AnalysisService(AnalysisConfig(output_dir=Path(folder))) as service:
            result = service.analyze_video(path, 'sample').to_dict()
            rhythm = result['shot_rhythm']
            self.assertEqual(rhythm['style'], expected, rhythm)
            release = next(f['timestamp'] for f in result['key_frames'] if f['phase']=='release_frame')
            self.assertLessEqual(rhythm['evidence_end'], release + .001)
            self.assertLess(rhythm['evidence_start'], rhythm['evidence_end'])
            self.assertEqual(rhythm['replay_url'], '/results/sample/rhythm.mp4')
            text_bounds = {}
            typography = {}
            draw_text = ImageDraw.ImageDraw.text
            def record_domain(draw, xy, text, *args, **kwargs):
                bounds = draw.textbbox(xy, text, font=kwargs['font'], anchor=kwargs['anchor'])
                text_bounds[text] = bounds
                typography[text] = (kwargs["font"], kwargs["fill"], xy[1])
                return draw_text(draw, xy, text, *args, **kwargs)

            with patch.object(ImageDraw.ImageDraw, 'text', record_domain):
                rhythm_poster(Path(folder) / 'sample', result)
            title = 'One motion.' if expected == 'one_motion' else 'Two motion.'
            self.assertLess(text_bounds[title][3], text_bounds['Rhythm frame'][1])
            for label, (left, top, right, bottom) in text_bounds.items():
                self.assertTrue(0 <= left < right <= 1080 and 0 <= top < bottom <= 1350, label)
            prefix_font, prefix_color, prefix_baseline = typography["Check your shot at "]
            domain_font, domain_color, domain_baseline = typography["formrefine.ai"]
            self.assertEqual((domain_font.size, domain_baseline), (prefix_font.size, prefix_baseline))
            self.assertIn("Bold", domain_font.getname()[1])
            self.assertEqual(domain_color, typography[title][1])
            self.assertNotEqual(domain_color, prefix_color)
            signatures = [box for label, box in text_bounds.items() if 'formrefine.ai' in label]
            self.assertEqual(len(signatures), 1, 'Use a single domain signature')
            left, top, right, bottom = signatures[0]
            self.assertTrue(0 <= left < right <= 1080 and 135 <= top < bottom <= 1215)
            self.assertTrue(24 <= bottom - top <= 36, 'Keep the signature readable and secondary')
            clip = cv2.VideoCapture(str(Path(folder) / 'sample/rhythm.mp4'))
            try:
                readable, _ = clip.read()
                self.assertTrue(readable)
            finally:
                clip.release()

    def test_curry_sample(self):
        self.check_clip('Curry', 'one_motion')

    def test_booker_sample(self):
        self.check_clip('Booker', 'two_motion')
