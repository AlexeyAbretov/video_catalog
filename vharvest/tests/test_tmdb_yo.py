import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test@localhost/test")

from app.enrich import _prefer_overview, choose_tmdb, tmdb_bridge_query


def _film(title: str, original: str, date: str, movie_id: int = 490132) -> dict:
    return {
        "id": movie_id,
        "title": title,
        "original_title": original,
        "release_date": date,
    }


class _Search:
    def __init__(self, pages: dict[tuple, list[dict]]):
        self.pages = pages
        self.calls: list[tuple[str, int | None]] = []

    def search(self, title: str, year: int | None) -> list[dict]:
        self.calls.append((title, year))
        return list(self.pages.get((title, year), []))


class TmdbYoTests(unittest.TestCase):
    def test_yo_spelling_finds_the_film(self):
        search = _Search(
            {
                ("Зелёная книга", 2018): [
                    _film("Зелёная книга", "Green Book", "2018-11-16")
                ],
            }
        )
        status, candidate, score = choose_tmdb(search, "Зеленая книга", 2018)
        self.assertEqual(status, "matched")
        self.assertEqual(candidate["id"], 490132)
        self.assertGreaterEqual(score, 0.78)
        self.assertIn(("Зелёная книга", 2018), search.calls)
        self.assertNotIn(("Зёлёная книга", 2018), search.calls)

    def test_reverse_yo_spelling(self):
        search = _Search(
            {
                ("Зеленая книга", 2018): [
                    _film("Зеленая книга", "Green Book", "2018-11-16")
                ],
            }
        )
        status, candidate, _score = choose_tmdb(search, "Зелёная книга", 2018)
        self.assertEqual(status, "matched")
        self.assertEqual(candidate["id"], 490132)

    def test_confident_hit_skips_extra_queries(self):
        search = _Search(
            {
                ("Зеленая книга", 2018): [
                    _film("Зеленая книга", "Green Book", "2018-11-16")
                ],
            }
        )
        status, _candidate, _score = choose_tmdb(search, "Зеленая книга", 2018)
        self.assertEqual(status, "matched")
        self.assertEqual(search.calls, [("Зеленая книга", 2018)])

    def test_two_letters_are_tried_together(self):
        search = _Search(
            {
                ("Ёлки зелёные", 2010): [
                    _film("Ёлки зелёные", "Yolki", "2010-01-01", 1)
                ],
            }
        )
        status, candidate, _score = choose_tmdb(search, "Елки зеленые", 2010)
        self.assertEqual(status, "matched")
        self.assertEqual(candidate["id"], 1)


class OverviewTests(unittest.TestCase):
    def test_keeps_the_longer_russian_text(self):
        short = "Короткий синопсис."
        long = "Длинное описание сюжета, которое не надо затирать коротким."
        self.assertEqual(_prefer_overview(short, long), long)
        self.assertEqual(_prefer_overview(long, short), long)
        self.assertEqual(_prefer_overview(long, "A longer English plot that should not replace Russian."), long)
        self.assertEqual(_prefer_overview("English only.", short), short)
        self.assertEqual(_prefer_overview(None, ""), None)


class BridgeTests(unittest.TestCase):
    def test_english_title_is_used_only_as_a_fallback(self):
        self.assertEqual(tmdb_bridge_query("Зеленая книга", "Green Book", None), "Green Book")
        self.assertIsNone(tmdb_bridge_query("Green Book", "Green Book", None))
        self.assertIsNone(tmdb_bridge_query("Зеленая книга", "Green Book", 490132))
        self.assertIsNone(tmdb_bridge_query("Зеленая книга", "  ", None))


if __name__ == "__main__":
    unittest.main()
