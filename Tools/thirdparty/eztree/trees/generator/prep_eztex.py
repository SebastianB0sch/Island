"""prep_eztex.py <ez-tree src/lib/assets dir> <out textures dir> : copies bark color/normal jpgs + leaf pngs,
builds glTF ORM (R=AO, G=roughness, B=0 metal) PNGs from the *_ao_1k / *_roughness_1k maps."""
import sys, os, shutil
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for bark in ('oak', 'pine', 'birch', 'willow'):
    for k in ('color', 'normal'):
        shutil.copy(os.path.join(src, 'bark', f'{bark}_{k}_1k.jpg'), out)
    ao = Image.open(os.path.join(src, 'bark', f'{bark}_ao_1k.jpg')).convert('L')
    ro = Image.open(os.path.join(src, 'bark', f'{bark}_roughness_1k.jpg')).convert('L').resize(ao.size)
    Image.merge('RGB', (ao, ro, Image.new('L', ao.size, 0))).save(os.path.join(out, f'{bark}_orm_1k.png'), optimize=True)
for leaf in ('ash', 'aspen', 'oak', 'pine'):
    im = Image.open(os.path.join(src, 'leaves', f'{leaf}_color.png')).convert('RGBA')
    im.save(os.path.join(out, f'{leaf}_color.png'), optimize=True)
print(sorted(os.listdir(out)))
