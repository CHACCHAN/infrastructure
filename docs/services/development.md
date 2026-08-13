# development.yml
開発専用VMを、テンプレート構築からVM内部のセットアップまで一気通貫で構築します。

VM内のセットアップは**Debian 13専用**のため、既定で Debian 13 を構築します。

## 2つの実行方法
対象の決め方だけが違い、それ以降の処理は共通です。

| 実行方法 | 対象 | 台数 |
| --- | --- | --- |
| インベントリ版(既定) | `inventories/lab/development.yml` のホスト。`--limit` で選択 | 1台〜全台 |
| 手動指定版(`-e "manual=true"`) | `-e` で指定した1台 | 1台 |

```sh
# インベントリ版: 全台 / 1台だけ / 複数台
ansible-playbook playbooks/services/development.yml --ask-vault-pass -vv -e "vm_ssh_password=<パスワード>"
ansible-playbook playbooks/services/development.yml --ask-vault-pass -vv \
--limit 192.168.10.21 -e "vm_ssh_password=<パスワード>"
ansible-playbook playbooks/services/development.yml --ask-vault-pass -vv \
--limit '192.168.10.21,192.168.10.22' -e "vm_ssh_password=<パスワード>"

# 手動指定版
ansible-playbook playbooks/services/development.yml --ask-vault-pass -vv \
-e "manual=true vm_node=<ノードIP> proxmox_storage=<ストレージ名> \
    vm_id=<VMID> vm_name=<VM名> vm_ipv4=<IPv4/CIDR> vm_ipv4_gw=<ゲートウェイ> \
    vm_ssh_user=<ユーザ名> vm_ssh_password=<パスワード> \
    vm_ssh_pubkey_file=~/.ssh/<公開鍵> vm_ssh_prikey=~/.ssh/<秘密鍵>"
```

- インベントリの `development` グループが空なら、`manual=true` なしでも手動指定版になります
- 手動指定版では**ハードウェアと動作設定の既定値がありません**(インベントリの `vars:` に
  あるため)。同じ構成にするには `vm_hardware` / `vm_options` も `-e` で渡してください

## インベントリ
[inventories/lab/development.yml](../../inventories/lab/development.yml) に**1台1ホスト**で書きます。
ホスト名はVMのIPアドレスです。

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
8. [playbooks/vms/development.yml](../vms/development.md) — VM内部のセットアップ

手順1〜6はProxmoxノードへ、手順7〜8はVM自身へ接続します。

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
| `vm_ssh_user` | cloud-initで作成するログインユーザー(SSH・cockpit・RDP共通) |
| `vm_ssh_pubkey_file` | VMに登録するSSH公開鍵のファイルパス(`vm_ssh_pubkey` で内容の直接指定も可) |
| `vm_ssh_prikey` | 秘密鍵のパス。VM内セットアップのSSH接続に使います |
| `vm_hardware` / `vm_options` | ハードウェア / 動作設定(後述) |

## ハードウェア・動作設定の既定値
インベントリの `vm_hardware` / `vm_options` で指定しています。書式は
[proxmox_vm_hardware.md](../proxmox/proxmox_vm_hardware.md) /
[proxmox_vm_options.md](../proxmox/proxmox_vm_options.md) を参照してください。

| 項目 | 既定値 | 指定 |
| --- | --- | --- |
| CPU / RAM | 8コア(`host`)/ 8GB | `cpu: {cores: 8, type: host}` `memory: {size: 8192}` |
| BIOS / マシン / 画面 | SeaBIOS / Q35 / 標準VGA | `options: {bios: seabios, machine: q35, vga: std}` |
| ディスク | 256GiB | `resize: [{bus: scsi, index: 0, size: 256}]` |
| QEMUエージェント / 自動起動 | 有効 | `agent: 1` `onboot: 1` |

- ディスクは **`resize`(既存ディスクの拡張)で指定します**。`disks` に書くと新しい空ディスクに
  置き換わり、クローンしたOSディスクが未使用ボリュームとして残ります
- 既に指定サイズ以上なら拡張は行われません(Proxmoxは縮小に対応していないため)
- `-e` で `vm_hardware` を渡すとインベントリの値は**置き換え**になるため、
  変更しない項目も併せて指定してください(JSONにはスペースを含めないこと)

## `-e` で渡す変数
| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `manual` | インベントリが空なら `true` | 手動指定版として動作します |
| `vm_ssh_password` | (なし) | VMのログインパスワード(cockpitのWebコンソールとRDPで使用) |
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
| `vm_ip` | ホスト名 | SSHの接続先(ホスト名と違うIPで繋ぐ場合) |
| `vm_gui_required` | `false` | `true` でXFCE + RDPも構成 |
| `vm_ssh_wait_timeout` | `600` | SSHログインできるまでの待機上限(秒) |

### 例: 1台だけメモリを増やしてGUIも入れる
```sh
ansible-playbook playbooks/services/development.yml --ask-vault-pass -vv \
--limit 192.168.10.21 \
-e 'vm_ssh_password=<パスワード> vm_gui_required=true \
    vm_hardware={"cpu":{"cores":8,"type":"host"},"memory":{"size":16384},"resize":[{"bus":"scsi","index":0,"size":512}]}'
```

### 例: 手動指定版でインベントリと同じ構成にする
```sh
ansible-playbook playbooks/services/development.yml --ask-vault-pass -vv \
-e 'manual=true vm_node=192.168.10.11 proxmox_storage=local-lvm \
    vm_id=200 vm_name=devvm \
    vm_ipv4=192.168.10.60/24 vm_ipv4_gw=192.168.10.1 \
    vm_ssh_user=devuser vm_ssh_password=<パスワード> \
    vm_ssh_pubkey_file=~/.ssh/dev-vm-ssh.pub vm_ssh_prikey=~/.ssh/dev-vm-ssh \
    vm_hardware={"cpu":{"cores":8,"type":"host"},"memory":{"size":8192},"options":{"bios":"seabios","machine":"q35","vga":"std"},"resize":[{"bus":"scsi","index":0,"size":256}]} \
    vm_options={"agent":1,"onboot":1}'
```

## 注意
- **同じ `vm_id` での再実行はできません。** 作り直す場合は
  `playbooks/proxmox/proxmox_vm_delete.yml` で削除するか、別の `vm_id` にしてください
- 全台実行時は並行して処理されます。1台が失敗しても他はそのまま進みます
- `--ask-vault-pass` は必須です(`vault/proxmox.yml` を読むため)
- 手動指定版では `--limit` を使わないでください(`hosts: localhost` のプレイが
  対象外になり、構築対象が登録されません)
- VM内の設定は `vm_` 接頭辞で指定します。`ssh_user` や `ipv4` をそのまま `-e` で渡すと
  **テンプレート側にも**焼き込まれてしまうためです
- 他のOSを指定した場合、手順7までは動作しますが手順8でOS判定により停止します
