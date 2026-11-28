# k3s_truecommand

TrueCommand(TrueNAS をまとめて管理する画面)を、TrueCharts のチャートで k3s に置き、`https://<truecommand_host>` で LAN に公開する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「クラスタ内アプリの構成」)。

## 使い方

`playbooks/k3s/truecommand.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_truecommand` と `defaults/main.yml`。

前提:

- Longhorn が入っている(状態のボリューム)。
- SAML でログインするには、Authentik の SAML のアプリケーション `truecommand`(`playbooks/k3s/authentik.yml` の `authentik_saml_apps`)と、グループ `admins` か `services` の所属が要る。

## 最初に行うこと

TrueCommand は、最初に画面を開いた人に管理者を作らせる。適用したら、すぐに次を行う。

1. `https://<truecommand_host>` を開き、管理者 `admin` を作る。パスワードは `vault_truecommand_admin_password`(`ansible-vault view vault/truecommand.yml`)。これが緊急用の管理者になる。
2. Settings → Administration → Configuration で、SAML Identity Provider URL に `https://<authentik_host>/application/saml/truecommand/metadata/` を入れて保存する。もう一度開いて Start the SAML service を選び、保存する。
3. `https://<truecommand_host>/saml/metadata` の `entityID` を、インベントリの `authentik_saml_apps` の `truecommand` の `audience` に書き、`playbooks/k3s/authentik.yml` を適用する(ほかのアプリ宛てのアサーションを受け付けないため)。
4. TrueNAS の画面で、`truenas_admin` のパスワードを `vault_truenas_admin_password`(`ansible-vault view vault/truenas.yml`)に変える。TrueCommand で、TrueNAS(`truenas01` の IP、ポート 443)を、ユーザー `truenas_admin` とこのパスワードで登録する。TrueNAS の側でパスワードを変えたら、vault と TrueCommand の登録も同じ値に直す。

## ログイン

- 普段は、TrueCommand のログイン画面から SAML で Authentik にログインする。使えるのは、Authentik のグループ `admins` と `services` のメンバーだけ(TrueCommand の SAML はグループに対応しないため、Authentik が絞る)。
- SAML で初めてログインしたユーザーは、TrueCommand のユーザーになる。TrueCommand の中の権限(管理者にするか、どの TrueNAS を見せるか)は、緊急用の `admin` が TrueCommand の画面で付ける(状態)。
- Authentik の属性は `unique_name`(ユーザー名)・`display_name`(表示名)・`email`(メールアドレス)。NameID は persistent。
- Authentik が使えないときは、同じログイン画面から緊急用の `admin` でログインする。公開は LAN と VPN だけなので、パスワードのログインは外からは届かない。

## 注意

- 設定・登録した TrueNAS とその認証情報・ユーザー・収集した統計は、Longhorn のボリューム(`truecommand_storage_size`、既定 10Gi)の `/data` に置く(状態。Longhorn のバックアップで守る)。使用量が7割を超えたら広げる(縮められない)。
- Pod が受ける通信は、同じ namespace と Traefik に絞る(NetworkPolicy)。TrueNAS(`truenas01` の 443)へは Pod から出ていく。
- Cloudflare Tunnel には載せない(`cloudflared_hosts` に入れると、このロールが止まる)。認証プロキシも掛けない(自前のログインを持つため)。
- TrueCharts のチャートが動作を確かめている Kubernetes は 1.35.0 まで(`trueforge.org/max_kubernetes_version`)。このクラスタの k3s はそれより新しい。チャートの版を上げるときは、CHANGELOG とこの範囲を確かめる。
- TrueCommand は、ドライブ 50 本までは無料で使える。
- 公式イメージは root で動く。
