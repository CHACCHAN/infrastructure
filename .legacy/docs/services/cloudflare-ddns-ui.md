# cloudflare-ddns-ui.yml
[cloudflare-ddns-ui](https://hub.docker.com/r/martijnf/cloudflare-ddns-ui)
(`martijnf/cloudflare-ddns-ui`)のVMを、テンプレート構築からVM内部のセットアップまで
一気通貫で構築します。完了時点で、回線の公開IPが変わるたびにCloudflareのAレコードが
自動更新される状態になります。

VM内のセットアップは**Debian 13専用**のため、既定で Debian 13 を構築します。

## 2つの実行方法
対象の決め方だけが違い、それ以降の処理は共通です。

| 実行方法 | 対象 | 台数 |
| --- | --- | --- |
| インベントリ版(既定) | `inventories/lab/cloudflare-ddns-ui.yml` のホスト。`--limit` で選択 | 1台〜全台 |
| 手動指定版(`-e "manual=true"`) | `-e` で指定した1台 | 1台 |

```sh
# インベントリ版: レコードはインベントリ、認証情報はvaultから入ります
ansible-playbook playbooks/services/cloudflare-ddns-ui.yml --ask-vault-pass -vv -e "vm_ssh_password=<パスワード>"

# 更新するレコードだけ差し替える
ansible-playbook playbooks/services/cloudflare-ddns-ui.yml --ask-vault-pass -vv \
-e "vm_ssh_password=<パスワード> cloudflare_ddns_ui_records=auth.example.com,wg.example.com"

# 手動指定版
ansible-playbook playbooks/services/cloudflare-ddns-ui.yml --ask-vault-pass -vv \
-e 'manual=true vm_node=<ノードIP> proxmox_storage=<ストレージ名> \
    vm_id=<VMID> vm_name=<VM名> vm_ipv4=<IPv4/CIDR> vm_ipv4_gw=<ゲートウェイ> \
    vm_ssh_user=<ユーザ名> vm_ssh_password=<パスワード> \
    vm_ssh_pubkey_file=~/.ssh/<公開鍵> vm_ssh_prikey=~/.ssh/<秘密鍵> \
    cloudflare_ddns_ui_records=<FQDN> cloudflare_ddns_ui_zone_domain=<ゾーン> \
    vm_hardware={"cpu":{"cores":2,"type":"host"},"memory":{"size":512},"resize":[{"bus":"scsi","index":0,"size":8}]} \
    vm_options={"agent":1,"onboot":1}'
```

- インベントリの `cloudflare_ddns_ui` グループが空なら、`manual=true` なしでも手動指定版になります
- ⚠ **レコード・ゾーン・認証情報の指定漏れは、VMを作る前に停止します**
  (VMだけ出来上がって設定が入っていない状態を避けるためです)
- ⚠ **ダッシュボードには認証がありません。** レコードの削除まで行える画面がそのまま開きます
  (`cloudflare_ddns_ui_http_bind: 127.0.0.1` で絞れます)

## インベントリ
[inventories/lab/cloudflare-ddns-ui.yml](../../inventories/lab/cloudflare-ddns-ui.yml) に**1台1ホスト**で
書きます。ホスト名はVMのIPアドレスです。

**グループ名だけは `cloudflare_ddns_ui`(アンダースコア)です。**
Ansibleのグループ名にハイフンを使えないためで、他のplaybookとの違いはここだけです。

| 優先順位 | 指定方法 |
| --- | --- |
| 高 | `-e "変数名=値"` |
| 中 | インベントリの `hosts:` 配下(VMごと) |
| 低 | インベントリの `vars:`(グループ共通) |

更新するレコードとゾーンはインベントリに書きますが、**トークンやゾーンIDは
平文で書かないでください**(次のvaultを使います)。

## 認証情報(vault)
CloudflareのゾーンIDとAPIトークンは [vault/cloudflare.yml](../vault/cloudflare.yml) に置き、
**暗号化したまま**リポジトリに保管します。playbookが自動で読み込むため、
実行時に認証情報を渡す必要はありません(`--ask-vault-pass` は必要です)。

```sh
# 中身を編集・確認する
ansible-vault edit vault/cloudflare.yml
ansible-vault view vault/cloudflare.yml
```

| 変数 | 渡される先 |
| --- | --- |
| `vault_cloudflare_zone_id` | `cloudflare_ddns_ui_zone_id` |
| `vault_cloudflare_api_token` | `cloudflare_ddns_ui_api_token` |

- ⚠ **`--ask-vault-pass` はパスワードを1つしか受け取りません。**
  `vault/proxmox.yml` と**同じパスワード**で暗号化してください
  (別にしたい場合は `--vault-id` を使い分ける必要があります)
- APIトークンは **Zone → DNS → Edit** 権限で、対象ゾーンだけに絞って作成してください
- 複数ゾーンを扱う場合は、vaultではなく `cloudflare_ddns_ui_zones`(ドメイン: ゾーンID)で
  指定します。ゾーンIDを平文で置きたくない場合は `ansible-vault encrypt_string` を使ってください
- `playbooks/vms/cloudflare-ddns-ui.yml` を単体で実行する場合、このvaultは
  読まれません(`-e "cloudflare_ddns_ui_api_token=..."` のように渡してください)

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
8. [playbooks/vms/cloudflare-ddns-ui.yml](../vms/cloudflare-ddns-ui.md) —
   VM内部のセットアップ、VM再起動、実行元の端末からの接続確認

手順1〜6はProxmoxノードへ、手順7〜8はVM自身へ接続します。

完了後、表示されたURL(`http://<VMのIP>:8080/`)でダッシュボードを開けます。

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
| CPU / RAM | 2コア(`x86-64-v2-AES`)/ 512MB | `cpu: {cores: 2, type: x86-64-v2-AES}` `memory: {size: 512}` |
| BIOS / マシン / 画面 | SeaBIOS / Q35 / 標準VGA | `options: {bios: seabios, machine: q35, vga: std}` |
| ディスク | 8GiB | `resize: [{bus: scsi, index: 0, size: 8}]` |
| QEMUエージェント / 自動起動 | 有効 | `agent: 1` `onboot: 1` |

- 数分おきに公開IPを確認してAPIを叩くだけのサービスなので、1コア / 512MBで十分です
- ディスクは **`resize`(既存ディスクの拡張)で指定します**。`disks` に書くと新しい空ディスクに
  置き換わります
- `-e` で `vm_hardware` を渡すとインベントリの値は**置き換え**になるため、
  変更しない項目も併せて指定してください(JSONにはスペースを含めないこと)

## アプリ本体の設定
`cloudflare_ddns_ui_` で始まる変数はそのまま手順8へ渡ります。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `cloudflare_ddns_ui_records` | **(必須)** | 更新するレコード(FQDN)。リストでもカンマ区切りでも可 |
| `cloudflare_ddns_ui_zone_domain` | **(必須)** | レコードが属するゾーン(例: `example.com`) |
| `cloudflare_ddns_ui_zone_id` | vaultの値 | ゾーンID([vault](#認証情報vault)から渡ります) |
| `cloudflare_ddns_ui_api_token` | vaultの値 | APIトークン([vault](#認証情報vault)から渡ります) |
| `cloudflare_ddns_ui_zones` | `{}` | 複数ゾーンを扱う場合の「ドメイン: ゾーンID」 |
| `cloudflare_ddns_ui_version` | `v1.0.2` | イメージタグ |
| `cloudflare_ddns_ui_http_port` | `8080` | ダッシュボードの公開ポート |
| `cloudflare_ddns_ui_http_bind` | `0.0.0.0` | ダッシュボードの待ち受けアドレス(`127.0.0.1` でVM内のみ) |
| `cloudflare_ddns_ui_interval` | `300` | 公開IPを確認する間隔(秒) |

⚠ このアプリは **Aレコード(IPv4)のみ**を、**TTL自動・プロキシ無効**で更新します。
また**Cloudflare側に既にAレコードがある必要があります**。
全項目と制約は
[docs/vms/cloudflare-ddns-ui.md](../vms/cloudflare-ddns-ui.md)
を参照してください。

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
| `vm_nameserver` / `vm_searchdomain` | (なし) | DNSサーバーと検索ドメイン |
| `vm_ip` | ホスト名 | SSHの接続先(ホスト名と違うIPで繋ぐ場合) |
| `vm_ssh_wait_timeout` | `600` | SSHログインできるまでの待機上限(秒) |

## 再実行・復旧
- **同じ `vm_id` での再実行はできません。** 作り直す場合は
  `playbooks/proxmox/proxmox_vm_delete.yml` で削除するか、別の `vm_id` にしてください
- レコードを変えるだけなら `playbooks/vms/cloudflare-ddns-ui.yml` を
  直接実行してください(`-e` の指定を変えて再実行すると `config.json` が置き換わります)

## 注意
- `--ask-vault-pass` は必須です(`vault/proxmox.yml` と
  `vault/cloudflare.yml` を読むため。**2つは同じパスワードで暗号化してください**)
- 手動指定版では `--limit` を使わないでください(`hosts: localhost` のプレイが
  対象外になり、構築対象が登録されません)
- VM内の設定は `vm_` 接頭辞で指定します。`ssh_user` や `ipv4` をそのまま `-e` で渡すと
  **テンプレート側にも**焼き込まれてしまうためです
