# playbooks/utils

単発で使うツール。繰り返し流す前提ではない。

**実機を変更する。** 実行は、実行を頼まれたときだけ行う([AGENTS.md](../../AGENTS.md) の安全規則)。

## playbook

| playbook | 内容 | 実行例 |
| --- | --- | --- |
| `k3s_token.yml` | k3s に ServiceAccount(`cluster-admin`)と長期トークンを作り、トークンと認証局の証明書を `vault/k3s.yml` に暗号化して保存する | `ansible-playbook playbooks/utils/k3s_token.yml 2>&1 \| cat` |
| `k3s_cluster_token.yml` | k3s のクラスタのトークン(サーバーの参加に使う)を `vault/k3s.yml` に保存する。クラスタが動いていれば先頭のホストのトークンを写し、無ければ新しく作る | `ansible-playbook playbooks/utils/k3s_cluster_token.yml 2>&1 \| cat` |
| `homarr_admin.yml` | Homarr の緊急用の管理者(`admin`)を、無ければ作り、パスワードを `vault/homarr.yml` の値に設定する | `ansible-playbook playbooks/utils/homarr_admin.yml 2>&1 \| cat` |
| `k3s_app_remove.yml` | クラスタからアプリを取り除く(Helm のリリースと namespace を消す) | `ansible-playbook playbooks/utils/k3s_app_remove.yml -e k3s_app_remove_namespace=<名前> -e k3s_app_remove_confirm=<名前> 2>&1 \| cat` |

## k3s_token.yml

- 初回の1回だけ行う。`vault/k3s.yml` に `vault_k3s_api_token` があれば何もしない。作り直すときは、その値を消してから実行する(クラスタ側の Secret はそのまま使う)。ファイルのほかの値は保つ。
- k3s01 に SSH し、ノード上の管理用 kubeconfig(`k3s kubectl`)を使う。SSH の鍵は [playbooks/vm](../vm/README.md) と同じ。
- 平文のトークンは、`/dev/shm` に一時的に置き、暗号化したあとに消す。
- 作ったトークンは [k3s](../../roles/k3s/README.md) ロールが使う。

## k3s_cluster_token.yml

- k3s01 に SSH し、`/var/lib/rancher/k3s/server/token` を読む。クラスタが動いていれば、そのトークン(`K10<認証局のハッシュ>::server:<秘密>`)を `vault_k3s_cluster_token` に保存する。同じ値なら何もしない。既存の値(`vault_k3s_*`)は保つ。
- クラスタがまだ無く、vault にも無ければ、秘密だけを新しく作る。クラスタを一から作るときは、これを実行し、`playbooks/vm/k3s.yml -l k3s01` で先頭のホストを構築してから、もう一度実行する(参加するホストが、認証局のハッシュで参加先を確かめられるようにするため)。
- 平文は `/dev/shm` に一時的に置き、暗号化したあとに消す。
- トークンは [vm_k3s](../../roles/vm_k3s/README.md) が使う。

## homarr_admin.yml

- Homarr はユーザーを宣言で作れないため、Pod の中で Homarr の CLI を実行する(`kubectl exec`。接続は `vault/k3s.yml` のトークン)。
- 実行のたびにパスワードを設定し直し、そのユーザーのセッションを切る。パスワードを変えるときは、`vault/homarr.yml` を変えてから実行する。
- 先に [playbooks/k3s/homarr.yml](../k3s/README.md) を適用しておく。ユーザーを作ったあと、初回の設定(管理者にする外部グループなど)は、このユーザーでログインして画面で行う。
- パスワードは標準入力で Pod へ渡すが、Pod の中では CLI の引数になる。API のトークンは、実行中の `kubectl` の引数に載る(開発コンテナの中のプロセスから見える)。

## k3s_app_remove.yml

- 使わなくなったアプリを、クラスタから取り除く。Helm のリリースを消し、namespace ごと消す。**ボリュームのデータも消える。**
- 取り違えを防ぐため、消す namespace の名前を `k3s_app_remove_confirm` にも渡す。クラスタ自体の namespace(`kube-system` など)と、ほかのアプリが頼る基盤(MetalLB、cert-manager、Longhorn、CloudNativePG、Authentik とその PostgreSQL)は消せない。
- リリース名が namespace と違うときは、`-e k3s_app_remove_release=<名前>` を付ける。リリースが見つからないときは止まる(リリースを消したあとの残りを消すときは `-e k3s_app_remove_no_release=true`)。
- 専用の DB(PostgreSQL)を持つアプリは、DB の namespace(`<アプリの namespace>-db`)も、この playbook で別に消す。
- 消すのはクラスタの中だけ。ロール・playbook・vault・インベントリのホスト名・Authentik の OIDC クライアントは、別に取り除く。
