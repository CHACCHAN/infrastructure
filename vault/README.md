# vault

Ansible Vault で暗号化した秘密情報。規則は [docs/conventions.md](../docs/conventions.md) の「秘密情報」。**平文の秘密を、チャット・ログ・コミットに出さない。**

## ファイル

| ファイル | 変数 | 使う playbook |
| --- | --- | --- |
| `proxmox.yml` | `vault_proxmox_token_id`(`user@realm!name` の形)、`vault_proxmox_token_secret` | `playbooks/pve/provision.yml` |
| `proxmox_oidc.yml` | `vault_proxmox_oidc_client_secret`(Proxmox の OpenID のレルムの OIDC クライアントのシークレット。Proxmox 側の設定にも同じ値を入れる。API トークンを Authentik の playbook に渡さないよう、`proxmox.yml` と分ける) | `playbooks/k3s/authentik.yml` |
| `k3s.yml` | `vault_k3s_api_token`(ServiceAccount のトークン)、`vault_k3s_ca_cert`(API の認証局の証明書)、`vault_k3s_cluster_token`(サーバーの参加に使うクラスタのトークン) | `playbooks/k3s/`(作成は `playbooks/utils/k3s_token.yml`)、`playbooks/vm/k3s.yml`(クラスタのトークンの作成は `playbooks/utils/k3s_cluster_token.yml`) |
| `cloudflare.yml` | `vault_cloudflare_api_token`(対象ゾーンの DNS の編集とゾーンの読み取りだけを許可した API トークン) | `playbooks/k3s/cert_manager.yml` |
| `cloudflared.yml` | `vault_cloudflared_tunnel_token`(Cloudflare の画面で作った Tunnel のトークン) | `playbooks/k3s/cloudflared.yml` |
| `authentik.yml` | `vault_authentik_secret_key`、`vault_authentik_db_password`(専用の PostgreSQL の、DB の所有者のロールのパスワード)、`vault_authentik_bootstrap_password`(緊急用の `akadmin`)、`vault_authentik_bootstrap_token`、`vault_authentik_google_client_id`・`vault_authentik_google_client_secret`(Google でのログインに使う OAuth クライアントの client_id と client_secret) | `playbooks/k3s/authentik.yml` |
| `openwebui.yml` | `vault_openwebui_db_password`(専用の PostgreSQL の、DB の所有者のロールのパスワード)、`vault_openwebui_oidc_client_secret`、`vault_openwebui_secret_key`、`vault_openwebui_admin_password`(緊急用の管理者) | `playbooks/k3s/openwebui.yml`、`authentik.yml` |
| `litellm.yml` | `vault_litellm_db_password`(専用の PostgreSQL の、DB の所有者のロールのパスワード)、`vault_litellm_master_key`(API の鍵)、`vault_litellm_salt_key`(DB に保存する認証情報の暗号化キー)、`vault_litellm_oidc_client_secret`、`vault_litellm_ui_password`(緊急用の `admin`)、`vault_litellm_provider_keys`(プロバイダーの API キーの辞書) | `playbooks/k3s/litellm.yml`、`authentik.yml` |
| `cliproxy.yml` | `vault_cliproxy_management_password`(管理画面と管理 API の管理キー)、`vault_cliproxy_api_keys`(API のクライアントの鍵の初期値。設定ファイルが無いときだけ使われる) | `playbooks/k3s/cliproxy.yml` |
| `nextcloud.yml` | `vault_nextcloud_db_password`(専用の PostgreSQL の、DB の所有者のロールのパスワード)、`vault_nextcloud_oidc_client_secret`(Nextcloud の OIDC クライアントのシークレット。Nextcloud の画面の `user_oidc` の設定にも同じ値を入れる)、`vault_nextcloud_admin_password`(緊急用の `admin`) | `playbooks/k3s/nextcloud.yml`、`authentik.yml` |
| `nextcloud_hermes.yml` | `vault_nextcloud_hermes_agent_password`(Hermes の専用のユーザー `hermes-agent` のログインのパスワード。Hermes には渡さない)、`vault_nextcloud_hermes_agent_mcp_auth`(`hermes-agent:<アプリパスワード>` の base64。Hermes の MCP の設定に入れる) | なし(控え。[docs/design/hermes.md](../docs/design/hermes.md)) |
| `hermes.yml` | `vault_hermes_oidc_client_secret`(Hermes の管理画面の OIDC クライアントのシークレット。Hermes 側の設定にも同じ値を入れる) | `playbooks/k3s/authentik.yml` |
| `opnsense.yml` | `vault_opnsense_oidc_client_secret`(OPNsense の管理画面の OIDC クライアントのシークレット。OPNsense 側の設定にも同じ値を入れる) | `playbooks/k3s/authentik.yml` |
| `ssh.yml` | `vault_ssh_private_key`(ラボ専用の SSH 秘密鍵。対の公開鍵は `inventory/group_vars/all/ssh.yml`) | `playbooks/vm/`、`playbooks/utils/k3s_token.yml` |

ファイル名はサービス名、変数名は `vault_<サービス>_<用途>`。

## 緊急用のユーザー

各アプリには、Authentik が使えないときのための、パスワードでログインする管理者を1つずつ残す(設計は [docs/design/k3s.md](../docs/design/k3s.md))。パスワードは機械的に作った 24〜32 文字の英数字で、ここにだけ置く。確認は `ansible-vault view vault/<ファイル>.yml` で行う。

## 使い方

- 必要な playbook だけが `vars_files` で読み込む。`group_vars` には置かない。
- 編集は `ansible-vault edit vault/<ファイル>.yml`。パスワードは `ANSIBLE_VAULT_PASSWORD_FILE` が指すファイル。
- パスワードは、開発マシン以外にも控えを持つ。失うと復号できない。
- 競合は、テキストをマージせず、再暗号化で解消する(`.gitattributes` で `-text -diff -merge`)。
