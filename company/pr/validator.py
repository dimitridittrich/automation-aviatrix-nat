import os
import requests
import json
from azure.identity import EnvironmentCredential, CredentialUnavailableError
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient
import yaml

from os.path import abspath

root = abspath('../../')
path = abspath('../')

class SubscriptionManager:
    def __init__(self):
        try:
            self._client = SubscriptionClient(credential=EnvironmentCredential())
        except CredentialUnavailableError as error:
            message = ('Please, verify your environment variables. \n'
                       'Azure Key Vault needs: \n'
                       '"AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET" and "AZURE_TENANT_ID".')
            print(message)
            raise error
        except Exception as error:
            print(error)
            raise error

    def list_subs(self):
        try:
            page_result = self._client.subscriptions.list()
            result = [item for item in page_result]
            subs_infos=[]
            for item in result:
                subs_infos.append({ 'subscription_id': item.subscription_id,
                    'subscription_name': item.display_name
                })
            return subs_infos
        except Exception as error:
            print(error)
            raise error



subs = SubscriptionManager().list_subs()
subnets_result = []
azagents = []
#kvs =   []
pvt_edpt_zones =[]
token = EnvironmentCredential().get_token('https://management.azure.com/.default')
header={'Content-Type':'application/json', 'Authorization': "Bearer {}".format(token.token)}
# kvs_result = requests.get('https://dev.azure.com/company-SA/_apis/git/repositories/xxxxxxxxxxxxxxxxxx/items?scopePath=/components/baselinemanager.json&download=true&api-version=7.0',headers={'Content-Type':'application/json'},auth=("IAC",os.environ["AZURE_DEVOPS_EXT_PAT"]))
# resultjson = json.loads(kvs_result.content)
# kvs_obj =   {}
# for landigzone in resultjson:
#     kvs_obj[landigzone['name']] = landigzone



for sub in subs:
    print(sub)
    _sub_id = sub['subscription_id']
    _sub_name = sub['subscription_name']
    result = requests.get('https://management.azure.com/subscriptions/{0}/tagNames?api-version=2021-04-01'.format(_sub_id),headers=header)
    content = json.loads(result.content)
    tags = []
    for item in content['value']:
        if item['tagName'] == "landigzone":
            tag_value = item['values'][0]
            _landigzone_short_name = tag_value['tagValue']
            # try:
            #     landigzone = kvs_obj[_sub_name]
            #     kvs.append({'id':landigzone['kv_id'],
            #                 'name':landigzone['kv_name'],
            #                 'landigzone_alias':landigzone['alias'],
            #                 'landigzone_name':landigzone['name']})                
            # except:
            #     print("Essa subscription não tem KV de landigzone.")

            rgs = ResourceManagementClient(EnvironmentCredential(), _sub_id).resource_groups.list()
            for group in rgs:
                vnet_rg_name = group.name
                vnet_rg_id = group.id

                if "private-endpoint" in vnet_rg_name : 
                    pvt_edpt_zones.append({'rg_name': vnet_rg_name, 'rg_id':  vnet_rg_id})

                location = group.location
                if "network" in vnet_rg_name :
                    if "ingress" not in vnet_rg_name:
                        result = requests.get('https://management.azure.com/subscriptions/{0}/resourceGroups/{1}/providers/Microsoft.Network/virtualNetworks?api-version=2021-05-01'.format(_sub_id, vnet_rg_name),headers=header)
                        content = json.loads(result.content)
                        for item in content['value']:
                            try: 
                            
                                spoke_name = item['tags']['terraform.spoke.name']
                                spoke_alias = item['tags']['terraform.spoke.alias']
                                spoke_location = item['tags']['terraform.spoke.location']
                                spoke_environment = item['tags']['terraform.spoke.environment']

                            except: 
                                continue


                            vnet_name = item['name']
                            vnet_id = item['id']
  
                                
                            subnets = item['properties']['subnets']
                            for subnet in subnets:
                                if "AzureBastionSubnet" not in subnet['name']:
                                    subnets_result.append({'rg_name': vnet_rg_name,  
                                    'subnet_name': subnet['name'], 
                                    'subnet_id': subnet['id'], 
                                    'subscription_id': _sub_id, 
                                    'subscription_name': _sub_name, 
                                    'vnet_id': vnet_id, 
                                    'vnet_name': vnet_name, 
                                    'spoke_name': spoke_name, 
                                    'spoke_alias': spoke_alias,
                                    'spoke_location': spoke_location,
                                    'spoke_environment': spoke_environment ,
                                    'landigzone_short_name': _landigzone_short_name})


headers_pools={'Content-Type':'application/json', 'Accept': 'application/json'}
pools = requests.get('https://dev.azure.com/company-SA/_apis/distributedtask/pools?api-version=6.0',headers=headers_pools, auth=('iac', os.getenv("AZURE_DEVOPS_EXT_PAT")))
pools_content = json.loads(pools.content)

for az_pool in pools_content['value']:
    name = az_pool['name']
    if "azagent" in name:
        azagents.append(name)

old_subnets = []
old_zones = []
old_kvs = []

with open('{0}/subnets.json'.format(root), 'r') as file:
    subnets_json = json.loads(file.read())
    old_subnets  = subnets_json
    file.close()

with open('{0}/subnets.json'.format(root), 'w') as file:
    subnets =  [*subnets_result , *old_subnets]
    file.write(json.dumps(subnets))
    file.close()

# with open('{0}/kvs.json'.format(root), 'r') as file:
#     kvs_json = json.loads(file.read())
#     old_kvs  = kvs_json
#     file.close()

# with open('{0}/kvs.json'.format(root), 'w') as file:
#     _kvs =  [*kvs , *old_kvs]    
#     file.write(json.dumps(_kvs))
#     file.close()

with open('{0}/pvt_zones.json'.format(root), 'r') as file:
    pvt_zones_json = json.loads(file.read())
    old_zones = pvt_zones_json
    file.close()

with open('{0}/pvt_zones.json'.format(root), 'w') as file:
    zones =  [*pvt_edpt_zones ,*old_zones]
    file.write(json.dumps(zones))
    file.close()

with open('{0}/nat/azure-pipeline.yaml'.format(path), 'r') as file:
    document = yaml.full_load(file.read())
    parameters = document['parameters']
    _params = []
    for param in parameters:
        _param = param
        if param['name'] == "AGENT_POOL":
            _param['values'] = []
            for agent in azagents:
             _param['values'].append(agent)
        _params.append(_param)
    document['parameters'] = _params
    file.close()

with open('{0}/nat/azure-pipeline.yaml'.format(path), 'w') as f:
    yaml.dump(document, f ,sort_keys=False)
    f.close()

