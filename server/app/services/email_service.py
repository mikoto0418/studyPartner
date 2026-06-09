import smtplib
import asyncio
from email.mime.text import MIMEText
from email.header import Header
from app.config import settings
from app.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def _is_configured() -> bool:
        required_values = [
            settings.SMTP_HOST,
            settings.SMTP_USER,
            settings.SMTP_PASSWORD,
            settings.SMTP_FROM_EMAIL,
        ]
        return all(value and "example.com" not in value and "password_here" not in value for value in required_values)

    @staticmethod
    def _send_email_sync(to_email: str, subject: str, content: str):
        if not EmailService._is_configured():
            raise ValidationError("SMTP 邮件服务未配置完整，验证码无法发送", code="SMTP_NOT_CONFIGURED")

        message = MIMEText(content, 'html', 'utf-8')
        message['From'] = Header(f"{settings.APP_NAME} <{settings.SMTP_FROM_EMAIL}>", 'utf-8')
        message['To'] = Header(to_email, 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')

        try:
            if settings.SMTP_PORT == 465:
                # SSL
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
            else:
                # STARTTLS
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
                server.starttls()
            
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], message.as_string())
            server.quit()
            logger.info(f"Email successfully sent to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
            raise e

    @classmethod
    async def send_verification_code(cls, to_email: str, code: str):
        subject = f"[{settings.APP_NAME}] 验证码"
        content = f"""
        <html>
            <body>
                <h3>您好：</h3>
                <p>您的验证码是：<strong style="color: #4f46e5; font-size: 20px;">{code}</strong></p>
                <p>该验证码在 5 分钟内有效，请勿泄露给他人。</p>
                <br/>
                <p>此邮件为系统自动发出，请勿回复。</p>
            </body>
        </html>
        """
        await asyncio.to_thread(cls._send_email_sync, to_email, subject, content)
