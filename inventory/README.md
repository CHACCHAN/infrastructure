# inventory

ホストの宣言。唯一の真実の置き場所。VLAN・ID・VMID・IP の規則は [docs/design/network.md](../docs/design/network.md)。

## 構成

| 場所 | 内容 |
| --- | --- |
| `hosts/<VLAN番号>_<名前>.yml` | VLAN ごとに1ファイル。グループの `vlan` と、ホストの `id`・`node` などを書く |
| `group_vars/all/network.yml` | `vlan` と `id` から、VMID・IP・ゲートウェイを導出する |
| `group_vars/all/pve.yml` | Proxmox の API に共通する値 |
| `group_vars/<グループ>.yml` | グループに共通する値(ロールの既定値との差分だけ) |
| `host_vars/` | 個体差が出たホストだけ |

値の優先順位は [docs/conventions.md](../docs/conventions.md) の「変数の層」。

## ホストを足す

`new-host` スキル([.agents/skills/new-host/SKILL.md](../.agents/skills/new-host/SKILL.md))に従う。ホストが宣言するのは `id`・`node` と、既定値との差分だけ。VMID・IP・ゲートウェイは書かない。

## 確かめる

```sh
ansible-inventory --graph                                        # 警告が出ないこと
ansible k3s01 -c local -m ansible.builtin.debug -a 'var=vmid'    # 導出された値(vmid、ansible_host、gateway)
```
