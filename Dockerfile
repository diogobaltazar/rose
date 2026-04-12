FROM alpine:3.19

RUN apk add --no-cache python3 py3-pip bash git github-cli

WORKDIR /topgun

COPY pyproject.toml .
COPY src/ src/
RUN pip3 install --no-cache-dir --break-system-packages .

# topgun install — global Claude config
COPY global/ global/

WORKDIR /project

ENTRYPOINT ["topgun"]
CMD ["--help"]
