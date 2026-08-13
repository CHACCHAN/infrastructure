# technitium-dns.yml
[Technitium DNS Server](https://technitium.com/dns/) のVMを、テンプレート構築から
VM内部のセットアップまで一気通貫で構築します。
完了時点で、LAN内の端末がこのVMをDNSサーバーとして使える状態になります。

VM内のセットアップは**Debian 13専用**のため、既定で Debian 13 を構築します。

## 2つの実行方法
対象の決め方だけが違い、それ以降の処理は共通です。

| 実行方法 | 対象 | 台数 |
| --- | --- | --- |
| インベントリ版(既定) | `inventories/lab/technitium-dns.yml` のホスト。`--limit` で選択 | 1台〜全台 |
| 手動指定版(`-e "manual=true"`) | `-e` で指定した1台 | 1台 |

```sh
# インベントリ版: 全台 / 1台だけ
ansible-playbook playbooks/services/technitium-dns.yml --ask-vault-pass -vv -e "vm_ssh_password=<パスワード>"
ansible-playbook playbooks/services/technitium-dns.yml --ask-vault-pass -vv \
--limit 192.168.10.53 -e "vm_ssh_password=<パスワード>"

# 上位DNSへの転送と管理者パスワードまで一度に設定する
ansible-playbook playbooks/services/technitium-dns.yml --ask-vault-pass -vv --limit 192.168.10.53 \
-e '{"vm_ssh_password":"<パスワード>","technitium_admin_password":"<16文字以上>",
     "technitium_forwarders":["1.1.1.1","8.8.8.8"]}'

# 手動指定版
ansible-playbook playbooks/services/technitium-dns.yml --ask-vault-pass -vv \
-e 'manual=true vm_node=<ノードIP> proxmox_storage=<ストレージ名> \
    vm_id=<VMID> vm_name=<VM名> vm_ipv4=<IPv4/CIDR> vm_ipv4_gw=<ゲートウェイ> \
    vm_ssh_user=<ユーザ名> vm_ssh_password=<パスワード> \
    vm_ssh_pubkey_file=~/.ssh/<公開鍵> vm_ssh_prikey=~/.ssh/<秘密鍵> \
    vm_hardware={"cpu":{"cores":2,"type":"host"},"memory":{"size":2048},"resize":[{"bus":"scsi","index":0,"size":16}]} \
    vm_options={"agent":1,"onboot":1}'
```

- インベントリの `technitium_dns` グループが空なら、`manual=true` なしでも手動指定版になります
- ⚠ **手動指定版では `vm_hardware` の既定値がありません。** `resize` を省くとディスクが
  テンプレート素の約3GBのままになり、イメージとログの置き場所が足りなくなります
  (指定が無い場合は実行開始時に警告し、VM内の空き容量チェックで中止します)

## インベントリ
[inventories/lab/technitium-dns.yml](../../inventories/lab/technitium-dns.yml) に**1台1ホスト**で書きます。
ホスト名はVMのIPアドレスです。

**グループ名だけは `technitium_dns`(アンダースコア)です。**
Ansibleのグループ名にハイフンを使えないためで、他のplaybookとの違いはここだけです。

| 優先順位 | 指定方法 |
| --- | --- |
| 高 | `-e "変数名=値"` |
| 中 | インベントリの `hosts:` 配下(VMごと) |
| 低 | インベントリの `vars:`(グループ共通) |

## 実行される順番
1. [proxmox_template_build.yml](../proxmox/proxmox_template_build.md) —
   テンプレート構築。**ノードごとに1台だけが担当**します(VMID衝突を避けるため)
2. [proxmox_vm_build.yml](../proxmox/proxmox_vm_build.md) — VMをクローン
3. [proxmox_vm_hardware.yml](../proxmox/proxmox_vm_hardware.md) —
   ハードウェア調整(`vm_hardware` 指定時のみ)
4. [proxmox_vm_options.yml](../proxmox/proxmox_vm_options.md) —
   動作設定(`vm_options` 指定時のみ)
5. [proxmox_vm_cloudinit.yml](../proxmox/proxmox_vm_cloudinit.md) — cloud-init設定
6. [proxmox_vm_powerctl.yml](../proxmox/proxmox_vm_powerctl.md) — VMの起動
7. SSHでログインできるまで待機(cloud-initの完了待ち)
8. [playbooks/vms/technitium-dns.yml](../vms/technitium-dns.md) —
   VM内部のセットアップ、VM再起動、実行元の端末からの接続確認

手順1〜6はProxmoxノードへ、手順7〜8はVM自身へ接続します。

完了後、表示されたURL(`http://<VMのIP>:5380/`)にユーザー名 `admin` でログインします。
パスワードはVM内の `/opt/technitium-dns/.env` にあります。

## VMごとに指定する変数
インベントリの `hosts:` 配下、または `-e` で指定します。

| 変数 | 内容 |
| --- | --- |
| `vm_id` | 新規VMのVMID |
| `vm_name` | VM名 |
| `vm_node` | 構築先ProxmoxノードのIPアドレス |
| `vm_ipv4` | VMの固定IP(CIDR)。省略時は**ホスト名 + `vm_ipv4_prefix`** から組み立てます |

`proxmox_ip` ではなく `vm_node` なのは、`-e proxmox_ip=...` を使うと呼び出し先が
そのIPを別の構築対象として登録してしまうためです。

**DNSサーバーのIPアドレスは固定にしてください。** クライアント側がこのIPを直接指定するためです。

## 共通で指定する変数
インベントリの `vars:`、または `-e` で指定します。

| 変数 | 内容 |
| --- | --- |
| `proxmox_storage` | テンプレートとVMのディスクを置くストレージ名 |
| `vm_ipv4_prefix` / `vm_ipv4_gw` | プレフィックス長(既定 `24`)/ ゲートウェイ |
| `vm_ssh_user` | cloud-initで作成するログインユーザー |
| `vm_ssh_pubkey_file` | VMに登録するSSH公開鍵のファイルパス(`vm_ssh_pubkey` で内容の直接指定も可) |
| `vm_ssh_prikey` | 秘密鍵のパス。VM内セットアップのSSH接続に使います |
| `vm_hardware` / `vm_options` | ハードウェア / 動作設定(後述) |

## ハードウェア・動作設定の既定値
インベントリの `vm_hardware` / `vm_options` で指定しています。書式は
[proxmox_vm_hardware.md](../proxmox/proxmox_vm_hardware.md) /
[proxmox_vm_options.md](../proxmox/proxmox_vm_options.md) を参照してください。

| 項目 | 既定値 | 指定 |
| --- | --- | --- |
| CPU / RAM | 2コア(`x86-64-v3`)/ 2GB | `cpu: {cores: 2, type: x86-64-v3}` `memory: {size: 2048}` |
| BIOS / マシン / 画面 | SeaBIOS / Q35 / 標準VGA | `options: {bios: seabios, machine: q35, vga: std}` |
| ディスク | 16GiB | `resize: [{bus: scsi, index: 0, size: 16}]` |
| QEMUエージェント / 自動起動 | 有効 | `agent: 1` `onboot: 1` |

- DNSサーバーは軽いので1コア/1GBでも動きます。キャッシュを多く持たせるならRAMを増やしてください
- **`onboot: 1` は外さないでください。** DNSが落ちたままだとLAN全体の名前解決が止まります
- ディスクは **`resize`(既存ディスクの拡張)で指定します**。`disks` に書くと新しい空ディスクに
  置き換わります。また既に指定サイズ以上なら拡張は行われません
- `-e` で `vm_hardware` を渡すとインベントリの値は**置き換え**になるため、
  変更しない項目も併せて指定してください(JSONにはスペースを含めないこと)

## DNSサーバー本体の設定
`technitium_` で始まる変数はそのまま手順8へ渡ります。インベントリにも `-e` にも書けます。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `technitium_version` | `15.4.0` | イメージタグ |
| `technitium_dns_port` | `53` | DNSサービスの公開ポート |
| `technitium_http_port` | `5380` | Webコンソールの公開ポート |
| `technitium_admin_password` | 自動生成 | 管理者`admin`のパスワード(**初回のみ有効**) |
| `technitium_forwarders` | `[]` | 上位DNSのアドレス(**初回のみ有効**) |
| `technitium_recursion` | `AllowOnlyForPrivateNetworks` | 再帰問い合わせを許す範囲(**初回のみ有効**) |

⚠ **Technitiumは設定ファイルが作られる初回起動時にしか環境変数を読みません。**
「初回のみ有効」の項目は、構築済みVMに再実行しても変わりません
(Webコンソールの「Settings」から変更してください)。ポート番号は再実行でも変えられます。

全項目とバックアップ・バージョンアップの考え方は
[docs/vms/technitium-dns.md](../vms/technitium-dns.md) を参照してください。
パスワード類は平文でインベントリに置かず、`-e` か `ansible-vault encrypt_string` を使ってください。

## VM自身のDNS設定について
`vm_nameserver` はcloud-initがVMに設定する**上位DNS**です。
構築中は自分自身のDNSサーバーがまだ動いていないため、
**ここに構築対象のVM自身のIPを指定しないでください**(パッケージの取得に失敗します)。

構築後にVM自身も自分のDNSを使わせたい場合は、VM内で `/etc/resolv.conf` を編集してください。

## `-e` で渡す変数
| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `manual` | インベントリが空なら `true` | 手動指定版として動作します |
| `vm_ssh_password` | (なし) | VMのログインパスワード(Proxmoxのコンソール用。SSHは鍵認証) |
| `proxmox_ssh_user` | `root` | Proxmoxホストへ接続するSSHユーザー |
| `vm_reboot_after_setup` | `true` | VM内セットアップ後に再起動するか |

`proxmox_ssh_user` と `vm_reboot_after_setup` は、対象ホストの変数が参照できない
タイミングで使われるため、インベントリに書いても反映されません。

## 任意の変数
| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `os_type` / `os_version` | `debian` / `13` | VM内のセットアップがDebian 13専用のため固定 |
| `target_storage` | `proxmox_storage` と同じ | VMのディスクを置くストレージ名 |
| `vm_hardware_delete` / `vm_options_delete` | (なし) | 削除するプロパティ |
| `vm_ipv6` / `vm_ipv6_gw` | (なし) | IPv6アドレス(CIDR)とゲートウェイ |
| `vm_nameserver` / `vm_searchdomain` | (なし) | 上位DNSと検索ドメイン(前述) |
| `vm_ip` | ホスト名 | SSHの接続先(ホスト名と違うIPで繋ぐ場合) |
| `vm_ssh_wait_timeout` | `600` | SSHログインできるまでの待機上限(秒) |

## 再実行・復旧
- **同じ `vm_id` での再実行はできません。** 作り直す場合は
  `playbooks/proxmox/proxmox_vm_delete.yml` で削除するか、別の `vm_id` にしてください
- 構築済みVMのTechnitiumだけを更新する場合は `playbooks/vms/technitium-dns.yml` を
  直接実行してください(設定・ゾーンと管理者パスワードは引き継がれます)

## 注意
- 全台実行時は並行して処理されます。1台が失敗しても他はそのまま進みます
- `--ask-vault-pass` は必須です(`vault/proxmox.yml` を読むため)
- 手動指定版では `--limit` を使わないでください(`hosts: localhost` のプレイが
  対象外になり、構築対象が登録されません)
- VM内の設定は `vm_` 接頭辞で指定します。`ssh_user` や `ipv4` をそのまま `-e` で渡すと
  **テンプレート側にも**焼き込まれてしまうためです
- 他のOSを指定した場合、手順7までは動作しますが手順8でOS判定により停止します
- 冗長化のためDNSサーバーを2台立てる場合は、インベントリに2ホスト書いて全台実行し、
  ゾーンの同期はTechnitium側のプライマリ/セカンダリ設定で行ってください
  (このplaybookはゾーンの内容には関与しません)
