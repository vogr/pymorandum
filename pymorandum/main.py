import argparse
import configparser
import logging as log
from pathlib import Path
import subprocess
import sys

import pkg_resources
from natsort import natsorted
import ninja_syntax
import jinja2
import slugify


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--init', action='store_true')
    return parser.parse_args()


def render_template(outfile, template_vars, template_dir):
    template_loader = jinja2.FileSystemLoader(str(template_dir))
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template('template.html')

    output_text = template.render(template_vars)
    outfile.write_text(output_text)


def init(config_file):
    if not config_file.exists():
        default_config = configparser.ConfigParser()
        default_config['general_config'] = {
            'base_url': '',
            'input_directory': '~/Pictures/Photo Gallery',
            'output_directory': '_site',
            'resources_directory': 'resources',
            'log_level': 'INFO',
            'icc_profile_path': '/usr/share/color/icc/colord/sRGB.icc',
            'downloadable_zipfiles': 'true',
        }
        default_config['template_vars'] = {
                'gallery_title': 'A world of wonders',
                'gallery_description': 'We are such stuff as dreams are made on, and our little life is rounded with a sleep.'
            }
        with config_file.open('w') as c:
            default_config.write(c)
        log.warning("Config file has been written to %s", config_file)
    else:
        log.warning("Config file already exists, it will not be modified.")
    user_config = configparser.ConfigParser()
    user_config.read(config_file)
    package_resources = Path(pkg_resources.resource_filename(__name__, "resources")).absolute()
    user_resources = Path(user_config['general_config']['resources_directory']).absolute()
    if not user_resources.exists():
        log.warning("Copying resources to %s", user_resources)
        subprocess.run(['rsync', '-aPzh',
                        "{}/".format(package_resources),
                        user_resources
                    ])
        log.warning("Exiting.")
    else:
        log.warning("Resources directory already exists at %s, aborting.", user_resources)
    sys.exit()

def main():
    args = parse_args()
    config_file = Path('config.ini').absolute()

    if args.init:
        init(config_file)

    if not config_file.exists():
        log.warning("Config file doesn't exist yet, aborting.")
        log.warning("If you would like to write the default config and templates, use --init.")
        raise FileNotFoundError("{}".format(config_file))


    user_config = configparser.ConfigParser()
    user_config.read(config_file)
    general_config = user_config['general_config']

    log.basicConfig(level=getattr(log, general_config['log_level']))
    log.info("Reading config from %s", config_file)

    config = {}
    config['indir'] = Path(general_config["input_directory"]).expanduser().absolute()
    config['outdir'] = Path(general_config["output_directory"]).expanduser().absolute()
    # Careful! if defined, base_url begins with a leading slash
    config['base_url'] = Path('/') / general_config["base_url"]
    
    config['resources'] = Path(general_config["resources_directory"]).expanduser().absolute()
    log.info('Using input directory: %s', config['indir'])
    if not config['indir'].exists():
        raise Exception("Directory {} doesn't exist, use --init to create it with default values.".format(config['indir']))
    if not config['resources'].exists():
        raise Exception("Directory {} doesn't exist, use --init to use default resources.".format(config['resources']))

    log.info('Using output directory: %s', config['outdir'])
    log.info('Using resources from: %s', config['resources'])
    
    config['ninjafile'] = Path('build.ninja').absolute()
    config['icc_profile'] = Path(general_config['icc_profile_path']).expanduser().absolute()
    config['downloadable'] = general_config.getboolean('downloadable_zipfiles')
    config['to_exclude'] = ['metadata.ini']

    config['photo_exts'] = set(['.jpg', '.jpeg', '.png'])
    config['sizes'] = ['1920', '1280', '1024', '640', '320']
    config['video_exts'] = set(['.mov', '.avi', '.mts', '.vid', '.mp4'])
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
    n.variable('ffmpeg_options', '-y -threads 0')
    
    n.rule(name='make_thumbnails',
           command='vipsthumbnail \
                    --size x$size \
                    $vips_options \
                    -o $out[optimize_coding,strip] \
                    $in'
           )
    n.rule(name='ffmpeg-webm',
           command='ffmpeg -i $in \
                    -c:v libvpx -b:v 2M -crf 10 \
                    -qmin 0 -qmax 50 \
                    -c:a libvorbis -q:a 4 \
                    $ffmpeg_options \
                    $out'
           )
    n.rule(name='ffmpeg-mp4',
           command='ffmpeg -i $in \
                    -c:v libx264 -crf 18 -preset:v fast \
                    -c:a libfdk_aac -vbr 4 \
                    -movflags +faststart \
                    $ffmpeg_options \
                    $out'
          )
    n.rule(name='rsync',
           command='rsync -aPzh --delete $in/ $out')
    n.rule(name='zip', command='zip -j $out $in')


    # Save collections metadata in a list of dicts (collections_data)  holding all the informations that will
    # be used by the template. This list will be (naturally) sorted by names of collection (the name of the directory
    # containing the collection).
    collections_data = []
    for collection in natsorted((d.absolute() for d in config['indir'].iterdir() if d.is_dir()), key=str):
        name = str(collection.relative_to(config['indir']))
        metadata_file = collection / Path('metadata.ini')
        c = configparser.ConfigParser()
        c.read(metadata_file)
        data = {}
        data['name'] = name
        data['title'] = c.get('collection', 'title', fallback=name)
        data['uri_title'] = c.get('collection', 'uri_title',
                                  fallback=slugify.slugify(data['title']))
        data['path'] = Path('collections') / Path(data['uri_title'])
        data['src_uri'] = str(config['base_url'] / data['path'])
        if data['src_uri'][-1] != '/':
            data['src_uri'] += '/'

        collection_out = (config['outdir'] / Path("collections") / Path(data['uri_title'])).absolute()

        data['slides'] = []
        for f in natsorted((f.absolute() for f in collection.iterdir() if f.is_file()), key=str):
            is_image = f.suffix.lower() in config['photo_exts']
            is_video = f.suffix.lower() in config['video_exts']
            is_media = is_image or is_video
            if is_media:
                path = collection_out.relative_to(config['outdir']) / Path(f.name)
                src_uri = str(config['base_url'] / path)
                if is_image:
                    slide = {'type': 'photo', 'path': path, 'src_uri': src_uri}
                    data['slides'].append(slide)
                    for size in config['sizes']:
                        out = config['outdir'] / path / Path("{}px.jpg".format(size))
                        n.build(str(out), 'make_thumbnails',
                                inputs=str(f), variables={'size':size})
                elif is_video:
                    slide = {'type': 'video', 'path': path, 'src_uri': src_uri}
                    data['slides'].append(slide)
                    for codec in config['codecs']:
                        out = config['outdir'] / path / Path('video.{}'.format(codec))
                        n.build(str(config['outdir'] / out), 'ffmpeg-{}'.format(codec), inputs=str(f))
        collections_data.append(data)
        if config['downloadable']:
            archive = (collection_out / Path('{}.zip'.format(data['uri_title']))).absolute()
            to_zip = [str(f.absolute()) for f in collection.iterdir() if f.name not in config['to_exclude']]
            n.build(str(archive), 'zip', to_zip)



    (config['resources'] / Path('assets')).mkdir(exist_ok=True)
    n.build(str(config['outdir'] / Path('assets')),
            'rsync',
            str(config['resources'] / Path('assets')))

    n.close()
    subprocess.run(['ninja'])

    template_vars = dict(user_config['template_vars'])
    template_vars['collections_data'] = collections_data
    template_vars['downloadable'] = config['downloadable']
    template_vars['base_url'] = str(config['base_url'])
    # Careful! In the template, base_url comes with leading AND trailing slash!
    if template_vars['base_url'][-1] != '/':
        template_vars['base_url'] += '/'

    index = config['outdir'] / Path('index.html')
    initial_collection = collections_data[0]
    template_vars['slides'] = initial_collection['slides']
    template_vars['current_collection'] = initial_collection
    render_template(index, template_vars, config['resources'])

    for collection in collections_data:
        index = config['outdir'] / collection['path'] / Path('index.html')
        template_vars['slides'] = collection['slides']
        template_vars['current_collection'] = collection
        render_template(index, template_vars, config['resources'])


if __name__ == '__main__':
    main()
