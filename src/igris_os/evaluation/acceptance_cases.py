"""Contratos y pruebas externas: el generador recibe el contrato, no la solucion."""

STATS_CONTRACT = ('Expone statistics(text) que devuelve exactamente words, lines y characters: '
    'len(text.split()), len(text.splitlines()) y len(text). El texto vacio da ceros; '
    'rechaza entradas que no sean str con TypeError.')

CONTRACTS = {
    'todo_memory': ('Crea una aplicacion Python de consola para tareas. En main.py define TaskList: '
        'add(title) valida str no vacio, elimina espacios exteriores y devuelve id entero unico desde 1; '
        'items() devuelve copias de diccionarios id,title,done en orden de creacion; '
        'complete(id) marca done=True y devuelve True, o False si no existe. '
        'Titulos vacios dan ValueError. Instancias independientes. Incluye pruebas propias.'),
    'text_statistics': 'Crea una aplicacion Python de estadisticas en main.py. ' + STATS_CONTRACT,
    'inventory_components': ('Crea inventario Python con service.py y app.py que use service. '
        'service.Inventory(): add(sku, quantity), set_quantity(sku, quantity), items()->dict. '
        'SKU es str no vacio, quantity entero no negativo, bool/float no admitidos. '
        'Datos invalidos y SKU duplicado dan ValueError; set_quantity de SKU ausente da KeyError. '
        'items devuelve copia. Una operacion rechazada no modifica el inventario. Incluye pytest.'),
    'notes_components': ('Crea notas Python con service.py y app.py que use service. '
        'service.Notebook: add(text) elimina espacios exteriores, rechaza vacios con ValueError '
        'y devuelve id entero unico; search(query) busca subcadena sin distinguir mayusculas con casefold '
        'y devuelve copias de diccionarios id,text en orden de creacion; delete(id) devuelve bool. '
        'Instancias independientes. Incluye pytest.'),
    'statistics_components': ('Crea estadisticas Python con service.py y app.py que use service. '
        'En service.py: ' + STATS_CONTRACT + ' Incluye pytest.'),
    'repository_inventory': ('Repara este repositorio Python existente conservando sus APIs y pruebas. '
        'service.Inventory(path) almacena inventario JSON mediante storage.load/save. '
        'add(sku, quantity) valida SKU str no vacio, cantidad int >=0 (no bool/float), '
        'duplicado ValueError. adjust(sku, delta) acepta int firmado, rechaza bool/float y '
        'resultado negativo con ValueError; SKU ausente KeyError. snapshot() devuelve copia. '
        'Cada cambio valido persiste y otra instancia lo recupera. Un fallo de validacion '
        'no cambia memoria ni disco. storage.load de archivo inexistente devuelve {}; '
        'JSON corrupto, raiz no dict, SKU vacio o cantidades invalidas dan ValueError sin '
        'sobrescribir el archivo. Conserva report.py y sus resultados. Mejora service.py y '
        'storage.py, añade pruebas de aceptacion y documenta la ejecucion en README.md. '
        'Solo biblioteca estandar. No requiere interfaz grafica, red, instaladores ni ejecutable.'),
}

STATS_TESTS = '''
    def test_values(self):
        for text in ['', 'uno', 'uno dos\\ntres', ' \\n\\n', 'áé 漢字\\n', 'x\\r\\ny']:
            with self.subTest(text=text):
                self.assertEqual(m.statistics(text), dict(words=len(text.split()),
                    lines=len(text.splitlines()), characters=len(text)))
    def test_many_lengths(self):
        randomizer = random.Random(81732)
        for _ in range(20):
            text = ''.join(randomizer.choice('abc \\n\\t') for _ in range(randomizer.randrange(70)))
            self.assertEqual(m.statistics(text), dict(words=len(text.split()),
                lines=len(text.splitlines()), characters=len(text)))
    def test_type_error(self):
        for value in [None, 12, [], b'abc']:
            with self.assertRaises(TypeError): m.statistics(value)
'''

TESTS = {
    'todo_memory': '''
    def test_add_complete(self):
        tasks = m.TaskList()
        first, second = tasks.add('  escribir  '), tasks.add('revisar')
        self.assertEqual((first, second), (1, 2))
        self.assertTrue(tasks.complete(first))
        self.assertFalse(tasks.complete(9981))
        self.assertEqual(tasks.items(), [{'id': 1, 'title': 'escribir', 'done': True},
                                        {'id': 2, 'title': 'revisar', 'done': False}])
    def test_empty_rejected(self):
        tasks = m.TaskList()
        for value in ['', '  ', '\\n']:
            with self.assertRaises(ValueError): tasks.add(value)
        self.assertEqual(tasks.items(), [])
    def test_copies_and_instances(self):
        tasks = m.TaskList()
        tasks.add('uno')
        rows = tasks.items()
        rows[0]['title'] = 'mutated'
        rows.clear()
        self.assertEqual(tasks.items()[0]['title'], 'uno')
        self.assertEqual(m.TaskList().items(), [])
''',
    'text_statistics': STATS_TESTS,
    'statistics_components': STATS_TESTS,
    'inventory_components': '''
    def test_updates(self):
        stock = m.Inventory()
        for i in range(15): stock.add('sku-' + str(i), i * 7)
        stock.set_quantity('sku-2', 93)
        self.assertEqual(stock.items()['sku-2'], 93)
        self.assertEqual(len(stock.items()), 15)
    def test_errors_preserve_state(self):
        stock = m.Inventory()
        stock.add('a', 4)
        for value in [-1, 2.5, True, '3']:
            with self.assertRaises(ValueError): stock.set_quantity('a', value)
        with self.assertRaises(ValueError): stock.add('a', 2)
        with self.assertRaises(ValueError): stock.add('', 2)
        with self.assertRaises(KeyError): stock.set_quantity('absent', 1)
        self.assertEqual(stock.items(), {'a': 4})
    def test_copies(self):
        stock = m.Inventory()
        stock.add('a', 0)
        stock.items()['a'] = 99
        self.assertEqual(stock.items(), {'a': 0})
        self.assertEqual(m.Inventory().items(), {})
''',
    'notes_components': '''
    def test_search_and_delete(self):
        notes = m.Notebook()
        one, two = notes.add('  Café Python  '), notes.add('Otra nota')
        self.assertIs(type(one), int)
        self.assertNotEqual(one, two)
        self.assertEqual(notes.search('CAFÉ'), [{'id': one, 'text': 'Café Python'}])
        self.assertTrue(notes.delete(one))
        self.assertFalse(notes.delete(one))
        self.assertEqual(notes.search('café'), [])
        self.assertEqual(notes.search('nota'), [{'id': two, 'text': 'Otra nota'}])
    def test_empty(self):
        notes = m.Notebook()
        for text in ['', '  ']:
            with self.assertRaises(ValueError): notes.add(text)
        self.assertEqual(notes.search(''), [])
    def test_copies_and_instances(self):
        notes = m.Notebook()
        key = notes.add('original')
        notes.search('')[0]['text'] = 'changed'
        self.assertEqual(notes.search('original'), [{'id': key, 'text': 'original'}])
        self.assertEqual(m.Notebook().search(''), [])
''',
    'repository_inventory': '''
    def test_persistence_and_copies(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / 'stock.json'
            stock = m.Inventory(path)
            for i in range(12): stock.add('item-' + str(i), i * 9)
            stock.adjust('item-3', -7)
            self.assertEqual(m.Inventory(path).snapshot()['item-3'], 20)
            copy = stock.snapshot()
            copy.clear()
            self.assertEqual(len(stock.snapshot()), 12)
    def test_invalid_operations_are_unchanged(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / 'stock.json'
            stock = m.Inventory(path)
            stock.add('a', 7)
            original = path.read_bytes()
            operations = [(stock.add, ('a', 2)), (stock.add, ('', 2)),
                (stock.add, ('bad', -1)), (stock.add, ('bad', True)),
                (stock.adjust, ('a', -8)), (stock.adjust, ('a', 1.5)), (stock.adjust, ('a', False))]
            for call, args in operations:
                with self.assertRaises(ValueError): call(*args)
                self.assertEqual(stock.snapshot(), {'a': 7})
                self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(KeyError): stock.adjust('missing', 1)
            self.assertEqual(path.read_bytes(), original)
    def test_invalid_storage_is_reported_without_overwrite(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / 'stock.json'
            for text in ['broken {', '[]', '{"a": -1}', '{"a": true}', '{"": 2}', '{"a": 1.5}']:
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError): m.Inventory(path)
                self.assertEqual(path.read_text(encoding='utf-8'), text)
    def test_existing_reporting(self):
        import report
        self.assertEqual(report.total_units({'x': 4, 'y': 11}), 15)
''',
}


def oracle_source(case):
    module = 'main' if case in {'todo_memory', 'text_statistics'} else 'service'
    return ('''import importlib, json, random, sys, tempfile, unittest
from pathlib import Path
root = sys.argv.pop()
sys.path.insert(0, root)
m = importlib.import_module(''' + repr(module) + ''')
class Acceptance(unittest.TestCase):
''' + TESTS[case] + '''
if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Acceptance)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    ok = result.wasSuccessful() and result.testsRun > 0 and not result.skipped
    print('IGRIS_EXTERNAL_RESULT=' + json.dumps({'ok': ok, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}))
    raise SystemExit(0 if ok else 1)
''')
