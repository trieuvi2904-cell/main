EMAIL BÁO KHI CÓ KHÁCH HỎI LỄ TÂN A.I  (gửi tới fairygardenhoian@gmail.com)

Cách bật (làm một lần):
 1) Đăng nhập Gmail fairygardenhoian@gmail.com, vào https://myaccount.google.com/security
    và BẬT "Xác minh 2 bước" (2-Step Verification) nếu chưa bật.
 2) Vào https://myaccount.google.com/apppasswords , đặt tên ứng dụng (ví dụ "Le tan AI") -> Tạo.
    Google hiện mật khẩu 16 ký tự (dạng abcd efgh ijkl mnop).
 3) Tạo file mail_password.txt cạnh rec.py, chỉ dán mật khẩu 16 ký tự đó vào (có dấu cách cũng được).
 4) Chạy lại ứng dụng. Khi có khách hỏi, console sẽ in "[Mail] Đã gửi email thông báo ...".

Cách hoạt động:
 - Các lượt hỏi-đáp liên tiếp được gom vào 1 email, gửi sau khi khách yên lặng 60 giây (hoặc tối đa 5 phút).
 - Nội dung email: giờ, ngôn ngữ, câu khách nói, câu A.I trả lời. Có báo thêm khi hệ thống gặp lỗi.
 - Khách bấm phím mà không nói gì: mặc định KHÔNG báo (đổi INCLUDE_EMPTY = True trong thong_bao_mail.py nếu muốn).
 - Muốn gửi bằng Gmail khác / nhận ở địa chỉ khác: đặt biến môi trường MAIL_FROM, MAIL_TO.
 - Không có mail_password.txt thì tính năng tự tắt, ứng dụng vẫn chạy bình thường.

Lưu ý: không gửi mật khẩu ứng dụng cho ai và không đưa lên GitHub (mail_password.txt đã nằm trong .gitignore).
Nội dung khách nói được gửi qua email: nên có thông báo tại quầy nếu cần.
