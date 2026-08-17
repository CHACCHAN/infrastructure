# AWX — Web UIからの実行と、その設定のコード管理

このリポジトリはAWX(クラスタ上の `ansible.cc-chacchan.com`)からも実行できる。**AWX側の設定(Project / Inventory / Credential / EE / Job Template+Survey)はすべてコードで管理**しており、手動でJob Templateを作る必要はない。

| 何を | どこで |
| --- | --- |
| AWX本体のデプロイ | `roles/k8s_awx`(③ドメイン → [docs/k8s/](../k8s/README.md)) |
| AWX側の設定(JT/Survey等) | [awx/*.yml](../../awx/)(定義)+ [playbooks/awx/configure.yml](../../playbooks/awx/configure.yml)(適用) |
| 実行環境(EE)イメージ | [ee/](../../ee/)(ansible-builder定義) |
| AWX接続トークン | [vault/awx_api.yml](../../vault/awx_api.yml)(暗号化) |

## セットアップ(Configuration as Code)

```sh
# 1. AWXのOAuthトークンを設定(発行手順はファイル内コメント)
ansible-vault edit vault/awx_api.yml

# 2. AWX側の設定を一括収束(冪等。定義を変えたら再実行するだけ)
ansible-playbook playbooks/awx/configure.yml \
  -e awx_kubeconfig_content="$(cat ~/.kube/config)"   # 初回のみ: k8s-deploy用kubeconfig
```

- **Vault credential**: 既定でDevContainerの `ANSIBLE_VAULT_PASSWORD_FILE` の中身が登録される(明示は `-e awx_vault_password=`)
- **プライベートリポジトリの場合**: `-e awx_scm_username=<GitHubユーザー> -e awx_scm_token=<PAT>` でSCM credentialも作成される
- Job Templateを追加・変更するときは [awx/job_templates.yml](../../awx/job_templates.yml) を編集して再実行(AWX UIでは編集しない。次回のconfigure実行で上書きされる)

### EEイメージのビルドと登録

コレクションはAWXがProject同期時に `collections/requirements.yml`(実体は `ee/requirements.yml` へのシンボリックリンク)から入れるが、**Pythonパッケージと実行ファイルはEEイメージ側に必要**(①pve: `proxmoxer`/`requests`、③k8s: `kubernetes`/`helm`)。

```sh
ansible-builder build --tag awx-ee-lab:latest --container-runtime docker \
  -f ee/execution-environment.yml
# AWX Podから到達できるレジストリへpushし、awx/execution_environment.yml の
# awx_ee_image をそのURLへ更新して configure.yml を再実行する
```

## AWXから実行するときの前提(読み物)

AWXのJob Templateの**変数欄とSurveyは、どちらも `-e`(extra vars)と同じ**扱いで届く。手元の `-e` で動く指定は、そのままAWXでも同じに動く。以下の前提の多くは**Survey定義に機械化済み**だが、仕組みを知っておくとトラブル時に迷わない。

### 1. インベントリはプロジェクト由来にする

Inventory `lab` は **Sources → Sourced from a Project**(このリポジトリの `inventory/`)として定義されている(configure.ymlが設定)。Syncすると `inventory/group_vars/` の3層がそのまま届き、**手元と完全に同じ宣言で動く**。

手動インベントリのまま使う場合はgroup_varsが一切届かないため、必要な値をすべて変数欄で渡す。playbookは黙って壊れず、不足変数を列挙して止まる(provisionの基本変数チェック等)。

### 2. Limit(絞り込み)を使わない

`adhoc.yml` と `ssh_key.yml` は **localhost** で前処理を行う。Limitや `-l` を指定すると**このプレイごと除外される**ため、鍵の一時ファイルが作られない・一時ホストが登録されない。絞り込みは **`target` 変数**で行う(Job Templateは `ask_limit_on_launch: false` で定義済み)。

### 3. 鍵はファイルではなく本文で渡す

実行環境のHOMEには鍵ファイルが無いため、`pve_ssh_pubkey_value` / `pve_ssh_prikey_value` に**本文**を渡す(Survey定義済み。秘密鍵は暗号化質問)。パスフレーズ付きの秘密鍵は非対話で解錠できないため使えない。仕組みは [docs/vm/ssh_key.md](../vm/ssh_key.md)。

### 4. Surveyの未回答は「変数を送らない」

AWXは未回答の質問を**空文字**で渡すことがある。空文字は「未定義」ではないため `| default(...)` が効かない。このリポジトリのSurvey定義は全質問をdefaultなしで作ってあり(未回答=送らない)、さらにplaybook側も空文字を安全側に倒す:

| 変数 | 空文字で渡したとき |
| --- | --- |
| `target` | **実行を中止する**(既定へ戻すと対象が意図せず広がるため) |
| `profile` | ad-hoc登録を行わない(通常運用と同じ) |
| `ip2` | `cluster_ip` を作らない |
| `pve_ssh_password` | パスワード設定を行わない |
| `pve_ssh_pubkey_value` / `pve_ssh_prikey_value` | ファイル指定へフォールバックする |

### 5. EEのansible-coreは手元より古い

`quay.io/ansible/awx-ee` のansible-coreは手元のDev Containerより古い(実質2.17か2.18)。**2.19より前は、テンプレートの結果を `{` `[` `True` `False` で始まるものしかPythonオブジェクトへ戻さない。**

つまり `"{{ ... | default(none) }}"` は**文字列 `"None"`** になり、`is none` が成立しない。**このリポジトリでは `none` をセンチネルに使わない**:

| 用途 | 使うセンチネル | 判定 |
| --- | --- | --- |
| VMの検索結果(dict) | `default({})` | `\| length == 0` |
| 任意指定の値(文字列・数値) | `default('')` | 真偽値(`not x`) |

実例は [roles/pve/tasks/find_vm.yml](../../roles/pve/tasks/find_vm.yml) の冒頭コメント。手元(2.19以降)では `none` でも動いてしまい**AWXでだけ落ちる**ので、新しいロールを書くときも上表に合わせること。

### 6. ③k8sドメインはkubeconfigが要る

`k8s-deploy` は接続先が宣言(`k8s_api_server`)と一致するか検証してからでないと一切書き込まない。kubeconfigは**カスタムCredential Type `kubeconfig`** が `K8S_AUTH_KUBECONFIG` として注入する(configure.ymlが定義・紐づけ済み)。AWX PodのServiceAccountへのフォールバックは効かない(仕様)。

### 7. 仕上げの疎通確認はAWX Podから行われる

各サービスplaybookの最後にある `uri` / `wait_for` は `delegate_to: localhost`、つまり**AWXの実行Pod**から対象VMのLAN側IPへ接続する。構築は成功したのに最後の確認だけ落ちる場合は、Podからの経路・NetworkPolicy・VM側のfirewallを疑う。テンプレート初回作成時のチェックサム取得やHelmリポジトリへの通信も実行Pod側で必要になる。

## Job Template一覧

定義の正は [awx/job_templates.yml](../../awx/job_templates.yml)(このリストは対応表のみ)。

| Job Template | playbook | ドキュメント |
| --- | --- | --- |
| pve-provision / pve-power / pve-destroy / pve-template | playbooks/pve/*.yml | [docs/pve/](../pve/README.md) |
| vm-authentik / vm-ddns / vm-k3s / vm-pbs / vm-supabase / vm-technitium / vm-wg-easy / vm-dev-setup / vm-dev-password | playbooks/vm/*.yml | [docs/vm/](../vm/README.md) |
| k8s-deploy | playbooks/k8s/deploy.yml | [docs/k8s/deploy.md](../k8s/deploy.md) |
