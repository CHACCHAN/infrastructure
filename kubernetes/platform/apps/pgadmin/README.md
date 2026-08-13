# pgAdmin 4

PostgreSQL の管理 WebUI。

| 項目 | 値 |
| --- | --- |
| チャート | `runix/pgadmin4` |
| バージョン | **1.66.0** (pgAdmin 9.17) |
| Namespace | `platform` |
| ホスト名 | `pgadmin.cc-chacchan.com` |
| 設定 DB | [postgresql/](../postgresql/) の `pgadmin` DB (SQLite ではない) |
| 認証 | ローカルアカウント + Authentik の OIDC |
| 設定 | [`values.yaml`](values.yaml) |
| 公開経路 | [`ingress.yaml`](ingress.yaml) |

## このディレクトリの構成

**本体と経路で適用方法が違う。**

| ファイル | 何を作るか | 適用方法 |
| --- | --- | --- |
| `values.yaml` | Deployment / Service / PVC / NetworkPolicy / ConfigMap | **helm template → kubectl apply** |
| `ingress.yaml` | Ingress | `kubectl apply -k .` (kustomize) |
| `kustomization.yaml` | `ingress.yaml` だけを列挙 | — |

**上流チャートには OIDC 用の値も設定 DB 用の値も無い。**
pgAdmin 側が「`config.py` の項目は `config_local.py` で上書きできる」
という作りなので、そのファイルを `values.yaml` の `extraDeploy`
(チャートがそのまま出力する追加マニフェスト) に ConfigMap として
書いて、`extraConfigmapMounts` でマウントしている。
**設定はすべて `values.yaml` に閉じている。**

pgAdmin の設定の優先順位は次のとおりで、`config_local.py` が最終的に勝つ。

```
config_local.py > PGADMIN_CONFIG_* 環境変数 > config_distro.py > config.py
```

## 適用

**入れる順番は気にしなくてよい。** Secret や DB が揃っていない間は
Pod が起動に失敗するが、kubelet が再試行し続けるので、
あとから足せば勝手に立ち上がる。

設定 DB は [postgresql/](../postgresql/) の `pgadmin` DB。

### 1. Secret

[`vault/pgadmin.yaml`](../../../vault/) にマニフェストがある (git 追跡外)。

```sh
kubectl diff  -k vault
kubectl apply -k vault
```

`kubectl create secret` で作っても中身は同じ。

```sh
# ローカルログイン用の初期管理者パスワード
kubectl -n platform create secret generic pgadmin-admin \
  --from-literal=password="$(openssl rand -base64 24 | tr -d '/+=')"

# Authentik で発行したクライアント資格情報 (手順は次節)
kubectl -n platform create secret generic pgadmin-oidc \
  --from-literal=PGADMIN_OAUTH2_CLIENT_ID='...' \
  --from-literal=PGADMIN_OAUTH2_CLIENT_SECRET='...'
```

> `pgadmin-oidc` と `pgadmin-db` は `envFrom` で読むので、
> **Secret のキー名がそのまま環境変数名になる**。
> `config_local.py` が `os.environ[...]` でその名前を参照しているため、
> キー名を変えるなら `values.yaml` の `config_local.py` も直すこと。

初期管理者のメールアドレスは `values.yaml` の `env.email`
(`chacchan.info@gmail.com`) に書いてある。

### 2. Authentik 側の設定 (初回だけ)

`auth.cc-chacchan.com` (172.16.11.2) の管理画面で作る。

1. **Provider** — 種別 `OAuth2/OpenID Provider`
   - Client type: `Confidential`
   - Redirect URI (Strict): `https://pgadmin.cc-chacchan.com/oauth2/authorize`
   - Signing Key: 任意の証明書
   - Scopes: `openid` `email` `profile`
2. **Application** — Slug は **`pgadmin`**
   - `values.yaml` の `OAUTH2_SERVER_METADATA_URL` が
     `https://auth.cc-chacchan.com/application/o/pgadmin/.well-known/openid-configuration`
     なので、slug を変えたら values 側も直す。
3. 発行された Client ID / Secret を `pgadmin-oidc` に入れる。

> **コールバック URL は `/oauth2/authorize`。**
> Homarr (`/api/auth/callback/oidc`) とは違うので、
> Authentik 側で同じものを使い回さないこと。

### 3. 本体 (helm)

```sh
helm repo add runix https://helm.runix.net
helm repo update

helm template pgadmin runix/pgadmin4 \
  --version 1.66.0 \
  --namespace platform \
  --values platform/apps/pgadmin/values.yaml \
  --no-hooks \
  | kubectl apply --server-side -f -
```

リポジトリのルートから実行すること。

`kubectl apply` 側に `--namespace` は不要。
このチャートは `metadata.namespace` を自分で出力する。

> `--no-hooks` は `helm test` 用の Pod を除外するため。
> `values.yaml` で `test.enabled: false` にもしてあるので二重の保険。

### 4. 経路 (kustomize)

```sh
kubectl apply -k .        # リポジトリのルートで
```

## 設定を変える

すべて `values.yaml` にある。

```sh
vim platform/apps/pgadmin/values.yaml

helm template pgadmin runix/pgadmin4 \
  --version 1.66.0 -n platform \
  --values platform/apps/pgadmin/values.yaml --no-hooks \
  | kubectl diff -f -

helm template pgadmin runix/pgadmin4 \
  --version 1.66.0 -n platform \
  --values platform/apps/pgadmin/values.yaml --no-hooks \
  | kubectl apply --server-side -f -
```

**`config_local.py` (extraDeploy の ConfigMap) を書き換えた場合は、
Pod の再起動が要る。** マウントしたファイルの更新が反映されるまで
時間がかかるうえ、pgAdmin は起動時にしか読まない。

```sh
kubectl -n platform rollout restart deploy/pgadmin
```

既定値の全体はこれで見られる。

```sh
helm show values runix/pgadmin4 --version 1.66.0
```

## バージョンを上げる

1. 上のコマンドの `--version` を新しい値にする
2. **この README の表とコマンド例のバージョンも書き換える**
3. `| kubectl diff -f -` で差分を確認する
4. `| kubectl apply --server-side -f -`
5. **Service のポート名が変わっていないか確認する**

5 が重要。`ingress.yaml` はポートを**名前** (`http`) で参照している。

```sh
kubectl -n platform get svc pgadmin -o jsonpath='{.spec.ports}' | jq
```

```sh
helm search repo runix/pgadmin4 --versions | head
```

> pgAdmin 本体のバージョンはチャートの appVersion で決まる (1.66.0 → 9.17)。
> 設定 DB のスキーマは pgAdmin が起動時に alembic で移行する。
> **上げる前に `pg_dump -d pgadmin` を取っておくこと。**

## 確認

```sh
kubectl -n platform rollout status deploy/pgadmin
kubectl -n platform get pvc pgadmin

# 設定 DB が PostgreSQL 側にできているか (SQLite ではなく)
kubectl -n platform exec sts/postgresql -- psql -U postgres -d pgadmin -c '\dt'

curl -s -o /dev/null -w '%{http_code}\n' https://pgadmin.cc-chacchan.com/   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://pgadmin.cc-chacchan.com/    # 404 が正しい
```

ログイン画面に、メール/パスワードの欄と "Authentik" ボタンの両方が出る。

`\dt` で `role` / `server` / `user` などのテーブルが並んでいれば、
設定 DB の切り替えは成功している。何も出ない場合は SQLite に
書かれているので、`PGADMIN_DB_URI` が渡っているか確認する。

```sh
kubectl -n platform exec deploy/pgadmin -- printenv | grep -c PGADMIN_DB_URI   # 1
```

## 気をつけること

### 設定 DB を PostgreSQL に置いている

既定では `/var/lib/pgadmin/pgadmin4.db` (SQLite) に、ユーザ・ロール・
登録済みサーバがすべて入る。それを `CONFIG_DATABASE_URI` で
[postgresql/](../postgresql/) の `pgadmin` DB に向けている。

**これは循環依存になっている。** PostgreSQL が落ちると pgAdmin にも
ログインできない。「PostgreSQL が落ちたので pgAdmin で調べる」が
できないので、DB 本体の調査は `kubectl exec` + `psql` で行うこと。

```sh
kubectl -n platform exec -it sts/postgresql -- psql -U postgres
```

PVC (`pgadmin`) はまだ必要で、セッションとストレージマネージャの
作業領域が入っている。設定は入っていないので 2Gi で足りる。

### OIDC ログインだとサーバ接続のパスワードを保存できない

pgAdmin は保存したサーバ接続のパスワードを「ログインパスワード」を
鍵にして暗号化する。OIDC にはそれが無いため、そのままでは保存できず、
接続のたびに入力することになる。

保存したい場合は `MASTER_PASSWORD_HOOK` に鍵を返すスクリプトを渡す
(server mode で auth source が oauth2 のときだけ使われる設定)。
今は設定していない。

### 自動作成されるユーザは一般ユーザ

`OAUTH2_AUTO_CREATE_USER = True` にしてあるので、Authentik で認証が
通れば pgAdmin 側のユーザが自動で作られる。ただしロールは `User` で、
自分が登録したサーバしか見えない。

管理者にするには、`values.yaml` の `env.email` のアカウントで
ローカルログインして Administrator へ昇格させる。
**そのため `AUTHENTICATION_SOURCES` から `internal` を外さないこと。**
外すと管理者の入り口が無くなる。

### ENHANCED_COOKIE_PROTECTION を False にしている

pgAdmin はクライアント IP をセッションクッキーに紐づける機能を持つが、
上流のドキュメントが「Kubernetes やロードバランサの背後では
False にすること」と明記している。Traefik 経由なので False。

### 秘密情報

`values.yaml` には書かない。`config_local.py` は `os.environ` で
読むだけで、値は 3 つの Secret
(`pgadmin-admin` / `pgadmin-oidc` / `pgadmin-db`) にある。
マニフェストは [`vault/pgadmin.yaml`](../../../vault/) — **git 追跡外**。
