*** Settings ***
Library    SSHLibrary
Library    Collections
Suite Setup    Connect to the node

*** Variables ***
${module_id}    ${EMPTY}

*** Keywords ***
Run action
    [Arguments]    ${action}    ${data}=${EMPTY}    ${expected}=0
    ${command} =    Set Variable    api-cli run module/${module_id}/${action}
    IF    $data != ''    ${command} =    Set Variable    ${command} --data '${data}'
    ${output}    ${rc} =    Execute Command    ${command}    return_rc=True
    Should Be Equal As Integers    ${rc}    ${expected}
    RETURN    ${output}

*** Test Cases ***
Install a guarded C1 skeleton
    ${output}    ${rc} =    Execute Command    add-module ${IMAGE_URL} 1    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${result} =    Evaluate    json.loads($output)    modules=json
    Set Global Variable    ${module_id}    ${result['module_id']}

Report incomplete setup and sanitized configuration
    ${output} =    Run action    get-configuration
    ${result} =    Evaluate    json.loads($output)    modules=json
    Should Not Be True    ${result['configured']}
    Should Be Equal    ${result['state']}    blocked
    Should Be Empty    ${result['administration_url']}
    ${output} =    Run action    get-integration-status
    ${result} =    Evaluate    json.loads($output)    modules=json
    Should Not Be True    ${result['authentication_ready']}
    Should Not Be True    ${result['bootstrap_ready']}

Reject unsupported configuration keys
    Run action    configure-module    {"C1_CRASH_AFTER":"commit"}    10

Start only private backends
    Run action    start-backends    {}
    ${output}    ${rc} =    Execute Command    runagent -m ${module_id} podman ps --format '{{.Names}}'    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Contain    ${output}    cone-postgres
    Should Contain    ${output}    cone-terminusdb
    Should Contain    ${output}    cone-openfga
    Should Not Contain    ${output}    keycloak
    Should Not Contain    ${output}    cone-app

C1 startup and backup remain guarded
    ${rc} =    Execute Command    runagent -m ${module_id} check-production-contract    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    4
    ${rc} =    Execute Command    runagent -m ${module_id} module-dump-state    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    4

Remove only this disposable skeleton
    ${rc} =    Execute Command    remove-module --no-preserve ${module_id}    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
