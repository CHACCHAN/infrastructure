# Apache Guacamole

ブラウザから RDP / VNC / SSH を触るためのリモートデスクトップゲートウェイ。

| 項目 | 値 |
| --- | --- |
| 上流チャート | **無し** (Deployment を直接書いている) |
| バージョン | **1.6.0** (`guacamole/guacamole` と `guacamole/guacd`) |
| Namespace | `platform` |
| ホスト名 | `guacamole.cc-chacchan.com` |
| DB | [postgresql/](../postgresql/) の `guacamole` DB |
| 認証 | Authentik の OIDC (implicit flow) + 退避用の `guacadmin` |
| 永続ボリューム | **無し** (状態はすべて PostgreSQL 側) |

## このディレクトリの構成

**このアプリは全部 kustomize が扱う。** 公式の Helm チャートが存在しないので、
[`_example/`](../_example/) のパターン (自前でマニフェストを書く) を採っている。
`helm template` の手順は無い。

| ファイル | 何を作るか |
| --- | --- |
| `guacd.yaml` | guacd の Deployment / Service |
| `guacamole.yaml` | WebUI の Deployment / Service |
| `ingress.yaml` | Ingress |
| `kustomization.yaml` | 上の 3 つを列挙 |

## 構成

```
ブラウザ ──HTTPS──> Traefik ──> guacamole (Tomcat :8080)
                                   │
                                   ├─4822─> guacd ──> RDP / VNC / SSH な機器
                                   │
                                   └─5432─> postgresql (guacamole DB)
```

**2 つのコンテナに分かれている。**

| | 役割 |
| --- | --- |
| `guacamole` | WebUI と認証。Tomcat の上で動く Java の webapp |
| `guacd` | プロトコルを実際に喋る側。RDP/VNC を描画して転送する |

`guacd` は外に出さない (Ingress を持たない)。
`guacamole` から `guacd.platform.svc.cluster.local:4822` で呼ばれるだけ。

**どちらも状態を持たない。** ユーザ・接続定義・接続履歴はすべて
PostgreSQL 側にあるので、PVC は 1 つも無い。

> **2 つのイメージのタグは必ず揃えること。** guacamole と guacd の間の
> プロトコルはバージョン間の互換性が保証されていない。

## 設定は全部環境変数

1.6.0 のイメージは entrypoint が環境変数から `guacamole.properties` を
組み立てる作りになっていて、**接頭辞の有無で拡張が入る**。

| 接頭辞 | 入る拡張 |
| --- | --- |
| `POSTGRESQL_` | JDBC 認証 (PostgreSQL) |
| `OPENID_` | OpenID Connect 認証 |
| `REMOTE_IP_VALVE_` | Tomcat の RemoteIpValve |

明示的に切りたいときは `<接頭辞>ENABLED=false` を渡す。
これを使ったのが `guacamole.yaml` の `OPENID_ENABLED`
(下の「Authentik が落ちたとき」)。

## 適用

### 1. Secret

[`vault/apache-guacamole.yaml`](../../../vault/) にマニフェストがある (git 追跡外)。

```sh
kubectl diff  -k vault
kubectl apply -k vault
```

`kubectl create secret` で作っても中身は同じ。

```sh
PW="$(kubectl -n platform get secret postgresql-superuser \
  -o jsonpath='{.data.postgres-password}' | base64 -d)"

kubectl -n platform create secret generic guacamole-db \
  --from-literal=db-password="$PW"

# Authentik で発行したクライアント ID (手順は 3.)。シークレットは無い。
kubectl -n platform create secret generic guacamole-oidc \
  --from-literal=oidc-client-id='...'
```

### 2. DB とスキーマを用意する

**ここだけ他のアプリと違う。** Guacamole は起動時にテーブルを作らない。
空の DB を用意したうえで、スキーマを流し込む必要がある。

```sh
# 2-1. 空の DB を作る
kubectl -n platform exec sts/postgresql -- \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c 'CREATE DATABASE guacamole;'

# 2-2. イメージからスキーマ SQL を取り出す
kubectl run guacamole-initdb --rm --attach --restart=Never --quiet \
  --image=guacamole/guacamole:1.6.0 \
  --command -- /opt/guacamole/bin/initdb.sh --postgresql \
  > /tmp/guacamole-schema.sql

# 2-3. 流し込む
kubectl -n platform exec -i sts/postgresql -- \
  psql -v ON_ERROR_STOP=1 -U postgres -d guacamole < /tmp/guacamole-schema.sql
```

確認。

```sh
kubectl -n platform exec sts/postgresql -- \
  psql -U postgres -d guacamole -c '\dt' | head
```

`guacamole_connection` や `guacamole_entity` が並んでいれば成功。

> **`CREATE DATABASE guacamole;` は
> [postgresql/values.yaml](../postgresql/values.yaml) の `customScripts`
> にも足してある。** ただしあれはデータディレクトリが空のときにしか
> 実行されないので、稼働中のクラスタでは上のとおり手で作る。
> スキーマのほうは `customScripts` に入れていない (SQL が数百行あるため)。
> **クラスタを作り直したときは 2-2 と 2-3 を必ずやること。**

### 3. Authentik 側の設定 (初回だけ)

`auth.cc-chacchan.com` (172.16.11.2) の管理画面で作る。

1. **Provider** — 種別 `OAuth2/OpenID Provider`
   - Client type: **`Public`**
   - Redirect URI (Strict): `https://guacamole.cc-chacchan.com/`
   - **Signing Key: 必ず選ぶ** (RS256 の証明書)
   - Scopes: `openid` `email` `profile`
2. **Application** — Slug は **`guacamole`**
   - `guacamole.yaml` の `OPENID_ISSUER` と `OPENID_JWKS_ENDPOINT` が
     この slug を含んでいるので、変えたら両方直す。
3. 発行された Client ID を `guacamole-oidc` に入れる。

> **Guacamole の OIDC は implicit flow。**
> 上流のドキュメントが
> *"Guacamole's OpenID Connect support implements the 'implicit flow'"*
> と明記していて、**クライアントシークレットを使わない**。
> だから Authentik 側も `Confidential` ではなく `Public` にする。
> Homarr / pgAdmin / Nextcloud とはここが違う。

> **Signing Key を空のままにしないこと。**
> Authentik は署名鍵が未設定だと id_token を HS256 (クライアント
> シークレットが鍵) で署名する。Guacamole は JWKS エンドポイントから
> 取った公開鍵で検証するので、その組み合わせでは必ず検証に失敗し、
> ログインできない。

> **Redirect URI は末尾スラッシュまで一致させること。**
> `guacamole.yaml` の `OPENID_REDIRECT_URI` は
> `https://guacamole.cc-chacchan.com/` (`WEBAPP_CONTEXT: ROOT` のため)。
> Strict 指定なので 1 文字でも違うと Authentik 側で弾かれる。

### 4. 本体と経路 (kustomize)

**helm は使わない。**

```sh
kubectl diff  -k .        # リポジトリのルートで
kubectl apply -k .
```

```sh
kubectl -n platform rollout status deploy/guacd
kubectl -n platform rollout status deploy/guacamole
```

Tomcat の起動と war の展開に少し時間がかかる。`startupProbe` に
`10s × 30 = 5 分`の猶予を持たせてある。

### 5. 最初の管理者を作る

スキーマが作る初期ユーザは **`guacadmin` / `guacadmin`** (パスワードも同じ)。
ただし `EXTENSION_PRIORITY: openid` にしてあるので、
ブラウザで開くと Authentik へ飛んでしまい、この画面に辿り着けない。

**手順はこう。**

1. まず Authentik でログインしてみる。`POSTGRESQL_AUTO_CREATE_ACCOUNTS`
   を `true` にしてあるので、DB 側に自分のアカウントが自動で作られる。
   この時点では権限が無いので「接続が 1 つも無い」画面になる。これで正しい。

2. OIDC を一時的に切る。`guacamole.yaml` の `OPENID_ENABLED` を
   `"false"` にして apply する。

   ```sh
   kubectl apply -k .
   kubectl -n platform rollout status deploy/guacamole
   ```

3. `guacadmin` / `guacadmin` でログインする。

4. **まず `guacadmin` のパスワードを変える。** 初期値のまま放置しない。

5. 「設定 > ユーザー」に 1. で作られた自分のアカウント
   (Authentik の `preferred_username`) が居るので、管理者権限を与える。

6. `OPENID_ENABLED` を `"true"` に戻して apply する。

以降は Authentik でログインして、そのまま管理できる。

## Authentik が落ちたとき

`guacamole.yaml` の `OPENID_ENABLED` を `"false"` にして apply すると、
OIDC 拡張が読み込まれなくなり、ローカルの `guacadmin` で入れる。

```sh
# platform/apps/apache-guacamole/guacamole.yaml を編集してから
kubectl apply -k .
kubectl -n platform rollout status deploy/guacamole
```

復旧したら `"true"` に戻すこと。

> **`kubectl set env` で切り替えないこと。** 次に `kubectl apply -k .` を
> 打った時点でマニフェストの値に戻り、理由の分からない挙動になる。
> マニフェストを直して apply するのが正しい。

## 接続を追加する

WebUI の「設定 > 接続」から追加する。マニフェストには書かない
(接続定義は DB の中にあり、kustomize の管理外)。

代表的なプロトコルと必要なポートは次のとおり。**接続先はクラスタの外**
(Proxmox 上の VM など) なので、k3s ノードからそこへ到達できる必要がある。

| プロトコル | ポート | 備考 |
| --- | --- | --- |
| RDP | 3389 | Windows。`security` は `nla` が既定 |
| VNC | 5900+ | Proxmox の VM コンソールなど |
| SSH | 22 | 端末だけなら一番軽い |

## 確認

```sh
kubectl -n platform get deploy guacd guacamole
kubectl -n platform get svc   guacd guacamole

# webapp から guacd が見えているか
kubectl -n platform exec deploy/guacamole -- \
  timeout 3 bash -c 'cat < /dev/null > /dev/tcp/guacd.platform.svc.cluster.local/4822' \
  && echo "guacd reachable"

# 拡張が読み込まれたか (openid と postgresql の 2 つ)
kubectl -n platform logs deploy/guacamole | grep -i "extension"

curl -s -o /dev/null -w '%{http_code}\n' https://guacamole.cc-chacchan.com/   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://guacamole.cc-chacchan.com/    # 404 が正しい
```

## 気をつけること

### レプリカを増やすならセッションアフィニティが要る

`guacamole` は 1 レプリカにしてある。Tomcat のセッションがメモリ上に
あるので、増やすと接続ごとに別 Pod へ飛んで認証が切れる。

増やす場合は Service に `sessionAffinity: ClientIP` を付けるか、
Traefik 側でスティッキーセッションを設定すること。

`guacd` のほうもレプリカを増やせるが、**稼働中のセッションは
特定の guacd Pod に紐づいている**ので、Pod が入れ替わるとその
セッションは切れる。増やしても既存セッションの冗長化にはならない。

### WebSocket を塞がない

画面転送は `/websocket-tunnel` の WebSocket で流れる。Traefik は
素通しするので追加の設定は要らないが、**Ingress に Authentik の
forwardAuth Middleware を付けると通らなくなる。**
認証は Guacamole 自身の OIDC で完結させている。

### ユーザ名のクレームを後から変えない

`OPENID_USERNAME_CLAIM_TYPE` を `preferred_username` にしてある
(既定は `email`)。**これを変えると同じ人が別ユーザとして扱われる。**
DB 側の既存ユーザに割り当てた接続権限が全部外れるので、
運用を始めたあとは変えないこと。

### 接続履歴の送信元 IP

`REMOTE_IP_VALVE_ENABLED: "true"` を入れてあるので、Tomcat が
`X-Forwarded-For` を見て本当のクライアント IP を記録する。
これが無いと接続履歴の送信元が全部 Traefik の Pod IP になる。

`internalProxies` は指定していない。Tomcat の既定の正規表現が
`10.x.x.x` を含んでいて、k3s の Pod CIDR (`10.42.0.0/16`) が
その中に入るため。

`X-Forwarded-Proto` も見せている。これが無いと Tomcat が
「HTTP で来た」と判断し、OIDC のリダイレクト URI とセッションクッキーが
`http://` で組み立てられてログインが一周しない。

### `guacadmin` を消さない

OIDC が使えなくなったときの唯一の入り口。**パスワードは必ず変えたうえで、
アカウント自体は残しておくこと。** 消すと `OPENID_ENABLED: "false"` に
しても入れなくなり、DB を直接触ることになる。

### バックアップ

PVC が無いので、**DB がすべて**。接続定義もユーザも権限もここにある。

```sh
kubectl -n platform exec sts/postgresql -- \
  pg_dump -U postgres -d guacamole --clean > guacamole-$(date +%F).sql   # リポジトリには入れない
```

RDP の接続パスワードも `guacamole_connection_parameter` に平文で入っている。
**このダンプはリポジトリに置かないこと。**

## バージョンを上げる

1. `guacd.yaml` と `guacamole.yaml` の `image` タグを**両方同時に**変える
2. **この README の表のバージョンも書き換える**
3. `kubectl diff -k .` で差分を確認する
4. `kubectl apply -k .`

```sh
curl -s 'https://hub.docker.com/v2/repositories/guacamole/guacamole/tags?page_size=20' \
  | jq -r '.results[].name'
```

> **DB スキーマの移行が要る場合がある。** マイナー更新でも
> `guacamole_*` テーブルに変更が入ることがあり、その場合は
> 上流が用意する `upgrade/upgrade-pre-X.Y.Z.sql` を流す必要がある。
> リリースノートを確認すること。
>
> **上げる前に `pg_dump -d guacamole` を取っておくこと。**
