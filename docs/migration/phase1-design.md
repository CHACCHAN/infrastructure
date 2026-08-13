# Phase 1: 設計 v2 — 宣言的Proxmox管理への刷新 & Kubernetes適用のAnsible統合

[Phase 0 調査結果](phase0-investigation.md)に基づく移行設計。実装(Phase 2)の指示書を兼ねる。

- 設計日: 2026-08-13(v2)
- 改訂: v1(既存インターフェース互換方針)は、利用者の要望「CLIの使い勝手を最優先に刷新してよい」を受けて**破棄**。本v2が正
- 設計思想(利用者指定): **ベース → 役割ごとのカスタマイズ → 実装** の3層。コードは最小限に。優先度は **読みやすさ > 共通化**

---

## 1. 設計原則

1. **宣言的に書く**: 「VMをどう作るか(手順)」ではなく「VMがどうあるべきか(状態)」をインベントリに書き、playbookは収束させるだけ
2. **3層の変数ピラミッド**(Ansible標準の変数優先順位をそのまま使う。マージ処理のコードは書かない):
   - **ベース** = ロールの `defaults/` + `group_vars/all/`(クラスタ共通の既定値)
   - **役割プロファイル** = `group_vars/<役割>.yml`(k8sノードは2NIC・4コア、開発VMは小さめ…)
   - **実装** = `hosts.yml` の各ホスト(vmid・配置ノード・IPの**3行程度**)
3. **1動詞=1playbook**: `provision` / `power` / `destroy` / `apply`。オプションの組み合わせ地獄を作らない
4. **フラット変数**: ネストした辞書(旧 `vm_hardware='{"cpu":{"cores":4}}'`)をやめ、`pve_vm_cores: 4` のような1階層の変数にする。上書きも読解も容易
5. 破壊的操作(destroy)にだけ明示的な確認変数を要求する

## 2. 利用者インターフェース(完成形)

```sh
# 事前入力なし: Vaultパスワードは環境変数で自動供給(devcontainerが設定、§6)
# 実行場所はリポジトリルート(R0以降)

# 宣言どおりにVMを収束(テンプレート準備→クローン→設定→cloud-init→起動 まで全部)
ansible-playbook playbooks/pve/provision.yml -l k8s          # 役割ごと
ansible-playbook playbooks/pve/provision.yml -l k3s-worker03 # 1台だけ
ansible-playbook playbooks/pve/provision.yml                 # 宣言済み全VM

# 電源(冪等)
ansible-playbook playbooks/pve/power.yml -l migration-test -e state=started
ansible-playbook playbooks/pve/power.yml -l k8s -e state=stopped

# 削除(vmid直指定+confirm必須。インベントリ未登録のVMも対象化できる唯一の口)
ansible-playbook playbooks/pve/destroy.yml -e vmid=991 -e confirm=991

# Kubernetesマニフェスト適用(kubectl apply -k . --server-side 相当)
ansible-playbook playbooks/k8s/apply.yml --check --diff   # 差分確認
ansible-playbook playbooks/k8s/apply.yml                  # 適用
```

- `-e proxmox_ip=` / `--ask-vault-pass` / JSON文字列変数 は**全廃**
- VM内セットアップ(既存 `playbooks/services/`)は当面現行のまま。N6 で新provisionに接続する

## 3. リポジトリ統合と新構造(v2.1で拡張)

**方針(利用者指定)**: リポジトリ全体を「基本ベース → 3つのドメイン最適化ベース → 具体的な実装」の3層で統一する。現在分かれている `ansible/` と `kubernetes/` は最終的に統合する。分かりやすさを最優先。

### 3.0 ドメインと命名規則

| ドメイン | ベース(共通部品) | 実装(具体物) |
| --- | --- | --- |
| ① Proxmoxホスト操作 | `roles/pve`, `pve_vm`, `pve_template` | インベントリの宣言そのもの(hosts.yml + group_vars) |
| ② VMセットアップ | `roles/vm`(旧common), `vm_docker`(旧docker) | `roles/vm_authentik`, `vm_wg_easy`, `vm_supabase` 等 |
| ③ Kubernetes | `roles/k8s`(適用・接続の共通処理) | `roles/k8s_portainer` 等(将来。マニフェスト完全移行後はロールがマニフェストを内包) |

**命名規則: `<ドメイン>` = ベースロール、`<ドメイン>_<名前>` = そのドメインの部品・実装。** playbookもドメイン別ディレクトリで対応させる。

### 3.1 リポジトリ全体構造(リポジトリルート = Ansibleプロジェクトルート)

git履歴がリセットされた今が構造変更の最小コストなので、`ansible/` の1階層を廃してルートへ引き上げる(R0)。

```
/infrastructure
├── ansible.cfg                   # inventory=./inventory を既定に
├── inventory/                    # ★宣言(単一の真実): hosts.yml + group_vars/
│   ├── hosts.yml                 #   実装層: 1VM=3〜5行。グループ=役割
│   └── group_vars/
│       ├── all/pve.yml           #   ベース層: クラスタ共通値
│       └── <役割>.yml            #   プロファイル層: 役割の差分だけ
├── playbooks/
│   ├── pve/                      # ① provision / power / destroy
│   ├── vm/                       # ② サービスVM構築(N6で旧services+vmsを統合改名)
│   ├── k8s/                      # ③ apply / apply-vault (K1)
│   ├── proxmox/ services/ vms/   # 旧(N6/N7で削除)
├── roles/
│   ├── pve/ pve_vm/ pve_template/    # ①ベース
│   ├── vm/ vm_docker/                # ②ベース(N6で改名)
│   ├── vm_<サービス>/                 # ②実装(N6で改名)
│   ├── k8s/                          # ③ベース(K1)
│   ├── k8s_<アプリ>/                  # ③実装(将来のマニフェスト移行後)
│   └── proxmox_* common docker 等    # 旧(N6/N7で削除)
├── kubernetes/                   # 既存kustomize一式(マニフェスト完全移行まで現状のまま)
├── vault/                        # Ansible Vault(proxmox_api.yml 等)
├── collections/requirements.yml  # AWX互換の標準位置
├── docs/                         # migration/ + 旧ansible/docsを統合
└── .legacy/                      # 旧実装アーカイブ + 旧インベントリ(inventories/)
```

- 旧サービスフローはN6まで実行可能を維持: `ansible-playbook -i .legacy/inventories/lab playbooks/services/<x>.yml`
- **k8sマニフェスト完全移行(将来フェーズM)**: `kubernetes/` のkustomize構成は、③の実装ロール(`k8s_<アプリ>`)がマニフェストをtemplates/として内包する形へ段階移行し、最終的に `kubernetes/` を解体する。K1〜K3(適用の入口統合)はその足場

### 3.2 インベントリの書きかた(実装層)

```yaml
# inventory/hosts.yml — ホスト名=VM名。ansible_host にVMのIPを書く
# 親グループ lab で束ねる。新playbookは lab とその配下だけを対象にする
lab:
  children:
    k8s:
      hosts:
        k3s-master01: { vmid: 201, node: pve01, ansible_host: 172.16.13.10 }
        k3s-worker01: { vmid: 202, node: pve02, ansible_host: 172.16.13.11 }
    dev:
      hosts:
        dev-chacchan: { vmid: 501, node: pve05, ansible_host: 172.16.12.10 }
    test:
      hosts:
        migration-test: { vmid: 990, node: pve01, ansible_host: 172.16.19.90 }
```

- 旧インベントリは `.legacy/inventories/` へ移動済み(グループ名マージ衝突の回避。旧 `services` フローは `-i .legacy/inventories/lab` でN6まで実行可能)
- ノード名↔管理IPの対応: `pveNN` = `172.16.11.(10+NN)`(例: pve05=172.16.11.15)。クラスタAPIの `ip` フィールドはコロシンク網(10.10.10.x)を返すため**IPからの実行時解決は使わない**(v1破棄理由の1つ)

- **`node` はノード名で直書き**(pve01〜pve10)。旧 `vm_node`(IP)+実行時解決は廃止(名前の方が読める。IP→名前解決コードも消える)
- ホスト名がそのまま `qm` 上のVM名になる(`pve_vm_name` で上書き可)
- IPv6 や2枚目NICのIPは必要なホスト/グループにだけ `cluster_ip:` 等を足す

### 3.3 ベースとプロファイル(変数はすべてフラット)

```yaml
# group_vars/all/pve.yml — ベース(クラスタ共通)
pve_storage: ssd01
pve_bridge: vmbr0
pve_nameserver: 172.16.11.1
pve_ssh_user: chacchan
pve_ssh_pubkey_file: ~/.ssh/id_ed25519.pub
pve_os: debian
pve_os_version: "13"
pve_ipv4_gw: 172.16.0.1

# group_vars/k8s.yml — 役割プロファイル(差分だけ書く)
pve_vm_cores: 4
pve_vm_memory: 8192
pve_vm_disk_size: 64
pve_vm_nets:
  - bridge: vmbr2
  - bridge: vmbr3
```

ロールの `defaults/main.yml` が全変数の既定値と一覧表を兼ねる(cores: 2, memory: 2048, disk_size: 20 等)。**マージ処理は書かない**— Ansibleの変数優先順位(role defaults < group_vars/all < group_vars/<役割> < host)に任せる。

## 4. ロール設計

### 4.1 `pve`(ベース部品)

- `tasks/find_vm.yml`(`tasks_from` 専用): `proxmox_vm_info` で vmid のVMを探し、`pve_found_vm`(dict or none)を返す。全ロール/playbookの存在確認を一本化
- 認証は各playbookの `module_defaults: group/community.proxmox.proxmox:`(アクショングループで全モジュール一括)+ `vars_files: vault/proxmox_api.yml`。**7行で済むためロール化しない**(読みやすさ優先)

### 4.2 `pve_vm`(1VMの宣言収束)— 中核

`tasks/main.yml` から4つの短いタスクファイルを順に読む。各ファイルは1責務・20行以内目標:

| タスク | 内容 | 使用モジュール |
| --- | --- | --- |
| `clone.yml` | vmidが存在しなければテンプレートからフルクローン | `proxmox_kvm`(clone/newid/full/storage/node) |
| `configure.yml` | cores/memory/net/options を宣言値へ(`update: true`) | `proxmox_kvm` |
| `disks.yml` | ディスクサイズ拡張(宣言値より小さい場合のみ)・追加ディスク | `proxmox_disk`(resized / present) |
| `cloudinit.yml` | ciuser/sshkeys/ipconfig/nameserver(sshkeysは文字列直渡し) | `proxmox_kvm`(update) |
| `power.yml` | `pve_vm_power: started|stopped`(既定 started)へ収束 | `proxmox_kvm`(state) |

- 冪等性はモジュールに委ねる。旧実装の argv組み立て・qm config正規表現パース・ポーリング(計約600行)は**全て消える**
- 旧 `vm_hardware/validate.yml`(158行)の入力チェックは、フラット変数化により大半が不要。残す価値のあるもの(ssd×virtio禁止等)だけ `assert` 1タスクに集約
- **収束の実装規約(N1検証で確定)**: `proxmox_kvm` の `update: true` は差分判定をせず常に設定を書き込むため、ロール側で `proxmox_vm_info(config=current)` の現在値と宣言値を比較し、**差分がある項目だけ update を呼ぶ**(差分なしなら changed=0)。NICは現在の `macaddr` を必ず引き継いで文字列を組み立てる(毎回MACが変わる事故の防止)。ディスク拡張・追加も現在configとの比較で実行要否を判定する

### 4.3 `pve_template`(テンプレート収束)

- **テンプレートは (OS, ノード) ごとに収束させる**。全ストレージがノードローカル(shared=0、2026-08-13 API確認)でクロスノードクローンができないため、VMを置くノード上にテンプレートが必要
- **VMID体系: `9XXNN`**(XX=OSカタログ番号00〜, NN=ノード番号01〜10)。例: debian13(XX=00)をpve03に→`90003`。旧テンプレート(9000〜9008、単一ノード方式)はPhase 3の切替完了まで温存し、その後削除
- テンプレート名は `<os><ver>-template-<node>`(例: `debian13-template-pve03`)
- OSカタログ(`vars/os/{debian,ubuntu,rocky,almalinux}.yml`)は旧 `proxmox_os_defaults` のデータを移設し、各os/versionに `catalog_index`(XX)を付与
- 流れ: 既存確認(vmidがテンプレートなら即スキップ)→ チェックサム取得(localhost `uri`)→ `proxmox_template`(`url=` でPVE側が直接DL、`content_type=import`、storage=local)→ テンプレVM作成(`proxmox_kvm`)→ ディスク取り込み(`proxmox_disk import_from`)→ `state=template` 化
- `provision.yml` から `throttle: 1` で呼ぶ(N4。同一テンプレの同時作成レース回避)。`playbooks/pve/template.yml` で単体実行も可

### 4.4 削除するもの(旧→新対応)

| 旧 | 新 |
| --- | --- |
| `proxmox_connect` + add_host群 | 廃止(localhost + API) |
| `proxmox_os_defaults` | `pve_template` の vars へデータ移設 |
| `proxmox_template_build` | `pve_template` |
| `proxmox_vm_build` / `_hardware` / `_options` / `_cloudinit` / `_powerctl` | `pve_vm`(1ロールに統合。宣言収束なので操作別ロールが不要になる) |
| `proxmox_vm_delete` | `playbooks/pve/destroy.yml`(タスク3個程度のためロール化しない) |
| `proxmox_common` | `pve`(find_vmのみ。node解決・cloudinit共有は不要化) |
| 変数 `vm_id`/`vm_name`/`vm_node`/`vm_hardware`(JSON)/`vm_options`/`proxmox_ip`… | `vmid`/`node`/`pve_vm_*` フラット変数 |
| `playbooks/proxmox/*.yml`(7本) | `playbooks/pve/*.yml`(3本) |

## 5. Kubernetes適用(v1から変更なし、再掲)

- `playbooks/k8s/apply.yml`: `k8s` + `lookup('kubernetes.core.kustomize', dir=<repo>/kubernetes)` + `server_side_apply: {field_manager: kubectl}`(現行 `kubectl apply --server-side` とフィールド所有権を揃える)。`--check --diff` が `kubectl diff -k .` 相当
- `playbooks/k8s/apply-vault.yml`: `kubernetes/vault/` 専用(秘密Secret、ルートと混ぜない)
- `kubernetes/` 配下のマニフェスト・kustomize構成は一切変更しない。helm群の統合は任意課題(K4)
- **長期方針(利用者決定)**: 将来的にマニフェスト自体もAnsibleへ完全移行する(kustomize廃止、Ansibleで資源定義を管理)。K1〜K3はその中間段階であり、最終形を妨げない実装とする(適用の入口をAnsibleに一本化しておくことが移行の足場になる)

## 6. 実行環境

- devcontainer の `containerEnv` に `ANSIBLE_VAULT_PASSWORD_FILE=/home/vscode/.ansible_vault_pass` を追加 → **`--ask-vault-pass` 全廃**(ファイルはリポジトリ外・要再作成手順はREADMEに記載)。AWXは自前のVaultクレデンシャル機構を使うため影響なし
- `ansible/collections/requirements.yml`(作成済み)でコレクションを固定

## 7. 実装計画(1ステップ=実装→レビュー→実機検証)

| # | 内容 | 検証(テストID: VM 990-999 / テンプレ 9990番台) |
| --- | --- | --- |
| N0 | インベントリ新レイアウト(hosts.yml + group_vars、既存インベントリと並存)+ devcontainer環境変数 | lintのみ(実VM操作なし) — **完了** |
| N1 | `pve` ロール + `playbooks/pve/power.yml` | VM 990 起動→再実行(changed=0)→停止→再実行(changed=0) — **完了** |
| R0 | リポジトリ再構成: `ansible/*`をルートへ、docs統合、`.legacy/`集約、ansible.cfg調整(§3.1) | graph / syntax-check / power.yml冪等 全てOK — **完了** |
| N2 | `pve_vm` の configure/cloudinit/disks | VM 990 で変更→復元→再実行3回changed=0 — **完了** |
| N3 | `pve_template` + `provision.yml`(テンプレ部) | テンプレ 9990 新規構築+再実行changed=0 — **完了** |
| N4 | `pve_vm` clone + `provision.yml` 完成 | 991をテンプレ自動構築(90001)から一気通貫、再実行changed=0 — **完了** |
| N5 | `destroy.yml` | confirm不一致の拒否を確認後、991と9990を削除 — **完了** |
| N6 | ②ドメイン整備: `common`→`roles/vm`、`docker`→`vm_docker`、サービスロール→`vm_<サービス>` へ改名し、旧services+vmsを `playbooks/vm/` へ統合(新provision接続、pv_*機構の廃止) | dev VM 992 で一気通貫(ok=77 failed=0)。再実行はchanged=1(仕様の最終再起動のみ)。992破棄・インベントリ掃除済み — **完了** |
| N7 | 旧 `proxmox_*` ロール・`playbooks/proxmox/` 削除、旧docsの `.legacy/docs/` 退避、docs全面更新(README・docs/pve.md・docs/vm.md・docs/k8s.md) | 新実装からの旧ロール参照ゼロをgrepで機械確認後に削除。全14playbook syntax-check OK — **完了**(`.legacy/` 自体の削除はPhase 3で990比較後に判断) |
| K1 | `playbooks/k8s/apply.yml` | SSA所有権移行を`-e force=true`で1回実施(差分ゼロ確認済み)、以後 `--check --diff` 差分ゼロ / apply changed=0 — **完了** |
| K2 | `apply-vault.yml` | `--check` でdry-run検証まで — **完了**(実適用は手元vaultの鮮度を利用者が確認してから) |
| K3 | `kubernetes/README.md` 更新 | 適用手順をAnsible経由(apply/apply-vault)へ更新 — **完了** |
| P1 | Phase 3 新旧パリティ監査: APIで全VMの実configを吸い上げて宣言と突合。cpu表記ゆれ(`cputype=`プレフィックス混在)の比較正規化をconfigure.ymlへ追加。宣言修正: shun-devの実ノードはpve02 / k8s各ノードのcores・memory・diskは個体値 / devグループの鍵は個人持ちのため非管理化(未定義=触れない) | 本番13台+990へ `provision.yml --check` → **全14台 changed=0**(sshkeysも全サービスVMで内容一致を確認) — **完了** |
| P2 | Phase 3 旧成果物の掃除 | **利用者操作待ち**(自動実行は環境の権限制約で保留): ①VM990削除 `destroy.yml -e vmid=990 -e confirm=990` → inventoryのtestグループも削除 ②旧テンプレ9000削除 `destroy.yml -e vmid=9000 -e confirm=9000`(本番VMは全てフルクローンで依存なし) ③`.legacy/` をgit rm ④**旧 `root@pam!ansible` トークンの失効確認**(.legacy内に平文秘密が2件あり、git履歴にも残存。公開前に失効+履歴除去が必要) |

## 8. リスクと安全策

1. git履歴なし(2026-08-13リセット確認)。旧実装は `ansible/.legacy/proxmox-ssh/` にアーカイブ済み。**初回コミット推奨**
2. Codex(danger-full-access)には「対象ファイル以外に触れない」「実VM操作禁止(検証はFable 5)」を毎回明示
3. 本番VM保護: テストID規約の徹底。`destroy.yml` は confirm 必須 + 稼働中VM拒否(旧仕様踏襲)
4. 新旧並行: 旧 `playbooks/proxmox/` と `playbooks/services/` はN7まで現状のまま動く(新構造は追加のみで構築)
