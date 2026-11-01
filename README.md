# caza_chollos_amazon

Bot de Telegram para alertas de ofertas en Amazon UE, con publicación en `@CholloPulseGroup`.

## Modo de barrido

El workflow revisa una tienda europea por ejecución y rota entre España, Alemania, Francia, Italia, Países Bajos, Bélgica, Polonia y Suecia. Cada ejecución se programa aproximadamente cada 10 minutos. La lista contiene 30 categorías de alto valor de reventa, incluyendo cinco búsquedas de Amazon Warehouse.

El escáner espera entre categorías, aplica un máximo de tres reintentos para respuestas HTTP 503 con retroceso progresivo y se detiene ante otros errores de acceso. No usa rotación de IP, evasión de CAPTCHA, bypass de límites ni reintentos infinitos. La programación de GitHub Actions puede sufrir retrasos.

Las alertas se basan en el precio y la referencia de descuento que Amazon muestra en la página de resultados. Deben verificarse antes de comprar: vendedor, condición, garantía, gastos de envío, variantes y disponibilidad pueden cambiar.

## Ejecución local

```bash
export TELEGRAM_BOT_TOKEN='...'
export TARGET_CHAT_ID='-1003980825772'
python3 bot.py --once
```

El bot de comandos en modo continuo se ejecuta con `python3 bot.py`. Nunca subas el token al repositorio; en GitHub Actions debe configurarse como secret `TELEGRAM_BOT_TOKEN`.
