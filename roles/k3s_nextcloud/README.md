# k3s_nextcloud

Nextcloud Hub と専用の PostgreSQL を入れる。アプリの導入と SSO の接続は Nextcloud の画面で行う。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/nextcloud.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_nextcloud` と `defaults/main.yml`。

前提: Longhorn と CloudNativePG のオペレーターが入っている。専用の PostgreSQL(namespace `nextcloud-db`)は、このロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。

1. `vault/nextcloud.yml` に `vault_nextcloud_db_password`・`vault_nextcloud_oidc_client_secret`・`vault_nextcloud_admin_password` を用意する。OIDC のシークレットは `playbooks/k3s/authentik.yml` が読み、Nextcloud の画面にも同じ値を入力する。緊急用のパスワードは機械的に作った24〜32文字の英数字にする。
2. `playbooks/k3s/authentik.yml` を適用して OIDC クライアント `nextcloud` を用意し、[k3s_authentik](../k3s_authentik/README.md) の Blueprint の成功を確認する。
3. `ansible-playbook playbooks/k3s/nextcloud.yml [--check --diff] 2>&1 | cat` を実行する。
4. LAN か VPN から緊急用の `admin` で Nextcloud にログインし(使う端末の hosts ファイルで `<nextcloud_host>` を `172.16.12.5` に向けてから開く(公開ホスト名は LAN からも Tunnel を通り、Tunnel ではパスワードのログインを通さないため))、アプリストアで「OpenID Connect user backend」(`user_oidc`)をインストールする。管理画面でプロバイダーを次の値で登録する。`<authentik_host>` はインベントリの Authentik の公開ホスト名に置き換える。
   - 識別子: `Authentik`
   - クライアント ID: `nextcloud`
   - クライアントシークレット: `vault_nextcloud_oidc_client_secret` の値(`ansible-vault view vault/nextcloud.yml` で確認する)
   - Discovery endpoint: `https://<authentik_host>/application/o/nextcloud/.well-known/openid-configuration`
   - スコープ: `openid email profile`
   - グループのマッピング: `groups`
   - グループのプロビジョニング: 有効
   - グループのホワイトリストの正規表現: `/^(?!admin$).*$/`
5. Authentik の画面で利用グループをアプリケーションに結びつける。管理者にするユーザーは、Nextcloud の画面で `admin` グループに所属させる。この所属は OIDC の同期対象に含めない。
6. アプリストアで使うアプリをインストールする。Talk を入れたら、Talk の管理画面で通話を誰も始められないように通話の権限を設定する。
7. Cloudflare の画面で Tunnel の経路とレート制限を設定する。ログインと `/remote.php` などの同期のパスを制限の対象にする。

## 処理の流れ

DB → アプリの Secret(`nextcloud-admin`・`nextcloud-db`) → Helm のリリース → Ingress と NetworkPolicy の順に適用する。Ansible が再現するのは、素の Nextcloud(インストール直後)と、ほかの決定のために要る設定だけ。最初のインストールでは `post-installation` フックがマーカーを置く。web ユーザーの `before-starting` フックは、cron を選び、マーカーがあるときだけ既定の容量の上限を設定してマーカーを消す。Pod のネットワークをログインの失敗の制限の例外に足す処理は、起動のたびに行う。

## 注意

- 緊急用の `admin` は初回のインストールでだけ作る。パスワードは `vault/nextcloud.yml` を `ansible-vault view` で確認する。あとから vault を変えても、既存のパスワードは変わらない。Authentik が使えないときは LAN か VPN からログインする(使う端末の hosts ファイルで `<nextcloud_host>` を `172.16.12.5` に向けてから開く(公開ホスト名は LAN からも Tunnel を通り、Tunnel ではパスワードのログインを通さないため))。`admin` にはアプリパスワードを作らない。
- 外部からはパスワードでログインできない。クライアントは Login Flow v2 で Authentik にログインしてアプリパスワードを受け取る。LAN でもクライアントにはアプリパスワードを使う。
- ユーザーごとの既定の容量の上限(`nextcloud_default_quota`)は、最初のインストールでだけ設定する初期値。その後の Nextcloud の画面での変更は保つ。`nextcloud_default_quota` をあとから変えても既存のインストールには反映しないため、画面で変更する。Pod のネットワーク(`nextcloud_trusted_proxies`)は、ログインの失敗の制限の例外に足す(画面で足した例外は消さない)。
- アプリとその版は状態として扱う。既定で入っているアプリも含め、追加・更新・有効化・無効化・削除は、アプリストアを使える Nextcloud の画面で行う。アプリはボリュームの `custom_apps` と DB に保持し、バックアップで守る。`user_oidc` の導入とプロバイダーの設定も画面で行う状態。
- Talk の通話を誰も始められないようにする設定は、Talk の導入後に管理画面で行う状態。External sites のサイトと表示方法も画面で設定する。
- 最初のインストールのとき、Nextcloud は追加の設定ファイル(`vars/main.yml` の `configs` の `lab.config.php` など)の値を `config.php` にも書き込む。`lab.config.php` から設定を外しても `config.php` の値が効くため、外すときは k3s01 で `sudo k3s kubectl exec -n nextcloud deploy/nextcloud -c nextcloud -- su -s /bin/sh www-data -c 'php occ config:system:delete <キー>'` も実行する。
- データは Longhorn の PVC 1つと専用の PostgreSQL に保存する。**現在はバックアップがない。** 使用量が7割を超えたら PVC を広げる。縮小はできない。
- Cloudflare の1リクエストの上限を超える、分割に対応しないアップロードは LAN か VPN から行う(送る端末の hosts ファイルで `<nextcloud_host>` を `172.16.12.5` に向けてから送る。公開ホスト名は LAN からも Tunnel を通るため)。iOS のバックグラウンドのアップロードは実機で確認する。

## バージョンを上げる

Nextcloud は1メジャーずつ更新する。チャートの既定のイメージを確かめ、インストール済みのアプリが次の Nextcloud の版に対応することを画面で確認してから、`defaults/main.yml` のチャートの版を更新する。アプリの更新は画面で行う。更新前にバックアップの確保を検討し、更新後は Pod のログ、管理画面、SSO と同期を確認する。
