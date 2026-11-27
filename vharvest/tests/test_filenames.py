import unittest

from app.filenames import parse_release_name, should_skip_file, year_conflicts


class ParseTests(unittest.TestCase):
    def test_library_names(self):
        cases = {
            "Bastarden.2023.HDRip AVC.mkv": ("Bastarden", 2023),
            "Chernoknizhnik.1989.BDRip.DUB.avi": ("Chernoknizhnik", 1989),
            "Dust.Bunny.2025.x264.WEB-DLRip - New-Team.mkv": ("Dust Bunny", 2025),
            "Hot.Fuzz.HDRip.Kubik.v.Kube.mkv": ("Hot Fuzz", None),
            "K-Pax.2001.DTheaterRip.1080p.mkv": ("K-Pax", 2001),
            "Legenda.2024.Dub.WEB-DLRip.avi": ("Legenda", 2024),
            "Minecraft в кино_2025_WEB-DLRip.avi": ("Minecraft в кино", 2025),
            "Oxota.za.tenyu.2025.WEB-DLRip.AVC.mkv": ("Oxota za tenyu", 2025),
            "Shaun.of.the.Dead.HDRip.Kubik.v.Kube.mkv": ("Shaun of the Dead", None),
            "Жмот (2016) BDRip-AVC_ivanes20031987.mkv": ("Жмот", 2016),
            "Paul (2011) BDRip.mkv": ("Paul", 2011),
            "Die Hard [1988 HDRip].avi": ("Die Hard", 1988),
            "Die.Hard.2.1990.BDRip.Dub_by_LBS.avi": ("Die Hard 2", 1990),
            "Tango_&_Cash_1989_BDRip_by_Dalemake.avi": ("Tango & Cash", 1989),
            "The Lord of the Rings The Fellowship of the Ring (2001) BDRip.mkv": (
                "The Lord of the Rings The Fellowship of the Ring",
                2001,
            ),
            "Гадкая сестра_2025_WEB-DLRip": ("Гадкая сестра", 2025),
            "Krepkii.Oreshek.4.0.2007.O.M.RUS.HDTVRip.XviD.AC3.-ENGINEER.avi": (
                "Krepkii Oreshek 4.0",
                2007,
            ),
            "Carry-On.2024.D.NF.WEB-DLRip.1.46Gb.MegaPeer.avi": ("Carry-On", 2024),
            "Lost.in.the.Stars.2022.WEB-DLRip-AVC.x264.ExKinoRay.mkv": ("Lost in the Stars", 2022),
            "Avariya.1997.RUS.BDRip.XviD.AC3.-HRIME.avi": ("Avariya", 1997),
            "Крепкий орешек-3 (ЕА + Оригинал).avi": ("Крепкий орешек-3", None),
            "Снова в деле (2025) WEB-DLRip-AVC_ivanes.mkv": ("Снова в деле", 2025),
            "Экстремальная работа (2019, Южная Корея) BDRip-AVC.mkv": ("Экстремальная работа", 2019),
            "Armageddec_2013_BDRip_by_Dalemake.avi": ("Armageddec", 2013),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(parse_release_name(name), expected)

    def test_year_conflict_needs_a_different_year_in_the_file(self):
        self.assertFalse(year_conflicts("Die Hard [1988 HDRip].avi", None, 1988))
        self.assertTrue(year_conflicts("Die Hard [1988 HDRip].avi", None, 1990))
        self.assertTrue(year_conflicts("Die Hard [1988 HDRip].avi", None, None))
        self.assertFalse(year_conflicts("Hot.Fuzz.HDRip.Kubik.v.Kube.mkv", None, 2007))

    def test_skip_samples_keep_real_titles(self):
        self.assertTrue(should_skip_file("Movie.sample.mkv"))
        self.assertTrue(should_skip_file("Movie.trailer.mkv"))
        self.assertTrue(should_skip_file("._hidden.mkv"))
        self.assertFalse(should_skip_file("Trailer.Park.Boys.mkv"))


if __name__ == "__main__":
    unittest.main()
