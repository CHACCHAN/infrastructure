# k3s_litellm

LiteLLM Proxy(LLM API のゲートウェイ)を Helm で入れる。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/litellm.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_litellm` と `defaults/main.yml`。

前提: PostgreSQL に `litellm` の DB とロールがある。

モデルとプロバイダーの認証情報は、管理画面(`https://<litellm_host>/ui`。Authentik の SSO でログインする)で登録する。Hermes Agent が使うモデルの名前は `hermes_llm` にする。宣言で持ちたいモデルは、`litellm_models`(プロキシの `model_list`)と `vault_litellm_provider_keys`(環境変数名をキーにした辞書)でも足せる。

## 注意

- 管理画面は Authentik の SSO でログインする。グループ `litellm_admin_group`(既定は `admins`)のユーザーが管理者(`proxy_admin`)になる。管理画面を使えるユーザーを管理者だけに絞るのは、Authentik の画面で、LiteLLM のアプリケーションにそのグループを結びつけて行う。
- 緊急用の管理者(`litellm_ui_username`、パスワードは `vault_litellm_ui_password`)は、`https://<litellm_host>/fallback/login` からパスワードでログインする。
- Pod が受ける通信は、同じ namespace、Traefik、`litellm_client_namespaces`(既定は OpenWebUI の namespace)に絞る。OpenWebUI からは、クラスタ内の Service(`http://litellm.<namespace>.svc.cluster.local:4000`)へ直接つなげる。
- マスターキー(`vault_litellm_master_key`)は API の鍵で、管理画面のログインには使えない。
- 管理画面で登録したモデル・認証情報・仮想キーは DB に保存される(状態で、Ansible では管理しない)。
- 認証情報は `vault_litellm_salt_key` で暗号化される。モデルを登録したあとにこのキーを変えると、登録済みの認証情報が読めなくなる。
