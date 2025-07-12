#!/bin/bash

# Script cài đặt và khởi động IP Monitor Bot
# Hỗ trợ cả virtual environment và global installation

set -e  # Exit on any error

echo "🌐 === IP Monitor Bot Setup ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check if Python 3 is installed
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 không được tìm thấy. Vui lòng cài đặt Python 3.6+"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_status "Đã tìm thấy Python $PYTHON_VERSION"
}

# Ask user for installation method
choose_installation_method() {
    echo ""
    echo "Chọn phương thức cài đặt:"
    echo "1) Virtual Environment (Khuyến nghị - cô lập môi trường)"
    echo "2) Global Installation (Cài đặt toàn hệ thống)"
    echo ""
    
    while true; do
        read -p "Nhập lựa chọn [1-2]: " choice
        case $choice in
            1)
                USE_VENV=true
                print_status "Đã chọn Virtual Environment"
                break
                ;;
            2)
                USE_VENV=false
                print_warning "Đã chọn Global Installation"
                break
                ;;
            *)
                print_error "Vui lòng chọn 1 hoặc 2"
                ;;
        esac
    done
}

# Setup virtual environment
setup_venv() {
    if [ "$USE_VENV" = true ]; then
        print_header "Thiết lập Virtual Environment"
        
        if [ ! -d "venv" ]; then
            print_status "Tạo virtual environment..."
            python3 -m venv venv
        else
            print_warning "Virtual environment đã tồn tại"
        fi
        
        print_status "Kích hoạt virtual environment..."
        source venv/bin/activate
        
        PYTHON_CMD="./venv/bin/python"
        PIP_CMD="./venv/bin/pip"
    else
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    fi
}

# Install dependencies
install_dependencies() {
    print_header "Cài đặt Dependencies"
    
    print_status "Cài đặt requests..."
    $PIP_CMD install requests
    
    # Check if python-dotenv is installed and offer to remove it
    if $PIP_CMD list | grep -q python-dotenv; then
        print_warning "Phát hiện python-dotenv (không cần thiết cho phiên bản mới)"
        read -p "Bạn có muốn gỡ python-dotenv không? [y/N]: " remove_dotenv
        if [[ $remove_dotenv =~ ^[Yy]$ ]]; then
            $PIP_CMD uninstall python-dotenv -y
            print_status "Đã gỡ python-dotenv"
        fi
    fi
    
    print_status "Dependencies đã được cài đặt"
}

# Create config file
create_config() {
    print_header "Tạo File Cấu Hình"
    
    if [ ! -f "config.json" ]; then
        print_status "Tạo config.json..."
        cat > config.json << 'EOF'
{
    "check_interval": 300,
    "notification_methods": ["email"],
    "email": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "",
        "sender_password": "",
        "recipient_email": ""
    },
    "telegram": {
        "bot_token": "",
        "chat_ids": []
    },
    "discord": {
        "webhook_urls": []
    }
}
EOF
        print_status "Đã tạo config.json mẫu"
    else
        print_warning "config.json đã tồn tại, bỏ qua tạo mới"
    fi
}

# Create systemd service
create_systemd_service() {
    print_header "Tạo Systemd Service"
    
    if [ "$USE_VENV" = true ]; then
        EXEC_START="$PWD/venv/bin/python $PWD/main.py"
    else
        EXEC_START="/usr/bin/python3 $PWD/main.py"
    fi
    
    print_status "Tạo systemd service file..."
    sudo tee /etc/systemd/system/ip-monitor.service > /dev/null << EOF
[Unit]
Description=IP Monitor Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=$EXEC_START
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    print_status "Systemd service đã được tạo"
}

# Create utility scripts
create_utility_scripts() {
    print_header "Tạo Utility Scripts"
    
    # Start script
    print_status "Tạo start.sh..."
    if [ "$USE_VENV" = true ]; then
        cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python main.py
EOF
    else
        cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 main.py
EOF
    fi
    chmod +x start.sh
    
    # Stop script
    print_status "Tạo stop.sh..."
    cat > stop.sh << 'EOF'
#!/bin/bash
if systemctl is-active --quiet ip-monitor; then
    sudo systemctl stop ip-monitor
    echo "✅ Đã dừng IP Monitor service"
else
    pkill -f main.py && echo "✅ Đã dừng IP Monitor process" || echo "❌ Không tìm thấy process đang chạy"
fi
EOF
    chmod +x stop.sh
    
    # Check IP script
    print_status "Tạo check_ip.sh..."
    if [ "$USE_VENV" = true ]; then
        cat > check_ip.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python main.py --check-ip
EOF
    else
        cat > check_ip.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 main.py --check-ip
EOF
    fi
    chmod +x check_ip.sh
    
    # Status script
    print_status "Tạo status.sh..."
    cat > status.sh << 'EOF'
#!/bin/bash
echo "🔍 === IP Monitor Bot Status ==="
echo ""

# Check if service is running
if systemctl is-active --quiet ip-monitor; then
    echo "✅ Service: RUNNING"
    echo "📊 Service status:"
    systemctl status ip-monitor --no-pager -l
else
    echo "❌ Service: STOPPED"
    
    # Check if running manually
    if pgrep -f main.py > /dev/null; then
        echo "⚠️  Manual process: RUNNING"
        echo "📊 Process info:"
        ps aux | grep main.py | grep -v grep
    else
        echo "❌ Manual process: NOT RUNNING"
    fi
fi

echo ""
echo "📁 Files:"
ls -la *.py *.json *.sh 2>/dev/null || echo "No files found"

echo ""
echo "📝 Recent logs:"
if [ -f "ip_monitor.log" ]; then
    tail -5 ip_monitor.log
else
    echo "No log file found"
fi
EOF
    chmod +x status.sh
    
    # Management script
    print_status "Tạo manage.sh..."
    if [ "$USE_VENV" = true ]; then
        cat > manage.sh << 'EOF'
#!/bin/bash

PROJECT_DIR="$(dirname "$0")"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"

cd "$PROJECT_DIR"

case "$1" in
    start)
        if systemctl is-active --quiet ip-monitor; then
            echo "⚠️  Service đã chạy"
        else
            sudo systemctl start ip-monitor
            echo "✅ Đã khởi động service"
        fi
        ;;
    stop)
        ./stop.sh
        ;;
    restart)
        sudo systemctl restart ip-monitor
        echo "🔄 Đã khởi động lại service"
        ;;
    status)
        ./status.sh
        ;;
    ip)
        $VENV_PYTHON main.py --check-ip
        ;;
    log)
        if [ -f "ip_monitor.log" ]; then
            tail -f ip_monitor.log
        else
            echo "❌ Không tìm thấy log file"
        fi
        ;;
    config)
        nano config.json
        ;;
    enable)
        sudo systemctl enable ip-monitor
        echo "✅ Đã enable service (tự khởi động cùng hệ thống)"
        ;;
    disable)
        sudo systemctl disable ip-monitor
        echo "❌ Đã disable service"
        ;;
    test)
        echo "🧪 Testing configuration..."
        $VENV_PYTHON main.py --check-ip
        echo "✅ Test completed"
        ;;
    *)
        echo "📖 Usage: $0 {start|stop|restart|status|ip|log|config|enable|disable|test}"
        echo ""
        echo "Commands:"
        echo "  start    - Khởi động service"
        echo "  stop     - Dừng service"
        echo "  restart  - Khởi động lại service"
        echo "  status   - Kiểm tra trạng thái"
        echo "  ip       - Xem IP hiện tại"
        echo "  log      - Xem log real-time"
        echo "  config   - Chỉnh sửa cấu hình"
        echo "  enable   - Enable auto-start"
        echo "  disable  - Disable auto-start"
        echo "  test     - Test cấu hình"
        ;;
esac
EOF
    else
        cat > manage.sh << 'EOF'
#!/bin/bash

PROJECT_DIR="$(dirname "$0")"

cd "$PROJECT_DIR"

case "$1" in
    start)
        if systemctl is-active --quiet ip-monitor; then
            echo "⚠️  Service đã chạy"
        else
            sudo systemctl start ip-monitor
            echo "✅ Đã khởi động service"
        fi
        ;;
    stop)
        ./stop.sh
        ;;
    restart)
        sudo systemctl restart ip-monitor
        echo "🔄 Đã khởi động lại service"
        ;;
    status)
        ./status.sh
        ;;
    ip)
        python3 main.py --check-ip
        ;;
    log)
        if [ -f "ip_monitor.log" ]; then
            tail -f ip_monitor.log
        else
            echo "❌ Không tìm thấy log file"
        fi
        ;;
    config)
        nano config.json
        ;;
    enable)
        sudo systemctl enable ip-monitor
        echo "✅ Đã enable service (tự khởi động cùng hệ thống)"
        ;;
    disable)
        sudo systemctl disable ip-monitor
        echo "❌ Đã disable service"
        ;;
    test)
        echo "🧪 Testing configuration..."
        python3 main.py --check-ip
        echo "✅ Test completed"
        ;;
    *)
        echo "📖 Usage: $0 {start|stop|restart|status|ip|log|config|enable|disable|test}"
        echo ""
        echo "Commands:"
        echo "  start    - Khởi động service"
        echo "  stop     - Dừng service"
        echo "  restart  - Khởi động lại service"
        echo "  status   - Kiểm tra trạng thái"
        echo "  ip       - Xem IP hiện tại"
        echo "  log      - Xem log real-time"
        echo "  config   - Chỉnh sửa cấu hình"
        echo "  enable   - Enable auto-start"
        echo "  disable  - Disable auto-start"
        echo "  test     - Test cấu hình"
        ;;
esac
EOF
    fi
    chmod +x manage.sh
    
    print_status "Đã tạo tất cả utility scripts"
}

# Test installation
test_installation() {
    print_header "Kiểm Tra Cài Đặt"
    
    if [ ! -f "main.py" ]; then
        print_error "Không tìm thấy main.py. Vui lòng tạo file main.py với code bot."
        return 1
    fi
    
    print_status "Kiểm tra IP hiện tại..."
    if $PYTHON_CMD main.py --check-ip 2>/dev/null; then
        print_status "✅ Bot hoạt động bình thường"
    else
        print_warning "⚠️  Không thể lấy IP (có thể do chưa có main.py hoặc lỗi mạng)"
    fi
}

# Display final instructions
show_final_instructions() {
    print_header "Cài Đặt Hoàn Tất!"
    echo ""
    
    print_status "📁 Các file đã tạo:"
    echo "   • config.json      - File cấu hình chính"
    echo "   • start.sh         - Khởi động thủ công"
    echo "   • stop.sh          - Dừng bot"
    echo "   • check_ip.sh      - Kiểm tra IP hiện tại"
    echo "   • status.sh        - Kiểm tra trạng thái"
    echo "   • manage.sh        - Script quản lý tổng hợp"
    
    if [ "$USE_VENV" = true ]; then
        echo "   • venv/            - Virtual environment"
    fi
    
    echo ""
    print_status "📋 Các bước tiếp theo:"
    echo "   1. Tạo file main.py với code bot"
    echo "   2. Chỉnh sửa cấu hình: nano config.json"
    echo "   3. Test bot: ./check_ip.sh"
    echo "   4. Khởi động bot:"
    echo "      • Thủ công: ./start.sh"
    echo "      • Service: ./manage.sh start"
    echo "      • Auto-start: ./manage.sh enable"
    
    echo ""
    print_status "🛠️  Quản lý bot:"
    echo "   • ./manage.sh status   - Kiểm tra trạng thái"
    echo "   • ./manage.sh log      - Xem log"
    echo "   • ./manage.sh config   - Chỉnh sửa cấu hình"
    echo "   • ./manage.sh test     - Test cấu hình"
    
    echo ""
    if [ -f "main.py" ]; then
        print_status "🌐 IP hiện tại của bạn:"
        $PYTHON_CMD main.py --check-ip 2>/dev/null || echo "   Không thể lấy IP"
    else
        print_warning "⚠️  Cần tạo file main.py trước khi chạy bot"
    fi
    
    echo ""
    print_status "🎉 Cài đặt thành công!"
}

# Main installation flow
main() {
    print_header "Bắt đầu cài đặt"
    
    # Check prerequisites
    check_python
    
    # Choose installation method
    choose_installation_method
    
    # Setup environment
    setup_venv
    
    # Install dependencies
    install_dependencies
    
    # Create configuration
    create_config
    
    # Create systemd service
    create_systemd_service
    
    # Create utility scripts
    create_utility_scripts
    
    # Test installation
    test_installation
    
    # Show final instructions
    show_final_instructions
}

# Run main function
main "$@"