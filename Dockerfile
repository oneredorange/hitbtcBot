FROM python:3.6

RUN pip install ccxt slackClient
RUN mkdir /opt/hitbtcBot/
COPY . /opt/hitbtcBot/
WORKDIR /opt/hitbtcBot/

ENTRYPOINT ["python", "bot.py"]
