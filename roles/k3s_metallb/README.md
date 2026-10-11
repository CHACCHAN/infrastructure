# k3s_metallb

MetalLB(L2)を Helm で入れ、Ingress の VIP(`172.20.<vlan>.<k3s_ingress_vip_id>`)を LoadBalancer の Service に割り当てる。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/metallb.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_metallb` と `defaults/main.yml`。チャートのバージョンは `metallb_chart_version` にだけ書く。

## 処理の流れ

[k3s](../k3s/README.md) ロールに、MetalLB のチャートと、アドレスのプール(`IPAddressPool`)・L2 の広告(`L2Advertisement`)を渡して適用する。

あわせて、k3s 内蔵の Traefik の設定(`HelmChartConfig`)を置く。Traefik を全ノードに置き(DaemonSet)、Service を `externalTrafficPolicy: Local` にする。VIP を持つノードの Traefik が直接受けるため、アプリから見えるクライアントの IP が保たれる。
