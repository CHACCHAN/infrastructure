# supabase.yml
起動済みのVMに [Supabase](https://supabase.com/docs/guides/self-hosting/docker) を
セルフホスト構成(Docker Compose)で構築します。Postgres・API(PostgREST)・認証(GoTrue)・
Storage・Realtime・Edge Functions・ダッシュボード(Studio)が一式入ります。

接続情報と共通オプションは [README](../README.md#全playbook共通の指定) を参照してください。

```sh
# 最小(パスワードとAPIキーは自動生成されます)
ansible-playbook playbooks/vms/supabase.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名>"

# 公開URLを指定する(リバースプロキシ経由で使う場合)
ansible-playbook playbooks/vms/supabase.yml -vv \
-e "vm_ip=172.16.11.6 vm_ssh_user=supabase vm_ssh_prikey=~/.ssh/id_ed25519_supabase \
    supabase_public_url=https://supabase.example.com \
    supabase_site_url=https://app.example.com"
```

- **compose定義・Kongの設定・DBの初期化SQLは公式のものをそのまま使います。**
  Ansibleが管理するのは `.env`(環境変数)だけです
- パスワードとAPIキーは未指定なら**公式スクリプト**(`utils/generate-keys.sh`)で生成し、
  `.env` に保存します。**再実行では作り直しません**(DBの中身と対になっているため)
- ⚠ **ダッシュボードはBasic認証のみ**、**Postgresもポートを公開**します。
  LAN内に閉じるか、リバースプロキシ側で保護してください

## 必要なスペック
**Debian(cloud image)のVM専用**です。他のディストリビューションでは実行前に停止します。

| 項目 | 必要量 |
| --- | --- |
| CPU / RAM | **2コア / 4GB以上**(4コア / 8GB推奨)。11個のコンテナが常駐します |
| ディスク | **40GB以上を推奨**。イメージだけで数GiB、残りはDBとStorageの実データです |

イメージ取得の前にVM内の空き容量を確認し、足りなければ中止します
(既定 `supabase_min_free_disk_gb: 15`)。

## 構成の取得元(バージョンの決まり方)
セルフホスト構成は `supabase/supabase` リポジトリの `docker/` 配下で配布されており、
**各コンテナのイメージタグはその中の `docker-compose.yml` に固定**されています。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `supabase_ref` | (固定のコミット) | 取得するリビジョン。`master` にすると毎回最新を取りに行きます |
| `supabase_repo_url` | 公式リポジトリ | 取得元 |

- 取得は**sparse checkout**で `docker/` だけを落とします(リポジトリ全体は巨大なため)
- `supabase_ref` を変えない限りバージョンは上がりません。上げるときは
  [公式のCHANGELOG](https://github.com/supabase/supabase/blob/master/docker/CHANGELOG.md)を
  確認してから、新しいコミットハッシュを指定してください
- データ(`volumes/db/data` など)と `.env` は上流の `.gitignore` に入っているため、
  リビジョンを切り替えてもデータは消えません

## 指定できる項目
**`.env` に入る値はすべて変数として指定できます**(対応は下の表)。
ここに無い項目は `supabase_extra_env` で足せます。

### 秘密情報(空なら自動生成 → `.env` に保存)
| 変数 | 環境変数 |
| --- | --- |
| `supabase_postgres_password` | `POSTGRES_PASSWORD` |
| `supabase_jwt_secret` | `JWT_SECRET` |
| `supabase_anon_key` / `supabase_service_role_key` | `ANON_KEY` / `SERVICE_ROLE_KEY` |
| `supabase_dashboard_username` / `supabase_dashboard_password` | `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` |
| `supabase_secret_key_base` | `SECRET_KEY_BASE` |
| `supabase_realtime_db_enc_key` | `REALTIME_DB_ENC_KEY` |
| `supabase_vault_enc_key` | `VAULT_ENC_KEY` |
| `supabase_pg_meta_crypto_key` | `PG_META_CRYPTO_KEY` |
| `supabase_logflare_public_access_token` / `_private_access_token` | `LOGFLARE_*_ACCESS_TOKEN` |
| `supabase_s3_protocol_access_key_id` / `_secret` | `S3_PROTOCOL_ACCESS_KEY_*` |
| `supabase_minio_root_password` | `MINIO_ROOT_PASSWORD` |
| `supabase_pooler_tenant_id` | `POOLER_TENANT_ID` |

⚠ **これらはDBの中身と対になっています。** 後から変えると既存のJWTが検証できなくなったり、
Realtime/Supavisorが保存済みの設定を復号できなくなります。変更する場合は
`volumes/db/data` ごと作り直してください。

### 非対称鍵(ES256)方式のAPIキー
| 変数 | 環境変数 |
| --- | --- |
| `supabase_enable_asymmetric_keys` | (生成するかどうか。既定 `false`) |
| `supabase_publishable_key` / `supabase_secret_key` | `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_SECRET_KEY` |
| `supabase_jwt_keys` / `supabase_jwt_jwks` | `JWT_KEYS` / `JWT_JWKS` |
| `supabase_anon_key_asymmetric` / `supabase_service_role_key_asymmetric` | `ANON_KEY_ASYMMETRIC` / `SERVICE_ROLE_KEY_ASYMMETRIC` |

`true` にすると公式スクリプト(`utils/add-new-auth-keys.sh`)で生成します
(生成後も従来の `ANON_KEY` / `SERVICE_ROLE_KEY` は使えます)。

### URL・接続先
| 変数 | 環境変数 | 既定値 |
| --- | --- | --- |
| `supabase_public_url` | `SUPABASE_PUBLIC_URL` | `http://<VMのIP>:<Kongのポート>` |
| `supabase_api_external_url` | `API_EXTERNAL_URL` | 公開URL + `/auth/v1` |
| `supabase_site_url` | `SITE_URL` | `http://localhost:3000` |
| `supabase_additional_redirect_urls` | `ADDITIONAL_REDIRECT_URLS` | (なし) |
| `supabase_kong_http_port` / `_https_port` | `KONG_HTTP_PORT` / `KONG_HTTPS_PORT` | `8000` / `8443` |

### データベース・プーラー
| 変数 | 環境変数 | 既定値 |
| --- | --- | --- |
| `supabase_postgres_host` / `_db` / `_port` | `POSTGRES_HOST` / `POSTGRES_DB` / `POSTGRES_PORT` | `db` / `postgres` / `5432` |
| `supabase_pooler_proxy_port_transaction` | `POOLER_PROXY_PORT_TRANSACTION` | `6543` |
| `supabase_pooler_default_pool_size` / `_max_client_conn` / `_db_pool_size` | `POOLER_*` | `20` / `100` / `5` |

### Studio・Auth・API・Storage・その他
| 変数 | 環境変数 | 既定値 |
| --- | --- | --- |
| `supabase_studio_default_organization` / `_project` | `STUDIO_DEFAULT_*` | `Default Organization` / `Default Project` |
| `supabase_openai_api_key` | `OPENAI_API_KEY` | (なし。AIアシスタント用) |
| `supabase_jwt_expiry` | `JWT_EXPIRY` | `3600` |
| `supabase_disable_signup` | `DISABLE_SIGNUP` | `false` |
| `supabase_enable_email_signup` / `_email_autoconfirm` | `ENABLE_EMAIL_*` | `true` / `false` |
| `supabase_smtp_admin_email` / `_host` / `_port` / `_user` / `_pass` / `_sender_name` | `SMTP_*` | (ダミーのSMTP) |
| `supabase_enable_anonymous_users` | `ENABLE_ANONYMOUS_USERS` | `false` |
| `supabase_enable_phone_signup` / `_phone_autoconfirm` | `ENABLE_PHONE_*` | `true` / `true` |
| `supabase_mailer_urlpaths_*` | `MAILER_URLPATHS_*` | `/auth/v1/verify` |
| `supabase_pgrst_db_schemas` / `_max_rows` / `_extra_search_path` | `PGRST_DB_*` | `public,graphql_public` / `1000` / `public` |
| `supabase_global_s3_bucket` / `supabase_region` / `supabase_storage_tenant_id` | `GLOBAL_S3_BUCKET` / `REGION` / `STORAGE_TENANT_ID` | `stub` |
| `supabase_minio_root_user` | `MINIO_ROOT_USER` | `supa-storage` |
| `supabase_functions_verify_jwt` | `FUNCTIONS_VERIFY_JWT` | `false` |
| `supabase_imgproxy_auto_webp` | `IMGPROXY_AUTO_WEBP` | `true` |
| `supabase_docker_socket_location` | `DOCKER_SOCKET_LOCATION` | `/var/run/docker.sock` |
| `supabase_google_project_id` / `_number` | `GOOGLE_PROJECT_*` | (ログ収集を足したときに使用) |
| `supabase_proxy_domain` / `supabase_certbot_email` | `PROXY_DOMAIN` / `CERTBOT_EMAIL` | (TLSプロキシを足したときに使用) |
| `supabase_extra_env` | (任意) | `{}` |

### 構成の切り替え(`supabase_compose_files`)
公式は用途別のcompose定義を同梱しており、`COMPOSE_FILE` で重ねて使います。

```sh
# ログ収集(Vector + Logflare)を足す
-e '{"supabase_compose_files": ["docker-compose.yml", "docker-compose.logs.yml"]}'
```

| 定義 | 内容 |
| --- | --- |
| `docker-compose.logs.yml` | Vector + Logflareによるログ収集・分析 |
| `docker-compose.s3.yml` / `docker-compose.rustfs.yml` | Storageのバックエンドをオブジェクトストレージにする |
| `docker-compose.pg15.yml` / `docker-compose.pg17.yml` | Postgresのメジャーバージョンを固定する |
| `docker-compose.caddy.yml` / `docker-compose.nginx.yml` | Let's EncryptでHTTPS化する(`supabase_proxy_domain` が必要) |

### OAuth・SAML・SMS認証について
`GOOGLE_*` / `GITHUB_*` / `SAML_*` / `SMS_*` / `MFA_*` は、**公式の
`docker-compose.yml` 側でも対応する `GOTRUE_*` の行を有効にする必要がある**ため、
環境変数を渡すだけでは有効になりません。使う場合は
`supabase_extra_env` で値を渡したうえで、
[公式ドキュメント](https://supabase.com/docs/guides/self-hosting/docker)の手順に従って
compose定義側も編集してください(そのままでは次回の取得で戻ります)。

## 実施する内容
1. OS確認(**Debianであること**)、変数の検証、**空き容量の確認**
2. [全VM共通のセットアップ](../README.md#共通セットアップtasks)(OS更新、タイムゾーン、
   ロケール、zram、sudoグループ、基本パッケージ、QEMUエージェント)
3. Dockerの導入(`get.docker.com`)と、SSHユーザーのdockerグループ追加
4. 公式のセルフホスト構成を取得(**sparse checkoutで `docker/` のみ**)
5. 秘密情報の決定(-e > 既存の `.env` > 公式スクリプトで生成)と `.env` の配置
6. `docker compose up`(**`.env` が変わった場合はコンテナを作り直します**)
7. ufwが導入済みかつ有効な場合のみポートを開放(通常はスキップ)
8. **全コンテナが起動するまで待機** → 認証APIとダッシュボードの応答確認
9. VM再起動 → コンテナが自動復帰し、実行元の端末からAPIが見えることを確認

## 構成されるもの
| パス | 内容 |
| --- | --- |
| `/opt/supabase/supabase/docker/` | 公式のcompose一式(compose実行ディレクトリ) |
| `/opt/supabase/supabase/docker/.env` | 環境変数(root所有・`0640`・dockerグループのみ読み取り可) |
| `/opt/supabase/supabase/docker/volumes/db/data` | **Postgresのデータ本体** |
| `/opt/supabase/supabase/docker/volumes/storage` | Storageのファイル実体 |

公開されるポート(既定):

| ポート | 用途 |
| --- | --- |
| `8000` / `8443` | Kong(API + ダッシュボード) |
| `5432` | Postgres(Supavisorのセッションモード) |
| `6543` | Supavisor(トランザクションモード) |

## 運用
```sh
# VM内(SSHユーザーのまま。dockerグループに入っています)
cd /opt/supabase/supabase/docker
docker compose ps
docker compose logs -f auth        # サービス名: db / auth / rest / realtime / storage / kong / studio ...

sudo grep -E '^(ANON_KEY|SERVICE_ROLE_KEY|DASHBOARD_PASSWORD)=' .env
```

⚠ 停止・起動は **`docker compose up -d` / `down`** を使ってください。

### アプリからの接続
```
URL      : http://<VMのIP>:8000
anon key : .env の ANON_KEY(クライアント用)
service  : .env の SERVICE_ROLE_KEY(⚠ サーバー専用。公開しないこと)
Postgres : postgres://postgres.<POOLER_TENANT_ID>:<POSTGRES_PASSWORD>@<VMのIP>:5432/postgres
```

### バージョンアップ
`-e "supabase_ref=<新しいコミットハッシュ>"` を付けて再実行すると、その版の
compose定義に入れ替わってコンテナが作り直されます。**先にバックアップを取り、
[公式のCHANGELOG](https://github.com/supabase/supabase/blob/master/docker/CHANGELOG.md)で
破壊的変更(特にPostgresのメジャーバージョン)を確認**してください。

### バックアップ
`.env` と `volumes/db/data` は**対**です。両方まとめて保存してください
(鍵だけ失うとDBを読めなくなります)。論理バックアップなら
`docker compose exec db pg_dumpall -U postgres > dump.sql` も使えます。

## 再実行について
何度実行しても同じ状態になります。`.env` が変わらなければコンテナは作り直されず、
DBのデータもそのまま残ります。秘密情報は既存の `.env` から引き継ぐため、
**再実行でパスワードやAPIキーが変わることはありません**。

## うまくいかないとき
| 症状 | 確認すること |
| --- | --- |
| 「空き容量が足りません」で止まる | `df -h /`。イメージだけで数GiB必要です(`vm_hardware` の `resize`) |
| 「すべてのコンテナが起動しませんでした」で止まる | 表示されたログ。`cd /opt/supabase/supabase/docker && sudo docker compose ps` |
| `db` が起動しない | `volumes/db/data` に古いデータが残っていないか(`.env` を作り直した場合は要削除) |
| `auth` / `rest` が再起動を繰り返す | `.env` の `JWT_SECRET` と `ANON_KEY` / `SERVICE_ROLE_KEY` の組み合わせが合っているか |
| ダッシュボードに入れない | ユーザー名は `DASHBOARD_USERNAME`、パスワードは `.env` の `DASHBOARD_PASSWORD` |
| APIキーが分からない | `sudo grep '^ANON_KEY=' /opt/supabase/supabase/docker/.env` |
| メールのリンクが `localhost` になる | `supabase_public_url` / `supabase_site_url` を実際のURLにして再実行 |
| 外部からPostgresに繋げない | ユーザー名が `postgres.<POOLER_TENANT_ID>` 形式になっているか(Supavisor経由のため) |
