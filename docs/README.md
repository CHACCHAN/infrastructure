# ドキュメント

このリポジトリのドキュメントは **playbooks/ と同じディレクトリ構成**で置かれている(1 playbook = 1ページ)。まず各ドメインのREADMEで全体像を掴み、playbookごとのページで実行方法・変数・AWX設定を確認する。

## ドメイン別

| ドメイン | 入口 | 内容 |
| --- | --- | --- |
| ① Proxmox操作(pve) | [pve/README.md](pve/README.md) | VMの宣言的な構築・電源・削除・テンプレート(API経由) |
| ② VMセットアップ(vm) | [vm/README.md](vm/README.md) | VMの中身(OS設定・Docker・サービス)をSSHで構築 |
| ③ Kubernetes(k8s) | [k8s/README.md](k8s/README.md) | k3sクラスタ上の全アプリを宣言的に収束 |
| AWX | [utils/awx/README.md](utils/awx/README.md) | Web UIからの実行の前提とSurvey設計(設定を収束させるplaybookも utils/awx/) |
| 単発ツール(utils) | [utils/README.md](utils/README.md) | APIを叩く単発ツール集(utils/awx/=AWX設定収束・Job操作、utils/authentik/=ユーザー管理) |

## 実行方式は二本立て

すべてのplaybookは**同じ変数名**で2通りに実行できる(実装は分岐していない):

| 方式 | 使いかた | 変数の出どころ |
| --- | --- | --- |
| **インベントリ実行** | `ansible-playbook playbooks/<domain>/<name>.yml` | `inventory/hosts.yml`(識別)+ `group_vars/`(スペック)+ `vault/`(機密)の3層 |
| **直接実行** | 同じコマンドに `-e target= -e profile= -e vmid= ...` を足す(AWXではSurveyに回答する) | extra vars(最優先)。仕組みは [pve/adhoc.md](pve/adhoc.md) |

extra vars(`-e` / AWX Survey / Job Templateの変数欄)はAnsibleの変数優先度で最も強く、インベントリの宣言をいつでも上書きできる。「インベントリで再現し、`-e` で実験する」が基本の使い分け。

## そのほかの参照先

- ネットワーク構成・サービス公開経路の全体像: [infrastructure.md](../infrastructure.md)
- 設計思想(3層構造・冪等性・ドメイン分離): [README.md](../README.md)
- 変数の既定値の正: `roles/*/defaults/main.yml`(ドキュメントには書き写さない方針)

## 雛形(default.md / default.yml)

新しいページやplaybookを足すときは、同じディレクトリの雛形をコピーして書き換える。雛形は見出しの順序・節の名前・書きかたの決まりを持つ。

| 置き場所 | 雛形 | 使うとき |
| --- | --- | --- |
| `docs/<ドメイン>/` | `default.md` | playbookのページを追加する(utils は `docs/utils/default.md` を `utils/<サービス>/` のページに使う) |
| `docs/` | [default.md](default.md) | ドメインの入口ページ(README.md)を追加する |
| `playbooks/<ドメイン>/` | `default.yml` | playbookを追加する(utils は `playbooks/utils/default.yml` を `utils/<サービス>/` に使う) |
| `roles/` | [default.yml](../roles/default.yml) | ロールを追加する(ディレクトリ構成と命名も記載) |
| `inventory/group_vars/` | [default.yml](../inventory/group_vars/default.yml) | 役割グループのプロファイルを追加する |
| `awx/` | [default.yml](../awx/default.yml) | Job Template等の定義を追加する |
| `vault/` | [default.yml](../vault/default.yml) | 暗号化ファイルを追加する(コピー後に暗号化する) |

共通の決まり:

- **文章もコメントも説明だけを書く**(判断の経緯・変更の過程は書かない)
- `##` 見出しは雛形の名称・順序のまま使い、固有の話題は `###` で書く
- 既定値はコードが正で、ドキュメントへ書き写さない
- 雛形はプレースホルダを含むため `.ansible-lint` の `exclude_paths` に登録する
