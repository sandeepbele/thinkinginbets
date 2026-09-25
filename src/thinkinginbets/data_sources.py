"""Data-source capability checks without exposing secrets."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DataSourceStatus:
    name: str
    credential_env_vars: tuple[str, ...]
    credential_status: str
    supports_live: bool
    supports_historical_replay: bool
    notes: str


def data_source_statuses(environ: dict[str, str] | None = None) -> list[DataSourceStatus]:
    env = environ if environ is not None else dict(os.environ)
    return [
        _status(
            "statsbomb_open_data",
            (),
            True,
            True,
            "No credentials needed for public open-data matches; event timelines can be replayed.",
            env,
        ),
        _status(
            "wyscout_public_dataset",
            (),
            False,
            True,
            "No credentials expected for the public Figshare dataset; download/replay, not live stream.",
            env,
        ),
        _status(
            "espn_public_scoreboard",
            (),
            True,
            True,
            "No credentials needed; undocumented public endpoint, so archive raw snapshots.",
            env,
        ),
        _status(
            "kalshi",
            ("KALSHI_API_KEY_ID", "KALSHI_PRIVATE_KEY_PATH"),
            True,
            True,
            "Credentials needed for authenticated trading/user streams; public/historical access varies by endpoint.",
            env,
        ),
        _status(
            "polymarket",
            ("POLYMARKET_API_KEY", "POLYMARKET_API_SECRET", "POLYMARKET_API_PASSPHRASE"),
            True,
            True,
            "Credentials needed for authenticated order activity; public market data may not require them.",
            env,
        ),
        _status(
            "predexon",
            ("PREDEXON_API_KEY",),
            False,
            True,
            "Optional third-party historical orderbook source; validate coverage before relying on it.",
            env,
        ),
    ]


def _status(
    name: str,
    env_vars: tuple[str, ...],
    supports_live: bool,
    supports_historical_replay: bool,
    notes: str,
    environ: dict[str, str],
) -> DataSourceStatus:
    if not env_vars:
        credential_status = "not_required"
    elif all(environ.get(env_var) for env_var in env_vars):
        credential_status = "present"
    elif any(environ.get(env_var) for env_var in env_vars):
        credential_status = "partial"
    else:
        credential_status = "missing"

    return DataSourceStatus(
        name=name,
        credential_env_vars=env_vars,
        credential_status=credential_status,
        supports_live=supports_live,
        supports_historical_replay=supports_historical_replay,
        notes=notes,
    )
