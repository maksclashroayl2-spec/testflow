import resend
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        resend.api_key = None

    def open(self):
        import os
        resend.api_key = os.getenv("RESEND_API_KEY")
        return True

    def close(self):
        pass

    def send_messages(self, email_messages):
        if not resend.api_key:
            self.open()

        sent = 0
        for message in email_messages:
            try:
                resend.Emails.send({
                    "from": message.from_email,
                    "to": message.to,
                    "subject": message.subject,
                    "text": message.body,
                })
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
