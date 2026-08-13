# wg-easy.yml
起動済みのVMに [wg-easy](https://github.com/wg-easy/wg-easy)(WireGuardのVPNサーバー +
Web UI)をDocker Composeで構築します。**認証は既定でOIDC**を使います。

⚠ **OAuth/OIDCは `15.4.0-beta.1` で追加された機能です。** 安定版(`15.3.0` 以前)では
`OAUTH_*` が無視され、ログイン画面はユーザー名/パスワードだけになります。
そのため既定のイメージタグは**ベータ版**(`15.4.0-beta.1`)です。
パスワード認証だけで使う場合は `-e "wg_easy_version=15.3.0"` のように安定版を指定してください。

接続情報と共通オプションは [README](../README.md#全playbook共通の指定) を参照してください。

```sh
# OIDC(Authentik等)で認証する既定の構成
ansible-playbook playbooks/vms/wg-easy.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名> \
    wg_easy_init_host=vpn.example.com \
    wg_easy_oauth_oidc_server=https://auth.example.com \
    wg_easy_oauth_oidc_client_id=<クライアントID> \
    wg_easy_oauth_oidc_client_secret=<クライアントシークレット>"

# パスワード認証だけで使う(OIDCを設定しない)
ansible-playbook playbooks/vms/wg-easy.yml -vv \
-e "vm_ip=192.168.10.60 vm_ssh_user=wg vm_ssh_prikey=~/.ssh/id_ed25519_wg \
    wg_easy_init_host=vpn.example.com wg_easy_oauth_providers="
```

- `wg_easy_init_host` は **クライアントから見た接続先**(FQDNまたはグローバルIP)です。
  VMのLAN内IPではありません。**未指定なら実行前に停止します**
- 管理者パスワードは未指定なら自動生成し、VM内の `/opt/wg-easy/.env` に保存します
- ⚠ **ルーターでUDP 51820をこのVMへ転送**しないと、外からVPN接続できません

## 認証の考え方
wg-easyは**まず管理者アカウントを1つ作り**、そこにOIDCのアカウントを紐付ける作りです。

1. 初期セットアップ(`INIT_*`)で管理者を作成 — このplaybookが自動で行います
2. その管理者でログインし、OIDCでログインし直してアカウントを紐付ける
3. 紐付けが済んだら、必要に応じて `wg_easy_disable_password_auth=true` で
   パスワード認証を止める(**先に紐付けを済ませないと締め出されます**)

`wg_easy_oauth_auto_register=true` にすると、OIDCでログインした未登録の利用者を
自動作成できます。⚠ **作られる利用者は管理者権限**になるため、
`wg_easy_oauth_allowed_domains` でメールドメインを絞ってください。

### OIDCプロバイダ側の設定
プロバイダ側に**リダイレクトURIの登録**が必要です。URLは
**ブラウザでwg-easyを開くときのホスト**から組み立てられ、
**プロトコルは `wg_easy_insecure` で決まります**(`true`なら`http`、`false`なら`https`)。

```
# 既定(wg_easy_insecure=true、LAN内からIPで開く場合)
http://<VMのIP>:51821/api/auth/oidc/callback   ← ログイン用
http://<VMのIP>:51821/api/auth/oidc/link       ← 既存アカウントとの紐付け用

# リバースプロキシでHTTPS化した場合(wg_easy_insecure=false)
https://vpn.example.com/api/auth/oidc/callback
https://vpn.example.com/api/auth/oidc/link
```

⚠ ブラウザで開くURL(IPで開くのか、FQDNで開くのか)と**完全に一致**する必要があります。

wg-easy側の要件は次のとおりです(いずれもプロバイダ側の設定項目)。

- PKCE に対応していること
- スコープ `openid email profile`
- クライアント認証方式が `client_secret_post`
- **プロバイダは有効な証明書のHTTPSで公開されていること**

## 必要なスペック
**Debian(cloud image)のVM専用**です。他のディストリビューションでは実行前に停止します。

| 項目 | 必要量 |
| --- | --- |
| CPU / RAM | 1コア / 512MB以上(暗号化処理が中心のため、回線が太いならCPUを増やします) |
| ディスク | **8GB以上**。イメージは展開後およそ100MB、データは鍵とクライアント情報だけです |

WireGuardのカーネルモジュールはDebian 13の標準カーネルに含まれています
(公式の構成に合わせて `/lib/modules` を読み取り専用でマウントします)。

## 指定できる項目
**コンテナの環境変数はすべて変数として指定できます**(対応は下の表)。
未指定の項目は `.env` に書き出さず、イメージ側の既定値が使われます。

### 基本設定
| 変数 | 環境変数 | 既定値 | 内容 |
| --- | --- | --- | --- |
| `wg_easy_ui_port` | `PORT` | `51821` | Web UIのポート(VM側の公開ポートとコンテナ内の待ち受けの両方) |
| `wg_easy_host` | `HOST` | `0.0.0.0` | コンテナ内でWeb UIが待ち受けるアドレス |
| `wg_easy_insecure` | `INSECURE` | `true` | HTTPでのアクセスを許可する(後述) |
| `wg_easy_disable_ipv6` | `DISABLE_IPV6` | `false` | IPv6を使わない(DockerネットワークもIPv4のみになります) |
| `wg_easy_disable_version_check` | `DISABLE_VERSION_CHECK` | `false` | 更新確認を無効化する |
| `wg_easy_experimental_awg` | `EXPERIMENTAL_AWG` | `false` | AmneziaWG(実験的機能) |
| `wg_easy_debug` | `DEBUG` | (イメージ既定) | ログの詳細度。例: `Server,WireGuard` |
| `wg_easy_extra_env` | (任意) | `{}` | 上に無い環境変数を足す |

### 初期セットアップ(初回起動時のみ有効)
| 変数 | 環境変数 | 既定値 | 内容 |
| --- | --- | --- | --- |
| `wg_easy_init_enabled` | `INIT_ENABLED` | `true` | ウィザードを飛ばして自動セットアップする |
| `wg_easy_init_username` | `INIT_USERNAME` | `admin` | 管理者のユーザー名 |
| `wg_easy_init_password` | `INIT_PASSWORD` | 自動生成 | 管理者のパスワード |
| `wg_easy_init_host` | `INIT_HOST` | **(必須)** | クライアントの接続先(FQDN / グローバルIP) |
| `wg_easy_init_port` | `INIT_PORT` | `wg_easy_wg_port` | クライアントの接続先ポート |
| `wg_easy_init_dns` | `INIT_DNS` | (アプリ既定) | クライアントに配るDNS。例: `1.1.1.1,8.8.8.8` |
| `wg_easy_init_ipv4_cidr` / `_ipv6_cidr` | `INIT_IPV4_CIDR` / `INIT_IPV6_CIDR` | (アプリ既定) | VPNのアドレス範囲。**2つセットで指定** |
| `wg_easy_init_allowed_ips` | `INIT_ALLOWED_IPS` | (アプリ既定) | クライアントのAllowedIPs。例: `0.0.0.0/0,::/0` |

⚠ `INIT_*` が効くのは**初回起動時だけ**です。構築済みのサーバーの設定は
Web UIから変更してください(再実行しても `.env` が変わるだけで反映されません)。

⚠ `INIT_IPV4_CIDR` と `INIT_IPV6_CIDR` は**片方だけの指定が無視される**仕様のため、
片方だけ指定した場合は実行前に停止します。

### 外部認証
| 変数 | 環境変数 | 既定値 | 内容 |
| --- | --- | --- | --- |
| `wg_easy_oauth_providers` | `OAUTH_PROVIDERS` | `oidc` | 使うプロバイダ。`oidc` / `google` / `github` をカンマ区切り。空でパスワードのみ |
| `wg_easy_oauth_oidc_server` | `OAUTH_OIDC_SERVER` | (oidcで必須) | OIDCプロバイダのURL |
| `wg_easy_oauth_oidc_client_id` | `OAUTH_OIDC_CLIENT_ID` | (oidcで必須) | クライアントID |
| `wg_easy_oauth_oidc_client_secret` | `OAUTH_OIDC_CLIENT_SECRET` | (oidcで必須) | クライアントシークレット |
| `wg_easy_oauth_oidc_name` | `OAUTH_OIDC_NAME` | `OIDC` | ログイン画面に表示される名前。例: `Authentik` |
| `wg_easy_oauth_auto_register` | `OAUTH_AUTO_REGISTER` | `false` | 未登録の利用者を自動作成(⚠ 管理者権限で作られます) |
| `wg_easy_oauth_allowed_domains` | `OAUTH_ALLOWED_DOMAINS` | (制限なし) | ログインを許可するメールドメイン |
| `wg_easy_oauth_auto_launch` | `OAUTH_AUTO_LAUNCH` | (なし) | ログイン画面から自動で飛ばすプロバイダ |
| `wg_easy_oauth_google_client_id` / `_secret` | `OAUTH_GOOGLE_*` | (googleで必須) | Google OAuth |
| `wg_easy_oauth_github_client_id` / `_secret` | `OAUTH_GITHUB_*` | (githubで必須) | GitHub OAuth |
| `wg_easy_disable_password_auth` | `DISABLE_PASSWORD_AUTH` | `false` | パスワード認証を止める(⚠ 紐付け後に) |

### その他(環境変数ではない項目)
| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `wg_easy_install_dir` | `/opt/wg-easy` | 設置先 |
| `wg_easy_version` | `15.4.0-beta.1` | イメージタグ。**OIDCにはこれ以降が必要**(安定版は `15.3.0`、master追従は `edge` / `nightly`) |
| `wg_easy_image` | `ghcr.io/wg-easy/wg-easy` | イメージ名 |
| `wg_easy_container_name` | `wg-easy` | コンテナ名 |
| `wg_easy_wg_port` | `51820` | WireGuardの公開ポート(UDP) |
| `wg_easy_ui_bind` | `0.0.0.0` | Web UIを公開するVM側のアドレス(`127.0.0.1` でVM内のみ) |
| `wg_easy_network_*` | 公式と同じ | コンテナが使うDockerネットワークのサブネット / アドレス |
| `wg_easy_ready_retries` / `_delay` | `30` / `5` | Web UI起動待ちのリトライ回数 / 間隔(秒) |
| `wg_easy_health_retries` / `_delay` | `12` / `10` | WireGuard起動待ちのリトライ回数 / 間隔(秒) |
| `wg_easy_oauth_min_version` | `15.4.0-beta.1` | OAuth/OIDCが使える最小バージョン(エラーメッセージに使います) |

### HTTPでのアクセス(`wg_easy_insecure`)
wg-easyは既定ではHTTPS経由での利用を前提にしています(`INSECURE=false` だと
HTTPではログインできません)。このロールは**LAN内からIPで直接開く前提**のため
`true` にしています。

- ⚠ **この値はOIDCのリダイレクトURIのプロトコルにもなります**(`true`なら`http://`)。
  リバースプロキシ(Traefik / Caddy / nginx)でHTTPS化する場合は
  `-e "wg_easy_insecure=false"` にして、プロバイダ側の登録も `https://` に揃えてください
  (OIDC**プロバイダ**側は、どちらの場合も有効な証明書のHTTPSである必要があります)
- Web UIをLANにも晒したくない場合は `wg_easy_ui_bind=127.0.0.1` にして
  SSHポートフォワード経由で開きます

```sh
ssh -i ~/.ssh/<秘密鍵> -L 51821:127.0.0.1:51821 <SSHユーザ名>@<VMのIP>
# → 手元のブラウザで http://127.0.0.1:51821/
```

## 実施する内容
1. OS確認(**Debianであること**)、変数の検証(環境変数の組み合わせを含む)
2. [全VM共通のセットアップ](../README.md#共通セットアップtasks)(OS更新、タイムゾーン、
   ロケール、zram、sudoグループ、基本パッケージ、QEMUエージェント)
3. Dockerの導入(`get.docker.com`)と、SSHユーザーのdockerグループ追加
4. `etc_wireguard/` の作成(鍵が入るためroot専用・`0700`)
5. `.env` の配置(未指定の項目は書き出しません)
6. `docker compose up`(**設定が変わった場合はコンテナを作り直します**)
7. ufwが導入済みかつ有効な場合のみポートを開放(通常はスキップ)
8. **コンテナが起動し続けているか**の確認(落ちている場合はログを表示して停止)
   → Web UIの応答確認 → **外部認証が実際に有効か**の確認(後述)
   → **WireGuardのインターフェースが起動したか**の確認
9. VM再起動 → コンテナが自動復帰し、実行元の端末からWeb UIが見えることを確認

## 外部認証が有効かの確認
設定したのに使えていない状態(バージョンが古い、環境変数の綴り違いなど)を見逃さないよう、
構築の最後に**アプリ自身が公開しているログイン方式のAPI**(`/api/auth/methods`)を
問い合わせて、指定したプロバイダが実際に有効かを確認します。

有効になっていない場合は、原因(APIが無い = バージョンが古い / プロバイダが空)を
表示して**エラーで停止**します。`OAUTH_*` は非対応バージョンでは黙って無視されるため、
ここで止めないと「ログイン画面にOIDCが出ない」ことに後から気付くことになります。

```sh
# VM内でも同じものを確認できます
curl -s http://127.0.0.1:51821/api/auth/methods
# {"providers":{"oidc":{"enabled":true,...}},"oauthEnabled":true,...}
```

## 構成されるもの
| パス | 内容 |
| --- | --- |
| `/opt/wg-easy/docker-compose.yml` | Compose定義(Ansibleが生成。手動編集は上書きされます) |
| `/opt/wg-easy/.env` | 環境変数(root所有・`0640`・dockerグループのみ読み取り可) |
| `/opt/wg-easy/etc_wireguard` | サーバーの鍵・クライアント情報(**root専用・`0700`**) |

公式の構成に合わせて、コンテナには `NET_ADMIN` / `SYS_MODULE` と
WireGuardに必要な `sysctls` を与え、専用のDockerネットワーク(`10.42.42.0/24`)に
固定アドレスで接続します。

## 運用
```sh
# VM内(SSHユーザーのまま。dockerグループに入っています)
cd /opt/wg-easy
docker compose ps
docker logs -f wg-easy
docker exec wg-easy wg show          # ピアの状態
sudo grep INIT_PASSWORD /opt/wg-easy/.env
```

⚠ 停止・起動は **`docker compose up` / `down`** を使ってください
(`start` / `stop` では状態が中途半端になり、起動時に問題が出ることがあります)。

### バージョンアップ
`-e "wg_easy_version=15.4.0"` を付けて再実行するとそのタグに入れ替わります
(指定しなければ既定のタグのままで、**勝手に上がりません**)。

### バックアップ
`/opt/wg-easy/etc_wireguard` に鍵とクライアント情報が入っています。
**このディレクトリを失うと全クライアントの再設定が必要**です。

## 再実行について
何度実行しても同じ状態になります。`.env` と `docker-compose.yml` のどちらも
変わらなければコンテナは作り直されず、クライアント情報もそのまま残ります。
ただし `INIT_*` は初回起動時にしか効かないため、**再実行で管理者パスワードや
接続先が変わることはありません**(変更はWeb UIから)。

## うまくいかないとき
| 症状 | 確認すること |
| --- | --- |
| 「クライアントの接続先が必要です」で止まる | `wg_easy_init_host` を指定しているか(外から見たFQDN / グローバルIP) |
| 「OIDCを使うには…3つが必要です」で止まる | サーバー・クライアントID・シークレットが揃っているか |
| 「コンテナが起動し続けられていません」で止まる | 表示されたログを確認。DockerのIPv6が有効か(`wg_easy_disable_ipv6=true` で回避可) |
| WireGuardが起動しない(注意が出る) | `sudo docker logs wg-easy`。`INIT_*` の4項目(ユーザー名・パスワード・接続先・ポート)が揃っているか |
| 「wg-easy側で有効になっていません」で止まる | イメージタグが `15.4.0-beta.1` 以降か(安定版はOAuth非対応) |
| ログイン画面にOIDCのボタンが出ない | 同上。`curl http://127.0.0.1:51821/api/auth/methods` で `oauthEnabled` を確認 |
| ログインできない | HTTPで開いていて `INSECURE=false` になっていないか。パスワードは `.env` の `INIT_PASSWORD` |
| OIDCでログインすると失敗する | プロバイダ側のリダイレクトURI(`/api/auth/oidc/callback` と `/link`)、PKCE、`client_secret_post` の設定 |
| OIDCの後に締め出された | `wg_easy_disable_password_auth=false` に戻して再実行し、パスワードでログインして紐付け直す |
| クライアントが繋がらない | ルーターでUDP 51820がVMへ転送されているか。`wg_easy_init_host` が現在のグローバルIPを指しているか |
| 繋がるが通信できない | クライアント側のAllowedIPs、VM側の `docker logs`。VPN先のDNS(`INIT_DNS`)が届くか |
