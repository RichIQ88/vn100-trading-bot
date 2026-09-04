import os
import sys
import time
import glob
import requests
import pandas as pd

# Thêm đường dẫn src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from notifier import get_telegram_credentials, send_telegram_alert, send_telegram_photo
from indicators import compute_indicators, add_relative_strength
from strategy import generate_signals
from chart_generator import generate_signal_chart
from market_regime import get_market_regime
from position_tracker import load_positions, calculate_position_size
from sector_data import get_sector, get_sector_breakdown

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def get_updates(token: str, offset: int = None, timeout: int = 15):
    """Lấy danh sách tin nhắn mới nhất từ Telegram Bot API qua long-polling"""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": timeout}
    if offset:
        params["offset"] = offset
    try:
        resp = requests.get(url, params=params, timeout=timeout + 5)
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception as e:
        print(f"[-] Lỗi polling Telegram: {e}")
    return []

def handle_command(text: str, chat_id: str) -> bool:
    """Xử lý lệnh từ người dùng và phản hồi tự động"""
    cmd = text.strip()
    parts = cmd.split()
    first = parts[0].upper() if parts else ""

    # 1. Hướng dẫn sử dụng (/start, /help)
    if first in ["/START", "/HELP"]:
        msg = (
            "👋 <b>CHÀO MỪNG BẠN ĐẾN VỚI VN100 QUANT TRADING ASSISTANT!</b>\n\n"
            "Hệ thống định lượng T+ hỗ trợ bạn tra cứu thị trường 24/7:\n\n"
            "🔹 <code>/scan</code>: Quét toàn bộ rổ VN100 tìm tín hiệu mua đạt chuẩn ngay lập tức.\n"
            "🔹 <code>/chart FPT</code> (hoặc chỉ cần gõ <code>FPT</code>, <code>SSI</code>, <code>HPG</code>): Nhận biểu đồ kỹ thuật và các ngưỡng TP/SL tức thì.\n"
            "🔹 <code>/pos</code> hoặc <code>/portfolio</code>: Xem danh mục các mã đang nắm giữ và phân bổ ngành.\n"
            "🔹 <code>/market</code>: Báo cáo xu hướng thị trường VN-Index và mức độ rủi ro hôm nay.\n"
            "🔹 <code>/calc 500 FPT</code>: Tính khối lượng mua an toàn cho FPT với NAV 500 triệu (rủi ro 2% NAV).\n\n"
            "<i>💡 Bạn có thể gõ trực tiếp mã cổ phiếu bất kỳ để xem biểu đồ!</i>"
        )
        send_telegram_alert(msg)
        return True

    # 2. Báo cáo trạng thái thị trường (/market)
    elif first == "/MARKET":
        regime = get_market_regime(update=False)
        msg = (
            f"🏛️ <b>BÁO CÁO TRẠNG THÁI THỊ TRƯỜNG VN-INDEX</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Trạng thái: {regime['color']} <b>{regime['label']}</b>\n"
            f"• Điểm số hiện tại: <b>{regime['close']:.2f} điểm</b>\n"
            f"• Đường SMA20: <code>{regime['sma20']:.2f}</code> | SMA50: <code>{regime['sma50']:.2f}</code>\n"
            f"• Độ biến động (ATR 14): <code>{regime['atr']:.2f} điểm</code>\n\n"
            f"💡 <b>Khuyến nghị hành động:</b>\n"
            f"{regime['action']}"
        )
        send_telegram_alert(msg)
        return True

    # 3. Quét tín hiệu toàn thị trường (/scan)
    elif first == "/SCAN":
        send_telegram_alert("🔍 <b>Đang quét toàn bộ 56+ mã VN100 theo tiêu chí Alpha Leader...</b> Vui lòng chờ 3-5 giây.")
        files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
        files = [f for f in files if "optimization" not in f and "VNINDEX" not in f]
        found = []
        for f in sorted(files):
            sym = os.path.basename(f).replace(".csv", "")
            try:
                df = pd.read_csv(f)
                if len(df) < 50: continue
                df['time'] = pd.to_datetime(df['time'])
                df = compute_indicators(df)
                df = add_relative_strength(df)
                df = generate_signals(df, mode="high_winrate")
                tail = df.tail(3)
                for idx, row in tail.iterrows():
                    if row['signal'] == 1:
                        p = float(row['close'])
                        atr_v = float(row.get('atr', p * 0.025))
                        tp_p = round(p + 2.5 * atr_v, 2)
                        sl_p = round(max(p - 1.5 * atr_v, p * 0.945), 2)
                        rs_v = float(row.get('rs_score', 100.0))
                        cmf_v = float(row.get('cmf', 0.0))
                        sec = get_sector(sym)
                        found.append({
                            'symbol': sym,
                            'sector': sec,
                            'date': row['time'].strftime("%d/%m"),
                            'price': p,
                            'tp': tp_p,
                            'sl': sl_p,
                            'rs': rs_v,
                            'cmf': cmf_v,
                            'setup': row['setup_name']
                        })
            except Exception:
                continue

        if not found:
            send_telegram_alert("🔔 <b>[VN100 SCAN]</b> Không có mã nào đạt đủ 5 tiêu chí nảy chuẩn trong các phiên gần nhất. Hệ thống khuyến nghị tiếp tục kiên nhẫn quan sát.")
        else:
            # Sắp xếp theo RS Leader cao nhất
            found = sorted(found, key=lambda x: x['rs'], reverse=True)
            msg = f"🔔 <b>[VN100 SCANNER] TÌM THẤY {len(found)} CƠ HỘI MUA TIỀM NĂNG:</b>\n\n"
            for i, s in enumerate(found[:5], 1):
                star = "⭐" if s['rs'] >= 102 else "🔹"
                msg += f"{star} <b>{i}. {s['symbol']}</b> ({s['sector']}) - {s['date']}\n"
                msg += f"   • Giá vào: <b>{s['price']:.2f}</b>\n"
                msg += f"   • TP (ATR): <b>{s['tp']:.2f}</b> | SL (ATR): <b>{s['sl']:.2f}</b>\n"
                msg += f"   • RS Leader: <code>{s['rs']:.1f}</code> | CMF Dòng tiền: <code>{s['cmf']:+.2f}</code>\n"
                msg += f"   • Setup: <code>{s['setup']}</code>\n\n"
            msg += "<i>Gõ tên mã (ví dụ: FPT) để xem biểu đồ phân tích chi tiết!</i>"
            send_telegram_alert(msg)
        return True

    # 4. Xem danh mục vị thế mở (/pos, /portfolio)
    elif first in ["/POS", "/PORTFOLIO"]:
        positions = load_positions()
        open_pos = [p for p in positions if p.get('status') == 'OPEN']
        if not open_pos:
            send_telegram_alert("💼 <b>DANH MỤC HIỆN TẠI:</b> Chưa có vị thế nào đang mở. Gõ <code>/scan</code> để tìm cơ hội mới.")
            return True

        breakdown = get_sector_breakdown(positions)
        msg = f"💼 <b>DANH MỤC VỊ THẾ ĐANG THEO DÕI ({len(open_pos)} MÃ):</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        for p in open_pos:
            sym = p['symbol']
            sec = p.get('sector', get_sector(sym))
            tp_hit = " (Đã chốt 50%)" if p.get('tp1_hit') else ""
            msg += f"• <b>{sym}</b> ({sec}){tp_hit}\n"
            msg += f"  - Ngày mua: {p['entry_date']} | Giá vốn: <b>{p['entry_price']:.2f}</b>\n"
            msg += f"  - Mục tiêu TP: <code>{p['tp_target']:.2f}</code> | Dừng lỗ SL: <code>{p['sl_target']:.2f}</code>\n"
        
        msg += "\n📊 <b>Cơ cấu theo ngành:</b>\n"
        for sec, cnt in breakdown.items():
            msg += f"• {sec}: {cnt} mã\n"
        send_telegram_alert(msg)
        return True

    # 5. Máy tính quản trị vốn (/calc <NAV> <SYMBOL>)
    elif first in ["/CALC", "/RISK"]:
        if len(parts) < 3:
            send_telegram_alert("⚠️ <b>Cú pháp:</b> <code>/calc &lt;NAV_Triệu&gt; &lt;Mã_CP&gt;</code>\nVí dụ: <code>/calc 500 FPT</code> (NAV 500 triệu, mã FPT)")
            return True
        try:
            nav_mil = float(parts[1])
            sym = parts[2].upper().strip()
            nav_vnd = nav_mil * 1_000_000.0

            csv_path = os.path.join(DATA_DIR, f"{sym}.csv")
            if not os.path.exists(csv_path):
                send_telegram_alert(f"[-] Không tìm thấy dữ liệu mã {sym} trong rổ VN100.")
                return True

            df = pd.read_csv(csv_path)
            last_p = float(df['close'].iloc[-1])
            sl_p = round(last_p * 0.955, 2)

            res = calculate_position_size(nav_vnd, last_p, sl_p, risk_pct=0.02)
            msg = (
                f"💰 <b>KẾ HOẠCH PHÂN BỔ VỐN CHO {sym}:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• Tổng NAV: <b>{nav_mil:,.0f} triệu VNĐ</b>\n"
                f"• Giá thị trường ước tính: <b>{last_p:.2f}</b> (SL: {sl_p:.2f})\n"
                f"• Mức chịu rủi ro (2% NAV): <b>{nav_vnd * 0.02:,.0f} VNĐ</b>\n"
                f"• Khối lượng nên mua: <b>{res['shares']:,} cổ phiếu</b> (lô chuẩn)\n"
                f"• Tổng giá trị giải ngân: <b>{res['capital_vnd']:,.0f} VNĐ</b> ({res['capital_pct']}% NAV)\n"
                f"• Số tiền tối đa bị lỗ nếu chạm SL: <b>{res['max_loss_vnd']:,.0f} VNĐ</b> ({res['max_loss_pct']}% NAV)\n\n"
                f"✅ <i>Tuân thủ nghiêm ngặt quản trị vốn giúp bạn trụ vững trên thị trường!</i>"
            )
            send_telegram_alert(msg)
            return True
        except Exception as e:
            send_telegram_alert(f"[-] Lỗi tính toán: {e}")
            return True

    # 6. Tra cứu biểu đồ kỹ thuật (/chart SYMBOL hoặc chỉ gõ SYMBOL)
    ticker = parts[1].upper() if first == "/CHART" and len(parts) > 1 else (first.replace("/", "") if len(first) in [3, 4] else "")
    if ticker:
        csv_path = os.path.join(DATA_DIR, f"{ticker}.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                df['time'] = pd.to_datetime(df['time'])
                df = compute_indicators(df)
                df = add_relative_strength(df)
                last_row = df.iloc[-1]
                last_p = float(last_row['close'])
                atr_v = float(last_row.get('atr', last_p * 0.025))
                tp_est = round(last_p + 2.5 * atr_v, 2)
                sl_est = round(max(last_p - 1.5 * atr_v, last_p * 0.945), 2)
                rs_v = float(last_row.get('rs_score', 100.0))
                cmf_v = float(last_row.get('cmf', 0.0))

                chart_file = generate_signal_chart(df, ticker, tp_target=tp_est, sl_target=sl_est, lookback=60)
                if chart_file and os.path.exists(chart_file):
                    caption = (
                        f"📈 <b>BIỂU ĐỒ KỸ THUẬT: {ticker} ({get_sector(ticker)})</b>\n"
                        f"• Giá đóng cửa: <b>{last_p:.2f}</b>\n"
                        f"• Mục tiêu Chốt lời (2.5x ATR): <b>{tp_est:.2f}</b> (+{(tp_est/last_p - 1)*100:.1f}%)\n"
                        f"• Ngưỡng Cắt lỗ (1.5x ATR): <b>{sl_est:.2f}</b> ({(sl_est/last_p - 1)*100:.1f}%)\n"
                        f"• RS vs VN-Index: <code>{rs_v:.1f}</code> | CMF Dòng tiền: <code>{cmf_v:+.2f}</code>"
                    )
                    send_telegram_photo(chart_file, caption=caption)
                    return True
            except Exception as e:
                print(f"[-] Lỗi vẽ chart: {e}")

    return False

def run_bot_listener():
    """Chạy vòng lặp lắng nghe tin nhắn từ Telegram"""
    token, target_chat_id = get_telegram_credentials()
    if not token:
        print("[!] Chưa có cấu hình TELEGRAM_BOT_TOKEN.")
        return

    print("🤖 [TELEGRAM BOT INTERACTIVE] Đang kích hoạt trợ lý 2 chiều...")
    print(f"Bot Token: {token[:6]}... | Target Chat ID: {target_chat_id}")
    
    last_offset = None
    while True:
        try:
            updates = get_updates(token, offset=last_offset, timeout=10)
            for upd in updates:
                last_offset = upd["update_id"] + 1
                msg_obj = upd.get("message", {})
                chat = msg_obj.get("chat", {})
                c_id = str(chat.get("id", ""))
                text = msg_obj.get("text", "").strip()

                if not text:
                    continue

                # Kiểm tra bảo mật: Chỉ phản hồi đúng chat_id của chủ sở hữu
                if target_chat_id and c_id != target_chat_id:
                    print(f"[!] Bỏ qua tin nhắn từ người lạ (Chat ID: {c_id})")
                    continue

                print(f"[>] Nhận lệnh từ người dùng: '{text}'")
                handle_command(text, c_id)

            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[!] Dừng listener bot.")
            break
        except Exception as e:
            print(f"[-] Lỗi trong listener: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_bot_listener()
