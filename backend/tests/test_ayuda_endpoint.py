def test_put_crea_y_get_uno(client):
    r = client.put("/api/ayuda/test.clave", json={"texto": "hola", "titulo": "T", "pantalla": "p"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["clave"] == "test.clave" and b["texto"] == "hola" and b["titulo"] == "T"
    assert "id" not in b
    g = client.get("/api/ayuda/test.clave")
    assert g.status_code == 200 and g.json()["texto"] == "hola"


def test_put_actualiza_no_duplica(client):
    client.put("/api/ayuda/test.clave", json={"texto": "v1"})
    r = client.put("/api/ayuda/test.clave", json={"texto": "v2"})
    assert r.json()["texto"] == "v2"
    todos = [x for x in client.get("/api/ayuda").json() if x["clave"] == "test.clave"]
    assert len(todos) == 1


def test_put_texto_vacio_422(client):
    assert client.put("/api/ayuda/x.y", json={"texto": ""}).status_code == 422


def test_get_uno_inexistente_404(client):
    assert client.get("/api/ayuda/no.existe").status_code == 404


def test_lista_filtra_por_pantalla(client):
    client.put("/api/ayuda/a.k", json={"texto": "t", "pantalla": "equipos"})
    client.put("/api/ayuda/b.k", json={"texto": "t", "pantalla": "mapa"})
    data = client.get("/api/ayuda", params={"pantalla": "equipos"}).json()
    assert all(x["pantalla"] == "equipos" for x in data)
    assert any(x["clave"] == "a.k" for x in data)


def test_delete(client):
    client.put("/api/ayuda/del.k", json={"texto": "t"})
    assert client.delete("/api/ayuda/del.k").status_code == 204
    assert client.get("/api/ayuda/del.k").status_code == 404
    assert client.delete("/api/ayuda/del.k").status_code == 404


def test_ayuda_protegido_sin_token_401(client_sin_auth):
    assert client_sin_auth.get("/api/ayuda").status_code == 401
