# k3s 設計

## 決定済み

### ノード

- 3台とも k3s のサーバーで、ワークロードも動かす。名前は `k3s01`〜`k3s03`、VMID は `2101`〜`2103`、IP は `172.20.21.1`〜`.3`(VLAN21)。
- k3s01 の仮想CPUは4コア、起動ディスクは256GiB(pve01 の `ssd01` に置く)。
- OS は Debian 13 minimal。RAM は12GBで固定し、Proxmox のメモリバルーニングは切る。
- ZRAM を使う。kubelet は `failSwapOn: false` と `memorySwap.swapBehavior: NoSwap` にする(Pod はスワップせず、ホスト側の保険として使う)。

### VIP と Ingress

| 用途 | IP | 実装 |
| --- | --- | --- |
| Ingress(HTTP/HTTPS) | `172.20.21.5` | MetalLB(L2) |
| Kubernetes API | `172.20.21.6` | kube-vip |

- k3s の `servicelb` は無効にする。Traefik は k3s 内蔵のものを使う。
- Traefik は、クラスタ内のサービスだけでなく、LAN内のサービス(Proxmox・TrueNAS・PBS の管理UI)へのリバースプロキシも兼ねる。ホスト名のDNSは `172.20.21.5` を指す。例: `pve01.cc-chacchan.com` → Traefik → `172.20.20.1:8006`。
- 管理UIは Cloudflare Tunnel を経由しない。

### ストレージとバックアップ

- Longhorn を使う。通常のPVCは複製数2にする。
- k3s02・k3s03(pve02・pve03 上)は、仮想ディスクを1本だけ持つ。Longhorn のデータは、OS と同じディスクに置く([hardware.md](hardware.md))。
- k3s ノードは、VMとしてのバックアップを取らない。コード(Ansible・Helm・マニフェスト)から再構築する。
- Longhorn のバックアップ先(NFSのNAS)は未構築。**現時点では、k3s上の永続データにバックアップがない。**

### アプリ

- Portainer は k3s の中で動かし、k3s の Web UI として使う(無料枠は3ノード)。
- PostgreSQL は k3s で運用する。インスタンスは1つで、ボリュームは Longhorn(複製数2)に置く。
- Authentik は k3s で運用する。旧構成からは移さず、新規に構築して手動で設定する。
- Rancher、AWX、Nextcloud は使わない。

## 推奨(未確定)

- Traefik を3ノードすべてに置き、`externalTrafficPolicy: Local` にする。VIPを持つノードに必ず Traefik がいて、クライアントの実IPも保たれる。
- 3台を、別々の Proxmox ノードに置く。
- k3s01 を先に単独で構築する場合([network.md](network.md) の移行)は、最初から次のようにする。
  - 組み込み etcd を有効にして(`cluster-init`)、k3s02・k3s03 を後から参加させられるようにする。
  - API の証明書に `172.20.21.6` を含め(`tls-san`)、接続先は最初から API の VIP にする。
  - Longhorn の複製数は、ノードが1台の間は1にし、2台目が参加したら2に上げる。
- k3s 標準の local-storage(local-path)を無効にし、Longhorn を既定の StorageClass にする。ノード内だけに残る PVC が意図せず作られ、別ノードで復帰できなくなるのを防ぐ。

## 決定済み: ノードのネットワーク経路(案A)

k3s ノードのVMは、VLAN21 の1NIC(NIC1側の `vmbr`)だけにつなぐ。NIC2 はホスト専用にする。

### 通信の流れ

```text
LAN クライアント
  → ルータ(VLAN間ルーティング)
  → 172.20.21.5(MetalLB が ARP に応答するノード)
  → Traefik
  → ① クラスタ内サービス: Pod へ(別ノードなら flannel の VXLAN)
  → ② LAN内サービス(Proxmox・TrueNAS・PBS): デフォルトルートからルータへ → 実IP

公開アプリ(Cloudflare Tunnel)
  インターネット → Cloudflare → cloudflared Pod(クラスタから外向きに接続)
  → Traefik の ClusterIP → Pod        (172.20.21.5 を通らない)

kubectl・Ansible
  開発VM(VLAN22) → ルータ → 172.20.21.6:6443(kube-vip のリーダーノード)
```

### NICの扱い

| | 案A: VLAN21 のみ(NIC1) | 案B: VLAN21 + VLAN31(NIC1 + NIC2) |
| --- | --- | --- |
| 設定 | インターフェースが1つで単純 | `node-ip`・flannel のインターフェース・`tls-san`・kube-vip/MetalLB のインターフェースを分けて指定する |
| 帯域 | NIC1(1GbE)を Ingress・Longhorn の複製・リビルドで共有する | ノード間通信を、専用の1GbEへ逃がせる |
| 分離 | k3s の VM は NIC2 に触れない(NIC2 はホスト専用) | k3s の VM が NIC2 側のL2に載る。スイッチがVLAN非対応なので、分離はホストの設定だけ |
| Longhorn のバックアップ(→TrueNAS) | VLAN21 → ルータ → VLAN23 | NIC2 経由で直接 |

案Aは、複雑さと分離の面で有利。pve02・pve03 の NIC2 は USB LAN で、etcd や Longhorn の通信を載せると、リンクが落ちたときにノードがクラスタから外れる。帯域の不足は、実際に計測してから案Bまたは Longhorn の専用ストレージネットワークで補う。

### 確認が要る事項

- ルータ(ER605)が、VIP の切り替え時のGratuitous ARP を受け付け、ARPテーブルを更新するか。実機でフェイルオーバーを試す。
- VLAN をまたぐ通信(Ingress、Traefik から LAN内サービスへのプロキシ、Longhorn のバックアップ)は、ルータを通る。ER605 のルーティング性能とフィルタ設定が、その実効帯域の上限になる。同じ VLAN21 の中のノード間通信(etcd・flannel・Longhorn の複製)は、SWHUB が中継し、ルータを通らない。
- USB LAN のチップ型番([hardware.md](hardware.md))。
- Longhorn のリビルド中の Ingress への影響(同時リビルド数を制限する)。
- ノード停止時に、Longhorn のボリュームを持つ Pod が別ノードで復帰するか、復帰までの時間。Longhorn のノード停止時の Pod 削除ポリシーを設定したうえで、k3s の VM を止めて計測する。

## 未決

- k3s01 の仮想ディスク(k3s02・k3s03 と同じく1本にするか、Longhorn 用に別のディスクを足すか)。
- k3s02・k3s03 の仮想CPUのコア数と仮想ディスクのサイズ(pve02・pve03 は 4C/8T で、OS と Longhorn が同居する 1TB の SSD)。
- 3台の k3s を置く Proxmox ノード([hardware.md](hardware.md) の配置案を参照)。
- Longhorn の容量の最終値。
- NASを構築するまでの、データ保護の暫定策。
