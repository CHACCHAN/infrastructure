# 単発ツール(utils)ドメイン

`playbooks/utils/` は**単発で叩く実用ツール集**(Ansibleにおけるシェルスクリプト集に相当)。①②③のインフラドメインとは責務を分けており、**構成管理(宣言の収束)ではなく、必要なときに1回実行する操作**を置く。

| このディレクトリに置くもの | 置かないもの |
| --- | --- |
| API操作・問い合わせ・単発のメンテナンス作業 | VMやk8sの宣言的な構築(①②③へ) |
| 冪等でも「宣言の一部」ではない操作 | 他playbookの前処理(pve/adhoc.yml、vm/ssh_key.ymlの類) |

## playbook一覧

| playbook | ドキュメント | 内容 | 使うvault |
| --- | --- | --- | --- |
| `awx_job_launch.yml` | [awx_job_launch.md](awx_job_launch.md) | AWXのJob Templateを名前指定で起動(既定で完了待ち) | `awx_api.yml` |
| `awx_job_status.yml` | [awx_job_status.md](awx_job_status.md) | AWXのJobの状況取得(オプションで完了待ち) | `awx_api.yml` |
| `awx_inventory_sync.yml` | [awx_inventory_sync.md](awx_inventory_sync.md) | Inventory Source(project-inventory)の同期 | `awx_api.yml` |
| `authentik_users.yml` | [authentik_users.md](authentik_users.md) | Authentikユーザー作成(単一/一括)+グループ所属(冪等) | `authentik.yml` |

## 共通の前提

- すべて **localhost実行**(SSH不要)。リポジトリルートから `ansible-playbook playbooks/utils/<name>.yml` で実行する
- vaultの復号は他playbookと同じ(Dev Containerでは `ANSIBLE_VAULT_PASSWORD_FILE` で自動)
- **`--check` には対応しない**(API呼び出しのみのため。実行前assertで明示的に止まる)
- AWXからも実行できる(Job Template `utils-*`。定義は [awx/job_templates.yml](../../awx/job_templates.yml)、前提は [docs/awx/README.md](../awx/README.md))

## 必要なvault変数

| ファイル | 変数 | 内容 |
| --- | --- | --- |
| `vault/awx_api.yml` | `vault_awx_host` / `vault_awx_oauthtoken` | AWXのURLとOAuthトークン(configure.ymlと共用) |
| `vault/authentik.yml` | `vault_authentik_host` | AuthentikのURL(例 `https://auth.cc-chacchan.com`) |
| | `vault_authentik_api_token` | APIトークン(Directory → Tokens で intent=API を発行) |

編集は `ansible-vault edit vault/<ファイル>.yml`(全ファイル同一パスワード。[vault/README.md](../../vault/README.md))。
