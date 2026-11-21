# Codex–Qwen Worktree Runner

A small macOS CLI for handing bounded coding jobs to Qwen Code while a human or another agent scopes and reviews the work. Each job gets an isolated Git worktree, a wall-clock limit, a tool-call limit, and a compact result manifest. Two independent jobs can run concurrently in separate worktrees.

This is a local command-line workflow, not an account-wide ChatGPT integration. The example `AGENTS.example.md` shows how to ask Codex to use it for coding tasks.

## Requirements

- macOS with `sandbox-exec`, Git, Python 3, and npm
- A clean Git checkout for the repository to work on
- Qwen Code access through a Qwen Plus/Pro account or a separately configured API-key provider

Install the pinned Qwen Code CLI and Node runtime:

```sh
npm ci --no-audit --no-fund
./login-qwen.sh
```

For a Qwen account subscription, enter `/auth` in the interactive CLI, choose **Qwen Account with Subscription**, and complete the browser authorization once. Subsequent jobs reuse Qwen Code's local subscription login. Credentials stay in Qwen Code's home directory; this runner checks only whether the subscription credential file exists.

## One job

Copy `task.example.json` and replace its objective, acceptance criteria, and optional `paths` scope. Then run:

```sh
python3 agentctl.py run \
  --repo /absolute/path/to/clean/repo \
  --task /absolute/path/to/task.json \
  --minutes 10 --tool-calls 25
```

The command prints a `jobs/<id>/result.json` path. Read that manifest, the changed files, the Git diff, and relevant test output before integrating. `python3 agentctl.py list` and `python3 agentctl.py status JOB_ID` provide compact status views. A job with no changes or edits outside its declared `paths` is marked `needs_attention` even if Qwen exits successfully.

## Two independent jobs

Give each task JSON a disjoint `paths` array. End a directory scope with `/`, such as `src/capture/`. Then run:

```sh
python3 batchctl.py \
  --repo /absolute/path/to/clean/repo \
  --task /absolute/path/to/capture-task.json \
  --task /absolute/path/to/presentation-task.json \
  --minutes 10 --tool-calls 25
```

The batch runner starts exactly two Qwen processes and writes `jobs/batch-*/batch.json`. It rejects overlapping declared scopes and flags overlapping actual edits. Integrate the results sequentially after review. Dependent tasks should run sequentially. Concurrent jobs share the same Qwen account allowance, so they may reach a provider limit sooner.

## Safety and limits

Qwen's headless mode runs with `yolo` approval inside macOS Seatbelt's `permissive-open` profile. Main project writes are restricted to each worktree; Qwen's own state and normal temporary/cache directories remain writable. The process can read other local files and access the network. Do not run it with production secrets in the checkout or environment. The runner itself does not push, merge, or deploy, but its prompt is not a hard network or Git-push barrier. Review every diff before integration.

Each process has finite wall-clock, turn, and tool-call limits; the Qwen subagent tool is excluded so inner agents cannot evade the tool-call cap. The default is 10 minutes and 25 tool calls per job. Increase limits only for a concrete task. A budget-exceeded run is marked `needs_attention`; inspect the worktree before deciding on a narrower follow-up.

Qwen Code supports [headless use](https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/) and [subscription sign-in](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/). Provider terms differ. In particular, [QwenCloud Token Plan](https://docs.qwencloud.com/token-plan/token-plan-permissions-and-usage) prohibits non-interactive batch scripts; do not use its API key with this runner.

## Local tests

The tests use a fake Qwen executable and disposable Git repositories; they do not call a model:

```sh
python3 -m unittest discover -s tests -v
```
