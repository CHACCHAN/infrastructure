# AGENTS.md

Operating guide for AI coding agents (Claude Code, Codex, Antigravity, etc.) working in this repository.
Human-facing documentation starts at [README.md](README.md) and [docs/README.md](docs/README.md).

## What this repository is

Home-lab infrastructure managed **declaratively with Ansible**. The repository root is the Ansible project root (`ansible.cfg`).

| Domain | Roles | Playbooks | Talks to |
| --- | --- | --- | --- |
| ① pve | `pve`, `pve_vm`, `pve_template` | `playbooks/pve/` | Proxmox VE API (`connection: local`) |
| ② vm | `vm`, `vm_docker`, `vm_<service>` | `playbooks/vm/` | Service VMs over SSH (after ① provisions them) |
| ③ k8s | `k8s`, `k8s_<app>` | `playbooks/k8s/` | k3s cluster via kubeconfig (server-side apply) |
| utils | – | `playbooks/utils/{awx,authentik}/` | REST APIs, one-shot tools |

Other directories: `inventory/` (the single source of truth), `vault/` (encrypted secrets), `awx/` (AWX Job Templates / Surveys / Credentials as code), `ee/` (AWX execution environment; `collections/requirements.yml` is a symlink into it), `docs/` (mirrors `playbooks/`).

**Language**: documentation, comments, task names and commit messages are written in Japanese. Only this file and `CLAUDE.md` are English.

## Conventions that must hold

1. **Three variable layers, no merge logic.** `roles/*/defaults/main.yml` (every default, the single source) → `inventory/group_vars/<role>.yml` (only the differences for that role) → `inventory/hosts.yml` (per-VM: `vmid`, `node`, `ansible_host`, individual overrides). Ansible precedence does the merging; extra vars (`-e`, AWX Survey) override everything.
2. **Naming.** Role `<domain>` is the base, `<domain>_<name>` is an implementation. Variables drop the domain prefix (`vm_authentik` → `authentik_*`, `pve_vm` → `pve_*`). Shared roles `vm` / `vm_docker` receive arguments as `svc_*`. Inventory group name = role name; host names must differ from group names (`authentik01`, `coolify01`), and `pve_vm_name` pins the VM name on Proxmox when it differs.
3. **Templates (`default.yml` / `default.md`).** Every directory that holds playbooks, roles, docs, group_vars, awx or vault files has one. Copy it to add a new item, keep heading names and order, delete sections that do not apply. Templates contain placeholders and are listed in `.ansible-lint` `exclude_paths`; add any new template path there. Changing a template is allowed when the new shape is applied to all existing files of that directory.
4. **Docs mirror playbooks.** One playbook = one page at the same path under `docs/`. Adding a playbook also means: a row in `docs/<domain>/README.md`, a Job Template in `awx/job_templates.yml`, and a row in `vault/README.md` if a new vault file appears.
5. **Comment and prose style.** Describe the current purpose only. No history ("used to be", "changed from"), no process narrative, no work reports, no justification of lint suppressions beyond one line. Prefer one-line comments. Default values live in code and are not copied into docs.
6. **Idempotency.** Every task converges: a second run yields `changed=0`. `shell` / `command` need `creates` or `changed_when` plus a state check. Compare with the live state before updating (pve: `proxmox_vm_info` vs declared values). No random, time-based or `lookup('password')` values in rendered templates. Secrets are handled with `no_log`.
7. **Two execution modes, one implementation.** Inventory run (`ansible-playbook playbooks/<d>/<n>.yml`) and direct run (`-e target= -e profile= -e vmid= -e node= -e ip=`) share the same playbook and variable names. Never branch on the mode. Selection uses the `target` variable (not `-l`) so the `localhost` preparation plays are not excluded in AWX. Optional Survey questions are `required: false` without `default`; defaults are applied with `default()` in code.
8. **Secrets.** `vault/*.yml` are encrypted with one shared password (`ANSIBLE_VAULT_PASSWORD_FILE` is set in the dev container). Edit with `ansible-vault edit`, never by hand. Do not print decrypted vault content into chat, logs or commits; do not commit plaintext tokens, passwords or private keys.

## Safety: this environment reaches production

The dev container can reach the real Proxmox API, the k3s cluster and every service VM. These playbooks mutate real infrastructure: `playbooks/pve/*` (except `--syntax-check`), `playbooks/vm/*`, `playbooks/k8s/deploy.yml` without `--check`, `playbooks/utils/*`.

- Do not run them unless the user explicitly asks for that run in the current conversation.
- Read-only operations are always fine: `ansible-lint`, `ansible-playbook --syntax-check`, `ansible-inventory --graph`, `ansible-playbook playbooks/k8s/deploy.yml --check --diff`.
- `destroy.yml` requires `-e confirm=<vmid>`; never work around that guard.
- Throwaway VM convention for agreed tests: `-e target=tmp01 -e profile=dev -e vmid=799` (see `docs/pve/adhoc.md`).

## Validation before reporting done

```sh
ansible-galaxy collection install -r ee/requirements.yml   # once; awx.awx is needed for utils/awx syntax checks
ansible-lint --profile production --offline                # must end with 0 failure(s)
ansible-playbook --syntax-check playbooks/<domain>/<name>.yml
ansible-inventory --graph                                  # must print no "same name" warnings
```

Check that every relative link in a touched Markdown file resolves, and that docs, `awx/job_templates.yml` and code agree on variable names and Job Template names.

## Checklists

**New service VM** (`<svc>`)
1. `roles/vm_<svc>/` from `roles/default.yml` (`defaults/main.yml`, `tasks/main.yml` importing `validate` → `vm` → `vm_docker` → install → configure → `configure_ufw_ports` → `verify_service`).
2. `playbooks/vm/<svc>.yml` from `playbooks/vm/default.yml` (three plays: `ssh_key.yml` → `../pve/provision.yml` → SSH setup).
3. Group `<svc>` with host `<svc>01` in `inventory/hosts.yml`; `inventory/group_vars/<svc>.yml` from its `default.yml`.
4. `docs/vm/<svc>.md` from `docs/vm/default.md`; row in `docs/vm/README.md`; entry in `awx/job_templates.yml`; vault file and `vault/README.md` row if secrets exist; `infrastructure.md` if a new IP or public route appears.

**New Kubernetes app** (`<app>`)
1. `roles/k8s_<app>/` (templates rendered through `roles/k8s` apply/helm tasks).
2. Register in `k8s_apps` in `inventory/group_vars/all/k8s.yml`; secrets in `vault/k8s_secrets.yml` as `k8s_secret_<name>`.
3. External services go through `k8s_external_routes` in the same file, not a hand-written Ingress.

## Git

- Commit messages are Japanese, one-line summaries in the style of `git log`. Do not commit or push unless asked.
- `vault/*.yml` are marked `-diff -merge` in `.gitattributes`; resolve conflicts by re-encrypting, never by merging text.
