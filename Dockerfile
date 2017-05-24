
FROM ubuntu:16.04

RUN apt-get update
RUN apt-get -y install python-flask python-requests git

RUN mkdir /usr/local/blocked
VOLUME /usr/local/blocked
COPY server.py /usr/local/blocked/server.py
ADD BlockedFrontend /usr/local/blocked/BlockedFrontend
ADD .git /usr/local/blocked/.git
ADD .ssh /root/.ssh

COPY config.py /usr/local/blocked/config.py

ENV BLOCKEDFRONTEND_CONFIG /usr/local/blocked/config.py

EXPOSE 5000

CMD /usr/bin/python /usr/local/blocked/server.py

