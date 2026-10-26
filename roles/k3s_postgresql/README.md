# k3s_postgresql

アプリ1つ専用の PostgreSQL(CloudNativePG の `Cluster`)を Helm の `cluster` チャートで作り、DB とその所有者のロールを宣言する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

DB を使うアプリのロール(`k3s_authentik`・`k3s_openwebui`・`k3s_litellm`)が、自分の DB を作るために `include_role` で呼ぶ。単独の playbook は無い。変数の一覧は `ansible-doc -t role k3s_postgresql` と `defaults/main.yml`。

前提: [k3s_cnpg](../k3s_cnpg/README.md) でオペレーターが入っている(`playbooks/k3s/cnpg.yml`)。

## 処理の流れ

所有者のロールのパスワードの Secret(`<リリース名>-owner`)を渡してから、`Cluster` を適用する。DB と所有者のロール(どちらも `postgresql_database` の名前)は初期化で作り、以降はロールのパスワードを Secret に合わせ、拡張(`postgresql_extensions`)を宣言で保つ。

アプリは `<リリース名>-rw.<namespace>.svc.cluster.local:5432` に接続する。リリース名の既定は namespace と同じ。

DB はアプリと別の namespace(`<アプリの namespace>-db`)に置く。Pod が受ける通信は、インベントリの `helm_network_policies` に、その namespace をキーにして挙げた namespace(オペレーターの `cnpg-system` と、DB を使うアプリ)に絞る(NetworkPolicy)。アプリの namespace の NetworkPolicy は Traefik などからも受けるため、同じ namespace に置くと DB にも届いてしまう。

スーパーユーザーのアクセスは無効。インスタンスが1つのときは、PodDisruptionBudget を置かない(ノードの退避を止めないため)。バックアップは設定していない(NAS の構築後に設計する)。

DB を消すときは、アプリと別に、DB の namespace も [k3s_app_remove](../../playbooks/utils/README.md) で消す。
