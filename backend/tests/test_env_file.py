import os

from app.env_file import load_env_file, parse_env


def test_parse_env_basico():
    pares = parse_env("A=1\nB = dos\n")
    assert pares == {"A": "1", "B": "dos"}


def test_parse_env_ignora_comentarios_y_blancos():
    texto = "# comentario\n\n  # otro\nX=valor\n"
    assert parse_env(texto) == {"X": "valor"}


def test_parse_env_admite_export_y_comillas():
    texto = 'export TOKEN="ab:cd"\nNAME=\'Ramon\'\n'
    assert parse_env(texto) == {"TOKEN": "ab:cd", "NAME": "Ramon"}


def test_parse_env_separa_por_primer_igual():
    assert parse_env("URL=http://x/?a=b") == {"URL": "http://x/?a=b"}


def test_load_env_file_inexistente_no_falla(tmp_path):
    assert load_env_file(tmp_path / "no.env") == {}


def test_load_env_file_rellena_environ(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("MI_VAR_TEST=hola\n", encoding="utf-8")
    monkeypatch.delenv("MI_VAR_TEST", raising=False)
    aplicados = load_env_file(f)
    assert aplicados == {"MI_VAR_TEST": "hola"}
    assert os.environ["MI_VAR_TEST"] == "hola"


def test_load_env_file_no_pisa_entorno_existente(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("MI_VAR_TEST=delfichero\n", encoding="utf-8")
    monkeypatch.setenv("MI_VAR_TEST", "delentorno")
    aplicados = load_env_file(f)
    assert aplicados == {}
    assert os.environ["MI_VAR_TEST"] == "delentorno"


def test_load_env_file_override(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("MI_VAR_TEST=delfichero\n", encoding="utf-8")
    monkeypatch.setenv("MI_VAR_TEST", "delentorno")
    aplicados = load_env_file(f, override=True)
    assert aplicados == {"MI_VAR_TEST": "delfichero"}
    assert os.environ["MI_VAR_TEST"] == "delfichero"
