# kubernetes.yml
起動済みのVMに [k3s](https://k3s.io/)(軽量なKubernetesディストリビューション)を構築します。
**1回の実行で1ノード**を構築し、`kubernetes_node_role` でコントロールプレーンとワーカーの
どちらを作るかを決めます。

接続情報と共通オプションは [README](../README.md#全playbook共通の指定) を参照してください。

```sh
# コントロールプレーン(1台目)
ansible-playbook playbooks/vms/kubernetes.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名> \
    kubernetes_node_role=server"

# ワーカー(コントロールプレーンのIPを指定するだけ。トークンは自動取得します)
ansible-playbook playbooks/vms/kubernetes.yml -vv \
-e "vm_ip=<ワーカーのIP> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名> \
    kubernetes_node_role=agent kubernetes_server_ip=<コントロールプレーンのIP>"

# コントロールプレーンのログインユーザー・鍵がワーカーと違う場合
ansible-playbook playbooks/vms/kubernetes.yml -vv \
-e "vm_ip=192.168.10.71 vm_ssh_user=worker vm_ssh_prikey=~/.ssh/id_ed25519_worker \
    kubernetes_node_role=agent kubernetes_server_ip=192.168.10.70 \
    kubernetes_server_ssh_user=k3s kubernetes_server_ssh_prikey=~/.ssh/id_ed25519_k3s"
```

- `kubernetes_node_role` は **`server`(コントロールプレーン)/ `agent`(ワーカー)** です。
  `control-plane` / `worker` という書き方でも受け付けます。**既定値はありません**
  (指定漏れがそのままコントロールプレーンの構築にならないよう、必ず指定させています)
- ワーカーの構築中は、**参加先のコントロールプレーンにもSSH接続します**
  (トークンの取得と、参加できたかの確認のため)。起動したままにしてください
- `development.yml` と違い、CockpitやGUI・開発ツールは導入しません。
  **Dockerも入れません**(k3sに同梱のcontainerdがコンテナランタイムのため)

## 必要なスペック
**Debian 13(cloud image)のVM専用**です。他のOSやバージョンでは実行前に停止します。

| 項目 | 必要量 |
| --- | --- |
| CPU / RAM | コントロールプレーン: 2コア / 4GB以上、ワーカー: 2コア / 2GB以上を推奨(公式の下限は1コア/512MB) |
| ディスク | **32GB以上を推奨**。k3s本体は約500MBですが、コンテナイメージが `/var/lib/rancher` に積み上がります |

Debianのcloud imageテンプレートは素のままだと約3GBしかないため、
`proxmox/` から構築する場合は `vm_hardware` の `resize` を必ず指定してください。

Proxmox側では**QEMUゲストエージェントの有効化**(`qm set <vmid> --agent enabled=1`)だけ
行っておくと、ホストからIPが見えて扱いやすくなります(`playbooks/proxmox/` の管轄)。

## 指定できる項目
共通オプションに加えて以下を指定できます。`kubernetes_node_role` 以外は**すべて任意です**。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `kubernetes_node_role` | **(必須)** | `server`(コントロールプレーン)/ `agent`(ワーカー) |
| `kubernetes_server_ip` | (未設定) | 参加先コントロールプレーンのIP。**agentでは必須**。SSH(トークン取得・Ready確認)にも使います |
| `kubernetes_server_node_ip` | `kubernetes_server_ip` | 参加先のAPIサーバーへ接続するIP。**クラスタ通信を占有ネットワークに分ける場合のみ**指定(後述) |
| `kubernetes_server_port` | `6443` | APIサーバーのポート(変える場合は `kubernetes_extra_config` の `https-listen-port` も合わせる) |
| `kubernetes_server_ssh_user` | `vm_ssh_user` | 参加先へSSH接続するユーザー(トークン取得用) |
| `kubernetes_server_ssh_prikey` | `vm_ssh_prikey` | 参加先へSSH接続する秘密鍵(トークン取得用) |
| `kubernetes_token` | 自動取得 | 参加用トークンを直接渡す場合に指定 |
| `kubernetes_version` | (最新安定版) | 例: `v1.34.1+k3s1`。指定するとその版に揃えます |
| `kubernetes_channel` | `stable` | バージョン未指定時に使うチャンネル(`latest` など) |
| `kubernetes_node_name` | VMのホスト名 | Kubernetes上のノード名(小文字) |
| `kubernetes_node_ip` | (自動判定) | ノード間通信に使うIP。**NICが複数ある場合のみ**指定(後述) |
| `kubernetes_flannel_iface` | `kubernetes_node_ip` のNIC | Pod間通信(flannel)が使うNIC名。通常は自動判定に任せます |
| `kubernetes_node_labels` | `[]` | 例: `["disk=ssd"]` |
| `kubernetes_node_taints` | `[]` | 例: `["node-role.kubernetes.io/control-plane:NoSchedule"]` |
| `kubernetes_disable` | `[]` | 標準コンポーネントの無効化。例: `["traefik"]` |
| `kubernetes_tls_san` | `[]` | APIサーバー証明書に追加するSAN(VIPやFQDN経由で使う場合) |
| `kubernetes_cluster_init` | `false` | 1台目で埋め込みetcdを使う(後述。**あとから変更不可**) |
| `kubernetes_extra_config` | `{}` | `config.yaml` にそのまま書き足す項目 |
| `kubernetes_install_open_iscsi` | `true` | `open-iscsi`(Longhorn等のiSCSI系ストレージ用)を入れる |
| `kubernetes_disable_swap` | `true` | swapを無効化する(後述) |
| `kubernetes_ready_retries` / `_delay` | `30` / `10` | ノードがReadyになるまでのリトライ回数 / 間隔(秒) |

変数の接頭辞は他のロールと同じくロール名(`kubernetes_`)に揃えています。
`kubernetes_disable` / `_tls_san` / `_node_labels` などの値は、そのままk3sの
`/etc/rancher/k3s/config.yaml` の項目(`disable` / `tls-san` / `node-label`)になります。

## 実施する内容
1. OS確認(**Debian 13であること**)、変数の検証
2. [全VM共通のセットアップ](../README.md#共通セットアップtasks)(OS更新、タイムゾーン、
   ロケール、sudoグループ、基本パッケージ、QEMUエージェント)。
   **swapだけは共通のzramではなく無効化**します(後述)
3. `open-iscsi` の導入(iSCSI系のCSIドライバ用。NFS用の `nfs-common` は基本パッケージ側)
4. ワーカーの場合、**コントロールプレーンから参加用トークンを取得**(後述)
5. `/etc/rancher/k3s/config.yaml` を配置 → 公式インストールスクリプト(`get.k3s.io`)でk3sを導入
6. ノードが **Ready** になるまで待機(ワーカーはコントロールプレーン側から確認)
7. コントロールプレーンのみ、SSHユーザーが `kubectl` をそのまま使えるよう
   `~/.kube/config` を配置
8. ufwが導入済みかつ有効な場合のみポートを開放(通常はスキップ)
9. VM再起動 → k3sが自動復帰することを確認 → **実行元の端末からAPIサーバーに繋がることを確認**

## トークンの自動取得
ワーカー(と2台目以降のコントロールプレーン)は、参加先の
`/var/lib/rancher/k3s/server/node-token` を**SSH経由でsudo読み取り**して使います。
手元でトークンをコピーして回す必要はありません。

```
実行元 ──SSH(vm_ssh_prikey)──────────→ 構築するワーカー
   └───SSH(kubernetes_server_ssh_prikey)──→ コントロールプレーン(トークン取得・Ready確認)
```

- 鍵を分けていない場合、`kubernetes_server_ssh_*` の指定は不要です(対象VMと同じ鍵を使います)
- 取得したトークンは `/etc/rancher/k3s/config.yaml`(root専用・`0600`)に書き込まれます。
  playbookのログには出しません(`no_log`)
- 参加先に繋がらない・k3sが入っていない場合は、その旨を表示して**k3sを入れる前に**中止します

## NICを2枚に分ける(クラスタ間の占有ネットワーク)
外部通信用のNICとは別に、**ノード間通信だけを流す占有ネットワーク**を持たせられます。
`kubernetes_node_ip` に占有ネットワーク側のIPを指定すると、以下がまとめてそちらに寄ります。

| 通信 | 使われるNIC |
| --- | --- |
| kubelet / etcd / APIサーバーへのノード間アクセス(`node-ip`) | 占有ネットワーク |
| Pod間通信のVXLAN(`flannel-iface`) | 占有ネットワーク(node-ipのNICを自動判定) |
| ワーカーからの参加先(`server:`) | `kubernetes_server_node_ip` を指定した場合のみ占有ネットワーク |
| **AnsibleのSSH・手元からの `kubectl`** | **外部通信用のまま**(`vm_ip` / `kubernetes_server_ip`) |

```sh
# ワーカー: 管理は192.168.10.x、クラスタ通信は10.10.10.x に分ける
ansible-playbook playbooks/vms/kubernetes.yml -vv \
-e "vm_ip=192.168.10.71 vm_ssh_user=k3s vm_ssh_prikey=~/.ssh/id_ed25519_k3s \
    kubernetes_node_role=agent \
    kubernetes_server_ip=192.168.10.70 kubernetes_server_node_ip=10.10.10.11 \
    kubernetes_node_ip=10.10.10.21"
```

- **SSH接続先の `kubernetes_server_ip` は変えません。** 占有ネットワークはVM間だけの
  ネットワークで、Ansibleの実行元からは見えないのが普通だからです。
  APIサーバーへの接続先だけを `kubernetes_server_node_ip` で分けています
- `kubernetes_node_ip` に指定したIPを持つNICがVM内に無い場合は、
  **k3sを入れる前に**エラーで停止します(cloud-initのIP設定漏れをそこで拾えます)
- コントロールプレーンでは、`tls-san` に `vm_ip`(外部通信用のIP)が**自動で追加**されます。
  `node-ip` を占有ネットワーク側にすると証明書のSANがそちらだけになり、
  手元から `kubectl` が使えなくなるためです
- VMのNIC自体の追加と占有ネットワークのIP設定はProxmox側の作業です。
  `proxmox/playbooks/kubernetes.yml` から構築する場合は `vm_cluster_ipv4` を書くだけで
  ここまで自動で設定されます([proxmox/docs/kubernetes.md](../../proxmox/docs/kubernetes.md))

## swapの扱い
Kubernetesはノードにswapが無い前提で設計されているため、このロールでは
**共通タスクのzram(`vm_zram_percent`)を使わず、swapを無効化**します。

- zramswapサービスの停止・無効化、`swapoff -a`、`/etc/fstab` のswap行のコメントアウトを行います
- k3s自体は `--fail-swap-on=false` で動くため、`-e "kubernetes_disable_swap=false"` にすれば
  共通のzramを使う構成にもできます(メモリ逼迫時の挙動が読みにくくなります)

## 構成されるもの
| 対象 | 内容 |
| --- | --- |
| サービス | `k3s.service`(server)/ `k3s-agent.service`(agent)。systemdで自動起動 |
| コマンド | `kubectl` `crictl` `ctr`(インストールスクリプトが `/usr/local/bin` に作るシンボリックリンク) |
| `/etc/rancher/k3s/config.yaml` | k3sの設定(Ansibleが生成。手動編集は上書きされます)。**トークンを含むため0600** |
| `/etc/rancher/k3s/k3s.yaml` | k3sが作るkubeconfig(root専用のまま触りません) |
| `/home/<vm_ssh_user>/.kube/config` | 上の複製(SSHユーザー所有・`0600`)。接続先はVMのIPに書き換え済み |
| `/var/lib/rancher/k3s` | データ本体(コンテナイメージ・etcd/sqlite・マニフェスト) |

k3sの標準構成のまま、**CoreDNS / Traefik / ServiceLB / local-path-provisioner /
metrics-server / Helm Controller** が入ります。
不要なものは `-e '{"kubernetes_disable": ["traefik", "servicelb"]}'` のように無効化できます。

**Helmコマンドは入れません。** k3sにはHelm Controllerが内蔵されているため、
`kind: HelmChart` のマニフェストを適用すればチャートを展開できます。
手元から `helm` / `kubectl` を使いたい場合は `development.yml` のVMに揃っています。

## 運用
```sh
# VM内(SSHユーザーのまま。~/.kube/config を見ます)
kubectl get nodes -o wide
kubectl get pods -A

sudo systemctl status k3s          # ワーカーは k3s-agent
sudo journalctl -u k3s -f
sudo cat /etc/rancher/k3s/config.yaml
```

```sh
# 手元の端末から使う(kubeconfigを持ってくる)
scp -i ~/.ssh/<秘密鍵> <SSHユーザ名>@<コントロールプレーンのIP>:.kube/config ~/.kube/config-k3s
KUBECONFIG=~/.kube/config-k3s kubectl get nodes
```

### バージョンアップ
`-e "kubernetes_version=v1.34.1+k3s1"` を付けて再実行すると、その版に入れ替えて再起動します
(指定しなければ、既に入っているk3sはそのまま使われ**勝手に上がりません**)。
**コントロールプレーン → ワーカーの順**に、1台ずつ実行してください。

### ノードを外す・作り直す
```sh
kubectl drain <ノード名> --ignore-daemonsets --delete-emptydir-data   # コントロールプレーン側
sudo /usr/local/bin/k3s-agent-uninstall.sh   # ワーカー側(serverは k3s-uninstall.sh)
kubectl delete node <ノード名>
```

## 再実行について
何度実行しても同じ状態になります。`config.yaml` が変わらなければk3sは再起動されず、
クラスタの状態(デプロイ済みのワークロードやデータ)もそのまま残ります。
`config.yaml` が変わった場合のみサービスを再起動します。

## うまくいかないとき
| 症状 | 確認すること |
| --- | --- |
| 「Debian 13専用です」で止まる | 対象VMのOS。このロールはDebian 13のcloud image前提です |
| 「kubernetes_node_role が指定されていない」で止まる | `-e "kubernetes_node_role=server"` または `=agent` を付けているか |
| 参加先に接続できず中止する | コントロールプレーンのVMが起動しているか、`kubernetes_server_ssh_user` / `kubernetes_server_ssh_prikey` が合っているか |
| node-tokenを読めず中止する | 参加先が `kubernetes_node_role=server` で構築済みか(`sudo systemctl status k3s`) |
| ワーカーがReadyにならない | ワーカー側 `sudo journalctl -u k3s-agent -n 50`。ポート6443へ到達できるか、時刻がずれていないか |
| 「指定されたノードIPを持つNICが見つかりません」で止まる | 2枚目のNICにIPが付いているか(`ip -4 addr`)。cloud-initの `net1_ipv4` を設定した後にVMを起動し直したか |
| NICを2枚にしたらPod間通信だけ届かない | 全ノードの `sudo cat /etc/rancher/k3s/config.yaml` で `flannel-iface` が占有ネットワーク側のNICに揃っているか。占有ネットワークのブリッジが全Proxmoxノードで繋がっているか |
| Podが起動しない・イメージが落ちてこない | `df -h /` と `kubectl describe pod`。ディスク不足なら `vm_hardware` の `resize` を確認 |
| NFSのPVがマウントできない | `nfs-common` は基本パッケージで入ります。NFSサーバー側のエクスポート設定を確認 |
| iSCSI(Longhorn)でアタッチに失敗する | `systemctl status iscsid`。`kubernetes_install_open_iscsi=false` にしていないか |

## HA構成(コントロールプレーンの複数台化)
1台目を `-e "kubernetes_node_role=server kubernetes_cluster_init=true"` で構築すると、
sqliteではなく**埋め込みetcd**になり、あとからコントロールプレーンを増やせます。

```sh
# 2台目以降のコントロールプレーン(1台目のIPを kubernetes_server_ip に指定)
ansible-playbook playbooks/vms/kubernetes.yml -vv \
-e "vm_ip=<2台目のIP> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名> \
    kubernetes_node_role=server kubernetes_server_ip=<1台目のIP> kubernetes_cluster_init=true"
```

- **`kubernetes_cluster_init` はあとから変更できません**。HAにする可能性があるなら1台目で
  `true` にしておいてください(単体構成のsqliteからは移行できません)
- etcdのクォーラムのため、コントロールプレーンは**3台以上の奇数**にしてください
- 手元から固定のIP/FQDNで繋ぎたい場合は `kubernetes_tls_san` にそのアドレスを追加してください
