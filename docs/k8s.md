# ③ Kubernetes適用ドメイン(k8s)

`kubernetes/` のKustomizeマニフェストを**Ansible経由でserver-side apply**するドメイン。マニフェスト自体の構成・追加手順は [kubernetes/README.md](../kubernetes/README.md) が正で、このドメインは「見る・流す」の入口を担う。

> **将来**: マニフェストはAnsibleロール(`k8s_<app>`)へ完全移行し、Kustomizeは解体する予定。現在のplaybookはその橋渡し。

## 全体像

```mermaid
flowchart LR
    K["kubernetes/<br>kustomization.yaml"] -->|kustomize lookup<br>(手元でレンダリング)| A["playbooks/k8s/apply.yml"]
    V["kubernetes/vault/<br>Secret(git追跡外)"] -->|存在チェック付き| AV["playbooks/k8s/apply-vault.yml"]
    A & AV -->|server-side apply<br>field_manager: kubectl| C["k3sクラスタ"]
```

## コマンド

```sh
# 差分を見る(クラスタに触らない)
ansible-playbook playbooks/k8s/apply.yml --check --diff

# 適用する(収束済みなら changed=0)
ansible-playbook playbooks/k8s/apply.yml

# フィールド所有権の衝突時のみ(下記参照)
ansible-playbook playbooks/k8s/apply.yml -e force=true

# 秘密情報(kubernetes/vault/)を適用する
ansible-playbook playbooks/k8s/apply-vault.yml --check   # --diffはSecretが平文で出るため付けない
ansible-playbook playbooks/k8s/apply-vault.yml
```

## 冪等性と所有権の設計

- **server-side apply(SSA)** で適用し、`field_manager` は `kubectl` に固定。`kubectl apply --server-side` と同じ管理者名なので、手動運用と混ざっても所有権が分裂しない
- 過去に `kubectl apply`(client-side)で適用したリソースは、所有者が `kubectl-client-side-apply` のままで `FieldManagerConflict` になることがある。**`--check --diff` で差分が実質ゼロであることを確認してから** `-e force=true` で所有権を引き継ぐ(クラスタごとに一度だけ)
- 適用後の通常運用は `changed=0` が正常

## 秘密情報(apply-vault)の注意

| 注意 | 理由 |
| --- | --- |
| 適用前に手元の `kubernetes/vault/*.yml` が稼働中より**新しい**ことを確認 | vault/はgit追跡外。古いファイルを流すと稼働中のSecretを上書きして壊す |
| `--diff` を付けない | Secretの中身が平文でログに出る |
| ルートの `kustomization.yaml` には含めない(現状維持) | `apply.yml` の通常適用で秘密情報が流れない分離を保つ |
