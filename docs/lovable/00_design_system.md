# Prompt Lovable 00 — Sistema de diseño + shell (marca 6TL)

> Pega esto PRIMERO en Lovable, antes que el resto de prompts. Define la identidad corporativa de 6TL y el layout base. Los prompts 01–05 asumen que esto ya existe.

---

Estoy construyendo **6TL Postventa**, una aplicación web interna para gestionar la postventa de sistemas de test electrónico (ATE) de la empresa 6TL Engineering. Es una herramienta de datos, de uso interno (sin login en esta versión). Quiero que apliques de forma estricta la identidad corporativa de 6TL.

## Identidad corporativa 6TL (obligatoria)

**Colores corporativos (úsalos como design tokens, no hardcodees hex sueltos por ahí):**
- **Lila (color de marca, primario):** `#9e007e` (Pantone 2415C). Es el acento principal: botones primarios, navegación activa, enlaces, foco, isotipo.
- **Gris:** `#3d3d3f` — color de texto principal y de UI.
- **Negro:** `#000000` — solo titulares fuertes o cuando el lila no contrasta.
- **Blanco:** `#ffffff` — fondos.

Deriva una escala del lila para hovers/fondos suaves (mantén el `#9e007e` como `lila-600`):
`lila-50 #fdf2fa`, `lila-100 #fae3f3`, `lila-200 #f3c2e3`, `lila-300 #e68fc9`, `lila-400 #d456ab`, `lila-600 #9e007e` (marca), `lila-700 #7d0063`, `lila-800 #5c0049`.

Neutros de grises a partir del gris corporativo `#3d3d3f` para textos secundarios, bordes y fondos (`#f6f6f7` fondo de página, `#e7e7e9` bordes, `#6b6b6e` texto secundario).

**Colores funcionales (secundarios, SOLO para semáforos de estado, nunca como acento de marca):** verde `#2e7d32`, ámbar `#b26a00`, rojo `#c62828`. Úsalos discretos (texto/badge), el protagonismo cromático es del lila.

**Tipografías corporativas (Google Fonts):**
- **Open Sans** — tipografía principal: titulares, etiquetas, navegación, botones.
- **Roboto** — tipografía secundaria: cuerpo de texto, celdas de tablas y datos (números de serie, fechas).
Configura `font-display`/`--font-heading: 'Open Sans'` y `--font-body: 'Roboto'`. Carga ambas desde Google Fonts.

**Isotipo 6TL:** es un **círculo lila con "6TL" en blanco** (el "6" como dígito y "TL" como monograma, todo dentro de un círculo). No tengo el SVG oficial a mano. Crea un componente `<Logo6TL />` que dibuje un isotipo fiel: un círculo relleno de lila `#9e007e` con el texto "6TL" en blanco, Open Sans extrabold, centrado. Déjalo preparado para sustituir fácilmente por el SVG oficial (un único componente, comentario `// TODO: sustituir por SVG oficial de 6TL cuando esté disponible`). Versión sobre fondo claro: círculo lila + texto blanco. Si va sobre fondo lila, círculo blanco + texto lila.

**Tono visual:** limpio, corporativo, mucho blanco, lila como acento, esquinas suavemente redondeadas (radius ~8px), sombras sutiles. Nada de degradados llamativos ni colores fuera de la paleta. Densidad de datos alta pero legible (es una app de gestión).

## Configuración técnica

- **API backend (FastAPI) en `http://127.0.0.1:8020`.** Crea un cliente API central (`src/lib/api.ts`) con `const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8020'`. Todas las llamadas pasan por ahí. Maneja errores: si la respuesta no es ok, lee `detail` del JSON y muéstralo en un toast.
- Usa React + TypeScript + Tailwind + shadcn/ui (que ya usas), pero **re-tematiza shadcn con los colores de marca** (primary = lila `#9e007e`, ring = lila, etc.) en lugar del azul por defecto.

## Layout / shell de la aplicación

Crea un layout con **barra lateral de navegación** fija a la izquierda:
- Arriba: `<Logo6TL />` + el texto "Postventa" en Open Sans.
- Items de navegación (con icono lucide y resaltado lila cuando activo):
  1. **Base instalada** (`/`) — icono `boxes` o `server`
  2. **Catálogo** (`/catalogo`) — icono `package`
  3. **Ubicaciones** (`/ubicaciones`) — icono `map-pin`
- El item activo: texto lila `#9e007e`, fondo `lila-50`, barra lila a la izquierda.
- Contenido principal a la derecha sobre fondo `#f6f6f7`, con un header superior delgado que deja sitio para un **buscador global** (lo cablearemos en el prompt 01).
- Pie discreto con "6TL Engineering · Postventa" en gris.

Responsive: en pantallas pequeñas la barra lateral colapsa a un menú.

Crea las rutas vacías (`/`, `/catalogo`, `/ubicaciones`, y `/equipos/:id`) con placeholders por ahora; las rellenamos en los siguientes prompts.

No inventes endpoints ni datos: deja los placeholders hasta que te pase el prompt de cada pantalla.
