import argparse
import json
import logging as log
from pathlib import Path
import sys

import ninja
#import jinja2
#from tqdm import tqdm

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true')
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
    config_file = Path('config.json').absolute()

    if args.init:
        if not config_file.exists():
            default_config = {}
            default_config['input_directory'] = '~/Pictures'
            default_config['output_directory'] = '_site'
            default_config['ressources_directory'] = 'ressources'
            default_config['log_level'] = 'INFO'
            default_config['icc_profile_path'] = '/usr/share/color/icc/colord/sRGB.icc'
            json.dump(default_config, config_file.open('w'), indent=True)
            log.warn("Config file has been written to {}".format(config_file))
        else:
            log.warn("Config file already exists, it will not be modified.")
        sys.exit()

    if not config_file.exists():
        log.warn("Config file doesn't exist yet, aborting.")
        log.warn("If you would like to write the default config and templates, use --init.")
        raise FileNotFoundError("config.json")

    user_config = json.loads(config_file.read_text())

    log.basicConfig(level=getattr(log, user_config['log_level']))
    log.info("Reading config from {}".format(config_file))

    config = {}
    config['indir'] = Path(user_config["input_directory"]).expanduser().absolute()
    config['outdir'] = Path(user_config["output_directory"]).expanduser().absolute()
    config['ressources'] = Path(user_config["ressources_directory"]).expanduser().absolute()
    log.info('Using input directory: {}'.format(config['indir']))
    if not config['indir'].exists():
        raise Exception("Directory {} doesn't exist".format(config['indir']))
    config['ressources'].mkdir(exist_ok=True)

    log.info('Using output directory: {}'.format(config['outdir']))
    log.info('Using ressources from: {}'.format(config['ressources']))
    
    config['ninjafile'] = Path('build.ninja').absolute()
    config['assets'] = config['outdir'] / Path('assets')
    config['icc_profile'] = Path(user_config['icc_profile_path']).absolute()

    config['photo_exts'] = set(['.jpg', '.jpeg', '.png'])
    config['sizes'] = ['1920', '1280', '1024', '640', '320']
    config['video_exts'] = set(['.mov', '.avi', '.mts'])
    config['codecs'] = ['webm', 'mp4']
    #mp4: h264, aac
    #webm: vp8, vorbis
    config['vips_options'] = []
    if config['icc_profile'] is not None and config['icc_profile'].exists():
        config['vips_options'].append('--eprofile {}'.format(config['icc_profile']))
        config['vips_options'].append('--delete')
    #config['vips_options'].append('--linear')

    n = ninja.Writer(config['ninjafile'].open('w', encoding='utf-8'))
    #n.variable('builddir', str(config['outdir']))
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
           command='ffmpeg -i $in \
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
    
    if config['assets'].is_dir():
        n.build(str(config['assets']), 'rsync', inputs=str(config['ressources'] / Path('assets')))
    for collection in (d.absolute() for d in config['indir'].iterdir() if d.is_dir()):
        for f in (p.absolute() for p in collection.iterdir() if p.is_file()):
            relative = f.relative_to(config['indir'])
            original = config['outdir'] / relative / Path('original')
            n.build(str(original), 'copy', inputs=str(f))

            if f.suffix.lower() in config['photo_exts']:
                for size in config['sizes']:
                    out = config['outdir'] / relative / Path("{}px.jpg".format(size))
                    n.build(str(out), 'make_thumbnails',
                            inputs=str(f), variables={'size':size})

            elif f.suffix.lower() in config['video_exts']:
                for codec in config['codecs']:
                    out = config['outdir'] / relative / Path('video.{}'.format(codec))
                    n.build(str(out), 'ffmpeg-{}'.format(codec), inputs=str(f))

    ninja.ninja()



if __name__ == '__main__':
    main()
