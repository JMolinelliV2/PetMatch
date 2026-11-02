"""Read-only Mercado Pago configuration check. Never prints credentials or payer details."""
import argparse
import json

from app.core.config import settings
from app.payments import MercadoPago, PaymentError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect-account", "check"])
    args = parser.parse_args()
    if len(settings.mp_access_token.get_secret_value()) < 20:
        parser.error("Configure the private Access Token first; keep MP_ENABLED=false during setup")
    try:
        account = MercadoPago().request("GET", "/users/me")
    except PaymentError as exc:
        print(json.dumps({"ok": False, "code": exc.code}))
        raise SystemExit(1) from None
    identity, site = str(account.get("id", "")), account.get("site_id")
    if args.action == "inspect-account":
        print(json.dumps({"collector_id": identity, "site_id": site, "environment_selected": settings.mp_environment}))
        return
    checks = {"configuration_complete": settings.mp_configured,
        "collector_matches": identity == settings.mp_collector_id, "uruguay_account": site == "MLU"}
    print(json.dumps({"ok": all(checks.values()), "checks": checks,
        "new_checkouts_enabled": settings.mp_enabled, "environment": settings.mp_environment,
        "webhook_url": settings.mp_public_base_url.rstrip("/") + "/api/payments/mercadopago/webhook"}))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
