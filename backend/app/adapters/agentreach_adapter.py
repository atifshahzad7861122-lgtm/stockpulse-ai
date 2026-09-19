"""Agent-Reach adapter (source_types: ``agentreach_web``, ``v2ex``, ``xueqiu``).

Wraps the real no-auth agent-reach v1.5.0 Python methods (source-verified
2026-09-19):
  - ``WebChannel().read(url)`` — Jina Reader fetch of a URL (returns markdown str)
  - ``V2EXChannel().get_hot_topics()``
  - ``XueqiuChannel().get_hot_stocks()`` / ``get_hot_posts()`` / ``get_stock_quote()``
  - RSS via ``feedparser`` directly (rss_adapter)
  - Health: ``check_all(Config(read_only=True))`` → per-channel
    {status: ok|warn|off|error, message, ...} (NO ready/needs_auth — we map
    them ourselves).

NOTE (install): PyPI currently serves agent-reach 0.1.0 (installer-only,
channels: rss/youtube). The v1.5.0 inspected at /tmp/agent-reach was
installed from that source tree. If the installed package lacks these
classes, the adapter reports UNAVAILABLE with the reason — never crashes.

Guarded import: adapter imports and reports UNAVAILABLE when agent-reach
is missing; never crashes app startup.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.adapters.base import (
    AdapterHealth,
    CollectionContext,
    RawRecord,
    SourceAdapter,
)
from app.adapters.normalized import TrendSignalInput
from app.schemas.enums import DataProvenance, SourceStatus

logger = logging.getLogger(__name__)


class AgentReachAdapter(SourceAdapter):
    source_type = "agentreach_web"

    @property
    def dependency(self) -> str:
        return "agent_reach"

    # Curated trend article URLs fetched via Jina Reader (web channel).
    DEFAULT_URLS = [
        "https://blog.adobe.com/en/topics/adobe-stock",
        "https://www.petapixel.com/",
    ]

    def _import_channels(self):
        from agent_reach.channels.web import WebChannel

        return WebChannel

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        available, reason = self.dependency_available()
        if not available:
            logger.warning("agentreach collect skipped: %s", reason)
            return []
        try:
            WebChannel = self._import_channels()
            channel = WebChannel()
        except Exception as exc:
            logger.warning("WebChannel unavailable: %s", exc)
            return []
        records: list[RawRecord] = []
        urls = ctx.queries or self.DEFAULT_URLS
        for url in urls[: ctx.limit]:
            try:
                text = channel.read(url)
            except Exception as exc:
                logger.warning("WebChannel.read failed for %s: %s", url, exc)
                continue
            if isinstance(text, dict):
                title = text.get("title") or url
                body = text.get("content") or text.get("markdown") or str(text)
            else:
                title = url
                body = str(text or "")
            records.append(
                RawRecord(
                    source_type=self.source_type,
                    title=title,
                    body=body[:4000] or None,
                    url=url,
                    published_at=datetime.now(UTC),
                    extra={"channel": "web"},
                )
            )
        return records

    def normalize(self, records: list[RawRecord]) -> list[TrendSignalInput]:
        signals: list[TrendSignalInput] = []
        for rec in records:
            signals.append(
                TrendSignalInput(
                    signal_name=rec.title[:200],
                    description=(rec.body or "")[:2000] or None,
                    metric_name="channel_mentions",
                    metric_value=1.0,
                    metric_unit="mentions",
                    observed_at=datetime.now(UTC),
                    provenance=DataProvenance.THIRD_PARTY,
                    confidence=0.45,
                    collection_method="agent_reach_channel",
                    data_timestamp=rec.published_at,
                    raw_reference={"url": rec.url, "channel": rec.extra.get("channel")},
                )
            )
        return signals

    @staticmethod
    def _channel_statuses() -> dict[str, dict] | None:
        """Run check_all and return per-channel rows, or None on failure."""
        from agent_reach.config import Config
        from agent_reach.doctor import check_all

        result = check_all(Config(read_only=True))
        return result if isinstance(result, dict) else None

    @staticmethod
    def _map_health(statuses: dict | None) -> tuple[SourceStatus, str]:
        """Map check_all rows ({channel: {status, message}}) → SourceStatus.

        check_all statuses: ok|warn|off|error (no ready/needs_auth — we map).
        warn with an auth hint (认证/登录/auth/cookie/token/login) → NEEDS_AUTH,
        other warn → TEMP_FAILING.
        """
        if not statuses:
            return SourceStatus.TEMP_FAILING, "check_all returned no statuses"
        flat: dict[str, str] = {}
        messages: dict[str, str] = {}
        for channel, row in statuses.items():
            if isinstance(row, dict):
                flat[channel] = str(row.get("status", "off")).lower()
                messages[channel] = str(row.get("message", ""))
            else:
                flat[channel] = str(row).lower()
        values = list(flat.values())
        if all(v == "ok" for v in values):
            return SourceStatus.AVAILABLE, "all channels ok"
        if any(v == "error" for v in values):
            bad = [c for c, v in flat.items() if v == "error"]
            return SourceStatus.TEMP_FAILING, f"channel errors: {', '.join(bad)}"
        warns = [c for c, v in flat.items() if v == "warn"]
        if warns:
            auth_hint = any(
                kw in messages[c].lower()
                for c in warns
                for kw in ("认证", "登录", "auth", "cookie", "token", "login", "sign in")
            )
            status = SourceStatus.NEEDS_AUTH if auth_hint else SourceStatus.TEMP_FAILING
            return status, f"channels warn: {', '.join(warns)}"
        if all(v == "off" for v in values):
            return SourceStatus.UNAVAILABLE, "all channels off"
        return SourceStatus.TEMP_FAILING, f"mixed statuses: {flat}"

    def get_status(self) -> AdapterHealth:
        available, reason = self.dependency_available()
        if not available:
            return AdapterHealth(
                status=SourceStatus.UNAVAILABLE,
                detail=f"agent-reach not installed: {reason}",
            )
        try:
            statuses = self._channel_statuses()
            # This adapter drives the Jina "web" channel; map only that row.
            web_row = (statuses or {}).get("web")
            if web_row is None:
                return AdapterHealth(
                    status=SourceStatus.UNAVAILABLE,
                    detail="web channel missing from check_all output",
                )
            status, detail = self._map_health({"web": web_row})
            return AdapterHealth(status=status, detail=f"web: {detail}")
        except Exception as exc:
            return AdapterHealth(
                status=SourceStatus.TEMP_FAILING,
                detail=f"health check failed: {exc}",
                last_error=str(exc),
            )


class _SubChannelAdapter(AgentReachAdapter):
    """Base for v2ex / xueqiu sub-channels of the same adapter family."""

    channel_name: str = ""

    def get_status(self) -> AdapterHealth:
        available, reason = self.dependency_available()
        if not available:
            return AdapterHealth(
                status=SourceStatus.UNAVAILABLE,
                detail=f"agent-reach not installed: {reason}",
            )
        try:
            statuses = self._channel_statuses()
            row = (statuses or {}).get(self.channel_name)
            flat = {"_": row}
            # Reuse the mapping on a single-channel view.
            status, detail = self._map_health(
                {self.channel_name: row} if row is not None else None
            )
            if status == SourceStatus.AVAILABLE and not flat:
                status = SourceStatus.UNAVAILABLE
            return AdapterHealth(
                status=status,
                detail=f"{self.channel_name}: {detail}",
            )
        except Exception as exc:
            return AdapterHealth(
                status=SourceStatus.TEMP_FAILING,
                detail=f"health check failed: {exc}",
                last_error=str(exc),
            )


class V2EXAdapter(_SubChannelAdapter):
    """V2EX hot topics via V2EXChannel().get_hot_topics() (no auth)."""

    source_type = "v2ex"
    channel_name = "v2ex"

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        available, reason = self.dependency_available()
        if not available:
            logger.warning("v2ex collect skipped: %s", reason)
            return []
        try:
            from agent_reach.channels.v2ex import V2EXChannel

            topics = V2EXChannel().get_hot_topics(limit=ctx.limit) or []
        except Exception as exc:
            logger.warning("V2EXChannel failed: %s", exc)
            return []
        records = []
        for t in topics[: ctx.limit]:
            if isinstance(t, dict):
                title, url = t.get("title"), t.get("url")
            else:
                title, url = str(t), None
            records.append(
                RawRecord(
                    source_type=self.source_type,
                    title=title or "V2EX hot topic",
                    url=url,
                    published_at=datetime.now(UTC),
                    extra={"channel": "v2ex"},
                )
            )
        return records


class XueqiuAdapter(_SubChannelAdapter):
    """Xueqiu hot stocks/posts via XueqiuChannel (no auth)."""

    source_type = "xueqiu"
    channel_name = "xueqiu"

    def collect(self, ctx: CollectionContext) -> list[RawRecord]:
        available, reason = self.dependency_available()
        if not available:
            logger.warning("xueqiu collect skipped: %s", reason)
            return []
        try:
            from agent_reach.channels.xueqiu import XueqiuChannel

            channel = XueqiuChannel()
        except Exception as exc:
            logger.warning("XueqiuChannel unavailable: %s", exc)
            return []
        records = []
        try:
            stocks = channel.get_hot_stocks(limit=ctx.limit) or []
        except Exception as exc:
            logger.warning("xueqiu get_hot_stocks failed: %s", exc)
            stocks = []
        for s in stocks:
            name = s.get("name") if isinstance(s, dict) else str(s)
            code = s.get("code") if isinstance(s, dict) else None
            records.append(
                RawRecord(
                    source_type=self.source_type,
                    title=f"Xueqiu hot stock: {name}" + (f" ({code})" if code else ""),
                    published_at=datetime.now(UTC),
                    extra={"channel": "xueqiu_hot_stocks", "code": code},
                )
            )
            if len(records) >= ctx.limit:
                break
        if len(records) < ctx.limit:
            try:
                posts = channel.get_hot_posts(limit=ctx.limit - len(records)) or []
            except Exception as exc:
                logger.warning("xueqiu get_hot_posts failed: %s", exc)
                posts = []
            for p in posts:
                title = p.get("title") if isinstance(p, dict) else str(p)
                records.append(
                    RawRecord(
                        source_type=self.source_type,
                        title=title or "Xueqiu hot post",
                        published_at=datetime.now(UTC),
                        extra={"channel": "xueqiu_hot_posts"},
                    )
                )
        return records


__all__ = ["AgentReachAdapter", "V2EXAdapter", "XueqiuAdapter"]
