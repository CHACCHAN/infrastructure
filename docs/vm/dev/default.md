# dev/<playbook名>.yml — <開発VMに対して何をするか>

<!--
このディレクトリ(②VMセットアップドメインの開発VM向け)のページはこのテンプレートに従う。
- 1ページ = 1playbook。ファイル名はplaybookと同名
- `##` 見出しは下記の名称・順序のまま使う。該当しない節だけ丸ごと削除し、固有の話題は該当する `##` の下に `###` で書く
- 文章もコメントも「説明」だけを書く。判断の経緯・変更の過程は書かない
- 変数の既定値の正は roles/vm_dev/defaults/main.yml と inventory/group_vars/dev.yml
- 新規追加時は docs/vm/README.md のplaybook一覧にも1行足す
-->

<概要。2〜4文で「何をするplaybookか」「対象(devグループ全台か1台か)」を書く。>

## 実行方法

```sh
# インベントリ実行(devグループ全台)
ansible-playbook playbooks/vm/dev/<playbook名>.yml

# 1台に絞る
ansible-playbook playbooks/vm/dev/<playbook名>.yml -l <ホスト名>
```

## 変数一覧

接続系の共通変数は [../README.md](../README.md#共通の変数)。全既定値の正は [roles/vm_dev/defaults/main.yml](../../../roles/vm_dev/defaults/main.yml)。

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `<変数>` | <型> | | `<既定値>` | <説明> |

## AWXでの実行

Job Template **`vm-dev-<名前>`**(定義: [awx/job_templates.yml](../../../awx/job_templates.yml))。<Surveyの構成と注意点。>

## つまずきやすいポイント

- **<症状>** → <原因と対処>
