# proxmox_vm_build.yml
指定したノードにテンプレートからVMを構築します。

- 事前に `proxmox_template_build.yml` でテンプレートを構築しておいてください
- `template_vmid` にはテンプレート構築時のVMID
  (`roles/proxmox_os_defaults/vars/os_defaults/<OSタイプ>.yml` の `versions.<バージョン>.template_vmid`。
  一覧は [proxmox_template_build.md](proxmox_template_build.md) を参照)を指定します

```sh
ansible-playbook playbooks/proxmox/proxmox_vm_build.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> template_vmid=<テンプレートのVMID> \
    vm_id=<新規VMのVMID> vm_name=<VM名> target_storage=<Proxmoxホストのストレージ名>"
```

- SSHユーザは既定で `root`。変更する場合は `-e "proxmox_ssh_user=<ユーザ名>"` を追加します
- 指定したVMIDがクラスタ内で既に使用されている場合はエラーで終了します
- テンプレートが接続先ノード以外に存在する場合はエラーで終了します。
  `proxmox_ip` にテンプレートが存在するノードのIPアドレスを指定し直してください

## 1つのテンプレートから複数のVMをまとめて構築する
`vm_id` と `vm_name` をどちらも `[...]` 形式の配列文字列にし、同じ個数で指定します
(先頭から順にペアとして扱われます)。

```sh
ansible-playbook playbooks/proxmox/proxmox_vm_build.yml --ask-vault-pass -vv \
-e 'proxmox_ip=<ProxmoxホストのIPアドレス> template_vmid=<テンプレートのVMID> \
    vm_id=[100,102,103] vm_name=["web1","web2","web3"] \
    target_storage=<Proxmoxホストのストレージ名>'
```

- `vm_id` と `vm_name` の個数が一致しない場合、`vm_id` に重複がある場合はエラーで終了します
- 途中のVMIDでクローンが失敗した場合、それ以降のVMは構築されません
  (成功済みのVMはそのまま残ります)
