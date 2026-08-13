# authentik.yml
起動済みのVMに [Authentik](https://goauthentik.io/)(SSO/IdP)をDocker Composeで構築します。
完了時点で他の端末のブラウザからWebUIに接続できる状態になります。

接続情報と共通オプションは [README](../README.md#全playbook共通の指定) を参照してください。

```sh
ansible-playbook playbooks/vms/authentik.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名>"

# 初期管理者のパスワードまで一度に決める場合
ansible-playbook playbooks/vms/authentik.yml -vv \
-e "vm_ip=192.168.10.60 vm_ssh_user=authentik vm_ssh_prikey=~/.ssh/id_ed25519 \
    authentik_bootstrap_password=<パスワード> authentik_bootstrap_email=<メールアドレス>"
```

`development.yml` と違い、CockpitやGUI・開発ツールは導入しません(Authentik専用VMのため)。

## 必要なスペック
| 項目 | 必要量 |
| --- | --- |
| CPU / RAM | 2コア / 4GB以上(公式の最小構成。下回るとOOMになります) |
| ディスク | **32GB以上を推奨**。イメージだけで展開後あわせて約1.5GiB(server 約1GiB + postgres 約0.3GiB)使います |

実行の冒頭で空き容量を確認し、5GiB未満なら**イメージの取得を始める前に中止**します
(`authentik_min_free_disk_gb` で変更可)。
Debianのcloud imageテンプレートは素のままだと約3GBしかないため、
`proxmox/` から構築する場合は `vm_hardware` の `resize` を必ず指定してください。

## 指定できる項目
共通オプションに加えて以下を指定できます。**すべて任意です。**

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `authentik_install_dir` | `/opt/authentik` | 設置先 |
| `authentik_version` | `2026.5.6` | イメージタグ |
| `authentik_image` | `ghcr.io/goauthentik/server` | イメージ名 |
| `authentik_postgres_image` | `docker.io/library/postgres:16-alpine` | PostgreSQLのイメージ |
| `authentik_http_port` | `9000` | WebUI(HTTP)の公開ポート |
| `authentik_https_port` | `9443` | WebUI(HTTPS)の公開ポート |
| `authentik_pg_db` / `authentik_pg_user` | `authentik` | データベース名 / ユーザー名 |
| `authentik_pg_password` | 自動生成 | データベースのパスワード |
| `authentik_secret_key` | 自動生成 | セッション・トークンの署名鍵 |
| `authentik_bootstrap_password` | (未設定) | 初期管理者`akadmin`のパスワード(**初回のみ有効**) |
| `authentik_bootstrap_email` | (未設定) | 初期管理者のメールアドレス(**初回のみ有効**) |
| `authentik_bootstrap_token` | (未設定) | 初期管理者のAPIトークン(**初回のみ有効**) |
| `authentik_error_reporting` | `false` | エラー情報をauthentik側へ送信するか |
| `authentik_min_free_disk_gb` | `5` | イメージ取得前に必要な空き容量(GiB) |
| `authentik_extra_env` | `{}` | 上に無い環境変数を `.env` に足す(例: SMTP設定の `AUTHENTIK_EMAIL__*`) |
| `authentik_ready_retries` / `_delay` | `60` / `10` | WebUI起動待ちのリトライ回数 / 間隔(秒) |

パスワード類を手動指定する場合は**16文字以上の英数字と `_` `.` `-` のみ**にしてください
(`.env`に書き出すため。実行前に検証してエラーにします)。

## 実施する内容
1. OS確認、変数の検証、**ディスクの空き容量の確認**
2. [全VM共通のセットアップ](../README.md#共通セットアップtasks)(OS更新、タイムゾーン、
   ロケール、zram、sudoグループ、基本パッケージ、QEMUエージェント、Docker)
3. `/opt/authentik` 配下の作成 → `.env` 生成 → `docker compose up -d`
4. ufwが導入済みかつ有効な場合のみWebUIのポートを開放(通常はスキップ)
5. VM内からWebUIの応答を確認 → VM再起動 → **実行元の端末から接続できることを確認**

## 初期セットアップ(初回のみ)
```
http://<VMのIPアドレス>:9000/if/flow/initial-setup/
```
`authentik_bootstrap_password` を指定していた場合は、この画面を経由せず
`akadmin` でログインできます。
HTTPS(`https://<IP>:9443/`)は自己署名証明書のため警告が出ます。

## 構成されるもの
公式の `docker-compose.yml` と同じ構成です。

| サービス | 内容 |
| --- | --- |
| `server` | WebUI/APIの本体 |
| `worker` | 証明書生成・メール送信・ブループリント適用など |
| `postgresql` | データベース(名前付きボリューム `authentik_database`) |

**Redisのコンテナはありません**(2026.x系は不要になったため)。
`authentik_version` に2025.x以前のタグを指定すると起動しません。

| パス | 内容 |
| --- | --- |
| `/opt/authentik/docker-compose.yml` | Compose定義(Ansibleが生成。手動編集は上書きされます) |
| `/opt/authentik/.env` | パスワード・シークレットキー・ポート(root所有・`0640`・dockerグループのみ読み取り可) |
| `/opt/authentik/data` `certs` `custom-templates` | データ / 証明書 / テンプレート差し替え用 |

## パスワード・シークレットキーの扱い
`-e の指定` > `既存の.env` > `自動生成` の順で決まります。
シークレットキーを変えると既存セッションが無効になり、DBパスワードを変えると
初期化済みDBに接続できなくなるため、**再実行時は必ず既存の値が引き継がれます**。

秘密情報を扱うタスクは `no_log` で出力を抑止しているため、失敗しても詳細が出ません。
切り分けが必要なときは `roles/authentik/tasks/configure_env.yml` の `no_log` を外してください。

## 運用
```sh
cd /opt/authentik
docker compose ps
docker compose logs -f server
curl -i http://localhost:9000/-/health/ready/   # 204で準備完了
```

### バージョンアップ
`authentik_version` を指定して再実行するとイメージを取得してコンテナを作り直します
(データは残ります)。**事前にバックアップを取り**、飛び級は避けてリリースノートを確認してください。

### バックアップ
以下の3点が揃わないと復旧できません。

| 対象 | 内容 |
| --- | --- |
| `/opt/authentik/.env` | シークレットキーとDBパスワード |
| dockerボリューム `authentik_database` | PostgreSQLのデータ本体 |
| `/opt/authentik/data`・`certs` | メディア・証明書 |

```sh
cd /opt/authentik
docker compose exec -T postgresql pg_dump -U authentik authentik > authentik-$(date +%F).sql
```

## 再実行について
何度実行しても同じ状態になります。`.env` と `docker-compose.yml` が変わらなければ
コンテナは作り直されず、既存のデータベース・設定も消えません。

## うまくいかないとき
| 症状 | 確認すること |
| --- | --- |
| 「空き容量が足りません」で止まる | `df -h /` と `lsblk`。**ディスクが3GB程度**ならテンプレート素のまま(`vm_hardware` の `resize` 漏れ)。**ディスクは大きいのにFSが小さい**なら、拡張後にVMを再起動すればgrowpartが広げます |
| `no space left on device` | 上と同じ原因。残ったレイヤは `sudo docker system prune -af` で掃除してから再実行 |
| WebUIの起動待ちでタイムアウト | `docker compose logs server`。初回は数分かかります。メモリ4GB未満でも起動しません |
| 実行元の端末からだけ繋がらない | VM内で `curl http://localhost:9000/-/health/ready/`。通るならVM外のネットワーク側の問題 |
| ポートを変えたい | `-e "authentik_http_port=8080 authentik_https_port=8443"` |
