# AWXから実行するときの前提

このリポジトリは**手元(Dev Container・リポジトリルートで実行)を基準**に作ってある。AWXは実行環境が違うため、次を満たさないと「手元では動くのにAWXだけ落ちる」ことになる。

なお、AWXのJob Templateの**変数欄とSurveyは、どちらも `-e`(extra vars)と同じ**扱いで届く。手元の `-e` で動く指定は、そのままAWXの変数欄に書けば同じに動く。

## 1. インベントリはプロジェクト由来にする(推奨)

AWXは**自前で生成したインベントリ**をplaybookへ渡す。Job Templateに紐づくInventoryを **Sources → Sourced from a Project**(このリポジトリの `inventory/`)にしてSyncすると、`inventory/group_vars/` の3層(`all/` とロールプロファイル)がそのまま届き、手元と完全に同じ宣言で動く。

- 確認: AWXの Inventory → Hosts → 任意のホストの Variables に `pve_vm_cores` などが入っているか
- k3sの**初回**構築は宣言順(`order: inventory` + `serial: 1`)に依存する。AWX生成インベントリの並びがコントロールプレーン先頭でない場合、ワーカーがトークン取得に失敗する(現在のホスト名はどう並べても `k3s-master01` が先頭になるため顕在化しない)

**同期しない場合**(手動インベントリのまま使う場合)は、group_vars が一切届かないため、必要な値をすべてJob Templateの変数欄で渡す。playbookは黙って壊れずに次で知らせる:

- adhoc登録時に「プロファイルは適用されません」と表示する(役割プロファイルの継承が効かないため、実質 `profile: lab` と同じになる)
- provisionの最初に、group_vars/all 由来の基本変数(`pve_storage` / `pve_bridge` / `pve_ipv4_prefix` / `pve_ipv4_gw`)の不足を**列挙して停止**する

手動インベントリの制約: SSHを伴うplaybookは、**adhocで作ったVM(`target`/`profile` 指定)なら鍵本文でそのまま動く**が、手動インベントリに元から書いてあるホストへは鍵パスの自動解決が効かない(そのホストの変数に `pve_ssh_prikey_resolved` を持たせるか、プロジェクト同期に切り替える)。

手動インベントリでインベントリ外VMを1台つくる変数欄の例:

```yaml
target: test
profile: lab
vmid: 901
node: pve09
ip: 172.16.11.77

# group_vars/all/pve.yml の代わりに自分で渡す
pve_storage: local-lvm
pve_bridge: vmbr0
pve_ipv4_prefix: 24
pve_ipv4_gw: 172.16.11.1

# 上書きしたいVM設定と、SSHするなら鍵(Surveyで渡すなら不要)
pve_vm_cores: 2
pve_ssh_user: dev
```

## 2. Limit(絞り込み)を使わない

[playbooks/pve/adhoc.yml](../playbooks/pve/adhoc.yml) と [playbooks/vm/ssh_key.yml](../playbooks/vm/ssh_key.yml) は **localhost** で前処理を行う。Job Templateの Limit や `-l` を指定すると**このプレイごと除外される**ため、鍵の一時ファイルが作られない・一時ホストが登録されない。

絞り込みは **`-e target=<ホスト名>`** で行う。

## 3. 鍵はファイルではなく本文で渡す

実行環境のHOMEには `~/.ssh/id_ed25519_*` が無いため、`pve_ssh_pubkey_file` / `pve_ssh_prikey_file` は解決できない。Surveyの**テキストエリア**で `pve_ssh_pubkey_value` / `pve_ssh_prikey_value` に鍵本文を渡す。→ [docs/vm.md](vm.md#鍵をファイルではなく本文で渡すawxのsurveyなど)

パスフレーズ付きの秘密鍵は非対話で解錠できないため使えない。秘密鍵と `pve_ssh_password` は必ず**暗号化したSurvey質問**で渡す(Job Templateの変数欄は画面から見えるため)。

## 4. Surveyは「未回答なら変数を送らない」設定にする

AWXは未回答の質問を**空文字**で渡すことがある。空文字は「未定義」ではないため、`| default(...)` が既定値に戻してくれない。

このリポジトリでよく使う変数は空文字でも安全側に倒してある。

| 変数 | 空文字で渡したとき |
| --- | --- |
| `target` | **実行を中止する**(既定へ戻すと対象が意図せず広がるため) |
| `profile` | ad-hoc登録を行わない(通常運用と同じ) |
| `ip2` | `cluster_ip` を作らない |
| `pve_ssh_password` | パスワード設定を行わない |
| `pve_ssh_pubkey_value` / `pve_ssh_prikey_value` | ファイル指定へフォールバックする |

これ以外(`vmid` `node` `ip` `app` など)は素通りするため、任意項目は必ず「未回答時に変数を送らない」設定にする。

## 5. 実行環境(EE)に入れておくもの

`collections/requirements.yml` のコレクションはAWXがProject同期時に入れるが、**Pythonパッケージと実行ファイルはEEイメージ側に必要**。

| ドメイン | 必要なもの |
| --- | --- |
| ① pve | `proxmoxer` / `requests` |
| ③ k8s | `kubernetes` / `helm` バイナリ |

`playbooks/pve/*` と `playbooks/k8s/deploy.yml` は `ansible_python_interpreter` をAnsible本体のPythonへ固定しているため、そのPythonから import できる必要がある。

## 6. ③k8sドメインはkubeconfigが要る

[playbooks/k8s/deploy.yml](../playbooks/k8s/deploy.yml) は接続先が宣言(`k8s_api_server`)と一致するか検証してからでないと一切書き込まない。AWXではkubeconfigか `K8S_AUTH_*` を渡す。AWX PodのServiceAccountへフォールバックすると、内部APIのURLが宣言と一致せずpreflightで止まる。

## 7. 仕上げの疎通確認はAWX Podから行われる

各サービスplaybookの最後にある `uri` / `wait_for` は `delegate_to: localhost`、つまり**AWXの実行Pod**から対象VMのLAN側IPへ接続する。構築は成功したのに最後の確認だけ落ちる場合は、Podからの経路・NetworkPolicy・VM側のfirewallを疑う。テンプレート初回作成時のチェックサム取得やHelmリポジトリへの通信も実行Pod側で必要になる。
