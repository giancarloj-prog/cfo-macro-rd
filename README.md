# CFO Macro Dashboard — RD, USA y noticias farmacéuticas

Dashboard publicado en https://giancarloj-prog.github.io/cfo-macro-rd/.

## Actualización

GitHub Actions verifica y publica todos los días, incluidos fines de semana, a las 7:15 AM, 1:00 PM y 6:00 PM de Santo Domingo (UTC−4). Los horarios son aproximados y dependen de la disponibilidad de GitHub Actions. También se puede ejecutar manualmente el workflow.

- `scripts/update_data.py`: BCRD, archivos XLSX de DGII, Hacienda y DIGEPRES. Conserva el último dato si falla una fuente y muestra el estado de la consulta.
- `scripts/update_usa.py`: rango objetivo de la Fed, Treasury nominal a 10 años (H.15, alternativa FRED DGS10), PMI Manufacturing y Services de ISM, y WCI de Drewry. Los PMI se buscan en ISM y, como alternativa, en los comunicados emitidos por ISM en PR Newswire. Cada observación conserva período, fuente y fecha de verificación; un fallo no renueva esa fecha.
- `scripts/update_news.py`: busca titulares farmacéuticos en medios seleccionados mediante Google News RSS. Valida medio, tema y fecha en `America/Santo_Domingo`; elimina duplicados y reemplaza el listado diario. Las consultas se dividen en grupos cortos de medios para evitar que el buscador descarte términos. No se almacenan artículos completos ni se presenta un archivo histórico; los cambios de JSON permanecen en el historial normal de Git. Los enlaces del agregador redirigen al artículo original; algunos medios tienen suscripción. La selección no pretende cobertura exhaustiva de toda la prensa.

## Pestañas

1. República Dominicana: indicadores, CFO Watch y gráficos con períodos dinámicos.
2. USA & logística global: Fed, Treasury, PMI y WCI (USD por contenedor de 40 pies; referencia global).
3. Noticias farmacéuticas: filtro por región y búsqueda por texto. Las noticias de días anteriores se ocultan también en el navegador, incluso si una actualización falla.

## Verificación local

```bash
pip install -r requirements.txt
python -m unittest discover -s tests
python scripts/update_data.py
python scripts/update_usa.py
python scripts/update_news.py
```

Los fallos de una fuente macro no impiden ejecutar y publicar las noticias. Cada lector informa su estado; el éxito del workflow no implica que todas las fuentes hayan respondido. Los datos mensuales conservan su mes publicado y no se presentan como observaciones del día.
