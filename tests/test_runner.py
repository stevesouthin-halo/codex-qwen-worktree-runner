import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('agentctl.py', 'batchctl.py'):
            shutil.copy2(SOURCE / name, self.root / name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Test User')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'README.md').write_text('test repo\n')
        self.git('add', 'README.md')
        self.git('commit', '-q', '-m', 'initial')
        self.fake = self.root / 'fake-qwen'
        self.fake.write_text("#!/usr/bin/env python3\n"
                             "import json,re,sys,time\n"
                             "from pathlib import Path\n"
                             "p=re.search(r'^Owned paths: ([^\\n]+)',sys.argv[1],re.M).group(1).split(',')[0].strip()\n"
                             "time.sleep(0.2)\n"
                             "Path(p).write_text('done\\n')\n"
                             "print(json.dumps([{'type':'result','subtype':'success','result':'Done'}]))\n")
        self.fake.chmod(0o755)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              text=True, capture_output=True).stdout.strip()

    def task(self, name):
        path = self.root / (name + '.json')
        path.write_text(json.dumps({'title': 'Write ' + name, 'objective': 'Create ' + name,
                                    'acceptance': name + ' exists', 'paths': [name + '.txt']}))
        return path

    def call(self, script, *args):
        prefix = [sys.executable, str(self.root / script)]
        if script == 'agentctl.py':
            prefix.append('run')
        return subprocess.run(prefix + ['--repo', str(self.repo),
                               *args, '--minutes', '1', '--tool-calls', '5', '--qwen', str(self.fake)],
                              text=True, capture_output=True, timeout=20)

    def test_single_job_isolated_and_scoped(self):
        result = self.call('agentctl.py', '--task', str(self.task('alpha')))
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(result.stdout.strip()).read_text())
        self.assertEqual(manifest['state'], 'finished')
        self.assertEqual(manifest['changedPaths'], ['alpha.txt'])
        self.assertEqual(manifest['scopeViolations'], [])
        self.assertFalse((self.repo / 'alpha.txt').exists())

    def test_two_jobs_run_in_disjoint_worktrees(self):
        result = self.call('batchctl.py', '--task', str(self.task('alpha')),
                           '--task', str(self.task('beta')))
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(Path(result.stdout.strip()).read_text())
        self.assertEqual(manifest['state'], 'finished')
        self.assertEqual(manifest['actualPathOverlap'], [])
        self.assertEqual([x['changedPaths'] for x in manifest['jobs']],
                         [['alpha.txt'], ['beta.txt']])

    def test_overlapping_scopes_are_rejected(self):
        task = self.task('alpha')
        result = self.call('batchctl.py', '--task', str(task), '--task', str(task))
        self.assertEqual(result.returncode, 2)
        self.assertIn('scopes overlap', result.stderr)

    def test_budget_failure_reports_cause_and_retry_guidance(self):
        self.fake.write_text("#!/usr/bin/env python3\n"
                             "import json,sys\n"
                             "print(json.dumps({'error': {'type': 'FatalBudgetExceededError', "
                             "'message': 'tool-call budget exceeded', 'code': 55}}))\n"
                             "sys.exit(55)\n")
        result = self.call('agentctl.py', '--task', str(self.task('alpha')))
        self.assertEqual(result.returncode, 55)
        manifest = json.loads(Path(result.stdout.strip()).read_text())
        self.assertEqual(manifest['failure']['type'], 'FatalBudgetExceededError')
        self.assertEqual(manifest['changedPaths'], [])
        self.assertIn('Narrow the objective', manifest['nextAction'])


if __name__ == '__main__':
    unittest.main()
