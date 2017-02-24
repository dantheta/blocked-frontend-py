
FROM ubuntu:16.04

RUN apt-get update
RUN apt-get -y install python-flask python-requests git

RUN mkdir /usr/local/blocked
VOLUME /usr/local/blocked
COPY server.py /usr/local/blocked/server.py
ADD BlockedFrontend /usr/local/blocked/BlockedFrontend
ADD .git /usr/local/blocked/.git
ADD .ssh /root/.ssh

COPY frontend.live.ini /usr/local/blocked/config.ini

EXPOSE 5000

CMD /usr/bin/python /usr/local/blocked/server.py -c /usr/local/blocked/config.ini --dev

