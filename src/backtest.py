import pandas as pd
import numpy as np

def simulate_trades(
    df: pd.DataFrame,
    symbol: str = "TICKER",
    take_profit_pct: float = 0.08,     # +8% chốt lời (nếu không dùng ATR)
    stop_loss_pct: float = 0.05,       # -5% cắt lỗ (nếu không dùng ATR)
    use_dynamic_atr: bool = True,      # Bật chốt lời/cắt lỗ động theo độ biến động ATR
    tp_atr_mult: float = 2.5,          # TP = Entry + 2.5 * ATR
    sl_atr_mult: float = 1.5,          # SL = Entry - 1.5 * ATR
    min_hold_days: int = 3,            # T+3 mới được bán (quy định VN)
    max_hold_days: int = 12,           # Tối đa 12-15 phiên (~2-3 tuần)
    fee_roundtrip_pct: float = 0.004,  # Phí 0.15% mua + 0.15% bán + 0.1% thuế = 0.4%
    entry_at: str = "next_open"        # 'next_open' hoặc 'signal_close'
):
    """
    Mô phỏng giao dịch theo luật T+ thị trường Việt Nam kết hợp ngưỡng ATR động.
    """
    trades = []
    n = len(df)
    if n < 20:
        return trades

    in_position = False
    entry_idx = -1
    entry_price = 0.0
    entry_date = None
    setup_name = ""
    tp_target = 0.0
    sl_target = 0.0

    for i in range(n - 1):
        # 1. Kiểm tra vào lệnh
        if not in_position and df.iloc[i]['signal'] == 1:
            if entry_at == "next_open":
                buy_idx = i + 1
                buy_price = df.iloc[buy_idx]['open']
                buy_date = df.iloc[buy_idx]['time']
                prev_close = df.iloc[i]['close']
                
                # Bỏ qua nếu trần cứng đầu phiên (tăng >= 6.8% so với giá đóng cửa hôm trước)
                if buy_price >= prev_close * 1.068:
                    continue
            else:
                buy_idx = i
                buy_price = df.iloc[buy_idx]['close']
                buy_date = df.iloc[buy_idx]['time']

            in_position = True
            entry_idx = buy_idx
            entry_price = buy_price
            entry_date = buy_date
            setup_name = df.iloc[i]['setup_name']

            # Tính toán ngưỡng TP và SL động theo ATR của phiên vào lệnh
            if use_dynamic_atr and 'atr' in df.columns and pd.notnull(df.iloc[buy_idx]['atr']):
                atr_val = float(df.iloc[buy_idx]['atr'])
                tp_target = entry_price + tp_atr_mult * atr_val
                # Cắt lỗ theo ATR nhưng khống chế mức lỗ tối đa không vượt quá -5.5% để bảo vệ vốn
                sl_target = max(entry_price - sl_atr_mult * atr_val, entry_price * 0.945)
            else:
                tp_target = entry_price * (1.0 + take_profit_pct)
                sl_target = entry_price * (1.0 - stop_loss_pct)

            continue

        # 2. Kiểm tra thoát lệnh nếu đang giữ hàng
        if in_position:
            days_held = i - entry_idx
            curr_low = df.iloc[i]['low']
            curr_high = df.iloc[i]['high']
            curr_close = df.iloc[i]['close']
            curr_date = df.iloc[i]['time']
            prev_close = df.iloc[i-1]['close'] if i > 0 else curr_close

            # Ràng buộc luật T+: Không thể bán trước min_hold_days (T+3)
            if days_held < min_hold_days:
                continue

            exit_price = None
            exit_reason = ""

            if curr_high >= tp_target:
                # Chốt lời thành công tại giá mục tiêu TP
                exit_price = tp_target
                exit_reason = "Take Profit"
            elif curr_low <= sl_target:
                # Cắt lỗ tại mức SL (kiểm tra nếu bị sàn cứng không thoát được giá tốt)
                floor_price = prev_close * 0.932
                exit_price = max(sl_target, floor_price)
                exit_reason = "Stop Loss"
            elif days_held >= max_hold_days:
                # Hết thời gian lướt sóng T+ tối đa (2-3 tuần)
                exit_price = curr_close
                exit_reason = "Time Exit"

            if exit_price is not None:
                gross_pnl_pct = (exit_price - entry_price) / entry_price
                net_pnl_pct = gross_pnl_pct - fee_roundtrip_pct
                is_win = net_pnl_pct > 0

                trades.append({
                    'symbol': symbol,
                    'setup': setup_name,
                    'entry_date': entry_date,
                    'entry_price': entry_price,
                    'tp_target': tp_target,
                    'sl_target': sl_target,
                    'exit_date': curr_date,
                    'exit_price': exit_price,
                    'days_held': days_held,
                    'exit_reason': exit_reason,
                    'gross_pnl_pct': gross_pnl_pct,
                    'net_pnl_pct': net_pnl_pct,
                    'is_win': is_win
                })

                in_position = False
                entry_idx = -1
                entry_price = 0.0

    return trades

def calculate_performance_metrics(trades_list):
    """
    Tính toán các chỉ số thống kê hiệu suất: Winrate, Profit Factor, Avg Return, v.v.
    """
    if not trades_list:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_return_pct': 0.0,
            'avg_win_pct': 0.0,
            'avg_loss_pct': 0.0,
            'win_count': 0,
            'loss_count': 0
        }

    df_trades = pd.DataFrame(trades_list)
    total_trades = len(df_trades)
    wins = df_trades[df_trades['is_win'] == True]
    losses = df_trades[df_trades['is_win'] == False]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100.0 if total_trades > 0 else 0.0

    total_gross_win = wins['net_pnl_pct'].sum() if win_count > 0 else 0.0
    total_gross_loss = abs(losses['net_pnl_pct'].sum()) if loss_count > 0 else 0.0
    profit_factor = (total_gross_win / total_gross_loss) if total_gross_loss > 0 else (99.0 if total_gross_win > 0 else 0.0)

    avg_return_pct = df_trades['net_pnl_pct'].mean() * 100.0
    avg_win_pct = wins['net_pnl_pct'].mean() * 100.0 if win_count > 0 else 0.0
    avg_loss_pct = losses['net_pnl_pct'].mean() * 100.0 if loss_count > 0 else 0.0

    return {
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'avg_return_pct': round(avg_return_pct, 2),
        'avg_win_pct': round(avg_win_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        'win_count': win_count,
        'loss_count': loss_count
    }

def run_full_backtest(mode="leader_alpha", use_dynamic_atr=True, tp_atr_mult=2.5, sl_atr_mult=1.5):
    """
    Chạy backtest trên toàn bộ tập dữ liệu 8 năm (2018 - 2026) của rổ VN100
    """
    import os
    import glob
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from indicators import compute_indicators, add_relative_strength
    from strategy import generate_signals

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    files = [f for f in files if "optimization" not in f and "VNINDEX" not in f]

    all_trades = []
    for f in files:
        sym = os.path.basename(f).replace(".csv", "")
        try:
            df = pd.read_csv(f)
            if len(df) < 60:
                continue
            df['time'] = pd.to_datetime(df['time'])
            df = compute_indicators(df)
            df = add_relative_strength(df)
            df = generate_signals(df, mode=mode)
            trades = simulate_trades(
                df,
                symbol=sym,
                use_dynamic_atr=use_dynamic_atr,
                tp_atr_mult=tp_atr_mult,
                sl_atr_mult=sl_atr_mult,
                take_profit_pct=0.06,
                stop_loss_pct=0.04,
                min_hold_days=3,
                max_hold_days=10
            )
            all_trades.extend(trades)
        except Exception as e:
            continue

    metrics = calculate_performance_metrics(all_trades)
    return metrics, all_trades

if __name__ == "__main__":
    print("Running 8-year backtest on VN100 universe...")
    metrics, trades = run_full_backtest(mode="leader_alpha", use_dynamic_atr=True)
    print("LEADER ALPHA + DYNAMIC ATR RESULTS:")
    print(metrics)
