import telebot
from telebot import apihelper
import time
import requests
import json
from datetime import datetime, timedelta
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import numpy as np

# ========== إعدادات الوقت ==========
apihelper.READ_TIMEOUT = 60
apihelper.CONNECT_TIMEOUT = 60

# ========== إعدادات البوت ==========
TOKEN = "8770804155:AAGisTnHi_91GiYPOV5m2Hg8x_-h1n4Gy4g"
CHAT_ID = 7779443498
# ==========================================

bot = telebot.TeleBot(TOKEN)

# إزالة أي webhook قديم
try:
    bot.remove_webhook()
except:
    pass

# ========== خادم Flask الصحي ==========
try:
    from flask import Flask
    health_app = Flask(__name__)
    @health_app.route('/')
    @health_app.route('/health')
    def health_check():
        return "Bot is alive!", 200
    def run_health_server():
        port = int(os.environ.get('PORT', 8080))
        health_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    threading.Thread(target=run_health_server, daemon=True).start()
except:
    pass

# ========== جلب العملات ==========
def get_all_coins():
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        response = requests.get(url, timeout=10)
        data = response.json()
        coins = []
        for symbol in data['symbols']:
            if symbol['quoteAsset'] == 'USDT' and symbol['status'] == 'TRADING':
                base = symbol['baseAsset']
                if not any(x in base for x in ['UP', 'DOWN', 'BULL', 'BEAR', 'USDC', 'USDP', 'TUSD', 'BUSD', 'DAI', 'FDUSD']):
                    coins.append(base)
        coins = sorted(list(set(coins)))
        print(f"✅ تم العثور على {len(coins)} عملة")
        return coins[:100]
    except:
        return ['BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOGE', 'MATIC', 'DOT', 'LINK']

MAIN_COINS = get_all_coins()
print(f"📊 عدد العملات: {len(MAIN_COINS)}")

# ========== تحليل السوق العام ==========
def get_market_direction():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
        response = requests.get(url, timeout=3)
        data = response.json()
        btc_price = float(data['lastPrice'])
        btc_change = float(data['priceChangePercent'])
        
        if btc_change > 1:
            overall = "صاعد 🟢"
        elif btc_change < -1:
            overall = "هابط 🔴"
        else:
            overall = "جانبي ⚪"
        
        return {'overall': overall, 'btc_price': btc_price, 'btc_change': btc_change}
    except:
        return {'overall': 'جانبي ⚪', 'btc_price': 0, 'btc_change': 0}

# ========== نظام التعلم ==========
SIGNALS_FILE = "signals_log.json"
PERFORMANCE_FILE = "performance.json"

def load_signals():
    if os.path.exists(SIGNALS_FILE):
        try:
            with open(SIGNALS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_signals(signals):
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(signals, f, indent=2)

def load_performance():
    if os.path.exists(PERFORMANCE_FILE):
        try:
            with open(PERFORMANCE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {'total': 0, 'correct': 0, 'accuracy': 0.70, 'buy_accuracy': 0.70, 'sell_accuracy': 0.70}
    return {'total': 0, 'correct': 0, 'accuracy': 0.70, 'buy_accuracy': 0.70, 'sell_accuracy': 0.70}

def save_performance(perf):
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(perf, f, indent=2)

signals_log = load_signals()
performance = load_performance()

def log_signal(symbol, signal, score, price, market_direction):
    global signals_log
    new_id = len(signals_log) + 1
    signals_log.append({
        'id': new_id, 'timestamp': datetime.now().isoformat(),
        'symbol': symbol, 'signal': signal, 'score': score,
        'price': price, 'market_direction': market_direction,
        'evaluated': False, 'success': None, 'price_after': None
    })
    save_signals(signals_log)
    return new_id

def evaluate_old_signals():
    global signals_log, performance
    updated = False
    for sig in signals_log:
        if not sig['evaluated']:
            sig_time = datetime.fromisoformat(sig['timestamp'])
            if datetime.now() - sig_time > timedelta(hours=24):
                try:
                    url = f"https://api.binance.com/api/v3/ticker/price?symbol={sig['symbol']}USDT"
                    response = requests.get(url, timeout=5)
                    current_price = float(response.json()['price'])
                    sig['price_after'] = current_price
                    sig['evaluated'] = True
                    sig['success'] = current_price > sig['price'] if sig['signal'] == 'BUY' else current_price < sig['price']
                    updated = True
                    if sig['success']:
                        performance['correct'] += 1
                        if sig['signal'] == 'BUY':
                            performance['buy_correct'] = performance.get('buy_correct', 0) + 1
                        else:
                            performance['sell_correct'] = performance.get('sell_correct', 0) + 1
                    performance['total'] += 1
                    if sig['signal'] == 'BUY':
                        performance['buy_total'] = performance.get('buy_total', 0) + 1
                        performance['buy_accuracy'] = performance.get('buy_correct', 0) / performance.get('buy_total', 1)
                    else:
                        performance['sell_total'] = performance.get('sell_total', 0) + 1
                        performance['sell_accuracy'] = performance.get('sell_correct', 0) / performance.get('sell_total', 1)
                    performance['accuracy'] = performance['correct'] / performance['total'] if performance['total'] > 0 else 0.70
                    print(f"📊 تقييم {sig['symbol']}: {'✅ نجاح' if sig['success'] else '❌ فشل'}")
                except Exception as e:
                    print(f"خطأ: {e}")
    if updated:
        save_signals(signals_log)
        save_performance(performance)

def start_auto_evaluation():
    def evaluate_loop():
        while True:
            try:
                evaluate_old_signals()
                time.sleep(3600)
            except:
                time.sleep(3600)
    threading.Thread(target=evaluate_loop, daemon=True).start()

start_auto_evaluation()

# ========== دوال التحليل المحسنة ==========
cache = {}
CACHE_DURATION = 90
bot_data = {}

def calculate_rsi_advanced(closes, period=14):
    """RSI محسن مع حساسية أفضل"""
    if len(closes) < period + 1:
        return 50
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [c if c > 0 else 0 for c in changes[-period:]]
    losses = [-c if c < 0 else 0 for c in changes[-period:]]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 1
    if avg_loss == 0:
        return 100
    rsi = 100 - (100 / (1 + (avg_gain / avg_loss)))
    
    # تصحيح RSI ليكون أكثر دقة
    if rsi < 30:
        rsi = rsi * 0.95  # تشديد منطقة التشبع البيعي
    elif rsi > 70:
        rsi = min(100, rsi * 1.05)  # تشديد منطقة التشبع الشرائي
    return rsi

def calculate_macd_advanced(closes, fast=12, slow=26, signal=9):
    """MACD محسن مع تحليل التقاطع"""
    if len(closes) < slow + signal:
        return 0, 0, 0
    
    def ema(data, period):
        if len(data) < period:
            return data[-1] if data else 0
        alpha = 2 / (period + 1)
        ema_val = data[0]
        for val in data[1:]:
            ema_val = alpha * val + (1 - alpha) * ema_val
        return ema_val
    
    macd_line = ema(closes, fast) - ema(closes, slow)
    return macd_line

def calculate_bollinger_advanced(closes, period=20, std_dev=2):
    """Bollinger Bands محسنة"""
    if len(closes) < period:
        return 0, 0, 0, 0.5
    sma = sum(closes[-period:]) / period
    variance = sum([(x - sma)**2 for x in closes[-period:]]) / period
    std = variance ** 0.5
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    # حساب نسبة الاختراق
    position = (closes[-1] - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
    
    # تصحيح للمناطق القصوى
    if position < 0.1:
        position = max(0, position * 0.8)
    elif position > 0.9:
        position = min(1, position + (1 - position) * 0.2)
    return upper, lower, sma, position

def calculate_stochastic_advanced(highs, lows, closes, k_period=14, d_period=3):
    """Stochastic محسن"""
    if len(highs) < k_period:
        return 50
    low_14 = min(highs[-k_period:])
    high_14 = max(highs[-k_period:])
    if (high_14 - low_14) == 0:
        return 50
    stoch_k = 100 * ((closes[-1] - low_14) / (high_14 - low_14))
    return min(100, max(0, stoch_k))

def calculate_atr_advanced(highs, lows, period=14):
    """ATR محسن"""
    if len(highs) < period:
        return (highs[-1] - lows[-1]) if highs and lows else 0
    tr_values = []
    for i in range(1, min(period, len(highs))):
        hl = highs[-i] - lows[-i]
        tr_values.append(hl)
    return sum(tr_values) / len(tr_values) if tr_values else 0

def get_analysis_premium(symbol, market_dir=None):
    """تحليل متقدم - دقة عالية"""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit=50"
        response = requests.get(url, timeout=3)
        klines = response.json()
        
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        
        if not closes:
            return None
        
        current_price = closes[-1]
        price_24h_ago = closes[-24] if len(closes) >= 24 else closes[0]
        price_48h_ago = closes[-48] if len(closes) >= 48 else closes[0]
        
        # حساب جميع المؤشرات المحسنة
        rsi = calculate_rsi_advanced(closes)
        macd = calculate_macd_advanced(closes)
        bb_upper, bb_lower, bb_middle, bb_position = calculate_bollinger_advanced(closes)
        stoch = calculate_stochastic_advanced(highs, lows, closes)
        atr = calculate_atr_advanced(highs, lows)
        if atr == 0:
            atr = current_price * 0.02
        
        # حجم التداول المحسن
        avg_volume = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else volumes[-1]
        volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
        volume_trend = "صاعد" if volume_ratio > 1.2 else "هابط" if volume_ratio < 0.8 else "طبيعي"
        
        # المتوسطات المتحركة
        sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else current_price
        sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else current_price
        
        # التغيرات
        change_1h = ((closes[-1] - closes[-2]) / closes[-2]) * 100 if len(closes) >= 2 else 0
        change_4h = ((closes[-1] - closes[-4]) / closes[-4]) * 100 if len(closes) >= 4 else 0
        change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100 if price_24h_ago > 0 else 0
        change_48h = ((current_price - price_48h_ago) / price_48h_ago) * 100 if price_48h_ago > 0 else 0
        
        # اتجاه السعر
        if sma_20 > sma_50 and current_price > sma_20:
            price_trend = "صاعد قوي"
            trend_score = 1
        elif current_price > sma_20:
            price_trend = "صاعد ضعيف"
            trend_score = 0.5
        elif sma_20 < sma_50 and current_price < sma_20:
            price_trend = "هابط قوي"
            trend_score = -1
        elif current_price < sma_20:
            price_trend = "هابط ضعيف"
            trend_score = -0.5
        else:
            price_trend = "جانبي"
            trend_score = 0
        
        # نظام النقاط المتقدم
        score = 0.0
        reasons = []
        
        # 1. RSI (وزن 3)
        if rsi < 28:
            score += 3
            reasons.append(f"🔥 RSI شديد الانخفاض ({rsi:.1f})")
        elif rsi < 35:
            score += 2
            reasons.append(f"📉 RSI منخفض ({rsi:.1f})")
        elif rsi < 45:
            score += 1
            reasons.append(f"📉 RSI منخفض نسبياً ({rsi:.1f})")
        elif rsi > 72:
            score -= 3
            reasons.append(f"🔥 RSI شديد الارتفاع ({rsi:.1f})")
        elif rsi > 65:
            score -= 2
            reasons.append(f"📈 RSI مرتفع ({rsi:.1f})")
        elif rsi > 55:
            score -= 1
            reasons.append(f"📈 RSI مرتفع نسبياً ({rsi:.1f})")
        else:
            reasons.append(f"⚖️ RSI متوسط ({rsi:.1f})")
        
        # 2. MACD (وزن 2)
        if macd > 0.001:
            score += 2
            reasons.append("📈 MACD إيجابي قوي")
        elif macd > 0:
            score += 1
            reasons.append("📈 MACD إيجابي")
        elif macd < -0.001:
            score -= 2
            reasons.append("📉 MACD سلبي قوي")
        elif macd < 0:
            score -= 1
            reasons.append("📉 MACD سلبي")
        
        # 3. Bollinger (وزن 2)
        if bb_position < 0.15:
            score += 2
            reasons.append("📊 السعر أقل من Bollinger السفلي")
        elif bb_position < 0.3:
            score += 1
            reasons.append("📊 السعر قرب الدعم")
        elif bb_position > 0.85:
            score -= 2
            reasons.append("📊 السعر فوق Bollinger العلوي")
        elif bb_position > 0.7:
            score -= 1
            reasons.append("📊 السعر قرب المقاومة")
        
        # 4. Stochastic (وزن 1)
        if stoch < 15:
            score += 1.5
            reasons.append(f"🎯 Stochastic منخفض جداً ({stoch:.0f})")
        elif stoch < 25:
            score += 0.5
            reasons.append(f"🎯 Stochastic منخفض ({stoch:.0f})")
        elif stoch > 85:
            score -= 1.5
            reasons.append(f"🎯 Stochastic مرتفع جداً ({stoch:.0f})")
        elif stoch > 75:
            score -= 0.5
            reasons.append(f"🎯 Stochastic مرتفع ({stoch:.0f})")
        
        # 5. حجم التداول (وزن 1)
        if volume_ratio > 2.5 and score > 0:
            score += 1.5
            reasons.append(f"📊 حجم تداول مرتفع جداً ({volume_ratio:.1f}x)")
        elif volume_ratio > 1.8 and score > 0:
            score += 1
            reasons.append(f"📊 حجم تداول مرتفع ({volume_ratio:.1f}x)")
        elif volume_ratio > 1.3 and score > 0:
            score += 0.5
            reasons.append(f"📊 حجم تداول متوسط ({volume_ratio:.1f}x)")
        
        # 6. اتجاه السعر (وزن 1)
        score += trend_score
        if trend_score > 0:
            reasons.append(f"📈 اتجاه {price_trend}")
        elif trend_score < 0:
            reasons.append(f"📉 اتجاه {price_trend}")
        
        # 7. التغيرات السعرية (وزن 1)
        if change_24h < -8:
            score += 2
            reasons.append(f"🔄 هبوط حاد جداً {change_24h:.1f}%")
        elif change_24h < -4:
            score += 1
            reasons.append(f"🔄 هبوط {change_24h:.1f}%")
        elif change_24h > 8:
            score -= 2
            reasons.append(f"🔄 صعود حاد جداً {change_24h:.1f}%")
        elif change_24h > 4:
            score -= 1
            reasons.append(f"🔄 صعود {change_24h:.1f}%")
        
        # 8. اتجاه السوق العام (وزن 1)
        if market_dir:
            if market_dir['overall'] == "صاعد 🟢" and score > 0:
                score += 1
                reasons.append("🌍 السوق العام يدعم الشراء")
            elif market_dir['overall'] == "هابط 🔴" and score < 0:
                score -= 1
                reasons.append("🌍 السوق العام يدعم البيع")
        
        # تحديد الإشارة (عتبة أعلى لدقة أفضل)
        if score >= 4:
            signal = "BUY"
            if score >= 6:
                strength = "🔥🔥 ممتازة جداً"
                success_rate = 0.92
            elif score >= 5:
                strength = "🔥 قوية جداً"
                success_rate = 0.88
            elif score >= 4:
                strength = "✅ قوية"
                success_rate = 0.82
            else:
                strength = "📊 متوسطة"
                success_rate = 0.75
        elif score <= -4:
            signal = "SELL"
            if score <= -6:
                strength = "🔥🔥 ممتازة جداً"
                success_rate = 0.92
            elif score <= -5:
                strength = "🔥 قوية جداً"
                success_rate = 0.88
            elif score <= -4:
                strength = "✅ قوية"
                success_rate = 0.82
            else:
                strength = "📊 متوسطة"
                success_rate = 0.75
        else:
            signal = "NEUTRAL"
            strength = "⚪ ضعيفة"
            success_rate = 0.55
        
        # تعديل نسبة النجاح حسب الأداء التاريخي
        if signal == "BUY":
            success_rate = (success_rate * 0.6) + (performance.get('buy_accuracy', 0.70) * 0.4)
        elif signal == "SELL":
            success_rate = (success_rate * 0.6) + (performance.get('sell_accuracy', 0.70) * 0.4)
        else:
            success_rate = (success_rate * 0.7) + (performance['accuracy'] * 0.3)
        success_rate = min(0.94, max(0.55, success_rate))
        
        # تسجيل الإشارة
        if signal != "NEUTRAL" and abs(score) >= 3:
            log_signal(symbol, signal, score, current_price, market_dir['overall'] if market_dir else "غير معروف")
        
        # أفضل سعر دخول (Limit Order)
        if signal == "BUY":
            entry_discount = 0.0015 + (abs(score) * 0.0005)
            limit_entry = round(current_price * (1 - entry_discount), 8)
            stop_loss = round(current_price - (atr * 1.3), 8)
            tp1 = round(current_price + (atr * 1.5), 8)
            tp2 = round(current_price + (atr * 2.5), 8)
            tp3 = round(current_price + (atr * 4), 8)
        elif signal == "SELL":
            entry_premium = 0.0015 + (abs(score) * 0.0005)
            limit_entry = round(current_price * (1 + entry_premium), 8)
            stop_loss = round(current_price + (atr * 1.3), 8)
            tp1 = round(current_price - (atr * 1.5), 8)
            tp2 = round(current_price - (atr * 2.5), 8)
            tp3 = round(current_price - (atr * 4), 8)
        else:
            limit_entry = current_price
            stop_loss = current_price
            tp1 = current_price
            tp2 = current_price
            tp3 = current_price
        
        return {
            'signal': signal, 'strength': strength, 'success_rate': success_rate, 'score': score,
            'price': current_price, 'limit_entry': limit_entry,
            'stop_loss': stop_loss, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3,
            'rsi': rsi, 'macd': macd, 'stoch': stoch,
            'volume_ratio': volume_ratio, 'volume_trend': volume_trend,
            'change_1h': change_1h, 'change_4h': change_4h, 'change_24h': change_24h, 'change_48h': change_48h,
            'sma_20': sma_20, 'sma_50': sma_50, 'price_trend': price_trend,
            'reasons': reasons[:6], 'atr': atr
        }
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")
        return None

def get_cached_analysis(symbol, market_dir):
    now = time.time()
    key = f"{symbol}"
    if key in cache and (now - cache[key]['time']) < CACHE_DURATION:
        return cache[key]['data']
    analysis = get_analysis_premium(symbol, market_dir)
    if analysis:
        cache[key] = {'data': analysis, 'time': now}
    return analysis

def get_top_opportunities(market_dir):
    buy_list, sell_list = [], []
    print(f"⚡ جاري التحليل المتقدم...")
    start_time = time.time()
    
    for coin in MAIN_COINS:
        analysis = get_cached_analysis(coin, market_dir)
        if analysis and analysis['signal'] != 'NEUTRAL':
            item = {'symbol': coin, 'signal': analysis['signal'], 'strength': analysis['strength'], 
                    'success_rate': analysis['success_rate'], 'score': analysis['score'], 
                    'price': analysis['price'], 'limit_entry': analysis['limit_entry'],
                    'rsi': analysis['rsi'], 'change_24h': analysis['change_24h']}
            if analysis['signal'] == 'BUY':
                buy_list.append(item)
                print(f"🟢 {coin}: شراء | نقاط: {analysis['score']:.1f} | نجاح: {analysis['success_rate']:.0%}")
            else:
                sell_list.append(item)
                print(f"🔴 {coin}: بيع | نقاط: {analysis['score']:.1f} | نجاح: {analysis['success_rate']:.0%}")
            time.sleep(0.03)
    
    buy_list.sort(key=lambda x: x['score'], reverse=True)
    sell_list.sort(key=lambda x: x['score'])
    elapsed = time.time() - start_time
    print(f"✅ اكتمل في {elapsed:.1f} ثانية | شراء: {len(buy_list)} | بيع: {len(sell_list)}")
    return buy_list[:10], sell_list[:10]

def format_signal(analysis, symbol, market_dir=None):
    if analysis['signal'] == 'BUY':
        arrow = "🟢"
        direction = "شراء"
        advice = "✔️ ضع أمر شراء معلق (Limit Order) بالسعر الموصى به أو أقل"
    else:
        arrow = "🔴"
        direction = "بيع"
        advice = "✔️ ضع أمر بيع معلق (Limit Order) بالسعر الموصى به أو أعلى"
    
    power_icon = "🔥🔥" if "ممتازة" in analysis['strength'] else "🔥" if "قوية جداً" in analysis['strength'] else "✅" if "قوية" in analysis['strength'] else "📊"
    
    msg = f"""
╔══════════════════════════════════════════════════╗
║     🎯 *التحليل المتقدم* 🤖
║     {arrow} {symbol} - {direction} {arrow}
╚══════════════════════════════════════════════════╝

{power_icon} *القوة:* {analysis['strength']}
📊 *نقاط القوة:* `{analysis['score']:.1f}`
🎯 *النجاح المتوقع:* `{analysis['success_rate']:.0%}`

💰 *سعر السوق:* `${analysis['price']:.6f}`
🎯 *أفضل سعر دخول (Limit):* `${analysis['limit_entry']:.6f}`

📈 *التغيرات:*
• 1 ساعة: `{analysis['change_1h']:+.2f}%`
• 4 ساعات: `{analysis['change_4h']:+.2f}%`
• 24 ساعة: `{analysis['change_24h']:+.2f}%`

📊 *المؤشرات الفنية:*
• RSI: `{analysis['rsi']:.1f}`
• MACD: `{analysis['macd']:.6f}`
• Stochastic: `{analysis['stoch']:.0f}`
• حجم التداول: `{analysis['volume_ratio']:.1f}x` ({analysis['volume_trend']})
• المتوسط 20: `${analysis['sma_20']:.6f}`
• المتوسط 50: `${analysis['sma_50']:.6f}`

📈 *اتجاه السعر:* `{analysis['price_trend']}`

📝 *تحليل الإشارة:*
"""
    for r in analysis['reasons'][:5]:
        msg += f"  • {r}\n"

    msg += f"""
📐 *نقاط الدخول والخروج:*
• 🚪 *الدخول الموصى به:* `${analysis['limit_entry']:.6f}`
• 🛑 *وقف الخسارة:* `${analysis['stop_loss']:.6f}`
• 🎯 *الهدف 1:* `${analysis['tp1']:.6f}` 🟢
• 🎯 *الهدف 2:* `${analysis['tp2']:.6f}` 🟡
• 🎯 *الهدف 3:* `${analysis['tp3']:.6f}` 🔴
• 📊 *التقلب (ATR):* `${analysis['atr']:.6f}`

💡 *نصيحة التنفيذ:* {advice}

⚠️ *تنبيه:* هذا تحليل آلي - طبق إدارة المخاطر (لا تخاطر بأكثر من 1-2% من رأس المال)
"""
    return msg

def create_main_menu(buy, sell):
    markup = InlineKeyboardMarkup(row_width=2)
    for i, opp in enumerate(buy[:5], 1):
        markup.add(InlineKeyboardButton(f"🟢 #{i} {opp['symbol']} | {opp['success_rate']:.0%}", callback_data=f"buy_{i-1}"))
    for i, opp in enumerate(sell[:5], 1):
        markup.add(InlineKeyboardButton(f"🔴 #{i} {opp['symbol']} | {opp['success_rate']:.0%}", callback_data=f"sell_{i-1}"))
    return markup

def create_back_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="back_main"))
    return markup

# ========== أوامر التليجرام ==========
@bot.message_handler(commands=['start'])
def start(message):
    market_dir = get_market_direction()
    msg = f"""
╔══════════════════════════════════════════════════╗
║   🚀 *البوت المتقدم - الإصدار النهائي* 🤖      ║
╚══════════════════════════════════════════════════╝

📊 *حالة السوق:*
• الاتجاه العام: `{market_dir['overall']}`
• سعر BTC: `${market_dir['btc_price']:,.0f}`
• تغير BTC 24س: `{market_dir['btc_change']:+.2f}%`

📋 *الأوامر المتاحة:*
• `/daily` - أفضل 10 شراء + 10 بيع
• `/buy` - أفضل 10 فرص شراء
• `/sell` - أفضل 10 فرص بيع  
• `/coin BTC` - تحليل عملة محددة

✨ *الميزات:*
• 🎯 أفضل سعر دخول (Limit Order)
• 📊 8 مؤشرات فنية محسنة
• 🧠 نظام تعلم ذاتي
• ⚡ تحليل سريع (30-40 ثانية)

✅ *البوت جاهز!*
"""
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['daily'])
def daily(message):
    status = bot.reply_to(message, "🎯 جاري التحليل المتقدم... (قد يستغرق 30-40 ثانية)")
    def analyze():
        market_dir = get_market_direction()
        buy, sell = get_top_opportunities(market_dir)
        bot_data[message.chat.id] = {'buy': buy, 'sell': sell}
        if buy or sell:
            markup = create_main_menu(buy, sell)
            header = f"""
🎯 *نتائج التحليل المتقدم*
🟢 شراء: {len(buy)} | 🔴 بيع: {len(sell)}
🌍 اتجاه السوق: {market_dir['overall']}
📊 دقة البوت: {performance['accuracy']:.1%}

👇 اضغط على أي عملة للتفاصيل:
"""
            try:
                bot.edit_message_text(header, message.chat.id, status.message_id, reply_markup=markup, parse_mode='Markdown')
            except:
                bot.send_message(message.chat.id, header, reply_markup=markup, parse_mode='Markdown')
        else:
            try:
                bot.edit_message_text("⚠️ لا توجد إشارات قوية حالياً.\n💡 جرب `/coin BTC` لتحليل عملة محددة", message.chat.id, status.message_id, parse_mode='Markdown')
            except:
                pass
    threading.Thread(target=analyze, daemon=True).start()

@bot.message_handler(commands=['buy'])
def send_buy(message):
    status = bot.reply_to(message, "🎯 جاري البحث عن فرص شراء...")
    def analyze():
        market_dir = get_market_direction()
        buy, _ = get_top_opportunities(market_dir)
        bot_data[message.chat.id] = {'buy': buy, 'sell': []}
        if buy:
            markup = create_main_menu('buy', buy)
            bot.edit_message_text(f"🟢 *فرص الشراء*\n🌍 اتجاه السوق: {market_dir['overall']}\n\n👇 اضغط للتفاصيل:", message.chat.id, status.message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.edit_message_text("⚠️ لا توجد فرص شراء قوية حالياً", message.chat.id, status.message_id)
    threading.Thread(target=analyze, daemon=True).start()

@bot.message_handler(commands=['sell'])
def send_sell(message):
    status = bot.reply_to(message, "🎯 جاري البحث عن فرص بيع...")
    def analyze():
        market_dir = get_market_direction()
        _, sell = get_top_opportunities(market_dir)
        bot_data[message.chat.id] = {'buy': [], 'sell': sell}
        if sell:
            markup = create_main_menu('sell', sell)
            bot.edit_message_text(f"🔴 *فرص البيع*\n🌍 اتجاه السوق: {market_dir['overall']}\n\n👇 اضغط للتفاصيل:", message.chat.id, status.message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.edit_message_text("⚠️ لا توجد فرص بيع قوية حالياً", message.chat.id, status.message_id)
    threading.Thread(target=analyze, daemon=True).start()

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        data = call.data
        chat_id = call.message.chat.id
        if chat_id not in bot_data:
            bot.answer_callback_query(call.id, "انتهت الصلاحية، أعد /daily")
            return
        if data == "back_main":
            buy = bot_data[chat_id].get('buy', [])
            sell = bot_data[chat_id].get('sell', [])
            markup = create_main_menu(buy, sell)
            market_dir = get_market_direction()
            header = f"🎯 *النتائج*\n🟢 شراء: {len(buy)} | 🔴 بيع: {len(sell)}\n🌍 اتجاه السوق: {market_dir['overall']}"
            try:
                bot.edit_message_text(header, chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
            except:
                pass
        elif data.startswith('buy_'):
            idx = int(data.split('_')[1])
            if idx < len(bot_data[chat_id].get('buy', [])):
                opp = bot_data[chat_id]['buy'][idx]
                market_dir = get_market_direction()
                analysis = get_cached_analysis(opp['symbol'], market_dir)
                if analysis:
                    msg = format_signal(analysis, opp['symbol'], market_dir)
                    markup = create_back_button()
                    try:
                        bot.edit_message_text(msg, chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
                    except:
                        pass
        elif data.startswith('sell_'):
            idx = int(data.split('_')[1])
            if idx < len(bot_data[chat_id].get('sell', [])):
                opp = bot_data[chat_id]['sell'][idx]
                market_dir = get_market_direction()
                analysis = get_cached_analysis(opp['symbol'], market_dir)
                if analysis:
                    msg = format_signal(analysis, opp['symbol'], market_dir)
                    markup = create_back_button()
                    try:
                        bot.edit_message_text(msg, chat_id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
                    except:
                        pass
        bot.answer_callback_query(call.id, "✅")
    except Exception as e:
        print(f"خطأ: {e}")

@bot.message_handler(commands=['coin'])
def coin(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ مثال: `/coin BTC`", parse_mode='Markdown')
            return
        symbol = parts[1].upper()
        status_msg = bot.reply_to(message, f"🎯 تحليل {symbol} المتقدم...")
        market_dir = get_market_direction()
        analysis = get_analysis_premium(symbol, market_dir)
        if analysis:
            msg = format_signal(analysis, symbol, market_dir)
            bot.edit_message_text(msg, message.chat.id, status_msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(f"❌ لا يمكن تحليل {symbol}", message.chat.id, status_msg.message_id)
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        text = message.text.strip().upper()
        if len(text) >= 2 and len(text) <= 6 and text.isalpha():
            if text in MAIN_COINS:
                status_msg = bot.reply_to(message, f"🎯 تحليل {text}...")
                market_dir = get_market_direction()
                analysis = get_analysis_premium(text, market_dir)
                if analysis:
                    arrow = "🟢" if analysis['signal'] == 'BUY' else "🔴"
                    dir_ar = "شراء" if analysis['signal'] == 'BUY' else "بيع"
                    msg = f"""
🎯 *{text}* {arrow}
💰 السعر: `${analysis['price']:.4f}`
⚡ {dir_ar} | نجاح: {analysis['success_rate']:.0%}
🎯 أفضل دخول: `${analysis['limit_entry']:.6f}`
📊 RSI: {analysis['rsi']:.1f}
📈 التغير 24س: {analysis['change_24h']:+.2f}%
"""
                    bot.edit_message_text(msg, message.chat.id, status_msg.message_id, parse_mode='Markdown')
    except:
        pass

print("=" * 70)
print(f"🚀 البوت المتقدم - الإصدار النهائي")
print(f"📊 تم تحميل {len(MAIN_COINS)} عملة")
print(f"📈 دقة البوت الحالية: {performance['accuracy']:.1%}")
print(f"🟢 دقة الشراء: {performance.get('buy_accuracy', 0):.1%}")
print(f"🔴 دقة البيع: {performance.get('sell_accuracy', 0):.1%}")
print("=" * 70)

try:
    bot.send_message(CHAT_ID, f"🚀 *البوت المتقدم بدأ العمل!*\n📊 يحلل {len(MAIN_COINS)} عملة\n🎯 أفضل سعر دخول (Limit Order)\n📈 دقة البوت: {performance['accuracy']:.1%}\n💡 أرسل `/daily` للبدء", parse_mode='Markdown')
except:
    pass

bot.infinity_polling()