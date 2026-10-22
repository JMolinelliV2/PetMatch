"""Private release checks; optional explicit operator email, never an automatic bulk send."""
import argparse
from email.message import EmailMessage
import json
import time
from redis import Redis
from app.core.config import settings
from app.routers.operations import readiness
from app.ops.ai_health import ai_readiness
from app.ops.backup_status import read_status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-test-email",metavar="OPERATOR_EMAIL")
    args=parser.parse_args()
    checks={**readiness(),**ai_readiness()}
    with Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2) as redis:
        last=float(redis.get("mascomatch:backup:last_success") or 0)
        status=read_status()
        checks["backup_recent"]=0<=time.time()-last<=max(28800,status["local_interval"]+7200)
    checks["smtp_configured"]=settings.mail_delivery_mode=="smtp" and bool(settings.smtp_username) and bool(settings.smtp_password.get_secret_value())
    if args.send_test_email:
        import re
        target=args.send_test_email.strip().lower()
        if len(target)>320 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",target):
            parser.error("Provide a valid operator email address")
        from app.notifications.email import send_message
        message=EmailMessage()
        message["From"]=settings.smtp_from
        message["To"]=target
        message["Subject"]="MascoMatch · comprobación de correo"
        message.set_content("Este correo fue solicitado por la administración para comprobar la configuración de MascoMatch.")
        send_message(message)
        checks["smtp_accepted_test"]=True
    print(json.dumps({"ready":all(checks.values()),"checks":checks,"backups":read_status()}))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__=="__main__":
    main()
