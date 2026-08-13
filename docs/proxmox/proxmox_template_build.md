# proxmox_template_build.yml
指定したノードに対してCloudInitのテンプレートを構築します。

- `os_type` は `roles/proxmox_os_defaults/vars/os_defaults/<OSタイプ>.yml` から選んでください(例: debian)
- `os_version` は下表の対応バージョンから選んでください。省略した場合は各OSの既定バージョンが使われます
- 対応していない `os_version` を指定した場合は、対応バージョン一覧を表示して構築前に停止します
- テンプレートは **SCSIコントローラ `virtio-scsi-single`**、OS用ディスク(`scsi0`)は
  **IOスレッド・SSDエミュレーション・discardを有効**にして構築します。クローンしたVMが
  この設定を引き継ぎます(変更する場合は `proxmox_template_build_scsihw` /
  `proxmox_template_build_iothread` / `proxmox_template_build_ssd` /
  `proxmox_template_build_discard`)。
  **HDD上に置くVMは、インベントリの `vm_hardware.disk_options` で `ssd: 0` を指定**します
  ([proxmox_vm_hardware.md](proxmox_vm_hardware.md) を参照)

```sh
ansible-playbook playbooks/proxmox/proxmox_template_build.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> proxmox_storage=<Proxmoxホストのストレージ名> \
    os_type=<OSタイプ> os_version=<バージョン> \
    ssh_user=<ユーザ名> ssh_password=<パスワード> ssh_pubkey='<公開鍵>' \
    ipv4=<IPv4アドレス/CIDR> ipv4_gw=<IPv4アドレス> \
    ipv6=<IPv6アドレス/CIDR> ipv6_gw=<IPv6アドレス>"
```

- SSHユーザは既定で `root`。変更する場合は `-e "proxmox_ssh_user=<ユーザ名>"` を追加します
- cloud-init関連(`ssh_user` / `ssh_password` / `ssh_pubkey` / `ipv4` / `ipv4_gw` / `ipv6` / `ipv6_gw`)は
  すべて任意です。指定した項目だけがテンプレートに設定されます
- `ssh_password` はVM内のログインパスワード(cloud-initの `cipassword`)です。
  Proxmoxホストへの接続パスワードとは別物で、**テンプレートに設定するとクローンした
  全VMに引き継がれます**。VMごとに変えたい場合はクローン後に
  [proxmox_vm_cloudinit.yml](proxmox_vm_cloudinit.md) で設定してください
- 適用処理は `proxmox_vm_cloudinit.yml` と共通の `tasks/apply_cloudinit.yml` を使用します
- 対象VMIDのテンプレートがクラスタ内の別ノードに存在する場合は、Proxmox API経由で
  そちらを削除してから接続先ノードで再構築します

## 対応OS / バージョン
`template_vmid` はクラスタ内で一意である必要があるため、OS・バージョンごとに別の値を割り当てています。

| os_type | os_version | template_vmid | template_name |
| --- | --- | --- | --- |
| debian | `13` (既定) | 9000 | debian13-template |
| debian | `12` | 9002 | debian12-template |
| ubuntu | `26.04` (既定) | 9001 | ubuntu2604-template |
| ubuntu | `24.04` | 9003 | ubuntu2404-template |
| ubuntu | `22.04` | 9004 | ubuntu2204-template |
| rocky | `10` (既定) | 9005 | rocky10-template |
| rocky | `9` | 9006 | rocky9-template |
| almalinux | `10` (既定) | 9007 | almalinux10-template |
| almalinux | `9` | 9008 | almalinux9-template |

- Ubuntuの対応バージョンはLTSのみです
- DebianとUbuntuはURLの `latest` / `current` を参照しているため、各シリーズの
  最新ポイントリリースが取得されます(ファイル名は変わりません)

```sh
# 例: Debian 12のテンプレートを構築する
ansible-playbook playbooks/proxmox/proxmox_template_build.yml --ask-vault-pass -vv \
-e "proxmox_ip=192.168.10.11 proxmox_storage=local-lvm os_type=debian os_version=12"

# 例: Ubuntuの既定バージョン(26.04)のテンプレートを構築する
ansible-playbook playbooks/proxmox/proxmox_template_build.yml --ask-vault-pass -vv \
-e "proxmox_ip=192.168.10.11 proxmox_storage=local-lvm os_type=ubuntu"
```

## バージョンやOSを追加する
`roles/proxmox_os_defaults/vars/os_defaults/<OSタイプ>.yml` の `versions` にエントリを足すだけで追加できます。
新しいOSを追加する場合は、既存ファイルをコピーして `os_defaults_<OSタイプ>` のキー名を
ファイル名に合わせてください(`os_type` と同じ名前である必要があります)。

- `template_vmid` は既存のものと重複しない値を割り当ててください
- チェックサムファイルはGNU形式(`<ハッシュ>  <ファイル名>`)・
  BSD形式(`SHA256 (<ファイル名>) = <ハッシュ>`)・ハッシュのみのいずれにも対応しています
- `cloud_image_checksum_algorithm` は `sha256` / `sha512` に対応しています
