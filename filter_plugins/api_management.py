"""管理 API の現在値と宣言を比較し、更新値と秘密を含まない項目一覧を返す。"""

from ansible.errors import AnsibleFilterError


_MISSING = object()


def _index(records, identity):
    result = {}
    for record in records:
        try:
            key = identity(record)
        except (KeyError, TypeError) as exc:
            raise AnsibleFilterError("管理 API の識別子が不足しています") from exc
        if not isinstance(key, str) or key in result:
            raise AnsibleFilterError("管理 API の識別子が不正または重複しています")
        result[key] = record
    return result


def _current(index, key):
    if key not in index:
        raise AnsibleFilterError("管理対象が現在の設定に存在しません")
    return index[key]


def litellm_model_plan(desired, current):
    """未指定の真偽値を保ち、変更した接続設定だけを更新する。"""
    existing = _index(current, lambda row: row["model_info"]["id"])
    _index(desired, lambda row: row["model_info"]["id"])
    changes, summary = [], []
    for record in desired:
        model_id = record["model_info"]["id"]
        before = _current(existing, model_id)
        delta = {
            key: value
            for key, value in record["litellm_params"].items()
            if before["litellm_params"].get(key, _MISSING) != value
        }
        fields = ["litellm_params." + key for key in delta]
        if before["model_name"] != record["model_name"]:
            fields.append("model_name")
        if not fields:
            continue
        # LiteLLM の部分更新でも既定の真偽値が送られる版があるため、現在値を明示する。
        booleans = {
            key: value
            for key, value in before["litellm_params"].items()
            if isinstance(value, bool)
        }
        changes.append(
            {
                "model_name": record["model_name"],
                "litellm_params": {**booleans, **delta},
                "model_info": {"id": model_id},
            }
        )
        summary.append({"id": model_id, "fields": sorted(fields)})
    return {"changes": changes, "summary": summary}


def litellm_resolve_keys(desired, material):
    """宣言と秘密の台帳を結びつけ、同じキーへの重複した更新を拒否する。"""
    _index(desired, lambda row: row["name"])
    resolved = []
    for record in desired:
        secret = _current(material, record["name"])
        settings = {**record["settings"], **secret.get("settings", {})}
        if "alias_suffix" in secret and "key_alias" in settings:
            settings["key_alias"] = settings["key_alias"] + "-" + secret["alias_suffix"]
        resolved.append({"name": record["name"], "key": secret["hash"], "settings": settings})
    _index(resolved, lambda row: row["key"])
    return resolved


def litellm_key_plan(desired, current):
    """キーのハッシュと設定値を表示用の情報から分離する。"""
    existing = _index(current, lambda row: row["token"])
    _index(desired, lambda row: row["name"])
    _index(desired, lambda row: row["key"])
    changes, summary = [], []
    for record in desired:
        before = _current(existing, record["key"])
        delta = {
            key: value
            for key, value in record["settings"].items()
            if before.get(key, _MISSING) != value
        }
        if delta:
            changes.append({**delta, "key": record["key"]})
            summary.append({"name": record["name"], "fields": sorted(delta)})
    return {"changes": changes, "summary": summary}


def authentik_application_plan(desired, current):
    """表示設定の差分だけを作り、プロバイダーや認可の結びつけを保つ。"""
    existing = _index(current, lambda row: row["slug"])
    _index(desired, lambda row: row["slug"])
    changes, summary = [], []
    for record in desired:
        before = _current(existing, record["slug"])
        delta = {
            key: value
            for key, value in record["settings"].items()
            if before.get(key, _MISSING) != value
        }
        if delta:
            changes.append({"slug": record["slug"], "settings": delta})
            summary.append({"slug": record["slug"], "fields": sorted(delta)})
    return {"changes": changes, "summary": summary}


class FilterModule:
    """Ansible へ副作用のない差分フィルターを登録する。"""

    def filters(self):
        return {
            "litellm_model_plan": litellm_model_plan,
            "litellm_resolve_keys": litellm_resolve_keys,
            "litellm_key_plan": litellm_key_plan,
            "authentik_application_plan": authentik_application_plan,
        }
