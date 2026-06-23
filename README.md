# Dự án pm-mcp (Multi-User Server)

MCP Server (Model Context Protocol) quản lý công việc (TMS) có hỗ trợ khả năng Multi-User thông qua kết nối HTTP/SSE. Người dùng kết nối đến Server thông qua Client (ví dụ: Claude Desktop) và tự cung cấp `Session Cookie` của mình qua HTTP Header để xác thực.

## 1. Cài đặt và Triển khai Server (Dành cho Admin)

Máy chủ được khuyến nghị chạy trên Ubuntu/Linux thông qua Docker. 

### Bước chuẩn bị:
1. Đảm bảo server đã được cài đặt `docker` và `docker-compose`.
2. Clone mã nguồn về máy chủ.
3. Tạo/Cấu hình file `config.json` nếu cần cấu hình các tham số URL.

### Khởi chạy Server:
Tại thư mục chứa mã nguồn, chạy lệnh sau:
```bash
docker compose up -d --build
```
Lệnh này sẽ build Docker image và khởi chạy server trên cổng `8000` với chế độ HTTP/SSE (`streamable-http`).

> **Lưu ý quan trọng**: Khi chạy qua HTTP, server hoàn toàn **stateless**. Biến `SESSION_COOKIE` trong file `.env` sẽ không được sử dụng. Từng user sẽ tự truyền cookie của họ thông qua HTTP request.

---

## 2. Hướng dẫn sử dụng cho Người dùng (Client Setup)

Bất kỳ nhân viên nào trong công ty đều có thể kết nối tới MCP Server mà không cần cài đặt Python. Hệ thống sẽ nhận diện tài khoản của từng người dựa trên Cookie.

### Bước 1: Cài đặt NodeJS
Để kết nối từ xa, máy tính cần cài đặt **NodeJS** (chỉ dành cho Windows/Mac).
- Tải về tại: [nodejs.org](https://nodejs.org/) và cài đặt mặc định.

### Bước 2: Lấy Cookie cá nhân (TMS)
1. Mở trình duyệt, đăng nhập vào hệ thống quản lý công việc TMS.
2. Nhấn `F12` để mở **Developer Tools**.
3. Chuyển sang tab **Network** và tải lại trang (`F5`).
4. Bấm vào một Request (thường là cái đầu tiên) và kéo xuống tìm phần **Request Headers**.
5. Copy toàn bộ chuỗi ký tự đằng sau chữ `Cookie:`.

### Bước 3: Cấu hình Claude Desktop (Windows)
1. Mở Claude Desktop.
2. Vào **File** > **Settings** > **Developer** > **Edit Config**.
3. Thêm cấu hình mcp-remote kết nối vào IP của Ubuntu Server:

```json
{
  "mcpServers": {
    "pm-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://172.25.146.4:8000/sse",
        "--allow-http",
        "--header", "x-tms-cookie: PASTE_COOKIE_VỪA_COPY_VÀO_ĐÂY"
      ]
    }
  }
}
```

> **Lưu ý nhỏ cho người dùng Windows & WSL:**
> - Nếu Server chạy trong WSL ngay trên máy, hãy thay `<IP_UBUNTU_SERVER>` thành `172.x.x.x` (IP của WSL) hoặc đơn giản là `localhost`.
> - Luôn sử dụng lệnh `npx` trên Windows để tránh lỗi không tìm thấy đường dẫn NodeJS.
> - Cờ `--allow-http` là bắt buộc vì ứng dụng client sẽ tự động chặn các địa chỉ IP HTTP vì lý do bảo mật.

4. Lưu file và khởi động lại ứng dụng Claude Desktop.

### Bước 4: Khắc phục khi Cookie hết hạn
Nếu sau một vài tuần hoặc vài tháng hệ thống báo lỗi không lấy được dữ liệu, có nghĩa là Session Cookie đã bị máy chủ TMS tự động đăng xuất. Chỉ cần thực hiện lại **Bước 2** để lấy Cookie mới và thay vào file cấu hình.

---

## 3. Development (Dành cho Lập trình viên)

Nếu muốn chạy server trực tiếp ở máy local mà không dùng Docker hay HTTP (Chế độ Stdio 1-kèm-1 cũ):

1. Tạo file `.env` từ file `.env.example` và thiết lập biến `SESSION_COOKIE` trong đó.
2. Chạy lệnh:
```bash
uv run main.py
```
*(Nếu không có các biến môi trường HTTP, ứng dụng sẽ tự động rơi vào chế độ giao tiếp `stdio` phục vụ cho phát triển cá nhân)*.
