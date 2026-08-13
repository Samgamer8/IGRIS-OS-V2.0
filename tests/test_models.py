import pytest

from igris_os.models import ModelProvider, ProviderKind, ProviderRegistry, default_providers


def test_default_is_local_only():
    assert [p.name for p in default_providers().available()] == ["ollama"]


@pytest.mark.parametrize(("kind", "endpoint"), [
    (ProviderKind.REMOTE, "http://example.com"),
    (ProviderKind.LOCAL, "http://192.168.1.2:11434"),
])
def test_unsafe_provider_is_rejected(kind, endpoint):
    with pytest.raises(ValueError):
        ProviderRegistry().register(ModelProvider("unsafe", kind, endpoint))
