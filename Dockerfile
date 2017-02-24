
FROM ubuntu:16.04

RUN apt-get update
RUN apt-get -y install python-flask python-requests

RUN mkdir /usr/local/blocked
COPY server.py /usr/local/blocked/server.py
ADD BlockedFrontend /usr/local/blocked/BlockedFrontend

COPY frontend.live.ini /usr/local/blocked/config.ini

EXPOSE 5000

CMD /usr/bin/python /usr/local/blocked/server.py -c /usr/local/blocked/config.ini

