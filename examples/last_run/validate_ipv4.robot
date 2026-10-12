*** Settings ***
Library    sut.provisioning

*** Test Cases ***
'192.168.1.10' returns True
    ${result}=    Validate Ipv4    192.168.1.10
    Should Be True    ${result}

'0.0.0.0' returns True
    ${result}=    Validate Ipv4    0.0.0.0
    Should Be True    ${result}

'255.255.255.255' returns True
    ${result}=    Validate Ipv4    255.255.255.255
    Should Be True    ${result}

'256.1.1.1' returns False
    ${result}=    Validate Ipv4    256.1.1.1
    Should Not Be True    ${result}

'1.2.3' returns False
    ${result}=    Validate Ipv4    1.2.3
    Should Not Be True    ${result}

'192.168.01.1' returns False
    ${result}=    Validate Ipv4    192.168.01.1
    Should Not Be True    ${result}
    
'' (empty string) returns False
    ${result}=    Validate Ipv4    ${EMPTY}
    Should Not Be True    ${result}