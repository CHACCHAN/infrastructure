# proxmox-backup-server.yml

Proxmox Backup Server(PBS)のVMを、Debian 13(cloud image)テンプレートの構築から
VM内部のセットアップまで一気通貫で構築します。
構築後はPVEの「データセンター → ストレージ → 追加 → Proxmox Backup Server」で
バックアップ先として登録できます。

## 2つの実行方法

```sh
# インベントリ版: 全台 / 1台だけ
ansible-playbook playbooks/services/proxmox-backup-server.yml --ask-vault-pass
ansible-playbook playbooks/services/proxmox-backup-server.yml --ask-vault-pass --limit <VMのIP>

# 手動指定版(インベントリにホストが無ければ自動でこちら)
ansible-playbook playbooks/services/proxmox-backup-server.yml --ask-vault-pass -vv \
-e "vm_node=<ProxmoxノードのIP> vm_id=<VMID> vm_name=proxmox-backup-server" \
-e "vm_ipv4=<VMのIP>/24 vm_ipv4_gw=<ゲートウェイ>" \
-e "vm_ssh_user=pbs vm_ssh_pubkey_file=~/.ssh/id_ed25519_pbs.pub vm_ssh_prikey=~/.ssh/id_ed25519_pbs" \
-e 'vm_hardware={"cpu":{"cores":2,"type":"x86-64-v2-AES"},"memory":{"size":4096},"resize":[{"bus":"scsi","index":0,"size":128}]}' \
-e 'vm_options={"agent":1,"onboot":1}'
```

- `--ask-vault-pass` は必須です(`vault/proxmox.yml` を読むため)
- 対象の書き方は [inventories/lab/proxmox-backup-server.yml](../../inventories/lab/proxmox-backup-server.yml)
  を参照してください(1台1ホスト、ホスト名はVMのIPアドレス)

## 実行される順番

1. [proxmox_template_build.yml](../proxmox/proxmox_template_build.md) —
   Debian 13 cloud imageのテンプレート構築(既にあれば何もしない)
2. [proxmox_vm_build.yml](../proxmox/proxmox_vm_build.md) — VMをクローン
3. [proxmox_vm_hardware.yml](../proxmox/proxmox_vm_hardware.md) —
   CPU/メモリ/ディスク拡張(`vm_hardware` 指定時)
4. [proxmox_vm_options.yml](../proxmox/proxmox_vm_options.md) —
   QEMUエージェント・自動起動(`vm_options` 指定時)
5. [proxmox_vm_cloudinit.yml](../proxmox/proxmox_vm_cloudinit.md) — cloud-init設定
6. [proxmox_vm_powerctl.yml](../proxmox/proxmox_vm_powerctl.md) — VMの起動
7. SSH接続待ち
8. [playbooks/vms/proxmox-backup-server.yml](../vms/proxmox-backup-server.md) —
   VM内部のセットアップ(PBSのインストール・データストア・管理者ユーザー)

## ディスク構成(OS用SSD + バックアップ用ディスク)

**ディスクは2本構成**です。`vm_hardware` で次のように指定します。

| ディスク | 指定 | 用途 |
| --- | --- | --- |
| `scsi0` | `resize`(テンプレートのクローンを拡張) | OS用。`proxmox_storage`(SSD)に載る |
| `scsi1` | `disks`(別ストレージに新規作成) | バックアップの実データ用。VM内でGPTで初期化され `/mnt/datastore/backup` にマウントされる |

```yaml
vm_hardware:
  resize:
    - { bus: scsi, index: 0, size: 32 }        # OS用(SSD)
  disks:
    - bus: scsi
      index: 1
      storage: hdd01                            # バックアップを置くストレージ
      size: 512
      backup: 0                                 # このディスク自体はPVEのバックアップ対象外
```

`disks` の指定が無いと、Proxmox操作を始める前に停止します
(バックアップの置き場所が無い状態でVMを作らないため)。

⚠ **`disks` は「新しいディスクを作る」指定です。** 構築済みVMに対して
[proxmox_vm_hardware.yml](../proxmox/proxmox_vm_hardware.md) を `disks` 付きで
実行すると、空のディスクに差し替わり、それまでのバックアップが切り離されます。
容量を増やすときは `disks` ではなく **`resize`** を使ってください。

## ネットワーク構成(NIC 2枚)

| NIC | IP | 用途 |
| --- | --- | --- |
| `net0` | インベントリのホスト名(例: `172.16.11.7`) | 外からの入口。SSHとWeb UIに使う |
| `net1` | `vm_cluster_ipv4`(例: `10.10.30.7/24`) | Proxmox間の占有回線。PVE↔PBSのバックアップ通信を流す |

- `vm_cluster_ipv4` を指定すると、cloud-initの `ipconfig1` でnet1にIPが付き、
  playbook最後の案内で**PVEに登録すべき接続先が占有回線側のIP**になります
- net1が `vm_hardware` の `network` に無い状態で `vm_cluster_ipv4` を指定すると停止します
  (テンプレートは `net0` の1枚しか持たないため)
- 占有回線は外に出ないため `vm_cluster_ipv4_gw` は指定しないでください
  (デフォルトゲートウェイが2つあると通信経路が不安定になります)
- PBSのWeb UI/APIは両方のNICで待ち受けます。SSHとブラウザはnet0側のまま使い、
  PVEのストレージ登録だけをnet1側に向ける形になります

## PBS本体の設定

指定できる項目(`pbs_` 接頭辞)は [docs/vms/proxmox-backup-server.md](../vms/proxmox-backup-server.md)
を参照してください。インベントリや `-e` の値がそのまま渡ります。

- 管理者パスワードは未指定なら自動生成され、VM内の `/root/.pbs_admin_password` に
  保存されます(Web UIのログインは `admin@pbs`)
- バックアップ元のPVEと同じクラスタのノード上にPBSのVMを置く構成も動きますが、
  そのノード自体が壊れるとバックアップごと失われます。可能なら別ノード・別ストレージに
  置いてください

## 注意

- 同じ `vm_id` のVMが既にあると失敗します。
  `playbooks/proxmox/proxmox_vm_delete.yml` で削除するか、別の `vm_id` にしてください
- 構築済みVMのPBSだけを更新する場合は `playbooks/vms/proxmox-backup-server.yml` を
  直接実行してください(Proxmox側の操作をスキップできます)
