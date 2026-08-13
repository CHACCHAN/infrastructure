# nfs-subdir-external-provisioner

TrueNAS の NFS 共有を StorageClass `truenas-nfs` として使えるようにする。
PVC を作ると NFS 上にサブディレクトリが自動で切られる。

| 項目 | 値 |
| --- | --- |
| チャート | `nfs-subdir-external-provisioner/nfs-subdir-external-provisioner` |
| バージョン | **4.0.18** |
| Namespace | `storage` |
| 設定 | [`values.yaml`](values.yaml) |
| 作られる StorageClass | `truenas-nfs` (既定クラスではない) |

前提: TrueNAS 側で `10.10.20.10:/mnt/Storage/Kubernetes` が NFS 共有されていること。

## 適用

Helm は**テンプレートを展開するためだけ**に使う。
リリースとしてはインストールしないので、`helm list` には出てこない。

```sh
helm repo add nfs-subdir-external-provisioner \
  https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
helm repo update

helm template nfs nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --version 4.0.18 \
  --namespace storage \
  --values system/nfs-provisioner/values.yaml \
  --no-hooks \
  | kubectl apply --server-side --namespace storage -f -
```

リポジトリのルートから実行すること。

### ⚠️ `kubectl apply` の `--namespace storage` は必須

**このチャートは `metadata.namespace` を出力しない。**

`helm template --namespace storage` と書いても、チャートのテンプレートが
`metadata.namespace` を持っていなければ出力には入らない。
Helm は `helm install -n storage` の時点で置き場所を決める作りなので、
チャート側が書いていなくても本来は動いてしまう。

そのため `kubectl apply` 側で namespace を補う必要がある。
**付け忘れると 4 つのリソースが `default` namespace に作られる。**

| リソース | 付け忘れると |
| --- | --- |
| `ServiceAccount/nfs-nfs-subdir-external-provisioner` | `default` |
| `Role/leader-locking-nfs-nfs-subdir-external-provisioner` | `default` |
| `RoleBinding/leader-locking-nfs-nfs-subdir-external-provisioner` | `default` |
| `Deployment/nfs-nfs-subdir-external-provisioner` | `default` |

稼働中のものとは別に、**もう 1 セットの provisioner が動き出す**。
StorageClass は 1 つしかないので、どちらが PVC を処理するか不定になる。

適用後は必ず確認する。

```sh
# storage に 4 つ、default に 0 個であること
kubectl -n storage get sa,role,rolebinding,deploy | grep nfs
kubectl -n default get sa,role,rolebinding,deploy | grep nfs && echo "⚠️ default に漏れている"
```

> cert-manager では逆に `--namespace` を付けてはいけない
> (複数 namespace を使うチャートなのでエラーになる)。
> チャートごとに違うので、この README のコマンドをそのまま使うこと。

## 設定を変える

```sh
vim system/nfs-provisioner/values.yaml

# 何が変わるか確認する (クラスタは変わらない)
helm template nfs nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --version 4.0.18 -n storage \
  --values system/nfs-provisioner/values.yaml --no-hooks \
  | kubectl diff --namespace storage -f -
```

### StorageClass は作り直せない

`storageClass.name` や `reclaimPolicy`、`archiveOnDelete` を変えたい場合、
StorageClass は**ほぼ不変**なので `apply` では反映されない。
一度削除してから再適用することになる。

```sh
# ⚠️ 既存 PVC がある状態でやらないこと
kubectl delete storageclass truenas-nfs
```

既存の PV / PVC は StorageClass を消しても動き続けるが、
新しい PVC が作れなくなるので短時間で戻すこと。

## バージョンを上げる

1. 上のコマンドの `--version` を新しい値にする
2. **この README の表とコマンド例のバージョンも書き換える**
3. `| kubectl diff --namespace storage -f -` で差分を確認する
4. `| kubectl apply --server-side --namespace storage -f -`

## 確認

```sh
kubectl get storageclass
kubectl -n storage get deploy
kubectl -n storage logs -l app=nfs-subdir-external-provisioner --tail=30
```

データの扱い:

- `reclaimPolicy: Retain` — PVC を消しても PV は残る
- `archiveOnDelete: true` — NFS 上の実データは `archived-*` として残る
