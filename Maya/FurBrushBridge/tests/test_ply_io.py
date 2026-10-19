import tempfile
import unittest
from pathlib import Path
from FurBrushBridge import ply_io


class PlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'groom.ply'
    def tearDown(self):
        self.temp.cleanup()
    def write(self, text):
        self.path.write_text(text, encoding='utf-8')
        return ply_io.read_ply(str(self.path))
    def test_roundtrip_variable_strands_unicode_layers(self):
        strands=[{'layer_id':3,'points':[(1.25,2,3),(2.5,3,4)]},
                 {'layer_id':7,'points':[(-1,0,0),(0,1,0),(1,2,0)]}]
        ply_io.write_ply(str(self.path),strands,{3:'Front fringe',7:'耳 fur'})
        data=ply_io.read_ply(str(self.path))
        self.assertEqual([s['points'] for s in data['strands']],[s['points'] for s in strands])
        self.assertEqual(data['layers'][7],'耳 fur')
        self.assertFalse(data['assumed_unit'])
    def test_mm_and_reordered_fields_with_colliding_layer_curve_ids(self):
        data=self.write('ply\nformat ascii 1.0\ncomment sisir_unit mm\nelement vertex 4\nproperty int curve_id\nproperty int layer_id\nproperty float z\nproperty float x\nproperty float y\nend_header\n0 1 30 10 20\n0 2 60 40 50\n0 1 40 20 30\n0 2 70 50 60\n')
        self.assertEqual(len(data['strands']),2)
        self.assertEqual(data['strands'][0]['points'][0],(1,2,3))
        self.assertEqual(data['strands'][1]['points'][1],(5,6,7))
    def test_fixed_legacy_points(self):
        data=self.write('ply\nformat ascii 1.0\ncomment points_per_strand 2\nelement vertex 4\nproperty float x\nproperty float y\nproperty float z\nend_header\n0 0 0\n1 1 1\n2 2 2\n3 3 3\n')
        self.assertEqual(len(data['strands']),2)
        self.assertTrue(data['assumed_unit'])
    def test_rejects_truncated_ambiguous_nan_and_interior_roots(self):
        prefix='ply\nformat ascii 1.0\nelement vertex 2\nproperty float x\nproperty float y\nproperty float z\n'
        examples=[prefix+'end_header\n0 0 0\n1 1 1\n',
                  prefix+'property int curve_id\nend_header\n0 0 0 0\n',
                  prefix+'property int curve_id\nend_header\nnan 0 0 0\n1 1 1 0\n',
                  prefix+'property int curve_id\nproperty int anchor\nend_header\n0 0 0 0 0\n1 1 1 0 1\n']
        for text in examples:
            with self.subTest(text=text):
                self.path.write_text(text)
                with self.assertRaises(ValueError):ply_io.read_ply(str(self.path))
    def test_rejects_binary_and_incomplete_header(self):
        for text in ['ply\nformat binary_little_endian 1.0\nelement vertex 0\nend_header\n','ply\nformat ascii 1.0\n']:
            self.path.write_text(text)
            with self.assertRaises(ValueError):ply_io.read_ply(str(self.path))
    def test_axis_roundtrip_and_unreal_mapping(self):
        p=(1,2,3)
        self.assertEqual(ply_io.yup_to_maya(ply_io.maya_to_yup(p,'z'),'z'),p)
        self.assertEqual(ply_io.unreal_point(p),(1,3,2))
        self.assertEqual(ply_io.unit_scale('m'),100)
        self.assertEqual(ply_io.unit_scale('in'),2.54)
    def test_abc_quoting_preserves_spaces_rejects_job_injection(self):
        self.assertEqual(ply_io.quote_abc(r'C:\Fur Brush\groom.abc'),'"C:/Fur Brush/groom.abc"')
        with self.assertRaises(ValueError):ply_io.quote_abc('name" -root other')


if __name__=='__main__':unittest.main()
