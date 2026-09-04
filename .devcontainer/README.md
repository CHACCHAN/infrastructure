# .devcontainer セットアップ手順

このリポジトリをVS CodeのDev Containerで開くときの注意点です。

## Featuresの設定

- 標準で`NodeJS, Claude Code CLI, Codex CLI, kubectl, helm, kubectx/kubens, k9s, lazygit, helmfile`が入っています。`Antigravity CLI`は`postCreateCommand`で導入されます。
- Ansibleに直接必要ではないので必要に応じて調整してください。

```json
"ghcr.io/devcontainers/features/node:2": {},
"ghcr.io/anthropics/devcontainer-features/claude-code:latest": {},
"ghcr.io/devcontainers-extra/features/npm-packages:1": {
    "packages": "@openai/codex"
},
"ghcr.io/devcontainers/features/kubectl-helm-minikube:1": {
    "helm": "latest",
    "kubectl": "latest",
    "minikube": "none"
},
"ghcr.io/devcontainers-extra/features/kubectx-kubens:1": {},
"ghcr.io/dhoeric/features/k9s:1": {},
"ghcr.io/thediveo/devcontainer-features/lazygit:0": {},
"ghcr.io/schlich/devcontainer-features/helmfile:1": {}
```

## Mountsの設定

- `.ssh, .kube, .ansible_vault_pass`は実際にAnsibleのタスクを実行するのに必須になります。
- その他は必要に応じて調整を行ってください。

```json
"mounts": [
    "source=${localEnv:HOME}/.ssh,target=/home/vscode/.ssh,type=bind",
    "source=${localEnv:HOME}/.gitconfig,target=/home/vscode/.gitconfig,type=bind,consistency=cached",
    "source=${localEnv:HOME}/.claude,target=/home/vscode/.claude,type=bind,consistency=cached",
    "source=${localEnv:HOME}/.codex,target=/home/vscode/.codex,type=bind,consistency=cached",
    "source=${localEnv:HOME}/.claude.json,target=/home/vscode/.claude.json,type=bind,consistency=cached",
    "source=${localEnv:HOME}/.kube,target=/home/vscode/.kube,type=bind,consistency=cached",
    "source=${localEnv:HOME}/.ansible_vault_pass,target=/home/vscode/.ansible_vault_pass,type=bind,consistency=cached",
    "source=${localEnv:HOME}/.gemini,target=/home/vscode/.gemini,type=bind,consistency=cached",
    "source=${localEnv:HOME}/.cline,target=/home/vscode/.cline,type=bind,consistency=cached"
]
```
