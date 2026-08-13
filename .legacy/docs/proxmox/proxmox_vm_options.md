# proxmox_vm_options.yml
既存VMの動作設定(`qm set` のオプション)を変更します。

- **VMの電源はオンのままでも実行できます**(稼働中に変更できる設定を対象にしているため)
- CPU/メモリ/ディスク/NIC・BIOS・マシンタイプなど**VMの構成そのもの**を変える場合は
  [proxmox_vm_hardware.yml](proxmox_vm_hardware.md) を使ってください(電源オフが必要です)
- 指定できるオプション名は `qm set` に準拠します
  (一覧: https://pve.proxmox.com/pve-docs/qm.1.html )

```sh
ansible-playbook playbooks/proxmox/proxmox_vm_options.yml --ask-vault-pass -vv \
-e 'proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<対象VMのVMID> \
    vm_options={"agent":1,"onboot":1}'
```

- SSHユーザは既定で `root`。変更する場合は `-e "proxmox_ssh_user=<ユーザ名>"` を追加します
- `vm_options` は**スペースを含まないJSON文字列**、または辞書そのもので指定します
- `vm_options` と `vm_options_delete` の少なくとも一方は必須です

## よく使うオプション

| オプション | 内容 |
| --- | --- |
| `agent` | QEMUゲストエージェントの有効化(`1`)。IPアドレス表示・正常なシャットダウン・整合性のあるスナップショットに使います。ゲスト側に `qemu-guest-agent` の導入が必要です |
| `onboot` | Proxmoxホスト起動時にVMを自動起動する(`1`) |
| `startup` | 起動順序・待ち時間(例: `order=1,up=30`) |
| `description` | VMの説明文 |
| `protection` | 誤削除の保護(`1`) |
| `tags` | タグ(カンマ区切り) |

## オプションを削除する
`vm_options_delete` に削除したいオプション名を配列文字列(**スペースを含めないこと**)、
またはリストで指定します。

```sh
ansible-playbook playbooks/proxmox/proxmox_vm_options.yml --ask-vault-pass -vv \
-e 'proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<対象VMのVMID> \
    vm_options_delete=["description","tags"]'
```

## 値にスペースを含めたい場合
`-e` 全体をJSONにする方法が使えます。

```sh
ansible-playbook playbooks/proxmox/proxmox_vm_options.yml --ask-vault-pass -vv \
-e '{"proxmox_ip":"<ProxmoxホストのIPアドレス>","vm_id":101,"vm_options":{"description":"dev vm"}}'
```

## 注意
- 指定したVMIDがクラスタ内に見つからない場合、接続先ノード以外に存在する場合は
  エラーで終了します(`proxmox_ip` にVMが存在するノードのIPアドレスを指定し直してください)
- 設定はVM設定に即座に反映されますが、ゲスト側の動作に関わるもの(`agent` など)は
  次回起動時から有効になる場合があります
