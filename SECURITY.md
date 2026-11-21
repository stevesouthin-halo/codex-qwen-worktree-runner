# Security policy

The latest `main` branch is the supported preview version. No older release line receives security fixes yet.

Please report vulnerabilities privately through the repository's **Security → Advisories → Report a vulnerability** flow. Do not put exploit details, credentials, or private files in a public issue.

## Execution model

This runner starts Qwen Code in headless `yolo` mode inside macOS Seatbelt's `permissive-open` profile. The Git worktree organizes and limits expected project edits, but **it is not a confidentiality boundary**: the process can read other files accessible to the macOS user and can use the network. The prompt's instruction not to push or deploy is not an enforced security control. Run it only in an environment whose accessible files and credentials you are comfortable exposing to the coding agent. A separate macOS user or disposable VM is appropriate for untrusted repositories.

The runner stores prompts, model output, and job manifests in the local ignored `jobs/` directory. Review them before sharing. Qwen authentication is managed by Qwen Code outside this repository.
