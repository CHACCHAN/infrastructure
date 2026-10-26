# playbooks/pve

Proxmox VE の API だけを使い、テンプレートと VM を宣言どおりにする。ノードへ SSH しない。設計は [docs/design/pve.md](../../docs/design/pve.md)。

**この playbook は、実機の Proxmox を変更する。** 実行は、実行を頼まれたときだけ行う([AGENTS.md](../../AGENTS.md) の安全規則)。

## playbook

| playbook | 内容 | 実行例 |
| --- | --- | --- |
| `provision.yml` | インベントリのグループの VM を、テンプレートから作り、宣言どおりにして起動する | `ansible-playbook playbooks/pve/provision.yml -e target=k3s [-l k3s01]` |

`target` を渡し忘れると、どのホストにも一致せず何もしない。

## ディスクを拡張する

1. インベントリの `pve_vm_disk_size`(GiB)を大きくする。ディスクは縮められないため、置き先のストレージの空きを先に確かめる。
2. `ansible-playbook playbooks/pve/provision.yml -e target=<グループ> -l <ホスト名> 2>&1 | cat` で、起動ディスク(`scsi0`)を広げる。VM は止まらない。
3. `ansible-playbook playbooks/vm/<名前>.yml -l <ホスト名> 2>&1 | cat`(`<名前>` は `k3s` か `hermes`)で、VM の中のルートのパーティションと ext4 を広げる(`vm` ロール)。再起動は要らない。

## テンプレートの扱い

OS のテンプレートは、`provision.yml` が必要なときに作り、残す。

- 未作成の VM があるノードにテンプレートが無ければ、cloud イメージを取得して作る。あれば、そのまま使う。
- 作り直したいときは、Proxmox の画面でテンプレートと、`local` の取り込み用イメージを削除し、もう一度実行する。
- 作成の途中で失敗して VMID が残った場合、テンプレートではない VM とは衝突として止まる(中断された構築の可能性があるため、Proxmox 上で確認する)。

## 前提

- `vault/proxmox.yml` に API トークンがある([vault/README.md](../../vault/README.md))。トークンには、操作に必要な権限が要る。
- VM を置くノードのホスト(グループ `pve`)に、`template_storage`([roles/pve_template](../../roles/pve_template/README.md))と `lan_nic`(LAN 側の物理 NIC の番号)が宣言されている。
- VM のブリッジ(`vmbr<lan_nic><VLAN>`)が、置くノードにある。無いと、VM の起動で失敗する([docs/design/pve.md](../../docs/design/pve.md))。
- 対象の VM に `pve_vm_storage` と `pve_vm_ssh_pubkeys` が宣言されている([roles/pve_vm](../../roles/pve_vm/README.md))。

## まだ無いもの

VM の停止と削除の playbook。作るときは、確認用の変数を必須にする。

## 注意

- ロールに接続先の Python を渡すため、`connection: local` と `ansible_python_interpreter: "{{ ansible_playbook_python }}"` を使う。
- 対話のないシェルから実行すると止まることがある。対処は [docs/conventions.md](../../docs/conventions.md) の「注意点」。
