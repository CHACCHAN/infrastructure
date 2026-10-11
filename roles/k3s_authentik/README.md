# k3s_authentik

Authentik(IdP)を Helm で入れ、アプリの OIDC クライアントと認証プロキシを Blueprint で宣言する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「クラスタ内アプリの構成」「再現性の範囲」)。

## 使い方

`playbooks/k3s/authentik.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_authentik` と `defaults/main.yml`。

前提: PostgreSQL に `authentik` の DB とロールがある([k3s_postgresql](../k3s_postgresql/README.md))。

## 処理の流れ

[k3s](../k3s/README.md) ロールに、チャートと、設定の Secret(`authentik-config`)、Blueprint の ConfigMap を渡して適用する。

- OIDC クライアントの `client_id` は slug と同じ。`client_secret` は、アプリ側の vault ファイル(`vault/homarr.yml` など)の値を、Authentik の Blueprint と、アプリの Secret の両方に渡す。そのため、Authentik を先に完成させなくても、アプリを先に入れられる。
- クライアントを足すときは、`authentik_oidc_clients` に足し、`playbooks/k3s/authentik.yml` の `authentik_oidc_client_secrets` に secret を足す。
- Blueprint は2つ(`oidc-clients` と、認証プロキシの `forward-auth`)。Authentik が ConfigMap の変更を検知して適用する。playbook は適用の成否を見ないので、Authentik の画面(Customization → Blueprints)で `successful` を確かめる。
- IP ごとに、ログインの失敗が成功を `authentik_login_failure_limit` 回だけ上回ると、その IP からのログインを拒否する(同じ IP からの成功は、失敗を1回ずつ打ち消す。最初の記録から `authentik_login_failure_expiry` 秒で解ける。緊急用の `akadmin` も同じ IP からは入れない)。解除を待てないときは、別の IP から入るか、ログイン済みのセッションで管理画面の Reputation の記録を消す。
- MFA を登録していないユーザーには、ログインの途中で登録させる(`authentik_mfa_required`)。
- 自前のログインを持たない画面(`authentik_proxy_apps`。既定は Longhorn の管理 UI)を、認証プロキシ(forward auth)で守る。Blueprint がプロキシプロバイダーとアプリケーションを作り、Authentik 内蔵のアウトポストに受け持たせる。Traefik のミドルウェア(`authentik_forward_auth_middleware`)を `authentik` namespace に置き、守る画面の Ingress は `<namespace>-<名前>@kubernetescrd`(既定は `authentik-forward-auth@kubernetescrd`)で参照する。守る画面を使えるのは、グループ `authentik_proxy_access_group`(既定は `admins`)のメンバーだけ(グループが無い間は、誰も使えない)。内蔵のアウトポストが受け持つプロバイダーは、Blueprint の内容に置き換わる(画面で足したものは、次の適用で外れる)。
- Pod が受ける通信を、同じ namespace と Traefik に絞る(NetworkPolicy)。
- Google でログインできるようにする(`authentik_google_client_id` が空でないとき)。入れるのは、Authentik に作ってあるユーザーと、メールアドレスが一致する Google アカウントだけ。一致するユーザーがいないアカウントは拒否し、ユーザーを自動では作らない。Google でのログインでは、Authentik の MFA を求めない(Google の2段階認証に任せる)。
- Google の OAuth クライアント(ウェブアプリケーション)には、承認済みのリダイレクト URI として `https://<authentik_host>/source/oauth/callback/google/` を登録する。

## 管理しないもの

ユーザー、パスワード、グループ、グループの所属、アプリケーションを使えるグループの結びつけは、Authentik の状態として扱い、Ansible では管理しない。Authentik の画面で設定する。権限はグループに付け、ユーザーには直接付けない。OIDC のアプリケーションは、グループを結びつけるまで、Authentik のすべてのユーザーが使える(認証プロキシのアプリケーションは、上のとおり Blueprint がグループで絞る)。緊急用の管理者 `akadmin` は、初回の起動時に `vault/authentik.yml` のパスワードとトークンで作られる(2回目以降は変更されない)。Google でログインするユーザーは、メールアドレスを Google アカウントと同じにする。
