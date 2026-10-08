# coolify.yml — Coolify(セルフホストPaaS)を構築する

Coolify v4をVMごと一気通貫で構築する。導入は公式install.sh(バージョン固定・再実行=アップグレード)で、Coolifyは自身の内蔵プロキシ(Traefik)を:80/:443に立て、デプロイしたアプリと管理UIをHostヘッダで捌く。

## 公開経路(このリポジトリでの扱い)

TLSは**k3s側のTraefikで終端**し、VMの:80へHTTPで転送する(Authentikと同じ`k8s_external_routes`方式)。

| ホスト | 用途 | 公開範囲 |
| --- | --- | --- |
| `coolify.cc-chacchan.com` | 管理UI(内蔵プロキシ経由。WebSocketも:80へ集約される) | LAN内のみ |
| `*.web.cc-chacchan.com` | デプロイしたアプリ | LAN + Cloudflare Tunnel到達可(公開の可否はCloudflare側の経路表) |

- 証明書: `*.web.cc-chacchan.com` は `*.cc-chacchan.com` ではカバーされない(LEワイルドカードは1階層のみ)ため、Certificateの**SANに含めている**(`roles/k8s_certificates`)。DNSレコード(`*.web` → Traefik)は別途設定する
- Coolify側の設定(構築後にWeb UIで1回):
  - Settings → **URL(Instance Domain)** = `https://coolify.cc-chacchan.com`、**Redirect HTTP to HTTPS = 必ずDisabled**。
    TLSは手前のk3sで終端し内蔵プロキシへは常にHTTP(:80)で届くため、Enabledにすると
    302→:80→302…の**無限リダイレクトループ**になる(内蔵Traefikのredirectschemeは
    X-Forwarded-Protoを見ない)。URLをhttpsにしておくと
    APP_URL・Cookie・WebSocket URLが外側TLSと整合する。/app(リアルタイム)と
    /terminal/ws(ターミナル)のルーターは:80側にも自動生成されるためそのまま動く
  - Servers → localhost → **Wildcard Domain** = `http://web.cc-chacchan.com`(新規アプリへ `<名前>.web.cc-chacchan.com` が自動割当される。アプリ個別のドメインは**httpスキーム**で登録する=アプリごとのLet's Encrypt発行を発生させない)
  - Servers → localhost → **Proxy → Configuration**(Traefikのcompose定義)の `command:` へ以下の2行を追加してプロキシを再起動する。**これが無いと内蔵TraefikがX-Forwarded-Proto: httpsを破棄して`http`で上書きし、アプリの生成URLが全てhttpになる**(httpsページでCSSがmixed contentブロックされる・リダイレクトがhttpへ飛ぶ。送信元はk3sノードの172.16.12.0/24):

    ```yaml
          - '--entrypoints.http.forwardedHeaders.trustedIPs=172.16.12.0/24'
          - '--entrypoints.https.forwardedHeaders.trustedIPs=172.16.12.0/24'
    ```
  - Settings → Advanced → **DNS validation を無効化**(インスタンスURLの検証が「公開IPへのAレコード」を要求するが、この環境はスプリットDNS(LAN内解決)のため常に失敗する。検証が失敗しても設定自体は保存される)

## 実行方法

```sh
# インベントリ実行(coolifyグループの宣言どおり)
ansible-playbook playbooks/vm/coolify.yml

# 初期root管理者を事前作成する場合(3つセット。未指定ならWeb UI初回アクセスで作成)
ansible-playbook playbooks/vm/coolify.yml \
  -e coolify_root_username=admin -e coolify_root_user_email=admin@example.com \
  -e coolify_root_user_password=<パスワード>

# 経路の反映(証明書SANとTraefikルート)
ansible-playbook playbooks/k8s/deploy.yml -e app=certificates
ansible-playbook playbooks/k8s/deploy.yml -e app=external
```

## 変数一覧

接続系の共通変数は [README.md](README.md#共通の変数)。全既定値の正は [roles/vm_coolify/defaults/main.yml](../../roles/vm_coolify/defaults/main.yml)。

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `coolify_version` | str | | `4.3.9` | 固定する版。上げるときはここを変えて再実行(=アップグレード) |
| `coolify_autoupdate` | bool | | `false` | 本体の自動更新。宣言管理のため既定で無効 |
| `coolify_root_username` / `_user_email` / `_user_password` | str | | なし | 初回インストール時のroot管理者事前作成(3つセット。2回目以降は無視される) |
| `coolify_ui_port` | int | | `8000` | Web UI(初回セットアップとLAN内直接アクセス用) |
| `coolify_min_free_disk_gb` | int | | `20` | 事前チェックの必要空き容量(上流要件) |

## AWXでの実行

Job Template **`vm-coolify`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。Surveyは共通セット+root管理者3問(任意)。

## つまずきやすいポイント

- **UIドメインが404** → Instance Domain未設定。まず `http://172.16.11.6:8000/` で初期セットアップし、Settingsでドメインを設定する
- **リダイレクトが無限に繰り返される** → Settings の「Redirect HTTP to HTTPS」がEnabledになっている(上記のとおりDisabledが必須)
- **CSSが当たらない/httpへリダイレクトされる** → 内蔵TraefikのforwardedHeaders.trustedIPs未設定(上記のProxy設定を追加)。確認は `curl -sk -o /dev/null -w '%{redirect_url}' https://coolify.cc-chacchan.com/` がhttpsのURLを返すこと
- **アプリのURLがhttpで生成される/ログインループ** → アプリのドメイン登録スキームと、内蔵プロキシがX-Forwarded-Protoを信頼しない点に注意(UIのURL設定をhttpsにしておくのが安全)
- **`*.web` の証明書エラー** → `deploy.yml -e app=certificates` の適用漏れ、またはDNS-01用の `_acme-challenge.web` がCloudflareで解決できていない
