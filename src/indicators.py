import pandas as pd
import numpy as np

def compute_indicators(
    df: pd.DataFrame,
    bb_period: int = 20,
    bb_std_mult: float = 2.0,
    vol_period: int = 20,
    ma_trend_period: int = 9,
    bandwidth_window: int = 60
) -> pd.DataFrame:
    """
    Tính toán 5 công cụ chỉ báo kỹ thuật:
    1. Bollinger Bands (Upper, Mid, Lower)
    2. Bollinger Bands %B
    3. Bollinger Bands Width
    4. Volume & Volume MA
    5. MA xu hướng ngắn ngày (EMA9 / SMA)
    """
    df = df.copy()
    
    # 1. Bollinger Bands
    df['bb_mid'] = df['close'].rolling(window=bb_period).mean()
    df['bb_std'] = df['close'].rolling(window=bb_period).std(ddof=0)
    df['bb_upper'] = df['bb_mid'] + bb_std_mult * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - bb_std_mult * df['bb_std']
    
    # 2. Bollinger Bands %B
    band_range = df['bb_upper'] - df['bb_lower']
    df['bb_pct_b'] = np.where(band_range > 0, (df['close'] - df['bb_lower']) / band_range, 0.5)
    
    # 3. Bollinger Bands Width
    df['bb_width'] = np.where(df['bb_mid'] > 0, band_range / df['bb_mid'], 0.0)
    # Độ nén tương đối so với quá khứ (Rolling percentile hoặc rolling min)
    df['bb_width_min'] = df['bb_width'].rolling(window=bandwidth_window).min()
    df['is_squeeze'] = df['bb_width'] <= (df['bb_width_min'] * 1.25)
    
    # 4. Volume & Volume MA
    df['vol_ma'] = df['volume'].rolling(window=vol_period).mean()
    df['vol_ratio'] = np.where(df['vol_ma'] > 0, df['volume'] / df['vol_ma'], 1.0)
    
    # 5. MA Xu hướng ngắn ngày (EMA trend)
    df['ma_trend'] = df['close'].ewm(span=ma_trend_period, adjust=False).mean()
    df['ma_trend_slope'] = df['ma_trend'] - df['ma_trend'].shift(2)
    
    # Nến xanh / đỏ
    df['is_bullish_candle'] = df['close'] >= df['open']
    
    return df

if __name__ == "__main__":
    # Test nhanh
    sample_data = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=50),
        'open': np.random.uniform(50, 60, 50),
        'high': np.random.uniform(60, 65, 50),
        'low': np.random.uniform(45, 50, 50),
        'close': np.random.uniform(50, 60, 50),
        'volume': np.random.uniform(100000, 500000, 50)
    })
    res = compute_indicators(sample_data)
    print("Columns:", [c for c in res.columns if 'bb' in c or 'vol' in c or 'ma' in c])
    print(res[['close', 'bb_upper', 'bb_mid', 'bb_lower', 'bb_pct_b', 'bb_width', 'vol_ratio', 'ma_trend']].tail(3))
