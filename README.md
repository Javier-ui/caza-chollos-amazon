# caza_chollos_amazon

Bot de Telegram para alertas de ofertas en Amazon UE, con publicación en `@CholloPulseGroup`.

## Estado actual

El MVP incluye polling de Telegram, suscripción de chats, comandos de estado y configuración del ciclo de comprobación cada 10 minutos. El motor de precios permanece desactivado hasta conectar fuentes públicas permitidas y verificables; no usa APIs premium ni técnicas para evadir límites, CAPTCHA o controles de acceso.

## Ejecución local

```bash
export TELEGRAM_BOT_TOKEN='...'
python3 bot.py
```

Nunca subas el token al repositorio. En GitHub Actions debe configurarse como secret.
