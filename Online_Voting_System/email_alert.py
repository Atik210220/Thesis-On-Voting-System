# email_alert.py
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings

def send_email_smtp_direct(recipients, subject, body):

    if not recipients:
        return False, "no recipients"

    smtp_host = getattr(settings, "EMAIL_HOST", "smtp.gmail.com")
    smtp_port = getattr(settings, "EMAIL_PORT", 587)
    use_tls = getattr(settings, "EMAIL_USE_TLS", True)
    username = getattr(settings, "EMAIL_HOST_USER", None)
    password = getattr(settings, "EMAIL_HOST_PASSWORD", None)
    from_addr = getattr(settings, "DEFAULT_FROM_EMAIL", username)

    if not username or not password:
        return False, "missing EMAIL_HOST_USER or EMAIL_HOST_PASSWORD in settings"

    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        context = ssl.create_default_context()
        # Use SMTP + STARTTLS (port 587)
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.ehlo()
        if use_tls:
            server.starttls(context=context)
            server.ehlo()
        server.login(username, password)
        server.sendmail(from_addr, recipients, msg.as_string())
        server.quit()
        return True, "sent"
    except Exception as e:
        return False, str(e)
