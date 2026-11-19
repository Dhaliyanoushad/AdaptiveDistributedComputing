"""Deterministic synthetic image preparation and immutable content manifests."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from PIL import Image, ImageDraw

PROFILES = {'small':(6,320,240), 'medium':(24,1280,720), 'large':(60,2560,1440)}


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def inspect_workload(directory: Path) -> dict:
    items = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in {'.jpg','.jpeg','.png'} or not path.is_file():
            continue
        data = path.read_bytes()
        if not 0 < len(data) <= 10*1024*1024:
            raise ValueError(f'Invalid encoded image size: {path.name}')
        with Image.open(path) as image:
            width,height = image.size
            if image.format not in {'PNG','JPEG'} or max(width,height)>4096 or width*height>16_000_000 or getattr(image,'n_frames',1)!=1:
                raise ValueError(f'Unsupported image: {path.name}')
            image.verify()
        items.append({'filename':path.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'width':width,'height':height})
    if not items:
        raise ValueError('No JPG/PNG images found')
    return {'workload_id':fingerprint(items),'images':items}


def generate(directory: Path, profile='small', *, seed=42, count=None, width=None, height=None, image_format='png') -> dict:
    if directory.exists():
        raise ValueError('Choose a new workload directory; existing data is never replaced')
    defaults = PROFILES[profile]
    count,width,height = (defaults[0] if count is None else count, defaults[1] if width is None else width, defaults[2] if height is None else height)
    if not 1<=count<=1000 or not (1<=width<=4096 and 1<=height<=4096) or width*height>16_000_000 or image_format not in {'png','jpg'}:
        raise ValueError('Invalid workload count, dimensions or format')
    rng = random.Random(seed)
    directory.mkdir(parents=True)
    for index in range(count):
        image = Image.new('RGB',(width,height),tuple(rng.randrange(256) for _ in range(3)))
        draw = ImageDraw.Draw(image)
        for _ in range(100):
            x1,x2 = sorted([rng.randrange(width),rng.randrange(width)])
            y1,y2 = sorted([rng.randrange(height),rng.randrange(height)])
            draw.rectangle((x1,y1,x2,y2),fill=tuple(rng.randrange(256) for _ in range(3)))
        image.save(directory/f'image-{index:04d}.{image_format}',format='PNG' if image_format=='png' else 'JPEG')
    manifest = inspect_workload(directory)
    manifest.update(provenance='Synthetic seeded RGB rectangles, generated locally with Pillow; not external photographs',seed=seed,profile=profile)
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--profile',choices=PROFILES,default='small')
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--count',type=int);parser.add_argument('--width',type=int);parser.add_argument('--height',type=int)
    parser.add_argument('--format',choices=['png','jpg'],default='png')
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args.directory,args.profile,seed=args.seed,count=args.count,width=args.width,height=args.height,image_format=args.format),indent=2))
    except (ValueError,OSError) as exc:
        parser.exit(1,f'{exc}\n')


if __name__=='__main__':
    main()
