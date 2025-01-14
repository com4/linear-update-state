FROM python:3.13-alpine

COPY action.py /action.py

ENTRYPOINT ["/action.py"]