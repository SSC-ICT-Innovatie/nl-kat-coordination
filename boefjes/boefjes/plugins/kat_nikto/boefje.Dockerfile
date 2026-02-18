FROM perl:5.40

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs

RUN git clone https://github.com/sullo/nikto

ARG BOEFJE_PATH=./boefjes/plugins/kat_nikto
COPY $BOEFJE_PATH ./

ENTRYPOINT [ "node", "./" ]
