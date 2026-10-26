# k3s_nextcloud

Nextcloud Hub を Helm で入れ、Authentik の OIDC でログインできるようにする。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/nextcloud.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_nextcloud` と `defaults/main.yml`。

前提: Longhorn と CloudNativePG のオペレーターが入っている。専用の PostgreSQL(namespace `nextcloud-db`)は、このロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。

1. `vault/nextcloud.yml` に `vault_nextcloud_db_password`・`vault_nextcloud_oidc_client_secret`・`vault_nextcloud_admin_password` を用意する。このファイルは `playbooks/k3s/authentik.yml` も読む。緊急用のパスワードは機械的に作った24〜32文字の英数字にする。
2. SSO を使うには、`playbooks/k3s/authentik.yml` を適用し、[k3s_authentik](../k3s_authentik/README.md) の Blueprint の成功を確認する。Nextcloud のインストールは先に行ってもよく、Authentik にクライアントが用意されると SSO を使える。
3. `ansible-playbook playbooks/k3s/nextcloud.yml [--check --diff] 2>&1 | cat` を実行する。
4. Authentik の画面で利用グループをアプリケーションに結びつける。管理者にするユーザーは、Nextcloud の画面で `admin` グループに所属させる。この所属は OIDC の同期対象に含めない。
5. Cloudflare の画面で Tunnel の経路とレート制限を設定する。ログインと `/remote.php` などの同期のパスを制限の対象にする。

## 処理の流れ

DB → アプリの Secret → Helm のリリース → Ingress と NetworkPolicy の順に適用する。起動のたびに、web ユーザーの `before-starting` フックでアプリの版を確認し、異なるアプリだけを取得・SHA-256 検証・配置する。必要な DB の更新を行い、アプリの有効化と宣言した設定を合わせる。

## 注意

- 緊急用の `admin` は初回のインストールでだけ作る。パスワードは `vault/nextcloud.yml` を `ansible-vault view` で確認する。あとから vault を変えても、既存のパスワードは変わらない。Authentik が使えないときは LAN か VPN からログインする。`admin` にはアプリパスワードを作らない。
- 外部からはパスワードでログインできない。クライアントは Login Flow v2 で Authentik にログインしてアプリパスワードを受け取る。LAN でもクライアントにはアプリパスワードを使う。
- Pod の起動のたびに、フックがユーザーごとの既定の容量の上限(`nextcloud_default_quota`)と、Talk の通話開始を禁止する設定を宣言した値に合わせる(画面で変えても戻る)。Pod のネットワーク(`nextcloud_trusted_proxies`)は、ログインの失敗の制限の例外に足す(画面で足した例外は消さない)。
- External sites のサイトと表示方法は画面で設定する。既定で入っているアプリの有効・無効は変更しない。
- データは Longhorn の PVC 1つと専用の PostgreSQL に保存する。**現在はバックアップがない。** 使用量が7割を超えたら PVC を広げる。縮小はできない。
- Cloudflare の1リクエストの上限を超える、分割に対応しないアップロードは LAN か VPN から行う。iOS のバックグラウンドのアップロードは実機で確認する。

## バージョンを上げる

Nextcloud は1メジャーずつ更新する。チャートの既定のイメージと、各アプリの対応する Nextcloud の版を確かめ、`defaults/main.yml` のチャートとアプリの版を更新する。アプリは、リリースのアーカイブについてアプリストアの署名を検証してから、URL と SHA-256 を記入する。更新前にバックアップの確保を検討し、更新後は Pod のログ、管理画面、SSO と同期を確認する。
