# Đối chiếu yêu cầu và hạng mục cần bổ sung

Tài liệu này đối chiếu yêu cầu ban đầu với phiên bản hiện tại của nền tảng
quản trị từ xa trong mạng LAN. Mọi máy Agent phải là máy do tổ chức sở hữu
hoặc có sự đồng ý rõ ràng của người dùng.

## 1. Relay Server / Gateway

| Yêu cầu | Trạng thái | Ghi chú bổ sung |
|---|---|---|
| WebSocket nhận kết nối Agent | Có | `server/relay.py` lắng nghe `/ws/agent`. |
| Danh sách Agent online theo ID | Có | Agent trùng ID sẽ thay thế phiên cũ; cần hiển thị cả hostname và thời điểm kết nối. |
| Chuyển lệnh và trả kết quả đúng Agent | Có | Có `request_id`, timeout 20 giây và xóa pending request khi hoàn tất. |
| Xóa Agent khi ngắt kết nối | Có | Gateway xóa session và ghi audit event. |
| Xác thực và phân quyền | Có | HMAC cho Agent, JWT/RBAC cho Dashboard. |
| Mã hóa trên LAN | Cần cấu hình khi triển khai | Dùng WSS/HTTPS với chứng chỉ hợp lệ; không dùng `ws://` hoặc secret mặc định trên mạng thật. |
| Giới hạn tải và theo dõi sức khỏe | Thiếu | Bổ sung rate limit, giới hạn số lệnh/Agent, kích thước frame, heartbeat/last-seen và cảnh báo kết nối bất thường. |
| Lưu vết | Có một phần | Audit hiện là JSONL; cần chính sách lưu giữ, phân quyền đọc log và không ghi dữ liệu nhạy cảm vào log. |

## 2. Client / Agent

| Yêu cầu | Trạng thái | Ghi chú bổ sung |
|---|---|---|
| Chủ động kết nối, đăng ký ID, tự kết nối lại | Có | Agent dùng kết nối outbound, HMAC challenge và retry sau 3 giây. Nên đổi sang exponential backoff có jitter. |
| Ứng dụng và tiến trình | Có một phần | Có liệt kê, mở ứng dụng allow-list, và dừng PID có bảo vệ tiến trình hệ thống. Cần tách “Application” khỏi “Process” nếu muốn hiển thị đúng ứng dụng có cửa sổ. |
| Telemetry | Có | CPU, RAM, uptime và nhiệt độ khi hệ điều hành/hardware hỗ trợ. |
| Screen | Có một phần | Hiện là chuỗi ảnh snapshot do Dashboard polling; chưa phải stream thời gian thực có điều khiển bitrate/FPS. Cần xác nhận cục bộ mỗi phiên và chỉ báo đang chia sẻ màn hình. |
| Webcam | Có một phần | Chỉ có snapshot sau khi bật cờ consent cục bộ. Chưa có quay video Start/Stop, mã hóa, thời hạn lưu file hay luồng gửi file. |
| Files | Có một phần | Chỉ duyệt danh sách bên dưới `REMOTE_ADMIN_FILE_ROOT`; thiếu download/upload. Nếu bổ sung, cần whitelist thư mục, giới hạn dung lượng/loại file, quét malware, checksum, progress, resume và audit từng file. |
| Power | Có | Lock, sleep, restart, shutdown; yêu cầu admin và cờ cho phép tại Agent. |
| Logout | Thiếu | Nếu cần, thêm `logout` vào allow-list, yêu cầu admin + xác nhận cục bộ, và ghi audit. |
| Cập nhật/phiên bản Agent | Thiếu | Cần gửi version, OS, capabilities và health trong lúc đăng ký để Dashboard có thể tương thích tính năng. |
| Keylogger | Không hỗ trợ (cố ý) | Không bổ sung. Thu thập phím gõ là dữ liệu cực nhạy cảm và không phù hợp cho công cụ quản trị thông thường. |

## 3. Web Dashboard

| Yêu cầu | Trạng thái | Ghi chú bổ sung |
|---|---|---|
| Đăng nhập, chọn Agent và làm mới danh sách | Có | Dashboard kết nối Server qua HTTPS/JWT, không kết nối thẳng Agent. |
| Nhập `IP::Port` và tạo WebSocket trên trình duyệt | Không áp dụng với kiến trúc hiện tại | Đây là yêu cầu của mô hình Dashboard kết nối Relay trực tiếp. Dự án hiện dùng Server làm lớp xác thực/proxy, an toàn hơn. Địa chỉ Gateway phải cấu hình phía Server/Agent, không nhập trên web client. |
| Applications | Có một phần | Có refresh, tìm kiếm và đóng PID. Thiếu UI “Start new application”; chỉ cho phép chọn ứng dụng nằm trong allow-list. |
| Processes | Có một phần | Có refresh, tìm kiếm và kill. Thiếu sắp xếp theo Name/PID bằng click tiêu đề và UI chạy tiến trình mới (không nên cho chạy lệnh tùy ý). |
| Screen | Có một phần | Có Start/Stop với snapshot polling. Cần chỉ báo consent, FPS/độ trễ và trạng thái khi Agent ngắt kết nối. |
| Webcam video | Thiếu | Không có Start/Stop recording, phát video, tải file hay kiểm soát lưu trữ. Chỉ nên triển khai nếu có consent theo phiên, đèn/badge hiển thị rõ và phân quyền audit. |
| File transfer | Thiếu | Chưa có API lẫn UI upload/download; áp dụng các kiểm soát tại phần Client trước khi triển khai. |
| Power | Có một phần | Có lock/sleep/restart/shutdown; thiếu logout và hộp xác nhận có mô tả Agent đích. |
| Audit | Có | Có tab audit; nên thêm lọc theo Agent, người dùng, action, thời gian và trạng thái thành công/thất bại. |

## Thứ tự ưu tiên đề xuất

1. Hoàn thiện an toàn vận hành: WSS/HTTPS, secret không mặc định, rate limit,
   version/capability của Agent và retry backoff.
2. Hoàn thiện UI hiện có: nút mở ứng dụng từ allow-list, sắp xếp tiến trình,
   trạng thái kết nối/consent và bộ lọc audit.
3. Nếu nghiệp vụ được phê duyệt: transfer file có kiểm soát và logout, với
   kiểm thử đường dẫn, dung lượng, quyền và audit.
4. Chỉ đánh giá quay webcam/video hoặc screen stream sau khi có chính sách
   consent theo phiên, thông báo trực quan và thời hạn xóa dữ liệu.

## Tiêu chí nghiệm thu tối thiểu

- Agent không xác thực hoặc lệnh ngoài allow-list phải bị từ chối và ghi log.
- Mất kết nối phải làm Agent biến mất khỏi danh sách online trong một chu kỳ
  heartbeat; request đang chờ nhận lỗi rõ ràng.
- Lệnh hủy tiến trình, power, xem màn hình/camera và transfer file phải có
  RBAC, audit và kiểm soát cục bộ tương ứng.
- Không thể duyệt/đọc/ghi file ra ngoài thư mục được cấp quyền, kể cả qua
  `..`, symlink hoặc đường dẫn tuyệt đối.
- Không có cơ chế ghi phím; Dashboard và Agent hiển thị rõ khi màn hình/camera
  đang được chia sẻ.
