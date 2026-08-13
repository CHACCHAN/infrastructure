# Kubernetes システム

k3s クラスタ上で稼働させるリソースの定義を管理するリポジトリ。
いつでも同じ状態を再構築できることを目的とする。

構成管理は **素のマニフェスト + Kustomize**。
上流 Helm チャートを使う 7 つだけ、`helm template` で展開して kubectl に流す。
**Helm リリースは作らない。**

## クラスタ

| 項目 | 値 |
| --- | --- |
| ディストリビューション | k3s (Traefik v3 同梱) |
| Ingress Controller | Traefik |
| 証明書 | cert-manager + Let's Encrypt (Cloudflare DNS-01) のワイルドカード |
| 永続ストレージ | TrueNAS NFS `10.10.20.10:/mnt/Storage/Kubernetes` (StorageClass `truenas-nfs`) |
| 既定 StorageClass | `local-path` (ノードローカル。永続用途では使わない) |
| 外部公開 | Cloudflare Tunnel (`auth` / `api.cc-chacchan.com`)。他は LAN 内のみ |

## 管理方法は 2 つある

**どちらで管理されているかを最初に把握すること。** 更新手順が違う。

| | Kustomize | 上流 Helm チャート |
| --- | --- | --- |
| 対象 | 経路・証明書・Namespace・cloudflared・自前コンテナ | cert-manager / NFS プロビジョナ / Portainer 本体 / AWX / Homarr / pgAdmin / PostgreSQL |
| 置き場所 | `namespaces/` `platform/` `cloudflare/` | `system/*/` `platform/apps/` の portainer / ansible-awx / homarr / pgadmin / postgresql |
| リポジトリにあるもの | マニフェストそのもの | `values.yaml` + `README.md` のみ |
| 適用 | `kubectl apply -k .` | `helm template ... \| kubectl apply -f -` |
| 手順 | 下記 | 各ディレクトリの `README.md` |

### Kustomize 側の適用は Ansible 経由 (リポジトリルートで実行)

```sh
ansible-playbook playbooks/k8s/apply.yml --check --diff   # 稼働中との差分を見る (クラスタに触らない)
ansible-playbook playbooks/k8s/apply.yml                  # 適用する (server-side apply)
```

**適用前には必ず `--check --diff` を見る**。
レンダリング結果だけ見たいときは `kubectl kustomize kubernetes/` も使える。

初回や `kubectl apply` を手で使った後は、フィールド所有者の衝突
(`FieldManagerConflict`) が出ることがある。差分が実質ゼロであることを
`--check --diff` で確認したうえで `-e force=true` を付けると所有権を引き継げる
(一度通せば以後は不要)。

`kubectl delete -k .` は使わない。クラスタを丸ごと消す。
不要になったリソースは、マニフェストを消したうえで
`kubectl delete <kind> <name>` と個別に指定して消す。

### 秘密情報は vault/ にある

Secret のマニフェストは [`vault/`](vault/) にまとめてある。
**`README.md` を除いて git 追跡外**なので、`git clone` した直後は空。
何が要るかは [`vault/README.md`](vault/README.md) の表を見ること。

```sh
ansible-playbook playbooks/k8s/apply-vault.yml --check    # 差分の有無だけ確認 (--diffは平文が出るため注意)
ansible-playbook playbooks/k8s/apply-vault.yml            # 適用する
```

> **適用前に、手元の `vault/*.yml` が稼働中より新しいことを必ず確認する。**
> 古いファイルのまま流すと稼働中の Secret を潰す。

ルートの `kustomization.yaml` からは意図的に外してある。
`apply.yml` では秘密情報は流れない。

### Helm 側

各 README にコマンドがそのまま書いてある。

- [`system/README.md`](system/README.md) — 7 つまとめた手順と注意点
- [`system/cert-manager/README.md`](system/cert-manager/README.md)
- [`system/nfs-provisioner/README.md`](system/nfs-provisioner/README.md)
- [`platform/apps/portainer/README.md`](platform/apps/portainer/README.md)
- [`platform/apps/ansible-awx/README.md`](platform/apps/ansible-awx/README.md)
- [`platform/apps/homarr/README.md`](platform/apps/homarr/README.md)
- [`platform/apps/pgadmin/README.md`](platform/apps/pgadmin/README.md)
- [`platform/apps/postgresql/README.md`](platform/apps/postgresql/README.md)

> **`kubectl apply` の `--namespace` はチャートごとに要否が逆になる。**
> cert-manager は付けるとエラー、nfs-provisioner と awx-operator と homarr は
> 付けないと `default` に落ちる。README のコマンドをそのまま使うこと。

> **`platform/apps/postgresql/` だけは `ingress.yaml` を持たない。**
> Traefik の Ingress は HTTP しか通せず、PostgreSQL は素の TCP なので
> 経路を作れない。kustomize 側は空で、すべて helm 側にある。

> **AWX だけは「チャートがアプリを入れる」構造になっていない。**
> チャートが入れるのは Operator と CRD で、AWX 本体は Operator が作る。
> `--include-crds` が要る点も含めて
> [`platform/apps/ansible-awx/README.md`](platform/apps/ansible-awx/README.md) を読むこと。

## 考え方

このクラスタで公開するサービスは 2 種類しかない。

1. **external** — クラスタ外 (独立 VM 等) で動いていて、Traefik でリバースプロキシするだけのもの
2. **apps** — k3s 上にデプロイして動かすもの

| やりたいこと | 置き場所 | ひな形 / 手順 |
| --- | --- | --- |
| クラスタ外の VM を Traefik で公開する | `platform/external/<名前>/` | [`_example/`](platform/external/_example/) |
| 自前コンテナ (GHCR 等) を動かす | `platform/apps/<名前>/` | [`_example/`](platform/apps/_example/) |
| 上流チャートがあるアプリ | `platform/apps/<名前>/` | [portainer/](platform/apps/portainer/) を真似る |

**Ingress は必ずリポジトリ側で書く**。上流チャートの `ingress:` は使わない
(`values.yaml` 側で `enabled: false` にする)。経路の書き方を 1 箇所に保つためで、
TLS や Authentik 連携をアプリごとに書き分けなくて済む。

## ディレクトリ構成

```
.
├── kustomization.yaml      Kustomize 側のエントリポイント
│
├── namespaces/             Namespace の定義 (ここに集約する)
│
├── system/                 上流 Helm チャートで入れるクラスタ基盤
│   ├── README.md           ★ 7 つまとめた適用手順
│   ├── cert-manager/       values.yaml + README.md のみ
│   └── nfs-provisioner/    values.yaml + README.md のみ
│
├── platform/               platform namespace
│   ├── certificates/       ClusterIssuer / Certificate
│   ├── external/           クラスタ外サービスの経路
│   │   ├── _example/       ひな形 (コピーして使う)
│   │   └── authentik/ proxmox/ truenas/ wg-easy/ technitium/ cloudflare-ddns-ui/
│   └── apps/               k3s 上のアプリ
│       ├── _example/       自前コンテナのひな形 (コピーして使う)
│       ├── ansible-awx/    values.yaml + README.md + ingress.yaml
│       ├── homarr/         values.yaml + README.md + ingress.yaml
│       ├── pgadmin/        values.yaml + README.md + ingress.yaml
│       ├── portainer/      values.yaml + README.md + ingress.yaml
│       └── postgresql/     ★ 共用 DB。values.yaml + README.md のみ
│
├── cloudflare/
│   └── cloudflared/        Cloudflare Tunnel コネクタ
│
├── vault/                  秘密情報 (Secret マニフェスト)
│                           ★ README.md 以外は git 追跡外
│
├── docs/
│   └── MIGRATION.md        Helm から Kustomize へ移行したときの記録
│
└── .legacy/                さらに前の構成の置き場。現行クラスタには適用しない
```

### 配置ルール

- **`_example/` で始まるディレクトリは適用されない**。親の `kustomization.yaml` に
  意図的に含めていない。コピーして使う。
- **上流チャートのバージョンは各 README にしか書いていない**。
  上げるときは README の表とコマンド例の両方を直す。
- **Namespace はアプリ側で作らない**。`namespaces/` に集約する。
- **イメージタグに `latest` を使わない**。`imagePullPolicy` も明示する。
- **秘密情報は `vault/` に置く**。アプリのディレクトリには書かない。
  `vault/` は `README.md` を除いて git 追跡外
  ([`vault/README.md`](vault/README.md))。
- 拡張子は `.yaml` に統一する。

## デプロイ済みのサービス

### external (Traefik でリバースプロキシ)

| サービス | ホスト名 | バックエンド | 備考 |
| --- | --- | --- | --- |
| Authentik | `auth.cc-chacchan.com` | `172.16.11.2:9000` | forwardAuth Middleware を提供 |
| Proxmox VE | `pve01`〜`pve05.cc-chacchan.com` | `172.16.11.11-15:8006` | 自己署名 HTTPS |
| TrueNAS | `nas.cc-chacchan.com` | `172.16.11.10:443` | 自己署名 HTTPS |
| WG-Easy | `wgui.cc-chacchan.com` | `172.16.11.5:51821` | WebUI のみ |
| Technitium DNS | `dns` / `doh.cc-chacchan.com` | `172.16.11.3:5380,8053` | |
| Cloudflare DDNS UI | `ddns.cc-chacchan.com` | `172.16.11.4:8080` | Authentik で保護 |
| Supabase | `supabase.cc-chacchan.com` | `172.16.11.6:3000` | ダッシュボード。LAN 内のみ |
| Supabase API | `api.cc-chacchan.com` | `172.16.11.6:8000` | Kong。Cloudflare Tunnel で外部公開 |

### apps / system

| コンポーネント | Namespace | 管理方法 |
| --- | --- | --- |
| Portainer CE (`portainer.cc-chacchan.com`) | `platform` | Helm 239.5.0 + Ingress は kustomize |
| AWX (`ansible.cc-chacchan.com`) | `platform` | Helm 3.2.1 (Operator 経由) + Ingress は kustomize。認証は Authentik の OIDC |
| Homarr (`homarr.cc-chacchan.com`) | `platform` | Helm 8.26.0 + Ingress は kustomize。認証は Authentik の OIDC |
| pgAdmin (`pgadmin.cc-chacchan.com`) | `platform` | Helm 1.66.0 + Ingress は kustomize。認証は Authentik の OIDC |
| PostgreSQL (公開なし) | `platform` | Helm 1.6.7 (`postgres:16.14`)。homarr / AWX / pgAdmin の共用 DB |
| cert-manager | `cert-manager` | Helm v1.21.0 |
| NFS プロビジョナ | `storage` | Helm 4.0.18 |
| cloudflared | `cloudflare` | kustomize |
| Traefik | `kube-system` | **k3s が管理**。このリポジトリの管理外 |

## サービスを 1 つ追加する

### クラスタ外のサービス

```sh
cp -r platform/external/_example platform/external/myapp
```

置換する箇所と、Authentik 連携や自己署名 HTTPS のパターンは
[`platform/external/_example/README.md`](platform/external/_example/README.md) に書いてある。
最後に `platform/external/kustomization.yaml` へ 1 行足す。

### 自前コンテナ (GHCR 等)

```sh
cp -r platform/apps/_example platform/apps/myapp
```

詳しくは [`platform/apps/_example/README.md`](platform/apps/_example/README.md)。

GHCR のプライベートイメージは、k3s ノードの `/etc/rancher/k3s/registries.yaml`
に認証情報があるため **`imagePullSecrets` は通常不要**。
秘密情報はマニフェストに書かず、`kubectl create secret` して `envFrom` で読む。

### 上流チャートがあるアプリ

[`platform/apps/portainer/`](platform/apps/portainer/) を真似る。

1. `platform/apps/<名前>/values.yaml` を書く (`ingress.enabled: false` を忘れない)
2. `platform/apps/<名前>/README.md` に適用コマンドを書く
   — **`--namespace` の要否をレンダリング結果で確認して書くこと**
3. `platform/apps/<名前>/ingress.yaml` と `kustomization.yaml` を書く
4. `platform/apps/kustomization.yaml` に 1 行足す

## 新規構築

クラスタを 1 から作る場合。

**大半は順序を気にしなくてよい。** Secret / ConfigMap / DB が揃っていない
間、Pod は `CreateContainerConfigError` や `CrashLoopBackOff` で止まるが、
kubelet がそのまま再試行し続けるので、あとから足せば勝手に立ち上がる。

順序が要るのは `kubectl apply` そのものが弾かれる 2 か所だけ。
弾かれたリソースは作られず、誰も再試行しない。

| 待つもの | 待たないと |
| --- | --- |
| cert-manager の webhook | `ClusterIssuer` / `Certificate` の apply が webhook に拒否される |
| AWX の CRD が Established | AWX リソースの apply が `no matches for kind "AWX"` で落ちる |

```sh
# 1. Namespace
kubectl apply -k namespaces

# 2. 秘密情報 (リポジトリには入っていない)
#    vault/ の YAML に値を入れてから適用する。
#    何をどこに書くかは vault/README.md にまとめてある。
#    Authentik の OIDC クライアントは先に発行しておくこと。
kubectl diff  -k vault     # 空のまま流さないよう必ず確認する
kubectl apply -k vault

# 3. Helm リポジトリ
helm repo add jetstack https://charts.jetstack.io
helm repo add nfs-subdir-external-provisioner \
  https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
helm repo add portainer https://portainer.github.io/k8s/
helm repo add awx-operator https://ansible-community.github.io/awx-operator-helm/
helm repo add runix https://helm.runix.net
helm repo add groundhog2k https://groundhog2k.github.io/helm-charts/
helm repo add homarr-labs https://homarr-labs.github.io/charts/
helm repo update

# 4. cert-manager を先に (--namespace を付けない)
helm template cert-manager jetstack/cert-manager \
  --version v1.21.0 -n cert-manager \
  --values system/cert-manager/values.yaml --no-hooks \
  | kubectl apply --server-side -f -

# 5. webhook が応答するまで待つ (CRD の検証に必要)
kubectl -n cert-manager wait --for=condition=Available deploy --all --timeout=180s

# 6. NFS プロビジョナ (--namespace storage が必須)
helm template nfs nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --version 4.0.18 -n storage \
  --values system/nfs-provisioner/values.yaml --no-hooks \
  | kubectl apply --server-side --namespace storage -f -

# 7. PostgreSQL (--namespace platform が必須)
helm template postgresql groundhog2k/postgres \
  --version 1.6.7 -n platform \
  --values platform/apps/postgresql/values.yaml \
  | kubectl apply --server-side --namespace platform -f -

# 8. Portainer 本体
helm template portainer portainer/portainer \
  --version 239.5.0 -n platform \
  --values platform/apps/portainer/values.yaml --no-hooks \
  | kubectl apply --server-side -f -

# 9. AWX Operator と CRD (--namespace platform が必須)
#    ここでは AWX 本体を作らない。CRD が有効になるのを待つ必要があるため。
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 -n platform \
  --values platform/apps/ansible-awx/values.yaml --include-crds \
  --set AWX.enabled=false \
  | kubectl apply --server-side --namespace platform -f -

kubectl wait --for=condition=Established crd/awxs.awx.ansible.com --timeout=120s
kubectl -n platform rollout status deploy/awx-operator-controller-manager

# 10. AWX 本体 (--set を外して同じコマンド)
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 -n platform \
  --values platform/apps/ansible-awx/values.yaml --include-crds \
  | kubectl apply --server-side --namespace platform -f -

# 11. Homarr (--namespace platform が必須)
helm template homarr homarr-labs/homarr \
  --version 8.26.0 -n platform \
  --values platform/apps/homarr/values.yaml \
  | kubectl apply --server-side --namespace platform -f -

# 12. pgAdmin
helm template pgadmin runix/pgadmin4 \
  --version 1.66.0 -n platform \
  --values platform/apps/pgadmin/values.yaml --no-hooks \
  | kubectl apply --server-side -f -

# 13. 残り全部 (経路・証明書・cloudflared)
kubectl apply -k . --server-side

# 14. 証明書が発行されるまで待つ
kubectl -n platform wait --for=condition=Ready certificate/cc-chacchan-wildcard --timeout=300s

# 15. AWX が組み上がるまで待つ (DB 接続と migration が走るので数分)
kubectl -n platform wait awx/awx --for=condition=Successful --timeout=900s
```

2 回目以降は、変えたものだけを適用すればよい。

> `--server-side` を付けているのは、フィールドの所有者を kubectl に一本化するため。
> 付けなくても動くが、混在させると次の apply で所有権の衝突警告が出る。

## 運用メモ

### `kubectl diff -k .` が見ているのは一部だけ

Kustomize 管理下 (経路・証明書・Namespace・cloudflared) しか比較しない。
cert-manager / NFS / Portainer 本体 / AWX / Homarr / pgAdmin / PostgreSQL
の差分は出ない。
そちらは各 README の `| kubectl diff -f -` で確認する。

### Kustomize は「余分なものを消す」ことをしない

マニフェストを消しても、クラスタ上のリソースは残り続ける。
定期的に突き合わせて、消し忘れの残骸がないか見る。

```sh
diff <(kubectl kustomize . | grep -A2 '^kind: Ingress' | grep '  name:' | awk '{print $2}' | sort) \
     <(kubectl -n platform get ingress -o name | sed 's#.*/##' | sort)
```

### HTTP (平文) での公開について

Ingress には既定で `router.entrypoints: websecure` が付き、**HTTPS でしか
公開されない**。`web` (平文 :80) も受けているのは、Cloudflare Tunnel で
外部公開している 2 本だけ。

| Ingress | ホスト名 | entrypoints |
| --- | --- | --- |
| `authentik` | `auth.cc-chacchan.com` | `web,websecure` |
| `supabase-api` | `api.cc-chacchan.com` | `web,websecure` |

これは cloudflared のオリジンが
`http://traefik.kube-system.svc.cluster.local:80` に固定されているためで、
Cloudflare 側の設定を `https://` + `noTLSVerify` に変更すれば
両方の `entrypoints` から `web` を削れる。

**トンネルに載せるホスト名は Cloudflare 側で管理されており、このリポジトリには
含まれない。** Ingress を足しただけでは外部公開されないし、逆に `web` を受ける
Ingress を足しても、トンネルに経路がなければ外からは届かない。
LAN 内限定にしたい経路は `websecure` のみにしておく (Traefik 側の意思表示)。

Traefik 側で web → websecure の常時リダイレクトを有効にするのは、
上記のトンネル設定を直すまでは**リダイレクトループになるので入れないこと**。

### 証明書の namespace

TLS Secret は namespace をまたげない。`platform` 以外の namespace で
サービスを公開する場合は、その namespace 用の `Certificate` を
`platform/certificates/` に追加する。

### Traefik には触らない

`kube-system` の `traefik` / `traefik-crd` は k3s が HelmChart CRD で管理している。
このリポジトリの管理外で、`helm list -A` に出てくるのはそのため。
設定を変えるときは k3s の `HelmChartConfig` を使う。

### `helm.sh/chart` ラベルが残っている件

`helm template` の出力をそのまま適用しているので、Portainer や cert-manager の
リソースには `helm.sh/chart` や `app.kubernetes.io/managed-by: Helm` という
ラベルが付いている。

**このクラスタに Helm リリースは存在しない**。上流チャートが付けているラベルが
そのまま残っているだけで、実際の管理は kubectl が行っている。

### `.legacy/`

さらに前の構成 (生マニフェストを直接 `kubectl apply` していた時代) の置き場。
現行クラスタには適用しない。

> **注意: `.legacy/` には秘密鍵と Secret マニフェストが git 追跡されたまま入っている**
> (`infrastructure/jupyter-lab/jupyterhub/tls.key` など)。
> 既に履歴に入っているため `.gitignore` では消えない。
> 該当する鍵・認証情報はすべて失効済みとして扱い、再利用しないこと。
