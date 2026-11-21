"""Títulos de la Filmoteca: lo que añade al <h1> que no es el título.

    python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper_modificado import analizar_h1, detectar_sede  # noqa: E402

CASOS = [
    ("BERLÍN. Uno, dos, tres", dict(titulo="Uno, dos, tres", ciclo="Berlín")),
    ("SAN FRANCISCO. Vértigo (Vertigo, EEUU, 1958)",
     dict(titulo="Vértigo", ciclo="San Francisco", titulo_original="Vertigo", anio=1958)),
    ("Todos lo sabían (España, 2025) - TAFALLA",
     dict(titulo="Todos lo sabían", localidad="Tafalla", anio=2025, nota="")),
    ("Sustraiak (Raíces perdidas) TAFALLA",
     dict(titulo="Sustraiak", localidad="Tafalla", titulo_original="Raíces perdidas")),
    ("La quimera - (ALSASUA)", dict(titulo="La quimera", localidad="Alsasua")),
    ("Emilia Pérez - CIVIVOX CONDESTABLE",
     dict(titulo="Emilia Pérez", localidad="Civivox Condestable")),
    ("Anatomía de una caída (Anatomie d'une chute) - CIVIVOX CONDESTABLE",
     dict(titulo="Anatomía de una caída", titulo_original="Anatomie d'une chute")),
    ("Cowboy de medianoche (Midnight Cowboy, Estados Unidos, 1969) Sesión con concierto.",
     dict(titulo="Cowboy de medianoche", nota="Sesión con concierto", anio=1969, localidad=None)),
    ("Sutura simple (2025) / Wuhan Zona Cero (2021)",
     dict(titulo="Sutura simple / Wuhan Zona Cero", programa=["Sutura simple", "Wuhan Zona Cero"])),
    ("Contadores / Por fin me jubilo / Tito - TAFALLA",
     dict(programa=["Contadores", "Por fin me jubilo", "Tito"], localidad="Tafalla")),
    ("Katanga / La danza de los escorpiones (Katanga / La danse des scorpions, Burkina Faso, 2024)",
     dict(titulo="Katanga / La danza de los escorpiones", programa=[], anio=2024)),
    ("El acontecimiento (L'événement)", dict(titulo="El acontecimiento", titulo_original="L'événement")),
    ("Batman (EEUU, 1989)", dict(titulo="Batman", anio=1989, localidad=None, titulo_original=None)),
    ("TCB: The Toni Cade Bambara School of Organizing",
     dict(titulo="TCB: The Toni Cade Bambara School of Organizing", ciclo=None)),
    ("El Dr. Frankenstein (1931)", dict(titulo="El Dr. Frankenstein", anio=1931)),
    ("CIMASUB I", dict(titulo="CIMASUB I", ciclo=None, localidad=None)),
]


class TestAnalizarH1(unittest.TestCase):
    def test_casos_reales(self):
        for h1, esperado in CASOS:
            resultado = analizar_h1(h1)
            for campo, valor in esperado.items():
                with self.subTest(h1=h1, campo=campo):
                    self.assertEqual(resultado[campo], valor)


class TestDetectarSede(unittest.TestCase):
    def test_sedes(self):
        self.assertEqual(detectar_sede("Sábado, 3 de octubre 19:00 - CONDESTABLE"), "Civivox Condestable")
        self.assertEqual(detectar_sede("Viernes 7 de noviembre 19:00 - TAFALLA"), "Filmoteca en Tafalla")
        self.assertEqual(detectar_sede("Viernes 7 de noviembre 19:00", "", "Tafalla"), "Filmoteca en Tafalla")
        # Un ciclo en mayúsculas en el <title> no es una sede
        self.assertEqual(detectar_sede("Viernes 19:00", "Vértigo - SAN FRANCISCO - Filmoteca de Navarra"),
                         "Filmoteca de Navarra")


if __name__ == '__main__':
    unittest.main()
