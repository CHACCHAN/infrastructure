# docs

人間とAIエージェントの両方が読む資料の案内。[AGENTS.md](../AGENTS.md) はここにあるファイルを import して参照する。

- **使い方**は、各ディレクトリの `README.md` に書く(何をするか、前提、実行順、実行例)。
- **設計**は、`docs/design/` に書く(決定済み・未決、理由、複数の領域にまたがる話)。

## 領域ごとの案内

| 領域 | 使い方 | 設計 |
| --- | --- | --- |
| Proxmox のテンプレートと VM | [playbooks/pve](../playbooks/pve/README.md)、[roles/pve_template](../roles/pve_template/README.md)、[roles/pve_vm](../roles/pve_vm/README.md) | [design/pve.md](design/pve.md) |
| ホストの宣言 | [inventory](../inventory/README.md) | [design/network.md](design/network.md) |
| 秘密情報 | [vault](../vault/README.md) | [conventions.md](conventions.md) |
| k3s クラスタ | (実装後に追加) | [design/k3s.md](design/k3s.md) |
| クラスタ内アプリ | (実装後に追加) | [design/k8s.md](design/k8s.md) |
| 物理ノード | | [design/hardware.md](design/hardware.md) |

## 全体の規則

| ファイル | 内容 |
| --- | --- |
| [conventions.md](conventions.md) | 命名規則・変数の層・冪等性・Vault・バージョン管理 |

## 書き方

- 決定済みの事項と未決の事項を分けて書く。未決の事項は、決めた根拠が揃うまでコードに反映しない。
- 決定が変わったら、関連するドキュメントと、そのディレクトリの `README.md` を同じ変更で更新する。
- README には使い方だけを書き、設計の理由と未決は `docs/design/` に置く。変数の一覧は写さない(`defaults/main.yml` と `meta/argument_specs.yml` が唯一の置き場)。
- 旧構成(`legacy/`)の値は、新しい構成の根拠として書かない。
