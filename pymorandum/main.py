import argparse
import json
import logging as log
from pathlib import Path
import subprocess
import sys

import ninja_syntax
import jinja2

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
    │       ...
    └── Holidays in Tokyo
        ├── IMG-52.jpg
            ...

    _site (output directory)
    ├── Holidays in Rome
    │   ├── IMG-3
    │   │   ├── 1024px.jpg
    │   │   │     ...
    │   │   └── original
    │        ...
    └── Holidays in Tokyo
        ├── IMG-52
        │   ├── 1024px.jpg
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
            default_config['template_variables'] = {
                 'gallery_title': 'My Photo Library',
                 'gallery_description': 'Que le jour recommence et que le jour finisse',
                 'sidebar_content':'Sans que jamais Titus puisse voir Bérénice'
                }
            config_file.write_text(json.dumps(default_config, indent=True))
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

    n = ninja_syntax.Writer(config['ninjafile'].open('w', encoding='utf-8'))
    #n.variable('builddir', str(config['outdir']))
    n.variable('vips_options', ' '.join(config['vips_options']))
    n.variable('ffmpeg_options', '-threads 0')
    
    n.rule(name='copy', command='cp $in $out')
    n.rule(name='rsync', command='rsync -aPzhu $in/ $out')
    n.rule(name='make_thumbnails',
           command='vipsthumbnail \
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

    (config['ressources'] / Path('assets')).mkdir(exist_ok=True)
    n.build(str(config['outdir'] / Path('assets')), 'rsync', inputs=str(config['ressources'] / Path('assets')))

    slides = []
    for collection in (d.absolute() for d in config['indir'].iterdir() if d.is_dir()):
        for f in (p.absolute() for p in collection.iterdir() if p.is_file()):
            relative = f.relative_to(config['indir'])
            is_image = f.suffix.lower() in config['photo_exts']
            is_video = f.suffix.lower() in config['video_exts']
            is_media = is_image or is_video
            if is_media:
                src = Path("media") / relative
                original_dest = config['outdir'] / src / Path('original')
                n.build(str(original_dest), 'copy', inputs=str(f))
                if is_image:
                    photo_metadata = {'filename': str(src)}
                    slide = {'type': 'photo', 'data': photo_metadata}
                    slides.append(slide)
                    for size in config['sizes']:
                        out = config['outdir'] / src / Path("{}px.jpg".format(size))
                        n.build(str(out), 'make_thumbnails',
                                inputs=str(f), variables={'size':size})
                elif is_video:
                    for codec in config['codecs']:
                        out = Path('media') / relative / Path('video.{}'.format(codec))
                        n.build(str(config['outdir'] / out), 'ffmpeg-{}'.format(codec), inputs=str(f))

    print(slides)
    n.close()

    subprocess.run(['ninja'])

    print("Jinja2")

    template_loader = jinja2.FileSystemLoader(str(config['ressources']))
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template('template.html')

    template_vars = user_config['template_variables']
    template_vars['slides'] = slides
    output_text = template.render(template_vars)
    (config['outdir'] / Path('index.html')).write_text(output_text)
    print("Done")

if __name__ == '__main__':
    main()
