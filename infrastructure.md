# インフラストラクチャ

## ネットワーク
```mermaid
flowchart TB
  WAN["WAN(インターネット)"]

  subgraph gateway["上流層(LAN)"]
    ROUTER["ルータ"]
  end

  subgraph switches["スイッチングハブ(物理2台)"]
    SW1["スイッチングハブ1<br>ルータへの上流あり<br>VLAN11 / VLAN12 を収容"]
    SW2["スイッチングハブ2<br>上流なし(クラスタ間専用の閉じた回路)"]
  end

  subgraph physical["物理層(各PVEノード)"]
    NIC1["物理NIC1<br>→ スイッチングハブ1"]
    NIC2["物理NIC2<br>→ スイッチングハブ2"]
  end

  subgraph home["自宅ルータ直結(スイッチングハブ1経由)"]
    vmbr0["vmbr0 (Proxmox)<br>172.16.11.0/24 (VLAN11)"]
    vmbr2["vmbr2 (k3s)<br>172.16.12.0/24 (VLAN12)"]
  end

  subgraph dedicated["占有回線(スイッチングハブ2経由)"]
    vmbr1["vmbr1 (Proxmox)<br>10.10.10.0/24"]
    vmbr3["vmbr3 (k3s)<br>10.10.20.0/24 (VLAN12)"]
  end

  subgraph pve_group["Proxmox Cluster"]
    pve01["pve01<br>vmbr0: 172.16.11.11<br>vmbr1: 10.10.10.11"]
    pve02["pve02<br>vmbr0: 172.16.11.12<br>vmbr1: 10.10.10.12"]
    pve03["pve03<br>vmbr0: 172.16.11.13<br>vmbr1: 10.10.10.13"]
    pve04["pve04<br>vmbr0: 172.16.11.14<br>vmbr1: 10.10.10.14"]
    pve05["pve05<br>vmbr0: 172.16.11.15<br>vmbr1: 10.10.10.15"]
    pve06["pve06<br>vmbr0: 172.16.11.16<br>vmbr1: 10.10.10.16"]
    pve07["pve07<br>vmbr0: 172.16.11.17<br>vmbr1: 10.10.10.17"]
    pve08["pve08<br>vmbr0: 172.16.11.18<br>vmbr1: 10.10.10.18"]
    pve09["pve09<br>vmbr0: 172.16.11.19<br>vmbr1: 10.10.10.19"]
    pve10["pve10<br>vmbr0: 172.16.11.20<br>vmbr1: 10.10.10.20"]

    pve01 ~~~ pve03 ~~~ pve05 ~~~ pve07 ~~~ pve09
    pve02 ~~~ pve04 ~~~ pve06 ~~~ pve08 ~~~ pve10
  end

  subgraph vm_services["Proxmox VM: サービス"]
    vm_service01["Authentik<br>vmbr0: 172.16.11.2"]
    vm_service02["TechnitiumDNS<br>vmbr0: 172.16.11.3"]
    vm_service03["Cloudflare-DDNS-UI<br>vmbr0: 172.16.11.4"]
    vm_service04["WG-Easy<br>vmbr0: 172.16.11.5"]
    vm_service05["Coolify<br>vmbr0: 172.16.11.6"]
    vm_service06["Proxmox Backup Server<br>vmbr0: 172.16.11.7<br>vmbr1: 10.10.10.7"]
    vm_service07["Rancher<br>vmbr0: 172.16.11.8"]
    vm_service08["Portainer<br>vmbr0: 172.16.11.9"]
    vm_service09["Hermes Agent<br>vmbr0: 172.16.11.31"]

    vm_service01 ~~~ vm_service04 ~~~ vm_service07
    vm_service02 ~~~ vm_service05 ~~~ vm_service08
    vm_service03 ~~~ vm_service06 ~~~ vm_service09
  end

  subgraph vm_developments["Proxmox VM: 開発専用"]
    vm_development01["yuya-dev<br>vmbr0: 172.16.11.21<br>vmbr3: (IPなし)"]
    vm_development02["shun-dev<br>vmbr0: 172.16.11.22"]
  end

  subgraph k3s_cluster["Proxmox VM: Kubernetes Cluster (k3s)"]
    k3s01["k3s-master01<br>vmbr2: 172.16.12.11<br>vmbr3: 10.10.20.11"]
    k3s02["k3s-worker01<br>vmbr2: 172.16.12.15<br>vmbr3: 10.10.20.15"]
    k3s03["k3s-worker02<br>vmbr2: 172.16.12.16<br>vmbr3: 10.10.20.16"]
    k3s04["k3s-worker03<br>vmbr2: 172.16.12.17<br>vmbr3: 10.10.20.17"]
    k3s05["k3s-worker04<br>vmbr2: 172.16.12.18<br>vmbr3: 10.10.20.18"]

    k3s01 ~~~ k3s04
    k3s02 ~~~ k3s05
  end

  WAN --> ROUTER
  ROUTER --> SW1
  SW1 --> NIC1
  SW2 --> NIC2
  NIC1 --> vmbr0 & vmbr2
  NIC2 --> vmbr1 & vmbr3
  vmbr0 & vmbr1 & vmbr2 & vmbr3 --> pve_group
  pve_group --> vm_services & vm_developments & k3s_cluster
```

- 各PVEノードの物理NIC 2枚は、**別々のスイッチングハブ**に挿さっている。NIC1側のハブだけがルータへ上がり、NIC2側のハブは上流を持たないクラスタ間専用の閉じた回路
- したがって外部と通信できるのは NIC1 が収容する `vmbr0` / `vmbr2`(ともに自宅ルータ直結・VLANタグ付き)だけ。`vmbr1` / `vmbr3` はクラスタ内部専用で、デフォルトゲートウェイを持たない
- k3s APIサーバー(`k8s_api_server: https://10.10.20.11:6443`)やPBSのバックアップ転送は、この占有回線側を通る

## 公開経路(Traefik)

すべてのHTTP(S)公開はk3s同梱のTraefik v3に集約される。**インターネットへ出るのはCloudflare Tunnel経由のホスト(auth. / *.web. / hermes.)だけ**で、残りはLAN内(WireGuard接続中の端末を含む)からのみ到達できる。

```mermaid
flowchart TB
  C_EXT["外部クライアント<br>(インターネット)"]
  C_LAN["LAN内クライアント<br>VLAN11 / VLAN12"]

  subgraph cloudflare["Cloudflare"]
    CF_DNS["Cloudflare DNS<br>cc-chacchan.com"]
    CF_TUNNEL["Cloudflare Tunnel<br>経路表(ホスト名→オリジン)はCloudflare側<br>このリポジトリでは管理しない"]
  end

  subgraph edge["宅内エッジ"]
    ROUTER["ルータ<br>外部へ開けるのは UDP 51820 のみ"]
    WG["wg-easy (VM) 172.16.11.5<br>WireGuard終端 / Authentik OIDC<br>配布DNS: 172.16.11.3"]
    DNS["TechnitiumDNS (VM) 172.16.11.3<br>*.cc-chacchan.com を内部解決"]
  end

  subgraph entry["k3sクラスタの入口"]
    CFD["cloudflared ×2 (cloudflare ns)<br>Cloudflareへアウトバウンド接続<br>受信ポートの開放なし"]
    SLB["ServiceLB (klipper)<br>k3sノード 172.16.12.11 / .15〜.18"]
  end

  subgraph traefik["Traefik v3 (k3s同梱・kube-system / 管理対象外)"]
    EP_WEB["entrypoint: web (:80)"]
    EP_SEC["entrypoint: websecure (:443)<br>TLS: cc-chacchan-wildcard-tls<br>cert-manager + Let's Encrypt DNS-01"]
  end

  subgraph pub["インターネット公開(entrypoints: web,websecure)"]
    H_AUTH["auth.cc-chacchan.com<br>→ Authentik 172.16.11.2:9000"]
    H_WEB["*.web.cc-chacchan.com<br>→ Coolify 172.16.11.6:80<br>(デプロイしたアプリ)"]
    H_HERMES["hermes.cc-chacchan.com<br>→ Hermes 172.16.11.31:9119(管理UI)<br>/line/* → 172.16.11.31:8646(LINE webhook)<br>認証はHermes側のAuthentik OIDC"]
  end

  subgraph lan_app["LAN内のみ: クラスタ内アプリ(Ingress→Service→Pod)"]
    A_APPS["ansible.(AWX) / homarr.<br>pgadmin. / nextcloud. / guacamole. / ai.(OpenWebUI)<br>認証はAuthentik OIDC(アプリ側で実装)"]
  end

  subgraph lan_ext["LAN内のみ: クラスタ外サービス(k8s_external)"]
    E_FWD["ddns. → 172.16.11.4:8080<br>Authentik forwardAuth Middleware を通す"]
    E_NET["dns. → 172.16.11.3:5380<br>doh. → 172.16.11.3:8053<br>wgui. → 172.16.11.5:51821<br>coolify. → 172.16.11.6:80<br>rancher. → 172.16.11.8:80<br>portainer. → 172.16.11.9:9000"]
    E_INFRA["pve01.〜pve10. → 172.16.11.11〜.20:8006<br>pbs. → 172.16.11.7:8007<br>nas. → 172.16.11.10:443<br>自己署名HTTPS(insecureSkipVerify)"]
  end

  C_EXT -->|"HTTPS"| CF_DNS
  C_EXT -->|"WireGuard UDP 51820<br>cc-chacchan.com"| ROUTER
  CF_DNS --> CF_TUNNEL
  CF_TUNNEL -->|"HTTP :80"| CFD
  CFD --> EP_WEB
  ROUTER --> WG
  WG -->|"接続後はLAN内と同じ経路"| DNS
  C_LAN --> DNS
  DNS -->|"解決結果 172.16.12.x:443 へ"| SLB
  SLB --> EP_SEC
  EP_WEB --> pub
  EP_SEC --> pub & lan_app & lan_ext
```

### 公開範囲の決めかた

- 公開範囲は Ingress の `traefik.ingress.kubernetes.io/router.entrypoints` で決まる。既定は `websecure` のみ = **LAN内限定**。`web,websecure` を明示したホスト名だけが、HTTP :80 で入ってくるCloudflare Tunnelから到達できる
- ルータで外部へ開けているのは WireGuard の UDP 51820 だけ。HTTP/HTTPS の受信ポートは開けていない(公開はすべて cloudflared のアウトバウンド接続経由)
- Cloudflare Tunnel の経路表はCloudflare側にあり、`roles/k8s_cloudflared` はコネクタ(Deployment/PDB)だけを収束させる。**公開ホストを増やす操作はこのリポジトリでは完結しない**
- クラスタ外サービスの単一の真実は `inventory/group_vars/all/k8s.yml` の `k8s_external_routes`。1エントリからService(セレクタなし)+EndpointSlice+Ingress+Middlewareが生成される
- WireGuardクライアントには `172.16.11.3`(TechnitiumDNS)が配布されるため、VPN接続中は LAN内クライアントとまったく同じ名前解決・同じ経路になる
