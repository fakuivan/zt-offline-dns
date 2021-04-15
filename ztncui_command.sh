#!/usr/bin/env bash
set -euo pipefail

eval_on_ztncui () {
    # shellcheck disable=1090
    (source ~/containers/ztncui.sh && ztncui-compose exec -T ztncui bash -c "$1"); return $?
}

# Arguments are escaped, last argument gets the address of the server prepended, auth token is added to the header
curl_on_ztncui () {
    # shellcheck disable=2016
    eval_on_ztncui 'curl -s --header "X-ZT1-Auth: $ZT_TOKEN" '"$(printf "%q " "${@:1:$#-1}")"'"$ZT_ADDR"/'"$(printf "%q " "${@: -1}")"
}

url_escape () {
    printf '%s' "$1" | jq -sRr '@uri'
}

json_array() {
    local -a args=( )
    local jq_expr='['
    local i=0 name
    for arg in "$@"; do
        name="var$i"
        jq_expr+=' $'"$name,"
        args+=( --arg "$name" "$arg" )
        ((i++))
    done
    jq_expr+=" null][:-1]"
    echo '[]' | jq "${args[@]}" "$jq_expr"
}

set_dns_params () {
    local path domain servers_json
    path=controller/network/"$(url_escape "$1")"
    domain="$2"
    shift 2
    servers_json="$(json_array "$@")"
    curl_on_ztncui -X GET "$path" |
        jq --arg domain "$domain" \
           --argjson servers "$servers_json" \
           '.dns={ $domain, $servers }' |
        curl_on_ztncui -X POST -d @- "$path"

}

with_network () {
    local path verb nwid
    nwid="$1"
    path=controller/network/"$(url_escape "$nwid")"
    verb="$2"
    shift 2
    case "$verb" in
        'get_pa_modes')
            curl_on_ztncui -X GET "$path" |
                jq '.v6AssignMode | {
                    "6plane": .["6plane"],
                    "rfc4193": .rfc4193
                    }'
            ;;
        'set_dns_params')
            set_dns_params "$nwid" "$@"
            ;;
        'get_member_ips')
            path+=/member/"$(url_escape "$1")"
            curl_on_ztncui -X GET "$path" | jq '.ipAssignments'
            ;;
        *)
            echo "$0: invalid verb ${verb@Q}" 1>&2
            ;;
    esac
}

case "$1" in
    "get_networks")
        curl_on_ztncui -X GET controller/network/ | jq .
        ;;
    "with_network")
        shift
        with_network "$@"
        ;;
    *)
        echo "$0: invalid command ${1@Q}" 1>&2
        ;;
esac
