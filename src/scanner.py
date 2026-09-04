import os
import sys
import glob
import argparse
import pandas as pd
from datetime import datetime

# Đảm bảo import được các module trong src/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from indicators import compute_indicators
from strategy import generate_signals
from notifier import send_telegram_alert, format_signal_message
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
    Quét toàn bộ danh mục VN100 để tìm các cổ phiếu xuất hiện tín hiệu mua.
    """
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n=================================================================")
    print(f"🚀 [VN100 SCANNER] BẮT ĐẦU QUÉT TÍN HIỆU THỊ TRƯỜNG ({now_str})")
    print(f"   Chế độ quét: {mode.upper()} | Lookback: {lookback_days} phiên gần nhất")
    print(f"=================================================================\n")

    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    files = [f for f in files if "optimization" not in f]

    if not files:
        print("[-] Chưa có dữ liệu cổ phiếu trong thư mục data/. Vui lòng chạy data_loader.py trước.")
        return []

    signals_found = []

    for f in sorted(files):
        sym = os.path.basename(f).replace(".csv", "")
        try:
            df = pd.read_csv(f)
            if len(df) < 35:
                continue
            df['time'] = pd.to_datetime(df['time'])

            # Cập nhật thêm nến mới nhất nếu cần
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
            df_sig = generate_signals(df_ind, mode=mode)

            # Quét trong N phiên gần nhất
            check_rows = df_sig.tail(lookback_days)
            for idx, row in check_rows.iterrows():
                if row['signal'] == 1:
                    price = float(row['close'])
                    target_tp = round(price * (1.0 + tp_pct), 2)
                    target_sl = round(price * (1.0 - sl_pct), 2)

                    sig_info = {
                        'symbol': sym,
                        'setup': row['setup_name'],
                        'date': row['time'].strftime("%Y-%m-%d"),
                        'price': price,
                        'pct_b': round(float(row['bb_pct_b']), 2),
                        'bandwidth': round(float(row['bb_width']), 3),
                        'vol_ratio': round(float(row['vol_ratio']), 2),
                        'tp_pct': tp_pct,
                        'target_tp': target_tp,
                        'sl_pct': sl_pct,
                        'target_sl': target_sl,
                        'max_hold_days': max_hold_days
                    }
                    signals_found.append(sig_info)
        except Exception:
            continue

    # Xuất kết quả
    if signals_found:
        print(f"🎯 PHÁT HIỆN {len(signals_found)} TÍN HIỆU MUA THỎA MÃN:")
        df_disp = pd.DataFrame(signals_found)
        print(df_disp[['symbol', 'date', 'setup', 'price', 'pct_b', 'vol_ratio', 'target_tp', 'target_sl']].to_string(index=False))

        # Gửi thông báo Telegram
        msg = format_signal_message(signals_found)
        send_telegram_alert(msg)
    else:
        print("[i] Không có mã nào xuất hiện tín hiệu mua mới trong phiên.")

    print(f"\n[✓] Quá trình quét hoàn tất.")
    return signals_found

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VN100 Bollinger Bands & Volume Scanner")
    parser.add_argument("--mode", type=str, default="high_winrate", choices=["high_winrate", "multi_setup"], help="Chế độ chiến lược")
    parser.add_argument("--lookback", type=int, default=1, help="Số phiên quét gần nhất (mặc định 1 = phiên hôm nay)")
    parser.add_argument("--no-update", action="store_true", help="Không tải lại giá mới nhất từ vnstock")
    args = parser.parse_args()

    scan_market(
        mode=args.mode,
        update_latest=not args.no_update,
        lookback_days=args.lookback
    )
