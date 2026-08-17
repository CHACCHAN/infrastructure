# provision.yml — VMを宣言どおりに収束させる

テンプレート準備→クローン→設定→cloud-init→電源まで、VMを**あるべき状態へ冪等に収束**させる。収束済みなら `changed=0` で、何度でも流せる。

## 実行方法

### インベントリ実行(宣言どおりの再現)

```sh
ansible-playbook playbooks/pve/provision.yml              # lab全体
ansible-playbook playbooks/pve/provision.yml -l k8s       # 役割ごと
ansible-playbook playbooks/pve/provision.yml -l yuya-dev  # 1台
```

### 直接実行(インベントリに無いVMを変数だけで構築)

```sh
# devプロファイルを継承(CPU/メモリ/鍵は group_vars/dev.yml から)
ansible-playbook playbooks/pve/provision.yml \
  -e target=tmp01 -e profile=dev -e vmid=799 -e node=pve07 -e ip=172.16.11.99

# プロファイルを継承せず(profile=lab)、必要な値だけ自分で決める
ansible-playbook playbooks/pve/provision.yml \
  -e target=tmp02 -e profile=lab -e vmid=798 -e node=pve06 -e ip=172.16.11.98 \
  -e pve_vm_cores=4 -e pve_vm_memory=4096 -e pve_os=ubuntu -e pve_os_version=24.04
```

仕組みと注意(1回1台・`-l` 併用禁止・IPは `-e ip=` で渡す等)は [adhoc.md](adhoc.md)。

## 動きかた

2つのプレイで収束させる。

1. **テンプレート準備**(`serial: 1`): 対象VMが未作成で、そのノードに(OS, バージョン)のテンプレートが無ければ作る。イメージはPVEノードがチェックサム検証付きで直接ダウンロードする
2. **VM収束**: 未作成ならテンプレートからフルクローン。以降は基本設定(CPU/メモリ/NIC/オプション)→ディスク(拡張のみ)→cloud-init(ユーザー/鍵/IP/DNS)→電源(既定: started)の順に、**差分がある項目だけ**適用する

実行前に2段階の検証があり、不足変数を**名前ごと列挙して**止まる:

- クラスタ共通値(`pve_storage` / `pve_bridge` / `pve_ipv4_prefix` / `pve_ipv4_gw`)— group_vars/all が届いていない実行環境の検出
- ホスト固有値(`vmid` / `node` / `ansible_host`)— 宣言漏れ・指定漏れの検出

## 変数一覧

### 必須(ホストごと)

| 変数 | 型 | 説明 | インベントリ実行での供給元 | 直接実行での渡しかた |
| --- | --- | --- | --- | --- |
| `vmid` | int | Proxmox VMID | hosts.yml | `-e vmid=` |
| `node` | str | 配置先PVEノード名 | hosts.yml | `-e node=` |
| `ansible_host` | str | 1枚目NICのIP | hosts.yml | `-e ip=`(adhocがホスト変数化する) |

### 必須(クラスタ共通)

| 変数 | 型 | 既定値 | 説明 |
| --- | --- | --- | --- |
| `pve_storage` | str | `ssd01`(宣言値) | ブートディスクのストレージ。**固定ではない**: 役割・個体・`-e`/Surveyで `ssd02` / `local-lvm` 等へ上書きできる(実例: authentik=local-lvm、supabase=ssd02) |
| `pve_bridge` | str | `vmbr0` | 1枚目NICのブリッジ(NIC構成ごと変えるなら `pve_vm_nets`) |
| `pve_ipv4_prefix` | int | `24` | IPv4プレフィックス長 |
| `pve_ipv4_gw` | str | `172.16.11.1` | デフォルトゲートウェイ |

供給元は [inventory/group_vars/all/pve.yml](../../inventory/group_vars/all/pve.yml)。インベントリが届かない実行では `-e` で渡す。

### 主な任意(既定値はrole defaultsまたはプロファイル)

| 変数 | 型 | 既定値 | 説明 |
| --- | --- | --- | --- |
| `target` | str | `lab` | 対象のホスト/グループ(直接実行では新ホスト名) |
| `profile` | str | なし | 直接実行で継承する役割グループ(継承なしは `lab`) |
| `pve_os` / `pve_os_version` | str | `debian` / `13` | クローン元OS(カタログは [README.md](README.md#テンプレートの仕組み)) |
| `pve_vm_cores` | int | `2` | CPUコア数 |
| `pve_vm_memory` | int | `2048` | メモリ(MiB) |
| `pve_vm_disk_size` | int | `20` | ディスク(GiB)。拡張のみ |
| `pve_vm_power` | str | `started` | 収束後の電源状態 |
| `pve_vm_nets` | list | `[{bridge: vmbr0}]` | NICのリスト(**任意の枚数**。並び順=net0,net1,…)。AWXでは変数欄にYAMLで渡す([書式](README.md#ストレージnicディスクの宣言何個でも)) |
| `pve_vm_disks` | list | `[]` | 追加ディスクのリスト(**任意の本数・ディスクごとにstorage指定可**)。同上 |
| `cluster_ip` | str | なし | 2枚目NICのCIDR(直接実行では `-e ip2=`) |
| `pve_ssh_user` | str | プロファイル | cloud-initが作るユーザー(未定義ならユーザー/鍵設定をスキップ) |
| `pve_ssh_pubkey_value` / `pve_ssh_pubkey_file` | str | なし / プロファイル | 公開鍵の本文/パス(本文が優先) |
| ハードウェア系(`pve_bridge` / `pve_vm_bios` / `pve_vm_machine` / `pve_vm_vga` / `pve_vm_cpu_type` / `pve_vm_disk_ssd` / `pve_vm_disk_iothread` / `pve_vm_disk_discard` / `pve_vm_onboot` / `pve_vm_agent`) | | 宣言値 | BIOS・SSDエミュレーション等([一覧と選べる値](README.md#ハードウェア設定すべて変数)) |

全既定値の正は [roles/pve_vm/defaults/main.yml](../../roles/pve_vm/defaults/main.yml) と [roles/pve_template/defaults/main.yml](../../roles/pve_template/defaults/main.yml)。

### 認証情報(vault)

`vault_proxmox_api_host` / `vault_proxmox_api_user` / `vault_proxmox_api_token_id` / `vault_proxmox_api_token_secret` の4変数を [vault/proxmox_api.yml](../../vault/proxmox_api.yml) が供給する(`ansible-vault edit` で編集)。

## AWXでの実行

Job Template **`pve-provision`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml)、適用: `ansible-playbook playbooks/awx/configure.yml`)。

- Surveyは共通セット(target / profile / vmid / node / ip / ip2 / pve_storage / SSHユーザー / 鍵2種 / cores / memory / disk_size + ハードウェア設定群)。**全問任意**: インベントリ実行なら未回答のまま起動、変えたい項目だけ回答する
- `profile` は選択式(選択肢はインベントリの役割グループから自動生成)
- リスト変数(`pve_vm_nets` / `pve_vm_disks`)はSurveyでは渡せないため、Job Templateの**変数欄**にYAMLで書く
- 鍵はファイルパスではなく**本文**で渡す(`pve_ssh_pubkey_value` / `pve_ssh_prikey_value`)
- Limitは使わない(絞り込みは `target`)

## つまずきやすいポイント

- **「未定義または空です」で止まった** → 止まるのは仕様(API操作前の検出)。メッセージに列挙された変数を、インベントリ宣言か `-e` で渡す
- **稼働中VMの設定変更が反映されない** → PVE側で保留され再起動まで反映されないことがある(該当時はメッセージで通知される。電源操作は自動では行わない)
- **`-e ansible_host=` を渡してはいけない** → extra varsは全ホストへ効くため、他ホストの参照まで書き換わる。直接実行のIPは必ず `-e ip=`([adhoc.md](adhoc.md)の解説参照)
- **ディスクを小さくできない** → 仕様(拡張のみ)。縮小したい場合は作り直す
