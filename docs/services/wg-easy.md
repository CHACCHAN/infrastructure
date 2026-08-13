# wg-easy.yml
[wg-easy](https://github.com/wg-easy/wg-easy)(WireGuardのVPNサーバー + Web UI)のVMを、
テンプレート構築からVM内部のセットアップまで一気通貫で構築します。
**認証は既定でOIDC**です。完了時点で、WireGuardが起動しWeb UIからクライアントを
追加できる状態になります。

⚠ **OAuth/OIDCは `15.4.0-beta.1` で追加された機能**のため、既定のイメージタグは
**ベータ版**です(安定版の `15.3.0` 以前では `OAUTH_*` が無視されます)。
構築の最後に、OIDCが実際に有効かをアプリのAPIで確認します。

VM内のセットアップは**Debian 13専用**のため、既定で Debian 13 を構築します。

## 2つの実行方法
対象の決め方だけが違い、それ以降の処理は共通です。

| 実行方法 | 対象 | 台数 |
| --- | --- | --- |
| インベントリ版(既定) | `inventories/lab/wg-easy.yml` のホスト。`--limit` で選択 | 1台〜全台 |
| 手動指定版(`-e "manual=true"`) | `-e` で指定した1台 | 1台 |

```sh
# インベントリ版: 接続先とOIDCサーバーはインベントリ、クライアント情報はvaultから入ります
ansible-playbook playbooks/services/wg-easy.yml --ask-vault-pass -vv -e "vm_ssh_password=<パスワード>"

# 接続先だけ差し替える
ansible-playbook playbooks/services/wg-easy.yml --ask-vault-pass -vv \
-e "vm_ssh_password=<パスワード> wg_easy_init_host=vpn.example.com"

# 手動指定版
ansible-playbook playbooks/services/wg-easy.yml --ask-vault-pass -vv \
-e 'manual=true vm_node=<ノードIP> proxmox_storage=<ストレージ名> \
    vm_id=<VMID> vm_name=<VM名> vm_ipv4=<IPv4/CIDR> vm_ipv4_gw=<ゲートウェイ> \
    vm_ssh_user=<ユーザ名> vm_ssh_password=<パスワード> \
    vm_ssh_pubkey_file=~/.ssh/<公開鍵> vm_ssh_prikey=~/.ssh/<秘密鍵> \
    wg_easy_init_host=vpn.example.com wg_easy_oauth_providers= \
    vm_hardware={"cpu":{"cores":2,"type":"host"},"memory":{"size":1024},"resize":[{"bus":"scsi","index":0,"size":8}]} \
    vm_options={"agent":1,"onboot":1}'
```

- インベントリの `wg_easy` グループが空なら、`manual=true` なしでも手動指定版になります
- ⚠ **接続先(`wg_easy_init_host`)とOIDCの設定漏れは、VMを作る前に停止します**
- ⚠ **ルーターでUDP 51820をこのVMへ転送**しないと、外からVPN接続できません
  (ポート転送はこのplaybookの対象外です)

## インベントリ
[inventories/lab/wg-easy.yml](../../inventories/lab/wg-easy.yml) に**1台1ホスト**で書きます。
ホスト名はVMのIPアドレスです。

**グループ名だけは `wg_easy`(アンダースコア)です。**
Ansibleのグループ名にハイフンを使えないためで、他のplaybookとの違いはここだけです。

| 優先順位 | 指定方法 |
| --- | --- |
| 高 | `-e "変数名=値"` |
| 中 | インベントリの `hosts:` 配下(VMごと) |
| 低 | インベントリの `vars:`(グループ共通) |

## 認証情報(vault)
OIDCのクライアントIDとシークレット、管理者の初期パスワードは
[vault/wg-easy.yml](../vault/wg-easy.yml) に置き、**暗号化したまま**保管します。

```sh
# 値を入れてから暗号化する(vault/proxmox.yml と同じパスワードにすること)
ansible-vault encrypt vault/wg-easy.yml

# 中身を編集・確認する
ansible-vault edit vault/wg-easy.yml
ansible-vault view vault/wg-easy.yml
```

| 変数 | 渡される先 |
| --- | --- |
| `vault_wg_easy_oidc_client_id` | `wg_easy_oauth_oidc_client_id` |
| `vault_wg_easy_oidc_client_secret` | `wg_easy_oauth_oidc_client_secret` |
| `vault_wg_easy_init_password` | `wg_easy_init_password`(空なら自動生成) |

- ⚠ **`--ask-vault-pass` はパスワードを1つしか受け取りません。**
  `vault/proxmox.yml` と**同じパスワード**で暗号化してください
- OIDCプロバイダのURL(`wg_easy_oauth_oidc_server`)は秘密ではないため
  インベントリ側に書いています
- `playbooks/vms/wg-easy.yml` を単体で実行する場合、このvaultは読まれません
  (`-e "wg_easy_oauth_oidc_client_secret=..."` のように渡してください)

## OIDC(Authentik等)側の設定
プロバイダ側に**リダイレクトURIの登録**が必要です。
URLは**ブラウザでwg-easyを開くときのホスト**から組み立てられ、
プロトコルは `wg_easy_insecure` で決まります(`true`なら`http`、`false`なら`https`)。

```
# 既定(LAN内からIPで開く場合)
http://172.16.11.5:51821/api/auth/oidc/callback   ← ログイン用
http://172.16.11.5:51821/api/auth/oidc/link       ← 既存アカウントとの紐付け用
```

- プロバイダは **PKCE**、スコープ `openid email profile`、
  クライアント認証方式 `client_secret_post` に対応している必要があります
- 構築直後は**パスワード認証も有効**です。まず管理者(`admin`)でログインし、
  OIDCでログインし直してアカウントを紐付けてから
  `wg_easy_disable_password_auth: true` にしてください(紐付け前に切ると締め出されます)
- 手順の詳細は
  [docs/vms/wg-easy.md](../vms/wg-easy.md#認証の考え方) を参照

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
8. [playbooks/vms/wg-easy.yml](../vms/wg-easy.md) —
   VM内部のセットアップ、VM再起動、実行元の端末からの接続確認

手順1〜6はProxmoxノードへ、手順7〜8はVM自身へ接続します。

完了後、表示されたURL(`http://<VMのIP>:51821/`)でWeb UIを開けます。
管理者のパスワードはVM内の `/opt/wg-easy/.env`(`INIT_PASSWORD`)にあります。

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
| CPU / RAM | 2コア(`x86-64-v2-AES`)/ 1GB | `cpu: {cores: 2, type: x86-64-v2-AES}` `memory: {size: 1024}` |
| BIOS / マシン / 画面 | SeaBIOS / Q35 / 標準VGA | `options: {bios: seabios, machine: q35, vga: std}` |
| ディスク | 8GiB | `resize: [{bus: scsi, index: 0, size: 8}]` |
| QEMUエージェント / 自動起動 | 有効 | `agent: 1` `onboot: 1` |

- VPNの暗号化処理が中心のため、太い回線で使うならCPUコアを増やしてください
- ディスクは **`resize`(既存ディスクの拡張)で指定します**。`disks` に書くと新しい空ディスクに
  置き換わります
- `-e` で `vm_hardware` を渡すとインベントリの値は**置き換え**になるため、
  変更しない項目も併せて指定してください(JSONにはスペースを含めないこと)

## wg-easy本体の設定
`wg_easy_` で始まる変数はそのまま手順8へ渡ります。
**コンテナの環境変数はすべて指定できます**(全項目の対応表は
[docs/vms/wg-easy.md](../vms/wg-easy.md#指定できる項目))。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `wg_easy_init_host` | **(必須)** | クライアントの接続先(外から見たFQDN / グローバルIP) |
| `wg_easy_oauth_providers` | `oidc` | 認証プロバイダ。空にするとパスワード認証のみ |
| `wg_easy_oauth_oidc_server` | (oidcで必須) | OIDCプロバイダのURL |
| `wg_easy_oauth_oidc_name` | `OIDC` | ログイン画面に表示される名前 |
| `wg_easy_disable_password_auth` | `false` | パスワード認証を止める(⚠ 紐付け後に) |
| `wg_easy_version` | `15.4.0-beta.1` | イメージタグ。**OIDCにはこれ以降が必要**(安定版は `15.3.0`) |
| `wg_easy_wg_port` | `51820` | WireGuardの公開ポート(UDP) |
| `wg_easy_ui_port` / `_ui_bind` | `51821` / `0.0.0.0` | Web UIのポートと待ち受けアドレス |
| `wg_easy_insecure` | `true` | HTTPでのアクセスを許可する(リバースプロキシを使うなら `false`) |
| `wg_easy_init_dns` | (アプリ既定) | クライアントに配るDNS |

⚠ `INIT_*`(接続先・管理者・アドレス範囲など)が効くのは**初回起動時だけ**です。
構築後の変更はWeb UIから行ってください。

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
- 設定を変えるだけなら `playbooks/vms/wg-easy.yml` を直接実行してください
  (ただし `INIT_*` は初回のみ有効です)
- ⚠ **VMを作り直すとクライアントの鍵も失われます。** `/opt/wg-easy/etc_wireguard` を
  バックアップしておいてください

## 注意
- `--ask-vault-pass` は必須です(`vault/proxmox.yml` と
  `vault/wg-easy.yml` を読むため。**2つは同じパスワードで暗号化してください**)
- 手動指定版では `--limit` を使わないでください(`hosts: localhost` のプレイが
  対象外になり、構築対象が登録されません)
- VM内の設定は `vm_` 接頭辞で指定します。`ssh_user` や `ipv4` をそのまま `-e` で渡すと
  **テンプレート側にも**焼き込まれてしまうためです
- VPNの接続先を自宅の可変グローバルIPにする場合は、
  [cloudflare-ddns-ui.yml](cloudflare-ddns-ui.md) で `wg_easy_init_host` と同じ名前の
  Aレコードを更新し続ける構成にできます
