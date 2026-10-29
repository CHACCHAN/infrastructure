# k3s_gravitee

Gravitee API Management(APIM。汎用の API ゲートウェイと開発者ポータル)を Helm で入れる。ログインは、Gravitee Access Management([k3s_gravitee_am](../k3s_gravitee_am/README.md))を経由する Authentik の SSO。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/gravitee.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_gravitee` と `defaults/main.yml`。

前提:

- CloudNativePG のオペレーターが入っている(`playbooks/k3s/cnpg.yml`)。専用の PostgreSQL(namespace `gravitee-db`)は、このロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。
- `playbooks/k3s/authentik.yml` でコンソールの認証プロキシを作り、グループ `admins` に所属している。Blueprint の適用前はコンソールを開けない。
- AM を入れ、AM の画面での設定(ドメイン `apim` と、Client ID `gravitee` のアプリケーション)を済ませてある([k3s_gravitee_am](../k3s_gravitee_am/README.md))。

| ホスト | パス | 向け先 | 公開 |
| --- | --- | --- | --- |
| `gravitee_host` | `/` | ポータルの画面 | LAN・Tunnel |
| `gravitee_host` | `/portal` | ポータル API | LAN・Tunnel。Tunnel では `Authorization` を持つ要求を通さない |
| `gravitee_host` | `/gateway` | ゲートウェイ(API の呼び出し。接頭辞を除いて転送する) | LAN・Tunnel |
| `gravitee_console_host` | `/console/` | コンソール(管理画面) | LAN・VPN。Authentik の認証プロキシ(`admins`) |
| `gravitee_console_host` | `/management` | 管理 API | LAN・VPN。Authentik の認証プロキシ(`admins`) |

## ログインと権限

- ポータル(`https://<gravitee_host>/`)とコンソール(`https://<gravitee_console_host>/console/`)は、AM のボタンからログインし、Authentik へ進む。ポータルは、ログインしないと何も表示しない。コンソールは画面の前に Authentik の認証プロキシを通り、`admins` だけが開ける。
- ログインのたびに、Authentik が渡すグループで権限を決め直す。`admins` は組織と環境の管理者、それ以外のユーザー(`externals` など)は利用者(API の参照、アプリケーションの作成、購読、API キーの発行)。API を登録できるのは `admins` だけ。
- コンソールで、ユーザーにロールを手で付けない。手で付けたロールは、ログインのたびの決め直しで消えず、グループより優先される。
- 緊急用の `admin`: AM が使えず Authentik が使えるときは、LAN か VPN から `https://<gravitee_console_host>/console/` を開き、認証プロキシを通ったあと、ユーザー `admin`、パスワード `vault_gravitee_admin_password`(`ansible-vault view vault/gravitee.yml`)でログインする。Tunnel からは、パスワードでログインできない。
- Authentik が使えないときはコンソールを開けない。k3s01 で `sudo k3s kubectl port-forward -n gravitee svc/gravitee-api 8083:83` を実行し、開発マシンから `ssh -L 8083:localhost:8083 <k3s01>` でつないで、`http://localhost:8083/management/` の管理 API を緊急用の `admin` で使う。namespace と Service 名は既定値(`gravitee_namespace` と `gravitee_release_name`)に合わせる。コンソール UI は管理 API の絶対 URL を呼ぶため、ポート転送では使えない。ゲートウェイと発行済みの API キーは引き続き使える。

## LiteLLM を API として登録する

API・プラン・購読・API キーは状態で、このロールでは作らない。管理者が、次の順にコンソールで設定する。

1. LiteLLM の管理画面で、APIM 専用の仮想キーを作る。使えるモデルと予算を絞り、マスターキーは使わない。
2. コンソールで HTTP proxy の API を作る。context path は `/llm`、バックエンドは `http://litellm.litellm.svc.cluster.local:4000`。利用者が呼ぶ URL は `https://<gravitee_host>/gateway/llm/v1/...` になる。
3. プランは API Key だけを作って公開する(Keyless は作らない)。利用者は `X-Gravitee-Api-Key` ヘッダーで API キーを送る。
4. API のフローに Transform Headers を置き、利用者が送った `Authorization` と `x-litellm-customer-id` を消してから、`Authorization: Bearer <1 の仮想キー>` と `x-litellm-customer-id: {#context.attributes['application']}`(APIM のアプリケーションの ID)を付ける。仮想キーは、API の暗号化したプロパティに置く。
5. LiteLLM の利用者(Customers)の画面で、アプリケーションごとの利用を確かめる。利用者が `x-litellm-customer-id` やリクエストの `user` を偽っても、別のアプリケーションに数えられないことを確かめる。

Gravitee の分析機能は使わないため、利用の履歴は LiteLLM で見る。レート制限は、プランのポリシーで設定し、PostgreSQL で数える。

## グループから外したとき

Authentik でグループやアプリケーションの結びつけを外しても、発行済みの API キーは使え続ける。管理者が、コンソールでそのユーザーのアプリケーションの購読を閉じ、API キーを失効させる。`admins` から外したユーザーが API の所有者(Primary owner)なら、所有者をほかの管理者へ移す。

## 注意

- Cloudflare の画面で、`gravitee.<lab_domain>` を Tunnel の経路表に足す(向け先は、ほかのホスト名と同じ Tunnel 専用の入口)。`gravitee-console.<lab_domain>` は Tunnel に載せない(ワイルドカードの DNS で `172.16.12.5` に届き、LAN と VPN からだけ使える)。
- API・購読・API キー・ユーザーは DB に保存される(状態。バックアップは無い)。
- API の暗号化したプロパティは `vault_gravitee_properties_encryption_secret` で暗号化される。プロパティを置いたあとにこのキーを変えると、読めなくなる。
- 技術 API(`services.core.http`)は無効にしている。Gateway のプローブは本体のポートを使う。
