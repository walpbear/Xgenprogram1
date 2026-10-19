"""Offline Maya adapter contract checks. These do not run Maya or author real Alembic."""
import importlib
import json
import shlex
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

for name in ['maya','maya.cmds','maya.mel','maya.api','maya.api.OpenMaya']:
    sys.modules.setdefault(name,types.ModuleType(name))
bridge=importlib.import_module('FurBrushBridge.maya_bridge')


class FakeCmds:
    def __init__(self, fail=False):
        self.fail=fail;self.nodes=set();self.curves={};self.index=0
        self.selection=['|originalHair'];self.deleted=[];self.jobs=[];self.attributes={}
    def ls(self,*args,**kw):
        return self.selection[:] if kw.get('selection') else list(args)
    def objExists(self,n):return n in self.nodes or n=='|originalHair'
    def currentUnit(self,**kw):return 'm'  # exercises explicit cm -> UI conversion
    def currentTime(self,**kw):return 12
    def undoInfo(self,**kw):pass
    def group(self,**kw):self.nodes.add('|stage');return '|stage'
    def curve(self,**kw):
        self.index+=1;n='curve'+str(self.index);self.curves[n]=kw['point'];self.nodes.add(n);return n
    def parent(self,curve,stage):
        n=stage+'|'+curve;self.curves[n]=self.curves[curve];self.nodes.add(n);return [n]
    def listRelatives(self,node,**kw):return [node+'|shape']
    def addAttr(self,node,**kw):pass
    def setAttr(self,name,value,**kw):self.attributes[name]=value
    def select(self,nodes=None,**kw):self.selection=[] if kw.get('clear') else list(nodes)
    def delete(self,node):self.deleted.append(node);self.nodes.discard(node)
    def AbcExport(self,j):
        self.jobs.append(j)
        if self.fail:raise RuntimeError('simulated Maya export error')
        args=shlex.split(j);path=args[args.index('-file')+1]
        Path(path).write_bytes(b'Ogawa'+b'\0'*32)  # stub output, not real Alembic validation


class ExportTests(unittest.TestCase):
    def run_export(self,fail=False):
        fake=FakeCmds(fail);arrays={}
        strands=[{'layer_id':1,'points':[(100,200,300),(100,210,300)],'points_world_cm':[(100,200,300),(100,210,300)]},
                 {'layer_id':4,'points':[(400,500,600),(400,510,600)],'points_world_cm':[(400,500,600),(400,510,600)]}]
        order=lambda stage:['|stage|curve2|shape','|stage|curve1|shape']
        attr=lambda node,name,kind,values,**kw:arrays.update({name:list(values)})
        return fake,strands,order,attr,arrays
    def test_export_stages_cm_and_metadata_in_actual_dag_order(self):
        fake,strands,order,attr,arrays=self.run_export()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'hair with spaces.abc'
            with patch.object(bridge,'cmds',fake),patch.object(bridge,'_plugin'),patch.object(bridge,'collect_curves',return_value=strands),patch.object(bridge,'_dag_curve_order',order),patch.object(bridge,'_array_attr',attr):
                report=bridge.export_unreal(str(path),samples=2,base_group_id=10)
            self.assertEqual(fake.curves['curve1'][0],(1,3,2))
            self.assertEqual(arrays['groom_group_id'],[14,11])
            self.assertEqual(arrays['groom_guide'],[0,0])
            self.assertEqual(report['import_conversion']['rotation'],[0,0,0])
            self.assertEqual(json.loads(Path(str(path)+'.furbrush.json').read_text())['strand_count'],2)
            self.assertEqual(fake.selection,['|originalHair'])
            self.assertEqual(fake.deleted,['|stage'])
            self.assertIn('-worldSpace',fake.jobs[0])
            self.assertEqual(fake.attributes['|stage.riCurves'],True)
    def test_failed_export_preserves_existing_file_and_cleans_scene(self):
        fake,strands,order,attr,arrays=self.run_export(fail=True)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'existing.abc';path.write_bytes(b'original file')
            with patch.object(bridge,'cmds',fake),patch.object(bridge,'_plugin'),patch.object(bridge,'collect_curves',return_value=strands),patch.object(bridge,'_dag_curve_order',order),patch.object(bridge,'_array_attr',attr):
                with self.assertRaises(RuntimeError):bridge.export_unreal(str(path),samples=2)
            self.assertEqual(path.read_bytes(),b'original file')
            self.assertEqual(fake.deleted,['|stage'])
            self.assertEqual(fake.selection,['|originalHair'])
            self.assertEqual(list(Path(directory).iterdir()),[path])
    def test_root_uv_uses_original_world_roots_not_baked_coordinates(self):
        fake,strands,order,attr,arrays=self.run_export();seen=[]
        class Mesh:
            def getClosestPoint(self,p,space):seen.append(p);return p,0
            def getUVAtPoint(self,p,space,uv_set):return p[0]/1000.,p[1]/1000.
        fake_om=types.SimpleNamespace(MPoint=lambda *p:p,MSpace=types.SimpleNamespace(kWorld=0))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(bridge,'cmds',fake),patch.object(bridge,'om',fake_om),patch.object(bridge,'_plugin'),patch.object(bridge,'collect_curves',return_value=strands),patch.object(bridge,'_dag_curve_order',order),patch.object(bridge,'_array_attr',attr),patch.object(bridge,'_scalp_mesh',return_value=(Mesh(),'map1')):
                bridge.export_unreal(str(Path(directory)/'uv.abc'),samples=2,scalp='|scalp')
        self.assertEqual(seen,[(400,500,600),(100,200,300)])
        self.assertEqual(arrays['groom_root_uv'],[(.4,.5,0),(.1,.2,0)])


if __name__=='__main__':unittest.main()
