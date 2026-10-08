# ハードウェア

## 物理ノード

| ノード | CPU | RAM | ストレージ | 想定の役割(案) |
| --- | --- | --- | --- | --- |
| pve01 | Core i7-6950X(10C/20T) | 32GB(完全移行後に64GB) | SYS 256GB(NVMe、OS専用)、ssd01 480GB(SATA)、ssd02 1TB(SATA)、ssd03 1TB(SATA、移行後) | 汎用 |
| pve02 | Core i7-3610QM(4C/8T) | 16GB | SYS 1TB(SATA SSD) | k3s |
| pve03 | Core i7-3610QM(4C/8T) | 16GB | SYS 1TB(SATA SSD) | k3s |
| pve04 | Ryzen 7 3700X(8C/16T) | 32GB | SYS 128GB(NVMe、OS専用)、ssd01 1TB(SATA) | Hermes Agent |

Proxmox ノードは4台。

各ノードは 1GbE のNICを2つ持つ([network.md](network.md))。

| ノード | 筐体 | NIC |
| --- | --- | --- |
| pve01 | デスクトップ | Realtek の LAN カード2枚(内蔵 Intel NIC は、ドライバが不安定なので使わない) |
| pve04 | デスクトップ | 物理NIC 2つ |
| pve02・pve03 | ノートPC | 内蔵LAN + USB LAN |

### USB LAN の扱い

- USB LAN は、サスペンド(autosuspend)や抜けかけで、リンクが落ちることがある。`pve` ロールで、インターフェース名をMACアドレスで固定し、autosuspend を切る。
- 内蔵LANを NIC1、USB LANを NIC2 にする([network.md](network.md))。USB LAN は、人が触れて抜けない場所に設置する。

## 物理マシン(Proxmox ではないもの)

- PBS: 専用の物理マシン(VLAN23)。移行後に接続する。Core i3-3110M(2C/4T)、8GB、SYS 128GB(SATA、OS専用)、バックアップ専用の HDD 1TB(USB-SATA)。
- TrueNAS: 専用の物理マシン(VLAN23)。移行後に接続する。
- 接続方法は、移行が進んでから決める。スペックは未確認。

## ルータ

TP-Link ER605。VLAN間のルーティングとFWを担う([network.md](network.md))。

## ストレージ方式

Proxmox のストレージは LVM-thin(一般的な標準構成)。SYS 以外の SSD(ssd01〜)は、すべてVM用のストレージにする。pve02・pve03 は、SYS の1本の local-lvm に、Proxmox の OS と VM(k3s)を載せる。ZFS を使わないので、ARC がRAMを使わない。

### 未確認の事項

- NICの型番(USB LAN のチップ、デスクトップのNIC)。
- PBS のNICの数。TrueNAS のスペックとNICの数。
- pve02・pve03 の電源設定(蓋を閉じても止まらないこと)。

### CPU の世代に関する注意

i7-3610QM(Ivy Bridge)は AVX2 に対応していない。AVX2 を要求するイメージ(一部のML系やx86-64-v3向けのビルド)は、pve02・pve03 上の VM では動かない可能性がある。

## 配置の考え方(案・未確定)

| ノード | 載せるもの | 理由 |
| --- | --- | --- |
| pve01 | k3s01、開発VM | RAM・CPUに余裕がある汎用ノード |
| pve02 | k3s02 | 16GB のうち12GB をVMに使う。ZFS を使わないので、ホストに約4GBが残る |
| pve03 | k3s03 | 同上 |
| pve04 | Hermes Agent | Hermes 専用ノード |

- pve02・pve03 は実質 k3s 専用になる。他のVMを載せる余裕はない。
- 3台のk3sは同じ性能ではない。重いワークロード(PostgreSQL・Open WebUI など)は、`nodeAffinity` で k3s01 に寄せる。k3s02・k3s03 は etcd の定数、Longhorn の複製、軽いワークロードを受け持つ。
- LVM-thin のシンプールは、満杯になるとVMのディスクが壊れる。Longhorn のディスクを含めて、プールの使用率を監視する。
