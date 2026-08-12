# Django Modal Component

## Goal

The goal of this Modal Component is to have a "one stop shop" solution for a modal dialog, with the HTML structure as a template, CSS styling in SASS, JS logic for its dynamics and Django for all data related logic all bundled into one solution. Utilizing the `django-component` third-party library, it enables us to implement modals easily in Django templates, wherever they're needed. By using `slot` and `fill` we have great content flexibility, while keeping the aforementioned topics like HTML structure, CSS and JS as DRY as possible.

## Usage

This outlines the basic usages and provides a code block example below, of how to implement the component in a Django template.

### Instantiate

First you need to add `{% load component_tags %}` at the top of your template. Next you need to add the following code block at the bottom, to include the corresponding JS (if you haven't already you also need to add `{% load static %}`).

```
{% block html_at_end_body %}
    <script src="{% static "modal/script.js" %}" nonce="{{ request.csp_nonce }}" type="module"></script>
{% endblock html_at_end_body %}
```

After that, `{% component "modal" modal_id="xx" size="xx" %}` is enough to instantiate the dialog modal component where `modal_id` should contain a unique identifier that must be also used in the triggers `data-modal-id` attribute, and `size` should contain the appropriate class name to achieve the correct sizing. This can be either `dialog-small`, `dialog-medium` or `dialog-large`.

### The trigger element

The trigger element needs some explaining. This will be the element that `on click` will show the modal dialog,
the `element` gets assigned the click handler by JavaScript.
It's essential to include the data attribute `data-modal-id="xx"`, where "xx" is the same as the `id` attribute on the intended modal. This is what defines the modal dialog that this trigger is meant to target. The only exception to this is when an `<a>` is used, with an `href` containing an anchor `"#xx"`, which points to `the modal-id` of the target modal.
While it might seem obvious to use a `button` or a `a` as a trigger, the modal is set up in a way that allows for any HTML element to be used as a trigger.
The trigger doesn't need to be part of the `{% component %}` itself and can be placed anywhere in the HTML template, though it makes sense to place them adjacent or as close as possible to each other.

### Slots and fills

Each named `fill` corresponds with a placeholder/target `slot` in the component template. The contents between the `fill` tag will be passed to the corresponding `slot`. As shown in the below example it's possible to utilise Django template tags and `HTML` tags with these `fill` tags. This enables us to entirely build the contents of the modal in the template where we implement it. Because we can use `HTML` tags here, we can also use `forms` and leave the handling of said form up to the Django template that knows about the context and applicable data, where we implement the modal. The defaults are used when no `fill` tags are implemented for this slot at all.

There's a total of three slots you can fill:

1.  `header`: empty by default
2.  `content`: empty by default
3.  `footer_buttons`: cancel `button` by default. To have _no buttons_ show at all, it's needed to implement empty `fill` tags for this `slot`.

### CSS dependencies

Including `{% component_css_dependencies %}` is needed to inject the reference to the correct stylesheet needed to style the component into the HTML document. Configuring the location of said stylesheet is done in the components `.py` file.

### Example implementation

```
  <a href="#" data-modal-id="rename-modal">
```

```
{% component "modal" modal_id="rename-modal" size="dialog-small" %}
	{% fill "header" %}
		{% translate "This is an example header." %}
	{% endfill %}
	{% fill "content" %}
		<form  id="content-form"  class="horizontal-view"  action=""  method="post">
			{% csrf_token %}
			{% blocktranslate with context_data_variable=context_data_variable %}
				<p>You can use {{ context_data_variable }} and HTML here <code>valid_time</code>!</p>
			{% endblocktranslate %}
		</form>
	{% endfill %}
	{% fill "footer_buttons" %}
		<input  type="submit"  form="content-form"  class="submit"  value="Submit">
	{% endfill %}
{% endcomponent %}
{% component_css_dependencies %}
```
