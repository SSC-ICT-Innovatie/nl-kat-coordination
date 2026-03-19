*** Settings ***
Library     OperatingSystem
Library     RequestsLibrary
Library     DateTime
Library     Collections
Library     CeleryMonitor.py


*** Variables ***
${REF_HOSTNAME}                     Hostname|internet|example.com
${REF_IPADDR}                       IPAddressV4|internet|1.1.1.1
${REF_RESOLVEDHOSTNAME}             ResolvedHostname|internet|example.com|internet|1.1.1.1

${OCTOPOES_URI}                     http://localhost:29000/_dev
${XTDB_URI}                         http://localhost:29002/_xtdb/_dev
${QUEUE_URI}                        amqp://ci_user:ci_pass@localhost:29004/kat
${RABBIT_MQ_API_URI}                http://ci_user:ci_pass@localhost:29003/api
${VALID_TIME}                       2022-01-01T00:00:00+00:00

${SCAN_PROFILE_MUTATION_QUEUE}      scan_profile_mutations


*** Keywords ***
Declare Scan Profile
    [Arguments]    ${reference}    ${scan_level}
    ${params}    Get Valid Time Params
    ${data}    Create Dictionary    reference=${reference}    level=${scan_level}    scan_profile_type=declared
    ${response}    Put
    ...    ${OCTOPOES_URI}/scan_profiles
    ...    json=${data}
    ...    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200

Insert Observation
    [Arguments]    ${origin_file}
    ${norm_output_json}    Get File    ${origin_file}
    ${response}    Post    ${OCTOPOES_URI}/observations    ${norm_output_json}
    Should Be Equal As Integers    ${response.status_code}    200

Insert Declaration
    [Arguments]    ${origin_file}
    ${norm_output_json}    Get File    ${origin_file}
    ${response}    Post    ${OCTOPOES_URI}/declarations    ${norm_output_json}
    Should Be Equal As Integers    ${response.status_code}    200

Insert Normalizer Output
    Insert Observation    tests/fixtures/normalizer_output.json

Insert Empty Normalizer Output
    Insert Observation    tests/fixtures/normalizer_output_empty.json

Insert Calvin Outputs
    Insert Declaration    tests/fixtures/calvin_output_1.json
    Insert Declaration    tests/fixtures/calvin_output_2.json

    Await Sync

Insert Regular Declarations
    Insert Declaration    tests/fixtures/regular_manual_declaration.json
    Insert Declaration    tests/fixtures/regular_manual_declaration_with_null_values.json

    Await Sync

Get Messages From Queue
    [Arguments]    ${queue}    ${ackmode}
    &{data}    Create dictionary    count=10000    ackmode=${ackmode}    encoding=auto    truncate=50000
    ${response}    Post    ${RABBIT_MQ_API_URI}/queues/kat/${queue}/get    json=${data}
    RETURN    ${response.json()}

Wait For XTDB Synced
    ${response}    Get    ${XTDB_URI}/sync

Get All Document Ids
    ${query}    Set Variable    {:query {:find [?e] :where [[?e :xt/id]]}}
    ${headers}    Create Dictionary    Content-Type=application/end    Accept=application/json
    ${response}    Post    ${XTDB_URI}/query    data=${query}    headers=${headers}
    ${rows}    Set Variable    ${response.json()}
    ${ids}    Create List
    FOR    ${cols}    IN    @{rows}
        Append To List    ${ids}    ${cols[0]}
    END
    RETURN    ${ids}

Clear XTDB
    ${ids}    Get All Document Ids
    ${operations}    Create List
    FOR    ${id}    IN    @{ids}
        ${operation}    Create List    evict    ${id}    ${VALID_TIME}
        Append To List    ${operations}    ${operation}
    END
    ${transaction}    Create Dictionary    tx-ops=${operations}
    ${headers}    Create Dictionary    Content-Type=application/json    Accept=application/json
    ${response}    Post    ${XTDB_URI}/submit-tx    json=${transaction}    headers=${headers}
    Wait For XTDB Synced

Setup Test
    Create XTDB node
    Start Monitoring    ${QUEUE_URI}

Teardown Test
    Delete XTDB node
    Get Messages From Queue    octopoes    ack_requeue_false
    Get Messages From Queue    ${SCAN_PROFILE_MUTATION_QUEUE}    ack_requeue_false
    Stop Monitoring

Await Sync
    Sleep    300ms
    Await Tasks Done
    Wait For XTDB Synced

Get Objects
    ${params}    Get Valid Time Params
    ${response}    Get    ${OCTOPOES_URI}/objects    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200
    Should Be Equal    ${response.headers["content-type"]}    application/json
    ${response_data}    Set Variable    ${response.json()}
    RETURN    ${response_data}

Get Valid Time Params
    ${valid_time_params}    Create Dictionary    valid_time=${VALID_TIME}
    RETURN    ${valid_time_params}

Await Tasks Done
    Wait Until Keyword Succeeds    1 min    200ms    Task Type Empty    SENT
    Wait Until Keyword Succeeds    1 min    200ms    Task Type Empty    RECEIVED
    Wait Until Keyword Succeeds    1 min    200ms    Task Type Empty    STARTED

Task Type Empty
    [Arguments]    ${task_type}
    ${count}    Count Tasks    ${task_type}
    Should Be Equal As Integers    ${count}    0

Object List Should Contain
    [Arguments]    ${reference}
    ${response_data}    Get Objects
    ${pks}    Evaluate    [item["primary_key"] for item in ${response_data["items"]}]
    Should Contain    ${pks}    ${reference}    ${reference} not found in object list

Object List Should Not Contain
    [Arguments]    ${reference}
    ${response_data}    Get Objects
    ${pks}    Evaluate    [item["primary_key"] for item in ${response_data["items"]}]
    Should Not Contain    ${pks}    ${reference}    ${reference} found in object list

Total Object Count Should Be
    [Arguments]    ${length}
    ${response_data}    Get Objects
    Should Be Equal As Integers    ${response_data["count"]}    ${length}    Object count should be ${length}

Recalculate Scan Profiles
    ${params}    Get Valid Time Params
    ${response}    Get
    ...    ${OCTOPOES_URI}/scan_profiles/recalculate
    ...    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200
    Await Sync

Verify Object Present
    [Arguments]    ${reference}
    ${params}    Create Dictionary
    ...    reference=${reference}
    ...    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/object    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200

Verify Object Not Present
    [Arguments]    ${reference}
    ${params}    Create Dictionary
    ...    reference=${reference}
    ...    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/object    params=${params}    expected_status=404

Create XTDB node
    ${response}    Post    ${OCTOPOES_URI}/node
    Should Be Equal As Integers    ${response.status_code}    200

Delete XTDB node
    ${response}    Delete    ${OCTOPOES_URI}/node
    Should Be Equal As Integers    ${response.status_code}    200
