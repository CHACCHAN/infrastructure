# system/

上流 Helm チャートで入れるクラスタ基盤。

| ディレクトリ | 何を入れるか | Namespace |
| --- | --- | --- |
| [`cert-manager/`](cert-manager/) | 証明書の自動発行 / 更新 | `cert-manager` |
| [`nfs-provisioner/`](nfs-provisioner/) | StorageClass `truenas-nfs` | `storage` |

Portainer / AWX / Homarr / pgAdmin / PostgreSQL も上流チャートだが、
公開経路とセットで扱うほうが分かりやすいので
[`platform/apps/`](../platform/apps/) 側に置いてある。

**[`platform/apps/postgresql/`](../platform/apps/postgresql/) だけは
`ingress.yaml` を持たない。** Traefik の Ingress は HTTP しか通せず、
PostgreSQL は素の TCP なので経路を作れない。すべて helm 側にある。

## ここだけ kustomize ではない

このリポジトリは基本的に素のマニフェスト + Kustomize で管理している。
ただし上流チャートを展開する機能が Kustomize にはないので、
**この 7 つだけ helm でレンダリングして kubectl に流す**。

```
helm template ... --values values.yaml --no-hooks | kubectl apply --server-side -f -
        ↑                                                    ↑
   展開するだけ                                        適用するのは kubectl
```

**Helm リリースは作らない。** `helm list -A` に出てくるのは
k3s が管理している `traefik` / `traefik-crd` だけ。

各ディレクトリには `values.yaml` と `README.md` しか置いていない。
レンダリング結果はコミットしていないので、
**適用するときは必ず helm が要る**。

## 7 つのコマンドは形が違う

チャートごとに癖があるので、**各 README のコマンドをそのまま使うこと**。
特に `kubectl apply` 側の `--namespace` は逆になる。

| チャート | `kubectl apply` の `--namespace` | 理由 |
| --- | --- | --- |
| cert-manager | **付けてはいけない** | `kube-system` にもリソースを置くため、付けるとエラー |
| nfs-provisioner | **必須 (`storage`)** | `metadata.namespace` を出力しないため、付けないと `default` に落ちる |
| portainer | 不要 | `metadata.namespace` を自分で出力する |
| awx-operator | **必須 (`platform`)** | 同上。AWX リソースだけは自分で出力するので紛らわしい |
| homarr | **必須 (`platform`)** | `metadata.namespace` を出力しないため |
| pgadmin4 | 不要 | `metadata.namespace` を自分で出力する |
| postgres | **必須 (`platform`)** | `metadata.namespace` を出力しないため |

`--no-hooks` を付けるのは cert-manager / nfs-provisioner / portainer / pgadmin4 の 4 つ。
Helm フック (cert-manager の `startupapicheck` Job、portainer のテスト Pod) は
Helm が実行して片付ける前提のリソースで、`kubectl apply` すると残骸になる。
awx-operator / homarr / postgres にはフックがないので付けていない。
pgadmin4 は `values.yaml` の `test.enabled: false` でも止めてある。

**awx-operator だけは `--include-crds` が要る。** CRD が `crds/` にあり、
`helm template` は既定でそれを出力しない。他の 6 つは CRD を
`templates/` に持っているか、そもそも CRD を持たない。

## まとめて適用する

順序が要るのは cert-manager と awx-operator の 2 か所だけ。
どちらも `kubectl apply` そのものが弾かれるパターンで、
弾かれたリソースは作られず、誰も再試行しない。

- cert-manager は webhook が起動しきる前に `ClusterIssuer` / `Certificate` を作れない
- awx-operator は CRD が有効になる前に AWX リソースを作れない

**それ以外は順序を気にしなくてよい。** Secret / ConfigMap / DB が
揃っていない間は Pod が起動に失敗するが、kubelet が再試行し続けるので、
あとから足せば勝手に立ち上がる。

```sh
# リポジトリのルートで実行する

helm repo add jetstack https://charts.jetstack.io
helm repo add nfs-subdir-external-provisioner \
  https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
helm repo add portainer https://portainer.github.io/k8s/
helm repo add awx-operator https://ansible-community.github.io/awx-operator-helm/
helm repo add runix https://helm.runix.net
helm repo add groundhog2k https://groundhog2k.github.io/helm-charts/
helm repo add homarr-labs https://homarr-labs.github.io/charts/
helm repo update

# --- cert-manager (--namespace を付けない) ---
helm template cert-manager jetstack/cert-manager \
  --version v1.21.0 -n cert-manager \
  --values system/cert-manager/values.yaml --no-hooks \
  | kubectl apply --server-side -f -

kubectl -n cert-manager wait --for=condition=Available deploy --all --timeout=180s

# --- NFS プロビジョナ (--namespace storage が必須) ---
helm template nfs nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --version 4.0.18 -n storage \
  --values system/nfs-provisioner/values.yaml --no-hooks \
  | kubectl apply --server-side --namespace storage -f -

# --- PostgreSQL (--namespace platform が必須) ---
# homarr / AWX / pgAdmin の DB。順序は問わない (Pod が再試行する)
helm template postgresql groundhog2k/postgres \
  --version 1.6.7 -n platform \
  --values platform/apps/postgresql/values.yaml \
  | kubectl apply --server-side --namespace platform -f -

# --- Portainer ---
helm template portainer portainer/portainer \
  --version 239.5.0 -n platform \
  --values platform/apps/portainer/values.yaml --no-hooks \
  | kubectl apply --server-side -f -

# --- AWX: まず Operator と CRD だけ (--namespace platform が必須) ---
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 -n platform \
  --values platform/apps/ansible-awx/values.yaml --include-crds \
  --set AWX.enabled=false \
  | kubectl apply --server-side --namespace platform -f -

kubectl wait --for=condition=Established crd/awxs.awx.ansible.com --timeout=120s
kubectl -n platform rollout status deploy/awx-operator-controller-manager

# --- AWX 本体 (--set を外して同じコマンド) ---
helm template awx-operator awx-operator/awx-operator \
  --version 3.2.1 -n platform \
  --values platform/apps/ansible-awx/values.yaml --include-crds \
  | kubectl apply --server-side --namespace platform -f -

# --- Homarr (--namespace platform が必須) ---
helm template homarr homarr-labs/homarr \
  --version 8.26.0 -n platform \
  --values platform/apps/homarr/values.yaml \
  | kubectl apply --server-side --namespace platform -f -

# --- pgAdmin ---
helm template pgadmin runix/pgadmin4 \
  --version 1.66.0 -n platform \
  --values platform/apps/pgadmin/values.yaml --no-hooks \
  | kubectl apply --server-side -f -
```

適用後の確認。

```sh
kubectl -n cert-manager get deploy
kubectl -n storage get deploy
kubectl -n platform get deploy portainer
kubectl -n platform get sts postgresql
kubectl -n platform wait awx/awx --for=condition=Successful --timeout=900s
kubectl -n platform rollout status deploy/homarr
kubectl -n platform rollout status deploy/pgadmin
kubectl get storageclass

# NFS が default に漏れていないこと (漏れていたら --namespace の付け忘れ)
kubectl -n default get deploy,sa,role,rolebinding 2>/dev/null | grep nfs \
  && echo "⚠️ default に漏れている" || echo "OK"
```

## バージョンの管理

**バージョンは各 README にしか書いていない。**
上げるときは README の表とコマンド例の両方を書き換えること
(片方だけ直すと、次に読んだ人が古いバージョンで適用してしまう)。

| チャート | 現在 |
| --- | --- |
| cert-manager | v1.21.0 |
| nfs-subdir-external-provisioner | 4.0.18 |
| portainer | 239.5.0 |
| awx-operator | 3.2.1 (AWX Operator 2.19.1 / AWX 24.6.1) |
| homarr | 8.26.0 (Homarr v1.74.0) |
| pgadmin4 | 1.66.0 (pgAdmin 9.17) |
| groundhog2k/postgres | 1.6.7 (`postgres:16.14` に固定) |

実際にクラスタで動いているバージョンは、この表ではなくクラスタに聞く。

```sh
kubectl -n cert-manager get deploy cert-manager -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl -n storage get deploy -o jsonpath='{.items[0].spec.template.spec.containers[0].image}'
kubectl -n platform get deploy portainer -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl -n platform get deploy awx-web -o jsonpath='{.spec.template.spec.containers[1].image}'
kubectl -n platform get deploy homarr -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl -n platform get deploy pgadmin -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl -n platform get sts postgresql -o jsonpath='{.spec.template.spec.containers[0].image}'
```
