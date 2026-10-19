"""Emit a Win64 helper that reads the theme beside the executable, then applies it
at the application's existing QWidget::setStyleSheet call site."""
import struct
from keystone import Ks,KS_ARCH_X86,KS_MODE_64

def emit_theme_helper(va,imports,tail,mode):
 ks=Ks(KS_ARCH_X86,KS_MODE_64);code=bytearray();labels={};fixups=[]
 def ins(s):
  b,_=ks.asm(s,va+len(code));code.extend(b)
 def label(n):labels[n]=len(code)
 def branch(n,op='z'):
  prefix={'z':b'\x0f\x84','nz':b'\x0f\x85','ae':b'\x0f\x83','a':b'\x0f\x87','jmp':b'\xe9'}[op]
  code.extend(prefix+b'\0'*4);fixups.append((len(code)-4,n))
 def rip(op,target):
  disp=target-(va+len(code)+len(op)+4);code.extend(op+struct.pack('<i',disp))
 def call(n):rip(b'\xff\x15',imports[n])
 ins('sub rsp, 0x518')
 ins('mov qword ptr [rsp+0x40], rcx');ins('mov qword ptr [rsp+0x48], rdx')
 ins('xor eax,eax');ins('mov qword ptr [rsp+0x50],rax');ins('mov qword ptr [rsp+0x58],rax')
 ins('xor ecx,ecx');ins('lea rdx,[rsp+0x100]');ins('mov r8d,512');call('GetModuleFileNameW')
 ins('test eax,eax');branch('fallback');ins('cmp eax,480');branch('fallback','a')
 ins('lea r8,[rsp+0x100]')
 label('slash');ins('test eax,eax');branch('fallback');ins('dec eax');ins('cmp word ptr [r8+rax*2],0x5c');branch('slash','nz')
 ins('inc eax');ins('lea r8,[r8+rax*2]');rip(b'\x4c\x8d\x0d',tail)
 label('append');ins('movzx edx,word ptr[r9]');ins('mov word ptr[r8],dx');ins('add r9,2');ins('add r8,2');ins('test dx,dx');branch('append','nz')
 ins('lea rcx,[rsp+0x50]');ins('lea rdx,[rsp+0x100]');rip(b'\x4c\x8d\x05',mode);call('_wfopen_s')
 ins('test eax,eax');branch('fallback','nz');ins('cmp qword ptr[rsp+0x50],0');branch('fallback')
 ins('mov ecx,65537');call('malloc');ins('mov qword ptr[rsp+0x58],rax');ins('test rax,rax');branch('close_fallback')
 ins('mov rcx,rax');ins('mov edx,1');ins('mov r8d,65536');ins('mov r9,qword ptr[rsp+0x50]');call('fread');ins('mov qword ptr[rsp+0x60],rax')
 ins('mov rcx,qword ptr[rsp+0x50]');call('fclose')
 ins('cmp qword ptr[rsp+0x60],0');branch('free_fallback')
 ins('cmp qword ptr[rsp+0x60],65536');branch('free_fallback','ae')
 ins('mov rax,qword ptr[rsp+0x60]');ins('mov rdx,qword ptr[rsp+0x58]');ins('mov byte ptr[rdx+rax],0')
 ins('lea rcx,[rsp+0x70]');call('??0QString@@QEAA@PEBD@Z')
 ins('mov rcx,qword ptr[rsp+0x40]');ins('lea rdx,[rsp+0x70]');call('?setStyleSheet@QWidget@@QEAAXAEBVQString@@@Z')
 ins('lea rcx,[rsp+0x70]');call('??1QString@@QEAA@XZ')
 ins('mov rcx,qword ptr[rsp+0x58]');call('free');branch('done','jmp')
 label('close_fallback');ins('mov rcx,qword ptr[rsp+0x50]');call('fclose');branch('fallback','jmp')
 label('free_fallback');ins('mov rcx,qword ptr[rsp+0x58]');call('free')
 label('fallback');ins('mov rcx,qword ptr[rsp+0x40]');ins('mov rdx,qword ptr[rsp+0x48]');call('?setStyleSheet@QWidget@@QEAAXAEBVQString@@@Z')
 label('done');ins('add rsp,0x518');ins('ret')
 for off,n in fixups:struct.pack_into('<i',code,off,labels[n]-off-4)
 return bytes(code)
