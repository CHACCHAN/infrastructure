# k3s_postgresql

PostgreSQL(CloudNativePG の `Cluster`)を Helm の `cluster` チャートで作り、アプリごとの DB とロールを宣言する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/postgresql.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_postgresql` と `defaults/main.yml`。

前提: [k3s_cnpg](../k3s_cnpg/README.md) でオペレーターが入っている。`vault/postgresql.yml` の `vault_postgresql_passwords` に、`postgresql_databases` の名前ごとのパスワードがある。

## 処理の流れ

`postgresql_databases` から、ロール(同名)・`Database`・パスワードの Secret(`postgresql-role-<名前>`)を導出し、リリースの前に Secret を渡して適用する。

アプリは `postgresql-rw.postgresql.svc.cluster.local:5432` に、DB 名と同名のロールで接続する。DB を足すときは、`postgresql_databases` に足して、vault にパスワードを足す。

Pod が受ける通信は、インベントリの `helm_network_policies` の `postgresql` に挙げた namespace(オペレーターと、DB を使うアプリ)に絞る(NetworkPolicy)。別の namespace のアプリが DB を使うときは、ここに足す。namespace の名前は、各ロールの `*_namespace` と別に書いてあるので、変えるときは `helm_network_policies`(`inventory/group_vars/k3s.yml`)のキーと値も合わせる(`k3s_longhorn` の `longhorn_ingress_middleware` も同じ)。

スーパーユーザーのアクセスは無効。バックアップは設定していない(NAS の構築後に設計する)。

接続先のホスト名(`postgresql-rw.<namespace>.svc.cluster.local`)は、各アプリのロール(`k3s_authentik`・`k3s_homarr`・`k3s_openwebui`・`k3s_litellm`)の `*_db_host` にも既定値として書いてある。リリース名か namespace を変えるときは、4つとも合わせる。
