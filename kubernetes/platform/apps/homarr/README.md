# Homarr

セルフホストサービスをまとめるダッシュボード。

| 項目 | 値 |
| --- | --- |
| チャート | `homarr-labs/homarr` |
| バージョン | **8.26.0** (appVersion `v1.74.0`) |
| Namespace | `platform` |
| ホスト名 | `homarr.cc-chacchan.com` |
| DB | [postgresql/](../postgresql/) の `homarr` DB |
| 認証 | ローカル資格情報 + Authentik の OIDC |
| 設定 | [`values.yaml`](values.yaml) |
| 公開経路 | [`ingress.yaml`](ingress.yaml) |

## このディレクトリの構成

**本体と経路で適用方法が違う。**

| ファイル | 何を作るか | 適用方法 |
| --- | --- | --- |
| `values.yaml` | Deployment / Service / PVC | **helm template → kubectl apply** |
| `ingress.yaml` | Ingress | `kubectl apply -k .` (kustomize) |
| `kustomization.yaml` | `ingress.yaml` だけを列挙 | — |

Ingress を上流チャートに任せず自分で書いているのは、TLS・entrypoints・
Middleware の書き方をリポジトリ全体で 1 か所に揃えるため。
そのため `values.yaml` では `ingress.enabled: false` にしてある。

## 適用

**入れる順番は気にしなくてよい。** Secret や DB が揃っていない間は
Pod が起動に失敗するが、kubelet が再試行し続けるので、
あとから足せば勝手に立ち上がる。

### 1. Secret

チャートは `existingSecret` を参照するだけで、Secret 自体は作らない。
[`vault/homarr.yaml`](../../../vault/) にマニフェストがある (git 追跡外)。

```sh
kubectl diff  -k vault
kubectl apply -k vault
```

`kubectl create secret` で作っても中身は同じ。

`SECRET_ENCRYPTION_KEY` は DB 内の資格情報 (各サービスの API キー等) を
暗号化する鍵。**これを失うと DB の中身が復号できなくなる**ので、
生成した値は別途パスワードマネージャ等に控えておくこと。

**値は必ず 64 文字の 16 進数にすること。** 好きな文字列は入れられない。
Homarr は起動時に `/^[0-9a-fA-F]{64}$/` で検証していて、外れると
`Invalid environment variables` を出して Pod が起動しない。

```sh
kubectl -n platform create secret generic homarr-db-encryption \
  --from-literal=db-encryption-key="$(openssl rand -hex 32)"
```

OIDC のクライアント資格情報は Authentik 側で発行する (手順は下記)。

```sh
kubectl -n platform create secret generic homarr-oidc \
  --from-literal=oidc-client-id='...' \
  --from-literal=oidc-client-secret='...'
```

### 2. Authentik 側の設定 (初回だけ)

`auth.cc-chacchan.com` (172.16.11.2) の管理画面で作る。

1. **Provider** を作る — 種別 `OAuth2/OpenID Provider`
   - Client type: `Confidential`
   - Redirect URI (Strict): `https://homarr.cc-chacchan.com/api/auth/callback/oidc`
   - Signing Key: 任意の証明書 (未設定だと `id_token` が署名されず弾かれる)
   - Scopes: `openid` `email` `profile` に加えて **`groups` のスコープマッピング**
     を必ず含める。無いと `groups` クレームが飛ばず、グループ同期が効かない。
2. **Application** を作る — Slug は **`homarr`**
   - `values.yaml` の `AUTH_OIDC_ISSUER` が
     `https://auth.cc-chacchan.com/application/o/homarr/` なので、
     slug を変えたら values 側も直すこと。
3. 発行された Client ID / Client Secret を上の `homarr-oidc` Secret に入れる。

> **issuer の末尾スラッシュは消さないこと。**
> Homarr のドキュメントは「issuer は末尾スラッシュなし」と書いているが、
> **Authentik だけは例外で末尾スラッシュが要る**と明記されている。

### 3. 本体 (helm)

Helm は**テンプレートを展開するためだけ**に使う。
リリースとしてはインストールしないので、`helm list` には出てこない。

```sh
helm repo add homarr-labs https://homarr-labs.github.io/charts/
helm repo update

helm template homarr homarr-labs/homarr \
  --version 8.26.0 \
  --namespace platform \
  --values platform/apps/homarr/values.yaml \
  | kubectl apply --server-side --namespace platform -f -
```

リポジトリのルートから実行すること。

**`kubectl apply` 側にも `--namespace platform` が要る。**
このチャートは `metadata.namespace` を出力しないので、
付け忘れると `default` に落ちる。

> Portainer のチャートとはここが逆になっている。README のコマンドをそのまま使うこと。

> **OCI レジストリ (`oci://ghcr.io/homarr-labs/charts/homarr`) を直接指さないこと。**
> 同じチャートだが、helm が `Pulled:` と `Digest:` の 2 行を
> **標準出力に混ぜる**ため、`| kubectl apply -f -` がその 2 行を
> YAML ドキュメントとして読んでしまう。
>
> ```
> error validating "STDIN": error validating data: [apiVersion not set, kind not set]
> ```
>
> `helm repo add` した HTTP リポジトリ経由なら出力は `---` から始まる。
> レンダリング結果は完全に同一。

### 4. 経路 (kustomize)

```sh
kubectl apply -k .        # リポジトリのルートで
```

## 設定を変える

```sh
vim platform/apps/homarr/values.yaml

# 何が変わるか確認する (クラスタは変わらない)
helm template homarr homarr-labs/homarr \
  --version 8.26.0 -n platform \
  --values platform/apps/homarr/values.yaml \
  | kubectl diff --namespace platform -f -

# 適用
helm template homarr homarr-labs/homarr \
  --version 8.26.0 -n platform \
  --values platform/apps/homarr/values.yaml \
  | kubectl apply --server-side --namespace platform -f -
```

`values.yaml` には上流の既定値との**差分だけ**を書いている。
既定値の全体はこれで見られる。

```sh
helm show values homarr-labs/homarr --version 8.26.0
```

### PVC のサイズは後から広げられない (縮められない)

`persistence.homarrDatabase.size` を変えても、既存の PVC には反映されない。
NFS の StorageClass は expansion に対応していないので、実質やり直しになる。
データの退避が必要。

## バージョンを上げる

1. 上のコマンドの `--version` を新しい値にする
2. **この README の表とコマンド例のバージョンも書き換える**
3. `| kubectl diff --namespace platform -f -` で差分を確認する
4. `| kubectl apply --server-side --namespace platform -f -`
5. **Service のポート名が変わっていないか確認する**

5 が重要。`ingress.yaml` はポートを**名前** (`app`) で参照している。

```sh
kubectl -n platform get svc homarr -o jsonpath='{.spec.ports}' | jq
```

名前が変わっていたら `ingress.yaml` も直す。

## 確認

```sh
kubectl -n platform rollout status deploy/homarr
kubectl -n platform get pvc homarr-database

# テーブルが PostgreSQL 側にできているか
kubectl -n platform exec sts/postgresql -- psql -U postgres -d homarr -c '\dt' | head

curl -s -o /dev/null -w '%{http_code}\n' https://homarr.cc-chacchan.com/   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://homarr.cc-chacchan.com/    # 404 が正しい
```

初回は `https://homarr.cc-chacchan.com/` を開くとオンボーディング
(管理者ユーザの作成) が始まる。ログイン画面には
ローカルのユーザ名/パスワード欄と "Authentik" ボタンの両方が出る。

## 気をつけること

### DB に SQLite を使っていない

チャートの既定は SQLite (`/appdata/db.sqlite`) だが、それだと DB ファイルが
NFS 上に置かれる。SQLite は `fcntl()` のファイルロックに依存していて、
NFS 上ではロックが正しく効かず DB が壊れることがある、というのは
SQLite 本家が昔から警告している既知の話。

このリポジトリの永続ストレージは TrueNAS の NFS しかないので、
`database.type: postgresql` にして [postgresql/](../postgresql/) を使っている。

PVC (`homarr-database`) はまだ必要で、アイコンのキャッシュや
信頼する証明書が入る。DB は入っていない。

バックアップは PostgreSQL 側で取る。

```sh
kubectl -n platform exec sts/postgresql -- \
  pg_dump -U postgres -d homarr --clean --if-exists > homarr-$(date +%F).sql
```

### レプリカを増やす場合

DB が外部になったので原理的には増やせるが、`/appdata` の PVC が
`ReadWriteOnce` なので今のままでは 2 つ目の Pod が起動しない。
増やすなら `accessMode` を `ReadWriteMany` にして
(`truenas-nfs` は NFS なので RWX が使える)、
`strategyType` を `RollingUpdate` に戻す。

### 認証プロバイダを 2 つ有効にしている

`AUTH_PROVIDERS: "credentials,oidc"` にしてある。
上流は「1 つだけにするのを強く推奨」としているが、
Authentik はクラスタ**外** (172.16.11.2) で動いていて、
そちらが落ちると Homarr にも入れなくなるため、
ローカル資格情報を退避経路として残している。

OIDC だけで運用すると決めたら `"oidc"` にして、
`AUTH_OIDC_AUTO_LOGIN` を `"true"` にするとログイン画面を挟まなくなる。
逆に `credentials` を残したまま auto-login を有効にすると、
退避経路のログイン画面に辿り着けなくなるので注意。

### Ingress に forwardAuth を付けていない

Homarr 自身が OIDC で Authentik に認証を投げるので、
Traefik 側の `authentik-forward-auth` Middleware は付けていない。
付けると認証が二重になる (cloudflare-ddns-ui のように
アプリ側に認証機能が無いものだけが Middleware を使う)。

### Pod から auth.cc-chacchan.com が引けること

OIDC の discovery とトークン交換は **Pod から** Authentik への通信になる。
名前解決やルーティングで詰まると、ログイン画面のボタンを押した先で
`fetch failed` 系のエラーになる。

```sh
kubectl -n platform exec deploy/homarr -- \
  wget -qO- https://auth.cc-chacchan.com/application/o/homarr/.well-known/openid-configuration
```

引けない場合は、チャートの `hostAliases` で Traefik の LB IP を
直接指す手がある (SNI は変わらないので証明書はそのまま通る)。

```yaml
hostAliases:
  - ip: "10.10.20.x"
    hostnames:
      - "auth.cc-chacchan.com"
```

### Kubernetes 連携ウィジェットは無効にしてある

`rbac.enabled: true` にすると、チャートが ServiceAccount と
**ClusterRole** (Pod / Secret / Node などのクラスタ全体の閲覧権限) を作り、
それを Homarr の Pod に渡す。ダッシュボードから見えて便利ではあるが
権限が広いので、必要になるまで無効のままにしてある。

### 秘密情報

`values.yaml` には書かない。`envSecrets` で参照している 3 つの Secret
(`homarr-db-encryption` / `homarr-oidc` / `homarr-db`) のマニフェストは
[`vault/homarr.yaml`](../../../vault/) にある — **git 追跡外**。
base64 は暗号化ではないので、git に入れたら平文と同じ。
