# cloudflare-ddns-ui.yml
起動済みのVMに [cloudflare-ddns-ui](https://hub.docker.com/r/martijnf/cloudflare-ddns-ui)
(`martijnf/cloudflare-ddns-ui`)をDocker Composeで構築します。
回線の公開IPが変わったときにCloudflareの**Aレコード**を自動更新する常駐サービスで、
状況を確認できるWebダッシュボードが付いています。

接続情報と共通オプションは [README](../README.md#全playbook共通の指定) を参照してください。

```sh
ansible-playbook playbooks/vms/cloudflare-ddns-ui.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名> \
    cloudflare_ddns_ui_api_token=<APIトークン> \
    cloudflare_ddns_ui_zone_domain=example.com cloudflare_ddns_ui_zone_id=<ゾーンID> \
    cloudflare_ddns_ui_records=auth.example.com,wg.example.com"
```

- **APIトークン・ゾーン・更新するレコードの指定は必須です**(既定値はありません)
- ⚠ **ダッシュボードには認証がありません。** レコードの削除まで行える画面が
  そのまま開きます。既定では `0.0.0.0:8080` で公開されるため、LAN内の誰でも操作できます。
  見せたくない場合は `cloudflare_ddns_ui_http_bind=127.0.0.1`(後述)
- ⚠ トークンは**コマンド履歴に残ります**。`proxmox/` から構築する場合は
  [vault](../../proxmox/docs/cloudflare-ddns-ui.md#認証情報vault)から自動で渡ります

## できること・できないこと
アプリの作りがそのまま制約になります(設定できる項目はここに挙げたものだけです)。

| 項目 | 内容 |
| --- | --- |
| 対象レコード | **Aレコード(IPv4)のみ**。AAAA(IPv6)は扱いません |
| レコードの存在 | **Cloudflare側に既にAレコードが必要**です(無い場合はダッシュボードから作成できます) |
| TTL / プロキシ | 更新時に **TTL=自動・プロキシ無効**で固定されます(変更できません) |
| 公開IPの取得元 | `api.ipify.org` で固定 |
| 認証 | **ダッシュボードに認証はありません** |

TTLやプロキシを制御したい、IPv6も更新したい、といった場合はこのアプリでは対応できません。

## 必要なスペック
**Debian(cloud image)のVM専用**です。他のディストリビューションでは実行前に停止します。

| 項目 | 必要量 |
| --- | --- |
| CPU / RAM | 1コア / 512MB以上(数分おきに公開IPを確認してAPIを叩くだけです) |
| ディスク | **8GB以上**。イメージは展開後およそ50MB、データもログと更新履歴だけです |

## 指定できる項目
共通オプションに加えて以下を指定できます。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `cloudflare_ddns_ui_api_token` | **(必須)** | CloudflareのAPIトークン(Zone → DNS → Edit) |
| `cloudflare_ddns_ui_records` | **(必須)** | 更新するレコード(FQDN)。リストでもカンマ区切りでも可 |
| `cloudflare_ddns_ui_zone_domain` | **(必須)** | レコードが属するゾーン(例: `example.com`) |
| `cloudflare_ddns_ui_zone_id` | **(必須)** | 上記ゾーンのゾーンID |
| `cloudflare_ddns_ui_zones` | `{}` | 複数ゾーンを扱う場合に「ドメイン: ゾーンID」で指定(上2つより優先) |
| `cloudflare_ddns_ui_install_dir` | `/opt/cloudflare-ddns-ui` | 設置先 |
| `cloudflare_ddns_ui_version` | `v1.0.2` | イメージタグ |
| `cloudflare_ddns_ui_image` | `docker.io/martijnf/cloudflare-ddns-ui` | イメージ名 |
| `cloudflare_ddns_ui_container_name` | `cloudflare-ddns-ui` | コンテナ名 |
| `cloudflare_ddns_ui_http_port` | `8080` | ダッシュボードの公開ポート |
| `cloudflare_ddns_ui_http_bind` | `0.0.0.0` | ダッシュボードの待ち受けアドレス(後述) |
| `cloudflare_ddns_ui_interval` | `300` | 公開IPを確認してレコードを更新する間隔(秒) |
| `cloudflare_ddns_ui_refresh` | `30` | ダッシュボードの自動リロード間隔(秒) |
| `cloudflare_ddns_ui_extra_env` | `{}` | コンテナに渡す環境変数を足す(`TZ` はVMのタイムゾーンから自動設定) |
| `cloudflare_ddns_ui_ready_retries` / `_delay` | `30` / `5` | ダッシュボード起動待ちのリトライ回数 / 間隔(秒) |
| `cloudflare_ddns_ui_check_retries` / `_delay` | `12` / `5` | 1回目のレコード確認を待つリトライ回数 / 間隔(秒) |

変数の接頭辞は他のロールと同じくロール名(`cloudflare_ddns_ui_`)に揃えています。

### APIトークンの権限
Cloudflareのダッシュボードで、以下の権限のトークンを作成します。

- **権限**: Zone → DNS → Edit
- **ゾーンリソース**: 更新したいゾーンだけを含める(アカウント全体の権限は不要です)

ゾーンIDはCloudflareのゾーン概要ページの右下(**Zone ID**)に表示されています。

### 複数ゾーンを扱う場合
レコード名から登録可能ドメイン(`example.com`)を求めてゾーンIDを引く作りのため、
扱うゾーンの分だけ対応を書きます。

```sh
-e '{"cloudflare_ddns_ui_zones": {"example.com": "<ゾーンID>", "example.net": "<ゾーンID>"},
     "cloudflare_ddns_ui_records": ["home.example.com", "vpn.example.net"]}'
```

対応の無いゾーンのレコードを書いた場合は、**構築を始める前に**エラーで停止します
(そのまま動かすとログに `No zone ID configured` が出続けるだけになるためです)。

### ダッシュボードの待ち受け(`cloudflare_ddns_ui_http_bind`)
このダッシュボードには**認証がありません**。開いた人は誰でもレコードの追加・更新・
**削除**ができ、設定画面ではAPIトークンも扱えます。

| 指定 | 動作 |
| --- | --- |
| `0.0.0.0`(既定) | VMのIPで公開する。LAN内から `http://<VMのIP>:8080/` で開ける |
| `127.0.0.1` | VM内からのみ。手元から見るときはSSHポートフォワードを使う |

```sh
# 127.0.0.1に絞った場合の見かた
ssh -i ~/.ssh/<秘密鍵> -L 8080:127.0.0.1:8080 <SSHユーザ名>@<VMのIP>
# → 手元のブラウザで http://127.0.0.1:8080/
```

`127.0.0.1` に絞ると、実行元の端末からの疎通確認(再起動後)は自動でスキップされます。

## 実施する内容
1. OS確認(**Debianであること**)、変数の検証(トークン・ゾーン・レコードの対応を含む)
2. [全VM共通のセットアップ](../README.md#共通セットアップtasks)(OS更新、タイムゾーン、
   ロケール、zram、sudoグループ、基本パッケージ、QEMUエージェント)
3. Dockerの導入(`get.docker.com`)と、SSHユーザーのdockerグループ追加
4. `config/` と `logs/` の作成
5. `config/config.json`(トークン・ゾーン・レコード・間隔)の配置
6. `docker compose up`(**設定が変わった場合はコンテナを作り直します**)
7. ufwが導入済みかつ有効な場合のみポートを開放(通常はスキップ)
8. **コンテナが起動し続けているか**の確認(落ちている場合はログを表示して停止)
   → ダッシュボードの応答確認 → **1回目のレコード更新の結果**を動作ログから確認
9. VM再起動 → コンテナが自動復帰し、実行元の端末からダッシュボードが見えることを確認

## 構成されるもの
| パス | 内容 |
| --- | --- |
| `/opt/cloudflare-ddns-ui/docker-compose.yml` | Compose定義(Ansibleが生成。手動編集は上書きされます) |
| `/opt/cloudflare-ddns-ui/config/config.json` | アプリの設定(**APIトークンを含むためroot専用・`0600`**) |
| `/opt/cloudflare-ddns-ui/logs/ddns.log` | 動作ログ(更新の成否・Cloudflare APIの応答) |
| `/opt/cloudflare-ddns-ui/logs/record_stats.json` | レコードごとの更新回数・失敗回数 |

### Web UIで変更した設定について
`config.json` は**アプリ自身も書き換えます**(設定画面や「管理対象に追加」の操作)。
Ansibleは次の方針で扱います。

| 項目 | 再実行したとき |
| --- | --- |
| APIトークン / ゾーン / レコード / 間隔 | **Ansibleの指定で上書き**されます |
| 画面の開閉状態(`ui_state`) | UIでの変更が**引き継がれます** |

レコードを増やすときは、UIではなく `cloudflare_ddns_ui_records` を変えて再実行するのが
確実です(UIで足しただけだと次回の実行で消えます)。

## 更新結果の確認
構築の最後に、1回目のレコード確認の結果を `logs/ddns.log` から拾って表示します。

- 全レコードが「更新済み」または「更新した」となれば成功です
- 確認できないレコードがある場合は**注意書きを出しますが構築は完了扱い**にします
  (Cloudflare側にAレコードが無い、トークンの権限が足りない、などが原因です)

```sh
# VM内での確認
sudo tail -50 /opt/cloudflare-ddns-ui/logs/ddns.log
sudo cat /opt/cloudflare-ddns-ui/logs/record_stats.json
docker compose -f /opt/cloudflare-ddns-ui/docker-compose.yml ps
```

## 運用
```sh
# VM内(SSHユーザーのまま。dockerグループに入っています)
cd /opt/cloudflare-ddns-ui
docker compose ps
docker logs -f cloudflare-ddns-ui
sudo cat config/config.json     # APIトークンを含む
```

### レコードの追加・変更
`cloudflare_ddns_ui_records` を変えて再実行してください。

### バージョンアップ
`-e "cloudflare_ddns_ui_version=v1.0.3"` を付けて再実行するとそのタグに入れ替わります
(指定しなければ既定のタグのままで、**勝手に上がりません**)。

### バックアップ
`/opt/cloudflare-ddns-ui` を丸ごとコピーすれば設定とログが残ります。

## 再実行について
何度実行しても同じ状態になります。`config.json` と `docker-compose.yml` のどちらも
変わらなければコンテナは作り直されず、ログと更新履歴もそのまま残ります。

## うまくいかないとき
| 症状 | 確認すること |
| --- | --- |
| 「APIトークンが指定されていません」で止まる | `cloudflare_ddns_ui_api_token` を渡しているか(`proxmox/` からならvaultの内容) |
| 「ゾーンの指定に含まれないレコードがあります」で止まる | レコードが `cloudflare_ddns_ui_zone_domain` 配下のFQDNか。別ゾーンなら `cloudflare_ddns_ui_zones` に追加 |
| 「コンテナが起動し続けられていません」で止まる | 表示されたログを確認。`config.json` が壊れていないか |
| ログに `DNS record not found` が出る | **Cloudflare側にそのAレコードがまだ無い**。ダッシュボードか Cloudflare 側で先に作成する |
| ログに `No zone ID configured` が出る | ゾーンIDの対応が無い。レコードのドメインとゾーンの指定が一致しているか |
| ログに `403` / `Authentication error` が出る | トークンの権限(Zone → DNS → Edit)と対象ゾーンの指定 |
| 公開IPが `Unavailable` になる | VMから `api.ipify.org` に出られるか(外向き通信・DNS) |
| ダッシュボードが見えない | `cloudflare_ddns_ui_http_bind` を `127.0.0.1` にしていないか。ポートが他と重なっていないか |
