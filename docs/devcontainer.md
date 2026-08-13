# .devcontainer セットアップ手順

このリポジトリをVS CodeのDev Containerで開くときの注意点です。

## Claude Code / Codex を使わない場合

`devcontainer.json` の `mounts` には、デフォルトで Claude Code (`~/.claude`) と Codex (`~/.codex`) のマウント設定が**有効な状態で含まれています**。

- 使わない場合、単に中身が空のディレクトリがコンテナ内にマウントされるだけで実害はありません

それでも自分の環境に不要なマウントを残したくない場合は、`devcontainer.json` の該当行を削除(またはコメントアウト)してください。

```jsonc
"mounts": [
   // 不要なら以下の2行を削除してください
   "source=${localEnv:HOME}${localEnv:USERPROFILE}/.claude,target=/home/vscode/.claude,type=bind,consistency=cached",
   "source=${localEnv:HOME}${localEnv:USERPROFILE}/.codex,target=/home/vscode/.codex,type=bind,consistency=cached"

   "source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind",
   "source=${localEnv:HOME}${localEnv:USERPROFILE}/.gitconfig,target=/home/vscode/.gitconfig,type=bindconsistency=cached",
],
```

また拡張機能でclaude codeが入っているので使わない場合は削除(またはコメントアウト)してください。

```jsonc
"extensions": [
   // 省略
   "anthropic.claude-code",
   // 省略
],
```
