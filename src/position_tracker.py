import os
import json
import pandas as pd
from datetime import datetime
from notifier import send_telegram_alert

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
POSITIONS_FILE = os.path.join(DATA_DIR, "active_positions.json")

def load_positions():
    """Đọc danh sách các vị thế từ file JSON"""
    if not os.path.exists(POSITIONS_FILE):
        return []
    try:
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_positions(positions):
    """Lưu danh sách vị thế vào file JSON"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)

def add_new_position(symbol, entry_date, entry_price, tp_target, sl_target, setup_name, max_hold=8):
    """Thêm một khuyến nghị mua mới vào danh sách theo dõi vị thế"""
    positions = load_positions()
    
    # Kiểm tra xem mã này đã có vị thế OPEN chưa
    for p in positions:
        if p['symbol'] == symbol and p['status'] == 'OPEN':
            return False # Đã có vị thế đang mở

    new_pos = {
        'symbol': symbol,
        'entry_date': entry_date,
        'entry_price': round(float(entry_price), 2),
        'tp_target': round(float(tp_target), 2),
        'sl_target': round(float(sl_target), 2),
        'setup_name': setup_name,
        'max_hold': max_hold,
        'status': 'OPEN',
        'tp1_hit': False,
        'history': []
    }
    positions.append(new_pos)
    save_positions(positions)
    print(f"[✓] Đã thêm vị thế mới theo dõi: {symbol} tại giá {entry_price:.2f}")
    return True

def update_and_alert_positions(latest_quotes):
    """
    Quét kiểm tra toàn bộ các vị thế đang mở (OPEN):
    - Chốt lời từng phần 50% khi chạm TP1
    - Cắt lỗ bảo toàn vốn khi chạm SL
    - Thoát lệnh khi hết hạn nắm giữ T+8
    """
    positions = load_positions()
    if not positions:
        return

    today = datetime.now()
    changed = False

    for p in positions:
        if p['status'] != 'OPEN':
            continue

        sym = p['symbol']
        if sym not in latest_quotes:
            continue

        quote = latest_quotes[sym]
        curr_price = float(quote.get('close', quote.get('price', 0)))
        if curr_price <= 0:
            continue

        entry_date = datetime.strptime(p['entry_date'], "%Y-%m-%d")
        days_held = (today - entry_date).days # Ngày lịch hoặc số phiên

        entry_price = p['entry_price']
        tp_target = p['tp_target']
        sl_target = p['sl_target']
        pnl_pct = ((curr_price - entry_price) / entry_price) * 100

        # 1. KỊCH BẢN CHỐT LỜI (TAKE PROFIT)
        if curr_price >= tp_target:
            if not p.get('tp1_hit', False):
                # Chốt lời 50% đợt 1 và nâng Stop Loss lên giá vốn (Breakeven)
                p['tp1_hit'] = True
                p['sl_target'] = entry_price # Dời dừng lỗ lên giá vốn
                p['history'].append({'date': today.strftime("%Y-%m-%d"), 'action': 'TP1_50%', 'price': curr_price})
                changed = True

                msg = f"🟢 <b>[CẢNH BÁO CHỐT LỜI ĐỢT 1 - TP1] MÃ {sym}</b>\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"• Giá hiện tại: <b>{curr_price:.2f}</b> (Mục tiêu: {tp_target:.2f})\n"
                msg += f"• Lợi nhuận tạm tính: <b>+{pnl_pct:.2f}%</b> (Vào: {entry_price:.2f} ngày {p['entry_date']})\n"
                msg += f"• 🎯 <b>KHUYẾN NGHỊ:</b>\n"
                msg += f"  1. <b>Chốt lời trước 50% khối lượng</b> để bỏ tiền vào túi!\n"
                msg += f"  2. <b>Nâng Stop Loss 50% còn lại lên giá vốn ({entry_price:.2f})</b> để rủi ro = 0.\n"
                msg += f"  3. Tiếp tục gồng lãi bám theo đường EMA9 để đón siêu sóng!\n"
                send_telegram_alert(msg)
            elif pnl_pct >= 10.0 or curr_price >= tp_target * 1.05:
                # Chốt nốt 50% còn lại khi đạt trên +10%
                p['status'] = 'CLOSED_TP'
                p['exit_date'] = today.strftime("%Y-%m-%d")
                p['exit_price'] = curr_price
                p['final_pnl_pct'] = pnl_pct - 0.4
                changed = True

                msg = f"🎉 <b>[TẤT TOÁN VỊ THẾ TOÀN BỘ] MÃ {sym}</b>\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"• Đã chốt toàn bộ vị thế tại giá <b>{curr_price:.2f}</b>\n"
                msg += f"• Tổng lợi nhuận ròng: <b>+{pnl_pct:.2f}%</b>\n"
                msg += f"• Chúc mừng quý khách hàng đã có thương vụ đầu tư xuất sắc!\n"
                send_telegram_alert(msg)

        # 2. KỊCH BẢN CẮT LỖ (STOP LOSS)
        elif curr_price <= sl_target:
            p['status'] = 'CLOSED_SL'
            p['exit_date'] = today.strftime("%Y-%m-%d")
            p['exit_price'] = curr_price
            p['final_pnl_pct'] = pnl_pct - 0.4
            changed = True

            sl_type = "BẢO TOÀN LÃI (HÒA VỐN)" if p.get('tp1_hit', False) else "DỪNG LỖ KỶ LUẬT"
            msg = f"🔴 <b>[CẢNH BÁO {sl_type}] MÃ {sym}</b>\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"• Giá hiện tại: <b>{curr_price:.2f}</b> đã chạm ngưỡng dừng lỗ {sl_target:.2f}\n"
            msg += f"• Lợi nhuận/Thua lỗ: <b>{pnl_pct:+.2f}%</b> (Vào giá {entry_price:.2f})\n"
            msg += f"• ⚠️ <b>KHUYẾN NGHỊ:</b> Bán dứt khoát để bảo toàn vốn và quản trị rủi ro kỷ luật!\n"
            send_telegram_alert(msg)

        # 3. KỊCH BẢN HẾT HẠN T+8 (TIME EXIT)
        elif days_held >= p['max_hold']:
            p['status'] = 'CLOSED_TIME'
            p['exit_date'] = today.strftime("%Y-%m-%d")
            p['exit_price'] = curr_price
            p['final_pnl_pct'] = pnl_pct - 0.4
            changed = True

            msg = f"🟡 <b>[CẢNH BÁO HẾT HẠN NẮM GIỮ T+] MÃ {sym}</b>\n"
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"• Mã {sym} đã nắm giữ đủ {days_held} phiên (Giá hiện tại: <b>{curr_price:.2f}</b> | PnL: <b>{pnl_pct:+.2f}%</b>)\n"
            msg += f"• 💡 <b>KHUYẾN NGHỊ:</b> Đóng vị thế theo thời gian để giải phóng nguồn vốn cho cơ hội mới.\n"
            send_telegram_alert(msg)

    if changed:
        save_positions(positions)

if __name__ == "__main__":
    # Test tracking
    add_new_position("MSB", "2026-08-13", 13.46, 14.27, 12.92, "High-Winrate Trend Pullback")
    print("Active positions count:", len(load_positions()))
