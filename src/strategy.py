import pandas as pd
import numpy as np

def generate_signals(
    df: pd.DataFrame,
    mode: str = "high_winrate", # "high_winrate" (3-4 lệnh/tháng), "ultra_quality" (1-2 lệnh/tháng), "multi_setup"
    enable_setup1: bool = True,
    enable_setup2: bool = True,
    enable_setup3: bool = True,
    min_vol_ratio_s1: float = 1.6,
    min_vol_ratio_s2: float = 1.05,
    min_vol_ratio_s3: float = 1.25,
    pct_b_s1_thresh: float = 0.85
) -> pd.DataFrame:
    """
    Hệ thống phát hiện tín hiệu giao dịch theo 5 chỉ báo:
    - Bollinger Bands (Upper, Mid, Lower)
    - Bollinger Bands %B
    - Bollinger Bands Width
    - Volume & Volume MA20
    - MA xu hướng ngắn ngày (EMA9 / SMA50)

    Modes:
    1. 'high_winrate': Cân bằng tối ưu tần suất 3-4 lệnh/tháng (~40-50 lệnh/năm), Winrate 54-70%, PF 1.45+.
    2. 'ultra_quality': Rất khắt khe, chỉ 1-2 lệnh/tháng, Winrate 60-77%, PF 1.65 - 1.76.
    3. 'multi_setup': Đa dạng 3 setup (Breakout, Pullback, Bắt đáy), tần suất 8-10 lệnh/tháng.
    """
    df = df.copy()
    df['signal'] = 0
    df['setup_name'] = ""
    
    n = len(df)
    if n < 50:
        return df

    if 'sma50' not in df.columns:
        df['sma50'] = df['close'].rolling(50).mean()

    # Bộ lọc xu hướng tăng: Giá trên SMA50, SMA20 dốc lên, EMA9 >= SMA20
    uptrend = (df['close'] > df['sma50']) & (df['bb_mid'] > df['bb_mid'].shift(5)) & (df['ma_trend'] >= df['bb_mid'])

    # --- SETUP PULLBACK BOUNCE ---
    if mode == "ultra_quality":
        # Khắt khe tuyệt đối: 1-2 lệnh/tháng
        vol_dry = (df['volume'].shift(1) < df['vol_ma'].shift(1) * 0.9) | (df['volume'].shift(2) < df['vol_ma'].shift(2) * 0.9)
        bounce_mid = (df['low'] <= df['bb_mid'] * 1.015) & (df['close'] > df['open']) & (df['close'] >= df['bb_mid'])
        pct_b_mid = (df['bb_pct_b'] >= 0.45) & (df['bb_pct_b'] <= 0.70)
        vol_bounce = df['vol_ratio'] >= 1.15
        candle_str = (df['close'] - df['low']) >= (df['high'] - df['low'] + 1e-9) * 0.55
    else:
        # Cân bằng tối ưu: 3-4 lệnh/tháng
        vol_dry = (df['volume'].shift(1) < df['vol_ma'].shift(1) * 1.05) | (df['volume'].shift(2) < df['vol_ma'].shift(2) * 1.05)
        bounce_mid = (df['low'] <= df['bb_mid'] * 1.02) & (df['close'] > df['open']) & (df['close'] >= df['bb_mid'] * 0.995)
        pct_b_mid = (df['bb_pct_b'] >= 0.45) & (df['bb_pct_b'] <= 0.72)
        vol_bounce = df['vol_ratio'] >= min_vol_ratio_s2
        candle_str = (df['close'] - df['low']) >= (df['high'] - df['low'] + 1e-9) * 0.45

    sig_pullback = uptrend & vol_dry & bounce_mid & pct_b_mid & vol_bounce & candle_str

    if mode in ["high_winrate", "ultra_quality"]:
        df.loc[sig_pullback, 'signal'] = 1
        df.loc[sig_pullback, 'setup_name'] = "High-Winrate Trend Pullback"
        return df

    # --- MULTI-SETUP MODE ---
    # Setup 1: Squeeze Breakout
    was_narrow = df['bb_width'].shift(1).rolling(6).min() <= 0.085
    expanding = df['bb_width'] > df['bb_width'].shift(1)
    breakout_pct_b = df['bb_pct_b'] >= pct_b_s1_thresh
    vol_surge = df['vol_ratio'] >= min_vol_ratio_s1
    candle_bull = (df['close'] > df['open']) & (df['close'] >= df['high'] - (df['high'] - df['low'] + 1e-9) * 0.3)
    sig_squeeze = was_narrow & expanding & breakout_pct_b & vol_surge & candle_bull & uptrend

    # Setup 3: Oversold Reversal
    panic_prev = (df['bb_pct_b'].shift(1) < 0.0) | (df['low'].shift(1) < df['bb_lower'].shift(1))
    bounce_lower = (df['close'] > df['open']) & (df['close'] > df['bb_lower']) & (df['bb_pct_b'] >= 0.15) & (df['bb_pct_b'] <= 0.40)
    vol_cap = (df['vol_ratio'] >= min_vol_ratio_s3) | (df['vol_ratio'].shift(1) >= min_vol_ratio_s3)
    filter_crash = df['close'] >= df['sma50'] * 0.75
    sig_oversold = panic_prev & bounce_lower & vol_cap & filter_crash

    if enable_setup2:
        df.loc[sig_pullback, 'signal'] = 1
        df.loc[sig_pullback, 'setup_name'] = "Trend Pullback"

    if enable_setup1:
        mask1 = sig_squeeze & (df['signal'] == 0)
        df.loc[mask1, 'signal'] = 1
        df.loc[mask1, 'setup_name'] = "Squeeze Breakout"

    if enable_setup3:
        mask3 = sig_oversold & (df['signal'] == 0)
        df.loc[mask3, 'signal'] = 1
        df.loc[mask3, 'setup_name'] = "Oversold Reversal"

    return df

if __name__ == "__main__":
    print("Strategy updated with balanced 3-4 trades/month mode.")
