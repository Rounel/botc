"""
news_filter.py
Filtre de news économiques.
Pause trading pendant les annonces majeures (NFP, CPI, FOMC, etc.)
Source : ForexFactory RSS ou API calendrier économique.
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass
import xml.etree.ElementTree as ET

import config

logger = logging.getLogger(__name__)


@dataclass
class NewsEvent:
    time: datetime
    currency: str
    impact: str         # "High" | "Medium" | "Low"
    title: str
    forecast: str
    previous: str


class NewsFilter:
    """Filtre les créneaux de trading selon les annonces économiques."""

    HIGH_IMPACT_CURRENCIES = {
        "EURUSD": ["EUR", "USD"],
        "GBPUSD": ["GBP", "USD"],
        "XAUUSD": ["USD"],
        "BTCUSD": ["USD"],
        "XAGUSD": ["USD"],
    }

    def __init__(self):
        self.enabled = config.NEWS_FILTER_ENABLED
        self.pause_minutes = config.NEWS_PAUSE_MINUTES
        self._cache: List[NewsEvent] = []
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 3600  # 1h

    # ──────────────────────────────────────────
    # RÉCUPÉRATION DES NEWS
    # ──────────────────────────────────────────

    def fetch_forexfactory_calendar(self) -> List[NewsEvent]:
        """
        Récupère le calendrier ForexFactory via RSS.
        Fallback : liste manuelle des événements majeurs.
        """
        # Vérifier cache
        if self._cache_time and (datetime.utcnow() - self._cache_time).total_seconds() < self._cache_ttl:
            return self._cache

        events = []

        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    try:
                        dt = datetime.strptime(item.get("date", ""), "%Y-%m-%dT%H:%M:%S%z")
                        dt = dt.replace(tzinfo=None)
                    except (ValueError, TypeError):
                        continue

                    impact = item.get("impact", "")
                    if impact not in ("High", "Medium"):
                        continue

                    events.append(NewsEvent(
                        time=dt,
                        currency=item.get("country", ""),
                        impact=impact,
                        title=item.get("title", ""),
                        forecast=item.get("forecast", ""),
                        previous=item.get("previous", ""),
                    ))

                logger.info(f"[News] {len(events)} événements chargés depuis ForexFactory")
        except Exception as e:
            logger.warning(f"[News] Erreur chargement FF calendar : {e}")
            events = self._get_fallback_events()

        self._cache = events
        self._cache_time = datetime.utcnow()
        return events

    def _get_fallback_events(self) -> List[NewsEvent]:
        """Événements récurrents connus (jour J)."""
        now = datetime.utcnow()
        today = now.date()

        # NFP premier vendredi du mois
        events = []
        if today.weekday() == 4:  # Vendredi
            nfp_time = datetime.combine(today, datetime.min.time().replace(hour=13, minute=30))
            events.append(NewsEvent(
                time=nfp_time, currency="USD", impact="High",
                title="Non-Farm Payrolls", forecast="", previous=""
            ))

        return events

    # ──────────────────────────────────────────
    # VÉRIFICATION
    # ──────────────────────────────────────────

    def is_trading_allowed(self, pair: str, dt: Optional[datetime] = None) -> tuple:
        """
        Retourne (allowed: bool, reason: str).
        Trading interdit si annonce haute impact dans la fenêtre.
        """
        if not self.enabled:
            return True, "Filtre news désactivé"

        dt = dt or datetime.utcnow()
        currencies = self.HIGH_IMPACT_CURRENCIES.get(pair, ["USD"])
        events = self.fetch_forexfactory_calendar()

        for event in events:
            if event.impact != "High":
                continue
            if event.currency not in currencies:
                continue

            window_start = event.time - timedelta(minutes=self.pause_minutes)
            window_end   = event.time + timedelta(minutes=self.pause_minutes)

            if window_start <= dt <= window_end:
                msg = (
                    f"⚠️ News HIGH impact : {event.title} ({event.currency})\n"
                    f"📅 {event.time.strftime('%H:%M UTC')} | "
                    f"Pause {self.pause_minutes}min avant/après"
                )
                return False, msg

        return True, "OK"

    def get_upcoming_events(self, hours: int = 24, pair: Optional[str] = None) -> List[NewsEvent]:
        """Retourne les événements dans les prochaines N heures."""
        now = datetime.utcnow()
        limit = now + timedelta(hours=hours)
        events = self.fetch_forexfactory_calendar()

        if pair:
            currencies = self.HIGH_IMPACT_CURRENCIES.get(pair, [])
            events = [e for e in events if e.currency in currencies]

        return [e for e in events if now <= e.time <= limit]

    def format_upcoming(self, hours: int = 24, pair: Optional[str] = None) -> str:
        """Formate les prochains événements pour Telegram."""
        events = self.get_upcoming_events(hours, pair)
        if not events:
            return "📭 Aucune news majeure dans les prochaines 24h"

        lines = ["📰 *Prochaines news majeures :*\n"]
        for e in events:
            icon = "🔴" if e.impact == "High" else "🟡"
            lines.append(
                f"{icon} `{e.time.strftime('%d/%m %H:%M')} UTC` | "
                f"**{e.currency}** — {e.title}"
            )
        return "\n".join(lines)
