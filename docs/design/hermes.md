# Hermes Agent 設計

Hermes Agent の VM(`vm_hermes`)の設計。ネットワークは [network.md](network.md)、ノードの構成は [hardware.md](hardware.md)、VM の層は [pve.md](pve.md)。

## 決定済み

### インスタンス

- 組織ごとに VM を1つ割り当てる。インスタンス1つを1つの会社に見立て、全体をグループ会社に見立てる。インスタンス同士で監視や問い合わせをさせる。
- 組織同士の関係(やり取りの方式、互いをどこまで信用するか、相互の監視)は、Hermes が自分で設計する。Ansible と、このリポジトリの設計では決めない。
- Hermes の VM には、専用の VLAN(番号は未決。[network.md](network.md))を与える。ほかの VLAN との分離は、VM の外(OPNsense。[network.md](network.md))で行う。同じ VLAN の中の Hermes 同士の通信は、インフラの側では絞らない。
- ノードは pve04([hardware.md](hardware.md) の配置案)。

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

### ユーザーと権限

- Hermes は、専用のユーザー(`hermes`)で動かす。このユーザーには sudo を渡さない(誤って OS の側を書き換えるのを防ぐため)。
- Ansible は、cloud イメージが作る `debian`(sudo できる)で接続する。
- `hermes` のユーザー単位の systemd は、ログアウトしたあとも動かし続ける(linger)。常駐のサービスは Hermes が自分で作り、sudo なしで再起動できる。

### コンテナ

- コンテナは Docker を使う。Hermes の隔離環境が Docker を前提に作られているため(Podman は、対応するとあるだけで、root を使わない場合の記述が無い)。
- 用途は、Hermes がコマンドを実行する隔離環境(サンドボックス)と、組織が自分で作る小道具。
- Debian のパッケージで入れる(`docker compose` を含む)。
- `hermes` を `docker` グループに入れ、Docker を自由に使わせる(`hermes_groups`)。`docker` グループのユーザーは、ホストのファイルをコンテナにマウントでき、その VM の root と同じことができる。組織ごとに VM を分けているので、これを認め、次の前提に立つ。
  - 隔離の境界は VM にする。VM の中は、その組織のものとして扱う。ラボは、Hermes の VLAN とほかの VLAN との間の通信の制限で守る([network.md](network.md) の未決)。Hermes は、その VLAN の中で IP や MAC を偽れるため、VLAN の中の送信元の IP を、組織の識別には使わない。
  - 「ホームの外は Ansible が再現する」は、導入した時点の状態を指す。Hermes は、Docker を通せばホームの外も書き換えられる。sudo を渡さないのは、誤って OS を書き換えるのを防ぐためで、権限の境界にはならない。
  - VM の中に、ラボの秘密情報(vault の中身、ほかの機器の認証情報)を置かない。置くのは、その組織が自分で使う認証情報だけにする。

### OS

- Debian 13 の cloud イメージ(k3s ノードと同じテンプレート)。
- ZRAM の swap を使う。k3s ノードは使わない([k3s.md](k3s.md))が、Hermes の VM は、プロセスがそのまま swap を使える。

## 推奨(未確定)

実装の既定値にしているが、オーナーが決めたものではない。

- `hermes` に、`pve_vm_ssh_pubkeys` の公開鍵を登録する(Hermes の初期設定を、このユーザーのログインで行うため)。登録は `hermes` 自身の権限で行う。Hermes は、自分で鍵を足せる。消した鍵は、次に playbook を流すと戻る。
- ZRAM の swap の大きさは、メモリの 50%、圧縮は zstd。
- ブラウザの自動操作(Chromium)と Computer Use は入れない(画面を持たない VM のため。`hermes_skip_browser`・`hermes_skip_computer_use`)。

## 確認が要る事項

- Debian のパッケージの Docker(26 系)で、Hermes の隔離環境が動くか。動かなければ、Docker の公式のリポジトリから入れる。
- cloud イメージのカーネルで ZRAM が動くか。`vm` ロールが、swap が有効になったことを確かめる。
- Hermes が OS のパッケージを要求したとき(新しい版が要求する場合を含む)。再現できるよう、`hermes_packages` に足して playbook を流す(Hermes が Docker を通して自分で入れたものは、Ansible からは再現されない)。

## 未決

- 組織の数と名前、VM のサイズ(pve04 のメモリは 32GB。Hermes は、導入した直後でディスクを約 2.5GB 使う。`pve_vm` の既定のディスクは 20GiB)。
- Hermes の VLAN の番号。pve04 のインベントリへの追加と、その VLAN のブリッジ・ストレージ([pve.md](pve.md))。
- インフラ(このリポジトリ、Proxmox、k3s)を操作させる組織を作るか。
- VM が動いていることの監視(Hermes 同士の監視とは別に、インフラの側で持つか)。
- LLM の接続先(LiteLLM の `hermes_llm`。[k3s.md](k3s.md))と、組織ごとに仮想キーと予算を分けるか。VM に置いた鍵は、その組織が自由に使えるものとして扱うことになる(共通の鍵を置くと、全組織に同じ鍵を渡すことになる)。
- 管理画面の公開(`k3s_lan_proxy`)と、Authentik の SSO。
- OS のパッケージの更新。VM を作り直さないため、更新の方法(自動更新か、playbook か)を決める。
- Hermes の状態の保護。PBS をつなぐまでの、スナップショットの取り方。
- Hermes の VLAN と、ほかの VLAN・インターネットとの間の通信の制限([network.md](network.md) の未決)。
