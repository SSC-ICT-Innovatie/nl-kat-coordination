*** Settings ***
Library     OTP
Library     Browser    strict=False
Library     DebugLibrary
Library     OperatingSystem


*** Keywords ***
Browser Setup
    Set Suite Variable    ${ROOT_URL}    localhost:8000
    New Browser    chromium    headless=${headless}    downloadsPath=/tmp
    New Context    acceptDownloads=True    viewport={'width': 1920, 'height': 1080}
    New Page    ${ROOT_URL}

Login As User For The First Time
    [Arguments]    ${email}    ${password}
    Click    "Login"
    Fill Text    css=#id_auth-username    ${email}
    Fill Text    css=#id_auth-password    ${password}
    Click    "Log in"
    ${otp-raw}    Get Attribute    css=#totp-input    value
    Set Global Variable    ${otp-raw-global}    ${otp-raw}
    ${otp-code}    get otp    ${otp-raw-global}
    Fill Text    css=#id_generator-token    ${otp-code}
    Click    "Authenticate"
    Click    "Start using OpenKAT"
    Get Title    equal    OpenKAT - step_1_introduction_registration

Login As User Normally
    [Arguments]    ${email}    ${password}
    Click    "Login"
    Fill Text    css=#id_auth-username    ${email}
    Fill Text    css=#id_auth-password    ${password}
    Click    "Log in"
    ${otp-code}    get otp    ${otp-raw-global}
    Fill Text    id=id_token-otp_token    ${otp-code}
    Click    "Submit"
    Get Text    .login-meta    contains    Logged in as:    error login failed

Logout Normally
    Click    "Logout"
    Get Element Count    .login-meta    ==    0    error still logged in

Generate First DNS Report
    Click    "Let\'s get started"
    Click    css=#main-content > section > div > p:nth-child(10) > a:nth-child(2)
    Click    "Let\'s choose a report"
    Click    "DNS report"
    Click    "Add URL"
    Fill Text    css=#id_raw    https://mispo.es
    Click    "Create object"
    Click    xpath=//*[@id="main-content"]/section/div/form/button
    Click    "Enable and start scan"
    Click    "Start scanning"
    Get Text    css=#main-content > section > div > h3    contains    Boefjes are scanning    boefjes are not scanning

Reload The Page Until Element Contains    # For the desired effect, should be called through: Wait Until Keyword Succeeds    60s    2s    Reload The Page Until Element Contains    url    selector    keyword
    [Arguments]    ${url}    ${selector}    ${keyword}
    Go to    ${url}
    Reload
    ${result}    Get Text    ${selector}    contains    ${keyword}    ${selector} does not contain ${keyword}
    Should Contain    ${result}    ${keyword}
