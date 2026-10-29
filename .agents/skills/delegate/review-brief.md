# Review brief (template)

Copy everything below the line into a brief file, fill in the angle brackets, and run it with `cc-max`. For two independent opinions, give the same brief to a second model and compare the answers yourself.

---

You review a change you did not write. You have no stake in it. Do not edit any file.

## The change

<What the change is for, and the owner's decisions it implements, quoted with their source.>

The last commit of this copy (`base`) holds the uncommitted work; read it with `git show HEAD`. <For work that is already committed: `git diff <commit hash> HEAD` (the sandbox rejects `~` in commands).> Review only these paths: <paths>. <Optional focus.>

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
