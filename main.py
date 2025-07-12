#!/usr/bin/env python3
"""
IP Monitor Bot - Theo dõi thay đổi IP public
Hỗ trợ thông báo qua email, Telegram, và Discord
"""

import requests
import time
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from dotenv import load_dotenv

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ip_monitor.log'),
        logging.StreamHandler()
    ]
)

class IPMonitor:
    def __init__(self, config_file='config.json'):
        # Load environment variables
        load_dotenv()
        
        self.config_file = config_file
        self.config = self.load_config()
        self.current_ip = None
        self.ip_file = 'current_ip.txt'
        
    def load_config(self):
        """Tải cấu hình từ file JSON và environment variables"""
        default_config = {
            "check_interval": int(os.getenv("CHECK_INTERVAL", 300)),
            "notification_methods": os.getenv("NOTIFICATION_METHODS", "email").split(","),
            "email": {
                "smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", 587)),
                "sender_email": os.getenv("EMAIL_SENDER", ""),
                "sender_password": os.getenv("EMAIL_PASSWORD", ""),
                "recipient_email": os.getenv("EMAIL_RECIPIENT", "")
            },
            "telegram": {
                "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
                "chat_ids": self._parse_chat_ids(os.getenv("TELEGRAM_CHAT_IDS", "")),
                "chat_id": os.getenv("TELEGRAM_CHAT_ID", "")  # Backward compatibility
            },
            "discord": {
                "webhook_urls": self._parse_webhook_urls(os.getenv("DISCORD_WEBHOOK_URLS", "")),
                "webhook_url": os.getenv("DISCORD_WEBHOOK_URL", "")  # Backward compatibility
            }
        }
        
        try:
            with open(self.config_file, 'r') as f:
                file_config = json.load(f)
                
                # Merge file config with env config, prioritizing env variables
                config = default_config.copy()
                for key, value in file_config.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict) and isinstance(config[key], dict):
                        # Merge nested dictionaries
                        for sub_key, sub_value in value.items():
                            if sub_key not in config[key] or not config[key][sub_key]:
                                config[key][sub_key] = sub_value
                    elif not config[key]:  # Only use file value if env value is empty
                        config[key] = value
                
                return config
        except FileNotFoundError:
            logging.info(f"File cấu hình {self.config_file} không tồn tại. Tạo file mới.")
            with open(self.config_file, 'w') as f:
                json.dump(self._clean_config_for_file(default_config), f, indent=4)
            return default_config
    
    def _parse_chat_ids(self, chat_ids_str):
        """Parse chat IDs từ environment variable"""
        if not chat_ids_str:
            return []
        return [chat_id.strip() for chat_id in chat_ids_str.split(",") if chat_id.strip()]
    
    def _parse_webhook_urls(self, webhook_urls_str):
        """Parse webhook URLs từ environment variable"""
        if not webhook_urls_str:
            return []
        return [url.strip() for url in webhook_urls_str.split(",") if url.strip()]
    
    def _clean_config_for_file(self, config):
        """Remove sensitive info when saving to file"""
        clean_config = config.copy()
        clean_config["email"]["sender_password"] = ""
        clean_config["telegram"]["bot_token"] = ""
        return clean_config
    
    def get_public_ip(self):
        """Lấy IP public hiện tại"""
        services = [
            'https://api.ipify.org?format=json',
            'https://httpbin.org/ip',
            'https://api.myip.com',
            'https://ipapi.co/json'
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Xử lý response khác nhau từ các service
                if 'ip' in data:
                    return data['ip']
                elif 'origin' in data:
                    return data['origin']
                elif 'query' in data:
                    return data['query']
                    
            except Exception as e:
                logging.warning(f"Không thể lấy IP từ {service}: {e}")
                continue
        
        raise Exception("Không thể lấy IP public từ tất cả các service")
    
    def load_previous_ip(self):
        """Tải IP trước đó từ file"""
        try:
            with open(self.ip_file, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return None
    
    def save_current_ip(self, ip):
        """Lưu IP hiện tại vào file"""
        with open(self.ip_file, 'w') as f:
            f.write(ip)
    
    def send_email_notification(self, old_ip, new_ip):
        """Gửi thông báo qua email"""
        try:
            email_config = self.config['email']
            
            msg = MIMEMultipart()
            msg['From'] = email_config['sender_email']
            msg['To'] = email_config['recipient_email']
            msg['Subject'] = f"Thay đổi IP Public - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            body = f"""
Xin chào!

IP public của bạn đã thay đổi:

• IP cũ: {old_ip or 'Không xác định'}
• IP mới: {new_ip}
• Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Bot IP Monitor
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['sender_email'], email_config['sender_password'])
            server.send_message(msg)
            server.quit()
            
            logging.info("Đã gửi thông báo email thành công")
            
        except Exception as e:
            logging.error(f"Lỗi khi gửi email: {e}")
    
    def send_telegram_notification(self, old_ip, new_ip):
        """Gửi thông báo qua Telegram đến multiple chat IDs"""
        try:
            telegram_config = self.config['telegram']
            bot_token = telegram_config.get('bot_token')
            
            if not bot_token:
                logging.warning("Telegram bot token không được cấu hình")
                return
            
            # Lấy danh sách chat IDs (ưu tiên chat_ids, fallback về chat_id)
            chat_ids = telegram_config.get('chat_ids', [])
            if not chat_ids and telegram_config.get('chat_id'):
                chat_ids = [telegram_config.get('chat_id')]
            
            if not chat_ids:
                logging.warning("Không có chat ID nào được cấu hình cho Telegram")
                return
            
            message = f"""
🔄 *Thay đổi IP Public*

• IP cũ: `{old_ip or 'Không xác định'}`
• IP mới: `{new_ip}`
• Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            success_count = 0
            for chat_id in chat_ids:
                try:
                    data = {
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                    
                    response = requests.post(url, data=data, timeout=10)
                    response.raise_for_status()
                    success_count += 1
                    logging.info(f"Đã gửi thông báo Telegram thành công đến chat ID: {chat_id}")
                    
                except Exception as e:
                    logging.error(f"Lỗi khi gửi Telegram đến chat ID {chat_id}: {e}")
            
            if success_count > 0:
                logging.info(f"Đã gửi thành công {success_count}/{len(chat_ids)} thông báo Telegram")
            
        except Exception as e:
            logging.error(f"Lỗi khi gửi Telegram: {e}")
    
    def send_discord_notification(self, old_ip, new_ip):
        """Gửi thông báo qua Discord đến multiple webhooks"""
        try:
            discord_config = self.config['discord']
            
            # Lấy danh sách webhook URLs (ưu tiên webhook_urls, fallback về webhook_url)
            webhook_urls = discord_config.get('webhook_urls', [])
            if not webhook_urls and discord_config.get('webhook_url'):
                webhook_urls = [discord_config.get('webhook_url')]
            
            if not webhook_urls:
                logging.warning("Không có webhook URL nào được cấu hình cho Discord")
                return
            
            embed = {
                "title": "🔄 Thay đổi IP Public",
                "color": 0x00ff00,
                "fields": [
                    {"name": "IP cũ", "value": old_ip or "Không xác định", "inline": True},
                    {"name": "IP mới", "value": new_ip, "inline": True},
                    {"name": "Thời gian", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "inline": False}
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            data = {"embeds": [embed]}
            
            success_count = 0
            for webhook_url in webhook_urls:
                try:
                    response = requests.post(webhook_url, json=data, timeout=10)
                    response.raise_for_status()
                    success_count += 1
                    # Log webhook URL một cách an toàn (chỉ hiển thị phần cuối)
                    masked_url = f"...{webhook_url[-20:]}" if len(webhook_url) > 20 else webhook_url
                    logging.info(f"Đã gửi thông báo Discord thành công đến webhook: {masked_url}")
                    
                except Exception as e:
                    masked_url = f"...{webhook_url[-20:]}" if len(webhook_url) > 20 else webhook_url
                    logging.error(f"Lỗi khi gửi Discord đến webhook {masked_url}: {e}")
            
            if success_count > 0:
                logging.info(f"Đã gửi thành công {success_count}/{len(webhook_urls)} thông báo Discord")
            
        except Exception as e:
            logging.error(f"Lỗi khi gửi Discord: {e}")
    
    def send_notifications(self, old_ip, new_ip):
        """Gửi thông báo qua tất cả các phương thức được cấu hình"""
        methods = self.config.get('notification_methods', [])
        
        for method in methods:
            if method == 'email':
                self.send_email_notification(old_ip, new_ip)
            elif method == 'telegram':
                self.send_telegram_notification(old_ip, new_ip)
            elif method == 'discord':
                self.send_discord_notification(old_ip, new_ip)
    
    def run(self):
        """Chạy bot theo dõi IP"""
        logging.info("Bắt đầu theo dõi IP public...")
        
        # Lấy IP trước đó nếu có
        previous_ip = self.load_previous_ip()
        logging.info(f"IP trước đó: {previous_ip}")
        
        while True:
            try:
                # Lấy IP hiện tại
                current_ip = self.get_public_ip()
                logging.info(f"IP hiện tại: {current_ip}")
                
                # Kiểm tra thay đổi
                if previous_ip != current_ip:
                    logging.info(f"Phát hiện thay đổi IP: {previous_ip} -> {current_ip}")
                    
                    # Gửi thông báo
                    self.send_notifications(previous_ip, current_ip)
                    
                    # Cập nhật IP
                    self.save_current_ip(current_ip)
                    previous_ip = current_ip
                
                # Chờ đến lần kiểm tra tiếp theo
                time.sleep(self.config['check_interval'])
                
            except KeyboardInterrupt:
                logging.info("Dừng bot theo yêu cầu người dùng")
                break
            except Exception as e:
                logging.error(f"Lỗi trong quá trình theo dõi: {e}")
                time.sleep(60)  # Chờ 1 phút trước khi thử lại

def main():
    """Hàm main"""
    import argparse
    
    parser = argparse.ArgumentParser(description='IP Monitor Bot - Theo dõi thay đổi IP public')
    parser.add_argument('--config', default='config.json', help='File cấu hình (mặc định: config.json)')
    parser.add_argument('--check-ip', action='store_true', help='Chỉ kiểm tra IP hiện tại và thoát')
    
    args = parser.parse_args()
    
    monitor = IPMonitor(args.config)
    
    if args.check_ip:
        try:
            ip = monitor.get_public_ip()
            print(f"IP public hiện tại: {ip}")
        except Exception as e:
            print(f"Lỗi khi lấy IP: {e}")
    else:
        monitor.run()

if __name__ == "__main__":
    main()