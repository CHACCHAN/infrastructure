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
