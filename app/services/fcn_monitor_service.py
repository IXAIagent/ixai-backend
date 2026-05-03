from __future__ import annotations

import json
import math
import re
from typing import Any

from app.services.market_data.service import MarketDataService


class FCNMonitorService:
    """Realtime FCN worst-of monitor without persisting analysis results."""

    SYMBOL_FIELDS = (
        "underlying_symbols",
        "underlyings",
        "underlying_symbol",
        "symbols",
        "worst_of_symbol",
        "worst_of",
        "symbol",
    )
    FALLBACK_SYMBOL_FIELDS = ("name", "fcn_code", "code")

    INITIAL_PRICE_FIELDS = (
        "initial_prices",
        "initial_price_map",
        "initial_price_by_symbol",
        "initial_price",
        "strike_price",
        "current_price",
    )
    CURRENT_PRICE_FIELDS = (
        "current_prices",
        "current_price_map",
        "current_price_by_symbol",
        "current_price",
    )
    UNDERLYING_COLLECTION_FIELDS = (
        "underlyings",
        "underlying_positions",
        "fcn_underlyings",
    )
    KI_FIELDS = ("ki", "ki_level", "ki_ratio", "knock_in", "knock_in_level")
    KO_FIELDS = ("ko", "ko_level", "ko_ratio", "knock_out", "knock_out_level")
    STRIKE_FIELDS = ("strike", "strike_level", "strike_ratio")

    COMMENT_BY_RISK = {
        "high": "已接近或跌破 KI，需高度關注 Worst-of 標的",
        "medium": "接近風險區間，建議持續觀察",
        "low": "目前仍在安全區間",
        "unknown": "資料不足，無法判斷 FCN 風險",
    }

    def __init__(self, market_data_service: MarketDataService | None = None) -> None:
        self.market_data_service = market_data_service or MarketDataService()

    @classmethod
    def analyze_fcn(cls, fcn_position: Any) -> dict[str, Any] | None:
        return cls().analyze(fcn_position)

    def analyze(self, fcn_position: Any) -> dict[str, Any] | None:
        try:
            return self._analyze(fcn_position)
        except Exception:
            return self._unknown_analysis(fcn_position, [], "exception")

    def _analyze(self, fcn_position: Any) -> dict[str, Any] | None:
        underlyings = self.parse_underlyings(fcn_position)
        if not underlyings:
            return self._unknown_analysis(fcn_position, [], None)

        underlying_results: list[dict[str, Any]] = []
        valid_results: list[dict[str, Any]] = []
        used_sources: set[str] = set()

        for underlying in underlyings:
            symbol = underlying["symbol"]
            initial_price = self._safe_float(underlying.get("initial_price"))
            result: dict[str, Any] = {
                "symbol": symbol,
                "initial_price": self._round(initial_price),
                "current_price": None,
                "performance": None,
                "price_source": None,
            }

            if underlying.get("data_quality_warning"):
                result["data_quality_warning"] = underlying["data_quality_warning"]

            if initial_price is None:
                self._add_warning(result, "missing_initial_price")
                underlying_results.append(result)
                continue

            price_result = self._get_market_price(symbol)
            current_price = self._safe_float(self._value_from_object(price_result, ("price", "current_price")))
            if current_price is None:
                current_price = self._safe_float(price_result)
            source = str(self._value_from_object(price_result, ("source",)) or "")

            if current_price is None:
                current_price = self._safe_float(underlying.get("current_price"))
                if current_price is None:
                    self._add_warning(result, "missing_current_price")
                    underlying_results.append(result)
                    continue
                source = "manual"

            if source:
                used_sources.add(source)

            performance = (current_price - initial_price) / initial_price
            result.update({
                "symbol": symbol,
                "initial_price": self._round(initial_price),
                "current_price": self._round(current_price),
                "performance": self._round(performance),
                "price_source": source or None,
            })
            underlying_results.append(result)
            valid_results.append({
                "symbol": symbol,
                "initial_price": initial_price,
                "current_price": current_price,
                "performance": performance,
                "price_source": source or None,
            })

        if not valid_results:
            return self._unknown_analysis(
                fcn_position,
                underlying_results,
                self._price_source(used_sources),
            )

        worst = min(valid_results, key=lambda item: item["performance"])
        ki_level_pct = self._extract_level_pct(fcn_position, self.KI_FIELDS)
        ko_level_pct = self._extract_level_pct(fcn_position, self.KO_FIELDS)
        strike_level_pct = self._extract_level_pct(fcn_position, self.STRIKE_FIELDS)

        ki_barrier = self._barrier_price(worst["initial_price"], ki_level_pct)
        ko_barrier = self._barrier_price(worst["initial_price"], ko_level_pct)
        distance_to_ki = self._barrier_distance(
            worst["current_price"],
            ki_barrier,
            worst["initial_price"],
            "down",
        )
        distance_to_ko = self._barrier_distance(
            worst["current_price"],
            ko_barrier,
            worst["initial_price"],
            "up",
        )

        if distance_to_ki is None:
            distance_to_ki = self._distance_from_existing_pct(fcn_position, "distance_to_ki_pct")
        if distance_to_ko is None:
            distance_to_ko = self._distance_from_existing_pct(fcn_position, "distance_to_ko_pct")

        risk_level = self._risk_level_from_worst(worst["current_price"], ki_barrier, distance_to_ki)

        return {
            "fcn_id": getattr(fcn_position, "id", None),
            "fcn_code": getattr(fcn_position, "fcn_code", None) or getattr(fcn_position, "name", None),
            "worst_symbol": worst["symbol"],
            "worst_of": worst["symbol"],
            "worst_performance": self._round(worst["performance"]),
            "distance_to_KI": self._round(distance_to_ki),
            "distance_to_KO": self._round(distance_to_ko),
            "risk_level": risk_level,
            "ai_comment": self.COMMENT_BY_RISK[risk_level],
            "ki": self._round(self._pct_to_ratio(ki_level_pct)),
            "ko": self._round(self._pct_to_ratio(ko_level_pct)),
            "strike": self._round(self._pct_to_ratio(strike_level_pct)),
            "ki_barrier": self._round(ki_barrier),
            "ko_barrier": self._round(ko_barrier),
            "price_source": self._price_source(used_sources),
            "symbols": [underlying["symbol"] for underlying in underlyings],
            "prices": underlying_results,
            "underlying_results": underlying_results,
        }

    def parse_underlyings(self, fcn_position: Any) -> list[dict[str, Any]]:
        records = self._records_from_underlyings(getattr(fcn_position, "underlyings", None))
        if not records:
            records = self._records_from_underlyings(getattr(fcn_position, "underlying_details", None))
        if not records:
            records = [
                {"symbol": symbol}
                for symbol in self._symbols_from_fields(
                    fcn_position,
                    (
                        "underlying_symbols",
                        "underlying_symbol",
                        "symbols",
                        "worst_of_symbol",
                        "worst_of",
                        "symbol",
                    ),
                )
            ]
        if not records:
            records = [{"symbol": symbol} for symbol in self._symbols_from_fields(fcn_position, self.FALLBACK_SYMBOL_FIELDS)]

        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()

        for record in records:
            symbol = self._clean_symbol_value(record.get("symbol"))
            if not symbol or symbol in seen:
                continue

            item: dict[str, Any] = {
                "symbol": symbol,
                "initial_price": self._safe_float(record.get("initial_price")),
                "current_price": self._safe_float(record.get("current_price")),
            }
            if record.get("data_quality_warning"):
                item["data_quality_warning"] = str(record["data_quality_warning"])

            normalized.append(item)
            seen.add(symbol)

        if not normalized:
            return []

        initial_prices = self._prices_from_fields(fcn_position, [item["symbol"] for item in normalized], self.INITIAL_PRICE_FIELDS)
        current_prices = self._prices_from_fields(fcn_position, [item["symbol"] for item in normalized], self.CURRENT_PRICE_FIELDS)

        for item in normalized:
            symbol = item["symbol"]
            if item["initial_price"] is None and initial_prices.get(symbol) is not None:
                item["initial_price"] = initial_prices[symbol]
            if item["current_price"] is None and current_prices.get(symbol) is not None:
                item["current_price"] = current_prices[symbol]
            if item["initial_price"] is None:
                self._add_warning(item, "missing_initial_price")

        return normalized

    def _records_from_underlyings(self, raw_value: Any) -> list[dict[str, Any]]:
        decoded = self._decode_underlyings(raw_value)
        if decoded is None:
            return []

        if isinstance(decoded, str):
            return [
                {"symbol": symbol}
                for symbol in self._split_symbols(decoded)
            ]

        if isinstance(decoded, dict):
            if self._value_from_object(decoded, ("symbol", "ticker", "underlying_symbol")):
                record = self._record_from_underlying_item(decoded)
                return [record] if record else []

            records: list[dict[str, Any]] = []
            for symbol, value in decoded.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("symbol", symbol)
                else:
                    item = {"symbol": symbol, "initial_price": value}

                record = self._record_from_underlying_item(item)
                if record:
                    records.append(record)
            return records

        if isinstance(decoded, (list, tuple, set)):
            records: list[dict[str, Any]] = []
            for item in decoded:
                if isinstance(item, str) and re.search(r"[,/|;\s]+", item):
                    records.extend({"symbol": symbol} for symbol in self._split_symbols(item))
                    continue

                record = self._record_from_underlying_item(item)
                if record:
                    records.append(record)
            return records

        record = self._record_from_underlying_item(decoded)
        return [record] if record else []

    def _decode_underlyings(self, raw_value: Any) -> Any:
        if raw_value is None:
            return None

        if not isinstance(raw_value, str):
            return raw_value

        text = raw_value.strip()
        if not text:
            return None

        if text[0] in "[{":
            try:
                return json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                return text

        return text

    def _record_from_underlying_item(self, item: Any) -> dict[str, Any] | None:
        if isinstance(item, dict):
            symbol = self._value_from_object(item, ("symbol", "ticker", "underlying_symbol"))
            initial_price = self._value_from_object(item, ("initial_price", "initial", "initialPrice", "strike_price", "strikePrice"))
            current_price = self._value_from_object(item, ("current_price", "current", "currentPrice", "price"))
            warning = self._value_from_object(item, ("data_quality_warning", "warning"))
            record: dict[str, Any] = {
                "symbol": symbol,
                "initial_price": initial_price,
                "current_price": current_price,
            }
            if warning:
                record["data_quality_warning"] = warning
            return record

        if isinstance(item, (str, int, float)):
            return {"symbol": item}

        symbol = self._symbol_from_object(item)
        if not symbol:
            return None

        return {
            "symbol": symbol,
            "initial_price": self._value_from_object(item, ("initial_price", "initial", "strike_price")),
            "current_price": self._value_from_object(item, ("current_price", "current", "price")),
        }

    def _prices_from_fields(
        self,
        fcn_position: Any,
        symbols: list[str],
        field_names: tuple[str, ...],
    ) -> dict[str, float | None]:
        prices: dict[str, float | None] = {symbol: None for symbol in symbols}

        for field_name in field_names:
            raw_value = getattr(fcn_position, field_name, None)
            if raw_value is None:
                continue

            decoded = self._decode_underlyings(raw_value)

            if isinstance(decoded, dict):
                for key, value in decoded.items():
                    symbol = self._clean_symbol_value(key)
                    if symbol in prices:
                        prices[symbol] = self._price_from_field_value(value, field_names)
                continue

            if isinstance(decoded, (list, tuple)):
                for symbol, value in zip(symbols, decoded):
                    prices[symbol] = self._price_from_field_value(value, field_names)
                continue

            if isinstance(decoded, str) and len(symbols) > 1 and re.search(r"[,/|;\s]+", decoded):
                values = [self._price_from_field_value(part, field_names) for part in re.split(r"[,/|;\s]+", decoded)]
                for symbol, value in zip(symbols, values):
                    prices[symbol] = value
                continue

            value = self._price_from_field_value(decoded, field_names)
            if value is not None and len(symbols) == 1:
                prices[symbols[0]] = value

        return prices

    def _price_from_field_value(self, value: Any, field_names: tuple[str, ...]) -> float | None:
        if isinstance(value, dict):
            nested_value = self._value_from_object(value, field_names)
            if nested_value is not None:
                return self._safe_float(nested_value)

        return self._safe_float(value)

    def _clean_symbol_value(self, value: Any) -> str:
        symbol = str(value or "").strip().upper()
        return re.sub(r"[^A-Z0-9.\-^=]", "", symbol)

    def _add_warning(self, result: dict[str, Any], warning: str) -> None:
        existing = str(result.get("data_quality_warning") or "")
        warnings = [part.strip() for part in existing.split(";") if part.strip()]
        if warning not in warnings:
            warnings.append(warning)
        if warnings:
            result["data_quality_warning"] = "; ".join(warnings)

    def _unknown_analysis(
        self,
        fcn_position: Any,
        underlying_results: list[dict[str, Any]],
        price_source: str | None,
    ) -> dict[str, Any]:
        return {
            "fcn_id": getattr(fcn_position, "id", None),
            "fcn_code": getattr(fcn_position, "fcn_code", None) or getattr(fcn_position, "name", None),
            "worst_symbol": None,
            "worst_of": None,
            "worst_performance": None,
            "distance_to_KI": None,
            "distance_to_KO": None,
            "risk_level": "unknown",
            "ai_comment": self.COMMENT_BY_RISK["unknown"],
            "ki": self._round(self._pct_to_ratio(self._extract_level_pct(fcn_position, self.KI_FIELDS))),
            "ko": self._round(self._pct_to_ratio(self._extract_level_pct(fcn_position, self.KO_FIELDS))),
            "strike": self._round(self._pct_to_ratio(self._extract_level_pct(fcn_position, self.STRIKE_FIELDS))),
            "price_source": price_source,
            "symbols": [result["symbol"] for result in underlying_results if result.get("symbol")],
            "prices": underlying_results,
            "underlying_results": underlying_results,
        }

    def _extract_symbols(self, fcn_position: Any) -> list[str]:
        symbols = self._symbols_from_fields(fcn_position, self.SYMBOL_FIELDS)
        if not symbols:
            symbols = self._symbols_from_fields(fcn_position, self.FALLBACK_SYMBOL_FIELDS)
        return symbols

    def _symbols_from_fields(self, fcn_position: Any, field_names: tuple[str, ...]) -> list[str]:
        symbols: list[str] = []
        seen: set[str] = set()

        for field_name in field_names:
            raw_value = getattr(fcn_position, field_name, None)
            for symbol in self._split_symbols(raw_value):
                if symbol not in seen:
                    seen.add(symbol)
                    symbols.append(symbol)

        return symbols

    def _split_symbols(self, raw_value: Any) -> list[str]:
        if raw_value is None:
            return []

        if isinstance(raw_value, dict):
            raw_parts = raw_value.keys()
        elif isinstance(raw_value, (list, tuple, set)):
            raw_parts = raw_value
        else:
            raw_parts = re.split(r"[,/|;\s]+", str(raw_value))

        symbols: list[str] = []
        for raw_part in raw_parts:
            object_symbol = self._symbol_from_object(raw_part)
            symbol = object_symbol or str(raw_part or "").strip().upper()
            symbol = re.sub(r"[^A-Z0-9.\-^=]", "", symbol)
            if symbol:
                symbols.append(symbol)

        return symbols

    def _extract_initial_prices(self, fcn_position: Any, symbols: list[str]) -> dict[str, float | None]:
        prices: dict[str, float | None] = {symbol: None for symbol in symbols}
        prices.update(self._prices_from_underlyings(
            fcn_position,
            symbols,
            ("initial_price", "initial"),
            allow_zero=True,
        ))

        for field_name in self.INITIAL_PRICE_FIELDS:
            raw_value = getattr(fcn_position, field_name, None)
            if raw_value is None:
                continue

            if isinstance(raw_value, dict):
                for key, value in raw_value.items():
                    symbol = str(key or "").strip().upper()
                    if symbol in prices:
                        prices[symbol] = self._safe_number(value)
                continue

            if isinstance(raw_value, (list, tuple)):
                for symbol, value in zip(symbols, raw_value):
                    prices[symbol] = self._safe_number(value)
                continue

            if isinstance(raw_value, str) and len(symbols) > 1 and re.search(r"[,/|;\s]+", raw_value):
                values = [self._safe_number(part) for part in re.split(r"[,/|;\s]+", raw_value)]
                for symbol, value in zip(symbols, values):
                    prices[symbol] = value
                continue

            value = self._safe_number(raw_value)
            if value is not None:
                for symbol in symbols:
                    prices[symbol] = value

        return prices

    def _extract_current_prices(self, fcn_position: Any, symbols: list[str]) -> dict[str, float | None]:
        prices: dict[str, float | None] = {symbol: None for symbol in symbols}
        prices.update(self._prices_from_underlyings(fcn_position, symbols, ("current_price", "price")))

        for field_name in self.CURRENT_PRICE_FIELDS:
            raw_value = getattr(fcn_position, field_name, None)
            if raw_value is None:
                continue

            if isinstance(raw_value, dict):
                for key, value in raw_value.items():
                    symbol = str(key or "").strip().upper()
                    if symbol in prices:
                        prices[symbol] = self._safe_float(value)
                continue

            if isinstance(raw_value, (list, tuple)):
                for symbol, value in zip(symbols, raw_value):
                    prices[symbol] = self._safe_float(value)
                continue

            if isinstance(raw_value, str) and len(symbols) > 1 and re.search(r"[,/|;\s]+", raw_value):
                values = [self._safe_float(part) for part in re.split(r"[,/|;\s]+", raw_value)]
                for symbol, value in zip(symbols, values):
                    prices[symbol] = value
                continue

            value = self._safe_float(raw_value)
            if value is not None:
                for symbol in symbols:
                    prices[symbol] = value

        return prices

    def _prices_from_underlyings(
        self,
        fcn_position: Any,
        symbols: list[str],
        field_names: tuple[str, ...],
        allow_zero: bool = False,
    ) -> dict[str, float | None]:
        prices: dict[str, float | None] = {symbol: None for symbol in symbols}

        for collection_field in self.UNDERLYING_COLLECTION_FIELDS:
            raw_collection = getattr(fcn_position, collection_field, None)
            if raw_collection is None or isinstance(raw_collection, str):
                continue

            items = raw_collection.values() if isinstance(raw_collection, dict) else raw_collection
            for item in items:
                symbol = self._symbol_from_object(item)
                if symbol not in prices:
                    continue

                for field_name in field_names:
                    raw_price = getattr(item, field_name, None)
                    price = self._safe_number(raw_price) if allow_zero else self._safe_float(raw_price)
                    if price is not None:
                        prices[symbol] = price
                        break

        return prices

    def _value_from_object(self, value: Any, field_names: tuple[str, ...]) -> Any:
        if value is None:
            return None

        if isinstance(value, dict):
            for field_name in field_names:
                if field_name in value:
                    return value[field_name]
            return None

        for field_name in field_names:
            raw_value = getattr(value, field_name, None)
            if raw_value is not None:
                return raw_value

        return None

    def _get_market_price(self, symbol: str) -> Any:
        try:
            return self.market_data_service.get_price(symbol)
        except Exception:
            return None

    def _symbol_from_object(self, value: Any) -> str | None:
        if isinstance(value, (str, int, float)):
            return None

        for field_name in ("symbol", "ticker", "underlying_symbol"):
            raw_symbol = self._value_from_object(value, (field_name,))
            if raw_symbol:
                return self._clean_symbol_value(raw_symbol)

        return None

    def _extract_level_pct(self, fcn_position: Any, field_names: tuple[str, ...]) -> float | None:
        for field_name in field_names:
            value = self._safe_float(getattr(fcn_position, field_name, None))
            if value is None:
                continue

            if value <= 1:
                return value * 100

            return value

        return None

    def _pct_to_ratio(self, value: float | None) -> float | None:
        if value is None:
            return None
        return value / 100

    def _barrier_price(self, initial_price: float | None, level_pct: float | None) -> float | None:
        if initial_price is None or level_pct is None:
            return None
        return initial_price * (level_pct / 100)

    def _barrier_distance(
        self,
        current_price: float | None,
        barrier_price: float | None,
        initial_price: float | None,
        direction: str,
    ) -> float | None:
        if current_price is None or barrier_price is None or initial_price is None or initial_price <= 0:
            return None

        if direction == "down":
            return (current_price - barrier_price) / initial_price

        return (barrier_price - current_price) / initial_price

    def _risk_level_from_worst(
        self,
        current_price: float | None,
        ki_barrier: float | None,
        distance_to_ki: float | None,
    ) -> str:
        if current_price is None or ki_barrier is None or distance_to_ki is None:
            return "unknown"

        if current_price <= ki_barrier:
            return "high"

        if distance_to_ki <= 0.10:
            return "high"

        if distance_to_ki <= 0.20:
            return "medium"

        return "low"

    def _extract_ratio(self, fcn_position: Any, field_names: tuple[str, ...]) -> float | None:
        for field_name in field_names:
            value = self._safe_float(getattr(fcn_position, field_name, None))
            if value is None:
                continue

            if value > 1:
                return value / 100

            if value > 0:
                return value

        return None

    def _distance_to_ki(
        self,
        fcn_position: Any,
        worst_ratio: float,
        ki_ratio: float | None,
    ) -> float | None:
        if ki_ratio is not None:
            return worst_ratio - ki_ratio
        return self._distance_from_existing_pct(fcn_position, "distance_to_ki_pct")

    def _distance_to_ko(
        self,
        fcn_position: Any,
        worst_ratio: float,
        ko_ratio: float | None,
    ) -> float | None:
        if ko_ratio is not None:
            return ko_ratio - worst_ratio
        return self._distance_from_existing_pct(fcn_position, "distance_to_ko_pct")

    def _distance_from_existing_pct(self, fcn_position: Any, field_name: str) -> float | None:
        value = self._safe_number(getattr(fcn_position, field_name, None))
        if value is None:
            return None
        return value / 100

    def _risk_level(
        self,
        fcn_position: Any,
        worst_ratio: float,
        ki_ratio: float | None,
        distance_to_ki: float | None,
    ) -> str:
        if ki_ratio is not None:
            if worst_ratio < ki_ratio:
                return "high"
            if worst_ratio < ki_ratio + 0.10:
                return "medium"
            return "low"

        existing_level = str(getattr(fcn_position, "risk_level", "") or "").strip().lower()
        if existing_level in self.COMMENT_BY_RISK:
            return existing_level

        if distance_to_ki is not None:
            if distance_to_ki <= 0:
                return "high"
            if distance_to_ki <= 0.10:
                return "medium"

        return "low"

    def _price_source(self, sources: set[str]) -> str | None:
        normalized_sources = {source for source in sources if source}
        if not normalized_sources:
            return None
        if len(normalized_sources) == 1:
            return next(iter(normalized_sources))
        return "mixed"

    def _safe_float(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            number = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(number) or number <= 0:
            return None

        return number

    def _safe_number(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            number = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(number):
            return None

        return number

    def _round(self, value: float | None) -> float | None:
        if value is None:
            return None
        number = self._safe_number(value)
        if number is None:
            return None
        return round(number, 6)
