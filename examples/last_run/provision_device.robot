*** Settings ***
Library    sut.provisioning

*** Test Cases ***
Example1 - Valid Config returns {'status': 'ok', 'errors': []}
    ${config}=    Evaluate    {"ip": "192.168.1.1", "bandwidth": "100Mbps"}
    ${expected_result}=    Evaluate    '{"status":"ok","errors":[]}'
    ${actual_result}=    Provision Device    ${config}
    Log To Console    Actual Result = '${actual_result}' Expected Result = '${expected_result}'
    Should Equal As Strings    ${actual_result}    ${expected_result}

Example2 - Missing IP key adds error and status='error'
    ${config}=    Evaluate    {"bandwidth": "100Mbps"}
    ${expected_result}=    Evaluate    '{"status":"error","errors":["missing \'ip\'"]}'
    ${actual_result}=    Provision Device    ${config}
    Log To Console    Actual Result = '${actual_result}' Expected Result = '${expected_result}'
    Should Be Equal As Strings    ${actual_result['status']}    "${expected_result['status']}"
    For Each    @{ERRORS:=${actual_result['errors']}}
        Should Contain String     ${ERRORS[0]}   missing ip'

Example3 - Missing Bandwidth key adds error and status='error'
    ${config}=    Evaluate    {"ip": "192.168.1.1"}
    ${expected_result}=    Evaluate    '{"status":"error","errors":["missing \'bandwidth\'"]}'
    ${actual_result}=    Provision Device    ${config}
    Log To Console    Actual Result = '${actual_result}' Expected Result = '${expected_result}'
    Should Be Equal As Strings    ${actual_result['status']}    "${expected_result['status']}"
    For Each    @{ERRORS:=${actual_result['errors']}} 
        Should Contain String     ${ERRORS[0]}  missing 'bandwidth''

Example4 - Invalid IPv4 address reports error and status='error'
    ${config}=    Evaluate    {"ip": "999.1.1.1", "bandwidth": "100Mbps"}
    ${expected_result}=    Evaluate    '{"status":"error","errors":["invalid ip: \'999.1.1.1\'"]}'
    ${actual_result}=    Provision Device    ${config}
    Log To Console    Actual Result = '${actual_result}' Expected Result = '${expected_result}'
    Should Be Equal As Strings    ${actual_result['status']}    "${expected_result['status']}"
    For Each    @{ERRORS:=${actual_result['errors']}}
        Should Match Regexp      ${ERRORS[0]}       invalid ip.*"999\.1\.\d+\."$