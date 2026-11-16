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

Hermes VM の組織名や役割は Hermes 側で管理し、インベントリには記録しない。

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

FreeHub の NVIDIA の無料 API モデルと Mistral のサブスクリプションモデルは CLIProxy 経由で接続する。公開モデル名には NVIDIA の無料 API モデルは NVIDIA 自社モデルを除いて `-free` を付け、Mistral のサブスクリプションモデルには付けない。同じモデルを指す重複エイリアスは集約し、接続確認のタイムアウトだけでは登録対象から除外しない。プレビュー・Playground のみで API が提供されないモデルは対象外とする。互換性がある場合は開発元の LiteLLM プロバイダー、それ以外は Custom OpenAI を使う。接続先が開発元と異なる応答形式を返す場合は、その形式に対応するプロバイダーを使う。モデルの作成と認証情報の登録は管理 UI/API で済ませてから、既存モデルの ID を inventory に追加する。`playbooks/k3s/litellm_manage.yml` は既存モデルの更新だけを行い、モデルを作成しない。

Google AI Studio の無料枠 Gemini 接続は公開しない。CLIProxy 経由の短名の Gemini モデル登録は維持する。

公開名に空白を含むプロバイダー名付きの長名モデル登録と、それを参照する旧ルーティンググループは公開しない。参照先のモデルが存在しない旧グループも残さない。Claude 系を含め、短名のモデル登録は維持する。

`cc-` 系のルーティンググループは短名のモデルを参照し、判定用の `cc-judge`・`cc-max-judge` を含め、Gemini を振り分け先に含めない。`cc-simple` は `nemotron-3.5-super-vl` だけを使う。`cc-reasoning`・`cc-max-complex` は `gpt-6.1-terra` と `kimi-k3.1-pro`、`cc-max-reasoning` は `gpt-6.1-sol` と `claude-sonnet-5.5` を使う。利用枠の上限や障害時は既存の段階間フォールバックを使う。

`HermesAgent`(`client_02`) の仮想キーは、Web UI の実態に合わせて `all-proxy-models` を許可している。全プロキシモデルを利用できるため、想定外のモデルや高コスト・高消費枠のモデルへ到達し得るリスクがある。

プロバイダーの API キー・認証ヘッダー・発行済みキーのハッシュと取得記録は Vault に保管する。API の再取得では、このモデル宣言は書き換えない。

Authentik のアプリ設定は [group_vars/authentik.yml](group_vars/authentik.yml)で編集し、`playbooks/k3s/authentik_manage.yml --check --diff` で slug と変更項目名を確認する。OIDC プロバイダーと認証プロキシの接続設定は Blueprint が同じ inventory から読む([手順](../roles/k3s_authentik/README.md))。
