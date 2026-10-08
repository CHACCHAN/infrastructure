# vault

Ansible Vault で暗号化した秘密情報。規則は [docs/conventions.md](../docs/conventions.md) の「秘密情報」。**平文の秘密を、チャット・ログ・コミットに出さない。**

## ファイル

| ファイル | 変数 | 使う playbook |
| --- | --- | --- |
| `proxmox.yml` | `vault_proxmox_token_id`(`user@realm!name` の形)、`vault_proxmox_token_secret` | `playbooks/pve/` の `template.yml`・`provision.yml` |

ファイル名はサービス名、変数名は `vault_<サービス>_<用途>`。

## 使い方

- 必要な playbook だけが `vars_files` で読み込む。`group_vars` には置かない。
- 編集は `ansible-vault edit vault/<ファイル>.yml`。パスワードは `ANSIBLE_VAULT_PASSWORD_FILE` が指すファイル。
- パスワードは、開発マシン以外にも控えを持つ。失うと復号できない。
- 競合は、テキストをマージせず、再暗号化で解消する(`.gitattributes` で `-text -diff -merge`)。
