# CFO Macro Dashboard — República Dominicana

Repositorio listo para publicar el dashboard HTML en GitHub Pages.

## Publicación inicial
1. Crea un repositorio en GitHub, por ejemplo `cfo-macro-rd`.
2. Sube **todo el contenido de esta carpeta**, incluyendo `.github`.
3. En GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Abre **Actions** y ejecuta `Update and publish CFO Macro RD` una vez.
5. GitHub Pages mostrará la URL publicada.

## Automatización configurada
- Lunes a viernes ~7:15 AM hora de Santo Domingo.
- Verifica disponibilidad de BCRD, DGII y Hacienda.
- Conserva el último snapshot validado si una fuente falla.
- Publica el sitio mediante GitHub Pages.

## Estado de integración
La infraestructura de actualización/publicación ya está lista.
`data/current.json` contiene el snapshot inicial validado.
La extracción automática de cada serie se incorpora fuente por fuente después de
validar el contrato de descarga/API oficial; no se hace scraping silencioso de
valores financieros sin validación.

## Próxima integración
1. BCRD: FX, TPM, tasas, IPC, IMAE, crédito, reservas.
2. DGII: operaciones totales/gravadas ITBIS y recaudación.
3. Hacienda: balance/ingresos/ejecución fiscal.
4. Validaciones de período, rango y variaciones antes de publicar.
