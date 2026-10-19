from pathlib import Path
import argparse,json,struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
parser=argparse.ArgumentParser()
parser.add_argument('--package',type=Path,default=Path('/workspace/FurBrush-package'))
parser.add_argument('--analysis',type=Path,default=Path('/workspace/furbrush-analysis'))
args=parser.parse_args()
p=pefile.PE(str(args.package/'FurBrush.exe'))
info=json.loads((args.analysis/'native-patch.json').read_text())
imports={e.name.decode():e.address-p.OPTIONAL_HEADER.ImageBase for d in p.DIRECTORY_ENTRY_IMPORT for e in d.imports if e.name}
helper_rva=int(info['helper_va'],16)-p.OPTIONAL_HEADER.ImageBase
stub_names=['addmenu','module','resolve','action','visible']
stubs={name:0x600000+i*0x100 for i,name in enumerate(stub_names)}
nonvolatile=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
def test(failure,base):
 u=Uc(UC_ARCH_X86,UC_MODE_64)
 u.mem_map(base,0x500000);u.mem_write(base,p.get_memory_mapped_image())
 u.mem_map(0x600000,0x1000);u.mem_map(0x700000,0x10000);u.mem_map(0x800000,0x10000)
 for addr in stubs.values():u.mem_write(addr,b'\xc3')
 for name,stub in [('?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z','addmenu'),('GetModuleHandleW','module'),('GetProcAddress','resolve')]:
  u.mem_write(base+imports[name],struct.pack('<Q',stubs[stub]))
 end=0x600f00;u.mem_write(end,b'\x90')
 rsp=0x80f008;u.mem_write(rsp,struct.pack('<Q',end))
 u.reg_write(UC_X86_REG_RSP,rsp)
 u.reg_write(UC_X86_REG_RCX,0x701000);u.reg_write(UC_X86_REG_RDX,0x702000)
 for i,r in enumerate(nonvolatile):u.reg_write(r,0x123000+i)
 calls=[];hidden=[]
 def cstr(addr,wide=False):
  buf=bytearray();step=2 if wide else 1
  while True:
   b=bytes(u.mem_read(addr+len(buf),step))
   if b==b'\0'*step:return buf.decode('utf-16le' if wide else 'ascii')
   buf+=b
 def hook(uc,address,size,data):
  if address==end:uc.emu_stop();return
  if address not in stubs.values():return
  name=next(k for k,v in stubs.items() if v==address)
  calls.append(name)
  sp=uc.reg_read(UC_X86_REG_RSP);assert sp%16==8,'Win64 stack alignment'
  rcx=uc.reg_read(UC_X86_REG_RCX);rdx=uc.reg_read(UC_X86_REG_RDX)
  if name=='addmenu':
   assert (rcx,rdx)==(0x701000,0x702000)
   result=0 if failure=='null_menu' else 0x703000
  elif name=='module':
   dll=cstr(rcx,True)
   assert dll in ['Qt6Widgets.dll','Qt6Gui.dll']
   result={'Qt6Widgets.dll':1,'Qt6Gui.dll':2}[dll]
   if failure==('missing_widgets' if result==1 else 'missing_gui'):result=0
  elif name=='resolve':
   sym=cstr(rdx)
   if 'menuAction' in sym:
    assert rcx==1;result=0 if failure=='missing_menu_action' else stubs['action']
   else:
    assert sym=='?setVisible@QAction@@QEAAX_N@Z' and rcx==2
    result=0 if failure=='missing_set_visible' else stubs['visible']
  elif name=='action':
   assert rcx==0x703000
   result=0 if failure=='null_action' else 0x704000
  else:
   assert rcx==0x704000 and rdx==0
   hidden.append(True);result=0
  # Windows/Qt callees can overwrite all volatile registers and shadow space.
  for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11]:uc.reg_write(r,0xdeadbeef)
  uc.mem_write(sp+8,b'\xcc'*32)
  uc.reg_write(UC_X86_REG_RAX,result)
 u.hook_add(UC_HOOK_CODE,hook)
 u.emu_start(base+helper_rva,end+1,count=1000)
 assert u.reg_read(UC_X86_REG_RIP)==end
 assert u.reg_read(UC_X86_REG_RSP)==rsp+8
 assert u.reg_read(UC_X86_REG_RAX)==(0 if failure=='null_menu' else 0x703000)
 assert bool(hidden)==(failure is None)
 for i,r in enumerate(nonvolatile):assert u.reg_read(r)==0x123000+i
 return len(calls)
count=0
for base in [0x140000000,0x180000000]:
 for failure in [None,'null_menu','missing_widgets','missing_menu_action','null_action','missing_gui','missing_set_visible']:
  test(failure,base);count+=1
print(f'PASS: {count} emulated cases across two image bases; hides only Help action; preserves menu result, stack, shadow space and nonvolatile registers. Lookup failures return safely.')
