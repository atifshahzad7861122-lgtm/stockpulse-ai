"""Phase 2 real-data adapter layer (PHASE2_DESIGN.md §1)."""

from app.adapters.base import (
    AdapterHealth,
    CollectionContext,
    RawRecord,
    SourceAdapter,
    StoredResult,
)
from app.adapters.normalized import (
    MarketMetricInput,
    NormalizedSignal,
    PrivateSignalInput,
    TrendSignalInput,
)
from app.adapters.registry import ADAPTERS, get_adapter, get_all_adapter_types
from app.adapters.store import store_normalized_signals

__all__ = [
    "ADAPTERS",
    "AdapterHealth",
    "CollectionContext",
    "MarketMetricInput",
    "NormalizedSignal",
    "PrivateSignalInput",
    "RawRecord",
    "SourceAdapter",
    "StoredResult",
    "TrendSignalInput",
    "get_adapter",
    "get_all_adapter_types",
    "store_normalized_signals",
]
