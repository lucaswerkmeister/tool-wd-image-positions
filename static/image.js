function setup() {
    'use strict';

    const translations = JSON.parse(document.getElementsByTagName('main')[0].dataset.translations);

    function addScaleInputs() {
        document.querySelectorAll('.wd-image-positions--wrapper').forEach(addScaleInput);
    }

    function addScaleInput(wrapper) {
        // remove the no-JS inputs, labels, and <br> before the wrapper
        const nodesToRemove = new Set(['#text', 'BR', 'LABEL', 'INPUT']);
        let node, value = 1;
        while (nodesToRemove.has((node = wrapper.previousSibling).nodeName)) {
            if (node.checked) {
                value = node.value;
            }
            node.remove();
        }
        // create JS input (can be wrapped in a div, unlike the no-JS ones,
        // which must be direct siblings of the wrapper for the CSS to work)
        const div = document.createElement('div');
        const label = document.createElement('label');
        label.innerHTML = translations['image-scale'];
        const input = document.createElement('input');
        input.type = 'range';
        input.value = value;
        input.min = 0;
        input.max = 5; // arbitrary
        input.step = 'any';
        input.classList.add('wd-image-positions--scale');
        label.append(input);
        div.append(label);
        wrapper.before(div);

        const image = wrapper.firstElementChild;
        const updateScale = () => {
            image.style.setProperty('--scale', input.value);
        };
        input.addEventListener('input', updateScale);
        updateScale();
    }

    addScaleInputs();
}

setup();
