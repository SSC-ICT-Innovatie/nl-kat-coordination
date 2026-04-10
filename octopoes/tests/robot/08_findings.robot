*** Settings ***
Library             OperatingSystem
Library             RequestsLibrary
Library             DateTime
Library             String
Resource            robot.resource

Test Setup          Setup Test
Test Teardown       Teardown Test


*** Test Cases ***
List Findings
    Insert Observation    tests/fixtures/normalizer_output_nxdomain.json
    Declare Scan Profile    Hostname|internet|example.com    1
    Await Sync

    Finding List Should Have Length    1
    Finding Count Per Severity Should Be    'pending'    1
    Finding Count Per Severity Should Be    'low'    0
    Finding Count Per Severity Should Be    'critical'    0


*** Keywords ***
Setup Test
    robot.Setup Test
    Insert Normalizer Output
    ${params}    Create Dictionary    valid_time=${VALID_TIME}
    ${response}    Post    ${OCTOPOES_URI}/bits/recalculate    params=${params}
    Await Sync

List Findings
    ${params}    Create Dictionary    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/findings    params=${params}
    ${response_data}    Set Variable    ${response.json()}
    RETURN    ${response_data}

Get Count Per Severity
    ${params}    Create Dictionary    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/findings/count_by_severity    params=${params}
    ${response_data}    Set Variable    ${response.json()}
    RETURN    ${response_data}

Finding List Should Have Length
    [Arguments]    ${expected_length}
    ${findings}    List Findings
    Should Be Equal As Integers
    ...    ${findings['count']}
    ...    ${expected_length}
    ...    Expected count of finding list was not as expected
    Length Should Be
    ...    ${findings['items']}
    ...    ${expected_length}
    ...    Expected length of finding list was not as expected

Finding Count Per Severity Should Be
    [Arguments]    ${severity}    ${expected_counts}
    ${counts}    Get Count Per Severity
    Should Be Equal As Integers
    ...    ${counts[${severity}]}
    ...    ${expected_counts}
    ...    Expected count of finding count per severity was not as expected
