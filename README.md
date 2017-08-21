# Pymorandum

Pymorandum is a blazing fast photo gallery site generator. From a simple collection of photos organised in directories, pymorandum creates a simple static website ready to be served by a webserver (or by [GitLab Pages][gitlab-pages]!).

Visit a [live example][example] now to see what the output looks like, and see behind the scenes in the [source repository][gallery-source]. (And a quick thanks to [Pixabay][pixabay] for the royalty-free photos and videos).


Features include:
* Photo and video support
* Easy pages customization using Jinja2 templates.
* Responsive images size
* Incremental generation (only generate thumbnails for new photos)

Pymorandum's speed stems from its usage of the [ninja build system][ninja] together with the superfast image thumbnailer [`vipsthumbnail`][vipsthumbnail].


[gitlab-pages]: https://about.gitlab.com/features/pages/
[example]: https://vogier.gitlab.io/pymorandum-gallery
[gallery-source]: https://gitlab.com/vogier/pymorandum-gallery
[ninja]: https://ninja-build.org/
[pixabay]: https://pixabay.com
[vipsthumbnail]: https://jcupitt.github.io/libvips/API/current/Using-vipsthumbnail.md.html

## Installation

### Dependencies
Pymorandum delegates intensive work to powerful allies. To this end it must call `ninja`, `vipsthumbnail` and `ffmpeg`. 

#### Fedora
(Note: you will need a version of ffmpeg shipping with libfdk_aac. You can get one by enabling [negativo17's multimedia repository][multimedia]: `dnf config-manager --add-repo=https://negativo17.org/repos/fedora-multimedia.repo`)
```
sudo dnf install ninja-build vips-tools ffmpeg
```

[multimedia]: https://negativo17.org/handbrake/
#### Debian/Ubuntu
```
sudo apt-get install ninja-build libvips-tools ffmpeg
```
### Pymorandum
```
git clone https://gitlab.com/vogier/pymorandum
cd pymorandum
python3 -m pip install .
```
> Tip: run `python3 -m pip --user install .` instead to install it to your home directory. In this case you should also add `~/.local/bin` to your `$PATH` if it is not already in it.
> To do this automatically on every install create the file `~/.config/pip/pip.conf` with the content<br>
    `[global]`<br>
    `user = 1`

If you do not wish to install pymorandum, you may run it directly using `python3 pymorandum/main.py`. In this case you will need to manually install other dependencies: `python3 -m pip install setuptools natsort ninja_syntax jinja2 slugify`.

## Usage

Create a directory where pymorandum will do its work, and simply run `pymorandum --init` to get started

```
mkdir 'Photo Gallery'
cd 'Photo Gallery'
pymorandum --init
```

You directory will now contain the file `config.ini` and the folder `resources`.
You should modify `config.ini` to your needs. Here is a quick description of the different variables:
* `base_url`: if your photo gallery is hosted at `yoursite.com`, leave it blank, else if it lives at `yoursite.com/photo-gallery` change it to `photo-gallery`. On GitLab Pages, it should correspong to your chosen `baseurl` (by default the project name). (Note: leading and trailing slashes are ignored.)
* `input_directory`: the directory where pymorandum will look for your collections. A collection is a directory containing photos or videos. For each collection, pymorandum will create a page accessible from the sidebar on the website.
* `output_directory`: the directory where pymorandum will generate the website.
* `resources_directory`: pymorandum will look for a template named `template.html` in this folder. The `assets` folder in the resources directory will simply be copied to the `output_directory`.
* `log_level`: the level of warnings to get (advised: leave `INFO`)
* `icc_profile_path`: the ICC profile used by `vipsthumbnail` during the thumbnail generation. Ideally this should link to a valid sRGB.icc profile. If in doubt, there is no need to modify it.
* All variables in the category `templates_vars` will be passed to jinja2 when rendering the template.

> Tip: You may use `~` in any variable to denote `/home/your_user`.

Once you're happy with your config file, simply run `pymorandum` and you'll quickly get all the necessary files in `output_dir`.

> Tip: to preview yout website, you can use python's built in webserver. Simply run `cd _site; python3 -m http.server 8000` (this will not work if you have specified a `base_url`).


Pymorandum will respect the alphabetical order of files and folders when generating the gallery, you may therefore precede any file or directory name by a number to organise your gallery (no need for leading zeroes, the order 1, 2, 3, ..., 10, 11, 12 works as expected!).

By default a collection's name will be the name of the directory. You may modify it by placing a `metadata.ini` file in the corresponding directory with the following content:
```
[collection]
title = Your new title
uri_title = your_title   # (Optional) This title will be used in the collection's uri: yoursite.com/collections/your_title
```
