# k3s_cnpg

CloudNativePG のオペレーターを Helm で入れる。各アプリの PostgreSQL は、アプリのロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/cnpg.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_cnpg` と `defaults/main.yml`。

CRD はチャートのテンプレートで管理されるため、チャートのバージョンを上げると更新される。
