# k3s_litellm

LiteLLM Proxy(LLM API のゲートウェイ)を Helm で入れる。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

## 使い方

`playbooks/k3s/litellm.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_litellm` と `defaults/main.yml`。

前提: CloudNativePG のオペレーターが入っている(`playbooks/k3s/cnpg.yml`)。専用の PostgreSQL(namespace `litellm-db`)は、このロールが [k3s_postgresql](../k3s_postgresql/README.md) で作る。

モデルの追加とプロバイダーの認証情報の登録は、管理画面(`https://<litellm_host>/ui`。Authentik の SSO でログインする)で登録する。Hermes Agent が使うモデルの名前は `hermes_llm` にする。宣言で持ちたいモデルは、`litellm_models`(プロキシの `model_list`)と `vault_litellm_provider_keys`(環境変数名をキーにした辞書)でも足せる。

## 注意

- `litellm_values.proxy_config.litellm_settings.drop_params` を有効にし、接続先モデルが対応しないパラメーターを除外する。この基盤設定とチャートの版は `playbooks/k3s/litellm.yml` で適用する。管理 API 用の `litellm_manage.yml` では適用しない。

- 管理画面は Authentik の SSO でログインする。グループ `litellm_admin_group`(既定は `admins`)のユーザーが管理者(`proxy_admin`)になる。管理画面を使えるユーザーを管理者だけに絞るのは、Authentik の画面で、LiteLLM のアプリケーションにそのグループを結びつけて行う。
- 緊急用の管理者(`litellm_ui_username`、パスワードは `vault_litellm_ui_password`)は、`https://<litellm_host>/fallback/login` からパスワードでログインする。
- Pod が受ける通信は、同じ namespace、Traefik、インベントリの `helm_network_policies` の `litellm` に挙げた namespace(OpenWebUI)に絞る。OpenWebUI からは、クラスタ内の Service(`http://litellm.<namespace>.svc.cluster.local:4000`)へ直接つなげる。
- マスターキー(`vault_litellm_master_key`)は API の鍵で、管理画面のログインには使えない。
- 管理画面で登録したモデル・認証情報・仮想キーは DB に保存される。管理対象の既存モデルと仮想キーの設定は、下記の専用 playbook で管理する。
- 認証情報は `vault_litellm_salt_key` で暗号化される。モデルを登録したあとにこのキーを変えると、登録済みの認証情報が読めなくなる。

## 管理 API で設定を管理する

[inventory/group_vars/litellm.yml](../../inventory/group_vars/litellm.yml)で、サービスのホスト名・Helm の上書き・モデル・キーの利用範囲を編集する。モデルは既存の ID、ルーティンググループ(router 設定の `routing_groups`。自動ルーターの段階の向け先も含む)はグループ名、キーは論理名で識別する。ルーティンググループは宣言したものだけを置き換え、宣言していないグループと並び順は保つ。LiteLLM は `priority` 以外のグループどうしで同じモデルを共有できないため、共有するグループ(自動ルーターの判定用の `*-judge` など)は `priority` にし、均等に振り分けるときは優先度をすべて同じ値にする。フォールバック(router 設定の `fallbacks`)は、元のルーティンググループ名をキーにし、失敗したときに順に試すグループを並べる。自動ルーターでは、選ばれた段階のグループ名(`cc-complex` など)のフォールバックが使われる。宣言したキーだけを置き換え、ほかのフォールバックは保つ。元と先は、どちらも存在するルーティンググループにする。モデルの ID とキーの論理名は保持する。宣言した設定を画面で変えても、次の適用で inventory の値に戻る。

キーのハッシュ・発行時に保存したキー本体・非公開のメタデータは [vault/litellm_keys.yml](../../vault/litellm_keys.yml) に暗号化して保管する。公開設定と非公開設定に同じ項目を重複して宣言すると停止する。既存キーの本体はハッシュから復元できない。

```sh
ansible-playbook playbooks/k3s/litellm_manage.yml --check --diff 2>&1 | cat
ansible-playbook playbooks/k3s/litellm_manage.yml 2>&1 | cat
```

変更対象の件数と、モデル ID・ルーティンググループ名(フォールバックの元を含む)・キーの論理名、変更する項目名を確認できる。設定値・キー本体・ハッシュは表示しない。更新するのは既存モデルの宣言した接続設定、宣言したルーティンググループ(モデルの更新のあと、管理画面と同じ `/config/update` で router 設定の `routing_groups` と `fallbacks` のうち変わったものだけを送る)と、キーの許可モデル・予算・レート制限など。未指定の設定と使用量・期限は保つ。キーの発行・削除・利用停止・再発行は、この通常適用では行わない。管理対象から外しても削除しない。対象が見つからない、設定に `null` がある、キーの操作が処理中の場合は停止する。

モデル更新に認証情報・ヘッダー・API のマスク文字列は指定できない。認証情報を含む URL は inventory に置かない。名前付き認証情報が解決する接続先は画面側との二重管理を避ける。変数と許可する項目は `defaults/main.yml` と `meta/argument_specs.yml` の `manage` を参照する。

処理は管理 API の読み取り → 差分計算 → 部分更新 → 再取得・確認。`--check` は読み取りと計算だけを行う。通常適用は冪等で、差分がなければ `changed=0`。API の更新は複数の対象をまたいだトランザクションではない。途中で停止したら原因を直して再実行する。戻すときは inventory を戻し、チェックしてから再適用する。

## キーの発行・利用停止・ローテーション

`playbooks/utils/litellm_key.yml` を通常の適用とは別に実行する。対象の論理名と操作を指定し、実行前に確認値を「論理名/操作」の形で渡す。

```sh
ansible-playbook playbooks/utils/litellm_key.yml --check -e litellm_key_name=client_01 -e litellm_key_action=block 2>&1 | cat
ansible-playbook playbooks/utils/litellm_key.yml -e litellm_key_name=client_01 -e litellm_key_action=block -e litellm_key_confirm=client_01/block 2>&1 | cat
```

操作は `create`(発行)、`block`(利用停止)、`unblock`(再開)、`rotate`(新キーの準備)、`retire`(配布済みの旧キー停止)。新規発行する場合は、先に inventory へキーの論理名・表示名・許可モデルなどを宣言する。発行するキーは LLM 呼び出し用にし、空の許可モデル一覧は全モデルを許可する LiteLLM の仕様に従う。発行時の表示名には世代ごとのサフィックスを付け、旧キーと新キーの表示名が重複しないようにする。既存の登録があれば `create` は再発行しない。停止・再開も状態が同じなら何もしない。`rotate` は新しいキーを別に発行して台帳の現行キーにし、旧キーを配布完了まで残す。旧キーの停止が終わるまで、次のローテーションは拒否する。配布後に同じ論理名で `retire` を実行し、旧キーを停止する。これらは通常の反復適用とは別の操作にする。

発行・交換の秘密は、API 操作前に台帳へ暗号化して保存する。通信失敗や最後の保存失敗では処理中の秘密が残り、同じ論理名・操作で再実行すると同じ秘密で回復する。処理中の操作を別の操作で上書きしない。処理中の台帳を通常適用が使おうとした場合は停止する。台帳の排他ロックが残った場合は、ほかの実行が動いていないことを確認してから `<台帳ファイル>.lock` を取り除く。

キー本体は `ansible-vault edit vault/litellm_keys.yml` で確認し、利用サービスへ手動で配布する。新キーへ利用サービスの設定を更新してから、確認値を `client_01/retire` として `retire` を実行する。旧キーはその操作まで使える。新キーは別キーとして利用量と予算が数えられるため、切り替え中の利用と予算は両方を確認する。Enterprise 専用の再発行 API は使わない。配布の自動化は行わない。削除 API は使わず、利用停止では履歴と台帳を保つ。チェックモードではキーの生成・ファイル保存・API 更新を行わない。

## 参照用の取得記録

```sh
ansible-playbook playbooks/utils/litellm_export.yml 2>&1 | cat
```

取得結果は [vault/litellm_snapshot.yml](../../vault/litellm_snapshot.yml) だけに保存する。既にファイルがある場合、置き換えるときだけ `-e litellm_export_overwrite=true` を指定する。inventory・キー台帳は読み書きしない。取得記録を通常適用の入力にはしない。

画面で追加したモデルやルーティンググループを管理対象にするときは、別の保存先を指定して取得記録を暗号化し、既存の ID・モデル名・グループ名・許可された非機密の設定だけを inventory へ追加する。取得記録には router 設定も含む。取得結果からキー本体やプロバイダー認証情報を完全には復元できず、DB の保護を代替しない。

取得値に Jinja の区切り文字(`{{`・`{%`・`{#`)があれば保存前に停止する。手で宣言を編集するときも区切り文字を入れない。API の版によっては取得記録に秘密が含まれるため、ファイル全体を秘密情報として扱う。接続は LAN/VPN 用の HTTPS とし、TLS を検証する。Pod 内の実行と DB の直接操作は行わない。ローカル実行の一時領域は `/dev/shm` に置く。
