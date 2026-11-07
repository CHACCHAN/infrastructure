# inventory

ホストの宣言。唯一の真実の置き場所。VLAN・ID・VMID・IP の規則は [docs/design/network.md](../docs/design/network.md)。

## 構成

| 場所 | 内容 |
| --- | --- |
| `hosts/<VLAN番号>_<名前>.yml` | VLAN ごとに1ファイル。グループの `vlan` と、ホストの `id`・`node` などを書く |
| `group_vars/all/network.yml` | `vlan` と `id` から、VMID・IP・ゲートウェイを導出する |
| `group_vars/all/pve.yml` | Proxmox の API に共通する値 |
| `group_vars/all/ssh.yml` | VM の cloud-init に登録する SSH 公開鍵 |
| `group_vars/all/domain.yml` | ラボのドメイン(`lab_domain`) |
| `group_vars/<グループ>.yml` または `group_vars/<グループ>/*.yml` | グループに共通する値(ロールの既定値との差分だけ) |
| `group_vars/k3s.yml` | k3s の共通値・公開ホスト名・NetworkPolicy・VIP の ID(`k3s_api_vip_id`・`k3s_ingress_vip_id`) |
| `group_vars/litellm.yml` | LiteLLM のサービス設定・モデル・キーの利用範囲。秘密値は置かない。`litellm` グループは `k3s` を子に持つ |
| `group_vars/authentik.yml` | Authentik のサービス設定・OIDC・認証プロキシ・既存アプリの表示設定。`authentik` グループは `k3s` を子に持つ |
| `host_vars/` | 個体差が出たホストだけ |

値の優先順位は [docs/conventions.md](../docs/conventions.md) の「変数の層」。

## ホストを足す

[ネットワーク設計](../docs/design/network.md)の VLAN・ID の規則に従う。ホストが宣言するのは `id`・`node` と、既定値との差分だけ。VMID・IP・ゲートウェイは書かない。

## 確かめる

```sh
ansible-inventory --graph                                        # 警告が出ないこと
ansible k3s01 -c local -m ansible.builtin.debug -a 'var=vmid'    # 導出された値(vmid、ansible_host、gateway)
```

## LiteLLM のモデル設定を編集する

[group_vars/litellm.yml](group_vars/litellm.yml)を編集し、次のコマンドで管理 API の現在値と異なる対象と項目名を確認する。既存モデルの ID は維持する。適用手順と管理できるフィールドは [LiteLLM ロール](../roles/k3s_litellm/README.md)を参照する。

```sh
ansible-playbook playbooks/k3s/litellm_manage.yml --check --diff 2>&1 | cat
```

プロバイダーの API キー・認証ヘッダー・発行済みキーのハッシュと取得記録は Vault に保管する。API の再取得では、このモデル宣言は書き換えない。

Authentik のアプリ設定は [group_vars/authentik.yml](group_vars/authentik.yml)で編集し、`playbooks/k3s/authentik_manage.yml --check --diff` で slug と変更項目名を確認する。OIDC プロバイダーと認証プロキシの接続設定は Blueprint が同じ inventory から読む([手順](../roles/k3s_authentik/README.md))。
