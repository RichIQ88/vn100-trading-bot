# Sector classification for VN100 Universe

SECTOR_MAP = {
    # Ngân hàng (Banking)
    "ACB": "Ngân hàng", "BID": "Ngân hàng", "CTG": "Ngân hàng", "EIB": "Ngân hàng",
    "HDB": "Ngân hàng", "LPB": "Ngân hàng", "MBB": "Ngân hàng", "MSB": "Ngân hàng",
    "OCB": "Ngân hàng", "SHB": "Ngân hàng", "STB": "Ngân hàng", "TCB": "Ngân hàng",
    "TPB": "Ngân hàng", "VCB": "Ngân hàng", "VIB": "Ngân hàng", "VPB": "Ngân hàng",
    "EVF": "Tài chính & Tín dụng",

    # Chứng khoán (Securities)
    "BSI": "Chứng khoán", "CTS": "Chứng khoán", "FTS": "Chứng khoán", "HCM": "Chứng khoán",
    "ORS": "Chứng khoán", "SSI": "Chứng khoán", "VCI": "Chứng khoán", "VDS": "Chứng khoán",
    "VIX": "Chứng khoán", "VND": "Chứng khoán", "DSE": "Chứng khoán",

    # Bất động sản dân cư (Real Estate)
    "DIG": "Bất động sản", "DXG": "Bất động sản", "KDH": "Bất động sản", "NLG": "Bất động sản",
    "NVL": "Bất động sản", "PDR": "Bất động sản", "VHM": "Bất động sản", "VIC": "Bất động sản",
    "VRE": "Bất động sản", "HDG": "Bất động sản",

    # Khu công nghiệp, Xây dựng & Hạ tầng
    "BCM": "BĐS Khu công nghiệp", "KBC": "BĐS Khu công nghiệp", "GVR": "BĐS Khu công nghiệp & Cao su",
    "SZC": "BĐS Khu công nghiệp", "CII": "Hạ tầng & Đầu tư", "CTD": "Xây dựng", "VCG": "Xây dựng",

    # Thép & Vật liệu xây dựng
    "HPG": "Thép & Kim loại", "HSG": "Thép & Kim loại", "NKG": "Thép & Kim loại", "BMP": "Vật liệu nhựa & Xây dựng",

    # Công nghệ thông tin & Viễn thông
    "FPT": "Công nghệ thông tin", "CMG": "Công nghệ thông tin", "CTR": "Hạ tầng viễn thông",

    # Bán lẻ & Hàng tiêu dùng
    "MWG": "Bán lẻ", "FRT": "Bán lẻ", "DGW": "Bán lẻ công nghệ", "PNJ": "Vàng bạc & Trang sức",
    "MSN": "Tiêu dùng & Thực phẩm", "VNM": "Tiêu dùng & Thực phẩm", "SAB": "Đồ uống & Bia",
    "BAF": "Nông nghiệp & Chăn nuôi", "DBC": "Nông nghiệp & Chăn nuôi",

    # Năng lượng, Dầu khí & Tiện ích
    "GAS": "Dầu khí", "PLX": "Dầu khí", "BSR": "Dầu khí", "PVD": "Dầu khí", "PVS": "Dầu khí",
    "POW": "Điện lực", "PC1": "Xây lắp điện & Năng lượng", "REE": "Cơ điện lạnh & Năng lượng",
    "BWE": "Cấp thoát nước",

    # Hóa chất & Phân bón
    "DGC": "Hóa chất cơ bản", "DCM": "Phân bón & Hóa chất", "DPM": "Phân bón & Hóa chất",

    # Thủy sản
    "ANV": "Thủy sản", "VHC": "Thủy sản",

    # Vận tải & Logistics
    "GMD": "Cảng biển & Logistics", "HAH": "Vận tải biển", "PVT": "Vận tải dầu khí",
    "VOS": "Vận tải biển", "VSC": "Cảng biển & Container",

    # Bảo hiểm
    "BVH": "Bảo hiểm"
}

def get_sector(symbol: str) -> str:
    """Trả về tên nhóm ngành của mã cổ phiếu"""
    return SECTOR_MAP.get(symbol.upper().strip(), "Khác")

def check_sector_limit(open_positions: list, candidate_symbol: str, max_per_sector: int = 2) -> tuple[bool, str]:
    """
    Kiểm tra xem mã cổ phiếu đề xuất có vượt quá trần phân bổ ngành hay không.
    Trả về: (được_mua: bool, lý_do: str)
    """
    candidate_sector = get_sector(candidate_symbol)
    
    # Đếm số mã cùng ngành đang nắm giữ
    current_count = 0
    symbols_in_sector = []
    for pos in open_positions:
        if pos.get('status') == 'OPEN':
            sym = pos.get('symbol', '')
            if get_sector(sym) == candidate_sector:
                current_count += 1
                symbols_in_sector.append(sym)
                
    if current_count >= max_per_sector:
        reason = f"Ngành '{candidate_sector}' đã có {current_count} mã đang mở ({', '.join(symbols_in_sector)}), đã chạm hạn mức tối đa {max_per_sector} mã/ngành để phân tán rủi ro!"
        return False, reason
        
    return True, f"Ngành '{candidate_sector}' hiện có {current_count}/{max_per_sector} mã, hợp lệ giải ngân."

def get_sector_breakdown(positions: list) -> dict:
    """Thống kê cơ cấu ngành của các vị thế đang mở"""
    breakdown = {}
    for pos in positions:
        if pos.get('status') == 'OPEN':
            sec = get_sector(pos.get('symbol', ''))
            breakdown[sec] = breakdown.get(sec, 0) + 1
    return breakdown
