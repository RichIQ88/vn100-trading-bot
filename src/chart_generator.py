import os
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt

CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

def generate_signal_chart(df: pd.DataFrame, symbol: str, tp_target: float, sl_target: float, lookback: int = 60) -> str:
    """
    Tự động vẽ biểu đồ nến Nhật kèm dải Bollinger Bands, Volume, EMA trend và mốc TP/SL
    """
    df_plot = df.tail(lookback).copy()
    if len(df_plot) < 20:
        return None

    # Chuẩn bị DataFrame cho mplfinance (Index là DatetimeIndex và tên cột viết hoa)
    df_plot['time'] = pd.to_datetime(df_plot['time'])
    df_plot.set_index('time', inplace=True)
    
    mpf_data = pd.DataFrame({
        'Open': df_plot['open'],
        'High': df_plot['high'],
        'Low': df_plot['low'],
        'Close': df_plot['close'],
        'Volume': df_plot['volume']
    })

    # Tạo các dải chỉ báo bổ trợ
    addplots = []
    if 'bb_upper' in df_plot.columns:
        addplots.append(mpf.make_addplot(df_plot['bb_upper'], color='#E74C3C', linestyle='--', width=1.0))
    if 'bb_mid' in df_plot.columns:
        addplots.append(mpf.make_addplot(df_plot['bb_mid'], color='#2980B9', linestyle='-', width=1.2))
    if 'bb_lower' in df_plot.columns:
        addplots.append(mpf.make_addplot(df_plot['bb_lower'], color='#27AE60', linestyle='--', width=1.0))
    if 'ma_trend' in df_plot.columns:
        addplots.append(mpf.make_addplot(df_plot['ma_trend'], color='#F39C12', linestyle=':', width=1.2))

    # Mũi tên Buy ở nến cuối cùng
    signal_scatter = [np.nan] * len(df_plot)
    signal_scatter[-1] = df_plot['low'].iloc[-1] * 0.985
    addplots.append(mpf.make_addplot(signal_scatter, type='scatter', markersize=120, marker='^', color='#2ECC71'))

    # Thiết lập màu sắc và giao diện
    market_colors = mpf.make_marketcolors(
        up='#2ECC71',
        down='#E74C3C',
        edge='inherit',
        wick='inherit',
        volume='#34495E'
    )
    custom_style = mpf.make_mpf_style(
        marketcolors=market_colors,
        gridstyle=':',
        gridcolor='#E0E0E0',
        facecolor='#FAFAFA'
    )

    last_date = df_plot.index[-1].strftime('%Y-%m-%d')
    output_filename = f"{symbol}_{last_date}.png"
    output_path = os.path.join(CHARTS_DIR, output_filename)

    title = f"\n{symbol} - Tín Hiệu Mua Lướt Sóng T+ ({last_date})\nTP: {tp_target:.2f} | SL: {sl_target:.2f}"

    try:
        mpf.plot(
            mpf_data,
            type='candle',
            volume=True,
            addplot=addplots,
            style=custom_style,
            title=title,
            hlines=dict(hlines=[tp_target, sl_target], colors=['#27AE60', '#C0392B'], linestyle='-.', linewidths=1.5),
            savefig=dict(fname=output_path, dpi=150, bbox_inches='tight'),
            figsize=(10, 6)
        )
        plt.close('all')
        print(f"[✓] Đã vẽ biểu đồ kỹ thuật tại: {output_path}")
        return output_path
    except Exception as e:
        print(f"[-] Lỗi khi vẽ biểu đồ {symbol}: {e}")
        plt.close('all')
        return None

if __name__ == "__main__":
    # Test vẽ chart mẫu
    import numpy as np
    dates = pd.date_range('2024-01-01', periods=60)
    test_df = pd.DataFrame({
        'time': dates,
        'open': np.linspace(20, 25, 60) + np.random.randn(60)*0.5,
        'high': np.linspace(21, 26, 60) + np.random.randn(60)*0.5,
        'low': np.linspace(19, 24, 60) - np.random.randn(60)*0.5,
        'close': np.linspace(20, 25, 60) + np.random.randn(60)*0.4,
        'volume': np.random.randint(500000, 2000000, 60)
    })
    test_df['bb_mid'] = test_df['close'].rolling(20).mean()
    test_df['bb_upper'] = test_df['bb_mid'] + 2 * test_df['close'].rolling(20).std()
    test_df['bb_lower'] = test_df['bb_mid'] - 2 * test_df['close'].rolling(20).std()
    test_df['ma_trend'] = test_df['close'].ewm(span=9).mean()
    chart = generate_signal_chart(test_df, "TEST", tp_target=26.5, sl_target=23.8)
    print("Generated test chart:", chart)
