# k3s_lan_proxy

クラスタの外にある LAN 内のサービス(Proxmox の管理 UI)を、Traefik でリバースプロキシする。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「VIP と Ingress」「クラスタ内アプリの構成」)。

## 使い方

`playbooks/k3s/lan_proxy.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_lan_proxy` と `defaults/main.yml`。

前提:

- Traefik が LAN 用の入口で動いていて、既定の証明書がある([k3s_metallb](../k3s_metallb/README.md)、[k3s_cert_manager](../k3s_cert_manager/README.md))。
- k3s ノード(VLAN12)から、宛先の IP とポートへ届く(VLAN をまたぐ通信は、ルータが通す)。
- 公開ホスト名の DNS が、Ingress の VIP を指している。

## 処理の流れ

サービスごとに [k3s](../k3s/README.md) ロールを呼び、セレクタの無い Service、宛先の IP を持つ EndpointSlice、Ingress を置く。チャートが無いため、Helm のリリースは作らない。

- 既定では、インベントリの `pve` グループの全ノードを対象にする。公開ホスト名は `<ノード名>.<lab_domain>`、宛先はノードの IP の 8006 番。ノードをインベントリに足したら、この playbook を実行する。
- 宛先の証明書が自己署名のときは、検証しない(`insecure_skip_verify`)。Proxmox の管理 UI は自己署名のため、検証しない。

## 注意

- 認証プロキシ(Authentik)は掛けない。Proxmox の管理 UI は、自前のログインを持つため。
- 外部(Cloudflare Tunnel)には公開しない。LAN と VPN からだけ使う。
- リストからサービスを外しても、置いたリソースは消えない。消すときは、namespace ごと消して入れ直す([playbooks/utils](../../playbooks/utils/README.md) の `k3s_app_remove.yml` に `-e k3s_app_remove_no_release=true` を付ける)。
