FROM 3.7-slim
COPY requirements.txt
RUN pip install -r requirements.txt
COPY ta-lib-0.4.0-src.tar.gz
RUN tar -xvzf ta-lib-0.4.0-src.tar.gz && \
  cd ta-lib/ && \
  ./configure --build=aarch64-unknown-linux-gnu && \
  make && \
  make install
RUN pip install TA-Lib
ENTRYPOINT ["python", "assignment_230411.py"]
