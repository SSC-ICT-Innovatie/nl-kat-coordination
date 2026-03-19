*** Settings ***
Library             OperatingSystem
Library             RequestsLibrary
Library             DateTime
Library             String
Resource            robot.resource

Test Setup          Setup Test
Test Teardown       Teardown Test


*** Test Cases ***
Inheritance Of Two Declared Scan Profiles
    Await Sync
    Declare Scan Profile    ${REF_HOSTNAME}    ${4}
    Declare Scan Profile    ${REF_IPADDR}    ${2}
    Await Sync
    Recalculate Scan Profiles
    Verify Scan Level    ${REF_HOSTNAME}    ${4}
    Verify Scan Level    ${REF_IPADDR}    ${2}
    Verify Scan Level    ${REF_RESOLVEDHOSTNAME}    ${4}
    Verify Scan LeveL Filter    1    ${0}
    Verify Scan LeveL Filter    2    ${2}
    Verify Scan LeveL Filter    3    ${0}
    Verify Scan LeveL Filter    4    ${3}
    Verify Scan LeveL Filter    0    ${9}
    Verify Scan LeveL Filter    ${{ [2,4] }}    ${5}
    Verify Scan LeveL Filter    ${{ [3,4] }}    ${3}
    Verify Scan LeveL Filter    ${{ [2,0] }}    ${11}
    Verify Scan Profile Mutation Queue    ${REF_HOSTNAME}    ${{[0, 4]}}
    Verify Scan Profile Mutation Queue    ${REF_IPADDR}    ${{[0, 2]}}
    Verify Scan Profile Mutation Queue    ${REF_RESOLVEDHOSTNAME}    ${{[0, 4]}}
    Total Object Count Should Be    14

Recalculate Inheritance After Modification
    Declare Scan Profile    ${REF_HOSTNAME}    ${4}
    Declare Scan Profile    ${REF_IPADDR}    ${2}
    Await Sync
    Recalculate Scan Profiles
    Set Scan Profile To Empty    ${REF_HOSTNAME}
    Recalculate Scan Profiles
    Verify Scan Level    ${REF_HOSTNAME}    ${0}
    Verify Scan Level    ${REF_IPADDR}    ${2}
    Verify Scan Level    ${REF_RESOLVEDHOSTNAME}    ${0}
    Verify Scan Profile Mutation Queue    ${REF_HOSTNAME}    ${{[0, 4, 0]}}
    Verify Scan Profile Mutation Queue    ${REF_IPADDR}    ${{[0, 2]}}
    Verify Scan Profile Mutation Queue    ${REF_RESOLVEDHOSTNAME}    ${{[0, 4, 0]}}

Empty Scan Profiles
    Recalculate Scan Profiles
    Verify Scan Level    ${REF_HOSTNAME}    ${0}
    Verify Scan Level    ${REF_IPADDR}    ${0}
    Verify Scan Level    ${REF_RESOLVEDHOSTNAME}    ${0}
    Verify Scan Profile Mutation Queue    ${REF_HOSTNAME}    ${{[0]}}
    Verify Scan Profile Mutation Queue    ${REF_IPADDR}    ${{[0]}}
    Verify Scan Profile Mutation Queue    ${REF_RESOLVEDHOSTNAME}    ${{[0]}}


*** Keywords ***
Setup Test
    robot.Setup Test
    Insert Normalizer Output
    Await Sync

Set Scan Profile To Empty
    [Arguments]    ${reference}
    ${params}    Get Valid Time Params
    ${data}    Create Dictionary    reference=${reference}    scan_profile_type=empty
    ${response}    Put
    ...    ${OCTOPOES_URI}/scan_profiles
    ...    json=${data}
    ...    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200

Verify Scan Level
    [Arguments]    ${reference}    ${scan_level}
    ${params}    Create Dictionary
    ...    reference=${reference}
    ...    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/object    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200
    Should Be Equal    ${response.headers["content-type"]}    application/json
    ${response_data}    Set Variable    ${response.json()}
    Should Be Equal    ${response_data["primary_key"]}    ${reference}
    Should Be Equal As Integers
    ...    ${response_data["scan_profile"]["level"]}
    ...    ${scan_level}
    ...    Scan Level of ${reference} should be ${scan_level} in the database

Verify Scan LeveL Filter
    [Arguments]    ${scan_level}    ${expected_count}
    ${params}    Create Dictionary
    ...    scan_level=${scan_level}
    ...    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/objects    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200
    ${response_data}    Set Variable    ${response.json()}
    Should Be Equal As Integers
    ...    ${response_data["count"]}
    ...    ${expected_count}
    ...    Scan Level Filter should return ${expected_count} objects for scan level ${scan_level}
    Length Should Be    ${response_data["items"]}    ${expected_count}

Verify Scan Profile Mutation Queue
    [Arguments]    ${reference}    ${scan_levels}
    ${messages}    Get Messages From Queue    ${SCAN_PROFILE_MUTATION_QUEUE}    ack_requeue_true
    FOR    ${message}    IN    @{messages}
        ${payload}    Evaluate    json.loads("""${message["payload"]}""")    json
        IF    "${payload['primary_key']}" == "${reference}"
            ${expected_scan_level}    Remove From List    ${scan_levels}    0

            Should Be Equal As Integers
            ...    ${payload["value"]["scan_profile"]["level"]}
            ...    ${expected_scan_level}
            ...    Scan Level of ${reference} should be ${expected_scan_level} in the mutation queue
            @{reference_parts}    Split String    ${reference}    |
            Should Be Equal    ${payload["value"]["object_type"]}    ${reference_parts}[0]

            IF    ${scan_levels} == []    RETURN
        END
    END
    Fail    Scan Level of ${reference} should be mutated to ${scan_levels}[0]
