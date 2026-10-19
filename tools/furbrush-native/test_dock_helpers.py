from pathlib import Path
import argparse,json,struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,default=Path('/workspace/FurBrush-package'));ap.add_argument('--analysis',type=Path,default=Path('/workspace/furbrush-analysis'));args=ap.parse_args()
p=pefile.PE(str(args.package/'FurBrush.exe'));meta=json.loads((args.analysis/'native-patch.json').read_text());original_base=p.OPTIONAL_HEADER.ImageBase
imports={e.name.decode():e.address-original_base for d in p.DIRECTORY_ENTRY_IMPORT for e in d.imports if e.name}
names=['?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z','GetModuleHandleW','GetProcAddress','toggle','?addAction@QWidget@@QEAAXPEAVQAction@@@Z','?addDockWidget@QMainWindow@@QEAAXW4DockWidgetArea@Qt@@PEAVQDockWidget@@@Z','?show@QWidget@@QEAAXXZ','?raise@QWidget@@QEAAXXZ']
stubs={n:0x600000+i*0x100 for i,n in enumerate(names)}
regs=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
def test(base,kind,failure):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x500000);u.mem_write(base,p.get_memory_mapped_image());u.mem_map(0x600000,0x1000);u.mem_map(0x700000,0x10000);u.mem_map(0x800000,0x10000)
 for n,stub in stubs.items():
  u.mem_write(stub,b'\xc3')
  if n in imports:u.mem_write(base+imports[n],struct.pack('<Q',stub))
 main=0x701000;bar=0x702000;label=0x703000;menu=0x704000;dock=0x705000;action=0x706000
 u.mem_write(main+0x1e0,struct.pack('<Q',0 if failure=='no_dock' else dock))
 for i,r in enumerate(regs):u.reg_write(r,main if r==UC_X86_REG_RDI else 0x123000+i)
 rsp=0x80f008;end=0x600f00;u.mem_write(end,b'\x90');u.mem_write(rsp,struct.pack('<Q',end));u.reg_write(UC_X86_REG_RSP,rsp)
 if kind=='view':u.reg_write(UC_X86_REG_RCX,bar);u.reg_write(UC_X86_REG_RDX,label)
 else:u.reg_write(UC_X86_REG_RCX,main);u.reg_write(UC_X86_REG_RDX,1);u.reg_write(UC_X86_REG_R8,0 if failure=='no_dock' else dock)
 calls=[]
 def string(addr,wide=False):
  data=bytearray();step=2 if wide else 1
  while True:
   b=bytes(u.mem_read(addr+len(data),step))
   if b==b'\0'*step:return data.decode('utf-16le' if wide else 'ascii')
   data+=b
 def hook(uc,address,size,unused):
  if address==end:uc.emu_stop();return
  if address not in stubs.values():return
  name=next(n for n,a in stubs.items() if a==address);calls.append(name)
  sp=uc.reg_read(UC_X86_REG_RSP);assert sp%16==8
  rcx=uc.reg_read(UC_X86_REG_RCX);rdx=uc.reg_read(UC_X86_REG_RDX);r8=uc.reg_read(UC_X86_REG_R8);result=0
  if name==names[0]:assert (rcx,rdx)==(bar,label);result=0 if failure=='no_menu' else menu
  elif name=='GetModuleHandleW':assert string(rcx,True)=='Qt6Widgets.dll';result=0 if failure=='no_module' else 1
  elif name=='GetProcAddress':assert rcx==1 and string(rdx)=='?toggleViewAction@QDockWidget@@QEBAPEAVQAction@@XZ';result=0 if failure=='no_export' else stubs['toggle']
  elif name=='toggle':assert rcx==dock;result=0 if failure=='no_action' else action
  elif name==names[4]:assert (rcx,rdx)==(menu,action)
  elif name==names[5]:assert (rcx,rdx,r8)==(main,1,0 if failure=='no_dock' else dock);result=0xabc123
  elif name in names[6:]:assert rcx==dock
  for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11]:uc.reg_write(r,0xdeadbeef)
  uc.mem_write(sp+8,b'\xcc'*32);uc.reg_write(UC_X86_REG_RAX,result)
 u.hook_add(UC_HOOK_CODE,hook)
 entry=int(meta['viewport_menu_helper_va' if kind=='view' else 'viewport_reset_helper_va'],16)-original_base+base
 u.emu_start(entry,end+1,count=1000)
 assert u.reg_read(UC_X86_REG_RSP)==rsp+8 and u.reg_read(UC_X86_REG_RIP)==end
 for i,r in enumerate(regs):assert u.reg_read(r)==(main if r==UC_X86_REG_RDI else 0x123000+i)
 if kind=='view':
  assert u.reg_read(UC_X86_REG_RAX)==(0 if failure=='no_menu' else menu)
  assert (names[4] in calls)==(failure is None)
 else:
  assert u.reg_read(UC_X86_REG_RAX)==0xabc123
  assert (names[6] in calls)==(failure is None)
  assert (names[7] in calls)==(failure is None)
  if failure is None:assert calls[-3:]==names[5:]
count=0
for base in [0x140000000,0x180000000]:
 for failure in [None,'no_menu','no_dock','no_module','no_export','no_action']:test(base,'view',failure);count+=1
 for failure in [None,'no_dock']:test(base,'reset',failure);count+=1
print('PASS:',count,'dock helper cases: View attaches the real Viewport toggle; Default Layout re-docks/shows/raises that dock; missing-object/lookups return safely; ASLR, stack, registers and return values preserved.')
