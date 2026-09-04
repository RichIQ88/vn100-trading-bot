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
from indicators import compute_indicators, add_relative_strength
from strategy import generate_signals
from chart_generator import generate_signal_chart
from market_regime import get_market_regime
from position_tracker import load_positions, add_new_position, save_positions, calculate_position_size
from sector_data import get_sector, check_sector_limit, get_sector_breakdown
from notifier import send_telegram_alert, send_telegram_alert_with_status, send_telegram_photo, get_telegram_credentials
from monthly_report import generate_monthly_report
from backtest import calculate_performance_metrics
from ai_assistant import (
    build_stock_context,
    call_gemini_api,
    generate_fallback_analysis,
    get_gemini_api_key,
    SYSTEM_BROKER_INSTRUCTION
)

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
st.sidebar.markdown("### 🤖 Trợ Lý Telegram 2 Chiều")
st.sidebar.caption("Nhắn tin trực tiếp với bot để nhận phản hồi sau 2s:")
st.sidebar.markdown("""
• `/scan`: Quét cơ hội mua toàn thị trường
• `FPT` hoặc `/chart SSI`: Gửi biểu đồ kỹ thuật tức thì
• `/pos`: Xem danh mục vị thế đang mở
• `/market`: Cập nhật xu hướng VN-Index
• `/calc 500 FPT`: Tính khối lượng mua theo NAV
""")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Cài đặt Quét Tín hiệu")
scan_mode = st.sidebar.selectbox(
    "Chế độ Chiến lược",
    ["leader_alpha", "high_winrate", "multi_setup"],
    index=0,
    help="leader_alpha: Tối ưu Winrate đỉnh cao với RS Leader & Smart Money CMF | high_winrate: 3-4 lệnh/tháng | multi_setup: bắt cả breakout và bắt đáy"
)
lookback_days = st.sidebar.slider("Số phiên quét gần nhất", min_value=1, max_value=10, value=3)

# ----------------- MAIN TABS -----------------
st.markdown('<div class="main-header">🚀 HỆ THỐNG CỐ VẤN GIAO DỊCH VN100</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Quản lý khuyến nghị, tối ưu hóa điểm vào RS Leader, quản trị rủi ro danh mục và định cỡ vị thế</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💼 Vị Thế Đang Mở & Ngành",
    "🔔 Quét Tín Hiệu (RS Leader)",
    "💰 Quản Trị Vốn (Position Sizer)",
    "📊 Hiệu Suất Hệ Thống (8 Năm)",
    "📜 Báo Cáo Tháng Khách Hàng",
    "🧠 Trợ Lý AI Research & Tư Vấn"
])

# ----------------- TAB 1: LIVE POSITIONS & SECTOR -----------------
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
        if 'sector' not in df_open.columns:
            df_open['sector'] = df_open['symbol'].apply(get_sector)
        if 'shares' not in df_open.columns:
            df_open['shares'] = 0

        st.dataframe(
            df_open[['symbol', 'sector', 'entry_date', 'entry_price', 'tp_target', 'sl_target', 'shares', 'setup_name', 'tp1_hit']],
            column_config={
                "symbol": "Mã CP",
                "sector": "Nhóm Ngành",
                "entry_date": "Ngày Mua",
                "entry_price": st.column_config.NumberColumn("Giá Vào (Vốn)", format="%.2f"),
                "tp_target": st.column_config.NumberColumn("Mục Tiêu TP", format="%.2f"),
                "sl_target": st.column_config.NumberColumn("Dừng Lỗ SL", format="%.2f"),
                "shares": st.column_config.NumberColumn("Khối Lượng CP", format="%d"),
                "setup_name": "Setup",
                "tp1_hit": st.column_config.CheckboxColumn("Đã chốt 50% TP1?")
            },
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### 🛡️ Cơ Cấu Phân Bổ Theo Ngành (Tối đa 2 mã/ngành)")
        sec_breakdown = get_sector_breakdown(positions)
        sec_cols = st.columns(min(len(sec_breakdown), 4) if sec_breakdown else 1)
        for idx, (sec_name, count) in enumerate(sec_breakdown.items()):
            col_idx = idx % len(sec_cols)
            with sec_cols[col_idx]:
                if count >= 2:
                    st.warning(f"⚠️ **{sec_name}**: {count}/2 mã (Đã chạm trần!)")
                else:
                    st.success(f"✅ **{sec_name}**: {count}/2 mã (An toàn)")
    else:
        st.info("Hiện tại chưa có mã nào trong danh mục vị thế mở. Hãy chuyển sang Tab 'Quét Tín Hiệu' để tìm kiếm cơ hội mới!")

    st.markdown("---")
    st.markdown("#### ➕ Thêm Khuyến Nghị Thủ Công Vào Danh Mục")
    with st.expander("Nhấp vào đây để thêm mã khuyến nghị mới"):
        with st.form("add_pos_form"):
            col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
            with col_f1:
                f_sym = st.text_input("Mã cổ phiếu", value="FPT").upper()
            with col_f2:
                f_price = st.number_input("Giá mua", value=130.0, step=0.1)
            with col_f3:
                f_tp = st.number_input("Giá chốt lời TP", value=round(f_price * 1.06, 2), step=0.1)
            with col_f4:
                f_sl = st.number_input("Giá cắt lỗ SL", value=round(f_price * 0.96, 2), step=0.1)
            with col_f5:
                f_shares = st.number_input("Khối lượng CP", value=1000, step=100)
            f_submit = st.form_submit_button("Thêm Vào Danh Mục Theo Dõi")
            if f_submit:
                ok_add, msg_add = add_new_position(
                    f_sym,
                    pd.Timestamp.now().strftime("%Y-%m-%d"),
                    f_price,
                    f_tp,
                    f_sl,
                    "Manual Entry",
                    shares=f_shares
                )
                if ok_add:
                    st.success(f"✅ {msg_add}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg_add}")

# ----------------- TAB 2: SCANNER & CHARTS (RS LEADER) -----------------
with tab2:
    st.markdown("### 🔔 Quét Tín Hiệu Định Lượng & Biểu Đồ Kỹ Thuật")
    col_s1, col_s2 = st.columns([2, 3])

    with col_s1:
        if st.button("🚀 Kích Hoạt Quét Toàn Bộ VN100 Ngay", type="primary"):
            with st.spinner("Đang tính toán 5 chỉ báo, đo lường RS Leader và dòng tiền CMF..."):
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
                        df_ind = add_relative_strength(df_ind)
                        df_sig = generate_signals(df_ind, mode=scan_mode)
                        tail = df_sig.tail(lookback_days)
                        for idx, row in tail.iterrows():
                            if row['signal'] == 1:
                                p = float(row['close'])
                                atr_v = float(row.get('atr', p * 0.025)) if pd.notnull(row.get('atr')) else p * 0.025
                                tp_dyn = round(p + 2.5 * atr_v, 2)
                                sl_dyn = round(max(p - 1.5 * atr_v, p * 0.945), 2)
                                rs_v = float(row.get('rs_score', 100.0))
                                cmf_v = float(row.get('cmf', 0.0))
                                found.append({
                                    'Mã': sym,
                                    'Ngành': get_sector(sym),
                                    'Ngày': row['time'].strftime("%Y-%m-%d"),
                                    'Setup': row['setup_name'],
                                    'Giá Mua': p,
                                    'TP (ATR)': tp_dyn,
                                    'SL (ATR)': sl_dyn,
                                    'RS Leader': round(rs_v, 1),
                                    'CMF Dòng Tiền': round(cmf_v, 2),
                                    'Vol/MA20': round(float(row['vol_ratio']), 2)
                                })
                    except Exception:
                        continue
                if found:
                    found = sorted(found, key=lambda x: x['RS Leader'], reverse=True)
                    st.success(f"🎯 Tìm thấy {len(found)} tín hiệu mua thỏa mãn (Ưu tiên RS Leader cao nhất)!")
                    st.dataframe(pd.DataFrame(found), use_container_width=True, hide_index=True)
                else:
                    st.info("Không có mã nào đạt đủ tiêu chuẩn khắt khe trong các phiên được chọn.")

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
            df_view = add_relative_strength(df_view)
            last_row = df_view.iloc[-1]
            last_p = float(last_row['close'])
            atr_v = float(last_row.get('atr', last_p * 0.025))
            tp_est = round(last_p + 2.5 * atr_v, 2)
            sl_est = round(max(last_p - 1.5 * atr_v, last_p * 0.945), 2)
            rs_val = float(last_row.get('rs_score', 100.0))
            cmf_val = float(last_row.get('cmf', 0.0))

            chart_file = generate_signal_chart(df_view, selected_sym, tp_target=tp_est, sl_target=sl_est, lookback=60)
            if chart_file and os.path.exists(chart_file):
                col_c1, col_c2, col_c3 = st.columns(3)
                with col_c1:
                    st.metric("Nhóm Ngành", get_sector(selected_sym))
                with col_c2:
                    st.metric("RS Score (vs VNINDEX)", f"{rs_val:.1f}", delta="Leader" if rs_val >= 102 else "Neutral")
                with col_c3:
                    st.metric("CMF Dòng Tiền (20 phiên)", f"{cmf_val:+.2f}", delta="Tích lũy" if cmf_val > 0 else "Phân phối")
                st.image(chart_file, caption=f"Biểu đồ kỹ thuật {selected_sym} (Dải trên đỏ, Trục giữa xanh lam, Dải dưới xanh lá, EMA9 vàng, TP/SL đứt đoạn)")

# ----------------- TAB 3: POSITION SIZER & RISK CALCULATOR -----------------
with tab3:
    st.markdown("### 💰 Máy Tính Quản Trị Vốn & Định Cỡ Vị Thế (Position Sizer)")
    st.caption("Công thức chuẩn quản trị rủi ro quỹ: Giới hạn mức lỗ tối đa 2% NAV mỗi lệnh và giải ngân <= 25% NAV/mã.")

    col_rk1, col_rk2 = st.columns(2)
    with col_rk1:
        calc_nav_mil = st.number_input("Tổng quy mô vốn đầu tư (NAV - Triệu VNĐ):", value=500.0, step=50.0)
        calc_risk_pct = st.slider("Mức chịu rủi ro tối đa mỗi lệnh (% NAV):", min_value=1.0, max_value=3.0, value=2.0, step=0.5)
        calc_sym = st.selectbox("Chọn mã cổ phiếu dự định mua:", all_csvs, index=all_csvs.index("FPT") if "FPT" in all_csvs else 0)

    # Đọc giá hiện tại của mã được chọn
    c_csv = os.path.join(DATA_DIR, f"{calc_sym}.csv")
    if os.path.exists(c_csv):
        df_c = pd.read_csv(c_csv)
        df_c = compute_indicators(df_c)
        cur_p = float(df_c['close'].iloc[-1])
        cur_atr = float(df_c['atr'].iloc[-1]) if pd.notnull(df_c['atr'].iloc[-1]) else cur_p * 0.025
        sug_tp = round(cur_p + 2.5 * cur_atr, 2)
        sug_sl = round(max(cur_p - 1.5 * cur_atr, cur_p * 0.945), 2)
    else:
        cur_p, sug_tp, sug_sl = 100.0, 106.0, 96.0

    with col_rk2:
        in_price = st.number_input("Giá mua dự kiến (Nghìn VNĐ):", value=cur_p, step=0.1)
        in_sl = st.number_input("Giá cắt lỗ (SL - Nghìn VNĐ):", value=sug_sl, step=0.1)
        in_tp = st.number_input("Giá chốt lời (TP - Nghìn VNĐ):", value=sug_tp, step=0.1)

    nav_vnd = calc_nav_mil * 1_000_000.0
    res_size = calculate_position_size(nav_vnd, in_price, in_sl, risk_pct=calc_risk_pct/100.0)

    st.markdown("---")
    st.markdown(f"#### 📊 Kế Hoạch Giải Ngân Khuyến Nghị Cho **{calc_sym}** ({get_sector(calc_sym)}):")
    col_out1, col_out2, col_out3, col_out4 = st.columns(4)
    with col_out1:
        st.metric("Khối lượng nên mua", f"{res_size['shares']:,} CP", help="Đã làm tròn xuống lô 100 HOSE")
    with col_out2:
        st.metric("Tổng giá trị giải ngân", f"{res_size['capital_vnd']/1e6:,.1f} tr VNĐ", delta=f"{res_size['capital_pct']}% NAV")
    with col_out3:
        st.metric("Mức lỗ tối đa nếu chạm SL", f"{res_size['max_loss_vnd']/1e6:,.2f} tr VNĐ", delta=f"-{res_size['max_loss_pct']}% NAV (Rủi ro)")
    with col_out4:
        reward_vnd = res_size['shares'] * (in_tp - in_price) * 1000.0
        rr_ratio = reward_vnd / res_size['max_loss_vnd'] if res_size['max_loss_vnd'] > 0 else 0.0
        st.metric("Lợi nhuận kỳ vọng (TP)", f"{reward_vnd/1e6:,.2f} tr VNĐ", delta=f"R:R = {rr_ratio:.2f}")

    if st.button(f"📥 Thêm {calc_sym} ({res_size['shares']:,} CP) vào Danh mục Vị thế mở"):
        ok_a, msg_a = add_new_position(
            calc_sym,
            pd.Timestamp.now().strftime("%Y-%m-%d"),
            in_price,
            in_tp,
            in_sl,
            "Risk-Sized Position",
            shares=res_size['shares']
        )
        if ok_a:
            st.success(f"✅ {msg_a}")
            st.rerun()
        else:
            st.warning(f"⚠️ {msg_a}")

# ----------------- TAB 4: PERFORMANCE METRICS -----------------
with tab4:
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

# ----------------- TAB 5: MONTHLY REPORT -----------------
with tab5:
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

# ----------------- TAB 6: AI BROKER CO-PILOT -----------------
with tab6:
    st.markdown("### 🧠 Trợ Lý Phân Tích & Nghiên Cứu Đầu Tư AI (Broker Co-Pilot)")
    st.caption("Trợ lý trí tuệ nhân tạo chuyên sâu cho Môi giới: Tự động nạp dữ liệu định lượng, săn Catalyst Gap, phản biện rủi ro và soạn bản tin Room VIP.")

    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = [
            {"role": "assistant", "content": "👋 Xin chào! Tôi là **VN100 Broker Co-Pilot**. Hãy chọn một mã cổ phiếu ở trên để tôi phân tích chuyên sâu hoặc bạn có thể đặt bất kỳ câu hỏi nào về thị trường!"}
        ]

    col_ai_top1, col_ai_top2 = st.columns([1, 2])
    with col_ai_top1:
        ai_symbol = st.selectbox("Chọn mã cổ phiếu cần nghiên cứu:", all_csvs, index=all_csvs.index("FPT") if "FPT" in all_csvs else 0, key="ai_stock_select")
    with col_ai_top2:
        saved_key = get_gemini_api_key()
        custom_api_key = st.text_input(
            "Google Gemini API Key (Miễn phí tại aistudio.google.com):",
            value=saved_key,
            type="password",
            placeholder="Dán Gemini API Key vào đây (hoặc để trống để dùng Bộ Phân Tích Định Lượng Tích Hợp)",
            help="Hệ thống ưu tiên dùng API Key bạn nhập hoặc cấu hình trong Secrets GEMINI_API_KEY."
        )

    st.markdown("##### ⚡ Phân Tích 1-Chạm Nhanh Cho Mã Đã Chọn:")
    btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)
    trigger_action = None
    with btn_c1:
        if st.button("📊 Phân Tích Kỹ Thuật & Dòng Tiền", use_container_width=True):
            trigger_action = "technical"
    with btn_c2:
        if st.button("🕵️ Săn Catalyst Gap", use_container_width=True):
            trigger_action = "catalyst"
    with btn_c3:
        if st.button("😈 Phản Biện Rủi Ro (Devil's Advocate)", use_container_width=True):
            trigger_action = "devil"
    with btn_c4:
        if st.button("📢 Soạn Khuyến Nghị Room VIP", use_container_width=True):
            trigger_action = "room_vip"

    # Xử lý khi bấm nút 1-chạm
    if trigger_action:
        ctx = build_stock_context(ai_symbol)
        if ctx:
            user_label = {
                "technical": f"Yêu cầu phân tích Kỹ thuật & Dòng tiền cho mã {ai_symbol}",
                "catalyst": f"Săn lùng Catalyst Gap và triển vọng kỳ vọng cho mã {ai_symbol}",
                "devil": f"Đóng vai phản biện rủi ro (Devil's Advocate): Tại sao KHÔNG NÊN mua {ai_symbol}?",
                "room_vip": f"Soạn tin nhắn khuyến nghị lướt sóng T+ chuyên nghiệp cho mã {ai_symbol} gửi Room VIP"
            }.get(trigger_action, f"Phân tích {ai_symbol}")

            st.session_state.ai_messages.append({"role": "user", "content": user_label})

            with st.spinner(f"Đang bóc tách dữ liệu và nhờ AI phân tích {ai_symbol}..."):
                active_key = custom_api_key.strip() if custom_api_key else saved_key
                response_text = None
                if active_key:
                    sys_prompt = f"{SYSTEM_BROKER_INSTRUCTION}\n\n[DỮ LIỆU ĐỊNH LƯỢNG THỰC TẾ MÃ {ai_symbol}]:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"
                    prompt = f"Hãy thực hiện yêu cầu: {user_label} đối với cổ phiếu {ai_symbol} dựa trên các dữ liệu định lượng thực tế đã cung cấp."
                    response_text = call_gemini_api(prompt, system_prompt=sys_prompt, api_key=active_key)
                
                if not response_text:
                    response_text = generate_fallback_analysis(ctx, trigger_action)

                st.session_state.ai_messages.append({"role": "assistant", "content": response_text})
                st.rerun()

    # Hiển thị lịch sử chat
    st.markdown("---")
    for m in st.session_state.ai_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # Ô nhập chat tự do
    user_query = st.chat_input("Nhập câu hỏi hoặc yêu cầu phân tích tự do cho AI (Ví dụ: Đánh giá triển vọng ngành Thép quý này?)...")
    if user_query:
        st.session_state.ai_messages.append({"role": "user", "content": user_query})
        with st.spinner("AI đang tư duy và phân tích..."):
            active_key = custom_api_key.strip() if custom_api_key else saved_key
            response_text = None
            ctx = build_stock_context(ai_symbol)
            if active_key:
                sys_prompt = f"{SYSTEM_BROKER_INSTRUCTION}\n\n[DỮ LIỆU ĐỊNH LƯỢNG MÃ ĐANG CHỌN {ai_symbol}]:\n{json.dumps(ctx, ensure_ascii=False, indent=2) if ctx else 'Không có dữ liệu'}"
                response_text = call_gemini_api(user_query, system_prompt=sys_prompt, api_key=active_key)

            if not response_text:
                if ctx and any(word in user_query.upper() for word in ["RỦI RO", "KHÔNG NÊN", "BÁN", "XẤU"]):
                    response_text = generate_fallback_analysis(ctx, "devil")
                elif ctx and any(word in user_query.upper() for word in ["ROOM", "VIP", "KHUYẾN NGHỊ", "PHÍM"]):
                    response_text = generate_fallback_analysis(ctx, "room_vip")
                elif ctx:
                    response_text = generate_fallback_analysis(ctx, "technical")
                else:
                    response_text = "Vui lòng chọn một mã cổ phiếu hợp lệ trong rổ VN100 hoặc nhập Gemini API Key để trò chuyện tự do về mọi chủ đề vĩ mô!"

            st.session_state.ai_messages.append({"role": "assistant", "content": response_text})
            st.rerun()

    col_rst1, col_rst2 = st.columns([1, 5])
    with col_rst1:
        if st.button("🗑️ Xóa Lịch Sử Chat"):
            st.session_state.ai_messages = [
                {"role": "assistant", "content": "Lịch sử chat đã được làm mới. Tôi sẵn sàng cho phiên nghiên cứu mới!"}
            ]
            st.rerun()

