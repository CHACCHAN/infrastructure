# proxmox-ansible

Proxmox VE上にDebian 13のcloud-init対応VMテンプレートを作成し、そこから用途別VM(k3s master/worker、dev、wireguard)をクローンするAnsibleワークスペース。

Proxmox APIのみで完結し、VMイメージのダウンロードからディスクインポートまでSSHを使わない。

対になる [k3s-ansible](../k3s-ansible) は、ここで付与した `tags` を元に `community.general.proxmox` 動的inventoryでホストをグルーピングする前提。

## 前提条件

### 1. API tokenの作成(Proxmoxノード上で1回だけ)

```bash
pveum user token add root@pam ansible --privsep 0
pveum acl modify / --tokens 'root@pam!ansible' --roles Administrator
```

ラボ用途のため簡易にAdministratorロールを付与している。本番相当で使う場合は `VM.Allocate` / `VM.Config.*` / `Datastore.AllocateTemplate` / `Sys.AccessNetwork` 程度に絞ることを推奨。

### 2. ストレージのimportコンテンツ有効化

cloud imageのダウンロード先ストレージ(`vars/vms.yml` の `dl_storage`、既定値 `local`)で `import` コンテンツタイプを有効化する。

```bash
pvesm set local --content iso,vztmpl,backup,snippets,import
```

### 3. token secretの設定

```bash
cp group_vars/vault.yml.example group_vars/vault.yml
# group_vars/vault.yml の REPLACE_ME を実際のtoken secretに書き換える
ansible-vault encrypt group_vars/vault.yml
```

### 4. 必要なcollectionのインストール

```bash
ansible-galaxy collection install ansible.builtin
```

(`ansible.builtin` は同梱だが、`community.general` を将来使う場合は別途インストール)

## 実行

```bash
# 1. Debian13テンプレートを作成(既に存在する場合は自動でスキップ)
ansible-playbook playbooks/build_template.yml --ask-vault-pass

# 2. テンプレートから各VMをクローンし、cloud-init/ネットワーク/tagsを適用して起動
ansible-playbook playbooks/clone_vms.yml --ask-vault-pass
```

## ディレクトリ構成

```
proxmox-ansible/
├── ansible.cfg
├── inventory/
│   └── hosts.yml          # localhost のみ(API操作)
├── group_vars/
│   ├── all.yml             # Proxmox API接続情報
│   └── vault.yml.example   # token secretのテンプレート
├── vars/
│   └── vms.yml             # テンプレート定義 + クローン対象VM一覧(tags付き)
└── playbooks/
    ├── build_template.yml
    └── clone_vms.yml
```

## 既知の制約・today's scope外

- クローン後のSSH到達性待機は未実装(`clone_vms.yml` 実行後、k3s-ansible側で `wait_for_connection` を挟む想定)
- ディスクリサイズ未実装(cloud imageそのままのサイズで作成される)
- ゲストOS内のNICインターフェース命名(`net.ifnames=0` 等)はテンプレート側で未対応。将来cloud-initのvendor-data snippetで対応予定
