# k3s_homarr

Homarr(ダッシュボード)を Helm で入れ、Authentik の OIDC でログインできるようにする。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/homarr.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_homarr` と `defaults/main.yml`。

前提: PostgreSQL に `homarr` の DB とロールがある。OIDC のクライアントは [k3s_authentik](../k3s_authentik/README.md) の Blueprint で宣言する(同じ `vault/homarr.yml` の client_secret を使う)。

## 注意

- ログインは、Authentik が使えないときの緊急用として、`credentials` も残している。緊急用の管理者 `admin` は、[playbooks/utils/homarr_admin.yml](../../playbooks/utils/README.md) で作る(パスワードは `vault/homarr.yml`)。
- 初回の設定は、緊急用の管理者でログインして画面で行う。管理者にする外部グループには、Authentik の画面で作ったグループと同じ名前を指定する。
- DB の暗号化キー(`vault_homarr_db_encryption_key`)を失うと、DB の中の暗号化された値が読めない。
- ボード、ユーザー、統合の設定は Homarr の状態で、Ansible では管理しない。
- 外部(Cloudflare Tunnel)に公開するのは、インベントリの `cloudflared_hosts` に `homarr_host` があるとき。外からは、このアプリのパスワードのログイン(緊急用の管理者)を通さない。
- Pod が受ける通信を、同じ namespace と Traefik に絞る(NetworkPolicy)。
- ボリュームを持たない。データは PostgreSQL に置き、`/appdata`(キャッシュ)は Pod を作り直すと消える。
