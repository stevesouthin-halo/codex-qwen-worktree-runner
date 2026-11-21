#!/usr/bin/env python3
"""Bounded Qwen coding jobs in isolated Git worktrees."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / 'jobs'
QWEN = ROOT / 'node_modules' / '@qwen-code' / 'qwen-code' / 'cli-entry.js'
NODE = ROOT / 'node_modules' / '.bin' / 'node'


def git(*args, cwd=None):
    return subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def repo_path(value):
    p = Path(value).expanduser().resolve()
    if not (p / '.git').exists() and not git('rev-parse', '--is-inside-work-tree', cwd=p) == 'true':
        raise ValueError('not a Git worktree')
    return p


def read_task(path):
    task = json.loads(Path(path).read_text())
    if not isinstance(task, dict) or not all(isinstance(task.get(k), str) and task[k].strip() for k in ('title', 'objective', 'acceptance')):
        raise ValueError('task JSON requires nonempty title, objective, acceptance strings')
    if 'paths' in task:
        paths = task['paths']
        if not isinstance(paths, list) or not paths or not all(isinstance(x, str) and x and
                not x.startswith('/') and not any(part in ('', '.', '..') for part in x.rstrip('/').split('/')) for x in paths):
            raise ValueError('paths must be nonempty repo-relative file or directory paths')
    return task


def within_scope(path, scopes):
    return any(path.startswith(scope) if scope.endswith('/') else path == scope for scope in scopes)


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2) + '\n')
    temp.replace(path)


def run(args):
    repo = repo_path(args.repo)
    if git('status', '--porcelain', cwd=repo):
        raise ValueError('source worktree is dirty; commit or choose a clean checkout first')
    task = read_task(args.task)
    if args.auth_type == 'qwen-subscription' and not args.qwen:
        qwen_home = Path(os.environ.get('QWEN_HOME') or Path.home() / '.qwen').expanduser()
        if not qwen_home.is_absolute():
            qwen_home = (Path.cwd() / qwen_home).resolve()
        if not (qwen_home / 'subscription_credentials.json').is_file():
            raise ValueError('Qwen subscription is not signed in; run login-qwen.sh once and complete browser authorization')
    exe = Path(args.qwen).expanduser().resolve() if args.qwen else QWEN
    if not exe.exists() or (not args.qwen and not NODE.exists()):
        raise ValueError(f'Qwen CLI or bundled Node missing; run npm install in {ROOT}')
    JOBS.mkdir(exist_ok=True)
    job_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    jobdir = JOBS / job_id
    jobdir.mkdir()
    checkout = jobdir / 'checkout'
    branch = 'qwen/' + job_id.lower()
    try:
        lock_path = JOBS / ('.worktree-' + hashlib.sha256(str(repo).encode()).hexdigest()[:16] + '.lock')
        with lock_path.open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            git('worktree', 'add', '-b', branch, str(checkout), 'HEAD', cwd=repo)
    except Exception:
        jobdir.rmdir()
        raise
    scope_note = ('Owned paths: ' + ', '.join(task['paths']) + '\nEdit only these paths; report if a shared file is needed.\n\n') if task.get('paths') else ''
    prompt = (f"Job: {task['title']}\n\nObjective: {task['objective']}\n\n"
              f"Acceptance: {task['acceptance']}\n\n" + scope_note +
              "Work only in this checkout. Make the smallest coherent change. Run relevant tests. "
              "Do not push, deploy, access production credentials, or start subagents. "
              "Do not keep polling after a result is known. End with changed files, tests, and blockers.\n")
    (jobdir / 'prompt.txt').write_text(prompt)
    start = time.time()
    meta = {'id': job_id, 'title': task['title'], 'repo': str(repo), 'worktree': str(checkout),
            'branch': branch, 'baseCommit': git('rev-parse', 'HEAD', cwd=repo), 'state': 'running',
            'startedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'limits': {'minutes': args.minutes, 'toolCalls': args.tool_calls}}
    write_json(jobdir / 'result.json', meta)
    cmd = ([str(exe)] if args.qwen else [str(NODE), str(exe)]) + [prompt, '--auth-type', args.auth_type,
           '--output-format', 'json', '--approval-mode', 'yolo', '--sandbox=sandbox-exec',
           '--exclude-tools', 'agent', '--max-session-turns', str(args.tool_calls * 2 + 6),
           '--max-wall-time', f'{args.minutes}m', '--max-tool-calls', str(args.tool_calls)]
    qwen_env = os.environ.copy()
    qwen_env['SEATBELT_PROFILE'] = 'permissive-open'
    try:
        proc = subprocess.run(cmd, cwd=checkout, env=qwen_env, text=True, capture_output=True, timeout=args.minutes * 60 + 30)
        rc = proc.returncode
        (jobdir / 'qwen.json').write_text(proc.stdout)
        (jobdir / 'qwen.stderr.log').write_text(proc.stderr)
    except subprocess.TimeoutExpired as exc:
        rc = 124
        (jobdir / 'qwen.json').write_text((exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or ''))
        (jobdir / 'qwen.stderr.log').write_text('Runner timeout reached.\n')
    except Exception as exc:
        rc = 125
        (jobdir / 'qwen.stderr.log').write_text(str(exc) + '\n')
    changed_files = git('status', '--porcelain', cwd=checkout).splitlines()
    commits = git('log', '--oneline', f"{meta['baseCommit']}..HEAD", cwd=checkout).splitlines()
    changed_paths = sorted(set(git('diff', '--name-only', meta['baseCommit'], cwd=checkout).splitlines() +
                               git('ls-files', '--others', '--exclude-standard', cwd=checkout).splitlines()))
    scope_violations = [x for x in changed_paths if not within_scope(x, task['paths'])] if task.get('paths') else []
    meta.update({'state': 'finished' if rc == 0 and (changed_files or commits) and not scope_violations else 'needs_attention', 'exitCode': rc,
                 'finishedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'elapsedSeconds': round(time.time() - start, 1),
                 'headCommit': git('rev-parse', 'HEAD', cwd=checkout),
                 'changedFiles': changed_files,
                 'changedPaths': changed_paths,
                 'scopeViolations': scope_violations,
                 'diffStat': git('diff', '--stat', 'HEAD', cwd=checkout),
                 'commits': commits})
    try:
        output = json.loads((jobdir / 'qwen.json').read_text())
        if isinstance(output, list):
            results = [x for x in output if isinstance(x, dict) and x.get('type') == 'result']
            if results:
                meta['agentResult'] = {k: results[-1].get(k) for k in ('subtype', 'result', 'duration_ms', 'usage') if k in results[-1]}
    except (ValueError, OSError):
        pass
    write_json(jobdir / 'result.json', meta)
    print(jobdir / 'result.json')
    return rc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('run', help='run one bounded Qwen coding job')
    a.add_argument('--repo', required=True)
    a.add_argument('--task', required=True, help='JSON with title, objective, acceptance')
    a.add_argument('--minutes', type=int, default=10)
    a.add_argument('--tool-calls', type=int, default=25)
    a.add_argument('--qwen', help='alternate Qwen executable, useful for testing')
    a.add_argument('--auth-type', default='qwen-subscription',
                   choices=('qwen-subscription', 'qwen-oauth', 'openai', 'openai-responses', 'anthropic', 'gemini', 'vertex-ai'),
                   help='Qwen provider; defaults to the Plus/Pro account subscription')
    s = sub.add_parser('status', help='print a job result')
    s.add_argument('job_id')
    sub.add_parser('list', help='list job IDs and states')
    a = p.parse_args()
    try:
        if a.command == 'run':
            if not 1 <= a.minutes <= 120 or not 1 <= a.tool_calls <= 300:
                raise ValueError('limits must be 1–120 minutes and 1–300 tool calls')
            return run(a)
        if a.command == 'status':
            print((JOBS / a.job_id / 'result.json').read_text())
        else:
            for x in sorted(JOBS.glob('*/result.json'), reverse=True):
                data = json.loads(x.read_text())
                print(data['id'], data['state'], data['title'])
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'agentctl: {exc}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
