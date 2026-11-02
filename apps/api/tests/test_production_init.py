import importlib.util
from pathlib import Path
import pytest


def initializer():
    path=next((parent/"tools"/"production_init.py" for parent in Path(__file__).resolve().parents if (parent/"tools"/"production_init.py").is_file()),None)
    if path is None:
        pytest.skip("Operator tooling is tested from the repository root")
    spec=importlib.util.spec_from_file_location("production_init",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.initialize


def test_private_deployment_generation_does_not_replace_keys(tmp_path):
    initialize=initializer()
    initialize(tmp_path)
    before=(tmp_path/".secrets"/"jwt_secret").read_text()
    assert len(before.strip())>=48
    assert "MAIL_DELIVERY_MODE=disabled" in (tmp_path/".env.production").read_text()
    assert before.strip() not in (tmp_path/".env.production").read_text()
    with pytest.raises(FileExistsError):initialize(tmp_path)
    assert (tmp_path/".secrets"/"jwt_secret").read_text()==before


def test_deployment_domain_cannot_inject_configuration(tmp_path):
    with pytest.raises(ValueError):initializer()(tmp_path,"mascomatch.com\nSMTP_PASSWORD=unexpected")


def test_payment_secrets_are_empty_private_and_never_replaced(tmp_path):
    initialize = initializer()
    initialize(tmp_path)
    config = (tmp_path / ".env.production").read_text()
    assert "MP_ENABLED=false" in config and "MP_ENVIRONMENT=test" in config
    secret = tmp_path / ".secrets" / "mp_access_token"
    assert secret.read_text().strip() == ""
    secret.chmod(0o600)
    secret.write_text("already-installed-private-test-key")
    initialize.__globals__["prepare_payment_secrets"](tmp_path)
    assert secret.read_text() == "already-installed-private-test-key"
    assert "already-installed-private-test-key" not in config
