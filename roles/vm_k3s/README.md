# vm_k3s

k3s サーバーを、`vm` で整えた Debian 13 の VM に構築する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/vm/k3s.yml` から使う([playbooks/vm/README.md](../../playbooks/vm/README.md))。

- 対象ホストのグループに `vlan` が宣言されていること。Kubernetes API の VIP は、`172.16.<vlan>.<k3s_api_vip_id>` に導出される。
- 変数の一覧は `ansible-doc -t role vm_k3s` と `defaults/main.yml`。バージョンは `k3s_version`・`k3s_kube_vip_version` にだけ書く。

## 構成されるもの

- k3s サーバー(組み込み etcd)。グループ `k3s` の先頭のホストがクラスタを作り(`cluster-init`)、ほかは API の VIP へ参加する。参加には、クラスタのトークン(`k3s_cluster_token`。playbook が `vault/k3s.yml` の `vault_k3s_cluster_token` を渡す)を使う。参加するホストには、認証局のハッシュを含むトークンが要る([playbooks/utils](../../playbooks/utils/README.md) の `k3s_cluster_token.yml`)。バイナリはチェックサムを検証して入れ、systemd のユニットを置く。
- `servicelb` と `local-storage` は無効。Traefik は k3s 内蔵のものを使う。
- swap は使わない(kubelet の既定どおり)。
- クラスタ内から公開ホスト名(`k3s_ingress_hosts`)を引くと、Traefik の Service を返す(CoreDNS の `coredns-custom`)。Pod からの OIDC の通信などが、外の DNS に頼らない。
- kube-vip(DaemonSet)が API の VIP を持つ。証明書の SAN にも VIP を入れる。

MetalLB・Longhorn・アプリは含まない(`k3s_<app>` ロールが Helm で入れる。[docs/design/k3s.md](../../docs/design/k3s.md))。

## 処理の流れ

`validate` → `storage`(Longhorn の前提パッケージ・カーネルモジュール)→ `install`(バイナリ・設定・ユニット)→ `kube_vip`(マニフェスト)→ `coredns`(公開ホスト名をクラスタ内の Traefik へ向ける設定)→ `start`(起動、ノードの Ready を待つ)→ `verify`(VIP の応答)。

## 注意

- k3s の設定やバイナリを変えると、k3s を再起動する。ノードが1台のあいだは、その間 API が止まる。playbook は1台ずつ実行する(`serial: 1`)。
- 先頭のホストにクラスタのデータが無く、API の VIP が応答しているときは、別のクラスタを作らないよう止まる。先頭のホストを作り直すときは、動いているノードで古いノードを消し(`kubectl delete node`)、グループの先頭を動いているノードに入れ替えてから実行する(作り直したホストは参加する側になる)。
- 書き換える前に、トークンを確かめて止まる。先頭のホストにクラスタのデータがあれば、vault のトークンが動いているクラスタのものと一致すること。参加するホストは、API の VIP の認証局が、トークンのハッシュと一致すること(一致しないまま参加させると、k3s が参加を待ち続け、playbook が終わらない)。クラスタを作り直したら、`k3s_cluster_token.yml` で vault の値を更新する。
- kube-vip のマニフェストは、k3s が `/var/lib/rancher/k3s/server/manifests/` から自動で適用する。
