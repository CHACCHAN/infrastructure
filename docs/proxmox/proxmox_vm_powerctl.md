# proxmox_vm_powerctl.yml
既存VMの電源を操作します(起動/シャットダウン)。

- `power_state` に `on`(起動)または `off`(シャットダウン)を指定します
- 既に目的の電源状態であれば何もしません(起動中のVMに `on` を指定した場合など)
- 指定したVMIDがクラスタ内に見つからない場合、接続先ノード以外に存在する場合は
  エラーで終了します(`proxmox_ip` にVMが存在するノードのIPアドレスを指定し直してください)
- SSHユーザは既定で `root`。変更する場合は `-e "proxmox_ssh_user=<ユーザ名>"` を追加します

## VMを起動する
```sh
ansible-playbook playbooks/proxmox/proxmox_vm_powerctl.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<対象VMのVMID> power_state=on"
```

## VMをシャットダウンする(既定: 5分待って、タイムアウトしても強制停止しない)
```sh
ansible-playbook playbooks/proxmox/proxmox_vm_powerctl.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<対象VMのVMID> power_state=off"
```
- ゲストOSへACPI経由でシャットダウンを要求し、既定で最大5分待ちます
- 5分以内にシャットダウンが完了しない場合、既定(`shutdown_force`未指定/false)では
  電源を切らずにエラーで終了します

## n分待ってもシャットダウンしない場合は強制終了する
```sh
ansible-playbook playbooks/proxmox/proxmox_vm_powerctl.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<対象VMのVMID> power_state=off \
    shutdown_timeout_minutes=3 shutdown_force=true"
```
- `shutdown_timeout_minutes`(既定 `5`): 何分待つか
- `shutdown_force`(既定 `false`): タイムアウト後も電源が切れていなければ強制停止するか
