# Prompts Lovable — Frontend 6TL Postventa

Frontend (React/Vite/TS/Tailwind/shadcn) del sub-proyecto 1 (trazabilidad + base instalada).
Backend FastAPI en `http://127.0.0.1:8020`. Pega los prompts **en orden** en Lovable.

| # | Prompt | Pantalla / contenido |
|---|--------|----------------------|
| 00 | `00_design_system.md` | **Pegar primero.** Identidad corporativa 6TL (lila `#9e007e`, Open Sans/Roboto, isotipo) + shell con navegación + cliente API a :8020 |
| 01 | `01_base_instalada.md` | Home: tabla de base instalada + buscador global por nº de serie + filtros |
| 02 | `02_ficha_equipo.md` | Ficha de equipo (central): config actual + ubicación actual + historiales + modales montar/desmontar/sustituir/mover |
| 03 | `03_alta_edicion_equipo.md` | Alta y edición de equipo (+ componentes iniciales) |
| 04 | `04_catalogo.md` | Catálogo de productos (part numbers) |
| 05 | `05_ubicaciones.md` | Ubicaciones (fábricas/sedes) |

## Identidad corporativa (de `6TL_Línies bàsiques imatge corporativa.pdf`)
- **Lila** `#9e007e` (Pantone 2415C) — color de marca / acento primario
- **Gris** `#3d3d3f` · **Negro** `#000000` · **Blanco** `#ffffff`
- Tipografías: **Open Sans** (principal) · **Roboto** (secundaria/datos)
- Isotipo: círculo lila con "6TL" en blanco (SVG oficial pendiente — el prompt 00 crea uno fiel sustituible)

## Notas de validación (método habitual)
- Tras pegar cada prompt: verificar contrato (nombres de campo exactos), no fiarse de "errores CORS" engañosos (pueden ser 500 silenciosos o desajuste de nombre de campo).
- Arrancar backend antes: `.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8020` desde `backend/`.
