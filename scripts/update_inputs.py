"""Public input-market signals only. No purchasing, inventory or supplier records."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, date
from io import StringIO
from pathlib import Path
import csv
import json
import math
import re
import requests
from input_catalog import catalogue

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'inputs.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Public-Input-Market-Monitor/1.0)'}
GSCPI_PAGE = 'https://www.newyorkfed.org/research/policy/gscpi'
FDA_URL = 'https://api.fda.gov/drug/shortages.json'

# Macro references are not quotes for pharmaceutical grades or converted packaging.
SERIES = {
    'aluminum': dict(name='Aluminio primario', series_id='PALUMUSDM', source='FMI · FRED', unit='USD / tonelada', scope='Referencia mundial del metal base; no es precio de foil farmacéutico.', category='empaque'),
    'resins': dict(name='Resinas termoplásticas', series_id='WPU0662', source='BLS · FRED', unit='Índice PPI', scope='Canasta de resinas en EE. UU.; señal amplia para plásticos. No mide específicamente PVC, PVDC ni PET farmacéutico.', category='empaque'),
    'corrugated': dict(name='Cartón corrugado', series_id='PCU32221132221105', source='BLS · FRED', unit='Índice PPI', scope='Láminas y rollos de cartón corrugado en EE. UU.; no es una cotización de cajas en RD.', category='empaque'),
    'paperboard': dict(name='Cajas plegadizas', series_id='WPU09150336', source='BLS · FRED', unit='Índice PPI', scope='Cajas, empaques y componentes de cartón plegadizo en EE. UU.; referencia externa.', category='empaque'),
    'ethanol': dict(name='Etanol', series_id='WPU06140341', source='BLS · FRED', unit='Índice PPI', scope='Etanol en EE. UU.; no distingue concentración, grado farmacéutico ni precio local. No representa isopropanol.', category='excipiente'),
    'sugar': dict(name='Azúcar mundial', series_id='PSUGAISAUSDM', source='FMI · FRED', unit='Centavos USD / libra', scope='Azúcar No. 11; referencia upstream para sacarosa. No cotiza sacarosa farmacéutica, mezclas de compresión directa ni polioles.', category='excipiente'),
}


def parse_fred_csv(content, series_id, today=None):
    today = today or date.today()
    rows = csv.DictReader(StringIO(content))
    if rows.fieldnames not in (['observation_date', series_id], ['DATE', series_id]):
        raise ValueError('Encabezado de serie no válido')
    dates = {}
    for row in rows:
        raw_date = row.get('observation_date', row.get('DATE', ''))
        if not re.fullmatch(r'\d{4}-\d{2}-01', raw_date or ''):
            raise ValueError('Se esperaba una frecuencia mensual')
        day = date.fromisoformat(raw_date)
        if day > today or row[series_id] in ('', '.', None):
            continue
        value = float(row[series_id])
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Observación fuera de rango')
        dates[raw_date[:7]] = value
    if not dates:
        raise ValueError('Sin observaciones mensuales válidas')
    return [{'period': p, 'value': round(v, 6)} for p, v in sorted(dates.items())][-61:]


def month_before(period, months):
    y, m = map(int, period.split('-'))
    serial = y * 12 + m - 1 - months
    return f'{serial // 12:04d}-{serial % 12 + 1:02d}'


def changes(history):
    if not history:
        return {key: None for key in ('mom', 'qoq', 'yoy')}
    values = {x['period']: x['value'] for x in history}
    latest = history[-1]
    result = {}
    for key, months in [('mom', 1), ('qoq', 3), ('yoy', 12)]:
        base = values.get(month_before(latest['period'], months))
        result[key] = round((latest['value'] / base - 1) * 100, 2) if base is not None and base > 0 else None
    return result


def get(url, **kwargs):
    r = requests.get(url, headers=HEADERS, timeout=25, **kwargs)
    r.raise_for_status()
    return r


def fred(key):
    config = SERIES[key]
    response = get('https://fred.stlouisfed.org/graph/fredgraph.csv', params={'id': config['series_id']})
    history = parse_fred_csv(response.text, config['series_id'])
    return dict(config, id=key, url='https://fred.stlouisfed.org/series/' + config['series_id'], history=history, **history[-1], changes=changes(history))


def parse_gscpi(content, today=None):
    today = today or date.today()
    rows = csv.DictReader(StringIO(content))
    if not rows.fieldnames or rows.fieldnames[0] != 'Date':
        raise ValueError('Encabezado GSCPI no identificado')
    vintages = []
    for name in rows.fieldnames[1:]:
        try:
            vintage = datetime.strptime(name, '%b-%y').date()
            if vintage <= today:
                vintages.append((vintage, name))
        except ValueError:
            continue
    if not vintages:
        raise ValueError('Sin edición GSCPI identificada')
    column = max(vintages)[1]
    observations = {}
    for row in rows:
        if not row.get('Date', '').strip():
            continue
        day = datetime.strptime(row['Date'], '%d-%b-%Y').date()
        raw = row.get(column, '')
        if day > today or not raw or raw.strip().lower() in ('na', 'n/a', '.'):
            continue
        value = float(raw)
        if not math.isfinite(value) or abs(value) > 20:
            raise ValueError('GSCPI fuera de rango')
        observations[day.strftime('%Y-%m')] = value
    if not observations:
        raise ValueError('Sin observaciones GSCPI válidas')
    return [{'period': p, 'value': v} for p, v in sorted(observations.items())][-61:]


def gscpi():
    url = 'https://www.newyorkfed.org/medialibrary/research/interactives/data/gscpi/gscpi_interactive_data.csv'
    history = parse_gscpi(get(url).text)
    return dict(id='gscpi', name='Presión logística global', source='Federal Reserve Bank of New York', url=GSCPI_PAGE, unit='Desviaciones estándar', category='logistica', scope='GSCPI: presión frente al promedio histórico. No mide disponibilidad de una sustancia ni una ruta a RD. Sus variaciones se leen en puntos, no en porcentajes.', history=history, **history[-1])


def matches_active(row, active):
    text = row.get('generic_name', '').casefold()
    def has(term):
        return re.search(r'(?<![a-z])' + re.escape(term) + r'(?![a-z])', text) is not None
    return all(has(t) for t in active['terms']) and not any(has(t) for t in active['exclude'])


def parse_shortages(rows, catalog):
    items = []
    for active in catalog['actives']:
        current = [r for r in rows if str(r.get('status', '')).casefold() == 'current' and matches_active(r, active)]
        # FDA records describe finished-drug presentations, not API stock.
        products = {}
        for row in current:
            record = {k: row.get(k, '') for k in ('generic_name', 'presentation', 'company_name', 'availability', 'shortage_reason', 'update_date')}
            key = (record['presentation'], record['company_name'])
            products[key] = record
        items.append({'name': active['name'], 'count': len(products), 'presentations': list(products.values())})
    return items


def shortages(catalog):
    rows, total, updated = [], None, None
    for skip in range(0, 5000, 1000):
        payload = get(FDA_URL, params={'limit': 1000, 'skip': skip}).json()
        meta = payload.get('meta', {})
        count = meta.get('results', {}).get('total')
        batch = payload.get('results')
        if not isinstance(count, int) or not isinstance(batch, list) or not batch:
            raise ValueError('Respuesta FDA incompleta')
        if total is None:
            total, updated = count, meta.get('last_updated')
        elif count != total or meta.get('last_updated') != updated:
            raise ValueError('La base FDA cambió durante la consulta')
        rows.extend(batch)
        if len(rows) >= total:
            break
    if total is None or len(rows) != total:
        raise ValueError('No se recuperó toda la base FDA')
    if not updated or date.fromisoformat(updated) > date.today():
        raise ValueError('Fecha de base FDA no válida')
    return {'last_updated': updated, 'url': 'https://www.fda.gov/drugs/drug-safety-and-availability/drug-shortages', 'source': 'FDA · openFDA Drug Shortages', 'items': parse_shortages(rows, catalog)}


def merge_series(previous, results, stamp):
    series, health = {}, {}
    for key, (observation, error) in results.items():
        health[key] = {'ok': error is None, 'checked_at': stamp, 'error': error}
        if observation is not None:
            series[key] = dict(observation, verified_at=stamp)
        elif key in previous:
            # A failed check must not refresh the last successful verification.
            series[key] = previous[key]
    return series, health


def main():
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    try:
        previous = json.loads(DATA.read_text())
    except (FileNotFoundError, ValueError):
        previous = {}

    catalog = catalogue()
    def run(key):
        try:
            value = shortages(catalog) if key == 'fda' else gscpi() if key == 'gscpi' else fred(key)
            return key, (value, None)
        except Exception as exc:
            return key, (None, type(exc).__name__ + ': fuente no verificable en esta consulta')

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(run, [*SERIES, 'gscpi', 'fda']))
    fda_result, fda_error = results.pop('fda')
    series, health = merge_series(previous.get('series', {}), results, stamp)
    health['fda'] = {'ok': fda_error is None, 'checked_at': stamp, 'error': fda_error}
    fda_data = dict(fda_result, verified_at=stamp) if fda_result else previous.get('fda')
    payload = {'checked_at': stamp, 'series': series, 'source_health': health, 'catalogue': catalog, 'fda': fda_data}
    DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print('Public input signals:', {k: v['ok'] for k, v in health.items()})


if __name__ == '__main__':
    main()
