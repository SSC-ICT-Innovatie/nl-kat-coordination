*** Settings ***
Resource        ../xxx.resource

Suite Setup     Browser Setup


*** Test Cases ***
I want to login as the default superuser for the first time
    Login As User For The First Time    robot@localhost    robotpassword

I want to add indemnifications
    Click    xpath=//a[@class="button"]
    Fill Text    xpath=//*[@id="id_name"]    Dev Org
    Fill Text    xpath=//*[@id="id_code"]    dev
    Click    "Submit"
    # Click    xpath=//button[contains(text(),"Submit")]
    Check Checkbox    css=#id_may_scan
    Check Checkbox    css=#id_am_authorized
    Click    "Submit"
    Get Title    equal    OpenKAT - step_4_trusted_acknowledge_clearance_level
