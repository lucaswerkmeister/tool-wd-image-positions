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

On Wikimedia Toolforge, this tool runs under the `wd-image-positions` tool name,
from a container built using the [Toolforge Build Service](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Building_container_images).

### Image build

To build a new version of the image,
run the following command on Toolforge after becoming the tool account:

```sh
toolforge build start --use-latest-versions https://gitlab.wikimedia.org/toolforge-repos/wd-image-positions
```

The image will contain all the dependencies listed in `requirements.txt`,
as well as the commands specified in the `Procfile`.

### Webservice

The web frontend of the tool runs as a webservice using the `buildpack` type.
The web service runs the first command in the `Procfile` (`web`),
which runs the Flask WSGI app using gunicorn.

```
webservice start
```

Or, if the `~/service.template` file went missing:

```
webservice --mount=none buildservice start
```

If it’s acting up, try the same command with `restart` instead of `start`.

### Configuration

The tool reads configuration from both the `config.yaml` file (if it exists)
and from any environment variables starting with `TOOL_*`.
The config file is more convenient for local development;
the environment variables are used on Toolforge:
list them with `toolforge envvars list`.
Nested dicts are specified with envvar names where `__` separates the key components,
and the tool lowercases keys in nested dicts,
so that e.g. the following are equivalent:

```sh
toolforge envvars create TOOL_OAUTH__CONSUMER_KEY 271b735e0cf895694f2ee7a3ae7a2dbc
```

```yaml
OAUTH:
    CONSUMER_KEY: 271b735e0cf895694f2ee7a3ae7a2dbc
```

For the available configuration variables, see the `config.yaml.example` file.

### Update

To update the tool, build a new version of the image as described above,
then restart the webservice:

```sh
toolforge build start --use-latest-versions https://gitlab.wikimedia.org/toolforge-repos/wd-image-positions
webservice restart
```

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://gitlab.wikimedia.org/toolforge-repos/wd-image-positions.git
cd wd-image-positions
pip3 install -r requirements.txt -r dev-requirements.txt
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
