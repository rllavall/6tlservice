from app import notificaciones


def test_email_none_sin_smtp(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert notificaciones.enviar_email("a", "b") is None


def test_email_true_con_transporte(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("NOTIF_EMAIL_TO", "a@x.com, b@x.com")
    enviados = []
    assert notificaciones.enviar_email("Asunto", "Cuerpo", transporte=lambda msg, cfg: enviados.append(msg)) is True
    assert enviados and enviados[0]["To"] == "a@x.com, b@x.com"
    assert enviados[0]["Subject"] == "Asunto"


def test_email_false_si_transporte_lanza(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("NOTIF_EMAIL_TO", "a@x.com")
    def boom(msg, cfg):
        raise RuntimeError("smtp down")
    assert notificaciones.enviar_email("a", "b", transporte=boom) is False


def test_telegram_none_sin_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert notificaciones.enviar_telegram("hola") is None


def test_telegram_true_con_http_post(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    capt = []
    assert notificaciones.enviar_telegram("hola", http_post=lambda t, c, txt: capt.append((t, c, txt))) is True
    assert capt == [("tok", "123", "hola")]


def test_notificar_dispara_ambos():
    r = notificaciones.notificar("As", "Cu",
        email_fn=lambda a, c: True, telegram_fn=lambda txt: None)
    assert r == {"email": True, "telegram": None}
