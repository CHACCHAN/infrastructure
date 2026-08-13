# _example — クラスタ外サービスのひな形

クラスタ外 (独立 VM など) で動いているサービスを Traefik 経由で公開するときの型。
**このディレクトリはどこからも参照されていない**ので、コピーして使う。

```sh
cp -r platform/external/_example platform/external/myapp
```

コピーしたら以下を置換する。

| 置換前 | 置換後 | 出てくる場所 |
| --- | --- | --- |
| `myapp` | サービス名 | Service / EndpointSlice / Ingress の名前、ラベル |
| `172.16.11.99` | バックエンドの IP | EndpointSlice |
| `8080` | バックエンドのポート | Service / EndpointSlice |
| `myapp.cc-chacchan.com` | 公開ホスト名 | Ingress |

最後に `platform/external/kustomization.yaml` へ 1 行足す。

```yaml
resources:
  - myapp
```

確認してから適用する。

```sh
kubectl kustomize platform/external/myapp   # レンダリング結果を見る
kubectl diff -k .                           # クラスタとの差分を見る
kubectl apply -k .
```

## よく使う追加パターン

### バックエンドが自己署名 HTTPS の場合

`platform/external/truenas/` が実例。Service のアノテーションを 2 つ足し、
`ServersTransport` を 1 つ作る。

```yaml
# service.yaml の Service 側
  annotations:
    traefik.ingress.kubernetes.io/service.serversscheme: "https"
    traefik.ingress.kubernetes.io/service.serverstransport: "platform-myapp-transport@kubernetescrd"
```

```yaml
# serverstransport.yaml
apiVersion: traefik.io/v1alpha1
kind: ServersTransport
metadata:
  name: myapp-transport
  namespace: platform
spec:
  insecureSkipVerify: true
  # バックエンドが SNI を見る場合は足す
  # serverName: myapp.cc-chacchan.com
```

### アプリが自分の URL を X-Forwarded-Proto から組み立てる場合

WG-Easy や Technitium の WebUI が該当する。`platform/external/wg-easy/` が実例。
`middleware.yaml` を足して、Ingress のアノテーションから参照する。

### Authentik で保護する場合

`platform/external/cloudflare-ddns-ui/` が実例。Ingress を 2 本にする。

1. 本体 — `middlewares: platform-authentik-forward-auth@kubernetescrd` を付ける
2. outpost — `/outpost.goauthentik.io` を認証なしで `authentik-external` へ流す

outpost 側を忘れると、認証後のコールバックが本体に吸われて無限リダイレクトになる。

### 1 バックエンドに複数の経路が要る場合

`platform/external/technitium/` が実例。Service に複数ポートを持たせ、
Ingress を経路の数だけ作って `port.name` で振り分ける。

## 命名の約束

| リソース | 名前 |
| --- | --- |
| Service / EndpointSlice | `<サービス名>-external` |
| Ingress | `<サービス名>` (経路が複数なら `<サービス名>-<用途>`) |
| Middleware | `<Ingress 名>-forwarded-https` |
| ServersTransport | `<サービス名>-transport` |

`-external` を付けているのは、クラスタ内で動いているアプリの Service と
一目で区別するため。
