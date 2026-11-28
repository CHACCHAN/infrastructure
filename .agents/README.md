# .agents

Community skills shared by agents. Repository rules live in [AGENTS.md](../AGENTS.md).

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

Claude Code reads them through [.claude/skills](../.claude/skills), a symlink to this directory. Skills are available on the next turn; reload the client session if its discovery cache persists.

`ansible-docs` requires ansible-know. [.mcp.json](../.mcp.json) launches `ansible-know-mcp==0.11.0` through `pipx run`. Project-level MCP configuration is loaded by trusted clients; reload the MCP connection after changing configuration. The Python dev-container feature provides pipx. Optional scaffolding tools such as ansible-creator and Molecule are installed only when needed; the skills document their fallbacks.

Repository instructions override generic recommendations, including Japanese documentation, the flat role naming scheme, explicit Vault loading, the read-only status of `legacy/`, and the prohibition on running infrastructure mutations without an explicit request. A skill's general offer to fix findings does not require a new approval when the owner already requested implementation and self-review.
