function setup() {
    const baseUrl = document.querySelector('link[rel=index]').href.replace(/\/$/, ''),
          loginElement = document.getElementById('login'),
          csrfTokenElement = document.getElementById('csrf_token');

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
                    rotatable: false,
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
                    } ).then(response => {
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
              form = document.createElement('form'),
              fieldset = document.createElement('fieldset'),
              explanationSpan = document.createElement('span'),
              itemIdLabel = document.createElement('label'),
              itemIdInputGroup = document.createElement('div'),
              itemIdInput = document.createElement('input'),
              itemIdButton = document.createElement('button'),
              somevalueButton = document.createElement('button'),
              novalueButton = document.createElement('button');
        form.classList.add('form-inline');
        fieldset.classList.add('form-inline');
        explanationSpan.classList.add('form-text', 'mr-2');
        explanationSpan.textContent = 'Add more “depicted” statements:';
        itemIdInputGroup.classList.add('input-group');
        itemIdLabel.classList.add('sr-only');
        itemIdLabel.textContent = 'Item ID';
        itemIdInput.classList.add('form-control', 'w-75');
        itemIdInput.name = 'item_id';
        itemIdInput.type = 'text';
        itemIdInput.pattern = 'Q[1-9][0-9]*';
        itemIdInput.required = true;
        itemIdInput.placeholder = 'Q42';
        itemIdInput.id = Math.random().toString(36).substring(2);
        itemIdLabel.htmlFor = itemIdInput.id;
        itemIdButton.type = 'submit';
        itemIdButton.classList.add('btn', 'btn-primary', 'form-control', 'w-25');
        itemIdButton.name = 'snaktype';
        itemIdButton.value = 'value';
        itemIdButton.textContent = 'Add';
        for (const button of [somevalueButton, novalueButton]) {
            button.type = 'submit';
            button.classList.add('btn', 'btn-secondary', 'form-control', 'ml-sm-2', 'mt-1', 'mt-sm-0');
            button.formNoValidate = true;
            button.name = 'snaktype';
        }
        somevalueButton.value = 'somevalue';
        somevalueButton.textContent = 'Unknown value';
        somevalueButton.hidden = true; // the overall SDoC ecosystem isn’t quite ready for this yet; TODO: unhide
        novalueButton.value = 'novalue';
        novalueButton.textContent = 'No value';
        novalueButton.hidden = true; // there’s no technical reason not to implement this, but it’s not really useful
        itemIdInputGroup.append(itemIdInput, itemIdButton);
        fieldset.append(explanationSpan, itemIdLabel, itemIdInputGroup, somevalueButton, novalueButton);
        form.append(fieldset);
        entityElement.append(form);

        form.addEventListener('submit', function(event) {
            event.preventDefault();
            fieldset.disabled = true;

            const formData = new FormData();
            formData.append('entity_id', subjectId);
            formData.append('_csrf_token', csrfTokenElement.textContent);

            // the event doesn’t tell us which button was clicked :/
            const focusedElement = form.querySelector(':focus');
            for (const button of [itemIdButton, somevalueButton, novalueButton]) {
                if (button === focusedElement) {
                    formData.append(button.name, button.value);
                }
            }
            if (itemIdInput === focusedElement) {
                formData.append(itemIdButton.name, itemIdButton.value);
            }

            if (formData.get('snaktype') === 'value') {
                formData.append('item_id', itemIdInput.value);
            }

            fetch(`${baseUrl}/api/v1/add_statement/${subjectDomain}`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            } ).then(response => {
                if (response.ok) {
                    return response.json().then(json => {
                        const statementId = json.depicted.statement_id;
                        const previousElement = form.previousElementSibling;
                        let depictedsWithoutRegionList;
                        if (previousElement.classList.contains('wd-image-positions--depicteds-without-region')) {
                            depictedsWithoutRegionList = previousElement.children[0];
                        } else {
                            const depictedsWithoutRegionDiv = document.createElement('div'),
                                  depictedsWithoutRegionText = document.createTextNode('Depicted, but with no region specified:');
                            depictedsWithoutRegionList = document.createElement('ul');
                            depictedsWithoutRegionDiv.classList.add('wd-image-positions--depicteds-without-region');
                            depictedsWithoutRegionDiv.append(depictedsWithoutRegionText, depictedsWithoutRegionList);
                            form.insertAdjacentElement('beforebegin', depictedsWithoutRegionDiv);
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
                fieldset.disabled = false;
            });;
        });
    }

    function addNewDepictedForms() {
        if (csrfTokenElement !== null && loginElement === null) {
            document.querySelectorAll('.wd-image-positions--entity').forEach(addNewDepictedForm);
        }
    }

    addEditButtons();
    addNewDepictedForms();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
} else {
    setup();
}
