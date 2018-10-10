FROM tensorflow/tensorflow:1.9.0
#FROM python:2

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD [ "python", "./app.py" ]

#FLASK_APP=app.py FLASK_DEBUG=1 python -m flask run