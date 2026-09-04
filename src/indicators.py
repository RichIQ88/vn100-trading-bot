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
    
    # 5. MA Xu hướng ngắn ngày (EMA trend) & Trung hạn SMA50
    df['ma_trend'] = df['close'].ewm(span=ma_trend_period, adjust=False).mean()
    df['ma_trend_slope'] = df['ma_trend'] - df['ma_trend'].shift(2)
    df['sma50'] = df['close'].rolling(window=50).mean()
    
    # 6. Average True Range (ATR 14)
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    df['atr_pct'] = np.where(df['close'] > 0, df['atr'] / df['close'], 0.03)
    
    # 7. Chaikin Money Flow (CMF 20 - Đo dòng tiền lớn Smart Money)
    cl_diff = (df['close'] - df['low']) - (df['high'] - df['close'])
    hl_diff = df['high'] - df['low']
    mfm = np.where(hl_diff > 1e-9, cl_diff / hl_diff, 0.0)
    mfv = mfm * df['volume']
    sum_mfv = pd.Series(mfv, index=df.index).rolling(window=20).sum()
    sum_vol = df['volume'].rolling(window=20).sum()
    df['cmf'] = np.where(sum_vol > 0, sum_mfv / sum_vol, 0.0)
    
    # 8. Tỷ suất lợi nhuận 20 phiên (ROC20) phục vụ chấm điểm RS
    df['roc20'] = (df['close'] / df['close'].shift(20)) - 1.0
    
    # Nến xanh / đỏ
    df['is_bullish_candle'] = df['close'] >= df['open']
    
    return df

_VNI_CACHE = None

def get_vnindex_data():
    """Tải và cache dữ liệu VN-Index để tính RS Score"""
    global _VNI_CACHE
    if _VNI_CACHE is not None:
        return _VNI_CACHE
    import os
    vni_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "VNINDEX.csv")
    if os.path.exists(vni_path):
        try:
            vni = pd.read_csv(vni_path)
            vni['time'] = pd.to_datetime(vni['time'])
            vni = vni.sort_values('time').reset_index(drop=True)
            vni['vni_roc20'] = (vni['close'] / vni['close'].shift(20)) - 1.0
            _VNI_CACHE = vni[['time', 'close', 'vni_roc20']].rename(columns={'close': 'vni_close'})
            return _VNI_CACHE
        except Exception:
            return None
    return None

def add_relative_strength(df: pd.DataFrame) -> pd.DataFrame:
    """
    Gắn chỉ số Sức mạnh Tương quan RS so với VN-Index trong 20 phiên (1 tháng):
    RS Score = ((1 + Cổ phiếu ROC20) / (1 + VNINDEX ROC20)) * 100
    - RS > 100: Cổ phiếu khoẻ hơn thị trường chung (Nhóm Leader)
    - RS < 100: Cổ phiếu yếu hơn thị trường (Nhóm Laggard)
    """
    df = df.copy()
    vni = get_vnindex_data()
    if vni is None or 'time' not in df.columns:
        df['rs_score'] = 100.0
        df['is_leader'] = True
        return df

    df['time'] = pd.to_datetime(df['time'])
    merged = pd.merge_asof(df.sort_values('time'), vni.sort_values('time'), on='time', direction='backward')
    
    # Tính RS Score
    stock_roc = merged['roc20'].fillna(0.0)
    vni_roc = merged['vni_roc20'].fillna(0.0)
    merged['rs_score'] = np.where(1.0 + vni_roc != 0, ((1.0 + stock_roc) / (1.0 + vni_roc)) * 100.0, 100.0)
    # Leader nếu RS >= 102 (khoẻ hơn VN-Index ít nhất 2% trong 20 phiên)
    merged['is_leader'] = merged['rs_score'] >= 102.0
    
    return merged

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
