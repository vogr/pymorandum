import argparse
import hashlib
import configparser
import logging as log
from pathlib import Path
import subprocess
import sys

import pkg_resources
import ninja_syntax
import jinja2


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true')
    return parser.parse_args()

def render_template(collection, outfile, template_vars, template_dir):
    template_loader = jinja2.FileSystemLoader(str(template_dir))
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template('template.html')

    output_text = template.render(template_vars)
    outfile.write_text(output_text)

def main():
    args = parse_args()
    config_file = Path('config.ini').absolute()

    if args.init:
        if not config_file.exists():
            default_config = configparser.ConfigParser()
            default_config['general_config'] = {
                'input_directory': '~/Pictures/Photo Gallery',
                'output_directory': '_site',
                'resources_directory': 'resources',
                'log_level': 'INFO',
                'icc_profile_path': '/usr/share/color/icc/colord/sRGB.icc'
            }
            default_config['template_vars'] = {
                 'gallery_title': 'My Photo Library',
                 'gallery_description': 'Que le jour recommence et que le jour finisse',
                 'sidebar_content':'Sans que jamais Titus puisse voir Bérénice'
                }
            with config_file.open('w') as c:
                default_config.write(c)
            log.warn("Config file has been written to {}".format(config_file))
        else:
            log.warn("Config file already exists, it will not be modified.")
        sys.exit()

    if not config_file.exists():
        log.warn("Config file doesn't exist yet, aborting.")
        log.warn("If you would like to write the default config and templates, use --init.")
        raise FileNotFoundError("{}".format(config_file))


    user_config = configparser.ConfigParser()
    user_config.read(config_file)
    general_config = user_config['general_config']

    log.basicConfig(level=getattr(log, general_config['log_level']))
    log.info("Reading config from {}".format(config_file))

    config = {}
    config['indir'] = Path(general_config["input_directory"]).expanduser().absolute()
    config['outdir'] = Path(general_config["output_directory"]).expanduser().absolute()
    config['resources'] = Path(general_config["resources_directory"]).expanduser().absolute()
    config['package_resources'] = Path(pkg_resources.resource_filename(__name__, "resources")).absolute()

    log.info('Using input directory: {}'.format(config['indir']))
    if not config['indir'].exists():
        raise Exception("Directory {} doesn't exist".format(config['indir']))
    if not config['resources'].exists():
        subprocess.run(['rsync', '-aPzh',
                        "{}/".format(config['package_resources']),
                        config['resources']
                       ])

    log.info('Using output directory: {}'.format(config['outdir']))
    log.info('Using resources from: {}'.format(config['resources']))
    
    config['ninjafile'] = Path('build.ninja').absolute()
    config['icc_profile'] = Path(general_config['icc_profile_path']).absolute()

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


    # Save collections in a list of  holding all the informations that will
    # be used by the template.
    collections = []
    collection_slides = {}
    for collection_dir in (d.absolute() for d in config['indir'].iterdir() if d.is_dir()):
        collection = {
            'name': str(collection_dir.relative_to(config['indir'])),
            'path': str(Path('collections') / collection_dir.relative_to(config['indir'])),
        }
        collection_slides[collection['name']] = []
        for f in (p.absolute() for p in collection_dir.iterdir() if p.is_file()):
            relative = f.relative_to(config['indir'])
            is_image = f.suffix.lower() in config['photo_exts']
            is_video = f.suffix.lower() in config['video_exts']
            is_media = is_image or is_video
            if is_media:
                src = Path("collections") / relative
                original_dest = config['outdir'] / src / Path('original')
                n.build(str(original_dest), 'copy', inputs=str(f))
                if is_image:
                    photo_metadata = {'filename': str(src)}
                    slide = {'type': 'photo', 'data': photo_metadata}
                    collection_slides[collection['name']].append(slide)
                    for size in config['sizes']:
                        out = config['outdir'] / src / Path("{}px.jpg".format(size))
                        n.build(str(out), 'make_thumbnails',
                                inputs=str(f), variables={'size':size})
                elif is_video:
                    for codec in config['codecs']:
                        out = Path('collections') / relative / Path('video.{}'.format(codec))
                        n.build(str(config['outdir'] / out), 'ffmpeg-{}'.format(codec), inputs=str(f))
        collections.append(collection)

    n.close()

    subprocess.run(['ninja'])

    (config['resources'] / Path('assets')).mkdir(exist_ok=True)
    subprocess.run(['rsync', '-aPzu',
             '{}/'.format(config['resources'] / Path('assets')),
             format(config['outdir'] / Path('assets'))
             ])

    template_vars = dict(user_config['template_vars'])
    template_vars['collections'] = collections

    index = config['outdir'] / Path('index.html')
    template_vars['slides'] = collection_slides[collections[0]['name']]
    template_vars['current_collection'] = collections[0]['name']
    render_template(collections[0], index, template_vars, config['resources'])

    for collection in collections:
        index = config['outdir'] / collection['path'] / Path('index.html')
        template_vars['slides'] = collection_slides[collection['name']]
        template_vars['current_collection'] = collection['name']
        render_template(collections[0], index, template_vars, config['resources'])
        render_template(collection, index, template_vars, config['resources'])


if __name__ == '__main__':
    main()
