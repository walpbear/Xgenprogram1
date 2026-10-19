from pathlib import Path
import sys,struct,os,argparse
from PySide6.QtWidgets import *
from PySide6.QtGui import QFontDatabase,QIcon,QImage
from PySide6.QtCore import Qt,qInstallMessageHandler
import pefile
parser=argparse.ArgumentParser()
parser.add_argument('--package',type=Path,required=True)
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=args.package.resolve();args.repo=args.repo.resolve();args.output=args.output.resolve()
os.chdir(root)
messages=[]
def msg(kind,ctx,text):
 messages.append(text)
qInstallMessageHandler(msg)
app=QApplication([]);app.setStyle('Fusion')
fontid=QFontDatabase.addApplicationFont(str(root/'fonts/GeistPixel-Regular-VariableFont_ELSH.ttf'))
assert fontid>=0
assert 'Geist Pixel' in QFontDatabase.applicationFontFamilies(fontid)
app.setStyleSheet((root/'themes/Windows7-Retro.qss').read_text())
app.setWindowIcon(QIcon(str(root/'FurBrush.ico')))
w=QMainWindow();w.resize(920,640);w.setWindowTitle('FurBrush - representative Qt theme preview')
for n in ['File','Edit','View','Modules']:w.menuBar().addMenu(n).addAction('Example item')
tool=w.addToolBar('Modules')
for n in ['Guides','Hair','Cards','Texture']:
 a=tool.addAction(n);a.setCheckable(True)
 if n=='Guides':a.setChecked(True)
body=QWidget();layout=QVBoxLayout(body)
title=QLabel('Windows 7-inspired theme preview');title.setObjectName('moduleLabel');layout.addWidget(title)
layout.addWidget(QLabel('Representative Qt controls; this is not a screenshot of the full Windows application.'))
tabs=QTabWidget();tab=QWidget();form=QFormLayout(tab)
name=QLineEdit('FurBrush groom');form.addRow('Name',name)
combo=QComboBox();combo.addItems(['Guides','Hair','Cards']);form.addRow('Module',combo)
spin=QDoubleSpinBox();spin.setRange(0,100);spin.setValue(12.5);form.addRow('Brush size',spin)
slider=QSlider(Qt.Horizontal);slider.setValue(65);form.addRow('Strength',slider)
check=QCheckBox('Show guide curves');check.setChecked(True);form.addRow('',check)
row=QWidget();r=QHBoxLayout(row)
for n in ['Apply','Reset','Disabled']:
 b=QPushButton(n);b.setEnabled(n!='Disabled');r.addWidget(b)
form.addRow('',row);tabs.addTab(tab,'Brush settings');tabs.addTab(QWidget(),'Materials');layout.addWidget(tabs)
items=QTreeWidget();items.setHeaderLabels(['Layer','Type']);items.setAlternatingRowColors(True)
for n in ['Fringe','Side tufts','Neck fur']:QTreeWidgetItem(items,[n,'Guide layer'])
layout.addWidget(items)
p=QProgressBar();p.setValue(68);layout.addWidget(p)
w.setCentralWidget(body);w.statusBar().showMessage('Geist Pixel loaded - editable QSS theme')
w.show();app.processEvents();app.processEvents()
w.grab().save(str(args.output))
# Extract and decode the actual patched Qt resources, not the separate ICO.
exe=pefile.PE(str(root/'FurBrush.exe'))
original=pefile.PE(str(args.repo/'Sisir.exe'))
for off in [0x362164,0x3663e9]:
 rva=original.get_rva_from_offset(off)
 size=struct.unpack('>I',exe.get_data(rva-4,4))[0]
 data=exe.get_data(rva,size)
 if off==0x362164:
  icon=QIcon();img=QImage.fromData(data,'ICO');assert not img.isNull()
 else:img=QImage.fromData(data,'PNG');assert not img.isNull()
 assert img.width()==256 and img.height()==256
# Check inherited window icon on a real Qt save/discard message box.
box=QMessageBox(w);box.setWindowTitle('Save changes?');box.setText('Save changes before closing?')
box.setStandardButtons(QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
assert box.windowIcon().cacheKey()==app.windowIcon().cacheKey()
errors=[m for m in messages if any(s in m.lower() for s in ['could not parse','unknown property','could not create pixmap'])]
assert not errors,errors
print('PASS: Geist Pixel loaded, QSS rendered in Qt '+__import__('PySide6').__version__+', no stylesheet parsing/property errors, both patched embedded icons decoded, and Qt save dialog inherited the application icon.')
for m in messages:print('Qt note:',m)
