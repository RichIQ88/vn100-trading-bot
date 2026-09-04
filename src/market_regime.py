import os
import pandas as pd
from datetime import datetime, timedelta
from vnstock.api.quote import Quote

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
VNINDEX_PATH = os.path.join(DATA_DIR, "VNINDEX.csv")

def update_vnindex_data():
    """Tải hoặc cập nhật dữ liệu lịch sử của VN-Index"""
    try:
        q = Quote(symbol='VNINDEX', source='VCI')
        start_date = "2018-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")
        df = q.history(start=start_date, end=end_date)
        if df is not None and not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            df.columns = [c.lower() for c in df.columns]
            df = df.sort_values('time').drop_duplicates(subset=['time']).reset_index(drop=True)
            df.to_csv(VNINDEX_PATH, index=False)
            return df
    except Exception as e:
        print(f"[-] Lỗi cập nhật VNINDEX từ vnstock: {e}")

    if os.path.exists(VNINDEX_PATH):
        try:
            df = pd.read_csv(VNINDEX_PATH)
            df['time'] = pd.to_datetime(df['time'])
            return df
        except Exception:
            pass
    return None

def get_market_regime(update=True):
    """
    Phân loại trạng thái thị trường chung VN-Index:
    - BULL (🟢 Xanh): Thị trường uptrend thuận lợi.
    - NEUTRAL (🟡 Vàng): Thị trường sideway / điều chỉnh nhẹ.
    - BEAR (🔴 Đỏ): Thị trường downtrend mạnh (khóa mua để bảo vệ vốn).
    """
    df = update_vnindex_data() if update else None
    if df is None and os.path.exists(VNINDEX_PATH):
        df = pd.read_csv(VNINDEX_PATH)
        df['time'] = pd.to_datetime(df['time'])

    if df is None or len(df) < 60:
        return {
            'status': 'BULL',
            'color': '🟢',
            'label': 'THUẬN LỢI',
            'action': 'Giao dịch bình thường',
            'allow_buy': True,
            'close': 0,
            'sma20': 0,
            'sma50': 0
        }

    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()

    curr = df.iloc[-1]
    prev5 = df.iloc[-6] if len(df) >= 6 else curr

    close = float(curr['close'])
    sma20 = float(curr['sma20'])
    sma50 = float(curr['sma50'])
    sma20_prev5 = float(prev5['sma20'])

    # Logic phân loại
    if close >= sma50 and sma20 >= sma20_prev5 * 0.998:
        status = 'BULL'
        color = '🟢'
        label = 'UPTREND THUẬN LỢI'
        action = 'Giải ngân bình thường (20-25% NAV/mã)'
        allow_buy = True
    elif close < sma50 and (close < sma20 or sma20 < sma50):
        status = 'BEAR'
        color = '🔴'
        label = 'DOWNTREND PHÒNG THỦ'
        action = 'Tạm dừng mở vị thế mới, ưu tiên nắm giữ tiền mặt'
        allow_buy = False
    else:
        status = 'NEUTRAL'
        color = '🟡'
        label = 'SIDEWAY THẬN TRỌNG'
        action = 'Hạ tỷ trọng lệnh xuống 10-15% NAV/mã'
        allow_buy = True

    return {
        'status': status,
        'color': color,
        'label': label,
        'action': action,
        'allow_buy': allow_buy,
        'date': curr['time'].strftime('%Y-%m-%d'),
        'close': close,
        'sma20': round(sma20, 2),
        'sma50': round(sma50, 2)
    }

if __name__ == "__main__":
    regime = get_market_regime(update=True)
    print("Market Regime Current Status:")
    print(regime)
