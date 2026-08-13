# vault/ — 秘密情報の置き場

クラスタに入れる Secret のマニフェストをここにまとめる。

> **このディレクトリは、この `README.md` を除いて git 追跡外。**
> ルートの `.gitignore` で `/vault/*` を無視し、`README.md` だけ例外にしてある。
> base64 は暗号化ではないので、Secret を git に入れたら平文と同じ。

そのため **`git clone` した直後の vault/ には、この README しか無い**。
下の表を見て YAML を作り直すこと。どのファイルに何を書くかは
各アプリの README.md にも書いてある。

## 中身

| ファイル | Secret | Namespace | キー |
| --- | --- | --- | --- |
| `cloudflare.yaml` | `cloudflare-api-token` | `cert-manager` | `api-token` |
| | `tunnel-token` | `cloudflare` | `token` |
| `postgresql.yaml` | `postgresql-superuser` | `platform` | `postgres-password` |
| `homarr.yaml` | `homarr-db` | `platform` | `db-url` |
| | `homarr-db-encryption` | `platform` | `db-encryption-key` |
| | `homarr-oidc` | `platform` | `oidc-client-id` `oidc-client-secret` |
| `ansible-awx.yaml` | `awx-postgres-configuration` | `platform` | `host` `port` `database` `username` `password` `sslmode` `type` |
| | `awx-oidc` | `platform` | `oidc.py` (Python の設定ファイルそのもの) |
| `pgadmin.yaml` | `pgadmin-admin` | `platform` | `password` |
| | `pgadmin-oidc` | `platform` | `PGADMIN_OAUTH2_CLIENT_ID` `PGADMIN_OAUTH2_CLIENT_SECRET` |
| | `pgadmin-db` | `platform` | `PGADMIN_DB_URI` |
| `nextcloud.yaml` | `nextcloud-admin` | `platform` | `nextcloud-username` `nextcloud-password` |
| | `nextcloud-db` | `platform` | `db-hostname` `db-name` `db-username` `db-password` |
| | `nextcloud-oidc` | `platform` | `oidc-client-id` `oidc-client-secret` |
| `apache-guacamole.yaml` | `guacamole-db` | `platform` | `db-password` |
| | `guacamole-oidc` | `platform` | `oidc-client-id` (シークレットは無い) |

`kustomization.yaml` は上の 7 ファイルを列挙しているだけ。

### ここに置かないもの

Operator やチャートが**自分で生成する** Secret は置かない。

| Secret | 誰が作るか |
| --- | --- |
| `awx-admin-password` | AWX Operator |
| `awx-secret-key` | AWX Operator |
| `letsencrypt-prod-account-key` | cert-manager |
| `cc-chacchan-wildcard-tls` | cert-manager |

ただし **`awx-secret-key` は失うと登録済みの認証情報が全滅する**。
`kubectl get secret -o yaml` で別途退避しておくこと
(手順は [`../platform/apps/ansible-awx/README.md`](../platform/apps/ansible-awx/README.md))。

## 適用

```sh
kubectl diff  -k vault     # 先に必ずこれを見る
kubectl apply -k vault
```

**`kubectl apply -k .` (ルート) では適用されない。** ルートの
`kustomization.yaml` から意図的に外してある。秘密情報を
普段の apply に混ぜないため。

> **値が空のまま apply しないこと。**
> 稼働中の Secret が空文字で上書きされ、アプリが軒並み落ちる。
> `kubectl diff -k vault` の出力を必ず見る。

Secret とアプリのどちらを先に入れてもよい。Secret が無い間は Pod が
`CreateContainerConfigError` で止まるが、あとから Secret を作れば
kubelet が拾って起動する。**順番を守る必要は無い。**

## 値を用意する

### パスワードの生成

```sh
openssl rand -base64 24 | tr -d '/+='     # 一般的なパスワード
openssl rand -hex 32                      # homarr の db-encryption-key
```

記号を落として英数字だけにしているのは、AWX がパスワードに
`'` `"` `\` を禁止していること、`/` と `@` が接続 URL の区切りと
ぶつかることによる。

### DB のパスワードは 1 つだけ

アプリごとにロールは分けていない。**`postgres` ユーザで自分の DB に繋ぐ**。
そのため覚えるパスワードは `postgres-password` の 1 つで、
それを 3 つの接続情報にも書く。

| `postgresql.yaml` | 同じ値を書く場所 |
| --- | --- |
| `postgres-password` | `homarr.yaml` の `db-url` (URL の `:` の後) |
| | `ansible-awx.yaml` の `password` |
| | `pgadmin.yaml` の `PGADMIN_DB_URI` (URL の `:` の後) |
| | `nextcloud.yaml` の `db-password` |
| | `apache-guacamole.yaml` の `db-password` |

ロールを分ければ「アプリごとに自分の DB しか触れない」状態にはできるが、
同じパスワードを DB 側とアプリ側の 2 か所に書くことになり、
ずれたときの事故のほうが大きい。管理者が 1 人のクラスタなので分けていない。

### OIDC のクライアント資格情報

Authentik (`auth.cc-chacchan.com`) で Application と Provider を作ると
発行される。**アプリごとに別々に作ること** — コールバック URL が違う。

| アプリ | Authentik の Slug | Redirect URI |
| --- | --- | --- |
| Homarr | `homarr` | `https://homarr.cc-chacchan.com/api/auth/callback/oidc` |
| pgAdmin | `pgadmin` | `https://pgadmin.cc-chacchan.com/oauth2/authorize` |
| AWX | `awx` | `https://ansible.cc-chacchan.com/sso/complete/oidc/` |
| Nextcloud | `nextcloud` | `https://nextcloud.cc-chacchan.com/apps/user_oidc/code` |
| Guacamole | `guacamole` | `https://guacamole.cc-chacchan.com/` |

**Guacamole だけシークレットが発行されない。** Guacamole の OIDC は
implicit flow なので、Authentik 側は Client type: `Public` で作る。
あわせて Provider の **Signing Key を必ず選ぶこと**
(空だと id_token が HS256 になり、Guacamole が JWKS で検証できない)。

**`awx-oidc` だけ形が違う。** 値ではなく Python の設定ファイルを丸ごと
入れる (`oidc.py`)。Operator がそれを `/etc/tower/conf.d/oidc.py` に
マウントし、AWX が読む。

## 変更するとき

### PostgreSQL のパスワード

`postgres-password` は**初回起動時にしか読まれない**。
すでに DB がある状態で値を変えても反映されない。DB 側を先に変える。

```sh
kubectl -n platform exec -i sts/postgresql -- \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres -v password='<新しいパスワード>' \
  <<'EOSQL'
ALTER ROLE postgres PASSWORD :'password';
EOSQL
```

そのあと vault の 6 ファイル
(`postgresql` `homarr` `ansible-awx` `pgadmin` `nextcloud` `apache-guacamole`)
を直して `kubectl apply -k vault`、最後にアプリを再起動する。

```sh
kubectl -n platform rollout restart \
  deploy/homarr deploy/pgadmin deploy/nextcloud deploy/guacamole
kubectl -n platform delete pod -l app.kubernetes.io/name=awx-web
kubectl -n platform delete pod -l app.kubernetes.io/name=awx-task
```

### 変えられないもの

| 値 | 理由 |
| --- | --- |
| `homarr-db-encryption` の `db-encryption-key` | DB 内の資格情報がこの鍵で暗号化されている。変えると復号できなくなる |
| `awx-secret-key` (Operator 生成) | 同上 |

**この 2 つはパスワードマネージャ等に控えておくこと。**
クラスタを作り直すときに、PVC より先に必要になる。

## 元の手順

`kubectl create secret generic ...` で作っても中身は同じ。
各アプリの README.md にはそちらの形で書いてある。

- [`../platform/apps/postgresql/README.md`](../platform/apps/postgresql/README.md) — まとめて作るスクリプト
- [`../platform/apps/homarr/README.md`](../platform/apps/homarr/README.md)
- [`../platform/apps/pgadmin/README.md`](../platform/apps/pgadmin/README.md)
- [`../platform/apps/ansible-awx/README.md`](../platform/apps/ansible-awx/README.md)
