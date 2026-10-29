# k3s_openwebui

OpenWebUI を Helm で入れ、Authentik の OIDC でログインできるようにする。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/openwebui.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_openwebui` と `defaults/main.yml`。

前提: CloudNativePG のオペレーターが入っている(`playbooks/k3s/cnpg.yml`)。専用の PostgreSQL(namespace `open-webui-db`。pgvector の拡張を作る)は、このロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。OIDC のクライアントは [k3s_authentik](../k3s_authentik/README.md) の Blueprint で宣言する(同じ `vault/openwebui.yml` の client_secret を使う)。

## 注意

- ボリュームを持たない。ユーザー、チャット、設定、RAG のベクトルは PostgreSQL にある。アップロードしたファイルの実体は、Pod を作り直すと消える。
- LLM への接続(LiteLLM など)は、管理画面で登録する。OpenWebUI の設定は、環境変数が初回だけ使われ、以降は画面で変えた値が DB に保存されて優先される場合がある。
- 更新で DB のマイグレーションが走る。上げる前に、DB のバックアップを考える(現在はバックアップなし)。
- 緊急用の管理者(`openwebui_admin_email`、パスワードは `vault/openwebui.yml`)は、ユーザーが1人もいない初回の起動時にだけ作られる。あとから vault の値を変えても、パスワードは変わらない(画面で変える)。既にユーザーがいる DB に入れたときは作られないので、管理画面で同じメールアドレスと vault のパスワードの管理者を作る。
- Authentik のグループから権限を決める対応づけは、Ansible では設定しない。緊急用の管理者でログインし、管理画面の OAuth の設定で行う(`ENABLE_OAUTH_PERSISTENT_CONFIG` で、画面からの変更を許している)。設定するまで、SSO で新しく入ったユーザーは、OpenWebUI の既定の役割(管理画面の設定)になる。
- 管理画面で OAuth の設定を保存すると、その値は DB に残り、環境変数より優先される。接続先や client_secret を画面で保存したあとは、Ansible で変えても反映されないので、画面でも直す。
- 外部(Cloudflare Tunnel)に公開するのは、インベントリの `cloudflared_hosts` に `openwebui_host` があるとき。外からは、このアプリのパスワードのログイン(緊急用の管理者)を通さない。公開ホスト名は LAN からも Tunnel を通るため、緊急用の管理者でログインするときは、使う端末の hosts ファイルで `<openwebui_host>` を `172.16.12.5` に向けてから開く。
- Pod が受ける通信を、同じ namespace と Traefik に絞る(NetworkPolicy)。
- パスワードでの新規登録は受け付けない。
- SSO でのアカウント作成とメールでの統合を有効にしている。Authentik では、ユーザーが自分でメールアドレスを変えられないようにする。
