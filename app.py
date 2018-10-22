# -*- coding: utf-8 -*-

import flask
import json
import urllib.parse
import urllib.request

from exceptions import *


app = flask.Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')


@app.route('/', methods=['GET', 'POST'])
def index():
    if flask.request.method == 'POST':
        if 'item_id' in flask.request.form:
            item_id = flask.request.form['item_id']
            property_id = flask.request.form.get('property_id')
            if property_id:
                return flask.redirect(flask.url_for('item_and_property', item_id=item_id, property_id=property_id))
            else:
                return flask.redirect(flask.url_for('item', item_id=item_id))
        if 'iiif_region' in flask.request.form:
            iiif_region = flask.request.form['iiif_region']
            property_id = flask.request.form.get('property_id')
            if property_id:
                return flask.redirect(flask.url_for('iiif_region_and_property', iiif_region=iiif_region, property_id=property_id))
            else:
                return flask.redirect(flask.url_for('iiif_region', iiif_region=iiif_region))
    return flask.render_template('index.html')

@app.route('/item/<item_id>')
def item(item_id):
    return item_and_property(item_id, property_id='P18')

@app.route('/item/<item_id>/<property_id>')
def item_and_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id)
    if item is None:
        return flask.render_template('item-without-image.html',)
    return flask.render_template('item.html', **item)

@app.route('/iiif_region/<iiif_region>')
def iiif_region(iiif_region):
    return iiif_region_and_property(iiif_region, 'P18')

@app.route('/iiif_region/<iiif_region>/<property_id>')
def iiif_region_and_property(iiif_region, property_id):
    query = 'SELECT DISTINCT ?item WHERE { ?item p:P180/pq:P2677 "' + iiif_region.replace('\\', '\\\\').replace('"', '\\"') + '". }'
    with urllib.request.urlopen('https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(query)) as request:
        query_results = json.loads(request.read().decode())

    items = []
    items_without_image = []
    for result in query_results['results']['bindings']:
        item_id = result['item']['value'][len('http://www.wikidata.org/entity/'):]
        item = load_item_and_property(item_id, property_id)
        if item is None:
            items_without_image.append(item_id)
        else:
            items.append(item)

    return flask.render_template('iiif_region.html', items=items, items_without_image=items_without_image)

# https://iiif.io/api/image/2.0/#region
@app.template_filter()
def iiif_region_to_style(iiif_region):
    if iiif_region == 'full':
        return 'left: 0px; top: 0px; width: 100%; height: 100%;'
    if iiif_region.startswith('pct:'):
        left, top, width, height = iiif_region[len('pct:'):].split(',')
        z_index = int(1000000 / (float(width)*float(height)))
        return 'left: %s%%; top: %s%%; width: %s%%; height: %s%%; z-index: %s;' % (left, top, width, height, z_index)
    left, top, width, height = iiif_region.split(',')
    z_index = int(1000000000 / (int(width)*int(height)))
    return 'left: %spx; top: %spx; width: %spx; height: %spx; z-index: %s;' % (left, top, width, height, z_index)

@app.template_global()
def item_link(item_id, label):
    return (flask.Markup(r'<a href="http://www.wikidata.org/entity/') +
            flask.Markup.escape(item_id) +
            flask.Markup(r'" lang="') +
            flask.Markup.escape(label['language']) +
            flask.Markup(r'" data-entity-id="') +
            flask.Markup.escape(item_id) +
            flask.Markup(r'">') +
            flask.Markup.escape(label['value']) +
            flask.Markup(r'</a>'))

@app.errorhandler(WrongDataValueType)
def handle_wrong_data_value_type(error):
    response = flask.render_template('wrong-data-value-type.html',
                                     expected_data_value_type=error.expected_data_value_type,
                                     actual_data_value_type=error.actual_data_value_type)
    return response, error.status_code


def load_item_and_property(item_id, property_id):
    language_codes = request_language_codes()

    with urllib.request.urlopen('https://www.wikidata.org/w/api.php?format=json&formatversion=2&action=wbgetentities&props=claims&ids=' + item_id) as request:
        item_data = json.loads(request.read().decode())['entities'][item_id]

    image_datavalue = best_value(item_data, property_id)
    if image_datavalue is None:
        return None
    if image_datavalue['type'] != 'string':
        raise WrongDataValueType(expected_data_value_type='string', actual_data_value_type=image_datavalue['type'])
    image_title = image_datavalue['value']

    depicteds = depicted_items(item_data)
    item_ids = [depicted['item_id'] for depicted in depicteds]
    item_ids.append(item_id)
    labels = load_labels(item_ids, language_codes)
    for depicted in depicteds:
        depicted['label'] = labels[depicted['item_id']]

    return {
        'item_id': item_id,
        'label': labels[item_id],
        'image_title': image_title,
        'image_attribution': image_attribution(image_title, language_codes[0]),
        'depicteds': depicteds,
    }

def request_language_codes():
    language_codes = flask.request.args.getlist('uselang')

    for accept_language in flask.request.headers.get('Accept-Language', '').split(','):
        language_code = accept_language.split(';')[0].strip()
        language_code = language_code.lower()
        language_codes.append(language_code)
        if '-' in language_code:
            language_codes.append(language_code.split('-')[0])
    
    language_codes.append('en')

    return language_codes

def best_value(item_data, property_id):
    if property_id not in item_data['claims']:
        return None

    statements = item_data['claims'][property_id]
    normal_value = None
    deprecated_value = None

    for statement in statements:
        if statement['mainsnak']['snaktype'] != 'value':
            continue

        datavalue = statement['mainsnak']['datavalue']
        if statement['rank'] == 'preferred':
            return datavalue
        if statement['rank'] == 'normal':
            normal_value = datavalue
        else:
            deprecated_value = datavalue

    return normal_value or deprecated_value

def depicted_items(item_data):
    depicteds = []

    for statement in item_data['claims'].get('P180', []):
        if statement['mainsnak']['snaktype'] != 'value':
            continue
        depicted = {'item_id': statement['mainsnak']['datavalue']['value']['id']}

        for qualifier in statement.get('qualifiers', {}).get('P2677', []):
            if qualifier['snaktype'] != 'value':
                continue
            depicted['iiif_region'] = qualifier['datavalue']['value']
            break

        depicteds.append(depicted)
    return depicteds

def load_labels(item_ids, language_codes):
    item_ids = list(set(item_ids))
    labels = {}
    for chunk in [item_ids[i:i+50] for i in range(0, len(item_ids), 50)]:
        with urllib.request.urlopen('https://www.wikidata.org/w/api.php?format=json&formatversion=2&action=wbgetentities&props=labels' +
                                    '&languages=' + '|'.join(language_codes) +
                                    '&ids=' + '|'.join(chunk)) as request:
            items_data = json.loads(request.read().decode())['entities']
        for item_id, item_data in items_data.items():
            labels[item_id] = {'language': 'zxx', 'value': item_id}
            for language_code in language_codes:
                if language_code in item_data['labels']:
                    labels[item_id] = item_data['labels'][language_code]
                    break
    return labels

def image_attribution(image_title, language_code):
    with urllib.request.urlopen('https://commons.wikimedia.org/w/api.php?format=json&formatversion=2' +
                                '&action=query&prop=imageinfo&iiprop=extmetadata' +
                                '&iiextmetadatalanguage=' + language_code +
                                '&titles=File:' + urllib.parse.quote(image_title)) as request:
        response = json.loads(request.read().decode())
    metadata = response['query']['pages'][0]['imageinfo'][0]['extmetadata']
    no_value = {'value': None}

    attribution_required = metadata.get('AttributionRequired', no_value)['value']
    if attribution_required != 'true':
        return None

    attribution = flask.Markup()

    artist = metadata.get('Artist', no_value)['value']
    if artist:
        attribution += flask.Markup(r', ') + flask.Markup(artist)

    license_short_name = metadata.get('LicenseShortName', no_value)['value']
    license_url = metadata.get('LicenseUrl', no_value)['value']
    if license_short_name and license_url:
        attribution += (flask.Markup(r', <a href="') + flask.Markup.escape(license_url) + flask.Markup(r'">') +
                        flask.Markup.escape(license_short_name) +
                        flask.Markup(r'</a>'))

    credit = metadata.get('Credit', no_value)['value']
    if credit:
        attribution += flask.Markup(r' (') + flask.Markup(credit) + flask.Markup(r')')

    return attribution
