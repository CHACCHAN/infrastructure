# users.yml — Authentikのユーザーとグループ所属を収束させる

Authentik REST API(`/api/v3/core/users/` ほか)でユーザーを作成し、任意でグループへ追加する。**単一ユーザーと複数ユーザーの一括作成**の両方に対応する。

## 冪等性(何度実行しても安全)

- **既存ユーザーは作り直さない**(名前・メールも上書きしない。作成のみ)
- **グループ追加は所属済みでも安全**(Authentik APIの `add_user` が冪等)
- **グループ未指定(空)ならユーザー作成のみ**行う
- **パスワードは新規作成したユーザーにだけ設定**する(既存ユーザーのパスワードは変えない)
- 指定されたグループが存在しない場合は**何も変更する前に**一覧つきで停止する(グループは作成しない)

## 実行方法

```sh
# 単一ユーザー(グループなし=作成のみ)
ansible-playbook playbooks/utils/authentik/users.yml -e username=taro

# 単一ユーザー+グループ+初期パスワード
ansible-playbook playbooks/utils/authentik/users.yml \
  -e username=taro -e display_name="Taro Yamada" -e email=taro@example.com \
  -e user_groups=developers,ops -e user_password='S3cret-Pass123'

# 複数ユーザーの一括作成(ファイルで渡す)
ansible-playbook playbooks/utils/authentik/users.yml -e @users.yml
```

一括作成のファイル書式(`users.yml`。**リポジトリにはコミットしない**こと):

```yaml
authentik_users:
  - username: taro          # 必須
    name: "Taro Yamada"     # 任意(未指定ならusername)
    email: taro@example.com # 任意
    groups: [developers, ops]  # 任意。空/未指定ならユーザー作成のみ
    password: "S3cret-Pass123" # 任意。新規作成時のみ設定される
  - username: hanako
    groups: developers      # カンマ区切り文字列でもよい
  - username: jiro          # 作成のみ(グループ・パスワードなし)
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `username` | str | ✔(単一時) | | ユーザー名(英数字と `@ . + _ -`、150文字以内) |
| `display_name` | str | | username | 表示名(APIの `name`) |
| `email` | str | | なし | メールアドレス |
| `user_groups` | str/list | | なし | 所属グループ(カンマ区切り or リスト)。**変数名が `groups` でないのはAnsibleのマジック変数と衝突するため** |
| `user_password` | str | | なし | 初期パスワード(新規作成時のみ設定) |
| `authentik_users` | list | ✔(一括時) | | 上記書式のユーザーのリスト(単一指定と併用も可) |

vault変数(`ansible-vault edit vault/authentik.yml`):

| 変数 | 内容 |
| --- | --- |
| `vault_authentik_host` | AuthentikのURL(例 `https://auth.cc-chacchan.com`) |
| `vault_authentik_api_token` | APIトークン。Authentik管理画面 → Directory → Tokens で intent=API を発行 |

## AWXでの実行

Job Template **`utils-authentik-users`**。Surveyは単一ユーザー向け(`username` / `display_name` / `email` / `user_groups` / `user_password`)。一括作成はSurveyではなく**変数欄**に `authentik_users:` のYAMLを書く。

## つまずきやすいポイント

- **「存在しないグループ」で止まる** → グループはこのツールでは作成しない。Authentik側(Directory → Groups)で先に作る
- **パスワードが変わらない** → 仕様(新規作成時のみ)。既存ユーザーはAuthentikのWeb UIかリカバリーフローで変更する
- **APIの失敗詳細が見えない** → トークンを含むためAPI呼び出しは `no_log`。直後のassertがHTTP状態と応答JSON(トークンを含まない)だけを表示する
- トークンを漏らした・チャットや画面に貼った場合は Directory → Tokens で**失効させて発行し直し**、`ansible-vault edit vault/authentik.yml` で入れ替える
