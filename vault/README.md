# Vault(暗号化された秘密情報)

このディレクトリのYAMLはすべて `ansible-vault` で暗号化されています。
**すべて同じVaultパスワードで暗号化してください**(playbookが複数ファイルを同時に読むため)。

| ファイル | 内容 | 使うplaybook |
| --- | --- | --- |
| `proxmox.yml` | Proxmoxホストへの接続パスワード(`vault_proxmox_ssh_password`) | `playbooks/proxmox/` と `playbooks/services/` の全playbook |
| `proxmox_api.yml` | Proxmox VE APIトークン認証の4変数(`vault_proxmox_api_host` / `vault_proxmox_api_user` / `vault_proxmox_api_token_id` / `vault_proxmox_api_token_secret`) | community.proxmox モジュール移行後の `playbooks/proxmox/` (Phase 2以降) |
| `supabase.yml` | Supabaseダッシュボードのログインパスワード | `playbooks/services/supabase.yml` |
| `cloudflare.yml` | Cloudflare APIトークン | `playbooks/services/cloudflare-ddns-ui.yml` |
| `wg-easy.yml` | wg-easyの管理者パスワード等 | `playbooks/services/wg-easy.yml` |

## コマンドリスト

- 暗号化: `ansible-vault encrypt vault/<ファイル名>.yml`
- 編集: `ansible-vault edit vault/<ファイル名>.yml`
- 確認: `ansible-vault view vault/<ファイル名>.yml`

実行時は `--ask-vault-pass`(またはAWXのVaultクレデンシャル)で復号します。
