# ssh_key.yml — 鍵を本文で渡すための前処理

秘密鍵を**本文**で受け取ったとき(`pve_ssh_prikey_value`)に、SSHが使える0600の一時ファイルへ書き出す部品。各サービスplaybookが先頭でimportするため**単体では実行しない**。

## なぜ必要か

AWXのSurveyはファイル入力に対応していない。鍵をパスで置けない実行環境では、**鍵の本文をそのまま入れる変数**を代わりに使う。

| ファイルで渡す(既定) | 本文で渡す | 中身 |
| --- | --- | --- |
| `pve_ssh_pubkey_file` | `pve_ssh_pubkey_value` | cloud-initがVMに登録する公開鍵 |
| `pve_ssh_prikey_file` | `pve_ssh_prikey_value` | AnsibleがVMへSSHする秘密鍵 |

**本文が入っていればファイル指定より優先される**ため、`group_vars/<役割>.yml` の宣言は書き換えなくてよい。

公開鍵はcloud-initへ文字列のまま渡せるが、秘密鍵はSSHクライアントが**ファイルしか受け付けない**。そこでこのplaybookが `~/.ansible/pve_ssh_keys/<鍵本文のSHA1>` へ0600で書き出し、接続にはそれを指す `pve_ssh_prikey_resolved` を使う。本文を渡さなければ何もしない(`changed=0`)。

**改行の自動復元**: AWX SurveyのPassword型は1行入力欄のため、貼り付けた鍵の改行が失われて届くことがある(そのままでは `invalid format` でSSHが拒否する)。このplaybookはヘッダ/フッタとbase64本体からPEM構造を自動復元するため、**そのまま貼り付ければよい**。改行が保たれている鍵は無変換で通り、鍵の形式でない入力は書き出す前に日本語メッセージで停止する。

## 実行方法

単体実行はしない。各playbookから自動で呼ばれる。手元から本文で渡す場合:

```sh
# コマンドラインから渡すときはJSONで。-e key=value は複数行が1行目で切れる
ansible-playbook playbooks/vm/wg-easy.yml -e @keys.json
```

```json
{
  "pve_ssh_pubkey_value": "ssh-ed25519 AAAA... comment",
  "pve_ssh_prikey_value": "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----\n"
}
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `pve_ssh_prikey_value` | str | | なし | 秘密鍵の本文。空なら何もしない |
| `pve_ssh_prikey_tmpfile` | str | | `~/.ansible/pve_ssh_keys/<SHA1>` | 書き出し先(自動導出。鍵の内容から名前が決まるため並列実行でも衝突しない) |

## AWXでの扱い

- Surveyの `pve_ssh_prikey_value` は**暗号化された質問(Password型)**として全VM系Job Templateに定義済み([awx/job_templates.yml](../../awx/job_templates.yml))
- パスフレーズ付きの秘密鍵は非対話で解錠できないため使えない
- AWXの **Machine Credential はこのリポジトリではそのままでは効かない**。playbookが `ansible_user` / `ansible_ssh_private_key_file` をplay変数で指定しており、Credentialが渡すコマンドラインオプションより優先されるため(この設計を維持しているのは、鍵の受け渡し経路をSurvey/vaultに一本化するため)

## つまずきやすいポイント

- **`-l` と併用しない**: このプレイはlocalhostで動くため、Limitで除外されると一時ファイルが作られず後段の接続が失敗する。絞り込みは `-e target=`
- **書き出した秘密鍵は実行後も残る**: AWXは実行環境コンテナごと破棄されるが、手元で試したときは `~/.ansible/pve_ssh_keys/` を消す
