import unittest

from app.translit import cyrillic_variant, looks_like_ru_latin, ordered_queries, should_try_alternate


class TranslitTests(unittest.TestCase):
    def test_russian_titles_written_in_latin(self):
        cases = {
            "Koloniya": "Колония",
            "Koloniya ELEKTRI4KA": "Колония",
            "Chernoknizhnik": "Чернокнижник",
            "Oxota za tenyu": "Охота за теню",
            "Krepkii Oreshek 4.0": "Крепкий орешек 4.0",
            "Ja slezhu za toboj": "Я слежу за тобой",
            "Mstiteli Voina beskonechnosti": "Мстители война бесконечности",
            "Pyatyi Element": "Пятый елемент",
            "Ubiica": "Убийца",
            "Ubiitsa": "Убийца",
            "Nastoyashchie detektivy": "Настоящие детективы",
            "Klyuch ot vseh dverey": "Ключ от всех дверей",
            "Kostyanoi tomagavk": "Костяной томагавк",
            "Myatezh": "Мятеж",
            "Bezumnaya svadba": "Безумная свадба",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(cyrillic_variant(source), expected)

    def test_koloniya_is_searched_in_cyrillic_first(self):
        self.assertTrue(looks_like_ru_latin("Koloniya"))
        self.assertEqual(ordered_queries("Koloniya"), ["Колония", "Koloniya"])
        self.assertEqual(ordered_queries("Koloniya ELEKTRI4KA"), ["Колония", "Koloniya"])
        self.assertFalse(should_try_alternate("Koloniya", 1.0))
        self.assertTrue(should_try_alternate("Koloniya", 0.6))

    def test_english_titles_stay_first(self):
        self.assertFalse(looks_like_ru_latin("Die Hard"))
        self.assertFalse(looks_like_ru_latin("Royal"))
        self.assertFalse(looks_like_ru_latin("Shaun of the Dead"))
        self.assertEqual(ordered_queries("Die Hard")[0], "Die Hard")
        self.assertFalse(should_try_alternate("Die Hard", 0.95))
        self.assertEqual(ordered_queries("Колония"), ["Колония"])
        self.assertIsNone(cyrillic_variant("Minecraft в кино"))


if __name__ == "__main__":
    unittest.main()
