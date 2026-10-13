import logging
import httpx
from datetime import datetime

from app.config import TEAMS_WEBHOOK_URL

logger = logging.getLogger(__name__)

async def send_teams_notification(title: str, description: str, **kwargs):
    """
    Hàm tĩnh thực hiện gửi thông báo qua Microsoft Teams Webhook.
    Chạy bất đồng bộ (async). Nên đưa vào BackgroundTasks của FastAPI.
    """
    if not TEAMS_WEBHOOK_URL:
        logger.warning("Chưa cấu hình TEAMS_WEBHOOK_URL. Bỏ qua gửi thông báo Teams.")
        return False
        
    try:
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # Xây dựng các facts cho Adaptive Card
        facts = [{"title": "Thời gian:", "value": now_str}]
        for k, v in kwargs.items():
            formatted_key = str(k).replace('_', ' ') + ":"
            facts.append({"title": formatted_key, "value": str(v)})

        # Adaptive Card format cho Power Automate Workflows mới của Teams
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": f"📢 **{title}**",
                                "weight": "Bolder",
                                "size": "Medium"
                            },
                            {
                                "type": "TextBlock",
                                "text": description,
                                "wrap": True
                            },
                            {
                                "type": "FactSet",
                                "facts": facts
                            }
                        ]
                    }
                }
            ]
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                TEAMS_WEBHOOK_URL,
                json=payload
            )
            response.raise_for_status()
            logger.info(f"Đã gửi thông báo Teams thành công.")
            return True
            
    except Exception as e:
        logger.error(f"Lỗi khi gửi thông báo Teams: {str(e)}")
        return False
