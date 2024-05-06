# Wikidata Image Positions

[This tool](https://wd-image-positions.toolforge.org/) shows
[relative position within image](https://www.wikidata.org/wiki/Property:P2677) qualifiers
of [depicts](https://www.wikidata.org/wiki/Property:P180) statements on [Wikidata](https://www.wikidata.org/) items
as areas on the item’s [image](https://www.wikidata.org/wiki/Property:P18) (or other property).
It also supports [Wikimedia Commons](https://commons.wikimedia.org/) files,
where the [named place on map](https://www.wikidata.org/wiki/Property:P9664) property is used in a similar way.

Examples:

* [The Coronation of Napoleon](https://wd-image-positions.toolforge.org/item/Q1231009)
* [Situation Room](https://wd-image-positions.toolforge.org/item/Q2915674)

For more usage information,
please see the tool’s [on-wiki documentation page](https://www.wikidata.org/wiki/User:Lucas_Werkmeister/Wikidata_Image_Positions).

## Toolforge setup

On Wikimedia Toolforge, this tool runs under the `wd-image-positions` tool name.
Source code resides in `~/www/python/src/`,
a virtual environment is set up in `~/www/python/venv/`,
logs end up in `~/uwsgi.log`.

If the web service is not running for some reason, run the following command:
```
webservice start
```
If it’s acting up, try the same command with `restart` instead of `start`.
Both should pull their config from the `service.template` file in the source code directory.

To update the service, run the following commands after becoming the tool account:
```
cd ~/www/python/src
git fetch
git log -p @..@{u} # inspect changes
git rebase
git submodule update --init --recursive
webservice restart
```

If there were any changes in the Python environment (e.g. new dependencies),
add the following steps before the `webservice restart`:
```
webservice shell
source ~/www/python/venv/bin/activate
pip-sync ~/www/python/src/requirements.txt
```

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone --recurse-submodules https://gitlab.wikimedia.org/toolforge-repos/wd-image-positions.git
cd wd-image-positions
pip3 install -r requirements.txt
FLASK_ENV=development flask run
```

If you want, you can do this inside some virtualenv too.

## Contributing

To send a patch, you can submit a
[pull request on GitHub](https://github.com/lucaswerkmeister/tool-wd-image-positions) or a
[merge request on GitLab](https://gitlab.wikimedia.org/toolforge-repos/wd-image-positions).
(E-mail / patch-based workflows are also acceptable.)

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
