import os
import requests
from dotenv import load_dotenv

# Tải cấu hình từ .env
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def send_telegram_alert(message: str) -> bool:
    """
    Gửi tin nhắn văn bản HTML tới Telegram qua Bot API.
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

def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    """
    Gửi ảnh biểu đồ kỹ thuật kèm chú thích HTML tới Telegram.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID trong .env")
        return False

    if not photo_path or not os.path.exists(photo_path):
        print(f"[-] Không tìm thấy file ảnh: {photo_path}")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }

    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            resp = requests.post(url, data=data, files=files, timeout=15)
        if resp.status_code == 200:
            print(f"[✓] Đã gửi ảnh chart {os.path.basename(photo_path)} tới Telegram thành công!")
            return True
        else:
            print(f"[-] Gửi ảnh Telegram thất bại: {resp.text}")
            return False
    except Exception as e:
        print(f"[-] Lỗi kết nối Telegram khi gửi ảnh: {e}")
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
        msg += f"• Giá vào: <b>{s['price']:.2f}</b>\n"
        msg += f"• %B: <code>{s['pct_b']:.2f}</code> | BB Width: <code>{s['bandwidth']:.3f}</code>\n"
        msg += f"• Khối lượng nảy: <code>{s['vol_ratio']:.1f}x MA20</code>\n"
        msg += f"• Mục tiêu Chốt lời (+{s['tp_pct']*100:.1f}%): <b>{s['target_tp']:.2f}</b> (Chốt 50%)\n"
        msg += f"• Ngưỡng Dừng lỗ (-{s['sl_pct']*100:.1f}%): <b>{s['target_sl']:.2f}</b>\n"
        msg += f"• Thời gian nắm giữ tối đa: <b>{s['max_hold_days']} phiên (T+)</b>\n\n"

    msg += "⚠️ <i>Khuyến nghị: Quản trị vốn tối đa 20-25% NAV/mã. Chốt lời 50% tại dải trên, 50% còn lại gồng lãi theo EMA9.</i>"
    return msg

if __name__ == "__main__":
    print("Notifier module with photo support ready.")
