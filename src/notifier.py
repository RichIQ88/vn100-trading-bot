import os
import requests
from dotenv import load_dotenv

# Tải cấu hình từ .env
load_dotenv()

def get_credential(key: str, default: str = "") -> str:
    """Lấy cấu hình từ biến môi trường hoặc Streamlit Secrets (nếu chạy trên Streamlit Cloud)"""
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            val = str(st.secrets[key]).strip()
            if val:
                return val
    except Exception:
        pass
    return default

def get_telegram_credentials():
    token = get_credential("TELEGRAM_BOT_TOKEN")
    chat_id = get_credential("TELEGRAM_CHAT_ID")
    return token, chat_id

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def send_telegram_alert_with_status(message: str) -> tuple[bool, str]:
    """
    Gửi tin nhắn Telegram và trả về bộ (thành_công: bool, thông_báo_chi_tiết: str)
    giúp người dùng và Dashboard biết chính xác nguyên nhân nếu thất bại.
    """
    token, chat_id = get_telegram_credentials()
    if not token or not chat_id:
        err = (
            "Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.\n"
            "• Nếu đang chạy trên Streamlit Cloud: Vào App Settings > Secrets và thêm TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID.\n"
            "• Nếu chạy Local: Tạo file .env và điền 2 thông số này."
        )
        print(f"[!] {err}")
        return False, err

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("[✓] Đã gửi thông báo Telegram thành công!")
            return True, "Gửi tin nhắn Telegram thành công!"
        elif resp.status_code == 403:
            err = (
                "Lỗi Telegram 403 (Forbidden): Bot không được phép gửi tin nhắn trước cho bạn!\n"
                "👉 Cách khắc phục: Mở ứng dụng Telegram, tìm tên Bot của bạn và bấm START (hoặc gửi 1 tin nhắn bất kỳ cho Bot) rồi thử lại."
            )
            print(f"[-] {err}\nChi tiết: {resp.text}")
            return False, err
        elif resp.status_code == 400:
            err = f"Lỗi Telegram 400 (Bad Request): Chat ID không hợp lệ hoặc định dạng tin nhắn sai. Chi tiết: {resp.text}"
            print(f"[-] {err}")
            return False, err
        elif resp.status_code == 401:
            err = "Lỗi Telegram 401 (Unauthorized): TELEGRAM_BOT_TOKEN không chính xác. Hãy kiểm tra lại token từ @BotFather."
            print(f"[-] {err}")
            return False, err
        else:
            err = f"Lỗi Telegram HTTP {resp.status_code}: {resp.text}"
            print(f"[-] {err}")
            return False, err
    except Exception as e:
        err = f"Lỗi kết nối mạng tới máy chủ Telegram: {e}"
        print(f"[-] {err}")
        return False, err

def send_telegram_alert(message: str) -> bool:
    """
    Gửi tin nhắn văn bản HTML tới Telegram qua Bot API (Trả về bool để tương thích ngược).
    """
    success, _ = send_telegram_alert_with_status(message)
    return success

def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    """
    Gửi ảnh biểu đồ kỹ thuật kèm chú thích HTML tới Telegram.
    """
    token, chat_id = get_telegram_credentials()
    if not token or not chat_id:
        print("[!] Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID")
        return False

    if not photo_path or not os.path.exists(photo_path):
        print(f"[-] Không tìm thấy file ảnh: {photo_path}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {
        "chat_id": chat_id,
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
    msg += f"<i>Khung: Daily | Chiến lược: Bollinger Bands + Volume + RS Leader</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, s in enumerate(signals_list, 1):
        sec = s.get('sector', '')
        sec_str = f" ({sec})" if sec else ""
        rs_str = f" | RS: <code>{s['rs_score']}</code>" if 'rs_score' in s else ""
        cmf_str = f" | CMF: <code>{s['cmf']:+.2f}</code>" if 'cmf' in s else ""
        
        msg += f"<b>{i}. Mã: {s['symbol']}</b>{sec_str} (Setup: <code>{s['setup']}</code>)\n"
        msg += f"• Giá vào: <b>{s['price']:.2f}</b>\n"
        msg += f"• %B: <code>{s['pct_b']:.2f}</code> | Khối lượng: <code>{s['vol_ratio']:.1f}x MA20</code>{rs_str}{cmf_str}\n"
        msg += f"• Mục tiêu Chốt lời (TP): <b>{s['target_tp']:.2f}</b> (+{s['tp_pct']*100:.1f}%) [Chốt 50%]\n"
        msg += f"• Ngưỡng Cắt lỗ (SL): <b>{s['target_sl']:.2f}</b> (-{s['sl_pct']*100:.1f}%)\n"
        msg += f"• Thời gian nắm giữ: <b>{s['max_hold_days']} phiên (T+)</b>\n\n"

    msg += "⚠️ <i>Khuyến nghị: Quản trị rủi ro tối đa 2% NAV/mã (hoặc giải ngân <= 25% NAV/mã). Tối đa 2 mã/ngành.</i>"
    return msg

if __name__ == "__main__":
    print("Notifier module with photo support ready.")
