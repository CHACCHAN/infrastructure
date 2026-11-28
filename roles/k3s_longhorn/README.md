# k3s_longhorn

Longhorn を Helm で入れ、既定の StorageClass(`longhorn`)にする。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「ストレージとバックアップ」「クラスタ内アプリの構成」)。

## 使い方

`playbooks/k3s/longhorn.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_longhorn` と `defaults/main.yml`。

前提: ノードに `open-iscsi` などと `iscsi_tcp`・`dm_crypt` モジュールがある(`playbooks/vm/k3s.yml` の `vm_k3s` が用意する)。

## 注意

- ボリュームの複製数(`longhorn_replica_count`)は、インベントリの `k3s` グループのホストが1台なら1、2台以上なら2。CSI・マネージャー・UI の Pod の数(`longhorn_control_replicas`)は、ホストの数。ホストを足したら、クラスタに参加させてから、このロールを適用する。インベントリのホストがすべて Ready になるまで適用しない(複製数・Pod の数を、参加前のノードに合わせないため)。ノードを止めている間に適用するときは、`-e helm_min_ready_nodes=0` で確認を外す。`longhorn_replica_count` は、これから作る PVC の StorageClass の既定値だけを変える。作成済みのボリューム(PostgreSQL など)は 1 のままなので、Longhorn の画面か `volumes.longhorn.io` の `numberOfReplicas` で個別に上げる。
- 管理 UI は `https://<longhorn_host>` で公開する。認証を持たないため、Authentik の認証プロキシ(`longhorn_ingress_middleware`)を必ず掛け、Pod へ届く経路を NetworkPolicy で Traefik に限る。Authentik([k3s_authentik](../k3s_authentik/README.md))を入れるまでは開けない。使えるのは、Authentik のグループ `admins` と `services`(`k3s_authentik` の `authentik_proxy_access_groups`)のメンバーだけ。
- `longhorn_backup_target` を宣言すると、すべてのボリュームを毎日1回(日本時間の3時)バックアップし、7世代を保つ。空のあいだは、バックアップ先も定期バックアップも置かない。宣言から外しても、置いたバックアップ先と定期バックアップは消えない(Longhorn の画面で外す)。
- 戻すときは、Longhorn の画面の Backup から、ボリュームごとに戻す。

## バックアップ先を用意する

1. TrueNAS で、Longhorn 用のデータセットと NFS 共有を作る。NFSv4 を有効にし、k3s ノード(`172.16.12.1`〜`.3`)にだけ読み書きを許す。Longhorn はノードの root でファイルを作るため、共有の Maproot User と Maproot Group を `root` にする(TrueNAS CORE では Group は `wheel`)。
2. OPNsense で、k3s ノードから TrueNAS(`172.16.14.1`)の 2049/TCP への通信を許す。
3. インベントリ(`inventory/group_vars/k3s.yml`)に `longhorn_backup_target: "nfs://{{ hostvars['truenas01'].ansible_host }}:/<エクスポートのパス>"` を宣言し、`playbooks/k3s/longhorn.yml` を `--check --diff` で確かめてから実行する。
4. Longhorn の画面の Settings → Backup Target で、`default` が Available になっていることを確かめる。
