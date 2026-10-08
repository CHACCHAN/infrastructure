Operating guide for AI agents (Claude Code, Codex, Antigravity, OpenCode) working in this repository. Human-facing overview: [README.md](README.md). Reusable procedures live in [.agents/skills/](.agents/skills/).

The rules and design decisions are written in Japanese under `docs/`, for humans and agents alike. This file holds only what is specific to agents, and imports the documents below.

## Required reading

@docs/conventions.md
@docs/design/network.md
@docs/design/k3s.md

Claude Code expands the `@path` lines above. If your agent does not expand them, open those files before starting work. Read [docs/design/hardware.md](docs/design/hardware.md) when a task depends on node capacity or placement, and [docs/design/pve.md](docs/design/pve.md) when working on the `pve*` roles, and [docs/design/k8s.md](docs/design/k8s.md) when working on the `k8s*` roles.

## What this repository is

Home-lab infrastructure managed declaratively with Ansible. The repository root is the Ansible project root (`ansible.cfg`).

The environment is being redesigned for new hardware. **The tree is currently a skeleton**: inventory groups are empty, roles and playbooks are placeholders. Never assume a role, playbook or variable exists; check first.

| Domain | Roles | Playbooks | Talks to |
| --- | --- | --- | --- |
| pve | `pve` `pve_vm` `pve_template` | `playbooks/pve/` | Proxmox VE (API and hosts) |
| vm | `vm` `vm_k3s` `vm_<service>` | `playbooks/vm/` | Debian 13 VMs over SSH |
| k8s | `k8s` `k8s_<app>` | `playbooks/k8s/` | k3s cluster via API token from vault (no kubeconfig) |
| utils | none | `playbooks/utils/` | One-shot tools calling REST APIs |

- `inventory/hosts/` has one file per VLAN; `inventory/group_vars/all/` holds values shared by every host. `vault/` holds encrypted secrets.
- `legacy/` is the previous configuration, kept as **read-only reference**: never edit it, never lint it, never run its playbooks. Port ideas, not values: its `172.16.x` addresses, node-encoded VMIDs, AWX/EE, Rancher, WG-Easy and Nextcloud are obsolete.
- Language: documentation, comments, task names and commit messages are Japanese. Only this file, `.agents/` and `.claude/agents/` are English.

## Working agreements

- **Think, then propose.** The owner explicitly wants analysis, opinions and proposals, not just execution, and says they are often wrong. When a request or a plan looks mistaken, risky or over-engineered, say so first, explain why, and offer a better option with its trade-offs. Raise problems nobody asked about when they affect the design. Decisions remain the owner's: after giving your opinion, follow their call.
- **Do not invent design.** Anything marked undecided in `docs/design/` must be asked about, not decided. If a task needs a decision that is not written down, ask. Quote where a decision comes from.
- Before working in a directory, read its `README.md` if it has one (usage, prerequisites, run order). READMEs describe usage only; design and undecided items live in `docs/design/`, and variable lists live in `defaults/main.yml` and `meta/argument_specs.yml`.
- When the user describes a problem or asks a question, report findings first and change files only when asked.
- When a design decision changes, update the matching file under `docs/` and the affected directory's `README.md` in the same change.
- Skills for recurring work: `new-host`, `new-role`, `validate` (see [.agents/README.md](.agents/README.md)).
- Delegate wide repository exploration to subagents when the agent supports them; keep the main context for decisions.
- Claude Code subagents ([.claude/agents/](.claude/agents/)): `checker` runs the validation suite and reports the results verbatim; `reviewer` runs an independent read-only review. Run `checker` before reporting a change as done. Run `reviewer` only for non-trivial changes (design documents, new roles, anything spanning several files); weigh its findings, and the decision stays with the owner.

## Safety: this environment reaches production

The dev container mounts `~/.ssh` and the vault password, so it can reach the real Proxmox nodes and every VM, and the k3s cluster through the token in the vault.

- Anything that mutates infrastructure runs only when the user explicitly asks for that run in the current conversation, never "to investigate" or "to verify". That covers `playbooks/pve/*`, `playbooks/vm/*`, `playbooks/utils/*`, `playbooks/k8s/*` without `--check`, and write operations of `kubectl` / `helm`.
- Always allowed (read-only): `ansible-lint`, `ansible-playbook --syntax-check`, `ansible-inventory --graph|--list`, `ansible-playbook playbooks/k8s/<name>.yml --check --diff`, and read-only `kubectl` (`get`, `describe`, `logs`).
- Destructive operations (deleting VMs, powering off, draining nodes) must require an explicit confirmation variable in the playbook. Never work around such a guard.
- Changing a Proxmox host's NIC, VLAN or bridge settings can lock the node out. Do it only on explicit instruction and only after confirming console or out-of-band access.
- Never print decrypted vault content into chat, logs or commits. Never commit plaintext tokens, passwords, private keys or kubeconfigs.

## Validation before reporting done

Use the `validate` skill. In short:

```sh
ansible-galaxy collection install -r collections/requirements.yml   # once per container
ansible-lint                                                        # must end with 0 failure(s)
ansible-playbook --syntax-check playbooks/<domain>/<name>.yml
ansible-inventory --graph                                           # must print no warnings
```

Check that every relative link in a touched Markdown file resolves. State the results verbatim, and say explicitly what was not run (for example, that nothing was run against real infrastructure).

## Git

- Commit messages follow [docs/conventions.md](docs/conventions.md). Do not commit or push unless asked.
