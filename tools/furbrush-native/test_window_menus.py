from pathlib import Path
import argparse,json,struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,default=Path('/workspace/FurBrush-package'));ap.add_argument('--analysis',type=Path,default=Path('/workspace/furbrush-analysis'));args=ap.parse_args()
p=pefile.PE(str(args.package/'FurBrush.exe'));meta=json.loads((args.analysis/'native-patch.json').read_text());imagebase=p.OPTIONAL_HEADER.ImageBase
imports={e.name.decode():e.address-imagebase for d in p.DIRECTORY_ENTRY_IMPORT for e in d.imports if e.name}
addmenu='?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z';addaction='?addAction@QWidget@@QEAAXPEAVQAction@@@Z';newaction='?addAction@QWidget@@QEAAPEAVQAction@@AEBVQString@@@Z';menubar='?menuBar@QMainWindow@@QEBAPEAVQMenuBar@@XZ';ctor='??0QString@@QEAA@PEBD@Z';dtor='??1QString@@QEAA@XZ'
names=[addmenu,addaction,newaction,menubar,ctor,dtor,'GetModuleHandleW','GetProcAddress','toggle']
stubs={n:0x600000+i*0x100 for i,n in enumerate(names)}
regs=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
def test(base,kind,failure):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x600000);u.mem_write(base,p.get_memory_mapped_image());u.mem_map(0x600000,0x1000);u.mem_map(0x700000,0x40000);u.mem_map(0x900000,0x10000)
 for n,stub in stubs.items():
  u.mem_write(stub,b'\xc3')
  if n in imports:u.mem_write(base+imports[n],struct.pack('<Q',stub))
 main=0x701000;bar=0x702000;filetitle=0x703000;filemenu=0x704000;windowmenu=0x705000;helpmenu=0x720000;abouttitle=0x721000;aboutaction=0x722000;infomenu=0x723000
 strings={filetitle:b'File',abouttitle:b'About'};added=[];menus=[];destroyed=[];toggled=[]
 docks=[0x710000+i*0x1000 for i in range(4)];actions=[0x718000+i*0x100 for i in range(4)]
 for i,offset in enumerate([0x1c8,0x1d0,0x1d8,0x1e0]):u.mem_write(main+offset,struct.pack('<Q',0 if failure=='all_docks_missing' or (failure=='one_dock_missing' and i==2) else docks[i]))
 for i,r in enumerate(regs):u.reg_write(r,main if r==UC_X86_REG_RDI else 0x123000+i)
 rsp=0x90f008;end=0x600f00;u.mem_write(end,b'\x90');u.mem_write(rsp,struct.pack('<Q',end));u.reg_write(UC_X86_REG_RSP,rsp)
 u.reg_write(UC_X86_REG_RCX,bar if kind=='window' else helpmenu);u.reg_write(UC_X86_REG_RDX,filetitle if kind=='window' else abouttitle)
 def readstr(addr,wide=False):
  data=bytearray();step=2 if wide else 1
  while True:
   b=bytes(u.mem_read(addr+len(data),step))
   if b==b'\0'*step:return data.decode('utf-16le') if wide else bytes(data)
   data+=b
 def hook(uc,addr,size,unused):
  if addr==end:uc.emu_stop();return
  if addr not in stubs.values():return
  name=next(n for n,a in stubs.items() if a==addr);sp=uc.reg_read(UC_X86_REG_RSP);assert sp%16==8
  rcx=uc.reg_read(UC_X86_REG_RCX);rdx=uc.reg_read(UC_X86_REG_RDX);result=0
  if name==ctor:strings[rcx]=readstr(rdx);result=rcx
  elif name==dtor:assert rcx in strings;destroyed.append(strings.pop(rcx))
  elif name==addmenu:
   assert rcx==bar
   title=strings[rdx];menus.append(title)
   if title==b'File':result=0 if failure=='no_file_menu' else filemenu
   elif title==b'Window':result=0 if failure=='no_window_menu' else windowmenu
   else:assert title==b'Info';result=0 if failure=='no_info_menu' else infomenu
  elif name==newaction:assert (rcx,rdx)==(helpmenu,abouttitle);result=0 if failure=='no_about_action' else aboutaction
  elif name==menubar:assert rcx==main;result=0 if failure=='no_menu_bar' else bar
  elif name=='GetModuleHandleW':assert readstr(rcx,True)=='Qt6Widgets.dll';result=0 if failure=='no_module' else 1
  elif name=='GetProcAddress':assert rcx==1 and readstr(rdx)==b'?toggleViewAction@QDockWidget@@QEBAPEAVQAction@@XZ';result=0 if failure=='no_export' else stubs['toggle']
  elif name=='toggle':
   assert rcx in docks;i=docks.index(rcx);toggled.append(i);result=0 if failure=='one_action_missing' and i==1 else actions[i]
  elif name==addaction:
   if kind=='window':assert rcx==windowmenu and rdx in actions;added.append(actions.index(rdx))
   else:assert (rcx,rdx)==(infomenu,aboutaction);added.append('About')
  for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11]:uc.reg_write(r,0xdeadbeef)
  uc.mem_write(sp+8,b'\xcc'*32);uc.reg_write(UC_X86_REG_RAX,result)
 u.hook_add(UC_HOOK_CODE,hook)
 entry=int(meta['window_menu_helper_va' if kind=='window' else 'info_menu_helper_va'],16)-imagebase+base;u.emu_start(entry,end+1,count=2000)
 assert u.reg_read(UC_X86_REG_RIP)==end and u.reg_read(UC_X86_REG_RSP)==rsp+8
 for i,r in enumerate(regs):assert u.reg_read(r)==(main if r==UC_X86_REG_RDI else 0x123000+i)
 if kind=='window':
  assert u.reg_read(UC_X86_REG_RAX)==(0 if failure=='no_file_menu' else filemenu)
  expected=[] if failure in ['no_file_menu','no_window_menu','no_module','no_export','all_docks_missing'] else [i for i in range(4) if not(failure=='one_dock_missing' and i==2) and not(failure=='one_action_missing' and i==1)]
  assert added==expected,(failure,added)
  assert menus==([b'File'] if failure=='no_file_menu' else [b'File',b'Window'])
 else:
  assert u.reg_read(UC_X86_REG_RAX)==(0 if failure=='no_about_action' else aboutaction)
  assert added==(['About'] if failure is None else [])
 assert len(strings)==2,'Temporary QString not destroyed'
count=0
for base in [0x140000000,0x180000000]:
 for f in [None,'no_file_menu','no_window_menu','no_module','no_export','one_dock_missing','one_action_missing','all_docks_missing']:test(base,'window',f);count+=1
 for f in [None,'no_about_action','no_menu_bar','no_info_menu']:test(base,'info',f);count+=1
print('PASS:',count,'Window/Info helper cases: File then Window ordering; four real dock toggles; original About action reused; missing-object fallbacks; temporary QString cleanup; ASLR; ABI/return preservation.')
