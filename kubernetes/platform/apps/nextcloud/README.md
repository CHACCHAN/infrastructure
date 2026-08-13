# Nextcloud

ファイル共有 / グループウェア。

| 項目 | 値 |
| --- | --- |
| チャート | `nextcloud/nextcloud` |
| バージョン | **9.2.5** (Nextcloud 34.0.2, flavor `apache`) |
| Namespace | `platform` |
| ホスト名 | `nextcloud.cc-chacchan.com` |
| DB | [postgresql/](../postgresql/) の `nextcloud` DB |
| ファイルの実体 | **External Storage** (WebUI から後で追加する) |
| 自身の領域 | PVC `nextcloud-nextcloud` (`truenas-nfs` 20Gi) |
| 認証 | Authentik の OIDC (`user_oidc`) + 退避用ローカル管理者 |
| 設定 | [`values.yaml`](values.yaml) |
| 公開経路 | [`ingress.yaml`](ingress.yaml) |

## このディレクトリの構成

**本体と経路で適用方法が違う。**

| ファイル | 何を作るか | 適用方法 |
| --- | --- | --- |
| `values.yaml` | Deployment / Service / PVC / ConfigMap | **helm template → kubectl apply** |
| `ingress.yaml` | Ingress | `kubectl apply -k .` (kustomize) |
| `kustomization.yaml` | `ingress.yaml` だけを列挙 | — |

## ストレージの考え方

**2 種類ある。混ぜないこと。**

| | 置き場 | 何が入るか |
| --- | --- | --- |
| Nextcloud 自身の領域 | PVC `nextcloud-nextcloud` (`truenas-nfs` 20Gi) | 本体のソース、インストールしたアプリ、`config/`、プレビュー、バージョン履歴 |
| ユーザのファイル | **External Storage** | 共有したいファイルの実体 |

PVC のほうは `/var/www/html` にマウントされる。20Gi にしてあるのは
「本体 + アプリで 2GB ほど、残りはプレビューとバージョン履歴の余裕」という
見積もりで、ユーザのファイルを置く前提の数字ではない。

External Storage は **WebUI から追加する**。`files_external` は
Nextcloud 34 に同梱されていて、管理画面の「管理者設定 > 外部ストレージ」から
有効化して設定する。CLI から入れるなら次のとおり。

```sh
kubectl -n platform exec deploy/nextcloud -- \
  su -s /bin/sh www-data -c 'php occ app:enable files_external'
```

> **20Gi という数字はほぼ名目値。** `nfs-subdir-external-provisioner` が
> 作るのは NFS 共有の下のディレクトリで、この容量を強制する仕組みは無い
> (StorageClass は `allowVolumeExpansion: true`)。
> 実際の上限は TrueNAS 側のデータセットの空き容量になる。

## 適用

**入れる順番は気にしなくてよい。** Secret や DB が揃っていない間は
Pod が起動に失敗するが、kubelet が再試行し続けるので、
あとから足せば勝手に立ち上がる。

### 1. Secret

[`vault/nextcloud.yaml`](../../../vault/) にマニフェストがある (git 追跡外)。

```sh
kubectl diff  -k vault
kubectl apply -k vault
```

`kubectl create secret` で作っても中身は同じ。

```sh
PW="$(kubectl -n platform get secret postgresql-superuser \
  -o jsonpath='{.data.postgres-password}' | base64 -d)"

# 退避用のローカル管理者
kubectl -n platform create secret generic nextcloud-admin \
  --from-literal=nextcloud-username='admin' \
  --from-literal=nextcloud-password="$(openssl rand -base64 24 | tr -d '/+=')"

# 共用 PostgreSQL の接続情報
kubectl -n platform create secret generic nextcloud-db \
  --from-literal=db-hostname=postgresql.platform.svc.cluster.local \
  --from-literal=db-name=nextcloud \
  --from-literal=db-username=postgres \
  --from-literal=db-password="$PW"

# Authentik で発行したクライアント資格情報 (手順は 3.)
kubectl -n platform create secret generic nextcloud-oidc \
  --from-literal=oidc-client-id='...' \
  --from-literal=oidc-client-secret='...'
```

### 2. DB を用意する

**既に稼働している PostgreSQL には `nextcloud` DB が無い。**
[postgresql/values.yaml](../postgresql/values.yaml) の `customScripts` に
足してあるが、**あれはデータディレクトリが空のときにしか実行されない**。
稼働中のクラスタでは psql で作る。

```sh
kubectl -n platform exec sts/postgresql -- \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c 'CREATE DATABASE nextcloud;'
```

確認。

```sh
kubectl -n platform exec sts/postgresql -- psql -U postgres -c '\l' | grep nextcloud
```

### 3. Authentik 側の設定 (初回だけ)

`auth.cc-chacchan.com` (172.16.11.2) の管理画面で作る。

1. **Provider** — 種別 `OAuth2/OpenID Provider`
   - Client type: `Confidential`
   - Redirect URI (Strict): `https://nextcloud.cc-chacchan.com/apps/user_oidc/code`
   - Signing Key: 任意の証明書
   - Scopes: `openid` `email` `profile`
2. **Application** — Slug は **`nextcloud`**
   - `values.yaml` の `--discoveryuri` が
     `https://auth.cc-chacchan.com/application/o/nextcloud/.well-known/openid-configuration`
     なので、slug を変えたら values 側も直す。
3. 発行された Client ID / Secret を `nextcloud-oidc` に入れる。

> **コールバック URL は `/apps/user_oidc/code`。**
> Homarr (`/api/auth/callback/oidc`) や pgAdmin (`/oauth2/authorize`) とは
> 違うので、Authentik 側で使い回さないこと。

### 4. 本体 (helm)

```sh
helm repo add nextcloud https://nextcloud.github.io/helm/
helm repo update

helm template nextcloud nextcloud/nextcloud \
  --version 9.2.5 \
  --namespace platform \
  --values platform/apps/nextcloud/values.yaml \
  | kubectl apply --server-side --namespace platform -f -
```

リポジトリのルートから実行すること。

**`kubectl apply` 側にも `--namespace platform` が要る。**
このチャートは `metadata.namespace` を出力しないので、
付け忘れると `default` に落ちる。
(pgAdmin や Portainer のチャートとはここが違う)

```sh
kubectl -n platform rollout status deploy/nextcloud --timeout=2h
```

**初回起動は 1 時間前後かかる。** entrypoint が Nextcloud 本体一式
(30,214 ファイル / 868 MB) を NFS 上の `/var/www/html` へ rsync するため。
NFS は小さいファイルの作成が 32 ms/個 と遅く、ここが律速になる。

`values.yaml` の `startupProbe` に `10s × 720 = 2 時間`の猶予を
持たせてあるので、放っておけば立ち上がる。**進まないように見えても
Pod を消して作り直さないこと。** rsync は途中から再開できるが、
作り直すと最初からやり直しになる。

詳しい実測値と速くする手段は「気をつけること」の
[初回起動に 1 時間前後かかる](#初回起動に-1-時間前後かかる-nfs-の小ファイル性能) を参照。

### 5. 経路 (kustomize)

```sh
kubectl apply -k .        # リポジトリのルートで
```

## 認証 (OIDC)

普段のログインは Authentik。ログイン画面に
「Login with authentik」のボタンと、ローカルのユーザ名/パスワード欄の
両方が出る。ローカルのほうは **Authentik が落ちたときの退避経路**で、
Homarr / pgAdmin と同じ考え方。

### どう設定されるか

Nextcloud には OIDC の設定を環境変数で入れる仕組みが無く、チャートにも
値が用意されていない。公式アプリ [`user_oidc`](https://github.com/nextcloud/user_oidc)
を入れて `occ` で設定する。

そのスクリプトは `values.yaml` の `nextcloud.hooks.before-starting` にある。
チャートがこれを ConfigMap にして、`0755` で
`/docker-entrypoint-hooks.d/before-starting/helm.sh` にマウントし、
イメージの entrypoint が実行する。**設定は values.yaml に閉じている。**

**5 つあるフックのうち `before-starting` を選んでいる。**
これだけがインストール/アップグレードの有無にかかわらず毎回の起動で走る。
`post-installation` は初回だけ、`post-upgrade` はバージョンが上がったときだけで、
設定を変えて再起動しても反映されない。

`occ user_oidc:provider` は upsert なので、毎回走っても
既にその通りなら何も変わらない。

cron sidecar では走らない。あちらは `command: [/cron.sh]` で
イメージの ENTRYPOINT を置き換えているため、二重実行にはならない。

### 失敗しても起動は止まらない

アプリストアに繋がらない、Authentik が落ちている、といった理由で
Nextcloud 全体が `CrashLoopBackOff` になるほうが困るので、
フックは失敗しても `exit 0` する。

```sh
kubectl -n platform logs deploy/nextcloud -c nextcloud | grep helm-hook
```

- `OIDC provider 'authentik' is configured.` — 成功
- `WARNING: failed to configure OIDC.` — 失敗。ローカル管理者では入れる

失敗していたら、同じコマンドを手で叩いて原因を見る。

```sh
kubectl -n platform exec deploy/nextcloud -- \
  su -s /bin/sh www-data -c 'php occ user_oidc:provider'   # 登録済み一覧
```

### 秘密情報

`values.yaml` には書かない。Client ID / Secret は Secret `nextcloud-oidc`
から環境変数 (`NEXTCLOUD_OIDC_CLIENT_ID` / `NEXTCLOUD_OIDC_CLIENT_SECRET`)
で渡している。

**シークレットは `--clientsecret` ではなく `--clientsecret-env` で渡している。**
コマンドライン引数にすると Pod の `ps` と occ のログに平文で出るため。

### OIDC 一本に絞る

ローカルのログイン欄を消して Authentik へ直行させたい場合は、
`values.yaml` のフック内の `allow_multiple_user_backends` を `0` にする。

```sh
php occ config:app:set user_oidc allow_multiple_user_backends --value=0
```

そのときの退避経路は `https://nextcloud.cc-chacchan.com/login?direct=1`。
**このパラメータを忘れると、Authentik が落ちたときに誰も入れなくなる。**

## 設定を変える

すべて `values.yaml` にある。

```sh
vim platform/apps/nextcloud/values.yaml

helm template nextcloud nextcloud/nextcloud \
  --version 9.2.5 -n platform \
  --values platform/apps/nextcloud/values.yaml \
  | kubectl diff --namespace platform -f -

helm template nextcloud nextcloud/nextcloud \
  --version 9.2.5 -n platform \
  --values platform/apps/nextcloud/values.yaml \
  | kubectl apply --server-side --namespace platform -f -
```

`hooks.before-starting` を書き換えた場合、チャートが Deployment に
`hooks-hash` アノテーションを付けているので **apply しただけで
Pod が入れ替わる**。手動の rollout restart は要らない。

既定値の全体はこれで見られる。

```sh
helm show values nextcloud/nextcloud --version 9.2.5
```

## 確認

```sh
kubectl -n platform rollout status deploy/nextcloud
kubectl -n platform get pvc nextcloud-nextcloud

# DB にテーブルができているか (SQLite ではなく)
kubectl -n platform exec sts/postgresql -- psql -U postgres -d nextcloud -c '\dt' | head

curl -s -o /dev/null -w '%{http_code}\n' https://nextcloud.cc-chacchan.com/   # 302
curl -s -o /dev/null -w '%{http_code}\n' http://nextcloud.cc-chacchan.com/    # 404 が正しい
```

`oc_users` などのテーブルが並んでいれば DB の切り替えは成功している。

そのあと WebUI の **管理者設定 > 概要 (設定チェック)** を見る。
ここに出る警告が、リバースプロキシまわりの設定が効いているかの答え合わせになる。

## 気をつけること

### Redis を入れていない

チャート同梱の Redis は bitnami のサブチャート (`bitnamilegacy/redis`) で、
[postgresql/README.md](../postgresql/README.md) に書いたのと同じ理由
(2025 年 8 月に無償カタログが `latest` タグだけになった) で使えない。
外部 Redis も今は無いので、`redis` / `externalRedis` の両方を無効にしてある。

影響は次の 2 つ。

- **ローカルキャッシュは APCu**。チャートの `apcu.config.php` が設定するので
  これは効いている。設定チェックでメモリキャッシュの警告は出ない。
- **ファイルロックが DB ベースになる**。`memcache.locking` が設定されないため。
  利用者 1 人規模なら問題にならないが、同じファイルへの同時書き込みが
  増えると PostgreSQL の負荷になる。

必要になったら Redis を別途立てて `externalRedis` に向ける。

> チャートには不具合があり、`redis.enabled: false` でも `REDIS_URL` という
> env が 1 つ残る (`REDIS_URL` を出すブロックが `redis.enabled` の外にある)。
> 参照先の `REDIS_HOST` が未定義なので `$(...)` は展開されず、値としては
> 無意味なまま残るだけ。イメージ側の `redis.config.php` は `REDIS_HOST` を
> 見ているので、Redis の設定は入らない。**動作に影響は無い。**
> `values.yaml` で `redis.auth.enabled: false` にして、
> 認証情報らしき形にならないようにしてある。

### リバースプロキシまわり

Traefik が TLS を終端して Pod へは平文 HTTP で渡すので、
そのままだと Nextcloud が自分の URL を `http://` で組み立てる。
`values.yaml` で次を入れてある。

| 設定 | 何のため |
| --- | --- |
| `phpClientHttpsFix.enabled: true` | `OVERWRITEPROTOCOL=https`。無いと iOS/Android クライアントと WebDAV が mixed content で落ちる |
| `TRUSTED_PROXIES=10.42.0.0/16` | k3s の Pod CIDR。無いと全アクセスの送信元が Traefik の Pod IP に見え、ブルートフォース対策が誤作動する |
| `OVERWRITECLIURL` | cron sidecar は Ingress を通らないので、メール通知等のリンクのベース URL を教える |

クライアント IP の書き換え自体はイメージ側の `mod_remoteip` が
`X-Real-IP` を見てやっている。既定で `10.0.0.0/8` を信頼していて
Pod CIDR がその中に入るので、`APACHE_DISABLE_REWRITE_IP` は設定していない。

### `/.well-known/` の警告

設定チェックに `/.well-known/caldav` や `/.well-known/webfinger` が
解決できないという警告が出た場合は、Traefik 側でリダイレクトを足す。
apache flavor は `.htaccess` でこれを処理するので通常は出ないが、
出たときは `platform/` に Middleware を 1 つ置いて Ingress に付ける。

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: nextcloud-wellknown
  namespace: platform
spec:
  redirectRegex:
    regex: "^https://([^/]+)/\\.well-known/(card|cal)dav"
    replacement: "https://${1}/remote.php/dav/"
    permanent: true
```

```yaml
traefik.ingress.kubernetes.io/router.middlewares: "platform-nextcloud-wellknown@kubernetescrd"
```

### Ingress に forwardAuth を付けない

Authentik の forwardAuth Middleware は **付けてはいけない**。
デスクトップ / モバイルクライアントと WebDAV はブラウザのリダイレクトを
辿れないので、前段で認証を挟むと繋がらなくなる。
SSO は Nextcloud 側の `user_oidc` で完結させている。

### 初回起動に 1 時間前後かかる (NFS の小ファイル性能)

**これがこの構成でいちばん厄介な点。**

entrypoint は起動のたびに本体一式を rsync で `/var/www/html` に展開する。
rsync が終わるまで Apache は起動せず、`:80` は connection refused のまま。

```sh
rsync -rlDog --chown www-data:www-data --delete \
  --exclude-from=/upgrade.exclude /usr/src/nextcloud/ /var/www/html/
```

この構成での実測値 (k3s-worker04 → TrueNAS 10.10.20.10, nfs4.2)。

| 測ったもの | 結果 |
| --- | --- |
| 逐次書き込み (128MB 1 ファイル) | **113 MB/s** |
| 小さいファイルの作成 (NFS) | **32 ms/個 = 30〜41 個/s** |
| 小さいファイルの作成 (コンテナのローカル) | **21,051 個/s** |
| Nextcloud 34.0.2 の本体 | **30,214 ファイル / 868 MB** |

**帯域は問題ない。** 868 MB を 1 ファイルで書けば 8 秒で終わる。
効いているのは 1 ファイルあたり 32 ms のメタデータ往復のほうで、
rsync は 1 ファイルにつき
`open(O_CREAT|O_EXCL)` → `write` → `fchmodat` → `lchown` → `rename` と
4〜5 回往復するため、**30214 × 4 × 32ms ≒ 65 分**かかる。

そのため `startupProbe` は `10s × 720 = 2 時間`にしてある。

> **`failureThreshold` を小さくしないこと。**
> 以前 `60` (= 10 分) にしていたときは、初回同期が終わる前に kubelet が
> コンテナを SIGKILL し、再起動 → rsync が最初からやり直し → また 10 分で
> 殺される、という無限ループになった。ログが
> `Initializing nextcloud 34.0.2.1 ...` で止まったまま進まないように見え、
> `rsync` が D state (`rpc_wait_bit_killable`) で張り付くので
> NFS のハングと紛らわしいが、**実際には正常に進んでいて時間が
> 足りていないだけ**だった。

進み具合はこれで見られる。30214 に近づいていけば正常。

```sh
kubectl -n platform exec deploy/nextcloud -c nextcloud -- \
  sh -c 'find /var/www/html | wc -l'
```

**この確認コマンドを何度も叩かないこと。** `find` 自体が NFS の
往復を数万回発生させ、rsync から RPC を奪って同期を遅くする。
見るなら数分に 1 回にする。

同じ理由で、**アップグレード直後の 1 回目の起動も同じだけ遅い**。
`rollout status` には `--timeout=2h` を付けること。

#### 速くしたい場合

32 ms/op は、10GbE 相当の帯域が出ている (113 MB/s) こととあわせて考えると
ネットワーク遅延ではなく、**ZFS が同期書き込みを毎回コミットしている**
時間とみてよい。効く順に並べると次のとおり。

1. **TrueNAS 側にSLOG を足す** (NVMe など)。32 ms が 1〜2 ms 台になれば
   初回同期は数分で終わる。PostgreSQL 含め他のアプリにも効く。
2. データセットの `sync=disabled`。同じ効果だが、**電断時に直近の
   書き込みが消える**。
3. `/var/www/html` を NFS から外す。本体 3 万ファイルはイメージから
   毎回再生成されるので、本来 NFS に置く必要が無い
   (config / data / custom_apps / themes だけ残せばよい)。
   ただし**このチャートの values では表現できない。**
   全マウントが単一ボリューム `nextcloud-main` にハードコードされていて、
   `html` の subPath だけ emptyDir にする値が用意されていないため。
   やるならレンダリング結果に kustomize でパッチを当てることになり、
   このリポジトリの「helm template → 直接 apply」の流儀から外れる。

### cron は sidecar

`cronjob.type: sidecar` にしてある。PVC が `ReadWriteOnce` なので、
別 Pod の CronJob は本体と違うノードに載ると `/var/www/html` を
マウントできない。sidecar なら必ず同じ Pod なのでその事故が起きない。

crond は root が要るが、apache flavor は root で起動するので問題ない。

### レプリカを増やしてはいけない

`/var/www/html` が `ReadWriteOnce` の PVC なので、2 つ目の Pod は
掴めずに起動しない。`strategy` も既定の `Recreate` のままにしてある
(RollingUpdate だと更新のたびに新旧 Pod がデッドロックする)。

増やしたい場合は `persistence.accessMode` を `ReadWriteMany` にする
(`truenas-nfs` は NFS なので RWX が使える)。ただしその場合は
ファイルロックのために Redis がほぼ必須になる。

### PVC を消すとデータが消える

チャートは PVC に `helm.sh/resource-policy: keep` を付けているが、
これは helm リリースとして運用している場合の話。
このリポジトリは `helm template` で展開しているだけなので関係ない。

`kubectl apply` で PVC が消えることはない。
**`kubectl delete` を PVC に対して打たないこと。**

### バックアップ

PVC の実体は TrueNAS 上の
`/mnt/Storage/Kubernetes/platform-nextcloud-nextcloud-*` にある。
**DB のほうが本体**なので、そちらも取ること。

```sh
kubectl -n platform exec sts/postgresql -- \
  pg_dump -U postgres -d nextcloud --clean > nextcloud-$(date +%F).sql   # リポジトリには入れない
```

External Storage に置いたファイルは Nextcloud の管理外なので、
**そのストレージ側でバックアップを取ること。**

## バージョンを上げる

**チャートのバージョンと Nextcloud のバージョンは別。**
`values.yaml` の `image.tag` で明示的に固定してあるので、
チャートを上げても Nextcloud は動かない。

### 手順

1. `--version` を新しい値にする
2. `values.yaml` の `image.tag` を新しい appVersion に合わせる
3. **この README の表とコマンド例のバージョンも書き換える**
4. `| kubectl diff --namespace platform -f -` で差分を確認する
5. `| kubectl apply --server-side --namespace platform -f -`
6. **Service のポート名が変わっていないか確認する**

6 が重要。`ingress.yaml` はポートを**名前** (`http`) で参照している。

```sh
kubectl -n platform get svc nextcloud -o jsonpath='{.spec.ports}' | jq
```

```sh
helm search repo nextcloud/nextcloud --versions | head
```

> **メジャーバージョンを飛ばさないこと。** Nextcloud は 1 つずつしか
> アップグレードできない (33 → 34 は可、33 → 35 は不可)。
> `image.tag` を 2 つ先にすると entrypoint が
> `Can't start Nextcloud because the version of the data is higher` で止まる。
>
> **上げる前に `pg_dump -d nextcloud` を取っておくこと。**
