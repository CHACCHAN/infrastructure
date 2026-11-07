# Review brief (template)

Copy everything below the line, fill in the angle brackets, and pass it to a fresh Mistral Vibe CLI session with only `read_file` enabled, following [the job procedure](README.md#delegated-jobs). Do not reuse the implementation session. The CLI is not an OS sandbox; keep the first paragraph's restrictions.

---

You review a change you did not write. You have no stake in it. This is a delegated review job, not the main agent. Do not edit any file, delegate, read secrets, or run commands (including `git`, `ansible*`, `kubectl`, `helm`, `ssh` and `curl`). Ansible evaluates Jinja while parsing, and the main environment reaches production. Only read the supplied diff and relevant non-secret files with `read_file`. The main agent handles all validation.

## The change

<What the change is for, and the owner's decisions it implements, quoted with their source.>

The main agent supplied a plain-text diff at <absolute diff path>, comparing the candidate with <base description>. Review only these paths: <paths>. <Optional focus.>

## Method

1. Read `AGENTS.md`, `docs/conventions.md`, `docs/design/network.md` and `docs/design/k3s.md`; read `docs/design/hardware.md` when capacity matters, and the `README.md` of every directory the change touches.
2. Read changed files in full when the diff is not enough. Ignore `legacy/`.

## What to check, in this order

1. Contradictions between the change and the decisions in `docs/design/`, and decisions invented where the documents say undecided.
2. Correctness: wrong IP / VMID / VLAN derivation, broken YAML or Jinja, tasks that are not idempotent, missing `no_log` on secrets, unsafe operations against production.
3. Violations of `docs/conventions.md` (naming, variable layers, comments that record history).
4. Broken relative links in touched Markdown files.

## Report

Only real problems, most severe first, each as: `file:line`, what is wrong, a concrete failure scenario, and the fix. If there are none, say so in one line. Do not praise, summarise or restate the diff. State what you could not check.
