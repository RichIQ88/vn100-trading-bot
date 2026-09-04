import os
import requests
from dotenv import load_dotenv

# Tải cấu hình từ .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def send_telegram_alert(message: str) -> bool:
    """
    Gửi tin nhắn thông báo tín hiệu tới Telegram qua Bot API.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("[✓] Đã gửi thông báo Telegram thành công!")
            return True
        else:
            print(f"[-] Gửi Telegram thất bại: {resp.text}")
            return False
    except Exception as e:
        print(f"[-] Lỗi kết nối Telegram: {e}")
        return False

def format_signal_message(signals_list: list) -> str:
    """
    Định dạng danh sách tín hiệu mua thành văn bản HTML đẹp cho Telegram
    """
    if not signals_list:
        return "<b>[VN100 BOT]</b> Không có tín hiệu mua mới trong phiên hôm nay."

    msg = f"🔔 <b>[VN100 SCANNER] PHÁT HIỆN TÍN HIỆU MUA ({len(signals_list)} MÃ)</b>\n"
    msg += f"<i>Khung: Daily | Chiến lược: Bollinger Bands + Volume + MA Trend</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, s in enumerate(signals_list, 1):
        msg += f"<b>{i}. Mã: {s['symbol']}</b> (Setup: <code>{s['setup']}</code>)\n"
        msg += f"• Giá hiện tại: <b>{s['price']:.2f}</b>\n"
        msg += f"• %B: <code>{s['pct_b']:.2f}</code> | BB Width: <code>{s['bandwidth']:.3f}</code>\n"
        msg += f"• Vol/MA20: <code>{s['vol_ratio']:.1f}x</code>\n"
        msg += f"• Điểm chốt lời dự kiến (+{s['tp_pct']*100:.1f}%): <b>{s['target_tp']:.2f}</b>\n"
        msg += f"• Điểm cắt lỗ đề xuất (-{s['sl_pct']*100:.1f}%): <b>{s['target_sl']:.2f}</b>\n"
        msg += f"• Thời gian nắm giữ tối đa: <b>{s['max_hold_days']} phiên (T+)</b>\n\n"

    msg += "⚠️ <i>Khuyến nghị: Luôn quản trị rủi ro và tuân thủ kỷ luật dừng lỗ.</i>"
    return msg

if __name__ == "__main__":
    test_signals = [{
        'symbol': 'FPT',
        'setup': 'Trend Pullback',
        'price': 135.5,
        'pct_b': 0.52,
        'bandwidth': 0.085,
        'vol_ratio': 1.6,
        'tp_pct': 0.07,
        'target_tp': 144.98,
        'sl_pct': 0.04,
        'target_sl': 130.08,
        'max_hold_days': 10
    }]
    print(format_signal_message(test_signals))
