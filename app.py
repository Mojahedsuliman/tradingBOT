import telebot
from telebot import apihelper
import time
import requests
import json
from datetime import datetime, timedelta
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from flask import Flask

# ========== إعدادات الوقت ==========
apihelper.READ_TIMEOUT = 60
apihelper.CONNECT_TIMEOUT = 60

# ========== إعدادات البوت ==========
TOKEN = "8770804155:AAGisTnHi_91GiYPOV5m2Hg8x_-h1n4Gy4g"
CHAT_ID = 7779443498
# ==========================================

bot = telebot.TeleBot(TOKEN)

# ========== إزالة أي webhook موجود ==========
try:
    bot.remove_webhook()
    print("✅ Webhook removed")
except:
    pass

# ========== جلب جميع العملات ==========
def get_all_coins():
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        coins = []
        for symbol in data['symbols']:
            if symbol['quoteAsset'] == 'USDT' and symbol['status'] == 'TRADING':
                base = symbol['baseAsset']
                if not any(x in base for x in ['UP', 'DOWN', 'BULL', 'BEAR', 'USDC', 'USDP', 'TUSD', 'BUSD', 'DAI']):
                    coins.append(base)
        
        coins = sorted(list(set(coins)))
        print(f"✅ تم العثور على {len(coins)} عملة")
        return coins[:100]
    except Exception as e:
        print(f"خطأ: {e}")
        return ['BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOGE', 'MATIC', 'DOT', 'LINK']

MAIN_COINS = get_all_coins()
print(f"📊 عدد العملات: {len(MAIN_COINS)}")

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
            return {'total': 0, 'correct': 0, 'accuracy': 0.70}
    return {'total': 0, 'correct': 0, 'accuracy': 0.70}

def save_performance(perf):
    with open(PERFORMANCE_FILE, 'w') as f:
        json.dump(perf, f, indent=2)

signals_log = load_signals()
performance = load_performance()

def log_signal(symbol, signal, score, price):
    global signals_log
    new_id = len(signals_log) + 1
    signals_log.append({
        'id': new_id,
        'timestamp': datetime.now().isoformat(),
        'symbol': symbol,
        'signal': signal,
        'score': score,
        'price': price,
        'evaluated': False,
        'success': None
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
                    
                    sig['evaluated'] = True
                    if sig['signal'] == 'BUY':
                        sig['success'] = current_price > sig['price']
                    else:
                        sig['success'] = current_price < sig['price']
                    
                    updated = True
                    
                    if sig['success']:
                        performance['correct'] += 1
                    performance['total'] += 1
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
            except Exception as e:
                print(f"خطأ: {e}")
            time.sleep(3600)
    threading.Thread(target=evaluate_loop, daemon=True).start()

start_auto_evaluation()

# ========== ذاكرة تخزين ==========
cache = {}
CACHE_DURATION = 45
bot_data = {}

# ========== دوال مساعدة ==========
def calculate_average(data):
    if not data:
        return 0
    return sum(data) / len(data)

def calculate_rsi(closes):
    if len(closes) < 15:
        return 50
    changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [c for c in changes[-14:] if c > 0]
    losses = [-c for c in changes[-14:] if c < 0]
    avg_gain = sum(gains) / 14 if gains else 0
    avg_loss = sum(losses) / 14 if losses else 1
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

def calculate_ema(data, period):
    if len(data) < period:
        return data[-1] if data else 0
    alpha = 2 / (period + 1)
    ema = data[0]
    for val in data[1:]:
        ema = alpha * val + (1 - alpha) * ema
    return ema

def calculate_atr(highs, lows, closes):
    if len(highs) < 15:
        return (highs[-1] - lows[-1]) if highs and lows else 0
    tr_values = []
    for i in range(1, min(14, len(highs))):
        hl = highs[-i] - lows[-i]
        hc = abs(highs[-i] - closes[-i-1]) if i < len(closes) else hl
        lc = abs(lows[-i] - closes[-i-1]) if i < len(closes) else hl
        tr_values.append(max(hl, hc, lc))
    return sum(tr_values) / len(tr_values) if tr_values else 0

def get_precise_analysis(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}USDT&interval=1h&limit=50"
        response = requests.get(url, timeout=5)
        klines = response.json()
        
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        
        if not closes:
            return None
        
        current_price = closes[-1]
        price_24h_ago = closes[-24] if len(closes) >= 24 else closes[0]
        
        rsi = calculate_rsi(closes)
        ema12 = calculate_ema(closes, 12)
        ema26 = calculate_ema(closes, 26)
        macd = ema12 - ema26
        
        sma20 = calculate_average(closes[-20:])
        variance = sum([(x - sma20)**2 for x in closes[-20:]]) / 20 if closes[-20:] else 0
        std = variance ** 0.5
        bb_lower = sma20 - (std * 2)
        bb_upper = sma20 + (std * 2)
        bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
        
        low_14 = min(lows[-14:]) if len(lows) >= 14 else min(lows)
        high_14 = max(highs[-14:]) if len(highs) >= 14 else max(highs)
        stoch = 100 * ((current_price - low_14) / (high_14 - low_14)) if (high_14 - low_14) > 0 else 50
        
        atr = calculate_atr(highs, lows, closes)
        if atr == 0:
            atr = current_price * 0.02
        
        avg_volume = calculate_average(volumes[-20:]) if len(volumes) >= 20 else volumes[-1]
        volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
        
        sma20_price = calculate_average(closes[-20:])
        sma50_price = calculate_average(closes[-50:]) if len(closes) >= 50 else sma20_price
        
        change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100 if price_24h_ago > 0 else 0
        
        # حساب النقاط
        score = 0
        reasons = []
        
        if rsi < 30:
            score += 3
            reasons.append(f"RSI شديد الانخفاض ({rsi:.1f})")
        elif rsi < 40:
            score += 2
            reasons.append(f"RSI منخفض ({rsi:.1f})")
        elif rsi > 70:
            score -= 3
            reasons.append(f"RSI مرتفع جداً ({rsi:.1f})")
        elif rsi > 60:
            score -= 2
            reasons.append(f"RSI مرتفع ({rsi:.1f})")
        
        if macd > 0.0005:
            score += 2
            reasons.append("MACD إيجابي")
        elif macd > 0:
            score += 1
        elif macd < -0.0005:
            score -= 2
            reasons.append("MACD سلبي")
        
        if bb_position < 0.15:
            score += 2
            reasons.append("السعر低于 Bollinger")
        elif bb_position > 0.85:
            score -= 2
            reasons.append("السعر فوق Bollinger")
        
        if stoch < 20:
            score += 1
            reasons.append(f"Stochastic منخفض ({stoch:.0f})")
        elif stoch > 80:
            score -= 1
            reasons.append(f"Stochastic مرتفع ({stoch:.0f})")
        
        if volume_ratio > 2 and score > 0:
            score += 1
            reasons.append(f"حجم مرتفع ({volume_ratio:.1f}x)")
        
        if current_price > sma20_price and sma20_price > sma50_price:
            score += 1
            reasons.append("اتجاه صاعد")
        elif current_price < sma20_price and sma20_price < sma50_price:
            score -= 1
            reasons.append("اتجاه هابط")
        
        if change_24h < -5:
            score += 2
            reasons.append(f"هبوط حاد {change_24h:.1f}%")
        elif change_24h > 5:
            score -= 2
            reasons.append(f"صعود حاد {change_24h:.1f}%")
        
        # تحديد الإشارة
        if score >= 2:
            signal = "BUY"
            if score >= 4:
                strength = "🔥 قوية جداً"
            elif score >= 3:
                strength = "✅ قوية"
            else:
                strength = "📊 متوسطة"
        elif score <= -2:
            signal = "SELL"
            if score <= -4:
                strength = "🔥 قوية جداً"
            elif score <= -3:
                strength = "✅ قوية"
            else:
                strength = "📊 متوسطة"
        else:
            signal = "NEUTRAL"
            strength = "⚪ ضعيفة"
        
        # نسبة النجاح
        abs_score = abs(score)
        if abs_score >= 5:
            success_rate = 0.88
        elif abs_score >= 3:
            success_rate = 0.82
        elif abs_score >= 2:
            success_rate = 0.75
        elif abs_score >= 1:
            success_rate = 0.68
        else:
            success_rate = 0.60
        
        # تعديل نسبة النجاح حسب الأداء التاريخي
        success_rate = (success_rate * 0.7) + (performance['accuracy'] * 0.3)
        success_rate = min(0.92, max(0.55, success_rate))
        
        # تسجيل الإشارة
        if signal != "NEUTRAL" and abs_score >= 2:
            log_signal(symbol, signal, score, current_price)
        
        entry = current_price
        stop_loss = round(current_price - (atr * 1.2), 6) if signal == "BUY" else round(current_price + (atr * 1.2), 6)
        tp1 = round(current_price + (atr * 1.5), 6) if signal == "BUY" else round(current_price - (atr * 1.5), 6)
        tp2 = round(current_price + (atr * 2.5), 6) if signal == "BUY" else round(current_price - (atr * 2.5), 6)
        tp3 = round(current_price + (atr * 4), 6) if signal == "BUY" else round(current_price - (atr * 4), 6)
        
        return {
            'signal': signal,
            'strength': strength,
            'success_rate': success_rate,
            'score': score,
            'price': current_price,
            'rsi': rsi,
            'macd': macd,
            'stoch': stoch,
            'volume_ratio': volume_ratio,
            'change_24h': change_24h,
            'reasons': reasons[:5],
            'entry': entry,
            'stop_loss': stop_loss,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3
        }
        
    except Exception as e:
        print(f"خطأ في {symbol}: {e}")
        return None

def get_cached_analysis(symbol):
    now = time.time()
    if symbol in cache and (now - cache[symbol]['time']) < CACHE_DURATION:
        return cache[symbol]['data']
    
    analysis = get_precise_analysis(symbol)
    if analysis:
        cache[symbol] = {'data': analysis, 'time': now}
    return analysis

def get_top_opportunities():
    buy_list = []
    sell_list = []
    
    print(f"⚡ جاري التحليل...")
    start_time = time.time()
    
    for coin in MAIN_COINS:
        analysis = get_cached_analysis(coin)
        if analysis and analysis['signal'] != 'NEUTRAL':
            item = {
                'symbol': coin,
                'signal': analysis['signal'],
                'strength': analysis['strength'],
                'success_rate': analysis['success_rate'],
                'score': analysis['score'],
                'price': analysis['price'],
                'rsi': analysis['rsi'],
                'change_24h': analysis['change_24h']
            }
            
            if analysis['signal'] == 'BUY':
                buy_list.append(item)
            else:
                sell_list.append(item)
        
        time.sleep(0.05)
    
    buy_list.sort(key=lambda x: x['success_rate'], reverse=True)
    sell_list.sort(key=lambda x: x['success_rate'], reverse=True)
    
    elapsed = time.time() - start_time
    print(f"✅ اكتمل في {elapsed:.1f} ثانية | شراء: {len(buy_list)} | بيع: {len(sell_list)}")
    
    return buy_list[:10], sell_list[:10]

def format_signal(analysis, symbol):
    if analysis['signal'] == 'BUY':
        arrow = "🟢"
        direction = "شراء"
    else:
        arrow = "🔴"
        direction = "بيع"
    
    if "قوية جداً" in analysis['strength']:
        power_icon = "🔥"
    elif "قوية" in analysis['strength']:
        power_icon = "✅"
    else:
        power_icon = "📊"
    
    msg = f"""
╔══════════════════════════════════════╗
║     🎯 *التحليل الدقيق* 🤖
║     {arrow} {symbol} - {direction} {arrow}
╚══════════════════════════════════════╝

{power_icon} *القوة:* {analysis['strength']}
📊 *النقاط:* `{analysis['score']:+d}`
🎯 *النجاح المتوقع:* `{analysis['success_rate']:.0%}`

💰 *السعر:* `${analysis['price']:.6f}`
📈 *التغير 24س:* `{analysis['change_24h']:+.2f}%`

📊 *المؤشرات:*
• RSI: `{analysis['rsi']:.1f}`
• MACD: `{analysis['macd']:.6f}`
• حجم التداول: `{analysis['volume_ratio']:.1f}x`

📝 *التحليل:*
"""
    for r in analysis['reasons'][:4]:
        msg += f"  • {r}\n"

    msg += f"""
📐 *نقاط الدخول والخروج:*
• 🚪 *الدخول:* `${analysis['entry']:.6f}`
• 🛑 *وقف:* `${analysis['stop_loss']:.6f}`
• 🎯 *هدف1:* `${analysis['tp1']:.6f}`
• 🎯 *هدف2:* `${analysis['tp2']:.6f}`
• 🎯 *هدف3:* `${analysis['tp3']:.6f}`

⚠️ للإشارة فقط
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
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
    return markup

# ========== أوامر التليجرام ==========
@bot.message_handler(commands=['start'])
def start(message):
    msg = f"""
🎯 *البوت المتعلم* 🤖

📊 /daily - أفضل الفرص
🔍 /coin BTC - تحليل عملة
📈 /stats - إحصائيات التعلم

✅ يحلل {len(MAIN_COINS)} عملة
✅ نسبة النجاح: {performance['accuracy']:.1%}
"""
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['daily'])
def daily(message):
    status = bot.reply_to(message, "🎯 جاري التحليل...")
    
    def analyze():
        buy, sell = get_top_opportunities()
        bot_data[message.chat.id] = {'buy': buy, 'sell': sell}
        
        if buy or sell:
            markup = create_main_menu(buy, sell)
            try:
                bot.edit_message_text(f"🎯 *النتائج*\n🟢 شراء: {len(buy)} | 🔴 بيع: {len(sell)}\n📊 نسبة النجاح: {performance['accuracy']:.1%}\n\n👇 اضغط للتفاصيل:", 
                                      message.chat.id, status.message_id, 
                                      reply_markup=markup, parse_mode='Markdown')
            except:
                pass
        else:
            try:
                bot.edit_message_text("⚠️ لا توجد إشارات حالياً", message.chat.id, status.message_id)
            except:
                pass
    
    threading.Thread(target=analyze, daemon=True).start()

@bot.message_handler(commands=['stats'])
def stats(message):
    evaluated = [s for s in signals_log if s['evaluated']]
    correct = sum(1 for s in evaluated if s['success'])
    pending = len([s for s in signals_log if not s['evaluated']])
    
    msg = f"""
📊 *إحصائيات التعلم*

🎯 نسبة النجاح: `{performance['accuracy']:.1%}`
📈 الإشارات المقيمة: `{len(evaluated)}`
✅ الناجحة: `{correct}`
❌ الفاشلة: `{len(evaluated) - correct}`
⏳ قيد التقييم: `{pending}`

📊 عدد العملات: `{len(MAIN_COINS)}`
"""
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = call.data
    chat_id = call.message.chat.id
    
    if chat_id not in bot_data:
        return
    
    if data == "back_main":
        buy = bot_data[chat_id].get('buy', [])
        sell = bot_data[chat_id].get('sell', [])
        markup = create_main_menu(buy, sell)
        try:
            bot.edit_message_text(f"🎯 *النتائج*\n🟢 شراء: {len(buy)} | 🔴 بيع: {len(sell)}", 
                                  chat_id, call.message.message_id, 
                                  reply_markup=markup, parse_mode='Markdown')
        except:
            pass
    
    elif data.startswith('buy_'):
        idx = int(data.split('_')[1])
        if idx < len(bot_data[chat_id].get('buy', [])):
            opp = bot_data[chat_id]['buy'][idx]
            analysis = get_cached_analysis(opp['symbol'])
            if analysis:
                msg = format_signal(analysis, opp['symbol'])
                markup = create_back_button()
                try:
                    bot.edit_message_text(msg, chat_id, call.message.message_id, 
                                          reply_markup=markup, parse_mode='Markdown')
                except:
                    pass
    
    elif data.startswith('sell_'):
        idx = int(data.split('_')[1])
        if idx < len(bot_data[chat_id].get('sell', [])):
            opp = bot_data[chat_id]['sell'][idx]
            analysis = get_cached_analysis(opp['symbol'])
            if analysis:
                msg = format_signal(analysis, opp['symbol'])
                markup = create_back_button()
                try:
                    bot.edit_message_text(msg, chat_id, call.message.message_id, 
                                          reply_markup=markup, parse_mode='Markdown')
                except:
                    pass

@bot.message_handler(commands=['coin'])
def coin(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "مثال: /coin BTC")
            return
        
        symbol = parts[1].upper()
        status_msg = bot.reply_to(message, f"🎯 تحليل {symbol}...")
        
        analysis = get_precise_analysis(symbol)
        
        if analysis:
            msg = format_signal(analysis, symbol)
            bot.edit_message_text(msg, message.chat.id, status_msg.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(f"❌ لا يمكن تحليل {symbol}", message.chat.id, status_msg.message_id)
            
    except Exception as e:
        bot.reply_to(message, f"خطأ: {e}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        text = message.text.strip().upper()
        if len(text) >= 2 and len(text) <= 6 and text.isalpha():
            if text in MAIN_COINS:
                status_msg = bot.reply_to(message, f"🎯 تحليل {text}...")
                analysis = get_precise_analysis(text)
                if analysis:
                    arrow = "🟢" if analysis['signal'] == 'BUY' else "🔴"
                    dir_ar = "شراء" if analysis['signal'] == 'BUY' else "بيع"
                    msg = f"""
🎯 *{text}* {arrow}
💰 السعر: `${analysis['price']:.4f}`
⚡ {dir_ar} | نجاح: {analysis['success_rate']:.0%}
📊 RSI: {analysis['rsi']:.1f}
"""
                    bot.edit_message_text(msg, message.chat.id, status_msg.message_id, parse_mode='Markdown')
    except:
        pass

# ========== خادم Flask الصحي (لـ Render) - التصحيح النهائي ==========
# إنشاء تطبيق Flask منفصل
health_app = Flask(__name__)

@health_app.route('/')
@health_app.route('/health')
def health_check():
    return "Bot is alive!", 200

def run_health_server():
    # استخدام المنفذ الذي يوفره Render أو 10000 كقيمة افتراضية
    port = int(os.environ.get('PORT', 10000))
    print(f"✅ Starting health server on port {port}")
    health_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# تشغيل الخادم الصحي في خلفية
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()
print("✅ Health check server started")

# ========== التشغيل الرئيسي ==========
print("=" * 60)
print(f"🎯 البوت المتعلم يعمل!")
print(f"📊 تم تحميل {len(MAIN_COINS)} عملة")
print(f"📈 نسبة النجاح الحالية: {performance['accuracy']:.1%}")
print("=" * 60)

# تشغيل البوت
bot.infinity_polling()