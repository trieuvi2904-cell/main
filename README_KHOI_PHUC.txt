KHÔI PHỤC ỨNG DỤNG LỄ TÂN A.I

CÓ TRONG GÓI NÀY:
  rec.py            chương trình chính (Groq STT, đa ngôn ngữ, hướng dẫn song ngữ...)
  ui_letan.py       giao diện (đã ẩn ô gõ phím)
  requirements.txt  danh sách thư viện

KHÔNG CÓ (tôi chưa từng nhận các file này, bạn cần tìm lại hoặc tạo lại):
  gv.py                      widget tuỳ chỉnh mà ui_letan.py import
  prompt_letan.py            SYSTEM_CONTEXT + time_context() (nội dung tư vấn của villa)
  doc_chu.py                 prep_for_speech() (chuẩn hoá cách đọc)
  anh nen app.png            ảnh nền 1376x768
  qr_host.png, qr_bank.png   hai mã QR
  fonts/ (Be Vietnam Pro .ttf)   font giao diện
  api_key.txt                khoá Anthropic (tạo lại ở console.anthropic.com)
  groq_key.txt               khoá Groq (tạo lại ở console.groq.com)
  audio_cache/               tự tạo lại khi chạy (không cần khôi phục)

CÀI ĐẶT:
  1) Cài Python 3.10+ (tick "Add to PATH") và ffmpeg (C:\ffmpeg\bin\ffmpeg.exe)
  2) pip install -r requirements.txt
  3) Đặt đủ các file ở trên cùng một thư mục, rồi: python rec.py
