# playbooks/pve

Proxmox VE の API だけを使い、テンプレートと VM を宣言どおりにする。ノードへ SSH しない。設計は [docs/design/pve.md](../../docs/design/pve.md)。

**どちらの playbook も、実機の Proxmox を変更する。** 実行は、実行を頼まれたときだけ行う([AGENTS.md](../../AGENTS.md) の安全規則)。

## 実行順

| 順 | playbook | 内容 | 実行例 |
| --- | --- | --- | --- |
| 1 | `template.yml` | OS(Debian 13)のテンプレートを、ノードごとに作る。作成済みなら何もしない | `ansible-playbook playbooks/pve/template.yml [-l pve01]` |
| 2 | `provision.yml` | インベントリのグループの VM を、テンプレートから作り、宣言どおりにして起動する | `ansible-playbook playbooks/pve/provision.yml -e target=k3s [-l k3s01]` |

`provision.yml` は `target` を渡し忘れると、どのホストにも一致せず何もしない。

## 前提

- `vault/proxmox.yml` に API トークンがある([vault/README.md](../../vault/README.md))。トークンには、操作に必要な権限が要る。
- `template.yml` の対象ホスト(グループ `pve`)に `template_storage` が宣言されている([roles/pve_template](../../roles/pve_template/README.md))。
- `provision.yml` の対象に `pve_vm_storage` と `pve_vm_ssh_pubkeys` が宣言されている([roles/pve_vm](../../roles/pve_vm/README.md))。
- VM を置くノードに、`template.yml` で作ったテンプレートがある。

## まだ無いもの

VM の停止と削除の playbook。作るときは、確認用の変数を必須にする。

## 注意

- ロールに接続先の Python を渡すため、`connection: local` と `ansible_python_interpreter: "{{ ansible_playbook_python }}"` を使う。
- 対話のないシェルから実行すると止まることがある。対処は [docs/conventions.md](../../docs/conventions.md) の「注意点」。
