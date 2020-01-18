# Pymorandum

Pymorandum is a blazing fast photo gallery site generator. From a simple collection of photos organised in directories, pymorandum creates a simple static website ready to be served by a webserver (or by [Github Pages][github-pages]!).

Visit a [live example][example] now to see what the output looks like, and see behind the scenes in the [source repository][gallery-source]. (And a quick thanks to [Pixabay][pixabay] for the royalty-free photos and videos).


Features include:
* Photo and video support
* Easy pages customization using Jinja2 templates
* Responsive images size
* Incremental generation (only generate thumbnails for new photos)
* Fast!

Pymorandum's speed stems from its usage of the [ninja build system][ninja] together with the superfast image thumbnailer [`vipsthumbnail`][vipsthumbnail].

This project was greatly inspired by [Jack000's Exposé][expose] and [PetitPrince's pyxpose][pyxpose] from which I even recycled bits of code (thanks to the generous MIT license).

[github-pages]: https://help.github.com/en/github/working-with-github-pages/getting-started-with-github-pages
[example]: https://vogier.github.io/pymorandum-gallery/
[gallery-source]: https://github.com/vogr/pymorandum-gallery
[ninja]: https://ninja-build.org/
[pixabay]: https://pixabay.com
[vipsthumbnail]: https://jcupitt.github.io/libvips/API/current/Using-vipsthumbnail.md.html
[expose]: https://github.com/Jack000/expose
[pyxpose]: https://github.com/PetitPrince/pyxpose
## Installation

### Dependencies
Pymorandum delegates intensive work to powerful allies. To this end it must call `ninja`, `rsync`, `vipsthumbnail`, `ffmpeg` and `zip`.

#### Fedora
(Note: you will need a version of ffmpeg shipping with libfdk_aac. You can get one by enabling [negativo17's multimedia repository][multimedia]: `dnf config-manager --add-repo=https://negativo17.org/repos/fedora-multimedia.repo`)
```bash
sudo dnf install ninja-build rsync vips-tools ffmpeg zip
```

[multimedia]: https://negativo17.org/handbrake/
#### Debian/Ubuntu
```bash
sudo apt-get install ninja-build rsync libvips-tools ffmpeg zip
```

#### Windows
It should work too! Simply install the previously listed dependencies and make sure they can be called from the command-line (ie they must be [added to your System PATH][PATH]). (WARNING: Untested!)

[PATH]: https://www.howtogeek.com/118594/how-to-edit-your-system-path-for-easy-command-line-access/

### Pymorandum
```bash
git clone https://github.com/vogier/pymorandum
cd pymorandum
python3 -m pip install .
```
> Tip: run `python3 -m pip --user install .` instead to install it to your home directory. In this case you should also add `~/.local/bin` to your `$PATH` if it is not already in it.
> To do this automatically on every install create the file `~/.config/pip/pip.conf` with the content
> ```ini
> [global]
> user = 1
> ```

If you do not wish to install pymorandum, you may run it directly using `python3 pymorandum/main.py`. In this case you will need to manually install other dependencies: `python3 -m pip install setuptools natsort ninja_syntax jinja2 slugify`.

## Usage

Create a directory where pymorandum will do its work, and simply run `pymorandum --init` to get started.

``` bash
mkdir 'Photo Gallery'
cd 'Photo Gallery'
pymorandum --init
```

Your directory will now contain the file `config.ini` and the folder `resources`.
You should modify `config.ini` to your needs. Here is a quick description of the different variables:
* `base_url`: if your photo gallery is hosted at `yoursite.com`, leave it blank, else if it lives at `yoursite.com/photo-gallery` change it to `photo-gallery`. On Github Pages, it should correspong to your chosen `baseurl` (by default the project name). (Note: leading and trailing slashes are ignored.)
* `input_directory`: the directory where pymorandum will look for your collections. A collection is a directory containing photos or videos. For each collection, pymorandum will create a page accessible from the sidebar on the website.
* `output_directory`: the directory where pymorandum will generate the website.
* `resources_directory`: pymorandum will look for a template named `template.html` in this folder. The `assets` folder in the resources directory will simply be copied to the `output_directory`.
* `log_level`: the level of warnings to get (advised: leave `INFO`).
* `icc_profile_path`: the ICC profile used by `vipsthumbnail` during the thumbnail generation. Ideally this should link to a valid sRGB.icc profile. If in doubt, there is no need to modify it.
* `downloadable_zipfiles`: for a each collection, show a download button for a zip archive containing the collection. WARNING: all files in the collection will end in the archive, not just photos and videos!
* All variables in the category `templates_vars` will be passed to jinja2 when rendering the template.

> Tip: You may use `~` in any path variable to denote `/home/your_user`.

Once you're happy with your config file, simply run `pymorandum` and you'll quickly get all the necessary files in `output_dir`.

> Tip: to preview yout website, you can use python's built in webserver. Simply run `cd _site; python3 -m http.server 8000` (this will not work if you have specified a `base_url`).
>
> When dealing with a `base_url`, I personnaly use [Caddy server][caddy] with the following `Caddyfile` (replace `base_url` accordingly):
> ```
> https://localhost:2015/base_url/ {
>     tls self_signed
>     root _site/
>     header / {
>         X-Content-Type-Options  "nosniff"
>         X-Frame-Options         "DENY"
>         Content-Security-Policy "default-src https:"
>     }
>     gzip
> }
> ```


[caddy]: https://caddyserver.com/


Pymorandum will respect the alphabetical order of files and folders when generating the gallery, you may therefore precede any file or directory name by a number to organise your gallery (no need for leading zeroes, the order 1, 2, 3, ..., 10, 11, 12 works as expected!).

By default a collection's name will be the name of the directory. You may modify it by placing a `metadata.ini` file in the corresponding directory with the following content:
```ini
[collection]
title = Your new title
uri_title = your_title   # (Optional) This title will be used in the collection's URI: yoursite.com/collections/uri_title
```
