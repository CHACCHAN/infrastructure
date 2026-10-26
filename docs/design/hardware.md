# ハードウェア

## 物理ノード

| ノード | CPU | RAM | ストレージ | 役割 |
| --- | --- | --- | --- | --- |
| pve01 | Core i7-6950X(10C/20T) | DDR4 64GB | SYS 256GB(NVMe、OS と local-lvm)、ssd01 480GB、ssd02 960GB、ssd03 960GB | 汎用、k3s、Hermes Agent |
| pve02 | Ryzen 9 5950X(16C/32T) | DDR4 32GB | SYS 128GB(NVMe、OS と local-lvm)、ssd01 960GB、ssd02 480GB、ssd03 960GB | Hermes Agent、k3s |
| pve03 | Xeon E3-1241 v3(4C/8T) | DDR3 32GB | SYS 128GB(OS と local-lvm)、ssd01 960GB、ssd02 960GB | k3s |

Proxmox ノードは3台で、クラスタ(`PveCluster`)を組んでいる。

すべてのノードが 1GbE のNICを持つ。NIC1(LAN)・NIC2(クラスタ)は役割の名前で、物理のインターフェースとの対応はノードごとに違う([network.md](network.md))。

| ノード | NIC1(LAN) | NIC2(クラスタ) | 使わないNIC |
| --- | --- | --- | --- |
| pve01 | `nic0` | `nic2` | `nic1` |
| pve02 | `nic1` | `nic0` | なし |
| pve03 | `nic1` | `nic0` | なし |

## 物理マシン(Proxmox ではないもの)

- PBS: 専用の物理マシン(基幹システムの VLAN)。未接続。Core i3-3110M(2C/4T)、8GB、SYS 128GB(SATA、OS専用)、バックアップ専用の HDD 1TB(USB-SATA)。
- TrueNAS: 専用の物理マシン(基幹システムの VLAN)。未接続。
- 接続の時期と方法は未決。スペックは未確認。

## ルータ

OPNsense(機材は未確認)。VLAN間のルーティングとFWを担う。TP-Link ER605 は外す([network.md](network.md))。

## ストレージ方式

SYS 以外の SSD(ssd01〜)は、すべてVM用のストレージにし、通常の LVM(thick)にする。SYS の `local-lvm` は LVM-thin([pve.md](pve.md))。ZFS を使わないので、ARC がRAMを使わない。

### 未確認の事項

- NICの型番。
- PBS のNICの数。TrueNAS のスペックとNICの数。

### CPU の世代

3台とも AVX2 に対応している(Broadwell-E、Zen 3、Haswell)。

## 配置

| ノード | 載せるもの | 理由 |
| --- | --- | --- |
| pve01 | k3s01、開発VM、Hermes Agent(3台) | RAM・CPUに余裕がある汎用ノード |
| pve02 | k3s02、Hermes Agent(3台) | 32GB のうち12GB を k3s02 に使い、残りを Hermes に回す |
| pve03 | k3s03 | 32GB のうち12GB を k3s03 に使う |
- 3台のk3sは同じ性能ではない。重いワークロードは、`nodeAffinity` で k3s01・k3s02 に寄せる。k3s03 は etcd の定数、Longhorn の複製、軽いワークロードを受け持つ。
  - 寄せるのは、メモリを多く使う Open WebUI・Authentik・LiteLLM・Nextcloud Hub と、それぞれの PostgreSQL。Homarr・cloudflared は寄せない。
  - 寄せ先はインベントリの `heavy_workloads` のノードで、条件は優先(preferred)にする。寄せ先が止まっても、k3s03 で動き続けるため。
- `ssd01` に置く k3s の VM のディスク(430GiB)には、Longhorn のデータも入る。VM の中のディスクの使用率を監視する。
