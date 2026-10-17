# ネットワーク設計

## 決定済み

### VLAN

ラボのネットワークは `172.16.0.0/16` を、VLANごとの `/24`(`172.16.<VLAN>.0/24`)に分ける。ゲートウェイは原則として各 `/24` の `.254`。VLAN間の通信はルータ(OPNsense)で制御する。VLAN は今後も足す。

| VLAN | サブネット | 用途 |
| --- | --- | --- |
| タグなし | `172.16.5.0/24` | (用途は未決) |
| 10 | `172.16.10.0/24` | Proxmox ノード |
| 11 | `172.16.11.0/24` | Private(開発専用機など) |
| 12 | `172.16.12.0/24` | k3s ノード |

基幹システム(物理PBS、TrueNAS)と Hermes Agent(AI専用)の VLAN は、まだ割り当てていない(未決)。

### ID・VMID・IP

IDひとつから、VMIDとIPを決める。

```text
VMID = VLAN × 100 + ID
IP   = 172.16.<VLAN>.<ID>
```

- ID は 1〜99 の整数で、VLANの中で一意。YAML には先頭の0を付けずに書く(`08` は文字列、`010` は8進数として読まれる)。物理機と仮想機は同じID空間を共有する(物理機にはVMIDがない)。
- 例: VLAN12 の ID 1 → VMID `1201` → `172.16.12.1`。
- ホストは、グループの `vlan`、自分の `id`、配置先の `node` だけを宣言し、VMID・IP・ゲートウェイ・VLANタグは導出する。
- 複数のNICを持つホストの VMID は、主となるNICのVLANで決める。

予約済みのID:

| VLAN | ID | 用途 |
| --- | --- | --- |
| 12 | 5 | Ingress の VIP(`172.16.12.5`) |
| 12 | 6 | k3s API の VIP(`172.16.12.6`) |

### 物理構成

- Proxmox ノードは、各ノードに 1GbE のNICがある。NIC1(LAN)・NIC2(クラスタ)は役割の名前で、物理のインターフェース(`nic0` など)との対応はノードごとに違う([hardware.md](hardware.md))。
- 構成: `WAN → OPNsense → SWHUB → Proxmox ノード(NIC1)`、`SWHUB2 → Proxmox ノード(NIC2)`。SWHUB は 802.1Q のタグVLANに対応している。SWHUB2 は NIC2 側の機器(Proxmox ノード。PBS、TrueNAS は接続したとき)だけをつなぎ、OPNsense や SWHUB にはつながない。
- NIC1: SWHUB(VLAN対応)につなぐ。Linux の VLAN サブインターフェースでVLANを分け、VLANごとに `vmbr` を作ってVMへ渡す。
- NIC2: VLAN非対応の SWHUB2 へつなぐ。PBS と TrueNAS も、接続するときは同じスイッチにつなぐ。クラスタ・バックアップ・ストレージの通信用で、ゲートウェイはなく、ルーティングしない。SWHUB2 はVLAN非対応なので、NIC2側のVLAN分離は各ホストの設定によるもので、スイッチは強制しない。
- NIC2 側は、すべてタグ付きの VLAN にする。アドレスは `10.10.<VLAN>.0/24`(`10.0.0.0/8` の中)。
- NIC2 側の Proxmox クラスタ用ネットワークは `10.10.10.0/24`(VLAN10 のタグ付き、ブリッジ `vmbr210`)。ノードの第4オクテットは、`.1` から順に振る(pve01 は `10.10.10.1`)。
- PBS は物理マシンに直接入れる(基幹システムの VLAN)。Proxmox ノードではなく、PBS 専用機にする。接続の時期は未決。
- ルータは OPNsense。WAN につながり、ラボを LAN 側に置く。VLANのタグ付け、VLAN間ルーティング、FW、NAT を担う。リモートアクセスの VPN(WireGuard)と DDNS も担う予定。TP-Link ER605 は使わない。
- NAT は1段だけにする(二重 NAT にしない)。
- リアルタイム通信は Cloudflare のサービスを使う。外部からの直接UDPの受け口は要らない。

### Proxmox クラスタ

- Proxmox の HA は使わない。k3s が自力で冗長化するため。corosync が落ちても、動作中のVMは止まらない。
- corosync は2リンクにする。第1リンクを NIC2、第2リンクを NIC1(VLAN10)にして、どちらかが落ちても knet が切り替える。
- NIC2 には、接続するときに PBS・TrueNAS もつなぐ。そのときは、バックアップの転送に帯域の上限(`bwlimit`)を設け、corosync のレイテンシを守る。

### 移行

- 旧構成からの移行は済み、旧構成は撤去した(`legacy/` は参照用のコードだけが残る)。
- TrueNAS と PBS は、接続するまで設計・実装の対象に含めない。
- 新構成は、pve01 と k3s01 だけで先に構築する。そのあとで、旧構成の物理マシンを Proxmox ノードとして参加させ、k3s02・k3s03 を作る。

### 名前解決

- 名前解決は Cloudflare の DNS を使う。
- OPNsense の DNS(Unbound)は、DNS リバインド対策でプライベート IP を返す応答を捨てる。`cc-chacchan.com` は Private Domains に登録し、この対策の対象から外す(ラボの公開ホスト名が `172.16.12.5` を返すため)。
- ルータの構成が固まってから、詳細を設計する。

### リモートアクセス・公開

- リモートアクセスは `cloudflared` を使う。
- 管理UI(Proxmox・PBS・TrueNAS)は LAN 内だけで使う。Cloudflare Tunnel には載せない。
- k3s のクラスタ内アプリのうち、Authentik・Homarr・OpenWebUI を Cloudflare Tunnel で公開する。LiteLLM と Longhorn の管理 UI は載せない。詳細と未決は [k3s.md](k3s.md)。

## 未決

- NIC2側の分割。クラスタ/バックアップ用と、ストレージ用に VLAN を分けるか(VLAN 番号も未決)。k3s ノードは NIC2 に載せない([k3s.md](k3s.md))。
- 基幹システム(PBS・TrueNAS)と Hermes Agent の VLAN 番号。
- タグなしの `172.16.5.0/24` の用途。自宅LAN(以前は `192.168.68.0/24`)がどこにあるか。
- OPNsense での VPN と DDNS の構成。
- VLAN間のFWポリシー(特にHermes帯域の隔離、ラボから自宅LANへの通信の遮断)。OPNsense のルールで行う。
- OPNsense と SWHUB のトランクが1本なので、VLAN間の通信はこの1本を通る。帯域が足りなければ、リンクアグリゲーションか L3 スイッチを検討する。
- 自宅LANからラボへの到達性。管理UIとTraefik(`172.16.12.5`)を自宅のPCから使うかどうかで決まる。
- 追加のVLAN(DMZ、テンプレート/一時用)。
- 名前解決の細部(LAN内クライアントの問い合わせ先、ノード同士の名前解決)。Cloudflare Tunnel を入れたあと、LAN から公開アプリへ直接届かせるか(OPNsense でのスプリット DNS)。
