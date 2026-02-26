"""
Macro-Economic & Geopolitical Analysis Engine.

Fetches and analyzes:
  1. Macro indicators: VIX, DXY, Bond Yields, USD/INR
  2. News headlines: Gold, Oil, Geopolitical, Fed, India, Trade/Sanctions
  3. Sentiment scoring: Bullish/Bearish keyword analysis
  4. Impact mapping: How events affect Gold, Silver, Oil, Stocks

Generates a "Market Intelligence" report for Telegram.
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yfinance as yf
import pandas as pd

try:
    import feedparser
except ImportError:
    feedparser = None


# ============================================================
# MACRO INDICATORS
# ============================================================

MACRO_TICKERS = {
    "VIX": {"ticker": "^VIX", "name": "VIX (Fear Index)", "unit": ""},
    "INDIA_VIX": {"ticker": "^INDIAVIX", "name": "India VIX", "unit": ""},
    "DXY": {"ticker": "DX-Y.NYB", "name": "US Dollar Index", "unit": ""},
    "US10Y": {"ticker": "^TNX", "name": "US 10Y Yield", "unit": "%"},
    "US2Y": {"ticker": "^IRX", "name": "US 2Y Yield", "unit": "%"},
    "US30Y": {"ticker": "^TYX", "name": "US 30Y Yield", "unit": "%"},
    "SP500": {"ticker": "^GSPC", "name": "S&P 500", "unit": ""},
    "USDINR": {"ticker": "USDINR=X", "name": "USD/INR", "unit": ""},
}


def fetch_macro_data():
    """Fetch all macro indicators from yfinance."""
    results = {}
    tickers_list = [v["ticker"] for v in MACRO_TICKERS.values()]

    try:
        data = yf.download(tickers_list, period="30d", interval="1d", progress=False, auto_adjust=True)
    except Exception as e:
        print(f"[MACRO] Batch download failed: {e}")
        return results

    for key, info in MACRO_TICKERS.items():
        ticker = info["ticker"]
        try:
            if isinstance(data.columns, pd.MultiIndex):
                close_col = ("Close", ticker)
                if close_col in data.columns:
                    series = data[close_col].dropna()
                else:
                    continue
            else:
                series = data["Close"].dropna()

            if len(series) < 2:
                continue

            current = float(series.iloc[-1])
            prev = float(series.iloc[-2])
            week_ago = float(series.iloc[-5]) if len(series) >= 5 else prev
            change_1d = ((current - prev) / prev) * 100
            change_5d = ((current - week_ago) / week_ago) * 100

            results[key] = {
                "name": info["name"],
                "value": round(current, 2),
                "change_1d": round(change_1d, 2),
                "change_5d": round(change_5d, 2),
                "unit": info["unit"],
                "trend": "UP" if change_5d > 0.5 else "DOWN" if change_5d < -0.5 else "FLAT",
            }
        except Exception:
            continue

    # Calculate yield curve (10Y - 2Y)
    if "US10Y" in results and "US2Y" in results:
        spread = results["US10Y"]["value"] - results["US2Y"]["value"]
        results["YIELD_CURVE"] = {
            "name": "Yield Curve (10Y-2Y)",
            "value": round(spread, 3),
            "unit": "%",
            "trend": "INVERTED" if spread < 0 else "NORMAL",
            "change_1d": 0,
            "change_5d": 0,
        }

    return results


def analyze_macro(macro_data):
    """
    Analyze macro data and generate impact assessments.
    Returns dict with risk_level, impacts per asset class, and warnings.
    """
    analysis = {
        "risk_level": "MEDIUM",
        "risk_score": 50,  # 0-100 (0=very safe, 100=very dangerous)
        "gold_bias": "NEUTRAL",
        "oil_bias": "NEUTRAL",
        "stock_bias": "NEUTRAL",
        "warnings": [],
        "insights": [],
    }

    score = 50  # Start neutral

    # --- VIX Analysis ---
    vix = macro_data.get("VIX", {})
    if vix:
        v = vix["value"]
        if v > 30:
            score += 25
            analysis["warnings"].append(f"VIX at {v} - EXTREME FEAR in markets")
            analysis["gold_bias"] = "BULLISH"  # Fear drives gold up
            analysis["stock_bias"] = "BEARISH"
        elif v > 25:
            score += 15
            analysis["warnings"].append(f"VIX at {v} - HIGH fear, market volatile")
            analysis["gold_bias"] = "BULLISH"
        elif v > 20:
            score += 5
            analysis["insights"].append(f"VIX at {v} - Elevated caution")
        elif v < 15:
            score -= 10
            analysis["insights"].append(f"VIX at {v} - Markets calm/complacent")
            analysis["stock_bias"] = "BULLISH"

    # --- India VIX ---
    india_vix = macro_data.get("INDIA_VIX", {})
    if india_vix:
        iv = india_vix["value"]
        if iv > 25:
            score += 10
            analysis["warnings"].append(f"India VIX at {iv} - Indian markets stressed")
        elif iv > 18:
            analysis["insights"].append(f"India VIX at {iv} - Moderate caution for NIFTY")

    # --- Dollar Index (DXY) ---
    dxy = macro_data.get("DXY", {})
    if dxy:
        if dxy["change_5d"] > 1.0:
            score += 10
            analysis["insights"].append(f"Dollar STRENGTHENING (+{dxy['change_5d']}% this week)")
            analysis["gold_bias"] = "BEARISH"  # Strong dollar = weak gold
            analysis["oil_bias"] = "BEARISH"   # Oil priced in USD
        elif dxy["change_5d"] < -1.0:
            score -= 5
            analysis["insights"].append(f"Dollar WEAKENING ({dxy['change_5d']}% this week)")
            analysis["gold_bias"] = "BULLISH"  # Weak dollar = gold goes up
            analysis["oil_bias"] = "BULLISH"

    # --- Bond Yields ---
    us10y = macro_data.get("US10Y", {})
    if us10y:
        if us10y["change_5d"] > 0.1:
            analysis["insights"].append(f"US 10Y yield RISING ({us10y['value']}%) - Hawkish signal")
            if analysis["gold_bias"] != "BULLISH":
                analysis["gold_bias"] = "BEARISH"  # Rising yields = bearish gold
        elif us10y["change_5d"] < -0.1:
            analysis["insights"].append(f"US 10Y yield FALLING ({us10y['value']}%) - Dovish signal")
            analysis["gold_bias"] = "BULLISH"

    # --- Yield Curve ---
    yc = macro_data.get("YIELD_CURVE", {})
    if yc and yc["trend"] == "INVERTED":
        score += 15
        analysis["warnings"].append(f"Yield curve INVERTED ({yc['value']}%) - Recession signal!")
        analysis["stock_bias"] = "BEARISH"
        analysis["gold_bias"] = "BULLISH"

    # --- USD/INR ---
    usdinr = macro_data.get("USDINR", {})
    if usdinr:
        if usdinr["change_5d"] > 0.5:
            analysis["insights"].append(f"Rupee WEAKENING (USD/INR {usdinr['value']}) - FII selling risk")
        elif usdinr["change_5d"] < -0.5:
            analysis["insights"].append(f"Rupee STRENGTHENING (USD/INR {usdinr['value']}) - FII inflow positive")

    # --- S&P 500 ---
    sp = macro_data.get("SP500", {})
    if sp:
        if sp["change_5d"] < -3:
            score += 15
            analysis["warnings"].append(f"S&P 500 CRASH ({sp['change_5d']}% this week)")
            analysis["gold_bias"] = "BULLISH"
            analysis["stock_bias"] = "BEARISH"
        elif sp["change_5d"] < -1.5:
            score += 5
            analysis["insights"].append(f"S&P 500 selling ({sp['change_5d']}% this week)")

    # Final risk level
    if score >= 75:
        analysis["risk_level"] = "EXTREME"
    elif score >= 60:
        analysis["risk_level"] = "HIGH"
    elif score >= 40:
        analysis["risk_level"] = "MEDIUM"
    else:
        analysis["risk_level"] = "LOW"

    analysis["risk_score"] = min(100, max(0, score))

    return analysis


# ============================================================
# NEWS & GEOPOLITICAL ANALYSIS
# ============================================================

NEWS_FEEDS = {
    "gold": {
        "url": "https://news.google.com/rss/search?q=gold+price+market+forecast&hl=en-US&gl=US&ceid=US:en",
        "label": "Gold & Precious Metals",
        "impacts": ["GOLD", "SILVER", "PLATINUM"],
    },
    "oil": {
        "url": "https://news.google.com/rss/search?q=crude+oil+OPEC+price&hl=en-US&gl=US&ceid=US:en",
        "label": "Oil & Energy",
        "impacts": ["CRUDE_OIL", "BRENT_CRUDE", "NATURAL_GAS"],
    },
    "geopolitical": {
        "url": "https://news.google.com/rss/search?q=geopolitical+tensions+war+conflict+market+impact&hl=en-US&gl=US&ceid=US:en",
        "label": "Geopolitical Tensions",
        "impacts": ["GOLD", "CRUDE_OIL", "ALL"],
    },
    "fed": {
        "url": "https://news.google.com/rss/search?q=Federal+Reserve+interest+rate+inflation&hl=en-US&gl=US&ceid=US:en",
        "label": "Fed & US Policy",
        "impacts": ["GOLD", "DXY", "STOCKS"],
    },
    "india": {
        "url": "https://news.google.com/rss/search?q=India+RBI+economy+market+Nifty&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "India Economy",
        "impacts": ["STOCKS", "USDINR"],
    },
    "trade_war": {
        "url": "https://news.google.com/rss/search?q=trade+war+tariff+sanctions+China+US&hl=en-US&gl=US&ceid=US:en",
        "label": "Trade Wars & Sanctions",
        "impacts": ["GOLD", "COPPER", "STOCKS", "ALL"],
    },
}

# Keyword sentiment dictionaries
BULLISH_KEYWORDS = [
    "surge", "soar", "rally", "jump", "gain", "rise", "high", "record",
    "bullish", "boom", "up", "climb", "strong", "positive", "recover",
    "stimulus", "cut", "ease", "dovish", "boost", "optimism", "growth",
    "peace", "deal", "agreement", "ceasefire", "support",
]

BEARISH_KEYWORDS = [
    "crash", "plunge", "fall", "drop", "decline", "low", "fear", "panic",
    "bearish", "sell", "down", "weak", "negative", "recession", "crisis",
    "war", "conflict", "tension", "sanctions", "tariff", "threat",
    "inflation", "hawkish", "hike", "collapse", "default", "risk",
    "attack", "missile", "nuclear", "escalation", "invasion",
]

# Specific geopolitical event keywords and their impacts
GEO_EVENT_IMPACTS = {
    # Middle East
    "iran": {"GOLD": +2, "CRUDE_OIL": +3, "STOCKS": -1},
    "israel": {"GOLD": +2, "CRUDE_OIL": +2, "STOCKS": -1},
    "hamas": {"GOLD": +1, "CRUDE_OIL": +2, "STOCKS": -1},
    "hezbollah": {"GOLD": +1, "CRUDE_OIL": +2, "STOCKS": -1},
    "yemen": {"GOLD": +1, "CRUDE_OIL": +2, "STOCKS": 0},
    "houthi": {"GOLD": +1, "CRUDE_OIL": +2, "STOCKS": 0},
    "red sea": {"CRUDE_OIL": +2, "STOCKS": -1, "GOLD": +1},
    "suez": {"CRUDE_OIL": +3, "GOLD": +1, "STOCKS": -1},
    "opec": {"CRUDE_OIL": +2, "GOLD": 0, "STOCKS": 0},

    # Russia/Ukraine
    "russia": {"GOLD": +2, "CRUDE_OIL": +2, "NATURAL_GAS": +3, "STOCKS": -1},
    "ukraine": {"GOLD": +2, "CRUDE_OIL": +1, "NATURAL_GAS": +3, "STOCKS": -1},
    "nato": {"GOLD": +1, "STOCKS": -1, "CRUDE_OIL": +1},

    # China
    "china trade": {"GOLD": +1, "COPPER": -2, "STOCKS": -2},
    "china taiwan": {"GOLD": +3, "STOCKS": -3, "CRUDE_OIL": +2},
    "taiwan": {"GOLD": +2, "STOCKS": -2, "COPPER": -1},
    "tariff": {"GOLD": +1, "STOCKS": -2, "COPPER": -1},
    "sanctions": {"GOLD": +2, "CRUDE_OIL": +1, "STOCKS": -1},

    # Central Banks
    "fed rate cut": {"GOLD": +3, "STOCKS": +2, "DXY": -2},
    "fed rate hike": {"GOLD": -3, "STOCKS": -2, "DXY": +2},
    "rbi rate": {"STOCKS_IN": +1, "GOLD": 0},
    "inflation high": {"GOLD": +2, "STOCKS": -1},
    "inflation low": {"GOLD": -1, "STOCKS": +1},
    "recession": {"GOLD": +3, "STOCKS": -3, "CRUDE_OIL": -2},

    # India specific
    "india election": {"STOCKS_IN": -1, "GOLD": +1},
    "india gdp": {"STOCKS_IN": +1},
    "fii selling": {"STOCKS_IN": -2},
    "fii buying": {"STOCKS_IN": +2},
    "rupee fall": {"GOLD": +1, "STOCKS_IN": -1},

    # Misc
    "nuclear": {"GOLD": +5, "STOCKS": -5, "CRUDE_OIL": +3},
    "pandemic": {"GOLD": +3, "STOCKS": -3, "CRUDE_OIL": -3},
    "default": {"GOLD": +3, "STOCKS": -3},
    "bank failure": {"GOLD": +3, "STOCKS": -2},
}


def fetch_news(max_per_feed=10):
    """Fetch news headlines from Google News RSS feeds."""
    if feedparser is None:
        print("[NEWS] feedparser not installed. Run: pip install feedparser")
        return {}

    all_news = {}
    for key, feed_info in NEWS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_info["url"])
            headlines = []
            for entry in feed.entries[:max_per_feed]:
                headlines.append({
                    "title": entry.get("title", ""),
                    "published": entry.get("published", ""),
                    "source": entry.get("source", {}).get("title", ""),
                    "link": entry.get("link", ""),
                })
            all_news[key] = {
                "label": feed_info["label"],
                "impacts": feed_info["impacts"],
                "headlines": headlines,
                "count": len(headlines),
            }
        except Exception as e:
            print(f"[NEWS] Failed to fetch {key}: {e}")

    return all_news


def analyze_sentiment(headlines):
    """
    Analyze sentiment of news headlines using keyword matching.
    Returns score from -1.0 (very bearish) to +1.0 (very bullish).
    """
    if not headlines:
        return 0.0

    bullish_count = 0
    bearish_count = 0

    for h in headlines:
        title = h["title"].lower()
        for kw in BULLISH_KEYWORDS:
            if kw in title:
                bullish_count += 1
        for kw in BEARISH_KEYWORDS:
            if kw in title:
                bearish_count += 1

    total = bullish_count + bearish_count
    if total == 0:
        return 0.0

    return round((bullish_count - bearish_count) / total, 2)


def detect_geo_events(news_data):
    """
    Detect specific geopolitical events from headlines and map to instrument impacts.
    Returns list of detected events with their impacts.
    """
    detected = []
    all_titles = []

    for feed_key, feed_data in news_data.items():
        for h in feed_data.get("headlines", []):
            all_titles.append(h["title"].lower())

    combined_text = " ".join(all_titles)

    for event_key, impacts in GEO_EVENT_IMPACTS.items():
        if event_key in combined_text:
            # Count occurrences for severity
            count = combined_text.count(event_key)
            severity = min(3, count)  # Cap at 3

            detected.append({
                "event": event_key,
                "mentions": count,
                "severity": severity,
                "impacts": impacts,
            })

    # Sort by severity (most impactful first)
    detected.sort(key=lambda x: x["severity"], reverse=True)
    return detected


def analyze_news(news_data):
    """
    Full news analysis: sentiment per category + geopolitical event detection.
    """
    analysis = {
        "sentiments": {},
        "geo_events": [],
        "top_headlines": [],
        "gold_news_bias": "NEUTRAL",
        "oil_news_bias": "NEUTRAL",
        "stock_news_bias": "NEUTRAL",
        "overall_sentiment": "NEUTRAL",
    }

    # Sentiment per category
    for key, feed_data in news_data.items():
        sentiment = analyze_sentiment(feed_data.get("headlines", []))
        analysis["sentiments"][key] = {
            "label": feed_data.get("label", key),
            "score": sentiment,
            "bias": "BULLISH" if sentiment > 0.15 else "BEARISH" if sentiment < -0.15 else "MIXED",
        }

    # Geo events
    analysis["geo_events"] = detect_geo_events(news_data)

    # Top headlines (most recent from each feed)
    for key, feed_data in news_data.items():
        if feed_data.get("headlines"):
            h = feed_data["headlines"][0]
            analysis["top_headlines"].append({
                "category": feed_data["label"],
                "title": h["title"],
                "source": h.get("source", ""),
            })

    # Aggregate biases
    gold_score = analysis["sentiments"].get("gold", {}).get("score", 0)
    oil_score = analysis["sentiments"].get("oil", {}).get("score", 0)
    geo_score = analysis["sentiments"].get("geopolitical", {}).get("score", 0)
    india_score = analysis["sentiments"].get("india", {}).get("score", 0)

    # Geopolitical tensions are BULLISH for gold, BEARISH for stocks
    if geo_score < -0.2:  # Bearish geo news = tensions = gold up
        analysis["gold_news_bias"] = "BULLISH"
        analysis["stock_news_bias"] = "BEARISH"
    elif geo_score > 0.2:
        analysis["gold_news_bias"] = "BEARISH"
        analysis["stock_news_bias"] = "BULLISH"

    # Override with specific gold/oil sentiment
    if gold_score > 0.15:
        analysis["gold_news_bias"] = "BULLISH"
    elif gold_score < -0.15:
        analysis["gold_news_bias"] = "BEARISH"

    if oil_score > 0.15:
        analysis["oil_news_bias"] = "BULLISH"
    elif oil_score < -0.15:
        analysis["oil_news_bias"] = "BEARISH"

    if india_score > 0.15:
        analysis["stock_news_bias"] = "BULLISH"
    elif india_score < -0.15:
        analysis["stock_news_bias"] = "BEARISH"

    # Overall
    avg = (gold_score + oil_score + geo_score + india_score) / 4
    analysis["overall_sentiment"] = "BULLISH" if avg > 0.1 else "BEARISH" if avg < -0.1 else "MIXED"

    return analysis


# ============================================================
# COMBINED INTELLIGENCE REPORT
# ============================================================

def generate_market_intelligence():
    """
    Generate complete market intelligence report combining macro + news + geo.
    This is the main function called by the scanner/digest.
    """
    print("[INTEL] Fetching macro indicators...")
    macro_data = fetch_macro_data()
    macro_analysis = analyze_macro(macro_data)

    print("[INTEL] Fetching news & geopolitical data...")
    news_data = fetch_news(max_per_feed=15)
    news_analysis = analyze_news(news_data)

    # Combine biases
    combined = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "macro": macro_data,
        "macro_analysis": macro_analysis,
        "news_analysis": news_analysis,

        # Final combined biases (macro + news)
        "gold_outlook": _combine_bias(
            macro_analysis.get("gold_bias", "NEUTRAL"),
            news_analysis.get("gold_news_bias", "NEUTRAL")
        ),
        "oil_outlook": _combine_bias(
            macro_analysis.get("oil_bias", "NEUTRAL"),
            news_analysis.get("oil_news_bias", "NEUTRAL")
        ),
        "stock_outlook": _combine_bias(
            macro_analysis.get("stock_bias", "NEUTRAL"),
            news_analysis.get("stock_news_bias", "NEUTRAL")
        ),
        "risk_level": macro_analysis["risk_level"],
        "risk_score": macro_analysis["risk_score"],
    }

    return combined


def _combine_bias(macro_bias, news_bias):
    """Combine macro and news biases into final outlook."""
    scores = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
    total = scores.get(macro_bias, 0) + scores.get(news_bias, 0)
    if total >= 1:
        return "BULLISH"
    elif total <= -1:
        return "BEARISH"
    return "NEUTRAL"


def format_intelligence_report(intel):
    """Format the intelligence report for Telegram."""
    lines = []
    lines.append("MARKET INTELLIGENCE REPORT")
    lines.append("=" * 35)
    lines.append(f"Time: {intel['timestamp']}")

    # Risk Level
    risk = intel["risk_level"]
    risk_bar = _risk_bar(intel["risk_score"])
    lines.append(f"\nRISK LEVEL: {risk} {risk_bar}")

    # Outlooks
    lines.append(f"\nOUTLOOK:")
    lines.append(f"  Gold:   {_bias_icon(intel['gold_outlook'])} {intel['gold_outlook']}")
    lines.append(f"  Oil:    {_bias_icon(intel['oil_outlook'])} {intel['oil_outlook']}")
    lines.append(f"  Stocks: {_bias_icon(intel['stock_outlook'])} {intel['stock_outlook']}")

    # Macro Dashboard
    macro = intel.get("macro", {})
    if macro:
        lines.append(f"\nMACRO DASHBOARD:")
        lines.append("-" * 30)
        for key in ["VIX", "INDIA_VIX", "DXY", "US10Y", "SP500", "USDINR"]:
            m = macro.get(key)
            if m:
                arrow = "^" if m["change_5d"] > 0 else "v" if m["change_5d"] < 0 else "="
                lines.append(f"  {m['name']}: {m['value']}{m['unit']} [{arrow} {m['change_5d']:+.1f}% 5d]")

        yc = macro.get("YIELD_CURVE")
        if yc:
            status = "INVERTED!" if yc["value"] < 0 else "Normal"
            lines.append(f"  Yield Curve: {yc['value']}{yc['unit']} ({status})")

    # Warnings
    warnings = intel.get("macro_analysis", {}).get("warnings", [])
    if warnings:
        lines.append(f"\n[!] WARNINGS:")
        for w in warnings:
            lines.append(f"  - {w}")

    # Insights
    insights = intel.get("macro_analysis", {}).get("insights", [])
    if insights:
        lines.append(f"\nINSIGHTS:")
        for i in insights[:5]:
            lines.append(f"  - {i}")

    # Geopolitical Events
    geo_events = intel.get("news_analysis", {}).get("geo_events", [])
    if geo_events:
        lines.append(f"\nGEO-POLITICAL EVENTS DETECTED:")
        lines.append("-" * 30)
        for ev in geo_events[:6]:
            impacts_str = ", ".join([
                f"{k}: {'UP' if v > 0 else 'DOWN'}"
                for k, v in ev["impacts"].items()
            ])
            severity_dots = "*" * ev["severity"]
            lines.append(f"  {severity_dots} {ev['event'].upper()} ({ev['mentions']}x)")
            lines.append(f"    Impact: {impacts_str}")

    # Top Headlines
    top = intel.get("news_analysis", {}).get("top_headlines", [])
    if top:
        lines.append(f"\nTOP HEADLINES:")
        lines.append("-" * 30)
        for h in top[:6]:
            source = f" ({h['source']})" if h.get("source") else ""
            lines.append(f"  [{h['category']}]")
            lines.append(f"  {h['title'][:100]}{source}")

    # News Sentiment
    sentiments = intel.get("news_analysis", {}).get("sentiments", {})
    if sentiments:
        lines.append(f"\nNEWS SENTIMENT:")
        for key, s in sentiments.items():
            bar = _sentiment_bar(s["score"])
            lines.append(f"  {s['label']}: {bar} ({s['bias']})")

    lines.append("")
    lines.append("=" * 35)
    lines.append("Intelligence report, NOT financial advice.")

    return "\n".join(lines)


def _risk_bar(score):
    """Visual risk bar."""
    filled = int(score / 10)
    return "[" + "#" * filled + "." * (10 - filled) + "]"


def _bias_icon(bias):
    """Text icon for bias."""
    if bias == "BULLISH":
        return "[UP]"
    elif bias == "BEARISH":
        return "[DOWN]"
    return "[--]"


def _sentiment_bar(score):
    """Visual sentiment bar from -1 to +1."""
    # Map -1..+1 to 0..10
    pos = int((score + 1) * 5)
    pos = max(0, min(10, pos))
    bar = "." * pos + "|" + "." * (10 - pos)
    return f"[{bar}]"


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    print("Generating Market Intelligence Report...")
    print("=" * 50)
    intel = generate_market_intelligence()
    report = format_intelligence_report(intel)
    print(report)
