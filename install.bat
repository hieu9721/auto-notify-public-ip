#!/bin/bash

# Script cài đặt và khởi động IP Monitor Bot

echo "=== IP Monitor Bot Setup ==="

# Tạo thư mục cho bot
BOT_DIR="$HOME/ip-monitor-bot"
mkdir -p "$BOT_DIR"
cd "$BOT_DIR"

# Cài đặt Python dependencies
echo "Cài đặt dependencies..."
pip3 install requests

# Tạo file cấu hình nếu chưa có
if [ ! -f "config.json" ]; then
    echo "Tạo file cấu hình..."
    cat > config.json << 'EOF'
{
  "check_interval": 300,
  "notification_methods": ["discord"],
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your-email@gmail.com",
    "sender_password": "your-app-password",
    "recipient_email": "recipient@gmail.com"
  },
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "discord": {
    "webhook_url": "https://discord.com/api/webhooks/1388807634429153311/cIdHskKC9r1-PLs63po5RzUk8bERP0JhGJyDsME23y1HKC5dpTWscC70OSkffsH6HR0f"
  }
}
EOF
fi

# Tạo systemd service
echo "Tạo systemd service..."
sudo tee /etc/systemd/system/ip-monitor.service > /dev/null << EOF
[Unit]
Description=IP Monitor Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
ExecStart=/usr/bin/python3 $BOT_DIR/ip_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Tạo script khởi động thủ công
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 ip_monitor.py
EOF
chmod +x start.sh

# Tạo script dừng
cat > stop.sh << 'EOF'
#!/bin/bash
sudo systemctl stop ip-monitor
echo "Đã dừng IP Monitor Bot"
EOF
chmod +x stop.sh

# Tạo script kiểm tra IP
cat > check_ip.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 ip_monitor.py --check-ip
EOF
chmod +x check_ip.sh

echo ""
echo "=== Cài đặt hoàn tất! ==="
echo ""
echo "Các bước tiếp theo:"
echo "1. Chỉnh sửa file config.json với thông tin của bạn"
echo "2. Chạy bot:"
echo "   • Thủ công: ./start.sh"
echo "   • Dưới dạng service: sudo systemctl enable ip-monitor && sudo systemctl start ip-monitor"
echo "3. Kiểm tra IP hiện tại: ./check_ip.sh"
echo "4. Xem log: tail -f ip_monitor.log"
echo ""
echo "File đã tạo:"
echo "• ip_monitor.py - Bot chính"
echo "• config.json - File cấu hình"
echo "• start.sh - Khởi động thủ công"
echo "• stop.sh - Dừng service"
echo "• check_ip.sh - Kiểm tra IP hiện tại"
echo ""

# Hiển thị IP hiện tại
echo "IP hiện tại của bạn:"
python3 ip_monitor.py --check-ip 2>/dev/null || echo "Không thể lấy IP (cần cài đặt dependencies)"