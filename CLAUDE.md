# CLAUDE.md

Operating guide for AI agents working in this repository. Human-facing documentation starts at [README.md](README.md) and [docs/README.md](docs/README.md).

## What this repository is

Home-lab infrastructure managed declaratively with Ansible. The repository root is the Ansible project root (`ansible.cfg`).

| Domain | Roles | Playbooks | Talks to |
| --- | --- | --- | --- |
| ① pve | `pve` `pve_vm` `pve_template` | `playbooks/pve/` | Proxmox VE API (`connection: local`, token from `vault/proxmox_api.yml`) |
| ② vm | `vm` `vm_docker` `vm_<service>` | `playbooks/vm/` | Debian 13 VMs created by ①, over SSH |
| ③ k8s | `k8s` `k8s_<app>` | `playbooks/k8s/deploy.yml` | k3s cluster via `~/.kube/config` (server-side apply) |
| utils | none | `playbooks/utils/{awx,authentik}/` | One-shot tools that call REST APIs |

- `inventory/` is the single source of truth: `hosts.yml` lists every VM, `group_vars/all/` holds cluster-wide values, `group_vars/<role>.yml` holds the role profile.
- `vault/` is fully encrypted (only `vault/default.yml` is a plaintext template). `awx/` holds AWX Job Templates, Surveys and Credentials as code.
- `ee/` defines the AWX execution environment. `collections/requirements.yml` is a symlink to `ee/requirements.yml`. `context/` is ansible-builder output and is git-ignored (never edit it).
- `docs/` mirrors `playbooks/` (one playbook = one page).
- Network layout and public routes: [infrastructure.md](infrastructure.md).

**Language**: documentation, comments, task names and commit messages are Japanese. Product names use their official spelling (cert-manager, k3s, …). Only this file is English.

## Safety: this environment reaches production

The dev container can reach the real Proxmox API, the k3s cluster and every service VM. These mutate real infrastructure: `playbooks/pve/*` (except `--syntax-check`), `playbooks/vm/*`, `playbooks/k8s/deploy.yml` without `--check`, `playbooks/utils/*`.

- Run them only when the user explicitly asks for that run in the current conversation. Never run them "to investigate" or "to verify".
- Always allowed (read-only): `ansible-lint`, `ansible-playbook --syntax-check`, `ansible-inventory --graph`, `ansible-playbook playbooks/k8s/deploy.yml --check --diff`.
- `destroy.yml` requires both `-e vmid=<id>` and `-e confirm=<id>`. Never work around that guard.
- `power.yml` targets every lab VM when `target` (or `-l`) is omitted. `-e state=stopped` requires an explicit target.
- Throwaway VM for agreed tests: `-e target=tmp01 -e profile=dev -e vmid=799 -e node=pve07 -e ip=172.16.11.99` ([docs/pve/adhoc.md](docs/pve/adhoc.md)).
- Never print decrypted vault content into chat, logs or commits. Never commit plaintext tokens, passwords or private keys.

## Conventions that must hold

1. **Three variable layers, no merge logic.** `roles/*/defaults/main.yml` (every default, the single source) → `inventory/group_vars/<role>.yml` (only differences from the defaults) → `inventory/hosts.yml` (per-VM `vmid` / `node` / `ansible_host` and individual overrides). Never repeat a default value in group_vars. Extra vars (`-e`, AWX Survey) override everything.
2. **Naming.** Role `<domain>` is the base, `<domain>_<name>` is an implementation. Variables drop the domain prefix (`vm_authentik` → `authentik_*`, `vm_ddns` → `ddns_*`, `pve_vm` → `pve_*`). Shared roles `vm` / `vm_docker` receive arguments as `svc_*`. Inventory group name = role name; host names differ from group names (`authentik01`); `pve_vm_name` pins the VM name on Proxmox when it differs.
3. **Templates (`default.yml` / `default.md`).** Every directory holding playbooks, roles, docs, group_vars, awx or vault files has one. Copy it to add an item; keep heading names and order; delete sections that do not apply. Templates contain placeholders and are listed in `.ansible-lint` `exclude_paths` — add any new template there.
4. **Docs mirror playbooks.** Adding a playbook also means `docs/<domain>/<name>.md`, a row in `docs/<domain>/README.md`, a Job Template in `awx/job_templates.yml`, and a row in `vault/README.md` if a new vault file appears.
5. **Comments and prose describe purpose only.** No history ("used to be", "changed from"), no work reports, no reasoning narrative; one line for a lint suppression. Defaults live in code and are not copied into docs.
6. **Idempotency.** A second run yields `changed=0`. `shell` / `command` are a last resort and need `creates` or a state check plus `changed_when`. Compare with live state before updating (pve: `proxmox_vm_info` vs declared values). No random, time-based or `lookup('password')` values rendered directly into templates (pair them with reuse of the existing value). Secrets use `no_log`; commands that echo whole environments (e.g. `docker inspect`) are filtered with `--format` or made `no_log`.
7. **Two execution modes, one implementation.** Inventory run (`ansible-playbook playbooks/<d>/<n>.yml`) and direct run (`-e target= -e profile= -e vmid= -e node= -e ip=`) share the same playbook and variable names; never branch on the mode. Select with the `target` variable, not `-l` (`-l` would exclude the `localhost` plays of `adhoc.yml` / `ssh_key.yml`). Optional Survey questions are `required: false` without `default`; defaults are applied with `default()` in code. An empty string is not "undefined": use `default(x, true)`.
8. **Secrets.** `vault/*.yml` share one password (`ANSIBLE_VAULT_PASSWORD_FILE` is set by the dev container). Edit with `ansible-vault edit`. Names are `vault_<service>_<purpose>`; playbooks pass them to roles as ordinary variables via `vars`. Kubernetes Secrets live in `vault/k8s_secrets.yml` as `k8s_secret_<name>`.
9. **`-e key=value` splits on whitespace.** Multi-line or space-containing values (kubeconfig, display names) must be passed as JSON `-e '{"key": "..."}'`, as `-e @file.json`, or through a file-path variable. Write documentation examples the same way.
10. **Jinja pitfalls on this ansible-core (2.21).** `regex_search` with a group argument raises when nothing matches; use `regex_replace` guarded by `is search`. A `'\1'` backreference inside a Jinja string literal becomes `chr(1)`; put such expressions in YAML block scalars (`>-`) where `'\\1'` survives, as the existing tasks do.
11. **Server-side apply ownership.** Objects once created by another field manager (e.g. `helm`) conflict when a label value changes. The one-time takeover is `playbooks/k8s/deploy.yml -e force=true`; run `--check --diff -e force=true` first.

## Where versions live

- Ansible collections: `ee/requirements.yml` (version ranges). Python deps: `ee/requirements.txt`. The dev container installs them through the ansible feature in `.devcontainer/devcontainer.json`. Note that `quay.io/ansible/awx-ee:latest` pins `ansible-core<2.19` while the dev container runs 2.21; do not rely on 2.19+ templating behavior.
- Container images and Helm charts: each `roles/*/defaults/main.yml` (`<service>_version`, `k8s_<app>_helm_version`). Some image tags are written directly in `roles/k8s_*/templates/*.j2`.
- Helm charts are rendered by `roles/k8s/tasks/helm.yml`; a chart reference starting with `oci://` is used without `--repo`.
- k3s: `kubernetes_version` in `inventory/group_vars/k8s.yml` (main cluster) and in `inventory/group_vars/rancher.yml` (Rancher VM). The Rancher VM version must stay inside Rancher's support matrix. Lowering a version is refused unless `kubernetes_allow_downgrade=true`.
- Rancher: `rancher_version` must exist as a chart in the configured repo (`helm search repo rancher-latest/rancher --versions`); a GitHub release tag alone is not enough.
- Nextcloud upgrades copy the release onto NFS and can exceed the role's rollout wait; the pod's startup probe allows two hours, so re-run `-e app=nextcloud` after the pod turns Ready instead of restarting it.
- When bumping a version, check the matching `docs/vm/*.md` / `docs/k8s/*.md` page and `infrastructure.md`.

## Validation before reporting done

```sh
ansible-galaxy collection install -r ee/requirements.yml   # once; awx.awx is needed for utils/awx syntax checks
ansible-lint --profile production --offline                # must end with 0 failure(s)
ansible-playbook --syntax-check playbooks/<domain>/<name>.yml
ansible-inventory --graph                                  # must print no "same name" warnings
```

Check that every relative link in a touched Markdown file resolves, and that docs, `awx/job_templates.yml` and code agree on variable names and Job Template names. If nothing was run against real infrastructure, say so explicitly in the report.

## Checklists

**New service VM** (`<svc>`)
1. `roles/vm_<svc>/` from `roles/default.yml` (`defaults/main.yml`; `tasks/main.yml` imports validate → vm → vm_docker → install → configure → configure_ufw_ports → verify_service).
2. `playbooks/vm/<svc>.yml` from `playbooks/vm/default.yml` (three plays: `ssh_key.yml` → `../pve/provision.yml` → SSH setup).
3. Group `<svc>` with host `<svc>01` in `inventory/hosts.yml`; `inventory/group_vars/<svc>.yml` from its `default.yml`.
4. `docs/vm/<svc>.md` from `docs/vm/default.md`; row in `docs/vm/README.md`; entry in `awx/job_templates.yml`; `vault/<svc>.yml` plus a `vault/README.md` row if secrets exist; `infrastructure.md` if a new IP or public route appears.
5. Anything reachable from the LAN or the internet goes through `k8s_external_routes` in `inventory/group_vars/all/k8s.yml`, never a hand-written Ingress.

**New Kubernetes app** (`<app>`)
1. `roles/k8s_<app>/` (templates are applied through the `roles/k8s` apply / helm tasks).
2. Register in `k8s_apps` in `inventory/group_vars/all/k8s.yml` in dependency order; secrets in `vault/k8s_secrets.yml` as `k8s_secret_<name>`.
3. Update the list in `docs/k8s/README.md`.

## Git

- Commit messages are Japanese one-line summaries in the style of `git log`. Do not commit or push unless asked.
- `vault/*.yml` are `-diff -merge` in `.gitattributes`; resolve conflicts by re-encrypting, never by merging text.

## Claude Code specifics

- When the user describes a problem or asks a question, report findings first and apply changes only when asked.
- Before reporting a change as done, run the validation commands above and state the results verbatim.
- Delegate repository exploration and bulk file reading to subagents; keep the main context for decisions and integration.
