# k3s_cloudflared

cloudflared(Cloudflare Tunnel のコネクタ)を Helm で入れる。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「クラスタ内アプリの構成」)。

## 使い方

`playbooks/k3s/cloudflared.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_cloudflared` と `defaults/main.yml`。

前提:

- Cloudflare の画面で Tunnel を作り、トークンを `vault/cloudflared.yml` に置いてある([vault](../../vault/README.md))。
- Traefik に Tunnel 専用の入口がある([k3s_metallb](../k3s_metallb/README.md))。
- 公開するアプリに、Tunnel 専用の入口の経路がある(インベントリの `cloudflared_hosts` に足したあとで、各アプリの playbook を実行する)。

## 処理の流れ

[k3s](../k3s/README.md) ロールに、チャート(`cloudflare-tunnel-remote`)とトークンを渡して適用する。このロールが置くのはコネクタだけで、Tunnel・経路表・DNS は Cloudflare の画面で管理する。

- Pod が受ける通信を、同じ namespace に絞る(NetworkPolicy)。cloudflared は外向きにだけ接続する。
- Pod の外向きの通信も絞る。通すのは、クラスタ内の DNS、Traefik の Tunnel 専用の入口、インターネットだけ。Cloudflare の画面で向け先を誤っても(LAN 用の入口、LAN の機器、公開ホスト名)、届かずにエラーになる。

## Cloudflare の画面での設定

Tunnel は新しく作る。旧構成の Tunnel が Cloudflare に残っていても、それにはコネクタを足さない(旧構成の経路表を引き継いでしまうため)。

公開するホスト名ごとに、Tunnel の経路(Public Hostname)を次のように作る。DNS のレコードは、Cloudflare が自動で作る。同じ名前のレコードが既にあるとき(旧構成の Tunnel を向いているもの)は、先にそれを消す。

| 項目 | 値 |
| --- | --- |
| ホスト名 | 公開するホスト名(例: `auth.cc-chacchan.com`) |
| 向け先(Service) | `https://traefik-tunnel.kube-system.svc.cluster.local:443`(すべてのホスト名で同じ) |
| TLS の Origin Server Name | 公開するホスト名と同じ値 |

- 向け先は、必ず Traefik の Tunnel 専用の入口にする。ほかの向け先(LAN 用の入口、公開ホスト名、LAN の機器の IP)は、NetworkPolicy が通さない。
- 画面にホスト名を足しても、`cloudflared_hosts` に無いアプリには届かない(Tunnel 専用の入口に経路が無く、404 になる)。
- `auth` を足す前に、ログインへのレート制限(WAF)を設定する。外からのログインには、Authentik の試行回数の制限が掛からない。

## 注意

- Tunnel を通る通信は、アプリからはすべて cloudflared の Pod の IP に見える(Traefik が、届いた転送ヘッダーを信頼しないため)。
- 公開をやめるときは、`cloudflared_hosts` から外してそのアプリの playbook を実行し(Traefik の経路が消える)、Cloudflare の画面でも経路を消す。
- トークンは、Helm のリリース情報(namespace 内の Secret)に残る。
- LAN の中から公開ホスト名を引いたときに Cloudflare を経由するかどうかは、LAN の名前解決で決まる([docs/design/network.md](../../docs/design/network.md))。
