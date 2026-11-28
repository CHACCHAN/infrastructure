"""LiteLLM の仮想キーの宣言と管理 API の現在値を比較し、更新値と秘密を含まない項目一覧を返す。"""

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


class FilterModule:
    """Ansible へ副作用のない差分フィルターを登録する。"""

    def filters(self):
        return {
            "litellm_resolve_keys": litellm_resolve_keys,
            "litellm_key_plan": litellm_key_plan,
        }
