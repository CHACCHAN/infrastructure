# proxmox-backup-server.yml

起動済みのDebian 13 VMにSSH接続し、Proxmox Backup Server(PBS)を
APTパッケージで構築します(Dockerは使いません)。

```sh
ansible-playbook playbooks/vms/proxmox-backup-server.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名>"

# データストア名と管理者パスワードまで一度に決める場合
ansible-playbook playbooks/vms/proxmox-backup-server.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名>" \
-e "pbs_datastore_name=backup pbs_admin_password=<16文字以上の英数字_.-> "
```

## 必要なスペック

| 項目 | 最低 | 推奨 |
| --- | --- | --- |
| OS | **Debian 13(trixie)専用** | 〃(PBS 4のリポジトリがtrixie向けのため) |
| CPU | 2コア | 4コア(検証・GCが並列で走るため多いほど良い) |
| メモリ | 2GB | 4GB以上 |
| ディスク | **2本**(OS用 + バックアップ用) | OS用16GB以上、バックアップ用は保存量に合わせる |

## ディスク構成(OS用とバックアップ用を分ける)

**OS用ディスク(scsi0)とは別のディスクを、データストアのパスにマウントします**。
バックアップの実データはそのディスクだけに置かれ、OS用ディスクは消費しません。

- 2本目のディスクは **GPTで初期化**します。ディスク全体を使うパーティションを1つ作り、
  ファイルシステムを作成して、UUIDで `/etc/fstab` に登録し `pbs_datastore_path` へ
  マウントします(`/dev/sdb` → `/dev/sdb1`、`/dev/nvme0n1` → `/dev/nvme0n1p1`)
- どのディスクを使うかは自動判別します(パーティションを1つも持たないディスクが
  1本だけならそれ)。候補が複数ある場合は `pbs_data_disk_device` で明示してください
- **既にファイルシステムがあるディスクは作り直しません**。種類が違う場合は
  上書きせずに中止します(既存データの保護)
- 再実行時は「マウント済みのデバイス → 同じラベル(`pbs-datastore`)の
  ファイルシステム → 未初期化のディスク」の順に探すため、初期化をやり直しません
  (前回の実行が途中で終わっていた場合も、作りかけのパーティションを引き継ぎます)
- マウントできなかった場合はデータストアを作る前に停止します
  (バックアップがOS用ディスクに書き込まれるのを防ぐため)
- `pbs_data_disk_device` にパーティション(`/dev/sdb1`)を直接指定した場合は、
  GPTの初期化を行わずそのまま使います

専用ディスクを使わずOS用ディスクにデータストアを作る場合は
`-e "pbs_data_disk_enabled=false"` を指定します。

## 指定できる項目

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `pbs_datastore_name` | `backup` | データストア名(PVEにストレージ登録するとき指定する名前) |
| `pbs_datastore_path` | `/mnt/datastore/<データストア名>` | バックアップの実データを置くパス(2本目のディスクのマウント先) |
| `pbs_data_disk_enabled` | `true` | バックアップ用に別ディスクを使うか |
| `pbs_data_disk_device` | (自動判別) | バックアップ用ディスク(例: `/dev/sdb`) |
| `pbs_data_disk_partition` | `true` | GPTで初期化してパーティションを作るか(`false` でディスク全体を直接フォーマット) |
| `pbs_data_disk_fstype` | `ext4` | バックアップ用ディスクのファイルシステム(`ext4` / `xfs`) |
| `pbs_data_disk_label` | `pbs-datastore` | ファイルシステムとGPTパーティションに付ける名前 |
| `pbs_data_disk_mount_opts` | `defaults,noatime` | マウントオプション |
| `pbs_admin_user` | `admin` | Web UIの管理者ユーザー名(`@pbs`レルムに作成される) |
| `pbs_admin_password` | (自動生成) | 管理者パスワード。16文字以上の英数字と `_` `.` `-` |
| `pbs_cluster_ip` | (空) | PVEに登録するときの接続先IP(占有回線側)。案内の表示にのみ使う |
| `pbs_repo_url` | `http://download.proxmox.com/debian/pbs` | APTリポジトリ(サブスクリプション契約時は enterprise 側に変更) |
| `pbs_repo_component` | `pbs-no-subscription` | リポジトリのコンポーネント |
| `pbs_min_free_disk_gb` | `8` | インストール前にOS用ディスクに必要な空き容量(GiB) |

- 管理者パスワードは「`-e` の指定 > 既存(変更しない) > 自動生成」の順で決まります。
  自動生成した値はVM内の `/root/.pbs_admin_password`(root専用)に保存されます
- **root@pamではWeb UIにログインできません**(cloud-init構築のVMはrootパスワードが
  無いため)。ログインは `<pbs_admin_user>@pbs` を使い、レルムに
  「Proxmox Backup authentication server」を選びます

## 実施する内容

1. VM共通の初期セットアップ(パッケージ更新〜QEMUゲストエージェント)
2. Proxmoxの署名鍵(SHA256検証あり)とAPTリポジトリ(deb822)の設定
3. `proxmox-backup-server` のインストールとサービスの有効化
4. バックアップ用ディスクのフォーマットとマウント(fstab登録・マウント確認)
5. データストアの作成(既存なら何もしない)
6. 管理者ユーザーの作成とAdmin権限の付与
7. ufwが有効な場合は8007/tcpの開放
8. Web UI(8007)とデータストアの動作確認、容量と証明書fingerprintの表示
9. 再起動後にバックアップ用ディスクが再マウントされることの確認

## 構築後: PVEのバックアップ先として登録する

PVE側の「データセンター → ストレージ → 追加 → Proxmox Backup Server」で登録します。

| 項目 | 値 |
| --- | --- |
| サーバー | このVMのIPアドレス(NIC2枚構成なら**占有回線側のIP**) |
| ユーザー名 | `<pbs_admin_user>@pbs`(例: `admin@pbs`) |
| データストア | `pbs_datastore_name` の値(例: `backup`) |
| Fingerprint | playbook最後に表示される値(または `proxmox-backup-manager cert info`) |

登録後は通常のバックアップジョブの保存先として選べます(重複排除・増分は自動)。

## 再実行について

再実行しても壊れないように作っています。データストア・管理者ユーザーは
既存があれば変更しません(`pbs_admin_password` を指定した場合のみパスワードを更新)。
PBS本体のバージョンアップは `apt update && apt upgrade` で行ってください
(このplaybookの再実行でも共通セットアップのパッケージ更新で上がります)。

## うまくいかないとき

- **「データ用ディスクを自動判別できませんでした」**: 2本目のディスクがVMに
  付いていないか、候補が複数あります。候補が複数の場合は
  `-e "pbs_data_disk_device=/dev/sdb"` で明示してください
- **空き容量チェックで止まる**: OS用ディスクが小さいままです。
  `playbooks/proxmox/proxmox_vm_hardware.yml` のresizeで拡張してください(VMの停止が必要)
- **Web UIに入れない**: レルムが「Proxmox Backup authentication server」に
  なっているか確認してください。パスワードはVM内の `/root/.pbs_admin_password` にあります
- **PVEからの接続でTLSエラー**: 自己署名証明書のため、登録時にFingerprintの入力が必要です

## バックアップ用ディスクの容量を増やすとき

`playbooks/proxmox/proxmox_vm_hardware.yml` の **resize** で `scsi1` を拡張したあと、
VM内でパーティションとファイルシステムを順に広げます。

```sh
# Proxmox側でディスクを拡張(VMの停止が必要)
ansible-playbook playbooks/proxmox/proxmox_vm_hardware.yml --ask-vault-pass \
-e 'proxmox_ip=<ノードIP> vm_id=<VMID> vm_hardware={"resize":[{"bus":"scsi","index":1,"size":1920}]}'

# VM内でパーティションを広げてからファイルシステムを広げる
sudo growpart /dev/sdb 1
sudo resize2fs /dev/sdb1        # xfsなら sudo xfs_growfs /mnt/datastore/backup
```

⚠ `disks` は**新しいディスクを作る**指定です。構築済みVMに `disks` 付きで実行すると
空のディスクに差し替わり、それまでのバックアップが切り離されます。
