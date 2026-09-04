import os
import sys
import glob
import argparse
import pandas as pd
from datetime import datetime, timedelta

# Đảm bảo import được các module trong src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from indicators import compute_indicators
from strategy import generate_signals
from backtest import simulate_trades, calculate_performance_metrics
from notifier import send_telegram_alert

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def get_previous_month():
    """Lấy định dạng YYYY-MM của tháng trước"""
    today = datetime.now()
    first_of_this_month = today.replace(day=1)
    last_month = first_of_this_month - timedelta(days=1)
    return last_month.strftime("%Y-%m")

def generate_monthly_report(target_month=None, send_telegram=True):
    """
    Tạo báo cáo hiệu suất giao dịch tổng hợp theo tháng dành cho khách hàng/nhà đầu tư.
    """
    if not target_month:
        target_month = get_previous_month()

    print(f"\n=================================================================")
    print(f"📊 [MONTHLY REPORT] ĐANG TỔNG HỢP HIỆU SUẤT THÁNG {target_month}")
    print(f"=================================================================\n")

    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    files = [f for f in files if "optimization" not in f]

    if not files:
        print("[-] Không tìm thấy dữ liệu trong thư mục data/.")
        return None

    all_trades = []
    for f in files:
        sym = os.path.basename(f).replace(".csv", "")
        try:
            df = pd.read_csv(f)
            if len(df) < 50:
                continue
            df['time'] = pd.to_datetime(df['time'])
            df_ind = compute_indicators(df)
            df_sig = generate_signals(df_ind, mode="high_winrate")
            trades = simulate_trades(
                df_sig,
                symbol=sym,
                take_profit_pct=0.06,
                stop_loss_pct=0.04,
                min_hold_days=3,
                max_hold_days=8
            )
            all_trades.extend(trades)
        except Exception:
            continue

    if not all_trades:
        print("[-] Chưa có giao dịch nào được ghi nhận.")
        return None

    df_trades = pd.DataFrame(all_trades)
    df_trades['entry_date'] = pd.to_datetime(df_trades['entry_date'])
    df_trades['exit_date'] = pd.to_datetime(df_trades['exit_date'])
    df_trades['entry_ym'] = df_trades['entry_date'].dt.strftime("%Y-%m")
    df_trades['exit_ym'] = df_trades['exit_date'].dt.strftime("%Y-%m")

    # Lọc các lệnh phát sinh hoặc đóng vị thế trong tháng mục tiêu
    month_trades = df_trades[df_trades['exit_ym'] == target_month].copy()
    if month_trades.empty:
        # Nếu chưa có lệnh đóng trong tháng đó, thử tìm theo tháng vào lệnh
        month_trades = df_trades[df_trades['entry_ym'] == target_month].copy()

    if month_trades.empty:
        msg = f"📊 <b>BÁO CÁO HIỆU SUẤT GIAO DỊCH THÁNG {target_month}</b>\n\n"
        msg += f"<i>Trong tháng {target_month}, hệ thống không phát sinh lệnh đóng vị thế do thị trường chưa hội tụ đủ các tiêu chí cạn cung và kiểm định trục giữa SMA20.</i>\n"
        print(f"[i] Không có lệnh nào hoàn tất trong tháng {target_month}.")
        if send_telegram:
            send_telegram_alert(msg)
        return None

    # Tính toán chỉ số thống kê
    metrics = calculate_performance_metrics(month_trades.to_dict('records'))
    total_pnl = month_trades['net_pnl_pct'].sum() * 100
    avg_hold = month_trades['days_held'].mean()

    # Tìm lệnh tốt nhất và xấu nhất
    month_trades = month_trades.sort_values(by='net_pnl_pct', ascending=False).reset_index(drop=True)
    best_trade = month_trades.iloc[0]
    worst_trade = month_trades.iloc[-1]

    # Soạn tin nhắn Telegram HTML cực đẹp chuẩn gửi khách hàng
    pnl_color = "🟢" if total_pnl >= 0 else "🔴"
    pnl_sign = "+" if total_pnl >= 0 else ""

    msg = f"📊 <b>BÁO CÁO HIỆU SUẤT GIAO DỊCH THÁNG {target_month}</b>\n"
    msg += f"<i>Hệ thống Định lượng VN100 | Bollinger Bands & Volume T+</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"📈 <b>TỔNG QUAN HIỆU SUẤT THÁNG:</b>\n"
    msg += f"• Tổng số khuyến nghị: <b>{metrics['total_trades']} lệnh</b>\n"
    msg += f"• Lệnh thắng: <b>{metrics['win_count']}</b> | Lệnh cắt lỗ: <b>{metrics['loss_count']}</b>\n"
    msg += f"• Tỷ lệ thắng (Win Rate): <b>{metrics['win_rate']}%</b>\n"
    msg += f"• Tổng PnL ròng tích lũy: {pnl_color} <b>{pnl_sign}{total_pnl:.2f}%</b>\n"
    msg += f"• Hiệu suất trung bình/lệnh: <b>{metrics['avg_return_pct']:+.2f}%</b>\n"
    msg += f"• Hệ số Lợi nhuận (Profit Factor): <b>{metrics['profit_factor']}</b>\n"
    msg += f"• Thời gian nắm giữ trung bình: <b>{avg_hold:.1f} phiên (T+)</b>\n\n"

    msg += f"🏆 <b>GIAO DỊCH NỔI BẬT:</b>\n"
    msg += f"• Thắng tốt nhất: <b>{best_trade['symbol']} ({best_trade['net_pnl_pct']*100:+.2f}%)</b>\n"
    msg += f"• Kiểm soát rủi ro: <b>{worst_trade['symbol']} ({worst_trade['net_pnl_pct']*100:+.2f}%)</b>\n\n"

    msg += f"📋 <b>CHI TIẾT DANH MỤC THỰC HIỆN:</b>\n"
    for i, t in enumerate(month_trades.to_dict('records'), 1):
        ret = t['net_pnl_pct'] * 100
        icon = "✅" if ret > 0 else "❌"
        sign = "+" if ret > 0 else ""
        msg += f"{i}. {icon} <b>{t['symbol']}</b>: {sign}{ret:.2f}%\n"
        msg += f"   • Vào: <code>{t['entry_price']:.2f}</code> ({t['entry_date'].strftime('%d/%m')}) ➜ Ra: <code>{t['exit_price']:.2f}</code> ({t['exit_date'].strftime('%d/%m')})\n"
        msg += f"   • Thời gian giữ: {t['days_held']} phiên | Lý do: {t['exit_reason']}\n"

    msg += "\n💡 <b>ĐỊNH HƯỚNG THÁNG TỚI:</b>\n"
    msg += "• Tiếp tục tuân thủ kỷ luật quản trị vốn (tối đa 20-25% NAV/mã).\n"
    msg += "• Kiên nhẫn chờ đợi tín hiệu cạn cung và rút chân trục giữa SMA20.\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "<i>Báo cáo được tổng hợp tự động bởi VN100 Trading Bot.</i>"

    print(msg.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", ""))

    if send_telegram:
        send_telegram_alert(msg)

    # Lưu bản báo cáo ra file text để lưu trữ
    out_file = os.path.join(DATA_DIR, f"report_{target_month}.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(msg)
    print(f"\n[✓] Đã lưu bản sao báo cáo tại: {out_file}")

    return msg

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tạo báo cáo hiệu suất giao dịch theo tháng")
    parser.add_argument("--month", type=str, default=None, help="Định dạng YYYY-MM (mặc định: tháng trước)")
    parser.add_argument("--no-telegram", action="store_true", help="Không gửi qua Telegram")
    args = parser.parse_args()

    generate_monthly_report(target_month=args.month, send_telegram=not args.no_telegram)
