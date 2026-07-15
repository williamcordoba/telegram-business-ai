# Despliegue low-cost en Render Free

Esta configuración usa un **Render Web Service Free** con webhook de Telegram.
Localmente el mismo programa sigue utilizando polling.

## Limitaciones aceptadas

- Render suspende el servicio tras 15 minutos sin tráfico.
- El primer mensaje después de una suspensión puede tardar cerca de un minuto.
- El historial conversacional se guarda en memoria y se pierde al reiniciar.
- Las gráficas son temporales y se eliminan después de enviarlas.
- Solo se despliega una instancia.
- `Ventas_3.db` viaja dentro de la imagen y se abre en modo de solo lectura.

Este diseño sirve para un proyecto personal o de demostración de bajo tráfico. Render
indica expresamente que sus instancias Free no deben considerarse producción crítica.

## 1. Credenciales nuevas

Antes de publicar, revoca cualquier credencial que haya sido mostrada en una terminal,
captura o conversación y crea:

- Un token nuevo de Telegram mediante `@BotFather`.
- Una API key nueva dentro de un proyecto de Groq exclusivo para producción.

Nunca guardes las claves en archivos que vayan a GitHub.

## 2. Identificar usuarios autorizados

Ejecuta el bot localmente y envía `/id`. El bot responderá con un número, por ejemplo:

```text
Tu Telegram user ID es: 123456789
```

Guarda ese número. Para autorizar varios usuarios, sepáralos con comas:

```text
123456789,987654321
```

## 3. Crear un repositorio propio en GitHub

El remoto actual pertenece al proyecto oficial `python-telegram-bot`. Crea un repositorio
vacío en GitHub, por ejemplo `telegram-business-ai`, sin README ni licencia adicionales.

Desde esta carpeta ejecuta, reemplazando `TU_USUARIO`:

```powershell
& '..\tools\MinGit\cmd\git.exe' remote rename origin upstream
& '..\tools\MinGit\cmd\git.exe' remote add origin https://github.com/TU_USUARIO/telegram-business-ai.git
& '..\tools\MinGit\cmd\git.exe' add bot_prueba.py ai_business_assistant.py BOT_NEGOCIO.md PRODUCCION_RENDER.md requirements-business-bot.txt Dockerfile .dockerignore .env.example render.yaml .gitignore data/stock-y-ventas/Ventas_3.db
& '..\tools\MinGit\cmd\git.exe' commit -m "Preparar chatbot de negocio para Render"
& '..\tools\MinGit\cmd\git.exe' push -u origin master
```

Si Git solicita autenticación, inicia sesión mediante el navegador o utiliza un Personal
Access Token de GitHub. No uses la contraseña normal de GitHub.

## 4. Crear el servicio desde el Blueprint

1. Entra en https://dashboard.render.com/ y accede con GitHub.
2. Selecciona **New > Blueprint**.
3. Conecta el repositorio `telegram-business-ai`.
4. Render detectará `render.yaml`.
5. Confirma que el servicio sea **Web Service**, runtime **Docker** y plan **Free**.
6. Cuando Render solicite variables secretas, introduce:

| Variable | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token nuevo y completo de BotFather |
| `GROQ_API_KEY` | Clave nueva del proyecto Groq de producción |
| `ALLOWED_TELEGRAM_USER_IDS` | ID obtenido con `/id` |

`WEBHOOK_SECRET` se genera automáticamente y `GROQ_MODEL` ya tiene un valor por defecto.

7. Selecciona **Apply** y espera a que termine el primer despliegue.

## 5. Verificar el despliegue

En los logs de Render deben aparecer mensajes similares a:

```text
Iniciando webhook en https://telegram-business-ai.onrender.com/telegram-webhook
Application started
```

Después abre Telegram y prueba:

```text
/start
¿Cuáles fueron los cinco productos con mayores ingresos?
Genera una gráfica de participación de ingresos por producto.
```

Telegram configura el webhook automáticamente durante el arranque. No necesitas ejecutar
`setWebhook` manualmente.

## 6. Operación gratuita

- Revisa **Render > Metrics/Logs** cuando haya errores.
- Revisa **Groq > Usage/Limits/Logs** para controlar solicitudes y tokens.
- Mantén `ALLOWED_TELEGRAM_USER_IDS` configurado para evitar consumo público.
- Usa `/nuevo` para reducir contexto cuando cambies de análisis.
- Los commits nuevos en `master` generan un despliegue automático.

## 7. Diagnóstico

### Render indica que no detectó un puerto

Comprueba que el servicio tenga `RENDER_EXTERNAL_URL` y que los logs indiquen el puerto
proporcionado en `PORT`. El código escucha en `0.0.0.0` automáticamente.

### Telegram no responde después de inactividad

Espera hasta un minuto y vuelve a enviar el mensaje. Es el arranque en frío del plan Free.

### `InvalidToken`

Reemplaza `TELEGRAM_BOT_TOKEN` en Render por un token nuevo y completo, y vuelve a desplegar.

### Error 401 de Groq

Reemplaza `GROQ_API_KEY` por una clave activa del proyecto correcto.

### Error 429 de Groq

Se alcanzó un límite gratuito. Espera al reinicio del límite o reduce el número de usuarios
y la longitud de las conversaciones.
