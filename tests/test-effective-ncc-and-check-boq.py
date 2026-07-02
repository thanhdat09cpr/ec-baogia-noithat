"""
Khóa hợp đồng cho nâng cấp lõi Phần A:
  - effective_ncc(): ưu tiên don_gia_ncc (trọn gói), fallback VL+NC, None khi trống.
  - check_boq.check(): bắt đúng các lỗi luật (thiếu diễn giải, cửa thiếu R×C, rèm tính bộ,
    khu ướt lát sàn thiếu ốp tường, phòng config chưa bóc, giá ncc lệch VL+NC).

Không cần fixture project thật — tự dựng project tạm trong tempdir.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_boq import check  # noqa: E402
from lib_boq import effective_ncc  # noqa: E402


def _write(project, name, header, rows):
    (project / "02-boq").mkdir(parents=True, exist_ok=True)
    lines = [header] + rows
    (project / "02-boq" / name).write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _config(project, phong, scope=("I.1", "I.2", "I.3", "I.4")):
    cfg = {"du_an": "T", "dia_diem": "", "hang_muc": "", "profit_percent": 10,
           "vat_percent": 8, "preliminaries_lumpsum": 0, "scope": list(scope), "phong": phong}
    project.mkdir(parents=True, exist_ok=True)
    (project / "cau-hinh.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


class EffectiveNccTest(unittest.TestCase):
    def test_tron_goi_uu_tien(self):
        self.assertEqual(effective_ncc(999, 100, 50), 999)

    def test_fallback_vl_nc(self):
        self.assertEqual(effective_ncc(None, 100, 50), 150)

    def test_chi_vl(self):
        self.assertEqual(effective_ncc(None, 100, None), 100)

    def test_trong_het(self):
        self.assertIsNone(effective_ncc(None, None, None))


class CheckBoqTest(unittest.TestCase):
    NEW_HDR = ("nhom_ma,nhom_ten,ky_hieu,hang_muc,quy_cach,don_vi,dien_giai,kl_1phong,"
               "don_gia_vl,don_gia_nc,don_gia_ncc,do_tin_cay,ghi_chu")

    def _codes(self, findings):
        return {f["code"] for f in findings}

    def test_bat_loi_do_bo_tach(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d) / "p"
            _config(project, [{"ma": "WC1", "ten": "WC 1", "so_luong": 1},
                              {"ma": "PN1", "ten": "Phong ngu", "so_luong": 1}])
            # WC1: lát sàn m2 thiếu diễn giải, không ốp tường, rèm tính bộ, cửa thiếu R×C
            _write(project, "WC1.csv", self.NEW_HDR, [
                "I.2,HT,,Lat san gach WC,300x300,m2,,4,,,250000,cao,",
                "I.4,TT,,Rem cua so,vai,bo,,1,,,900000,cao,",
                "I.3,Cua,D-01,Cua WC,,cai,,1,,,1200000,cao,",
            ])
            # PN1 vắng mặt file -> C-missing
            findings, stats = check(str(project))
            codes = self._codes(findings)
            self.assertIn("A-diengiai", codes)   # lát sàn m2 thiếu diễn giải
            self.assertIn("A-rem", codes)        # rèm tính bộ
            self.assertIn("A-kichthuoc", codes)  # cửa thiếu R×C
            self.assertIn("C-optuong", codes)    # ướt: lát sàn không ốp tường
            self.assertIn("C-missing", codes)    # PN1 chưa bóc
            self.assertGreater(stats["warn"], 0)

    def test_sach_khong_canh_bao(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d) / "p"
            _config(project, [{"ma": "PN1", "ten": "Phong ngu", "so_luong": 1}], scope=("I.1",))
            _write(project, "PN1.csv", self.NEW_HDR, [
                "I.1,Do roi,LF-01,Giuong,1800x2000,cai,,1,,,5000000,cao,",
                "I.1,Do roi,LF-02,Tu dau giuong,450x400,cai,,2,300000,200000,,cao,",
            ])
            findings, stats = check(str(project))
            self.assertEqual(stats["warn"], 0)

    def test_gia_lech_ncc_vs_vlnc(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d) / "p"
            _config(project, [{"ma": "PN1", "ten": "P", "so_luong": 1}], scope=("I.1",))
            _write(project, "PN1.csv", self.NEW_HDR, [
                "I.1,Do roi,LF-01,Ghe,W500,cai,,1,100000,50000,999999,cao,",
            ])
            findings, _ = check(str(project))
            self.assertIn("gia-lech", self._codes(findings))


if __name__ == "__main__":
    unittest.main()
