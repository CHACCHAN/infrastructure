# Phase 0: 調査・現状把握

Ansible中心アーキテクチャへの統合(TASK.md)に向けた調査結果。実装は行っていない。

- 調査日: 2026-08-13
- 対象: `ansible/` 配下の Proxmox 直接SSH方式、`kubernetes/` 配下の手動 kustomize 運用、Dev Container 実行環境

---

## 1. 結論サマリ

1. **移行先コレクションは `community.proxmox`(2.0.0)である。** TASK.md が前提とする `community.general.proxmox*` は community.general 9.0.0 で `community.proxmox` コレクションへ分離済みで、現行の ansible 12 系(ansible-core 2.21)には `community.proxmox 2.0.0` が同梱されている。
2. **現行のSSH方式で行っている全Proxmox操作は、community.proxmox のAPIモジュールで代替可能**(§4 マッピング表)。SSHでなければできない処理は見つからなかった。ノードへの `root` SSH パスワード認証と `add_host` によるグループ組み替えが丸ごと不要になる。
3. **Kubernetes 適用は `kubernetes.core.k8s` + `kubernetes.core.kustomize` lookup の組み合わせが最有力**(§5)。既存の kustomization ネスト構造は無変更で「適用の起点」だけ Ansible 化できる。動作確認済み。
4. **PVE APIトークン認証の疎通確認済み**(2026-08-13、リセット後の新シークレットで `proxmox_vm_info` によりクラスタ全体のVM 15台を取得)。テストVM 990(migration-test)も確認できた。
5. 実行環境(Dev Container)に問題があり修正した(§2)。**リビルドが必要**。

---

## 2. 実行環境の現状と修正

### 2.1 判明した問題

| 問題 | 原因 | 状態 |
| --- | --- | --- |
| `ansible` / `ansible-playbook` がPATHに無い | `pipx-package` feature は ansible メタパッケージのエントリポイント(`ansible-community`)しか公開しない(`--include-deps` 相当の挙動が無い) | **devcontainer.json 修正済み**(下記) |
| `proxmoxer` / `kubernetes` Python ライブラリ未導入 | community.proxmox / kubernetes.core モジュールの実行時依存。ansible メタパッケージには含まれない | 同上(injections で導入) |
| Vaultパスワードファイル(`~/.ansible_vault_pass`)消失 | コンテナリビルドで非マウント領域が初期化された | **要再作成**(利用者のみ可能) |

### 2.2 devcontainer.json の修正内容

```jsonc
// 旧
"ghcr.io/devcontainers-extra/features/pipx-package:1": { "package": "ansible" },
// 新
"ghcr.io/devcontainers-extra/features/ansible:2": {
    "injections": "proxmoxer requests kubernetes"
},
```

- `ansible:2` feature は ansible 一式のバイナリをPATHへ正しく公開する
- `injections` で venv に `proxmoxer` / `requests` / `kubernetes` を注入(モジュール実行時依存)
- 現行コンテナには暫定でシンボリックリンク + `pipx inject` を実施済み(リビルドで消えてよい)

### 2.3 確認済みバージョン

| コンポーネント | バージョン | 備考 |
| --- | --- | --- |
| ansible-core | 2.21.3 | ansible 12 系メタパッケージ |
| community.proxmox | 2.0.0 | ansible メタパッケージに同梱 |
| kubernetes.core | 6.5.0 | 同上。`server_side_apply` 対応 |
| kubectl | v1.36.3(kustomize v5.8.1 内蔵) | devcontainer feature 由来 |
| proxmoxer | 2.3.0 | pipx inject で導入 |

---

## 3. 現行 Proxmox 操作の棚卸し(直接SSH方式)

### 3.1 アーキテクチャ

```
localhost (connection: local)
  └─ proxmox_connect: add_host で proxmox グループ生成
       (ansible_host = ノードIP, ansible_user = root, ansible_password = vault_proxmox_ssh_password)
hosts: proxmox  ← ノードへ直接SSHし、ノード上で qm / pvesh を実行
  └─ proxmox_common/detect_proxmox_node: pvesh get /cluster/status から local==1 のノード名を特定
  └─ 各操作ロール: qm create / clone / set / resize / start / shutdown / destroy ...
  └─ 別ノード操作のみ pvesh のAPIプロキシ経由(SSHは接続先ノードのみ)
```

- `delegate_to` / `shell` / `become` は全ロールで不使用。コマンドは全て `ansible.builtin.command`
- `meta/dependencies` 無し。依存は `import_role` / `import_tasks` で明示
- サービス構築時は `_provision_vm.yml` が `playbooks/proxmox/*.yml` を6連続 `import_playbook` し、`add_host` で `ansible_host` を「ノード→VM」へ差し替える

### 3.2 実行コマンド一覧

| ロール / タスク | コマンド | 目的 |
| --- | --- | --- |
| proxmox_common/detect_proxmox_node | `pvesh get /cluster/status --output-format json` | 接続先ノード名の特定(local==1) |
| proxmox_common/get_cluster_vm_info | `pvesh get /cluster/resources --type vm --output-format json` | クラスタ全VM一覧 |
| proxmox_common/find_vm_on_node | (コマンド無し) | VMID存在+接続先ノード配置のassert |
| proxmox_common/apply_cloudinit | `qm set <vmid> [--ciuser ..] [--cipassword ..] [--sshkey <一時ファイル>] [--ipconfig0 ..] [--ipconfig1 ..] [--nameserver ..] [--searchdomain ..]` | cloud-init設定。公開鍵は `/tmp` に一時ファイルを作って渡す |
| proxmox_template_build/download_image | `uri`(チェックサムファイル取得+正規表現抽出) + `get_url`(`/var/lib/vz/import` へイメージ取得、checksum照合) | クラウドイメージ取得(※ノード上で実行) |
| proxmox_template_build/build_template | `qm create <vmid> --name .. --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-single --ostype l26` → `qm importdisk <vmid> <image> <storage>` → `qm set --scsi0 <storage>:vm-<vmid>-disk-0,iothread=1,ssd=1,discard=on` → `qm set --ide2 <storage>:cloudinit` → `qm set --boot c --bootdisk scsi0` → `qm set --serial0 socket --vga serial0` → `qm template <vmid>` | テンプレート構築の一連 |
| proxmox_template_build/remove_existing_on_other_node | `pvesh delete /nodes/<node>/qemu/<vmid> --purge 1` + `pvesh get /nodes/<node>/qemu` ポーリング(30回×5秒) | 別ノードの旧テンプレート削除 |
| proxmox_vm_build/clone_template_to_vm | `qm clone <template_vmid> <vm_id> --name <name> --full --storage <storage>`(loop) | フルクローン |
| proxmox_vm_hardware/change_hardware | `qm config <vmid>`(変更前設定の読み取り+マージ) → `qm set <vmid> <argv組み立て>` | CPU/メモリ/ディスク/NIC/オプション変更(電源オフ必須) |
| proxmox_vm_hardware/resize_disks | `qm config` → `qm resize <vmid> <bus><idx> <size>G`(現サイズ比較で冪等) | ディスク拡張(縮小不可) |
| proxmox_vm_options/change_options | `qm set <vmid> --<key> <value> ... [--delete k1,k2]` | agent/onboot等(稼働中可) |
| proxmox_vm_cloudinit | `qm config <vmid>`(cloudinitドライブ存在チェック) + apply_cloudinit 共有 | 既存VMのcloud-init変更 |
| proxmox_vm_powerctl/change_power | `qm start <vmid>` / `qm shutdown <vmid> --timeout <sec> [--forceStop 1]`(状態比較で冪等) | 電源操作 |
| proxmox_vm_delete/delete_vm | `qm destroy <vmid> [--purge 1] [--destroy-unreferenced-disks 1]` + `pvesh get /cluster/resources` ポーリング(30回×2秒) | 削除(電源オフ+confirm_vm_id必須) |

### 3.3 SSH方式が担っている暗黙の機能(移行時に意識すべき点)

1. **接続先ノード=操作対象ノード**という制約。`find_vm_on_node` は「VMが接続先ノードに居ること」をassertし、違えば利用者に `proxmox_ip` の指定し直しを求める。APIはクラスタ単位なのでこの制約自体が消える(挙動変更)
2. **イメージキャッシュ**は ノードローカルの `/var/lib/vz/import` ディレクトリ(get_url の checksum 照合で冪等)
3. **公開鍵の一時ファイル**(`qm set --sshkey` がファイルパスしか受けないための回避策)
4. **非同期操作のポーリング**(`qm destroy` / `pvesh delete` 後に一覧APIを retries で監視)
5. 認証は `vault_proxmox_ssh_password`(root のSSHパスワード)1変数のみ

---

## 4. community.proxmox 2.0.0 マッピング表

### 4.1 認証方式の変更

| 項目 | 現行(SSH) | 移行後(API) |
| --- | --- | --- |
| 接続先 | 各ノードへ root SSH | 任意の1ノードの `:8006`(APIはクラスタ全体に効く) |
| 認証情報 | `vault_proxmox_ssh_password` | `vault_proxmox_api_host` / `vault_proxmox_api_user`(`ansible@pve`) / `vault_proxmox_api_token_id`(`ansible`) / `vault_proxmox_api_token_secret` の4変数(Vault暗号化) |
| 実行ホスト | `hosts: proxmox`(add_host) | `hosts: localhost` / `connection: local` |
| 証明書 | — | 自己署名のため `validate_certs: false` が必要(全モジュール共通) |

- APIトークンは作成済み・権限付与済み。2026-08-13 にシークレットをリセットし、新シークレットで疎通確認済み
- **シークレットのVault追記が未了**(Vaultパスワードファイル再作成後に実施)

### 4.2 操作マッピング

| 現行コマンド | community.proxmox モジュール | 備考 |
| --- | --- | --- |
| `pvesh get /cluster/status`(ノード名特定) | `proxmox_cluster_status_info` または不要化 | API方式では「接続先ノード」概念が消える。VMの所在は `proxmox_vm_info` が返す `node` で分かる。**ノードIP→ノード名の解決方法は Phase 1 の論点**(§7-2) |
| `pvesh get /cluster/resources --type vm` | `proxmox_vm_info` | vmid/name/node で絞り込み可。`config` オプションで qm config 相当の構造化データも取得可能(現行の stdout 正規表現パースが不要になる) |
| イメージ取得(`uri`+`get_url`、ノード上) | `proxmox_template`(`url=` + `checksum=`/`checksum_algorithm=` + `content_type=import`) | **PVE側がURLから直接ストレージへダウンロード**(SSH不要)。対象ストレージに import コンテンツの有効化が必要(local は有効化済み)。チェックサムファイルの取得・抽出は localhost の `uri` で継続 |
| `qm create` | `proxmox_kvm`(state=present) | net/scsi/ide 等は dict 型で渡す |
| `qm importdisk` + `qm set --scsi0` | `proxmox_disk`(`import_from=`)または `proxmox_kvm` のディスク値 `import-from=` 構文 | import コンテンツ上のイメージから直接ディスク作成 |
| `qm set --ide2 <storage>:cloudinit` | `proxmox_kvm`(`ide: {ide2: "<storage>:cloudinit"}`) | |
| `qm set --boot/--serial0/--vga` | `proxmox_kvm`(`boot=` / `serial=` / `vga=`、update=true) | |
| `qm template` | `proxmox_kvm`(`state=template` または `template=true`) | 冪等(既にテンプレートならOK) |
| `qm clone --full --storage` | `proxmox_kvm`(`clone=` `newid=` `full=true` `storage=` `target=`) | `target` で別ノードへのクローンも可能(現行は不可だった) |
| `qm set`(cloud-init系) | `proxmox_kvm`(`ciuser` `cipassword` `sshkeys` `ipconfig` `nameservers` `searchdomains` `citype` `ciupgrade`、update=true) | **`sshkeys` は文字列で渡せる**ため一時ファイル回避策が不要になる |
| `qm config` | `proxmox_vm_info`(`config=current`) | 構造化データで返る。現行の正規表現による行パース(`build_disk_options_args` 等)を大幅簡素化できる |
| `qm set`(hardware/options) | `proxmox_kvm`(`update=true`、cores/sockets/vcpus/cpu/memory/balloon/net/scsi/scsihw/onboot/agent/tags 等) + `proxmox_nic`(NIC単体) + `proxmox_disk`(ディスク単体) | 一部パラメータは `update_unsafe=true` が必要。ディスクオプションの既存値マージは `proxmox_vm_info(config)` → merge → 適用で現行ロジックを再現 |
| `qm resize` | `proxmox_disk`(`state=resized` `size=`) | 拡張のみ(現行と同じ) |
| `qm start` | `proxmox_kvm`(`state=started`) | 冪等(モジュール内で状態判定) |
| `qm shutdown --timeout [--forceStop]` | `proxmox_kvm`(`state=stopped` `timeout=` `force=`) | 同上 |
| `qm destroy --purge` + ポーリング | `proxmox_kvm`(`state=absent` `purge=`) | モジュールがタスク(UPID)完了を待つため**ポーリングロジックが不要になる** |
| `pvesh delete /nodes/<node>/qemu/<vmid>`(別ノード) | `proxmox_kvm`(`state=absent` `node=`) | APIはクラスタ単位なので「別ノード専用処理」自体が不要 |

### 4.3 モジュール化できない/しない範囲

- **VM内OSセットアップ**(`common` / `docker` / 各サービスロール、`playbooks/vms/`): 対象外(TASK.md記載どおり)。VMへのSSHは継続。`_provision_vm.yml` の「ノード→VMへの add_host 切り替え」のうち **VM側(`vms` グループ)は現行維持**、ノード側(`proxmox` グループ)が不要化
- **チェックサムファイルの取得とハッシュ抽出**: `proxmox_template` は生のハッシュ値しか受けないため、ディストリのCHECKSUMSファイル取得+抽出(現行 `download_image.yml` の正規表現ロジック)は localhost 実行の `uri` + `set_fact` として温存する
- 現行ロールの**バリデーション資産**(158行の `vm_hardware/validate.yml` 等、入力の型・組み合わせチェック)はモジュール移行後も価値があるため、インターフェース互換の観点で Phase 1 で扱いを決める

---

## 5. Kubernetes 適用の Ansible 統合方式

### 5.1 現状

- `kubernetes/` はルート `kustomization.yaml` を起点とする4段ネスト(root → platform → external/apps → 各サービス)。kustomize 24ファイルは全て `resources:` のみで、patches/generators/overlays 等は不使用
- 適用起点は2つ: **リポジトリルート**(`kubectl apply -k . --server-side`)と **`vault/`**(秘密情報。意図的にルートから分離、git管理外)
- 上流アプリは `helm template | kubectl apply` 方式(Helmリリースを作らない)。GitOpsツールは不使用
- 運用規範: 適用前に必ず `kubectl diff -k .`、`kubectl delete -k .` は禁止
- Dev Container の `~/.kube` はマウント済みで、`kubectl get nodes`(k3s 4ノード)を確認済み

### 5.2 選択肢

| 方式 | 内容 | 評価 |
| --- | --- | --- |
| **A. `kustomize` lookup + `k8s`(推奨候補)** | `kubernetes.core.k8s: definition: "{{ lookup('kubernetes.core.kustomize', dir=...) }}"` + `server_side_apply` | ○ 本コンテナで動作確認済み。kubectl 内蔵 kustomize を利用。`k8s` の check_mode+diff で `kubectl diff -k` 相当も可能。リソース単位の changed 報告が得られる |
| B. `kubectl apply -k` を `command` でラップ | 最小変更 | △ Ansible化の意味が薄い(diff/check/changed が kubectl 任せ。モジュール統合というゴールに合わない) |
| C. `kubectl kustomize` の出力を一時ファイル化 → `k8s src=` | Aと等価の手動版 | △ Aで足りる。中間ファイル管理が増えるだけ |

方式Aの検証結果(本セッション):

- `kubernetes.core.k8s_cluster_info` → クラスタ接続OK(追加認証設定不要、`~/.kube/config` を自動使用)
- `lookup('kubernetes.core.kustomize', dir='kubernetes/namespaces')` → レンダリングOK
- `kubernetes.core 6.5.0` は `server_side_apply` パラメータ対応(現行運用の `--server-side` を踏襲可能)

### 5.3 スコープの論点(Phase 1 で確定)

1. **適用単位**: ルート一括(現行運用と同じ)か、`namespaces` / `platform` / `cloudflare` をタグ分割か
2. **`vault/` の扱い**: 秘密Secretの適用は別プレイ+明示タグとし、ルートと混ぜない(現行設計の意図を踏襲)
3. **`helm template | kubectl apply` 群**(cert-manager 等7チャート): TASK.md のゴールは kustomize 適用の統合であり必須ではないが、`kubernetes.core.helm_template` + `k8s` で同型に統合可能。段階的に対象へ含めるか判断
4. **適用前diff**: `k8s` の check_mode + diff を「適用プレイの直前確認」としてどう組み込むか

---

## 6. 疎通確認の実績(2026-08-13、本コンテナ)

| テスト | 結果 |
| --- | --- |
| `proxmox_vm_info`(APIトークン認証、`validate_certs: false`) | **成功**。クラスタ全体のVM 15台を取得(pve01〜05, 07)。VM 990(migration-test、旧方式で構築したP1検証台)の存在確認 |
| `k8s_cluster_info` | 成功(k3s v1.36 系 4ノード) |
| `kustomize` lookup | 成功(`kubernetes/namespaces` をレンダリング) |
| PVE Web(8006)到達性 | 成功(HTTP 200) |

※ APIシークレットは環境変数経由+`no_log: true` でテストし、リポジトリ・ログには残していない。

---

## 7. Phase 1 へ持ち越す論点

1. **ロール分割の維持 vs 統合**: 現行の操作単位ロール(`proxmox_vm_build` / `_hardware` / `_options` / `_powerctl` / `_cloudinit` / `_delete` / `_template_build`)は、playbook・docs・`_provision_vm.yml` と1:1対応しており、**外部インターフェース(変数名)を維持したまま内部実装をモジュールに置換**する案と、`proxmox_kvm` の表現力(1タスクで作成+HW+cloud-init)を活かして統合する案がある
2. **ノードの指定方法**: インベントリの `vm_node` はノードのIP。APIモジュールは**ノード名**(`node=`)を要求するため、(a) 実行時に `proxmox_node_info` 等でIP→名前を解決、(b) インベントリを名前指定に変更(破壊的変更・対応表必要)、のどちらかを選ぶ
3. **`proxmox_connect` / `add_host` 機構の去就**: API化で `proxmox` グループ自体が不要になる。`_provision_vm.yml` の中間プレイ(ノード用 add_host)の除去と、`pv_template_host` 一本化ロジック(VMID衝突回避)の要否
4. **`vault_proxmox_ssh_password` の残置**: 全面API化後もノードSSHが必要な運用(緊急時等)を playbook として残すか
5. **バリデーション資産の移植方針**: モジュール側バリデーションと現行 `validate.yml` の役割分担
6. **k8s 適用のスコープ**(§5.3)

## 8. 残作業・ブロッカー

| 項目 | 内容 | 担当 |
| --- | --- | --- |
| コンテナリビルド | devcontainer.json 修正の反映(ansible:2 feature + injections) | 利用者 |
| `~/.ansible_vault_pass` 再作成 | リビルドで消えるため再作成(mode 600、リポジトリ外)。playbook 自動実行に必要 | 利用者 |
| APIシークレットのVault追記 | `vault/proxmox.yml` へ `vault_proxmox_api_*` 4変数を追記(Vaultパスワード必要)。**平文コミット厳禁** | Vaultパスワード再設定後 |
| `ansible/collections/requirements.yml` | コレクションのバージョン固定(AWX実行環境も見据える)。Phase 2 冒頭で再作成 | Phase 2 |
| (任意)Codex委譲の環境修正 | コンテナ内 Codex CLI は seccomp により bwrap が失敗する。委譲する場合は利用者が `runArgs: ["--security-opt","seccomp=unconfined"]` を追加 | 利用者(任意) |
