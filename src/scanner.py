import os
import sys
import glob
import argparse
import pandas as pd
from datetime import datetime

# Đảm bảo import được các module trong src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from indicators import compute_indicators, add_relative_strength
from strategy import generate_signals
from notifier import send_telegram_alert, send_telegram_photo, format_signal_message
from chart_generator import generate_signal_chart
from market_regime import get_market_regime
from position_tracker import add_new_position, update_and_alert_positions, load_positions
from sector_data import get_sector, check_sector_limit
from vnstock.api.quote import Quote

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def scan_market(
    mode: str = "high_winrate",
    update_latest: bool = True,
    lookback_days: int = 1,
    tp_pct: float = 0.06,
    sl_pct: float = 0.04,
    max_hold_days: int = 8
):
    """
    Quét toàn bộ danh mục VN100, kiểm tra bộ lọc VN-Index, theo dõi vị thế mở và gửi ảnh chart.
    """
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n=================================================================")
    print(f"🚀 [VN100 SCANNER] BẮT ĐẦU QUÉT THỊ TRƯỜNG ({now_str})")
    print(f"=================================================================")

    # 1. KIỂM TRA TRẠNG THÁI THỊ TRƯỜNG CHUNG VN-INDEX
    regime = get_market_regime(update=update_latest)
    print(f"📊 [VN-INDEX REGIME] Trạng thái: {regime['color']} {regime['label']} (Điểm số: {regime['close']:.2f})")
    print(f"   Khuyến nghị: {regime['action']}\n")

    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    files = [f for f in files if "optimization" not in f and "VNINDEX" not in f]

    if not files:
        print("[-] Chưa có dữ liệu cổ phiếu trong thư mục data/. Vui lòng chạy data_loader.py trước.")
        return []

    signals_found = []
    latest_quotes = {}

    for f in sorted(files):
        sym = os.path.basename(f).replace(".csv", "")
        try:
            df = pd.read_csv(f)
            if len(df) < 35:
                continue
            df['time'] = pd.to_datetime(df['time'])

            # Cập nhật thêm nến mới nhất từ vnstock
            if update_latest:
                try:
                    q = Quote(symbol=sym, source='VCI')
                    latest_quote = q.history(start=(datetime.now() - pd.Timedelta(days=5)).strftime("%Y-%m-%d"))
                    if latest_quote is not None and not latest_quote.empty:
                        latest_quote['time'] = pd.to_datetime(latest_quote['time'])
                        latest_quote.columns = [c.lower() for c in latest_quote.columns]
                        df = pd.concat([df, latest_quote]).drop_duplicates(subset=['time']).reset_index(drop=True)
                except Exception:
                    pass

            df_ind = compute_indicators(df)
            df_ind = add_relative_strength(df_ind)
            df_sig = generate_signals(df_ind, mode=mode)

            # Lưu lại giá mới nhất phục vụ theo dõi vị thế
            latest_row = df_sig.iloc[-1]
            latest_quotes[sym] = {
                'close': float(latest_row['close']),
                'date': latest_row['time'].strftime("%Y-%m-%d")
            }

            # Nếu VN-Index đang Downtrend phòng thủ, không mở vị thế mua mới
            if not regime['allow_buy']:
                continue

            # Quét tìm tín hiệu mua trong N phiên gần nhất
            check_rows = df_sig.tail(lookback_days)
            for idx, row in check_rows.iterrows():
                if row['signal'] == 1:
                    price = float(row['close'])
                    atr_v = float(row.get('atr', price * 0.025)) if pd.notnull(row.get('atr')) else price * 0.025
                    target_tp = round(price + 2.5 * atr_v, 2)
                    target_sl = round(max(price - 1.5 * atr_v, price * 0.945), 2)
                    rs_val = float(row.get('rs_score', 100.0))
                    cmf_val = float(row.get('cmf', 0.0))
                    sec_name = get_sector(sym)

                    sig_info = {
                        'symbol': sym,
                        'sector': sec_name,
                        'setup': row['setup_name'],
                        'date': row['time'].strftime("%Y-%m-%d"),
                        'price': price,
                        'pct_b': round(float(row['bb_pct_b']), 2),
                        'bandwidth': round(float(row['bb_width']), 3),
                        'vol_ratio': round(float(row['vol_ratio']), 2),
                        'rs_score': round(rs_val, 1),
                        'cmf': round(cmf_val, 2),
                        'tp_pct': round((target_tp / price - 1.0), 3),
                        'target_tp': target_tp,
                        'sl_pct': round((1.0 - target_sl / price), 3),
                        'target_sl': target_sl,
                        'max_hold_days': max_hold_days,
                        'df_context': df_sig
                    }
                    signals_found.append(sig_info)
        except Exception:
            continue

    # 2. KIỂM TRA VÀ CẢNH BÁO CÁC VỊ THẾ ĐANG MỞ (CHỐT LỜI / CẮT LỖ REALTIME)
    print("[*] Kiểm tra các vị thế đang mở trong danh mục...")
    update_and_alert_positions(latest_quotes)

    # 3. XỬ LÝ VÀ BẮN TÍN HIỆU MUA MỚI KÈM ẢNH BIỂU ĐỒ
    if signals_found:
        # Sắp xếp ưu tiên các mã Leader (RS cao nhất)
        signals_found = sorted(signals_found, key=lambda x: x['rs_score'], reverse=True)
        print(f"\n🎯 PHÁT HIỆN {len(signals_found)} TÍN HIỆU MUA MỚI (ƯU TIÊN RS LEADER):")
        df_disp = pd.DataFrame(signals_found)
        print(df_disp[['symbol', 'sector', 'date', 'setup', 'price', 'rs_score', 'cmf', 'target_tp', 'target_sl']].to_string(index=False))

        # Gửi tin nhắn tổng hợp qua Telegram
        msg = format_signal_message(signals_found)
        send_telegram_alert(msg)

        # Tự động vẽ chart và gửi ảnh biểu đồ cho từng mã
        for s in signals_found:
            # Ghi nhận mã vào danh mục theo dõi vị thế mở (kiểm soát trần ngành)
            success_add, msg_add = add_new_position(
                symbol=s['symbol'],
                entry_date=s['date'],
                entry_price=s['price'],
                tp_target=s['target_tp'],
                sl_target=s['target_sl'],
                setup_name=s['setup'],
                max_hold=max_hold_days
            )
            if not success_add:
                print(f"[i] Bỏ qua thêm tự động {s['symbol']}: {msg_add}")

            # Vẽ và gửi ảnh chart
            df_ctx = s.get('df_context')
            if df_ctx is not None:
                chart_path = generate_signal_chart(
                    df=df_ctx,
                    symbol=s['symbol'],
                    tp_target=s['target_tp'],
                    sl_target=s['target_sl']
                )
                if chart_path:
                    caption = (
                        f"📊 <b>Biểu đồ kỹ thuật: {s['symbol']}</b>\n"
                        f"• Setup: <code>{s['setup']}</code>\n"
                        f"• Điểm vào: <b>{s['price']:.2f}</b> | Chốt lời 50%: <b>{s['target_tp']:.2f}</b>\n"
                        f"• Dừng lỗ: <b>{s['target_sl']:.2f}</b> | Rủi ro: <b>-4.0%</b>"
                    )
                    send_telegram_photo(chart_path, caption=caption)
    else:
        if not regime['allow_buy']:
            print("[!] Thị trường VN-Index đang trong trạng thái Phòng thủ. Khóa phát sinh tín hiệu mua mới.")
        else:
            print("[i] Không có mã nào xuất hiện tín hiệu mua mới trong phiên.")

    print(f"\n[✓] Quá trình quét hoàn tất.")
    return signals_found

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VN100 Scanner Pro")
    parser.add_argument("--mode", type=str, default="high_winrate", choices=["high_winrate", "multi_setup"], help="Chế độ chiến lược")
    parser.add_argument("--lookback", type=int, default=1, help="Số phiên quét gần nhất")
    parser.add_argument("--no-update", action="store_true", help="Không tải lại giá mới nhất")
    args = parser.parse_args()

    scan_market(
        mode=args.mode,
        update_latest=not args.no_update,
        lookback_days=args.lookback
    )
