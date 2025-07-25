from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from smtplib import SMTPException

from django.conf import settings
from django.template import Context, Template
from django.utils.html import escape

from trade_smart.models import Portfolio

logger = logging.getLogger(__name__)


class EmailNotificationService:
    def __init__(self):
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.smtp_port = settings.SMTP_PORT
        self.smtp_server_host = settings.SMTP_SERVER_HOST

    def send_advice_email(self, portfolio: Portfolio):
        advices = portfolio.advices.select_related().all()
        advice_rows = ""
        for adv in advices:
            advice_rows += f"""
            <tr>
                <td>{escape(adv.ticker) if adv.ticker else "Whole Portfolio"}</td>
                <td>{escape(adv.action)}</td>
                <td>{float(adv.confidence):.2f}</td>
                <td>{escape(adv.rationale)}</td>
            </tr>
            """

        html_body = f"""
        <html>
            <body>
                <p>Dear Investor,</p>
                <p>Please review the latest advice for your portfolio <b>{escape(portfolio.name)}</b>:</p>
                <table border="1" cellpadding="5" cellspacing="0">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th>Action</th>
                            <th>Confidence</th>
                            <th>Rationale</th>
                        </tr>
                    </thead>
                    <tbody>
                        {advice_rows}
                    </tbody>
                </table>
                <p>Regards,</p>
                <p>WiseTrade Team</p>
            </body>
        </html>
        """
        recipients = [portfolio.user.email]
        to = portfolio.user.email
        cc = ""

        self._send_email(
            subject=f"Investment Advice for {portfolio.user.username}",
            body=html_body,
            recipient_emails=recipients,
            to=to,
            cc=cc,
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
