# Vault の整理案

## 現在の扱い

暗号化ファイルは `vault/` 直下でサービスごとに分け、必要な playbook が `vars_files` で明示的に読む([規約](../conventions.md))。LiteLLM の基盤用の秘密と管理 API の取得結果は用途が異なるため、`litellm.yml`・`litellm_keys.yml`・`litellm_snapshot.yml` に分ける。モデルの非機密の宣言は `inventory/group_vars/litellm.yml` で管理する。API の取得結果には秘密を含む可能性のあるヘッダーやメタデータもあるため、取得記録全体を暗号化する。

## 提案: サービスごとのフォルダ

全サービスを移す場合は、サービス名を最上位にし、内部を用途で分ける。インフラ・アプリ・利用者という最上位の分類は、複数の分類にまたがるサービスで保存先が曖昧になるため設けない。

- `service.yml`: DB・暗号化用の鍵・管理 API の認証・緊急用の認証。
- `oidc.yml`: Authentik と共有する OIDC の認証。Authentik の playbook はこのファイルだけを読む。
- `providers.yml`: 上流プロバイダーの認証。実際に Ansible が必要とする場合だけ作る。
- `keys.yml`: 発行済みキーのハッシュ・保存できた秘密・非公開の設定・処理中の操作。公開設定は inventory に置く。
- `snapshot.yml`: API の参照用取得記録。通常適用は読まない。
- `clients.yml`: 発行時に保管できたサービス用キー本体。管理台帳のハッシュと区別する。発行・配布方法を決めるまでは作らない。

サービス固有の用途は、内容が分かる名前にする。k3s の `api.yml`・`cluster.yml`、Cloudflare の `dns.yml`、Authentik の `google.yml`、Nextcloud の `hermes.yml` はその例外で、以下の表を対応表とする。

### 移動先の対応

| 現在 | 提案する保存先 | 参照元・注意点 |
| --- | --- | --- |
| `vault/proxmox.yml` | `vault/proxmox/service.yml` | VM 作成の playbook |
| `vault/proxmox_oidc.yml` | `vault/proxmox/oidc.yml` | Authentik の playbook |
| `vault/k3s.yml` | `vault/k3s/api.yml` と `vault/k3s/cluster.yml` | アプリの適用は API 認証、ノード構築は参加トークンだけ。トークン保存ツールも修正する |
| `vault/cloudflare.yml` | `vault/cloudflare/dns.yml` | cert-manager の DNS 用の権限 |
| `vault/cloudflared.yml` | `vault/cloudflared/service.yml` | Tunnel のコネクタ |
| `vault/authentik.yml` | `vault/authentik/service.yml` と `vault/authentik/google.yml` | Google の OAuth と基盤の秘密を分ける |
| `vault/openwebui.yml` | `vault/openwebui/service.yml` と `vault/openwebui/oidc.yml` | Authentik は OIDC だけを読む |
| `vault/litellm.yml` | `vault/litellm/service.yml`・`oidc.yml`・必要なら `providers.yml` | 管理 API は service、Authentik は oidc、Helm は必要な用途だけを読む |
| `vault/litellm_keys.yml` | `vault/litellm/keys.yml` | 通常のキー設定適用と、確認値を要求するキー操作 |
| `vault/litellm_snapshot.yml` | `vault/litellm/snapshot.yml` | 取得記録だけ。宣言とキー台帳は変更しない |
| `vault/authentik_snapshot.yml` | `vault/authentik/snapshot.yml` | アプリの取得記録だけ |
| `vault/cliproxy.yml` | `vault/cliproxy/service.yml` | 管理認証と API キー初期値。稼働中の設定を初期値で上書きしない |
| `vault/nextcloud.yml` | `vault/nextcloud/service.yml` と `vault/nextcloud/oidc.yml` | Authentik は OIDC だけを読む |
| `vault/nextcloud_hermes.yml` | `vault/nextcloud/hermes.yml` | Hermes 専用ユーザーの認証とアプリパスワード |
| `vault/gravitee.yml` | `vault/gravitee/service.yml` と `vault/gravitee/oidc.yml` | AM の OIDC クライアントとの共有値を分ける |
| `vault/gravitee_am.yml` | `vault/gravitee_am/service.yml` と `vault/gravitee_am/oidc.yml` | Authentik は OIDC だけを読む |
| `vault/hermes.yml` | `vault/hermes/oidc.yml` | Authentik の playbook |
| `vault/opnsense.yml` | `vault/opnsense/oidc.yml` | Authentik の playbook |
| `vault/ssh.yml` | `vault/ssh/service.yml` | VM 構築と SSH を使う単発ツール |

変数名は既存の `vault_<サービス>_<用途>` を保ち、移動と変数名変更を同時に行わない。分割したファイルのパスは省略せず、playbook に列挙する。全ファイルを glob で読む処理は設けない。

### 移行手順

1. 参照元を `rg` で列挙する。`vars_files` のほか、トークン保存ツールの書き込み先、ロールの既定値・引数説明、README、設計文書も対象にする。
2. `.gitattributes` の `vault/*.yml` を再帰的な配置に対応させ、移動先でも `-text -diff -merge` が付くことを `git check-attr` で確認する。
3. 単純な移動は暗号文のまま行う。用途別の分割だけメモリ上で復号・分離・再暗号化し、秘密値を画面や平文ファイルへ出さない。同じ変数を複数の保存先へ複製しない。
4. 読み書きの参照元を同じ変更で更新し、旧パスへの参照が残らないことを確認する。旧ファイルとの二重管理やシンボリックリンクは使わない。
5. 移行前後で変数名と値が一致することを、秘密を表示せずに比較する。lint・構文・インベントリ・相対リンクを検証する。パス変更の確認だけのために実機へ適用しない。

## 未決

- 上記のフォルダ移動と用途別分割を実施する時期。ここでは配置と手順の提案にとどめ、現在のパスを保つ。
- LiteLLM の利用サービスへのキー配布の自動化。発行・利用停止・再開・ローテーションは明示的な操作に分離し、秘密は API 更新より前に台帳へ保存する。既存キーのハッシュからキー本体は復元できない。Gravitee の利用者向けキーはポータル発行を保つ([k3s 設計](k3s.md))。
- 上流プロバイダーの秘密を Ansible へ取り込む範囲。OAuth の認証状態とDB全体は、この整理だけで再現できない。
