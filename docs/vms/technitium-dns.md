# technitium-dns.yml
起動済みのVMに [Technitium DNS Server](https://technitium.com/dns/) をDocker Composeで構築します。
完了時点で、LAN内の端末がこのVMをDNSサーバーとして使える状態になります。

接続情報と共通オプションは [README](../README.md#全playbook共通の指定) を参照してください。

```sh
ansible-playbook playbooks/vms/technitium-dns.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名>"

# 上位DNSへの転送と管理者パスワードまで一度に決める場合
ansible-playbook playbooks/vms/technitium-dns.yml -vv \
-e '{"vm_ip":"192.168.10.53","vm_ssh_user":"dns","vm_ssh_prikey":"~/.ssh/id_ed25519",
     "technitium_forwarders":["1.1.1.1","8.8.8.8"],
     "technitium_admin_password":"<16文字以上のパスワード>"}'
```

`development.yml` と違い、CockpitやGUI・開発ツールは導入しません(DNSサーバー専用VMのため)。

## 必要なスペック
| 項目 | 必要量 |
| --- | --- |
| CPU / RAM | 1コア / 1GB以上(2コア / 2GBあれば十分。キャッシュを多く持たせるならRAMを増やします) |
| ディスク | **16GB以上を推奨**。イメージは展開後およそ0.7GiB。クエリログと統計が既定で365日分たまります |

実行の冒頭で空き容量を確認し、3GiB未満なら**イメージの取得を始める前に中止**します
(`technitium_min_free_disk_gb` で変更可)。
Debianのcloud imageテンプレートは素のままだと約3GBしかないため、
`proxmox/` から構築する場合は `vm_hardware` の `resize` を必ず指定してください。

## 指定できる項目
共通オプションに加えて以下を指定できます。**すべて任意です。**

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `technitium_install_dir` | `/opt/technitium-dns` | 設置先 |
| `technitium_version` | `15.4.0` | イメージタグ |
| `technitium_image` | `docker.io/technitium/dns-server` | イメージ名 |
| `technitium_dns_port` | `53` | DNSサービスの公開ポート(TCP/UDP) |
| `technitium_http_port` | `5380` | Webコンソール(HTTP)の公開ポート |
| `technitium_https_port` | `53443` | Webコンソール(HTTPS)の公開ポート |
| `technitium_enable_https_console` | `false` | WebコンソールのHTTPSを有効にする(自己署名証明書) |
| `technitium_extra_ports` | `[]` | 追加で公開するポート(後述) |
| `technitium_use_host_network` | `false` | DHCPサーバーとしても使う場合に `true`(後述) |
| `technitium_admin_password` | 自動生成 | Webコンソールの管理者`admin`のパスワード(**初回のみ有効**) |
| `technitium_server_domain` | `dns-server` | このDNSサーバー自身を指す名前(**初回のみ有効**) |
| `technitium_recursion` | `AllowOnlyForPrivateNetworks` | 再帰問い合わせを許す範囲(**初回のみ有効**) |
| `technitium_recursion_network_acl` | `[]` | 許可/拒否するネットワーク(**初回のみ有効**) |
| `technitium_forwarders` | `[]` | 上位DNSのアドレス(**初回のみ有効**) |
| `technitium_forwarder_protocol` | `Udp` | 上位DNSへの転送プロトコル(**初回のみ有効**) |
| `technitium_enable_blocking` | `false` | 広告・トラッカーのブロックを有効にする(**初回のみ有効**) |
| `technitium_block_list_urls` | `[]` | ブロックリストのURL(**初回のみ有効**) |
| `technitium_log_using_local_time` | `true` | ログの時刻をローカルタイムにするか(**初回のみ有効**) |
| `technitium_log_max_days` | `365` | ログの保持日数(**初回のみ有効**) |
| `technitium_min_free_disk_gb` | `3` | イメージ取得前に必要な空き容量(GiB) |
| `technitium_extra_env` | `{}` | 上に無い環境変数を `.env` に足す(**初回のみ有効**) |
| `technitium_ready_retries` / `_delay` | `30` / `5` | Webコンソール起動待ちのリトライ回数 / 間隔(秒) |

パスワードを手動指定する場合は**16文字以上の英数字と `_` `.` `-` のみ**にしてください
(`.env`に書き出すため。実行前に検証してエラーにします)。

### ⚠ 「初回のみ有効」について
Technitiumは**設定ファイル(`config/dns.config`)が無い初回起動時にだけ**環境変数を読み、
以降は自分の設定ファイルだけを見ます。つまり上表の「初回のみ有効」の項目は、
**構築済みのサーバーに再実行しても変わりません**。
構築後の変更はWebコンソールの「Settings」から行ってください。

一方、**ポート番号は再実行でも変えられます**。コンテナ内の待ち受けポートは
53 / 5380 / 53443 のまま固定し、VM側のポートだけをDockerのポート公開で
割り当てているためです(`technitium_use_host_network: true` のときを除く)。

### 再帰問い合わせ(`technitium_recursion`)
| 値 | 内容 |
| --- | --- |
| `AllowOnlyForPrivateNetworks` | プライベートIPからの問い合わせだけ許可(既定) |
| `Allow` | 誰からでも許可。⚠ インターネットに公開するとオープンリゾルバになります |
| `Deny` | 自分が持つゾーンにだけ答える(権威DNSとして使う場合) |
| `UseSpecifiedNetworkACL` | `technitium_recursion_network_acl` で指定した範囲だけ許可 |

```yaml
technitium_recursion: UseSpecifiedNetworkACL
technitium_recursion_network_acl:
  - 192.168.10.0/24
  - "!192.168.10.2"   # 先頭に ! を付けると拒否
```

### 追加ポート(`technitium_extra_ports`)
DoT(853)やDoH(443)など、既定で公開していないポートを足すときに指定します。
**VM側とコンテナ側で同じポート番号になります**(ずらせません)。

```yaml
technitium_extra_ports:
  - {port: 853, proto: tcp}   # DNS-over-TLS
  - {port: 853, proto: udp}   # DNS-over-QUIC
  - {port: 443, proto: tcp}   # DNS-over-HTTPS
```

ポートを開けるだけでは有効になりません。Webコンソールの「Settings」→「Optional Protocols」で
プロトコルを有効にし、証明書を設定してください。

### DHCPサーバーとしても使う場合(`technitium_use_host_network`)
`true` にするとポート公開をやめ、VMのネットワークをコンテナが直接使います
(DHCPはブロードキャストのためNAT越しでは動きません)。この場合の注意点:

- `technitium_dns_port` は53固定になります(指定するとエラーで止まります)
- Webコンソールのポートは**初回起動時にしか反映されません**
  (ポート公開ではなくTechnitium本体の待ち受けポートを変えるため)
- DHCPのスコープ設定はWebコンソールの「DHCP」タブから行います

## 実施する内容
1. OS確認、変数の検証、**ディスクの空き容量の確認**
2. [全VM共通のセットアップ](../README.md#共通セットアップtasks)(OS更新、タイムゾーン、
   ロケール、zram、sudoグループ、基本パッケージ、QEMUエージェント、Docker)と `dnsutils`
3. **53番ポートを空ける**(systemd-resolvedが動いていればスタブリゾルバを無効化)
4. `/opt/technitium-dns` 配下の作成 → `.env` 生成 → `docker compose up -d`
5. ufwが導入済みかつ有効な場合のみDNS・Webコンソールのポートを開放(通常はスキップ)
6. VM内から `dig` と Webコンソールの応答を確認 → VM再起動 →
   **実行元の端末から接続できることを確認**

## 構成されるもの
| パス | 内容 |
| --- | --- |
| `/opt/technitium-dns/docker-compose.yml` | Compose定義(Ansibleが生成。手動編集は上書きされます) |
| `/opt/technitium-dns/.env` | 初期設定と管理者パスワード(root所有・`0640`・dockerグループのみ読み取り可) |
| `/opt/technitium-dns/config` | 設定・ゾーン・統計(コンテナ内の `/etc/dns`) |
| `/opt/technitium-dns/logs` | クエリログ(コンテナ内の `/var/log/technitium/dns`) |

公式の `docker-compose.yml` と同じ構成ですが、設定とログは名前付きボリュームではなく
**バインドマウント**にしています(設置ディレクトリごとバックアップできるようにするため)。

## 53番ポートについて
DNSサーバーは53番を占有するため、VM側で53番を待ち受けているものがあると起動できません。

- Debianのcloud imageは既定で`systemd-resolved`を使わないため、通常は何も起きません
- `systemd-resolved`が動いていた場合は、スタブリゾルバ(`127.0.0.53:53`)を無効化し、
  VM自身の参照先を `/run/systemd/resolve/resolv.conf` へ向け直します
- それ以外のプロセス(dnsmasq等)が握っていた場合は、**中止して占有元を表示**します

なお**VM自身のDNS参照先は変更しません**(cloud-initで設定した値のままです)。
自分自身を使わせたい場合は、VM内で `/etc/resolv.conf` を編集するか、
`playbooks/proxmox/proxmox_vm_cloudinit.yml` の `nameserver` を変更してください。

## 初期セットアップ(初回のみ)
```
http://<VMのIPアドレス>:5380/
```
ユーザー名は `admin`、パスワードは `/opt/technitium-dns/.env` にあります。

```sh
sudo grep DNS_SERVER_ADMIN_PASSWORD /opt/technitium-dns/.env
```

`technitium_admin_password` を指定していた場合はその値です。
**パスワードの変更はWebコンソールから行ってください**(`.env`を書き換えても反映されません)。

## 運用
```sh
cd /opt/technitium-dns
docker compose ps
docker compose logs -f dns-server

dig @localhost localhost              # サーバーが応答するか(必ず127.0.0.1が返る)
dig @localhost technitium.com         # 外部の名前を引けるか
dig @<VMのIP> example.com             # 他の端末から引けるか
```

クライアント側は、ルーターのDHCPが配るDNSサーバー、または各端末のDNS設定に
**VMのIPアドレス**を指定します。

### バージョンアップ
`technitium_version` を指定して再実行するとイメージを取得してコンテナを作り直します
(`config/` に残るため設定・ゾーンは消えません)。**事前にバックアップを取ってください。**

### バックアップ
```sh
sudo tar czf technitium-$(date +%F).tar.gz -C /opt technitium-dns
```
`.env`(管理者パスワード)と `config/`(設定・ゾーン)が揃っていれば復旧できます。
ゾーンだけならWebコンソールの「Zones」→「Export」でも取り出せます。

## 再実行について
何度実行しても同じ状態になります。`.env` と `docker-compose.yml` が変わらなければ
コンテナは作り直されず、設定・ゾーンも消えません。
ただし**DNSサーバーの設定項目は初回起動時にしか反映されません**(前述)。

## うまくいかないとき
| 症状 | 確認すること |
| --- | --- |
| 「53番ポートが他のプロセスに使われています」で止まる | 表示された占有元を停止してください(`sudo ss -lntup 'sport = :53'`) |
| 「空き容量が足りません」で止まる | `df -h /` と `lsblk`。**ディスクが3GB程度**ならテンプレート素のまま(`vm_hardware` の `resize` 漏れ) |
| Webコンソールの起動待ちでタイムアウト | `docker compose logs dns-server` |
| 外部の名前が引けない(構築は成功) | VMからインターネットに出られるか。`technitium_forwarders` を指定して上位DNSに転送する手もあります |
| 他の端末から引けない | VM内で `dig @localhost localhost` が通るか。通るならVM外のネットワーク側の問題です |
| 設定を変えて再実行しても反映されない | **仕様です。** Webコンソールの「Settings」から変更してください |
| 管理者パスワードを忘れた | `sudo grep DNS_SERVER_ADMIN_PASSWORD /opt/technitium-dns/.env` |
