"""
telegram_interface.py
Interface Telegram complète.
Toutes les commandes et notifications.
"""

import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


class TelegramInterface:
    """Gère toutes les interactions Telegram avec le bot."""

    def __init__(self, bot_controller):
        self.bot = bot_controller
        self.app: Optional[Application] = None

    # ──────────────────────────────────────────
    # SETUP
    # ──────────────────────────────────────────

    def setup(self, token: str, post_init=None):
        builder = Application.builder().token(token)
        if post_init:
            builder = builder.post_init(post_init)
        self.app = builder.build()
        self._register_handlers()
        return self

    def _register_handlers(self):
        cmds = [
            ("start",         self.cmd_start),
            ("stop",          self.cmd_stop),
            ("status",        self.cmd_status),
            ("balance",       self.cmd_balance),
            ("profit",        self.cmd_profit),
            ("dashboard",     self.cmd_dashboard),
            ("mode_scalping", self.cmd_mode_scalping),
            ("mode_intraday", self.cmd_mode_intraday),
            ("mode_swing",    self.cmd_mode_swing),
            ("risk",          self.cmd_risk),
            ("pair",          self.cmd_pair),
            ("timeframe",     self.cmd_timeframe),
            ("news",          self.cmd_news),
            ("strategy",      self.cmd_strategy),
            ("trades",        self.cmd_trades),
            ("stats",         self.cmd_stats),
            ("weekly",        self.cmd_weekly),
            ("help",          self.cmd_help),
            ("resume",        self.cmd_resume),
        ]
        for name, handler in cmds:
            self.app.add_handler(CommandHandler(name, handler))

        self.app.add_handler(CallbackQueryHandler(self.handle_callback))

    def run(self):
        logger.info("[Telegram] Bot démarré — polling...")
        self.app.run_polling(drop_pending_updates=True)

    # ──────────────────────────────────────────
    # VÉRIFICATION ACCÈS
    # ──────────────────────────────────────────

    def _is_authorized(self, update: Update) -> bool:
        chat_id = str(update.effective_chat.id)
        allowed = str(config.TELEGRAM_CHAT_ID)
        if allowed and chat_id != allowed:
            logger.warning(f"Accès refusé : {chat_id}")
            return False
        return True

    async def _unauthorized(self, update: Update):
        await update.message.reply_text("⛔ Accès non autorisé.")

    # ──────────────────────────────────────────
    # COMMANDES
    # ──────────────────────────────────────────

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        result = self.bot.start()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard"),
             InlineKeyboardButton("⚖️ Balance", callback_data="balance")],
            [InlineKeyboardButton("📈 Stats", callback_data="stats"),
             InlineKeyboardButton("📰 News", callback_data="news_status")],
            [InlineKeyboardButton("⏹ Stop", callback_data="stop")],
        ])
        await update.message.reply_text(
            f"🤖 *Bot de trading démarré !*\n\n{result}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb
        )

    async def cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        result = self.bot.stop()
        await update.message.reply_text(f"⏹ *Bot arrêté.*\n{result}", parse_mode=ParseMode.MARKDOWN)

    async def cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        self.bot.risk_manager.resume()
        await update.message.reply_text("▶️ *Bot réactivé manuellement.*", parse_mode=ParseMode.MARKDOWN)

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        status = self.bot.get_status()
        await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)

    async def cmd_balance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        balance = self.bot.executor.get_balance()
        await update.message.reply_text(
            f"💰 *Balance actuelle :* `{balance:.2f}$`",
            parse_mode=ParseMode.MARKDOWN
        )

    async def cmd_profit(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        msg = self.bot.tracker.format_daily_summary()
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_dashboard(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        msg = self.bot.get_dashboard()
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_mode_scalping(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        self.bot.engine.set_mode("scalping")
        self.bot.active_timeframe = "M5"
        await update.message.reply_text("⚡ *Mode SCALPING activé* (M5)", parse_mode=ParseMode.MARKDOWN)

    async def cmd_mode_intraday(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        self.bot.engine.set_mode("intraday")
        self.bot.active_timeframe = "H1"
        await update.message.reply_text("📊 *Mode INTRADAY activé* (H1)", parse_mode=ParseMode.MARKDOWN)

    async def cmd_mode_swing(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        self.bot.engine.set_mode("swing")
        self.bot.active_timeframe = "H4"
        await update.message.reply_text("🌊 *Mode SWING activé* (H4)", parse_mode=ParseMode.MARKDOWN)

    async def cmd_risk(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        args = ctx.args
        if not args:
            await update.message.reply_text(
                f"⚖️ Risque actuel : `{self.bot.risk_manager.risk_pct}%`\n"
                f"Usage : `/risk 0.5` (0.1% — {config.MAX_RISK_PERCENT}%)",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        try:
            pct = float(args[0].replace("%", ""))
            if self.bot.risk_manager.set_risk(pct):
                await update.message.reply_text(
                    f"✅ Risque mis à jour : `{pct}%` par trade",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"❌ Valeur invalide. Min 0.1% — Max {config.MAX_RISK_PERCENT}%"
                )
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Usage : `/risk 0.5`", parse_mode=ParseMode.MARKDOWN)

    async def cmd_pair(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        args = ctx.args
        if not args:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(p, callback_data=f"pair_{p}") for p in config.DEFAULT_PAIRS[:3]],
                [InlineKeyboardButton(p, callback_data=f"pair_{p}") for p in config.DEFAULT_PAIRS[3:]],
            ])
            await update.message.reply_text("💱 *Choisir une paire :*", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            return
        pair = args[0].upper()
        if pair in config.ASSET_CONFIG:
            self.bot.active_pair = pair
            await update.message.reply_text(f"✅ Paire active : `{pair}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"❌ Paire inconnue : {pair}")

    async def cmd_timeframe(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        args = ctx.args
        if not args:
            await update.message.reply_text(
                "⏱ Usage : `/timeframe M1` | M5 | M15 | H1 | H4 | D1",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        tf = args[0].upper()
        self.bot.active_timeframe = tf
        await update.message.reply_text(f"✅ Timeframe : `{tf}`", parse_mode=ParseMode.MARKDOWN)

    async def cmd_news(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        args = ctx.args
        if args and args[0].lower() == "off":
            self.bot.news_filter.enabled = False
            await update.message.reply_text("📴 Filtre news *désactivé*.", parse_mode=ParseMode.MARKDOWN)
        elif args and args[0].lower() == "on":
            self.bot.news_filter.enabled = True
            await update.message.reply_text("📰 Filtre news *activé*.", parse_mode=ParseMode.MARKDOWN)
        else:
            msg = self.bot.news_filter.format_upcoming()
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_strategy(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        args = ctx.args
        strategies = {"smc": "Smart Money Concepts", "ict": "ICT Concepts",
                      "supplydemand": "Supply & Demand", "priceaction": "Price Action"}
        if not args:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(v, callback_data=f"strat_{k}")
                for k, v in strategies.items()
            ][i:i+2] for i in range(0, len(strategies), 2)])
            await update.message.reply_text(
                f"🎯 Stratégie active : `{self.bot.engine.active_strategy}`\nChoisir :",
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb
            )
            return
        strat = args[0].lower()
        if self.bot.engine.set_strategy(strat):
            await update.message.reply_text(
                f"✅ Stratégie : `{strategies.get(strat, strat)}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(f"❌ Stratégie inconnue : {strat}")

    async def cmd_trades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        open_trades = self.bot.executor.get_open_trades()
        if not open_trades:
            await update.message.reply_text("📭 Aucun trade ouvert.")
            return
        lines = ["📋 *Trades ouverts :*\n"]
        for t in open_trades:
            icon = "📈" if t.direction == "buy" else "📉"
            lines.append(
                f"{icon} `{t.pair}` {t.direction.upper()} @ {t.entry} "
                f"| SL {t.stop_loss} | TP {t.take_profit}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        msg = self.bot.tracker.format_full_stats()
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_weekly(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        msg = self.bot.tracker.format_weekly_summary()
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update): return await self._unauthorized(update)
        help_text = (
            "🤖 *Bot de Trading — Commandes*\n\n"
            "*Contrôle :*\n"
            "/start — Démarrer le bot\n"
            "/stop — Arrêter le bot\n"
            "/resume — Réactiver après arrêt\n"
            "/status — État complet\n\n"
            "*Compte :*\n"
            "/balance — Solde\n"
            "/profit — PnL journalier\n"
            "/stats — Statistiques globales\n"
            "/weekly — Résumé hebdomadaire\n\n"
            "*Configuration :*\n"
            "/mode\\_scalping — Mode scalping (M1/M5)\n"
            "/mode\\_intraday — Mode intraday (M15/H1)\n"
            "/mode\\_swing — Mode swing (H4/D1)\n"
            "/risk 0.5 — Définir le risque %\n"
            "/pair XAUUSD — Changer de paire\n"
            "/timeframe H1 — Changer le timeframe\n\n"
            "*Stratégies :*\n"
            "/strategy smc — Smart Money\n"
            "/strategy ict — ICT\n"
            "/strategy supplydemand — Offre/Demande\n"
            "/strategy priceaction — Price Action\n\n"
            "*News :*\n"
            "/news — Voir prochains événements\n"
            "/news on|off — Activer/Désactiver filtre\n\n"
            "*Trades :*\n"
            "/trades — Positions ouvertes\n"
            "/dashboard — Vue d'ensemble\n"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    # ──────────────────────────────────────────
    # CALLBACKS BOUTONS
    # ──────────────────────────────────────────

    async def handle_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "dashboard":
            msg = self.bot.get_dashboard()
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)

        elif data == "balance":
            bal = self.bot.executor.get_balance()
            await query.edit_message_text(
                f"💰 *Balance :* `{bal:.2f}$`", parse_mode=ParseMode.MARKDOWN
            )

        elif data == "stats":
            msg = self.bot.tracker.format_full_stats()
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)

        elif data == "news_status":
            msg = self.bot.news_filter.format_upcoming()
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)

        elif data == "stop":
            self.bot.stop()
            await query.edit_message_text("⏹ *Bot arrêté.*", parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("pair_"):
            pair = data.replace("pair_", "")
            self.bot.active_pair = pair
            await query.edit_message_text(f"✅ Paire active : `{pair}`", parse_mode=ParseMode.MARKDOWN)

        elif data.startswith("strat_"):
            strat = data.replace("strat_", "")
            self.bot.engine.set_strategy(strat)
            await query.edit_message_text(
                f"✅ Stratégie : `{strat}`", parse_mode=ParseMode.MARKDOWN
            )

    # ──────────────────────────────────────────
    # ENVOI DE NOTIFICATIONS
    # ──────────────────────────────────────────

    async def send_notification(self, text: str):
        """Envoie une notification au chat configuré."""
        try:
            await self.app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.error(f"[Telegram] Erreur envoi notification : {e}")
