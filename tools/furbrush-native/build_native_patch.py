"""Version-specific FurBrush title / hidden Help-menu patch.
Original executable must match the uploaded version; no original is overwritten.
Requires lief, pefile, capstone, keystone-engine (see pinned validation environment).
"""
from pathlib import Path
import argparse,hashlib,json,struct,io
from PIL import Image
from theme_helper import emit_theme_helper
import lief,pefile,capstone
from keystone import Ks,KS_ARCH_X86,KS_MODE_64
parser=argparse.ArgumentParser()
parser.add_argument('--repo',type=Path,default=Path('/workspace/Xgenprogram1'))
parser.add_argument('--package',type=Path,default=Path('/workspace/FurBrush-package'))
parser.add_argument('--analysis',type=Path,default=Path('/workspace/furbrush-analysis'))
parser.add_argument('--retro-ui',action='store_true',help='Enable external main-window stylesheet')
args=parser.parse_args()
root=args.package.resolve();source=args.repo.resolve()/'Sisir.exe'
artifacts=args.analysis.resolve();artifacts.mkdir(parents=True,exist_ok=True)
assert hashlib.sha256(source.read_bytes()).hexdigest()=='7d5c695776a42a43ca652ba502aea36926db31c1a5ebe95c31899d05ae7d4b1b', 'Unsupported Sisir version'
# First reproduce the verified icon-only build, before applying this patch.
original=pefile.PE(str(source)); base=original.OPTIONAL_HEADER.ImageBase
input_file=root/'FurBrush-icon-only.exe'
p=pefile.PE(str(input_file));binary=lief.PE.parse(str(input_file))
assert source.read_bytes()[original.get_offset_from_rva(0x251e20):][:7] == bytes.fromhex('488d15c9660c00')
assert source.read_bytes()[original.get_offset_from_rva(0x21bad4):][:6] == bytes.fromhex('ff15b6560e00')
assert p.get_data(0x251e20,7)==original.get_data(0x251e20,7)
assert p.get_data(0x21bad4,6)==original.get_data(0x21bad4,6)
# Resolve imports and verify every dynamic export against uploaded runtime DLLs.
imports={e.name.decode():e.address for d in p.DIRECTORY_ENTRY_IMPORT for e in d.imports if e.name}
addmenu=imports['?addMenu@QMenuBar@@QEAAPEAVQMenu@@AEBVQString@@@Z']
getmodule=imports['GetModuleHandleW'];getproc=imports['GetProcAddress']
menu_name=b'?menuAction@QMenu@@QEBAPEAVQAction@@XZ'
visible_name=b'?setVisible@QAction@@QEAAX_N@Z'
for dll,symbol in [('Qt6Widgets.dll',menu_name),('Qt6Gui.dll',visible_name)]:
 dll_pe=pefile.PE(str(args.repo/dll),max_symbol_exports=30000)
 assert symbol in {e.name for e in dll_pe.DIRECTORY_ENTRY_EXPORT.symbols},symbol
# Reserve a section for the helper, immutable strings and augmented unwind table.
old_exception=p.OPTIONAL_HEADER.DATA_DIRECTORY[3]
old_table=p.get_data(old_exception.VirtualAddress,old_exception.Size)
sec=lief.PE.Section('.fbpatch');sec.content=[0]*((len(old_table)+0x2000+0xfff)&~0xfff)
sec.characteristics=0x60000020 # initialized code, readable/executable, not writable
sec=binary.add_section(sec);rva=sec.virtual_address;va=base+rva
content=bytearray(sec.content)
patches=[]
def patch_va(address,data):
 binary.patch_address(address,list(data));patches.append((address,bytes(data)))
def put(off,data):content[off:off+len(data)]=data;return va+off
prefix=put(0x400,b'FurBrush v\0')
style_comment=put(0x580,b'/* External FurBrush theme; original accent %1 */\0')
widgets=put(0x440,'Qt6Widgets.dll\0'.encode('utf-16le'))
gui=put(0x480,'Qt6Gui.dll\0'.encode('utf-16le'))
menusym=put(0x4c0,menu_name+b'\0');visiblesym=put(0x540,visible_name+b'\0')
# Only volatile registers are used. Stack has Win64 shadow space and two locals.
# Failures of optional lookups return the real menu unchanged rather than crash.
asm=[]
ks=Ks(KS_ARCH_X86,KS_MODE_64)
fixups=[];labels={};code=bytearray()
def ins(text):
 b,_=ks.asm(text,va+len(code));code.extend(b)
def rip(prefix,target):
 addr=va+len(code);disp=target-(addr+len(prefix)+4)
 code.extend(prefix+struct.pack('<i',disp))
def branch(label):
 code.extend(b'\x0f\x84\0\0\0\0');fixups.append((len(code)-4,label))
ins('sub rsp, 0x38')
rip(b'\xff\x15',addmenu)
ins('mov qword ptr [rsp+0x20], rax');ins('test rax, rax');branch('done')
rip(b'\x48\x8d\x0d',widgets);rip(b'\xff\x15',getmodule)
ins('test rax, rax');branch('done');ins('mov rcx, rax')
rip(b'\x48\x8d\x15',menusym);rip(b'\xff\x15',getproc)
ins('test rax, rax');branch('done');ins('mov rcx, qword ptr [rsp+0x20]');ins('call rax')
ins('test rax, rax');branch('done');ins('mov qword ptr [rsp+0x28], rax')
rip(b'\x48\x8d\x0d',gui);rip(b'\xff\x15',getmodule)
ins('test rax, rax');branch('done');ins('mov rcx, rax')
rip(b'\x48\x8d\x15',visiblesym);rip(b'\xff\x15',getproc)
ins('test rax, rax');branch('done');ins('mov rcx, qword ptr [rsp+0x28]');ins('xor edx, edx');ins('call rax')
labels['done']=len(code)
ins('mov rax, qword ptr [rsp+0x20]');ins('add rsp, 0x38');ins('ret')
for off,label in fixups:struct.pack_into('<i',code,off,labels[label]-(off+4))
assert len(code)<0x400
put(0,code)
theme_code=b''
if args.retro_ui:
 tail=put(0xb00,'themes\\Windows7-Retro.qss\0'.encode('utf-16le'))
 mode=put(0xb60,'rb\0'.encode('utf-16le'))
 theme_code=emit_theme_helper(va+0x800,imports,tail,mode)
 assert len(theme_code)<0x300
 put(0x800,theme_code)
 # UWOP_ALLOC_LARGE for 0x518-byte stack frame, 7-byte prologue.
 put(0x680,bytes([1,7,2,0,7,1,0xa3,0]))
# UWOP_ALLOC_SMALL for sub rsp,0x38: permit Windows x64 stack unwinding.
put(0x600,bytes([1,4,1,0,4,0x62,0,0]))
new_table=old_table+struct.pack('<III',rva,rva+len(code),rva+0x600)
if theme_code:new_table+=struct.pack('<III',rva+0x800,rva+0x800+len(theme_code),rva+0x680)
put(0x1000,new_table)
entries=[struct.unpack_from('<III',content,0x1000+i) for i in range(0,len(new_table),12)]
assert entries==sorted(entries,key=lambda e:e[0])
sec.content=list(content)
binary.data_directories[3].rva=rva+0x1000
binary.data_directories[3].size=len(new_table)
# Redirect exactly one C-string constructor to the longer title prefix.
new_lea=b'\x48\x8d\x15'+struct.pack('<i',prefix-(base+0x251e20+7))
patch_va(base+0x251e20,new_lea)
# Keep Help menu creation/initialization; hide its menuAction in the helper.
new_call=b'\xe8'+struct.pack('<i',va-(base+0x21bad4+5))+b'\x90'
patch_va(base+0x21bad4,new_call)
# Replace both application-embedded QResource images, preserving static offsets.
# These are distinct from the executable's Windows icon resource.
art=Image.open(args.repo/'FurBrush.png').convert('RGBA')
side=max(art.size);square=Image.new('RGBA',(side,side),(0,0,0,0))
square.paste(art,((side-art.width)//2,(side-art.height)//2))
def png_that_fits(limit):
 for size in [256,192,128,96,64]:
  image=square.resize((size,size),Image.Resampling.LANCZOS)
  for colors in [256,128,64]:
   buf=io.BytesIO()
   image.quantize(colors=colors,method=Image.Quantize.FASTOCTREE).save(buf,format='PNG',optimize=True)
   if len(buf.getvalue())<=limit:return size,buf.getvalue()
 raise ValueError('Cannot fit application icon in reserved resource')
icon_details=[]
for offset,old_size,is_ico in [(0x362164,17025,True),(0x3663e9,34691,False)]:
 # QResource stores a big-endian size immediately before the resource data.
 assert struct.unpack('>I',source.read_bytes()[offset-4:offset])[0]==old_size
 dim,png=png_that_fits(old_size-(22 if is_ico else 0))
 if is_ico:
  data=struct.pack('<HHHBBBBHHII',0,1,1,dim%256,dim%256,0,0,1,32,len(png),22)+png
 else:data=png
 resource_rva=original.get_rva_from_offset(offset)
 patch_va(base+resource_rva-4,struct.pack('>I',len(data)))
 patch_va(base+resource_rva,data+b'\0'*(old_size-len(data)))
 icon_details.append({'resource_offset':hex(offset),'dimension':dim,'bytes':len(data),'ico':is_ico})
# A comment-only local stylesheet allows application-level external QSS to cascade.
# Retain %1 so the app's accent substitution continues without missing-arg warnings.
style_sites=[]
if args.retro_ui:
 # Apply file content at the original local stylesheet setter, independently
 # of command-line parsing or application/global-vs-local QSS precedence.
 assert p.get_data(0x2518d9,6)==bytes.fromhex('ff1599050b00')
 patch_va(base+0x2518d9,b'\xe8'+struct.pack('<i',(va+0x800)-(base+0x2518d9+5))+b'\x90')
 style_sites.append(hex(base+0x2518d9))
 # A local UTF-16 input-field style would otherwise outrank the external theme.
 local_style='QLineEdit { background: #101214; color: #C9D1D9; border: 1px solid #2B3138; border-radius: 4px; padding: 2px 6px; selection-background-color: #3A7BFF; }'
 local_offset=source.read_bytes().find(local_style.encode('utf-16le'))
 assert local_offset>=0
 restyled='/* External FurBrush theme */'.ljust(len(local_style))
 assert len(restyled)==len(local_style)
 patch_va(base+original.get_rva_from_offset(local_offset),restyled.encode('utf-16le'))
config=lief.PE.Builder.config_t();config.resources=False
output=root/'FurBrush.exe';binary.write(str(output),config)
check=pefile.PE(str(output));assert check.OPTIONAL_HEADER.AddressOfEntryPoint==p.OPTIONAL_HEADER.AddressOfEntryPoint
assert check.get_data(rva,len(code))==code
assert check.get_data(0x251e20,7)==new_lea
assert check.get_data(0x21bad4,6)==new_call
assert check.get_data(rva+0x400,11)==b'FurBrush v\0'
# Every original section must equal the input plus exactly the declared patches.
assert len(check.DIRECTORY_ENTRY_EXCEPTION)==len(p.DIRECTORY_ENTRY_EXCEPTION)+1+(1 if theme_code else 0)
for before,after in zip(p.sections,check.sections):
 assert before.Name==after.Name and before.VirtualAddress==after.VirtualAddress
 expected=bytearray(before.get_data());start=base+before.VirtualAddress
 for address,data in patches:
  if start<=address<start+len(expected):
   assert address+len(data)<=start+len(expected)
   expected[address-start:address-start+len(data)]=data
 assert bytes(expected)==after.get_data(),before.Name
assert [e.dll for e in p.DIRECTORY_ENTRY_IMPORT]==[e.dll for e in check.DIRECTORY_ENTRY_IMPORT]
check.OPTIONAL_HEADER.CheckSum=check.generate_checksum();check.write(str(output))
manifest={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'helper_va':hex(va),'helper_size':len(code),'title_instruction':hex(base+0x251e20),'help_instruction':hex(base+0x21bad4),'unwind_table_rva':hex(rva+0x1000),'theme_helper_va':hex(va+0x800) if theme_code else None,'theme_helper_size':len(theme_code),'embedded_icons':icon_details,'external_stylesheet_sites':style_sites,'note':'Static and emulator verification only; not tested on Windows.'}
(artifacts/'native-patch.json').write_text(json.dumps(manifest,indent=2))
(artifacts/'helper.bin').write_bytes(code)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
(artifacts/'helper.asm').write_text('\n'.join(f'{i.address:x}: {i.mnemonic} {i.op_str}' for i in md.disasm(code,va)))
if theme_code:(artifacts/'theme-helper.bin').write_bytes(theme_code)
print(json.dumps(manifest,indent=2))
