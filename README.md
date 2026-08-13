# infrastructure

自宅ラボのインフラを **Ansible中心・宣言的** に管理するリポジトリ。
Proxmox VEクラスタ上のVM構築から、VM内のサービスセットアップ、Kubernetesマニフェストの適用までを、ひとつの体系で扱う。

## 設計思想

**「ベース → 役割ごとの最適化 → 実装」の3層**で全ドメインを統一する。
変数のマージ処理は書かず、Ansible標準の変数優先順位に任せる。優先度は **読みやすさ > 共通化**。

```mermaid
flowchart TB
    subgraph L1["ベース層"]
        RD["roles/*/defaults<br>(全変数の既定値一覧)"]
        GA["inventory/group_vars/all/<br>(クラスタ共通値)"]
    end
    subgraph L2["役割プロファイル層"]
        GK["group_vars/k8s.yml<br>(2NIC・8コア…)"]
        GD["group_vars/dev.yml<br>(開発向け…)"]
        GS["group_vars/その他役割.yml"]
    end
    subgraph L3["実装層"]
        H["inventory/hosts.yml<br>1VM = vmid / node / IP の3行"]
    end
    L1 -->|"差分だけ上書き"| L2 -->|"個体差だけ上書き"| L3
```

## 3つのドメイン

**命名規則はひとつだけ**: `<ドメイン>` = ベースロール、`<ドメイン>_<名前>` = そのドメインの部品・実装。

| ドメイン | ベース | 実装 | playbook |
| --- | --- | --- | --- |
| ① Proxmox操作 | `roles/pve` `pve_vm` `pve_template` | インベントリの宣言そのもの | `playbooks/pve/` |
| ② VMセットアップ | `roles/vm` `vm_docker` | `vm_authentik` `vm_wg_easy` `vm_k3s` … | `playbooks/vm/` |
| ③ Kubernetes | `roles/k8s` | `k8s_external` `k8s_portainer` `k8s_guacamole` … | `playbooks/k8s/` |

```mermaid
flowchart LR
    INV[("inventory/<br>宣言(単一の真実)")]
    subgraph D1["① Proxmox操作 (API)"]
        PVE["pve / pve_vm / pve_template"]
    end
    subgraph D2["② VMセットアップ (SSH)"]
        VM["vm / vm_docker / vm_サービス"]
    end
    subgraph D3["③ Kubernetes (kubeconfig)"]
        K8S["k8s / k8s_アプリ"]
    end
    INV --> D1 & D2
    D1 -->|"VMを用意"| PVECLUSTER["Proxmox VEクラスタ<br>pve01〜pve10"]
    D2 -->|"サービスを構築"| VMS["サービスVM群"]
    D3 -->|"マニフェスト適用"| K3S["k3sクラスタ"]
    PVECLUSTER --- VMS
    VMS --- K3S
```

## 使いかた

Vaultパスワードは環境変数 `ANSIBLE_VAULT_PASSWORD_FILE`(Dev Containerが設定)で自動供給される。すべてリポジトリルートで実行する。

```sh
# VMを宣言どおりに収束(テンプレート準備→クローン→設定→cloud-init→起動 まで全部)
ansible-playbook playbooks/pve/provision.yml -l k8s          # 役割ごと
ansible-playbook playbooks/pve/provision.yml -l k3s-worker03 # 1台だけ

# 電源(冪等)
ansible-playbook playbooks/pve/power.yml -l k8s -e state=stopped

# 削除(confirm二重指定が必須。停止中のVM/テンプレートのみ)
ansible-playbook playbooks/pve/destroy.yml -e vmid=991 -e confirm=991

# テンプレートだけ単体で用意する場合
ansible-playbook playbooks/pve/template.yml -e os=debian -e version=13 -e target_node=pve01

# サービスVMの一気通貫構築(①provision + ②SSHセットアップ)
ansible-playbook playbooks/vm/authentik.yml

# Kubernetesアプリの収束(Secretも含めて全部。収束済みなら changed=0)
ansible-playbook playbooks/k8s/deploy.yml --check          # 差分の有無を確認
ansible-playbook playbooks/k8s/deploy.yml                  # 全アプリ
ansible-playbook playbooks/k8s/deploy.yml -e app=portainer # 1アプリだけ
```

### provision が収束させる流れ

```mermaid
sequenceDiagram
    autonumber
    participant A as ansible-playbook<br>(このリポジトリ)
    participant P as Proxmox API<br>(APIトークン認証)
    participant N as 対象ノード<br>(例: pve03)
    participant V as VM

    Note over A,N: プレイ1: テンプレート準備(serial: 1)
    A->>P: テンプレート 9XXNN は存在するか
    alt 無ければ
        P->>N: Cloud imageを直接ダウンロード(checksum検証)
        A->>P: 空VM作成 → ディスク取込 → テンプレート化
    end
    Note over A,V: プレイ2: VM収束
    A->>P: VMが無ければテンプレートからフルクローン
    A->>P: CPU/メモリ/NIC/オプションを宣言値へ(差分がある時だけ)
    A->>P: ディスク拡張(宣言値より小さい時だけ)
    A->>P: cloud-init(ユーザー/鍵/IP/DNS)
    A->>P: 電源を宣言値へ(既定: started)
    P->>V: 起動(cloud-initが初期設定)
```

- 全タスクが**冪等**: 収束済みなら `changed=0`
- テンプレートは **(OS, ノード)ごと** に VMID `9XXNN`(XX=OSカタログ番号, NN=ノード番号)で管理する。全ストレージがノードローカルであり、クロスノードのクローンができないため
- NICの更新時は既存MACアドレスを引き継ぐ(意図しないMAC再生成を防ぐ)

## ディレクトリ構成

```
.
├── ansible.cfg          # リポジトリルート = Ansibleプロジェクトルート
├── inventory/           # ★宣言(単一の真実)
│   ├── hosts.yml        #   全VM: グループ=役割、1VM=3〜5行
│   └── group_vars/      #   all/=ベース、<役割>.yml=プロファイル
├── playbooks/
│   ├── pve/             # ① provision / power / destroy / template
│   ├── vm/              # ② サービスVMの一気通貫構築
│   └── k8s/             # ③ deploy(全アプリ or -e app=X)
├── roles/               # ドメイン別: pve* / vm* / k8s*
├── vault/               # Ansible Vault(全ファイル暗号化済み)
├── collections/         # requirements.yml(AWX互換の標準位置)
├── docs/                # ドキュメント(migration/ に移行の設計・調査記録)
└── .legacy/             # 旧実装のアーカイブ(削除待ち。手順は設計書§7のP2)
```

## 秘匿情報の扱い

- **Ansible側**: `vault/*.yml` は全て `ansible-vault` で暗号化(同一パスワード)。平文の秘密情報・実IP以外のトークン類はコミットしない
- **Kubernetes側**: アプリのSecretも `vault/k8s_secrets.yml`(暗号化済み)に一元化。`deploy.yml` が各アプリのSecretを `no_log` で適用する(--diffでも中身は出ない)
- PVE APIトークンは `vault/proxmox_api.yml`(暗号化済み)の4変数。各playbookが `module_defaults` で全モジュールへ一括供給する

## ドキュメント

| ドキュメント | 内容 |
| --- | --- |
| [docs/pve.md](docs/pve.md) | ① Proxmox操作ドメインの使い方(provision/power/destroy/template) |
| [docs/vm.md](docs/vm.md) | ② VMセットアップドメインの使い方(サービス別playbook・k3sクラスタ構築) |
| [docs/k8s.md](docs/k8s.md) | ③ Kubernetesドメインの使い方(deploy・アプリ追加・Secret・チャート管理) |
| [docs/devcontainer.md](docs/devcontainer.md) | Dev Containerのセットアップ注意点 |
| [docs/migration/phase0-investigation.md](docs/migration/phase0-investigation.md) | 移行前調査(旧SSH方式の棚卸し・モジュールマッピング) |
| [docs/migration/phase1-design.md](docs/migration/phase1-design.md) | 設計書(3層思想・ドメイン構成・実装計画と検証記録) |

> 旧方式(ノードへの直接SSH + 手動kubectl)の実装・ドキュメントは `.legacy/` にアーカイブ済み。Phase 3(新旧比較の最終確認)の完了後に削除する。進捗は設計書の実装計画表を参照。
