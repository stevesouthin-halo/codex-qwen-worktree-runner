## Bounded Qwen coding jobs

Before copying this into another repository's `AGENTS.md`, replace `<runner-dir>` with the absolute path where you cloned this runner. Run `python3 <runner-dir>/agentctl.py` and `python3 <runner-dir>/batchctl.py` from any directory.

When the user asks to delegate coding to Qwen, give each job one clear objective and observable acceptance criteria. Use `agentctl.py` for one job, or `batchctl.py` for exactly two independent jobs with disjoint file scopes. Start with 10 minutes and 25 tool calls per job. Review only the compact result manifest, changed files, diff, and relevant tests. If a job reaches its cap without a useful change, narrow the task before trying again. Keep production credentials, deployment, and release approval outside Qwen's coding jobs.

After a Qwen job or batch, run `python3 <runner-dir>/agentctl.py report --since-hours 1`, make one integration decision, and give the user a compact checkpoint. Stop there unless a specific failed check requires another bounded job. Do not continuously poll a completed run or start a broad retry. If the host exposes Codex credit balance, compare its observed spend rate with the user's time budget; the runner's Qwen token report does not measure Codex credits.
