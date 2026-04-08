import logging
import httpx
from datetime import datetime

from app.config import ZALO_BOT_URL, ZALO_BOT_TOKEN, ZALO_NOTIFICATION_TARGET

logger = logging.getLogger(__name__)

async def send_zalo_notification(title: str, description: str, **kwargs):
    """
    Hàm tĩnh thực hiện gửi thông báo qua Zalo bot thông qua giao thức HTTP/REST.
    Chạy bất đồng bộ (async). Nên đưa vào BackgroundTasks của FastAPI.
    """
    if not ZALO_BOT_URL or not ZALO_BOT_TOKEN or not ZALO_NOTIFICATION_TARGET:
        logger.warning("Cấu hình Zalo chưa đầy đủ. Bỏ qua gửi thông báo.")
        return False
        
    try:
        # Chuẩn bị nội dung tin nhắn
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        message_text = f"📢 **[{title}]**\n"
        message_text += f"{description}\n"
        message_text += f"---\nThời gian: {now_str}"
        
        # Nếu có thêm tham số metadata như Mã sự cố, Người báo...
        if kwargs:
            message_text += "\n\nChi tiết:"
            for k, v in kwargs.items():
                message_text += f"\n- {k}: {v}"
                
        # API Payload có thể cần thay đổi tuỳ vào chuẩn của hệ thống Zalo bạn tạo
        # Hiện tại setup chung theo dạng OA: POST request với Header chứa Token
        headers = {
            "Content-Type": "application/json",
            "access_token": ZALO_BOT_TOKEN,
            "Authorization": f"Bearer {ZALO_BOT_TOKEN}"
        }
        
        # Tùy biến payload. Nếu Zalo cung cấp Webhook, đôi khi payload là `{"text": message_text}`
        payload = {
            "recipient": {
                "user_id": ZALO_NOTIFICATION_TARGET
            },
            "message": {
                "text": message_text
            }
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                ZALO_BOT_URL,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"Đã gửi thông báo Zalo thành công. Trạng thái: {response.status_code}")
            return True
            
    except Exception as e:
        logger.error(f"Lỗi khi gửi thông báo Zalo: {str(e)}")
        return False
