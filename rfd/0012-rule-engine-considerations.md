---
authors: Donny Peeters <@donnype>
state: draft
discussion:
labels: Business Rules, Rule Engine
---

# RFD 0012: Rule Engine Considerations

## Introduction

The current business rules in OpenKAT are hardcoded (`tasks/tasks.py`).
This creates maintenance challenges:

1. **Coupling**: Business logic is tightly coupled to code (deployment)
2. **Limited flexibility**: Only developers can create or modify rules

## Proposal

This RFD is only a discussion and analysis of the Zen rule engine (JDM - JSON Decision Model) to enable declarative,
visual business rule management.
Rules are stored as JSON in the database and executed through a Python binding.

### Basic Examples

### JDM Content Structure Example

<details>
<summary>Singular</summary>
```json
{
  "contentType": "application/vnd.gorules.decision",
  "nodes": [
    {
      "type": "inputNode",
      "content": {
        "schema": "{\n  \"type\": \"object\",\n  \"properties\": {\n    \"name\": {\n      \"type\": \"string\"\n    },\n    \"has_spf_record\": {\n      \"type\": \"boolean\"\n    },\n    \"has_dmarc_record\": {\n      \"type\": \"boolean\"\n    }\n  }\n}"
      },
      "id": "input_node",
      "name": "Hostname",
      "position": {
        "x": 245,
        "y": 130
      }
    },
    {
      "type": "outputNode",
      "content": {
        "schema": ""
      },
      "id": "output_node",
      "name": "Findings",
      "position": {
        "x": 1015,
        "y": 130
      }
    },
    {
      "type": "decisionTableNode",
      "content": {
        "hitPolicy": "collect",
        "rules": [
          {
            "_id": "rule1",
            "SPFfield": "== false",
            "DMARCfield": "",
            "FindingTypefield": "\"KAT-NO-SPF\"",
            "CreateFindingfield": "true",
            "namefield": "name"
          },
          {
            "_id": "rule2",
            "SPFfield": "",
            "DMARCfield": "== false",
            "FindingTypefield": "\"KAT-NO-DMARC\"",
            "CreateFindingfield": "true",
            "namefield": "name"
          }
        ],
        "inputs": [
          {
            "id": "SPFfield",
            "name": "SPF",
            "field": "has_spf_record"
          },
          {
            "id": "DMARCfield",
            "name": "DMARC",
            "field": "has_dmarc_record"
          }
        ],
        "outputs": [
          {
            "id": "FindingTypefield",
            "name": "FindingType",
            "field": "finding_type"
          },
          {
            "id": "CreateFindingfield",
            "name": "Create Finding",
            "field": "create_finding"
          },
          {
            "id": "namefield",
            "name": "Name",
            "field": "name"
          }
        ],
        "passThrough": true,
        "inputField": null,
        "outputPath": null,
        "executionMode": "single"
      },
      "id": "decisionTable1",
      "name": "Record Check",
      "position": {
        "x": 645,
        "y": 130
      }
    }
  ],
  "edges": [
    {
      "id": "edge1",
      "sourceId": "decisionTable1",
      "targetId": "output_node",
      "type": "edge"
    },
    {
      "id": "edge2",
      "sourceId": "input_node",
      "targetId": "decisionTable1",
      "type": "edge"
    }
  ]
}
```
</details>

Example input for simulator:

```json
{
  "name": "test.com",
  "has_spf_record": false,
  "has_dmarc_record": false
}
```

<details>
<summary>Batched</summary>
```json
{
  "contentType": "application/vnd.gorules.decision",
  "nodes": [
    {
      "type": "inputNode",
      "content": {
        "schema": "{\n  \"type\": \"array\",\n  \"items\": {\n    \"type\": \"object\",\n    \"properties\": {\n      \"name\": {\n        \"type\": \"string\"\n      },\n      \"has_spf_record\": {\n        \"type\": \"boolean\"\n      },\n      \"has_dmarc_record\": {\n        \"type\": \"boolean\"\n      }\n    }\n  }\n}"
      },
      "id": "9d39ff61-66bb-40d0-9184-a41cd30ad8dc",
      "name": "request",
      "position": {
        "x": 480,
        "y": 425
      }
    },
    {
      "type": "outputNode",
      "content": {
        "schema": ""
      },
      "id": "d2ff35c3-a267-48db-8639-10d891ef8e6d",
      "name": "response",
      "position": {
        "x": 1495,
        "y": 220
      }
    },
    {
      "type": "decisionTableNode",
      "content": {
        "hitPolicy": "collect",
        "rules": [
          {
            "_id": "7f57bede-6c1c-411a-9f65-e8e501cad21d",
            "ca3e1136-3a8c-4b74-92dd-0c94b66f140b": "== false",
            "9c564f4a-f108-4f94-9cc7-7df648ccb1a5": "",
            "2347fa02-7922-463b-b9a7-71b180fd9214": "\"KAT-NO-SPF\"",
            "15dab3a9-50b1-4fc0-b4f0-54c14153e54b": "true",
            "73d4930d-d7f0-4365-ad3e-d0ab1e0d0000": "name"
          },
          {
            "_id": "660f3e7f-69b7-40dc-83f1-5d3959ad34f3",
            "ca3e1136-3a8c-4b74-92dd-0c94b66f140b": "",
            "9c564f4a-f108-4f94-9cc7-7df648ccb1a5": "== false",
            "2347fa02-7922-463b-b9a7-71b180fd9214": "\"KAT-NO-DMARC\"",
            "15dab3a9-50b1-4fc0-b4f0-54c14153e54b": "true",
            "73d4930d-d7f0-4365-ad3e-d0ab1e0d0000": "name"
          }
        ],
        "inputs": [
          {
            "id": "ca3e1136-3a8c-4b74-92dd-0c94b66f140b",
            "name": "SPF",
            "field": "has_spf_record"
          },
          {
            "id": "9c564f4a-f108-4f94-9cc7-7df648ccb1a5",
            "name": "DMARC",
            "field": "has_dmarc_record"
          }
        ],
        "outputs": [
          {
            "id": "2347fa02-7922-463b-b9a7-71b180fd9214",
            "name": "Output",
            "field": "finding_type"
          },
          {
            "id": "15dab3a9-50b1-4fc0-b4f0-54c14153e54b",
            "name": "Output",
            "field": "create_finding"
          },
          {
            "id": "73d4930d-d7f0-4365-ad3e-d0ab1e0d0000",
            "name": "Output",
            "field": "name"
          }
        ],
        "passThrough": true,
        "inputField": null,
        "outputPath": null,
        "executionMode": "loop",
        "passThorough": false
      },
      "id": "eac87fb6-bf84-498a-b2ff-17d6d68c48c4",
      "name": "decisionTable1",
      "position": {
        "x": 1055,
        "y": 335
      }
    }
  ],
  "edges": [
    {
      "id": "1786e9fe-96e0-459e-878a-41d500ffd4b4",
      "sourceId": "eac87fb6-bf84-498a-b2ff-17d6d68c48c4",
      "type": "edge",
      "targetId": "d2ff35c3-a267-48db-8639-10d891ef8e6d"
    },
    {
      "id": "8b12468b-c969-479c-9503-899034816988",
      "sourceId": "9d39ff61-66bb-40d0-9184-a41cd30ad8dc",
      "type": "edge",
      "targetId": "eac87fb6-bf84-498a-b2ff-17d6d68c48c4"
    }
  ]
}
```
</details>

Example input for simulator:

```json
[
  {
    "name": "test.com",
    "has_spf_record": false,
    "has_dmarc_record": false
  },
  {
    "name": "test.com",
    "has_spf_record": false,
    "has_dmarc_record": true
  },
  {
    "name": "test.com",
    "has_spf_record": true,
    "has_dmarc_record": true
  }
]
```

## Architecture

### Components

1. **Editor**: external JDM editor (GoRules Zen Studio) for visual rule design and JSON exports
2. **DecisionGraph Model**: Stores these JDM definitions in PostgreSQL
3. **Executor**: Python service using `zen-engine-python` to evaluate rules

### Data Model

```python3
class DecisionGraph(models.Model):
    name = models.CharField(max_length=200, unique=True)
    jdm_content = models.JSONField()  # JDM graph definition
    enabled = models.BooleanField(default=True)
    organization = models.ForeignKey(Organization, null=True)

    input_object_type = models.ForeignKey(ContentType)
    input_query = models.TextField(blank=True)  # DjangoQL or dot notation

    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Execution Flow

```
1. Query objects using input_query → [Hostname objects]
2. Serialize objects to nested JSON → {hostname: {...}, dns_records: [...]}
3. Execute JDM graph on input → {findings: [...]}
4. Process output → Create/Delete Finding objects
```

## Input Query Options

### Design Challenge: Generic Input vs. Rule Simplicity

The key challenge is finding the right balance between:

1. **Generic rich input**: Providing comprehensive nested data structures that support many rules without code changes
2. **Simple JDM rules**: Keeping decision logic straightforward and maintainable in the JDM framework

**Problem**: If we pre-compute boolean flags (e.g., `has_spf`, `has_ipv6`) in Python, we couple business logic to code.
If we provide raw nested data, JDM expressions become complex.

**Potential Solution**: Use the dot notation query to declaratively specify what nested data each rule needs.
This allows:

- Rules to be self-documenting (query shows dependencies)
- Input to be rich enough to support expressions without pre-computation
- Multiple rules to share the same input structure
- JDM expressions to remain simple, with perhaps filter/map operations

### Dot Notation Query

Define nested JSON structure using dot notation paths:

```python
input_query = """
hostname
hostname.dnsarecord.ipaddress
hostname.dnstxtrecord
hostname.dnsnsrecord.nameserver.dnsaaaarecord
"""
```

This should generate the following nested JSON:

```json
{
  "name": "example.com",
  "network": "internet",
  "dnsarecord": [
    {
      "ipaddress": {
        "address": "192.0.2.1",
        "network": "internet"
      }
    }
  ],
  "dnstxtrecord": [
    { "value": "v=spf1 ..." },
    { "value": "v=DMARC1 ...", "prefix": "_dmarc" }
  ],
  "dnsnsrecord": [
    {
      "nameserver": {
        "name": "ns1.example.com",
        "dnsaaaarecord": [{ "ipaddress": { "...": "..." } }]
      }
    }
  ]
}
```

Or:

```python
input_query = """
ipaddress.ipport.software
"""
```

Generating:

```json
{
  "address": "127.0.0.1",
  "network": "internet",
  "ip_ports": [
    {
      "port": 443,
      "protocol": "TCP",
      "software": [{ "name": "nginx", "version": "1.21" }]
    }
  ]
}
```

**Benefits**:

- Declarative: Query defines both object selection AND serialization structure
- Consistent: Same pattern for all object traversals
- Flexible: Easy to add/remove related objects
- Self-documenting: Query shows exactly what data the rule needs

### Hybrid Approach with DjangoQL

We could also combine DjangoQL filtering with dot notation serialization:

```python
input_object_type = Hostname
input_filter = "scan_level >= 2"  # DjangoQL
input_relations = """
  hostname.dnstxtrecord
  hostname.dnsnsrecord.nameserver
"""  # Dot notation for nested structure
```

But perhaps this is not needed.

## Current Business Rules Migration

This section shows how all existing business rules can be grouped by shared input structures,
making the system more efficient.

### Group 1: All Hostname DNS Rules

**Rules**: `missing_spf`, `missing_dmarc`, `missing_caa`, `ipv6_webservers`, `ipv6_nameservers`, `domain_owner_verification` (6 rules total)

**Shared Input Query**:

```
hostname.dnstxtrecord
hostname.dnscaarecord
hostname.dnsaaaarecord
hostname.dnsnsrecord.nameserver.dnsaaaarecord
hostname.ipaddress.ipport
```

**Shared Input JSON** (single comprehensive structure):

```json
{
  "name": "example.com",
  "network": "internet",
  "dnstxtrecord": [
    { "value": "v=spf1 include:_spf.google.com ~all" },
    { "value": "v=DMARC1; p=quarantine;", "prefix": "_dmarc" }
  ],
  "dnscaarecord": [{ "flag": 0, "tag": "issue", "value": "letsencrypt.org" }],
  "dnsaaaarecord": [{ "ipaddress": { "address": "2001:db8::1" } }],
  "dnsnsrecord": [
    {
      "nameserver": {
        "name": "ns1.example.com",
        "dnsaaaarecord": [{ "ipaddress": { "address": "2001:db8::53" } }]
      }
    },
    {
      "nameserver": {
        "name": "ns2.example.com",
        "dnsaaaarecord": []
      }
    }
  ],
  "ipaddress": [
    {
      "address": "192.0.2.1",
      "ipport": [
        { "port": 443, "protocol": "TCP" },
        { "port": 80, "protocol": "TCP" }
      ]
    }
  ]
}
```

**JDM Decision Table**
TODO

---

### Group 2: Open Port Rules (IPAddress)

**Rules**: `open_sysadmin_port`, `open_database_port`, `open_remote_desktop_port`, `open_common_port`, `open_uncommon_port` (5 rules total)

**Shared Input Query**:

```
ipaddress.ipport
```

**Shared Input JSON**:

```json
{
  "address": "192.0.2.1",
  "ipport": [
    { "port": 22, "protocol": "TCP" },
    { "port": 3306, "protocol": "TCP" },
    { "port": 8080, "protocol": "TCP" }
  ]
}
```

**JDM Decision Table**
TODO

---

### Group 3: Software Detection Rules (IPAddress)

**Rules**: `mysql_detection`, `mongodb_detection`, `openssh_detection`, `rdp_detection`, `pgsql_detection`, `telnet_detection`, `db2_detection` (7 rules total)

**Shared Input Query**:

```
ipaddress.ipport.software
```

**Shared Input JSON**:

```json
{
  "address": "192.0.2.1",
  "ipport": [
    {
      "port": 3306,
      "protocol": "TCP",
      "software": [{ "name": "mysql", "version": "8.0" }]
    },
    {
      "port": 22,
      "protocol": "TCP",
      "software": [{ "name": "openssh", "version": "9.0" }]
    }
  ]
}
```

**JDM Decision Table**
TODO

---

## Summary

12 business rules → 3 input structures → Maximum query reduction and rule maintenance efficiency.

**Efficiency Gains**:

- **Single hostname query** evaluates 6 rules (SPF, DMARC, CAA, IPv6 webservers, IPv6 nameservers, domain verification)
- **Single IPAddress query** evaluates 5 port classification rules
- **Single IPAddress+software query** evaluates 7 software detection rules parametrically

## Functional Requirements

### Core Requirements (FR)

1. **FR1: Rule Independence**: Business rules should be independent of Python code deployment
2. **FR2: Object Query Support**: Rules must query and evaluate on OpenKAT object types
3. **FR3: Finding Management**: Rules must create and delete findings
4. **FR4: Organization Scoping**: Rules can be global or per-organization

## Extensibility

### Potential Future Requirements (EX)

1. **EX1: Object Creation**: Beyond findings, rules could create new objects
2. **EX2: Rule Composition**: Combine multiple rules into workflows
3. **EX3: Custom Actions**: Beyond findings, trigger custom actions

### Why the Proposal Covers Requirements

**FR1 (Rule Independence)**: JDM graphs stored as JSON in `DecisionGraph.jdm_content` field, editable without code deployment.
**FR2 (Object Query Support)**: Dot notation queries traverse Django relationships declaratively (`hostname.dnstxtrecord`, `ipaddress.ipport.software`).
**FR3 (Finding Management)**: JDM output includes `create_finding` boolean and `finding_type` field. Executor creates/deletes Finding objects based on output.
**FR4 (Organization Scoping)**: `DecisionGraph.organization` field (nullable for global rules). Filter by organization during execution.

## Implementation Phases

1. Add `DecisionGraph` model with basic fields
2. Implement Zen executor service for simple decision tables
3. Parse dot notation input queries to nested JSON serializer
4. Build REST API for CRUD operations
5. Migrate one business rule as proof of concept
6. Add test execution endpoint
7. Gradually migrate remaining business rules
8. Add rule versioning and audit logging

## Considerations

### Learning Curve

- **Concern**: JDM editor learning curve for rule authors
- **Mitigation**:
  - Documentation and examples
  - Templates for common patterns
  - Export existing rules as starting point

## Open Questions

1. Should we support multiple output types (findings, objects, metrics)?
2. How to handle rule conflicts (multiple rules creating same finding)?
3. What's the maximum acceptable query depth for dot notation?
4. How should we delete old findings that are invalid now? Should we add them to the input?
