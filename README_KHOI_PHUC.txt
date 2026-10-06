LỄ TÂN A.I - GÓI KHÔI PHỤC ĐẦY ĐỦ

CÀI ĐẶT
  1) Python 3.10+ (tick "Add to PATH") và ffmpeg (đặt ở C:\ffmpeg\bin\ffmpeg.exe) - ffmpeg dùng để tăng tốc giọng gTTS
  2) pip install -r requirements.txt
  3) Tạo 2 file khoá cạnh rec.py (mỗi file chỉ chứa khoá):
       api_key.txt   (Anthropic - console.anthropic.com)
       groq_key.txt  (Groq - console.groq.com)
  4) python rec.py   (chạy bằng quyền Administrator nếu thư viện 'keyboard' không bắt được phím)

CÁC FILE
  rec.py            chương trình chính
  ui_letan.py       giao diện 1376x768
  gv.py             widget chữ HTML (viết lại)
  prompt_letan.py   nội dung tư vấn - ĐIỀN các mục [CẬP NHẬT] (giờ nhận/trả phòng, xe máy, hồ bơi...)
  doc_chu.py        chuẩn hoá cách đọc (website, số điện thoại, wifi...) (viết lại)
  gen_assets.py     tạo lại ảnh nền + QR; "anh nen app.png", "qr_host.png", "qr_bank.png" đã tạo sẵn
  fonts/            (chưa có) tải Be Vietnam Pro (Google Fonts) rồi đặt các file .ttf vào đây; không có thì dùng font mặc định

LƯU Ý
  - qr_host.png trỏ tới https://hoianfairyvilla.com
  - qr_bank.png là mã VietQR tạo từ TPBank 1000 1689 000: HÃY QUÉT THỬ BẰNG APP NGÂN HÀNG trước khi in/dùng.
    Tốt nhất thay bằng ảnh QR tải từ app ngân hàng của bạn (đặt tên qr_bank.png).
  - Ảnh nền là bản vẽ lại, nếu có ảnh nền cũ thì ghi đè "anh nen app.png".
