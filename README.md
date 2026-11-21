# Codex–Qwen Worktree Runner

A macOS CLI that lets Codex hand a **specific coding task** to Qwen Code, then review the result. Qwen edits an isolated Git worktree under a time and tool-call limit; your original checkout stays untouched. Two independent tasks can run in parallel when their file scopes do not overlap.

Use it when you want Codex to plan, review, and decide what ships while Qwen does the implementation or test-writing work. Qwen runs on its own account or provider allowance. Codex review still uses Codex credits. The runner does not automatically intercept every coding request, merge code, push changes, or deploy. [AGENTS.example.md](AGENTS.example.md) is an optional instruction snippet for a target repository.

## Install on macOS

You need Git, Python 3, npm, and a Qwen Code account or compatible provider. The coding repository must have a clean Git checkout. This repository is private during its trial, so cloning it requires access from its owner.

```sh
git clone https://github.com/stevesouthin-halo/codex-qwen-worktree-runner.git
cd codex-qwen-worktree-runner
./setup.sh --login
```

`setup.sh` checks the local prerequisites, installs the locked Qwen Code dependency, runs the runner tests, and opens the Qwen subscription sign-in. In the interactive CLI, enter `/auth`, choose **Qwen Account with Subscription**, and complete the browser authorization once. After that, jobs reuse Qwen Code's local login. Use `./setup.sh` without `--login` to reinstall dependencies or rerun setup later; use `./login-qwen.sh` only if sign-in expires.

Credentials stay in Qwen Code's home directory and are not stored in this repository. The runner checks only whether its subscription credential file exists.

## Run your first job

Copy `task.example.json` to `task.local.json` in this runner directory and edit its objective, acceptance criteria, and repo-relative `paths`. That local task file is ignored by Git. For example, `paths: ["src/vehicle.py", "tests/test_vehicle.py"]` allows Qwen to edit only those two files.

Run a job against a **different, clean Git repository**:

```sh
python3 agentctl.py run \
  --repo /absolute/path/to/your-project \
  --task "$PWD/task.local.json" \
  --minutes 10 --tool-calls 25
```

The command prints a `jobs/<id>/result.json` path. Open that manifest and review its `worktree`, `changedPaths`, `scopeViolations`, test summary, and diff before copying or merging changes into your project. The runner leaves the Qwen worktree in place for review. `python3 agentctl.py list` and `python3 agentctl.py status JOB_ID` show compact status. A job with no changes or edits outside its declared paths is marked `needs_attention`.

To ask Codex to use this workflow, a prompt can be: “Use the Qwen runner for the implementation. Give it one bounded task with acceptance criteria, then review the diff and tests and stop at a checkpoint.” Copy the relevant instructions from [AGENTS.example.md](AGENTS.example.md) into your target repository's existing `AGENTS.md` if you want the preference to persist there.

## Resource checkpoint

Run `python3 agentctl.py report --since-hours 1` to see completed, failed, and budget-exceeded jobs and the Qwen token totals that the provider returned. Jobs without token usage are counted separately; the report does not estimate their tokens. This is Qwen usage, not ChatGPT/Codex credit usage.

After each job or independent batch, inspect the result and make one integration decision. Stop the Codex review session at that checkpoint unless a specific failing check requires another bounded job. If a job hits its tool-call limit with no changes, narrow its objective and acceptance criteria before retrying. Avoid repeated status polling and broad reruns.

Codex credits are account-wide and this CLI cannot read or cap them. If your Codex host exposes a usage-balance tool, record the balance and time before and after a review window; compare the observed hourly spend with `remaining credits / hours until your target date`. Pause optional Codex work when the observed rate exceeds that budget. A Qwen job can still consume its own subscription allowance.

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
