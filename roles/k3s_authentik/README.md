# k3s_authentik

Authentik(IdP)を Helm で入れ、アプリの OIDC クライアントと認証プロキシを Blueprint で宣言する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「クラスタ内アプリの構成」「再現性の範囲」)。

## 使い方

`playbooks/k3s/authentik.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_authentik` と `defaults/main.yml`。

前提: CloudNativePG のオペレーターが入っている(`playbooks/k3s/cnpg.yml`)。専用の PostgreSQL(namespace `authentik-db`)は、このロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。

## 処理の流れ

[k3s](../k3s/README.md) ロールに、チャートと、設定の Secret(`authentik-config`)、Blueprint の ConfigMap を渡して適用する。

- OIDC クライアントの `client_id` は slug と同じ。`client_secret` は、アプリ側の vault ファイル(`vault/openwebui.yml` など)の値を、Authentik の Blueprint と、アプリの Secret の両方に渡す。そのため、Authentik を先に完成させなくても、アプリを先に入れられる。
- クライアントを足すときは、`authentik_oidc_clients` に足し、`playbooks/k3s/authentik.yml` の `authentik_oidc_client_secrets` に secret を足す。
- Blueprint は2つ(`oidc-clients` と、認証プロキシの `forward-auth`)。Authentik が ConfigMap の変更を検知して適用する。playbook は適用の成否を見ないので、Authentik の画面(Customization → Blueprints)で `successful` を確かめる。
- IP ごとに、ログインの失敗が成功を `authentik_login_failure_limit` 回だけ上回ると、その IP からのログインを拒否する(同じ IP からの成功は、失敗を1回ずつ打ち消す。最初の記録から `authentik_login_failure_expiry` 秒で解ける。緊急用の `akadmin` も同じ IP からは入れない)。解除を待てないときは、別の IP から入るか、ログイン済みのセッションで管理画面の Reputation の記録を消す。
- MFA を登録していないユーザーには、ログインの途中で登録させる(`authentik_mfa_required`)。
- 自前のログインを持たない画面や管理画面(`authentik_proxy_apps`。既定は Longhorn の管理 UI、CLIProxyAPI の管理画面、AM の管理 UI・管理 API、APIM のコンソール・管理 API)を、認証プロキシ(forward auth)で守る。Blueprint がプロキシプロバイダーとアプリケーションを作り、Authentik 内蔵のアウトポストに受け持たせる。Traefik のミドルウェア(`authentik_forward_auth_middleware`)を `authentik` namespace に置き、守る画面の Ingress は `<namespace>-<名前>@kubernetescrd`(既定は `authentik-forward-auth@kubernetescrd`)で参照する。守る画面を使えるのは、グループ `authentik_proxy_access_group`(既定は `admins`)のメンバーだけ(グループが無い間は、誰も使えない)。内蔵のアウトポストが受け持つプロバイダーは、Blueprint の内容に置き換わる(画面で足したものは、次の適用で外れる)。
- Pod が受ける通信を、同じ namespace と Traefik に絞る(NetworkPolicy)。
- 外部(Cloudflare Tunnel)に公開するのは、インベントリの `cloudflared_hosts` に `authentik_host` があるとき。Tunnel を通るログイン(LAN から公開ホスト名で開いたものを含む)は、cloudflared の Pod の IP に見えるため、ログインの失敗の制限を掛けない(`authentik_login_failure_exempt_networks`。Cloudflare 側で絞る。[k3s_cloudflared](../k3s_cloudflared/README.md))。緊急用の `akadmin` も、外からログインできる。
- Google でログインできるようにする(`authentik_google_client_id` が空でないとき)。入れるのは、Authentik に作ってあるユーザーと、メールアドレスが一致する Google アカウントだけ。一致するユーザーがいないアカウントは拒否し、ユーザーを自動では作らない。Google でのログインでは、Authentik の MFA を求めない(Google の2段階認証に任せる)。
- Google の OAuth クライアント(ウェブアプリケーション)には、承認済みのリダイレクト URI として `https://<authentik_host>/source/oauth/callback/google/` を登録する。

## 管理しないもの

ユーザー、パスワード、グループ、グループの所属、アプリケーションを使えるグループの結びつけは、Authentik の状態として扱い、Ansible では管理しない。Authentik の画面で設定する。権限はグループに付け、ユーザーには直接付けない。OIDC のアプリケーションは、グループを結びつけるまで、Authentik のすべてのユーザーが使える(認証プロキシのアプリケーションは、上のとおり Blueprint がグループで絞る)。緊急用の管理者 `akadmin` は、初回の起動時に `vault/authentik.yml` のパスワードとトークンで作られる(2回目以降は変更されない)。Google でログインするユーザーは、メールアドレスを Google アカウントと同じにする。

## 管理 API で既存アプリを管理する

[inventory/group_vars/authentik.yml](../../inventory/group_vars/authentik.yml)に、サービス設定・OIDC クライアント・認証プロキシ・既存アプリの表示設定を宣言する。既存の slug を保ち、次のコマンドで変更予定を確認してから適用する。

```sh
ansible-playbook playbooks/k3s/authentik_manage.yml --check --diff 2>&1 | cat
ansible-playbook playbooks/k3s/authentik_manage.yml 2>&1 | cat
```

この playbook は管理 API だけを使い、アプリ名・起動 URL・説明・表示グループ・新しいタブで開くかなど、宣言した表示設定だけを部分更新する。表示グループは認可のグループとは別のもの。プロバイダーの接続・認可ポリシー・利用者・所属・アプリへのグループの結びつけは変更しない。アプリの新規作成・削除・slug の変更は行わない。対象がなければ停止する。変数と許可する項目は `defaults/main.yml` と `meta/argument_specs.yml` の `manage` を参照する。

アプリの表示設定は Blueprint も同じ inventory から読む。管理画面で宣言済みの設定を変えても、次の適用では inventory の値に戻る。プロバイダーの作成と OIDC・認証プロキシの接続は、引き続き `authentik.yml` と Blueprint が担当する。画面で作ったアプリを追加管理するときは、取得記録から既存の slug と必要な表示設定だけを inventory に追加する。

処理は全ページの取得 → 差分計算 → 部分更新 → 再取得・確認。`--check --diff` ではアプリの slug と変更項目名だけを表示し、値やトークンは表示しない。通常適用は冪等。複数アプリをまたぐ更新はトランザクションではないため、途中失敗では原因を直して再実行する。設定を戻す場合は inventory を戻し、確認してから再適用する。

接続は LAN/VPN 用の `auth-api.<lab_domain>` を使う。この名前は既存のワイルドカード DNS で LAN 用の入口を返し、HTTPS はワイルドカード証明書で検証する。`Host` ヘッダーには既存の Authentik のホスト名を渡す。DNS レコードや Ingress は追加しない。この管理 API 接続は Cloudflare Tunnel を経由しない。API のトークンは `vault/authentik.yml` にある bootstrap 用の値を使う。ユーザーごとのアクセス判定ではなく全アプリを取得するため、管理者のトークンが必要。

## 参照用の取得記録

`ansible-playbook playbooks/utils/authentik_export.yml 2>&1 | cat` で [vault/authentik_snapshot.yml](../../vault/authentik_snapshot.yml)へ暗号化して保存する。既存ファイルを置き換える場合だけ `-e authentik_export_overwrite=true` を指定する。取得記録は適用元にせず、inventory・トークン・キーの台帳は書き換えない。完全な DB バックアップの代わりにはならない。チェックモードでは保存しない。
