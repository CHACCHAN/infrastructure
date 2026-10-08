# k8s 設計

クラスタ内アプリ(`k8s` / `k8s_<app>`)の管理方法。クラスタ自体は [k3s.md](k3s.md)。

## 決定済み

### アプリの管理

- アプリは Helm の実リリース(`helm upgrade --install` に相当。`kubernetes.core.helm`)で管理する。
- チャートのバージョンは、ロールの `defaults/main.yml` にだけ書く([conventions.md](../conventions.md))。
- 秘密情報は vault に置き、playbook がロールへ渡す。

### クラスタへの接続

- kubeconfig を使わない。プロジェクトの外に機密情報を置かないため。
- 接続情報は vault に置く。接続先は API の VIP(`https://172.20.21.6:6443`)。

### 変更前の確認

- `--check --diff` には helm-diff プラグインを使う(Helm 4 では v3.14.0 以上)。開発コンテナに導入する(`.devcontainer/devcontainer.json`)。

## 推奨(未確定)

- 共通処理は `k8s` ロールに1つだけ置く(チャート・リリース名・namespace・values を受け取って適用する)。各 `k8s_<app>` は、`defaults/main.yml` にチャート・バージョン・values だけを書く。
- 接続は、専用の ServiceAccount のトークンで行う。最初の1回だけ、k3s01 上の管理用 kubeconfig(`/etc/rancher/k3s/k3s.yaml`)を SSH 越しに使ってトークンを作り、vault に格納する。
- values に入れた秘密値は、Helm のリリース情報(namespace 内の Secret)に残る。秘密値を扱うタスクには `no_log` を付ける。

## 未決

- ServiceAccount の権限(cluster-admin か、namespace ごとか)。
- トークンの作成手順と更新。
- kubectl で読み取り確認をするときの接続手段(kubeconfig を作らずに行う方法)。
- CRD の扱い(Helm は upgrade で `crds/` を更新しない。チャートごとに確認する)。
