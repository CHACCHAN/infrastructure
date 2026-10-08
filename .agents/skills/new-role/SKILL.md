---
name: new-role
description: Scaffold a new Ansible role that follows this repository's naming, layout and idempotency conventions. Use when adding a service VM role (vm_<service>), a Kubernetes app role (k8s_<app>) or a Proxmox role (pve_<name>).
---

# new-role

Read [docs/conventions.md](../../../docs/conventions.md) first (naming, variable layers, idempotency, secrets, versions).

## Steps

1. **Name.** `<domain>_<name>` with domain `pve`, `vm` or `k8s`. Variables drop the domain prefix: role `vm_k3s` uses `k3s_*`. If a role with a similar purpose exists, extend it instead.
2. **Layout** under `roles/<role>/`:
   - `defaults/main.yml`: every default, the single source of defaults. Image, chart and software versions live here as `<name>_version`.
   - `tasks/main.yml`: only `import_tasks` of stage files, in order (`validate` → `install` → `configure` → `verify`). Drop stages that do not apply.
   - `tasks/<stage>.yml`: the actual tasks.
   - `meta/argument_specs.yml`: type and required-ness of the role's inputs. Prefer it over hand-written `assert` tasks.
   - `templates/*.j2`: generated files start with `# Ansible(roles/<role>)が生成。手動編集は次回実行で上書きされる。`
   - `handlers/main.yml`: only if a handler is used.
   - `README.md`: Japanese, usage only, in this order: purpose (with the design document link), how to use (required variables, playbook, example), flow of the tasks. Do not copy variable lists; point to `ansible-doc -t role <role>`. See `roles/pve_vm/README.md` for the shape.
3. **Write the tasks.**
   - Task names are Japanese and say what the task achieves.
   - Prefer modules over `shell` / `command`. If unavoidable, add `creates` or a state check, plus `changed_when`.
   - Restart a service only through a handler triggered by a real change.
   - Do not overwrite configuration that the service itself owns.
   - Secrets arrive as variables from the playbook; tasks that touch them use `no_log: true`.
   - Do not hard-code IPs; derive them from inventory (`vlan` + `id`) or reference `hostvars`.
4. **Wire it up.** Add the playbook under `playbooks/<domain>/` (keep it thin: hosts, vars, role). For a new Kubernetes app, follow the `k8s` role pattern if one exists; while it is still a placeholder, ask the owner.
5. **Docs.** If a decision changed or a new component appeared, update the matching file under `docs/` and add the role to the area table in `docs/README.md`.
6. **Validate** with the `validate` skill. Do not run the new playbook against real infrastructure unless the user asked for that run.

## Do not

- Copy values from `legacy/` (old IPs, VMIDs, removed components).
- Put defaults in group_vars or tasks.
- Write history or reasoning into comments.
