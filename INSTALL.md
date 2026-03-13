# 🤖 Bot de Trading Telegram — Guide d'Installation

## Prérequis

- Python 3.10 ou supérieur
- macOS, Linux ou Windows (MT5 uniquement sous Windows)
- Compte Telegram
- Compte broker (ou mode demo pour tester)

---

## 1. Cloner / Extraire le projet

```bash
cd ~
mkdir trading_bot && cd trading_bot
# Copiez tous les fichiers .py ici
```

---

## 2. Créer un environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

---

## 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

Pour MetaTrader 5 (Windows uniquement) :
```bash
pip install MetaTrader5
```

Pour Binance :
```bash
pip install python-binance
```

Pour OANDA :
```bash
pip install oandapyV20
```

---

## 4. Créer votre bot Telegram

1. Ouvrez Telegram → cherchez **@BotFather**
2. Envoyez `/newbot`
3. Choisissez un nom : ex. `MonBotTrading`
4. Choisissez un username : ex. `MonBotTrading_bot`
5. Copiez le **token** fourni

**Obtenir votre Chat ID :**
1. Cherchez **@userinfobot** sur Telegram
2. Envoyez `/start`
3. Copiez votre **Id** numérique

---

## 5. Configurer le fichier .env

```bash
cp .env.example .env
nano .env   # ou ouvrez avec un éditeur
```

Remplissez :
```
TELEGRAM_TOKEN=votre_token_ici
TELEGRAM_CHAT_ID=votre_chat_id_ici
BROKER=demo   # commencez par demo !
```

---

## 6. Lancer le bot

```bash
python bot.py
```

Vous devriez voir dans le terminal :
```
[Bot] Initialisé | Balance=1000.00$ | Paire=XAUUSD
[Telegram] Bot démarré — polling...
```

Puis envoyez `/start` à votre bot Telegram.

---

## 7. Configuration du broker réel

### MetaTrader 5 (Windows)

```
BROKER=mt5
MT5_LOGIN=votre_login_numerique
MT5_PASSWORD=votre_mot_de_passe
MT5_SERVER=NomDuServeur-Demo  # ex: ICMarkets-Demo02
```

MT5 doit être installé et ouvert sur votre PC.

### Binance

```
BROKER=binance
BINANCE_API_KEY=votre_cle
BINANCE_API_SECRET=votre_secret
```

Créez une clé API sur : https://www.binance.com/fr/my/settings/api-management
Autorisez uniquement : **Spot Trading** (pas Withdraw)

### OANDA

```
BROKER=oanda
OANDA_API_KEY=votre_cle
OANDA_ACCOUNT_ID=votre_account_id
```

Créez un compte demo sur : https://www.oanda.com

---

## 8. Commandes Telegram disponibles

| Commande | Description |
|----------|-------------|
| `/start` | Démarrer le bot |
| `/stop` | Arrêter le bot |
| `/resume` | Réactiver après arrêt |
| `/status` | État complet |
| `/balance` | Solde du compte |
| `/profit` | PnL journalier |
| `/stats` | Statistiques globales |
| `/weekly` | Résumé hebdomadaire |
| `/dashboard` | Vue d'ensemble |
| `/mode_scalping` | Mode M1/M5 |
| `/mode_intraday` | Mode M15/H1 |
| `/mode_swing` | Mode H4/D1 |
| `/risk 0.5` | Risque par trade (%) |
| `/pair XAUUSD` | Changer de paire |
| `/timeframe H1` | Changer le timeframe |
| `/strategy smc` | Smart Money Concepts |
| `/strategy ict` | ICT Concepts |
| `/strategy supplydemand` | Offre & Demande |
| `/strategy priceaction` | Price Action |
| `/news` | Prochaines annonces |
| `/news on` | Activer filtre news |
| `/news off` | Désactiver filtre news |
| `/trades` | Positions ouvertes |
| `/help` | Aide complète |

---

## 9. Paires supportées

| Paire | Description |
|-------|-------------|
| `XAUUSD` | Or / Dollar |
| `BTCUSD` | Bitcoin / Dollar |
| `XAGUSD` | Argent / Dollar |
| `EURUSD` | Euro / Dollar |
| `GBPUSD` | Livre / Dollar |

---

## 10. Gestion du risque

Les paramètres par défaut sont conservateurs :

- **Risque par trade** : 0.5% du capital
- **RR minimum** : 1:2
- **Max pertes consécutives** : 3 (bot s'arrête)
- **Max trades/jour** : 5
- **Drawdown journalier max** : 3%
- **Drawdown total max** : 10%

Pour modifier : `/risk 1.0` ou éditer `config.py`

---

## 11. Lancer en arrière-plan (Linux/macOS)

```bash
# Avec nohup
nohup python bot.py > output.log 2>&1 &

# Avec screen
screen -S tradingbot
python bot.py
# Ctrl+A puis D pour détacher

# Avec systemd (Linux)
# Créez /etc/systemd/system/tradingbot.service
```

---

## 12. Structure des fichiers

```
trading_bot/
├── bot.py                    # Contrôleur principal
├── config.py                 # Configuration
├── strategy_engine.py        # Orchestrateur stratégies
├── smc_strategy.py           # Smart Money Concepts
├── ict_strategy.py           # ICT Concepts
├── supply_demand_strategy.py # Offre & Demande
├── price_action_strategy.py  # Price Action
├── risk_management.py        # Gestion du risque
├── market_analysis.py        # Analyse marché
├── news_filter.py            # Filtre économique
├── trade_executor.py         # Exécution trades
├── performance_tracker.py    # Journal & statistiques
├── telegram_interface.py     # Interface Telegram
├── requirements.txt          # Dépendances
├── .env.example              # Template config
├── trades_journal.csv        # Journal auto-généré
└── performance_stats.json    # Stats auto-générées
```

---

## ⚠️ Avertissement

Ce bot est un outil éducatif. Le trading comporte des risques.
**Testez toujours en mode demo avant d'utiliser des fonds réels.**
Les performances passées ne garantissent pas les performances futures.
