FROM python:3.7-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN apt-get clean && apt-get update
RUN apt-get -y install gcc
RUN apt-get -y install build-essential
COPY ta-lib-0.4.0-src.tar.gz .
RUN tar -xvzf ta-lib-0.4.0-src.tar.gz && \
  cd ta-lib/ && \
  ./configure --prefix=/usr && \
  make && \
  make install
RUN pip install TA-Lib
COPY . .
EXPOSE 8080
ENTRYPOINT ["python", "assignment_230411.py"]
# CMD gunicorn -b 0.0.0.0:80 assignment_230411:server
