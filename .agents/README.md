# .agents

Shared instructions and job procedures for agents. Repository rules live in [AGENTS.md](../AGENTS.md).

## Community skills

Source: [leogallego/ai-skills-ansible](https://github.com/leogallego/ai-skills-ansible), pinned commit `91b05d8e1c2a1750dda2422ba65aaf44e9a92fb4`, GPL-3.0-or-later. The upstream skill text is preserved; plugin-level reference files and the license are bundled with each installed skill so manual discovery works without a plugin loader.

| Skill | Purpose |
| --- | --- |
| [ansible-good-practices](skills/ansible-good-practices/SKILL.md) | Review Ansible changes against Red Hat CoP guidance |
| [ansible-new-role](skills/ansible-new-role/SKILL.md) | Scaffold roles |
| [ansible-new-collection](skills/ansible-new-collection/SKILL.md) | Scaffold collections |
| [ansible-new-ee](skills/ansible-new-ee/SKILL.md) | Scaffold execution environments |
| [ansible-new-molecule](skills/ansible-new-molecule/SKILL.md) | Scaffold Molecule tests |
| [ansible-docs](skills/ansible-docs/SKILL.md) | Consult official documentation through ansible-know |
| [ansible-zen](skills/ansible-zen/SKILL.md) | Review simplicity and readability |
| [ansible-pytest-migrate](skills/ansible-pytest-migrate/SKILL.md) | Audit or migrate pytest-ansible use |

Mistral Vibe CLI and Codex discover `.agents/skills/`. Claude Code uses [.claude/skills](../.claude/skills), a symlink to the same directory. Skills are available on the next turn; reload the client session if its discovery cache persists.

`ansible-docs` requires ansible-know. [.mcp.json](../.mcp.json) and [.codex/config.toml](../.codex/config.toml) launch `ansible-know-mcp==0.11.0` through `pipx run`. Project-level MCP configuration is loaded by trusted clients; reload the MCP connection after changing configuration. The Python dev-container feature provides pipx. Optional scaffolding tools such as ansible-creator and Molecule are installed only when needed; the skills document their fallbacks.

Repository instructions override generic recommendations, including Japanese documentation, the flat role naming scheme, explicit Vault loading, the read-only status of `legacy/`, and the prohibition on running infrastructure mutations without an explicit request. A skill's general offer to fix findings does not require a new approval when the owner already requested implementation and self-review.

## Delegated jobs

The main agent uses Mistral Vibe CLI for implementation, research, exploration, drafting, second opinions and independent review. The main agent's product and model are not prescribed. Job models follow the CLI's configured default; no project-level model pin or main-agent profile is required. See the [design](../docs/design/agents.md).

Prerequisite: `vibe` is installed and authenticated by the user. Check `vibe --version` and `vibe --help` before using version-specific options. Do not copy credentials into the repository or job briefs.

1. The main agent prepares a bounded brief: purpose, the owner's decisions with sources, allowed paths, acceptance criteria, and prohibitions on delegation, secrets, validators and infrastructure access.
2. For implementation, prepare a disposable working copy outside the repository containing the current work, including relevant uncommitted changes. Exclude `vault/`, ignored files, credentials and client-local settings. Do not copy `.git` metadata that points back to the original worktree. Parallel jobs use separate copies and briefs. Record the initial snapshot outside the repository so each job's diff excludes pre-existing work.
3. Launch a separate CLI session per job. Restrict tools to those below, without `--auto-approve`, `--yolo` or shell/process tools. The CLI is not an OS sandbox; do not give jobs access to production credentials. Stop if the installed CLI cannot enforce the required tool restrictions.

   ```sh
   # Implementation in a disposable copy; all paths are absolute.
   timeout 1800 vibe --workdir /absolute/job-copy --trust \
     --enabled-tools read_file --enabled-tools edit --enabled-tools write_file \
     --prompt-file /absolute/worker-brief.txt --output text > /absolute/worker-result.txt

   # Independent review in a fresh session, with the completed review brief.
   timeout 1800 vibe --workdir /absolute/review-copy \
     --enabled-tools read_file \
     --prompt-file /absolute/review-brief.txt --output text > /absolute/review-result.txt
   ```

   Research and review jobs use only `read_file`. Prepare the review copy from the candidate files, excluding the same sensitive paths as the implementation copy, and include a plain-text diff for the reviewer. Supply the diff path and relevant file paths in the brief. Tool discovery, shell execution, connectors and further agents are not needed and must not be enabled. Use the main agent's background-process facility for parallel jobs, keeping process IDs and reading final output and exit status. A timeout, non-zero exit or incomplete response is not a successful job.
4. Read the result and every diff against the job's initial snapshot before applying changes. Reject unrelated changes. The main agent alone integrates and runs the validation suite in [AGENTS.md](../AGENTS.md).
5. Non-trivial changes receive an independent read-only review in another CLI session using [review-brief.md](review-brief.md). Read the findings, resolve them, then validate the final changes. Do not leave job copies, logs or briefs in the repository.

The Claude Code production guard in [.claude/hooks/infra-guard.py](../.claude/hooks/infra-guard.py) remains specific to that client. Its presence does not protect Vibe CLI jobs or authorize infrastructure operations.
