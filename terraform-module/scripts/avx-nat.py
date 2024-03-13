'''
1 - Receber lista de IP e porta (locais) que serão expostos pelo AVX (inputs.yaml)
2 - Login AVX pela API
3 - Obter os NATs já existentes (GET) de um gateway específico (TODOS, não somente os marcados com 66001)
4 - Criar uma lista dos NATs obtidos do AVX (todos) para comparar com os NATs do inputs.yaml (inputados pelos usuários)
5 - Comparar a lista de NATs do AVX (todos) com os inputs.yaml (Não pode haver nenhuma regra NAT com o mesmo ip e porta (local) - É um AND)
6 - Comparar se lista de NATs do AVX (marcados com "66001") com os inputs.yaml (Não pode haver nenhuma regra NAT com o mesmo ip e porta (local) - É um AND)
7 - Criar uma lista completa com os NATs já existentes (com mark) e os inputs (AVX NATs + Inputs não duplicados)
8 - Submeter lista com novos inputs (inclusão/edição/exclusão)


Tem que dar um get no arquivo dos nats após fazer o post também
Garantir que o conteúdo do inputs.yaml exista no Aviatrix, mas que não altere as regras já existentes no Aviatrix (que não estejam no inputs.yaml)
Verificar se é DEV, STG ou PRD para definir se terá replicação com HA ou não.
Falta adicionar na lista os novos nats adicionados na lista inputs.yaml.
Falta também add todos os nats já existentes (que não sejam default) na lista de inputs.yaml e também o mark neles no Aviatrix
'''

import json
import os
import re
import sys
import requests
import yaml

controller_cid = None
controller_url = "avx-controller.company.com.br"
controller_username = os.environ["AVX_USERNAME"]
controller_password = os.environ["AVX_PASSWORD"]
gateway_name = sys.argv[1]
inputs_path = sys.argv[2]
initial_port = 60000
mark_dnat = "66001"
environment = sys.argv[3]
location = sys.argv[4]
hub_name = "avx-south-central-us-firenet"
sync_to_ha = False
if environment != "dev":
    sync_to_ha = True
if location != "southcentralus":
    hub_name = "avx-brazil-south-firenet"


def aviatrix_login():
    payload = {
        "action": "login",
        "username": controller_username,
        "password": controller_password
    }
    request = requests.post(f'https://{controller_url}/v1/api', data=payload)
    if request.status_code != 200:
        print("Não foi possível fazer login no Aviatrix")
        return False
    response = request.json()
    cid = response["CID"]
    return cid


def create_nat_set(nat_list):
    all_nats_set = set()  # duplicado ou nao - tupla com porta e ip
    all_nats_obj = {}

    for nat in nat_list:
        src_ip = dst_ip = dst_port = protocol = interface = connection = new_dst_ip = new_dst_port = apply_route_entry = None

        try:
            src_ip = nat["src_ip"]
        except:
            pass
        try:
            dst_ip = nat["dst_ip"]
        except:
            pass
        try:
            dst_port = nat["dst_port"]
        except:
            pass
        try:
            protocol = nat["protocol"]
        except:
            pass
        try:
            interface = nat["interface"]
        except:
            pass
        try:
            connection = nat["connection"]
        except:
            pass
        try:
            new_dst_ip = nat["new_dst_ip"]
        except:
            pass
        try:
            new_dst_port = nat["new_dst_port"]
        except:
            pass
        try:
            apply_route_entry = nat["apply_route_entry"]
        except:
            pass
        all_nats_set.add((new_dst_ip, new_dst_port))
        all_nats_obj[f'{new_dst_ip},{new_dst_port}'] = {
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "protocol": protocol,
            "interface": interface,
            "connection": connection,
            "new_dst_ip": new_dst_ip,
            "new_dst_port": new_dst_port,
            "apply_route_entry": apply_route_entry
        }
    return {
        "nats_dedup": all_nats_set,
        "nats_obj": all_nats_obj
    }


def remove_duplicated_nats(input_nats, all_nats):
    result_compare = []
    for nat in input_nats:
        if (nat["ip"], nat["port"]) in all_nats:
            # print("Essa regra de DNAT já existe! ({}:{})".format(nat["ip"], nat["port"]))
            continue
        result_compare.append(nat)
    return result_compare


def update_marked_with_inputs(input_nats, all_nats):
    result_compare = []
    port = 0
    advertise_ip = None
    for nat in all_nats:
        advertise_ip = nat["dst_ip"]
        # Verifica se a regra DNAT da lista de TODOS os NATs do Avx possui o mark 66001
        if 'mark' in nat and nat["mark"] == mark_dnat:
            nat_port = nat["dst_port"]
            if int(nat_port) > int(port):
                port = nat_port
            # Verifica se a regra dnat consta no inputs.yaml
            if any(nat['new_dst_ip'] == input_nat['ip'] and nat['new_dst_port'] == input_nat['port'] for input_nat in input_nats):
                # Adiciona na nova lista do result_compare
                result_compare.append(nat)
                # print("Essa regra de DNAT EXISTE nos inputs.yaml ({}:{})".format(nat["new_dst_ip"], nat["new_dst_port"]))
            else:
                print("\033[1;31m ===================================================================== \033[0m")
                print("\033[1;31m |PLAN| -> Essa regra de DNAT não existe mais no arquivo inputs.yaml, portanto será EXCLUÍDA: ({}:{}) \033[0m".format(
                    nat["new_dst_ip"], nat["new_dst_port"]))
        else:  # Se não tiver o mark 66001 na regra da lista ALL, adiciona na nova lista do result_compare
            result_compare.append(nat)
    return {"result_compare": result_compare, "max_port": port, "advertise_ip": advertise_ip}


def aviatrix_get_nats(CID, gateway_name):
    request = requests.get(
        f'https://{controller_url}/v1/api?action=get_gateway_dnat_config&CID={CID}&gateway_name={gateway_name}')
    result = request.json()
    nats = json.loads(result["results"])
    # print(nats)
    return nats


def aviatrix_post_nats(CID, gateway_name, policies, sync_to_ha):
    payload = {
        "action": "update_dnat_config",
        "CID": CID,
        "gateway_name": gateway_name,
        "policy_list": json.dumps(policies),
        "sync_snat_to_ha": sync_to_ha
    }
    #print("Payload do POST do AVX: ({})".format(payload))
    #print(json.dumps(payload))
    #print(policies)



    request = requests.post(f'https://{controller_url}/v1/api', data=payload)
    if request.status_code != 200:
            print("Não foi possível adicionar/editar/excluir a regra DNAT no Aviatrix")
            result = request.json()
            #result_return = result["return"] #json.loads(result["return"])
            #result_reason = result["reason"] #json.loads(result["reason"])
            #print(result_return)
            return False
    result = request.json()
    if 'reason' in result and 'unchanged' in result['reason']:
        print(f"\033[1;32m ===================================================================== \033[0m")
        print(f"\033[1;32m |APPLY| -> NENHUMA MUDANÇA FOI REALIZADA: \n\033[1;32m{result}\033[0m")
    if 'return' in result and result['return'] == False and 'unchanged' not in result['reason']:
        print(f"\033[1;31m ===================================================================== \033[0m")
        print(f"\033[1;31m |APPLY| -> OCORREU O ERRO ABAIXO NA EXECUÇÃO: \n\033[1;31m{result} \033[0m")
    if 'return' in result and result['return'] == True:
        print(f"\033[1;32m ===================================================================== \033[0m")
        print(f"\033[1;32m |APPLY| -> AS ALTERAÇÕES SOLICITADAS FORAM REALIZADAS: \n\033[1;32m{result} \033[0m")
    
    print("======================")
    print(request.status_code)
    print(result)
    #result_nats = json.loads(result["return","reason"])
    return result



# PASSO 1
count = 0
while count < 9:
    if os.path.exists(f"{inputs_path}/inputs.yaml"):
        print(f"O diretório: {inputs_path}, existe!")
        break
    
    inputs_path = inputs_path.rstrip('/')
    parts = inputs_path.split('/')
    number_part = parts[3]
    
    try:
        current_number = int(number_part)
    except ValueError:
        current_number = 1

    if current_number >= 1 and current_number <= 9:
        next_number = (current_number % 9) + 1
        parts[3] = str(next_number)
        inputs_path = '/'.join(parts)
        count += 1
    else:
        print("O número atual não está no intervalo de 1 a 9.")
        break

if os.path.exists(f"{inputs_path}/inputs.yaml"):
    with open(f"{inputs_path}/inputs.yaml", "r") as f:
        input_nats = yaml.safe_load(f)
    """     print("==============INPUT_NATS(todos do arquivo inputs.yaml)==============")
    print(input_nats)
    print(len(input_nats))
    print("=====================================================================") """
    input_nats_obj = {}
    for input in input_nats:
        input_nats_obj[f'{input["ip"]},{input["port"]}'] = input
else:
    print("O arquivo não foi encontrado em nenhum dos locais.")


# PASSO 2
cid = aviatrix_login()
if not cid:
    print("Não foi possível fazer login no Aviatrix")
    sys.exit()

# PASSO 3
nats = aviatrix_get_nats(cid, gateway_name)
""" print("==============NATS(todos do avx, inclusive os sem mark)==============")
print(nats)
print(len(nats))
print("=====================================================================") """


# PASSO 6
updated_mark_nats = update_marked_with_inputs(input_nats, nats)
""" print("==============UPDATED_NATS(Compilado com todos que tem e não tem mark, menos os que não estão mais no arquivo inputs.yaml)==============")
print(updated_mark_nats)
print(len(updated_mark_nats))
print("=====================================================================") """

# PASSO 4
all_nats = create_nat_set(updated_mark_nats["result_compare"])
#print(all_nats["nats_obj"])
# print(all_nats["nats_dedup"])

# PASSO 5
deduplicated_nats = remove_duplicated_nats(input_nats, all_nats["nats_dedup"])
if deduplicated_nats:
    print(f"\033[1;32m ===================================================================== \033[0m")
    print("\033[1;32m |PLAN| -> Essas regras de DNAT foram adicionadas ou alteradas no arquivo inputs.yaml, portanto serão CRIADAS: \033[0m")
    for item in deduplicated_nats:
        print(f"\033[1;32m{json.dumps(item)}\033[0m")

deduplicated_nats_objects = []
max_port = updated_mark_nats["max_port"]
max_port = int(max_port)
if max_port < 60000:
    max_port = initial_port

for rule in deduplicated_nats:
    new_port = int(max_port)+1
    result = {
        "src_ip": "0.0.0.0/0",
        "src_port": "",
        "dst_ip": updated_mark_nats["advertise_ip"],
        "dst_port": str(new_port),
        "protocol": input_nats_obj[f'{rule["ip"]},{rule["port"]}']["protocol"],
        "interface": None,
        "connection": hub_name,
        "mark": "66001",
        "new_dst_ip": str(rule["ip"]),
        "new_dst_port": str(rule["port"]),
        "apply_route_entry": True,
        "exclude_rtb": ""
    }
    max_port = new_port
    deduplicated_nats_objects.append(result)
#print(deduplicated_nats_objects)


#PASSO 8
post_rules = deduplicated_nats_objects+updated_mark_nats["result_compare"]
post_nats = aviatrix_post_nats(cid, gateway_name,post_rules,sync_to_ha)
post_nats_ha = None
if environment != "dev":
    gateway_name_ha = f"{gateway_name}-hagw"
    post_nats_ha = aviatrix_post_nats(cid, gateway_name_ha,post_rules,sync_to_ha)

#print("Post_nats: ({})".format(post_nats))

if 'results' in post_nats:
    if "Successfully updated" in post_nats['results']:
        pattern = r"gateway (.*?) DNAT"
        match = re.search(pattern, post_nats['results'])
        if match:
            spoke_name = match.group(1)
        print_separator = True
        if deduplicated_nats:
            for item in deduplicated_nats:
                ip = item["ip"]
                for rule in post_rules:
                    if rule.get("new_dst_ip") == ip:
                        if print_separator:
                            print("\033[1;32m ===================================================================== \033[0m")
                            print(f"\033[1;32m Abaixo estão o(s) IP(s) e Porta(s) necessário(s) para a conexão desejada via DNAT da spoke {spoke_name}: \033[0m")
                            print_separator = False                   
                        print("\033[1;32m IP de NAT (acessível pela VPN): \033[1;32m", rule['dst_ip'].split('/')[0])
                        print("\033[1;32m Porta do NAT: \033[1;32m", rule['dst_port'])
                        print("\033[1;32m IP local (interno da spoke): \033[1;32m", rule['new_dst_ip'])
                        print("\033[1;32m Porta local: \033[1;32m", rule['new_dst_port'])
                        print("\033[1;32m ---------------------------- \033[0m")

if post_nats_ha is not None:
    if 'results' in post_nats_ha:
        if "Successfully updated" in post_nats_ha['results']:
            print("\033[1;32m ===================================================================== \033[0m")
            print(f"\033[1;32m Regras sincronizadas com sucesso para o gateway ha \033[0m")
            print(post_nats_ha['results'])