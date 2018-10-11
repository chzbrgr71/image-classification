FROM python:2.7.15

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

#ENV FLASK_APP app.py
#ENV FLASK_DEBUG 1
#CMD [ "python",  "-m", "flask", "run" ]

ENTRYPOINT ["python"]
CMD ["app.py"]