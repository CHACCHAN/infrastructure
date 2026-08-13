# PostgreSQL

`platform` namespace 共用の PostgreSQL。

| 項目 | 値 |
| --- | --- |
| チャート | `groundhog2k/postgres` |
| バージョン | **1.6.7** (イメージは `postgres:16.14` に固定) |
| Namespace | `platform` |
| 接続先 | `postgresql.platform.svc.cluster.local:5432` |
| ストレージ | PVC `postgres-data-postgresql-0` (`truenas-nfs` 200Gi) |
| 設定 | [`values.yaml`](values.yaml) |
| 公開経路 | **無し** (Ingress を持たない) |

## 利用しているアプリ

| DB | 使う人 | 用途 |
| --- | --- | --- |
| `homarr` | [homarr/](../homarr/) | ダッシュボードの設定・ユーザ |
| `awx` | [ansible-awx/](../ansible-awx/) | AWX 本体の DB |
| `pgadmin` | [pgadmin/](../pgadmin/) | pgAdmin 自身の設定 DB |
| `nextcloud` | [nextcloud/](../nextcloud/) | ファイル・共有・ユーザのメタデータ |
| `guacamole` | [apache-guacamole/](../apache-guacamole/) | 接続定義・ユーザ・接続履歴 |

**ロールは分けていない。** どのアプリも `postgres` ユーザで自分の DB に繋ぐ。
ここが持つのは「空の DB を 5 つ用意すること」だけで、
中身 (ユーザ・認証情報) の管理はアプリ側の責任。

> **`guacamole` だけはスキーマも要る。** 他のアプリは起動時に自分で
> テーブルを作るが、Guacamole は作らない。空の DB を用意したうえで、
> `initdb.sh` が吐く SQL を流し込む
> ([apache-guacamole/README.md](../apache-guacamole/README.md))。

`pgadmin` は「PostgreSQL を管理する UI」であると同時に「この PostgreSQL を
使うアプリ」でもある。**pgAdmin の設定 DB がこの中にあるので、
PostgreSQL が落ちると pgAdmin にもログインできない。**

## このディレクトリの構成

**このアプリには `kustomization.yaml` も `ingress.yaml` も無い。**
Traefik の Ingress は HTTP しか通せず、PostgreSQL は素の TCP なので
経路を作れない。WebUI から触りたい場合は [pgadmin/](../pgadmin/) を使う。

そのため kustomize が扱うものが 1 つも無く、
`platform/apps/kustomization.yaml` にも書いていない。

| ファイル | 何を作るか | 適用方法 |
| --- | --- | --- |
| `values.yaml` | StatefulSet / Service / PVC / ConfigMap | **helm template → kubectl apply** |

## なぜこのチャートなのか

`groundhog2k/postgres` は **公式の `postgres` イメージ**
(`docker.io/library/postgres`) をそのまま使う薄いラッパー。
DB を作る初期化スクリプトも `values.yaml` に書ける。

他の候補を採らなかった理由:

- **`bitnami/postgresql`** — 2025 年 8 月に無償カタログが `latest` タグ
  のみになった。最新のチャートは `image.tag: latest` を埋め込んでいて、
  過去の固定タグ (`18.4.0-debian-12-r0` など) は
  Docker Hub から消えている (`not found`)。
  このリポジトリの「`latest` は使わない」という方針と両立しない。
  `bitnamilegacy/` に退避されたイメージを指せば動くが、
  そちらは更新されないので DB には向かない。
- **CloudNativePG** — 良いものだが Operator + CRD が増え、
  AWX と同じ「CRD を先に入れて待つ」手順も生える。
  1 インスタンスを共有するだけの用途には大きい。

## 適用

### 1. Secret

**この DB のパスワードは 1 つだけ。** `postgresql-superuser` の
`postgres-password` を決めて、それを利用側 3 つの接続情報にも書く。

マニフェストは [`vault/`](../../../vault/) にある (git 追跡外)。

```sh
kubectl diff  -k vault
kubectl apply -k vault
```

`kubectl create secret` で作っても中身は同じ。

```sh
PW="$(openssl rand -base64 24 | tr -d '/+=')"

kubectl -n platform create secret generic postgresql-superuser \
  --from-literal=postgres-password="$PW"

kubectl -n platform create secret generic homarr-db \
  --from-literal=db-url="postgresql://postgres:${PW}@postgresql.platform.svc.cluster.local:5432/homarr"

kubectl -n platform create secret generic pgadmin-db \
  --from-literal=PGADMIN_DB_URI="postgresql://postgres:${PW}@postgresql.platform.svc.cluster.local:5432/pgadmin"

kubectl -n platform create secret generic nextcloud-db \
  --from-literal=db-hostname=postgresql.platform.svc.cluster.local \
  --from-literal=db-name=nextcloud \
  --from-literal=db-username=postgres \
  --from-literal=db-password="$PW"

kubectl -n platform create secret generic guacamole-db \
  --from-literal=db-password="$PW"

kubectl -n platform create secret generic awx-postgres-configuration \
  --from-literal=host=postgresql.platform.svc.cluster.local \
  --from-literal=port=5432 \
  --from-literal=database=awx \
  --from-literal=username=postgres \
  --from-literal=password="$PW" \
  --from-literal=sslmode=prefer \
  --from-literal=type=unmanaged

echo "$PW"   # パスワードマネージャ等に控える
```

> **`tr -d '/+='` を挟んでいる理由。**
> AWX は「パスワードに `'` `"` `\` を含めてはいけない」と明記している。
> また `/` や `@` は接続 URL の区切りとぶつかる。
> 記号を落として英数字だけにしておくのがいちばん事故が少ない。

### 2. 本体 (helm)

Helm は**テンプレートを展開するためだけ**に使う。
リリースとしてはインストールしないので、`helm list` には出てこない。

```sh
helm repo add groundhog2k https://groundhog2k.github.io/helm-charts/
helm repo update

helm template postgresql groundhog2k/postgres \
  --version 1.6.7 \
  --namespace platform \
  --values platform/apps/postgresql/values.yaml \
  | kubectl apply --server-side --namespace platform -f -
```

リポジトリのルートから実行すること。

**`kubectl apply` 側にも `--namespace platform` が要る。**
このチャートは `metadata.namespace` を出力しないので、
付け忘れると `default` に落ちる。

```sh
kubectl -n platform rollout status sts/postgresql
```

**アプリより先に入れる必要は無い。** DB がまだ無い間、アプリの Pod は
起動に失敗するが、kubelet がそのまま再試行し続ける。
PostgreSQL が上がれば勝手に繋がる。

## 設定を変える

```sh
vim platform/apps/postgresql/values.yaml

# 何が変わるか確認する (クラスタは変わらない)
helm template postgresql groundhog2k/postgres \
  --version 1.6.7 -n platform \
  --values platform/apps/postgresql/values.yaml \
  | kubectl diff --namespace platform -f -

# 適用
helm template postgresql groundhog2k/postgres \
  --version 1.6.7 -n platform \
  --values platform/apps/postgresql/values.yaml \
  | kubectl apply --server-side --namespace platform -f -
```

`values.yaml` には上流の既定値との**差分だけ**を書いている。
既定値の全体はこれで見られる。

```sh
helm show values groundhog2k/postgres --version 1.6.7
```

## 確認

```sh
kubectl -n platform get sts postgresql
kubectl -n platform get pvc postgres-data-postgresql-0

# DB が揃っているか
kubectl -n platform exec sts/postgresql -- psql -U postgres -c '\l'
```

`homarr` / `awx` / `pgadmin` / `nextcloud` / `guacamole` の 5 つが
並んでいれば成功。

**既に稼働している PostgreSQL には `nextcloud` と `guacamole` が無い。**
初回起動スクリプトは 2 回目以降実行されないため、手で作る (次節)。

## 気をつけること

### 初回起動スクリプトは 2 回目以降実行されない

`/docker-entrypoint-initdb.d/` は **データディレクトリが空のときだけ**
実行される。すでに DB がある状態で `values.yaml` の `customScripts` を
書き換えても、何も起きない。

DB を後から足す場合は psql で直接作る。

```sh
kubectl -n platform exec sts/postgresql -- \
  psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c 'CREATE DATABASE myapp;'
```

**あわせて `values.yaml` の `customScripts` にも追記しておくこと。**
クラスタを作り直したときに再現しなくなる。

### アプリごとにロールを分けていない

どのアプリも `postgres` ユーザで繋ぐので、**どのアプリからも
他のアプリの DB が見える**。ロールを分ければ隔離できるが、
同じパスワードを DB 側とアプリ側の 2 か所に書くことになり、
ずれたときの事故のほうが大きい。管理者が 1 人のクラスタなので分けていない。

隔離が要るようになったら、`CREATE ROLE` して各アプリの接続情報を
そちらに向ける。DB は既にあるので `ALTER DATABASE ... OWNER TO` で足りる。

### レプリカを増やしてはいけない

レプリケーションの設定は何もしていない。`replicas: 2` にすると、
2 つ目の Pod は RWO の PVC を掴めずに起動しないか、
別ノードで掴めてしまった場合は同じデータディレクトリを
2 プロセスで開いて DB が壊れる。

冗長化が要るようになったら CloudNativePG を検討する。

### PGDATA はマウントポイントそのものにしない

PostgreSQL はデータディレクトリのパーミッションが `0700` でないと
起動を拒否する。NFS プロビジョナが作るディレクトリは `0777` なので、
`PGDATA` をマウントポイント (`/var/lib/postgresql/data`) にすると

```
FATAL:  data directory "/var/lib/postgresql/data" has invalid permissions
```

で起動しない。チャートは `settings.dataDir` + `settings.pgDir` を
`PGDATA` にしていて、マウントするのは `dataDir` のほう。
`initdb` 自身が `pg/` を `0700` で作る。**この 2 つは既定のまま触らない。**

### alpine イメージは使えない

チャート既定の `securityContext` は `runAsUser: 999` で、これは
**debian 版** の postgres ユーザの uid。alpine 版は uid 70 なので、
`image.tag` を `-alpine` にすると起動しない。

```sh
docker run --rm --entrypoint sh postgres:16.14-alpine -c 'id postgres'  # uid=70
docker run --rm --entrypoint sh postgres:16.14        -c 'id postgres'  # uid=999
```

どうしても alpine を使いたい場合は `securityContext` の
`runAsUser` / `runAsGroup` と `podSecurityContext` の
`fsGroup` / `supplementalGroups` をすべて 70 に変える。

### NFS の上で動かしている

このクラスタの永続ストレージは TrueNAS の NFS しかない。
SQLite ほど致命的ではなく (PostgreSQL は自前のロック機構を持っていて、
NFS 上での運用も公式に想定されている) が、注意点はある。

- **`hard` マウントであること。** `soft` だと I/O タイムアウトが
  「書けたかどうか分からない」形でアプリに返り、破損の原因になる。
  k8s の NFS マウントは既定で `hard` なので、既定のまま触らない。
- **性能は出ない。** fsync がネットワーク越しになる。
  この規模 (homarr / AWX / pgAdmin) なら問題にならない。

### バックアップ

PVC の実体は TrueNAS 上の
`/mnt/Storage/Kubernetes/platform-postgres-data-postgresql-0-*` にある。
スナップショットだけでも復旧はできるが、
**論理バックアップも取っておくほうが確実**。

```sh
kubectl -n platform exec sts/postgresql -- \
  pg_dumpall -U postgres --clean > postgresql-$(date +%F).sql   # リポジトリには入れない
```

### PVC のサイズは後から広げられない (縮められない)

NFS の StorageClass は expansion に対応していない。
`volumeClaimTemplates` は StatefulSet 作成後に変更もできないので、
広げたい場合は退避して作り直すことになる。

## バージョンを上げる

**チャートのバージョンと PostgreSQL のバージョンは別。**
`values.yaml` の `image.tag` で明示的に固定してあるので、
チャートを上げても PostgreSQL は動かない。

### チャート (1.6.7)

1. `--version` を新しい値にする
2. **この README の表とコマンド例のバージョンも書き換える**
3. `| kubectl diff --namespace platform -f -` で差分を確認する
4. `| kubectl apply --server-side --namespace platform -f -`
5. **Service 名とポート名が変わっていないか確認する**

5 が重要。利用側は `postgresql.platform.svc.cluster.local:5432` を
直接書いている (vault/ の接続情報)。

```sh
helm search repo groundhog2k/postgres --versions | head
```

### PostgreSQL 本体 (16.14)

**メジャーバージョンをまたぐ更新はタグを変えるだけではできない。**
データディレクトリの形式が違うので、起動時に

```
FATAL:  database files are incompatible with server
```

で止まる。`pg_dumpall` で吸い出して、新しい PVC に入れ直すこと。

マイナー更新 (16.14 → 16.15 など) はタグを変えるだけでよい。

**16 系にしているのは AWX の都合。** AWX 24.6.1 が同梱する PostgreSQL は
15 で、上流が動作確認しているのもそのバージョンだけ。
外部 DB として使う分には新しいバージョンでも動くとされているが、
18 まで上げるのは検証されていない範囲に入る。
チャートの appVersion は 18.4 だが、`image.tag` で 16.14 に固定している。
