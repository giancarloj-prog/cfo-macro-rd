# CFO Macro Dashboard — RD, USA y noticias farmacéuticas

Dashboard publicado en https://giancarloj-prog.github.io/cfo-macro-rd/.

## Actualización

GitHub Actions verifica y publica todos los días, incluidos fines de semana, cada hora entre las 6:17 AM y las 10:17 PM de Santo Domingo (UTC−4). Los horarios son aproximados y dependen de la disponibilidad de GitHub Actions. También se puede ejecutar manualmente el workflow.

- `scripts/update_data.py`: BCRD, archivos XLSX de DGII, Hacienda y DIGEPRES. Conserva el último dato si falla una fuente y muestra el estado de la consulta.
- `scripts/update_usa.py`: inflación general interanual CPI-U (BLS), último cierre publicado del S&P 500 en puntos (S&P Dow Jones Indices/FRED; Yahoo Finance como alternativa si FRED no responde, excluyendo la sesión que siga abierta), rango objetivo de la Fed, Treasury nominal a 10 años (H.15, alternativa FRED DGS10), PMI Manufacturing y Services de ISM, y WCI de Drewry. Los PMI se buscan en ISM y, como alternativa, en los comunicados emitidos por ISM en PR Newswire. Cada observación conserva período, fuente y fecha de verificación; un fallo no renueva esa fecha.
- `scripts/update_gdp.py`: PIB real trimestral por actividad. Descubre el Excel vigente del BCRD, comprueba las tasas oficiales contra los índices y mueve la ventana de cuatro trimestres al publicarse uno nuevo. Relee el histórico para incorporar revisiones. Los últimos 12 meses se calculan por actividad; no se suman índices entre actividades.
- `scripts/update_news.py`: busca titulares farmacéuticos en medios seleccionados mediante Google News RSS. Valida medio, tema y fecha en `America/Santo_Domingo`; elimina duplicados y reemplaza el listado diario. Las consultas se dividen en grupos cortos de medios para evitar que el buscador descarte términos. No se almacenan artículos completos ni se presenta un archivo histórico; los cambios de JSON permanecen en el historial normal de Git. Los enlaces del agregador redirigen al artículo original; algunos medios tienen suscripción. La selección no pretende cobertura exhaustiva de toda la prensa.
- `scripts/update_inputs.py`: consulta seis series mensuales públicas de FRED (FMI/BLS), la última edición del GSCPI de la Fed de Nueva York y toda la base FDA Drug Shortages, con paginación y validación de integridad. Calcula variaciones con meses comparables exactos; una consulta fallida conserva el último dato y no renueva su verificación. Los niveles PPI no son precios en dólares. No integra precios restringidos ni infiere disponibilidad del API a partir de faltantes de medicamentos terminados.

## Pestañas

1. República Dominicana: indicadores, CFO Watch y gráficos con períodos dinámicos.
2. USA & logística global: Fed, Treasury, PMI y WCI (USD por contenedor de 40 pies; referencia global).
3. Noticias farmacéuticas: filtro por región y búsqueda por texto. Las noticias de días anteriores se ocultan también en el navegador, incluso si una actualización falla.

4. PIB por actividad: últimas cuatro tasas trimestrales YoY, selector de actividades y desgloses, comparación de actividades principales, últimos 12 meses y acumulado del año.
5. Insumos y abastecimiento: aluminio, resinas termoplásticas, corrugado, cajas plegadizas, etanol, azúcar y presión logística global. Tabla alfabética que muestra exclusivamente sustancias con referencias numéricas públicas integradas; omite materiales sin serie disponible. Las señales FDA Current se mantienen como contexto separado en CFO Watch.

Esta pestaña utiliza exclusivamente datos públicos. No contiene registros empresariales de compras, inventarios, contratos, proveedores, precios negociados o prioridades de abastecimiento. El catálogo genérico no identifica un portafolio de compras empresarial. Los umbrales del CFO Watch son orientativos: precios 5/10/20% (amarillo) y 10/20/30% (rojo) a 1/3/12 meses; GSCPI 1 y 2 desviaciones estándar. No se activan nuevas alertas numéricas con una consulta fallida o una observación de más de 120 días.

## Verificación local

```bash
pip install -r requirements.txt
python -m unittest discover -s tests
python scripts/update_data.py
python scripts/update_usa.py
python scripts/update_news.py
python scripts/update_inputs.py
```

Los fallos de una fuente macro no impiden ejecutar y publicar las noticias. Cada lector informa su estado; el éxito del workflow no implica que todas las fuentes hayan respondido. Los datos mensuales conservan su mes publicado y no se presentan como observaciones del día.

### Fuentes directas de insumos

Los cuatro PPI se consultan en una sola solicitud a la API pública BLS v1, sin registro ni clave, para los últimos seis años. Aluminio y azúcar se descargan del Excel mensual vigente enlazado por la página Commodity Markets del Banco Mundial; no se fija un enlace anual de archivo. Los históricos se reemplazan completos por fuente; no se empalman con FMI/FRED. Azúcar: US$/kg × 100 × 0.45359237 = centavos US$/libra. Se conservan meses comparables exactos para variaciones a 1, 3 y 12 meses y el último histórico verificado ante fallos o regresión del período. El flujo programado existente ejecuta estas consultas sin cuentas adicionales.

### Noticias económicas y financieras RD

La pestaña Noticias económicas RD lee `data/economy_news.json`. El actualizador `scripts/update_economy_news.py` busca titulares públicos en Google News RSS de medios dominicanos seleccionados y dominios oficiales; cubre Banco Central, Hacienda, DGII, finanzas, valores y economía. Busca además Andy Dauhajre, Jaime Aristy Escuder, Juan Ariel Jiménez, Raúl Ovalle, José Luis de Ramón y Nassim Alemany. Las coincidencias por nombre no se presentan como autoría confirmada; la interfaz identifica cuando solo proceden de la búsqueda. La lista de economistas y aliases se puede ampliar en ECONOMISTS.

Se ejecuta con las actualizaciones existentes (cada hora de 6:17 a 22:17, hora RD, sujeto a retrasos de GitHub). Solo admite artículos del día dominicano, conserva descubrimientos durante ese día, combina duplicados por medio/titular y reinicia el conjunto al cambiar de día incluso si falla la fuente. La pantalla recarga el JSON cada cinco minutos y oculta registros de otro día sin esperar un despliegue. La cobertura no es exhaustiva; no hay archivo visible de días previos ni resúmenes inventados.
