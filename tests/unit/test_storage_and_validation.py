"""Unit tests for raw storage, dataset validation, repository and providers."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from backtesting_cripto.domain.exceptions import DataValidationError
from backtesting_cripto.domain.models import IndicatorValue, PriceBar
from backtesting_cripto.providers import (
    alternative_me_fng,
    bgeometrics_fng,
    bitstamp_ohlc,
)
from backtesting_cripto.storage.raw_store import RawStore, compute_sha256
from backtesting_cripto.storage.repository import (
    BacktestRepository,
    MemoryIndicatorSeries,
    MemoryPriceSeries,
)
from backtesting_cripto.validation.dataset_checks import (
    FEAR_GREED_FIRST_DAY,
    PRICES_FIRST_DAY,
    validate_fear_greed_series,
    validate_price_bars,
)


def make_bar(day: date, *, close: str = "105.00") -> PriceBar:
    return PriceBar(
        asset="BTC",
        quote="EUR",
        day=day,
        open=Decimal("100.00"),
        high=Decimal("110.00"),
        low=Decimal("90.00"),
        close=Decimal(close),
        volume=Decimal("10.5"),
        source="bitstamp",
    )


def make_fng_value(day: date, value: int = 37) -> IndicatorValue:
    return IndicatorValue(
        indicator="fear_greed", day=day, value=Decimal(value), source="bgeometrics"
    )


def day_range(start: date, end: date) -> list[date]:
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


# --- RawStore -----------------------------------------------------------------


def test_raw_store_saves_file_and_manifest_entry(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    store = RawStore(tmp_path)
    payload = b'{"sample": true}'

    entry = store.save(
        dataset_id="fear_greed_bgeometrics",
        source="bgeometrics",
        url="https://charts.bgeometrics.com/files/fear_greed.json",
        payload=payload,
        first_day="2018-02-01",
        last_day="2024-01-01",
        record_count=100,
        license="CC BY 4.0",
    )

    assert entry.sha256 == compute_sha256(payload)
    assert entry.record_count == 100
    assert entry.license == "CC BY 4.0"
    assert (tmp_path / entry.relative_path).read_bytes() == payload

    manifest = store.load_manifest()
    assert len(manifest) == 1
    assert manifest[0] == entry


def test_raw_store_manifest_contains_required_fields(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    store = RawStore(tmp_path)
    store.save(
        dataset_id="ds1",
        source="src",
        url="https://example.com/data.json",
        payload=b"{}",
        first_day="2018-02-01",
        last_day="2024-01-01",
        record_count=7,
        license="MIT",
    )
    manifest_json = json.loads(store.manifest_path.read_text(encoding="utf-8"))
    entry = manifest_json["datasets"][0]
    assert set(entry) == {
        "id",
        "source",
        "url",
        "retrieved_at",
        "sha256",
        "first_day",
        "last_day",
        "record_count",
        "license",
        "relative_path",
    }


def test_raw_store_is_idempotent_for_identical_content(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    store = RawStore(tmp_path)
    payload = b'{"same": 1}'

    first = store.save(
        dataset_id="ds1",
        source="src",
        url="https://example.com",
        payload=payload,
        first_day="2018-02-01",
        last_day="2024-01-01",
        record_count=1,
        license="MIT",
    )
    second = store.save(
        dataset_id="ds1",
        source="src",
        url="https://example.com",
        payload=payload,
        first_day="2018-02-01",
        last_day="2024-01-01",
        record_count=1,
        license="MIT",
    )

    assert first.relative_path == second.relative_path
    assert len(store.load_manifest()) == 1
    assert len(list((tmp_path / "src").glob("*.json"))) == 1


def test_raw_store_never_overwrites_with_different_content(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    store = RawStore(tmp_path)

    first = store.save(
        dataset_id="ds1",
        source="src",
        url="https://example.com",
        payload=b'{"version": 1}',
        first_day="2018-02-01",
        last_day="2024-01-01",
        record_count=1,
        license="MIT",
    )
    second = store.save(
        dataset_id="ds1",
        source="src",
        url="https://example.com",
        payload=b'{"version": 2}',
        first_day="2018-02-01",
        last_day="2024-02-01",
        record_count=2,
        license="MIT",
    )

    assert first.relative_path != second.relative_path
    assert (tmp_path / first.relative_path).read_bytes() == b'{"version": 1}'
    assert (tmp_path / second.relative_path).read_bytes() == b'{"version": 2}'
    assert len(store.load_manifest()) == 2


def test_raw_store_dataset_hash_is_deterministic(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    store_a = RawStore(tmp_path / "a")
    store_b = RawStore(tmp_path / "b")
    for store in (store_a, store_b):
        store.save(
            dataset_id="ds1",
            source="src",
            url="https://example.com",
            payload=b'{"x": 1}',
            first_day="2018-02-01",
            last_day="2024-01-01",
            record_count=1,
            license="MIT",
        )

    assert store_a.dataset_hash() == store_b.dataset_hash()

    store_b.save(
        dataset_id="ds2",
        source="src",
        url="https://example.com",
        payload=b'{"x": 2}',
        first_day="2018-02-01",
        last_day="2024-02-01",
        record_count=1,
        license="MIT",
    )
    assert store_a.dataset_hash() != store_b.dataset_hash()


def test_raw_store_latest_entry(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    store = RawStore(tmp_path)
    store.save(
        dataset_id="ds1",
        source="src",
        url="https://example.com",
        payload=b'{"v": 1}',
        first_day="2018-02-01",
        last_day="2024-01-01",
        record_count=1,
        license="MIT",
    )
    store.save(
        dataset_id="ds1",
        source="src",
        url="https://example.com",
        payload=b'{"v": 2}',
        first_day="2018-02-01",
        last_day="2024-06-01",
        record_count=2,
        license="MIT",
    )
    latest = store.latest_entry("ds1")
    assert latest is not None
    assert latest.last_day == "2024-06-01"


# --- dataset_checks -----------------------------------------------------------


def test_validate_fear_greed_accepts_series_with_gaps() -> None:
    days = [FEAR_GREED_FIRST_DAY, FEAR_GREED_FIRST_DAY + timedelta(days=2)]
    values = [make_fng_value(day) for day in days]
    validate_fear_greed_series(values, last_closed_day=days[-1])


def test_validate_fear_greed_rejects_wrong_first_day() -> None:
    values = [make_fng_value(date(2018, 2, 2))]
    with pytest.raises(DataValidationError, match="first day"):
        validate_fear_greed_series(values, last_closed_day=date(2018, 2, 2))


def test_validate_fear_greed_rejects_duplicates() -> None:
    day = FEAR_GREED_FIRST_DAY
    values = [make_fng_value(day), make_fng_value(day)]
    with pytest.raises(DataValidationError, match="duplicated"):
        validate_fear_greed_series(values, last_closed_day=day)


def test_validate_fear_greed_rejects_days_after_last_closed() -> None:
    values = [make_fng_value(date(2018, 2, 1)), make_fng_value(date(2018, 2, 2))]
    with pytest.raises(DataValidationError, match="last closed day"):
        validate_fear_greed_series(values, last_closed_day=date(2018, 2, 1))


def test_validate_fear_greed_rejects_out_of_range_value() -> None:
    bad = IndicatorValue.model_construct(
        indicator="fear_greed",
        day=FEAR_GREED_FIRST_DAY,
        value=Decimal("150"),
        source="bgeometrics",
    )
    with pytest.raises(DataValidationError, match="out of"):
        validate_fear_greed_series([bad], last_closed_day=FEAR_GREED_FIRST_DAY)


def test_validate_fear_greed_rejects_empty_series() -> None:
    with pytest.raises(DataValidationError, match="empty"):
        validate_fear_greed_series([], last_closed_day=date(2024, 1, 1))


def test_validate_price_bars_accepts_continuous_series() -> None:
    days = day_range(PRICES_FIRST_DAY, PRICES_FIRST_DAY + timedelta(days=4))
    bars = [make_bar(day) for day in days]
    validate_price_bars(bars, last_closed_day=days[-1])


def test_validate_price_bars_rejects_gap() -> None:
    days = [
        PRICES_FIRST_DAY,
        PRICES_FIRST_DAY + timedelta(days=1),
        PRICES_FIRST_DAY + timedelta(days=3),
    ]
    bars = [make_bar(day) for day in days]
    with pytest.raises(DataValidationError, match="missing"):
        validate_price_bars(bars, last_closed_day=days[-1])


def test_validate_price_bars_rejects_duplicates() -> None:
    day = PRICES_FIRST_DAY
    bars = [make_bar(day), make_bar(day)]
    with pytest.raises(DataValidationError, match="duplicated"):
        validate_price_bars(bars, last_closed_day=day)


def test_validate_price_bars_rejects_late_first_day() -> None:
    bars = [make_bar(date(2018, 1, 2))]
    with pytest.raises(DataValidationError, match="first day"):
        validate_price_bars(bars, last_closed_day=date(2018, 1, 2))


def test_validate_price_bars_rejects_bars_after_last_closed() -> None:
    bars = [make_bar(date(2018, 1, 1)), make_bar(date(2018, 1, 2))]
    with pytest.raises(DataValidationError, match="last closed day"):
        validate_price_bars(bars, last_closed_day=date(2018, 1, 1))


# --- Repository and series protocols ------------------------------------------


def populate_repository(repo: BacktestRepository, dataset_id: str = "d1") -> None:
    repo.upsert_dataset(
        dataset_id=dataset_id,
        source="bitstamp",
        url="https://example.com",
        retrieved_at="2024-01-01T00:00:00+00:00",
        sha256="abc123",
        first_day=date(2018, 1, 1),
        last_day=date(2018, 1, 3),
        record_count=3,
        license="MIT",
    )
    bars = [make_bar(day, close="105.00") for day in day_range(date(2018, 1, 1), date(2018, 1, 3))]
    repo.replace_price_bars(dataset_id=dataset_id, bars=bars)
    repo.replace_indicator_values(
        dataset_id=dataset_id,
        values=[
            make_fng_value(date(2018, 1, 1), 42),
            make_fng_value(date(2018, 1, 3), 8),
        ],
    )


def test_repository_round_trip_price_series(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    with BacktestRepository(tmp_path / "test.sqlite3") as repo:
        populate_repository(repo)
        series = repo.price_series(asset="BTC", quote="EUR")

        assert series.date_bounds() == (date(2018, 1, 1), date(2018, 1, 3))
        assert series.bar_on(date(2018, 1, 2)) is not None
        assert series.bar_on(date(2018, 1, 2)).close == Decimal("105.00")
        assert series.bar_on(date(2017, 12, 31)) is None
        assert series.last_close_on_or_before(date(2018, 1, 5)).day == date(2018, 1, 3)
        assert series.last_close_on_or_before(date(2017, 12, 31)) is None


def test_repository_preserves_decimal_precision_as_text(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    precise = Decimal("105.12345678")
    with BacktestRepository(tmp_path / "test.sqlite3") as repo:
        repo.upsert_dataset(
            dataset_id="d1",
            source="bitstamp",
            url="https://example.com",
            retrieved_at="2024-01-01T00:00:00+00:00",
            sha256="abc",
            first_day=date(2018, 1, 1),
            last_day=date(2018, 1, 1),
            record_count=1,
            license="MIT",
        )
        repo.replace_price_bars(
            dataset_id="d1", bars=[make_bar(date(2018, 1, 1), close="105.12345678")]
        )
        series = repo.price_series(asset="BTC", quote="EUR")
        bar = series.bar_on(date(2018, 1, 1))
        assert bar is not None
        assert bar.close == precise


def test_repository_indicator_series(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    with BacktestRepository(tmp_path / "test.sqlite3") as repo:
        populate_repository(repo)
        series = repo.indicator_series(indicator="fear_greed")

        assert series.date_bounds() == (date(2018, 1, 1), date(2018, 1, 3))
        assert series.value_on(date(2018, 1, 1)) == Decimal("42")
        assert series.value_on(date(2018, 1, 2)) is None
        assert series.value_on(date(2018, 1, 3)) == Decimal("8")


def test_repository_uses_latest_dataset_by_default(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    with BacktestRepository(tmp_path / "test.sqlite3") as repo:
        populate_repository(repo, dataset_id="old")
        populate_repository(repo, dataset_id="new")
        series = repo.price_series(asset="BTC", quote="EUR")
        assert series.date_bounds() == (date(2018, 1, 1), date(2018, 1, 3))


def test_memory_series_last_close_skips_gaps() -> None:
    bars = [make_bar(date(2018, 1, 1)), make_bar(date(2018, 1, 4))]
    series = MemoryPriceSeries.from_bars(bars)
    assert series.last_close_on_or_before(date(2018, 1, 3)).day == date(2018, 1, 1)
    assert series.bar_on(date(2018, 1, 3)) is None


def test_memory_indicator_series_from_values() -> None:
    values = [make_fng_value(date(2018, 1, 1), 10), make_fng_value(date(2018, 1, 2), 20)]
    series = MemoryIndicatorSeries.from_values(values)
    assert series.value_on(date(2018, 1, 2)) == Decimal("20")
    assert series.value_on(date(2018, 1, 9)) is None


# --- Provider parsers (no network) --------------------------------------------


def _utc_timestamp_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def test_bgeometrics_parser_builds_utc_days() -> None:
    payload = json.dumps(
        [[_utc_timestamp_ms(date(2018, 2, 1)), 37], [_utc_timestamp_ms(date(2018, 2, 2)), 100]]
    ).encode()
    values = bgeometrics_fng.parse_payload(payload)

    assert len(values) == 2
    assert values[0].day == date(2018, 2, 1)
    assert values[0].value == Decimal("37")
    assert values[0].source == "bgeometrics"
    assert values[1].value == Decimal("100")


def test_bgeometrics_parser_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="list"):
        bgeometrics_fng.parse_payload(b'{"not": "a list"}')


def test_alternative_me_parser_builds_utc_days() -> None:
    payload = json.dumps(
        {
            "data": [
                {"timestamp": str(_utc_timestamp_ms(date(2018, 2, 1)) // 1000), "value": "42"},
                {"timestamp": str(_utc_timestamp_ms(date(2018, 2, 2)) // 1000), "value": "9"},
            ]
        }
    ).encode()
    values = alternative_me_fng.parse_payload(payload)

    assert len(values) == 2
    assert values[0].day == date(2018, 2, 1)
    assert values[0].value == Decimal("42")
    assert values[0].source == "alternative.me"


def test_alternative_me_parser_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="data"):
        alternative_me_fng.parse_payload(b'{"unexpected": true}')


def _bitstamp_page(days: list[date]) -> bytes:
    ohlc = [
        {
            "timestamp": str(int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())),
            "open": "100.00",
            "high": "110.00",
            "low": "90.00",
            "close": "105.00",
            "volume": "10.5",
        }
        for d in days
    ]
    return json.dumps({"data": {"ohlc": ohlc}}).encode()


def _fake_bitstamp_get_bytes(url: str, *, timeout: int = 30) -> bytes:
    """Emulate Bitstamp: at most PAGE_DAYS candles ending at ``end`` (start ignored)."""
    params = parse_qs(urlparse(url).query)
    end = datetime.fromtimestamp(int(params["end"][0]), tz=UTC).date()
    start = end - timedelta(days=bitstamp_ohlc.PAGE_DAYS - 1)
    return _bitstamp_page(day_range(start, end))


def test_bitstamp_parser_builds_price_bars() -> None:
    payload = _bitstamp_page([date(2018, 1, 1), date(2018, 1, 2)])
    bars = bitstamp_ohlc.parse_payload(payload)

    assert len(bars) == 2
    assert bars[0].asset == "BTC"
    assert bars[0].quote == "EUR"
    assert bars[0].day == date(2018, 1, 1)
    assert bars[0].close == Decimal("105.00")
    assert bars[0].source == "bitstamp"


def test_bitstamp_fetch_bars_paginates_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bitstamp_ohlc, "get_bytes", _fake_bitstamp_get_bytes)

    start_day = date(2020, 1, 1)
    end_day = date(2023, 12, 31)  # more than PAGE_DAYS, forces several pages
    bars = bitstamp_ohlc.fetch_bars(start_day, end_day)

    assert [bar.day for bar in bars] == day_range(start_day, end_day)


def test_bitstamp_fetch_pages_do_not_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bitstamp_ohlc, "get_bytes", _fake_bitstamp_get_bytes)

    pages = bitstamp_ohlc.fetch_pages(date(2020, 1, 1), date(2023, 12, 31))
    assert len(pages) > 1

    all_days = [bar.day for _payload, page_bars in pages for bar in page_bars]
    assert len(all_days) == len(set(all_days))

    page_first_days = [min(bar.day for bar in page_bars) for _payload, page_bars in pages]
    assert page_first_days == sorted(page_first_days, reverse=True)


def test_bitstamp_fetch_bars_filters_out_of_window_days(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_bytes(url: str, *, timeout: int = 30) -> bytes:
        params = parse_qs(urlparse(url).query)
        end = datetime.fromtimestamp(int(params["end"][0]), tz=UTC).date()
        start = end - timedelta(days=bitstamp_ohlc.PAGE_DAYS - 1)
        # Simulate an API that also returns the still-open candle (end + 1).
        return _bitstamp_page(day_range(start, end + timedelta(days=1)))

    monkeypatch.setattr(bitstamp_ohlc, "get_bytes", fake_get_bytes)

    bars = bitstamp_ohlc.fetch_bars(date(2024, 1, 1), date(2024, 1, 3))
    assert [bar.day for bar in bars] == day_range(date(2024, 1, 1), date(2024, 1, 3))
