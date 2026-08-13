# Proxmox操作Playbook(playbooks/proxmox/)
- このディレクトリのplaybookはProxmoxホストに対して操作を行います
- VM内には影響しません
- インベントリファイルは使用しません。接続先は `proxmox_ip` にIPアドレスを直接指定します
  (ノード名は接続先ホストから自動取得されます)
- 実行はリポジトリ直下から `ansible-playbook playbooks/proxmox/<playbook名>.yml` で行います
  (Proxmoxホストへの接続パスワードを `vault/proxmox.yml` から読むため `--ask-vault-pass` が必須)

## Playbook一覧
各playbookの詳しい使い方は同じディレクトリの同名ファイルを参照してください。

| Playbook | 内容 |
| --- | --- |
| [proxmox_template_build.yml](proxmox_template_build.md) | CloudInitテンプレートを構築する |
| [proxmox_vm_build.yml](proxmox_vm_build.md) | テンプレートからVMを構築する(複数まとめても可) |
| [proxmox_vm_hardware.yml](proxmox_vm_hardware.md) | 既存VMのハードウェア設定(CPU/メモリ/ディスク/NIC等)を変更する |
| [proxmox_vm_options.yml](proxmox_vm_options.md) | 既存VMの動作設定(QEMUエージェント/自動起動/説明等)を変更する |
| [proxmox_vm_cloudinit.yml](proxmox_vm_cloudinit.md) | 既存VMのcloud-init設定(ユーザー/パスワード/SSH公開鍵/IP)を変更する |
| [proxmox_vm_powerctl.yml](proxmox_vm_powerctl.md) | 既存VMの電源を操作する(起動/シャットダウン) |
| [proxmox_vm_delete.yml](proxmox_vm_delete.md) | 既存VMを削除する |
