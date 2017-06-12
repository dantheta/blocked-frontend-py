
# Blocked Frontend 

A flask application that provides a frontend onto the blocked.org.uk
filter detection and reporting system.

# Installation 

    python setup.py install

# Configuration 

Create a config.py file somewhere on the filesystem, containing:

    API_EMAIL='account@example.com'
    API_SECRET='abcdefgh'

These credentials are obtained by registering with blocked.org.uk

# Running BlockedFrontend 

BlockedFrontend will run under mod_wsgi on apache.  Create a blocked.wsgi file somewhere on the filesystem, containing:

    from BlockedFrontend import application

Add an apache config file (or add to a virtualhost):

```
    WSGIDaemonProcess blockedfrontend threads=5
    WSGIScriptAlias / /path/to/blocked.wsgi

    <Directory /path/as/above>
        WSGIProcessGroup blockedfrontend
        WSGIApplicationGroup %{GLOBAL}
        Order deny,allow
        Allow from all
		Require all granted
    </Directory>
```

Optionally, the static resources bundled in the project can be exposed through apache.  The exact path may vary on your system.

```
	Alias /static /usr/lib/python2.7/site-packages/BlockedFrontend/static
	<Directory /usr/lib/python2.7/site-packages/BlockedFrontend/static>
        Order deny,allow
        Allow from all
		Require all granted
	</Directory>
```


# Editing pages 

Static pages can be found in BlockedFrontend/templates/cms.  The /about,
/contact and /support pages are contained in HTML files named about.html,
contact.html and support.html.

The HTML files are based on a template which defines regions in a 1 by 3 or 2
by 3 grid.  The page content is placed into one of these regions using a
`{% block %}`.

## Example:

```
{% block row1_col1 %}
<h3>Region Title</h3>

<p>This is were the text for this region goes</p>.
<p>You can <a href="/otherpage">link</a> to other pages too.</p>
{% endblock %}
```

Edits can be made using GitHub's online editor.

Blocks defined in the base template are:

* **page_menu** - list of links to show in the page's menu region
* **banner_text** - leading body text, shown below the page title
* **page_js_libs** - any extra javascript includes for this page.

Variables that can be used in the base template:

* **pagerole** - a page description, like "Site report"
* **pagetitle** - the page title, used in the title bar and as the large title on
  the page.
* **url** - (optional) 



## Creating new pages

If a file called BlockedFrontend/templates/cms/something.html, the page will
automatically be made available at /something.

A new page should declare which base template is being used:

```
{% extends "layout_1x3.page.html" %}
```

layout_1x3 defines a 1 column, 3 row grid
layout_2x3 defines a 2 column, 3 row grid.


Assign values to page variables (title, and optional role).

```
{%set pagetitle = "Taking action against censorship from Internet Service Providers" %}
```

The main blocks for the page are defined:

```
{% block banner_text %}
  <p>The UK government has pressured Internet Service Providers (ISPs) into
  promoting filters to prevent children and young people from seeing internet
  content that is supposed to be for over 18s.  This may seem like a good
  idea, but in reality filters block much more than they are supposed to,
  which means information is being censored.</p>

  <p>It is very possible that sites you care about are being restricted.  The
  Blocked project is here to help prevent this from happening.</p> 

{% endblock %}
```



