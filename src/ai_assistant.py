import os
import sys
import json
import requests
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from indicators import compute_indicators, add_relative_strength
from market_regime import get_market_regime
from sector_data import get_sector

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def get_gemini_api_key(custom_key: str = None) -> str:
    """Lấy API Key của Google Gemini từ tham số, biến môi trường hoặc Streamlit Secrets"""
    if custom_key and custom_key.strip():
        return custom_key.strip()
    val = os.getenv("GEMINI_API_KEY", "").strip()
    if val:
        return val
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return ""

def build_stock_context(symbol: str) -> dict:
    """Trích xuất toàn bộ dữ liệu định lượng thời gian thực của cổ phiếu để nạp vào AI"""
    symbol = symbol.upper().strip()
    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")
    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path)
        df['time'] = pd.to_datetime(df['time'])
        df = compute_indicators(df)
        df = add_relative_strength(df)

        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        p = float(last['close'])
        atr_v = float(last.get('atr', p * 0.025)) if pd.notnull(last.get('atr')) else p * 0.025
        tp_target = round(p + 2.5 * atr_v, 2)
        sl_target = round(max(p - 1.5 * atr_v, p * 0.945), 2)
        regime = get_market_regime(update=False)

        return {
            'symbol': symbol,
            'sector': get_sector(symbol),
            'last_date': last['time'].strftime('%Y-%m-%d'),
            'current_price': p,
            'change_pct': round((p / float(prev['close']) - 1.0) * 100.0, 2),
            'bb_mid': round(float(last['bb_mid']), 2),
            'bb_upper': round(float(last['bb_upper']), 2),
            'bb_lower': round(float(last['bb_lower']), 2),
            'pct_b': round(float(last['bb_pct_b']), 2),
            'bandwidth': round(float(last['bb_width']), 3),
            'is_squeeze': bool(last.get('is_squeeze', False)),
            'vol_ratio': round(float(last['vol_ratio']), 2),
            'rs_score': round(float(last.get('rs_score', 100.0)), 1),
            'is_leader': bool(last.get('is_leader', False)),
            'cmf': round(float(last.get('cmf', 0.0)), 2),
            'atr': round(atr_v, 2),
            'tp_target': tp_target,
            'sl_target': sl_target,
            'market_regime': regime['label'],
            'market_allow_buy': regime['allow_buy']
        }
    except Exception as e:
        print(f"[-] Lỗi nạp dữ liệu {symbol}: {e}")
        return None

SYSTEM_BROKER_INSTRUCTION = """Bạn là 'VN100 Broker Co-Pilot' - Cố vấn phân tích đầu tư định lượng và chiến lược cao cấp, đồng hành cùng một Môi giới Chứng khoán (Broker) chuyên nghiệp tại thị trường Việt Nam (HOSE/HNX).
Mục tiêu: Giúp Broker tìm kiếm cơ hội lướt sóng T+, phát hiện Catalyst Gap, phản biện rủi ro đa chiều và soạn thảo khuyến nghị Room VIP.
Nguyên tắc:
- Kỹ thuật: Bollinger Bands, RS Leader (>102), Dòng tiền Smart Money CMF, Volume nảy cạn cung.
- Quản trị rủi ro: Cắt lỗ tối đa 4-5.5% (hoặc 1.5x ATR), TP chốt 50% tại 2.5x ATR, rủi ro mỗi lệnh tối đa 2% NAV, tối đa 2 mã/ngành.
- Văn phong: Chuyên gia sắc sảo, tự tin, dùng số liệu cụ thể, tiếng Việt chuẩn thuật ngữ chứng khoán (T+2.5, VN-Index, cạn cung, lái gom, bẫy bull-trap, sóng ngành...).
"""

def call_gemini_api(prompt: str, system_prompt: str = None, api_key: str = None) -> str:
    """Gọi trực tiếp Google Gemini 1.5 Flash API qua HTTP REST"""
    key = get_gemini_api_key(api_key)
    if not key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    
    contents = []
    if system_prompt:
        contents.append({
            "role": "user",
            "parts": [{"text": f"[HƯỚNG DẪN HỆ THỐNG VÀ BỘ KHUNG TƯ DUY]:\n{system_prompt}"}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Tôi đã nắm rõ vai trò Cố vấn Phân tích Đầu tư VN100. Tôi sẵn sàng phân tích chuyên sâu cho bạn."}]
        })

    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1500
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
        else:
            print(f"[-] Gemini API Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[-] Lỗi kết nối Gemini API: {e}")

    return None

def generate_fallback_analysis(ctx: dict, action_type: str) -> str:
    """Tự động tạo báo cáo định lượng chuyên sâu nếu người dùng chưa cài đặt API Key"""
    sym = ctx['symbol']
    sec = ctx['sector']
    p = ctx['current_price']
    rs = ctx['rs_score']
    cmf = ctx['cmf']
    vol = ctx['vol_ratio']
    tp = ctx['tp_target']
    sl = ctx['sl_target']
    pct_b = ctx['pct_b']
    
    cmf_desc = "🟢 Dòng tiền lớn (Smart Money) đang tích lũy dương" if cmf > 0 else "🔴 Dòng tiền tổ chức đang có dấu hiệu phân phối nhẹ"
    rs_desc = "⭐ Thuộc nhóm Cổ Phiếu Dẫn Dắt (Leader) khỏe hơn VN-Index" if rs >= 102 else "🔹 Vận động đồng pha hoặc yếu hơn chỉ số chung"

    if action_type == "technical":
        return f"""### 📊 BÁO CÁO PHÂN TÍCH KỸ THUẬT & DÒNG TIỀN: {sym} ({sec})
• **Thị giá hiện tại:** **{p:.2f}** ({ctx['change_pct']:+.2f}%)
• **Vị thế Bollinger Bands:** %B đạt **{pct_b:.2f}** (Trục giữa SMA20: {ctx['bb_mid']:.2f}, Dải trên: {ctx['bb_upper']:.2f}).
• **Áp lực Khối lượng:** Đạt **{vol:.1f}x MA20** phiên gần nhất.
• **Sức mạnh tương quan (RS Score):** **{rs:.1f}** ➜ {rs_desc}.
• **Chaikin Money Flow (CMF 20):** **{cmf:+.2f}** ➜ {cmf_desc}.

**🎯 KHUYẾN NGHỊ VÙNG GIÁ T+ (ATR DYNAMIC):**
* **Vùng gom mua an toàn:** **{p * 0.995:.2f} – {p * 1.005:.2f}**
* **Mục tiêu Chốt lời TP (2.5x ATR):** **{tp:.2f}** (+{(tp/p - 1)*100:.1f}%) [Khuyến nghị chốt 50% vị thế]
* **Ngưỡng Cắt lỗ SL (1.5x ATR):** **{sl:.2f}** ({(sl/p - 1)*100:.1f}%) [Bảo toàn vốn tuyệt đối]
"""

    elif action_type == "devil":
        return f"""### 😈 GÓC PHẢN BIỆN RỦI RO (DEVIL'S ADVOCATE): TẠI SAO KHÔNG NÊN MUA {sym}?
1. **Rủi ro Cản kỹ thuật:** Giá đang ở mức **{p:.2f}**, biên độ lên dải trên Bollinger Bands ({ctx['bb_upper']:.2f}) không còn quá nhiều. Nếu dòng tiền suy yếu, nguy cơ tạo râu nến đảo chiều là rất lớn.
2. **Áp lực Dòng tiền Lớn:** Chỉ số CMF đang ở mức **{cmf:+.2f}**. { 'Dù dương nhưng cần kiểm định thêm lực cầu phiên ATC.' if cmf > 0 else 'Cảnh báo: Dòng tiền tổ chức đang âm, mua vào lúc này dễ dính bẫy nảy kỹ thuật (bull-trap) rồi tiếp tục giảm.' }
3. **Độ rộng Biến động (ATR {ctx['atr']:.2f}):** Khoảng cắt lỗ an toàn cách **{sl:.2f}** (tương đương {(sl/p - 1)*100:.1f}%). Nếu thị trường chung rung lắc mạnh, khả năng chạm SL là có thể xảy ra.
4. **Rủi ro Ngành {sec}:** Cần kiểm tra xem danh mục của bạn đã có mã cùng ngành chưa để tránh vi phạm nguyên tắc tập trung ngành quá 2 mã!
"""

    elif action_type == "catalyst":
        return f"""### 🕵️ BẢO MẬT CATALYST & KHOẢNG TRỐNG KỲ VỌNG (CATALYST GAP): {sym}
• **Nhóm ngành:** **{sec}**
• **Hiện trạng Dòng tiền thông minh:** CMF đạt **{cmf:+.2f}** kết hợp RS **{rs:.1f}**.
• **Nhận định Catalyst Gap:**
  - Nếu ngành {sec} đang có sóng vĩ mô hỗ trợ (hưởng lợi tỷ giá, giảm lãi suất, đẩy mạnh đầu tư công, giá hàng hóa phục hồi), mã {sym} với tư cách là Bluechip VN100 sẽ là thỏi nam châm thu hút dòng tiền đầu tiên.
  - **Dấu hiệu tích lũy cạn cung:** Khi %B co lại quanh trục giữa SMA20 ({ctx['bb_mid']:.2f}) với khối lượng thấp, đây thường là giai đoạn Smart Money âm thầm gom hàng trước khi tin tức công bố rộng rãi.
"""

    elif action_type == "room_vip":
        return f"""📢 **[KHUYẾN NGHỊ LƯỚT SÓNG T+ VIP] - CƠ HỘI {sym} ({sec})**
━━━━━━━━━━━━━━━━━━━━
🎯 **Mã cổ phiếu:** <b>{sym}</b> (Nhóm: {sec})
• **Vùng giá giải ngân:** <b>{p:.2f}</b>
• **Mục tiêu Chốt lời (TP1):** <b>{tp:.2f}</b> (+{(tp/p - 1)*100:.1f}%) ➜ <i>Chốt 50% khi chạm mục tiêu</i>
• **Ngưỡng Cắt lỗ (SL):** <b>{sl:.2f}</b> ({(sl/p - 1)*100:.1f}%) ➜ <i>Tuân thủ kỷ luật bảo toàn vốn</i>
• **Thời gian nắm giữ dự kiến:** 4 – 8 phiên (T+)

💡 **LUẬN ĐIỂM ĐỊNH LƯỢNG:**
1. Kiểm định thành công dải Bollinger Bands + Khối lượng nảy {vol:.1f}x MA20.
2. Sức mạnh RS đạt {rs:.1f} ({ 'Cổ phiếu Leader khỏe hơn thị trường' if rs >= 102 else 'Dòng tiền ổn định' }).
3. Quản trị rủi ro: Khuyến nghị tỷ trọng tối đa 20-25% NAV, rủi ro khống chế 2% NAV tài khoản.
━━━━━━━━━━━━━━━━━━━━
<i>Khuyến nghị thực hiện bởi VN100 Quant System.</i>
"""
    return "Không xác định kịch bản phân tích."
