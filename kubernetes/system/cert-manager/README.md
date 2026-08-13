# cert-manager

証明書の自動発行 / 更新。Let's Encrypt から Cloudflare DNS-01 で
ワイルドカード証明書を取る。

| 項目 | 値 |
| --- | --- |
| チャート | `jetstack/cert-manager` |
| バージョン | **v1.21.0** |
| Namespace | `cert-manager` |
| 設定 | [`values.yaml`](values.yaml) |

ClusterIssuer と Certificate はこのチャートに含まれない。
[`platform/certificates/`](../../platform/certificates/) で管理していて、
そちらは `kubectl apply -k .` の対象。

## 適用

Helm は**テンプレートを展開するためだけ**に使う。
リリースとしてはインストールしないので、`helm list` には出てこない。

```sh
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm template cert-manager jetstack/cert-manager \
  --version v1.21.0 \
  --namespace cert-manager \
  --values system/cert-manager/values.yaml \
  --no-hooks \
  | kubectl apply --server-side -f -
```

リポジトリのルートから実行すること。

### ⚠️ `kubectl apply` に `--namespace` を付けてはいけない

```sh
# ❌ これは失敗する
... | kubectl apply --server-side -n cert-manager -f -
```

```
the namespace from the provided object "kube-system" does not match the
namespace "cert-manager". You must pass '--namespace=kube-system' ...
```

**このチャートは 2 つの namespace にリソースを置く。**
leaderelection の Role / RoleBinding は意図的に `kube-system` にある
(チャートの `global.leaderElection.namespace` の既定値)。

マニフェスト側が `metadata.namespace` を正しく持っているので、
`kubectl` 側では何も指定しないのが正解。

```sh
# 実際どこにあるか
kubectl get role,rolebinding -A | grep leaderelection
```

### なぜ `--no-hooks` か

このチャートは `startupapicheck` という Job を Helm フックとして持つ。
「webhook が応答するようになるまで待つ」ためのもので、
Helm が install 後に実行して片付ける前提のリソース。

`kubectl apply` ではフックが実行されず、ただの Job として残る。
Job はほぼ不変なので、次に適用したとき `field is immutable` で失敗する。

代わりに手で確認する。

```sh
kubectl -n cert-manager rollout status deploy/cert-manager-webhook
kubectl -n cert-manager wait --for=condition=Available deploy --all --timeout=180s
```

### なぜ OCI (`oci://quay.io/...`) ではないのか

cert-manager は OCI レジストリでも配布されているが、OCI から取ると
helm が `Pulled:` / `Digest:` という情報行を **stdout に混ぜてくる**。
そのまま `kubectl apply -f -` に流すと
`apiVersion not set, kind not set` で失敗する。

`https://charts.jetstack.io` (HTTP リポジトリ) からのレンダリング結果は
OCI 版と**バイト単位で同一**であることを確認済み。

## 設定を変える

```sh
vim system/cert-manager/values.yaml

# 何が変わるか確認する (クラスタは変わらない)
helm template cert-manager jetstack/cert-manager \
  --version v1.21.0 -n cert-manager \
  --values system/cert-manager/values.yaml --no-hooks \
  | kubectl diff -f -

# 適用
helm template cert-manager jetstack/cert-manager \
  --version v1.21.0 -n cert-manager \
  --values system/cert-manager/values.yaml --no-hooks \
  | kubectl apply --server-side -f -
```

## バージョンを上げる

1. 上のコマンドの `--version` を新しい値にする
2. **この README の表と、下のコマンド例のバージョンも書き換える**
   (バージョンが書いてある場所はここだけ。ずれると事故る)
3. `| kubectl diff -f -` で差分を確認する
4. `| kubectl apply --server-side -f -`

CRD の破壊的変更がないか、上流のリリースノートを必ず読むこと。

```sh
helm search repo jetstack/cert-manager --versions | head
```

## 確認

```sh
kubectl -n cert-manager get deploy
kubectl -n platform get certificate
```
