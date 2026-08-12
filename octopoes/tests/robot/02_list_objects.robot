*** Settings ***
Resource            robot.resource

Test Setup          Setup Test
Test Teardown       Teardown Test


*** Test Cases ***
List Objects
    Insert Normalizer Output
    Await Sync
    Object List Should Contain    ${REF_HOSTNAME}
    Total Object Count Should Be    ${6}

List Objects With Filter
    Insert Normalizer Output
    Await Sync
    Verify Object List With Filter

List Objects With SearchString
    Insert Normalizer Output
    Await Sync
    Verify Object List With SearchString

List Random Objects With Filter
    Insert Normalizer Output
    Await Sync
    Declare Scan Profile    ${REF_HOSTNAME}    ${1}
    Await Sync
    Recalculate Scan Profiles
    Await Sync
    Length Of Random Object List With Filter Should Be    ${1}    ${5}
    Length Of Random Object List With Filter Should Be    ${0}    ${9}
    Length Of Random Object List With Filter Should Be    ${{ [1,0] }}    ${10}
    Length Of Random Object List With Filter Should Be    ${{ [2,3] }}    ${0}

Load Bulk
    Insert Normalizer Output
    Await Sync
    ${references}    Create List    ${REF_HOSTNAME}    ${REF_IPADDR}    ${REF_RESOLVEDHOSTNAME}
    Verify Bulk Load    ${references}


*** Keywords ***
Verify Object List With Filter
    ${response_data}    Get Objects With ScanLevel 0
    Should Be Equal    ${response_data["count"]}    ${6}

Get Objects With ScanLevel 0
    ${params}    Create Dictionary    scan_level=0    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/objects    params=${params}
    ${response_data}    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${response.status_code}    200
    RETURN    ${response_data}

Verify Object List With SearchString
    ${response_data}    Get Objects With SearchString example.com
    Should Be Equal    ${response_data["count"]}    ${4}

Get Objects With SearchString example.com
    ${params}    Create Dictionary    search_string=example.com    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/objects    params=${params}
    ${response_data}    Set Variable    ${response.json()}
    Should Be Equal As Integers    ${response.status_code}    200
    RETURN    ${response_data}

Length Of Random Object List With Filter Should Be
    [Arguments]    ${scan_levels}    ${expected_length}
    ${params}    Create Dictionary    scan_level=${scan_levels}    amount=10    valid_time=${VALID_TIME}
    ${response}    Get    ${OCTOPOES_URI}/objects/random    params=${params}
    Should Be Equal As Integers    ${response.status_code}    200
    Length Should Be    ${response.json()}    ${expected_length}

Verify Bulk Load
    [Arguments]    ${references}
    ${params}    Create Dictionary    valid_time=${VALID_TIME}
    ${response}    Post    ${OCTOPOES_URI}/objects/load_bulk    json=@{references}    params=${params}
    Log    ${response.json()}
    Should Be Equal As Integers    ${response.status_code}    200
    FOR    ${reference}    IN    @{references}
        Dictionary Should Contain Key    ${response.json()}    ${reference}
    END
