# k3s_longhorn

Longhorn を Helm で入れ、既定の StorageClass(`longhorn`)にする。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「ストレージとバックアップ」「クラスタ内アプリの構成」)。

## 使い方

`playbooks/k3s/longhorn.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_longhorn` と `defaults/main.yml`。

前提: ノードに `open-iscsi` などと `iscsi_tcp`・`dm_crypt` モジュールがある(`playbooks/vm/k3s.yml` の `vm_k3s` が用意する)。

## 注意

- ボリュームの複製数(`longhorn_replica_count`)は、インベントリの `k3s` グループのホストが1台なら1、2台以上なら2。CSI・マネージャー・UI の Pod の数(`longhorn_control_replicas`)は、ホストの数。ホストを足したら、クラスタに参加させてから、このロールを適用する。インベントリのホストがすべて Ready になるまで適用しない(複製数・Pod の数を、参加前のノードに合わせないため)。ノードを止めている間に適用するときは、`-e helm_min_ready_nodes=0` で確認を外す。`longhorn_replica_count` は、これから作る PVC の StorageClass の既定値だけを変える。作成済みのボリューム(PostgreSQL など)は 1 のままなので、Longhorn の画面か `volumes.longhorn.io` の `numberOfReplicas` で個別に上げる。
- 管理 UI は `https://<longhorn_host>` で公開する。認証を持たないため、Authentik の認証プロキシ(`longhorn_ingress_middleware`)を必ず掛け、Pod へ届く経路を NetworkPolicy で Traefik に限る。Authentik([k3s_authentik](../k3s_authentik/README.md))を入れるまでは開けない。使えるのは、Authentik のグループ `admins`(`k3s_authentik` の `authentik_proxy_access_group`)のメンバーだけ。
- バックアップ先は未構築で、永続データにバックアップはない。
