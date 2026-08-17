# supabase.yml — Supabaseを構築する

Docker composeでSupabase一式(PostgreSQL + API + Studio)をVMごと一気通貫で構築する。ダッシュボードのパスワードは [vault/supabase.yml](../../vault/supabase.yml) から渡る。構築後はAPI/Studioが :8000、Postgresがセッション :5432 / トランザクション :6543。APIキーの確認手順は実行結果に表示される。

## 実行方法

```sh
# インベントリ実行(supabaseグループの宣言どおり)
ansible-playbook playbooks/vm/supabase.yml
```

## 変数一覧(サービス固有の主要なもの)

接続系の共通変数は [README.md](README.md#共通の変数全サービスplaybook)。全既定値の正は [roles/vm_supabase/defaults/main.yml](../../roles/vm_supabase/defaults/main.yml)(設定項目は非常に多い。URL・ポート・プール設定・メール認証まわりはそちらを参照)。

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `supabase_dashboard_password` | str | | vault | Studio(ダッシュボード)のログインパスワード |
| `supabase_dashboard_username` | str | | `supabase` | ダッシュボードのユーザー名 |
| `supabase_public_url` | str | | `http://<IP>:8000` | ブラウザからのアクセスURL(役割プロファイルで宣言) |
| `supabase_ref` | str | | commit SHA固定 | 公式リポジトリの版(compose定義の再現性のため固定) |
| `supabase_kong_http_port` | int | | `8000` | API/Studioのポート |
| `supabase_postgres_password` / `supabase_jwt_secret` / `supabase_anon_key` ほか | str | | 自動生成 | 秘密情報一式(初回生成し `.env` に保存、再実行で引き継ぐ) |

## AWXでの実行

Job Template **`vm-supabase`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。Surveyは共通12問。

## つまずきやすいポイント

- **APIキー(anon/service_role)はどこ?** → 初回に自動生成され、VM上の `.env` にある。確認手順は実行結果に表示される
- **バックアップは `.env` と `volumes/db/data` を対で** → 秘密鍵とデータが対のため、片方だけ復元すると復号できない
- **構築に時間がかかる** → イメージが多い。SSH待ちの延長は `-e vm_ssh_wait_timeout=1200` のように渡せる
