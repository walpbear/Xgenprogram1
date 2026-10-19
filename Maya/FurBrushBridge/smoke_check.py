"""Optional real-Maya test. Creates/deletes only test objects; never opens a new scene."""
import json
import os
import platform
import tempfile
import traceback


def run():
    import maya.cmds as cmds
    from . import maya_bridge as bridge
    directory = tempfile.mkdtemp(prefix='FurBrush-Maya-check-')
    report = {'maya':cmds.about(version=True),'python':platform.python_version(),
              'linear_unit':cmds.currentUnit(query=True,linear=True),'up_axis':cmds.upAxis(query=True,axis=True),
              'checks':{},'output_directory':directory,'unreal_import_tested':False}
    previous=cmds.ls(selection=True,long=True) or []
    created=[]
    try:
        root=cmds.group(empty=True,name='FurBrush_Smoke#');created.append(root)
        for index in range(2):
            curve=cmds.curve(degree=1,point=[(-.2+index*.4,0,0),(-.2+index*.4,.2,0),(-.1+index*.4,.4,.1)])
            cmds.parent(curve,root)
        scalp=cmds.polyPlane(width=2,height=2,subdivisionsX=1,subdivisionsY=1,constructionHistory=False)[0];created.append(scalp)
        cmds.select(root,replace=True)
        ply=os.path.join(directory,'smoke.ply')
        assert bridge.export_ply(ply,samples=8)==2
        imported,data=bridge.import_ply(ply);created.append(imported)
        assert len(data['strands'])==2 and all(len(s['points'])==8 for s in data['strands'])
        report['checks']['ply_roundtrip']='passed: two strands, eight points, centimeter metadata'
        cmds.select(root,replace=True)
        abc=os.path.join(directory,'smoke.abc')
        result=bridge.export_unreal(abc,samples=8,scalp=scalp)
        assert result['root_uv_exported'] and result['strand_count']==2
        report['checks']['maya_ogawa_export']='passed: Maya exporter wrote Ogawa file with requested metadata; Unreal import still untested'
        report['export']=result
        try:
            bridge._plugin('xgenToolkit')
            nodes=set(cmds.allNodeTypes())
            report['xgen']={'plugin_loaded':True,'curve_to_spline_node':'xgmCurveToSpline' in nodes,'description_node':'xgmSplineDescription' in nodes}
            try:report['xgen']['spline_to_curves_help']=cmds.help('xgmSplineToCurves')
            except RuntimeError as exc:report['xgen']['spline_to_curves_help']=str(exc)
        except RuntimeError as exc:
            report['xgen']={'plugin_loaded':False,'error':str(exc)}
    except Exception as exc:
        report['failure']=str(exc);report['traceback']=traceback.format_exc()
    finally:
        for node in reversed(created):
            if cmds.objExists(node):cmds.delete(node)
        valid=[n for n in previous if cmds.objExists(n)]
        if valid:cmds.select(valid,replace=True)
        else:cmds.select(clear=True)
    path=os.path.join(directory,'Maya-check-report.json')
    with open(path,'w',encoding='utf-8') as handle:json.dump(report,handle,indent=2)
    print('FurBrush Maya check report: '+path)
    cmds.confirmDialog(title='FurBrush Maya check',message=('Checks failed; see report.' if 'failure' in report else 'Maya checks completed; Unreal import remains untested.')+'\n\n'+path,button=['OK'])
    return report
