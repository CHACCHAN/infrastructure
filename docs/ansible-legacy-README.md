# Ansible - Proxmox VM構築・サービスデプロイ

Proxmox上のVM構築(テンプレート作成〜クローン〜cloud-init)と、
VM内部のサービス構築(Docker Compose / k3s)をAnsibleで自動化するリポジトリです。

- 対象VMのOSは **Debian 13(cloud image)専用** です
- KubernetesのManifest類(kubectl / kustomize / Helm)は**別リポジトリ**で管理しています
  (このリポジトリはk3sノードの構築まで)

## ディレクトリ構造

```
.
├── ansible.cfg              # 共通設定(roles_path=./roles, inventory=./inventories/lab)
├── inventories/             # 環境ごとのインベントリ
│   └── lab/                 #   既定の環境。1サービス=1ファイル(グループ名=playbook名)
├── playbooks/               # オーケストレーションのみ(実処理はrolesへ)
│   ├── services/            #   サービス一気通貫構築(テンプレート→VM→VM内セットアップ)
│   │   └── _provision_vm.yml#   全サービス共通のVM構築フロー(単体では実行しない)
│   ├── proxmox/             #   Proxmoxホスト操作(テンプレート構築/VM作成/HW変更/電源/削除)
│   └── vms/                 #   VM内部のセットアップのみ(SSH接続。起動済みVMが前提)
├── roles/
│   ├── provision/           # 構築対象の決定・変数解決(playbooks/services/ 用)
│   ├── proxmox_connect/     # Proxmoxホストの動的インベントリ登録
│   ├── proxmox_common/      # Proxmox共通処理(ノード特定/VM一覧/cloud-init適用)
│   ├── proxmox_os_defaults/ # OS別テンプレート定義の読み込み(vars/os_defaults/)
│   ├── proxmox_*            # Proxmox操作ロール(template_build / vm_build / vm_hardware 等)
│   ├── vm_connect/          # 対象VMの動的インベントリ登録とSSH疎通確認
│   ├── common/              # VM共通セットアップ(パッケージ/タイムゾーン/zram/ufw等)
│   ├── docker/              # Dockerインストールとcompose配置
│   └── <サービス名>/         # サービスロール(authentik / kubernetes / supabase 等)
├── vault/                   # ansible-vaultで暗号化した秘密情報(→ vault/README.md)
└── docs/                    # 各playbookの詳細ドキュメント
    ├── services/            #   サービス一気通貫構築の使い方
    ├── proxmox/             #   Proxmox操作playbookの使い方
    └── vms/                 #   VM内セットアップplaybookの使い方
```

### 3層構造の役割分担

| 層 | Playbook | 対象 | 内容 |
| --- | --- | --- | --- |
| サービス | `playbooks/services/` | (下2層を呼ぶ) | テンプレート構築からVM内セットアップまで一気通貫。通常はこれを使う |
| Proxmox | `playbooks/proxmox/` | Proxmoxホスト | テンプレート構築・VMクローン・ハードウェア変更・電源操作など単機能 |
| VM | `playbooks/vms/` | VM内部(SSH) | OS初期設定とサービス構築のみ。構築済みVMの更新にも使う |

Playbookは**オーケストレーション(実行順・対象の制御)だけ**を持ち、実処理はすべて `roles/` にあります。

## 使い方

すべて**リポジトリ直下**から実行します(`ansible.cfg` がroles/inventoryを解決します)。

```sh
# サービスを一気通貫で構築(対象は inventories/lab/<サービス名>.yml に記載)
ansible-playbook playbooks/services/supabase.yml --ask-vault-pass

# 1台だけ構築
ansible-playbook playbooks/services/supabase.yml --ask-vault-pass --limit 172.16.11.6

# Proxmox単機能操作(例: VMの電源ON)
ansible-playbook playbooks/proxmox/proxmox_vm_powerctl.yml --ask-vault-pass \
  -e "proxmox_ip=<ノードIP> proxmox_target_vmid=402 power_state=on"

# 構築済みVMのサービスだけ更新
ansible-playbook playbooks/vms/supabase.yml \
  -e "vm_ip=<VMのIP> vm_ssh_user=<ユーザー> vm_ssh_prikey=~/.ssh/<秘密鍵>"
```

詳細は各層のREADMEへ:
[docs/services/README.md](docs/services/README.md) /
[docs/proxmox/README.md](docs/proxmox/README.md) /
[docs/vms/README.md](docs/vms/README.md) /
[vault/README.md](vault/README.md)

## インベントリと環境

- `inventories/lab/` が既定の環境です(`ansible.cfg` の `inventory`)
- 環境を増やすときは `inventories/<環境名>/`(例: `production` / `testing`)を作り、
  `-i inventories/<環境名>` で切り替えます。ファイル形式・グループ名は `lab/` と同じにします
- インベントリのホスト名は**構築するVMのIPアドレス**で、1サービス=1ファイルです

## AWXから使う場合

このリポジトリはAWXのGit Projectとしてそのまま使える構成です。

- **Job Template**: `playbooks/services/` `playbooks/proxmox/` `playbooks/vms/` の各playbookを
  1つずつJob Templateにします(`_provision_vm.yml` は共通部品なので対象外)
- **Inventory**: `inventories/lab/` をAWXのInventory(Source: Project)として取り込みます。
  環境を増やしたら環境ごとにInventoryを作ります
- **Credential**: Vaultパスワードは「Vault」タイプのCredentialにします
  (`--ask-vault-pass` の代わり)。`-e` で渡していた値はSurvey/Extra Variablesで渡せます
- ロールは `roles/` に集約されているため、AWX側の追加設定(roles_pathの調整)は不要です

## 開発環境

VS Code Dev Containerの設定があります([docs/devcontainer.md](docs/devcontainer.md))。
