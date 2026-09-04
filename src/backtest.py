import pandas as pd
import numpy as np

def simulate_trades(
    df: pd.DataFrame,
    symbol: str = "TICKER",
    take_profit_pct: float = 0.08,     # +8% chốt lời
    stop_loss_pct: float = 0.05,       # -5% cắt lỗ
    min_hold_days: int = 3,            # T+3 mới được bán (quy định VN)
    max_hold_days: int = 12,           # Tối đa 12-15 phiên (~2-3 tuần)
    fee_roundtrip_pct: float = 0.004,  # Phí 0.15% mua + 0.15% bán + 0.1% thuế = 0.4%
    entry_at: str = "next_open"        # 'next_open' hoặc 'signal_close'
):
    """
    Mô phỏng giao dịch theo luật T+ thị trường Việt Nam
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

            # Kiểm tra Take Profit
            tp_target = entry_price * (1.0 + take_profit_pct)
            sl_target = entry_price * (1.0 - stop_loss_pct)

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

if __name__ == "__main__":
    print("Backtest engine loaded.")
