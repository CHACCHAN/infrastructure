# pbs.yml — Proxmox Backup Serverを構築する

Proxmox Backup Server(PBS)をVMごと一気通貫で構築する。バックアップデータはOSと別のデータディスク(役割プロファイルの `pve_vm_disks` で宣言)に置き、**再起動後もマウントされていること**まで確認する。構築後は `https://<IP>:8007/`。PVE側への登録手順(データセンター→ストレージ→追加)は実行結果に表示される。

## 実行方法

```sh
# インベントリ実行(pbsグループの宣言どおり)
ansible-playbook playbooks/vm/pbs.yml

# 直接実行(インベントリ外に検証用をもう1台)
ansible-playbook playbooks/vm/pbs.yml \
  -e target=pbs02 -e profile=pbs -e vmid=1002 -e node=pve10 \
  -e ip=172.16.11.107 -e ip2=10.10.10.107/24 \
  -e pbs_data_disk_device=/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1
```

バックアップ転送は2枚目NIC(`cluster_ip`)の占有回線を通るため、直接実行では `-e ip2=` も指定する。データディスクのデバイス名は役割プロファイルが宣言しているが、プロファイルが届かない実行では `-e pbs_data_disk_device=` で渡す。

## 変数一覧

接続系の共通変数は [README.md](README.md#共通の変数)。全既定値の正は [roles/vm_pbs/defaults/main.yml](../../roles/vm_pbs/defaults/main.yml)。

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `pbs_data_disk_device` | str | ✔(disk有効時) | group_vars/pbs.yml | データディスクの永続名(`/dev/disk/by-id/...`)。`pve_vm_disks` の scsi index 1 に対応する |
| `pbs_data_disk_enabled` | bool | | `true` | データディスクを使うか |
| `pbs_data_disk_wipe` | bool | | `false` | 既存ディスクの初期化(OSディスク・マウント中は拒否される) |
| `pbs_datastore_name` / `pbs_datastore_path` | str | | `backup` / `/mnt/datastore/backup` | データストア名とマウント先 |
| `pbs_admin_user` | str | | `admin` | 管理者ユーザー(realm `@pbs`) |
| `pbs_admin_password` | str | | 自動生成 | 管理者パスワード(VM上の `/root/.pbs_admin_password` に保存) |
| `cluster_ip` | str | ✔ | hosts.yml | バックアップ転送用の占有ネットIP(直接実行では `-e ip2=`) |

## AWXでの実行

Job Template **`vm-pbs`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。Surveyは共通セット。

## つまずきやすいポイント

- **管理者パスワードがわからない** → 自動生成され、VM上の `/root/.pbs_admin_password` に保存される(SSHで確認)
- **データディスクの初期化が拒否される** → 安全装置。OSディスク・マウント中・子パーティションありのデバイスは `pbs_data_disk_wipe=true` でも消さない
- **PVEへの登録は手動** → 構築後に表示される手順どおり、PVEのデータセンター→ストレージ→追加でPBSを登録する
