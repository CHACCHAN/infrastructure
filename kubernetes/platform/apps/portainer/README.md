# Portainer CE

Kubernetes 管理 WebUI。

| 項目 | 値 |
| --- | --- |
| チャート | `portainer/portainer` |
| バージョン | **239.5.0** |
| Namespace | `platform` |
| ホスト名 | `portainer.cc-chacchan.com` |
| 設定 | [`values.yaml`](values.yaml) |
| 公開経路 | [`ingress.yaml`](ingress.yaml) |

## このディレクトリの構成

**本体と経路で適用方法が違う。**

| ファイル | 何を作るか | 適用方法 |
| --- | --- | --- |
| `values.yaml` | Deployment / Service / PVC / RBAC | **helm template → kubectl apply** |
| `ingress.yaml` | Ingress | `kubectl apply -k .` (kustomize) |
| `kustomization.yaml` | `ingress.yaml` だけを列挙 | — |

Ingress を上流チャートに任せず自分で書いているのは、TLS・entrypoints・
Middleware の書き方をリポジトリ全体で 1 か所に揃えるため。
そのため `values.yaml` では `ingress.enabled: false` にしてある。

## 適用

### 1. 本体 (helm)

Helm は**テンプレートを展開するためだけ**に使う。
リリースとしてはインストールしないので、`helm list` には出てこない。

```sh
helm repo add portainer https://portainer.github.io/k8s/
helm repo update

helm template portainer portainer/portainer \
  --version 239.5.0 \
  --namespace platform \
  --values platform/apps/portainer/values.yaml \
  --no-hooks \
  | kubectl apply --server-side -f -
```

リポジトリのルートから実行すること。

`kubectl apply` 側に `--namespace` は不要。
このチャートは `metadata.namespace` を自分で出力する。

> `--no-hooks` は、`helm test` 用のテスト Pod を除外するため。
> Helm が実行して片付ける前提のリソースなので、`kubectl apply` すると
> ただの Pod として残ってしまう。

### 2. 経路 (kustomize)

```sh
kubectl apply -k .        # リポジトリのルートで
```

## 設定を変える

```sh
vim platform/apps/portainer/values.yaml

# 何が変わるか確認する (クラスタは変わらない)
helm template portainer portainer/portainer \
  --version 239.5.0 -n platform \
  --values platform/apps/portainer/values.yaml --no-hooks \
  | kubectl diff -f -

# 適用
helm template portainer portainer/portainer \
  --version 239.5.0 -n platform \
  --values platform/apps/portainer/values.yaml --no-hooks \
  | kubectl apply --server-side -f -
```

### PVC のサイズは後から広げられない (縮められない)

`persistence.size` を変えても、既存の PVC には反映されない。
NFS の StorageClass は expansion に対応していないので、
実質やり直しになる。データの退避が必要。

## バージョンを上げる

1. 上のコマンドの `--version` を新しい値にする
2. **この README の表とコマンド例のバージョンも書き換える**
3. `| kubectl diff -f -` で差分を確認する
4. `| kubectl apply --server-side -f -`
5. **Service のポート名が変わっていないか確認する**

5 が重要。`ingress.yaml` はポートを**名前** (`http`) で参照している。

```sh
kubectl -n platform get svc portainer -o jsonpath='{.spec.ports}' | jq
```

名前が変わっていたら `ingress.yaml` も直す。

```sh
helm search repo portainer/portainer --versions | head
```

## 確認

```sh
kubectl -n platform rollout status deploy/portainer
kubectl -n platform get pvc portainer
curl -s -o /dev/null -w '%{http_code}\n' https://portainer.cc-chacchan.com/   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://portainer.cc-chacchan.com/    # 404 が正しい
```
