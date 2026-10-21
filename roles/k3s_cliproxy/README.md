# k3s_cliproxy

CLIProxyAPI(Codex・Claude Code などの CLI の OAuth の認証情報を、OpenAI・Claude・Gemini 互換の API として出すプロキシ)を k3s に置く。管理画面(Management Center)だけを、`https://<cliproxy_host>/management.html` で、Authentik の認証プロキシを通して LAN に公開する。API はクラスタ内からだけ使う。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/cliproxy.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_cliproxy` と `defaults/main.yml`。

前提:

- PostgreSQL に `cliproxy` の DB とロールがある(`playbooks/k3s/postgresql.yml`)。
- 管理画面を開くには、Authentik の認証プロキシ(`playbooks/k3s/authentik.yml` の `authentik_proxy_apps` の `cliproxy`)と、グループ `admins` の所属が要る。

チャートが無いため、Deployment・Service・Ingress をマニフェストで置く(Helm のリリースは作らない)。

## 管理画面

1. `https://<cliproxy_host>/management.html` を開くと、Authentik のログインに送られる(グループ `admins` のメンバーだけが通る)。
2. 続いて管理画面が管理キーを求める。管理キーは `vault_cliproxy_management_password`(`ansible-vault view vault/cliproxy.yml`)。
3. プロバイダーの OAuth のログインは、管理画面から始める。プロバイダーはブラウザを `localhost` のコールバックへ戻すため、そのページは開けない。アドレスバーの URL を管理画面に貼り付けて完了する。

Authentik が使えないときは、k3s01 に SSH で入り、`sudo k3s kubectl port-forward -n cliproxy svc/cliproxy 8317:8317` を実行する。開発マシンから `ssh -L 8317:localhost:8317` でつなぎ、`http://localhost:8317/management.html` を開く(kubeconfig を開発マシンに置かないため)。

## API

- API は、クラスタ内の Service(`http://cliproxy.cliproxy.svc.cluster.local:8317/v1`。OpenAI 互換)からだけ使う。LAN のクライアントは、LiteLLM を経由して使う。
- 公開ホスト名(`<cliproxy_host>`)は、すべてのパスが認証プロキシを通る。外から使えるのは管理画面だけ。
- Pod が受ける通信は、同じ namespace、Traefik、インベントリの `helm_network_policies` の `cliproxy` に挙げた namespace(LiteLLM)に絞る。
- クライアントは、API キー(初期値は `vault_cliproxy_api_keys`)で認証する。

## 注意

- 設定と認証情報(プロバイダーの OAuth のトークン)は、PostgreSQL に保存される(状態)。Pod は、起動時に DB の内容を作業用のディレクトリへ書き出す。
- 設定の初期値(`vault_cliproxy_api_keys`、`cliproxy_trusted_proxies` など)は、DB が空のときだけ使われる。以降は、管理画面で変えた内容が残り、Ansible は上書きしない。vault の API キーを変えても、動いている設定には効かない(管理画面で変える)。
- 管理画面のファイル(`management.html`)は、CLIProxyAPI が起動後に GitHub の最新のリリースから取得する。CLIProxyAPI は取得先を最新のリリースに固定しているため、バージョンを固定できない。
- 作業用のディレクトリはメモリ上にあり(`cliproxy_spool_size`)、コンテナのメモリの上限に含まれる。
- 管理キーは、5回間違えると、その送信元 IP から30分間使えなくなる。
