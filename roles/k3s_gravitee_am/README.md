# k3s_gravitee_am

Gravitee Access Management(AM)を Helm で入れる。Gravitee API Management([k3s_gravitee](../k3s_gravitee/README.md))のログインを、Authentik へ中継する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/gravitee_am.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_gravitee_am` と `defaults/main.yml`。

前提:

- CloudNativePG のオペレーターが入っている(`playbooks/k3s/cnpg.yml`)。専用の PostgreSQL(namespace `gravitee-am-db`)は、このロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。
- `playbooks/k3s/authentik.yml` で、OIDC クライアント `gravitee-am` と、管理画面の認証プロキシ(`authentik_proxy_apps` の `gravitee-am-admin`)を作ってある。
- `k3s_ingress_hosts` に `gravitee_host` を入れて、`playbooks/vm/k3s.yml` を流してある。APIM から AM へ、AM から Authentik への通信が、クラスタ内で Traefik に届くため。

| ホスト | パス | 向け先 | 公開 |
| --- | --- | --- | --- |
| `gravitee_host` | `/auth` | ゲートウェイ(ログインの中継。接頭辞を除いて転送し、AM は `X-Forwarded-Prefix` で公開 URL を作る) | LAN・Tunnel。Tunnel では、ローカルのアカウントのログイン・登録・パスワードの再設定などのパスを通さない |
| `gravitee_am_host` | `/management` | 管理 API | LAN・VPN。Authentik の認証プロキシ(`admins`) |
| `gravitee_am_host` | `/` | 管理画面 | LAN・VPN。Authentik の認証プロキシ(`admins`) |

## AM の画面での設定

AM のドメイン・identity provider・アプリケーションは状態で、Ansible では作らない。`gravitee_am.yml` のあと、`gravitee.yml` の前に、次のとおり設定する。シークレットは `ansible-vault view` で確認する。

1. `https://<gravitee_am_host>/` を開き、Authentik の認証プロキシを通ったあと、AM のユーザー `admin`(パスワードは `vault/gravitee_am.yml` の `vault_gravitee_am_admin_password`)でログインする。
2. セキュリティドメイン `apim` を作り、有効にする。ユーザーの登録とパスワードの再設定は、既定の無効のままにする。
3. ドメインの identity provider に OpenID Connect を足す。User mapper は設定しない(Authentik の claim を `groups` も含めてそのまま保ち、APIM へ渡すため)。

   | 項目 | 値 |
   | --- | --- |
   | 名前 | `Authentik` |
   | Client ID | `gravitee-am` |
   | Client Secret | `vault/gravitee_am.yml` の `vault_gravitee_am_oidc_client_secret` |
   | Well-Known Endpoint | `https://<authentik_host>/application/o/gravitee-am/.well-known/openid-configuration` |
   | Scopes | `openid`・`email`・`profile` |
   | Response type | `code` |

   AM が Authentik に渡すコールバックは `https://<gravitee_host>/auth/apim/login/callback`(Authentik 側には `authentik.yml` が登録済み)。
4. アプリケーション(Web)を足す。

   | 項目 | 値 |
   | --- | --- |
   | 名前 | `Gravitee API Management` |
   | Client ID | `gravitee` |
   | Client Secret | `vault/gravitee.yml` の `vault_gravitee_oidc_client_secret` |
   | Redirect URIs | `https://<gravitee_console_host>/console`(コンソール)、`https://<gravitee_host>/user/login`(ポータル) |
   | Grant types | `authorization_code` だけ |
   | Token endpoint の認証方式 | `client_secret_post`(APIM はシークレットを本文で送る。既定の `client_secret_basic` のままだと、ログインの最後に 401 になる) |
   | Scopes | `openid`・`profile`・`email`・`full_profile`(APIM が userinfo で `groups` を受け取るため) |
   | Identity providers | 3 の `Authentik` だけ(既定のローカルの identity provider は外す) |
   | Login | ログインフォームを隠す(Authentik へ直接進む) |

APIM が使う URL(ドメイン `apim`):

- Discovery: `https://<gravitee_host>/auth/apim/oidc/.well-known/openid-configuration`
- Authorize: `https://<gravitee_host>/auth/apim/oauth/authorize`
- Token: `https://<gravitee_host>/auth/apim/oauth/token`
- Userinfo: `https://<gravitee_host>/auth/apim/oidc/userinfo`

Authentik の画面で、アプリケーション `gravitee-am` に、グループ `admins` と `externals` を結びつける(状態)。結びつけたグループのユーザーだけが、APIM にログインできる。

## 注意

- `gravitee-am.<lab_domain>` は Tunnel に載せない(ログイン中継は `gravitee.<lab_domain>` で公開する)。
- AM の管理画面のログインは、SSO を持たないローカルのユーザー `admin` だけで、普段の管理にもこのユーザーを使う。そのため、管理画面と管理 API は、Authentik の認証プロキシで `admins` に限る。
- Authentik が使えないときは、管理画面に届かない。AM は Authentik へ中継するだけで、AM の画面で直せることはない。APIM の管理 API は、ポート転送と APIM の緊急用の `admin` で使う([k3s_gravitee](../k3s_gravitee/README.md))。
- ドメインの既定の証明書は、`vault_gravitee_am_certificate_key_password` と `vault_gravitee_am_certificate_store_password` で守られる。ドメインを作ったあとに変えると、その証明書が読めなくなる。
- 技術 API(`services.core.http`)は、Pod の中(`localhost`)だけで開く。パスワードは `vault_gravitee_am_technical_password`。
- ドメイン・identity provider・アプリケーション・ユーザーは DB に保存される(状態。バックアップは無い)。
