# 規約

このリポジトリで書くコードとドキュメントの決まりごと。人間もエージェントも同じ規約に従う。

## 言語

- ドキュメント・コメント・タスク名・コミットメッセージは日本語で書く。
- 製品名は公式の表記に合わせる(cert-manager、k3s、Longhorn など)。
- 英語で書くのは [AGENTS.md](../AGENTS.md)、`.agents/`、`.claude/agents/` だけ(エージェント向けの指示のため)。

## 構成

Ansible 公式の推奨配置([Sample Ansible setup](https://docs.ansible.com/ansible/latest/tips_tricks/sample_setup.html)、[Tips and tricks](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html))に合わせる。

- ロールは、リポジトリ直下の `roles/` にフラットに置く。サブディレクトリでグループ化せず、playbook の隣にも置かない。playbook を `playbooks/` の下に置くため、`ansible.cfg` の `roles_path` を `./roles` にしている。
- `group_vars/`・`host_vars/` は、インベントリ(`inventory/`)の隣に置く。グループは、機能(役割)の名前にする。
- すべての play・タスクに名前を付ける。モジュールは FQCN で書き、`state` を明示する。
- ファクトは `ansible_facts['…']` で参照する。`ansible.cfg` で `inject_facts_as_vars = False` にしているため、`ansible_distribution` のような変数名は使えない。
- OS の設定とアプリケーションの導入は、別のロールに分ける(`vm` と `vm_<サービス>`)。
- 公式の推奨から、次の点を意図的に外している。
  - `site.yml`(全体を一度に流す playbook)を置かない。実機を変更する playbook を、対象を指定して個別に実行するため。
  - Vault の変数を `group_vars` に置かず、必要な playbook だけが `vars_files` で読む(「秘密情報」を参照)。
  - 環境(本番・検証)ごとのインベントリに分けない。環境が1つのため。
  - 動的インベントリを使わない。インベントリが VM の宣言元で、VM はそこから作るため。

## 命名

| 対象 | 規則 | 例 |
| --- | --- | --- |
| ロール | `<ドメイン>` が基底、`<ドメイン>_<名前>` が実装。ドメインは `pve` / `vm` / `k8s` | `pve_vm`、`vm_k3s`、`k8s_cert_manager` |
| ロールの変数 | ドメイン接頭辞を落とした名前で始める。例外: `pve_vm` は `vm` ドメインの `vm_*` と衝突するため `pve_vm_*` | `vm_k3s` のロール変数は `k3s_*` |
| インベントリのグループ | ロールまたはサービスの名前 | `k3s`、`core` |
| ホスト名 | グループ名と別の名前にする(同名だと Ansible が警告する) | グループ `k3s` にホスト `k3s01` |
| インベントリのファイル | `inventory/hosts/<VLAN番号>_<名前>.yml` | `21_k3s.yml` |
| Vault の変数 | `vault_<サービス>_<用途>` | `vault_cloudflare_api_token` |

VLAN・ID・VMID・IP の規則は [design/network.md](design/network.md) に書く。

## 変数の層

値は次の順に重なり、後ろが優先される。層をまたいで同じ値を繰り返さない。

1. `roles/*/defaults/main.yml`: すべての既定値。既定値の単一の置き場所
2. `inventory/group_vars/`: 既定値との差分だけ
3. `inventory/hosts/`・`inventory/host_vars/`: ホストごとの値
4. `-e`: 最優先

導出できる値(VMID・IP・ゲートウェイ・VLANタグ)は、`vlan` と `id` から導出する。手で書かない。他のホストのインベントリで定義済みのIPをハードコードせず、`hostvars` を参照する。

## ドキュメント

- 使い方は、そのディレクトリの `README.md` に書く(目的・前提・使い方・設計へのリンク)。設計の理由と未決は `docs/design/` に置く。
- 変数の一覧は README に写さない。`defaults/main.yml` と `meta/argument_specs.yml` が唯一の置き場で、README は `ansible-doc -t role <ロール>` を案内する。
- 実装のないロール・ディレクトリには、README を置かない。実装するときに書く。
- 決定が変わったら、`docs/design/` と該当ディレクトリの README を同じ変更で直す。

## 冪等性

- 2回目の実行は `changed=0` になる。
- `shell` / `command` は最後の手段にする。使うときは `creates` か状態確認を付け、`changed_when` を書く。
- ランダム値・時刻に依存する値を、そのままテンプレートへ展開しない。
- サービスの再起動は、変更があったときだけ行う(ハンドラを使う)。
- サービス自身が持つ設定(アプリの設定ファイル・状態)は上書きしない。

## コメント

コメントとドキュメントには、目的だけを書く。「以前は〜だった」「〜から変更した」といった履歴や、作業の報告、判断の経緯は書かない。lint の抑制は1行で理由を書く。

## 秘密情報

- 秘密情報は `vault/*.yml` に暗号化して置く。ファイル名はサービス名にする(`vault/proxmox.yml`)。パスワードは1つを共有する(`ANSIBLE_VAULT_PASSWORD_FILE`)。
- vault は、必要な playbook だけが `vars_files` で明示的に読み込む。`group_vars` には置かない(秘密を必要な playbook にだけ渡すため)。
- SSH の秘密鍵も `vault/` に暗号化して置く(開発マシンの `~/.ssh` に依存しない)。
- vault のパスワードは、開発マシン以外にも控えを持つ(パスワードマネージャなど)。失うと vault は復号できない。
- Kubernetes への接続も kubeconfig を使わず、vault のトークンで行う([design/k8s.md](design/k8s.md))。
- 編集は `ansible-vault edit` で行う。
- playbook がロールへ通常の変数として渡す。秘密情報を扱うタスクには `no_log` を付ける。
- 平文のトークン・パスワード・秘密鍵・kubeconfig をコミットしない。

## バージョン管理

- コレクションは `collections/requirements.yml` に範囲指定で固定する。
- コンテナイメージ・Helm チャート・k3s などのバージョンは、ロールの `defaults/main.yml`(`<サービス>_version`)にだけ書く。テンプレートに直接書かない。
- Python のツールは開発コンテナ(`.devcontainer/devcontainer.json`)で導入する。

## 注意点

- `-e key=value` は空白で分割される。複数行や空白を含む値は、JSON(`-e '{"key": "..."}'`)か `-e @file.json` で渡す。
- 現在の ansible-core では、`regex_search` に group 引数を渡すと、一致しないときに例外になる。`regex_replace` を `is search` で守る。
- ツールの非対話シェルから `ansible-playbook` を実行すると、`Ansible requires blocking IO` で止まる。`2>&1 | cat` を付けて出力をパイプに通す。`ansible-vault` は、標準エラーをファイルへ逃がす(`2>ファイル`)。
- Jinja の文字列リテラルの中の `'\1'` は `chr(1)` になる。後方参照を使う式は、YAML のブロックスカラー(`>-`)の中に書く。

## Git

- コミットメッセージは、`git log` の書き方に合わせた日本語の1行にする。
- `vault/*.yml` は `.gitattributes` で `-text -diff -merge` にしている。競合は、テキストをマージせず、再暗号化で解消する。
