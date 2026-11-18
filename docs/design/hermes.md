# Hermes Agent 設計

Hermes Agent の VM(`vm_hermes`)の設計。ネットワークは [network.md](network.md)、ノードの構成は [hardware.md](hardware.md)、VM の層は [pve.md](pve.md)。

## 決定済み

### インスタンス

- Hermes Agent の VM を8台置く。組織の名称・役割・関係は Hermes 側で管理し、このリポジトリには記録しない。
- 組織同士の関係(やり取りの方式、互いをどこまで信用するか、相互の監視)は、Hermes が自分で設計する。Ansible と、このリポジトリの設計では決めない。
- Hermes の VM には、専用の VLAN13(`172.16.13.0/24`。[network.md](network.md))を与える。ブリッジは、配置先のノードの LAN 側の NIC の VLAN13(pve02・pve03 は `vmbr113`、pve01 は `vmbr013`。ホストは、この VLAN に IP を持たない)。ほかの VLAN との分離は、VM の外(OPNsense。[network.md](network.md))で行う。同じ VLAN の中の Hermes 同士の通信は、インフラの側では絞らない。
- ノードは pve02(hermes01〜hermes03)と pve01(hermes04〜hermes07)と pve03(hermes08)。配置はインベントリの `node` に書く([hardware.md](hardware.md))。
- ホスト名は番号で `hermes01`〜`hermes08`(VLAN13 の ID 1〜8)。VM の説明欄に組織名を宣言しない。

### VM のサイズ

- VM のサイズは、Hermes の現在の使い方に合わせてインベントリで管理する(`inventory/group_vars/hermes.yml` が既定、`inventory/hosts/13_hermes.yml` が個体差)。組織名・担当・利用目的は VM に固定して記録しない。
- メモリは pve02 に12GiB(3台)、pve01 に28GiB(4台)、pve03 に4GiB(1台)。pve02 は、k3s02 と Proxmox 本体が使う残り(約17GiB)に収まる。pve03 は、k3s03(12GiB)と並べても 32GB に収まる。VM の中身が似ているため、Proxmox の KSM が同じ内容のメモリを共有し、その分の余裕が生まれる。各ノードのメモリの使用量を見る。足りない分は ZRAM で補い、実際に使ってから見直す。Hermes の設計のプロジェクトから、足りないと伝えられたときも見直す。
- CPU の種類は `host`。VM の中で KVM を使うため(Android エミュレータなどのコンテナに `/dev/kvm` を渡す)。`hermes` を `kvm` グループに入れる(`hermes_groups`)。cloud イメージのカーネルでも、VM の中に `/dev/kvm` がある。CPU の違うノードへは移せない(pve01・pve02・pve03 は CPU が違う)ため、Hermes の VM はノード間で移さない。置き場所を変えるときは、作り直す。
- ディスクは、配置先のノードの `ssd03` に置く。pve03 には `ssd03` が無いため、pve03 の Hermes は `ssd02` に置く。

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
- hermes06 の管理画面(9120番)を、`hermes.<lab_domain>` で LAN に公開する(k3s の Traefik の `k3s_lan_proxy`。Cloudflare Tunnel には載せない)。ログインは Hermes 側の OIDC で、Authentik に OIDC クライアント `hermes` を置く。シークレットは `vault/hermes.yml` で決め、Hermes 側の設定にも同じ値を入れる。管理画面を動かし、9120番で VM の外から受けるようにするのは、Hermes の側(状態)。
  - Hermes のコールバックのパスは Hermes の側で決まるため、Authentik は `https://hermes.<lab_domain>/` の下のパスをすべて許可する(正規表現)。パスが決まったら、完全一致に絞る。
  - 必要な通信は、k3s の全ノード(VLAN12)から `172.16.13.6:9120` と、hermes06 から Authentik(`172.16.12.5:443`)。VLAN 間の FW ポリシー([network.md](network.md) の未決)で、この2つを通す。
  - Hermes は k3s のアプリではないため、[k3s.md](k3s.md) の緊急用のユーザーの規則の対象外。ログインの方法は Hermes 側の状態。
- VM に入れるのは、上の表で Ansible が持つもの(共通のパッケージ、ZRAM、QEMU Guest Agent、Docker、Hermes)だけで、すべての Hermes VM でそろえる。ブラウザの自動操作(Chromium)、Computer Use、Android エミュレータなどの道具は VM に入れず(`hermes_skip_browser`・`hermes_skip_computer_use`)、要るときは Hermes がコンテナで動かす。ホームの中は Hermes のものなので、Ansible はこれを強制しない(Hermes の側で守る)。

### ユーザーと権限

- Hermes は、専用のユーザー(`hermes`)で動かす。このユーザーには sudo を渡さない(誤って OS の側を書き換えるのを防ぐため)。
- Ansible は、cloud イメージが作る `debian`(sudo できる)で接続する。`debian` に入れる鍵は、ラボの鍵(`pve_vm_ssh_pubkeys`。秘密鍵は vault にだけある)だけにする。
- `hermes` に入れる鍵は、別のリスト(`hermes_ssh_pubkeys`)にする。Hermes の設計のエージェントは、このユーザーで入って Hermes を設定する。`debian` と同じリストにすると、`hermes` に入れる者が `debian`(sudo)にも入れてしまうため。Ansible は `debian` から sudo で `hermes` に切り替えるので、`hermes` にラボの鍵は要らない。
  - 鍵は、Hermes の設計のエージェント専用の鍵ペアにする(手元の鍵と分け、取り消しやすくする)。
  - 登録は `hermes` 自身の権限で行う。Hermes は、自分で鍵を足せる。消した鍵は、次に playbook を流すと戻る。
- `hermes` のユーザー単位の systemd は、ログアウトしたあとも動かし続ける(linger)。常駐のサービスは Hermes が自分で作り、sudo なしで再起動できる。

### コンテナ

- コンテナは Docker を使う。Hermes の隔離環境が Docker を前提に作られているため(Podman は、対応するとあるだけで、root を使わない場合の記述が無い)。
- 用途は、Hermes がコマンドを実行する隔離環境(サンドボックス)と、Hermes が自分で作る小道具。
- Debian のパッケージで入れる(`docker compose` を含む)。
- `hermes` を `docker` グループに入れ、Docker を自由に使わせる(`hermes_groups`)。`docker` グループのユーザーは、ホストのファイルをコンテナにマウントでき、その VM の root と同じことができる。Hermes VM ごとに分けているので、これを認め、次の前提に立つ。
  - 隔離の境界は VM にする。VM の中は、その VM を使う Hermes のものとして扱う。ラボは、Hermes の VLAN とほかの VLAN との間の通信の制限で守る([network.md](network.md) の未決)。Hermes は、その VLAN の中で IP や MAC を偽れるため、VLAN の中の送信元の IP を、利用者の識別には使わない。
  - 「ホームの外は Ansible が再現する」は、導入した時点の状態を指す。Hermes は、Docker を通せばホームの外も書き換えられる。sudo を渡さないのは、誤って OS を書き換えるのを防ぐためで、権限の境界にはならない。
  - VM の中に、ラボの秘密情報(vault の中身、ほかの機器の認証情報)を置かない。置くのは、その VM を使う Hermes が自分で使う認証情報だけにする。

### Nextcloud との接続

- Hermes Agent は、Authentik のユーザー `HermesAgent` で、MCP for Cloud(Nextcloud のアプリ `mcp`)から Nextcloud を操作する。ほかの人と同じく Authentik の SSO(`user_oidc`)で作る Nextcloud のユーザーにし、Nextcloud のローカルのユーザーは置かない(ほかのアプリへ OIDC で広げるときも、アカウントを Authentik の1か所で管理するため)。Nextcloud のユーザー ID は `user_oidc` が作るハッシュになる。ユーザーとグループの所属は Authentik の画面で設定する(状態)。
- `HermesAgent` は Authentik のグループ `services` にだけ入れ、`admins` には入れない(`admins` は Authentik の superuser で、認証プロキシで守る画面と各アプリの管理者の権限を持つため)。`services` は Hermes Agent が自動で管理するためのグループで、認証プロキシで守る画面(`authentik_proxy_access_groups`。Longhorn・CLIProxyAPI・AM・APIM のコンソール)と LiteLLM の管理者(`litellm_admin_groups`)に入れる(宣言)。ほかに Authentik で結びつけるのは Nextcloud のアプリケーション(状態)。緊急用の `admin` は渡さず、Nextcloud の `admin` グループにも入れない(Nextcloud の管理者は、アプリを入れて k3s の中の Nextcloud の Pod でコードを動かせるため)。
- Authentik のログインのパスワードは機械的に作った値で、`vault/nextcloud_hermes.yml` に置き、Hermes には渡さない。最初のログインで登録する MFA(TOTP)はオーナーが持つ。Nextcloud のユーザーを作るとき(最初のログイン)と、アプリパスワードを作り直すとき以外は、Authentik のログインを使わない。
- 認証は、`HermesAgent` のアプリパスワードでの Basic 認証にする(Nextcloud はクライアントにアプリパスワードだけを許す。[k3s.md](k3s.md))。SSO のユーザーはログインのパスワードを Nextcloud に持たないため、Authentik のパスワードを変えてもアプリパスワードは無効にならない。`<Nextcloud のユーザー ID>:<アプリパスワード>` を base64 にした値は、Hermes Agent が使う認証情報として、Hermes の側の MCP の設定に入れる(「コンテナ」の、VM に置いてよい認証情報)。控えは `vault/nextcloud_hermes.yml` に、base64 にした値とアプリパスワードそのものの両方を置き(作り直すときは両方を更新する)、どの playbook も読まない。漏れたときは、アプリパスワードを取り消して作り直す。
- MCP for Cloud の権限は、すべての操作を許す(削除・共有・公開リンク・Talk の会話の作成を含む)。サーバーのログは管理者用のため付けない。Nextcloud の中での権限は普通のユーザーと同じで、管理させるもの(Deck のボード、カレンダー、フォルダなど)は人が `HermesAgent` に共有する。コレクティブは、`services` のグループを普通のメンバーとして足す。
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

- インフラ(このリポジトリ、Proxmox、k3s)を操作させる権限と隔離の境界をどう設計するか。
- Hermes にインフラを操作させるとき、何を見て、何を操作してよいか(例: OPNsense のログや設定、ほかの機器)。「VM の中に、ラボの秘密情報(vault の中身、ほかの機器の認証情報)を置かない」という前提と、どう両立させるか。上の権限と隔離の境界の設計とも関わる。
- Hermes VM から Nextcloud へ届く経路(LAN 用の入口の `172.16.12.5` を VLAN 間の FW で通すか、Cloudflare Tunnel か)。
- VM が動いていることの監視(Hermes 同士の監視とは別に、インフラの側で持つか)。
- LLM の接続先(LiteLLM の `hermes_llm`。[k3s.md](k3s.md))と、仮想キーと予算を Hermes VM ごとに分けるか。VM に置いた鍵は、その VM を使う Hermes が自由に使えるものとして扱う(共通の鍵を置くと、すべての VM で同じ鍵を使う)。
- OS のパッケージの更新。VM を作り直さないため、更新の方法(自動更新か、playbook か)を決める。
- Hermes の状態の保護。PBS をつなぐまでの、スナップショットの取り方。
- Hermes の VLAN と、ほかの VLAN・インターネットとの間の通信の制限([network.md](network.md) の未決)。
