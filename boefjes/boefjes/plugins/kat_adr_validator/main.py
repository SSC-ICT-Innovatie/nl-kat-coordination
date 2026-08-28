import docker

ADR_VALIDATOR_REPOSITORY = "registry.gitlab.com/commonground/don/adr-validator"
ADR_VALIDATOR_VERSION = "0.2.0"


def run_adr_validator(url: str) -> str:
    client = docker.from_env()
    image = f"{ADR_VALIDATOR_REPOSITORY}:{ADR_VALIDATOR_VERSION}"
    args = ("-format", "json", url)

    return client.containers.run(image, args, remove=True, read_only=True)


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    input_ooi = boefje_meta["arguments"]["input"]
    api_url = input_ooi["api_url"]

    hostname = api_url["netloc"]["name"]
    path = api_url["path"]
    scheme = api_url["scheme"]

    url = f"{scheme}://{hostname}{path}"

    output = run_adr_validator(url)

    return [(set(), output)]
