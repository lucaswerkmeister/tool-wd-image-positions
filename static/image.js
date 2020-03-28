function setup() {
    const baseUrl = document.querySelector('link[rel=index]').href.replace(/\/$/, ''),
          loginElement = document.getElementById('login'),
          csrfTokenElement = document.getElementById('csrf_token');
    let ItemInputWidget; // loaded in addNewDepictedForms

    function addEditButtons() {
        document.querySelectorAll('.wd-image-positions--depicted-without-region').forEach(addEditButton);
    }

    function addEditButton(element) {
        const entity = element.closest('.wd-image-positions--entity'),
              subjectId = entity.dataset.entityId,
              subjectDomain = entity.dataset.entityDomain,
              depictedId = element.firstChild.dataset.entityId,
              image = entity.querySelector('.wd-image-positions--image');

        if (depictedId === undefined && csrfTokenElement === null) {
            // editing somevalue/novalue not supported in QuickStatements mode
            return;
        }

        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary', 'btn-sm');
        button.textContent = 'add region';
        button.addEventListener('click', onClick)
        element.append(document.createTextNode(' '));
        element.append(button);

        let cropper = null;

        function onClick() {
            if (cropper === null) {
                button.textContent = 'loading...';
                image.classList.add('wd-image-positions--active');
                button.classList.add('wd-image-positions--active');
                cropper = new Cropper(image.firstElementChild, {
                    viewMode: 2,
                    movable: false,
                    rotatable: true, // we don’t rotate the image ourselves, but this allows cropper.js to respect JPEG orientation
                    scalable: false,
                    zoomable: false,
                    checkCrossOrigin: false,
                    ready: function() {
                        button.textContent = 'use this region';
                    },
                });
                document.addEventListener('keydown', onKeyDown);
            } else {
                if (button.textContent === 'loading...') {
                    return;
                }
                image.classList.remove('wd-image-positions--active');
                const cropData = cropper.getData(),
                      imageData = cropper.getImageData(),
                      x = 100 * cropData.x / imageData.naturalWidth,
                      y = 100 * cropData.y / imageData.naturalHeight,
                      w = 100 * cropData.width / imageData.naturalWidth,
                      h = 100 * cropData.height / imageData.naturalHeight,
                      depicted = document.createElement('div');
                depicted.classList.add('wd-image-positions--depicted')
                depicted.append(element.firstChild.cloneNode(true));
                // note: the browser rounds the percentages a bit,
                // and we’ll use the rounded values for the IIIF region
                depicted.style.left = `${x}%`;
                depicted.style.top = `${y}%`;
                depicted.style.width = `${w}%`;
                depicted.style.height = `${h}%`;
                cropper.destroy();
                cropper = null;
                image.append(depicted);
                function pct(name) {
                    return depicted.style[name].replace('%', '');
                }
                const iiifRegion = `pct:${pct('left')},${pct('top')},${pct('width')},${pct('height')}`,
                      quickStatements = `${subjectId}\tP180\t${depictedId}\tP2677\t"${iiifRegion}"`;

                if (csrfTokenElement !== null) {
                    button.textContent = 'adding qualifier…';
                    const statementId = element.dataset.statementId,
                          csrfToken = csrfTokenElement.textContent,
                          formData = new FormData();
                    formData.append('statement_id', statementId);
                    formData.append('iiif_region', iiifRegion);
                    formData.append('_csrf_token', csrfToken);
                    fetch(`${baseUrl}/api/v2/add_qualifier/${subjectDomain}`, {
                        method: 'POST',
                        body: formData,
                        credentials: 'include',
                    }).then(response => {
                        if (response.ok) {
                            element.remove();
                        } else {
                            response.text().then(text => {
                                let message = `An error occurred:\n\n${text}`;
                                if (depictedId !== undefined) {
                                    // we’re not in an event handler, we can’t write to the clipboard directly
                                    message += `\n\nHere is the new region in QuickStatements syntax:\n\n${quickStatements}`;
                                }
                                window.alert(message);
                                element.remove();
                            });
                        }
                    });
                } else {
                    let message = '';
                    if (loginElement !== null) {
                        message = 'You are not logged in. ';
                    }
                    message += 'Copy the new region to the clipboard (in QuickStatements syntax)?';
                    if (window.confirm(message)) {
                        navigator.clipboard.writeText(quickStatements);
                        element.remove();
                    } else {
                        depicted.remove();
                        button.textContent = 'add region';
                        button.classList.remove('wd-image-positions--active');
                    }
                }
            }
            function onKeyDown(eKey) {
                if (eKey.key === 'Escape') {
                    cropper.destroy();
                    cropper = null;
                    image.classList.remove('wd-image-positions--active');
                    document.removeEventListener('keydown', onKeyDown);
                    button.textContent = 'add region';
                    button.classList.remove('wd-image-positions--active');
                }
            }
        }
    }

    function addNewDepictedForm(entityElement) {
        const entity = entityElement.closest('.wd-image-positions--entity'),
              subjectId = entity.dataset.entityId,
              subjectDomain = entity.dataset.entityDomain,
              itemIdInput = new ItemInputWidget({
                  name: 'item_id',
                  required: true,
                  placeholder: 'Q42',
              }),
              itemIdButton = new OO.ui.ButtonWidget({
                  label: 'Add',
              }),
              somevalueButton = new OO.ui.ButtonWidget({
                  label: 'Unknown value',
              }),
              novalueButton = new OO.ui.ButtonWidget({
                  label: 'No value',
              }),
              layout = new OO.ui.FieldsetLayout({
                  items: [
                      new OO.ui.ActionFieldLayout(
                          itemIdInput,
                          itemIdButton,
                          {
                              label: 'Item ID',
                              invisibleLabel: true,
                          },
                      ),
                      new OO.ui.FieldLayout(
                          new OO.ui.ButtonGroupWidget({
                              items: [
                                  // somevalueButton, // the overall SDoC ecosystem isn’t quite ready for this yet; TODO: unhide
                                  // novalueButton, // there’s no technical reason not to implement this, but it’s not really useful
                              ],
                          }),
                      ),
                  ],
                  label: 'Add more “depicted” statements:',
              }),
              layoutElement = layout.$element[0];
        itemIdInput.on('enter', addItemId);
        itemIdButton.on('click', addItemId);
        somevalueButton.on('click', addSomevalue);
        novalueButton.on('click', addNovalue);
        layout.$header.addClass('col-form-label-sm'); // Bootstrap makes OOUI’s <legend> too large by default
        entityElement.append(layoutElement);

        function setAllDisabled(disabled) {
            for (const widget of [itemIdInput, itemIdButton, somevalueButton, novalueButton]) {
                widget.setDisabled(disabled);
            }
        }

        function addItemId() {
            const formData = new FormData();
            formData.append('snaktype', 'value');
            formData.append('item_id', itemIdInput.id);
            addStatement(formData);
        }

        function addSomevalue() {
            const formData = new FormData();
            formData.append('snaktype', 'somevalue');
            addStatement(formData);
        }

        function addNovalue() {
            const formData = new FormData();
            formData.append('snaktype', 'novalue');
            addStatement(formData);
        }

        function addStatement(formData) {
            setAllDisabled(true);
            formData.append('entity_id', subjectId);
            formData.append('_csrf_token', csrfTokenElement.textContent);
            fetch(`${baseUrl}/api/v1/add_statement/${subjectDomain}`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            }).then(response => {
                if (response.ok) {
                    return response.json().then(json => {
                        const statementId = json.depicted.statement_id;
                        const previousElement = layoutElement.previousElementSibling;
                        let depictedsWithoutRegionList;
                        if (previousElement.classList.contains('wd-image-positions--depicteds-without-region')) {
                            depictedsWithoutRegionList = previousElement.children[0];
                        } else {
                            const depictedsWithoutRegionDiv = document.createElement('div'),
                                  depictedsWithoutRegionText = document.createTextNode('Depicted, but with no region specified:');
                            depictedsWithoutRegionList = document.createElement('ul');
                            depictedsWithoutRegionDiv.classList.add('wd-image-positions--depicteds-without-region');
                            depictedsWithoutRegionDiv.append(depictedsWithoutRegionText, depictedsWithoutRegionList);
                            layoutElement.insertAdjacentElement('beforebegin', depictedsWithoutRegionDiv);
                        }
                        const depicted = document.createElement('li');
                        depicted.classList.add('wd-image-positions--depicted-without-region');
                        depicted.dataset.statementId = statementId;
                        depicted.innerHTML = json.depicted_item_link;
                        depictedsWithoutRegionList.append(depicted);
                        addEditButton(depicted);
                    });
                } else {
                    return response.text().then(error => {
                        window.alert(`An error occurred:\n\n${error}`);
                    });
                }
            }).finally(() => {
                setAllDisabled(false);
            });
        }
    }

    function addNewDepictedForms() {
        if (csrfTokenElement !== null && loginElement === null) {
            fixMediaWiki().then(() => {
                mediaWiki.loader.using('wikibase.mediainfo.statements', require => {
                    ItemInputWidget = require('wikibase.mediainfo.statements').ItemInputWidget;
                    document.querySelectorAll('.wd-image-positions--entity').forEach(addNewDepictedForm);
                });
            }, console.error);
        }
    }

    function fixMediaWiki() {
        return new Promise((resolve, reject) => {
            // rewrite 'local' source (/w/load.php) to one with explicit domain,
            // and reset modules that could not be loaded from 'local'
            mediaWiki.loader.addSource({
                'commons': 'https://commons.wikimedia.org/w/load.php',
            });
            const needReload = [];
            for (const [name, module] of Object.entries(mediaWiki.loader.moduleRegistry)) {
                if (module.source === 'local') {
                    module.source = 'commons';
                }
                if (module.state === 'loading') {
                    module.state = 'registered';
                    needReload.push(name);
                }
            }
            // configure WikibaseMediaInfo
            mediaWiki.config.set('wbmiExternalEntitySearchBaseUri', 'https://www.wikidata.org/w/api.php');
            // remove private dependency of mediawiki.api module
            const mwApiModule = mediaWiki.loader.moduleRegistry['mediawiki.api'],
                  userTokensDependencyIndex = mwApiModule.dependencies.indexOf('user.tokens');
            if (userTokensDependencyIndex !== -1) {
                mwApiModule.dependencies.splice(userTokensDependencyIndex, 1); // user.tokens module is private, we can’t load it
            }
            // reload modules that could not be loaded from 'local'
            mediaWiki.loader.enqueue(needReload, resolve, reject);
        }).then(() => {
            return mediaWiki.loader.using('wikibase.api.RepoApi').then(() => {
                if ('getLocationAgnosticMwApi' in wikibase.api) { // used for ItemInputWidget’s search, but cf. T239518
                    wikibase.api.getLocationAgnosticMwApi = function(apiEndpoint) {
                        // original implementation isn’t anonymous, but we can only make anonymous requests
                        return new mediaWiki.ForeignApi(apiEndpoint, { anonymous: true });
                    };
                } else {
                    console.error('no getLocationAgnosticMwApi!');
                }
            });
        });
    }

    addEditButtons();
    addNewDepictedForms();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
} else {
    setup();
}
