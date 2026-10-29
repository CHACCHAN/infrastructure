# Hermes Agent 設計

Hermes Agent の VM(`vm_hermes`)の設計。ネットワークは [network.md](network.md)、ノードの構成は [hardware.md](hardware.md)、VM の層は [pve.md](pve.md)。

## 決定済み

### インスタンス

- 組織ごとに VM を1つ割り当てる。インスタンス1つを1つの会社に見立て、全体をグループ会社に見立てる。インスタンス同士で監視や問い合わせをさせる。
- 組織同士の関係(やり取りの方式、互いをどこまで信用するか、相互の監視)は、Hermes が自分で設計する。Ansible と、このリポジトリの設計では決めない。
- Hermes の VM には、専用の VLAN13(`172.16.13.0/24`。[network.md](network.md))を与える。ブリッジは、配置先のノードの LAN 側の NIC の VLAN13(pve02 は `vmbr113`、pve01 は `vmbr013`。ホストは、この VLAN に IP を持たない)。ほかの VLAN との分離は、VM の外(OPNsense。[network.md](network.md))で行う。同じ VLAN の中の Hermes 同士の通信は、インフラの側では絞らない。
- ノードは pve02(受付・本社・ライン子会社)と pve01(ディスコード子会社・秘書会社・社内サービス会社・Nextcloud Hub の管理)。配置はインベントリの `node` に書く([hardware.md](hardware.md))。
- 組織は7つ: 受付・本社・ライン子会社・ディスコード子会社・秘書会社・社内サービス会社・Nextcloud Hub の管理。組織の設計(役割や関係)は、Hermes の設計のプロジェクトが持つ。
- ホスト名は番号で `hermes01`〜`hermes07`(VLAN13 の ID 1〜7)。組織の名前は、VM の説明欄(`pve_vm_description`)に書く。組織の改名や再編で、VM の名前を変えないため。

### VM のサイズ

- 役割ごとに決める。値はインベントリ(`inventory/group_vars/hermes.yml` が既定、`inventory/hosts/13_hermes.yml` が差分)。
  - 既定は、Hermes と、Hermes がコンテナで動かす隔離環境や道具(ブラウザなど)に合わせる。本社・ライン子会社・ディスコード子会社・秘書会社・Nextcloud Hub の管理は、既定のまま。
  - 受付は、依頼を通すだけなので CPU とディスクを小さくする。メモリは小さくしない(Hermes のインストーラは、1GiB では終わらない)。
  - 社内サービス会社は、Android エミュレータをコンテナで動かすため大きくする。
- メモリは pve02 に12GiB(3台)、pve01 に28GiB(4台)。pve02 は、k3s02 と Proxmox 本体が使う残り(約17GiB)に収まる。VM の中身が似ているため、Proxmox の KSM が同じ内容のメモリを共有し、その分の余裕が生まれる。各ノードのメモリの使用量を見る。足りない分は ZRAM で補い、実際に使ってから見直す。Hermes の設計のプロジェクトから、足りないと伝えられたときも見直す。
- CPU の種類は `host`。VM の中で KVM を使うため(Android エミュレータなどのコンテナに `/dev/kvm` を渡す)。`hermes` を `kvm` グループに入れる(`hermes_groups`)。cloud イメージのカーネルでも、VM の中に `/dev/kvm` がある。CPU の違うノードへは移せない(pve01 と pve02 は CPU が違う)ため、Hermes の VM はノード間で移さない。置き場所を変えるときは、作り直す。
- ディスクは、配置先のノードの `ssd03` に置く。

### Ansible が再現する範囲

Hermes には、自分で成長させる(スキルやメモリだけでなく、Hermes 本体の更新も含む)。Ansible が再現するのは、未設定の Hermes が入った VM までにする。

| 持ち主 | 対象 |
| --- | --- |
| Ansible(毎回そろえる) | VM、Debian 13(cloud-init)、共通のパッケージ、ZRAM、QEMU Guest Agent、Docker、Hermes を動かすユーザー |
| Ansible(無いときだけ行う) | 公式のインストーラでの Hermes の導入 |
| Hermes | Hermes 本体とその版、モデルとプロバイダーの認証情報、チャネル、常駐の設定、スキル、メモリ、セッション、コンテナ |

- Ansible が管理する範囲の境界は、Hermes を動かすユーザーのホームディレクトリにする。ホームの外は Ansible が導入した時点の状態を再現し、ホームの中は Hermes のもので、Ansible は管理しない。Hermes の本体も、ホームの中(`~/.hermes/`)に入る。隔離の境界は VM(「コンテナ」を参照)。
- Ansible がホームの中に触るのは、導入(まだ入っていないときだけ)と、SSH の公開鍵の登録(「推奨(未確定)」を参照)だけ。ホームの中へは、root では書き込まない(Hermes のユーザーが、書き込み先を差し替えられるため)。
- Hermes の版は固定しない。導入した時点の最新が入り、そのあとは Hermes が自分で更新する。Ansible は、版を引き戻さない。[conventions.md](../conventions.md) の「バージョン管理」の例外。インストーラも版を固定できないため、チェックサムは照合せず、HTTPS で取得したものをそのまま実行する。
- 導入済みの Hermes が動くかどうかは、Ansible では確かめない(入れた直後だけ確かめる)。自己更新で壊れても、playbook は失敗しない。
- モデル、チャネル、常駐、管理画面の設定は、Ansible では行わない。Hermes の側で設定する。
- 受付(hermes01)の管理画面(9119番)を、`hermes.<lab_domain>` で LAN に公開する(k3s の Traefik の `k3s_lan_proxy`。Cloudflare Tunnel には載せない)。ログインは Hermes 側の OIDC で、Authentik に OIDC クライアント `hermes` を置く。シークレットは `vault/hermes.yml` で決め、Hermes 側の設定にも同じ値を入れる。管理画面を動かし、9119番で VM の外から受けるようにするのは、Hermes の側(状態)。
  - Hermes のコールバックのパスは Hermes の側で決まるため、Authentik は `https://hermes.<lab_domain>/` の下のパスをすべて許可する(正規表現)。パスが決まったら、完全一致に絞る。
  - 必要な通信は、k3s の全ノード(VLAN12)から `172.16.13.1:9119` と、hermes01 から Authentik(`172.16.12.5:443`)。VLAN 間の FW ポリシー([network.md](network.md) の未決)で、この2つを通す。
  - Hermes は k3s のアプリではないため、[k3s.md](k3s.md) の緊急用のユーザーの規則の対象外。ログインの方法は Hermes 側の状態。
- VM に入れるのは、上の表で Ansible が持つもの(共通のパッケージ、ZRAM、QEMU Guest Agent、Docker、Hermes)だけで、すべての組織でそろえる。ブラウザの自動操作(Chromium)、Computer Use、Android エミュレータなどの道具は VM に入れず(`hermes_skip_browser`・`hermes_skip_computer_use`)、要るときは Hermes がコンテナで動かす。ホームの中は Hermes のものなので、Ansible はこれを強制しない(Hermes の側で守る)。

### ユーザーと権限

- Hermes は、専用のユーザー(`hermes`)で動かす。このユーザーには sudo を渡さない(誤って OS の側を書き換えるのを防ぐため)。
- Ansible は、cloud イメージが作る `debian`(sudo できる)で接続する。`debian` に入れる鍵は、ラボの鍵(`pve_vm_ssh_pubkeys`。秘密鍵は vault にだけある)だけにする。
- `hermes` に入れる鍵は、別のリスト(`hermes_ssh_pubkeys`)にする。Hermes の設計のエージェントは、このユーザーで入って Hermes を設定する。`debian` と同じリストにすると、`hermes` に入れる者が `debian`(sudo)にも入れてしまうため。Ansible は `debian` から sudo で `hermes` に切り替えるので、`hermes` にラボの鍵は要らない。
  - 鍵は、Hermes の設計のエージェント専用の鍵ペアにする(手元の鍵と分け、取り消しやすくする)。
  - 登録は `hermes` 自身の権限で行う。Hermes は、自分で鍵を足せる。消した鍵は、次に playbook を流すと戻る。
- `hermes` のユーザー単位の systemd は、ログアウトしたあとも動かし続ける(linger)。常駐のサービスは Hermes が自分で作り、sudo なしで再起動できる。

### コンテナ

- コンテナは Docker を使う。Hermes の隔離環境が Docker を前提に作られているため(Podman は、対応するとあるだけで、root を使わない場合の記述が無い)。
- 用途は、Hermes がコマンドを実行する隔離環境(サンドボックス)と、組織が自分で作る小道具。
- Debian のパッケージで入れる(`docker compose` を含む)。
- `hermes` を `docker` グループに入れ、Docker を自由に使わせる(`hermes_groups`)。`docker` グループのユーザーは、ホストのファイルをコンテナにマウントでき、その VM の root と同じことができる。組織ごとに VM を分けているので、これを認め、次の前提に立つ。
  - 隔離の境界は VM にする。VM の中は、その組織のものとして扱う。ラボは、Hermes の VLAN とほかの VLAN との間の通信の制限で守る([network.md](network.md) の未決)。Hermes は、その VLAN の中で IP や MAC を偽れるため、VLAN の中の送信元の IP を、組織の識別には使わない。
  - 「ホームの外は Ansible が再現する」は、導入した時点の状態を指す。Hermes は、Docker を通せばホームの外も書き換えられる。sudo を渡さないのは、誤って OS を書き換えるのを防ぐためで、権限の境界にはならない。
  - VM の中に、ラボの秘密情報(vault の中身、ほかの機器の認証情報)を置かない。置くのは、その組織が自分で使う認証情報だけにする。

### Nextcloud Hub の管理(hermes07)

- Nextcloud の専用のユーザー `hermes-agent`(表示名 `HermesAgent`)で、MCP for Cloud(Nextcloud のアプリ `mcp`)から Nextcloud を操作する。Authentik の SSO を使わない、Nextcloud のローカルのユーザーにする([k3s.md](k3s.md) の SSO の例外)。緊急用の `admin` は渡さず、`admin` グループにも入れない(Nextcloud の管理者は、アプリを入れて k3s の中の Nextcloud の Pod でコードを動かせるため)。
- 認証は、`hermes-agent` のアプリパスワードでの Basic 認証にする(Nextcloud はクライアントにアプリパスワードだけを許す。[k3s.md](k3s.md))。`hermes-agent:<アプリパスワード>` を base64 にした値は、hermes07 の組織が自分で使う認証情報として、Hermes の側の MCP の設定に入れる(「コンテナ」の、VM に置いてよい認証情報)。控えは `vault/nextcloud_hermes.yml` に置き、どの playbook も読まない。ログインのパスワードも同じファイルに置き、Hermes には渡さない。漏れたときは、アプリパスワードを取り消して作り直す。
- MCP for Cloud の権限は、すべての操作を許す(削除・共有・公開リンク・Talk の会話の作成を含む)。サーバーのログは管理者用のため付けない。Nextcloud の中での権限は普通のユーザーと同じで、管理させるもの(Deck のボード、カレンダー、フォルダなど)は人が `hermes-agent` に共有する。
- ユーザー・アプリパスワード・MCP for Cloud の導入と権限は、Nextcloud の状態で、Ansible では管理しない。

### OS

- Debian 13 の cloud イメージ(k3s ノードと同じテンプレート)。
- ZRAM の swap を使う。k3s ノードは使わない([k3s.md](k3s.md))が、Hermes の VM は、プロセスがそのまま swap を使える。

## 推奨(未確定)

実装の既定値にしているが、オーナーが決めたものではない。

- ZRAM の swap の大きさは、メモリの 50%、圧縮は zstd。

## 確認が要る事項

- Hermes の管理画面のログイン(OIDC)が有効になっていること。プロキシは認証を掛けないため、管理画面が認証なしで動くと、`hermes.<lab_domain>` から LAN にそのまま出る。
- Debian のパッケージの Docker(26 系)で、Hermes の隔離環境が動くか。動かなければ、Docker の公式のリポジトリから入れる。
- cloud イメージのカーネルで ZRAM が動くか。`vm` ロールが、swap が有効になったことを確かめる。
- 決めたメモリで足りるか。導入して使ったあとの使用量を見る。
- Hermes の本体(インストーラや新しい版)が OS のパッケージを要求したとき。再現できるよう、`hermes_packages` に足して playbook を流す(Hermes が Docker を通して自分で入れたものは、Ansible からは再現されない)。道具(ブラウザなど)が使うパッケージは足さず、道具のコンテナに入れる。

## 未決

- インフラ(このリポジトリ、Proxmox、k3s)を操作させる組織を作るか。
- Nextcloud Hub の管理の組織(hermes07)が Nextcloud へ届く経路(LAN 用の入口の `172.16.12.5` を VLAN 間の FW で通すか、Cloudflare Tunnel か)。
- VM が動いていることの監視(Hermes 同士の監視とは別に、インフラの側で持つか)。
- LLM の接続先(LiteLLM の `hermes_llm`。[k3s.md](k3s.md))と、組織ごとに仮想キーと予算を分けるか。VM に置いた鍵は、その組織が自由に使えるものとして扱うことになる(共通の鍵を置くと、全組織に同じ鍵を渡すことになる)。
- OS のパッケージの更新。VM を作り直さないため、更新の方法(自動更新か、playbook か)を決める。
- Hermes の状態の保護。PBS をつなぐまでの、スナップショットの取り方。
- Hermes の VLAN と、ほかの VLAN・インターネットとの間の通信の制限([network.md](network.md) の未決)。
