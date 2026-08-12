*** Settings ***
Resource            robot.resource

Test Setup          Setup Test
Test Teardown       Teardown Test


*** Test Cases ***
Simple Scan Profile Inheritance
    Declare Scan Profile    ${REF_HOSTNAME}    ${4}
    Recalculate Scan Profile Propagation
    ${response_data}    Get Scan Profile Inheritance    ${REF_IPADDR}
    Length Should Be    ${response_data}    3
    Should Be Equal As Strings    ${response_data[1]["reference"]}    ${REF_RESOLVEDHOSTNAME}


*** Keywords ***
Setup Test
    robot.Setup Test
    Insert Normalizer Output
    Await Sync

Get Scan Profile Inheritance
    [Arguments]    ${reference}
    ${params}    Create Dictionary    reference=${reference}    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/scan_profiles/inheritance    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200
    ${response_data}    Set Variable    ${response.json()}
    RETURN    ${response_data}

Recalculate Scan Profile Propagation
    ${params}    Create Dictionary    sync=true    valid_time=${VALID_TIME}
    Get    ${OCTOPOES_URI}/scan_profiles/recalculate    params=${params}
