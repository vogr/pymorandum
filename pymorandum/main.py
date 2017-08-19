import argparse
import logging as log
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

import jinja2
from tqdm import tqdm

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

def hash_bytestr_iter(bytesiter, hasher):
    for block in bytesiter:
        hasher.update(block)
    return hasher.hexdigest()

def file_as_blockiter(afile, blocksize=65536):
    with afile:
        block = afile.read(blocksize)
        while len(block) > 0:
            yield block
            block = afile.read(blocksize)

def gen_hash(f):
    return hash_bytestr_iter(file_as_blockiter(f.open('rb')), hashlib.blake2b(digest_size=32))


def create_thumbnails(pictures_to_process, dest,
                      icc_profile=None, delete_icc=False, linear=False):
    log.info("Creating thumbnails, destination folder is {}".format(dest))
    dest.mkdir(exist_ok=True)
    for p in pictures_to_process:
        s = dest / p.stem
        s.mkdir()
        shutil.copy(p, s / Path('original'))

    sizes = [1920, 1280, 1024, 640, 320]
    options = []
    if icc_profile is not None and icc_profile.exists():
        options += ['--eprofile', icc_profile.absolute()]
    if delete_icc:
        options += ['--delete']
    if linear:
        options += ['--linear']
    for size in sizes:
        incantation = ['vipsthumbnail',
                       '--vips-progress',
                       '--size', 'x{}'.format(size),
                       '-o', dest / Path('%s/{}px.jpg[optimize_coding,strip]'.format(size))
                       #'-o', str(dest / Path('%s/{}px.jpg'.format(size)))
        ] + options +  pictures_to_process
#        incantation = ['parallel',
#                       'vipsthumbnail',
#                       '--vips-progress',
#                       '--size', 'x{}'.format(size),
#                       '-o', dest / Path('%s/{}px.jpg\[optimize_coding,strip\]'.format(size))
#                       #'-o', str(dest / Path('%s/{}px.jpg'.format(size)))
#        ] + options + [':::'] +  [str(p) for p in pictures_to_process]

        #log.info(str(incantation))
        subprocess.run(incantation)


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

    photo_exts = set(['.jpg', '.jpeg', '.png'])

    indir = Path(args.indir_path).absolute()
    outdir = Path(args.outdir_path).absolute()
    config_dir = Path(args.config_dir_path).absolute()
    outdir.mkdir(exist_ok=True)
    log.info('Using input directory: {}'.format(indir))
    log.info('Using output directory: {}'.format(outdir))
    log.info('Reading config from: {}'.format(config_dir))
    
    assets = outdir / Path('assets')
    icc_profile = Path(args.icc_profile_path).absolute()

    to_exclude = set([outdir, assets])
    
    # Save hashes of pictures already present in outdir to later
    # detetermine whether a picture's thumbnails should be re-generated.
    # At the same time, delete any output file whose source file is no longer
    # present.
    outfile_hashes = {}
    
   # Iterate collection of pictures (eg 'Holidays in Rome') 
    for d in (d.absolute() for d in outdir.iterdir() if d.is_dir()):
        # If the whole collection can't be found in input, delete it. 
        if not (indir / (d.relative_to(outdir))).exists():
            log.info("Directory {} doesn't exist anymore, deleting ".format((indir / d.relative_to(outdir)), d))
            shutil.rmtree(d)
        # Iterate over subdir containing thumbnails of a single picture (eg 'IMG-4')
        for subdir in (s.absolute() for s in d.iterdir()):
            relative = subdir.relative_to(outdir)
            key = relative
            # Delete single directory when the corresponding input file can't be found
            if not any((indir / relative).with_suffix(ex).exists() for ex in photo_exts):
                log.info("Subdirectory {} doesn't exist anymore, deleting {}".format((indir / relative), subdir))
                shutil.rmtree(subdir)
            else:
                outfile_hashes[key] = gen_hash(subdir / Path('original'))

    photo_dirs = [x for x in indir.iterdir() if (x.is_dir() and x != outdir)]
    log.info("Using photos from the following directories: {}".format(photo_dirs))

    for d in (d.absolute() for d in photo_dirs):
        pictures_to_process = []
        for picture in (p.absolute() for p in d.iterdir() if
                        p.is_file() and p.suffix in photo_exts):
            relative = picture.relative_to(indir)
            key = relative.with_suffix('')
            h = outfile_hashes.get(key)
            if h is not None:
                if h != gen_hash(picture):
                    log.warn("File has changed: {}".format(picture))
                    log.warn("Removing {}".format(outdir / key))
                    shutil.rmtree(outdir / key)
                    pictures_to_process.append(picture)
            else:
                pictures_to_process.append(picture)
        if pictures_to_process:
            create_thumbnails(pictures_to_process, outdir / d.relative_to(indir),
                            icc_profile = icc_profile, delete_icc = True,
                            linear=False)
        else:
            log.info("Nothing to do for directory {}".format(d))


