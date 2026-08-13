# インフラ構成移行タスク：Ansible中心アーキテクチャへの統合

## 体制

- **設計・司令塔**: Claude Fable 5（このセッション）— 全体設計、フェーズ分割、各実装フェーズのレビュー基準を決定
- **実装・レビュー**: GPT-5.6 High Max（Codex経由でサブエージェントとして委譲）— 各フェーズの実装、コードレビュー
- 各フェーズの実装完了後は、Fable 5が差分をレビューし、次フェーズに進むか、手戻りするかを判断する

## 背景・現状構成

リポジトリ: `infrastructure`（構成は添付の`tree`出力を参照）

現状は3つの領域がそれぞれ独立した手段で管理されている。

1. **Proxmox**: `ansible/roles/proxmox_*`配下で、`community.general.proxmox`系ではなく直接SSH接続する方式でVM操作・OSセットアップを実施している（`proxmox_connect`, `proxmox_vm_build`, `proxmox_vm_hardware`, `proxmox_vm_cloudinit`, `proxmox_template_build`等）
2. **Kubernetes**: `kubernetes/`配下でkustomizeベースのマニフェスト管理。適用は手動`kubectl apply -k`または類する手動オペレーション
3. **VM内セットアップ**: `ansible/roles/`配下の各サービスroleが、Proxmox VM構築後にSSH接続してOSセットアップ・Docker Compose展開等を行っている（`authentik`, `supabase`, `wg_easy`等）

## ゴール

以下3点を実現する。

1. **Kubernetesマニフェストの適用をAnsibleに統合する**
   - `kubernetes.core`コレクション（`kubernetes.core.k8s`モジュール）を使い、既存の`kubernetes/`配下のkustomize構成をAnsibleから直接applyできるようにする
   - `~/.kube`はDev Container側で同期済みなので、認証情報の追加設定は不要な前提で進めてよい
   - 既存のkustomize構成（`kubernetes/platform/`, `kubernetes/namespaces/`等のディレクトリ構造）はそのまま活かし、Ansible側は「適用の起点」として統合する（kustomize自体を書き直すのではない）

2. **ProxmoxのVM操作をコミュニティモジュール化する**
   - 対象範囲は限定しない。以下すべてを`community.general.proxmox*`系のコミュニティモジュールに置き換える対象とする：
     - Cloud-init用OSイメージの取得
     - VMの構築（テンプレートビルド、クローン）
     - VMのハードウェア設定変更（CPU/メモリ/ディスク/ネットワーク）
     - VMの電源操作・削除等のライフサイクル管理
     - VM構築後、VM内にSSH接続して行うOSセットアップ（現在`common`, `development`等のroleが担っている部分）は、モジュール化の直接対象ではないが、Proxmox側のモジュール化に伴うroleのインターフェース変更（変数名、戻り値の形式等）があれば整合を取る
   - 現在の直接SSH方式（`proxmox_connect`ロール等）で得ている情報・制御と、コミュニティモジュールで代替可能な範囲を明確に切り分けること

3. **既存のディレクトリ構造・命名規則との整合性を保つ**
   - `ansible/roles/`, `ansible/playbooks/`, `ansible/inventories/`の既存の設計思想（サービス単位でrole分割、`_provision_vm.yml`のような共通処理の抽出等）を踏襲する
   - 破壊的変更を行う場合は、移行前後の対応表をドキュメント化する

## 進め方（フェーズ分割）

### Phase 0: 調査・現状把握（Fable 5主導、GPT-5.6に一部委譲可）

- 現在の`ansible/roles/proxmox_*`が具体的にどのSSHコマンド・APIエンドポイントを叩いているか棚卸しする
- `community.general.proxmox`, `community.general.proxmox_kvm`, `community.general.proxmox_template`等、利用可能なコミュニティモジュールと現状の処理のマッピング表を作る
- `kubernetes.core.k8s`モジュールの`src`/`resource_definition`オプションと、既存kustomize構成（`kustomization.yaml`のネスト構造）の統合方式の選択肢を洗い出す（例: `kubectl kustomize build`の出力をパイプで`k8s`モジュールに渡す方式 vs `kustomize`プラグイン経由）
- 成果物: 調査結果と移行方針の選択肢を提示するドキュメント（実装はまだしない）

### Phase 1: 設計

- Phase 0の調査結果をもとに、Fable 5が最終的な移行方針を確定する
- 新しいrole構造・playbook構造の設計案を作成する（既存構造からの差分が分かる形で）
- 移行順序（どのサービス/どのProxmox操作から着手するか）の計画を立てる
- 成果物: 設計ドキュメント（Fable 5がレビューし、承認後にPhase 2へ）

### Phase 2: 実装（GPT-5.6主導、Fable 5がレビュー）

- Phase 1の設計に従い、段階的に実装する
- 1機能（例: 1つのProxmox操作、または1つのKubernetesリソース群）ごとに実装・動作確認・レビューのサイクルを回す
- 既存の`ansible/playbooks/proxmox/*.yml`や`kubernetes/`配下は、動作確認が取れるまで並行稼働できる状態を維持する（いきなり置き換えて壊さない）

### Phase 3: 検証・切り替え

- 新旧両方式で同じ結果が得られることを確認する
- 問題なければ旧方式（直接SSH方式のProxmox操作、手動kubectl適用）を廃止する
- ドキュメント（`ansible/docs/`配下、`kubernetes/docs/`配下）を更新する

## 制約・注意点

- Proxmox認証情報、Kubernetes接続情報等の秘匿情報は`ansible/vault/`のAnsible Vault管理を継続する。新しいモジュールに切り替える際も、平文化しないこと
- 本番相当のラボ環境なので、Phase 2以降は既存VM・既存Kubernetesリソースを壊さない形で段階的に進める（テスト用の別VM/別namespaceでの検証を優先する）
- リポジトリはPublic公開予定。実装過程で秘密情報（IPアドレス、トークン、パスワード等）を平文でコミットしないよう常に注意する

## Fable 5への確認事項（作業開始前に整理してほしいこと）

- Phase 0の調査は、GPT-5.6に委譲するか、Fable 5自身が行うか
- 既存の`ansible/roles/proxmox_*`のロール分割（`proxmox_vm_build`, `proxmox_vm_hardware`等が個別roleになっている）を、コミュニティモジュール化後も維持するか、統合するか
- `kubernetes.core`コレクションはAnsible環境に未インストールの可能性があるため、Dev Container側の対応（`ansible-galaxy collection install kubernetes.core`等）が必要かどうかの確認
