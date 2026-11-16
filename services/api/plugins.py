"""Domain-neutral extension contract; plugins supply data, never bypass eligibility gates.

Register independently tested official-data adapters here as coverage grows.
No placeholder adapter is advertised as a working external integration.
"""

from typing import Protocol, TypedDict


class Observation(TypedDict):
    value: float | str
    unit: str
    observed_at: str
    published_at: str
    source_url: str
    source_name: str


class DataVerifier(Protocol):
    domain: str

    async def observe(self, subject: str, metric: str, period: str) -> list[Observation]: ...


REGISTRY: dict[str, DataVerifier] = {}


def register(plugin: DataVerifier):
    if plugin.domain in REGISTRY:
        raise ValueError("领域插件已经注册。")
    REGISTRY[plugin.domain] = plugin
