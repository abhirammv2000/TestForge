*** Settings ***
Library    sut.provisioning

*** Test Cases ***
100Mbps returns 100
    [Documentation]    '100Mbps' should parse to 100 Mbps
    ${result}=    Parse Bandwidth    100Mbps
    Should Be Equal As Integers    ${result}    100

1Gbps returns 1000
    [Documentation]    '1Gbps' should parse to 1000 Mbps
    ${result}=    Parse Bandwidth    1Gbps
    Should Be Equal As Integers    ${result}    1000

2000Kbps returns 2
    [Documentation]    '2000Kbps' should parse to 2 Mbps
    ${result}=    Parse Bandwidth    2000Kbps
    Should Be Equal As Integers    ${result}    2

50 returns 50
    [Documentation]    Bare number without unit is treated as Mbps
    ${result}=    Parse Bandwidth    50
    Should Be Equal As Integers    ${result}    50

1 gbps returns 1000
    [Documentation]    Case-insensitive and tolerant of internal spaces
    ${result}=    Parse Bandwidth    1 gbps
    Should Be Equal As Integers    ${result}    1000

5Tbps raises ValueError
    [Tags]    RaisesError
    Run Keyword And Expect Error    ValueError*    Parse Bandwidth    5Tbps

-1Mbps raises ValueError
    [Tags]    RaisesError
    Run Keyword And Expect Error    ValueError*    Parse Bandwidth    -1Mbps