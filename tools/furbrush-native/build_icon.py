"""Reproduce the icon-only executable change; requires Pillow, lief, pefile."""
from pathlib import Path
import io, struct, sys, hashlib
from PIL import Image
import lief, pefile

repo = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
original = repo / 'Sisir.exe'
original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
image = Image.open(repo / 'FurBrush.png').convert('RGBA')
side = max(image.size)
canvas = Image.new('RGBA', (side, side), (0,0,0,0))
canvas.paste(image, ((side-image.width)//2,(side-image.height)//2))
image = canvas
image.save(out / 'FurBrush.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
buffer = io.BytesIO()
image.resize((256,256), Image.Resampling.LANCZOS).save(buffer, format='PNG')
png = buffer.getvalue()
pe = lief.PE.parse(str(original))
assert not pe.has_signatures, 'Refusing to alter a signed executable.'
icon_type = next(c for c in pe.resources.childs if c.id == 3)
group_type = next(c for c in pe.resources.childs if c.id == 14)
assert len(list(icon_type.childs)) == 1
icon_node = list(icon_type.childs)[0]
for language in icon_node.childs:
    language.content = png
for group in group_type.childs:
    for language in group.childs:
        data = bytes(language.content)
        assert struct.unpack_from('<HHH',data) == (0,1,1)
        assert struct.unpack_from('<H',data,18)[0] == icon_node.id
        language.content = struct.pack('<HHHBBBBHHIH',0,1,1,0,0,0,0,1,32,len(png),icon_node.id)
config = lief.PE.Builder.config_t()
config.resources = True
pe.write(str(out / 'FurBrush.exe'), config)
# Independent parser: verify embedded icon bytes and group reference.
check = pefile.PE(str(out / 'FurBrush.exe'))
for resource in check.DIRECTORY_ENTRY_RESOURCE.entries:
    if resource.id == 3:
        for entry in resource.directory.entries:
            for lang in entry.directory.entries:
                d=lang.data.struct
                assert check.get_data(d.OffsetToData,d.Size) == png
# Preserve program sections byte-for-byte, including embedded Qt resources.
a = pefile.PE(str(original))
for section in a.sections:
    if section.Name.rstrip(b'\0') != b'.rsrc':
        matches=[s for s in check.sections if s.Name == section.Name]
        assert len(matches)==1
        assert matches[0].VirtualAddress == section.VirtualAddress
        assert matches[0].get_data() == section.get_data(), section.Name
assert check.OPTIONAL_HEADER.AddressOfEntryPoint == a.OPTIONAL_HEADER.AddressOfEntryPoint
assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
with Image.open(out / 'FurBrush.ico') as icon:
    assert (256,256) in icon.ico.sizes()
print('Verified: embedded icon, ICO sizes, unchanged program sections and entry point; original preserved.')
