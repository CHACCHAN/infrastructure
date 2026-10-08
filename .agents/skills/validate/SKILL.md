---
name: validate
description: Run the repository's validation suite (ansible-lint, syntax checks, inventory graph, Markdown link check) and report the results honestly. Use before saying a change is done.
---

# validate

Run these from the repository root. None of them touches real infrastructure. Do not substitute a mutating playbook run for any step.

1. Install collections (once per container):
   `ansible-galaxy collection install -r collections/requirements.yml`
2. Lint: `ansible-lint`. The configuration is in `.ansible-lint` (production profile, `legacy/` excluded). It must end with `0 failure(s)`.
3. Syntax: for every playbook you added or changed, `ansible-playbook --syntax-check playbooks/<domain>/<name>.yml`.
4. Inventory: `ansible-inventory --graph`. It must print no warnings, in particular no parse failures and no "same name" warnings between a group and a host.
5. Links: every relative Markdown link in a file you touched must resolve.
   ```sh
   for f in <touched .md files>; do
     grep -oE '\]\([^)#:]+' "$f" | sed 's/](//' | while read -r l; do
       [ -e "$(dirname "$f")/$l" ] || echo "BROKEN: $f -> $l"
     done
   done
   ```
6. Consistency: variable names used in docs, `defaults/main.yml`, group_vars and templates agree.

## Reporting

- Quote each command and its result verbatim.
- If a tool is missing or a step could not run, say so. Never describe an unrun step as passed.
- State explicitly whether anything was run against real infrastructure (normally: no).
