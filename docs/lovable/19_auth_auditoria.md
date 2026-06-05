# Prompt 19 — Login + historial de auditoría por ficha

Contexto: app postventa 6TL (TanStack Start, API base `VITE_API_BASE ?? http://127.0.0.1:8020`,
helper `api<T>()`, tipos en `@/lib/types`, shadcn, paleta lila `#9e007e`). NO cambies nombres de campo.

## 1. Tipos en `src/lib/types.ts`
- `interface Usuario { id:number; username:string; nombre:string; rol:string; activo:boolean }`
- `interface AuditoriaLog { id:number; fecha_hora:string; usuario_id:number|null;
  usuario_username:string; entidad:string; entidad_id:number; accion:"alta"|"edicion"|"borrado";
  cambios:string|null }`  // `cambios` es un JSON string `{campo:[antes,despues]}`

## 2. Autenticación
- El helper `api()` debe inyectar la cabecera `Authorization: Bearer <token>` leyendo el token de
  `localStorage` (clave `token`). Si una respuesta es **401**, borra el token y redirige a `/login`.
- Página **pública** `/login` SIN el shell/menú interno: formulario usuario + contraseña →
  `POST /api/auth/login {username,password}`. Al 200 guarda `token` en localStorage y el usuario,
  redirige a la home. Muestra error en 401.
- En la cabecera de la app (zona interna): el `nombre` del usuario actual (`GET /api/auth/me`) y un
  botón **Salir** → `POST /api/auth/logout` (con el Bearer) → borra token → `/login`.
- Protege las rutas internas: si no hay token, redirige a `/login`.
- El formulario público de solicitud de soporte (`/solicitud`, si existe) **NO** debe requerir token.

## 3. Historial de cambios por ficha
- En las fichas de **equipo**, **incidencia** y **cliente**, añade una sección/acordeón "Historial de
  cambios" que llame `GET /api/auditoria?entidad=<tabla>&entidad_id=<id>` (entidad = `equipos`,
  `incidencias`, `clientes`).
- Muestra cada entrada como una línea de timeline: fecha-hora, `usuario_username`, `accion`
  (badge: alta=verde, edicion=ámbar, borrado=rojo) y, parseando `cambios` (JSON), la lista de campos
  cambiados `campo: antes → después` (en alta, "creado con …"; en borrado, "eliminado").

Usa EXACTAMENTE los nombres de campo de arriba; no inventes endpoints.
