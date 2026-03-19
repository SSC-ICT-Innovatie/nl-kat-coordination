import json
from json import JSONDecodeError
from typing import Literal

from jsonschema.exceptions import SchemaError
from jsonschema.validators import Draft202012Validator
from pydantic import field_validator

from octopoes.models import OOI, Reference
from octopoes.models.persistence import ReferenceField


class Question(OOI):
    object_type: Literal["Question"] = "Question"

    ooi: Reference = ReferenceField(OOI)
    schema_id: str
    json_schema: str

    _natural_key_attrs = ["schema_id", "ooi"]
    _traversable = False
    _reverse_relation_names = {"ooi": "questions"}

    @field_validator("json_schema")
    @classmethod
    def json_schema_valid(cls, schema: str) -> str:
        try:
            val = Draft202012Validator({})
            val.check_schema(json.loads(schema))
        except JSONDecodeError as e:
            raise ValueError("The json_schema is not valid JSON") from e
        except SchemaError as e:
            raise ValueError("The json_schema field is not a valid JSON schema") from e

        return schema

    @property
    def config_pk(self) -> str:
        config_id = self.schema_id.split("/")[-1]
        return f"Config|{self.ooi.tokenized.name}|{config_id}"
