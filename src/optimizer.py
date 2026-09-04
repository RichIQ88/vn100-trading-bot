import os
import glob
import pandas as pd
import numpy as np
from indicators import compute_indicators
from strategy import generate_signals
from backtest import simulate_trades, calculate_performance_metrics

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def load_cached_data():
    """Tải toàn bộ các file dữ liệu đã lưu trong thư mục data"""
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    datasets = {}
    for f in files:
        sym = os.path.basename(f).replace(".csv", "")
        try:
            df = pd.read_csv(f)
            if len(df) >= 100:
                df['time'] = pd.to_datetime(df['time'])
                datasets[sym] = df
        except Exception:
            continue
    return datasets

def run_grid_search():
    """
    Quét lưới các bộ tham số để tìm ra cấu hình có Winrate cao nhất và tăng trưởng ổn định.
    """
    datasets = load_cached_data()
    print(f"[*] Đang tải {len(datasets)} mã cổ phiếu cho quá trình tối ưu hóa...")
    if not datasets:
        print("[-] Không có dữ liệu để backtest!")
        return

    # Định nghĩa không gian tìm kiếm tham số
    # Tối ưu cho lướt sóng T+ (vài ngày đến 2-3 tuần), ưu tiên Winrate cao
    grid = [
        # (TP_pct, SL_pct, Max_hold, Min_vol_s1, Min_vol_s2, Min_vol_s3, Pct_b_s1, S1_on, S2_on, S3_on, Description)
        (0.06, 0.04, 8, 1.3, 1.1, 1.2, 0.85, True, True, True, "Chuẩn 3 Setup - TP +6%, SL -4%, Hold 8d"),
        (0.06, 0.04, 10, 1.4, 1.2, 1.3, 0.90, True, True, True, "Khắt khe Vol - TP +6%, SL -4%, Hold 10d"),
        (0.07, 0.04, 10, 1.4, 1.2, 1.3, 0.88, True, True, True, "TP +7%, SL -4%, Hold 10d"),
        (0.08, 0.05, 12, 1.3, 1.1, 1.2, 0.85, True, True, True, "TP +8%, SL -5%, Hold 12d"),
        (0.05, 0.035, 7, 1.3, 1.1, 1.2, 0.85, True, True, True, "Scalping T+ cực nhanh - TP +5%, SL -3.5%, Hold 7d"),
        (0.06, 0.04, 10, 1.3, 1.1, 1.2, 0.85, False, True, False, "Chỉ riêng Trend Pullback - TP +6%, SL -4%"),
        (0.07, 0.04, 10, 1.4, 1.1, 1.2, 0.88, False, True, False, "Chỉ riêng Trend Pullback - TP +7%, SL -4%"),
        (0.06, 0.04, 8, 1.4, 1.1, 1.3, 0.90, True, False, False, "Chỉ riêng Squeeze Breakout - TP +6%, SL -4%"),
        (0.06, 0.04, 8, 1.2, 1.1, 1.2, 0.85, False, False, True, "Chỉ riêng Oversold Reversal - TP +6%, SL -4%"),
        (0.07, 0.045, 10, 1.5, 1.2, 1.2, 0.90, True, True, False, "Kết hợp Squeeze + Trend Pullback (Bỏ bắt đáy)"),
        (0.06, 0.04, 8, 1.4, 1.2, 1.2, 0.88, True, True, False, "Squeeze + Trend Pullback (TP +6%, SL -4%)"),
        (0.08, 0.04, 12, 1.5, 1.2, 1.2, 0.90, True, True, False, "Squeeze + Trend Pullback (TP +8%, SL -4%, Hold 12d)")
    ]

    results = []

    # Tiền xử lý chỉ báo cho tất cả mã
    processed_dfs = {}
    for sym, df in datasets.items():
        processed_dfs[sym] = compute_indicators(df)

    print(f"[*] Bắt đầu kiểm thử {len(grid)} tổ hợp tham số trên dữ liệu lịch sử 8 năm...")

    for idx, (tp, sl, max_h, v_s1, v_s2, v_s3, pb_s1, s1_on, s2_on, s3_on, desc) in enumerate(grid, 1):
        all_trades = []
        for sym, df_ind in processed_dfs.items():
            df_sig = generate_signals(
                df_ind,
                enable_setup1=s1_on,
                enable_setup2=s2_on,
                enable_setup3=s3_on,
                min_vol_ratio_s1=v_s1,
                min_vol_ratio_s2=v_s2,
                min_vol_ratio_s3=v_s3,
                pct_b_s1_thresh=pb_s1
            )
            trades = simulate_trades(
                df_sig,
                symbol=sym,
                take_profit_pct=tp,
                stop_loss_pct=sl,
                min_hold_days=3,
                max_hold_days=max_h,
                fee_roundtrip_pct=0.004,
                entry_at="next_open"
            )
            all_trades.extend(trades)

        metrics = calculate_performance_metrics(all_trades)
        results.append({
            'Config_ID': idx,
            'Description': desc,
            'TP_Pct': f"+{tp*100:.1f}%",
            'SL_Pct': f"-{sl*100:.1f}%",
            'Max_Hold': max_h,
            'Trades': metrics['total_trades'],
            'WinRate': metrics['win_rate'],
            'Profit_Factor': metrics['profit_factor'],
            'Avg_Return': metrics['avg_return_pct'],
            'Wins': metrics['win_count'],
            'Losses': metrics['loss_count']
        })

    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values(by=['WinRate', 'Profit_Factor'], ascending=[False, False]).reset_index(drop=True)

    print("\n========================= BẢNG KẾT QUẢ BACKTEST TỐI ƯU HÓA =========================")
    print(df_res.to_string(index=False))
    print("===================================================================================\n")

    # Lưu kết quả tối ưu vào file csv
    out_path = os.path.join(DATA_DIR, "optimization_results.csv")
    df_res.to_csv(out_path, index=False)
    print(f"[✓] Đã lưu kết quả phân tích vào: {out_path}")
    return df_res

if __name__ == "__main__":
    run_grid_search()
