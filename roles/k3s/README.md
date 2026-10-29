# k3s

k3s のクラスタへ、Helm のリリースを適用する共通処理。kubeconfig を使わず、ServiceAccount のトークンで Kubernetes API の VIP に接続する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「クラスタ内アプリの管理」)。

## 使い方

単独では使わない。各 `k3s_<app>` ロールが `include_role` で呼び、チャート・バージョン・values を渡す(例: [k3s_metallb](../k3s_metallb/README.md))。

- 変数は `helm_*`。一覧は `ansible-doc -t role k3s` と `defaults/main.yml`。
- トークン(`helm_api_token`)と認証局の証明書(`helm_ca_cert`)は、playbook が `vault/k3s.yml` から渡す。作り方は [playbooks/utils](../../playbooks/utils/README.md)。
- 接続先は、インベントリの `vlan` と `k3s_api_vip_id` から導出する。ロールは、グループ `k3s` のホストの文脈で動かす。
- 認証局の証明書は、実行の間だけ `/dev/shm` に置き、終わると消す。

## 処理の流れ

認証局の証明書を書き出す → `helm_secrets` を適用する(あれば namespace を先に作る)→ Helm のリリースを適用する(`helm_wait` で Ready を待つ)→ `helm_manifests` と `helm_ingress` の Ingress を適用する → Tunnel 専用の入口の経路を適用する(`helm_ingress.tunnel` が false なら消す)→ NetworkPolicy を適用する(`helm_network_policy` が false なら消す)→ 証明書を消す。

`helm_secrets` の各 Secret は宣言どおりに置き換える。ラベル・すべてのキー・`type`(Opaque 以外のとき)を含む、完全な定義を書く。定義にないキー・ラベル・アノテーションは削除される。

`--check --diff` のときは helm-diff プラグインで差分を見る。リリースが新規または更新になる場合は、CRD などが揃っていないことがあるため、`helm_manifests`・Ingress・NetworkPolicy の確認を飛ばす。マニフェストが webhook に拒否されることがあるため、数回再試行する。

`helm_chart` を空にすると、Helm のリリースを作らず、namespace・`helm_manifests`・Ingress だけを適用する(チャートの無いもの。[k3s_lan_proxy](../k3s_lan_proxy/README.md) が使う)。

values に秘密値を渡すアプリは、`helm_no_log: true` にする。

## 通信の制限

`helm_network_policy: true` にすると、namespace の Pod が受ける通信を、同じ namespace、Traefik(`helm_ingress` があるとき)、インベントリの表 `helm_network_policies` でその namespace に挙げた namespace だけに絞る。表に namespace が無ければ止まる。外向きの通信は絞らない。ノード自身からの通信(kubelet のヘルスチェック)は、NetworkPolicy の対象にならない。

`helm_ingress.tunnel: true` にすると、Traefik の Tunnel 専用の入口(`tunnel`。[k3s_metallb](../k3s_metallb/README.md) が作る)にも経路(`IngressRoute`)を作り、Cloudflare Tunnel を通る外部からの通信を受ける。`helm_ingress.tunnel_deny_paths` のパスは、この入口でだけ経路から外し、アプリに届かないようにする(緊急用のパスワードのログインなど)。外したパスは、同じホストにほかのリリースの経路があればそちらに載り、無ければ 404 になる。`tunnel` を false に戻すと、経路を消す。この経路にはミドルウェアが掛からないため、`middlewares` とは同時に指定できない。

`helm_ingress.middlewares` で、Ingress に Traefik のミドルウェアを掛ける(Authentik の認証プロキシは `authentik-forward-auth@kubernetescrd`)。

複数の Service に振り分けるときは、`helm_ingress.routes` にパスと Service を指定する。各経路の `host` でホスト名を変えられ(省略時は `helm_ingress.host`)、1つのリリースで、Tunnel に載せるホストと載せないホストの経路を分けられる。ホストが違っても、リリースの中でパスは重ねられない。各経路に `middlewares`、`tunnel`、拒否するパスを指定できる。`strip_prefix: true` は転送前に接頭辞を除く。Tunnel に載せる経路には `middlewares` を指定できない。パスは `/` または `/` で始まる英数字・`._~/-` とし、`/` 以外に末尾の `/` を付けない。経路ごとの Ingress の名前は `<リリース名>-<パスの英数字を - でつないだもの>`(`/` は `root`)で、名前が重なるパスは並べられない。Tunnel 専用の入口では、経路のパスを `/` の区切りで一致させる(`/auth` の経路は `/auth` と `/auth/…` だけを受け、`/authX` は受けない)。経路から外したパスと、どの経路にも当たらないパスは、同じホストにほかのリリースの短いパスの経路(`/` など)があればそちらに載り、無ければ 404 になる。

```yaml
helm_ingress:
  host: app.example.com
  routes:
    - path: /
      service_name: portal
      service_port: 80
      tunnel: true
    - path: /console
      service_name: console
      service_port: 80
      strip_prefix: true
```

経路を削除・変更すると、使わなくなった Ingress と Middleware は自動で消えないため、確認して削除する。単一経路と `routes` の切り替えでも、使わなくなった Ingress を削除する。

`helm_ingress.tunnel_deny_post_paths` は、Tunnel 専用の入口で POST だけを通さない完全一致のパスを指定する。大文字・小文字を区別せず、末尾のスラッシュは任意。指定値には末尾のスラッシュを付けない。ログイン画面の GET や、Login Flow v2 の子パスは通せる。

`routes` の各経路の `tunnel_deny_headers` は、Tunnel 専用の入口で、指定したヘッダーを持つ要求を値によらず経路から外す(Cookie だけで使う API に、`Authorization` でのパスワードやトークンを外から送らせないなど)。
