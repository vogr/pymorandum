import argparse
import logging as log
from pathlib import Path

import ninja
#import jinja2
#from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log", dest="logLevel",
                        choices=['DEBUG', 'INFO', 'WARNING',
                                 'ERROR', 'CRITICAL'],
                        default="INFO",
                        help="Set the logging level")
    parser.add_argument('-d', dest='outdir_path',
                        default='_site')
    parser.add_argument('indir_path')
    parser.add_argument('-i', dest='icc_profile_path',
                        default='/usr/share/color/icc/colord/sRGB.icc')
    parser.add_argument('-c', dest='config_dir_path',
                        default='pymorandum_config')
    return parser.parse_args()

def main():
    """
    Convert a directory of pictures organised in subdirectories
    into a photo gallery website.
    The directory structure is the following:

    input_directory
    ├── Holidays in Rome
    │   ├── IMG-3.jpg
    │   ├── IMG-4.jpg
    │   └── IMG-5.jpg
    │       ...
    └── Holidays in Tokyo
        ├── IMG-52.jpg
        ├── IMG-53.jpg
        └── IMG-54.jpg
            ...

    _site (output directory)
    ├── Holidays in Rome
    │   ├── IMG-3
    │   │   ├── 1024px.jpg
    │   │   ├── 1280px.jpg
    │   │   ├── 1920px.jpg
    │   │   ├── 320px.jpg
    │   │   ├── 640px.jpg
    │   │   └── original
    │   ├── IMG-4 
    │        ...
    └── Holidays in Tokyo
        ├── IMG-52
        │   ├── 1024px.jpg
        │   ├── 1280px.jpg
        │   ├── 1920px.jpg
        │   ├── 320px.jpg
        │   ├── 640px.jpg
        │   └── original
        ├── IMG-53
            ...
    """

    args = parse_args()
    log.basicConfig(level=getattr(log, args.logLevel))

    config = {}


    config['indir'] = Path(args.indir_path).absolute()
    config['outdir'] = Path(args.outdir_path).absolute()
    config['config_dir'] = Path(args.config_dir_path).absolute()
    log.info('Using input directory: {}'.format(config['indir']))
    if not config['indir'].exists():
        raise Exception("Directory {} doesn't exist".format(config['indir']))

    log.info('Using output directory: {}'.format(config['outdir']))
    log.info('Reading config from: {}'.format(config['config_dir']))
    
    config['ninjafile'] = (config['config_dir'] / Path('build.ninja')).absolute()
    config['assets'] = config['outdir'] / Path('assets')
    config['icc_profile'] = Path(args.icc_profile_path).absolute()

    config['photo_exts'] = set(['.jpg', '.jpeg', '.png'])
    config['sizes'] = ['1920', '1280', '1024', '640', '320']
    config['video_exts'] = set(['.mov', '.avi'])
    config['codecs'] = ['webm', 'mp4']
    #mp4: h264, aac
    #webm: vp8, vorbis
    config['vips_options'] = []
    if config['icc_profile'] is not None and config['icc_profile'].exists():
        config['vips_options'].append('--eprofile {}'.format(config['icc_profile']))
        config['vips_options'].append('--delete')
    #config['vips_options'].append('--linear')

    n = ninja.Writer(config['ninjafile'].open('w', encoding='utf-8'))
    n.variable('builddir', str(config['outdir']))
    n.variable('vips_options', ' '.join(config['vips_options']))
    n.variable('ffmpeg_options', '-threads 0')
    
    n.rule(name='clean', command='rm -rf {}'.format(config['outdir']))
    n.rule(name='copy', command='cp $in $out')
    n.rule(name='rsync', command='rsync -aPzhu $in/ $out')
    n.rule(name='make_thumbnails',
           command='vipsthumbnail \
                    --vips-progress \
                    --size x$size \
                    $vips_options \
                    -o $out[optimize_coding,strip] \
                    $in'
           )
    n.rule(name='ffmpeg-webm',
           command='ffmpeg i-i $in \
                    -c:v libvpx -b:v 1M -crf 30 \
                    -c:a libvorbis -q:a 4 \
                    $out'
           )
    n.rule(name='ffmpeg-mp4',
           command='ffmpeg -i $in \
                    -c:v libx264 -crf 20 -preset:v veryslow \
                    -c:a libfdk_aac -vbr 4 \
                    -movflags +faststart \
                    $ffmpeg_options \
                    $out'
          )
    
    n.build(str(config['assets']), 'rsync', inputs=str(config['config_dir'] / Path('assets')))
    for collection in (d.absolute() for d in config['indir'].iterdir() if d.is_dir()):
        for f in (p.absolute() for p in collection.iterdir() if
                        p.is_file() and p.suffix):
            relative = f.relative_to(config['indir'])
            original = config['outdir'] / relative / Path('original')
            n.build(str(original), 'copy', inputs=str(f))

            if f.suffix in config['photo_exts']:
                for size in config['sizes']:
                    out = config['outdir'] / relative / Path("{}px.jpg".format(size))
                    n.build(str(out), 'make_thumbnails',
                            inputs=str(f), variables={'size':size})

            elif f.suffix in config['video_exts']:
                for codec in config['codecs']:
                    out = config['outdir'] / relative / Path('video.{}'.format(codec))
                    n.build(str(out), 'ffmpeg-{}'.format(codec), inputs=str(f))
    ninja.ninja(config['ninjafile'])

if __name__ == '__main__':
    main()
