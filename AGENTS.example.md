## Bounded Qwen coding jobs

When the user asks to delegate coding to Qwen, give each job one clear objective and observable acceptance criteria. Use `agentctl.py` for one job, or `batchctl.py` for exactly two independent jobs with disjoint file scopes. Start with 10 minutes and 25 tool calls per job. Review only the compact result manifest, changed files, diff, and relevant tests. If a job reaches its cap without a useful change, narrow the task before trying again. Keep production credentials, deployment, and release approval outside Qwen's coding jobs.
