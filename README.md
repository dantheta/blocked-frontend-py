
= Blocked Frontend =

A flask application that provides a frontend onto the blocked.org.uk
filter detection and reporting system.

= Installation =

    python setup.py install

= Configuration =

Create a config.py file somewhere on the filesystem, containing:

    API_EMAIL='account@example.com'
    API_SECRET='abcdefgh'

These credentials are obtained by registering with blocked.org.uk

= Running BlockedFrontend =

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




