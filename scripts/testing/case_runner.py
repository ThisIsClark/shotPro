"""Run unittest cases or legacy test functions and emit machine-readable case results."""
import argparse
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import time
import unittest

class Results(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
        self.started = {}
    def startTest(self, test):
        self.started[id(test)] = time.monotonic()
        super().startTest(test)
    def record(self, test, status, detail=''):
        self.cases.append({'id': test.id(), 'name': test.shortDescription() or test.id().split('.')[-1],
                           'status': status, 'seconds': round(time.monotonic()-self.started.get(id(test),time.monotonic()),3),
                           'detail':detail})
    def addSuccess(self,test):
        self.record(test,'passed'); super().addSuccess(test)
    def addFailure(self,test,err):
        self.record(test,'failed',self._exc_info_to_string(err,test)); super().addFailure(test,err)
    def addError(self,test,err):
        self.record(test,'failed',self._exc_info_to_string(err,test)); super().addError(test,err)
    def addSkip(self,test,reason):
        self.record(test,'skipped',reason); super().addSkip(test,reason)
    def addExpectedFailure(self,test,err):
        self.record(test,'skipped','Expected failure: '+self._exc_info_to_string(err,test)); super().addExpectedFailure(test,err)
    def addUnexpectedSuccess(self,test):
        self.record(test,'failed','Unexpected success; update the expected-failure marker.'); super().addUnexpectedSuccess(test)
    def addSubTest(self,test,subtest,err):
        if err: self.record(subtest,'failed',self._exc_info_to_string(err,test))
        super().addSubTest(test,subtest,err)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--discover')
    parser.add_argument('--file')
    args=parser.parse_args()
    if args.discover:
        suite=unittest.defaultTestLoader.discover(args.discover)
    else:
        path=Path(args.file)
        spec=importlib.util.spec_from_file_location(path.stem,path)
        module=importlib.util.module_from_spec(spec)
        sys.modules[path.stem]=module
        spec.loader.exec_module(module)
        suite=unittest.defaultTestLoader.loadTestsFromModule(module)
        if not suite.countTestCases():
            suite=unittest.TestSuite(unittest.FunctionTestCase(fn,description=fn.__doc__ or name)
                                     for name,fn in inspect.getmembers(module,inspect.isfunction) if name.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(suite)
    Path(args.output).write_text(json.dumps(result.cases,ensure_ascii=False,indent=2))
    sys.exit(0 if result.wasSuccessful() and result.testsRun else 1)
