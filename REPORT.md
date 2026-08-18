# 調査報告: infrastructure リポジトリ

- 調査日: 2026-08-18
- 調査者: Claude Code(Fable 5)+ サブエージェント8体(コード調査4 + Web最新情報検証4)
- 方針: バグ調査と最新情報との突き合わせ → 報告後、ユーザー指示により中程度以上の修正と優先度の高いバージョンアップを実装(下記「対応状況」)

## 実施内容

- `ansible-lint` / `yamllint` / 全playbook `--syntax-check`(実行環境: ansible-core 2.21.3)
- 全3ドメイン(pve / vm / k8s)+ AWX + EE + inventory のコード読解(263ファイル)
- Web検証: cloud image URL実在確認、コンテナ/チャート最新版、コレクション互換性、k3s/cert-manager
- インストール済み `community.proxmox 2.0.0` / `kubernetes.core 6.5.0` のモジュールソースとコードの突き合わせ

## 総合評価

**構文エラー0件・実行を止める致命的バグ0件。**

- 全playbookがsyntax-check合格。lint違反は意図的な1行のみ(下記)
- `vault/*.yml` 全6ファイルが `$ANSIBLE_VAULT;1.1;AES256` で暗号化済み。平文漏れなし
- Secretを扱う全経路の `no_log` が一貫している(k8s全ロール・ssh_key・password系を確認)
- 直近のAWX対応(Survey `default` キー補完、`playbooks/awx/configure.yml`)は既知バグ [ansible/awx#13640](https://github.com/ansible/awx/issues/13640) の正式ワークアラウンドと一致しており正しい実装

以下は「将来顕在化しうる問題」と「改善候補」。

## バグ・要注意(コード)

### 中程度

| # | 場所 | 内容 |
|---|------|------|
| 1 | `playbooks/awx/configure.yml` | `awx_vault_password` が空だとVault credential作成をスキップするのに、全Job Templateは無条件に `infrastructure Vault` を名前参照する。**vaultパスワード無しの環境で初回実行するとJT作成が全滅**する。DevContainer運用(`ANSIBLE_VAULT_PASSWORD_FILE` 自動供給)では顕在化しない |
| 2 | `roles/k8s/tasks/helm.yml` + `k8s_helm_inject_namespace: true`(nfs_provisioner / postgresql) | kubernetes.core の `merge_params` は **cluster-scopedリソース(ClusterRole/ClusterRoleBinding/StorageClass等)にも `metadata.namespace` を注入する**(コレクションソース `module_utils/k8s/resource.py:111-112` で確認)。K1/K2の実機検証を通過済みなので現状のクラスタでは動いているが、APIサーバーの許容挙動に依存した脆さ |
| 3 | `roles/vm_wg_easy/tasks/validate.yml` | 手動指定シークレット(`wg_easy_init_password` / `wg_easy_oauth_*_client_secret`)の形式検証が**欠落**。authentik/technitium/pbsには同種の検証(`^[A-Za-z0-9_.-]{16,}$`)があり非対称。`#` や空白を含む値が `.env` を静かに壊す |
| 4 | `roles/vm_supabase/tasks/configure_env.yml` | 初回構築で `ANON_KEY`/`SERVICE_ROLE_KEY` だけ `-e` 指定し `JWT_SECRET` 未指定だと、生成された別のJWT_SECRETと混在し**署名不整合で認証エラー**(全指定 or 全自動生成なら問題なし) |
| 5 | `roles/k8s/tasks/helm.yml` | `no_log` の仕組みが無い。現行チャートはvaluesに秘密値を入れないため実害なしだが、将来values経由で秘密を渡すと `--diff` で露出する設計ギャップ |
| 6 | `roles/k8s/tasks/helm.yml` | YAML 1.2 8進表記の正規化が6値のホワイトリスト。チャート更新で `0o600` 等が来ると型エラーで適用失敗(モグラ叩き構造) |
| 7 | `vault/README.md` | 一覧表に **`awx_api.yml` が未記載**(実在し `vault_awx_host` / `vault_awx_oauthtoken` / `vault_awx_scm_prikey` が使用中) |

### 低・情報

- `roles/k8s_external/templates/external.yaml.j2:76,106`: `forward_auth` のMiddleware名が `authentik-forward-auth` 固定。2つ目のルートに `forward_auth: true` を付けると同名Middlewareが重複出力される
- `roles/k8s_pgadmin/defaults/main.yml`: pgadminだけSecret内部キーが大文字スネーク前提(`envVarsFromSecrets` 方式のため)。他アプリはケバブケース + `secretKeyRef.key` 明示で、vault編集時の罠
- `roles/k8s_nfs_provisioner/tasks/main.yml`: Helm適用後のrollout待機なし(cert_manager / kubernetes_replicator にはある)。直後のpostgresqlのStatefulSet待機(最大300秒)が暗黙のバッファ
- `roles/k8s_certificates` / `roles/k8s_postgresql`: 必須Secretのassertが `is defined` のみで空dict(`{}`)を素通し(replicatorは `length > 0` まで検査しており非対称)
- `roles/vm_wg_easy` / `roles/vm_ddns`: `check_disk_space` 未適用(他4サービスは適用)。軽量サービスのため意図的省略の可能性が高い
- `roles/vm_pbs/tasks/configure_admin_user.yml`: パスワードが `proxmox-backup-manager` のargv経由でプロセス一覧に露出しうる(Ansibleログは `no_log` で秘匿済み)
- `inventory/group_vars/pbs.yml`: `pbs_data_disk_device` 未設定のため `playbooks/vm/pbs.yml` は毎回 `-e pbs_data_disk_device=...` が必須(誤初期化防止の意図的設計。運用上の制約として記録)
- `inventory/group_vars/dev.yml`: `pve_ssh_prikey_file` 未定義のため、`-e` 無しでSSHプレイに入るとundefinedエラー(コメントで文書化済みの前提)
- `ansible.cfg`: コメントの `.legacy/inventories/lab` が実体不在(N6移行の進行に伴う残骸の可能性)
- `roles/vm_dev/templates/` 全5ファイル: 冒頭コメントが旧ロール名 `roles/development` のまま(機能影響なし)
- ローカルの `ee/context/` / `context/`(git管理外・.gitignore対象)が `ee/requirements.yml` より古く `awx.awx` エントリが欠落 → 次回 `ansible-builder` 実行前に再生成推奨
- lint唯一の違反 `roles/k8s_awx/defaults/main.yml:70`(行長164 > 160)は `SOCIAL_AUTH_SAML_TEAM_ATTR` の1行必須制約(改行するとOperatorのreconcileが壊れる)による意図的な長行

### 調査中に否定した事項(誤検知の訂正)

- 「`collections/` symlinkが存在しない」というエージェント報告は**誤り**。`collections/requirements.yml → ../ee/requirements.yml` は実在し、Git管理下にあることを確認済み(エージェントのGlob検索がsymlinkを拾えなかった)
- `docs/pve/` `docs/vm/` `docs/awx/` の変数名・実行例・Job Template対応表はコードと一致。乖離なし
- `k8s_external_routes` 全16エントリと `external.yaml.j2` の突き合わせで、現行データで壊れる生成パターンはなし
- `.gitattributes` / `.devcontainer/devcontainer.json` は実態と整合

## 最新情報との検証(2026-08-18時点のWeb照会結果)

### 問題なし

- cloud image URL **全13本が有効**(Debian 13/12、Ubuntu 26.04 "resolute"・24.04・22.04、Rocky 10、Alma 10、get.k3s.io、get.docker.com)。Ubuntu 26.04のコードネーム "resolute" とSHA256SUMSのエントリも実在確認
- 使用コレクション(community.proxmox 2.0.0 / kubernetes.core 6.5.0 / community.docker 5.2.2 / ansible.posix 2.2.2 / awx.awx 24.6.1)と ansible-core 2.21.3 は**すべて現時点の最新**
- k3sピン `v1.36.2+k3s1` は実在するリリース。Technitium 15.4.0 / Guacamole 1.6.0 / Authentik 2026.5.6 / pgadmin chart 1.66.0 は最新
- PVE 9 の storage content-type `import`、`proxmox_kvm` の `update`+`update_unsafe`、`proxmox_disk` の `import_from` 形式は現行仕様に合致

### 更新が出ているもの(ピン留め設計のため不具合ではなく情報)

| 対象 | 調査時の固定値 | 最新 | 備考 |
|------|-------------|------|------|
| **wg-easy** | `15.4.0-beta.1` | **`15.4.0` 安定版**(2026-08-14) | beta卒業。移行推奨度が最も高い |
| cloudflared | 2026.7.3 | 2026.8.2 | 月次追従 |
| k3s | v1.36.2+k3s1 | v1.36.3+k3s1 | stableチャネル(2026-08-04) |
| cert-manager | v1.21.0 | v1.21.1 | パッチ |
| Nextcloud | 34.0.2-apache / chart 9.2.5 | 34.0.3-apache / chart 9.2.6 | パッチ(2026-08-17) |
| Homarr chart | 8.26.0 | 8.27.0 | マイナー |

### 未確認・注意

- **awx-operator chart 3.2.1 の最新性は未確認**(GitHub APIレート制限により2エージェントの情報が矛盾したため断定を回避)
- Proxmox VE 8.x は **2026-08-31 にEOL**。クラスタがPVE 9系なら影響なし(リポジトリのコードはPVE 9前提で正しい)
- pgadmin chart 1.66.0 にArtifactHub記録の未修正セキュリティ問題(高1・中1・低1)あり。監視継続を推奨

## 対応状況(2026-08-18 実装済み)

Codexリミット制限中のためFable 5が直接実装。全playbook syntax-check合格・ansible-lint新規違反ゼロ・追加ロジックは単体テストで検証済み(修正はコミット未実施)。

| 指摘 | 対応 |
|------|------|
| #1 AWX初回失敗経路 | ✅ 修正: `playbooks/awx/configure.yml` にpreflight追加。実値を渡さない実行ではAWX APIでCredential登録済みかを確認し、無ければ明確なメッセージで早期に停止 |
| #3 wg-easy検証欠落 | ✅ 修正: `roles/vm_wg_easy/tasks/validate.yml` に手動指定シークレット4種の検証を追加。**初版のauthentik式許可リスト(`^[A-Za-z0-9_.-]{16,}$`)は稼働中のvaultパスワード(10文字・一般記号入り)を誤って弾いたため**、実害のある文字だけを弾くブロックリスト(空白・引用符・#・$・`\`・バッククォート・非ASCII)へ再実装。実vault値で合格を確認済み |
| #4 supabase JWT不整合 | ✅ 修正: `configure_env.yml` にJWT三点セット(JWT_SECRET/ANON_KEY/SERVICE_ROLE_KEY)の全指定/全未指定を強制するassertを追加(単体テスト済み) |
| #5 helm.yml no_log欠落 | ✅ 修正: `k8s_helm_no_log` 変数を新設し、values書き出し→helm template→正規化→SSA適用の全経路へ伝播(既定false=挙動不変) |
| #6 8進ホワイトリスト | ✅ 修正: 任意の `0oNNN` を10進へ変換する汎用実装に置換(単体テスト済み)。実装中にJinja文字列リテラルのエスケープ処理(`'\1'`→chr(1))を踏み、regex_search方式で回避 |
| #7 vault/README欠落 | ✅ 修正: `awx_api.yml` の行とpgadminのSecret内部キー命名(大文字スネーク)の注意書きを追加 |
| certificates/postgresql の空dict素通し | ✅ 修正: assertへ `length > 0` を追加(replicatorと同水準) |
| nfs rollout待機なし | ✅ 修正: Deployment `nfs-nfs-subdir-external-provisioner` のAvailable待機を追加(cert_managerと同パターン。Deployment名はhelm templateで実レンダリングして確認) |
| ansible.cfg の `.legacy` 残骸 | ✅ 修正: 実体のないコメント行を削除 |
| vm_dev テンプレート旧ロール名 | ✅ 修正: 5ファイルのコメントを `roles/vm_dev` へ更新 |
| **wg-easy 15.4.0安定版** | ✅ 更新: defaults / group_vars / docs 2ファイルの計5箇所(`15.4.0-beta.1` → `15.4.0`)。`wg_easy_oauth_min_version` も安定版へ |
| **cloudflared 2026.8.2** | ✅ 更新: `deployment.yaml.j2`(`2026.7.3` → `2026.8.2`) |
| #2 cluster-scopedへのnamespace注入 | ⏸ 見送り: K1/K2で実機検証済みの経路のため変更せず。nfs chartがClusterRole等を含むことはhelm templateで事実確認済み。将来問題が出た場合は「ドキュメントごとにnamespaced判定してから注入する」方式へ変更する |
| forward_auth Middleware名固定 / pgadminキー命名(コード側) / pbs argvパスワード / wg_easy・ddnsのディスクチェック | ⏸ 見送り: 設計判断を伴うため報告のみ |
| k3s / cert-manager / Nextcloud / Homarr の版上げ | ⏸ 見送り: パッチ・マイナー差のみで、k3sはクラスタ全ノード再構築を伴うため(ピン留め設計どおり手動判断) |

### 実装中に発見した環境問題(コード外)

- `~/.ansible/collections` の `awx.awx 24.6.1` が消失していた(DevContainer環境の再作成による)。`ansible-galaxy collection install 'awx.awx:>=24.6.1,<25.0.0'` で復旧済み。再発しうるため、`.devcontainer` のセットアップへ `ansible-galaxy collection install -r ee/requirements.yml` を組み込むことを検討する価値あり
- Jinja文字列リテラルのエスケープ処理は文脈依存: YAML折り返しスカラー内の `'\1'` はchr(1)になる一方、`'\s'` は無変換。後方参照が必要な箇所では `regex_search` + 後処理で回避する(`playbooks/vm/ssh_key.yml` の `'\n'` コメントと同系の罠)

### 反映の確認手順(参考)

```sh
# k8s(cloudflared更新 + helm.yml変更の確認)
ansible-playbook playbooks/k8s/deploy.yml --check --diff -e app=cloudflared
ansible-playbook playbooks/k8s/deploy.yml -e app=cloudflared

# wg-easy 15.4.0への更新(イメージ入れ替え = 一時的な断)
ansible-playbook playbooks/vm/wg-easy.yml

# AWX preflightの動作(DevContainerでは従来どおり素通り)
ansible-playbook playbooks/awx/configure.yml
```
