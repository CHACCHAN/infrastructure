# Hermes Agent 設計

Hermes Agent と、このリポジトリとの境界。ネットワークは [network.md](network.md)、クラスタ内アプリとの接続は [k3s.md](k3s.md)。

## 決定済み

### 置き場所と Ansible が持つ範囲

- Hermes Agent は、開発専用機(ubuntu-dev `172.16.11.1`)の専用のユーザーで動かす(オーナーの決定)。Hermes 用の VM は置かない。
- Ansible が持つのは、Hermes の認証の定義と存在の定義だけ([k3s.md](k3s.md) の「再現性の範囲」)。
  - 認証の定義: Authentik の OIDC クライアント `hermes`・`hermes-security`・`hermes-platform`(`inventory/group_vars/authentik.yml`。シークレットは `vault/hermes.yml` で決め、Hermes 側の設定にも同じ値を入れる)。
  - 存在の定義: 管理画面の入口 `hermes.<lab_domain>`(開発専用機の9120番。k3s の Traefik の `k3s_lan_proxy`。Cloudflare Tunnel には載せない)。開発専用機はインベントリに無いため、`lan_proxy_extra_services` に IP を直接書く。
  - 秘密の控え: Hermes が使う Authentik のユーザーのパスワード・TOTP の種、Nextcloud のアプリパスワード、OPNsense の API キー(`vault/hermes.yml`・`vault/nextcloud_hermes.yml`・`vault/opnsense.yml`。どの playbook も読まない)。
- 開発専用機の OS、Hermes の導入・本体・版、モデル、チャネル、常駐、スキル、メモリ、管理画面の設定は、Ansible では管理しない(Hermes と開発専用機の側の状態)。
- 組織同士の関係(やり取りの方式、互いをどこまで信用するか、相互の監視)は、Hermes が自分で設計する。Ansible と、このリポジトリの設計では決めない。

### 管理画面

- ログインは Hermes 側の OIDC。Hermes のコールバックのパスは Hermes の側で決まるため、Authentik は `https://hermes.<lab_domain>/` の下のパスをすべて許可する(正規表現)。パスが決まったら、完全一致に絞る。
- 必要な通信は、k3s の全ノード(VLAN12)から `172.16.11.1:9120` と、開発専用機から Authentik(`172.16.12.5:443`)。開発専用機の ufw で、k3s の全ノード(`172.16.12.1`〜`.3`)から 9120番だけを通す(開発専用機の側の状態)。
- Hermes は k3s のアプリではないため、[k3s.md](k3s.md) の緊急用のユーザーの規則の対象外。ログインの方法は Hermes 側の状態。

### 権限と秘密

- インフラを操作させる Hermes には、このリポジトリの複製と vault のパスワードを置く(オーナーの決定。Proxmox・OPNsense・k3s も Hermes に管理させるため)。開発専用機は、ラボの秘密情報をすべて読めるものとして扱う。

### Authentik・Nextcloud との接続

- Hermes Agent は、Authentik のユーザー `HermesAgent` で、MCP for Cloud(Nextcloud のアプリ `mcp`)から Nextcloud を操作する。ほかの人と同じく Authentik の SSO(`user_oidc`)で作る Nextcloud のユーザーにし、Nextcloud のローカルのユーザーは置かない(ほかのアプリへ OIDC で広げるときも、アカウントを Authentik の1か所で管理するため)。Nextcloud のユーザー ID は `user_oidc` が作るハッシュになる。ユーザーとグループの所属は Authentik の画面で設定する(状態)。
- `HermesAgent` は Authentik のグループ `services` にだけ入れ、`admins` には入れない(`admins` は Authentik の superuser で、認証プロキシで守る画面と各アプリの管理者の権限を持つため)。`services` は Hermes Agent が自動で管理するためのグループで、認証プロキシで守る画面(`authentik_proxy_access_groups`。Longhorn・CLIProxyAPI・AM・APIM のコンソール)と LiteLLM の管理者(`litellm_admin_groups`)に入れる(宣言)。ほかに Authentik で結びつけるのは Nextcloud のアプリケーション(状態)。緊急用の `admin` は渡さず、Nextcloud の `admin` グループにも入れない(Nextcloud の管理者は、アプリを入れて k3s の中の Nextcloud の Pod でコードを動かせるため)。
- Authentik のログインのパスワードは機械的に作った値で、`vault/nextcloud_hermes.yml` に置く。MFA は TOTP で、その種(`vault_authentik_hermes_agent_totp_secret`)も同じファイルに置く。インフラを操作させる Hermes は、vault からこの2つを読んで、自分で Authentik にログインする(LiteLLM の管理画面、認証プロキシで守る画面)。メールアドレスは `hermes@cc-chacchan.com`(LiteLLM の SSO は、メールアドレスが空のユーザーを受け付けない)。
- `hermes-security`・`hermes-platform` の Hermes は、それぞれ Authentik のユーザー `HermesSecurity`・`HermesPlatform`(メールアドレスは `hermes-security@cc-chacchan.com`・`hermes-platform@cc-chacchan.com`)を使い、`HermesAgent` を共用しない(状態。Ansible では管理しない)。役割に要る分だけ、グループに足す。パスワードと `HermesSecurity` の MFA の TOTP の種(`vault_authentik_hermes_security_totp_secret`)は `vault/hermes.yml`、`HermesSecurity` の Nextcloud のアプリパスワード(`vault_nextcloud_hermes_security_mcp_auth`・`vault_nextcloud_hermes_security_app_password`)は `vault/nextcloud_hermes.yml` に置く。
- LiteLLM のアプリケーションには、Authentik の画面で `admins` と `services` のグループを結びつけている(状態。Ansible では管理しない)。
- OPNsense も Hermes Agent が管理する。OPNsense のアプリケーションには、Authentik で `admins` と `services` のグループを結びつけている(状態。Ansible では管理しない)。Hermes が使う OPNsense の API キーは、`HermesSecurity` が OIDC で OPNsense にログインして作られたユーザーのもの(`vault/opnsense.yml` の `vault_opnsense_hermes_api_key` / `vault_opnsense_hermes_api_secret`)。
- Nextcloud の認証は、アプリパスワードでの Basic 認証にする(Nextcloud はクライアントにアプリパスワードだけを許す。[k3s.md](k3s.md))。SSO のユーザーはログインのパスワードを Nextcloud に持たないため、Authentik のパスワードを変えてもアプリパスワードは無効にならない。`<Nextcloud のユーザー ID>:<アプリパスワード>` を base64 にした値は、Hermes の側の MCP の設定に入れる。控えは `vault/nextcloud_hermes.yml` に、base64 にした値とアプリパスワードそのものの両方を置く(作り直すときは両方を更新する)。漏れたときは、アプリパスワードを取り消して作り直す。
- MCP for Cloud の権限は、すべての操作を許す(削除・共有・公開リンク・Talk の会話の作成を含む)。サーバーのログは管理者用のため付けない。Nextcloud の中での権限は普通のユーザーと同じで、管理させるもの(Deck のボード、カレンダー、フォルダなど)は人が `HermesAgent` に共有する。コレクティブは、`services` のグループを普通のメンバーとして足す。
- ユーザー・アプリパスワード・MCP for Cloud の導入と権限は、Nextcloud の状態で、Ansible では管理しない。

## 確認が要る事項

- Hermes の管理画面のログイン(OIDC)が有効になっていること。プロキシは認証を掛けないため、管理画面が認証なしで動くと、`hermes.<lab_domain>` から LAN にそのまま出る。

## 未決

- Hermes に Proxmox・OPNsense・k3s を管理させるときの、権限の細かさ(API トークンの権限の範囲、OPNsense の管理者のユーザーを分けるか)。管理させることは決まっている。
- vault のパスワードを持つ Hermes(開発専用機)が乗っ取られたときの影響を、どこで抑えるか(VLAN 間の FW、監査のログ)。
- 開発専用機の上の Hermes の隔離。VM の境界が無く、`docker` グループに入れると開発専用機の root と同じことができ、同じマシンのほかのユーザーの環境(SSH 鍵を含む)に届く。
- LLM の接続先(LiteLLM の `hermes_llm`。[k3s.md](k3s.md))の仮想キーと予算を、Hermes ごとに分けるか。
- Hermes の状態(開発専用機のホーム)の保護。
