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

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ip_monitor.log"), logging.StreamHandler()],
)


class IPMonitor:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.current_ip = None
        self.ip_file = "current_ip.txt"

    def load_config(self):
        """Tải cấu hình từ file JSON"""
        default_config = {
            "check_interval": 300,
            "notification_methods": ["email"],
            "email": {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "",
                "sender_password": "",
                "recipient_email": "",
            },
            "telegram": {"bot_token": "", "chat_ids": []},
            "discord": {"webhook_urls": []},
        }

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                file_config = json.load(f)

                # Merge file config với default config
                config = default_config.copy()
                for key, value in file_config.items():
                    if key in config:
                        if isinstance(value, dict) and isinstance(config[key], dict):
                            # Merge nested dictionaries
                            config[key].update(value)
                        else:
                            config[key] = value
                    else:
                        config[key] = value

                return config

        except FileNotFoundError:
            logging.info(
                f"File cấu hình {self.config_file} không tồn tại. Tạo file mới."
            )
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            return default_config
        except json.JSONDecodeError as e:
            logging.error(f"Lỗi định dạng JSON trong file {self.config_file}: {e}")
            return default_config

    def get_public_ip(self):
        """Lấy IP public hiện tại"""
        services = [
            "https://api.ipify.org?format=json",
            "https://httpbin.org/ip",
            "https://api.myip.com",
            "https://ipapi.co/json",
        ]

        for service in services:
            try:
                response = requests.get(service, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Xử lý response khác nhau từ các service
                if "ip" in data:
                    return data["ip"]
                elif "origin" in data:
                    return data["origin"]
                elif "query" in data:
                    return data["query"]

            except Exception as e:
                logging.warning(f"Không thể lấy IP từ {service}: {e}")
                continue

        raise Exception("Không thể lấy IP public từ tất cả các service")

    def load_previous_ip(self):
        """Tải IP trước đó từ file"""
        try:
            with open(self.ip_file, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    def save_current_ip(self, ip):
        """Lưu IP hiện tại vào file"""
        with open(self.ip_file, "w") as f:
            f.write(ip)

    def send_email_notification(self, old_ip, new_ip):
        """Gửi thông báo qua email"""
        try:
            email_config = self.config["email"]

            if not email_config.get("sender_email") or not email_config.get(
                "sender_password"
            ):
                logging.warning("Email không được cấu hình đầy đủ")
                return

            msg = MIMEMultipart()
            msg["From"] = email_config["sender_email"]
            msg["To"] = email_config["recipient_email"]
            msg["Subject"] = (
                f"Thay đổi IP Public - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            body = f"""
                        Xin chào!

                        IP public của bạn đã thay đổi:
                        • IP cũ: {old_ip or 'Không xác định'}
                        • IP mới: {new_ip}
                        • Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

                        Bot IP Monitor
                    """

            msg.attach(MIMEText(body, "plain", "utf-8"))

            server = smtplib.SMTP(
                email_config["smtp_server"], email_config["smtp_port"]
            )
            server.starttls()
            server.login(email_config["sender_email"], email_config["sender_password"])
            server.send_message(msg)
            server.quit()

            logging.info("Đã gửi thông báo email thành công")

        except Exception as e:
            logging.error(f"Lỗi khi gửi email: {e}")

    def send_telegram_notification(self, old_ip, new_ip):
        """Gửi thông báo qua Telegram đến multiple chat IDs"""
        try:
            telegram_config = self.config["telegram"]
            bot_token = telegram_config.get("bot_token")

            if not bot_token:
                logging.warning("Telegram bot token không được cấu hình")
                return

            chat_ids = telegram_config.get("chat_ids", [])
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
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    }

                    response = requests.post(url, data=data, timeout=10)
                    response.raise_for_status()
                    success_count += 1
                    logging.info(
                        f"Đã gửi thông báo Telegram thành công đến chat ID: {chat_id}"
                    )

                except Exception as e:
                    logging.error(f"Lỗi khi gửi Telegram đến chat ID {chat_id}: {e}")

            if success_count > 0:
                logging.info(
                    f"Đã gửi thành công {success_count}/{len(chat_ids)} thông báo Telegram"
                )

        except Exception as e:
            logging.error(f"Lỗi khi gửi Telegram: {e}")

    def send_discord_notification(self, old_ip, new_ip):
        """Gửi thông báo qua Discord đến multiple webhooks"""
        try:
            discord_config = self.config["discord"]
            webhook_urls = discord_config.get("webhook_urls", [])

            if not webhook_urls:
                logging.warning("Không có webhook URL nào được cấu hình cho Discord")
                return

            embed = {
                "title": "🔄 Thay đổi IP Public",
                "color": 0x00FF00,
                "fields": [
                    {
                        "name": "IP cũ",
                        "value": old_ip or "Không xác định",
                        "inline": True,
                    },
                    {"name": "IP mới", "value": new_ip, "inline": True},
                    {
                        "name": "Thời gian",
                        "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "inline": False,
                    },
                ],
                "timestamp": datetime.now().isoformat(),
            }

            data = {"embeds": [embed]}

            success_count = 0
            for webhook_url in webhook_urls:
                try:
                    response = requests.post(webhook_url, json=data, timeout=10)
                    response.raise_for_status()
                    success_count += 1
                    # Log webhook URL một cách an toàn (chỉ hiển thị phần cuối)
                    masked_url = (
                        f"...{webhook_url[-20:]}"
                        if len(webhook_url) > 20
                        else webhook_url
                    )
                    logging.info(
                        f"Đã gửi thông báo Discord thành công đến webhook: {masked_url}"
                    )

                except Exception as e:
                    masked_url = (
                        f"...{webhook_url[-20:]}"
                        if len(webhook_url) > 20
                        else webhook_url
                    )
                    logging.error(f"Lỗi khi gửi Discord đến webhook {masked_url}: {e}")

            if success_count > 0:
                logging.info(
                    f"Đã gửi thành công {success_count}/{len(webhook_urls)} thông báo Discord"
                )

        except Exception as e:
            logging.error(f"Lỗi khi gửi Discord: {e}")

    def send_notifications(self, old_ip, new_ip):
        """Gửi thông báo qua tất cả các phương thức được cấu hình"""
        methods = self.config.get("notification_methods", [])

        for method in methods:
            if method == "email":
                self.send_email_notification(old_ip, new_ip)
            elif method == "telegram":
                self.send_telegram_notification(old_ip, new_ip)
            elif method == "discord":
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
                    logging.info(
                        f"Phát hiện thay đổi IP: {previous_ip} -> {current_ip}"
                    )

                    # Gửi thông báo
                    self.send_notifications(previous_ip, current_ip)

                    # Cập nhật IP
                    self.save_current_ip(current_ip)
                    previous_ip = current_ip

                # Chờ đến lần kiểm tra tiếp theo
                time.sleep(self.config["check_interval"])

            except KeyboardInterrupt:
                logging.info("Dừng bot theo yêu cầu người dùng")
                break
            except Exception as e:
                logging.error(f"Lỗi trong quá trình theo dõi: {e}")
                time.sleep(60)  # Chờ 1 phút trước khi thử lại


def main():
    """Hàm main"""
    import argparse

    parser = argparse.ArgumentParser(
        description="IP Monitor Bot - Theo dõi thay đổi IP public"
    )
    parser.add_argument(
        "--config", default="config.json", help="File cấu hình (mặc định: config.json)"
    )
    parser.add_argument(
        "--check-ip", action="store_true", help="Chỉ kiểm tra IP hiện tại và thoát"
    )

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
