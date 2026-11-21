#!/usr/bin/env python3
"""Run exactly two independent Qwen coding jobs in separate worktrees."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from agentctl import JOBS, ROOT, git, read_task, repo_path, write_json


def overlaps(left, right):
    if left == right:
        return True
    return (left.endswith('/') and right.startswith(left)) or (right.endswith('/') and left.startswith(right))


def run(args):
    if not 1 <= args.minutes <= 120 or not 1 <= args.tool_calls <= 300:
        raise ValueError('limits must be 1–120 minutes and 1–300 tool calls')
    repo = repo_path(args.repo)
    if git('status', '--porcelain', cwd=repo):
        raise ValueError('source worktree is dirty; commit or choose a clean checkout first')
    paths = [Path(x).expanduser().resolve() for x in args.task]
    tasks = [read_task(x) for x in paths]
    if not all(t.get('paths') for t in tasks):
        raise ValueError('both task JSON files need owned paths for parallel work')
    if any(overlaps(a, b) for a in tasks[0]['paths'] for b in tasks[1]['paths']):
        raise ValueError('task path scopes overlap; use sequential jobs instead')

    JOBS.mkdir(exist_ok=True)
    batch_id = 'batch-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    batch_dir = JOBS / batch_id
    batch_dir.mkdir()
    started = time.time()
    workers = []
    for task_path in paths:
        cmd = [sys.executable, str(ROOT / 'agentctl.py'), 'run', '--repo', str(repo),
               '--task', str(task_path), '--minutes', str(args.minutes), '--tool-calls', str(args.tool_calls)]
        if args.qwen:
            cmd += ['--qwen', str(Path(args.qwen).expanduser().resolve())]
        workers.append(subprocess.Popen(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE))

    results = []
    for index, proc in enumerate(workers):
        try:
            stdout, stderr = proc.communicate(timeout=args.minutes * 60 + 45)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            rc = 124
            stderr += '\nBatch worker timeout reached.\n'
        job_file = Path(stdout.strip().splitlines()[-1]) if stdout.strip() else None
        job = json.loads(job_file.read_text()) if job_file and job_file.is_file() else None
        results.append({'task': str(paths[index]), 'title': tasks[index]['title'],
                        'workerExitCode': rc, 'jobResult': str(job_file) if job else None,
                        'state': job.get('state') if job else 'needs_attention',
                        'changedPaths': job.get('changedPaths', []) if job else [],
                        'error': stderr[-500:].strip() if stderr else None})

    actual_overlap = sorted(set(results[0]['changedPaths']) & set(results[1]['changedPaths']))
    manifest = {'id': batch_id, 'repo': str(repo), 'state': 'finished' if all(
                x['state'] == 'finished' for x in results) and not actual_overlap else 'needs_attention',
                'elapsedSeconds': round(time.time() - started, 1), 'limitsPerJob':
                {'minutes': args.minutes, 'toolCalls': args.tool_calls},
                'actualPathOverlap': actual_overlap, 'jobs': results}
    result_file = batch_dir / 'batch.json'
    write_json(result_file, manifest)
    print(result_file)
    return 0 if manifest['state'] == 'finished' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--task', required=True, action='append', help='exactly two JSON task files with disjoint paths')
    parser.add_argument('--minutes', type=int, default=10)
    parser.add_argument('--tool-calls', type=int, default=25)
    parser.add_argument('--qwen', help='alternate executable for local testing')
    args = parser.parse_args()
    if len(args.task) != 2:
        parser.error('pass --task exactly twice')
    try:
        return run(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'batchctl: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
