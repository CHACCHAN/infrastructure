# infrastructure

自宅インフラをAnsibleで宣言的に管理するリポジトリ。使い方は各ディレクトリの `README.md`、設計は [docs/](docs/README.md)。リポジトリ直下がAnsibleプロジェクトのルート(`ansible.cfg`)。

旧構成は [legacy/](legacy/) に参照用として残している。新構成が揃うまで編集せず、lintの対象にもしない。

## ディレクトリ構成

```text
.
├── AGENTS.md                AIエージェント向けの運用ガイド(安全規則・作法。docs/ を import)
├── .agents/                 エージェント共通のスキル(new-host / new-role / validate)
├── .claude/                 Claude Code 専用(設定・サブエージェント。skills は .agents/ へのリンク)
├── .devcontainer/           開発コンテナ(Ansible・kubectl・Helm・エージェントCLI)
├── ansible.cfg              共通設定(roles_path / inventory)
├── .ansible-lint            lint設定(production profile、legacy/ は除外)
├── collections/
│   └── requirements.yml     使用するコレクション(単一の真実)
├── inventory/               ホスト宣言(単一の真実)
│   ├── hosts/               VLANごとに1ファイル(20_pve / 21_k3s / 22_private / 23_core / 24_hermes)
│   ├── group_vars/
│   │   ├── all/             全ホスト共通(network.yml=VLAN台帳、pve.yml=Proxmox API の共通値)
│   │   └── <group>.yml      グループ(役割)ごとの差分
│   └── host_vars/           個体差が出たホストだけ
├── playbooks/               薄いオーケストレーション(ロジックはロールに置く)
│   ├── pve/                 Proxmox(API): VMの作成・テンプレート
│   ├── vm/                  VM(SSH): OS設定・サービス導入・k3s構築
│   ├── k8s/                 クラスタ内アプリ(API トークン)
│   └── utils/               REST APIを叩く単発ツール
├── roles/                   ロール(ドメイン接頭辞: pve / vm / k8s)
├── vault/                   暗号化した秘密情報(1ファイル1用途)
└── docs/
    ├── README.md            案内(領域ごとの使い方と設計)
    ├── conventions.md       規約(命名・変数の層・冪等性・Vault・ドキュメント)
    └── design/              設計(network / k3s / k8s / pve / hardware)
```

## ロールの階層

| ロール | 役割 |
| --- | --- |
| `pve` | Proxmoxホスト自体の設定(NIC/VLAN・クラスタ) |
| `pve_vm` | VMの作成・更新 |
| `pve_template` | OSテンプレートの作成 |
| `vm` | 全VM共通のOS設定(Debian 13、ZRAM、SSH、FW) |
| `vm_k3s` | k3sノードの構築 |
| `k8s` | クラスタ内アプリを適用する共通処理(Helm) |

サービスVMは `vm_<service>`、クラスタ内アプリは `k8s_<app>` を追加する。変数名は接頭辞の層を落とす(`vm_k3s` → `k3s_*`)。

## 変数の層

`roles/*/defaults/main.yml`(既定値の単一の真実)→ `inventory/group_vars/`(既定との差分だけ)→ `inventory/hosts/`・`host_vars/`(個体差)→ `-e`(最優先)。
