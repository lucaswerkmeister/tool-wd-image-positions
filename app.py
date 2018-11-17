# -*- coding: utf-8 -*-

import collections
import flask
import iiif_prezi.factory
import json
import mwapi
import mwoauth
import os
import random
import requests
import requests_oauthlib
import string
import toolforge
import urllib.parse
import urllib.request
import yaml

from exceptions import *


app = flask.Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')

app.before_request(toolforge.redirect_to_https)

toolforge.set_user_agent('lexeme-forms', email='mail@lucaswerkmeister.de')
user_agent = requests.utils.default_user_agent()

anonymous_session = mwapi.Session(host='https://www.wikidata.org', user_agent=user_agent, formatversion=2)

default_property = 'P18'

__dir__ = os.path.dirname(__file__)
try:
    with open(os.path.join(__dir__, 'config.yaml')) as config_file:
        app.config.update(yaml.safe_load(config_file))
except FileNotFoundError:
    print('config.yaml file not found, assuming local development setup')
else:
    consumer_token = mwoauth.ConsumerToken(app.config['oauth']['consumer_key'], app.config['oauth']['consumer_secret'])


@app.route('/', methods=['GET', 'POST'])
def index():
    if flask.request.method == 'POST':
        if 'item_id' in flask.request.form:
            item_id = flask.request.form['item_id']
            property_id = flask.request.form.get('property_id')
            if 'manifest' in flask.request.form or 'preview' in flask.request.form:
                manifest_url = full_url('iiif_manifest_with_property', item_id=item_id, property_id=property_id or default_property)
                if 'manifest' in flask.request.form:
                    return flask.redirect(manifest_url)
                else:
                    mirador_protocol = 'https' if manifest_url.startswith('https') else 'http'
                    mirador_url = mirador_protocol + '://tools.wmflabs.org/mirador/?manifest=' + manifest_url
                    return flask.redirect(mirador_url)
            else:
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

@app.route('/login')
def login():
    redirect, request_token = mwoauth.initiate('https://www.wikidata.org/w/index.php', consumer_token, user_agent=user_agent)
    flask.session['oauth_request_token'] = dict(zip(request_token._fields, request_token))
    return flask.redirect(redirect)

@app.route('/oauth/callback')
def oauth_callback():
    access_token = mwoauth.complete('https://www.wikidata.org/w/index.php', consumer_token, mwoauth.RequestToken(**flask.session['oauth_request_token']), flask.request.query_string, user_agent=user_agent)
    flask.session['oauth_access_token'] = dict(zip(access_token._fields, access_token))
    return flask.redirect(flask.url_for('index'))

@app.route('/item/<item_id>')
def item(item_id):
    return item_and_property(item_id, property_id=default_property)

@app.route('/item/<item_id>/<property_id>')
def item_and_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_depicteds=True)
    if item is None:
        return flask.render_template('item-without-image.html',)
    return flask.render_template('item.html', **item)

@app.route('/iiif/<item_id>/manifest.json')
def iiif_manifest(item_id):
    return flask.redirect(flask.url_for('iiif_manifest_with_property', item_id=item_id, property_id=default_property))

@app.route('/iiif/<item_id>/<property_id>/manifest.json')
def iiif_manifest_with_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_description=True, include_metadata=True)
    if item is None:
        return '', 404
    manifest = build_manifest(item)
    resp = flask.jsonify(manifest.toJSON(top=True))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/iiif/<item_id>/list/annotations.json')
def iiif_annotations(item_id):
    return iiif_annotations_with_property(item_id, property_id=default_property)

@app.route('/iiif/<item_id>/<property_id>/list/annotations.json')
def iiif_annotations_with_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_depicteds=True)
    # Although the pct canvas is OK for the image API, we need to target
    # canvas coordinates with the annotations, so we need the w,h
    image_info = load_image_info(item['image_title'])
    width, height = int(image_info['thumbwidth']), int(image_info['thumbheight'])

    url = flask.url_for('iiif_annotations_with_property',
                item_id=item_id, property_id=property_id, _external=True,
                _scheme=flask.request.headers.get('X-Forwarded-Proto', 'http'))
    annolist = {
        '@id': url,
        '@type': 'sc:AnnotationList',
        'label': 'Annotations for ' + item['label']['value'],
        'resources': []
    }
    canvas_url = url[:-len('list/annotations.json')] + 'canvas/c0.json'
    for depicted in item['depicteds']:
        link = 'http://www.wikidata.org/entity/' + flask.Markup.escape(item_id)
        label = depicted['label']['value']
        # We can put a lot more in here, but minimum for now, and ensure works in Mirador
        anno = {
            '@id': '#' + depicted['statement_id'],
            '@type': 'oa:Annotation',
            'motivation': 'identifying',
            'on': canvas_url,
            'resource': {
                '@id': link,
                'format': 'text/plain',
                'chars': label
            }
        }
        iiif_region = depicted.get('iiif_region', None)
        if iiif_region:
            parts = iiif_region.replace('pct:', '').split(',')
            x = int(float(parts[0])*width/100)
            y = int(float(parts[1])*height/100)
            w = int(float(parts[2])*width/100)
            h = int(float(parts[3])*height/100)
            anno['on'] = anno['on'] + '#xywh=' + ','.join(str(d) for d in [x,y,w,h])
        annolist['resources'].append(anno)
    resp = flask.jsonify(annolist)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/iiif_region/<iiif_region>')
def iiif_region(iiif_region):
    return iiif_region_and_property(iiif_region, default_property)

@app.route('/iiif_region/<iiif_region>/<property_id>')
def iiif_region_and_property(iiif_region, property_id):
    query = 'SELECT DISTINCT ?item WHERE { ?item p:P180/pq:P2677 "' + iiif_region.replace('\\', '\\\\').replace('"', '\\"') + '". }'
    with urllib.request.urlopen('https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(query)) as request:
        query_results = json.loads(request.read().decode())

    items = []
    items_without_image = []
    for result in query_results['results']['bindings']:
        item_id = result['item']['value'][len('http://www.wikidata.org/entity/'):]
        item = load_item_and_property(item_id, property_id, include_depicteds=True)
        if item is None:
            items_without_image.append(item_id)
        else:
            items.append(item)

    return flask.render_template('iiif_region.html', items=items, items_without_image=items_without_image)

@app.route('/api/add_qualifier/<statement_id>/<iiif_region>/<csrf_token>', methods=['POST'])
def api_add_qualifier(statement_id, iiif_region, csrf_token):
    if csrf_token != flask.session['_csrf_token']:
        return 'Wrong CSRF token (try reloading the page).', 403

    access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
    auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                    resource_owner_key=access_token.key, resource_owner_secret=access_token.secret)
    session = mwapi.Session(host='https://www.wikidata.org', auth=auth, user_agent=user_agent, formatversion=2)

    token = session.get(action='query', meta='tokens', type='csrf')['query']['tokens']['csrftoken']
    response = session.post(action='wbsetqualifier', claim=statement_id, property='P2677',
                            snaktype='value', value=('"' + iiif_region + '"'),
                            summary='region drawn manually using [[User:Lucas Werkmeister/Wikidata Image Positions|Wikidata Image Positions tool]]',
                            token=token)
    if response['success'] == 1:
        return '', 204
    else:
        return str(response), 500


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

@app.template_filter()
def user_link(user_name):
    return (flask.Markup(r'<a href="https://www.wikidata.org/wiki/User:') +
            flask.Markup.escape(user_name.replace(' ', '_')) +
            flask.Markup(r'">') +
            flask.Markup(r'<bdi>') +
            flask.Markup.escape(user_name) +
            flask.Markup(r'</bdi>') +
            flask.Markup(r'</a>'))

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

@app.template_global()
def authentication_area():
    if 'oauth' not in app.config:
        return flask.Markup()

    if 'oauth_access_token' not in flask.session:
        return (flask.Markup(r'<a id="login" class="navbar-text" href="') +
                flask.Markup.escape(flask.url_for('login')) +
                flask.Markup(r'">Log in</a>'))

    access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
    identity = mwoauth.identify('https://www.wikidata.org/w/index.php',
                                consumer_token,
                                access_token)

    csrf_token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    flask.session['_csrf_token'] = csrf_token

    return (flask.Markup(r'<span class="navbar-text">Logged in as ') +
            user_link(identity['username']) +
            flask.Markup(r'</span><span id="csrf_token" style="display: none;">') +
            flask.Markup.escape(csrf_token) +
            flask.Markup(r'</span>'))

@app.errorhandler(WrongDataValueType)
def handle_wrong_data_value_type(error):
    response = flask.render_template('wrong-data-value-type.html',
                                     expected_data_value_type=error.expected_data_value_type,
                                     actual_data_value_type=error.actual_data_value_type)
    return response, error.status_code


def load_item_and_property(item_id, property_id,
                           include_depicteds=False, include_description=False, include_metadata=False):
    language_codes = request_language_codes()

    props = ['claims']
    if include_description:
        props.append('descriptions')

    api_response = anonymous_session.get(action='wbgetentities',
                                         props=props,
                                         ids=item_id,
                                         languages=language_codes)
    item_data = api_response['entities'][item_id]
    item = {
        'item_id': item_id,
    }
    entity_ids = [item_id]

    if include_description:
        description = None
        for language_code in language_codes:
            if language_code in item_data['descriptions']:
                description = item_data['descriptions'][language_code]
                break
        item['description'] = description

    image_datavalue = best_value(item_data, property_id)
    if image_datavalue is None:
        return None
    if image_datavalue['type'] != 'string':
        raise WrongDataValueType(expected_data_value_type='string', actual_data_value_type=image_datavalue['type'])
    image_title = image_datavalue['value']
    item['image_title'] = image_title
    item['image_attribution'] = image_attribution(image_title, language_codes[0])

    if include_depicteds:
        depicteds = depicted_items(item_data)
        for depicted in depicteds:
            entity_ids.append(depicted['item_id'])

    if include_metadata:
        metadata = item_metadata(item_data)
        entity_ids += metadata.keys()

    labels = load_labels(entity_ids, language_codes)
    item['label'] = labels[item_id]

    if include_depicteds:
        for depicted in depicteds:
            depicted['label'] = labels[depicted['item_id']]
        item['depicteds'] = depicteds

    if include_metadata:
        item['metadata'] = []
        for property_id, values in metadata.items():
            for value in values:
                item['metadata'].append({
                    'label': labels[property_id],
                    'value': value
                })

    return item

def load_image_info(image_title):
    file_title = 'File:' + image_title.replace(' ', '_')
    response = anonymous_session.get(action='query', prop='imageinfo', iiprop='url|mime',
                                     iiurlwidth=8000, titles=file_title)

    return response['query']['pages'][0]['imageinfo'][0]

def full_url(endpoint, **kwargs):
    return flask.url_for(endpoint, _external=True, _scheme=flask.request.headers.get('X-Forwarded-Proto', 'http'), **kwargs)

def current_url():
    return full_url(flask.request.endpoint, **flask.request.view_args)

def language_string_wikibase_to_iiif(language_string):
    if language_string is None:
        return None
    return {language_string['language']: language_string['value']}

def build_manifest(item):
    base_url = current_url()[:-len('/manifest.json')]
    fac = iiif_prezi.factory.ManifestFactory()
    fac.set_base_prezi_uri(base_url)
    fac.set_debug('error')

    manifest = fac.manifest(ident='manifest.json')
    manifest.label = language_string_wikibase_to_iiif(item['label'])
    manifest.description = language_string_wikibase_to_iiif(item['description'])
    attribution = image_attribution(item['image_title'], request_language_codes()[0])
    if attribution is not None:
        manifest.attribution = attribution['attribution_text']
        manifest.license = attribution['license_url']
    for metadata in item['metadata']:
        manifest.set_metadata({
            'label': language_string_wikibase_to_iiif(metadata['label']),
            'value': metadata['value'],
        })
    sequence = manifest.sequence(ident='normal', label='default order')
    canvas = sequence.canvas(ident='c0')
    canvas.label = language_string_wikibase_to_iiif(item['label'])
    annolist = fac.annotationList(ident='annotations', label='Things depicted on this canvas')
    canvas.add_annotationList(annolist)
    populate_canvas(canvas, item, fac)

    return manifest

def populate_canvas(canvas, item, fac):
    image_info = load_image_info(item['image_title'])
    width, height = image_info['thumbwidth'], image_info['thumbheight']
    canvas.set_hw(height, width)
    anno = canvas.annotation(ident='a0')
    img = anno.image(ident=image_info['thumburl'], iiif=False)
    img.set_hw(height, width)
    img.format = image_info['mime']

    # add a thumbnail to the canvas
    thumbs_path = image_info['thumburl'].replace('/wikipedia/commons/', '/wikipedia/commons/thumb/')
    thumb_400 = thumbs_path + '/400px-' + item['image_title']
    canvas.thumbnail = fac.image(ident=thumb_400)
    canvas.thumbnail.format = image_info['mime']
    thumbwidth, thumbheight = 400, int(height*(400/width))
    canvas.thumbnail.set_hw(thumbheight, thumbwidth)

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

def best_values(item_data, property_id):
    if property_id not in item_data['claims']:
        return []

    statements = item_data['claims'][property_id]
    preferred_values = []
    normal_values = []
    deprecated_values = []

    for statement in statements:
        if statement['mainsnak']['snaktype'] != 'value':
            continue

        datavalue = statement['mainsnak']['datavalue']
        if statement['rank'] == 'preferred':
            preferred_values.append(datavalue)
        elif statement['rank'] == 'normal':
            normal_values.append(datavalue)
        else:
            deprecated_values.append(datavalue)

    return preferred_values or normal_values or deprecated_values

def depicted_items(item_data):
    depicteds = []

    for statement in item_data['claims'].get('P180', []):
        if statement['mainsnak']['snaktype'] != 'value':
            continue
        depicted = {
            'item_id': statement['mainsnak']['datavalue']['value']['id'],
            'statement_id': statement['id'],
        }

        for qualifier in statement.get('qualifiers', {}).get('P2677', []):
            if qualifier['snaktype'] != 'value':
                continue
            depicted['iiif_region'] = qualifier['datavalue']['value']
            break

        depicteds.append(depicted)
    return depicteds

def item_metadata(item_data):
    # property IDs based on https://www.wikidata.org/wiki/Wikidata:WikiProject_Visual_arts/Item_structure#Describing_individual_objects
    property_ids = [
        'P170', # creator
        'P1476', # title
        'P571', # inception
        'P186', # material used
        'P2079', # fabrication method
        'P2048', # height
        'P2049', # width
        'P2610', # thickness
        'P88', # commissioned by
        'P1071', # location of final assembly
        'P127', # owned by
        'P1259', # coordinates of the point of view
        'P195', # collection
        'P276', # location
        'P635', # coordinate location
        'P1684', # inscription
        'P136', # genre
        'P135', # movement
        'P921', # main subject
        'P144', # based on
        'P941', # inspired by
    ]
    metadata = collections.defaultdict(list)

    for property_id in property_ids:
        for value in best_values(item_data, property_id):
            response = anonymous_session.get(action='wbformatvalue',
                                             generate='text/html',
                                             datavalue=json.dumps(value),
                                             property=property_id)
            metadata[property_id].append(response['result'])

    return metadata

def load_labels(entity_ids, language_codes):
    entity_ids = list(set(entity_ids))
    labels = {}
    for chunk in [entity_ids[i:i+50] for i in range(0, len(entity_ids), 50)]:
        items_data = anonymous_session.get(action='wbgetentities', props='labels', languages=language_codes, ids=chunk)['entities']
        for entity_id, item_data in items_data.items():
            labels[entity_id] = {'language': 'zxx', 'value': entity_id}
            for language_code in language_codes:
                if language_code in item_data['labels']:
                    labels[entity_id] = item_data['labels'][language_code]
                    break
    return labels

def image_attribution(image_title, language_code):
    response = anonymous_session.get(action='query', prop='imageinfo', iiprop='extmetadata',
                                     iiextmetadatalanguage=language_code,
                                     titles=('File:' + image_title))
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

    attribution = attribution[len(', '):]

    return {
        'license_url': license_url,
        'attribution_text': attribution.striptags(),
        'attribution_html': attribution,
    }
