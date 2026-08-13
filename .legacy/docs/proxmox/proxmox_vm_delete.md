# proxmox_vm_delete.yml
既存VMを削除します。**元に戻せません。**

- **対象VMの電源がオフの場合のみ**削除できます(起動中はエラーで終了します)
- 誤って別のVMIDを削除してしまう事故を防ぐため、`confirm_vm_id` に `vm_id` と
  同じ値を指定しないと実行されません
- 削除コマンド実行後、クラスタ上から実際に消えたことをポーリングで確認します
  (最大約1分。確認できない場合はエラーで終了し、手動確認を促します)
- 指定したVMIDがクラスタ内に見つからない場合、接続先ノード以外に存在する場合は
  エラーで終了します(`proxmox_ip` にVMが存在するノードのIPアドレスを指定し直してください)
- SSHユーザは既定で `root`。変更する場合は `-e "proxmox_ssh_user=<ユーザ名>"` を追加します

## VMを削除する
```sh
ansible-playbook playbooks/proxmox/proxmox_vm_delete.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<削除するVMのVMID> confirm_vm_id=<同じVMID>"
```

## バックアップ/レプリケーション設定や未参照ディスクもまとめて削除する
```sh
ansible-playbook playbooks/proxmox/proxmox_vm_delete.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<削除するVMのVMID> confirm_vm_id=<同じVMID> \
    purge=true destroy_unreferenced_disks=true"
```
- `purge`(既定 `false`): バックアップ・レプリケーション・HA設定からもVMIDを取り除くか
- `destroy_unreferenced_disks`(既定 `false`): 設定に紐付いていない、同じVMID名の
  ディスクもストレージから削除するか
