
FROM ubuntu:16.04

RUN apt-get update 
RUN apt-get -y install python-flask python-requests git apache2 libapache2-mod-wsgi
RUN apt-get clean

RUN mkdir /usr/local/blocked
VOLUME /usr/local/blocked
COPY server.py /usr/local/blocked/server.py
ADD BlockedFrontend /usr/local/blocked/BlockedFrontend
#ADD .git /usr/local/blocked/.git
#ADD .ssh /root/.ssh

COPY config.py /usr/local/blocked/config.py
COPY blocked.wsgi /usr/local/blocked/blocked.wsgi
COPY docker/000-default.conf /etc/apache2/sites-enabled

ENV BLOCKEDFRONTEND_SETTINGS /usr/local/blocked/config.py

EXPOSE 80


CMD rm /run/apache2/apache2.pid ; /usr/sbin/apachectl -DFOREGROUND

