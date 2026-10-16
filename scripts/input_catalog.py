"""Generic substances for a public market reference catalogue; alphabetical UI."""

# terms are English generic-name families, not purchasing specifications.
ACTIVES = [
    ('Azitromicina', ['azithromycin'], [], 'Familia de azitromicina; no identifica por sí sola el dihidrato.'),
    ('Candesartán cilexetilo', ['candesartan', 'cilexetil'], [], ''),
    ('Carbocisteína', ['carbocisteine'], [], ''),
    ('Citicolina', ['citicoline'], [], 'No identifica por sí sola la sal sódica.'),
    ('Clopidogrel', ['clopidogrel'], [], 'La sal y el polimorfo pueden cambiar la comparabilidad.'),
    ('Diosmina / hesperidina', ['diosmin', 'hesperidin'], [], 'La proporción y la micronización no se infieren de referencias genéricas.'),
    ('Etoricoxib', ['etoricoxib'], [], ''),
    ('Fosfomicina cálcica', ['fosfomycin', 'calcium'], [], 'No confundir con fosfomicina trometamol o sódica.'),
    ('Irbesartán', ['irbesartan'], [], ''),
    ('Lactulosa', ['lactulose'], [], 'La concentración y la presentación requieren comparación separada.'),
    ('Levetiracetam', ['levetiracetam'], [], ''),
    ('Losartán potásico', ['losartan', 'potassium'], [], ''),
    ('Metformina HCl', ['metformin', 'hydrochloride'], [], 'Las referencias genéricas no representan material granulado ni su formulación.'),
    ('Nifedipina', ['nifedipine'], [], 'La micronización no se infiere de referencias genéricas.'),
    ('Piracetam', ['piracetam'], [], ''),
    ('Quetiapina fumarato', ['quetiapine', 'fumarate'], [], ''),
    ('Rosuvastatina', ['rosuvastatin'], [], 'La sal y la especificación requieren comparación separada.'),
    ('Sacubitril / valsartán', ['sacubitril', 'valsartan'], [], 'El complejo y su forma hidratada requieren comparación específica.'),
    ('Valsartán', ['valsartan'], ['sacubitril'], 'Se excluyen combinaciones con sacubitril de la coincidencia FDA.'),
    ('Vildagliptina', ['vildagliptin'], [], ''),
]

EXCIPIENTS = [
    ('Alcohol etílico', 'ethanol', 'Etanol', 'Índice industrial; no cotiza concentración ni grado farmacéutico.'),
    ('Alcohol isopropílico', None, None, 'Sin serie pública específica integrada; no se sustituye por etanol.'),
    ('Celulosa microcristalina', None, None, 'Sin serie pública comparable integrada para grados farmacéuticos.'),
    ('Croscarmelosa sódica', None, None, 'Sin serie pública comparable integrada.'),
    ('Crospovidona', None, None, 'Sin serie pública comparable integrada.'),
    ('Dióxido de silicio coloidal', None, None, 'La sílice industrial no se trata como precio de sílice farmacéutica.'),
    ('Estearil fumarato de sodio', None, None, 'Sin serie pública comparable integrada.'),
    ('Hidroxipropilcelulosa', None, None, 'Sin serie pública comparable integrada por viscosidad y granulometría.'),
    ('Hipromelosa (HPMC)', None, None, 'Sin serie pública comparable integrada por grado y viscosidad.'),
    ('Lactosa', None, None, 'No se usa leche en polvo como precio de lactosa farmacéutica spray dried.'),
    ('Manitol', None, None, 'No se usa azúcar como precio de manitol farmacéutico.'),
    ('Sacarosa', 'sugar', 'Azúcar mundial', 'Referencia upstream; no cotiza grados farmacéuticos ni mezclas de compresión directa.'),
    ('Sorbitol', None, None, 'Sin serie pública comparable integrada por concentración y grado.'),
]


def catalogue():
    return {
        'actives': [dict(name=name, terms=terms, exclude=exclude, note=note) for name, terms, exclude, note in ACTIVES],
        'excipients': [dict(name=name, signal=signal, signal_name=signal_name, note=note) for name, signal, signal_name, note in EXCIPIENTS],
    }
