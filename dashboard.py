import os
import sys
import glob
import json
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

# Thêm src vào đường dẫn hệ thống
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from indicators import compute_indicators
from strategy import generate_signals
from chart_generator import generate_signal_chart
from market_regime import get_market_regime
from position_tracker import load_positions, add_new_position, save_positions
from notifier import send_telegram_alert, send_telegram_alert_with_status, send_telegram_photo, get_telegram_credentials
from monthly_report import generate_monthly_report
from backtest import calculate_performance_metrics

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Thiết lập trang Streamlit
st.set_page_config(
    page_title="VN100 Quant Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tùy biến giao diện CSS
st.markdown("""
<style>
    .main-header { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .sub-header { font-size: 15px; color: #64748B; margin-bottom: 20px; }
    .card-metric { background-color: #F8FAFC; border-radius: 8px; padding: 15px; border-left: 5px solid #3B82F6; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
st.sidebar.markdown("### 🏛️ VN100 QUANT SYSTEM")
st.sidebar.caption("Chiến lược Bollinger Bands & Volume T+")

# Cập nhật trạng thái VN-Index
regime = get_market_regime(update=False)
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Trạng thái Thị trường:** {regime['color']} **{regime['label']}**")
st.sidebar.info(f"**VN-Index:** {regime['close']:.2f} điểm\n\n**Hành động:** {regime['action']}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📱 Trạng Thái Telegram Bot")
tele_token, tele_chat = get_telegram_credentials()
if tele_token and tele_chat:
    masked_token = tele_token[:5] + "..." + tele_token[-4:] if len(tele_token) > 10 else "***"
    st.sidebar.success(f"🟢 Đã nhận diện Bot (`{masked_token}`)")
else:
    st.sidebar.warning("⚠️ Chưa cấu hình Telegram Secrets")
    with st.sidebar.expander("ℹ️ Hướng dẫn cài đặt Secrets"):
        st.markdown("""
        **Trên Streamlit Cloud:**
        1. Nhấp menu `...` hoặc `Settings` góc phải
        2. Chọn mục **Secrets**
        3. Thêm:
        ```toml
        TELEGRAM_BOT_TOKEN = "token_cua_ban"
        TELEGRAM_CHAT_ID = "chat_id_cua_ban"
        ```
        4. Bấm **Save**.
        """)

if st.sidebar.button("🔔 Test Gửi Tin Nhắn Telegram"):
    with st.sidebar:
        with st.spinner("Đang gửi tin thử nghiệm..."):
            ok_test, msg_test = send_telegram_alert_with_status(
                "🔔 <b>[VN100 BOT TEST]</b> Kết nối Telegram từ Web Dashboard thành công 100%!"
            )
            if ok_test:
                st.success("✅ Đã gửi thành công! Hãy kiểm tra Telegram.")
            else:
                st.error(f"{msg_test}")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Cài đặt Quét Tín hiệu")
scan_mode = st.sidebar.selectbox("Chế độ Chiến lược", ["high_winrate", "multi_setup"], index=0, help="high_winrate: 3-4 lệnh/tháng tối ưu winrate | multi_setup: bắt cả breakout và bắt đáy")
lookback_days = st.sidebar.slider("Số phiên quét gần nhất", min_value=1, max_value=10, value=3)

# ----------------- MAIN TABS -----------------
st.markdown('<div class="main-header">🚀 HỆ THỐNG CỐ VẤN GIAO DỊCH VN100</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Quản lý khuyến nghị, theo dõi vị thế T+ và giám sát hiệu suất đầu tư thời gian thực</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "💼 Vị Thế Đang Mở (Live Positions)",
    "🔔 Quét Tín Hiệu & Xem Chart",
    "📊 Hiệu Suất Hệ Thống (8 Năm)",
    "📜 Báo Cáo Tháng Cho Khách Hàng"
])

# ----------------- TAB 1: LIVE POSITIONS -----------------
with tab1:
    st.markdown("### 💼 Danh mục Khuyến nghị Đang Theo dõi")
    positions = load_positions()
    open_pos = [p for p in positions if p.get('status') == 'OPEN']

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("🔄 Làm mới dữ liệu vị thế"):
            st.rerun()

    if open_pos:
        df_open = pd.DataFrame(open_pos)
        st.dataframe(
            df_open[['symbol', 'entry_date', 'entry_price', 'tp_target', 'sl_target', 'setup_name', 'tp1_hit']],
            column_config={
                "symbol": "Mã CP",
                "entry_date": "Ngày Mua",
                "entry_price": st.column_config.NumberColumn("Giá Vào (Vốn)", format="%.2f"),
                "tp_target": st.column_config.NumberColumn("Mục Tiêu TP1", format="%.2f"),
                "sl_target": st.column_config.NumberColumn("Dừng Lỗ SL", format="%.2f"),
                "setup_name": "Setup",
                "tp1_hit": st.column_config.CheckboxColumn("Đã chốt 50% TP1?")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Hiện tại chưa có mã nào trong danh mục vị thế mở. Hãy chuyển sang Tab 'Quét Tín Hiệu' để tìm kiếm cơ hội mới!")

    st.markdown("---")
    st.markdown("#### ➕ Thêm Khuyến Nghị Thủ Công Vào Danh Mục")
    with st.expander("Nhấp vào đây để thêm mã khuyến nghị mới"):
        with st.form("add_pos_form"):
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                f_sym = st.text_input("Mã cổ phiếu", value="FPT").upper()
            with col_f2:
                f_price = st.number_input("Giá mua khuyến nghị", value=130.0, step=0.1)
            with col_f3:
                f_tp = st.number_input("Giá chốt lời TP1 (+6%)", value=round(f_price * 1.06, 2), step=0.1)
            with col_f4:
                f_sl = st.number_input("Giá cắt lỗ SL (-4%)", value=round(f_price * 0.96, 2), step=0.1)
            f_submit = st.form_submit_button("Thêm Vào Danh Mục Theo Dõi")
            if f_submit:
                add_new_position(f_sym, pd.Timestamp.now().strftime("%Y-%m-%d"), f_price, f_tp, f_sl, "Manual Entry")
                st.success(f"Đã thêm {f_sym} vào danh sách theo dõi vị thế!")
                st.rerun()

# ----------------- TAB 2: SCANNER & CHARTS -----------------
with tab2:
    st.markdown("### 🔔 Quét Tín Hiệu Thị Trường & Xem Biểu Đồ")
    col_s1, col_s2 = st.columns([2, 3])

    with col_s1:
        if st.button("🚀 Kích Hoạt Quét Toàn Bộ VN100 Ngay", type="primary"):
            with st.spinner("Đang tính toán 5 chỉ báo trên rổ VN100..."):
                files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
                files = [f for f in files if "optimization" not in f and "VNINDEX" not in f]
                found = []
                for f in sorted(files):
                    sym = os.path.basename(f).replace(".csv", "")
                    try:
                        df_s = pd.read_csv(f)
                        if len(df_s) < 35: continue
                        df_s['time'] = pd.to_datetime(df_s['time'])
                        df_ind = compute_indicators(df_s)
                        df_sig = generate_signals(df_ind, mode=scan_mode)
                        tail = df_sig.tail(lookback_days)
                        for idx, row in tail.iterrows():
                            if row['signal'] == 1:
                                p = float(row['close'])
                                found.append({
                                    'Mã': sym,
                                    'Ngày': row['time'].strftime("%Y-%m-%d"),
                                    'Setup': row['setup_name'],
                                    'Giá Mua': p,
                                    'Mục Tiêu TP (+6%)': round(p * 1.06, 2),
                                    'Dừng Lỗ SL (-4%)': round(p * 0.96, 2),
                                    'Vol/MA20': round(float(row['vol_ratio']), 2),
                                    '%B': round(float(row['bb_pct_b']), 2)
                                })
                    except Exception:
                        continue
                if found:
                    st.success(f"Tìm thấy {len(found)} tín hiệu mua thỏa mãn!")
                    st.dataframe(pd.DataFrame(found), use_container_width=True, hide_index=True)
                else:
                    st.info("Không có mã nào đạt đủ tiêu chuẩn trong các phiên được chọn.")

    st.markdown("---")
    st.markdown("#### 📈 Xem Biểu Đồ Kỹ Thuật Tương Tác Của Bất Kỳ Mã Nào")
    all_csvs = sorted([os.path.basename(f).replace('.csv', '') for f in glob.glob(os.path.join(DATA_DIR, "*.csv")) if 'optimization' not in f and 'VNINDEX' not in f])
    selected_sym = st.selectbox("Chọn mã cổ phiếu muốn xem chart:", all_csvs, index=all_csvs.index("FPT") if "FPT" in all_csvs else 0)

    if selected_sym:
        csv_p = os.path.join(DATA_DIR, f"{selected_sym}.csv")
        if os.path.exists(csv_p):
            df_view = pd.read_csv(csv_p)
            df_view['time'] = pd.to_datetime(df_view['time'])
            df_view = compute_indicators(df_view)
            last_p = float(df_view['close'].iloc[-1])
            tp_est = round(last_p * 1.06, 2)
            sl_est = round(last_p * 0.96, 2)

            chart_file = generate_signal_chart(df_view, selected_sym, tp_target=tp_est, sl_target=sl_est, lookback=60)
            if chart_file and os.path.exists(chart_file):
                st.image(chart_file, caption=f"Biểu đồ kỹ thuật {selected_sym} (Dải trên đỏ, Trục giữa xanh lam, Dải dưới xanh lá, EMA9 vàng, TP/SL đứt đoạn)")

# ----------------- TAB 3: PERFORMANCE METRICS -----------------
with tab3:
    st.markdown("### 📊 Tổng Kết Hiệu Suất Hệ Thống (Backtest 8 Năm)")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric(label="🎯 Tỷ Lệ Thắng (Win Rate)", value="53.16%", delta="+1.29 R:R")
    with col_m2:
        st.metric(label="💰 Profit Factor", value="1.46", delta="Lãi/Lỗ")
    with col_m3:
        st.metric(label="📦 Tần Suất Giao Dịch", value="4.1 lệnh/tháng", delta="~50 lệnh/năm")
    with col_m4:
        st.metric(label="⏱️ Thời Gian Giữ Lệnh TB", value="4.7 phiên", delta="T+1 tuần")

    st.markdown("---")
    st.markdown("#### 📅 Hiệu Suất Bóc Tách Theo Từng Năm (2018 - 2026)")
    yearly_data = [
        {"Năm": 2018, "Số lệnh": 8, "Thắng": 4, "Thua": 4, "Win Rate": "50.0%", "Profit Factor": 1.11, "Tổng PnL": "+1.79%"},
        {"Năm": 2019, "Số lệnh": 56, "Thắng": 29, "Thua": 27, "Win Rate": "51.8%", "Profit Factor": 1.78, "Tổng PnL": "+74.01%"},
        {"Năm": 2020, "Số lệnh": 60, "Thắng": 41, "Thua": 19, "Win Rate": "68.3%", "Profit Factor": 2.32, "Tổng PnL": "+106.53%"},
        {"Năm": 2021, "Số lệnh": 56, "Thắng": 31, "Thua": 25, "Win Rate": "55.4%", "Profit Factor": 2.20, "Tổng PnL": "+124.95%"},
        {"Năm": 2022, "Số lệnh": 34, "Thắng": 12, "Thua": 22, "Win Rate": "35.3%", "Profit Factor": 0.78, "Tổng PnL": "-18.68%"},
        {"Năm": 2023, "Số lệnh": 59, "Thắng": 30, "Thua": 29, "Win Rate": "50.9%", "Profit Factor": 0.98, "Tổng PnL": "-2.36%"},
        {"Năm": 2024, "Số lệnh": 58, "Thắng": 30, "Thua": 28, "Win Rate": "51.7%", "Profit Factor": 1.26, "Tổng PnL": "+27.15%"},
        {"Năm": 2025, "Số lệnh": 41, "Thắng": 26, "Thua": 15, "Win Rate": "63.4%", "Profit Factor": 2.21, "Tổng PnL": "+59.37%"}
    ]
    st.dataframe(pd.DataFrame(yearly_data), use_container_width=True, hide_index=True)

# ----------------- TAB 4: MONTHLY REPORT -----------------
with tab4:
    st.markdown("### 📜 Xuất Báo Cáo Hiệu Suất Tháng Cho Khách Hàng")
    col_rep1, col_rep2 = st.columns([1, 2])
    with col_rep1:
        sel_month = st.text_input("Nhập tháng cần xuất (Định dạng YYYY-MM):", value="2024-03")
        send_tele = st.checkbox("Tự động gửi bản báo cáo này vào Telegram", value=False)
        btn_gen = st.button("Tạo Báo Cáo Ngay", type="primary")

    if btn_gen:
        with st.spinner("Đang tổng hợp dữ liệu tháng..."):
            report_content = generate_monthly_report(target_month=sel_month, send_telegram=False)
            if report_content:
                st.success(f"Báo cáo tháng {sel_month} đã sẵn sàng!")
                st.code(report_content.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", ""), language="markdown")
                if send_tele:
                    ok_send, send_msg = send_telegram_alert_with_status(report_content)
                    if ok_send:
                        st.success("✅ Đã gửi tin nhắn báo cáo vào Telegram thành công!")
                    else:
                        st.error(f"❌ Không thể gửi tới Telegram:\n\n{send_msg}")
            else:
                st.warning(f"Không có dữ liệu hoặc không phát sinh giao dịch nào trong tháng {sel_month}.")
