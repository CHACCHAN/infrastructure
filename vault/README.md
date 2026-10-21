# vault

Ansible Vault で暗号化した秘密情報。規則は [docs/conventions.md](../docs/conventions.md) の「秘密情報」。**平文の秘密を、チャット・ログ・コミットに出さない。**

## ファイル

| ファイル | 変数 | 使う playbook |
| --- | --- | --- |
| `proxmox.yml` | `vault_proxmox_token_id`(`user@realm!name` の形)、`vault_proxmox_token_secret` | `playbooks/pve/provision.yml` |
| `k3s.yml` | `vault_k3s_api_token`(ServiceAccount のトークン)、`vault_k3s_ca_cert`(API の認証局の証明書)、`vault_k3s_cluster_token`(サーバーの参加に使うクラスタのトークン) | `playbooks/k3s/`(作成は `playbooks/utils/k3s_token.yml`)、`playbooks/utils/homarr_admin.yml`、`playbooks/vm/k3s.yml`(クラスタのトークンの作成は `playbooks/utils/k3s_cluster_token.yml`) |
| `cloudflare.yml` | `vault_cloudflare_api_token`(対象ゾーンの DNS の編集とゾーンの読み取りだけを許可した API トークン) | `playbooks/k3s/cert_manager.yml` |
| `cloudflared.yml` | `vault_cloudflared_tunnel_token`(Cloudflare の画面で作った Tunnel のトークン) | `playbooks/k3s/cloudflared.yml` |
| `postgresql.yml` | `vault_postgresql_passwords`(DB 名をキーにしたロールのパスワードの辞書) | `playbooks/k3s/postgresql.yml`、DB を使うアプリの playbook(`authentik.yml`・`homarr.yml`・`openwebui.yml`・`litellm.yml`) |
| `authentik.yml` | `vault_authentik_secret_key`、`vault_authentik_bootstrap_password`(緊急用の `akadmin`)、`vault_authentik_bootstrap_token`、`vault_authentik_google_client_id`・`vault_authentik_google_client_secret`(Google でのログインに使う OAuth クライアントの client_id と client_secret) | `playbooks/k3s/authentik.yml` |
| `homarr.yml` | `vault_homarr_oidc_client_secret`、`vault_homarr_db_encryption_key`、`vault_homarr_admin_password`(緊急用の `admin`) | `playbooks/k3s/homarr.yml`、`authentik.yml`、`playbooks/utils/homarr_admin.yml` |
| `openwebui.yml` | `vault_openwebui_oidc_client_secret`、`vault_openwebui_secret_key`、`vault_openwebui_admin_password`(緊急用の管理者) | `playbooks/k3s/openwebui.yml`、`authentik.yml` |
| `litellm.yml` | `vault_litellm_master_key`(API の鍵)、`vault_litellm_salt_key`(DB に保存する認証情報の暗号化キー)、`vault_litellm_oidc_client_secret`、`vault_litellm_ui_password`(緊急用の `admin`)、`vault_litellm_provider_keys`(プロバイダーの API キーの辞書) | `playbooks/k3s/litellm.yml`、`authentik.yml` |
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
