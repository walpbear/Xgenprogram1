"""Version-specific Viewport recovery helpers; Win64 ABI, no global UI reset."""
import struct
from keystone import Ks,KS_ARCH_X86,KS_MODE_64

def emit_dock_helpers(view_va,reset_va,imports,widgets_name,toggle_name):
 ks=Ks(KS_ARCH_X86,KS_MODE_64)
 def assemble(start,kind):
  code=bytearray();labels={};fixups=[]
  def ins(s):b,_=ks.asm(s,start+len(code));code.extend(b)
  def rip(op,target):code.extend(op+struct.pack('<i',target-(start+len(code)+len(op)+4)))
  def call(n):rip(b'\xff\x15',imports[n])
  def jz(n):code.extend(b'\x0f\x84'+b'\0'*4);fixups.append((len(code)-4,n))
  ins('sub rsp,0x38')
  if kind=='view':
   # RDI is the MainWindow receiver in the original menu builder, preserved.
   call('?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z')
   ins('mov qword ptr[rsp+0x20],rax');ins('test rax,rax');jz('done')
   ins('cmp qword ptr[rdi+0x1e0],0');jz('done')
   rip(b'\x48\x8d\x0d',widgets_name);call('GetModuleHandleW');ins('test rax,rax');jz('done')
   ins('mov rcx,rax');rip(b'\x48\x8d\x15',toggle_name);call('GetProcAddress');ins('test rax,rax');jz('done')
   ins('mov rcx,qword ptr[rdi+0x1e0]');ins('call rax');ins('test rax,rax');jz('done')
   ins('mov rdx,rax');ins('mov rcx,qword ptr[rsp+0x20]');call('?addAction@QWidget@@QEAAXPEAVQAction@@@Z')
   labels['done']=len(code);ins('mov rax,qword ptr[rsp+0x20]')
  else:
   ins('mov qword ptr[rsp+0x20],r8')
   call('?addDockWidget@QMainWindow@@QEAAXW4DockWidgetArea@Qt@@PEAVQDockWidget@@@Z')
   ins('mov qword ptr[rsp+0x28],rax')
   ins('mov rcx,qword ptr[rsp+0x20]');ins('test rcx,rcx');jz('done')
   call('?show@QWidget@@QEAAXXZ');ins('mov rcx,qword ptr[rsp+0x20]');call('?raise@QWidget@@QEAAXXZ')
   labels['done']=len(code);ins('mov rax,qword ptr[rsp+0x28]')
  ins('add rsp,0x38');ins('ret')
  for off,label in fixups:struct.pack_into('<i',code,off,labels[label]-off-4)
  return bytes(code)
 return assemble(view_va,'view'),assemble(reset_va,'reset')
