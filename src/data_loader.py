import os
import time
import pandas as pd
from datetime import datetime
from vnstock.api.listing import Listing
from vnstock.api.quote import Quote
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("VNSTOCK_API_KEY", "").strip()
if api_key:
    try:
        from vnstock.core import setup_api_key
        setup_api_key(api_key)
    except Exception:
        pass

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def get_vn100_symbols():
    """Lấy danh sách mã chứng khoán thuộc rổ VN100"""
    try:
        listing = Listing()
        symbols_series = listing.symbols_by_group('VN100')
        symbols = [s.strip() for s in symbols_series if isinstance(s, str) and len(s.strip()) == 3]
        if symbols and len(symbols) >= 50:
            return sorted(list(set(symbols)))
    except Exception as e:
        print(f"Lỗi khi lấy danh sách VN100 từ vnstock: {e}")
    
    fallback = [
        "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
        "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
        "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
        "ANV", "BAF", "BSI", "CTR", "DBC", "DCM", "DGC", "DIG", "DPM", "DXG",
        "EIB", "FRT", "GEX", "HDG", "HSG", "KBC", "KDC", "KDH", "LPB", "MSB",
        "NLG", "NT2", "OCB", "PAN", "PC1", "PDR", "PHR", "PVD", "PVS", "PVT",
        "REE", "SBT", "SCS", "SZC", "VCI", "VGC", "VHC", "VIX", "VND", "VPI"
    ]
    return sorted(list(set(fallback)))

def download_ticker_history(symbol, start_date="2018-01-01", end_date=None, force=False, max_retries=3):
    """
    Tải dữ liệu 8 năm của 1 mã cổ phiếu và lưu cache cục bộ dạng csv.
    Tự động xử lý giới hạn request (Rate Limit) cho tài khoản Guest/Free.
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")

    if not force and os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if len(df) > 50:
                df['time'] = pd.to_datetime(df['time'])
                return df
        except Exception:
            pass

    for attempt in range(max_retries):
        try:
            q = Quote(symbol=symbol, source='VCI')
            df = q.history(start=start_date, end=end_date)
            if df is not None and not df.empty:
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time').drop_duplicates(subset=['time']).reset_index(drop=True)
                df.columns = [c.lower() for c in df.columns]
                df.to_csv(csv_path, index=False)
                return df
            else:
                return None
        except Exception as e:
            err_msg = str(e).lower()
            if "rate limit" in err_msg or "giới hạn" in err_msg or "429" in err_msg or "request" in err_msg:
                print(f" [Rate limit, tạm nghỉ 25s trước khi thử lại ({attempt+1}/{max_retries})]...", end="", flush=True)
                time.sleep(25)
            else:
                time.sleep(2)
    return None

def download_all_vn100(start_date="2018-01-01", force=False, target_count=50):
    """
    Tải/đồng bộ dữ liệu lịch sử của danh mục VN100.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    symbols = get_vn100_symbols()
    print(f"[*] Đồng bộ dữ liệu danh mục VN100 (từ {start_date})...")
    
    success_count = 0
    for i, sym in enumerate(symbols, 1):
        csv_path = os.path.join(DATA_DIR, f"{sym}.csv")
        if not force and os.path.exists(csv_path):
            try:
                df_test = pd.read_csv(csv_path)
                if len(df_test) > 50:
                    success_count += 1
                    continue
            except Exception:
                pass

        print(f"[{i}/{len(symbols)}] Tải {sym}...", end=" ", flush=True)
        df = download_ticker_history(sym, start_date=start_date, force=force)
        if df is not None and not df.empty:
            print(f"✓ ({len(df)} phiên)")
            success_count += 1
        else:
            print("✗")
        # Nghỉ 3.1 giây giữa các request để đảm bảo < 20 req/min của gói Guest
        time.sleep(3.1)
        
        # Nếu đã đủ số lượng mẫu lớn để backtest tối ưu hóa
        if success_count >= target_count:
            print(f"[*] Đã tải thành công {success_count} mã đại diện đủ lớn cho mẫu dữ liệu thống kê.")
            break
        
    print(f"[✓] Hoàn thành: {success_count} mã cổ phiếu đã sẵn sàng trong cache dữ liệu.")
    return symbols

if __name__ == "__main__":
    download_all_vn100()
