# .devcontainer セットアップ手順

このリポジトリをVS CodeのDev Containerで開くときの注意点です。

## Featuresの設定

- 標準で`Codex CLI, Claude Code CLI, NodeJS`が入っています。
- Ansibleに直接必要ではないので必要に応じて調整してください。

```json
"ghcr.io/devcontainers/features/node:2": {},
"ghcr.io/anthropics/devcontainer-features/claude-code:latest": {},
"ghcr.io/devcontainers-extra/features/npm-packages:1": {
    "packages": "@openai/codex"
},
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
    "source=${localEnv:HOME}/.ansible_vault_pass,target=/home/vscode/.ansible_vault_pass,type=bind,consistency=cached"
]
```
