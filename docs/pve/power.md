# power.yml — 電源状態を収束させる

宣言済みVM(またはインベントリ外VM)の電源を `started` / `stopped` へ**冪等に収束**させる。すでに目的の状態なら `changed=0`。

## 実行方法

### インベントリ実行

```sh
ansible-playbook playbooks/pve/power.yml -l k8s -e state=started
ansible-playbook playbooks/pve/power.yml -l k8s -e state=stopped
# ゲストが応答しない場合の強制停止
ansible-playbook playbooks/pve/power.yml -l yuya-dev -e state=stopped -e pve_power_force=true
```

### 直接実行(インベントリ外VM)

```sh
ansible-playbook playbooks/pve/power.yml -e state=stopped \
  -e target=tmp01 -e profile=dev -e vmid=799 -e node=pve07 -e ip=172.16.11.99
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `state` | str | ✔ | - | `started` または `stopped` |
| `target` | str | | `lab` | 対象のホスト/グループ |
| `vmid` / `node` / `ansible_host` | | ✔ | - | ホストごとの識別(hosts.yml または adhoc変数) |
| `pve_power_timeout` | int | | `300` | 停止待ちの上限(秒)。stopped時のみ |
| `pve_power_force` | bool | | `false` | 応答しないゲストの強制停止。stopped時のみ |
| `vault_proxmox_api_*` | str | ✔ | - | API認証4変数([vault/proxmox_api.yml](../../vault/proxmox_api.yml)) |

## 動きかた

- `stopped` は**ゲストOSへの正常シャットダウン要求**。起動直後などゲストが応答できない間は失敗する
- 操作前にVMID・VM名・ノードを照合し、宣言と違う実体を掴んだら止まる

## AWXでの実行

Job Template **`pve-power`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。

- Survey: `target`(**必須**。誤って全VMを止めないためのガード)、`state`(**必須**・選択式)、`pve_power_force`(任意・選択式)、`pve_power_timeout`(任意)
- インベントリ外VMを対象にする場合は変数欄で `profile` / `vmid` / `node` / `ip` を追加する

## つまずきやすいポイント

- **`powerdown failed - got timeout`** → ゲストが要求に応答できない(起動直後・エージェント未起動)。少し待って再実行するか `-e pve_power_force=true`
- **stateの指定漏れ** → 必須。playbookが実行前に検出して止まる
- **削除の前段として使う** → [destroy.md](destroy.md) は停止中のVMしか消せない。先にここで `stopped` へ収束させる
