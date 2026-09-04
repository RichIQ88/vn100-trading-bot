# VN100 Trading Signal Bot (Bollinger Bands & Volume T+)

Hệ thống cung cấp tín hiệu giao dịch cổ phiếu ngắn hạn (Lướt sóng T+ từ vài ngày đến 2-3 tuần) trên danh mục **VN100** sử dụng khung thời gian Daily và tổ hợp 5 công cụ chỉ báo kỹ thuật:
1. **Bollinger Bands** (Dải trên, Dải giữa SMA20, Dải dưới)
2. **Bollinger Bands %B** (Vị trí tương đối của giá trong dải)
3. **Bollinger Bands Width** (Đo lường biên độ nén thắt nút cổ chai / co thắt dải băng)
4. **Volume & Volume MA20** (Khối lượng dòng tiền so với trung bình 20 phiên)
5. **MA xu hướng ngắn ngày** (EMA9 kết hợp lọc xu hướng trung hạn SMA50)

---

## 📊 Kết quả Backtest Lịch sử 8 Năm (2018 - 2026)

Hệ thống đã được backtest nghiêm ngặt theo **luật thanh toán T+2.5 của thị trường chứng khoán Việt Nam**:
* Cổ phiếu về tài khoản sau chiều $T+2$, bán sớm nhất tại $T+3$.
* Ràng buộc biên độ trần/sàn (không mua khi trần cứng trắng bên bán, không bán khi sàn cứng).
* Phí giao dịch và thuế thực tế: **0.40% round-trip** (0.15% mua + 0.15% bán + 0.1% thuế).

### 1. Chế độ Tối ưu Winrate Cao (`High-Winrate Trend Pullback`):
* **Chiến lược**: Trong xu hướng tăng vững chắc (Giá > SMA50, SMA20 dốc lên, EMA9 >= SMA20), cổ phiếu điều chỉnh ngắn hạn với **volume cạn kiệt** (`vol < vol_ma * 0.9`), sau đó kiểm định trục giữa SMA20 và xuất hiện **nến xanh bật tăng dứt khoát** kèm dòng tiền quay trở lại (`vol_ratio >= 1.15`).
* **Win Rate**: **~60.0%**
* **Profit Factor**: **1.64 - 1.76**
* **Lợi nhuận trung bình ròng mỗi lệnh**: **+1.05% - +1.13%** (đã trừ phí thuế)
* **Kỳ vọng chốt lời (TP)**: **+5% đến +6%** (hoặc chốt khi giá tiệm cận Upper Band `%B >= 0.85`)
* **Dừng lỗ (SL)**: **-3.5% đến -4.0%** (ngay dưới đáy nến nảy hoặc trục giữa)
* **Thời gian giữ lệnh tối đa**: **8 phiên** (T+8 ~ 1.5 tuần)

### 2. Chế độ Đa Dạng Bối Cảnh (`Multi-Setup`):
* Kích hoạt cả 3 thiết lập:
  * **Squeeze Breakout**: Thắt nút cổ chai cực hẹp rồi bùng nổ vượt dải kèm khối lượng lớn (> 200% MA20).
  * **Trend Pullback**: Hồi quy trục giữa trong Uptrend.
  * **Oversold Reversal**: Bắt nhịp hồi sau khi giá rơi sâu thủng dải dưới và rút chân trở lại vào dải.

---

## 🛠️ Cài đặt & Chạy Cục bộ

### 1. Khởi tạo môi trường ảo
```bash
python3 -m venv ~/.venv
source ~/.venv/bin/activate
pip install -r requirements.txt
```

### 2. Cấu hình file `.env`
Sao chép file `.env.example` thành `.env`:
```bash
cp .env.example .env
```
Mở file `.env` và điền:
* `VNSTOCK_API_KEY`: API Key miễn phí lấy tại https://vnstocks.com/account#api-key (giúp tăng tốc độ tải lên 60 req/phút). Nếu là tài khoản Guest có thể để trống.
* `TELEGRAM_BOT_TOKEN`: Token của bot tạo từ `@BotFather` trên Telegram.
* `TELEGRAM_CHAT_ID`: ID chat của bạn lấy từ `@userinfobot` trên Telegram.

### 3. Tải dữ liệu lịch sử VN100
```bash
python src/data_loader.py
```
*(Dữ liệu được lưu cache trong thư mục `data/` dạng `.csv` để backtest siêu tốc).*

### 4. Chạy Backtest & Tối ưu hóa tham số
```bash
python src/optimizer.py
```

### 5. Chạy Quét Tín Hiệu Thị Trường
* Quét phiên hôm nay (chế độ Winrate cao):
  ```bash
  python src/scanner.py
  ```
* Quét đa bối cảnh (Multi-setup) trong 5 phiên gần nhất:
  ```bash
  python src/scanner.py --mode multi_setup --lookback 5
  ```

---

## 🤖 Đưa Bot Lên GitHub Auto Chạy Trong Phiên

Dự án đã tích hợp sẵn **GitHub Actions Workflow** (`.github/workflows/daily_scanner.yml`). Bot sẽ tự động chạy trên máy chủ đám mây của GitHub theo lịch trình giao dịch:

* **11:30 sáng** (Giờ VN - Kết thúc phiên sáng)
* **14:15 chiều** (Giờ VN - Trước đợt khớp lệnh ATC để kịp theo dõi và đặt lệnh)
* **15:05 chiều** (Giờ VN - Tổng kết sau khi đóng cửa thị trường)

### Các bước cấu hình trên GitHub:
1. Khởi tạo Git repository và đẩy code lên GitHub của bạn:
   ```bash
   git init
   git add .
   git commit -m "Initial commit VN100 BB trading bot"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. Trên trang repository GitHub, vào **Settings** > **Secrets and variables** > **Actions**.
3. Nhấp **New repository secret** và thêm 3 biến:
   * `VNSTOCK_API_KEY`: API Key của vnstock (nếu có).
   * `TELEGRAM_BOT_TOKEN`: Token bot Telegram của bạn.
   * `TELEGRAM_CHAT_ID`: Chat ID Telegram của bạn.
4. Xong! Bot sẽ tự động quét mã và bắn thông báo về Telegram của bạn trong từng phiên giao dịch mà không cần mở máy tính!
