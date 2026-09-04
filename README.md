# VN100 Quant Trading & Advisory Bot (Bollinger Bands & Volume T+)

Hệ thống cung cấp tín hiệu giao dịch cổ phiếu ngắn hạn (Lướt sóng T+ từ vài ngày đến 1-2 tuần) trên danh mục **VN100** sử dụng khung thời gian Daily và tổ hợp 5 công cụ chỉ báo kỹ thuật:
1. **Bollinger Bands** (Dải trên, Dải giữa SMA20, Dải dưới)
2. **Bollinger Bands %B** (Vị trí tương đối của giá trong dải)
3. **Bollinger Bands Width** (Đo lường biên độ nén thắt nút cổ chai)
4. **Volume & Volume MA20** (Khối lượng dòng tiền so với trung bình 20 phiên)
5. **MA xu hướng ngắn ngày** (EMA9 kết hợp bộ lọc xu hướng trung hạn SMA50)

---

## 🚀 Các Tính Năng Cao Cấp Vừa Được Nâng Cấp

### 1. 📊 Tự Động Vẽ & Bắn Ảnh Biểu Đồ Kỹ Thuật Vào Telegram
* Khi phát hiện tín hiệu mua, bot tự động vẽ **biểu đồ nến Nhật 60 phiên** kèm dải Bollinger Bands, EMA9, cột khối lượng Volume nổi bật và các đường gióng mục tiêu:
  * Đường xanh lá đứt đoạn: **Mục tiêu Chốt lời TP (+5.5% đến +6%)**.
  * Đường đỏ đứt đoạn: **Ngưỡng Dừng lỗ SL (-4.0%)**.
* Ảnh chart được gửi trực tiếp vào Telegram cùng tin nhắn phân tích, giúp khách hàng quan sát trực quan trước khi ra quyết định.

### 2. 🧠 Bộ Lọc Xu Hướng Thị Trường Chung (VN-Index Regime Filter)
* Tự động phân loại trạng thái chỉ số VN-Index:
  * 🟢 **BULL (Thuận lợi)**: VN-Index > SMA50 và SMA20 dốc lên ➜ Mở vị thế bình thường (20-25% NAV/mã).
  * 🟡 **NEUTRAL (Thận trọng)**: Thị trường giằng co ➜ Hạ quy mô lệnh xuống 10-15% NAV.
  * 🔴 **BEAR (Phòng thủ)**: VN-Index gãy SMA50 kèm SMA20 dốc xuống ➜ **Tự động khóa lệnh mua mới**, bảo vệ 100% tiền mặt cho khách hàng.

### 3. 🎯 Quản Lý Vị Thế Realtime & Chốt Lời Từng Phần (Scale-out)
* **Theo dõi vị thế đang mở:** Tự động theo dõi các mã đã khuyến nghị (`data/active_positions.json`).
* **Kịch bản Chốt lời từng phần (TP1)**:
  * Khi cổ phiếu chạm mốc +5.5% đến +6%: Bot bắn thông báo **Chốt lời trước 50% khối lượng**.
  * **50% còn lại**: Nâng điểm dừng lỗ lên đúng **Giá vốn** (Breakeven - rủi ro bằng 0) và thả trôi gồng lãi bám theo đường EMA9 để đón siêu sóng (+15% - 25%).
* **Cảnh báo Cắt lỗ & Hết hạn T+8**: Tự động thông báo nếu vi phạm SL hoặc giữ quá 8 phiên.

### 4. 💻 Web Dashboard Quản Lý Khuyến Nghị Trực Quan
* Chạy bảng điều khiển web trực tiếp bằng Streamlit:
  ```bash
  streamlit run dashboard.py
  ```
* Xem danh mục khuyến nghị đang mở, hiệu suất 8 năm, tra cứu biểu đồ kỹ thuật của bất kỳ mã nào trong VN100 và tạo báo cáo tháng cho khách hàng chỉ với 1 cú click chuột!

---

## 🛠️ Hướng Dẫn Sử Dụng Cục Bộ

```bash
# 1. Kích hoạt môi trường ảo
source ~/.venv/bin/activate

# 2. Quét tín hiệu thị trường hôm nay
python src/scanner.py

# 3. Xuất báo cáo hiệu suất tháng bất kỳ
python src/monthly_report.py --month 2026-08

# 4. Mở Web Dashboard
streamlit run dashboard.py
```
