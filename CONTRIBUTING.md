# Contributing

Issues and pull requests are welcome. This project is a macOS CLI for bounded Qwen Code jobs; it does not integrate with every Codex request automatically.

## Before opening a pull request

1. Describe the behavior you want to change in an issue for larger features or changes to the sandbox and approval model.
2. Keep the change focused. Include a test for behavior that could otherwise regress.
3. Run `python3 -m unittest discover -s tests -v` and `sh -n setup.sh login-qwen.sh`.
4. On macOS, run `./setup.sh` to verify a clean dependency install. This uses no Qwen credentials or model calls.
5. Explain what changed, which checks passed, and any remaining limitations in the pull request.

Do not commit credentials, private repositories, job logs, generated worktrees, or proprietary code. The `jobs/` and `node_modules/` directories are ignored by Git. Use fake executables and disposable repositories in automated tests so contributors do not need a paid Qwen account.

The maintainer reviews and merges pull requests. Contributors do not need direct write access. Contributions are provided under the repository's MIT license.
