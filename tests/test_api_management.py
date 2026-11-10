"""管理 API の差分と表示内容を、架空のデータだけで検証する。"""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "api_management", Path(__file__).resolve().parents[1] / "filter_plugins/api_management.py"
)
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)


class ApiManagementTests(unittest.TestCase):
    def test_model_patch_preserves_boolean_and_excludes_credentials(self):
        before = [{"model_name": "model", "model_info": {"id": "id"}, "litellm_params": {
            "model": "provider/model", "timeout": 20, "api_key": "secret-test-value", "use_litellm_proxy": True}}]
        desired = [{"model_name": "model", "model_info": {"id": "id"}, "litellm_params": {"timeout": 30}}]
        original = copy.deepcopy(before)
        result = API.litellm_model_plan(desired, before)
        self.assertEqual(result["changes"][0]["litellm_params"], {"timeout": 30, "use_litellm_proxy": True})
        self.assertEqual(result["summary"], [{"id": "id", "fields": ["litellm_params.timeout"]}])
        self.assertNotIn("secret-test-value", json.dumps(result))
        self.assertEqual(before, original)
        before[0]["litellm_params"]["timeout"] = 30
        self.assertEqual(API.litellm_model_plan(desired, before)["changes"], [])

    def test_model_rename_does_not_expose_names_or_values(self):
        before = [{"model_name": "old", "model_info": {"id": "id"}, "litellm_params": {"use_litellm_proxy": True}}]
        desired = [{"model_name": "private-new-name", "model_info": {"id": "id"}, "litellm_params": {}}]
        result = API.litellm_model_plan(desired, before)
        self.assertEqual(result["summary"], [{"id": "id", "fields": ["model_name"]}])
        self.assertNotIn("private-new-name", json.dumps(result["summary"]))
        self.assertTrue(result["changes"][0]["litellm_params"]["use_litellm_proxy"])

    def test_routing_groups_replace_declared_and_keep_others(self):
        before = [
            {"group_name": "ui-only", "models": ["x"], "routing_strategy": "priority", "routing_strategy_args": None},
            {"group_name": "tier", "models": ["a"], "routing_strategy": "simple-shuffle", "routing_strategy_args": None},
        ]
        desired = [{"group_name": "tier", "models": ["a", "b"], "routing_strategy": "simple-shuffle"}]
        original = copy.deepcopy(before)
        result = API.litellm_routing_group_plan(desired, before)
        self.assertEqual(result["changes"]["routing_groups"], [
            {"group_name": "ui-only", "models": ["x"], "routing_strategy": "priority"},
            {"group_name": "tier", "models": ["a", "b"], "routing_strategy": "simple-shuffle"},
        ])
        self.assertEqual(result["summary"], [{"group_name": "tier", "fields": ["models"]}])
        self.assertEqual(before, original)
        before[1]["models"] = ["a", "b"]
        self.assertEqual(API.litellm_routing_group_plan(desired, before), {"changes": {}, "summary": []})

    def test_routing_groups_reject_shared_models_outside_priority(self):
        before = [
            {"group_name": "one", "models": ["a"], "routing_strategy": "priority"},
            {"group_name": "two", "models": ["a"], "routing_strategy": "priority"},
        ]
        shuffled = [{"group_name": "one", "models": ["a"], "routing_strategy": "simple-shuffle"}]
        self.assertEqual(len(API.litellm_routing_group_plan(shuffled, before)["summary"]), 1)
        both = shuffled + [{"group_name": "two", "models": ["a"], "routing_strategy": "simple-shuffle"}]
        with self.assertRaises(API.AnsibleFilterError):
            API.litellm_routing_group_plan(both, before)

    def test_routing_groups_reject_missing_or_duplicate_names(self):
        group = {"group_name": "tier", "models": ["a"], "routing_strategy": "priority"}
        with self.assertRaises(API.AnsibleFilterError):
            API.litellm_routing_group_plan([group], None)
        with self.assertRaises(API.AnsibleFilterError):
            API.litellm_routing_group_plan([group, group], [group])

    def test_fallbacks_replace_declared_and_keep_other_routes(self):
        groups = [{"group_name": name} for name in ("a", "b", "c")]
        before = [{"c": ["a"]}, {"model-x": ["model-y"], "extra": []}, {"a": ["c"]}]
        original = copy.deepcopy(before)
        result = API.litellm_fallback_plan([{"a": ["b"]}, {"b": ["a", "c"]}], before, groups)
        self.assertEqual(result["changes"]["fallbacks"], [
            {"c": ["a"]}, {"model-x": ["model-y"], "extra": []}, {"a": ["b"]}, {"b": ["a", "c"]}])
        self.assertEqual(result["summary"], [
            {"group_name": "a", "fields": ["fallbacks"]}, {"group_name": "b", "fields": ["fallbacks"]}])
        self.assertEqual(before, original)
        self.assertEqual(API.litellm_fallback_plan([{"c": ["a"]}], before, groups), {"changes": {}, "summary": []})
        self.assertEqual(API.litellm_fallback_plan([], None, groups), {"changes": {}, "summary": []})

    def test_fallbacks_reject_invalid_declarations(self):
        groups = [{"group_name": name} for name in ("a", "b")]
        for desired in ([{"a": ["b"], "b": ["a"]}], [{"a": ["b"]}, {"a": ["b"]}], [{"a": []}],
                        [{"a": ["a"]}], [{"a": "b"}], [{"a": ["missing"]}], [{"missing": ["a"]}]):
            with self.assertRaises(API.AnsibleFilterError):
                API.litellm_fallback_plan(desired, [], groups)

    def test_resolve_keys_preserves_precedence_alias_and_inputs(self):
        desired = [
            {"name": "client", "settings": {"key_alias": "client", "models": ["model"]}},
            {"name": "other", "settings": {"rpm_limit": 10}},
        ]
        material = {
            "client": {"hash": "a" * 64, "alias_suffix": "a" * 12,
                       "settings": {"metadata": {"private": "secret"}}},
            "other": {"hash": "b" * 64, "settings": {"rpm_limit": 20}},
        }
        original = copy.deepcopy((desired, material))
        result = API.litellm_resolve_keys(desired, material)
        self.assertEqual(result, [
            {"name": "client", "key": "a" * 64, "settings": {
                "key_alias": "client-" + "a" * 12, "models": ["model"], "metadata": {"private": "secret"}}},
            {"name": "other", "key": "b" * 64, "settings": {"rpm_limit": 20}},
        ])
        self.assertEqual((desired, material), original)
        self.assertEqual(API.litellm_resolve_keys([], material), [])

    def test_resolve_keys_rejects_duplicate_hash_and_missing_material_without_values(self):
        desired = [{"name": name, "settings": {}} for name in ("private-client", "private-other")]
        material = {name: {"hash": "a" * 64} for name in ("private-client", "private-other")}
        for registry in (material, {}):
            with self.assertRaises(API.AnsibleFilterError) as caught:
                API.litellm_resolve_keys(desired, registry)
            for private in ("private-client", "private-other", "a" * 64):
                self.assertNotIn(private, str(caught.exception))

    def test_key_plan_rejects_multiple_declarations_for_same_hash(self):
        desired = [{"name": name, "key": "a" * 64, "settings": {"rpm_limit": limit}}
                   for name, limit in (("first", 10), ("second", 20))]
        with self.assertRaises(API.AnsibleFilterError):
            API.litellm_key_plan(desired, [{"token": "a" * 64, "rpm_limit": 5}])

    def test_key_policy_preserves_counters_expiry_and_activation(self):
        desired = [{"name": "client", "key": "a" * 64, "settings": {"rpm_limit": 10, "metadata": {"private": "secret"}}}]
        before = [{"token": "a" * 64, "rpm_limit": 5, "metadata": {}, "spend": 100, "blocked": True, "expires": "2030-01-01"}]
        result = API.litellm_key_plan(desired, before)
        self.assertEqual(set(result["changes"][0]), {"key", "rpm_limit", "metadata"})
        self.assertEqual(result["summary"], [{"name": "client", "fields": ["metadata", "rpm_limit"]}])
        self.assertNotIn("secret", json.dumps(result["summary"]))
        self.assertNotIn("a" * 64, json.dumps(result["summary"]))

    def test_authentik_patch_omits_provider_and_permissions(self):
        desired = [{"slug": "app", "settings": {"name": "new", "open_in_new_tab": True}}]
        before = [{"slug": "app", "name": "old", "open_in_new_tab": True, "provider": 12, "policy_engine_mode": "all"}]
        result = API.authentik_application_plan(desired, before)
        self.assertEqual(result["changes"], [{"slug": "app", "settings": {"name": "new"}}])
        self.assertEqual(result["summary"], [{"slug": "app", "fields": ["name"]}])
        before[0]["name"] = "new"
        self.assertEqual(API.authentik_application_plan(desired, before)["changes"], [])

    def test_missing_or_duplicate_identity_fails_without_private_values(self):
        desired = [{"slug": "private-slug", "settings": {"name": "private-value"}}]
        for before in [[], [{"slug": "private-slug"}, {"slug": "private-slug"}]]:
            with self.assertRaises(API.AnsibleFilterError) as caught:
                API.authentik_application_plan(desired, before)
            self.assertNotIn("private-slug", str(caught.exception))
            self.assertNotIn("private-value", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
