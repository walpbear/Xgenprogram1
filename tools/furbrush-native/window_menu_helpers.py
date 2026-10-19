"""Create Window beside File and expose the existing About dialog under Info."""
import struct
from keystone import Ks,KS_ARCH_X86,KS_MODE_64

def emit_window_menus(window_va,info_va,imports,window_title,info_title,widgets_name,toggle_name):
 ks=Ks(KS_ARCH_X86,KS_MODE_64)
 def make(start,kind):
  code=bytearray();labels={};fixups=[]
  def ins(t):b,_=ks.asm(t,start+len(code));code.extend(b)
  def rip(op,target):code.extend(op+struct.pack('<i',target-(start+len(code)+len(op)+4)))
  def call(n):rip(b'\xff\x15',imports[n])
  def jz(n):code.extend(b'\x0f\x84'+b'\0'*4);fixups.append((len(code)-4,n))
  if kind=='window':
   ins('sub rsp,0x88');ins('mov qword ptr[rsp+0x20],rcx')
   call('?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z')
   ins('mov qword ptr[rsp+0x28],rax');ins('test rax,rax');jz('done')
   ins('lea rcx,[rsp+0x60]');rip(b'\x48\x8d\x15',window_title);call('??0QString@@QEAA@PEBD@Z')
   ins('mov rcx,qword ptr[rsp+0x20]');ins('lea rdx,[rsp+0x60]');call('?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z');ins('mov qword ptr[rsp+0x30],rax')
   ins('lea rcx,[rsp+0x60]');call('??1QString@@QEAA@XZ');ins('cmp qword ptr[rsp+0x30],0');jz('done')
   rip(b'\x48\x8d\x0d',widgets_name);call('GetModuleHandleW');ins('test rax,rax');jz('done')
   ins('mov rcx,rax');rip(b'\x48\x8d\x15',toggle_name);call('GetProcAddress');ins('test rax,rax');jz('done');ins('mov qword ptr[rsp+0x38],rax')
   for index,offset in enumerate([0x1c8,0x1d0,0x1d8,0x1e0]):
    ins(f'mov rcx,qword ptr[rdi+{offset}]');ins('test rcx,rcx');jz('next'+str(index))
    ins('call qword ptr[rsp+0x38]');ins('test rax,rax');jz('next'+str(index))
    ins('mov rdx,rax');ins('mov rcx,qword ptr[rsp+0x30]');call('?addAction@QWidget@@QEAAXPEAVQAction@@@Z')
    labels['next'+str(index)]=len(code)
   labels['done']=len(code);ins('mov rax,qword ptr[rsp+0x28]');ins('add rsp,0x88');ins('ret')
  else:
   ins('sub rsp,0x68');call('?addAction@QWidget@@QEAAPEAVQAction@@AEBVQString@@@Z');ins('mov qword ptr[rsp+0x20],rax');ins('test rax,rax');jz('done')
   ins('mov rcx,rdi');call('?menuBar@QMainWindow@@QEBAPEAVQMenuBar@@XZ');ins('mov qword ptr[rsp+0x28],rax');ins('test rax,rax');jz('done')
   ins('lea rcx,[rsp+0x40]');rip(b'\x48\x8d\x15',info_title);call('??0QString@@QEAA@PEBD@Z')
   ins('mov rcx,qword ptr[rsp+0x28]');ins('lea rdx,[rsp+0x40]');call('?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z');ins('mov qword ptr[rsp+0x30],rax')
   ins('lea rcx,[rsp+0x40]');call('??1QString@@QEAA@XZ');ins('cmp qword ptr[rsp+0x30],0');jz('done')
   ins('mov rcx,qword ptr[rsp+0x30]');ins('mov rdx,qword ptr[rsp+0x20]');call('?addAction@QWidget@@QEAAXPEAVQAction@@@Z')
   labels['done']=len(code);ins('mov rax,qword ptr[rsp+0x20]');ins('add rsp,0x68');ins('ret')
  for off,name in fixups:struct.pack_into('<i',code,off,labels[name]-off-4)
  return bytes(code)
 return make(window_va,'window'),make(info_va,'info')
