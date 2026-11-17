"""Regression infrastructure must not turn failed or missing checks into passes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from testing.report import render
from verify_site import execute,tap_cases
from watch_tests import snapshot

class ReportingTests(unittest.TestCase):
    def test_case_runner_records_failure_skip_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'test_sample.py';out=root/'cases.json'
            source.write_text('import unittest\nclass Demo(unittest.TestCase):\n def test_pass(self): pass\n def test_fail(self): self.assertEqual(1,2)\n @unittest.skip("not configured")\n def test_skip(self): pass\n')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/testing/case_runner.py'),'--file',str(source),'--output',str(out)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            cases=json.loads(out.read_text())
            self.assertEqual(sorted(c['status'] for c in cases),['failed','passed','skipped'])
            self.assertIn('1 != 2',next(c['detail'] for c in cases if c['status']=='failed'))

    def test_dashboard_keeps_history_and_escapes_injected_test_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for ident in ('run-a','run-b'):
                (root/'runs'/ident).mkdir(parents=True)
                render(root,{'id':ident,'status':'failed','checks':[{'id':'case','name':'</script><script>alert(1)</script>','exit_code':1,'cases':[]}]})
            html=(root/'index.html').read_text()
            self.assertNotIn('</script><script>alert(1)',html)
            self.assertIn('run-a',html);self.assertIn('run-b',html)
            self.assertEqual(json.loads((root/'summary.json').read_text())['id'],'run-b')
            self.assertTrue((root/'runs/run-a/summary.json').exists())

    def test_timeout_and_missing_command_fail(self):
        import os
        code,output=execute([sys.executable,'-c','import time;time.sleep(2)'],os.environ.copy(),0.03)
        self.assertEqual(code,124);self.assertIn('Timed out',output)
        code,_=execute(['/no/such/formrefine-test-executable'],os.environ.copy(),1)
        self.assertEqual(code,127)

    def test_node_tap_reports_failures_and_skips(self):
        cases=tap_cases('ok 1 - upload\n  duration_ms: 100\nnot ok 2 - login\nok 3 - optional # SKIP\n')
        self.assertEqual([c['status'] for c in cases],['passed','failed','skipped'])
        self.assertEqual(cases[0]['seconds'],0.1)

    def test_watcher_ignores_report_writes_but_detects_source_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'app').mkdir();(root/'artifacts').mkdir()
            source=root/'app/main.py';source.write_text('before')
            before=snapshot(root)
            (root/'artifacts/report.html').write_text('generated')
            self.assertEqual(before,snapshot(root))
            source.write_text('after modification')
            self.assertNotEqual(before,snapshot(root))
