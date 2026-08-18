# Vault(暗号化された秘密情報)

このディレクトリのYAMLはすべて `ansible-vault` で暗号化されています。
**すべて同じVaultパスワードで暗号化してください**(playbookが複数ファイルを同時に読むため)。

| ファイル | 内容 | 使うplaybook |
| --- | --- | --- |
| `proxmox_api.yml` | Proxmox VE APIトークン認証の4変数(`vault_proxmox_api_host` / `vault_proxmox_api_user` / `vault_proxmox_api_token_id` / `vault_proxmox_api_token_secret`) | `playbooks/pve/`(①。②のprovision部も) |
| `k8s_secrets.yml` | k8sアプリのSecret実値(`k8s_secret_<Secret名スネークケース>`)と、オペレータ生成物のバックアップ(`k8s_backup_*`) | `playbooks/k8s/deploy.yml`(③) |
| `supabase.yml` | Supabaseダッシュボードのログインパスワード | `playbooks/vm/supabase.yml` |
| `cloudflare.yml` | Cloudflare APIトークン | `playbooks/vm/ddns.yml` |
| `wg-easy.yml` | wg-easyの管理者パスワード等 | `playbooks/vm/wg-easy.yml` |
| `awx_api.yml` | AWXのURL・OAuthトークン・Project同期用SSH鍵(`vault_awx_host` / `vault_awx_oauthtoken` / `vault_awx_scm_prikey`) | `playbooks/awx/configure.yml` |

> **注意**: `k8s_secrets.yml` 内のSecretの**内部キー名**は、pgadminだけ大文字スネークケース(`PGADMIN_OAUTH2_CLIENT_ID` 等)で書く。pgadminはチャートの `envVarsFromSecrets`(キー名がそのまま環境変数名になる)方式のため。他アプリは `db-password` のようなケバブケース + マニフェスト側の `secretKeyRef.key` 明示。

## コマンドリスト

- 暗号化: `ansible-vault encrypt vault/<ファイル名>.yml`
- 編集: `ansible-vault edit vault/<ファイル名>.yml`
- 確認: `ansible-vault view vault/<ファイル名>.yml`

Dev Containerでは `ANSIBLE_VAULT_PASSWORD_FILE` が設定されるため復号は自動。それ以外では `--ask-vault-pass`(またはAWXのVaultクレデンシャル)で復号します。
