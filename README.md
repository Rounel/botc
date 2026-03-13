# Bot de Trading Algorithmique — Telegram

Bot de trading professionnel piloté via Telegram, connecté à MetaTrader 5, Binance ou OANDA. Il analyse le marché en temps réel et exécute des trades automatiquement selon des stratégies institutionnelles (SMC, ICT, Supply & Demand, Price Action).

---

## Fonctionnalités

- **4 stratégies** : SMC, ICT, Supply & Demand, Price Action (sélection manuelle ou automatique)
- **3 modes** : Scalping (M1/M5), Intraday (H1), Swing (H4)
- **Gestion du risque** : taille de position automatique, drawdown journalier/total, pertes consécutives
- **Filtre news** : pause automatique avant/après annonces haute impact (ForexFactory)
- **Brokers supportés** : MetaTrader 5, Binance, OANDA, mode Demo
- **Interface Telegram complète** : commandes, boutons, notifications en temps réel
- **Journal des trades** : export CSV, statistiques win rate / profit factor / expectancy

---

## Installation

### 1. Prérequis

- Python 3.10+
- Un bot Telegram (créé via [@BotFather](https://t.me/BotFather))
- MetaTrader 5 installé (si broker = mt5)

### 2. Environnement virtuel

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/Mac
```

### 3. Dépendances

```bash
pip install -r requirements.txt
```

Pour MetaTrader 5 (Windows uniquement) :
```bash
pip install MetaTrader5
```

### 4. Configuration

Crée un fichier `.env` à la racine du projet :

```env
TELEGRAM_TOKEN=ton_token_botfather
TELEGRAM_CHAT_ID=ton_chat_id

# Broker : "demo" | "mt5" | "binance" | "oanda"
BROKER=mt5

# MetaTrader 5
MT5_LOGIN=123456789
MT5_PASSWORD=ton_mot_de_passe
MT5_SERVER=NomDuServeur-Demo
```

> Pour trouver ton `CHAT_ID` : envoie un message à [@userinfobot](https://t.me/userinfobot)

### 5. Lancement

```bash
python bot.py
```

> **Important (MT5)** : Active l'Algo Trading dans MetaTrader 5 avant de lancer le bot.
> Menu **Outils → Options → Expert Advisors → Autoriser le trading automatisé**, ou clique le bouton **Algo Trading** dans la barre d'outils.

---

## Commandes Telegram

### Contrôle

| Commande | Description |
|----------|-------------|
| `/start` | Démarrer le bot |
| `/stop` | Arrêter le bot (positions conservées) |
| `/resume` | Réactiver après arrêt automatique |
| `/status` | État complet du bot |
| `/dashboard` | Vue d'ensemble (balance, PnL, news) |

### Compte & Performance

| Commande | Description |
|----------|-------------|
| `/balance` | Solde actuel |
| `/profit` | Résumé journalier |
| `/stats` | Statistiques globales |
| `/weekly` | Résumé hebdomadaire |
| `/trades` | Positions ouvertes |

### Configuration

| Commande | Description |
|----------|-------------|
| `/mode_scalping` | Mode scalping — M5 |
| `/mode_intraday` | Mode intraday — H1 |
| `/mode_swing` | Mode swing — H4 |
| `/risk 0.5` | Risque par trade en % (0.1 — 2.0) |
| `/pair XAUUSD` | Changer la paire active |
| `/timeframe H1` | Changer le timeframe manuellement |

### Stratégies

| Commande | Description |
|----------|-------------|
| `/strategy smc` | Smart Money Concepts |
| `/strategy ict` | ICT (Inner Circle Trader) |
| `/strategy supplydemand` | Offre & Demande |
| `/strategy priceaction` | Price Action pur |

### News

| Commande | Description |
|----------|-------------|
| `/news` | Prochaines annonces majeures (24h) |
| `/news on` | Activer le filtre news |
| `/news off` | Désactiver le filtre news |

---

## Stratégies

### SMC — Smart Money Concepts
Détecte les mouvements institutionnels via :
- **Break of Structure (BOS) / Change of Character (CHOCH)**
- **Order Blocks** : dernière bougie opposée avant un mouvement impulsif
- **Fair Value Gaps (FVG)** : déséquilibres de prix à combler
- **Liquidity Sweeps** : chasse aux stops avant reversal

### ICT — Inner Circle Trader
- **OTE (Optimal Trade Entry)** : retracement Fibonacci 0.62–0.79
- **Kill Zones** : London Open (7h–10h UTC), New York Open (13h–16h UTC)
- **Judas Swing** : faux breakout avant reversal
- **Liquidity Pools** : BSL/SSL (Buy-side / Sell-side Liquidity)

### Supply & Demand
- **Zones de demande (DBR)** : Drop-Base-Rally
- **Zones d'offre (RBD)** : Rally-Base-Drop
- Priorité aux zones **fraîches** (non encore testées)

### Price Action
- Niveaux Support / Résistance par clustering
- **Patterns** : Pin Bar, Engulfing, Hammer, Shooting Star, Inside Bar, Doji
- **Breakout** avec retest de niveau clé
- Continuation de tendance sur pullback EMA50

---

## Gestion du Risque

| Paramètre | Valeur par défaut |
|-----------|-------------------|
| Risque par trade | 0.5% du capital |
| Risque maximum | 2.0% |
| RR minimum | 2.0 |
| Pertes consécutives max | 3 (arrêt automatique) |
| Trades journaliers max | 5 |
| Drawdown journalier max | 3% |
| Drawdown total max | 10% |

Le lot size est calculé automatiquement :
```
lot = (balance × risque%) / (distance_SL_en_pips × valeur_du_pip)
```

---

## Paires supportées

| Paire | Pip Size | Taille contrat |
|-------|----------|----------------|
| XAUUSD | 0.01 | 100 |
| BTCUSD | 1.0 | 1 |
| EURUSD | 0.0001 | 100 000 |
| GBPUSD | 0.0001 | 100 000 |
| XAGUSD | 0.001 | 5 000 |

---

## Structure du projet

```
botS/
├── bot.py                    # Contrôleur principal + boucle de trading
├── config.py                 # Configuration centrale
├── strategy_engine.py        # Orchestrateur des stratégies
├── smc_strategy.py           # Stratégie Smart Money Concepts
├── ict_strategy.py           # Stratégie ICT
├── supply_demand_strategy.py # Stratégie Supply & Demand
├── price_action_strategy.py  # Stratégie Price Action
├── market_analysis.py        # Indicateurs techniques (EMA, RSI, ATR)
├── risk_management.py        # Gestion du risque et taille de position
├── trade_executor.py         # Exécution des ordres (MT5/Binance/OANDA/Demo)
├── performance_tracker.py    # Journal et statistiques de performance
├── news_filter.py            # Filtre actualités ForexFactory
├── telegram_interface.py     # Interface Telegram (commandes + notifications)
├── requirements.txt          # Dépendances Python
├── .env                      # Variables d'environnement (ne pas versionner)
├── bot.log                   # Journal des événements
└── trades_journal.csv        # Historique des trades (généré automatiquement)
```

---

## Fichiers générés automatiquement

| Fichier | Contenu |
|---------|---------|
| `bot.log` | Journal complet des événements |
| `trades_journal.csv` | Historique de tous les trades fermés |
| `performance_stats.json` | Statistiques de performance (win rate, PF, etc.) |

---

## Dépendances principales

```
python-telegram-bot==21.6
numpy>=1.24
pandas>=2.0
requests>=2.31
python-dotenv>=1.0
```

---

## Avertissement

Ce bot est fourni à titre éducatif. Le trading algorithmique comporte des risques de perte en capital. Testez toujours en mode **demo** avant de trader en compte réel. Les performances passées ne garantissent pas les performances futures.
