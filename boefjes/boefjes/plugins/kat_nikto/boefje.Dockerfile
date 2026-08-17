FROM perl:5.40

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs

RUN git clone --depth 1 --branch 2.6.0 https://github.com/sullo/nikto
RUN cpanm --notest JSON XML::Writer

ARG BOEFJE_PATH=./boefjes/plugins/kat_nikto
COPY $BOEFJE_PATH ./

ENTRYPOINT [ "node", "./" ]
