*** Settings ***
Library    sut.provisioning

*** Test Cases ***
Colon-Separated MAC Address Normalizes Correctly
    [Documentation]    MXL-103 - Acceptance Criteria 1
    ${result}=    Normalize Mac    aa:bb:cc:dd:ee:ff
    Should Be Equal As Strings    ${result}    AA:BB:CC:DD:EE:FF

Hyphen-Separated MAC Address Normalizes Correctly
    [Documentation]    MXL-103 - Acceptance Criteria 2
    ${result}=    Normalize Mac    AA-BB-CC-DD-EE-FF
    Should Be Equal As Strings    ${result}    AA:BB:CC:DD:EE:FF

Cisco Dotted MAC Address Normalizes Correctly
    [Documentation]    MXL-103 - Acceptance Criteria 3
    ${result}=    Normalize Mac    aabb.ccdd.eeff
    Should Be Equal As Strings    ${result}    AA:BB:CC:DD:EE:FF

Mixed-Case Hexadecimal Converts to Upper Case
    [Documentation]    MXL-103 - Acceptance Criteria 4
    ${result}=    Normalize Mac    1a:2b:3c:4d:5e:6f
    Should Be Equal As Strings    ${result}    1A:2B:3C:4D:5E:6F

Non-Hex Characters Raise ValueError
    [Tags]    RaisesError
    Run Keyword And Expect Error    ValueError*    Normalize Mac    gg:bb:cc:dd:ee:ff

Incorrect Number of Digits Raise ValueError
    [Tags]    RaisesError
    Run Keyword And Expect Error    ValueError*    Normalize Mac    aa:bb:cc