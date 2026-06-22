import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_USE_TLS,
    SMTP_USE_SSL,
    ADMIN_EMAIL,
    APP_BASE_URL,
)
from app.logger import get_logger

logger = get_logger(__name__)


def send_incident_email_notification(incident_id: int, issue_description: str, priority_label: str, reported_by: str, requester_department: str, device_user: str, device_location: str):
    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD or not ADMIN_EMAIL:
        logger.info("SMTP configuration is not fully set. Skipping email notification.")
        return

    try:
        # Prepare message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[IT Asset Hub] SỰ CỐ MỚI #{incident_id} - Ưu tiên: {priority_label}"
        msg['From'] = SMTP_USERNAME
        msg['To'] = ADMIN_EMAIL  # This can be a comma-separated string for display
        
        # Extract email list for SMTP RCPT TO
        admin_emails = [email.strip() for email in ADMIN_EMAIL.split(',') if email.strip()]

        # Detail link
        detail_url = f"{APP_BASE_URL}/incidents/{incident_id}"

        # HTML Body
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #f8fafc; }}
                .header {{ background-color: #e11d48; color: white; padding: 15px; border-radius: 8px 8px 0 0; font-weight: bold; text-align: center; font-size: 18px; }}
                .content {{ padding: 20px; background-color: white; border-radius: 0 0 8px 8px; border: 1px solid #f1f5f9; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                td {{ padding: 10px; border-bottom: 1px solid #f1f5f9; }}
                td.label {{ font-weight: bold; width: 40%; color: #475569; }}
                td.value {{ color: #0f172a; }}
                .desc-box {{ background-color: #f1f5f9; padding: 15px; border-radius: 8px; margin-top: 15px; white-space: pre-wrap; font-style: italic; border-left: 4px solid #cbd5e1; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #e11d48; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 20px; text-align: center; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 11px; color: #94a3b8; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    Sự Cố IT Mới Được Báo Cáo
                </div>
                <div class="content">
                    <p>Chào Ban Quản Trị IT,</p>
                    <p>Hệ thống vừa tiếp nhận một báo cáo sự cố mới <strong>#INC-{incident_id:04d}</strong>. Vui lòng kiểm tra và xử lý.</p>
                    
                    <table>
                        <tr>
                            <td class="label">Mã ticket:</td>
                            <td class="value">INC-{incident_id:04d}</td>
                        </tr>
                        <tr>
                            <td class="label">Người báo sự cố:</td>
                            <td class="value">{reported_by or "Không xác định"}</td>
                        </tr>
                        <tr>
                            <td class="label">Phòng ban yêu cầu:</td>
                            <td class="value">{requester_department or "Không xác định"}</td>
                        </tr>
                        <tr>
                            <td class="label">Người sử dụng thiết bị:</td>
                            <td class="value">{device_user or "Không rõ"}</td>
                        </tr>
                        <tr>
                            <td class="label">Khu vực sử dụng:</td>
                            <td class="value">{device_location or "Không rõ"}</td>
                        </tr>
                        <tr>
                            <td class="label">Mức độ ưu tiên:</td>
                            <td class="value"><span style="color: #e11d48; font-weight: bold;">{priority_label}</span></td>
                        </tr>
                    </table>

                    <div style="font-weight: bold; margin-top: 20px; color: #475569;">Nội dung yêu cầu / Mô tả lỗi:</div>
                    <div class="desc-box">{issue_description}</div>

                    <div style="text-align: center;">
                        <a href="{detail_url}" class="button" style="color: white;">Xem chi tiết trên IT Asset Hub</a>
                    </div>
                </div>
                <div class="footer">
                    Email tự động gửi từ hệ thống IT Asset Hub. Vui lòng không trả lời email này.
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html'))

        # Send mail
        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            if SMTP_USE_TLS:
                server.starttls()
        
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, admin_emails, msg.as_string())
        server.quit()
        logger.info(f"Successfully sent incident email notification for ticket #{incident_id} to {', '.join(admin_emails)}")
    except Exception as e:
        logger.exception(f"Failed to send email notification for incident #{incident_id}: {str(e)}")
