"""Read-only checks for every installed reference; failures must fail CI."""
import json
import unittest
from app.config import settings
from app.models.template import TemplateManager
from app.services.comparison_service import compare_curves

class ReferenceTests(unittest.TestCase):
    def test_all_installed_references_have_images_angles_and_matching_curves(self):
        manager = TemplateManager(settings.templates_dir)
        refs = manager.list_templates()
        self.assertTrue(refs, 'No reference templates installed')
        for ref in refs:
            with self.subTest(template=ref['id']):
                template = manager.get_template(ref['id'])
                self.assertIsNotNone(template)
                self.assertGreaterEqual(len(template.key_frames),4)
                root = settings.templates_dir/ref['id']
                for frame in template.key_frames:
                    self.assertTrue((settings.base_dir/frame.image_path).is_file(),frame.image_path)
                    self.assertTrue(frame.angles)
                curves = manager.get_template_curves(ref['id'])
                if template.has_curve_data:
                    self.assertIsNotNone(curves)
                    self.assertTrue(curves['angles'])
                    result=compare_curves(curves['angles'],curves)
                    self.assertTrue(result.get('joints'),result)
