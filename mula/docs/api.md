# API

The browsable api docs can be view at: [http://localhost:8004/docs](http://localhost:8004/docs).
A formal description of the spec can be referenced here: [open api spec](openapi.json)

## Filtering

The endpoints `/tasks` and `/queues/{queue_id}/pop` support additional payload
filters. An example:

```json
// POST /tasks

{
  "filters": [
    {
      "column": "status",
      "operator": "eq",
      "value": "completed"
    }
  ]
}
```

`column` specifies the column/field of the model to filter on.

`operator` specifies the type of operation to apply.

`value` specifies the value to filter on.

### Chaining

Filters can be chained using the `and`, `or` and `not`, and defaults to `and`:

```json
// POST /tasks

{
  "filters": [
    {
      "column": "type",
      "operator": "eq",
      "value": "boefje"
    },
    {
      "column": "status",
      "operator": "eq",
      "value": "completed"
    }
  ]
}
```

Is the same as:

```json
// POST /tasks

{
  "filters": {
    "and": [
      {
        "column": "type",
        "operator": "eq",
        "value": "boefje"
      },
      {
        "column": "status",
        "operator": "eq",
        "value": "completed"
      }
    ]
  }
}
```

Example using the `or` operator:

```json
// POST /tasks

{
  "filters": {
    "or": [
      {
        "column": "status",
        "operator": "eq",
        "value": "completed"
      },
      {
        "column": "status",
        "operator": "eq",
        "value": "failed"
      }
    ]
  }
}
```

Example using the `not` operator:

```json
// POST /tasks

{
  "filters": {
    "not": [
      {
        "column": "status",
        "operator": "eq",
        "value": "completed"
      }
    ]
  }
}
```

### Nested fields

Querying on nested field is also possible. Note that both the `Task`, and
`PrioritizedItem` models both use a `JSONB` column. To query nested field in
these `JSONB` columns you can use the `__` (double under, dunder) separators,
to specify what nested field to filter on.

Example:

```json
// POST /tasks

{
  "filters": [
    {
      "column": "scheduler_id",
      "operator": "eq",
      "value": "boefje"
    },
    {
      "column": "data",
      "field": "input_ooi",
      "operator": "like",
      "value": "%internet%"
    },
    {
      "column": "data",
      "field": "boefje__id", // note the double underscore
      "operator": "eq",
      "value": "dns-zone"
    }
  ]
}
```

When using the specialized `@>` and `<@` operators, make sure the value is
a JSON formatted string, for example:

```json
// POST /tasks

{
  "filters": [
    {
      "column": "scheduler_id",
      "operator": "eq",
      "value": "boefje"
    },
    {
      "column": "data",
      "operator": "@>",
      "value": "{\"boefje\": {\"id\": \"dns-zone\"}}"
    }
  ]
}
```

## Operators

Here's a list of the operators that you can use in the filters:

| Operator      | Description                                                                                           |
| ------------- | ----------------------------------------------------------------------------------------------------- |
| `==`, `eq`    |                                                                                                       |
| `!=`, `ne`    |                                                                                                       |
| `is`          |                                                                                                       |
| `is_not`      |                                                                                                       |
| `is_null`     |                                                                                                       |
| `is_not_null` |                                                                                                       |
| `>`, `gt`     |                                                                                                       |
| `<`, `lt`     |                                                                                                       |
| `>=`, `gte`   |                                                                                                       |
| `<=`, `lte`   |                                                                                                       |
| `like`        | pattern matching                                                                                      |
| `not_like`    | pattern matching                                                                                      |
| `ilike`       | case-insensitive pattern matching                                                                     |
| `not_ilike`   | case-insensitive pattern matching                                                                     |
| `in`          | matching against a list of values                                                                     |
| `not_in`      | matching against a list of values                                                                     |
| `contains`    | substring matching                                                                                    |
| `any`         |                                                                                                       |
| `match`       |                                                                                                       |
| `starts_with` |                                                                                                       |
| `@>`          | Contains, used to check if one JSON or array value contains another JSON or array value               |
| `<@`          | Is contained by, it checks if one JSON or array value is contained by another JSON or array value     |
| `@?`          | Exists, used to check if a key exists in a JSON object                                                |
| `@@`          | Full text search, performs postgresql full text searching using queries (requires `tsvector` columns) |
