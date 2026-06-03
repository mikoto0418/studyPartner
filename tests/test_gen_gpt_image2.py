import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "gen_gpt_image2(2).py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("gen_gpt_image2", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BaseUrlResolutionTest(unittest.TestCase):
    def test_env_base_url_is_used_when_cli_value_is_missing(self):
        module = load_script_module()

        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://example.test/v1/"}, clear=True):
            self.assertEqual(module.resolve_base_url(None), "https://example.test/v1")

    def test_cli_base_url_overrides_environment(self):
        module = load_script_module()

        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://example.test/v1"}, clear=True):
            self.assertEqual(module.resolve_base_url("https://cli.test/v1/"), "https://cli.test/v1")

    def test_generation_url_is_built_from_resolved_base_url(self):
        module = load_script_module()

        self.assertEqual(
            module.build_generation_url("https://example.test/v1/"),
            "https://example.test/v1/images/generations",
        )


class ApiKeyResolutionTest(unittest.TestCase):
    def test_env_api_key_is_used_when_cli_value_is_missing(self):
        module = load_script_module()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}, clear=True):
            self.assertEqual(module.resolve_api_key(None), "env-key")

    def test_cli_api_key_overrides_environment(self):
        module = load_script_module()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}, clear=True):
            self.assertEqual(module.resolve_api_key("cli-key"), "cli-key")


if __name__ == "__main__":
    unittest.main()
