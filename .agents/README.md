# .agents

Agent-neutral resources shared by every coding agent used in this repository (Claude Code, Codex, Antigravity, OpenCode). Entry point: [AGENTS.md](../AGENTS.md).

```text
.agents/
└── skills/                  one directory per skill, each with a SKILL.md
    ├── new-host/            add a host to the inventory (VLAN / ID / VMID / IP rules)
    ├── new-role/            scaffold a role that follows the repository conventions
    └── validate/            run the validation suite and report results honestly
```

## .agents/ and .claude/

| Path | Read by | Holds |
| --- | --- | --- |
| `.agents/` | every agent | skills (the source) |
| `.claude/` | Claude Code only | `settings.json` (model, effort, compaction), `agents/` (subagents, Claude frontmatter), `skills` (symlink) |

## Rules

- `.agents/skills/` is the single source. Claude Code reads skills only from `.claude/skills/`, a symlink to `../.agents/skills`; never put real files there.
- Subagents are Claude Code files and live in `.claude/agents/` as real files. Their model and effort are set in each file's frontmatter, per duty; do not repeat them elsewhere.
- Keep skills agent-neutral: plain Markdown, frontmatter limited to `name` and `description`, no agent-specific tool names.
- A skill states a procedure and points to [docs/](../docs/) for rules. It never copies decisions; when a decision changes, only the document under `docs/` changes.
- Skills and subagents are written in English (agent-facing). Files they create for humans (docs, comments, task names) follow the Japanese convention in AGENTS.md.
- Add a skill only for work that recurs. One-off knowledge belongs in AGENTS.md or `docs/design/`.
