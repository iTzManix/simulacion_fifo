"""Verificaciones del modelo, inferencia numérica y exportaciones."""
import csv
import math
import random
import tempfile
import unittest
from collections import deque
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import simulacion as s


class Pruebas(unittest.TestCase):
    def test_tablas_estadisticas_independientes(self):
        # Cuantiles tabulados de Student y colas chi-cuadrado conocidas.
        for gl, valor in [(1, 12.7062047364), (4, 2.7764451052), (30, 2.0422724563)]:
            self.assertAlmostEqual(s.t_critico(gl), valor, places=8)
        self.assertAlmostEqual(s.chi_supervivencia(5.9914645471, 2), .05, places=10)
        self.assertAlmostEqual(s.chi_supervivencia(3.8414588207, 1), .05, places=10)
        self.assertAlmostEqual(s.chi_supervivencia(9.4877290368, 4), .05, places=10)

    def test_trayectoria_manual_y_empate(self):
        cs = s.trayectoria([1, 1, 4, 5], [2, 5, 1, 2])
        self.assertEqual([(c.llegada, c.inicio, c.fin, c.espera) for c in cs],
                         [(1, 1, 3, 0), (2, 3, 8, 1), (6, 8, 9, 2), (11, 11, 13, 0)])
        empate = s.trayectoria([1, 2], [2, 1])
        self.assertEqual(empate[-1].espera, 0)
        self.assertEqual(s.metricas(empate)['cola_maxima'], 0)

    def test_referencia_independiente_por_eventos(self):
        # Referencia con reloj entero y cola explícita, distinta a la recurrencia.
        modelo = {'llegadas':'poisson_desplazada', 'servicio':'binomial_desplazada'}
        cs = s.simular(87, 100, modelo)
        pendientes = {c.llegada: c for c in cs}
        cola, resultados, activo = deque(), {}, None
        for reloj in range(cs[-1].fin+1):
            if activo is not None and reloj == activo[1]:
                activo = None
            if reloj in pendientes:
                cola.append(pendientes[reloj])
            if activo is None and cola:
                c = cola.popleft()
                activo = (c.cliente, reloj+c.servicio)
                resultados[c.cliente] = (reloj, reloj+c.servicio)
        self.assertEqual(len(resultados), 100)
        self.assertEqual(resultados, {c.cliente:(c.inicio,c.fin) for c in cs})
        area_cola = sum(sum(c.llegada <= t < c.inicio for c in cs) for t in range(cs[-1].fin))
        self.assertEqual(area_cola, sum(c.espera for c in cs))
        self.assertEqual(sum(c.servicio+c.ocio_previo for c in cs), cs[-1].fin)

    def test_inversa_fronteras_y_cola(self):
        f = s.FRECUENCIAS['llegadas']
        self.assertEqual(s.inversa(0, 'empirica', f), 1)
        self.assertEqual(s.inversa(.2, 'empirica', f), 1)
        self.assertEqual(s.inversa(math.nextafter(.2, 1), 'empirica', f), 2)
        self.assertEqual(s.inversa(.999, 'poisson_desplazada', f), 7)
        self.assertGreater(s.inversa(math.nextafter(1., 0.), 'poisson_desplazada', f), 5)
        with self.assertRaises(ValueError):
            s.inversa(1, 'empirica', f)

    def test_ajuste_seleccion_y_condiciones(self):
        ajustes = s.analizar_ajustes()
        self.assertEqual(s.seleccionar(ajustes), {'llegadas':'poisson_desplazada', 'servicio':'binomial_desplazada'})
        for a in ajustes:
            self.assertAlmostEqual(sum(a['esperadas']), 50)
            self.assertEqual(sum(a['observadas']), 50)
            if a['aplicable']:
                self.assertGreaterEqual(min(a['esperadas']), 5)
                self.assertEqual(a['gl'], len(a['grupos'])-1-a['parametros'])
            if a['modelo']=='empirica':
                self.assertFalse(a['aplicable'])

    def test_reproducibilidad_y_exportaciones(self):
        modelos = {'llegadas':'poisson_desplazada', 'servicio':'binomial_desplazada'}
        self.assertEqual(s.simular(1234, 100, modelos), s.simular(1234, 100, modelos))
        self.assertNotEqual(s.simular(1234, 100, modelos), s.simular(1235, 100, modelos))
        temporales = Path(__file__).resolve().parent/'tmp'/'pruebas'
        temporales.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporales) as tmp, redirect_stdout(StringIO()):
            ruta = Path(tmp)
            resumen = s.ejecutar(ruta)
            with (ruta/'clientes.csv').open(encoding='utf-8-sig', newline='') as f:
                clientes = list(csv.DictReader(f))
            with (ruta/'replicas.csv').open(encoding='utf-8-sig', newline='') as f:
                replicas = list(csv.DictReader(f))
            self.assertEqual(len(clientes), 100*len(replicas))
            self.assertEqual(len(replicas), resumen['total_replicas'])
            self.assertEqual(len(set(r['semilla'] for r in replicas)), len(replicas))
            self.assertTrue(resumen['cumple'])
            self.assertEqual(resumen['plan']['n_confirmacion'], 167)

    def test_momentos_generados(self):
        rng = random.Random(911)
        for variable, modelo, media, var in [('llegadas','poisson_desplazada',2.5,1.5),
                                            ('servicio','binomial_desplazada',2.9,.9975)]:
            xs = [s.inversa(rng.random(), modelo, s.FRECUENCIAS[variable]) for _ in range(30000)]
            self.assertAlmostEqual(sum(xs)/len(xs), media, delta=.035)
            self.assertAlmostEqual(sum((x-media)**2 for x in xs)/len(xs), var, delta=.06)


if __name__ == '__main__':
    unittest.main()
