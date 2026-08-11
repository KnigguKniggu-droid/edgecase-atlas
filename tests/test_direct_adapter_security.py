from __future__ import annotations

import pytest

from edgecase_atlas.adapters import OpenAICompatibleAdapter


def test_direct_adapter_rejects_literal_looking_api_key_reference() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleAdapter(
            base_url="https://models.invalid/v1",
            model="target",
            api_key_env="literal-secret-value!",
            network_enabled=False,
        )
