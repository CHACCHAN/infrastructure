# ② VMセットアップドメイン(vm)

VMの**中身**(OS設定・Docker・サービス)をSSHで収束させるドメイン。1サービス=1playbookで、①pveドメインのprovisionを先頭でimportするため、**インベントリの宣言から稼働中サービスまで一気通貫**で構築できる。

## 全体像

```mermaid
flowchart TB
    subgraph PB["playbooks/vm/&lt;service&gt;.yml"]
        P1["プレイ1: ../pve/provision.yml をimport<br>(テンプレ→クローン→cloud-init→起動)"]
        P2["プレイ2: SSHでセットアップ<br>接続待ち→ファクト収集→ロール適用→再起動"]
        P1 --> P2
    end
    subgraph ロール["roles/(ベース→カスタマイズ→実装)"]
        SVC["vm_&lt;service&gt;(実装)<br>wg_easy / authentik / k3s …"]
        BASE["vm(共通ベース)<br>apt更新・TZ/ロケール・zram<br>基本パッケージ・ゲストエージェント"]
        DOCKER["vm_docker(部品)<br>Docker CE + compose配置"]
        SVC --> BASE
        SVC -.Docker系のみ.-> DOCKER
    end
    P2 --> SVC
    宣言["inventory/group_vars/&lt;role&gt;.yml<br>VMプロファイル + SSH接続 + サービス設定"] --> PB
```

## コマンド

```sh
# 宣言から一気通貫で構築(既存VMなら差分適用のみ)
ansible-playbook playbooks/vm/wg-easy.yml
ansible-playbook playbooks/vm/authentik.yml
ansible-playbook playbooks/vm/k3s.yml        # k8sグループ全台を順にクラスタ化

# 1台だけに絞る(グループ内の特定ホスト)
ansible-playbook playbooks/vm/dev.yml -l yuya-dev

# 仕上げの再起動を抑止する(稼働中サービスの設定だけ直したいとき)
ansible-playbook playbooks/vm/wg-easy.yml -e vm_reboot_after_setup=false
```

playbookは8本: `authentik` `ddns` `dev` `k3s` `pbs` `supabase` `technitium` `wg-easy`

## サービスの宣言のしかた

役割グループの `inventory/group_vars/<role>.yml` に3種類の変数をまとめる。

```yaml
# inventory/group_vars/wg_easy.yml
# --- ① VMプロファイル(pveドメインが使う) ---
pve_vm_cores: 2
pve_vm_memory: 512
pve_vm_disk_size: 8

# --- ② SSH接続(cloud-initが作るユーザーと鍵) ---
pve_ssh_user: wg
pve_ssh_pubkey_file: ~/.ssh/id_ed25519_wg_easy.pub
pve_ssh_prikey: ~/.ssh/id_ed25519_wg_easy

# --- ③ サービス設定(vm_<service>ロールが使う) ---
wg_easy_init_host: wg.example.com
wg_easy_version: "15.4.0-beta.1"
```

- SSH接続は **provisionがcloud-initに書き込んだユーザー・鍵をそのまま使う**ため、宣言が一致していれば必ず入れる
- 秘密情報(APIトークン等)は平文で置かず `vault/` の暗号化ファイルに置く

## k3sだけの特別ルール

`playbooks/vm/k3s.yml` はクラスタを組むため順序が意味を持つ。

- **`k8s` グループの先頭ホスト=コントロールプレーン**、以降はワーカーとして参加する
- `order: inventory` + `serial: 1` で宣言順に1台ずつ処理する(ワーカーは先行するコントロールプレーンから参加トークンを取得するため)
- ワーカー追加は「`inventory/hosts.yml` の `k8s` グループ末尾にホストを足して再実行」するだけ

```mermaid
sequenceDiagram
    participant A as ansible(実行元)
    participant M as k3s-master01(先頭)
    participant W as k3s-worker0N(後続)
    A->>M: provision(①) → SSHでk3sサーバー構築
    A->>W: provision(①)
    W->>M: 参加トークンを取得(管理ネットワーク経由)
    A->>W: k3sエージェントとしてクラスタ参加(占有ネットワーク)
```

- SSHは管理ネットワーク(172.16.x)、k3s API・ノード間通信は占有ネットワーク(`cluster_ip`)を使う

## 設計メモ(なぜこうなっているか)

- **`gather_facts: false` + SSH到達後に明示的な `setup`**: プレイ冒頭の自動ファクト収集は `pre_tasks` の接続待ちより**先に**走るため、作りたてのVMでは必ず失敗する。全playbookで接続待ち→収集の順を明示している
- **ホスト鍵を検証しない**: cloud-init直後はVMのホスト鍵が毎回変わるため `StrictHostKeyChecking=no`。管理ネットワーク内での運用が前提
- **最後に必ず再起動**: dockerグループ追加・カーネル更新の反映のため。`restart: unless-stopped` のコンテナは自動復帰する
- **`vm_ssh_user` / `vm_ip`**: 旧ロール群が参照する変数名への橋渡し(playbook側で `pve_ssh_user` / `ansible_host` から供給)。ロール側の正規化は今後の課題

## トラブルシューティング

| 症状 | 原因と対処 |
| --- | --- |
| `SSH接続を待つ` でタイムアウト(既定600秒) | VMが起動しきっていないか、cloud-initのIP設定と `ansible_host` の不一致。PVE UIのコンソールでゲストの状態を確認 |
| `Permission denied (publickey)` | `pve_ssh_user` / `pve_ssh_pubkey_file` と実VMのcloud-init設定がずれている。`playbooks/pve/provision.yml` を流して収束させてから再実行 |
| セットアップ途中で `No route to host` | ゲストのネットワーク断か再起動中。少し待って同じplaybookを再実行(冪等なので途中からやり直せる) |
| k3sワーカーが参加に失敗 | コントロールプレーン(グループ先頭)が未構築のまま後続だけ実行した。グループ全体で `playbooks/vm/k3s.yml` を再実行 |
