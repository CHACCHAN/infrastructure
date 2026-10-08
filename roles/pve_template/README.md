# pve_template

OS のテンプレート(第2層の器)を、Proxmox ノードごとに1つ作る。OS だけを持ち、IP・ユーザー・SSH 公開鍵などの個体の値は持たない(クローンするとき [pve_vm](../pve_vm/README.md) が cloud-init で渡す)。設計は [docs/design/pve.md](../../docs/design/pve.md)。

## 使い方

`playbooks/pve/template.yml` から使う([playbooks/pve/README.md](../../playbooks/pve/README.md))。

- 必須の変数は `template_storage`(テンプレートのディスクを置くストレージ)。`inventory/hosts/20_pve.yml` のホストに書く。
- 変数の一覧は `ansible-doc -t role pve_template` と `defaults/main.yml`。
- テンプレートの VMID は `9<template_index><ノード番号>`(pve01 は `90001`)、名前は `<template_name_prefix>-template-<ノード名>`。

## 処理の流れ

1. `check_existing.yml`: 同じ VMID の VM を探す。テンプレートではない VM とは衝突として止まる。完成済みなら以降を行わない。
2. `prepare_image.yml`: cloud イメージを、チェックサムを確かめてノードの import 領域へ置く。
3. `create_vm.yml`: 空の VM を作り、イメージからディスクを作ってテンプレートへ変換する。

`resolve.yml` は、テンプレートの VMID と名前を求める。`pve_vm` が `include_role` の `tasks_from: resolve` で使う。
