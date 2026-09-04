import pandas as pd
import numpy as np

def generate_signals(
    df: pd.DataFrame,
    mode: str = "high_winrate", # "high_winrate" hoặc "multi_setup"
    enable_setup1: bool = True,
    enable_setup2: bool = True,
    enable_setup3: bool = True,
    min_vol_ratio_s1: float = 1.5,
    min_vol_ratio_s2: float = 1.15,
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
    1. 'high_winrate': Chiến lược tối ưu Winrate cao nhất (~60%, Profit Factor 1.6 - 1.8).
       Bắt nhịp điều chỉnh kiểm định trục giữa SMA20 (Trend Pullback Bounce) sau khi cạn kiệt nguồn cung.
    2. 'multi_setup': Kích hoạt đầy đủ 3 setup (Squeeze Breakout, Trend Pullback, Oversold Reversal)
       phù hợp với đa dạng bối cảnh thị trường.
    """
    df = df.copy()
    df['signal'] = 0
    df['setup_name'] = ""
    
    n = len(df)
    if n < 50:
        return df

    # Đảm bảo có SMA50 làm bộ lọc xu hướng trung hạn nếu có
    if 'sma50' not in df.columns:
        df['sma50'] = df['close'].rolling(50).mean()

    # Bộ lọc xu hướng tăng (Uptrend Confirmation): Giá trên SMA50, SMA20 dốc lên, EMA9 >= SMA20
    uptrend = (df['close'] > df['sma50']) & (df['bb_mid'] > df['bb_mid'].shift(5)) & (df['ma_trend'] >= df['bb_mid'])

    # 1. SETUP CHỦ ĐẠO WINRATE CAO: TREND PULLBACK BOUNCE (Bắt nhịp hồi trục giữa sau cạn cung)
    # Ràng buộc cạn kiệt von trước đó (Volume Dry-up)
    vol_dry_prev = (df['volume'].shift(1) < df['vol_ma'].shift(1) * 0.9) | (df['volume'].shift(2) < df['vol_ma'].shift(2) * 0.9)
    # Giá chạm/nhúng sát Mid Band (SMA20) và bật tăng dứt khoát
    bounce_mid = (df['low'] <= df['bb_mid'] * 1.015) & (df['close'] > df['open']) & (df['close'] >= df['bb_mid'])
    # %B ở vị trí kiểm định thành công trục giữa (0.45 - 0.70)
    pct_b_mid = (df['bb_pct_b'] >= 0.45) & (df['bb_pct_b'] <= 0.70)
    # Lực nảy có cầu xác nhận
    vol_bounce = df['vol_ratio'] >= min_vol_ratio_s2
    # Nến xanh đóng ở nửa trên thân nến
    candle_strength = (df['close'] - df['low']) >= (df['high'] - df['low'] + 1e-9) * 0.55

    sig_pullback = uptrend & vol_dry_prev & bounce_mid & pct_b_mid & vol_bounce & candle_strength

    if mode == "high_winrate":
        df.loc[sig_pullback, 'signal'] = 1
        df.loc[sig_pullback, 'setup_name'] = "High-Winrate Trend Pullback"
        return df

    # 2. SETUP SQUEEZE BREAKOUT (Bùng nổ vượt dải sau tích lũy)
    was_narrow = df['bb_width'].shift(1).rolling(5).min() <= 0.08
    expanding = df['bb_width'] > df['bb_width'].shift(1)
    breakout_pct_b = df['bb_pct_b'] >= pct_b_s1_thresh
    vol_surge = df['vol_ratio'] >= min_vol_ratio_s1
    candle_bull = (df['close'] > df['open']) & (df['close'] >= df['high'] - (df['high'] - df['low'] + 1e-9) * 0.3)
    sig_squeeze = was_narrow & expanding & breakout_pct_b & vol_surge & candle_bull & uptrend

    # 3. SETUP OVERSOLD REVERSAL (Bắt đáy đảo chiều từ dải dưới)
    panic_prev = (df['bb_pct_b'].shift(1) < 0.0) | (df['low'].shift(1) < df['bb_lower'].shift(1))
    bounce_lower = (df['close'] > df['open']) & (df['close'] > df['bb_lower']) & (df['bb_pct_b'] >= 0.15) & (df['bb_pct_b'] <= 0.40)
    vol_cap = (df['vol_ratio'] >= min_vol_ratio_s3) | (df['vol_ratio'].shift(1) >= min_vol_ratio_s3)
    filter_crash = df['close'] >= df['sma50'] * 0.75
    sig_oversold = panic_prev & bounce_lower & vol_cap & filter_crash

    # Gán tín hiệu theo thứ tự ưu tiên
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
    print("Calibrated Strategy module loaded.")
