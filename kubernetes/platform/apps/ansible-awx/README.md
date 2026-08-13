# AWX

Ansible の WebUI / API (旧 Ansible Tower の upstream)。

| 項目 | 値 |
| --- | --- |
| チャート | `awx-operator/awx-operator` |
| バージョン | **3.2.1** (AWX Operator 2.19.1 / AWX 24.6.1) |
| Namespace | `platform` |
| ホスト名 | `ansible.cc-chacchan.com` |
| DB | [postgresql/](../postgresql/) の `awx` DB (Operator に作らせない) |
| 認証 | ローカルアカウント + Authentik の OIDC |
| 設定 | [`values.yaml`](values.yaml) |
| 公開経路 | [`ingress.yaml`](ingress.yaml) |

## 他のアプリと違うところ

**このチャートは AWX 本体を入れない。** 入れるのは Operator と CRD で、
AWX 本体は Operator が作る。

```
values.yaml  --(helm template)-->  AWX リソース  --(Operator が見て作る)-->  Deployment / StatefulSet / Service
```

Portainer のように `helm template` の出力がそのまま最終形にはならない。
`kubectl apply` した直後に見えるのは AWX リソース 1 個だけで、
Pod が揃うまで **3〜5 分**かかる。

この構造から来る注意点が 2 つある。

1. **`helm template` に `--include-crds` が要る。** CRD は `crds/` にあり、
   `helm template` は既定で出力しない。付け忘れると AWX リソースの
   apply が `no matches for kind "AWX"` で落ちる。
2. **CRD と AWX リソースを同時に apply できない。** CRD が有効になるのは
   非同期なので、初回は Operator だけ入れて待つ (下の手順 2 と 3)。

**2 はこのリポジトリで数少ない「順序が要る」ところ。**
Pod の起動失敗は kubelet が再試行してくれるが、
`kubectl apply` そのものが弾かれるとリソースは作られず、
誰も再試行しない。

## このディレクトリの構成

**本体と経路で適用方法が違う。**

| ファイル | 何を作るか | 適用方法 |
| --- | --- | --- |
| `values.yaml` | CRD / Operator / AWX リソース | **helm template → kubectl apply** |
| `ingress.yaml` | Ingress | `kubectl apply -k .` (kustomize) |
| `kustomization.yaml` | `ingress.yaml` だけを列挙 | — |

Ingress を Operator に任せず自分で書いているのは、TLS・entrypoints・
Middleware の書き方をリポジトリ全体で 1 か所に揃えるため。
そのため `values.yaml` では `ingress_type: none` にしてある。

## 適用

Helm は**テンプレートを展開するためだけ**に使う。
リリースとしてはインストールしないので、`helm list` には出てこない。

```sh
helm repo add awx-operator https://ansible-community.github.io/awx-operator-helm/
helm repo update
```

以下はすべてリポジトリのルートから実行する。

### 0. DB

**AWX の DB は Operator に作らせていない。**
[postgresql/](../postgresql/) の `awx` DB を使う
(`values.yaml` の `postgres_configuration_secret`)。
接続情報は [`vault/ansible-awx.yaml`](../../../vault/) (git 追跡外)。

DB がまだ無くても apply はできる。Operator の migration タスクが
繋がるまでリトライし続けるだけなので、あとから PostgreSQL を
立てても組み上がる。ただし `kubectl wait awx/awx` はその間
返ってこないので、待つなら先に DB を用意しておくほうが早い。

### 1. Secret と Authentik (初回のみ)

OIDC を既定で有効にしてあるので、Secret `awx-oidc` が要る。
**無いと Pod がボリュームをマウントできず起動しない**
(あとから作れば kubelet が拾う)。

中身は [`vault/ansible-awx.yaml`](../../../vault/) (git 追跡外)。

```sh
kubectl diff  -k vault
kubectl apply -k vault
```

Authentik (`auth.cc-chacchan.com`) 側で作るもの:

1. **Provider** — 種別 `OAuth2/OpenID Provider`
   - Client type: `Confidential`
   - Redirect URI (Strict): `https://ansible.cc-chacchan.com/sso/complete/oidc/`
   - Signing Key: 任意の証明書
   - Scopes: `openid` `profile` `email`
     (social-core の既定。AWX 側でスコープは変えられない)
2. **Application** — Slug は **`awx`**
   - `values.yaml` の `SOCIAL_AUTH_OIDC_OIDC_ENDPOINT` が
     `https://auth.cc-chacchan.com/application/o/awx` なので、
     slug を変えたら values 側も直す。
3. 発行された Client ID / Secret を `awx-oidc` の `oidc.py` に入れる。

> **プロバイダ URL に末尾スラッシュを付けないこと。**
> social-core が
> `f"{OIDC_ENDPOINT}/.well-known/openid-configuration"`
> と連結するので、付けると `//` になって discovery に失敗する。
> **Homarr は逆に末尾スラッシュが要る。** 実装が違うので揃わない。

| アプリ | issuer / endpoint の末尾スラッシュ | コールバック |
| --- | --- | --- |
| AWX | **付けない** | `/sso/complete/oidc/` |
| Homarr | **付ける** | `/api/auth/callback/oidc` |
| pgAdmin | (discovery URL を直接指定) | `/oauth2/authorize` |

### 2. CRD と Operator (初回のみ)

`--set AWX.enabled=false` で AWX リソースを出力から外し、
CRD と Operator だけを先に入れる。

```sh
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 \
  --namespace platform \
  --values platform/apps/ansible-awx/values.yaml \
  --include-crds \
  --set AWX.enabled=false \
  | kubectl apply --server-side --namespace platform -f -
```

> **`kubectl apply` 側の `--namespace platform` は必須。**
> このチャートは Operator 側のリソースに `metadata.namespace` を出力しない。
> 付け忘れると `default` に入る (nfs-provisioner と同じ挙動)。

### 3. CRD が有効になるまで待つ

```sh
kubectl wait --for=condition=Established crd/awxs.awx.ansible.com --timeout=120s
kubectl -n platform rollout status deploy/awx-operator-controller-manager
```

### 4. AWX 本体 (AWX リソース)

`--set` を外して同じコマンドを打つ。手順 2 の内容も含んだ上位集合なので、
2 回目以降はこれだけでよい。

```sh
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 \
  --namespace platform \
  --values platform/apps/ansible-awx/values.yaml \
  --include-crds \
  | kubectl apply --server-side --namespace platform -f -
```

Operator が作り終わるまで待つ。migration の Job が走るので数分かかる。

```sh
kubectl -n platform wait awx/awx --for=condition=Successful --timeout=900s
```

### 5. 経路 (kustomize)

```sh
kubectl apply -k .        # リポジトリのルートで
```

## 初回ログイン

ユーザー名は `admin`。パスワードは Operator が生成して Secret に入れる。

```sh
kubectl -n platform get secret awx-admin-password \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

パスワードは WebUI から変更できる。変更しても**この Secret の中身は
古いまま残る** (Operator は初期パスワードとしてしか使わない)。

## 消してはいけない Secret

次の 3 つは失うと復旧に手間がかかる。

| Secret | 中身 | 誰が作るか | 失うと |
| --- | --- | --- | --- |
| `awx-secret-key` | DB 内の暗号化に使う共通鍵 | Operator が生成 | 登録済みの認証情報がすべて復号できなくなる |
| `awx-postgres-configuration` | 外部 DB の接続情報とパスワード | **自分で作る** | DB に繋がらなくなる |
| `awx-oidc` | OIDC のクライアント資格情報 | **自分で作る** | Pod が起動しない (再発行はできる) |

**クラスタを作り直すときは、PVC ではなくこれらを先に退避する。**
とくに `awx-secret-key` を無くすと、DB が無事でも Machine / Vault / SCM の
認証情報が全滅する (Operator が生成するので vault/ には無い)。

```sh
kubectl -n platform get secret awx-secret-key awx-postgres-configuration awx-oidc \
  -o yaml > vault/awx-generated-backup.yaml   # vault/ は git 追跡外
```

退避したものから復元する場合は、AWX リソースを作る**前**に
Secret を戻しておく。存在すれば Operator は生成せずそれを使う。

## 設定を変える

`values.yaml` の `AWX.spec` が、そのまま AWX リソースの spec になる。
書ける項目は上流のドキュメントを見ること。

<https://ansible.readthedocs.io/projects/awx-operator/en/latest/user-guide/>

```sh
vim platform/apps/ansible-awx/values.yaml

# 何が変わるか確認する (クラスタは変わらない)
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 -n platform \
  --values platform/apps/ansible-awx/values.yaml --include-crds \
  | kubectl diff --namespace platform -f -

# 適用
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 -n platform \
  --values platform/apps/ansible-awx/values.yaml --include-crds \
  | kubectl apply --server-side --namespace platform -f -
```

apply しても即座には反映されない。Operator が AWX リソースの変更に
気づいて Deployment を作り直すまで待つ。

```sh
kubectl -n platform logs deploy/awx-operator-controller-manager -c awx-manager -f
```

### AWX.name は変えられない

子リソースの名前がすべて `AWX.name` から決まる (`awx-service`、
`awx-web`、`awx-task`、`awx-secret-key` など)。
変えると Operator は「別の AWX」として一式を新規に作り、
古い方は消さずに残す。実質やり直しになる。

`ingress.yaml` の backend も `awx-service` を指しているので、
変えるならそちらも直す。

### DB を Operator に管理させていない

`postgres_configuration_secret` を書いてあるので、Operator は
postgres の StatefulSet を作らない (`type: unmanaged`)。
そのため `postgres_storage_class` や `postgres_resource_requirements`
といった項目は**書いても効かない**。DB 側の設定は
[`../postgresql/values.yaml`](../postgresql/values.yaml) にある。

**managed から unmanaged へ切り替えてもデータは引き継がれない。**
以前 Operator が作った DB があるなら、先に吸い出して入れ直すこと。

```sh
# 旧 (Operator 管理) から吸い出す
kubectl -n platform exec sts/awx-postgres-15 -- \
  pg_dump -U awx -d awx --clean --if-exists > awx.sql

# 共用 PostgreSQL へ入れる
kubectl -n platform exec -i sts/postgresql -- psql -U postgres -d awx < awx.sql
```

移行後、古い StatefulSet と PVC は自動では消えない。
中身を確認してから個別に消す (`kubectl delete sts awx-postgres-15` など)。

### OIDC の設定は UI から変えられない

`extra_settings` と `extra_settings_files` に書いた設定は、AWX 側で
**read-only** として扱われる。Settings → Generic OIDC の画面には出るが、
グレーアウトしていて保存できない。

変更するときはリポジトリ側を直す。

| 変えたいもの | どこ |
| --- | --- |
| プロバイダ URL / SSL 検証 | `values.yaml` の `extra_settings` |
| Client ID / Secret | `vault/ansible-awx.yaml` の `oidc.py` |

`vault/` 側を変えた場合は Pod を作り直す (起動時にしか読まない)。

```sh
kubectl apply -k vault
kubectl -n platform delete pod -l app.kubernetes.io/name=awx-web
kubectl -n platform delete pod -l app.kubernetes.io/name=awx-task
```

### OIDC でログインしたユーザには権限が付かない

AWX の Generic OIDC には設定が 4 つしかなく、**組織やチームへの
マッピングが無い** (LDAP や SAML にはある `ORGANIZATION_MAP` /
`TEAM_MAP` が OIDC には存在しない)。

初回ログインでユーザは作られるが、どの組織にも属さないので
何も見えない状態になる。`admin` でログインして手で割り当てること。

**そのためローカルの `admin` は残しておく。** OIDC だけにすると、
新規ユーザに権限を与える人がいなくなる。
(Authentik はクラスタ外なので、落ちたときの退避経路としても要る)

### プロジェクトを手動で置きたい場合

既定では Git などから取得する前提で、共有ボリュームを持たない。
`/var/lib/awx/projects` に直接置きたい場合は `values.yaml` に足す。

```yaml
    projects_persistence: true
    projects_storage_class: truenas-nfs
    projects_storage_access_mode: ReadWriteMany
    projects_storage_size: 8Gi
```

## バージョンを上げる

1. 上のコマンドの `--version` を新しい値にする
2. **この README の表とコマンド例のバージョンも書き換える**
3. `| kubectl diff --namespace platform -f -` で差分を確認する
4. `| kubectl apply --server-side --namespace platform -f -`
5. **CRD の差分を確認する。** Operator の更新では CRD も一緒に変わる。
6. **Service のポート名が変わっていないか確認する**

6 が重要。`ingress.yaml` はポートを**名前** (`http`) で参照している。

```sh
kubectl -n platform get svc awx-service -o jsonpath='{.spec.ports}' | jq
```

名前が変わっていたら `ingress.yaml` も直す。

```sh
helm search repo awx-operator/awx-operator --versions | head
```

> AWX 本体 (`quay.io/ansible/awx`) のバージョンは Operator が決める。
> Operator 2.19.1 は AWX 24.6.1 を入れる。個別に固定したい場合は
> `AWX.spec.image` / `image_version` を書くが、Operator が想定していない
> 組み合わせになるので通常は Operator ごと上げる。

## 確認

```sh
kubectl -n platform get awx awx
kubectl -n platform rollout status deploy/awx-web
kubectl -n platform rollout status deploy/awx-task
# DB は共用の PostgreSQL 側にある。AWX 用の postgres Pod は作られない。
kubectl -n platform exec sts/postgresql -- psql -U postgres -d awx -c '\dt' | head

curl -s https://ansible.cc-chacchan.com/api/v2/ping/ | jq              # version が返る
curl -s -o /dev/null -w '%{http_code}\n' https://ansible.cc-chacchan.com/   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://ansible.cc-chacchan.com/    # 404 が正しい
```

## 詰まりやすいところ

### ログイン画面で「CSRF 検証に失敗しました」

TLS を Traefik で終端していて AWX 自身は平文 HTTP で受けているため、
Django から見た Origin (`https://...`) と自分の認識 (`http`) が食い違う。
`values.yaml` の `extra_settings` で `CSRF_TRUSTED_ORIGINS` を渡して
回避している。**ホスト名を変えるときはここも直す。**

### `Unable to retrieve some image pull secrets (redhat-operators-pull-secret)`

Operator の Pod に出るイベント。上流チャートが Red Hat のレジストリ用に
`imagePullSecrets` を無条件で付けているため。使っているイメージはすべて
公開なので、警告が出るだけで動作に影響はない。

### Pod がスケジュールされない

`values.yaml` で requests を上流の既定より下げてある。それでも足りない場合、
AWX の Pod は web / task で合わせて 2Gi 前後を要求する。

```sh
kubectl -n platform describe pod -l app.kubernetes.io/name=awx-web | tail -20
```

## 削除する場合はhelm templateを展開したものを使って削除する
```sh
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 \
  --namespace platform \
  --values platform/apps/ansible-awx/values.yaml \
  --include-crds \
  --set AWX.enabled=false \
| kubectl delete --namespace platform -f -
```
