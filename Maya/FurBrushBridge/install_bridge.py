"""Drag this file onto Maya, or run it in Maya's Python Script Editor."""
import os
import sys
import maya.cmds as cmds
import maya.mel as mel


def install(path=None):
    if path is None:
        candidate = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in globals() else None
        if candidate and os.path.isfile(os.path.join(candidate,'FurBrushBridge','maya_bridge.py')):
            path = candidate
        else:
            result = cmds.fileDialog2(fileMode=3, caption='Choose the folder containing FurBrushBridge')
            if not result:
                return
            path = result[0]
    if os.path.basename(path) == 'FurBrushBridge':
        path = os.path.dirname(path)
    if not os.path.isfile(os.path.join(path,'FurBrushBridge','maya_bridge.py')):
        raise RuntimeError('Choose the folder containing the FurBrushBridge package.')
    command = 'import sys\np={0!r}\nif p not in sys.path: sys.path.insert(0,p)\nimport FurBrushBridge\nFurBrushBridge.show()'.format(path)
    shelf_top = mel.eval('$furBrushShelfTop=$gShelfTopLevel')
    shelf = cmds.shelfTabLayout(shelf_top,query=True,selectTab=True)
    cmds.shelfButton(parent=shelf,label='FurBrush',annotation='FurBrush Maya / XGen / Unreal bridge',sourceType='python',command=command,image='commandButton.png')
    exec(command)


def onMayaDroppedPythonFile(*args):
    install()


if __name__ == '__main__':
    install()
