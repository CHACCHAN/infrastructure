# <playbook名>.yml — <クラスタ上の何を収束させるか>

<!--
このディレクトリ(③Kubernetesドメイン)のページはこのテンプレートに従う。
- 1ページ = 1playbook。ファイル名はplaybookと同名
- 見出しは下記の順序・名称を変えない。該当しない節だけ丸ごと削除する
- 文章もコメントも「説明」だけを書く。判断の経緯・変更の過程は書かない
- アプリ登録簿・外部経路の宣言は inventory/group_vars/all/k8s.yml が正
- Secretの実値は vault/k8s_secrets.yml。値そのものはドキュメントに書かない
-->

<概要。2〜4文で「何を適用するか」「宣言の置き場所」「適用方式(SSA)」を書く。>

## 実行方法

```sh
# 全アプリを収束させる
ansible-playbook playbooks/k8s/<playbook名>.yml

# 1アプリだけ
ansible-playbook playbooks/k8s/<playbook名>.yml -e app=<アプリ名>

# 差分の確認だけ
ansible-playbook playbooks/k8s/<playbook名>.yml -e app=<アプリ名> --check --diff
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `<変数>` | <型> | | `<既定値>` | <説明> |

## AWXでの実行

Job Template **`k8s-<動詞>`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。<Surveyの構成と注意点。>

## つまずきやすいポイント

- **<症状>** → <原因と対処>
