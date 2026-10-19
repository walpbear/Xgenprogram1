from pathlib import Path
import argparse,json,struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,default=Path('/workspace/FurBrush-package'));parser.add_argument('--analysis',type=Path,default=Path('/workspace/furbrush-analysis'));args=parser.parse_args()
p=pefile.PE(str(args.package/'FurBrush.exe'));m=json.loads((args.analysis/'native-patch.json').read_text());helper=int(m['theme_helper_va'],16)-p.OPTIONAL_HEADER.ImageBase
imports={e.name.decode():e.address-p.OPTIONAL_HEADER.ImageBase for d in p.DIRECTORY_ENTRY_IMPORT for e in d.imports if e.name}
names=['GetModuleFileNameW','_wfopen_s','malloc','fread','fclose','free','??0QString@@QEAA@PEBD@Z','?setStyleSheet@QWidget@@QEAAXAEBVQString@@@Z','??1QString@@QEAA@XZ']
stubs={n:0x600000+i*0x100 for i,n in enumerate(names)}
nonvolatile=[UC_X86_REG_RBX,UC_X86_REG_RBP,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
def test(base,failure,content):
 u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x500000);u.mem_write(base,p.get_memory_mapped_image());u.mem_map(0x600000,0x1000);u.mem_map(0x700000,0x20000);u.mem_map(0x800000,0x20000)
 for name,stub in stubs.items():u.mem_write(stub,b'\xc3');u.mem_write(base+imports[name],struct.pack('<Q',stub))
 rsp=0x81f008;end=0x600f00;u.mem_write(end,b'\x90');u.mem_write(rsp,struct.pack('<Q',end));u.reg_write(UC_X86_REG_RSP,rsp)
 u.reg_write(UC_X86_REG_RCX,0x701000);u.reg_write(UC_X86_REG_RDX,0x702000)
 for i,r in enumerate(nonvolatile):u.reg_write(r,0x123000+i)
 filename='E:\\Fur Brush\\Furbr\u00fcsh0.1\\FurBrush.exe';expectedpath=filename.rsplit('\\',1)[0]+'\\themes\\Windows7-Retro.qss'
 strings={0x702000:b'original-dark-theme'};applied=[];opened=[];freed=[];closed=[];allocated=[]
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
  rcx=uc.reg_read(UC_X86_REG_RCX);rdx=uc.reg_read(UC_X86_REG_RDX);r8=uc.reg_read(UC_X86_REG_R8);r9=uc.reg_read(UC_X86_REG_R9);result=0
  if name=='GetModuleFileNameW':
   assert rcx==0 and r8==512
   if failure=='path_error':result=0
   elif failure=='long_path':result=512
   else:
    text='FurBrush.exe' if failure=='no_directory' else filename
    uc.mem_write(rdx,text.encode('utf-16le')+b'\0\0');result=len(text)
  elif name=='_wfopen_s':
   assert readstr(rdx,True)==expectedpath
   assert readstr(r8,True)=='rb'
   if failure=='open_error':uc.mem_write(rcx,b'\0'*8);result=2
   else:
    opened.append(True);uc.mem_write(rcx,struct.pack('<Q',0 if failure=='null_file' else 0x703000))
  elif name=='malloc':
   assert rcx==65537
   result=0 if failure=='allocation_failure' else 0x708000
   if result:allocated.append(result)
  elif name=='fread':
   assert (rcx,rdx,r8,r9)==(0x708000,1,65536,0x703000)
   if failure=='empty_file':result=0
   elif failure=='over_limit':result=65536
   else:uc.mem_write(rcx,content);result=len(content)
  elif name=='fclose':assert rcx==0x703000;closed.append(rcx)
  elif name=='free':assert rcx==0x708000;freed.append(rcx)
  elif name=='??0QString@@QEAA@PEBD@Z':strings[rcx]=readstr(rdx);result=rcx
  elif name=='??1QString@@QEAA@XZ':assert rcx in strings;strings.pop(rcx)
  else:assert rcx==0x701000;applied.append(strings[rdx])
  for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11]:uc.reg_write(r,0xdeadbeef)
  uc.mem_write(sp+8,b'\xcc'*32);uc.reg_write(UC_X86_REG_RAX,result)
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(base+helper,end+1,count=5000)
 assert u.reg_read(UC_X86_REG_RIP)==end and u.reg_read(UC_X86_REG_RSP)==rsp+8
 assert applied==([content] if failure is None else [b'original-dark-theme']),applied
 assert freed==allocated,'Allocation leak'
 assert len(closed)==(1 if failure in [None,'allocation_failure','empty_file','over_limit'] else 0),'File handle leak'
 for i,r in enumerate(nonvolatile):assert u.reg_read(r)==0x123000+i
count=0
for base in [0x140000000,0x180000000]:
 for failure in [None,'path_error','long_path','no_directory','open_error','null_file','allocation_failure','empty_file','over_limit']:
  test(base,failure,b'QWidget {background: #e6f4ee; color: #173e34;}');count+=1
 test(base,None,b'QWidget {background: #202834; color: #edf4fc;}');count+=1
print('PASS:',count,'native theme-loader cases: actual QSS bytes reach the local widget setter; executable-relative paths with spaces/Unicode; alternate palettes; ASLR; fallback; handle/allocation cleanup; stack/nonvolatile preservation.')
