from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from smtplib import SMTPException

from django.conf import settings
from django.template import Context, Template
from django.utils.html import escape

logger = logging.getLogger(__name__)


class EmailNotificationService:
    def __init__(self):
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.smtp_port = settings.SMTP_PORT
        self.smtp_server_host = settings.SMTP_SERVER_HOST

    def send_advice_email(self, gift):

        self._send_email(
            subject=subject,
            body=html_body,
            recipient_emails=recipients,
            to=to,
            cc=cc if cc else "",
            html_body=True,
        )

    def _send_email(
        self,
        subject: str,
        body: str,
        recipient_emails: list[str],
        to: str,
        cc: str,
        html_body=False,
    ):
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = to
            msg["Subject"] = subject
            msg["Cc"] = cc

            recipients = recipient_emails

            if html_body:
                msg.attach(MIMEText(body, "html", "utf-8"))
            else:
                msg.attach(MIMEText(body, "plain", "utf-8"))

            server = smtplib.SMTP(self.smtp_server_host, self.smtp_port)
            server.starttls()
            server.login(self.from_email, self.smtp_password)

            server.sendmail(self.from_email, recipients, msg.as_string())
            server.quit()
            logger.info("Email sent successfully")

        except SMTPException as e:
            logger.error(f"Failed to send email: {e}")
